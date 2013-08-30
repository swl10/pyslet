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
import pyslet.rfc4287 as atom
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

	def testCaseTypePromotion(self):
		"""If supported, binary numeric promotion SHOULD consist of the
		application of the following rules in the order specified:

		If either operand is of type Edm.Decimal, the other operand is converted to Edm.Decimal unless it is of type Edm.Single or Edm.Double."""
		self.failUnless(PromoteTypes(edm.SimpleType.Decimal,edm.SimpleType.Int64)==edm.SimpleType.Decimal,"Decimal promotion of Int64")
		self.failUnless(PromoteTypes(edm.SimpleType.Decimal,edm.SimpleType.Int32)==edm.SimpleType.Decimal,"Decimal promotion of Int32")
		self.failUnless(PromoteTypes(edm.SimpleType.Decimal,edm.SimpleType.Int16)==edm.SimpleType.Decimal,"Decimal promotion of Int16")
		self.failUnless(PromoteTypes(edm.SimpleType.Decimal,edm.SimpleType.Byte)==edm.SimpleType.Decimal,"Decimal promotion of Byte")
		#	Otherwise, if either operand is Edm.Double, the other operand is converted to type Edm.Double.
		self.failUnless(PromoteTypes(edm.SimpleType.Decimal,edm.SimpleType.Double)==edm.SimpleType.Double,"Double promotion of Decimal")
		self.failUnless(PromoteTypes(edm.SimpleType.Single,edm.SimpleType.Double)==edm.SimpleType.Double,"Double promotion of Single")
		self.failUnless(PromoteTypes(edm.SimpleType.Double,edm.SimpleType.Int64)==edm.SimpleType.Double,"Double promotion of Int64")
		self.failUnless(PromoteTypes(edm.SimpleType.Double,edm.SimpleType.Int32)==edm.SimpleType.Double,"Double promotion of Int32")
		self.failUnless(PromoteTypes(edm.SimpleType.Double,edm.SimpleType.Int16)==edm.SimpleType.Double,"Double promotion of Int16")
		self.failUnless(PromoteTypes(edm.SimpleType.Double,edm.SimpleType.Byte)==edm.SimpleType.Double,"Double promotion of Byte")
		#	Otherwise, if either operand is Edm.Single, the other operand is converted to type Edm.Single.
		self.failUnless(PromoteTypes(edm.SimpleType.Decimal,edm.SimpleType.Single)==edm.SimpleType.Single,"Single promotion of Decimal")
		self.failUnless(PromoteTypes(edm.SimpleType.Single,edm.SimpleType.Int64)==edm.SimpleType.Single,"Single promotion of Int64")
		self.failUnless(PromoteTypes(edm.SimpleType.Single,edm.SimpleType.Int32)==edm.SimpleType.Single,"Single promotion of Int32")
		self.failUnless(PromoteTypes(edm.SimpleType.Single,edm.SimpleType.Int16)==edm.SimpleType.Single,"Single promotion of Int16")
		self.failUnless(PromoteTypes(edm.SimpleType.Single,edm.SimpleType.Byte)==edm.SimpleType.Single,"Single promotion of Byte")		
		#	Otherwise, if either operand is Edm.Int64, the other operand is converted to type Edm.Int64.
		self.failUnless(PromoteTypes(edm.SimpleType.Int64,edm.SimpleType.Int32)==edm.SimpleType.Int64,"Int64 promotion of Int32")
		self.failUnless(PromoteTypes(edm.SimpleType.Int64,edm.SimpleType.Int16)==edm.SimpleType.Int64,"Int64 promotion of Int16")
		self.failUnless(PromoteTypes(edm.SimpleType.Int64,edm.SimpleType.Byte)==edm.SimpleType.Int64,"Int64 promotion of Byte")				
		#	Otherwise, if either operand is Edm.Int32, the other operand is converted to type Edm.Int32
		self.failUnless(PromoteTypes(edm.SimpleType.Int32,edm.SimpleType.Int16)==edm.SimpleType.Int32,"Int32 promotion of Int16")
		self.failUnless(PromoteTypes(edm.SimpleType.Int32,edm.SimpleType.Byte)==edm.SimpleType.Int32,"Int32 promotion of Byte")						
		#	Otherwise, if either operand is Edm.Int16, the other operand is converted to type Edm.Int16.
		self.failUnless(PromoteTypes(edm.SimpleType.Int16,edm.SimpleType.Byte)==edm.SimpleType.Int16,"Int16 promotion of Byte")						
		#	Special case, if either operand is null we return the type of the other operand
		self.failUnless(PromoteTypes(edm.SimpleType.Int16,None)==edm.SimpleType.Int16,"Int16 promotion of NULL")						
		self.failUnless(PromoteTypes(edm.SimpleType.Int32,None)==edm.SimpleType.Int32,"Int32 promotion of NULL")						
		self.failUnless(PromoteTypes(None,edm.SimpleType.Int64)==edm.SimpleType.Int64,"Int64 promotion of NULL")						
		self.failUnless(PromoteTypes(None,edm.SimpleType.Single)==edm.SimpleType.Single,"Single promotion of NULL")						
		try:
			PromoteTypes(edm.SimpleType.String,edm.SimpleType.Single)
			self.fail("Type promotion of String and Single")
		except EvaluationError:
			pass
		

class ODataURILiteralTests(unittest.TestCase):
	def testCaseNullLiteral(self):
		"""	nullLiteral = "null" """
		v=ParseURILiteral("null")
		self.failUnless(v.IsNull(),"null type IsNull")
		self.failUnless(v.typeCode is None,"null type: %s"%repr(v.typeCode))
		self.failUnless(v.pyValue is None,"null value: %s"%repr(v.pyValue))

	def testCaseBinaryLiteral(self):
		"""	binaryUriLiteral = caseSensitiveToken SQUOTE binaryLiteral SQUOTE
			binaryLiteral = hexDigPair
			caseSensitiveToken = "X" / "binary"
			; X is case sensitive binary is not
			hexDigPair = 2*HEXDIG [hexDigPair] """
		v=ParseURILiteral("X'0A'")
		self.failUnless(v.typeCode==edm.SimpleType.Binary,"binary type: %s"%repr(v.typeCode))
		self.failUnless(v.pyValue=='\x0a',"binary type: %s"%repr(v.pyValue))
		v=ParseURILiteral("X'0a'")
		self.failUnless(v.pyValue=="\x0a","binary type: %s"%repr(v.pyValue))
		try:
			v=ParseURILiteral("x'0a'")
			self.fail("Syntax error")
		except ValueError:
			pass
		v=ParseURILiteral("binary'0A'")
		self.failUnless(v.typeCode==edm.SimpleType.Binary,"binary type: %s"%repr(v.typeCode))
		self.failUnless(v.pyValue=='\x0a',"binary type: %s"%repr(v.pyValue))
		v=ParseURILiteral("BINARY'0A'")
		self.failUnless(v.typeCode==edm.SimpleType.Binary,"binary type: %s"%repr(v.typeCode))
		self.failUnless(v.pyValue=='\x0a',"binary type: %s"%repr(v.pyValue))
		# gotta love those recursive rules
		v=ParseURILiteral("X'deadBEEF'")
		self.failUnless(v.pyValue=="\xde\xad\xbe\xef","binary type: %s"%repr(v.pyValue))
		try:
			v=ParseURILiteral("X'de'ad")
			self.fail("Spurious data")
		except ValueError:
			pass
	
	def testCaseBooleanLiteral(self):
		"""booleanLiteral = true / false
			true = "true" / "1"
			false = "false" / "0"
		
		The spec is ambiguous here because 0 and 1 are valid literals for
		integer types."""
		v=ParseURILiteral("true")
		self.failUnless(v.typeCode==edm.SimpleType.Boolean,"boolean type: %s"%repr(v.typeCode))
		self.failUnless(v.pyValue is True,"boolean value: %s"%repr(v.pyValue))
		v=ParseURILiteral("false")
		self.failUnless(v.typeCode==edm.SimpleType.Boolean,"boolean type: %s"%repr(v.typeCode))
		self.failUnless(v.pyValue is False,"boolean value: %s"%repr(v.pyValue))

	def testCaseIntLiteral(self):
		"""byteLiteral = 1*3DIGIT;
		int16Literal= sign 1*5DIGIT
		int32Literal= sign 1*10DIGIT
		sbyteliteral= sign 1*3DIGIT	
		All returned as an int32 with python int value."""
		v=ParseURILiteral("0")
		self.failUnless(v.typeCode==edm.SimpleType.Int32,"0 type: %s"%repr(v.typeCode))
		self.failUnless(v.pyValue==0,"0 value: %s"%repr(v.pyValue))
		v=ParseURILiteral("1")
		self.failUnless(v.typeCode==edm.SimpleType.Int32,"1 type: %s"%repr(v.typeCode))
		self.failUnless(v.pyValue==1,"1 value: %s"%repr(v.pyValue))
		v=ParseURILiteral("2147483647")
		self.failUnless(v.typeCode==edm.SimpleType.Int32,"2147483647 type: %s"%repr(v.typeCode))
		self.failUnless(v.pyValue==2147483647,"2147483647 value: %s"%repr(v.pyValue))
		v=ParseURILiteral("0000000000")
		self.failUnless(v.typeCode==edm.SimpleType.Int32,"0000000000 type: %s"%repr(v.typeCode))
		self.failUnless(v.pyValue==0,"0000000000 value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-2147483648")
		self.failUnless(v.typeCode==edm.SimpleType.Int32,"-2147483648 type: %s"%repr(v.typeCode))
		self.failUnless(v.pyValue==-2147483648,"-2147483648 value: %s"%repr(v.pyValue))
		for bad in [ "00000000000", "2147483648", "-2147483649","+1" ]:
			try:
				v=ParseURILiteral(bad)
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
		v=ParseURILiteral("datetime'2012-06-30T23:59'")
		self.failUnless(v.typeCode==edm.SimpleType.DateTime,"date time type: %s"%repr(v.typeCode))
		self.failUnless(isinstance(v.pyValue,iso.TimePoint),"value type: %s"%repr(v.pyValue))
		self.failUnless(str(v.pyValue)=="2012-06-30T23:59:00","value: %s"%str(v.pyValue))
		v=ParseURILiteral("datetime'2012-06-30T23:59:59'")
		self.failUnless(v.typeCode==edm.SimpleType.DateTime,"date time type: %s"%repr(v.typeCode))
		self.failUnless(str(v.pyValue)=="2012-06-30T23:59:59","value: %s"%str(v.pyValue))
		v=ParseURILiteral("datetime'2012-06-30T23:59:59.9999999'")
		self.failUnless(v.typeCode==edm.SimpleType.DateTime,"date time type: %s"%repr(v.typeCode))
		self.failUnless(v.pyValue.GetCalendarString(ndp=-7)=="2012-06-30T23:59:59.9999999")
		# Now for the big one!
		v=ParseURILiteral("datetime'2012-06-30T23:59:60'")
		self.failUnless(v.typeCode==edm.SimpleType.DateTime,"date time type for leap second: %s"%repr(v.typeCode))
		self.failUnless(str(v.pyValue)=="2012-06-30T23:59:60","value for leap second: %s"%str(v.pyValue))
		v=ParseURILiteral("datetime'2012-06-30T24:00:00'")
		self.failUnless(v.typeCode==edm.SimpleType.DateTime,"date time extreme: %s"%repr(v.typeCode))
		self.failUnless(str(v.pyValue)=="2012-06-30T24:00:00","date time extreme: %s"%str(v.pyValue))
		# and now the crappy ones
		for crappy in [
			"datetime'2012-6-30T23:59:59'",
			"datetime'2012-06-1T23:59:59'",
			"datetime'2012-06-30T3:59:59'"
			]:
			v=ParseURILiteral(crappy)
			self.failUnless(v.typeCode==edm.SimpleType.DateTime,"date time type: %s"%repr(v.typeCode))
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
				v=ParseURILiteral(bad)
				self.fail("Bad parse: %s resulted in %s (%s)"%(bad,repr(v.pyValue),edm.SimpleType.EncodeValue(v.typeCode)))
			except ValueError:
				pass

	def testCaseDecimalLiteral(self):
		"""decimalUriLiteral = decimalLiteral
			("M"/"m")
			decimalLiteral = sign 1*29DIGIT
			["." 1*29DIGIT]
		All returned as a python Decimal instance."""
		v=ParseURILiteral("0M")
		self.failUnless(v.typeCode==edm.SimpleType.Decimal,"0M type: %s"%repr(v.typeCode))
		self.failUnless(isinstance(v.pyValue,decimal.Decimal),"0M value type: %s"%repr(v.pyValue))
		self.failUnless(v.pyValue==0,"0M value: %s"%repr(v.pyValue))
		v=ParseURILiteral("1.1m")
		self.failUnless(v.typeCode==edm.SimpleType.Decimal,"1.1m type: %s"%repr(v.typeCode))
		self.failUnless(isinstance(v.pyValue,decimal.Decimal),"1.1m value type: %s"%repr(v.pyValue))
		self.failUnless(v.pyValue*10==11,"1.1m value: %s"%repr(v.pyValue))
		v=ParseURILiteral("12345678901234567890123456789m")
		self.failUnless(v.typeCode==edm.SimpleType.Decimal,"29-digit type: %s"%repr(v.typeCode))
		self.failUnless(int(v.pyValue.log10())==28,"29-digit log10 value: %s"%repr(v.pyValue))
		v2=ParseURILiteral("12345678901234567890123456789.12345678901234567890123456789m")
		self.failUnless(v2.pyValue-v.pyValue<0.13 and v2.pyValue-v.pyValue>0.12,"29digit.29digit value: %s"%repr(v2.pyValue-v.pyValue))
		v=ParseURILiteral("-2147483648M")
		self.failUnless(v.typeCode==edm.SimpleType.Decimal,"-2147483648 type: %s"%repr(v.typeCode))
		self.failUnless(v.pyValue==-2147483648,"-2147483648 value: %s"%repr(v.pyValue))
		for bad in [ "123456789012345678901234567890m", "1.m", "1.123456789012345678901234567890m", "+1M" ]:
			try:
				v=ParseURILiteral(bad)
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
		v=ParseURILiteral("0D")
		self.failUnless(v.typeCode==edm.SimpleType.Double,"0D type: %s"%repr(v.typeCode))
		self.failUnless(type(v.pyValue) is FloatType,"0D value type: %s"%repr(v.pyValue))
		self.failUnless(v.pyValue==0,"0D value: %s"%repr(v.pyValue))
		v=ParseURILiteral("1.1d")
		self.failUnless(v.typeCode==edm.SimpleType.Double,"1.1d type: %s"%repr(v.typeCode))
		self.failUnless(type(v.pyValue) is FloatType,"1.1d value type: %s"%repr(v.pyValue))
		self.failUnless(v.pyValue*10==11,"1.1d value: %s"%repr(v.pyValue))
		v=ParseURILiteral("12345678901234567D")
		self.failUnless(v.typeCode==edm.SimpleType.Double,"17-digit type: %s"%repr(v.typeCode))
		self.failUnless(round(math.log10(v.pyValue),3)==16.092,"29-digit log10 value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-12345678901234567D")
		self.failUnless(v.typeCode==edm.SimpleType.Double,"17-digit negative type: %s"%repr(v.typeCode))
		self.failUnless(round(math.log10(-v.pyValue),3)==16.092,"29-digit log10 value: %s"%repr(v.pyValue))
		v=ParseURILiteral("123456789012345678901234567890.123456789012345678901234567890D")
		self.failUnless(v.typeCode==edm.SimpleType.Double,"30digit.30digit type: %s"%repr(v.typeCode))
		self.failUnless(round(math.log10(v.pyValue),3)==29.092,"30digit.30digit value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-123456789012345678901234567890.123456789012345678901234567890D")
		self.failUnless(round(math.log10(-v.pyValue),3)==29.092,"30digit.30digit negative value: %s"%repr(v.pyValue))
		v=ParseURILiteral(".142D")
		self.failUnless(v.pyValue==0.142,"Empty left value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-.142D")
		self.failUnless(v.pyValue==-0.142,"Empty left neg value: %s"%repr(v.pyValue))
		v=ParseURILiteral("3.D")
		self.failUnless(v.pyValue==3,"Empty right value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-3.D")
		self.failUnless(v.pyValue==-3,"Empty right neg value: %s"%repr(v.pyValue))
		v=ParseURILiteral(".D")
		self.failUnless(v.pyValue==0,"Empty left+right value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-.D")
		self.failUnless(v.pyValue==0,"Empty left+right neg value: %s"%repr(v.pyValue))
		v=ParseURILiteral("3.14159e000d")
		self.failUnless(round(v.pyValue,3)==3.142,"zero exp: %s"%repr(v.pyValue))
		v=ParseURILiteral("-123456789012345678901234567890.1234567890123456E1d")
		self.failUnless(round(math.log10(-v.pyValue),3)==30.092,"30.16 digits: %s"%repr(math.log10(-v.pyValue)))
		v=ParseURILiteral("NanD")
		self.failUnless(math.isnan(v.pyValue),"Nan double: %s"%repr(v.pyValue))
		v=ParseURILiteral("INFD")
		self.failUnless(v.pyValue>0 and math.isinf(v.pyValue),"Inf double: %s"%repr(v.pyValue))
		v=ParseURILiteral("-INFD")
		self.failUnless(v.pyValue<0 and math.isinf(v.pyValue),"Negative Inf double: %s"%repr(v.pyValue))		
		for bad in [ "123456789012345678D", "+1D", ".1e1d","+1.0E1d",
			"1.12345678901234567E10d","3.141Ed","3.141E1234d","3.141E+10d",".123E1D",
			"+NanD","-NanD","+INFD" ]:
			try:
				v=ParseURILiteral(bad)
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
		v=ParseURILiteral("0F")
		self.failUnless(v.typeCode==edm.SimpleType.Single,"0f type: %s"%repr(v.typeCode))
		self.failUnless(type(v.pyValue) is FloatType,"0f value type: %s"%repr(v.pyValue))
		self.failUnless(v.pyValue==0,"0f value: %s"%repr(v.pyValue))
		v=ParseURILiteral("1.1f")
		self.failUnless(v.typeCode==edm.SimpleType.Single,"1.1f type: %s"%repr(v.typeCode))
		self.failUnless(type(v.pyValue) is FloatType,"1.1f value type: %s"%repr(v.pyValue))
		self.failUnless(v.pyValue*10==11,"1.1f value: %s"%repr(v.pyValue))
		v=ParseURILiteral("12345678F")
		self.failUnless(v.typeCode==edm.SimpleType.Single,"8-digit type: %s"%repr(v.typeCode))
		self.failUnless(v.pyValue==12345678,"8-digit: %s"%repr(v.pyValue))
		v=ParseURILiteral("-12345678F")
		self.failUnless(v.typeCode==edm.SimpleType.Single,"8-digit negative type: %s"%repr(v.typeCode))
		self.failUnless(v.pyValue==-12345678,"8-digit neg value: %s"%repr(v.pyValue))
		v=ParseURILiteral("123456789012345678901234567890.123456789012345678901234567890f")
		self.failUnless(v.typeCode==edm.SimpleType.Single,"30digit.30digit type: %s"%repr(v.typeCode))
		self.failUnless(round(math.log10(v.pyValue),3)==29.092,"30digit.30digit value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-123456789012345678901234567890.123456789012345678901234567890F")
		self.failUnless(round(math.log10(-v.pyValue),3)==29.092,"30digit.30digit negative value: %s"%repr(v.pyValue))
		v=ParseURILiteral(".142f")
		self.failUnless(v.pyValue==0.142,"Empty left value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-.142F")
		self.failUnless(v.pyValue==-0.142,"Empty left neg value: %s"%repr(v.pyValue))
		v=ParseURILiteral("3.F")
		self.failUnless(v.pyValue==3,"Empty right value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-3.F")
		self.failUnless(v.pyValue==-3,"Empty right neg value: %s"%repr(v.pyValue))
		v=ParseURILiteral(".f")
		self.failUnless(v.pyValue==0,"Empty left+right value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-.F")
		self.failUnless(v.pyValue==0,"Empty left+right neg value: %s"%repr(v.pyValue))
		v=ParseURILiteral("3.14159e00F")
		self.failUnless(round(v.pyValue,3)==3.142,"zero exp: %s"%repr(v.pyValue))
		v=ParseURILiteral("-123456789012345678901234567890.12345678E1F")
		self.failUnless(round(math.log10(-v.pyValue),3)==30.092,"30.8 digits: %s"%repr(math.log10(-v.pyValue)))
		v=ParseURILiteral("3.E1F")
		self.failUnless(v.pyValue==30,"Empty right exp value: %s"%repr(v.pyValue))
		v=ParseURILiteral("NanF")
		self.failUnless(math.isnan(v.pyValue),"Nan single: %s"%repr(v.pyValue))
		v=ParseURILiteral("InfF")
		self.failUnless(v.pyValue>0 and math.isinf(v.pyValue),"Inf single: %s"%repr(v.pyValue))
		v=ParseURILiteral("-INFF")
		self.failUnless(v.pyValue<0 and math.isinf(v.pyValue),"Negative Inf single: %s"%repr(v.pyValue))		
		for bad in [ "123456789F", "+1F", ".1e1F","+1.0E1F",
			"1.123456789E10F","3.141EF","3.141E023F","3.141E+10F",".123E1F",
			"+NanF","-NanF","+INFF" ]:
			try:
				v=ParseURILiteral(bad)
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
		v=ParseURILiteral("guid'C0DEC0DE-C0DE-C0DE-C0DEC0DEC0DE'")
		self.failUnless(v.typeCode==edm.SimpleType.Guid,"guide type: %s"%repr(v.typeCode))
		self.failUnless(isinstance(v.pyValue,uuid.UUID),"guide type: %s"%repr(v.pyValue))
		self.failUnless(v.pyValue.hex.lower()=='c0dec0dec0dec0deffffc0dec0dec0de',"guid value (missing bytes): %s"%repr(v.pyValue))
		v=ParseURILiteral("guid'cd04f705-390c-4736-98dc-a3baa6b3a283'")
		self.failUnless(v.typeCode==edm.SimpleType.Guid,"guide type: %s"%repr(v.typeCode))
		self.failUnless(isinstance(v.pyValue,uuid.UUID),"guide type: %s"%repr(v.pyValue))
		self.failUnless(v.pyValue.hex.lower()=='cd04f705390c473698dca3baa6b3a283',"guid value (random): %s"%repr(v.pyValue))
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
				v=ParseURILiteral(bad)
				self.fail("Bad parse: %s"%bad)
			except ValueError:
				pass
	
	def testCaseInt64Literal(self):
		"""	int64UriLiteral= int64Literal ("L" / "l")
			int64Literal = sign 1*19DIGIT
			
			Return as a python long integer"""
		v=ParseURILiteral("0L")
		self.failUnless(v.typeCode==edm.SimpleType.Int64,"0L type: %s"%repr(v.typeCode))
		self.failUnless(type(v.pyValue)==LongType,"0L value type: %s"%repr(v.pyValue))
		self.failUnless(v.pyValue==0,"0L value: %s"%repr(v.pyValue))
		v=ParseURILiteral("1234567890123456789l")
		self.failUnless(v.typeCode==edm.SimpleType.Int64,"19-digit type: %s"%repr(v.typeCode))
		self.failUnless(v.pyValue==1234567890123456789L,"19-digit value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-1234567890123456789l")
		self.failUnless(v.typeCode==edm.SimpleType.Int64,"19-digit neg type: %s"%repr(v.typeCode))
		self.failUnless(v.pyValue==-1234567890123456789L,"19-digit neg value: %s"%repr(v.pyValue))
		for bad in [ "12345678901234567890L", "01234567890123456789l",
			 "+1l", "+0L" ]:
			try:
				v=ParseURILiteral(bad)
				self.fail("Bad parse: %s"%bad)
			except ValueError:
				pass

	def testCaseStringLiteral(self):
		"""stringUriLiteral = SQUOTE [*characters] SQUOTE
			characters = UTF8-char """
		v=ParseURILiteral("'0A'")
		self.failUnless(v.typeCode==edm.SimpleType.String,"string type: %s"%repr(v.typeCode))
		self.failUnless(v.pyValue=='0A',"string type: %s"%repr(v.pyValue))
		v=ParseURILiteral("'0a'")
		self.failUnless(v.pyValue=="0a","string type: %s"%repr(v.pyValue))
		v=ParseURILiteral("'Caf\xc3\xa9'")
		# When parsed from a URL we assume that %-encoding is removed
		# when the parameters are split leaving octet-strings that
		# are parsed.  So utf-8 encoding of strings must be removed
		# at the literal parsing stage
		self.failUnless(v.pyValue==u"Caf\xe9","unicode string type: %s"%repr(v.pyValue))
		# This next case is a shocker, the specification provides no way to escape SQUOTE
		# We support the undocumented doubling of the SQUOTE character.
		v=ParseURILiteral("'Peter O''Toole'")
		self.failUnless(v.pyValue==u"Peter O'Toole","double SQUOTE: %s"%repr(v.pyValue))
		v=ParseURILiteral("'Peter O%27Toole'")
		self.failUnless(v.pyValue==u"Peter O%27Toole","%%-encoding ignored: %s"%repr(v.pyValue))		
		for bad in [ "0A", "'0a","'Caf\xc3 Curtains'","'Peter O'Toole'"]:
			try:
				v=ParseURILiteral(bad)
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
		v=ParseURILiteral("time'P1Y2M3DT10H30M'")
		self.failUnless(v.typeCode==edm.SimpleType.Time,"date time type: %s"%repr(v.typeCode))
		self.failUnless(isinstance(v.pyValue,xsi.Duration),"value type: %s"%repr(v.pyValue))
		self.failUnless(str(v.pyValue)=="P1Y2M3DT10H30M","value: %s"%str(v.pyValue))		
		v=ParseURILiteral("time'-P120D'")
		self.failUnless(v.typeCode==edm.SimpleType.Time,"date time type: %s"%repr(v.typeCode))
		# There is no canonical representation so this is a weak test
		self.failUnless(str(v.pyValue)=="-P0Y0M120D","value: %s"%str(v.pyValue))
		for good in [
			"time'P1347Y'",
			"time'P1347M'",
			"time'P1Y2MT2H'",
			"time'P0Y1347M'",
			"time'P0Y1347M0D'",
			"time'-P1347M'"]:
			v=ParseURILiteral(good)
			self.failUnless(v.typeCode==edm.SimpleType.Time,"date time type: %s"%repr(v.typeCode))
			self.failUnless(isinstance(v.pyValue,xsi.Duration),"value type: %s"%repr(v.pyValue))
		for bad in [
			"time'P-1347M'",
			"time'P1Y2MT'",
			"time'P1Y2M3DT10H30M",
			"timeP1Y2M3DT10H30M'",
			"P1Y2M3DT10H30M"
			]:
			try:
				v=ParseURILiteral(bad)
				self.fail("Bad parse: %s resulted in %s (%s)"%(bad,str(v.pyValue),edm.SimpleType.EncodeValue(v.typeCode)))
			except ValueError:
				pass

	def testCaseDateTimeOffsetLiteral(self):
		"""
		dateTimeOffsetUriLiteral = "datetimeoffset" SQUOTE dateTimeOffsetLiteral SQUOTE
		dateTimeOffsetLiteral = <Defined by the lexical representation for datetime (including timezone offset) in [XMLSCHEMA2/2]>
		
		We test by using the examples from XMLSchema"""
		v=ParseURILiteral("datetimeoffset'2002-10-10T12:00:00-05:00'")
		self.failUnless(v.typeCode==edm.SimpleType.DateTimeOffset,"date time offset type: %s"%repr(v.typeCode))
		self.failUnless(isinstance(v.pyValue,iso.TimePoint),"value type: %s"%repr(v.pyValue))
		self.failUnless(isinstance(v.pyValue,iso.TimePoint),"value type: %s"%repr(v.pyValue))
		for good in [
			"datetimeoffset'2002-10-10T17:00:00Z'",
			"datetimeoffset'2002-10-10T12:00:00Z'",
			"datetimeoffset'2002-10-10T12:00:00+05:00'",
			"datetimeoffset'2002-10-10T07:00:00Z'",
			"datetimeoffset'2002-10-10T00:00:00+05:00'",
			"datetimeoffset'2002-10-09T19:00:00Z'"
			]:
			v=ParseURILiteral(good)
			self.failUnless(v.typeCode==edm.SimpleType.DateTimeOffset,"date time offset type: %s"%repr(v.typeCode))
			self.failUnless(isinstance(v.pyValue,iso.TimePoint),"value type: %s"%repr(v.pyValue))
		for bad in [
			"datetimeoffset'2002-10-10T17:00:00'",	# missing time zone
			"datetimeoffset'2002-10-10T17:00Z'",	# incomplete precision
			"datetimeoffset2002-10-10T17:00:00Z",	# missing quotes
			]:
			try:
				v=ParseURILiteral(bad)
				self.fail("Bad parse: %s resulted in %s (%s)"%(bad,str(v.pyValue),edm.SimpleType.EncodeValue(v.typeCode)))
			except ValueError:
				pass
	
			
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
	
	def testCaseQueryOptions(self):
		"""QueryOptions:
		
		Any number of the query options MAY<5> be specified in a data service URI.
		The order of Query Options within a URI MUST be insignificant.
		Query option names and values MUST be treated as case sensitive.
		System Query Option names MUST begin with a "$", as seen in System Query Option (section 2.2.3.6.1).
		Custom Query Options (section 2.2.3.6.2) MUST NOT begin with a "$".
		"""
		dsURI=ODataURI("Products()?$format=json&$top=20&$skip=10&space='%20'",'/x.svc')
		self.failUnless(dsURI.sysQueryOptions=={SystemQueryOption.format:'json',SystemQueryOption.top:'20',SystemQueryOption.skip:'10'},repr(dsURI.sysQueryOptions))
		self.failUnless(dsURI.queryOptions==["space='%20'"],'query options')
		dsURI=ODataURI("Products()?$top=20&space='%20'&$format=json&$skip=10",'/x.svc')
		self.failUnless(dsURI.sysQueryOptions=={SystemQueryOption.format:'json',SystemQueryOption.top:'20',SystemQueryOption.skip:'10'},repr(dsURI.sysQueryOptions))
		self.failUnless(dsURI.queryOptions==["space='%20'"],'query options')		
		try:
			dsURI=ODataURI("Products()?$unsupported=10",'/x.svc')
			self.fail("$unsupported system query option")
		except InvalidSystemQueryOption:
			pass

	def testCaseCommonExpressions(self):
		dsURI=ODataURI("Products()?$filter=substringof(CompanyName,%20'bikes')",'/x.svc')
		self.failUnless(isinstance(dsURI.sysQueryOptions[SystemQueryOption.filter],CommonExpression),"Expected common expression")
		# import pdb;pdb.set_trace()
		dsURI=ODataURI("Products()?$filter=true%20and%20false",'/x.svc')
		f=dsURI.sysQueryOptions[SystemQueryOption.filter]
		self.failUnless(isinstance(f,CommonExpression),"Expected common expression")
		self.failUnless(isinstance(f,BinaryExpression),"Expected binary expression, %s"%repr(f))
		self.failUnless(f.operator==Operator.boolAnd,"Expected and: %s"%repr(f.operator))		
		try:
			dsURI=ODataURI("Products()?$filter=true%20nand%20false",'/x.svc')
			self.fail("Expected exception for nand")
		except InvalidSystemQueryOption:
			pass
	
	def testCaseEvaluateCommonExpression(self):
		# cursory check:
		# a commonExpression must represent any and all supported common expression types
		p=Parser("true and false")
		e=p.ParseCommonExpression()
		self.failUnless(isinstance(e,CommonExpression),"Expected common expression")
		value=e.Evaluate(None)
		self.failUnless(isinstance(value,edm.SimpleValue),"Expected EDM value; found %s"%repr(value))
		self.failUnless(value.pyValue is False,"Expected false")
				
	def testCaseEvaluateBooleanExpression(self):
		# cursory check:
		# a boolCommonExpression MUST be a common expression that evaluates to the EDM Primitive type Edm.Boolean
		p=Parser("true and false")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.failUnless(value.pyValue is False,"Expected false")
				
	def testCaseEvaluateParenExpression(self):
		"""a parenExpression MUST be evaluated by evaluating the
		expression with the parentheses, starting with the innermost
		parenthesized expressions and proceeding outwards...

		...the result of the parenExpression MUST be the result of the
		evaluation of the contained expression."""
		p=Parser("(false and false or true)")		# note that or is the weakest operator
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is True,"Expected True")
		p=Parser("(false and (false or true))")		# should change the result
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is False,"Expected False")
		p=Parser("(((((((false) and (((false)) or true)))))))")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is False,"Expected False - multibrackets")
				
	def testCaseEvaluateBooleanParenExpression(self):
		"""Cursory check: a boolParenExpression MUST be evaluated by
		evaluating the expression with the parentheses. The result of
		the boolParenExpression MUST ... be of the EDM Primitive type
		Edm.Boolean"""
		p=Parser("(false and (false or true))")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.failUnless(value.pyValue is False,"Expected false")
	
	def testCaseEvaluateAddExpression(self):
		"""...operand expressions MUST evaluate to a value of one of the
		following EDM Primitive types:
			Edm.Decimal
			Edm.Double
			Edm.Single
			Edm.Int32
			Edm.Int64

		The addExpression SHOULD NOT be supported for any other EDM
		Primitive types.
		
		..data service SHOULD follow the binary numeric promotion
		rules... The EDM Primitive type of the result of evaluating the
		addExpression MUST be the same type as the operands after binary
		numeric promotion.
		
		data service can support evaluating operands with null values
		following the rules defined in Lifted operators"""
		p=Parser("2M add 2M")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.failUnless(value.pyValue == 4,"Expected 4")
		p=Parser("2D add 2M")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.failUnless(value.pyValue == 4.0,"Expected 4")
		p=Parser("2F add 2D")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.failUnless(value.pyValue == 4.0,"Expected 4")
		p=Parser("2 add 2L")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.failUnless(value.pyValue == 4L,"Expected 4")
		p=Parser("2 add '2'")
		e=p.ParseCommonExpression()
		try:
			value=e.Evaluate(None)
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		p=Parser("2 add null")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.failUnless(value.pyValue is None,"Expected None")

	def testCaseEvaluateSubExpression(self):
		"""See testCaseEvaluateAddExpression"""
		p=Parser("4M sub 2M")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.failUnless(value.pyValue == 2,"Expected 2.0")
		p=Parser("4D sub 2M")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.failUnless(value.pyValue == 2.0,"Expected 2.0")
		p=Parser("4F sub 2D")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.failUnless(value.pyValue == 2.0,"Expected 2.0")
		p=Parser("4 sub 2L")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.failUnless(value.pyValue == 2L,"Expected 2L")
		p=Parser("4 sub '2'")
		e=p.ParseCommonExpression()
		try:
			value=e.Evaluate(None)
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		p=Parser("4 sub null")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.failUnless(value.pyValue is None,"Expected None")

	def testCaseEvaluateMulExpression(self):
		"""See testCaseEvaluateAddExpression"""
		p=Parser("4M mul 2M")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.failUnless(value.pyValue == 8,"Expected 8.0")
		p=Parser("4D mul 2M")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.failUnless(value.pyValue == 8.0,"Expected 8.0")
		p=Parser("4F mul 2D")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.failUnless(value.pyValue == 8.0,"Expected 8.0")
		p=Parser("4 mul 2L")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.failUnless(value.pyValue == 8L,"Expected 8L")
		p=Parser("4 mul '2'")
		e=p.ParseCommonExpression()
		try:
			value=e.Evaluate(None)
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		p=Parser("4 mul null")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.failUnless(value.pyValue is None,"Expected None")

	def testCaseEvaluateDivExpression(self):
		"""See testCaseEvaluateAddExpression
		
		OData is ambiguous in the way it defines division as it makes reference only
		to the IEEE floating point operations.  For compatibility with SQL though we
		assume that integer division simple truncates fractional parts."""
		p=Parser("4M div 2M")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.failUnless(value.pyValue == 2,"Expected 2")
		p=Parser("4D div 2M")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.failUnless(value.pyValue == 2.0,"Expected 2.0")
		p=Parser("4D div 0")
		e=p.ParseCommonExpression()
		try:
			value=e.Evaluate(None)
			self.fail("Division by zero")
		except EvaluationError:
			pass
		p=Parser("4F div 2D")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.failUnless(value.pyValue == 2.0,"Expected 2.0")
		p=Parser("5 div 2L")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.failUnless(value.pyValue == 2L,"Expected 2L")
		p=Parser("-5 div 2L")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.failUnless(value.pyValue == -2L,"Expected -2L")
		p=Parser("4 div '2'")
		e=p.ParseCommonExpression()
		try:
			value=e.Evaluate(None)
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		p=Parser("4 div null")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.failUnless(value.pyValue is None,"Expected None")

	def testCaseEvaluateModExpression(self):
		"""See testCaseEvaluateAddExpression
		
		The data service SHOULD evaluate the operation represented by
		the modExpression, according to the rules of [IEEE754-2008]

		For integer division we just truncate fractional parts towards zero."""
		p=Parser("5.5M mod 2M")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.failUnless(value.pyValue == 1.5,"Expected 1.5")
		p=Parser("5.5D mod 2M")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.failUnless(value.pyValue == 1.5,"Expected 1.5")
		p=Parser("5.5D mod 0")
		e=p.ParseCommonExpression()
		try:
			value=e.Evaluate(None)
			self.fail("Division by zero")
		except EvaluationError:
			pass
		p=Parser("5.5F mod 2D")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.failUnless(value.pyValue == 1.5,"Expected 1.5")
		p=Parser("5 mod 2L")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.failUnless(value.pyValue == 1L,"Expected 1L")
		p=Parser("-5 mod 2L")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.failUnless(value.pyValue == -1L,"Expected -1L")
		p=Parser("5 mod '2'")
		e=p.ParseCommonExpression()
		try:
			value=e.Evaluate(None)
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		p=Parser("5 mod null")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.failUnless(value.pyValue is None,"Expected None")


	def testCaseEvaluateNegateExpression(self):
		"""See testCaseEvaluateAddExpression for list of simple types.
		
		..data service SHOULD follow the unary numeric promotion rules
		... to implicitly convert the operand to a supported EDM
		Primitive type

		the result of evaluating the negateExpression SHOULD always be
		equal to the result of evaluating the subExpression where one
		operand is the value zero and the other is the value of the
		operand.  [comment applies to null processing too]"""
		p=Parser("-(2M)")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.failUnless(value.pyValue == -2,"Expected -2.0")
		p=Parser("-(2D)")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.failUnless(value.pyValue == -2.0,"Expected -2.0")
		p=Parser("-(-2F)")	# unary numeric promotion to Double - a bit weird 
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.failUnless(value.pyValue == 2.0,"Expected 2.0")
		p=Parser("-(2L)")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.failUnless(value.pyValue == -2L,"Expected -2L")
		p=Parser("-'2'")
		e=p.ParseCommonExpression()
		try:
			value=e.Evaluate(None)
			self.fail("String promotion to numeric")
		except EvaluationError:
			pass
		p=Parser("-null")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.failUnless(value.pyValue is None,"Expected None")


	def testCaseEvaluateAndExpression(self):
		"""...operand expressions MUST evaluate to the EDM Primitive
		types of Edm.Boolean. The andExpression SHOULD NOT be supported
		for operands of any other EDM Primitive types.

		The EDM Primitive type of the result of evaluating the andExpression MUST be Edm.Boolean.

		...service MUST evaluate the expression to the value of true if
		the values of the operands are both true after being evaluated.
		If either operand is false after being evaluated, the expression
		MUST evaluate to the value of false.
		
		The data service can support evaluating operands with null
		values following the rules defined in Binary Numeric
		Promotions.... [for Boolean expressions evaluated to the value
		of null, a data service MUST return the value of false]"""
		p=Parser("false and false")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.failUnless(value.pyValue is False,"Expected False")
		p=Parser("false and 0")
		e=p.ParseCommonExpression()
		try:
			value=e.Evaluate(None)
			self.fail("Integer promotion to Boolean")
		except EvaluationError:
			pass
		p=Parser("false and true")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is False,"Expected False")
		p=Parser("true and false")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is False,"Expected False")
		p=Parser("true and true")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is True,"Expected True")
		p=Parser("true and null")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.failUnless(value.pyValue is False,"Expected False")
		p=Parser("false and null")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is False,"Expected False")
		p=Parser("false and false")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is False,"Expected False")


	def testCaseEvaluateOrExpression(self):
		"""See testCaseEvaluateAndExpression for more details.
		
		...data service MUST evaluate the expression to the value of
		true if at least one of the operands is true after being
		evaluated. If both operands are false after being evaluated, the
		expression MUST evaluate to the value of false"""
		p=Parser("false or false")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.failUnless(value.pyValue is False,"Expected False")
		p=Parser("false or 0")
		e=p.ParseCommonExpression()
		try:
			value=e.Evaluate(None)
			self.fail("Integer promotion to Boolean")
		except EvaluationError:
			pass
		p=Parser("false or true")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is True,"Expected True")
		p=Parser("true or false")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is True,"Expected True")
		p=Parser("true or true")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is True,"Expected True")
		p=Parser("true or null")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.failUnless(value.pyValue is False,"Expected False")
		p=Parser("false or null")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is False,"Expected False")
		p=Parser("null or null")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is False,"Expected False")

	def testCaseEvaluateEqExpression(self):
		"""...operand expressions MUST evaluate to a value of a known
		EntityType or one of the following EDM Primitive types:
			Edm.Decimal
			Edm.Double
			Edm.Single
			Edm.Int32
			Edm.Int64
			Edm.String
			Edm.DateTime
			Edm.Guid
			Edm.Binary
			
		The eqExpression SHOULD NOT be supported for any other EDM
		Primitive types.

		...a data service SHOULD follow the binary numeric promotion
		rules defined in Unary [sic] Numeric Promotions...
		
		...The EDM Primitive type of the result of evaluating the
		eqExpression MUST be Edm.Boolean.

		...a data service MUST return a value of true if the values of
		the operands are equal and false if they are not equal. If the
		type of the operands is a known EntityType, then a value of true
		MUST be returned if the operand expressions, once evaluated,
		represent the same entity instance.
		
		...for equality operators, a data service MUST consider two null
		values equal and a null value unequal to any non-null value."""
		p=Parser("2M eq 3M")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.failUnless(value.pyValue is False,"Expected False")
		p=Parser("2D eq 2M")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.failUnless(value.pyValue is True,"Expected True")
		p=Parser("2F eq 2D")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is True,"Expected True")
		p=Parser("2 eq 2L")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is True,"Expected True")
		p=Parser("2 eq '2'")
		e=p.ParseCommonExpression()
		try:
			value=e.Evaluate(None)
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		p=Parser("'2' eq '2'")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is True,"Expected True")
		p=Parser("datetime'2013-08-30T18:49' eq datetime'2013-08-30T18:49'")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is True,"Expected True")
		p=Parser("datetime'2013-08-30T18:49' eq datetime'2013-08-30T18:49:01'")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is False,"Expected False")
		p=Parser("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' eq guid'b3afeebc-9658-4699-9d9c-1df551fd6814'")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is True,"Expected True")
		p=Parser("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' eq guid'3fa6109e-f09c-4c5e-a5f3-6cf38d35c9b5'")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is False,"Expected False")
		p=Parser("X'DEADBEEF' eq binary'deadbeef'")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is True,"Expected True")			
		p=Parser("X'DEAD' eq binary'BEEF'")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is False,"Expected False")			
		p=Parser("2 eq null")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is False,"Expected False")			
		p=Parser("null eq null")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is True,"Expected True")			


	def testCaseEvaluateNeExpression(self):
		"""See testCaseEvaluateEqExpression for details."""
		p=Parser("2M ne 3M")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.failUnless(value.pyValue is True,"Expected True")
		p=Parser("2D ne 2M")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.failUnless(value.pyValue is False,"Expected False")
		p=Parser("2F ne 2D")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is False,"Expected False")
		p=Parser("2 ne 2L")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is False,"Expected False")
		p=Parser("2 ne '2'")
		e=p.ParseCommonExpression()
		try:
			value=e.Evaluate(None)
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		p=Parser("'2' ne '2'")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is False,"Expected False")
		p=Parser("datetime'2013-08-30T18:49' ne datetime'2013-08-30T18:49'")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is False,"Expected False")
		p=Parser("datetime'2013-08-30T18:49' ne datetime'2013-08-30T18:49:01'")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is True,"Expected True")
		p=Parser("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' ne guid'b3afeebc-9658-4699-9d9c-1df551fd6814'")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is False,"Expected False")
		p=Parser("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' ne guid'3fa6109e-f09c-4c5e-a5f3-6cf38d35c9b5'")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is True,"Expected True")
		p=Parser("X'DEADBEEF' ne binary'deadbeef'")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is False,"Expected False")			
		p=Parser("X'DEAD' ne binary'BEEF'")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is True,"Expected True")			
		p=Parser("2 ne null")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is True,"Expected True")			
		p=Parser("null ne null")
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.failUnless(value.pyValue is False,"Expected False")			


	def testCaseEntitySet(self):
		dsURI=ODataURI("Products()?$format=json&$top=20&$skip=10&space='%20'",'/x.svc')
		self.failUnless(dsURI.resourcePath=='/Products()',"resource path")
		self.failUnless(dsURI.sysQueryOptions=={SystemQueryOption.format:'json',SystemQueryOption.top:'20',SystemQueryOption.skip:'10'},repr(dsURI.sysQueryOptions))
		self.failUnless(dsURI.queryOptions==["space='%20'"],'query options')
		self.failUnless(dsURI.navPath==[(u'Products',{})],"entitySet: Products, found %s"%repr(dsURI.navPath))
		dsURI=ODataURI('Products()/$count','/x.svc')
		self.failUnless(dsURI.resourcePath=='/Products()/$count',"resource path")
		self.failUnless(dsURI.sysQueryOptions=={},'sysQueryOptions')
		self.failUnless(dsURI.queryOptions==[],'query options')		
		self.failUnless(dsURI.navPath==[(u'Products',{}),(u"$count",{})],"path: %s"%repr(dsURI.navPath))
		dsURI=ODataURI('Products(1)/$value','/x.svc')
		self.failUnless(dsURI.navPath==[(u'Products',{'':1}),(u"$value",{})],"path: %s"%repr(dsURI.navPath))
		dsURI=ODataURI('Products(x=1,y=2)','/x.svc')
		self.failUnless(dsURI.navPath==[(u'Products',{u'x':1,u'y':2})],"path: %s"%repr(dsURI.navPath))
		
			
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
			self.failUnless(self.Categories[c["ID"].pyValue]==c["Name"].pyValue,"Category Name")


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
		s.SetModel(doc)
		# at this point, the server's model root is available as model
		self.failUnless(s.model is doc.root,"model attribute")		
		

class CustomersByCityEntitySet(edm.FunctionEntitySet):
	
	def __init__(self,function,params):
		edm.FunctionEntitySet.__init__(self,function,params)
		self.city=params.get('city','Chunton')
		
	def itervalues(self):
		for customer in self.entitySet.data.itervalues():
			if customer[2][1]==self.city:
				yield self.entitySet[customer[0]]


class ShippedAddressByDateCollection(edm.FunctionCollection):
	
	def __init__(self,function,params):
		edm.FunctionCollection.__init__(self,function,params)
		self.date=params.get('date',None)
		if self.date is None:
			self.date=iso8601.TimePoint()
			self.date.Now()
		self.customers=function.FindParent(edmx.DataServices)['SampleModel.SampleEntities.Customers']
		
	def __iter__(self):
		for customer in self.customers.itervalues():
			yield customer['Address']


class ShippedCustomerNamesByDateCollection(edm.FunctionCollection):
	
	def __init__(self,function,params):
		edm.FunctionCollection.__init__(self,function,params)
		self.date=params.get('date',None)
		if self.date is None:
			self.date=iso8601.TimePoint()
			self.date.Now()
		self.customers=function.FindParent(edmx.DataServices)['SampleModel.SampleEntities.Customers']
		
	def __iter__(self):
		for customer in self.customers.itervalues():
			yield customer['CompanyName']	


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
		self.svc.SetModel(doc)
		customers=self.ds['SampleModel.SampleEntities.Customers']
		customers.data['ALFKI']=('ALFKI','Example Inc',("Mill Road","Chunton"),None)
		for i in xrange(90):
			customers.data['XXX%02X'%i]=('XXX%02X'%i,'Example-%i Ltd'%i,(None,None),None)
		employees=self.ds['SampleModel.SampleEntities.Employees']
		employees.data['1']=('1','Joe Bloggs',("The Elms","Chunton"),'DEADBEEF')
		orders=self.ds['SampleModel.SampleEntities.Orders']
		now=iso8601.TimePoint()
		now.Now()
		orders.data[1]=(1,now)
		orders.data[2]=(2,now)
		orders.data[3]=(3,now)
		association=self.ds['SampleModel.SampleEntities.Orders_Customers']
		association.Associate('ALFKI',1)
		association.Associate('ALFKI',2)
		orderLines=self.ds['SampleModel.SampleEntities.OrderLines']
		orderLines.data[100]=(100,12,0.45)
		orderLines.data[200]=(200,144,2.50)
		association=self.ds['SampleModel.SampleEntities.OrderLines_Orders']
		association.Associate(100,1)
		association.Associate(200,2)
		documents=self.ds['SampleModel.SampleEntities.Documents']
		documents.data[300]=(300,'The Book','The Author')
		documents.data[301]=(301,'A Book','An Author')
		customersByCity=self.ds['SampleModel.SampleEntities.CustomersByCity']
		customersByCity.Bind(CustomersByCityEntitySet)
		lastCustomerByLine=self.ds['SampleModel.SampleEntities.LastCustomerByLine']
		lastCustomerByLine.Bind(self.LastCustomerByLine)
		shippedAddressByDate=self.ds['SampleModel.SampleEntities.ShippedAddressByDate']
		shippedAddressByDate.Bind(ShippedAddressByDateCollection)
		lastShippedByLine=self.ds['SampleModel.SampleEntities.LastShippedByLine']
		lastShippedByLine.Bind(self.LastShippedByLine)
		shippedCustomerNamesByDate=self.ds['SampleModel.SampleEntities.ShippedCustomerNamesByDate']
		shippedCustomerNamesByDate.Bind(ShippedCustomerNamesByDateCollection)
		lastCustomerNameByLine=self.ds['SampleModel.SampleEntities.LastCustomerNameByLine']
		lastCustomerNameByLine.Bind(self.LastCustomerNameByLine)
		
	def LastCustomerByLine(self,function,params):
		customers=self.ds['SampleModel.SampleEntities.Customers']
		return customers['ALFKI']
				
	def LastShippedByLine(self,function,params):
		customers=self.ds['SampleModel.SampleEntities.Customers']
		return customers['ALFKI']['Address']
				
	def LastCustomerNameByLine(self,function,params):
		customers=self.ds['SampleModel.SampleEntities.Customers']
		return customers['ALFKI']['CompanyName']
				
	def tearDown(self):
		pass
	
	def testCaseEvaluateFirstMemberExpression(self):
		"""Back-track a bit to test some basic stuff using the sample data set.
		
		...the memberExpression can reference an Entity Navigation
		property, or an Entity Complex type property, or an Entity
		Simple Property, the target relationship end must have a
		cardinality of 1 or 0..1.
		
		The type of the result of evaluating the memberExpression MUST
		be the same type as the property reference in the
		memberExpression.
		
		...a data service MUST return null if any of the
		NavigationProperties are null."""
		orders=self.ds['SampleModel.SampleEntities.Orders']
		order=orders[1]
		# Simple Property
		p=Parser("OrderID")
		e=p.ParseCommonExpression()
		value=e.Evaluate(order)
		self.failUnless(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.failUnless(value.pyValue==1,"Expected 1")		
		customers=self.ds['SampleModel.SampleEntities.Customers']
		# customers.data['ALFKI']=('ALFKI','Example Inc',("Mill Road","Chunton"),None)
		customer=customers['ALFKI']
		# Complex Property
		p=Parser("Address")
		e=p.ParseCommonExpression()
		value=e.Evaluate(customer)
		self.failUnless(isinstance(value,edm.Complex),"Expected Complex value")
		self.failUnless(value['City'].pyValue=='Chunton',"Expected Chunton")		
		# Simple Property (NULL)
		p=Parser("Version")
		e=p.ParseCommonExpression()
		value=e.Evaluate(customer)
		self.failUnless(value.typeCode==edm.SimpleType.Binary,"Expected Binary")
		self.failUnless(value.pyValue is None,"Expected NULL")		
		# Navigation property
		p=Parser("Customer")
		e=p.ParseCommonExpression()
		value=e.Evaluate(order)
		self.failUnless(isinstance(value,edm.Entity),"Expected Entity")
		self.failUnless(value['CustomerID'].pyValue=='ALFKI',"Expected Customer('ALFKI')")
		# Navigation property with Null
		value=e.Evaluate(orders[3])
		self.failUnless(isinstance(value,edm.SimpleValue),"Expected SimpleValue (for NULL)")
		self.failIf(value,"Expected NULL")		
		# Navigation property with multiple cardinality
		p=Parser("Orders")
		e=p.ParseCommonExpression()
		try:
			value=e.Evaluate(customer)
			self.fail("Navigation property cardinality")
		except EvaluationError:
			pass
	
	def testCaseEvaluateMemberExpression(self):
		"""the target of the memberExpression MUST be a known Edm Entity or ComplexType.
		
		the memberExpression can reference an entity NavigationProperty,
		or an Entity Complex type property, or an Entity Simple Property.
		
		For entity NavigationProperties, the target relationship end
		must have a cardinality of 1 or 0..1.

		The type of the result of evaluating the memberExpression MUST
		be the same type as the property reference in the
		memberExpression.
		
		...a data service MUST return null if any of the
		NavigationProperties are null."""
		orders=self.ds['SampleModel.SampleEntities.Orders']
		order=orders[1]
		# Known Entity: SimpleProperty
		p=Parser("Customer/CustomerID")
		e=p.ParseCommonExpression()
		value=e.Evaluate(order)
		self.failUnless(value.typeCode==edm.SimpleType.String,"Expected string")
		self.failUnless(value.pyValue=='ALFKI',"Expected 'ALKFI'")		
		# Known ComplexType: SimpleProperty
		p=Parser("Customer/Address/City")
		e=p.ParseCommonExpression()
		value=e.Evaluate(order)
		self.failUnless(value.typeCode==edm.SimpleType.String,"Expected string")
		self.failUnless(value.pyValue=='Chunton',"Expected 'Chunton'")		
		# TODO: a two step navigation, sample data doesn't have one yet
		# 	navigation / navigation 
		# Simple Property (NULL)
		p=Parser("Customer/Version")
		e=p.ParseCommonExpression()
		value=e.Evaluate(order)
		self.failUnless(value.typeCode==edm.SimpleType.Binary,"Expected Binary")
		self.failUnless(value.pyValue is None,"Expected NULL")		
		# Navigation property with multiple cardinality
		p=Parser("Customer/Orders")
		e=p.ParseCommonExpression()
		try:
			value=e.Evaluate(order)
			self.fail("Navigation property cardinality")
		except EvaluationError:
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
		
		Although not explicitly stated, it seems that an entity set MUST NOT be
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

	def testCaseURI1(self):
		"""URI1 = scheme serviceRoot "/" entitySet
		
		[URI1] MUST identify all instances of the base EntityType or any
		of the EntityType's subtypes within the specified EntitySet
		specified in the last URI segment."""
		request=MockRequest('/service.svc/Customers')
		request.Send(self.svc)
		doc=app.Document()
		doc.Read(request.wfile.getvalue())
		self.failUnless(isinstance(doc.root,atom.Feed),"Expected atom.Feed from /Customers")
		self.failUnless(len(doc.root.Entry)==91,"Sample server has 91 Customers")
		#	the serviceOperation-collEt rule can be substituted for the
		#	first occurrence of an entitySet rule in the Resource Path
		request=MockRequest("/service.svc/CustomersByCity?city='Chunton'")
		# import pdb;pdb.set_trace()
		request.Send(self.svc)
		doc=app.Document()
		doc.Read(request.wfile.getvalue())
		self.failUnless(isinstance(doc.root,atom.Feed),"Expected atom.Feed from /CustomersByCity")
		self.failUnless(len(doc.root.Entry)==1,"Sample server has 1 Customer in Chunton")
		#	If the Entity Data Model... ...does not include an EntitySet with the name
		#	specified, the this URI (and any URI created by appending additional path segments)
		#	MUST be treated as identifying a non-existent resource.
		request=MockRequest("/service.svc/Prospects")
		request.Send(self.svc)
		self.failUnless(request.responseCode==404)		
		request=MockRequest("/service.svc/Prospects/$count")
		request.Send(self.svc)
		self.failUnless(request.responseCode==404)
		# all system query options are valid
		request=MockRequest("/service.svc/Customers?$expand=Orders&$filter=substringof(CompanyName,%20'bikes')&$orderby=CompanyName%20asc&$top=2&$skip=3&$skiptoken='Contoso','AKFNU'&$inlinecount=allpages&$select=CustomerID,CustomerName,Orders$format=xml")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
	
	def testCaseURI2(self):
		"""URI2 = scheme serviceRoot "/" entitySet "(" keyPredicate ")"
		
		MUST identify a single EntityType instance, which is within the
		EntitySet specified in the URI, where key EntityKey is equal to
		the value of the keyPredicate specified.
		
		If no entity identified by the keyPredicate exists in the
		EntitySet specified, then this URI (and any URI created by
		appending additional path segments) MUST represent a resource
		that does not exist in the data model"""
		request=MockRequest("/service.svc/Customers('ALFKI')")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.failUnless(isinstance(doc.root,Entry),"Expected a single Entry, found %s"%doc.root.__class__.__name__)
		self.failUnless(doc.root['CustomerID']=='ALFKI',"Bad CustomerID")
		request=MockRequest("/service.svc/Customers('ALFKJ')")
		request.Send(self.svc)
		self.failUnless(request.responseCode==404)
		request=MockRequest("/service.svc/Customers('ALFKJ')/Address")
		request.Send(self.svc)
		self.failUnless(request.responseCode==404)
		# $orderby, $skip, $top, $skiptoken, $inlinecount all banned
		baseURI="/service.svc/Customers('ALFKI')?$expand=Orders&$filter=substringof(CompanyName,%20'bikes')&$select=CustomerID,CustomerName,Orders&$format=xml"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)		
		for x in ["$orderby=CompanyName%20asc","$skip=3","$top=2","$skiptoken='Contoso','AKFNU'","$inlinecount=allpages"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.failUnless(request.responseCode==400,"URI2 with %s"%x)
	
	def testCaseURI3(self):
		"""URI3 = scheme serviceRoot "/" entitySet "(" keyPredicate ")/" entityComplexProperty
		
		MUST identify an instance of a ComplexType on the specified
		EntityType instance."""
		request=MockRequest("/service.svc/Customers('ALFKI')/Address")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.failUnless(isinstance(doc.root,Property),"Expected a single Property, found %s"%doc.root.__class__.__name__)
		value=doc.root.GetValue()
		self.failUnless(value['Street']=='Mill Road',"Bad street in address")		
		# $expand, $orderby, $skip, $top, $skiptoken, $inlinecount and $select all banned
		baseURI="/service.svc/Customers('ALFKI')/Address?$filter=substringof(CompanyName,%20'bikes')&$format=xml"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		for x in ["$expand=Orders","$orderby=CompanyName%20asc","$skip=3","$top=2","$skiptoken='Contoso','AKFNU'","$inlinecount=allpages","$select=CustomerID,CustomerName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.failUnless(request.responseCode==400,"URI3 with %s"%x)
	
	def testCaseURI4(self):
		"""URI4 = scheme serviceRoot "/" entitySet "(" keyPredicate ")/" entityComplexProperty "/" entityProperty
		
		MUST identify a property of a ComplexType defined on the
		EntityType of the entity whose EntityKey value is specified by
		the keyPredicate and is within the specified EntitySet."""
		request=MockRequest("/service.svc/Customers('ALFKI')/Address/Street")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.failUnless(isinstance(doc.root,Property),"Expected a single Property, found %s"%doc.root.__class__.__name__)
		value=doc.root.GetValue()
		self.failUnless(value.pyValue=='Mill Road',"Bad street")
		request=MockRequest("/service.svc/Customers('ALFKI')/Address/Street/$value")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		self.failUnless(request.wfile.getvalue()=='Mill Road',"Bad street $vaue")
		baseURI="/service.svc/Customers('ALFKI')/Address/Street?$format=xml"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		for x in ["$expand=Orders","$orderby=CompanyName%20asc","$filter=substringof(CompanyName,%20'bikes')",
			"$skip=3","$top=2","$skiptoken='Contoso','AKFNU'","$inlinecount=allpages",
			"$select=CustomerID,CustomerName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.failUnless(request.responseCode==400,"URI4 with %s"%x)
	
	def testCaseURI5(self):
		"""URI5 = scheme serviceRoot "/" entitySet "(" keyPredicate ")/" entityProperty

		MUST identify a property whose type is an EDMSimpleType on the
		EntityType instance (identified with EntityKey equal to the
		specified key predicate) within the specified EntitySet"""
		request=MockRequest("/service.svc/Customers('ALFKI')/CompanyName")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.failUnless(isinstance(doc.root,Property),"Expected a single Property, found %s"%doc.root.__class__.__name__)
		value=doc.root.GetValue()
		self.failUnless(value.pyValue=='Example Inc',"Bad company")
		request=MockRequest("/service.svc/Customers('ALFKI')/CompanyName/$value")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		self.failUnless(request.wfile.getvalue()=='Example Inc',"Bad company $vaue")
		baseURI="/service.svc/Customers('ALFKI')/CompanyName?$format=xml"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		for x in ["$expand=Orders","$orderby=CompanyName%20asc","$filter=substringof(CompanyName,%20'bikes')",
			"$skip=3","$top=2","$skiptoken='Contoso','AKFNU'","$inlinecount=allpages",
			"$select=CustomerID,CustomerName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.failUnless(request.responseCode==400,"URI5 with %s"%x)
	
	def testCaseURI6(self):
		"""URI6 = scheme serviceRoot "/" entitySet "(" keyPredicate ")/" entityNavProperty

		MUST identify a set of entities or an EntityType instance that
		is reached via the specified NavigationProperty on the entity
		identified by the EntitySet name and key predicate specified."""
		request=MockRequest("/service.svc/Customers('ALFKI')/Orders")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.failUnless(isinstance(doc.root,atom.Feed),"Expected atom.Feed from navigation property Orders")
		self.failUnless(len(doc.root.Entry)==2,"Sample customer has 2 orders")
		# TODO: navigation property pointing to a single Entity (Note 1)
# 		baseURI="/service.svc/Customers('ALFKI')/Orders?$expand=Orders&$filter=substringof(CompanyName,%20'bikes')&$format=xml&$select=CustomerID,CustomerName,Orders"
# 		request=MockRequest(baseURI)
# 		request.Send(self.svc)
# 		self.failUnless(request.responseCode==200)
# 		for x in ["$orderby=CompanyName%20asc",
# 			"$skip=3","$top=2","$skiptoken='Contoso','AKFNU'","$inlinecount=allpages"]:
# 			request=MockRequest(baseURI+"&"+x)
# 			request.Send(self.svc)
# 			self.failUnless(request.responseCode==400,"UR6 with %s"%x)
		# all system query options are valid when the navigation property identifies a set of entities (Note 2)
		request=MockRequest("/service.svc/Customers?$expand=Orders&$filter=substringof(CompanyName,%20'bikes')&$orderby=CompanyName%20asc&$top=2&$skip=3&$skiptoken='Contoso','AKFNU'&$inlinecount=allpages&$select=CustomerID,CustomerName,Orders$format=xml")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
	
	def testCaseURI7(self):
		"""URI7 = scheme serviceRoot "/" entitySet "(" keyPredicate ")/$links/" entityNavProperty
		
		MUST identify the collection of all Links from the specified
		EntityType instance (identified by the EntitySet name and key
		predicate specified) to all other entities that can be reached
		via the Navigation Property"""
		request=MockRequest("/service.svc/Customers('ALFKI')/$links/Orders")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.failUnless(isinstance(doc.root,Links),"Expected Links from $links request, found %s"%doc.root.__class__.__name__)
		self.failUnless(len(doc.root.URI)==2,"Sample customer has 2 orders")		
		request=MockRequest("/service.svc/Orders(1)/$links/Customer")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.failUnless(isinstance(doc.root,URI),"Expected URI from $links request")
		self.failUnless(doc.root.GetValue()=="http://host/service.svc/Customers('ALFKI')","Bad Customer link")			
		baseURI="/service.svc/Customers('ALFKI')/$links/Orders?$format=xml&$skip=3&$top=2&$skiptoken='Contoso','AKFNU'&$inlinecount=allpages"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		for x in ["$expand=Orders",
			"$filter=substringof(CompanyName,%20'bikes')",
			"$orderby=CompanyName%20asc",
			"$select=CustomerID,CustomerName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.failUnless(request.responseCode==400,"URI7 with %s"%x)
	
	def testCaseURI8(self):
		"""URI8 = scheme serviceRoot "/$metadata"
		
		MUST identify the Entity Data Model Extensions (EDMX) document,
		as specified in [MC-EDMX], which includes the Entity Data Model
		represented using a conceptual schema definition language
		(CSDL), as specified in [MC-CSDL], for the data service."""
		request=MockRequest("/service.svc/$metadata")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		doc=edmx.Document()
		doc.Read(request.wfile.getvalue())
		self.failUnless(isinstance(doc.root,edmx.Edmx),"Expected Edmx from $metadata request, found %s"%doc.root.__class__.__name__)
		baseURI="/service.svc/$metadata?"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		for x in ["$expand=Orders",
			"$filter=substringof(CompanyName,%20'bikes')",
			"$format=xml",
			"$orderby=CompanyName%20asc",
			"$skip=3",
			"$top=2",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CustomerName,Orders"]:
			request=MockRequest(baseURI+x)
			request.Send(self.svc)
			self.failUnless(request.responseCode==400,"URI8 with %s"%x)
		
	def testCaseURI9(self):
		"""URI9 = scheme serviceRoot "/$batch"

		MUST identify the endpoint of a data service which accepts Batch Requests.
		
		...If a data service does not implement support for a Batch
		Request, it must return a 4xx response code in the response to
		any Batch Request sent to it."""
		request=MockRequest("/service.svc/$batch")
		request.Send(self.svc)
		self.failUnless(request.responseCode==404)
		baseURI="/service.svc/$batch?"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.failUnless(request.responseCode==404)
		for x in ["$expand=Orders",
			"$filter=substringof(CompanyName,%20'bikes')",
			"$format=xml",
			"$orderby=CompanyName%20asc",
			"$skip=3",
			"$top=2",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CustomerName,Orders"]:
			request=MockRequest(baseURI+x)
			request.Send(self.svc)
			self.failUnless(request.responseCode==400,"URI9 with %s"%x)
	
	def testCaseURI10(self):
		"""URI10 = scheme serviceRoot "/" serviceOperation-et

		MUST identify a FunctionImport that returns a single EntityType instance.
		
		If no FunctionImport exists in the Entity Data Model associated
		with the data service which has the same name as specified by
		the serviceOperation-et rule, then this URI MUST represent a
		resource that does not exist in the data model"""
		# TODO, an actual function that does something that returns a single entity
		request=MockRequest("/service.svc/LastCustomerByLine?line=1")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		request=MockRequest("/service.svc/FirstCustomerByLine?line=1")
		request.Send(self.svc)
		self.failUnless(request.responseCode==404)
		baseURI="/service.svc/LastCustomerByLine?line=1&$format=xml"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		for x in ["$expand=Orders",
			"$filter=substringof(CompanyName,%20'bikes')",
			"$orderby=CompanyName%20asc",
			"$skip=3",
			"$top=2",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CustomerName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.failUnless(request.responseCode==400,"URI10 with %s"%x)

	def testCaseURI11(self):
		"""URI11 = scheme serviceRoot "/" serviceOperation-collCt

		MUST identify a FunctionImport which returns a collection of
		ComplexType instances.

		If no FunctionImport exists in the Entity Data Model associated
		with the data service that has the same name as specified by the
		serviceOperation-collCt rule, then this URI MUST represent a
		resource that does not exist in the data model."""
		# TODO, an actual function that does something that returns a collection of addresses
		request=MockRequest("/service.svc/ShippedAddressByDate?date=datetime'2013-08-02'")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		request=MockRequest("/service.svc/PendingAddressByDate?date=datetime'2013-08-02'")
		request.Send(self.svc)
		self.failUnless(request.responseCode==404)
		baseURI="/service.svc/ShippedAddressByDate?date=datetime'2013-08-02'&$format=xml"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		for x in ["$expand=Orders",
			"$filter=substringof(CompanyName,%20'bikes')",
			"$orderby=CompanyName%20asc",
			"$skip=3",
			"$top=2",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CustomerName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.failUnless(request.responseCode==400,"URI11 with %s"%x)
		
	def testCaseURI12(self):
		"""URI12 = scheme serviceRoot "/" serviceOperation-ct

		MUST identify a FunctionImport which returns a ComplexType
		instance.

		If no FunctionImport exists in the Entity Data Model associated
		with the data service that has the same name as specified by the
		serviceOperation-ct rule, then this URI MUST represent a
		resource that does not exist in the data model."""
		# TODO, an actual function that does something that returns a single entity
		request=MockRequest("/service.svc/LastShippedByLine?line=1")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		request=MockRequest("/service.svc/FirstShippedByLine?line=1")
		request.Send(self.svc)
		self.failUnless(request.responseCode==404)
		baseURI="/service.svc/LastShippedByLine?line=1&$format=xml"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		for x in ["$expand=Orders",
			"$filter=substringof(CompanyName,%20'bikes')",
			"$orderby=CompanyName%20asc",
			"$skip=3",
			"$top=2",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CustomerName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.failUnless(request.responseCode==400,"URI12 with %s"%x)
	
	def testCaseURI13(self):
		"""URI13 = scheme serviceRoot "/" serviceOperation-collPrim

		MUST identify a FunctionImport which returns a collection of
		Primitive type values

		If no FunctionImport exists in the Entity Data Model associated
		with the data service that has the same name as specified by the
		serviceOperation-collPrim rule, then this URI MUST represent a
		resource that does not exist in the data model."""
		# TODO, an actual function that does something that returns a single entity
		request=MockRequest("/service.svc/ShippedCustomerNamesByDate?date=datetime'2013-08-02'")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		request=MockRequest("/service.svc/PendingCustomerNamesByDate?date=datetime'2013-08-02'")
		request.Send(self.svc)
		self.failUnless(request.responseCode==404)
		baseURI="/service.svc/ShippedCustomerNamesByDate?date=datetime'2013-08-02'&$format=xml"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		for x in ["$expand=Orders",
			"$filter=substringof(CompanyName,%20'bikes')",
			"$orderby=CompanyName%20asc",
			"$skip=3",
			"$top=2",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CustomerName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.failUnless(request.responseCode==400,"URI13 with %s"%x)
	
	def testCaseURI14(self):
		"""URI14 = scheme serviceRoot "/" serviceOperation-prim

		MUST identify a FunctionImport which returns a single Primitive
		type value.
		
		If no FunctionImport exists in the Entity Data Model associated
		with the data service that has the same name as specified by the
		serviceOperation-collPrim rule, then this URI MUST represent a
		resource that does not exist in the data model.

		A path segment containing only the rule serviceOperation-prim
		may append a "/$value" segment. A $value MUST be interpreted as
		a dereference operator"""
		# TODO, an actual function that does something that returns a single entity
		request=MockRequest("/service.svc/LastCustomerNameByLine?line=1")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)		
		request=MockRequest("/service.svc/LastCustomerNameByLine/$value?line=1")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		request=MockRequest("/service.svc/FirstCustomerNameByLine?line=1")
		request.Send(self.svc)
		self.failUnless(request.responseCode==404)		
		baseURI="/service.svc/LastCustomerNameByLine?line=1&$format=xml"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		for x in ["$expand=Orders",
			"$filter=substringof(CompanyName,%20'bikes')",
			"$orderby=CompanyName%20asc",
			"$skip=3",
			"$top=2",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CustomerName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.failUnless(request.responseCode==400,"URI14 with %s"%x)


	def testCaseURI15(self):
		"""URI15 = scheme serviceRoot "/" entitySet count

		MUST identify the count of all instances of the base EntityType
		or any of the EntityType's subtypes within the specified
		EntitySet specified in the last URI segment"""
		request=MockRequest('/service.svc/Customers/$count')
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		self.failUnless(request.wfile.getvalue()=="91","Sample server has 91 Customers")
		baseURI="/service.svc/Customers/$count?$expand=Orders&$filter=substringof(CompanyName,%20'bikes')&$orderby=CompanyName%20asc&$skip=3&$top=2"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		for x in ["$format=xml",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CustomerName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.failUnless(request.responseCode==400,"URI15 with %s"%x)
	
	def testCaseURI16(self):
		"""URI16 = scheme serviceRoot "/" entitySet "(" keyPredicate ")" count

		MAY identify the count of a single EntityType instance (the
		count value SHOULD always equal one), which is within the
		EntitySet specified in the URI, where key EntityKey is equal to
		the value of the keyPredicate specified."""
		request=MockRequest("/service.svc/Customers('ALFKI')/$count")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		self.failUnless(request.wfile.getvalue()=="1","the count value SHOULD always equal one")
		request=MockRequest("/service.svc/Customers('ALFKJ')/$count")
		request.Send(self.svc)
		self.failUnless(request.responseCode==404)
		baseURI="/service.svc/Customers('ALFKI')/$count?$expand=Orders&$filter=substringof(CompanyName,%20'bikes')"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		for x in ["$format=xml",
			"$orderby=CompanyName%20asc",
			"$skip=3",
			"$top=2",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CustomerName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.failUnless(request.responseCode==400,"URI16 with %s"%x)
	
	def testCaseURI17(self):
		"""URI17 = scheme serviceRoot "/" entitySet "(" keyPredicate ")" value

		MUST identify the Media Resource [RFC5023] associated with the
		identified EntityType instance. The EntityType that defines the
		entity identified MUST be annotated with the "HasStream"
		attribute."""
		request=MockRequest("/service.svc/Documents(301)/$value")
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		baseURI="/service.svc/Documents(301)/$value?$format=xml"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.failUnless(request.responseCode==200)
		for x in ["$expand=Orders",
			"$filter=substringof(CompanyName,%20'bikes')",
			"$orderby=CompanyName%20asc",
			"$skip=3",
			"$top=2",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CustomerName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.failUnless(request.responseCode==400,"URI17 with %s"%x)
	
	def testCaseQueryOptions(self):
		"""If a data service does not support a System Query Option, it
		MUST reject any requests which contain the unsupported option"""			
		request=MockRequest("/service.svc/Documents(301)?$unsupported=1")
		request.Send(self.svc)
		self.failUnless(request.responseCode==400)
		request=MockRequest("/service.svc/Documents(301)?$filter=true%20nand%20false")
		request.Send(self.svc)
		self.failUnless(request.responseCode==400)
		
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
