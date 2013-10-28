#! /usr/bin/env python

import unittest, random, decimal, math, hashlib
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

import sys, os, time

class MockTime:
	now=time.time()	

	@classmethod
	def time(cls):
		return cls.now
	
	@classmethod
	def gmtime(cls,*args):
		return time.gmtime(*args)
	
	@classmethod
	def localtime(cls,*args):
		return time.localtime(*args)
		
iso.pytime=MockTime
		


ODATA_SAMPLE_SERVICEROOT="http://services.odata.org/OData/OData.svc/"
ODATA_SAMPLE_READWRITE="http://services.odata.org/(S(readwrite))/OData/OData.svc/"

TEST_DATA_DIR=os.path.join(os.path.split(os.path.abspath(__file__))[0],'data_odatav2')



class ODataTests(unittest.TestCase):
	def testCaseConstants(self):
		# self.assertTrue(IMSCP_NAMESPACE=="http://www.imsglobal.org/xsd/imscp_v1p1","Wrong CP namespace: %s"%IMSCP_NAMESPACE)
		# self.assertTrue(IMSCPX_NAMESPACE=="http://www.imsglobal.org/xsd/imscp_extensionv1p2","Wrong extension namespace: %s"%IMSCPX_NAMESPACE)
		pass

	def testCaseTypePromotion(self):
		"""If supported, binary numeric promotion SHOULD consist of the
		application of the following rules in the order specified:

		If either operand is of type Edm.Decimal, the other operand is converted to Edm.Decimal unless it is of type Edm.Single or Edm.Double."""
		self.assertTrue(PromoteTypes(edm.SimpleType.Decimal,edm.SimpleType.Int64)==edm.SimpleType.Decimal,"Decimal promotion of Int64")
		self.assertTrue(PromoteTypes(edm.SimpleType.Decimal,edm.SimpleType.Int32)==edm.SimpleType.Decimal,"Decimal promotion of Int32")
		self.assertTrue(PromoteTypes(edm.SimpleType.Decimal,edm.SimpleType.Int16)==edm.SimpleType.Decimal,"Decimal promotion of Int16")
		self.assertTrue(PromoteTypes(edm.SimpleType.Decimal,edm.SimpleType.Byte)==edm.SimpleType.Decimal,"Decimal promotion of Byte")
		#	Otherwise, if either operand is Edm.Double, the other operand is converted to type Edm.Double.
		self.assertTrue(PromoteTypes(edm.SimpleType.Decimal,edm.SimpleType.Double)==edm.SimpleType.Double,"Double promotion of Decimal")
		self.assertTrue(PromoteTypes(edm.SimpleType.Single,edm.SimpleType.Double)==edm.SimpleType.Double,"Double promotion of Single")
		self.assertTrue(PromoteTypes(edm.SimpleType.Double,edm.SimpleType.Int64)==edm.SimpleType.Double,"Double promotion of Int64")
		self.assertTrue(PromoteTypes(edm.SimpleType.Double,edm.SimpleType.Int32)==edm.SimpleType.Double,"Double promotion of Int32")
		self.assertTrue(PromoteTypes(edm.SimpleType.Double,edm.SimpleType.Int16)==edm.SimpleType.Double,"Double promotion of Int16")
		self.assertTrue(PromoteTypes(edm.SimpleType.Double,edm.SimpleType.Byte)==edm.SimpleType.Double,"Double promotion of Byte")
		#	Otherwise, if either operand is Edm.Single, the other operand is converted to type Edm.Single.
		self.assertTrue(PromoteTypes(edm.SimpleType.Decimal,edm.SimpleType.Single)==edm.SimpleType.Single,"Single promotion of Decimal")
		self.assertTrue(PromoteTypes(edm.SimpleType.Single,edm.SimpleType.Int64)==edm.SimpleType.Single,"Single promotion of Int64")
		self.assertTrue(PromoteTypes(edm.SimpleType.Single,edm.SimpleType.Int32)==edm.SimpleType.Single,"Single promotion of Int32")
		self.assertTrue(PromoteTypes(edm.SimpleType.Single,edm.SimpleType.Int16)==edm.SimpleType.Single,"Single promotion of Int16")
		self.assertTrue(PromoteTypes(edm.SimpleType.Single,edm.SimpleType.Byte)==edm.SimpleType.Single,"Single promotion of Byte")		
		#	Otherwise, if either operand is Edm.Int64, the other operand is converted to type Edm.Int64.
		self.assertTrue(PromoteTypes(edm.SimpleType.Int64,edm.SimpleType.Int32)==edm.SimpleType.Int64,"Int64 promotion of Int32")
		self.assertTrue(PromoteTypes(edm.SimpleType.Int64,edm.SimpleType.Int16)==edm.SimpleType.Int64,"Int64 promotion of Int16")
		self.assertTrue(PromoteTypes(edm.SimpleType.Int64,edm.SimpleType.Byte)==edm.SimpleType.Int64,"Int64 promotion of Byte")				
		#	Otherwise, if either operand is Edm.Int32, the other operand is converted to type Edm.Int32
		self.assertTrue(PromoteTypes(edm.SimpleType.Int32,edm.SimpleType.Int16)==edm.SimpleType.Int32,"Int32 promotion of Int16")
		self.assertTrue(PromoteTypes(edm.SimpleType.Int32,edm.SimpleType.Byte)==edm.SimpleType.Int32,"Int32 promotion of Byte")						
		#	Otherwise, if either operand is Edm.Int16, the other operand is converted to type Edm.Int16.
		self.assertTrue(PromoteTypes(edm.SimpleType.Int16,edm.SimpleType.Byte)==edm.SimpleType.Int16,"Int16 promotion of Byte")						
		#	Special case, if either operand is null we return the type of the other operand
		self.assertTrue(PromoteTypes(edm.SimpleType.Int16,None)==edm.SimpleType.Int16,"Int16 promotion of NULL")						
		self.assertTrue(PromoteTypes(edm.SimpleType.Int32,None)==edm.SimpleType.Int32,"Int32 promotion of NULL")						
		self.assertTrue(PromoteTypes(None,edm.SimpleType.Int64)==edm.SimpleType.Int64,"Int64 promotion of NULL")						
		self.assertTrue(PromoteTypes(None,edm.SimpleType.Single)==edm.SimpleType.Single,"Single promotion of NULL")						
		try:
			PromoteTypes(edm.SimpleType.String,edm.SimpleType.Single)
			self.fail("Type promotion of String and Single")
		except EvaluationError:
			pass
	
	def testCaseValidMetadataExamples(self):
		dPath=os.path.join(TEST_DATA_DIR,'valid')
		for fName in os.listdir(dPath):
			if fName[-4:]!=".xml":
				continue
			f=uri.URIFactory.URLFromPathname(os.path.join(dPath,fName))
			doc=edmx.Document(baseURI=f)
			doc.Read()
			try:
				doc.Validate()
			except InvalidMetadataDocument,e:
				self.fail("%s is valid but raised InvalidMetadataDocument: %s"%(fName,str(e)))

	def testCaseInvalidMetadataExamples(self):
		dPath=os.path.join(TEST_DATA_DIR,'invalid')
		for fName in os.listdir(dPath):
			if fName[-4:]!=".xml":
				continue
			f=uri.URIFactory.URLFromPathname(os.path.join(dPath,fName))
			doc=edmx.Document(baseURI=f)
			doc.Read()
			try:
				doc.Validate()
				self.fail("%s is invalid but did not raise InvalidMetadataDocument"%fName)
			except InvalidMetadataDocument:
				pass
		

class ODataURILiteralTests(unittest.TestCase):
	def testCaseNullLiteral(self):
		"""	nullLiteral = "null" """
		v=ParseURILiteral("null")
		self.assertTrue(v.IsNull(),"null type IsNull")
		self.assertTrue(v.typeCode is None,"null type: %s"%repr(v.typeCode))
		self.assertTrue(v.pyValue is None,"null value: %s"%repr(v.pyValue))

	def testCaseBinaryLiteral(self):
		"""	binaryUriLiteral = caseSensitiveToken SQUOTE binaryLiteral SQUOTE
			binaryLiteral = hexDigPair
			caseSensitiveToken = "X" / "binary"
			; X is case sensitive binary is not
			hexDigPair = 2*HEXDIG [hexDigPair] """
		v=ParseURILiteral("X'0A'")
		self.assertTrue(v.typeCode==edm.SimpleType.Binary,"binary type: %s"%repr(v.typeCode))
		self.assertTrue(v.pyValue=='\x0a',"binary type: %s"%repr(v.pyValue))
		v=ParseURILiteral("X'0a'")
		self.assertTrue(v.pyValue=="\x0a","binary type: %s"%repr(v.pyValue))
		try:
			v=ParseURILiteral("x'0a'")
			self.fail("Syntax error")
		except ValueError:
			pass
		v=ParseURILiteral("binary'0A'")
		self.assertTrue(v.typeCode==edm.SimpleType.Binary,"binary type: %s"%repr(v.typeCode))
		self.assertTrue(v.pyValue=='\x0a',"binary type: %s"%repr(v.pyValue))
		v=ParseURILiteral("BINARY'0A'")
		self.assertTrue(v.typeCode==edm.SimpleType.Binary,"binary type: %s"%repr(v.typeCode))
		self.assertTrue(v.pyValue=='\x0a',"binary type: %s"%repr(v.pyValue))
		# gotta love those recursive rules
		v=ParseURILiteral("X'deadBEEF'")
		self.assertTrue(v.pyValue=="\xde\xad\xbe\xef","binary type: %s"%repr(v.pyValue))
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
		self.assertTrue(v.typeCode==edm.SimpleType.Boolean,"boolean type: %s"%repr(v.typeCode))
		self.assertTrue(v.pyValue is True,"boolean value: %s"%repr(v.pyValue))
		v=ParseURILiteral("false")
		self.assertTrue(v.typeCode==edm.SimpleType.Boolean,"boolean type: %s"%repr(v.typeCode))
		self.assertTrue(v.pyValue is False,"boolean value: %s"%repr(v.pyValue))

	def testCaseIntLiteral(self):
		"""byteLiteral = 1*3DIGIT;
		int16Literal= sign 1*5DIGIT
		int32Literal= sign 1*10DIGIT
		sbyteliteral= sign 1*3DIGIT	
		All returned as an int32 with python int value."""
		v=ParseURILiteral("0")
		self.assertTrue(v.typeCode==edm.SimpleType.Int32,"0 type: %s"%repr(v.typeCode))
		self.assertTrue(v.pyValue==0,"0 value: %s"%repr(v.pyValue))
		v=ParseURILiteral("1")
		self.assertTrue(v.typeCode==edm.SimpleType.Int32,"1 type: %s"%repr(v.typeCode))
		self.assertTrue(v.pyValue==1,"1 value: %s"%repr(v.pyValue))
		v=ParseURILiteral("2147483647")
		self.assertTrue(v.typeCode==edm.SimpleType.Int32,"2147483647 type: %s"%repr(v.typeCode))
		self.assertTrue(v.pyValue==2147483647,"2147483647 value: %s"%repr(v.pyValue))
		v=ParseURILiteral("0000000000")
		self.assertTrue(v.typeCode==edm.SimpleType.Int32,"0000000000 type: %s"%repr(v.typeCode))
		self.assertTrue(v.pyValue==0,"0000000000 value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-2147483648")
		self.assertTrue(v.typeCode==edm.SimpleType.Int32,"-2147483648 type: %s"%repr(v.typeCode))
		self.assertTrue(v.pyValue==-2147483648,"-2147483648 value: %s"%repr(v.pyValue))
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
		self.assertTrue(v.typeCode==edm.SimpleType.DateTime,"date time type: %s"%repr(v.typeCode))
		self.assertTrue(isinstance(v.pyValue,iso.TimePoint),"value type: %s"%repr(v.pyValue))
		self.assertTrue(str(v.pyValue)=="2012-06-30T23:59:00","value: %s"%str(v.pyValue))
		v=ParseURILiteral("datetime'2012-06-30T23:59:59'")
		self.assertTrue(v.typeCode==edm.SimpleType.DateTime,"date time type: %s"%repr(v.typeCode))
		self.assertTrue(str(v.pyValue)=="2012-06-30T23:59:59","value: %s"%str(v.pyValue))
		v=ParseURILiteral("datetime'2012-06-30T23:59:59.9999999'")
		self.assertTrue(v.typeCode==edm.SimpleType.DateTime,"date time type: %s"%repr(v.typeCode))
		self.assertTrue(v.pyValue.GetCalendarString(ndp=-7)=="2012-06-30T23:59:59.9999999")
		# Now for the big one!
		v=ParseURILiteral("datetime'2012-06-30T23:59:60'")
		self.assertTrue(v.typeCode==edm.SimpleType.DateTime,"date time type for leap second: %s"%repr(v.typeCode))
		self.assertTrue(str(v.pyValue)=="2012-06-30T23:59:60","value for leap second: %s"%str(v.pyValue))
		v=ParseURILiteral("datetime'2012-06-30T24:00:00'")
		self.assertTrue(v.typeCode==edm.SimpleType.DateTime,"date time extreme: %s"%repr(v.typeCode))
		self.assertTrue(str(v.pyValue)=="2012-06-30T24:00:00","date time extreme: %s"%str(v.pyValue))
		# and now the crappy ones
		for crappy in [
			"datetime'2012-6-30T23:59:59'",
			"datetime'2012-06-1T23:59:59'",
			"datetime'2012-06-30T3:59:59'"
			]:
			v=ParseURILiteral(crappy)
			self.assertTrue(v.typeCode==edm.SimpleType.DateTime,"date time type: %s"%repr(v.typeCode))
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
		self.assertTrue(v.typeCode==edm.SimpleType.Decimal,"0M type: %s"%repr(v.typeCode))
		self.assertTrue(isinstance(v.pyValue,decimal.Decimal),"0M value type: %s"%repr(v.pyValue))
		self.assertTrue(v.pyValue==0,"0M value: %s"%repr(v.pyValue))
		v=ParseURILiteral("1.1m")
		self.assertTrue(v.typeCode==edm.SimpleType.Decimal,"1.1m type: %s"%repr(v.typeCode))
		self.assertTrue(isinstance(v.pyValue,decimal.Decimal),"1.1m value type: %s"%repr(v.pyValue))
		self.assertTrue(v.pyValue*10==11,"1.1m value: %s"%repr(v.pyValue))
		v=ParseURILiteral("12345678901234567890123456789m")
		self.assertTrue(v.typeCode==edm.SimpleType.Decimal,"29-digit type: %s"%repr(v.typeCode))
		self.assertTrue(int(v.pyValue.log10())==28,"29-digit log10 value: %s"%repr(v.pyValue))
		v2=ParseURILiteral("12345678901234567890123456789.12345678901234567890123456789m")
		self.assertTrue(v2.pyValue-v.pyValue<0.13 and v2.pyValue-v.pyValue>0.12,"29digit.29digit value: %s"%repr(v2.pyValue-v.pyValue))
		v=ParseURILiteral("-2147483648M")
		self.assertTrue(v.typeCode==edm.SimpleType.Decimal,"-2147483648 type: %s"%repr(v.typeCode))
		self.assertTrue(v.pyValue==-2147483648,"-2147483648 value: %s"%repr(v.pyValue))
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
		self.assertTrue(v.typeCode==edm.SimpleType.Double,"0D type: %s"%repr(v.typeCode))
		self.assertTrue(type(v.pyValue) is FloatType,"0D value type: %s"%repr(v.pyValue))
		self.assertTrue(v.pyValue==0,"0D value: %s"%repr(v.pyValue))
		v=ParseURILiteral("1.1d")
		self.assertTrue(v.typeCode==edm.SimpleType.Double,"1.1d type: %s"%repr(v.typeCode))
		self.assertTrue(type(v.pyValue) is FloatType,"1.1d value type: %s"%repr(v.pyValue))
		self.assertTrue(v.pyValue*10==11,"1.1d value: %s"%repr(v.pyValue))
		v=ParseURILiteral("12345678901234567D")
		self.assertTrue(v.typeCode==edm.SimpleType.Double,"17-digit type: %s"%repr(v.typeCode))
		self.assertTrue(round(math.log10(v.pyValue),3)==16.092,"29-digit log10 value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-12345678901234567D")
		self.assertTrue(v.typeCode==edm.SimpleType.Double,"17-digit negative type: %s"%repr(v.typeCode))
		self.assertTrue(round(math.log10(-v.pyValue),3)==16.092,"29-digit log10 value: %s"%repr(v.pyValue))
		v=ParseURILiteral("123456789012345678901234567890.123456789012345678901234567890D")
		self.assertTrue(v.typeCode==edm.SimpleType.Double,"30digit.30digit type: %s"%repr(v.typeCode))
		self.assertTrue(round(math.log10(v.pyValue),3)==29.092,"30digit.30digit value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-123456789012345678901234567890.123456789012345678901234567890D")
		self.assertTrue(round(math.log10(-v.pyValue),3)==29.092,"30digit.30digit negative value: %s"%repr(v.pyValue))
		v=ParseURILiteral(".142D")
		self.assertTrue(v.pyValue==0.142,"Empty left value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-.142D")
		self.assertTrue(v.pyValue==-0.142,"Empty left neg value: %s"%repr(v.pyValue))
		v=ParseURILiteral("3.D")
		self.assertTrue(v.pyValue==3,"Empty right value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-3.D")
		self.assertTrue(v.pyValue==-3,"Empty right neg value: %s"%repr(v.pyValue))
		v=ParseURILiteral("3.14159e000d")
		self.assertTrue(round(v.pyValue,3)==3.142,"zero exp: %s"%repr(v.pyValue))
		v=ParseURILiteral("NanD")
		self.assertTrue(math.isnan(v.pyValue),"Nan double: %s"%repr(v.pyValue))
		v=ParseURILiteral("INFD")
		self.assertTrue(v.pyValue>0 and math.isinf(v.pyValue),"Inf double: %s"%repr(v.pyValue))
		v=ParseURILiteral("-INFD")
		self.assertTrue(v.pyValue<0 and math.isinf(v.pyValue),"Negative Inf double: %s"%repr(v.pyValue))		
		for bad in [ "123456789012345678D", "+1D", ".1e1d","+1.0E1d",
			"1.12345678901234567E10d","3.141Ed","3.141E1234d","3.141E+10d",".123E1D",
			"+NanD","-NanD","+INFD",".D","-.D","-123456789012345678901234567890.1234567890123456E1d"]:
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
		self.assertTrue(v.typeCode==edm.SimpleType.Single,"0f type: %s"%repr(v.typeCode))
		self.assertTrue(type(v.pyValue) is FloatType,"0f value type: %s"%repr(v.pyValue))
		self.assertTrue(v.pyValue==0,"0f value: %s"%repr(v.pyValue))
		v=ParseURILiteral("1.1f")
		self.assertTrue(v.typeCode==edm.SimpleType.Single,"1.1f type: %s"%repr(v.typeCode))
		self.assertTrue(type(v.pyValue) is FloatType,"1.1f value type: %s"%repr(v.pyValue))
		self.assertTrue(v.pyValue*10==11,"1.1f value: %s"%repr(v.pyValue))
		v=ParseURILiteral("12345678F")
		self.assertTrue(v.typeCode==edm.SimpleType.Single,"8-digit type: %s"%repr(v.typeCode))
		self.assertTrue(v.pyValue==12345678,"8-digit: %s"%repr(v.pyValue))
		v=ParseURILiteral("-12345678F")
		self.assertTrue(v.typeCode==edm.SimpleType.Single,"8-digit negative type: %s"%repr(v.typeCode))
		self.assertTrue(v.pyValue==-12345678,"8-digit neg value: %s"%repr(v.pyValue))
		v=ParseURILiteral("123456789012345678901234567890.123456789012345678901234567890f")
		self.assertTrue(v.typeCode==edm.SimpleType.Single,"30digit.30digit type: %s"%repr(v.typeCode))
		self.assertTrue(round(math.log10(v.pyValue),3)==29.092,"30digit.30digit value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-123456789012345678901234567890.123456789012345678901234567890F")
		self.assertTrue(round(math.log10(-v.pyValue),3)==29.092,"30digit.30digit negative value: %s"%repr(v.pyValue))
		v=ParseURILiteral(".142f")
		self.assertTrue(v.pyValue==0.142,"Empty left value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-.142F")
		self.assertTrue(v.pyValue==-0.142,"Empty left neg value: %s"%repr(v.pyValue))
		v=ParseURILiteral("3.F")
		self.assertTrue(v.pyValue==3,"Empty right value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-3.F")
		self.assertTrue(v.pyValue==-3,"Empty right neg value: %s"%repr(v.pyValue))
		v=ParseURILiteral("3.14159e00F")
		self.assertTrue(round(v.pyValue,3)==3.142,"zero exp: %s"%repr(v.pyValue))
		v=ParseURILiteral("3.E1F")
		self.assertTrue(v.pyValue==30,"Empty right exp value: %s"%repr(v.pyValue))
		v=ParseURILiteral("NanF")
		self.assertTrue(math.isnan(v.pyValue),"Nan single: %s"%repr(v.pyValue))
		v=ParseURILiteral("InfF")
		self.assertTrue(v.pyValue>0 and math.isinf(v.pyValue),"Inf single: %s"%repr(v.pyValue))
		v=ParseURILiteral("-INFF")
		self.assertTrue(v.pyValue<0 and math.isinf(v.pyValue),"Negative Inf single: %s"%repr(v.pyValue))		
		for bad in [ "123456789F", "+1F", ".1e1F","+1.0E1F",
			"1.123456789E10F","3.141EF","3.141E023F","3.141E+10F",".123E1F",
			"+NanF","-NanF","+INFF",".f","-.F","-123456789012345678901234567890.12345678E1F"]:
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
		self.assertTrue(v.typeCode==edm.SimpleType.Guid,"guide type: %s"%repr(v.typeCode))
		self.assertTrue(isinstance(v.pyValue,uuid.UUID),"guide type: %s"%repr(v.pyValue))
		self.assertTrue(v.pyValue.hex.lower()=='c0dec0dec0dec0deffffc0dec0dec0de',"guid value (missing bytes): %s"%repr(v.pyValue))
		v=ParseURILiteral("guid'cd04f705-390c-4736-98dc-a3baa6b3a283'")
		self.assertTrue(v.typeCode==edm.SimpleType.Guid,"guide type: %s"%repr(v.typeCode))
		self.assertTrue(isinstance(v.pyValue,uuid.UUID),"guide type: %s"%repr(v.pyValue))
		self.assertTrue(v.pyValue.hex.lower()=='cd04f705390c473698dca3baa6b3a283',"guid value (random): %s"%repr(v.pyValue))
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
		self.assertTrue(v.typeCode==edm.SimpleType.Int64,"0L type: %s"%repr(v.typeCode))
		self.assertTrue(type(v.pyValue)==LongType,"0L value type: %s"%repr(v.pyValue))
		self.assertTrue(v.pyValue==0,"0L value: %s"%repr(v.pyValue))
		v=ParseURILiteral("1234567890123456789l")
		self.assertTrue(v.typeCode==edm.SimpleType.Int64,"19-digit type: %s"%repr(v.typeCode))
		self.assertTrue(v.pyValue==1234567890123456789L,"19-digit value: %s"%repr(v.pyValue))
		v=ParseURILiteral("-1234567890123456789l")
		self.assertTrue(v.typeCode==edm.SimpleType.Int64,"19-digit neg type: %s"%repr(v.typeCode))
		self.assertTrue(v.pyValue==-1234567890123456789L,"19-digit neg value: %s"%repr(v.pyValue))
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
		self.assertTrue(v.typeCode==edm.SimpleType.String,"string type: %s"%repr(v.typeCode))
		self.assertTrue(v.pyValue=='0A',"string type: %s"%repr(v.pyValue))
		v=ParseURILiteral("'0a'")
		self.assertTrue(v.pyValue=="0a","string type: %s"%repr(v.pyValue))
		v=ParseURILiteral("'Caf\xc3\xa9'")
		# When parsed from a URL we assume that %-encoding is removed
		# when the parameters are split leaving octet-strings that
		# are parsed.  So utf-8 encoding of strings must be removed
		# at the literal parsing stage
		self.assertTrue(v.pyValue==u"Caf\xe9","unicode string type: %s"%repr(v.pyValue))
		# This next case is a shocker, the specification provides no way to escape SQUOTE
		# We support the undocumented doubling of the SQUOTE character.
		v=ParseURILiteral("'Peter O''Toole'")
		self.assertTrue(v.pyValue==u"Peter O'Toole","double SQUOTE: %s"%repr(v.pyValue))
		v=ParseURILiteral("'Peter O%27Toole'")
		self.assertTrue(v.pyValue==u"Peter O%27Toole","%%-encoding ignored: %s"%repr(v.pyValue))		
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
		self.assertTrue(v.typeCode==edm.SimpleType.Time,"date time type: %s"%repr(v.typeCode))
		self.assertTrue(isinstance(v.pyValue,xsi.Duration),"value type: %s"%repr(v.pyValue))
		self.assertTrue(str(v.pyValue)=="P1Y2M3DT10H30M","value: %s"%str(v.pyValue))		
		v=ParseURILiteral("time'-P120D'")
		self.assertTrue(v.typeCode==edm.SimpleType.Time,"date time type: %s"%repr(v.typeCode))
		# There is no canonical representation so this is a weak test
		self.assertTrue(str(v.pyValue)=="-P0Y0M120D","value: %s"%str(v.pyValue))
		for good in [
			"time'P1347Y'",
			"time'P1347M'",
			"time'P1Y2MT2H'",
			"time'P0Y1347M'",
			"time'P0Y1347M0D'",
			"time'-P1347M'"]:
			v=ParseURILiteral(good)
			self.assertTrue(v.typeCode==edm.SimpleType.Time,"date time type: %s"%repr(v.typeCode))
			self.assertTrue(isinstance(v.pyValue,xsi.Duration),"value type: %s"%repr(v.pyValue))
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
		self.assertTrue(v.typeCode==edm.SimpleType.DateTimeOffset,"date time offset type: %s"%repr(v.typeCode))
		self.assertTrue(isinstance(v.pyValue,iso.TimePoint),"value type: %s"%repr(v.pyValue))
		self.assertTrue(isinstance(v.pyValue,iso.TimePoint),"value type: %s"%repr(v.pyValue))
		for good in [
			"datetimeoffset'2002-10-10T17:00:00Z'",
			"datetimeoffset'2002-10-10T12:00:00Z'",
			"datetimeoffset'2002-10-10T12:00:00+05:00'",
			"datetimeoffset'2002-10-10T07:00:00Z'",
			"datetimeoffset'2002-10-10T00:00:00+05:00'",
			"datetimeoffset'2002-10-09T19:00:00Z'"
			]:
			v=ParseURILiteral(good)
			self.assertTrue(v.typeCode==edm.SimpleType.DateTimeOffset,"date time offset type: %s"%repr(v.typeCode))
			self.assertTrue(isinstance(v.pyValue,iso.TimePoint),"value type: %s"%repr(v.pyValue))
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
		self.assertTrue(dsURI.pathPrefix=='',"empty path prefix")
		self.assertTrue(dsURI.resourcePath=='/',"resource path")
		self.assertTrue(dsURI.queryOptions==[],'query options')
		self.assertTrue(dsURI.navPath==[],"navPath: %s"%repr(dsURI.navPath))
		dsURI=ODataURI('/','/x')
		self.assertTrue(dsURI.pathPrefix=='/x',"non-empty path prefix")
		self.assertTrue(dsURI.resourcePath==None,"resource path")
		dsURI=ODataURI('/x','/x')
		self.assertTrue(dsURI.pathPrefix=='/x',"non-empty path prefix")
		self.assertTrue(dsURI.resourcePath=='',"empty resource path, special case")
		self.assertTrue(dsURI.navPath==[],"empty navPath, special case: %s"%repr(dsURI.navPath))		
		dsURI=ODataURI('/x.svc/Products','/x.svc')
		self.assertTrue(dsURI.pathPrefix=='/x.svc',"svc path prefix")
		self.assertTrue(dsURI.resourcePath=='/Products',"resource path")
		self.assertTrue(len(dsURI.navPath)==1,"navPath: %s"%repr(dsURI.navPath))
		self.assertTrue(type(dsURI.navPath[0][0]) is UnicodeType,"entitySet name type")
		self.assertTrue(dsURI.navPath[0][0]=='Products',"entitySet name: Products")
		self.assertTrue(dsURI.navPath[0][1]==None,"entitySet no key-predicate")		
		dsURI=ODataURI('Products','/x.svc')
		self.assertTrue(dsURI.pathPrefix=='/x.svc',"svc path prefix")
		self.assertTrue(dsURI.resourcePath=='/Products',"resource path")
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
		self.assertTrue(set(dsURI.sysQueryOptions.keys())==set([SystemQueryOption.format,
			SystemQueryOption.top,SystemQueryOption.skip]),repr(dsURI.sysQueryOptions))
		self.assertTrue(dsURI.queryOptions==["space='%20'"],'query options')
		dsURI=ODataURI("Products()?$top=20&space='%20'&$format=json&$skip=10",'/x.svc')
		self.assertTrue(set(dsURI.sysQueryOptions.keys())==set([SystemQueryOption.format,
			SystemQueryOption.top,SystemQueryOption.skip]),repr(dsURI.sysQueryOptions))
		self.assertTrue(dsURI.queryOptions==["space='%20'"],'query options')		
		try:
			dsURI=ODataURI("Products()?$unsupported=10",'/x.svc')
			self.fail("$unsupported system query option")
		except InvalidSystemQueryOption:
			pass

	def testCaseCommonExpressions(self):
		dsURI=ODataURI("Products()?$filter=substringof(CompanyName,%20'bikes')",'/x.svc')
		self.assertTrue(isinstance(dsURI.sysQueryOptions[SystemQueryOption.filter],CommonExpression),"Expected common expression")
		dsURI=ODataURI("Products()?$filter=true%20and%20false",'/x.svc')
		f=dsURI.sysQueryOptions[SystemQueryOption.filter]
		self.assertTrue(isinstance(f,CommonExpression),"Expected common expression")
		self.assertTrue(isinstance(f,BinaryExpression),"Expected binary expression, %s"%repr(f))
		self.assertTrue(f.operator==Operator.boolAnd,"Expected and: %s"%repr(f.operator))		
		try:
			dsURI=ODataURI("Products()?$filter=true%20nand%20false",'/x.svc')
			self.fail("Expected exception for nand")
		except InvalidSystemQueryOption:
			pass
	
	def EvaluateCommon(self,expressionString):
		p=Parser(expressionString)
		e=p.ParseCommonExpression()
		return e.Evaluate(None)
		
	def testCaseEvaluateCommonExpression(self):
		# cursory check:
		# a commonExpression must represent any and all supported common expression types
		p=Parser("true and false")
		e=p.ParseCommonExpression()
		self.assertTrue(isinstance(e,CommonExpression),"Expected common expression")
		value=e.Evaluate(None)
		self.assertTrue(isinstance(value,edm.SimpleValue),"Expected EDM value; found %s"%repr(value))
		self.assertTrue(value.pyValue is False,"Expected false")
				
	def testCaseEvaluateBooleanExpression(self):
		# cursory check:
		# a boolCommonExpression MUST be a common expression that evaluates to the EDM Primitive type Edm.Boolean
		value=self.EvaluateCommon("true and false")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected false")
				
	def testCaseEvaluateParenExpression(self):
		"""a parenExpression MUST be evaluated by evaluating the
		expression with the parentheses, starting with the innermost
		parenthesized expressions and proceeding outwards...

		...the result of the parenExpression MUST be the result of the
		evaluation of the contained expression."""
		p=Parser("(false and false or true)")		# note that or is the weakest operator
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.assertTrue(value.pyValue is True,"Expected True")
		p=Parser("(false and (false or true))")		# should change the result
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("(((((((false) and (((false)) or true)))))))")
		self.assertTrue(value.pyValue is False,"Expected False - multibrackets")
				
	def testCaseEvaluateBooleanParenExpression(self):
		"""Cursory check: a boolParenExpression MUST be evaluated by
		evaluating the expression with the parentheses. The result of
		the boolParenExpression MUST ... be of the EDM Primitive type
		Edm.Boolean"""
		value=self.EvaluateCommon("(false and (false or true))")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected false")
	
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
		value=self.EvaluateCommon("2M add 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.assertTrue(value.pyValue == 4,"Expected 4")
		value=self.EvaluateCommon("2D add 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 4.0,"Expected 4")
		value=self.EvaluateCommon("2F add 2D")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 4.0,"Expected 4")
		value=self.EvaluateCommon("2 add 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue == 4L,"Expected 4")
		try:
			value=self.EvaluateCommon("2 add '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("2 add null")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue is None,"Expected None")

	def testCaseEvaluateSubExpression(self):
		"""See testCaseEvaluateAddExpression"""
		value=self.EvaluateCommon("4M sub 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.assertTrue(value.pyValue == 2,"Expected 2.0")
		value=self.EvaluateCommon("4D sub 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 2.0,"Expected 2.0")
		value=self.EvaluateCommon("4F sub 2D")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 2.0,"Expected 2.0")
		value=self.EvaluateCommon("4 sub 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue == 2L,"Expected 2L")
		try:
			value=self.EvaluateCommon("4 sub '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("4 sub null")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue is None,"Expected None")

	def testCaseEvaluateMulExpression(self):
		"""See testCaseEvaluateAddExpression"""
		value=self.EvaluateCommon("4M mul 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.assertTrue(value.pyValue == 8,"Expected 8.0")
		value=self.EvaluateCommon("4D mul 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 8.0,"Expected 8.0")
		value=self.EvaluateCommon("4F mul 2D")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 8.0,"Expected 8.0")
		value=self.EvaluateCommon("4 mul 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue == 8L,"Expected 8L")
		try:
			value=self.EvaluateCommon("4 mul '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("4 mul null")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue is None,"Expected None")

	def testCaseEvaluateDivExpression(self):
		"""See testCaseEvaluateAddExpression
		
		OData is ambiguous in the way it defines division as it makes reference only
		to the IEEE floating point operations.  For compatibility with SQL though we
		assume that integer division simple truncates fractional parts."""
		value=self.EvaluateCommon("4M div 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.assertTrue(value.pyValue == 2,"Expected 2")
		value=self.EvaluateCommon("4D div 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 2.0,"Expected 2.0")
		try:
			value=self.EvaluateCommon("4D div 0")
			self.fail("Division by zero")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("4F div 2D")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 2.0,"Expected 2.0")
		value=self.EvaluateCommon("5 div 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue == 2L,"Expected 2L")
		value=self.EvaluateCommon("-5 div 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue == -2L,"Expected -2L")
		try:
			value=self.EvaluateCommon("4 div '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("4 div null")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue is None,"Expected None")

	def testCaseEvaluateModExpression(self):
		"""See testCaseEvaluateAddExpression
		
		The data service SHOULD evaluate the operation represented by
		the modExpression, according to the rules of [IEEE754-2008]

		For integer division we just truncate fractional parts towards zero."""
		value=self.EvaluateCommon("5.5M mod 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.assertTrue(value.pyValue == 1.5,"Expected 1.5")
		value=self.EvaluateCommon("5.5D mod 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 1.5,"Expected 1.5")
		try:
			value=self.EvaluateCommon("5.5D mod 0")
			self.fail("Division by zero")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("5.5F mod 2D")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 1.5,"Expected 1.5")
		value=self.EvaluateCommon("5 mod 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue == 1L,"Expected 1L")
		value=self.EvaluateCommon("-5 mod 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue == -1L,"Expected -1L")
		try:
			value=self.EvaluateCommon("5 mod '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("5 mod null")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue is None,"Expected None")


	def testCaseEvaluateNegateExpression(self):
		"""See testCaseEvaluateAddExpression for list of simple types.
		
		..data service SHOULD follow the unary numeric promotion rules
		... to implicitly convert the operand to a supported EDM
		Primitive type

		the result of evaluating the negateExpression SHOULD always be
		equal to the result of evaluating the subExpression where one
		operand is the value zero and the other is the value of the
		operand.  [comment applies to null processing too]"""
		value=self.EvaluateCommon("-(2M)")
		self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.assertTrue(value.pyValue == -2,"Expected -2.0")
		value=self.EvaluateCommon("-(2D)")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == -2.0,"Expected -2.0")
		p=Parser("-(-2F)")	# unary numeric promotion to Double - a bit weird 
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 2.0,"Expected 2.0")
		value=self.EvaluateCommon("-(2L)")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue == -2L,"Expected -2L")
		try:
			value=self.EvaluateCommon("-'2'")
			self.fail("String promotion to numeric")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("-null")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue is None,"Expected None")


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
		value=self.EvaluateCommon("false and false")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected False")
		try:
			value=self.EvaluateCommon("false and 0")
			self.fail("Integer promotion to Boolean")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("false and true")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("true and false")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("true and true")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("true and null")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("false and null")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("false and false")
		self.assertTrue(value.pyValue is False,"Expected False")


	def testCaseEvaluateOrExpression(self):
		"""See testCaseEvaluateAndExpression for more details.
		
		...data service MUST evaluate the expression to the value of
		true if at least one of the operands is true after being
		evaluated. If both operands are false after being evaluated, the
		expression MUST evaluate to the value of false"""
		value=self.EvaluateCommon("false or false")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected False")
		try:
			value=self.EvaluateCommon("false or 0")
			self.fail("Integer promotion to Boolean")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("false or true")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("true or false")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("true or true")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("true or null")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("false or null")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("null or null")
		self.assertTrue(value.pyValue is False,"Expected False")

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
		
		(For tests on EntityType instances see the same method in the
		sample data set later)
			
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
		value=self.EvaluateCommon("2M eq 3M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("2D eq 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("2F eq 2D")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("2 eq 2L")
		self.assertTrue(value.pyValue is True,"Expected True")
		try:
			value=self.EvaluateCommon("2 eq '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("'2' eq '2'")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' eq datetime'2013-08-30T18:49'")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' eq datetime'2013-08-30T18:49:01'")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' eq guid'b3afeebc-9658-4699-9d9c-1df551fd6814'")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' eq guid'3fa6109e-f09c-4c5e-a5f3-6cf38d35c9b5'")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("X'DEADBEEF' eq binary'deadbeef'")
		self.assertTrue(value.pyValue is True,"Expected True")			
		value=self.EvaluateCommon("X'DEAD' eq binary'BEEF'")
		self.assertTrue(value.pyValue is False,"Expected False")			
		value=self.EvaluateCommon("2 eq null")
		self.assertTrue(value.pyValue is False,"Expected False")			
		value=self.EvaluateCommon("null eq null")
		self.assertTrue(value.pyValue is True,"Expected True")			

	def testCaseEvaluateNeExpression(self):
		"""See testCaseEvaluateEqExpression for details."""
		value=self.EvaluateCommon("2M ne 3M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("2D ne 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("2F ne 2D")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("2 ne 2L")
		self.assertTrue(value.pyValue is False,"Expected False")
		try:
			value=self.EvaluateCommon("2 ne '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("'2' ne '2'")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' ne datetime'2013-08-30T18:49'")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' ne datetime'2013-08-30T18:49:01'")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' ne guid'b3afeebc-9658-4699-9d9c-1df551fd6814'")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' ne guid'3fa6109e-f09c-4c5e-a5f3-6cf38d35c9b5'")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("X'DEADBEEF' ne binary'deadbeef'")
		self.assertTrue(value.pyValue is False,"Expected False")			
		value=self.EvaluateCommon("X'DEAD' ne binary'BEEF'")
		self.assertTrue(value.pyValue is True,"Expected True")			
		value=self.EvaluateCommon("2 ne null")
		self.assertTrue(value.pyValue is True,"Expected True")			
		value=self.EvaluateCommon("null ne null")
		self.assertTrue(value.pyValue is False,"Expected False")			


	def testCaseEvaluateLtExpression(self):
		"""...operand expressions MUST evaluate to a value of one of the
		following EDM Primitive types:
			Edm.Decimal
			Edm.Double
			Edm.Single
			Edm.Int32
			Edm.Int64
			Edm.String
			Edm.DateTime
			Edm.Guid

		...data service SHOULD follow the binary numeric promotion
		
		...The EDM Primitive type of the result of evaluating the
		ltExpression MUST be Edm.Boolean.

		...a data service MUST return a value of true if the value of
		the first operand is less than the value of the second operand,
		false if not.
		
		...for relational operators, a data service MUST return the
		value false if one or both of the operands is null."""
		value=self.EvaluateCommon("2M lt 3M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("2D lt 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("2.1F lt 2D")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("2 lt 3L")
		self.assertTrue(value.pyValue is True,"Expected True")
		try:
			value=self.EvaluateCommon("2 lt '3'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("'20' lt '3'")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' lt datetime'2013-08-30T18:49'")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' lt datetime'2013-08-30T18:49:01'")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' lt guid'b3afeebc-9658-4699-9d9c-1df551fd6814'")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' lt guid'3fa6109e-f09c-4c5e-a5f3-6cf38d35c9b5'")
		self.assertTrue(value.pyValue is False,"Expected False")
		try:
			p=Parser("X'DEADBEEF' lt binary'deadbeef'")
			e=p.ParseCommonExpression()
			value=e.Evaluate(None)
			self.fail("Relational operation on binary data")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("2 lt null")
		self.assertTrue(value.pyValue is False,"Expected False")			
		value=self.EvaluateCommon("null lt null")
		self.assertTrue(value.pyValue is False,"Expected False")			

	def testCaseEvaluateLeExpression(self):
		"""See testCaseEvaluateLtExpression for more information - abbreviated tests"""
		value=self.EvaluateCommon("2D le 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' le datetime'2013-08-30T18:49:00'")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("2 le null")
		self.assertTrue(value.pyValue is False,"Expected False")			
		value=self.EvaluateCommon("null le null")
		self.assertTrue(value.pyValue is False,"Expected False")			
		
	def testCaseEvaluateGtExpression(self):
		"""See testCaseEvaluateLtExpression for more information - abbreviated tests"""
		value=self.EvaluateCommon("2D gt 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' gt datetime'2013-08-30T18:49:00'")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("2 gt null")
		self.assertTrue(value.pyValue is False,"Expected False")			
		value=self.EvaluateCommon("null gt null")
		self.assertTrue(value.pyValue is False,"Expected False")			
		
	def testCaseEvaluateGeExpression(self):
		"""See testCaseEvaluateLtExpression for more information - abbreviated tests"""
		value=self.EvaluateCommon("2D ge 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' ge datetime'2013-08-30T18:49:00'")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("2 ge null")
		self.assertTrue(value.pyValue is False,"Expected False")			
		value=self.EvaluateCommon("null ge null")
		self.assertTrue(value.pyValue is False,"Expected False")			

	def testCaseEvaluateNotExpression(self):
		"""...operation is supported ... as long as the operand
		expression evaluates to a value of the EDM Primitive type
		Edm.Boolean. The data service SHOULD NOT support operand
		expressions of any other EDM Primitive type

		The EDM Primitive type of the result of evaluating the
		notExpression MUST be Edm.Boolean.

		the data service MUST evaluate the logical negation operation by
		returning false if the operand value is true and returning true
		if the operand value is false.
		
		...for unary operators, a data service MUST return the value
		null if the operand value is null."""
		value=self.EvaluateCommon("not false")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("not true")
		self.assertTrue(value.pyValue is False,"Expected False")
		try:
			value=self.EvaluateCommon("not 1")
			self.fail("Integer promotion to Boolean")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("not null")
		self.assertTrue(value.pyValue is None,"Expected NULL")
	
	def testCaseEvaluateIsOfExpression(self):
		"""...the data service MAY<24> support some or all of the common
		expressions as the first operand value... the data service can
		support the first operand as being optional... interpreted to
		apply to the entity instance specified by the navigation portion
		of the request URI.
		
		The second operand MUST be a stringLiteral that represents the
		name of a known entity or EDM Primitive type.

		The EDM Primitive type of the result of evaluating the
		isofExpression MUST be Edm.Boolean.

		...the data service MUST evaluate the isofExpression to return a
		value of true if the targeted instance can be converted to the
		specified type. If the conversion is not allowed, then the
		expression MUST be evaluated to false.
		
		data service can support evaluating an operand with a null value
		following the rules defined in Binary Numeric Promotions. [It
		isn't clear what this means at all, clearly there is a typo.  We
		add our own rule... isof(NULL,'type') always returns False, in
		keeping with other boolean operators]
		
		It is also not clear which 'explicit conversions' are allowed in
		the Edm model and which aren't.  The approach taken is to allow
		only the numeric promotions supported for binary operations,
		which is a bit tight but perhaps safer than allowing forms which
		may not be portable."""
		value=self.EvaluateCommon("isof(2D,'Edm.Double')")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("isof(2M,'Edm.Double')")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("isof(2,'Edm.Double')")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("isof(2.0D,'Edm.Single')")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("isof('x','Edm.String')")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("isof(X'DEAD','Edm.String')")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("isof(false or true,'Edm.Boolean')")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("isof(null,'Edm.String')")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("isof('Edm.String')")
		self.assertTrue(value.pyValue is False,"Expected False")
	
	def testCaseEvaluateCastExpression(self):
		"""...see testCaseEvaluateIsOfExpression for more information.
		
		The type of the result of evaluating the castExpression MUST be
		the same type as represented by the string literal value from
		the second operand.
		
		A data service MAY support any cast operations where there
		exists an explicit conversion from the targeted instance (first
		operand) to the type represented by second operand. In all other
		cases, the data service SHOULD NOT support the specified cast
		operation.

		The data service MAY support evaluating an operand with a null
		value following the rules defined in Lifted Operators. [again,
		not 100% clear what these are.]"""
		value=self.EvaluateCommon("cast(2D,'Edm.Double')")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue==2.0,"Expected 2.0")
		value=self.EvaluateCommon("cast(2L,'Edm.Single')")
		self.assertTrue(value.typeCode==edm.SimpleType.Single,"Expected Single")
		self.assertTrue(value.pyValue==2.0,"Expected 2.0")
		value=self.EvaluateCommon("cast(2,'Edm.Int64')")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue==2L,"Expected 2")
		try:
			value=self.EvaluateCommon("cast(2.0D,'Edm.Single')")
			self.fail("Double cast to Single")
		except:
			pass
		value=self.EvaluateCommon("cast('x','Edm.String')")
		self.assertTrue(value.pyValue=='x',"Expected 'x'")
		try:
			value=self.EvaluateCommon("cast(X'DEAD','Edm.String')")
			self.fail("Binary cast to String")
		except:
			pass
		try:
			value=self.EvaluateCommon("cast(1,'Edm.Boolean')")
			self.fail("1 cast to Boolean")
		except:
			pass
		value=self.EvaluateCommon("cast(null,'Edm.String')")
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected String")
		self.assertTrue(value.pyValue is None,"Expected None")
		value=self.EvaluateCommon("cast('Edm.Int16')")
		self.assertTrue(value.typeCode==edm.SimpleType.Int16,"Expected Int16")
		self.assertTrue(value.pyValue is None,"Expected None")		
	
	def testCaseEvaluateBooleanCastExpression(self):
		# cursory check:
		value=self.EvaluateCommon("cast(true,'Edm.Boolean')")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is True,"Expected True")

	def testCaseEvaluateBooleanLiteralExpression(self):
		"""the type of the boolLiteralExpression MUST always be the EDM
		primitive type Edm.Boolean."""
		value=self.EvaluateCommon("true")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("false")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected False")

	def testCaseEvaluateLiteralExpression(self):
		"""the type of the literalExpression MUST be the EDM Primitive
		type for the lexical representation of the literal:
		
			null
			Edm.Binary
			Edm.Boolean
			Edm.Byte		
			Edm.DateTime
			Edm.Decimal
			Edm.Double
			Edm.Single
			Edm.Guid
			Edm.Int16
			Edm.Int32
			Edm.Int64
			Edm.SByte,
			Edm.String,
			Edm.Time,
			Edm.DateTimeOffset"""
		value=self.EvaluateCommon("null")
		self.assertTrue(value.typeCode==None,"Expected None")
		self.assertTrue(value.pyValue==None,"Expected None")
		value=self.EvaluateCommon("X'DEAD'")
		self.assertTrue(value.typeCode==edm.SimpleType.Binary,"Expected Binary")
		self.assertTrue(value.pyValue=='\xde\xad')
		value=self.EvaluateCommon("true")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Booelan")
		self.assertTrue(value.pyValue==True)
		value=self.EvaluateCommon("123")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue==123)
		value=self.EvaluateCommon("datetime'2013-08-31T15:28'")
		self.assertTrue(value.typeCode==edm.SimpleType.DateTime,"Expected DateTime")
		self.assertTrue(value.pyValue.date.year==13)
		value=self.EvaluateCommon("123.5M")
		self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.assertTrue(value.pyValue==123.5)
		value=self.EvaluateCommon("123.5D")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue==123.5)
		value=self.EvaluateCommon("123.5F")
		self.assertTrue(value.typeCode==edm.SimpleType.Single,"Expected Single")
		self.assertTrue(value.pyValue==123.5)
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814'")
		self.assertTrue(value.typeCode==edm.SimpleType.Guid,"Expected Guid")
		self.assertTrue(value.pyValue==uuid.UUID('b3afeebc-9658-4699-9d9c-1df551fd6814'))
		value=self.EvaluateCommon("123456")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue==123456)
		value=self.EvaluateCommon("123456L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue==123456L)
		value=self.EvaluateCommon("-123")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue==-123)
		value=self.EvaluateCommon("'123'")
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected String")
		self.assertTrue(value.pyValue=='123')
		value=self.EvaluateCommon("time'P123D'")
		self.assertTrue(value.typeCode==edm.SimpleType.Time,"Expected Time")
		self.assertTrue(value.pyValue.days==123)
		value=self.EvaluateCommon("datetimeoffset'2002-10-10T12:00:00-05:00'")
		self.assertTrue(value.typeCode==edm.SimpleType.DateTimeOffset,"Expected DateTimeOffset")
		self.assertTrue(value.pyValue==iso.TimePoint('2002-10-10T12:00:00-05:00'))

	def testCaseEvaluateMethodCallExpression(self):
		"""Cursory check only."""
		value=self.EvaluateCommon("length('x')")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue==1)

	def testCaseEvaluateBooleanMethodCallExpress(self):
		"""Cursory check only."""
		value=self.EvaluateCommon("startswith('xyz','x')")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue==True)

	def testCaseEvaluateEndsWithExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The endsWithMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		...the result of evaluating the endsWithMethodCallExpression
		SHOULD be a value of the EDM Primitive type Edm.Boolean.

		...the data service SHOULD evaluate ... by returning a Boolean
		value indicating whether the end of the first parameter
		values matches the second parameter value."""
		value=self.EvaluateCommon("endswith('startswith','with')")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue==True)
		value=self.EvaluateCommon("endswith('startswith','start')")
		self.assertTrue(value.pyValue==False)
		value=self.EvaluateCommon("endswith('startswith','WITH')")
		# not case insensitive
		self.assertTrue(value.pyValue==False)
		try:
			value=self.EvaluateCommon("endswith('3.14',4)")
			self.fail("integer as suffix")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("endswith('3.14')")
			self.fail("1 parameter")
		except EvaluationError:
			pass

	def testCaseEvaluateIndexOfExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The indexOfMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		...the EDM Primitive type of the result of evaluating the
		indexOfMethodCallExpression SHOULD be a value of the EDM
		Primitive type Edm.Int32.
		
		the data service SHOULD evaluate ... by returning an integer
		value indicating the index of the first occurrence of the second
		parameter value in the first parameter value. If no index is
		found, a value of -1 SHOULD be returned."""
		value=self.EvaluateCommon("indexof('startswith','tart')")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue==1)
		value=self.EvaluateCommon("indexof('startswith','start')")
		self.assertTrue(value.pyValue==0)
		value=self.EvaluateCommon("indexof('startswith','t')")
		self.assertTrue(value.pyValue==1)
		# not case insensitive
		value=self.EvaluateCommon("indexof('startswith','W')")
		self.assertTrue(value.pyValue==-1)
		try:
			value=self.EvaluateCommon("indexof('3.14',1)")
			self.fail("integer as parameter")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("indexof('3.14')")
			self.fail("1 parameter")
		except EvaluationError:
			pass

	def testCaseEvaluateReplaceExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The replaceMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		the EDM Primitive type of the result of evaluating the
		replaceMethodCallExpression SHOULD be a value of the EDM
		Primitive type Edm.String.

		the data service SHOULD evaluate ... by returning a string value
		with all occurrences of the second parameter value replaced by
		the third parameter value in the first parameter value."""
		value=self.EvaluateCommon("replace('startswith','tart','cake')")
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected String")
		self.assertTrue(value.pyValue==u"scakeswith")
		value=self.EvaluateCommon("replace('startswith','t','x')")
		self.assertTrue(value.pyValue==u"sxarxswixh")
		# not case insensitive
		value=self.EvaluateCommon("replace('sTartswith','t','x')")
		self.assertTrue(value.pyValue==u"sTarxswixh")
		value=self.EvaluateCommon("replace('startswith','t','tx')")
		self.assertTrue(value.pyValue==u"stxartxswitxh")
		try:
			value=self.EvaluateCommon("replace('3.14','1',2)")
			self.fail("integer as parameter")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("replace('3.14','1')")
			self.fail("2 parameter")
		except EvaluationError:
			pass

	def testCaseEvaluateStartsWithExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The startsWithMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		...the result of evaluating the startsWithMethodCallExpression
		SHOULD be a value of the EDM Primitive type Edm.Boolean.

		...the data service SHOULD evaluate ... by returning a Boolean
		value indicating whether the beginning of the first parameter
		values matches the second parameter value."""
		value=self.EvaluateCommon("startswith('startswith','start')")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue==True)
		value=self.EvaluateCommon("startswith('startswith','end')")
		self.assertTrue(value.pyValue==False)
		value=self.EvaluateCommon("startswith('startswith','Start')")
		# not case insensitive
		self.assertTrue(value.pyValue==False)
		try:
			value=self.EvaluateCommon("startswith('3.14',3)")
			self.fail("integer as prefix")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("startswith('3.14')")
			self.fail("1 parameter")
		except EvaluationError:
			pass

	def testCaseEvaluateToLowerExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The toLowerMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		...the EDM Primitive type of the result ... SHOULD be a value of
		the EDM Primitive type Edm.String.

		...the data service SHOULD evaluate ... by returning a string
		value with the contents of the parameter value converted to
		lower case."""
		value=self.EvaluateCommon("tolower('Steve')")
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected String")
		self.assertTrue(value.pyValue==u"steve")
		value=self.EvaluateCommon(u"tolower('CAF\xc9')")
		self.assertTrue(value.pyValue==u'caf\xe9')
		value=self.EvaluateCommon(u"tolower('caf\xe9')")
		self.assertTrue(value.pyValue==u'caf\xe9')
		try:
			value=self.EvaluateCommon("tolower(3.14F)")
			self.fail("floating lower")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("tolower('Steve','John')")
			self.fail("2 parameters")
		except EvaluationError:
			pass

	def testCaseEvaluateToUpperExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The toUpperMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		...the EDM Primitive type of the result ... SHOULD be a value of
		the EDM Primitive type Edm.String.

		...the data service SHOULD evaluate ... by returning a string
		value with the contents of the parameter value converted to
		upper case."""
		value=self.EvaluateCommon("toupper('Steve')")
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected String")
		self.assertTrue(value.pyValue==u"STEVE")
		value=self.EvaluateCommon(u"toupper('CAF\xc9')")
		self.assertTrue(value.pyValue==u'CAF\xc9')
		value=self.EvaluateCommon(u"toupper('caf\xe9')")
		self.assertTrue(value.pyValue==u'CAF\xc9')
		try:
			value=self.EvaluateCommon("toupper(3.14F)")
			self.fail("floating upper")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("toupper('Steve','John')")
			self.fail("2 parameters")
		except EvaluationError:
			pass

	def testCaseEvaluateTrimExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The trimMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		the EDM Primitive type of the result of evaluating the
		trimMethodCallExpression SHOULD be a value of the EDM Primitive
		type Edm.String.

		the data service SHOULD evaluate ... by returning a string value
		with the contents of the parameter value with all leading and
		trailing white-space characters removed."""
		value=self.EvaluateCommon("trim('  Steve\t\n\r \r\n')")
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected String")
		self.assertTrue(value.pyValue==u"Steve")
		value=self.EvaluateCommon(u"trim(' C  a  f \xe9 ')")
		self.assertTrue(value.pyValue==u'C  a  f \xe9')
		try:
			value=self.EvaluateCommon("trim(3.14F)")
			self.fail("floating trim")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("trim('Steve','John')")
			self.fail("2 parameters")
		except EvaluationError:
			pass

	def testCaseEvaluateSubstringExpression(self):
		"""The first parameter expression MUST evaluate to a value of
		the EDM Primitive type Edm.String. The second and third
		parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.Int32.

		The substringMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		the EDM Primitive type of the result of evaluating the
		substringMethodCallExpression SHOULD be a value of the EDM
		Primitive type Edm.String.

		the data service SHOULD evaluate ... by returning the string
		value starting at the character index specified by the second
		parameter value in the first parameter string value. If the
		optional third parameter is specified, the resulting string
		SHOULD be the length (in characters) of the third parameter
		value. Otherwise, the entire string from the specified starting
		index is returned."""
		value=self.EvaluateCommon("substring('startswith',1,4)")
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected String")
		self.assertTrue(value.pyValue==u"tart")
		value=self.EvaluateCommon("substring('startswith',1)")
		self.assertTrue(value.pyValue==u"tartswith")
		try:
			value=self.EvaluateCommon("substring('startswith',1.0D,4)")
			self.fail("double as parameter")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("substring('3.14')")
			self.fail("1 parameter")
		except EvaluationError:
			pass
	
	def testCaseEvaluateSubstringOfExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The substringOfMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		the EDM Primitive type of the result of evaluating the
		substringOfMethodCallExpression SHOULD be a value of the EDM
		Primitive type Edm.Boolean.

		...the data service SHOULD evaluate ... by returning a Boolean
		value indicating whether the second parameter string value
		occurs in the first parameter string value."""
		value=self.EvaluateCommon("substringof('startswith','tart')")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue==True)
		value=self.EvaluateCommon("substringof('startswith','start')")
		self.assertTrue(value.pyValue==True)
		value=self.EvaluateCommon("substringof('startswith','t')")
		self.assertTrue(value.pyValue==True)
		# not case insensitive
		value=self.EvaluateCommon("substringof('startswith','W')")
		self.assertTrue(value.pyValue==False)
		try:
			value=self.EvaluateCommon("substringof('3.14',1)")
			self.fail("integer as parameter")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("substringof('3.14')")
			self.fail("1 parameter")
		except EvaluationError:
			pass
		
	def testCaseEvaluateConcatExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The concatMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		the EDM Primitive type of the result of evaluating the
		concatMethodCallExpression SHOULD be a value of the EDM
		Primitive type Edm.String.

		the data service SHOULD evaluate ... by returning a string value
		which is the first and second parameter values merged together
		with the first parameter value coming first in the result."""
		value=self.EvaluateCommon("concat('starts','with')")
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected String")
		self.assertTrue(value.pyValue==u"startswith")
		value=self.EvaluateCommon("concat('3.1',concat('4','159'))")
		self.assertTrue(value.pyValue==u"3.14159")
		try:
			value=self.EvaluateCommon("concat('3.14',1)")
			self.fail("integer as parameter")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("concat('3.14')")
			self.fail("1 parameter")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("concat('3.1','4','159')")
			self.fail("3 parameters")
		except EvaluationError:
			pass
	
	def testCaseEvaluateLengthExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The lengthMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		the EDM Primitive type of the result of evaluating the
		lengthMethodCallExpression SHOULD be a value of the EDM
		Primitive type Edm.Int32.

		the data service SHOULD evaluate ... by returning the number of
		characters in the specified parameter value."""
		value=self.EvaluateCommon("length('Steve')")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue==5)
		value=self.EvaluateCommon(u"length('CAF\xc9')")
		self.assertTrue(value.pyValue==4)
		value=self.EvaluateCommon(u"length('')")
		self.assertTrue(value.pyValue==0)
		try:
			value=self.EvaluateCommon("length(3.14F)")
			self.fail("floating length")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("length('Steve','John')")
			self.fail("2 parameters")
		except EvaluationError:
			pass		

	def testCaseEvaluateYearExpression(self):
		"""The parameter expression MUST evaluate to a value of the EDM
		Primitive type Edm.DateTime.

		The yearMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.

		the EDM Primitive type of the result of evaluating the
		yearMethodCallExpression SHOULD be the EDM Primitive type
		Edm.Int32.

		the data service SHOULD evaluate ... by returning the year
		component value of the parameter value.
		
		We implement very similar tests for month, day, hour, minute and second"""
		for f,r in (
			("year",2013),
			("month",9),
			("day",1),
			("hour",10),
			("minute",56),
			("second",0)):
			value=self.EvaluateCommon("%s(datetime'2013-09-01T10:56')"%f)
			self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
			self.assertTrue(value.pyValue==r)
			try:
				value=self.EvaluateCommon("%s(datetimeoffset'2013-09-01T10:56:12-05:00')"%f)
				self.fail("datetimeoffset %s"%f)
			except EvaluationError:
				pass
			try:
				value=self.EvaluateCommon("%s(datetime'2013-09-01T10:56',datetime'2013-09-01T10:57')"%f)
				self.fail("2 parameters")
			except EvaluationError:
				pass

	def testCaseEvaluateRoundExpression(self):
		"""The parameter expression MUST evaluate to a value of one of
		the following EDM Primitive types:
			Edm.Decimal
			Edm.Double

		The roundMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.

		data service SHOULD follow the numeric promotion rules for
		method call parameters defined in Binary numeric promotions to
		implicitly convert the parameters to a supported EDM Primitive
		type.
		
		The EDM Primitive type of the result of evaluating the
		roundMethodCallExpression MUST be the same type as the parameter.
		
		the data service SHOULD evaluate ... by returning the nearest
		integral value to the parameter value, following the rules
		defined in [IEEE754-2008] for the rounding operation.
		
		We cover floor and ceil using similar routines..."""
		for f,r in (
			("round",(2,2,-2,2,3,-3,2,3)),
			("floor",(1,2,-3,1,2,-3,2,3)),
			("ceiling",(2,3,-2,2,3,-2,3,3))):
			value=self.EvaluateCommon("%s(1.5D)"%f)
			self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
			self.assertTrue(value.pyValue==r[0])
			# check rounding to even for binary floating point
			value=self.EvaluateCommon("%s(2.5D)"%f)
			self.assertTrue(value.pyValue==r[1])
			value=self.EvaluateCommon("%s(-2.5D)"%f)
			self.assertTrue(value.pyValue==r[2])
			value=self.EvaluateCommon("%s(1.5M)"%f)
			self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
			self.assertTrue(value.pyValue==r[3])
			# check rounding away from zero for decimals
			value=self.EvaluateCommon("%s(2.5M)"%f)
			self.assertTrue(value.pyValue==r[4])
			value=self.EvaluateCommon("%s(-2.5M)"%f)
			self.assertTrue(value.pyValue==r[5])
			# single promotes to double
			value=self.EvaluateCommon("%s(2.5F)"%f)
			self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
			self.assertTrue(value.pyValue==r[6])
			# integers promote to decimal - seems a bit strange but there you go
			value=self.EvaluateCommon("%s(3)"%f)
			self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
			self.assertTrue(value.pyValue==r[7])
			try:
				value=self.EvaluateCommon("%s('3')"%f)
				self.fail("round string parameter")
			except EvaluationError:
				pass
			try:
				value=self.EvaluateCommon("%s(3.1D,3.2D)"%f)
				self.fail("two parameters")
			except EvaluationError:
				pass		

	def testCaseOperatorPrecedence(self):
		value=self.EvaluateCommon("--2 mul 3 div 1 mul 2 mod 2 add 2 div 2 sub 1 eq 2 and false or true")
		self.assertTrue(value.pyValue is True)
			
	def testCaseEntitySet(self):
		dsURI=ODataURI("Products()?$format=json&$top=20&$skip=10&space='%20'",'/x.svc')
		self.assertTrue(dsURI.resourcePath=='/Products()',"resource path")
		self.assertTrue(set(dsURI.sysQueryOptions.keys())==set([SystemQueryOption.format,
			SystemQueryOption.top,SystemQueryOption.skip]),repr(dsURI.sysQueryOptions))
		self.assertTrue(dsURI.queryOptions==["space='%20'"],'query options')
		self.assertTrue(dsURI.navPath==[(u'Products',{})],"entitySet: Products, found %s"%repr(dsURI.navPath))
		dsURI=ODataURI('Products()/$count','/x.svc')
		self.assertTrue(dsURI.resourcePath=='/Products()/$count',"resource path")
		self.assertTrue(dsURI.sysQueryOptions=={},'sysQueryOptions')
		self.assertTrue(dsURI.queryOptions==[],'query options')
		self.assertTrue(dsURI.navPath==[(u'Products',{})],"path: %s"%repr(dsURI.navPath))
		self.assertTrue(dsURI.pathOption==PathOption.count,"$count recognised")
		dsURI=ODataURI('Products(1)/$value','/x.svc')
		self.assertTrue(dsURI.navPath==[(u'Products',{'':1})],"path: %s"%repr(dsURI.navPath))
		self.assertTrue(dsURI.pathOption==PathOption.value,"$value recognised")
		dsURI=ODataURI('Products(x=1,y=2)','/x.svc')
		self.assertTrue(dsURI.navPath==[(u'Products',{u'x':1,u'y':2})],"path: %s"%repr(dsURI.navPath))
		
	def testCaseExpand(self):
		"""Redundant expandClause rules on the same data service URI can
		be considered valid, but MUST NOT alter the meaning of the
		URI."""
		dsURI=ODataURI("Customers?$expand=Orders",'/x.svc')
		expand=dsURI.sysQueryOptions[SystemQueryOption.expand]
		self.assertTrue(len(expand)==1,"One path")
		self.assertTrue(expand['Orders'] is None,"Orders nav path")
		dsURI=ODataURI("Customers?$expand=Orders,Orders",'/x.svc')
		expand=dsURI.sysQueryOptions[SystemQueryOption.expand]
		self.assertTrue(len(expand)==1,"One path")
		self.assertTrue(expand['Orders'] is None,"redundant Orders nav path")
		dsURI=ODataURI("Orders?$expand=OrderLines/Product,Customer",'/x.svc')
		expand=dsURI.sysQueryOptions[SystemQueryOption.expand]
		self.assertTrue(expand['OrderLines']=={'Product':None},"OrderLines expansion: %s"%str(expand))
		self.assertTrue(expand['Customer'] is None,"Customer expansion")
	
	def testCaseFilter(self):
		dsURI=ODataURI("Orders?$filter=ShipCountry%20eq%20'France'",'/x.svc')
		filter=dsURI.sysQueryOptions[SystemQueryOption.filter]
		self.assertTrue(isinstance(filter,BinaryExpression),"Binary expression component")
		self.assertTrue(isinstance(filter.operands[0],PropertyExpression))
		self.assertTrue(filter.operands[0].name=="ShipCountry")
		dsURI=ODataURI("Orders?$filter%20=%20Customers/ContactName%20ne%20'Fred'",'/x.svc')
		filter=dsURI.sysQueryOptions[SystemQueryOption.filter]
		self.assertTrue(filter.operands[0].operands[1].name=="ContactName")
	
	def testCaseFormat(self):
		dsURI=ODataURI("Orders?$format=json",'/x.svc')
		format=dsURI.sysQueryOptions[SystemQueryOption.format]
		self.assertTrue(isinstance(format,http.AcceptList),"Format is an HTTP AcceptList instance")
		self.assertTrue(str(format)=='application/json',str(format[0]))

	def testCaseOrderby(self):
		dsURI=ODataURI("Orders?$orderby=ShipCountry",'/x.svc')
		orderBy=dsURI.sysQueryOptions[SystemQueryOption.orderby]
		self.assertTrue(len(orderBy)==1,"Single orderBy clause")
		orderBy=orderBy[0]
		self.assertTrue(orderBy[1]==1,"default is asc")
		self.assertTrue(isinstance(orderBy[0],PropertyExpression),"OrderBy is a property expression")
		self.assertTrue(orderBy[0].name=='ShipCountry',str(orderBy[0]))
		dsURI=ODataURI("Orders?$orderby%20=%20ShipCountry%20ne%20'France'%20desc",'/x.svc')
		orderBy=dsURI.sysQueryOptions[SystemQueryOption.orderby]
		orderBy=orderBy[0]
		self.assertTrue(orderBy[1]==-1,"desc")
		self.assertTrue(isinstance(orderBy[0],BinaryExpression),"OrderBy is a binary expression")
		self.assertTrue(orderBy[0].operands[0].name=='ShipCountry',str(orderBy[0].operands[0]))
		self.assertTrue(orderBy[0].operands[0].name=='ShipCountry',str(orderBy[0].operands[0]))
		dsURI=ODataURI("Orders?$orderby%20=%20ShipCountry%20ne%20'France'%20desc,OrderID%20asc",'/x.svc')
		orderBy=dsURI.sysQueryOptions[SystemQueryOption.orderby]
		self.assertTrue(len(orderBy)==2,"Two orderBy clauses")
					
	def testCaseSkip(self):
		"""The value of this query option ... MUST be an integer greater
		than or equal to zero. If a value less than 0 is specified, the
		URI should be considered malformed."""
		dsURI=ODataURI("Orders?$orderby=OrderDate%20desc&$skip=10",'/x.svc')
		skip=dsURI.sysQueryOptions[SystemQueryOption.skip]
		self.assertTrue(type(skip) is IntType,"skip type")
		self.assertTrue(skip==10,"skip 10")
		dsURI=ODataURI("Customers('ALFKI')/Orders?$skip=10",'/x.svc')
		skip=dsURI.sysQueryOptions[SystemQueryOption.skip]
		self.assertTrue(skip==10,"skip 10")
		dsURI=ODataURI("Orders?$orderby=OrderDate%20desc&$skip=0",'/x.svc')
		skip=dsURI.sysQueryOptions[SystemQueryOption.skip]
		self.assertTrue(skip==0,"skip 0")
		try:
			dsURI=ODataURI("Orders?$orderby=OrderDate%20desc&$skip=-1",'/x.svc')
			self.fail("skip=-1")
		except InvalidSystemQueryOption:
			pass

	def testCaseTop(self):
		"""The value of this query option ... MUST be an integer greater
		than or equal to zero. If a value less than 0 is specified, the
		URI should be considered malformed."""
		dsURI=ODataURI("Orders?$orderby=OrderDate%20desc&$top=10",'/x.svc')
		top=dsURI.sysQueryOptions[SystemQueryOption.top]
		self.assertTrue(type(top) is IntType,"top type")
		self.assertTrue(top==10,"top 10")
		dsURI=ODataURI("Customers('ALFKI')/Orders?$top=10",'/x.svc')
		top=dsURI.sysQueryOptions[SystemQueryOption.top]
		self.assertTrue(top==10,"top 10")
		dsURI=ODataURI("Orders?$orderby=OrderDate%20desc&$top=0",'/x.svc')
		top=dsURI.sysQueryOptions[SystemQueryOption.top]
		self.assertTrue(top==0,"top 0")
		try:
			dsURI=ODataURI("Orders?$orderby=OrderDate%20desc&$top=-1",'/x.svc')
			self.fail("top=-1")
		except InvalidSystemQueryOption:
			pass

	def testCaseSkipToken(self):
		"""The value of this query option ... MUST be an integer greater
		than or equal to zero. If a value less than 0 is specified, the
		URI should be considered malformed."""
		dsURI=ODataURI("Orders?$orderby=OrderDate%20desc&$skiptoken=AEF134ad",'/x.svc')
		skiptoken=dsURI.sysQueryOptions[SystemQueryOption.skiptoken]
		self.assertTrue(type(skiptoken) is UnicodeType,"skiptoken type")
		self.assertTrue(skiptoken==u"AEF134ad","skiptoken opqque string")
		dsURI=ODataURI("Customers('ALFKI')/Orders?$skiptoken=0%2010",'/x.svc')
		skiptoken=dsURI.sysQueryOptions[SystemQueryOption.skiptoken]
		self.assertTrue(skiptoken==u"0 10","skiptoken 010")

	def testCaseInlineCount(self):
		"""inlinecountQueryOp = "$inlinecount=" ("allpages" / "none") """
		dsURI=ODataURI("Orders?$inlinecount=allpages",'/x.svc')
		inlineCount=dsURI.sysQueryOptions[SystemQueryOption.inlinecount]
		self.assertTrue(inlineCount==InlineCount.allpages,"allpages constant")
		dsURI=ODataURI("Orders?$inlinecount=allpages&$top=10",'/x.svc')
		inlineCount=dsURI.sysQueryOptions[SystemQueryOption.inlinecount]
		self.assertTrue(inlineCount==InlineCount.allpages,"allpages constant")
		dsURI=ODataURI("Orders?$inlinecount=none&$top=10",'/x.svc')
		inlineCount=dsURI.sysQueryOptions[SystemQueryOption.inlinecount]
		self.assertTrue(inlineCount==InlineCount.none,"none constant")
		dsURI=ODataURI("Orders?$inlinecount=allpages&$filter=ShipCountry%20eq%20'France'",'/x.svc')
		inlineCount=dsURI.sysQueryOptions[SystemQueryOption.inlinecount]
		self.assertTrue(inlineCount==InlineCount.allpages,"allpages constant")
	
	def testCaseSelect(self):
		"""Syntax::
		
		selectQueryOp = "$select=" selectClause
		selectClause = [WSP] selectItem [[WSP] "," selectClause] [WSP]
		selectItem = star / selectedProperty / (selectedNavProperty ["/" selectItem])
		selectedProperty = entityProperty / entityComplexProperty
		selectedNavProperty = entityNavProperty-es / entityNavProperty-et
		star = "*"	"""
		dsURI=ODataURI("Customers?$select=CustomerID,CompanyName,Address",'/x.svc')
		select=dsURI.sysQueryOptions[SystemQueryOption.select]
		self.assertTrue(len(select)==3,"Three paths")
		self.assertTrue(select=={'CompanyName':None,'CustomerID':None,'Address':None})		
		dsURI=ODataURI("Customers?$select=CustomerID,Orders",'/x.svc')
		select=dsURI.sysQueryOptions[SystemQueryOption.select]
		self.assertTrue(select=={'CustomerID':None,'Orders':None})		
		dsURI=ODataURI("Customers?$select=CustomerID,Orders&$expand=Orders/OrderDetails",'/x.svc')
		select=dsURI.sysQueryOptions[SystemQueryOption.select]
		self.assertTrue(select=={'CustomerID':None,'Orders':None})		
		dsURI=ODataURI("Customers?$select=*",'/x.svc')
		select=dsURI.sysQueryOptions[SystemQueryOption.select]
		self.assertTrue(select=={'*':None})		
		dsURI=ODataURI("Customers?$select=CustomerID,Orders/*&$expand=Orders/OrderDetails",'/x.svc')
		select=dsURI.sysQueryOptions[SystemQueryOption.select]
		self.assertTrue(select=={'CustomerID':None,'Orders':{'*':None}})		
		dsURI=ODataURI("/service.svc/Customers?$expand=Orders&$filter=substringof(CompanyName,%20'bikes')&$orderby=CompanyName%20asc&$top=2&$skip=3&$skiptoken='Contoso','AKFNU'&$inlinecount=allpages&$select=CustomerID,CompanyName,Orders&$format=xml")
		select=dsURI.sysQueryOptions[SystemQueryOption.select]
		self.assertTrue(len(select)==3,"Three paths")
		try:
			dsURI=ODataURI("Customers?$select=CustomerID,*/Orders")
			self.fail("* must be last item in a select clause")
		except InvalidSystemQueryOption:
			pass

				
class ClientTests(unittest.TestCase):
	def testCaseConstructor(self):
		c=Client()
		self.assertTrue(len(c.feeds)==0,"Default constructor, no feeds")
		self.assertTrue(len(c.feedTitles)==0,"Default constructor, no feed titles")
		self.assertTrue(isinstance(c,app.Client),"OData client not an APP client")
		self.assertTrue(c.pageSize is None,"Default constructor page size")
		
	def tesxCaseServiceRoot(self):
		c=Client(ODATA_SAMPLE_SERVICEROOT)
		self.assertTrue(len(c.feeds)==3,"Sample feed, number of feeds")
		self.assertTrue(c.feedTitles["Products"]==ODATA_SAMPLE_SERVICEROOT+"Products","Sample feed titles")
		c=Client()
		c.SetService(ODATA_SAMPLE_SERVICEROOT)
		self.assertTrue(len(c.feeds)==3 and c.feedTitles["Suppliers"]==ODATA_SAMPLE_SERVICEROOT+"Suppliers","Addition of sample feed")

	def tesxCaseFeedEntries(self):
		c=Client(ODATA_SAMPLE_SERVICEROOT)
		fURL=c.feedTitles['Products']
		f=c.RetrieveFeed(fURL)
		self.assertTrue(isinstance(f,atom.Feed),"Feed instance")
		self.assertTrue(len(f.Entry)==9,"Number of entries returned")
		c.pageSize=2
		f=c.RetrieveFeed(fURL)
		self.assertTrue(len(f.Entry)==2,"Number of entries returned, restricted pageSize")
		entries=c.RetrieveEntries(fURL)
		count=0
		while True:
			try:
				e=entries.next()
				count=count+1
			except StopIteration:
				break
		self.assertTrue(count==9,"Number of entries returned by generator")

	def tesxCaseOrderBy(self):
		c=Client(ODATA_SAMPLE_SERVICEROOT)
		c.pageSize=1
		fURL=c.feedTitles['Products']
		query={'$orderby':'ID asc'}
		entries=c.RetrieveEntries(fURL,query)
		self.assertTrue(entries.next().Title.GetValue()=="Bread","Order by ID asc")
		query={'$orderby':'ID desc'}
		entries=c.RetrieveEntries(fURL,query)
		self.assertTrue(entries.next().Title.GetValue()=="LCD HDTV","Order by ID desc")
		query={'$orderby':'Rating asc,Price desc'}
		entries=c.RetrieveEntries(fURL,query)
		entries.next() # skip the LCD HDTV again
		self.assertTrue(entries.next().Title.GetValue()=="DVD Player","Order by ID low rating, high price")
		
	def tesxCaseProperties(self):
		c=Client(ODATA_SAMPLE_SERVICEROOT)
		c.pageSize=1
		fURL=c.feedTitles['Products']
		entries=c.RetrieveEntries(fURL)
		e=entries.next()
		self.assertTrue(isinstance(e,Entry),"OData entry type override")
		self.assertTrue(e['Rating']==4,"Rating property")
		self.assertTrue(e['Price']==2.5,"Price property")
		self.assertTrue(isinstance(e['ReleaseDate'],iso.TimePoint),"ReleaseDate type")
		self.assertTrue(e['ReleaseDate'].date.century==19 and e['ReleaseDate'].date.year==92,"ReleaseDate year")		
		self.assertTrue(e['DiscontinuedDate'] is None,"DiscontinuedDate NULL test")		
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
		self.assertTrue(isinstance(eResult,Entry),"OData entry type POST result")
		self.assertTrue(eResult['Rating']==5,"Rating property on POST")
		self.assertTrue(eResult['Price']==0.0,"Price property on POST")
		self.assertTrue(isinstance(eResult['ReleaseDate'],iso.TimePoint),"ReleaseDate type on POST: %s"%repr(eResult['ReleaseDate']))
		self.assertTrue(eResult['ReleaseDate']==now,"ReleaseDate match on POST")		
		self.assertTrue(eResult['DiscontinuedDate'] is None,"DiscontinuedDate NULL test on POST")
		for link in eResult.Link:
			if link.title=="Category":
				eCat=c.RetrieveEntry(link.ResolveURI(link.href))
				self.assertTrue(eCat['Name']=='Electronics')

	def tesxCaseMetadata(self):
		c=Client()
		if VERBOSE:
			c.SetLog(http.HTTP_LOG_INFO,sys.stdout)
		c.SetService(ODATA_SAMPLE_SERVICEROOT)
		# By default this should load the metadata document, if present
		self.assertTrue(isinstance(c.schemas['ODataDemo'],edm.Schema),"Failed to load metadata document")
		fURL=c.feedTitles['Products']
		f=c.RetrieveFeed(fURL)
		for e in f.Entry:
			self.assertTrue(e.entityType is c.schemas['ODataDemo']['Product'],"Entry not associated with EntityType")
		e=c.Entry('ODataDemo.Product')
		self.assertTrue(isinstance(e,Entry),"Entry creation from client")
		self.assertTrue(e.entityType is c.schemas['ODataDemo']['Product'],"New entry not associated with EntityType")
					

class ODataStoreClientTests(unittest.TestCase):

	Categories={
		0:"Food",
		1:"Beverages",
		2:"Electronics"
		}
		
	def testCaseConstructor(self):
		sClient=ODataStoreClient('http://localhost:%i/'%HTTP_PORT)
		self.assertTrue(isinstance(sClient,edm.ERStore),"ODataStore not an ERStore")
		s=sClient['ODataDemo']
		self.assertTrue(isinstance(s,edm.Schema),"ODataStore schema")
	
	def testCaseEntityReader(self):
		sClient=ODataStoreClient('http://localhost:%i/'%HTTP_PORT)
		for c in sClient.EntityReader("Categories"):
			self.assertTrue("ID" in c,"No key field in category")
			self.assertTrue(self.Categories[c["ID"].pyValue]==c["Name"].pyValue,"Category Name")


class ServerTests(unittest.TestCase):
	
	def setUp(self):
		self.sampleServerData=FilePath(FilePath(__file__).abspath().split()[0],'data_odatav2','sample_server')
		
	def tearDown(self):
		pass
	
	def LoadMetadata(self):
		doc=edmx.Document()
		mdPath=self.sampleServerData.join('metadata.xml')
		with mdPath.open('rb') as f:
			doc.Read(f)
		return doc
					
	def testCaseConstructor(self):
		s=Server()
		self.assertTrue(len(s.service.Workspace)==1,"Service not returning a single Workspace child")
		self.assertTrue(s.service.Workspace[0].Title.GetValue()=="Default","Service not returning a single Workspace child")		
		self.assertTrue(len(s.service.Workspace[0].Collection)==0,"Workspace not empty")
		self.assertTrue(isinstance(s.serviceRoot,uri.URI),"Service root not a URI")
		# feed=s.GetFeed('Test')
		# self.assertTrue(feed is None,"Missing feed")
		
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
		self.assertTrue(request.responseCode==200,"No DataServiceVersion:\n\n"+request.wfile.getvalue())
		self.assertTrue('DataServiceVersion' in request.responseHeaders,"Missing DataServiceVersion in response")
		major,minor,ua=ParseDataServiceVersion(request.responseHeaders['DataServiceVersion'])
		self.assertTrue(major==2 and minor==0,"No version should return 2.0")
		request=MockRequest('/')
		request.SetHeader('DataServiceVersion',"1.0; old request")
		request.Send(s)
		self.assertTrue(request.responseCode==200,"Version 1.0 request:\n\n"+request.wfile.getvalue())
		major,minor,ua=ParseDataServiceVersion(request.responseHeaders['DataServiceVersion'])
		self.assertTrue(major==1 and minor==0,"Version 1.0 request should return 1.0 response")				
		request=MockRequest('/')
		request.SetHeader('DataServiceVersion',"2.0; current request")
		request.Send(s)
		self.assertTrue(request.responseCode==200)
		major,minor,ua=ParseDataServiceVersion(request.responseHeaders['DataServiceVersion'])
		self.assertTrue(major==2 and minor==0,"Version 2.0 request should return 2.0 response")				
		# Should be OK
		request=MockRequest('/')
		request.SetHeader('DataServiceVersion',"2.1; future request")
		request.Send(s)
		self.assertTrue(request.responseCode==400,"Version mismatch error response: %i"%request.responseCode)
		doc=Document()
		doc.Read(src=request.wfile.getvalue())
		error=doc.root
		self.assertTrue(isinstance(error,Error),"Expected an error instance")
		self.assertTrue(error.Code.GetValue()=="DataServiceVersionMismatch","Error code")
		self.assertTrue(error.Message.GetValue()=="Maximum supported protocol version: 2.0","Error message")
		self.assertTrue(error.InnerError is None,"No inner error")				
		request=MockRequest('/')
		request.SetHeader('DataServiceVersion',"2.1; future request")
		request.SetHeader('Accept',"application/json")
		request.Send(s)
		self.assertTrue(request.responseCode==400,"Version mismatch error response")
		self.assertTrue(request.responseHeaders['Content-Type']=="application/json","Expected JSON response")
		doc=json.loads(request.wfile.getvalue())
		self.assertTrue(len(doc)==1,"Expected a single error object")
		self.assertTrue(len(doc['error'])==2,"Expected two children")
		self.assertTrue(doc['error']['code']=="DataServiceVersionMismatch","Error code")
		self.assertTrue(doc['error']['message']=="Maximum supported protocol version: 2.0","Error message")
		self.assertFalse('innererror' in doc['error'],"No inner error")				
		request=MockRequest('/')
		request.SetHeader('DataServiceVersion',"1.0; old request")
		request.SetHeader('MaxDataServiceVersion',"1.0; old max")
		request.Send(s)
		self.assertTrue(request.responseCode==200)
		major,minor,ua=ParseDataServiceVersion(request.responseHeaders['DataServiceVersion'])
		self.assertTrue(major==1 and minor==0,"MaxVersion 1.0 request should return 1.0 response: %i.%i"%(major,minor))				
		request=MockRequest('/')
		request.SetHeader('DataServiceVersion',"1.0; old request")
		request.SetHeader('MaxDataServiceVersion',"2.0; current max")
		request.Send(s)
		self.assertTrue(request.responseCode==200)
		major,minor,ua=ParseDataServiceVersion(request.responseHeaders['DataServiceVersion'])
		self.assertTrue(major==2 and minor==0,"MaxVersion 2.0 request should return 2.0 response")				
		request=MockRequest('/')
		request.SetHeader('DataServiceVersion',"1.0; old request")
		request.SetHeader('MaxDataServiceVersion',"2.1; future max")
		request.Send(s)
		self.assertTrue(request.responseCode==200)
		major,minor,ua=ParseDataServiceVersion(request.responseHeaders['DataServiceVersion'])
		self.assertTrue(major==2 and minor==0,"MaxVersion 2.1 request should return 2.0 response")				

	def testCaseServiceRoot(self):
		"""The resource identified by [the service root] ... MUST be an AtomPub Service Document"""
		s=Server()
		request=MockRequest('/')
		request.Send(s)
		self.assertTrue(request.responseCode==200)		
		doc=app.Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,app.Service),"Service root not an app.Service")
		# An empty server has no workspaces
		self.assertTrue(len(doc.root.Workspace)==1,"Empty server = 1 workspace")
		self.assertTrue(len(doc.root.Workspace[0].Collection)==0,"Empty Server = no collections")
		self.assertTrue(doc.root.GetBase()==str(s.serviceRoot),"Non-matching service root: base=%s, root=%s"%(repr(doc.root.GetBase()),repr(str(s.serviceRoot))))
		
	def testCaseModel(self):
		"""With a simple OData server we set the model manually"""
		s=Server()
		self.assertTrue(s.model is None,"no model initially")
		# Load the model document
		# import pdb;pdb.set_trace()
		doc=self.LoadMetadata()
		s.SetModel(doc)
		# at this point, the server's model root is available as model
		self.assertTrue(s.model is doc.root,"model attribute")
	
	def testCaseEntityTypeAsAtomEntry(self):
		doc=self.LoadMetadata()
		ds=doc.root.DataServices
		customers=ds['SampleModel.SampleEntities.Customers']
		customer=Entity(customers)
		customer['CustomerID'].SetFromPyValue('X')
		customer['CompanyName'].SetFromPyValue('Megacorp')		
		#	If the entity represents an AtomPub Entry Resource...
		#		the <atom:content> element MUST contain a "type" attribute with the value "application/xml"
		entry=Entry(None,customer)
		self.assertTrue(entry.Content.type=="application/xml")
		#		The <atom:content> element MUST also contain one <m:properties> child element
		children=list(entry.Content.GetChildren())
		self.assertTrue(len(children)==1,"one child element")
		self.assertTrue(isinstance(children[0],Properties),"child is properties element")
		children=list(entry.FindChildrenDepthFirst(atom.Link))
		links={}
		navigation=list(customer.Navigation())
		for child in children:
			#	Each <atom:link> element MUST contain an atom:rel attribute
			#	with the value defined by the relNavigationlLinkURI rule
			if child.rel.startswith(ODATA_RELATED):
				pName=child.rel[len(ODATA_RELATED):]
				#	...servers MUST represent each NavigationProperty of the
				#	EntityType as an <atom:link> element that is a child
				#	element of the <atom:entry> element.
				self.assertTrue(child.parent is entry,"Link must be a child of the entry element")
				#	The element SHOULD also contain an atom:title attribute
				#	with the value equal to the NavigationProperty name
				self.assertTrue(pName in navigation,"Link must be a navigation property")
				self.assertTrue(child.title==pName,"Title should be name of navigation property")
				#	and MUST contain an atom:href attribute with value equal to
				#	the URI which identifies the NavigationProperty on the
				#	EntityType.
				links[pName]=(child.href,child.type)
		self.assertTrue(links['Orders'][0]=="SampleEntities.Customers('X')/Orders","Orders link")
		#	[the atom:type attribute] should have a value of ...
		#	"application/atom+xml;type=feed" when the property
		#	identifies an EntitySet.
		self.assertTrue(links['Orders'][1]=="application/atom+xml;type=feed","Orders link type")
		#
		#	End of customer tests
		#
		orders=ds['SampleModel.SampleEntities.Orders']
		order=Entity(orders)
		order['OrderID'].SetFromPyValue(1)
		entry=Entry(None,order)
		children=list(entry.FindChildrenDepthFirst(atom.Link))
		links={}
		navigation=list(order.Navigation())
		for child in children:
			if child.rel.startswith(ODATA_RELATED):
				pName=child.rel[len(ODATA_RELATED):]
				links[pName]=(child.href,child.type)
		self.assertTrue(links['Customer'][0]=="SampleEntities.Orders(1)/Customer","Customer link")
		#	[the atom:type attribute] should have a value of
		#	"application/atom+xml;type=entry" when the
		#	NavigationProperty identifies a single entity instance
		self.assertTrue(links['Customer'][1]=="application/atom+xml;type=entry","Customer link type")
		self.assertTrue(links['OrderLine'][0]=="SampleEntities.Orders(1)/OrderLine","OrderLine link")
		self.assertTrue(links['OrderLine'][1]=="application/atom+xml;type=entry","OrderLine link type")
		#
		#	End of order tests
		#
		employees=ds['SampleModel.SampleEntities.Employees']
		employee=Entity(employees)
		employee['EmployeeID'].SetFromPyValue('12345')
		employee['EmployeeName'].SetFromPyValue('Joe Bloggs')
		employee['Address']['City'].SetFromPyValue('Chunton')
		entry=Entry(None,employee)
		properties=list(entry.Content.GetChildren())[0]
		pList=list(properties.GetChildren())
		#		Each child element representing a property MUST be
		#		defined in the data service namespace... and the
		#		element name must be the same as the property it
		#		represents.
		for p in pList:
			self.assertTrue(p.ns==ODATA_DATASERVICES_NAMESPACE,"Property not in data services namespace")
		pNames=map(lambda x:x.xmlname,pList)
		pNames.sort()
		self.assertTrue(pNames==["Address","EmployeeID","Version"],"Property names")
		#		The <m:properties> element MUST contain one child
		#		element for each EDMSimpleType and ComplexType property
		#		of the EntityType instance represented by the
		#		<atom:entry> element that is not otherwise mapped
		#		through a Customizable Feed property mapping
		self.assertTrue(len(pList)==3,"3/4 properties due to keep in content = False")
		#	If the Entity Type instance represented includes
		#	Customizable Feeds annotations in the data services
		#	metadata document, then the properties with custom mappings
		#	must be represented as directed by the mappings information
		gotLocation=False
		for child in entry.GetChildren():
			if child.GetXMLName()==("http://www.example.com","Location"):
				self.assertTrue(child.GetValue()=="Chunton","City not mapped to location")
				gotLocation=True
		self.assertTrue(gotLocation,"Missing custom feed mapping")
		#		If the Entity Type instance being represented was
		#		identified with a URI that includes a Select System
		#		Query Option (section 2.2.3.6.1.11), then the prior
		#		rule is relaxed such that only the properties
		#		identified by the $select query option SHOULD be
		#		represented as child elements of the <m:properties>
		#		element.
		employee.Expand({},{'Address':None})
		entry=Entry(None,employee)
		properties=list(list(entry.Content.GetChildren())[0].GetChildren())
		self.assertTrue(len(properties)==1,"A single property selected")
		employee['EmployeeName'].SetFromPyValue(None)
		entry=Entry(None,employee)
		#	If the property of an Entity Type instance ...includes
		#	Customizable Feed annotations ... and has a value of null,
		#	then the element ... can be present and MUST be empty.
		self.assertTrue(entry.Title.GetValue()=="","Empty title element")
		#
		#	End of employee tests
		#
		documents=ds['SampleModel.SampleEntities.Documents']
		document=Entity(documents)
		document['DocumentID'].SetFromPyValue(1801)
		document['Title'].SetFromPyValue('War and Peace')
		document['Author'].SetFromPyValue('Tolstoy')
		h=hashlib.sha256()
		h.update("Well, Prince, so Genoa and Lucca are now just family estates of the Buonapartes")
		document['Version'].SetFromPyValue(h.digest())
		entry=Entry(None,document)
		#	If the entity represents an AtomPub Media Link Entry...
		#		the <m:properties> element... the <m:properties>
		#		element MUST be a direct child of the <atom:entry>
		#		element
		children=list(entry.FindChildrenDepthFirst(Properties))
		self.assertTrue(len(children)==1,"one properties element")
		self.assertTrue(children[0].parent is entry,"properties is a direct child of *the* entry")
		children=list(entry.FindChildrenDepthFirst(atom.Link))
		links=set()
		for child in children:
			links.add(child.rel)
			if child.rel=="edit-media":
				self.assertTrue(child.href=="SampleEntities.Documents(1801)/$value","edit-media link")
				self.assertTrue(child.GetAttribute((ODATA_METADATA_NAMESPACE,"etag"))=="W/\"X'%s'\""%h.hexdigest().upper())
			if child.rel=="edit":
				#	[the edit link] MUST have an atom:href attribute
				#	whose value is a URI that identifies the entity
				self.assertTrue(child.href=="SampleEntities.Documents(1801)","edit link")
		#		[for AtomPub Media Link Entries] an <atom:link> element
		#		SHOULD be included, which contains an
		#		atom:rel="edit-media" attribute
		self.assertTrue("edit-media" in links,"Missing edit-media link")
		#	An <atom:link> element SHOULD be included, which contains
		#	an atom:rel="edit" or atom:rel="self" attribute
		self.assertTrue("edit" in links or "self" in links,"Missing edit/self link")
		#	An <atom:category> element containing an atom:term
		#	attribute and an atom:scheme attribute MUST be included if
		#	the EntityType of the EntityType instance represented by
		#	the <atom:entry> object is part of an inheritance hierarchy
		gotType=False
		for cat in entry.Category:
			# The value of the atom:scheme attribute MUST be a data
			# service specific IRI [or] it SHOULD use the URI shown in
			# grammar rule dataServiceSchemeURI
			if cat.scheme==ODATA_SCHEME:
				# The value of the atom:term attribute MUST be the
				# namespace qualified name of the EntityType of the
				# instance
				self.assertTrue(cat.term=="SampleModel.Document","Expected category term to be SampleModel.Document")
				gotType=True
		#	If the EntityType is not part of an inheritance hierarchy,
		#	then the <atom:category> element can be included
		self.assertTrue(gotType,"Expected category term")
		
	def testCaseEntityTypeFromAtomEntry(self):
		doc=self.LoadMetadata()
		ds=doc.root.DataServices
		customers=ds['SampleModel.SampleEntities.Customers']
		customer=Entity(customers)
		customer['CustomerID'].SetFromPyValue('X')
		customer['CompanyName'].SetFromPyValue('Megacorp')		
		entry=Entry(None,customer)
		self.assertTrue(entry.entityType==None,"Ensure there is no relation to the model here")
		newCustomer=entry.GetValue(Entity(customers))
		self.assertTrue(newCustomer['CustomerID'].pyValue=="X","Check customer ID")
		self.assertTrue(newCustomer['CompanyName'].pyValue=="Megacorp","Check customer name")
		self.assertFalse(newCustomer['Address']['Street'],"No street")
		self.assertFalse(newCustomer['Address']['City'],"No city")
		self.assertFalse(newCustomer['Version'],"No version")
		employees=ds['SampleModel.SampleEntities.Employees']
		employee=Entity(employees)
		employee['EmployeeID'].SetFromPyValue('12345')
		employee['EmployeeName'].SetFromPyValue('Joe Bloggs')
		employee['Address']['City'].SetFromPyValue('Chunton')
		entry=Entry(None,employee)
		self.assertTrue(entry.entityType==None,"Ensure there is no relation to the model here")
		newEmployee=entry.GetValue(Entity(employees))
		self.assertTrue(newEmployee['EmployeeID'].pyValue=="12345","Check employee ID")
		self.assertTrue(newEmployee['EmployeeName'].pyValue=="Joe Bloggs","Check employee name")
		self.assertFalse(newEmployee['Address']['Street'],"No street")
		self.assertTrue(newEmployee['Address']['City']=="Chunton","Check employee city")
		self.assertFalse(newEmployee['Version'],"No version")
		documents=ds['SampleModel.SampleEntities.Documents']
		document=Entity(documents)
		document['DocumentID'].SetFromPyValue(1801)
		document['Title'].SetFromPyValue('War and Peace')
		document['Author'].SetFromPyValue('Tolstoy')
		h=hashlib.sha256()
		h.update("Well, Prince, so Genoa and Lucca are now just family estates of the Buonapartes")
		document['Version'].SetFromPyValue(h.digest())
		entry=Entry(None,document)
		self.assertTrue(entry.entityType==None,"Ensure there is no relation to the model here")
		newDocument=entry.GetValue(Entity(documents))
		self.assertTrue(newDocument['DocumentID'].pyValue==1801,"Check document ID")
		self.assertTrue(newDocument['Title'].pyValue=="War and Peace","Check document name")
		self.assertTrue(newDocument['Author']=="Tolstoy","Check author name")
		self.assertTrue(newDocument['Version'].pyValue==h.digest(),"Mismatched version")

	def testCaseEntityTypeAsJSON(self):
		doc=self.LoadMetadata()
		ds=doc.root.DataServices
		customers=ds['SampleModel.SampleEntities.Customers']
		customer=Entity(customers)
		customer['CustomerID'].SetFromPyValue('X')
		customer['CompanyName'].SetFromPyValue('Megacorp')
		customer['Address']['City'].SetFromPyValue('Chunton')
		jsonData=string.join(customer.GenerateEntityTypeInJSON())
		obj=json.loads(jsonData)
		#	Each property on the EntityType MUST be represented as a name/value pair
		nProps=0
		for k in obj:
			if k.startswith("__"):
				continue
			nProps=nProps+1
		#	The default representation of a NavigationProperty is as a
		#	JSON name/value pair. The name is equal to "__deferred" and
		#	the value is a JSON object that contains a single
		#	name/value pair with the name equal to "uri"
		self.assertTrue("Orders" in obj)
		self.assertTrue("__deferred" in obj["Orders"])
		self.assertTrue(obj["Orders"]["__deferred"]["uri"]=="SampleEntities.Customers('X')/Orders")
		#	Each declared property defined on the ComplexType MUST be
		#	represented as a name/value pair within the JSON object.
		self.assertTrue("City" in obj["Address"],"City in Address")
		self.assertTrue("Street" in obj["Address"],"Street in Address")
		#	Additional name/value pairs that do not represent a
		#	declared property of the ComplexType SHOULD NOT be
		#	included.		
		self.assertTrue(len(obj["Address"])==2,"Only two properties in Address")
		#	Name/value pairs not representing a property defined on the
		#	EntityType SHOULD NOT be included
		self.assertTrue(nProps==5,"5 properties in Customer 4+1 navigation")
		#	an EntityType instance MAY include a name/value pair named
		#	"__metadata"
		self.assertTrue("__metadata" in obj,"Expected __metadata")
		#	The value of the "uri" name/value pair MUST be the
		#	canonical URI identifying the EntityType instance
		meta=obj["__metadata"]
		self.assertTrue(meta["uri"]=="SampleEntities.Customers('X')","uri in metadata")
		#	The value of the "type" name/value pair MUST be the
		#	namespace qualified name... of the EntityType of the
		#	instance
		self.assertTrue(meta["type"]=="SampleModel.Customer","type in metadata")
		self.assertFalse("etag" in meta,"etag null case")
		#	If the entity being represented is not a Media Link Entry,
		#	then the "edit_media", "media_src", "media_etag", and
		#	"content_type" name/value pairs MUST NOT be included
		self.assertFalse("media_src" in meta)
		self.assertFalse("content_type" in meta)
		self.assertFalse("edit_media" in meta)
		self.assertFalse("media_etag" in meta)		
		customer.Expand({},{'CustomerID':None,'CompanyName':None})
		#	[if using the] Select System Query Option then only the
		#	properties identified by the $select query option MUST be
		#	represented by name/value pairs
		jsonData=string.join(customer.GenerateEntityTypeInJSON())
		obj=json.loads(jsonData)
		nProps=0
		for k in obj:
			if k.startswith("__"):
				continue
			nProps=nProps+1
		self.assertTrue(nProps==2,"Two properties selected in Customer: %i"%nProps)
		documentSet=ds['SampleModel.SampleEntities.Documents']
		documents=pyds.InMemoryEntityStore(documentSet)
		docText="Well, Prince, so Genoa and Lucca are now just family estates of the Buonapartes"
		h=hashlib.sha256()
		h.update(docText)
		etag="W/\"X'%s'\""%h.hexdigest().upper()
		documents.data[1801]=(1801,'War and Peace','Tolstoy',h.digest())
		document=documentSet.GetCollection()[1801]
		document.SetItemStream('text/plain',docText)
		jsonData=string.join(document.GenerateEntityTypeInJSON())
		obj=json.loads(jsonData)
		meta=obj["__metadata"]
		self.assertTrue(meta["etag"]==etag,"document etag: %s"%meta["etag"])
		#	The "media_src" and "content_type" name/value pairs MUST be
		#	included and the "edit_media" and "media_etag" name/value
		#	pairs can be included if the entity being represented is a
		#	Media Link Entry
		self.assertTrue(meta["media_src"]=="SampleEntities.Documents(1801)/$value","media src link")
		self.assertTrue(meta["content_type"]=="text/plain","document content type")
		self.assertTrue(meta["edit_media"]=="SampleEntities.Documents(1801)/$value","edit-media link")
		self.assertTrue(meta["media_etag"]==etag,"document etag")
		
	def testCaseEntityTypeFromJSON(self):
		doc=self.LoadMetadata()
		ds=doc.root.DataServices
		customers=ds['SampleModel.SampleEntities.Customers']
		customer=Entity(customers)
		customer['CustomerID'].SetFromPyValue('X')
		customer['CompanyName'].SetFromPyValue('Megacorp')
		jsonData=string.join(customer.GenerateEntityTypeInJSON())
		obj=json.loads(jsonData)
		newCustomer=Entity(customers)
		newCustomer.SetFromJSONObject(obj)
		self.assertTrue(newCustomer['CustomerID'].pyValue=="X","Check customer ID")
		self.assertTrue(newCustomer['CompanyName'].pyValue=="Megacorp","Check customer name")
		self.assertFalse(newCustomer['Address']['Street'],"No street")
		self.assertFalse(newCustomer['Address']['City'],"No city")
		self.assertFalse(newCustomer['Version'],"No version")
		employees=ds['SampleModel.SampleEntities.Employees']
		employee=Entity(employees)
		employee['EmployeeID'].SetFromPyValue('12345')
		employee['EmployeeName'].SetFromPyValue('Joe Bloggs')
		employee['Address']['City'].SetFromPyValue('Chunton')
		jsonData=string.join(employee.GenerateEntityTypeInJSON())
		obj=json.loads(jsonData)
		newEmployee=Entity(employees)
		newEmployee.SetFromJSONObject(obj)
		self.assertTrue(newEmployee['EmployeeID'].pyValue=="12345","Check employee ID")
		self.assertTrue(newEmployee['EmployeeName'].pyValue=="Joe Bloggs","Check employee name")
		self.assertFalse(newEmployee['Address']['Street'],"No street")
		self.assertTrue(newEmployee['Address']['City']=="Chunton","Check employee city")
		self.assertFalse(newEmployee['Version'],"No version")
		documentSet=ds['SampleModel.SampleEntities.Documents']
		documents=pyds.InMemoryEntityStore(documentSet)
		docText="Well, Prince, so Genoa and Lucca are now just family estates of the Buonapartes"
		h=hashlib.sha256()
		h.update(docText)
		documents.data[1801]=(1801,'War and Peace','Tolstoy',h.digest())
		document=documentSet.GetCollection()[1801]
		document.SetItemStream('text/plain',docText)
		jsonData=string.join(document.GenerateEntityTypeInJSON())
		obj=json.loads(jsonData)
		newDocument=Entity(documentSet)
		newDocument.SetFromJSONObject(obj)
		self.assertTrue(newDocument['DocumentID'].pyValue==1801,"Check document ID")
		self.assertTrue(newDocument['Title'].pyValue=="War and Peace","Check document name")
		self.assertTrue(newDocument['Author']=="Tolstoy","Check author name")
		self.assertTrue(newDocument['Version'].pyValue==h.digest(),"Mismatched version")

	def testCaseEntitySetAsAtomFeed(self):
		doc=self.LoadMetadata()
		ds=doc.root.DataServices
		customersSet=ds['SampleModel.SampleEntities.Customers']
		customers=pyds.InMemoryEntityStore(customersSet)
		orders=pyds.InMemoryEntityStore(ds['SampleModel.SampleEntities.Orders'])
		association=pyds.InMemoryAssociationIndex(orders,customers,"Customer","Orders")
		customers.data['ALFKI']=('ALFKI','Example Inc',("Mill Road","Chunton"),None)
		for i in xrange(3):
			customers.data['XXX%02X'%i]=('XXX%02X'%i,'Example-%i Ltd'%i,(None,None),None)
		feed=Feed(None,customersSet.GetCollection())
		#	The <atom:id> element MUST contain the URI that identifies the EntitySet
		self.assertTrue(feed.AtomId.GetValue()=="SampleEntities.Customers")
		#	The <atom:title> element can contain the name of the
		#	EntitySet represented by the parent <atom:feed> element...
		#	The set name can be qualified with the name of the EDM
		#	namespace in which it is defined
		self.assertTrue(feed.Title.GetValue()=="SampleModel.SampleEntities.Customers")
		children=list(feed.FindChildrenDepthFirst(atom.Link,maxDepth=1))
		links=set()
		for child in children:
			links.add(child.rel)
			if child.rel=="self":
				#	An <atom:link> element with a rel="self" attribute MUST
				#	contain an href attribute with a value equal to the URI
				#	used to identify the set that the parent <atom:feed>
				#	element represents
				self.assertTrue(child.href=="SampleEntities.Customers","self link")
		self.assertTrue("self" in links,"Missing self link")
		self.assertTrue(len(feed.Entry)==0,"Feed uses generator instead of static array of entries")
		nEntries=0
		for child in feed.GetChildren():
			if isinstance(child,atom.Entry):
				nEntries+=1
		self.assertTrue(nEntries==4,"4 entries generated by the feed")		
		page=customersSet.GetCollection()
		page.TopMax(2)
		page.SetInlineCount(True)
		feed=Feed(None,page)
		nEntries=0
		#	[with inlineCount the response] MUST include the count of
		#	the number of entities in the collection of entities
		count=None
		for child in feed.GetChildren():
			if isinstance(child,Count):
				#	The count value included in the result MUST be
				#	enclosed in an <m:count> element
				#	The <m:count> element MUST be a direct child
				#	element of the <feed> element
				count=child.GetValue()
				self.assertTrue(count==4,"4 total size of collection")
			if isinstance(child,atom.Entry):
				# ...and MUST occur before any <atom:entry> elements in
				# the feed
				self.assertFalse(count is None,"count after Entry")
				nEntries+=1
		self.assertTrue(nEntries==2,"2 entries for partial feed")		
		children=list(feed.FindChildrenDepthFirst(atom.Link))
		links=set()
		#	if the server does not include an <atom:entry> element as a
		#	child element of the <atom:feed> element for every entity
		#	in the collection ... The href attribute of the <atom:link
		#	rel="next"> element ... MUST have a value equal to the URI
		#	that identifies the next partial set of entities
		for child in children:
			links.add(child.rel)
			if child.rel=="next":
				# Such a URI SHOULD include a Skip Token System Query Option
				self.assertTrue("$skiptoken" in child.href,"skiptoken")
		self.assertTrue("next" in links,"Missing next link")
		customer=customersSet.GetCollection()['ALFKI']
		feed=Feed(None,customer.Navigate('Orders'))
		#	If the URI in the sibling <atom:id> element is of the same
		#	form as URI 6 and the NavigationProperty identifies an
		#	EntitySet, then the <atom:title> element can contain the
		#	name of the NavigationProperty instead of the name of the
		#	EntitySet identified by the property
		self.assertTrue(feed.AtomId.GetValue()=="SampleEntities.Customers('ALFKI')/Orders")
		self.assertTrue(feed.Title.GetValue()=="Orders")

	def testCaseEntitySetAsJSON(self):
		doc=self.LoadMetadata()
		ds=doc.root.DataServices
		customersSet=ds['SampleModel.SampleEntities.Customers']
		customers=pyds.InMemoryEntityStore(customersSet)
		orders=pyds.InMemoryEntityStore(ds['SampleModel.SampleEntities.Orders'])
		association=pyds.InMemoryAssociationIndex(orders,customers,"Customer","Orders")
		customers.data['ALFKI']=('ALFKI','Example Inc',("Mill Road","Chunton"),None)
		for i in xrange(3):
			customers.data['XXX%02X'%i]=('XXX%02X'%i,'Example-%i Ltd'%i,(None,None),None)
		collection=customersSet.GetCollection()
		jsonData=string.join(collection.GenerateEntitySetInJSON(),'')
		#	Version 2 object by default
		obj=json.loads(jsonData)
		self.assertTrue(type(obj)==DictType,"Version 2 type is dictionary")
		self.assertTrue("results" in obj,"results present")
		#	An EntitySet or collection of entities MUST be represented
		#	as an array of JSON objects, with one object for each
		#	EntityType instance within the set
		self.assertTrue(type(obj["results"])==ListType,"EntitySet represented as JSON array")
		self.assertTrue(len(obj["results"])==4,"Four entities")
		#	Version 1.0 JSON representation
		v1JSONData=string.join(collection.GenerateEntitySetInJSON(1),'')
		obj=json.loads(v1JSONData)
		self.assertTrue(type(obj)==ListType,"Version 1 type is an array")
		self.assertTrue(len(obj)==4,"Four entities")
		collection.TopMax(2)
		collection.SetInlineCount(True)
		#	if the server does not include an entityTypeInJson ... for
		#	every entity in the collection ... a nextLinkNVP name value
		#	pair MUST be included
		jsonData=string.join(collection.GenerateEntitySetInJSON(),'')
		obj=json.loads(jsonData)
		self.assertTrue("__next" in obj,"next link included")
		#	The URI in the associated nextURINVP name value pair MUST
		#	have a value equal to the URI, which identifies the next
		#	partial set of entities from the originally identified
		#	complete set.
		self.assertTrue(type(obj["__next"])==DictType,"next link is json object")
		#	Such a URI SHOULD include a Skip Token System Query Option
		self.assertTrue("$skiptoken" in obj["__next"]["uri"],"next link contains a skiptoken")		
		#	If [the URI contains an $inlinecount System Query
		#	Option]		 the response MUST include the countNVP
		#	name/value pair (before the results name/value pair) with
		#	the value  equal to the count of the total number of
		#	entities.
		self.assertTrue("__count" in obj,"count included")
		self.assertTrue(obj["__count"]==4,"Four entities in total")
		self.assertTrue(jsonData.index("__count")<jsonData.index("results"),"first __count before results")
		#	An empty EntitySet or collection of entities MUST be
		#	represented as an empty JSON array.
		emptyCollection=collection['ALFKI'].Navigate("Orders")
		jsonData=string.join(emptyCollection.GenerateEntitySetInJSON(),'')
		obj=json.loads(jsonData)
		self.assertTrue(type(obj["results"])==ListType,"Empty EntitySet represented as JSON array")
		self.assertTrue(len(obj["results"])==0,"No entities")
		

class CustomersByCityEntityCollection(FunctionEntityCollection):
	
	def __init__(self,function,params,customers):
		FunctionEntityCollection.__init__(self,function,params)
		self.customers=customers
		self.collection=self.entitySet.GetCollection()
		self.city=params.get('city','Chunton')
		
	def itervalues(self):
		for customer in self.customers.data.itervalues():
			if customer[2][1]==self.city:
				yield self.collection[customer[0]]


class ShippedAddressByDateCollection(FunctionCollection):
	
	def __init__(self,function,params,customersEntitySet):
		edm.FunctionCollection.__init__(self,function,params)
		self.date=params.get('date',None)
		if self.date is None:
			self.date=iso8601.TimePoint()
			self.date.Now()
		self.collection=customersEntitySet.GetCollection()
		
	def __iter__(self):
		for customer in self.collection.itervalues():
			yield customer['Address']


class ShippedCustomerNamesByDateCollection(FunctionCollection):
	
	def __init__(self,function,params,customersEntitySet):
		edm.FunctionCollection.__init__(self,function,params)
		self.date=params.get('date',None)
		if self.date is None:
			self.date=iso8601.TimePoint()
			self.date.Now()
		self.collection=customersEntitySet.GetCollection()
		
	def __iter__(self):
		for customer in self.collection.itervalues():
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
		doc=edmx.Document()
		mdPath=self.sampleServerData.join('metadata.xml')
		with mdPath.open('rb') as f:
			doc.Read(f)
		self.ds=doc.root.DataServices
		self.svc.SetModel(doc)
		customers=pyds.InMemoryEntityStore(self.ds['SampleModel.SampleEntities.Customers'])
		customers.data['ALFKI']=('ALFKI','Example Inc',("Mill Road","Chunton"),None)
		for i in xrange(90):
			customers.data['XXX%02X'%i]=('XXX%02X'%i,'Example-%i Ltd'%i,(None,None),None)
		employees=pyds.InMemoryEntityStore(self.ds['SampleModel.SampleEntities.Employees'])
		employees.data['1']=('1','Joe Bloggs',("The Elms","Chunton"),'DEADBEEF')
		orders=pyds.InMemoryEntityStore(self.ds['SampleModel.SampleEntities.Orders'])
		now=iso8601.TimePoint('2013-08-01T11:05:00')
		now.Now()
		orders.data[1]=(1,iso8601.TimePoint('2013-08-01T11:05:00'))
		orders.data[2]=(2,iso8601.TimePoint('2013-08-13T10:26:00'))
		orders.data[3]=(3,iso8601.TimePoint('2012-05-29T18:13:00'))
		orders.data[4]=(4,iso8601.TimePoint('2012-05-29T18:13:00'))
		association=pyds.InMemoryAssociationIndex(orders,customers,"Customer","Orders")
		association.AddLink(1,'ALFKI')
		association.AddLink(2,'ALFKI')
		orderLines=pyds.InMemoryEntityStore(self.ds['SampleModel.SampleEntities.OrderLines'])
		orderLines.data[100]=(100,12,0.45)
		orderLines.data[200]=(200,144,2.50)
		association=pyds.InMemoryAssociationIndex(orders,orderLines,"OrderLine","Orders")
		association.AddLink(1,100)
		association.AddLink(2,200)
		documents=pyds.InMemoryEntityStore(self.ds['SampleModel.SampleEntities.Documents'])
		documents.data[300]=(300,'The Book','The Author')
		documents.data[301]=(301,'A Book','An Author')
		bitsAndPieces=pyds.InMemoryEntityStore(self.ds['SampleModel.ExtraEntities.BitsAndPieces'])
		bitsAndPieces.data[1]=(1,'blahblah')
		customersByCity=self.ds['SampleModel.SampleEntities.CustomersByCity']
		customersByCity.Bind(CustomersByCityEntityCollection,customers=customers)
		lastCustomerByLine=self.ds['SampleModel.SampleEntities.LastCustomerByLine']
		lastCustomerByLine.Bind(self.LastCustomerByLine)
		shippedAddressByDate=self.ds['SampleModel.SampleEntities.ShippedAddressByDate']
		shippedAddressByDate.Bind(ShippedAddressByDateCollection,customersEntitySet=self.ds['SampleModel.SampleEntities.Customers'])
		lastShippedByLine=self.ds['SampleModel.SampleEntities.LastShippedByLine']
		lastShippedByLine.Bind(self.LastShippedByLine)
		shippedCustomerNamesByDate=self.ds['SampleModel.SampleEntities.ShippedCustomerNamesByDate']
		shippedCustomerNamesByDate.Bind(ShippedCustomerNamesByDateCollection,customersEntitySet=self.ds['SampleModel.SampleEntities.Customers'])
		lastCustomerNameByLine=self.ds['SampleModel.SampleEntities.LastCustomerNameByLine']
		lastCustomerNameByLine.Bind(self.LastCustomerNameByLine)
		
	def LastCustomerByLine(self,function,params):
		customers=self.ds['SampleModel.SampleEntities.Customers'].GetCollection()
		return customers['ALFKI']
				
	def LastShippedByLine(self,function,params):
		customers=self.ds['SampleModel.SampleEntities.Customers'].GetCollection()
		return customers['ALFKI']['Address']
				
	def LastCustomerNameByLine(self,function,params):
		customers=self.ds['SampleModel.SampleEntities.Customers'].GetCollection()
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
		order=orders.GetCollection()[1]
		# Simple Property
		p=Parser("OrderID")
		e=p.ParseCommonExpression()
		value=e.Evaluate(order)
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue==1,"Expected 1")		
		customers=self.ds['SampleModel.SampleEntities.Customers']
		# customers.data['ALFKI']=('ALFKI','Example Inc',("Mill Road","Chunton"),None)
		customer=customers.GetCollection()['ALFKI']
		# Complex Property
		p=Parser("Address")
		e=p.ParseCommonExpression()
		value=e.Evaluate(customer)
		self.assertTrue(isinstance(value,edm.Complex),"Expected Complex value")
		self.assertTrue(value['City'].pyValue=='Chunton',"Expected Chunton")		
		# Simple Property (NULL)
		p=Parser("Version")
		e=p.ParseCommonExpression()
		value=e.Evaluate(customer)
		self.assertTrue(value.typeCode==edm.SimpleType.Binary,"Expected Binary")
		self.assertTrue(value.pyValue is None,"Expected NULL")		
		# Navigation property
		p=Parser("Customer")
		e=p.ParseCommonExpression()
		value=e.Evaluate(order)
		self.assertTrue(isinstance(value,edm.Entity),"Expected Entity")
		self.assertTrue(value['CustomerID'].pyValue=='ALFKI',"Expected Customer('ALFKI')")
		# Navigation property with Null
		value=e.Evaluate(orders.GetCollection()[3])
		self.assertTrue(isinstance(value,edm.SimpleValue),"Expected SimpleValue (for NULL)")
		self.assertFalse(value,"Expected NULL")		
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
		order=orders.GetCollection()[1]
		# Known Entity: SimpleProperty
		p=Parser("Customer/CustomerID")
		e=p.ParseCommonExpression()
		value=e.Evaluate(order)
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected string")
		self.assertTrue(value.pyValue=='ALFKI',"Expected 'ALKFI'")		
		# Known ComplexType: SimpleProperty
		p=Parser("Customer/Address/City")
		e=p.ParseCommonExpression()
		value=e.Evaluate(order)
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected string")
		self.assertTrue(value.pyValue=='Chunton',"Expected 'Chunton'")		
		# TODO: a two step navigation, sample data doesn't have one yet
		# 	navigation / navigation 
		# Simple Property (NULL)
		p=Parser("Customer/Version")
		e=p.ParseCommonExpression()
		value=e.Evaluate(order)
		self.assertTrue(value.typeCode==edm.SimpleType.Binary,"Expected Binary")
		self.assertTrue(value.pyValue is None,"Expected NULL")		
		# Navigation property with multiple cardinality
		p=Parser("Customer/Orders")
		e=p.ParseCommonExpression()
		try:
			value=e.Evaluate(order)
			self.fail("Navigation property cardinality")
		except EvaluationError:
			pass

	def testCaseEvaluateEqExpression(self):
		"""Equality of EntityType instances is harder to test than you think,
		the only way to get an expression to evaluate to an entity instance
		is through a navigation property."""
		orders=self.ds['SampleModel.SampleEntities.Orders']
		order=orders.GetCollection()[1]
		# Known Entity: SimpleProperty
		p=Parser("Customer eq Customer")
		e=p.ParseCommonExpression()
		value=e.Evaluate(order)
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected boolean")
		self.assertTrue(value.pyValue==True,"Expected True")		
		p=Parser("Customer eq OrderLine")
		e=p.ParseCommonExpression()
		value=e.Evaluate(order)
		self.assertTrue(value.pyValue==False,"Expected False")		
			
	def testCaseServiceRoot(self):
		"""The resource identified by [the service root] ... MUST be an AtomPub Service Document.
		
		The ServiceRoot of a data service MUST identify the Service
		Document for the data service.
		
		AtomPub Service Documents MUST be identified with the
		"application/atomsvc+xml" media type.
		
		JSON Service Documents MUST be identified using the
		"application/json" media type."""
		request=MockRequest('/service.svc')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==307)		
		self.assertTrue(request.responseHeaders['Location']=='http://host/service.svc/',"Expected redirect")
		request=MockRequest('/service.svc/')	
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200,"Service root response: %i"%request.responseCode)		
		self.assertTrue(request.responseHeaders['Content-Type']=='application/atomsvc+xml',"Expected application/atomsvc+xml")
		doc=app.Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,app.Service),"Service root not an app.Service")
		self.assertTrue(len(doc.root.Workspace)==1,"Sample server has 1 workspace")
		#	a data service MUST represent each EntitySet ...as an
		#	<app:collection> element
		self.assertTrue(len(doc.root.Workspace[0].Collection)==7,"Sample service has 7 entity sets")
		#	The URI identifying the EntitySet MUST be used as the value
		#	of the "href" attribute of the <app:collection> element
		feeds=set()
		for c in doc.root.Workspace[0].Collection:
			#	The name of the EntitySet can be used as the value of
			#	the <atom:title>... child element of the
			#	<app:collection> element
			self.assertTrue(c.Title.GetValue()==c.href)
			feeds.add(str(c.href))
		for r in ("Customers","Orders","OrderLines","Employees","Documents","ExtraEntities.Content","ExtraEntities.BitsAndPieces"):
			self.assertTrue(r in feeds,"Missing feed: %s"%r)
		request=MockRequest('/service.svc/')
		request.SetHeader('Accept',"application/json")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200,"Service root response: %i"%request.responseCode)		
		self.assertTrue(request.responseHeaders['Content-Type']=='application/json',"Expected application/json")
		obj=json.loads(request.wfile.getvalue())
		self.assertTrue("EntitySets" in obj)
		self.assertTrue(type(obj["EntitySets"])==ListType)
		self.assertTrue(len(obj["EntitySets"])==7)
		for c in obj["EntitySets"]:
			self.assertTrue(type(c)==UnicodeType)
	
	def testCaseEntitySet1(self):
		"""EntitySet names MAY be directly followed by open and close parenthesis."""		
		request1=MockRequest('/service.svc/Customers')
		request2=MockRequest('/service.svc/Customers()')
		request1.Send(self.svc)
		request2.Send(self.svc)
		self.assertTrue(request1.responseCode==200)		
		self.assertTrue(request2.responseCode==200)
		doc1=app.Document()
		doc1.Read(request1.wfile.getvalue())		
		doc2=app.Document()
		doc2.Read(request2.wfile.getvalue())		
		output=doc1.DiffString(doc2)
		self.assertTrue(request1.wfile.getvalue()==request2.wfile.getvalue(),"Mismatched responses with (): \n%s"%(output))

	def testCaseEntitySet2(self):
		"""If an EntitySet is not in the default EntityContainer, then the URI
		MUST qualify the EntitySet name with the EntityContainer name.
		
		Although not explicitly stated, it seems that an entity set MUST NOT be
		prefixed with the container name if it is in the default
		EntityContainer.  Witness the error from
		http://services.odata.org/OData/OData.svc/DemoService.Products"""
		request=MockRequest('/service.svc/Content')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==404,"Unqualified entity set from non-default container")
		request=MockRequest('/service.svc/ExtraEntities.Content')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200,"Qualified entity set from non-default container")
		request=MockRequest('/service.svc/SampleEntities.Customers')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==404,"Qualified entity set from default container")
	
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
		self.assertTrue(request.responseCode==200)
		# Add test case of a property on a sub-type perhaps?
		request=MockRequest("/service.svc/Customers('ALFKI')/Title")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==404)		
		request=MockRequest("/service.svc/Customers('ALFKI')/Address/Street")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)		
		request=MockRequest("/service.svc/Customers('ALFKI')/Address/ZipCode")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==404)		
	
	def testCaseComplexProperty(self):
		"""If the prior URI path segment identifies an instance of an EntityType
		ET1, this value MUST be the name of a declared property or dynamic
		property on type ET1 which represents a ComplexType instance.
		
		If the prior URI path segment identifies an instance of a ComplexType
		CT1, this value MUST be the name of a declared property on CT1 which
		represents a ComplexType instance."""
		request=MockRequest("/service.svc/Customers('ALFKI')/Address")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
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
		self.assertTrue(request.responseCode==200)
		request=MockRequest("/service.svc/Customers('ALFKI')/$links/Orders")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		request=MockRequest("/service.svc/Customers('ALFKI')/$links/Orders/dummy")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==400)
		
	def testCaseKeyPredicateSingle(self):
		"""An EntityKey consisting of a single EntityType property MAY be
		represented using the "<Entity Type property name> = <Entity Type
		property value>" syntax"""
		request1=MockRequest("/service.svc/Customers('ALFKI')")
		request2=MockRequest("/service.svc/Customers(CustomerID='ALFKI')")
		request1.Send(self.svc)
		request2.Send(self.svc)
		self.assertTrue(request1.responseCode==200)		
		self.assertTrue(request2.responseCode==200)
		self.assertTrue(request1.wfile.getvalue()==request2.wfile.getvalue(),"Mismatched responses with ()")

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
		self.assertTrue(isinstance(doc.root,atom.Feed),"Expected atom.Feed from /Customers")
		self.assertTrue(len(doc.root.Entry)==91,"Sample server has 91 Customers")
		#	the serviceOperation-collEt rule can be substituted for the
		#	first occurrence of an entitySet rule in the Resource Path
		request=MockRequest("/service.svc/CustomersByCity?city='Chunton'")
		request.Send(self.svc)
		doc=app.Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,atom.Feed),"Expected atom.Feed from /CustomersByCity")
		self.assertTrue(len(doc.root.Entry)==1,"Sample server has 1 Customer in Chunton")
		#	If the Entity Data Model... ...does not include an EntitySet with the name
		#	specified, the this URI (and any URI created by appending additional path segments)
		#	MUST be treated as identifying a non-existent resource.
		request=MockRequest("/service.svc/Prospects")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==404)		
		request=MockRequest("/service.svc/Prospects/$count")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==404)
		# all system query options are valid
		request=MockRequest("/service.svc/Customers?$expand=Orders&$filter=substringof(CompanyName,%20'bikes')&$orderby=CompanyName%20asc&$top=2&$skip=3&$skiptoken='Contoso','AKFNU'&$inlinecount=allpages&$select=CustomerID,CompanyName,Orders&$format=xml")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
	
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
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,Entry),"Expected a single Entry, found %s"%doc.root.__class__.__name__)
		self.assertTrue(doc.root['CustomerID']=='ALFKI',"Bad CustomerID")
		request=MockRequest("/service.svc/Customers('ALFKJ')")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==404)
		request=MockRequest("/service.svc/Customers('ALFKJ')/Address")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==404)
		# $orderby, $skip, $top, $skiptoken, $inlinecount all banned
		baseURI="/service.svc/Customers('ALFKI')?$expand=Orders&$filter=substringof(CompanyName,%20'bikes')&$select=CustomerID,CompanyName,Orders&$format=xml"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)		
		for x in ["$orderby=CompanyName%20asc","$skip=3","$top=2","$skiptoken='Contoso','AKFNU'","$inlinecount=allpages"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.assertTrue(request.responseCode==400,"URI2 with %s"%x)
	
	def testCaseURI3(self):
		"""URI3 = scheme serviceRoot "/" entitySet "(" keyPredicate ")/" entityComplexProperty
		
		MUST identify an instance of a ComplexType on the specified
		EntityType instance."""
		request=MockRequest("/service.svc/Customers('ALFKI')/Address")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,Property),"Expected a single Property, found %s"%doc.root.__class__.__name__)
		value=doc.root.GetValue()
		self.assertTrue(value['Street']=='Mill Road',"Bad street in address")		
		# $expand, $orderby, $skip, $top, $skiptoken, $inlinecount and $select all banned
		baseURI="/service.svc/Customers('ALFKI')/Address?$filter=substringof(CompanyName,%20'bikes')&$format=xml"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		for x in ["$expand=Orders","$orderby=CompanyName%20asc","$skip=3","$top=2","$skiptoken='Contoso','AKFNU'","$inlinecount=allpages","$select=CustomerID,CompanyName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.assertTrue(request.responseCode==400,"URI3 with %s"%x)
	
	def testCaseURI4(self):
		"""URI4 = scheme serviceRoot "/" entitySet "(" keyPredicate ")/" entityComplexProperty "/" entityProperty
		
		MUST identify a property of a ComplexType defined on the
		EntityType of the entity whose EntityKey value is specified by
		the keyPredicate and is within the specified EntitySet."""
		request=MockRequest("/service.svc/Customers('ALFKI')/Address/Street")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,Property),"Expected a single Property, found %s"%doc.root.__class__.__name__)
		value=doc.root.GetValue()
		self.assertTrue(value.pyValue=='Mill Road',"Bad street")
		request=MockRequest("/service.svc/Customers('ALFKI')/Address/Street/$value")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.wfile.getvalue()=='Mill Road',"Bad street $vaue")
		baseURI="/service.svc/Customers('ALFKI')/Address/Street?$format=xml"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		for x in ["$expand=Orders","$orderby=CompanyName%20asc","$filter=substringof(CompanyName,%20'bikes')",
			"$skip=3","$top=2","$skiptoken='Contoso','AKFNU'","$inlinecount=allpages",
			"$select=CustomerID,CompanyName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.assertTrue(request.responseCode==400,"URI4 with %s"%x)
	
	def testCaseURI5(self):
		"""URI5 = scheme serviceRoot "/" entitySet "(" keyPredicate ")/" entityProperty

		MUST identify a property whose type is an EDMSimpleType on the
		EntityType instance (identified with EntityKey equal to the
		specified key predicate) within the specified EntitySet"""
		request=MockRequest("/service.svc/Customers('ALFKI')/CompanyName")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,Property),"Expected a single Property, found %s"%doc.root.__class__.__name__)
		value=doc.root.GetValue()
		self.assertTrue(value.pyValue=='Example Inc',"Bad company")
		request=MockRequest("/service.svc/Customers('ALFKI')/CompanyName/$value")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.wfile.getvalue()=='Example Inc',"Bad company $vaue")
		baseURI="/service.svc/Customers('ALFKI')/CompanyName?$format=xml"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		for x in ["$expand=Orders","$orderby=CompanyName%20asc","$filter=substringof(CompanyName,%20'bikes')",
			"$skip=3","$top=2","$skiptoken='Contoso','AKFNU'","$inlinecount=allpages",
			"$select=CustomerID,CompanyName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.assertTrue(request.responseCode==400,"URI5 with %s"%x)
		"""Any media type is a valid value for [the MimeType] attribute.
		If this attribute is present on a property definition, then any
		RetreiveValue Request for the property MUST return a response
		which uses the specified mime type as the content type of the
		response body."""
		request=MockRequest("/service.svc/ExtraEntities.BitsAndPieces(1)/Details/$value")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['Content-Type']=="application/x-details")
		self.assertTrue(request.wfile.getvalue()=='blahblah',"Bad details $value")		

	def testCaseURI6(self):
		"""URI6 = scheme serviceRoot "/" entitySet "(" keyPredicate ")/" entityNavProperty

		MUST identify a set of entities or an EntityType instance that
		is reached via the specified NavigationProperty on the entity
		identified by the EntitySet name and key predicate specified."""
		request=MockRequest("/service.svc/Customers('ALFKI')/Orders")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,atom.Feed),"Expected atom.Feed from navigation property Orders")
		self.assertTrue(len(doc.root.Entry)==2,"Sample customer has 2 orders")
		# TODO: navigation property pointing to a single Entity (Note 1)
# 		baseURI="/service.svc/Customers('ALFKI')/Orders?$expand=Orders&$filter=substringof(CompanyName,%20'bikes')&$format=xml&$select=CustomerID,CompanyName,Orders"
# 		request=MockRequest(baseURI)
# 		request.Send(self.svc)
# 		self.assertTrue(request.responseCode==200)
# 		for x in ["$orderby=CompanyName%20asc",
# 			"$skip=3","$top=2","$skiptoken='Contoso','AKFNU'","$inlinecount=allpages"]:
# 			request=MockRequest(baseURI+"&"+x)
# 			request.Send(self.svc)
# 			self.assertTrue(request.responseCode==400,"UR6 with %s"%x)
		# all system query options are valid when the navigation property identifies a set of entities (Note 2)
		request=MockRequest("/service.svc/Customers?$expand=Orders&$filter=substringof(CompanyName,%20'bikes')&$orderby=CompanyName%20asc&$top=2&$skip=3&$skiptoken='Contoso','AKFNU'&$inlinecount=allpages&$select=CustomerID,CompanyName,Orders&$format=xml")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
	
	def testCaseURI7(self):
		"""URI7 = scheme serviceRoot "/" entitySet "(" keyPredicate ")/$links/" entityNavProperty
		
		MUST identify the collection of all Links from the specified
		EntityType instance (identified by the EntitySet name and key
		predicate specified) to all other entities that can be reached
		via the Navigation Property"""
		request=MockRequest("/service.svc/Customers('ALFKI')/$links/Orders")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,Links),"Expected Links from $links request, found %s"%doc.root.__class__.__name__)
		self.assertTrue(len(doc.root.URI)==2,"Sample customer has 2 orders")
		# test json output
		request=MockRequest("/service.svc/Customers('ALFKI')/$links/Orders?$inlinecount=allpages&$top=1")
		request.SetHeader('Accept',"application/json")
		request.Send(self.svc)
		self.assertTrue(request.responseHeaders['Content-Type']=="application/json")
		obj=json.loads(request.wfile.getvalue())
		self.assertTrue(type(obj)==DictType,"Version 2 JSON response is object")
		self.assertTrue("__count" in obj and obj["__count"]==2,"Version 2 JSON supports $inlinecount")
		self.assertTrue("results" in obj,"Version 2 JSON response has 'results'")
		self.assertTrue(type(obj["results"])==ListType,"list of links")
		self.assertTrue(len(obj["results"])==1,"Sample customer has 2 orders but only 1 returned due to $top")
		for link in obj["results"]:
			self.assertTrue(type(link)==DictType,"link is object")
			self.assertTrue("uri" in link,"link has 'link' propert")
		# similar test but force a version 1 response
		request=MockRequest("/service.svc/Customers('ALFKI')/$links/Orders")
		request.SetHeader('Accept',"application/json")
		request.SetHeader('MaxDataServiceVersion',"1.0; old max")
		request.Send(self.svc)
		obj=json.loads(request.wfile.getvalue())
		self.assertTrue(type(obj)==ListType,"Version 1 JSON response is array")
		self.assertTrue(len(obj)==2,"2 links in response")
		# end of json tests
		request=MockRequest("/service.svc/Orders(1)/$links/Customer")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,URI),"Expected URI from $links request")
		self.assertTrue(doc.root.GetValue()=="http://host/service.svc/Customers('ALFKI')","Bad Customer link")			
		baseURI="/service.svc/Customers('ALFKI')/$links/Orders?$format=xml&$skip=3&$top=2&$skiptoken='Contoso','AKFNU'&$inlinecount=allpages"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		for x in ["$expand=Orders",
			"$filter=substringof(CompanyName,%20'bikes')",
			"$orderby=CompanyName%20asc",
			"$select=CustomerID,CompanyName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.assertTrue(request.responseCode==400,"URI7 with %s"%x)
	
	def testCaseURI8(self):
		"""URI8 = scheme serviceRoot "/$metadata"
		
		All data services SHOULD expose a conceptual schema definition
		language (CSDL) based metadata endpoint that...
		
		MUST identify the Entity Data Model Extensions (EDMX) document,
		as specified in [MC-EDMX], which includes the Entity Data Model
		represented using a conceptual schema definition language
		(CSDL), as specified in [MC-CSDL], for the data service."""
		request=MockRequest("/service.svc/$metadata")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=edmx.Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,edmx.Edmx),"Expected Edmx from $metadata request, found %s"%doc.root.__class__.__name__)
		version=doc.Validate()
		# MimeType: This attribute MUST be used on a <Property> element...
		# Each <Property> element defining an EDMSimpleType property MAY<48>
		# include exactly one occurrence of this attribute.
		# Any media type (see [IANA-MMT] ) is a valid value for this attribute.
		pType=doc.root.DataServices["SampleModel.BitsAndPieces.Details"]
		mType=http.MediaType(pType.GetAttribute(MimeType))
		self.assertTrue(mType=="application/x-details","Expected x-details MimeType")	
		self.assertTrue(version=="2.0","Expected data service version 2.0")
		baseURI="/service.svc/$metadata?"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		for x in ["$expand=Orders",
			"$filter=substringof(CompanyName,%20'bikes')",
			"$format=xml",
			"$orderby=CompanyName%20asc",
			"$skip=3",
			"$top=2",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CompanyName,Orders"]:
			request=MockRequest(baseURI+x)
			request.Send(self.svc)
			self.assertTrue(request.responseCode==400,"URI8 with %s"%x)
		
	def testCaseURI9(self):
		"""URI9 = scheme serviceRoot "/$batch"

		MUST identify the endpoint of a data service which accepts Batch Requests.
		
		...If a data service does not implement support for a Batch
		Request, it must return a 4xx response code in the response to
		any Batch Request sent to it."""
		request=MockRequest("/service.svc/$batch")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==404)
		baseURI="/service.svc/$batch?"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==404)
		for x in ["$expand=Orders",
			"$filter=substringof(CompanyName,%20'bikes')",
			"$format=xml",
			"$orderby=CompanyName%20asc",
			"$skip=3",
			"$top=2",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CompanyName,Orders"]:
			request=MockRequest(baseURI+x)
			request.Send(self.svc)
			self.assertTrue(request.responseCode==400,"URI9 with %s"%x)
	
	def testCaseURI10(self):
		"""URI10 = scheme serviceRoot "/" serviceOperation-et

		MUST identify a FunctionImport that returns a single EntityType instance.
		
		If no FunctionImport exists in the Entity Data Model associated
		with the data service which has the same name as specified by
		the serviceOperation-et rule, then this URI MUST represent a
		resource that does not exist in the data model.
		
		If [the HttpMethod] attribute is present, the FunctionImport
		must be callable using the HTTP method specified."""
		# TODO, an actual function that does something that returns a single entity
		request=MockRequest("/service.svc/LastCustomerByLine?line=1")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		request=MockRequest("/service.svc/FirstCustomerByLine?line=1")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==404)
		baseURI="/service.svc/LastCustomerByLine?line=1&$format=xml"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		for x in ["$expand=Orders",
			"$filter=substringof(CompanyName,%20'bikes')",
			"$orderby=CompanyName%20asc",
			"$skip=3",
			"$top=2",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CompanyName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.assertTrue(request.responseCode==400,"URI10 with %s"%x)
		# TODO, a function import that uses a method other than GET
		
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
		request.SetHeader('Accept',"application/json")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		#	check json output
		self.assertTrue(request.responseHeaders['Content-Type']=="application/json")
		obj=json.loads(request.wfile.getvalue())
		#	should be version 2 output
		self.assertTrue("results" in obj,"Expected version 2 JSON output")
		i=0
		for ct in obj["results"]:
			#	should be a complex type
			c=edm.Complex(self.ds['SampleModel.CAddress'])
			JSONToComplex(c,obj)
			if c['Street']=="Mill Road":
				self.assertTrue(c['City']=="Chunton")
				iChunton=i
			else:
				self.assertFalse(c['City'],"Unknown address")
			i=i+1
		#	check version 1 json output
		request=MockRequest("/service.svc/ShippedAddressByDate?date=datetime'2013-08-02'")
		request.SetHeader('Accept',"application/json")
		request.SetHeader('MaxDataServiceVersion',"1.0; old max")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['Content-Type']=="application/json")
		obj=json.loads(request.wfile.getvalue())
		self.assertTrue(type(obj)==ListType,"Expected version 1 JSON output")
		self.assertTrue(len(obj)==i,"Expected same number of results")
		#	End of JSON tests
		request=MockRequest("/service.svc/PendingAddressByDate?date=datetime'2013-08-02'")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==404)
		baseURI="/service.svc/ShippedAddressByDate?date=datetime'2013-08-02'&$format=xml"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		for x in ["$expand=Orders",
			"$filter=substringof(CompanyName,%20'bikes')",
			"$orderby=CompanyName%20asc",
			"$skip=3",
			"$top=2",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CompanyName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.assertTrue(request.responseCode==400,"URI11 with %s"%x)
		
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
		self.assertTrue(request.responseCode==200)
		request=MockRequest("/service.svc/FirstShippedByLine?line=1")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==404)
		baseURI="/service.svc/LastShippedByLine?line=1&$format=xml"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		for x in ["$expand=Orders",
			"$filter=substringof(CompanyName,%20'bikes')",
			"$orderby=CompanyName%20asc",
			"$skip=3",
			"$top=2",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CompanyName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.assertTrue(request.responseCode==400,"URI12 with %s"%x)
	
	def testCaseURI13(self):
		"""URI13 = scheme serviceRoot "/" serviceOperation-collPrim

		MUST identify a FunctionImport which returns a collection of
		Primitive type values

		If no FunctionImport exists in the Entity Data Model associated
		with the data service that has the same name as specified by the
		serviceOperation-collPrim rule, then this URI MUST represent a
		resource that does not exist in the data model."""
		request=MockRequest("/service.svc/ShippedCustomerNamesByDate?date=datetime'2013-08-02'")
		request.SetHeader('Accept',"application/json")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		#	check json version 2 ouptput
		self.assertTrue(request.responseHeaders['Content-Type']=="application/json")
		obj=json.loads(request.wfile.getvalue())
		#	should be version 2 output
		self.assertTrue("results" in obj,"Expected version 2 JSON output")
		i=0
		for prim in obj["results"]:
			#	should be a simple type
			v=edm.StringValue()
			JSONToSimpleValue(v,prim)
			i=i+1
		#	check version 1 json output
		request=MockRequest("/service.svc/ShippedCustomerNamesByDate?date=datetime'2013-08-02'")
		request.SetHeader('Accept',"application/json")
		request.SetHeader('MaxDataServiceVersion',"1.0; old max")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['Content-Type']=="application/json")
		obj=json.loads(request.wfile.getvalue())
		self.assertTrue(type(obj)==ListType,"Expected version 1 JSON output")
		self.assertTrue(len(obj)==i,"Expected same number of results")
		#	End of JSON tests
		request=MockRequest("/service.svc/PendingCustomerNamesByDate?date=datetime'2013-08-02'")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==404)
		baseURI="/service.svc/ShippedCustomerNamesByDate?date=datetime'2013-08-02'&$format=xml"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		for x in ["$expand=Orders",
			"$filter=substringof(CompanyName,%20'bikes')",
			"$orderby=CompanyName%20asc",
			"$skip=3",
			"$top=2",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CompanyName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.assertTrue(request.responseCode==400,"URI13 with %s"%x)
	
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
		self.assertTrue(request.responseCode==200)		
		request=MockRequest("/service.svc/LastCustomerNameByLine/$value?line=1")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		request=MockRequest("/service.svc/FirstCustomerNameByLine?line=1")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==404)		
		baseURI="/service.svc/LastCustomerNameByLine?line=1&$format=xml"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		for x in ["$expand=Orders",
			"$filter=substringof(CompanyName,%20'bikes')",
			"$orderby=CompanyName%20asc",
			"$skip=3",
			"$top=2",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CompanyName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.assertTrue(request.responseCode==400,"URI14 with %s"%x)


	def testCaseURI15(self):
		"""URI15 = scheme serviceRoot "/" entitySet count

		MUST identify the count of all instances of the base EntityType
		or any of the EntityType's subtypes within the specified
		EntitySet specified in the last URI segment"""
		request=MockRequest('/service.svc/Customers/$count')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.wfile.getvalue()=="91","Sample server has 91 Customers")
		baseURI="/service.svc/Customers/$count?$expand=Orders&$filter=substringof(CompanyName,%20'bikes')&$orderby=CompanyName%20asc&$skip=3&$top=2"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		for x in ["$format=xml",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CompanyName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.assertTrue(request.responseCode==400,"URI15 with %s"%x)
	
	def testCaseURI16(self):
		"""URI16 = scheme serviceRoot "/" entitySet "(" keyPredicate ")" count

		MAY identify the count of a single EntityType instance (the
		count value SHOULD always equal one), which is within the
		EntitySet specified in the URI, where key EntityKey is equal to
		the value of the keyPredicate specified."""
		request=MockRequest("/service.svc/Customers('ALFKI')/$count")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.wfile.getvalue()=="1","the count value SHOULD always equal one")
		request=MockRequest("/service.svc/Customers('ALFKJ')/$count")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==404)
		baseURI="/service.svc/Customers('ALFKI')/$count?$expand=Orders&$filter=substringof(CompanyName,%20'bikes')"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		for x in ["$format=xml",
			"$orderby=CompanyName%20asc",
			"$skip=3",
			"$top=2",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CompanyName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.assertTrue(request.responseCode==400,"URI16 with %s"%x)
	
	def testCaseURI17(self):
		"""URI17 = scheme serviceRoot "/" entitySet "(" keyPredicate ")" value

		MUST identify the Media Resource [RFC5023] associated with the
		identified EntityType instance. The EntityType that defines the
		entity identified MUST be annotated with the "HasStream"
		attribute."""
		request=MockRequest("/service.svc/Documents(301)/$value")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		baseURI="/service.svc/Documents(301)/$value?$format=application/octet-stream"
		request=MockRequest(baseURI)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		for x in ["$expand=Orders",
			"$filter=substringof(CompanyName,%20'bikes')",
			"$orderby=CompanyName%20asc",
			"$skip=3",
			"$top=2",
			"$skiptoken='Contoso','AKFNU'",
			"$inlinecount=allpages",
			"$select=CustomerID,CompanyName,Orders"]:
			request=MockRequest(baseURI+"&"+x)
			request.Send(self.svc)
			self.assertTrue(request.responseCode==400,"URI17 with %s"%x)
	
	def testCaseQueryOptions(self):
		"""If a data service does not support a System Query Option, it
		MUST reject any requests which contain the unsupported option"""			
		request=MockRequest("/service.svc/Documents(301)?$unsupported=1")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==400)
		request=MockRequest("/service.svc/Documents(301)?$filter=true%20nand%20false")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==400)
		"""A data service URI with more than one query option present
		MUST be evaluated as if the query options were applied to the
		resource(s) identified by the Resource Path section of the URI,
		in the following order: $format, $inlinecount, $filter,
		$orderby, $skiptoken, $skip, $top, $expand"""
		# TODO
		
	def testCaseExpand(self):
		"""The left most entityNavProperty in an expandClause MUST
		represent a NavigationProperty defined in the EntityType, or a
		sub type thereof
		
		A subsequent NavigationProperty in the same expandClause must
		represent a NavigationProperty defined on the EntityType, or a
		sub type thereof, represented by the prior NavigationProperty in
		the expandClause."""
		request=MockRequest("/service.svc/Customers?$expand=Orders")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,atom.Feed),"Expected atom.Feed from /Customers?$expand=Orders")
		for e in doc.root.Entry:
			linkURI,linkInline=e.GetLink('Orders')
			if e['CustomerID'].pyValue=='ALFKI':
				#	A NavigationProperty that represents an EntityType
				#	instance or a group of entities and that is
				#	serialized inline MUST be placed within a single
				#	<m:inline> element that is a child element of the
				#	<atom:link> element.
				self.assertTrue(isinstance(linkInline,atom.Feed),"Expected atom.Feed in Orders link")
				self.assertTrue(len(linkInline.Entry)==2,"Expected 2 Orders in expand")
			else:
				self.assertTrue(linkInline is None,"Expected no inline content for Orders link")
		#	Test json format
		request=MockRequest("/service.svc/Customers?$expand=Orders")
		request.SetHeader('Accept',"application/json")
		request.Send(self.svc)
		obj=json.loads(request.wfile.getvalue())
		#	A NavigationProperty which is serialized inline MUST be
		#	represented as a name/value pair ...with the name equal to
		#	the NavigationProperty name.... If the NavigationProperty
		#	represents an EntitySet, the value MUST be as specified in
		#	Entity Set (as a JSON array)
		for objItem in obj["results"]:
			orders=objItem["Orders"]
			if objItem["CustomerID"]=='ALFKI':
				self.assertTrue("results" in orders,"Version 2 expanded entity set as array")
				self.assertTrue(len(orders["results"])==2,"Expected 2 Orders in expand")
			else:
				self.assertTrue(len(orders["results"])==0,"Expected no inline content for Orders link")							
		request=MockRequest("/service.svc/Orders(1)?$expand=Customer")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,atom.Entry),"Expected atom.Entry from /Orders(1)?$expand=Customer")
		linkURI,linkInline=doc.root.GetLink('Customer')
		self.assertTrue(isinstance(linkInline,atom.Entry),"Expected atom.Entry in Customer link")
		#	Test json format
		request=MockRequest("/service.svc/Orders(1)?$expand=Customer")
		request.SetHeader('Accept',"application/json")
		request.Send(self.svc)
		obj=json.loads(request.wfile.getvalue())
		#	If the NavigationProperty identifies a single EntityType
		#	instance, the value MUST be a JSON object representation of
		#	that EntityType instance, as specified in Entity Type (as a
		#	JSON object)
		customer=obj["Customer"]
		self.assertTrue(type(customer)==DictType,"Single object result")
		self.assertTrue(customer["CustomerID"]=='ALFKI',"Matching customer")
		request=MockRequest("/service.svc/Orders(3)?$expand=Customer")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,atom.Entry),"Expected atom.Entry from /Orders(3)?$expand=Customer")
		linkURI,linkInline=doc.root.GetLink('Customer')
		#	If the value of a NavigationProperty is null, then an empty
		#	<m:inline> element MUST appear under the <atom:link>
		#	element which represents the NavigationProperty
		self.assertTrue(linkInline is None,"Expected empty inline in Customer link")
		#	Test json format
		request=MockRequest("/service.svc/Orders(3)?$expand=Customer")
		request.SetHeader('Accept',"application/json")
		request.Send(self.svc)
		obj=json.loads(request.wfile.getvalue())
		customer=obj["Customer"]
		self.assertTrue(customer is None,"null json response")
		# test a property we can't expand!
		request=MockRequest("/service.svc/Customers?$expand=Address")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==400)
			
	def testCaseFilter(self):
		request=MockRequest("/service.svc/Orders?$filter=ShippedDate%20lt%20datetime'2013-08-05T00:00'")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,atom.Feed),"Expected atom.Feed from /Orders?$filter=...")
		self.assertTrue(len(doc.root.Entry)==3,"Expected 3 Order after filtering")
	
	def testCaseFormat(self):
		"""The $format query option ... SHOULD take precedence over the
		value(s) specified in the Accept request header.

		If the value of the query option is "atom", then the media type
		used in the response MUST be "application/atom+xml".

		If the value of the query option is "json", then the media type
		used in the response MUST be "application/json".

		If the value of the query option is "xml", then the media type
		used in the response MUST be "application/xml"	"""
		request=MockRequest("/service.svc/Orders?$format=xml")
		request.SetHeader('Accept',"application/json")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['Content-Type']=="application/xml")
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,atom.Feed),"Expected atom.Feed from /Orders?$format=xml")
		self.assertTrue(len(doc.root.Entry)==4,"Expected 4 Orders")
		request=MockRequest("/service.svc/Orders?$format=atom")
		request.SetHeader('Accept',"application/xml")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['Content-Type']=="application/atom+xml")
		request=MockRequest("/service.svc/Orders(1)?$format=json")
		request.SetHeader('Accept',"application/xml")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['Content-Type']=="application/json")
		doc=json.loads(request.wfile.getvalue())
		self.assertTrue("OrderID" in doc,"Expected a single entry object")
		# self.assertTrue(len(doc['error'])==2,"Expected two children")
		# self.assertTrue(doc['error']['code']=="DataServiceVersionMismatch","Error code")
		# self.assertTrue(doc['error']['message']=="Maximum supported protocol version: 2.0","Error message")		
		#
		# TODO: if ever, support custom format specifiers (note that media types are supported)
		# request.MockRequest("/Orders(1)/ShipCountry/$value/?$format=example")
		# request.SetHeader('Accept',"application/json")		
		
	def testCaseOrderby(self):
		"""the data service MUST return the entities, in order, based on
		the expression specified.
		
		If multiple expressions are specified ... then a data service
		MUST return the entities ordered by a secondary sort for each
		additional expression specified.
		
		If the expression includes the optional asc clause or if no
		option is specified, the entities MUST be returned in ascending
		order.
		
		If the expression includes the optional desc clause, the
		entities MUST be returned in descending order."""
		request=MockRequest("/service.svc/Orders?$orderby=ShippedDate")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,atom.Feed),"Expected atom.Feed from /Orders?$orderby=...")
		self.assertTrue(len(doc.root.Entry)==4,"Expected 4 Orders")
		# default is ascending order, later dates are later in the list
		lastTime=iso8601.TimePoint("19000101T000000")
		for e in doc.root.Entry:
			currTime=e['ShippedDate'].pyValue
			self.assertTrue(currTime>=lastTime,"ShippedDate increasing")
			lastTime=currTime
		request=MockRequest("/service.svc/Orders?$orderby=ShippedDate,OrderID%20desc")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		lastTime=iso8601.TimePoint("19000101T000000")
		lastID=10000
		failFlag=True
		for e in doc.root.Entry:
			currTime=e['ShippedDate'].pyValue
			currID=e['OrderID'].pyValue
			self.assertTrue(currTime>=lastTime,"ShippedDate increasing")
			if currTime==lastTime:
				failFlag=False
				self.assertTrue(currID<lastID,"OrderID decreasing")
			lastTime=currTime
			lastID=currID
		self.assertFalse(failFlag,"Expected one equality test")


	def testCaseSkip(self):
		"""If the data service URI contains a $skip query option, but
		does not contain an $orderby option, then the entities in the
		set MUST first be fully ordered by the data service. Such a full
		order SHOULD be obtained by sorting the entities based on their
		EntityKey values."""
		request=MockRequest("/service.svc/Orders?$orderby=ShippedDate")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(len(doc.root.Entry)==4,"Expected 4 Orders")
		# grab the third ID
		thirdID=doc.root.Entry[2]['OrderID'].pyValue
		request=MockRequest("/service.svc/Orders?$orderby=ShippedDate&$skip=2")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(len(doc.root.Entry)==2,"Expected 2 Orders")
		self.assertTrue(thirdID==doc.root.Entry[0]['OrderID'].pyValue,"Skipped first 2")
		request=MockRequest("/service.svc/Orders?$skip=0")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		lastID=-1
		for e in doc.root.Entry:
			currID=int(e['OrderID'].pyValue)
			self.assertTrue(currID>lastID,"OrderID increasing")
			lastID=currID
			
	def testCaseTop(self):
		"""If the data service URI contains a $top query option, but
		does not contain an $orderby option, then the entities in the
		set MUST first be fully ordered by the data service. Such a full
		order SHOULD be obtained by sorting the entities based on their
		EntityKey values."""
		request=MockRequest("/service.svc/Orders?$orderby=ShippedDate")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(len(doc.root.Entry)==4,"Expected 4 Orders")
		# grab the first ID
		firstID=doc.root.Entry[0]['OrderID'].pyValue
		request=MockRequest("/service.svc/Orders?$orderby=ShippedDate&$top=2")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(len(doc.root.Entry)==2,"Expected 2 Orders")
		self.assertTrue(firstID==doc.root.Entry[0]['OrderID'].pyValue,"First one correct")
		request=MockRequest("/service.svc/Orders?$top=4")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		lastID=-1		
		for e in doc.root.Entry:
			currID=int(e['OrderID'].pyValue)
			self.assertTrue(currID>lastID,"OrderID increasing")
			lastID=currID
		request=MockRequest("/service.svc/Orders?$top=0")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(len(doc.root.Entry)==0,"Expected 0 Orders")
			

	def testCaseInlineCount(self):
		"""A data service URI with an $inlinecount System Query Option
		specifies that the response to the request MUST include the
		count of the number of entities in the collection of entities,
		which are identified by the Resource Path section of the URI
		after all $filter System Query Options have been applied
		
		If a value other than "allpages" or "none" is specified, the
		data service MUST return a 4xx error response code.

		If a value of "none" is specified, the data service MUST NOT
		include the count in the response."""
		request=MockRequest("/service.svc/Orders?$inlinecount=allpages")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(len(doc.root.Entry)==4,"Expected 4 Orders")
		self.assertTrue(doc.root.Count.GetValue()==4,"Expected count of 4 Orders")
		request=MockRequest("/service.svc/Orders?$inlinecount=none")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(len(doc.root.Entry)==4,"Expected 4 Orders")
		self.assertTrue(doc.root.Count is None,"Expected no count")
		request=MockRequest("/service.svc/Orders?$top=2&$inlinecount=allpages")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(len(doc.root.Entry)==2,"Expected 2 Orders")
		self.assertTrue(doc.root.Count.GetValue()==4,"Expected count of 4 Orders")
		request=MockRequest("/service.svc/Orders?$top=2&$inlinecount=somepages")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==400)
			
	def testCaseSelectClause1(self):
		"""The left most selectedProperty or selectedNavProperty in a
		selectedClause MUST be a star or represent a property defined in
		the EntityType, or a subtype thereof, that is identified by the
		Resource Path section of the URI."""
		request=MockRequest("/service.svc/Customers?$select=CustomerID,CompanyName,Address")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		request=MockRequest("/service.svc/Customers?$select=*")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		request=MockRequest("/service.svc/Customers?$select=ShippedDate")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==400)
	
	def testCaseSelectClause2(self):
		"""A subsequent selectedProperty or selectedNavProperty in the
		same selectClause MUST represent a property defined on the
		EntityType, or a subtype thereof, that is represented by the
		prior navigation property in the selectClause."""
		request=MockRequest("/service.svc/Orders?$select=Customer/CompanyName")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)		
		request=MockRequest("/service.svc/Orders?$select=Customer/ShippedDate")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==400)		

	def testCaseSelectClause3(self):
		"""For AtomPub formatted responses: The value of a selectQueryOp
		applies only to the properties returned within the
		<m:properties> element...
		For example, if a property of an Entity Type is mapped with the
		attribute KeepInContent=false,... then that property must always
		be included in the response according to its Customizable Feed
		mapping."""
		# TODO
	
	def testCaseSelectClause4(self):
		"""For JSON formatted responses: The value of a selectQueryOp
		applies only to the name/value pairs with a name that does not
		begin with two consecutive underscore characters."""
		# TODO

	def testCaseSelectClause5(self):
		"""If a property is not requested as a selectItem (explicitly or
		via a star) it SHOULD NOT be included in the response."""
		# TODO
		
	def testCaseSelectClause6(self):
		"""If a selectedProperty appears alone as a selectItem in a
		request URI, then the response MUST contain the value of the
		property."""
		# TODO
		
	def testCaseSelectClause7(self):
		"""If a star appears alone in a selectClause, all properties on
		the EntityType within the collection of entities identified by
		the last path segment in the request URI MUST be included in the
		response."""
		request=MockRequest("/service.svc/Customers?$select=*")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		# TODO
		
	def testCaseSelectClause8(self):
		"""If a star appears in a selectItem following a
		selectedNavProperty, all non-navigation properties of the entity
		or entities represented by the prior selectedNavProperty MUST be
		included in the response."""
		request=MockRequest("/service.svc/Customers?$select=CustomerID,Orders/*&$expand=Orders/OrderLine")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		# TODO
		
	def testCaseSelectClause9(self):
		"""If a navigation property appears as the last segment of a
		selectItem and does not appear in an $expand query option, then
		the entity or collection of entities identified by the
		navigation property MUST be represented as deferred content"""
		request=MockRequest("/service.svc/Customers?$select=CustomerID,Orders")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		# TODO
		
	def testCaseSelectClause10(self):
		"""If a navigation property appears as the last segment of a
		selectItem and the same property is specified as a segment of a
		path in an $expand query option, then all the properties of the
		entity identified by the selectItem MUST be in the response. In
		addition, all the properties of the entities identified by
		segments in the $expand path after the segment that matched the
		selectedItem MUST also be included in the response."""
		request=MockRequest("/service.svc/Customers?$select=CustomerID,Orders&$expand=Orders/OrderLine")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		# TODO
		
	def testCaseSelectClause11(self):
		"""If multiple selectClause instances exist in a $select query
		option, then the total set of property values to be returned is
		equal to the union of the set of properties identified by each
		selectClause."""
		# TODO
		
	def testCaseSelectClause12(self):
		"""Redundant selectClause rules on the same URI can be
		considered valid, but MUST NOT alter the meaning of the URI."""
		# TODO
	
	def testCaseServiceOperationParameters(self):
		"""If a Service Operation requires input parameters, a null
		value may be specified for nullable type parameters by not
		including the parameter in the query string of the request
		URI."""
		# TODO
	
	def testCaseContentKind(self):
		"""If the FC_ContentKind property is not defined for an
		EntityType property, the value of the property should be assumed
		to be "text"
		"""
		request=MockRequest("/service.svc/Employees('1')")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,Entry),"Expected a single Entry, found %s"%doc.root.__class__.__name__)
		self.assertTrue(doc.root.Title.type==atom.TextType.text,"title is text")
		self.assertTrue(doc.root.Title.GetValue()=="Joe Bloggs","title is employee name")
		# Now let's go looking for the Location element...
		nLocation=0
		for e in doc.root.GetChildren():
			if e.GetXMLName()==(u"http://www.example.com",u"Location"):
				nLocation+=1
				self.assertTrue(e.GetValue()=="Chunton","Location is employee city name")
		self.assertTrue(nLocation==1,"Expected 1 and only 1 Location: %i"%nLocation)
	
	def testCaseMiscURI(self):
		"""Example URIs not tested elsewhere:"""
		for u in [
			"/service.svc/Customers",
			"/service.svc/Customers('ALFKI')/Orders"
			]:
			request=MockRequest(u)
			request.Send(self.svc)
			self.assertTrue(request.responseCode==200,"misc URI failed (path): %s"%u)

	def testCaseInsertEntity(self):
		customers=self.ds['SampleModel.SampleEntities.Customers'].GetCollection()
		customer=customers.NewEntity()
		customer['CustomerID'].SetFromPyValue(u'STEVE')
		customer['CompanyName'].SetFromPyValue("Steve's Inc")
		customer['Address']['City'].SetFromPyValue('Cambridge')
		#	street left blank
		request=MockRequest("/service.svc/Customers","POST")
		doc=Document(root=Entry(None,customer))
		data=str(doc)
		request.SetHeader('Content-Type',ODATA_RELATED_ENTRY_TYPE)
		request.SetHeader('Content-Type',str(len(data)))
		request.rfile.write(data)
		# print request.rfile.getvalue()		
		request.Send(self.svc)
		self.assertTrue(request.responseCode==201)
		# We expect a location header
		self.assertTrue(request.responseHeaders['Location']=="http://host/service.svc/Customers('STEVE')")
		self.assertTrue(request.responseHeaders['Content-Type']==http.MediaType(ODATA_RELATED_ENTRY_TYPE))
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,Entry),"Expected a single Entry, found %s"%doc.root.__class__.__name__)
		newCustomer=Entity(self.ds['SampleModel.SampleEntities.Customers'])
		doc.root.GetValue(newCustomer)
		self.assertTrue(newCustomer['CompanyName'].pyValue==u"Steve's Inc")
		self.assertTrue(newCustomer['Address']['City'].pyValue==u"Cambridge")
		self.assertFalse(newCustomer['Address']['Street'])	
		# insert entity with binding
		customer=customers.NewEntity()
		customer['CustomerID'].SetFromPyValue(u'ASDFG')
		customer['CompanyName'].SetFromPyValue("Contoso Widgets")
		customer['Address']['Street'].SetFromPyValue('58 Contoso St')
		customer['Address']['City'].SetFromPyValue('Seattle')
		customer.BindEntity("Orders",3)
		customer.BindEntity("Orders",4)
		request=MockRequest("/service.svc/Customers","POST")
		
if __name__ == "__main__":
	VERBOSE=True
	unittest.main()
