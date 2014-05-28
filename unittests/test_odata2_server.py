#! /usr/bin/env python

import unittest, random, decimal, math, hashlib
from types import *

HTTP_PORT=random.randint(1111,9999)

from threading import Thread
from SocketServer import ThreadingMixIn
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from pyslet.vfs import OSFilePath as FilePath
from test_rfc5023 import MockRequest
import pyslet.rfc2396 as uri
import pyslet.rfc4287 as atom
import pyslet.rfc5023 as app
import pyslet.odata2.memds as memds
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

	def log_message(self,format,*args):
		logging.info(format,*args)
		

def runODataServer():
	server=ThreadingHTTPServer(("localhost",HTTP_PORT), MockHandler)
	server.serve_forever()


def suite(prefix='test'):
	t=Thread(target=runODataServer)
	t.setDaemon(True)
	t.start()
	logging.info("OData tests starting HTTP server on localhost, port %i",HTTP_PORT)
	loader=unittest.TestLoader()
	loader.testMethodPrefix=prefix
	return unittest.TestSuite((
		loader.loadTestsFromTestCase(ODataTests),
		loader.loadTestsFromTestCase(ODataURILiteralTests),
		loader.loadTestsFromTestCase(ServerTests),
		loader.loadTestsFromTestCase(SampleServerTests)
		))
		

def load_tests(loader, tests, pattern):
	"""Called when we execute this file directly.
	
	This rather odd definition includes a larger number of tests, including one
	starting "tesx" which hit the sample OData services on the internet."""
	return suite('test')
	#return suite('tes')

	
from pyslet.odata2.server import *
import pyslet.rfc5023 as app
import pyslet.rfc4287 as atom
import pyslet.rfc2616 as http
import pyslet.iso8601 as iso
import pyslet.odata2.csdl as edm
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
		self.assertTrue(v.value is None,"null value: %s"%repr(v.value))

	def testCaseBinaryLiteral(self):
		"""	binaryUriLiteral = caseSensitiveToken SQUOTE binaryLiteral SQUOTE
			binaryLiteral = hexDigPair
			caseSensitiveToken = "X" / "binary"
			; X is case sensitive binary is not
			hexDigPair = 2*HEXDIG [hexDigPair] """
		v=ParseURILiteral("X'0A'")
		self.assertTrue(v.typeCode==edm.SimpleType.Binary,"binary type: %s"%repr(v.typeCode))
		self.assertTrue(v.value=='\x0a',"binary type: %s"%repr(v.value))
		v=ParseURILiteral("X'0a'")
		self.assertTrue(v.value=="\x0a","binary type: %s"%repr(v.value))
		try:
			v=ParseURILiteral("x'0a'")
			self.fail("Syntax error")
		except ValueError:
			pass
		v=ParseURILiteral("binary'0A'")
		self.assertTrue(v.typeCode==edm.SimpleType.Binary,"binary type: %s"%repr(v.typeCode))
		self.assertTrue(v.value=='\x0a',"binary type: %s"%repr(v.value))
		v=ParseURILiteral("BINARY'0A'")
		self.assertTrue(v.typeCode==edm.SimpleType.Binary,"binary type: %s"%repr(v.typeCode))
		self.assertTrue(v.value=='\x0a',"binary type: %s"%repr(v.value))
		# gotta love those recursive rules
		v=ParseURILiteral("X'deadBEEF'")
		self.assertTrue(v.value=="\xde\xad\xbe\xef","binary type: %s"%repr(v.value))
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
		self.assertTrue(v.value is True,"boolean value: %s"%repr(v.value))
		v=ParseURILiteral("false")
		self.assertTrue(v.typeCode==edm.SimpleType.Boolean,"boolean type: %s"%repr(v.typeCode))
		self.assertTrue(v.value is False,"boolean value: %s"%repr(v.value))

	def testCaseIntLiteral(self):
		"""byteLiteral = 1*3DIGIT;
		int16Literal= sign 1*5DIGIT
		int32Literal= sign 1*10DIGIT
		sbyteliteral= sign 1*3DIGIT	
		All returned as an int32 with python int value."""
		v=ParseURILiteral("0")
		self.assertTrue(v.typeCode==edm.SimpleType.Int32,"0 type: %s"%repr(v.typeCode))
		self.assertTrue(v.value==0,"0 value: %s"%repr(v.value))
		v=ParseURILiteral("1")
		self.assertTrue(v.typeCode==edm.SimpleType.Int32,"1 type: %s"%repr(v.typeCode))
		self.assertTrue(v.value==1,"1 value: %s"%repr(v.value))
		v=ParseURILiteral("2147483647")
		self.assertTrue(v.typeCode==edm.SimpleType.Int32,"2147483647 type: %s"%repr(v.typeCode))
		self.assertTrue(v.value==2147483647,"2147483647 value: %s"%repr(v.value))
		v=ParseURILiteral("0000000000")
		self.assertTrue(v.typeCode==edm.SimpleType.Int32,"0000000000 type: %s"%repr(v.typeCode))
		self.assertTrue(v.value==0,"0000000000 value: %s"%repr(v.value))
		v=ParseURILiteral("-2147483648")
		self.assertTrue(v.typeCode==edm.SimpleType.Int32,"-2147483648 type: %s"%repr(v.typeCode))
		self.assertTrue(v.value==-2147483648,"-2147483648 value: %s"%repr(v.value))
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
		self.assertTrue(isinstance(v.value,iso.TimePoint),"value type: %s"%repr(v.value))
		self.assertTrue(str(v.value)=="2012-06-30T23:59:00","value: %s"%str(v.value))
		v=ParseURILiteral("datetime'2012-06-30T23:59:59'")
		self.assertTrue(v.typeCode==edm.SimpleType.DateTime,"date time type: %s"%repr(v.typeCode))
		self.assertTrue(str(v.value)=="2012-06-30T23:59:59","value: %s"%str(v.value))
		v=ParseURILiteral("datetime'2012-06-30T23:59:59.9999999'")
		self.assertTrue(v.typeCode==edm.SimpleType.DateTime,"date time type: %s"%repr(v.typeCode))
		self.assertTrue(v.value.GetCalendarString(ndp=7,dp=".")=="2012-06-30T23:59:59.9999999")
		# Now for the big one!
		v=ParseURILiteral("datetime'2012-06-30T23:59:60'")
		self.assertTrue(v.typeCode==edm.SimpleType.DateTime,"date time type for leap second: %s"%repr(v.typeCode))
		self.assertTrue(str(v.value)=="2012-06-30T23:59:60","value for leap second: %s"%str(v.value))
		v=ParseURILiteral("datetime'2012-06-30T24:00:00'")
		self.assertTrue(v.typeCode==edm.SimpleType.DateTime,"date time extreme: %s"%repr(v.typeCode))
		self.assertTrue(str(v.value)=="2012-06-30T24:00:00","date time extreme: %s"%str(v.value))
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
				self.fail("Bad parse: %s resulted in %s (%s)"%(bad,repr(v.value),edm.SimpleType.EncodeValue(v.typeCode)))
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
		self.assertTrue(isinstance(v.value,decimal.Decimal),"0M value type: %s"%repr(v.value))
		self.assertTrue(v.value==0,"0M value: %s"%repr(v.value))
		v=ParseURILiteral("1.1m")
		self.assertTrue(v.typeCode==edm.SimpleType.Decimal,"1.1m type: %s"%repr(v.typeCode))
		self.assertTrue(isinstance(v.value,decimal.Decimal),"1.1m value type: %s"%repr(v.value))
		self.assertTrue(v.value*10==11,"1.1m value: %s"%repr(v.value))
		v=ParseURILiteral("12345678901234567890123456789m")
		self.assertTrue(v.typeCode==edm.SimpleType.Decimal,"29-digit type: %s"%repr(v.typeCode))
		self.assertTrue(int(v.value.log10())==28,"29-digit log10 value: %s"%repr(v.value))
		v2=ParseURILiteral("12345678901234567890123456789.12345678901234567890123456789m")
		self.assertTrue(v2.value-v.value<0.13 and v2.value-v.value>0.12,"29digit.29digit value: %s"%repr(v2.value-v.value))
		v=ParseURILiteral("-2147483648M")
		self.assertTrue(v.typeCode==edm.SimpleType.Decimal,"-2147483648 type: %s"%repr(v.typeCode))
		self.assertTrue(v.value==-2147483648,"-2147483648 value: %s"%repr(v.value))
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
		self.assertTrue(type(v.value) is FloatType,"0D value type: %s"%repr(v.value))
		self.assertTrue(v.value==0,"0D value: %s"%repr(v.value))
		v=ParseURILiteral("1.1d")
		self.assertTrue(v.typeCode==edm.SimpleType.Double,"1.1d type: %s"%repr(v.typeCode))
		self.assertTrue(type(v.value) is FloatType,"1.1d value type: %s"%repr(v.value))
		self.assertTrue(v.value*10==11,"1.1d value: %s"%repr(v.value))
		v=ParseURILiteral("12345678901234567D")
		self.assertTrue(v.typeCode==edm.SimpleType.Double,"17-digit type: %s"%repr(v.typeCode))
		self.assertTrue(round(math.log10(v.value),3)==16.092,"29-digit log10 value: %s"%repr(v.value))
		v=ParseURILiteral("-12345678901234567D")
		self.assertTrue(v.typeCode==edm.SimpleType.Double,"17-digit negative type: %s"%repr(v.typeCode))
		self.assertTrue(round(math.log10(-v.value),3)==16.092,"29-digit log10 value: %s"%repr(v.value))
		v=ParseURILiteral("123456789012345678901234567890.123456789012345678901234567890D")
		self.assertTrue(v.typeCode==edm.SimpleType.Double,"30digit.30digit type: %s"%repr(v.typeCode))
		self.assertTrue(round(math.log10(v.value),3)==29.092,"30digit.30digit value: %s"%repr(v.value))
		v=ParseURILiteral("-123456789012345678901234567890.123456789012345678901234567890D")
		self.assertTrue(round(math.log10(-v.value),3)==29.092,"30digit.30digit negative value: %s"%repr(v.value))
		v=ParseURILiteral(".142D")
		self.assertTrue(v.value==0.142,"Empty left value: %s"%repr(v.value))
		v=ParseURILiteral("-.142D")
		self.assertTrue(v.value==-0.142,"Empty left neg value: %s"%repr(v.value))
		v=ParseURILiteral("3.D")
		self.assertTrue(v.value==3,"Empty right value: %s"%repr(v.value))
		v=ParseURILiteral("-3.D")
		self.assertTrue(v.value==-3,"Empty right neg value: %s"%repr(v.value))
		v=ParseURILiteral("3.14159e000d")
		self.assertTrue(round(v.value,3)==3.142,"zero exp: %s"%repr(v.value))
		v=ParseURILiteral("NanD")
		self.assertTrue(math.isnan(v.value),"Nan double: %s"%repr(v.value))
		v=ParseURILiteral("INFD")
		self.assertTrue(v.value>0 and math.isinf(v.value),"Inf double: %s"%repr(v.value))
		v=ParseURILiteral("-INFD")
		self.assertTrue(v.value<0 and math.isinf(v.value),"Negative Inf double: %s"%repr(v.value))		
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
		self.assertTrue(type(v.value) is FloatType,"0f value type: %s"%repr(v.value))
		self.assertTrue(v.value==0,"0f value: %s"%repr(v.value))
		v=ParseURILiteral("1.1f")
		self.assertTrue(v.typeCode==edm.SimpleType.Single,"1.1f type: %s"%repr(v.typeCode))
		self.assertTrue(type(v.value) is FloatType,"1.1f value type: %s"%repr(v.value))
		self.assertTrue(v.value*10==11,"1.1f value: %s"%repr(v.value))
		v=ParseURILiteral("12345678F")
		self.assertTrue(v.typeCode==edm.SimpleType.Single,"8-digit type: %s"%repr(v.typeCode))
		self.assertTrue(v.value==12345678,"8-digit: %s"%repr(v.value))
		v=ParseURILiteral("-12345678F")
		self.assertTrue(v.typeCode==edm.SimpleType.Single,"8-digit negative type: %s"%repr(v.typeCode))
		self.assertTrue(v.value==-12345678,"8-digit neg value: %s"%repr(v.value))
		v=ParseURILiteral("123456789012345678901234567890.123456789012345678901234567890f")
		self.assertTrue(v.typeCode==edm.SimpleType.Single,"30digit.30digit type: %s"%repr(v.typeCode))
		self.assertTrue(round(math.log10(v.value),3)==29.092,"30digit.30digit value: %s"%repr(v.value))
		v=ParseURILiteral("-123456789012345678901234567890.123456789012345678901234567890F")
		self.assertTrue(round(math.log10(-v.value),3)==29.092,"30digit.30digit negative value: %s"%repr(v.value))
		v=ParseURILiteral(".142f")
		self.assertTrue(v.value==0.142,"Empty left value: %s"%repr(v.value))
		v=ParseURILiteral("-.142F")
		self.assertTrue(v.value==-0.142,"Empty left neg value: %s"%repr(v.value))
		v=ParseURILiteral("3.F")
		self.assertTrue(v.value==3,"Empty right value: %s"%repr(v.value))
		v=ParseURILiteral("-3.F")
		self.assertTrue(v.value==-3,"Empty right neg value: %s"%repr(v.value))
		v=ParseURILiteral("3.14159e00F")
		self.assertTrue(round(v.value,3)==3.142,"zero exp: %s"%repr(v.value))
		v=ParseURILiteral("3.E1F")
		self.assertTrue(v.value==30,"Empty right exp value: %s"%repr(v.value))
		v=ParseURILiteral("NanF")
		self.assertTrue(math.isnan(v.value),"Nan single: %s"%repr(v.value))
		v=ParseURILiteral("InfF")
		self.assertTrue(v.value>0 and math.isinf(v.value),"Inf single: %s"%repr(v.value))
		v=ParseURILiteral("-INFF")
		self.assertTrue(v.value<0 and math.isinf(v.value),"Negative Inf single: %s"%repr(v.value))		
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
		self.assertTrue(isinstance(v.value,uuid.UUID),"guide type: %s"%repr(v.value))
		self.assertTrue(v.value.hex.lower()=='c0dec0dec0dec0deffffc0dec0dec0de',"guid value (missing bytes): %s"%repr(v.value))
		v=ParseURILiteral("guid'cd04f705-390c-4736-98dc-a3baa6b3a283'")
		self.assertTrue(v.typeCode==edm.SimpleType.Guid,"guide type: %s"%repr(v.typeCode))
		self.assertTrue(isinstance(v.value,uuid.UUID),"guide type: %s"%repr(v.value))
		self.assertTrue(v.value.hex.lower()=='cd04f705390c473698dca3baa6b3a283',"guid value (random): %s"%repr(v.value))
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
		self.assertTrue(type(v.value)==LongType,"0L value type: %s"%repr(v.value))
		self.assertTrue(v.value==0,"0L value: %s"%repr(v.value))
		v=ParseURILiteral("1234567890123456789l")
		self.assertTrue(v.typeCode==edm.SimpleType.Int64,"19-digit type: %s"%repr(v.typeCode))
		self.assertTrue(v.value==1234567890123456789L,"19-digit value: %s"%repr(v.value))
		v=ParseURILiteral("-1234567890123456789l")
		self.assertTrue(v.typeCode==edm.SimpleType.Int64,"19-digit neg type: %s"%repr(v.typeCode))
		self.assertTrue(v.value==-1234567890123456789L,"19-digit neg value: %s"%repr(v.value))
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
		self.assertTrue(v.value=='0A',"string type: %s"%repr(v.value))
		v=ParseURILiteral("'0a'")
		self.assertTrue(v.value=="0a","string type: %s"%repr(v.value))
		v=ParseURILiteral("'Caf\xc3\xa9'")
		# When parsed from a URL we assume that %-encoding is removed
		# when the parameters are split leaving octet-strings that
		# are parsed.  So utf-8 encoding of strings must be removed
		# at the literal parsing stage
		self.assertTrue(v.value==u"Caf\xe9","unicode string type: %s"%repr(v.value))
		# This next case is a shocker, the specification provides no way to escape SQUOTE
		# We support the undocumented doubling of the SQUOTE character.
		v=ParseURILiteral("'Peter O''Toole'")
		self.assertTrue(v.value==u"Peter O'Toole","double SQUOTE: %s"%repr(v.value))
		v=ParseURILiteral("'Peter O%27Toole'")
		self.assertTrue(v.value==u"Peter O%27Toole","%%-encoding ignored: %s"%repr(v.value))		
		for bad in [ "0A", "'0a","'Caf\xc3 Curtains'","'Peter O'Toole'"]:
			try:
				v=ParseURILiteral(bad)
				self.fail("Bad parse: %s"%bad)
			except UnicodeDecodeError:
				pass
			except ValueError:
				pass

# 	def testCaseDurationLiteral(self):
# 		"""
#		This test is commented out because it turns out that use of duration was a typo
#		in the OData v2 specification and that regular 'time' was intended.
#
# 		timeUriLiteral = "time" SQUOTE timeLiteral SQUOTE
# 		timeLiteral = <Defined by the lexical representation for duration in [XMLSCHEMA2/2]>
# 		
# 		We test by using the examples from XMLSchema"""
# 		v=ParseURILiteral("time'P1Y2M3DT10H30M'")
# 		self.assertTrue(v.typeCode==edm.SimpleType.Time,"date time type: %s"%repr(v.typeCode))
# 		self.assertTrue(isinstance(v.value,xsi.Duration),"value type: %s"%repr(v.value))
# 		self.assertTrue(str(v.value)=="P1Y2M3DT10H30M","value: %s"%str(v.value))		
# 		v=ParseURILiteral("time'-P120D'")
# 		self.assertTrue(v.typeCode==edm.SimpleType.Time,"date time type: %s"%repr(v.typeCode))
# 		# There is no canonical representation so this is a weak test
# 		self.assertTrue(str(v.value)=="-P0Y0M120D","value: %s"%str(v.value))
# 		for good in [
# 			"time'P1347Y'",
# 			"time'P1347M'",
# 			"time'P1Y2MT2H'",
# 			"time'P0Y1347M'",
# 			"time'P0Y1347M0D'",
# 			"time'-P1347M'"]:
# 			v=ParseURILiteral(good)
# 			self.assertTrue(v.typeCode==edm.SimpleType.Time,"date time type: %s"%repr(v.typeCode))
# 			self.assertTrue(isinstance(v.value,xsi.Duration),"value type: %s"%repr(v.value))
# 		for bad in [
# 			"time'P-1347M'",
# 			"time'P1Y2MT'",
# 			"time'P1Y2M3DT10H30M",
# 			"timeP1Y2M3DT10H30M'",
# 			"P1Y2M3DT10H30M"
# 			]:
# 			try:
# 				v=ParseURILiteral(bad)
# 				self.fail("Bad parse: %s resulted in %s (%s)"%(bad,str(v.value),edm.SimpleType.EncodeValue(v.typeCode)))
# 			except ValueError:
# 				pass

	def testCaseDateTimeOffsetLiteral(self):
		"""
		dateTimeOffsetUriLiteral = "datetimeoffset" SQUOTE dateTimeOffsetLiteral SQUOTE
		dateTimeOffsetLiteral = <Defined by the lexical representation for datetime (including timezone offset) in [XMLSCHEMA2/2]>
		
		We test by using the examples from XMLSchema"""
		v=ParseURILiteral("datetimeoffset'2002-10-10T12:00:00-05:00'")
		self.assertTrue(v.typeCode==edm.SimpleType.DateTimeOffset,"date time offset type: %s"%repr(v.typeCode))
		self.assertTrue(isinstance(v.value,iso.TimePoint),"value type: %s"%repr(v.value))
		self.assertTrue(isinstance(v.value,iso.TimePoint),"value type: %s"%repr(v.value))
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
			self.assertTrue(isinstance(v.value,iso.TimePoint),"value type: %s"%repr(v.value))
		for bad in [
			"datetimeoffset'2002-10-10T17:00:00'",	# missing time zone
			"datetimeoffset'2002-10-10T17:00Z'",	# incomplete precision
			"datetimeoffset2002-10-10T17:00:00Z",	# missing quotes
			]:
			try:
				v=ParseURILiteral(bad)
				self.fail("Bad parse: %s resulted in %s (%s)"%(bad,str(v.value),edm.SimpleType.EncodeValue(v.typeCode)))
			except ValueError:
				pass
	

# class ODataStoreClientTests(unittest.TestCase):
# 
# 	Categories={
# 		0:"Food",
# 		1:"Beverages",
# 		2:"Electronics"
# 		}
# 		
# 	def testCaseConstructor(self):
# 		sClient=ODataStoreClient('http://localhost:%i/'%HTTP_PORT)
# 		self.assertTrue(isinstance(sClient,edm.ERStore),"ODataStore not an ERStore")
# 		s=sClient['ODataDemo']
# 		self.assertTrue(isinstance(s,edm.Schema),"ODataStore schema")
# 	
# 	def testCaseEntityReader(self):
# 		sClient=ODataStoreClient('http://localhost:%i/'%HTTP_PORT)
# 		for c in sClient.EntityReader("Categories"):
# 			self.assertTrue("ID" in c,"No key field in category")
# 			self.assertTrue(self.Categories[c["ID"].value]==c["Name"].value,"Category Name")


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
		self.assertTrue('DATASERVICEVERSION' in request.responseHeaders,"Missing DataServiceVersion in response")
		major,minor,ua=ParseDataServiceVersion(request.responseHeaders['DATASERVICEVERSION'])
		self.assertTrue(major==2 and minor==0,"No version should return 2.0")
		request=MockRequest('/')
		request.SetHeader('DataServiceVersion',"1.0; old request")
		request.Send(s)
		self.assertTrue(request.responseCode==200,"Version 1.0 request:\n\n"+request.wfile.getvalue())
		major,minor,ua=ParseDataServiceVersion(request.responseHeaders['DATASERVICEVERSION'])
		self.assertTrue(major==1 and minor==0,"Version 1.0 request should return 1.0 response")				
		request=MockRequest('/')
		request.SetHeader('DataServiceVersion',"2.0; current request")
		request.Send(s)
		self.assertTrue(request.responseCode==200)
		major,minor,ua=ParseDataServiceVersion(request.responseHeaders['DATASERVICEVERSION'])
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
		self.assertTrue(request.responseHeaders['CONTENT-TYPE']=="application/json","Expected JSON response")
		errorDoc=json.loads(request.wfile.getvalue())
		self.assertTrue(len(errorDoc)==1,"Expected a single error object")
		self.assertTrue(len(errorDoc['error'])==2,"Expected two children")
		self.assertTrue(errorDoc['error']['code']=="DataServiceVersionMismatch","Error code")
		self.assertTrue(errorDoc['error']['message']=="Maximum supported protocol version: 2.0","Error message")
		self.assertFalse('innererror' in errorDoc['error'],"No inner error")				
		request=MockRequest('/')
		request.SetHeader('DataServiceVersion',"1.0; old request")
		request.SetHeader('MaxDataServiceVersion',"1.0; old max")
		request.Send(s)
		self.assertTrue(request.responseCode==200)
		major,minor,ua=ParseDataServiceVersion(request.responseHeaders['DATASERVICEVERSION'])
		self.assertTrue(major==1 and minor==0,"MaxVersion 1.0 request should return 1.0 response: %i.%i"%(major,minor))				
		request=MockRequest('/')
		request.SetHeader('DataServiceVersion',"1.0; old request")
		request.SetHeader('MaxDataServiceVersion',"2.0; current max")
		request.Send(s)
		self.assertTrue(request.responseCode==200)
		major,minor,ua=ParseDataServiceVersion(request.responseHeaders['DATASERVICEVERSION'])
		self.assertTrue(major==2 and minor==0,"MaxVersion 2.0 request should return 2.0 response")				
		request=MockRequest('/')
		request.SetHeader('DataServiceVersion',"1.0; old request")
		request.SetHeader('MaxDataServiceVersion',"2.1; future max")
		request.Send(s)
		self.assertTrue(request.responseCode==200)
		major,minor,ua=ParseDataServiceVersion(request.responseHeaders['DATASERVICEVERSION'])
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
		doc=self.LoadMetadata()
		s.SetModel(doc)
		# at this point, the server's model root is available as model
		self.assertTrue(s.model is doc.root,"model attribute")
	
	def testCaseEntityTypeAsAtomEntry(self):
		doc=self.LoadMetadata()
		ds=doc.root.DataServices
		customers=ds['SampleModel.SampleEntities.Customers']
		customer=Entity(customers)
		customer['CustomerID'].SetFromValue('X')
		customer['CompanyName'].SetFromValue('Megacorp')
		# fake existence
		customer.exists=True
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
		navigation=list(customer.NavigationKeys())
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
		self.assertTrue(links['Orders'][0]=="Customers('X')/Orders","Orders link")
		#	[the atom:type attribute] should have a value of ...
		#	"application/atom+xml;type=feed" when the property
		#	identifies an EntitySet.
		self.assertTrue(links['Orders'][1]=="application/atom+xml;type=feed","Orders link type")
		#	Entity binding tests...
		customer.exists=False
		customer['Orders'].BindEntity(1)
		customer['Orders'].BindEntity(2)
		#	it isn't clear if the spec intends to support mixed cases
		#	of deep insert and binding to existing entities on the same
		#	request, but in theory there is no reason why we shouldn't
		order=Entity(ds['SampleModel.SampleEntities.Orders'])
		order['OrderID'].SetFromValue(3)
		customer['Orders'].BindEntity(order)
		#	To bind the new entity to an existing entity the "href"
		#	attribute of the <atom:link> element must represent the URI
		#	of the entity to be linked to.
		entry=Entry(None,customer)
		children=list(entry.FindChildrenDepthFirst(atom.Link))
		self.assertTrue(len(children)==3,"Three links present links")
		links={}
		deepLinks={}
		for child in children:
			if child.rel.startswith(ODATA_RELATED):
				self.assertTrue(child.parent is entry,"Link must be a child of the entry element")
				self.assertTrue(child.title==pName,"Title should be name of navigation property")
				self.assertTrue(child.type is None,"We don't need the child type")
				pName=child.rel[len(ODATA_RELATED):]
				self.assertTrue(pName=='Orders',"Only Orders link is bound")
				if child.href=="Customers('X')/Orders":
					self.assertTrue(child.Inline is not None,"deep link has child")
					self.assertTrue(child.Inline.Feed is not None,"deep link child has Feed")
					# test the collection in the feed
					self.assertTrue(len(child.Inline.Feed.collection)==1,"one deep-linked child")
					e=list(child.Inline.Feed.collection.itervalues())[0]
					self.assertTrue(e['OrderID'].value==3,"Order number 3")
				else:	
					links[child.href]=True
		self.assertTrue(len(links)==2,"Two entities bound")
		self.assertTrue("Orders(1)" in links,"Orders(1)")
		self.assertTrue("Orders(2)" in links,"Orders(2)")		
		#
		#	End of customer tests
		#
		orders=ds['SampleModel.SampleEntities.Orders']
		order=Entity(orders)
		order['OrderID'].SetFromValue(1)
		order.exists=True
		entry=Entry(None,order)
		children=list(entry.FindChildrenDepthFirst(atom.Link))
		links={}
		navigation=list(order.NavigationKeys())
		for child in children:
			if child.rel.startswith(ODATA_RELATED):
				pName=child.rel[len(ODATA_RELATED):]
				links[pName]=(child.href,child.type)
		self.assertTrue(links['Customer'][0]=="Orders(1)/Customer","Customer link")
		#	[the atom:type attribute] should have a value of
		#	"application/atom+xml;type=entry" when the
		#	NavigationProperty identifies a single entity instance
		self.assertTrue(links['Customer'][1]=="application/atom+xml;type=entry","Customer link type")
		self.assertTrue(links['OrderLine'][0]=="Orders(1)/OrderLine","OrderLine link")
		self.assertTrue(links['OrderLine'][1]=="application/atom+xml;type=entry","OrderLine link type")
		#
		#	End of order tests
		#
		employees=ds['SampleModel.SampleEntities.Employees']
		employee=Entity(employees)
		employee['EmployeeID'].SetFromValue('12345')
		employee['EmployeeName'].SetFromValue('Joe Bloggs')
		employee['Address']['City'].SetFromValue('Chunton')
		employee.exists=True
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
		employee['EmployeeName'].SetFromValue(None)
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
		document['DocumentID'].SetFromValue(1801)
		document['Title'].SetFromValue('War and Peace')
		document['Author'].SetFromValue('Tolstoy')
		h=hashlib.sha256()
		h.update("Well, Prince, so Genoa and Lucca are now just family estates of the Buonapartes")
		document['Version'].SetFromValue(h.digest())
		document.exists=True
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
				self.assertTrue(child.href=="Documents(1801)/$value","edit-media link")
				self.assertTrue(child.GetAttribute((ODATA_METADATA_NAMESPACE,"etag"))=="W/\"X'%s'\""%h.hexdigest().upper())
			if child.rel=="edit":
				#	[the edit link] MUST have an atom:href attribute
				#	whose value is a URI that identifies the entity
				self.assertTrue(child.href=="Documents(1801)","edit link")
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
		
	def testCaseEntityTypeAsJSON(self):
		doc=self.LoadMetadata()
		ds=doc.root.DataServices
		customers=ds['SampleModel.SampleEntities.Customers']
		customer=Entity(customers)
		customer['CustomerID'].SetFromValue('X')
		customer['CompanyName'].SetFromValue('Megacorp')
		customer['Address']['City'].SetFromValue('Chunton')
		customer.exists=True
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
		self.assertTrue(obj["Orders"]["__deferred"]["uri"]=="Customers('X')/Orders")
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
		self.assertTrue(meta["uri"]=="Customers('X')","uri in metadata")
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
		# Fake lack of existence
		customer.exists=False
		customer['Orders'].BindEntity(1)
		customer['Orders'].BindEntity(2)
		jsonData=string.join(customer.GenerateEntityTypeInJSON())
		obj=json.loads(jsonData)
		self.assertTrue(type(obj['Orders'])==ListType,"JSON array")
		self.assertTrue(len(obj['Orders'])==2,"Two bindings")
		links=set()
		for link in obj['Orders']:
			self.assertTrue(type(link)==DictType,"Each link is an object")
			links.add(link['__metadata']['uri'])
		self.assertTrue("Orders(1)" in links,"Orders(1)")
		self.assertTrue("Orders(2)" in links,"Orders(2)")
		customer.exists=True
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
		container=memds.InMemoryEntityContainer(ds['SampleModel.SampleEntities'])
		documents=container.entityStorage['Documents']
		docText="Well, Prince, so Genoa and Lucca are now just family estates of the Buonapartes"
		h=hashlib.sha256()
		h.update(docText)
		etag="W/\"X'%s'\""%h.hexdigest().upper()
		documents.data[1801]=(1801,'War and Peace','Tolstoy',h.digest())
		document=documentSet.OpenCollection()[1801]
		document.SetStreamFromGenerator('text/plain',[docText])
		jsonData=string.join(document.GenerateEntityTypeInJSON())
		obj=json.loads(jsonData)
		meta=obj["__metadata"]
		self.assertTrue(meta["etag"]==etag,"document etag: %s"%meta["etag"])
		#	The "media_src" and "content_type" name/value pairs MUST be
		#	included and the "edit_media" and "media_etag" name/value
		#	pairs can be included if the entity being represented is a
		#	Media Link Entry
		self.assertTrue(meta["media_src"]=="Documents(1801)/$value","media src link")
		self.assertTrue(meta["content_type"]=="text/plain","document content type")
		self.assertTrue(meta["edit_media"]=="Documents(1801)/$value","edit-media link")
		self.assertTrue(meta["media_etag"]==etag,"document etag")
		
	def testCaseEntityTypeFromJSON(self):
		doc=self.LoadMetadata()
		ds=doc.root.DataServices
		customers=ds['SampleModel.SampleEntities.Customers']
		customer=Entity(customers)
		customer['CustomerID'].SetFromValue('X')
		customer['CompanyName'].SetFromValue('Megacorp')
		jsonData=string.join(customer.GenerateEntityTypeInJSON())
		obj=json.loads(jsonData)
		newCustomer=Entity(customers)
		newCustomer.SetFromJSONObject(obj)
		self.assertTrue(newCustomer['CustomerID'].value=="X","Check customer ID")
		self.assertTrue(newCustomer['CompanyName'].value=="Megacorp","Check customer name")
		self.assertFalse(newCustomer['Address']['Street'],"No street")
		self.assertFalse(newCustomer['Address']['City'],"No city")
		self.assertFalse(newCustomer['Version'],"No version")
		employees=ds['SampleModel.SampleEntities.Employees']
		employee=Entity(employees)
		employee['EmployeeID'].SetFromValue('12345')
		employee['EmployeeName'].SetFromValue('Joe Bloggs')
		employee['Address']['City'].SetFromValue('Chunton')
		jsonData=string.join(employee.GenerateEntityTypeInJSON())
		obj=json.loads(jsonData)
		newEmployee=Entity(employees)
		newEmployee.SetFromJSONObject(obj)
		self.assertTrue(newEmployee['EmployeeID'].value=="12345","Check employee ID")
		self.assertTrue(newEmployee['EmployeeName'].value=="Joe Bloggs","Check employee name")
		self.assertFalse(newEmployee['Address']['Street'],"No street")
		self.assertTrue(newEmployee['Address']['City']=="Chunton","Check employee city")
		self.assertFalse(newEmployee['Version'],"No version")
		documentSet=ds['SampleModel.SampleEntities.Documents']
		container=memds.InMemoryEntityContainer(ds['SampleModel.SampleEntities'])
		documents=container.entityStorage['Documents']
		docText="Well, Prince, so Genoa and Lucca are now just family estates of the Buonapartes"
		h=hashlib.sha256()
		h.update(docText)
		documents.data[1801]=(1801,'War and Peace','Tolstoy',h.digest())
		document=documentSet.OpenCollection()[1801]
		document.SetStreamFromGenerator('text/plain',[docText])
		jsonData=string.join(document.GenerateEntityTypeInJSON())
		obj=json.loads(jsonData)
		newDocument=Entity(documentSet)
		newDocument.SetFromJSONObject(obj)
		self.assertTrue(newDocument['DocumentID'].value==1801,"Check document ID")
		self.assertTrue(newDocument['Title'].value=="War and Peace","Check document name")
		self.assertTrue(newDocument['Author']=="Tolstoy","Check author name")
		self.assertTrue(newDocument['Version'].value==h.digest(),"Mismatched version")

	def testCaseEntitySetAsAtomFeed(self):
		doc=self.LoadMetadata()
		ds=doc.root.DataServices
		container=memds.InMemoryEntityContainer(ds['SampleModel.SampleEntities'])
		customersSet=ds['SampleModel.SampleEntities.Customers']
		customers=container.entityStorage['Customers']
		orders=container.entityStorage['Orders']
		association=container.associationStorage['Orders_Customers']
		customers.data['ALFKI']=('ALFKI','Example Inc',("Mill Road","Chunton"),None)
		for i in xrange(3):
			customers.data['XXX%02X'%i]=('XXX%02X'%i,'Example-%i Ltd'%i,(None,None),None)
		feed=Feed(None,customersSet.OpenCollection())
		#	The <atom:id> element MUST contain the URI that identifies the EntitySet
		self.assertTrue(feed.AtomId.GetValue()=="Customers")
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
				self.assertTrue(child.href=="Customers","self link")
		self.assertTrue("self" in links,"Missing self link")
		self.assertTrue(len(feed.Entry)==0,"Feed uses generator instead of static array of entries")
		nEntries=0
		for child in feed.GetChildren():
			if isinstance(child,atom.Entry):
				nEntries+=1
		self.assertTrue(nEntries==4,"4 entries generated by the feed")		
		page=customersSet.OpenCollection()
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
		customer=customersSet.OpenCollection()['ALFKI']
		feed=Feed(None,customer['Orders'].OpenCollection())
		#	If the URI in the sibling <atom:id> element is of the same
		#	form as URI 6 and the NavigationProperty identifies an
		#	EntitySet, then the <atom:title> element can contain the
		#	name of the NavigationProperty instead of the name of the
		#	EntitySet identified by the property
		self.assertTrue(feed.AtomId.GetValue()=="Customers('ALFKI')/Orders")
		self.assertTrue(feed.Title.GetValue()=="Orders")

	def testCaseEntitySetAsJSON(self):
		doc=self.LoadMetadata()
		ds=doc.root.DataServices
		container=memds.InMemoryEntityContainer(ds['SampleModel.SampleEntities'])
		customersSet=ds['SampleModel.SampleEntities.Customers']
		customers=container.entityStorage['Customers']
		orders=container.entityStorage['Orders']
		association=container.associationStorage['Orders_Customers']
		customers.data['ALFKI']=('ALFKI','Example Inc',("Mill Road","Chunton"),None)
		for i in xrange(3):
			customers.data['XXX%02X'%i]=('XXX%02X'%i,'Example-%i Ltd'%i,(None,None),None)
		collection=customersSet.OpenCollection()
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
		emptyCollection=collection['ALFKI']["Orders"].OpenCollection()
		jsonData=string.join(emptyCollection.GenerateEntitySetInJSON(),'')
		obj=json.loads(jsonData)
		self.assertTrue(type(obj["results"])==ListType,"Empty EntitySet represented as JSON array")
		self.assertTrue(len(obj["results"])==0,"No entities")
		

class CustomersByCityEntityCollection(FunctionEntityCollection):
	
	def __init__(self,function,params,customers):
		FunctionEntityCollection.__init__(self,function,params)
		self.customers=customers
		self.collection=self.entitySet.OpenCollection()
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
			self.date=iso8601.TimePoint.FromNow()
		self.collection=customersEntitySet.OpenCollection()
		
	def __iter__(self):
		for customer in self.collection.itervalues():
			yield customer['Address']


class ShippedCustomerNamesByDateCollection(FunctionCollection):
	
	def __init__(self,function,params,customersEntitySet):
		edm.FunctionCollection.__init__(self,function,params)
		self.date=params.get('date',None)
		if self.date is None:
			self.date=iso8601.TimePoint.FromNow()
		self.collection=customersEntitySet.OpenCollection()
		
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
		self.container=memds.InMemoryEntityContainer(self.ds['SampleModel.SampleEntities'])
		customers=self.container.entityStorage['Customers']
		customers.data['ALFKI']=('ALFKI','Example Inc',("Mill Road","Chunton"),'\x00\x00\x00\x00\x00\x00\xfa\x01')
		for i in xrange(90):
			customers.data['XXX%02X'%i]=('XXX%02X'%i,'Example-%i Ltd'%i,(None,None),None)
		employees=self.container.entityStorage['Employees']
		employees.data['1']=('1','Joe Bloggs',("The Elms","Chunton"),'DEADBEEF')
		orders=self.container.entityStorage['Orders']
		now=iso8601.TimePoint.FromNow()
		orders.data[1]=(1,iso8601.TimePoint.FromString('2013-08-01T11:05:00'))
		orders.data[2]=(2,iso8601.TimePoint.FromString('2013-08-13T10:26:00'))
		orders.data[3]=(3,iso8601.TimePoint.FromString('2012-05-29T18:13:00'))
		orders.data[4]=(4,iso8601.TimePoint.FromString('2012-05-29T18:13:00'))
		orderLines=self.container.entityStorage['OrderLines']
		orderLines.data[100]=(100,12,decimal.Decimal('0.45'))
		orderLines.data[200]=(200,144,decimal.Decimal('2.50'))
		with orders.entitySet.OpenCollection() as collOrders:
			order=collOrders[1]
			order['Customer'].BindEntity('ALFKI')
			order['OrderLine'].BindEntity(100)
			collOrders.UpdateEntity(order)
			order=collOrders[2]
			order['Customer'].BindEntity('ALFKI')
			order['OrderLine'].BindEntity(200)
			collOrders.UpdateEntity(order)
			order=collOrders[3]
			order['Customer'].BindEntity('XXX00')
			collOrders.UpdateEntity(order)
		documents=self.container.entityStorage['Documents']
		documents.data[300]=(300,'The Book','The Author',None)
		documents.data[301]=(301,'A Book','An Author',None)
		with memds.EntityCollection(entitySet=documents.entitySet,entityStore=documents) as collection:
			doc=collection[301]
			doc.SetStreamFromGenerator(http.MediaType.FromString("text/plain; charset=iso-8859-1"),["An opening line written in a Caf\xe9"])
		self.xContainer=memds.InMemoryEntityContainer(self.ds['SampleModel.ExtraEntities'])
		bitsAndPieces=self.xContainer.entityStorage['BitsAndPieces']
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
		with self.ds['SampleModel.SampleEntities.Customers'].OpenCollection() as customers:
			return customers['ALFKI']
				
	def LastShippedByLine(self,function,params):
		with self.ds['SampleModel.SampleEntities.Customers'].OpenCollection() as customers:
			return customers['ALFKI']['Address']
				
	def LastCustomerNameByLine(self,function,params):
		with self.ds['SampleModel.SampleEntities.Customers'].OpenCollection() as customers:
			return customers['ALFKI']['CompanyName']
				
	def tearDown(self):
		pass
	
	def testCaseEntityTypeFromAtomEntry(self):
		customers=self.ds['SampleModel.SampleEntities.Customers']
		customer=Entity(customers)
		customer['CustomerID'].SetFromValue('X')
		customer['CompanyName'].SetFromValue('Megacorp')
		customer.exists=True
		entry=Entry(None,customer)
		self.assertTrue(entry.entityType==None,"Ensure there is no relation to the model here")
		newCustomer=Entity(customers)
		newCustomer.exists=True
		entry.GetValue(newCustomer)
		self.assertTrue(newCustomer['CustomerID'].value=="X","Check customer ID")
		self.assertTrue(newCustomer['CompanyName'].value=="Megacorp","Check customer name")
		self.assertFalse(newCustomer['Address']['Street'],"No street")
		self.assertFalse(newCustomer['Address']['City'],"No city")
		self.assertFalse(newCustomer['Version'],"No version")
		self.assertTrue(len(newCustomer['Orders'].bindings)==0,"new customer not bound")
		customer.exists=False
		customer['Orders'].BindEntity(1)
		customer['Orders'].BindEntity(2)
		order=Entity(self.ds['SampleModel.SampleEntities.Orders'])
		order['OrderID'].SetFromValue(3)
		customer['Orders'].BindEntity(order)
		entry=Entry(None,customer)
		newCustomer=Entity(customers)
		newCustomer.exists=False
		entry.GetValue(newCustomer,lambda x:self.svc.GetResourceFromURI(x))
		# now we need to check the bindings, which is a little hard to do without looking inside the box
		self.assertTrue(len(newCustomer['Orders'].bindings)==3,"new customer has 3 orders bound")
		idLinks=set()
		entityLink=None
		for binding in newCustomer['Orders'].bindings:
			if isinstance(binding,Entity):
				if binding.exists:
					idLinks.add(binding.Key())
				else:
					entityLink=binding
			else:
				idLinks.add(binding)
		self.assertTrue(1 in idLinks,"OrderID=1 is bound")
		self.assertTrue(2 in idLinks,"OrderID=2 is bound")
		self.assertTrue(entityLink['OrderID']==3,"OrderID 3 loaded")
		self.assertFalse(entityLink.exists,"OrderID 3 does not exist")
		#
		# End of customer tests
		#
		employees=self.ds['SampleModel.SampleEntities.Employees']
		employee=Entity(employees)
		employee['EmployeeID'].SetFromValue('12345')
		employee['EmployeeName'].SetFromValue('Joe Bloggs')
		employee['Address']['City'].SetFromValue('Chunton')
		entry=Entry(None,employee)
		self.assertTrue(entry.entityType==None,"Ensure there is no relation to the model here")
		newEmployee=entry.GetValue(Entity(employees))
		self.assertTrue(newEmployee['EmployeeID'].value=="12345","Check employee ID")
		self.assertTrue(newEmployee['EmployeeName'].value=="Joe Bloggs","Check employee name")
		self.assertFalse(newEmployee['Address']['Street'],"No street")
		self.assertTrue(newEmployee['Address']['City']=="Chunton","Check employee city")
		self.assertFalse(newEmployee['Version'],"No version")
		documents=self.ds['SampleModel.SampleEntities.Documents']
		document=Entity(documents)
		document['DocumentID'].SetFromValue(1801)
		document['Title'].SetFromValue('War and Peace')
		document['Author'].SetFromValue('Tolstoy')
		h=hashlib.sha256()
		h.update("Well, Prince, so Genoa and Lucca are now just family estates of the Buonapartes")
		document['Version'].SetFromValue(h.digest())
		entry=Entry(None,document)
		self.assertTrue(entry.entityType==None,"Ensure there is no relation to the model here")
		newDocument=entry.GetValue(Entity(documents))
		self.assertTrue(newDocument['DocumentID'].value==1801,"Check document ID")
		self.assertTrue(newDocument['Title'].value=="War and Peace","Check document name")
		self.assertTrue(newDocument['Author']=="Tolstoy","Check author name")
		self.assertTrue(newDocument['Version'].value==h.digest(),"Mismatched version")

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
		order=orders.OpenCollection()[1]
		# Simple Property
		p=Parser("OrderID")
		e=p.ParseCommonExpression()
		value=e.Evaluate(order)
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.value==1,"Expected 1")		
		customers=self.ds['SampleModel.SampleEntities.Customers']
		# customers.data['ALFKI']=('ALFKI','Example Inc',("Mill Road","Chunton"),None)
		customer=customers.OpenCollection()['ALFKI']
		# Complex Property
		p=Parser("Address")
		e=p.ParseCommonExpression()
		value=e.Evaluate(customer)
		self.assertTrue(isinstance(value,edm.Complex),"Expected Complex value")
		self.assertTrue(value['City'].value=='Chunton',"Expected Chunton")		
		# Simple Property (NULL)
		customer00=customers.OpenCollection()['XXX00']
		p=Parser("Version")
		e=p.ParseCommonExpression()
		value=e.Evaluate(customer00)
		self.assertTrue(value.typeCode==edm.SimpleType.Binary,"Expected Binary")
		self.assertTrue(value.value is None,"Expected NULL")		
		# Navigation property
		p=Parser("Customer")
		e=p.ParseCommonExpression()
		value=e.Evaluate(order)
		self.assertTrue(isinstance(value,edm.Entity),"Expected Entity")
		self.assertTrue(value['CustomerID'].value=='ALFKI',"Expected Customer('ALFKI')")
		# Navigation property with Null
		value=e.Evaluate(orders.OpenCollection()[4])
		self.assertTrue(isinstance(value,edm.SimpleValue),"Expected SimpleValue (for NULL) found %s"%repr(value))
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
		order=orders.OpenCollection()[1]
		order3=orders.OpenCollection()[3]
		# Known Entity: SimpleProperty
		p=Parser("Customer/CustomerID")
		e=p.ParseCommonExpression()
		value=e.Evaluate(order)
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected string")
		self.assertTrue(value.value=='ALFKI',"Expected 'ALKFI'")		
		# Known ComplexType: SimpleProperty
		p=Parser("Customer/Address/City")
		e=p.ParseCommonExpression()
		value=e.Evaluate(order)
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected string")
		self.assertTrue(value.value=='Chunton',"Expected 'Chunton'")		
		# TODO: a two step navigation, sample data doesn't have one yet
		#	navigation / navigation 
		# Simple Property (NULL)
		p=Parser("Customer/Version")
		e=p.ParseCommonExpression()
		value=e.Evaluate(order3)
		self.assertTrue(value.typeCode==edm.SimpleType.Binary,"Expected Binary")
		self.assertTrue(value.value is None,"Expected NULL")		
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
		order=orders.OpenCollection()[1]
		# Known Entity: SimpleProperty
		p=Parser("Customer eq Customer")
		e=p.ParseCommonExpression()
		value=e.Evaluate(order)
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected boolean")
		self.assertTrue(value.value==True,"Expected True")		
		p=Parser("Customer eq OrderLine")
		e=p.ParseCommonExpression()
		value=e.Evaluate(order)
		self.assertTrue(value.value==False,"Expected False")		
			
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
		self.assertTrue(request.responseHeaders['LOCATION']=='http://host/service.svc/',"Expected redirect")
		request=MockRequest('/service.svc/')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200,"Service root response: %i"%request.responseCode)		
		self.assertTrue(request.responseHeaders['CONTENT-TYPE']=='application/atomsvc+xml',"Expected application/atomsvc+xml")
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
		self.assertTrue(request.responseHeaders['CONTENT-TYPE']=='application/json',"Expected application/json")
		obj=json.loads(request.wfile.getvalue())
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
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
	
	def testCaseEntityProperty(self):
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
		self.assertTrue(value.value=='Mill Road',"Bad street")
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
		self.assertTrue(value.value=='Example Inc',"Bad company")
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
		self.assertTrue(request.responseHeaders['CONTENT-TYPE']=="application/x-details")
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
#		baseURI="/service.svc/Customers('ALFKI')/Orders?$expand=Orders&$filter=substringof(CompanyName,%20'bikes')&$format=xml&$select=CustomerID,CompanyName,Orders"
#		request=MockRequest(baseURI)
#		request.Send(self.svc)
#		self.assertTrue(request.responseCode==200)
#		for x in ["$orderby=CompanyName%20asc",
#			"$skip=3","$top=2","$skiptoken='Contoso','AKFNU'","$inlinecount=allpages"]:
#			request=MockRequest(baseURI+"&"+x)
#			request.Send(self.svc)
#			self.assertTrue(request.responseCode==400,"UR6 with %s"%x)
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
		self.assertTrue(request.responseHeaders['CONTENT-TYPE']=="application/json")
		obj=json.loads(request.wfile.getvalue())
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
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
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
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
		mType=http.MediaType.FromString(pType.GetAttribute(MimeType))
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
		self.assertTrue(request.responseHeaders['CONTENT-TYPE']=="application/json")
		obj=json.loads(request.wfile.getvalue())
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
		#	should be version 2 output
		self.assertTrue("results" in obj,"Expected version 2 JSON output")
		i=0
		fakeP=edm.Property(None)
		fakeP.complexType=self.ds['SampleModel.CAddress']
		for ct in obj["results"]:
			#	should be a complex type
			c=edm.Complex(fakeP)
			ReadEntityCTInJSON(c,obj)
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
		self.assertTrue(request.responseHeaders['CONTENT-TYPE']=="application/json")
		obj=json.loads(request.wfile.getvalue())
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
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
		self.assertTrue(request.responseHeaders['CONTENT-TYPE']=="application/json")
		obj=json.loads(request.wfile.getvalue())
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
		#	should be version 2 output
		self.assertTrue("results" in obj,"Expected version 2 JSON output")
		i=0
		for prim in obj["results"]:
			#	should be a simple type
			v=edm.StringValue()
			ReadEntityPropertyValueInJSON(v,prim)
			i=i+1
		#	check version 1 json output
		request=MockRequest("/service.svc/ShippedCustomerNamesByDate?date=datetime'2013-08-02'")
		request.SetHeader('Accept',"application/json")
		request.SetHeader('MaxDataServiceVersion',"1.0; old max")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['CONTENT-TYPE']=="application/json")
		obj=json.loads(request.wfile.getvalue())
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
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
			linkURI,linkInline=None,None
			for link in e.FindChildrenDepthFirst(Link):
				if link.title=="Orders":
					linkURI=link.href
					linkInline=link.Inline
					if linkInline is not None:
						linkInline=linkInline.Entry if linkInline.Feed is None else linkInline.Feed
			if e['CustomerID'].value=='ALFKI':
				#	A NavigationProperty that represents an EntityType
				#	instance or a group of entities and that is
				#	serialized inline MUST be placed within a single
				#	<m:inline> element that is a child element of the
				#	<atom:link> element.
				self.assertTrue(isinstance(linkInline,atom.Feed),"Expected atom.Feed in Orders link")
				self.assertTrue(len(linkInline.Entry)==2,"Expected 2 Orders in expand")
			elif e['CustomerID'].value!='XXX00':
				self.assertTrue(linkInline is None,"Expected no inline content for Orders link")
		#	Test json format
		request=MockRequest("/service.svc/Customers?$expand=Orders")
		request.SetHeader('Accept',"application/json")
		request.Send(self.svc)
		obj=json.loads(request.wfile.getvalue())
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
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
			elif objItem["CustomerID"]!='XXX00':
				self.assertTrue(len(orders["results"])==0,"Expected no inline content for Orders link")							
		request=MockRequest("/service.svc/Orders(1)?$expand=Customer")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,atom.Entry),"Expected atom.Entry from /Orders(1)?$expand=Customer")
		linkURI,linkInline=None,None
		for link in doc.root.FindChildrenDepthFirst(Link):
			if link.title=="Customer":
				linkURI=link.href
				linkInline=link.Inline
				if linkInline is not None:
					linkInline=linkInline.Entry if linkInline.Feed is None else linkInline.Feed
		self.assertTrue(isinstance(linkInline,atom.Entry),"Expected atom.Entry in Customer link")
		#	Test json format
		request=MockRequest("/service.svc/Orders(1)?$expand=Customer")
		request.SetHeader('Accept',"application/json")
		request.Send(self.svc)
		obj=json.loads(request.wfile.getvalue())
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
		#	If the NavigationProperty identifies a single EntityType
		#	instance, the value MUST be a JSON object representation of
		#	that EntityType instance, as specified in Entity Type (as a
		#	JSON object)
		customer=obj["Customer"]
		self.assertTrue(type(customer)==DictType,"Single object result")
		self.assertTrue(customer["CustomerID"]=='ALFKI',"Matching customer")
		request=MockRequest("/service.svc/Orders(4)?$expand=Customer")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,atom.Entry),"Expected atom.Entry from /Orders(4)?$expand=Customer")
		linkURI,linkInline=None,None
		for link in doc.root.FindChildrenDepthFirst(Link):
			if link.title=="Customer":
				linkURI=link.href
				linkInline=link.Inline
				if linkInline is not None:
					linkInline=linkInline.Entry if linkInline.Feed is None else linkInline.Feed
		#	If the value of a NavigationProperty is null, then an empty
		#	<m:inline> element MUST appear under the <atom:link>
		#	element which represents the NavigationProperty
		self.assertTrue(linkInline is None,"Expected empty inline in Customer link")
		#	Test json format
		request=MockRequest("/service.svc/Orders(4)?$expand=Customer")
		request.SetHeader('Accept',"application/json")
		request.Send(self.svc)
		obj=json.loads(request.wfile.getvalue())
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
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
		self.assertTrue(request.responseHeaders['CONTENT-TYPE']=="application/xml")
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,atom.Feed),"Expected atom.Feed from /Orders?$format=xml")
		self.assertTrue(len(doc.root.Entry)==4,"Expected 4 Orders")
		request=MockRequest("/service.svc/Orders?$format=atom")
		request.SetHeader('Accept',"application/xml")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['CONTENT-TYPE']=="application/atom+xml")
		request=MockRequest("/service.svc/Orders(1)?$format=json")
		request.SetHeader('Accept',"application/xml")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['CONTENT-TYPE']=="application/json")
		obj=json.loads(request.wfile.getvalue())
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
		self.assertTrue("OrderID" in obj,"Expected a single entry object")
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
		lastTime=iso8601.TimePoint.FromString("19000101T000000")
		for e in doc.root.Entry:
			# These entries are just that, they aren't entities
			currTime=iso8601.TimePoint.FromString(e['ShippedDate'].value)
			self.assertTrue(currTime>=lastTime,"ShippedDate increasing")
			lastTime=currTime
		request=MockRequest("/service.svc/Orders?$orderby=ShippedDate,OrderID%20desc")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		lastTime=iso8601.TimePoint.FromString("19000101T000000")
		lastID=10000
		failFlag=True
		for e in doc.root.Entry:
			currTime=iso8601.TimePoint.FromString(e['ShippedDate'].value)
			currID=e['OrderID'].value
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
		thirdID=doc.root.Entry[2]['OrderID'].value
		request=MockRequest("/service.svc/Orders?$orderby=ShippedDate&$skip=2")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(len(doc.root.Entry)==2,"Expected 2 Orders")
		self.assertTrue(thirdID==doc.root.Entry[0]['OrderID'].value,"Skipped first 2")
		request=MockRequest("/service.svc/Orders?$skip=0")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		lastID=-1
		for e in doc.root.Entry:
			currID=int(e['OrderID'].value)
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
		firstID=doc.root.Entry[0]['OrderID'].value
		request=MockRequest("/service.svc/Orders?$orderby=ShippedDate&$top=2")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(len(doc.root.Entry)==2,"Expected 2 Orders")
		self.assertTrue(firstID==doc.root.Entry[0]['OrderID'].value,"First one correct")
		request=MockRequest("/service.svc/Orders?$top=4")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		lastID=-1		
		for e in doc.root.Entry:
			currID=int(e['OrderID'].value)
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
		# remove a link before running this test
		with self.ds['SampleModel.SampleEntities.Orders'].OpenCollection() as orders:
			order=orders[3]
			with order['Customer'].OpenCollection() as navCollection:
				del navCollection['XXX00']				
		customers=self.ds['SampleModel.SampleEntities.Customers'].OpenCollection()
		customer=customers.NewEntity()
		customer['CustomerID'].SetFromValue(u'STEVE')
		customer['CompanyName'].SetFromValue("Steve's Inc")
		customer['Address']['City'].SetFromValue('Cambridge')
		#	street left blank
		request=MockRequest("/service.svc/Customers","POST")
		doc=Document(root=Entry(None,customer))
		data=str(doc)
		request.SetHeader('Content-Type',ODATA_RELATED_ENTRY_TYPE)
		request.SetHeader('Content-Length',str(len(data)))
		request.rfile.write(data)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==201)
		# We expect a location header
		self.assertTrue(request.responseHeaders['LOCATION']=="http://host/service.svc/Customers('STEVE')")
		self.assertTrue(request.responseHeaders['CONTENT-TYPE']==http.MediaType.FromString("application/atom+xml"))
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,Entry),"Expected a single Entry, found %s"%doc.root.__class__.__name__)
		newCustomer=Entity(self.ds['SampleModel.SampleEntities.Customers'])
		newCustomer.exists=True
		doc.root.GetValue(newCustomer)
		self.assertTrue(newCustomer['CustomerID'].value==u"STEVE")
		self.assertTrue(newCustomer['CompanyName'].value==u"Steve's Inc")
		self.assertTrue(newCustomer['Address']['City'].value==u"Cambridge")
		self.assertFalse(newCustomer['Address']['Street'])	
		# insert entity with binding
		customer=customers.NewEntity()
		customer['CustomerID'].SetFromValue(u'ASDFG')
		customer['CompanyName'].SetFromValue("Contoso Widgets")
		customer['Address']['Street'].SetFromValue('58 Contoso St')
		customer['Address']['City'].SetFromValue('Seattle')
		customer['Orders'].BindEntity(3)
		customer['Orders'].BindEntity(4)
		request=MockRequest("/service.svc/Customers","POST")
		doc=Document(root=Entry(None,customer))
		data=str(doc)
		request.SetHeader('Content-Type',ODATA_RELATED_ENTRY_TYPE)
		request.SetHeader('Content-Length',str(len(data)))
		request.rfile.write(data)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==201)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		newCustomer=Entity(self.ds['SampleModel.SampleEntities.Customers'])
		newCustomer.exists=True
		doc.root.GetValue(newCustomer)
		self.assertTrue(newCustomer['CustomerID'].value==u"ASDFG")
		self.assertTrue(newCustomer['Address']['Street'].value==u"58 Contoso St")
		request=MockRequest("/service.svc/Customers('ASDFG')/Orders")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,atom.Feed),"Expected atom.Feed from navigation property Orders")
		self.assertTrue(len(doc.root.Entry)==2,"Inserted customer has 2 orders")
		orderKeys=set()
		for entry in doc.root.Entry:
			order=Entity(self.ds['SampleModel.SampleEntities.Orders'])
			order.exists=True
			entry.GetValue(order)
			orderKeys.add(order['OrderID'].value)
		self.assertTrue(3 in orderKeys,"New entity bound to order 3")
		self.assertTrue(4 in orderKeys,"New entity bound to order 4")
		
	def testCaseInsertEntityJSON(self):
		# remove a link before running this test
		with self.ds['SampleModel.SampleEntities.Orders'].OpenCollection() as orders:
			order=orders[3]
			with order['Customer'].OpenCollection() as navCollection:
				del navCollection['XXX00']				
		customers=self.ds['SampleModel.SampleEntities.Customers'].OpenCollection()
		customer=customers.NewEntity()
		customer['CustomerID'].SetFromValue(u'STEVE')
		customer['CompanyName'].SetFromValue("Steve's Inc")
		customer['Address']['City'].SetFromValue('Cambridge')
		#	street left blank
		request=MockRequest("/service.svc/Customers","POST")
		data=string.join(customer.GenerateEntityTypeInJSON(False,1))
		request.SetHeader('Content-Type','application/json')
		request.SetHeader('Content-Length',str(len(data)))
		request.SetHeader('Accept',"application/json")		
		request.rfile.write(data)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==201)
		# We expect a location header
		self.assertTrue(request.responseHeaders['LOCATION']=="http://host/service.svc/Customers('STEVE')")
		self.assertTrue(request.responseHeaders['CONTENT-TYPE']==http.MediaType.FromString('application/json'))
		obj=json.loads(request.wfile.getvalue())		
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
		self.assertTrue(type(obj)==DictType,"Expected a single JSON object, found %s"%repr(type(obj)))
		newCustomer=Entity(self.ds['SampleModel.SampleEntities.Customers'])
		newCustomer.exists=True
		newCustomer.SetFromJSONObject(obj)
		self.assertTrue(newCustomer['CustomerID'].value==u"STEVE")
		self.assertTrue(newCustomer['CompanyName'].value==u"Steve's Inc")
		self.assertTrue(newCustomer['Address']['City'].value==u"Cambridge")
		self.assertFalse(newCustomer['Address']['Street'])	
		# insert entity with binding
		customer=customers.NewEntity()
		customer['CustomerID'].SetFromValue(u'ASDFG')
		customer['CompanyName'].SetFromValue("Contoso Widgets")
		customer['Address']['Street'].SetFromValue('58 Contoso St')
		customer['Address']['City'].SetFromValue('Seattle')
		customer['Orders'].BindEntity(3)
		customer['Orders'].BindEntity(4)
		request=MockRequest("/service.svc/Customers","POST")
		data=string.join(customer.GenerateEntityTypeInJSON(False,1))
		request.SetHeader('Content-Type','application/json')
		request.SetHeader('Content-Length',str(len(data)))
		request.SetHeader('Accept',"application/json")		
		request.rfile.write(data)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==201)
		obj=json.loads(request.wfile.getvalue())
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
		newCustomer=Entity(self.ds['SampleModel.SampleEntities.Customers'])
		newCustomer.exists=True
		newCustomer.SetFromJSONObject(obj)
		self.assertTrue(newCustomer['CustomerID'].value==u"ASDFG")
		self.assertTrue(newCustomer['Address']['Street'].value==u"58 Contoso St")
		request=MockRequest("/service.svc/Customers('ASDFG')/Orders")
		request.SetHeader('Accept',"application/json")		
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		obj=json.loads(request.wfile.getvalue())
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
		self.assertTrue(type(obj['results'])==ListType,"Expected JSON array from navigation property Orders")
		self.assertTrue(len(obj['results'])==2,"Inserted customer has 2 orders")
		orderKeys=set()
		for entry in obj['results']:
			order=Entity(self.ds['SampleModel.SampleEntities.Orders'])
			order.exists=True
			order.SetFromJSONObject(entry)
			orderKeys.add(order['OrderID'].value)
		self.assertTrue(3 in orderKeys,"New entity bound to order 3")
		self.assertTrue(4 in orderKeys,"New entity bound to order 4")

	def testCaseInsertLink(self):
		request=MockRequest("/service.svc/Customers('ALFKI')/$links/Orders","POST")
		doc=Document(root=URI)
		orders=self.ds['SampleModel.SampleEntities.Orders'].OpenCollection()
		order=orders[4]
		doc.root.SetValue(str(order.GetLocation()))
		data=str(doc)
		request.SetHeader('Content-Type','application/xml')
		request.SetHeader('Content-Length',str(len(data)))
		request.rfile.write(data)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==204)
		self.assertTrue(len(request.wfile.getvalue())==0,"empty response body expected")
		request=MockRequest("/service.svc/Customers('ALFKI')/Orders")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(len(doc.root.Entry)==3,"Customer now has 3 orders")
		orderKeys=set()
		for entry in doc.root.Entry:
			order=Entity(self.ds['SampleModel.SampleEntities.Orders'])
			order.exists=True
			entry.GetValue(order)
			orderKeys.add(order['OrderID'].value)
		self.assertTrue(4 in orderKeys,"Customer now bound to order 4")

	def testCaseInsertLinkJSON(self):
		request=MockRequest("/service.svc/Customers('ALFKI')/$links/Orders","POST")
		orders=self.ds['SampleModel.SampleEntities.Orders'].OpenCollection()
		order=orders[4]
		obj={'uri':str(order.GetLocation())}
		data=json.dumps(obj)
		request.SetHeader('Content-Type','application/json')
		request.SetHeader('Content-Length',str(len(data)))
		request.rfile.write(data)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==204)
		self.assertTrue(len(request.wfile.getvalue())==0,"empty response body expected")
		# let's just test the links themselves
		request=MockRequest("/service.svc/Customers('ALFKI')/$links/Orders")
		request.SetHeader('Accept','application/json')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		obj=json.loads(request.wfile.getvalue())
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]
		self.assertTrue(len(obj['results'])==3,"Customer now has 3 orders")
		orderKeys=set()
		for entry in obj['results']:
			orderKeys.add(entry['uri'])
		self.assertTrue('http://host/service.svc/Orders(4)' in orderKeys,"Customer now bound to order 4")
		
	def testCaseInsertMediaResource(self):
		data="Well, Prince, so Genoa and Lucca are now just family estates of the Buonapartes"
		h=hashlib.sha256()
		h.update(data)
		request=MockRequest("/service.svc/Documents","POST")
		request.SetHeader('Content-Type',"text/x-tolstoy")
		request.SetHeader('Content-Length',str(len(data)))
		request.SetHeader('Slug','War and Peace')
		request.rfile.write(data)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==201)
		# We expect a location header
		location=request.responseHeaders['LOCATION']
		self.assertTrue(location.startswith(u"http://host/service.svc/Documents("))
		self.assertTrue(location[len(u"http://host/service.svc/Documents("):-1].isdigit(),"document Id is an integer")
		self.assertTrue(request.responseHeaders['CONTENT-TYPE']==http.MediaType.FromString("application/atom+xml"))
		# Document has a concurrency token so we expect an ETag too
		self.assertTrue("ETAG" in request.responseHeaders)
		self.assertTrue(request.responseHeaders['ETAG']=="W/\"X'%s'\""%h.hexdigest().upper(),"ETag value")
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,Entry),"Expected a single Entry, found %s"%doc.root.__class__.__name__)
		newDocument=Entity(self.ds['SampleModel.SampleEntities.Documents'])
		newDocument.exists=True
		doc.root.GetValue(newDocument)
		# version should match the etag
		self.assertTrue(newDocument['Version'].value==h.digest(),'Version calculation')
		self.assertTrue(newDocument['Title'].value==u"War and Peace","Slug mapped to syndication title") 
		self.assertFalse(newDocument['Author'].value,"Empty string is a pass - we are reading from Atom")
		docID=newDocument['DocumentID'].value
		request=MockRequest("/service.svc/Documents(%i)/$value"%docID)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['CONTENT-TYPE']=="text/x-tolstoy")
		self.assertTrue(request.wfile.getvalue()==data)
		
	def testCaseRetrieveEntitySet(self):
		request=MockRequest('/service.svc/Customers')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/atom+xml")
		# Entity set can't have an ETag
		self.assertFalse("ETAG" in request.responseHeaders,"Entity set ETag") 
		doc=app.Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,atom.Feed),"Expected atom.Feed from /Customers")
		self.assertTrue(len(doc.root.Entry)==91,"Sample server has 91 Customers")
		
	def testCaseRetrieveEntitySetJSON(self):
		request=MockRequest('/service.svc/Customers')
		request.SetHeader('Accept','application/json')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/json")
		self.assertFalse("ETAG" in request.responseHeaders,"Entity set ETag") 
		obj=json.loads(request.wfile.getvalue())		
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
		self.assertTrue(type(obj)==DictType,"Expected a single JSON object, found %s"%repr(type(obj)))
		# by default we expect version 2 format
		self.assertTrue("results" in obj,"Version 2 format response")
		obj=obj["results"]
		self.assertTrue(type(obj)==ListType,"Expected list of entities")
		self.assertTrue(len(obj)==91,"Sample server has 91 Customers")
		# make the same request with version 1
		request=MockRequest('/service.svc/Customers')
		request.SetHeader('DataServiceVersion',"1.0; old request")
		request.SetHeader('Accept','application/json')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/json")
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("1.0;"),"DataServiceVersion 1.0 expected")
		self.assertFalse("ETAG" in request.responseHeaders,"Entity set ETag") 
		obj=json.loads(request.wfile.getvalue())		
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]	
		# should be version 1 response
		self.assertTrue(type(obj)==ListType,"Expected list of entities")
		self.assertTrue(len(obj)==91,"Sample server has 91 Customers")

	def testCaseRetrieveEntity(self):
		request=MockRequest("/service.svc/Customers('ALFKI')")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/atom+xml")
		# Customer does have a version field for optimistic concurrency control
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag") 
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,Entry),"Expected a single Entry, found %s"%doc.root.__class__.__name__)
		self.assertTrue(doc.root['CustomerID']=='ALFKI',"Bad CustomerID")
		
	def testCaseRetrieveEntityJSON(self):
		request=MockRequest("/service.svc/Customers('ALFKI')")
		request.SetHeader('Accept','application/json')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/json")
		# Customer does have a version field for optimistic concurrency control
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag") 
		obj=json.loads(request.wfile.getvalue())		
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
		self.assertTrue(type(obj)==DictType,"Expected a single JSON object, found %s"%repr(type(obj)))
		self.assertTrue("__metadata" in obj,"__metadata in response")
		self.assertTrue("CustomerID" in obj,"CustomerID in response")
		self.assertTrue(obj["CustomerID"]=='ALFKI',"Bad CustomerID")
		request=MockRequest("/service.svc/Customers('ALFKI')")
		request.SetHeader('DataServiceVersion',"1.0; old request")
		request.SetHeader('Accept','application/json')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("1.0;"),"DataServiceVersion 1.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/json")
		# Customer does have a version field for optimistic concurrency control
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag") 
		obj=json.loads(request.wfile.getvalue())		
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]
		# version 1.0 and 2.0 responses are the same
		self.assertTrue(type(obj)==DictType,"Expected a single JSON object, found %s"%repr(type(obj)))
		self.assertTrue("__metadata" in obj,"__metadata in response")
		self.assertTrue("CustomerID" in obj,"CustomerID in response")
		self.assertTrue(obj["CustomerID"]=='ALFKI',"Bad CustomerID")
	
	def testCaseRetrieveComplexType(self):
		request=MockRequest("/service.svc/Customers('ALFKI')/Address")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/xml")
		# Customer does have a version field for optimistic concurrency control
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag") 
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,Property),"Expected a single Property, found %s"%doc.root.__class__.__name__)
		value=doc.root.GetValue()
		self.assertTrue(value['Street']=='Mill Road',"Bad street in address")
		
	def testCaseRetrieveComplexTypeJSON(self):
		request=MockRequest("/service.svc/Customers('ALFKI')/Address")
		request.SetHeader('Accept','application/json')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/json")
		# Customer does have a version field for optimistic concurrency control
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag") 
		obj=json.loads(request.wfile.getvalue())		
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
		self.assertTrue(type(obj)==DictType,"Expected a single JSON object, found %s"%repr(type(obj)))
		self.assertTrue("results" in obj,"results in response")
		obj=obj["results"]
		self.assertTrue("Address" in obj,"Expected named object 'Address' in response")
		obj=obj["Address"]
		self.assertTrue(obj["Street"]=='Mill Road',"Bad street in address")
		request=MockRequest("/service.svc/Customers('ALFKI')/Address")
		request.SetHeader('DataServiceVersion',"1.0; old request")
		request.SetHeader('Accept','application/json')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("1.0;"),"DataServiceVersion 1.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/json")
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag") 
		obj=json.loads(request.wfile.getvalue())		
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
		self.assertTrue(type(obj)==DictType,"Expected a single JSON object, found %s"%repr(type(obj)))
		self.assertTrue("Address" in obj,"Expected named object 'Address' in response")
		obj=obj["Address"]
		self.assertTrue(obj["Street"]=='Mill Road',"Bad street in address")
				
	def testCaseRetrievePrimitiveProperty(self):
		request=MockRequest("/service.svc/Customers('ALFKI')/CompanyName")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/xml")
		# Customer does have a version field for optimistic concurrency control
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag") 
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,Property),"Expected a single Property, found %s"%doc.root.__class__.__name__)
		value=doc.root.GetValue()
		self.assertTrue(value.value=='Example Inc',"Bad company")

	def testCaseRetrievePrimitivePropertyJSON(self):
		request=MockRequest("/service.svc/Customers('ALFKI')/CompanyName")
		request.SetHeader('Accept','application/json')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/json")
		# Customer does have a version field for optimistic concurrency control
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag") 
		obj=json.loads(request.wfile.getvalue())		
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
		self.assertTrue(type(obj)==DictType,"Expected a single JSON object, found %s"%repr(type(obj)))
		self.assertTrue("results" in obj,"results in response")
		obj=obj["results"]
		self.assertTrue("CompanyName" in obj,"Expected named object 'CompanyName' in response")
		self.assertTrue(obj["CompanyName"]=='Example Inc',"Bad company")
		request=MockRequest("/service.svc/Customers('ALFKI')/CompanyName")
		request.SetHeader('DataServiceVersion',"1.0; old request")
		request.SetHeader('Accept','application/json')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("1.0;"),"DataServiceVersion 1.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/json")
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag") 
		obj=json.loads(request.wfile.getvalue())		
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
		self.assertTrue(type(obj)==DictType,"Expected a single JSON object, found %s"%repr(type(obj)))
		self.assertTrue("CompanyName" in obj,"Expected named object 'CompanyName' in response")
		self.assertTrue(obj["CompanyName"]=='Example Inc',"Bad company")

	def testCaseRetrieveValue(self):
		request=MockRequest("/service.svc/Customers('ALFKI')/CompanyName/$value")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(http.MediaRange.FromString("text/plain").MatchMediaType(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])))
		# Customer does have a version field for optimistic concurrency control
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag")
		self.assertTrue(request.wfile.getvalue()=='Example Inc',"Bad company")
		# check media type customisation
		request=MockRequest("/service.svc/ExtraEntities.BitsAndPieces(1)/Details/$value")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(request.responseHeaders['CONTENT-TYPE']=="application/x-details")
		self.assertTrue(request.wfile.getvalue()=='blahblah',"Bad details $value")
		# check that binary values are received as raw values
		request=MockRequest("/service.svc/Customers('ALFKI')/Version/$value")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/octet-stream")
		# Customer does have a version field for optimistic concurrency control
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag")
		self.assertTrue(request.wfile.getvalue()=='\x00\x00\x00\x00\x00\x00\xfa\x01',"Bad version")
		# check behaviour of null values, this was clarified in the v3 specification
		# A $value request for a property that is NULL SHOULD result in a 404 Not Found. response.
		request=MockRequest("/service.svc/Customers('XXX00')/Version/$value")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==404)
		
	def testCaseRetrieveMetadata(self):
		request=MockRequest("/service.svc/$metadata")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/xml")
		doc=edmx.Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,edmx.Edmx),"Expected Edmx from $metadata request, found %s"%doc.root.__class__.__name__)
		version=doc.Validate()
		#	The version number returned as the value of the
		#	DataServiceVersion response header MUST match the value of
		#	the DataServiceVersion attribute
		ds=doc.root.DataServices
		self.assertTrue(ds.DataServiceVersion()=="2.0","Expected matching data service version")
	
	def testCaseRetrieveServiceDocument(self):
		request=MockRequest("/service.svc/")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/atomsvc+xml")
		doc=app.Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,app.Service),"Expected atom service document, found %s"%doc.root.__class__.__name__)
	
	def testCaseRetrieveServiceDocumentJSON(self):
		request=MockRequest("/service.svc/")
		request.SetHeader('Accept','application/json')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/json")
		obj=json.loads(request.wfile.getvalue())		
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]		
		self.assertTrue(type(obj)==DictType,"Expected a single JSON object, found %s"%repr(type(obj)))
		self.assertTrue("EntitySets" in obj,"EntitySets in service document response")
		self.assertTrue(type(obj['EntitySets'])==ListType,"EntitySets is an array")

	def testCaseRetrieveLink(self):
		request=MockRequest("/service.svc/Customers('ALFKI')/$links/Orders")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/xml")
		self.assertFalse("ETAG" in request.responseHeaders,"Entity set ETag")
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,Links),"Expected Links from $links request, found %s"%doc.root.__class__.__name__)
		self.assertTrue(len(doc.root.URI)==2,"Sample customer has 2 orders")
		request=MockRequest("/service.svc/Orders(1)/$links/Customer")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/xml")
		self.assertFalse("ETAG" in request.responseHeaders,"Entity set ETag")
		doc=Document()
		doc.Read(request.wfile.getvalue())
		self.assertTrue(isinstance(doc.root,URI),"Expected URI from $links request, found %s"%doc.root.__class__.__name__)
		self.assertTrue(doc.root.GetValue()=="http://host/service.svc/Customers('ALFKI')","Bad customer link")

	def testCaseRetrieveLinkJSON(self):
		request=MockRequest("/service.svc/Customers('ALFKI')/$links/Orders")
		request.SetHeader('Accept','application/json')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/json")
		self.assertFalse("ETAG" in request.responseHeaders,"Entity set ETag")
		obj=json.loads(request.wfile.getvalue())		
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]
		self.assertTrue("results" in obj,"results in response")
		obj=obj["results"]
		self.assertTrue(type(obj)==ListType,"Expected json array of links")
		self.assertTrue(len(obj)==2,"Sample customer has 2 orders")
		# version 1 format
		request=MockRequest("/service.svc/Customers('ALFKI')/$links/Orders")
		request.SetHeader('DataServiceVersion',"1.0; old request")
		request.SetHeader('Accept','application/json')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("1.0;"),"DataServiceVersion 1.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/json")
		self.assertFalse("ETAG" in request.responseHeaders,"Entity set ETag")
		obj=json.loads(request.wfile.getvalue())		
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]
		self.assertTrue(type(obj)==ListType,"Expected json array of links")
		self.assertTrue(len(obj)==2,"Sample customer has 2 orders")
		# Now the single link use case: one format for both versions
		request=MockRequest("/service.svc/Orders(1)/$links/Customer")
		request.SetHeader('Accept','application/json')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])=="application/json")
		self.assertFalse("ETAG" in request.responseHeaders,"Entity set ETag")
		obj=json.loads(request.wfile.getvalue())		
		self.assertTrue(type(obj)==DictType and len(obj)==1 and "d" in obj,"JSON object is security wrapped")
		obj=obj["d"]	
		self.assertTrue("uri" in obj,"uri in response")
		self.assertTrue(obj["uri"]=="http://host/service.svc/Customers('ALFKI')","Bad customer link")
			
	def testCaseRetrieveCount(self):
		request=MockRequest('/service.svc/Customers/$count')
		request.Send(self.svc)
		self.assertTrue(request.responseCode==200)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(http.MediaRange.FromString("text/plain").MatchMediaType(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])))
		self.assertFalse("ETAG" in request.responseHeaders,"Count ETag")
		self.assertTrue(request.wfile.getvalue()=="91","Sample server has 91 Customers")

	def testCaseRetrieveMediaResource(self):
		request=MockRequest("/service.svc/Documents(301)/$value")
		request.Send(self.svc)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(http.MediaRange.FromString("text/plain ; charset=iso-8859-1").MatchMediaType(http.MediaType.FromString(request.responseHeaders['CONTENT-TYPE'])))
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag")		
		self.assertTrue(request.responseCode==200)
		self.assertTrue(unicode(request.wfile.getvalue(),"iso-8859-1")==unicode('An opening line written in a Caf\xc3\xa9','utf-8'),"media resource characters")

	def testCaseUpdateEntity(self):
		customers=self.ds['SampleModel.SampleEntities.Customers']
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
		customer['CompanyName'].SetFromValue("Example Inc Updated")
		request=MockRequest("/service.svc/Customers('ALFKI')","PUT")
		doc=Document(root=Entry)
		doc.root.SetValue(customer,True)
		data=str(doc)
		request.SetHeader('Content-Type',ODATA_RELATED_ENTRY_TYPE)
		request.SetHeader('Content-Length',str(len(data)))
		request.rfile.write(data)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==204)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag")		
		self.assertTrue(len(request.wfile.getvalue())==0,"Update must return 0 bytes")
		# now go behind the scenes to check the update really worked!
		customers=self.ds['SampleModel.SampleEntities.Customers']
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
			self.assertTrue(customer['CompanyName']=="Example Inc Updated")
		# Now do a case with an updated link
		orders=self.ds['SampleModel.SampleEntities.Orders']
		with orders.OpenCollection() as collection:
			order=collection[3]
		oldCustomer=order['Customer'].GetEntity()
		self.assertTrue(oldCustomer.Key()=='XXX00',"Previous customer")
		order['Customer'].BindEntity(customer)
		request=MockRequest("/service.svc/Orders(3)","PUT")
		doc=Document(root=Entry)
		doc.root.SetValue(order,True)
		data=str(doc)
		request.SetHeader('Content-Type',ODATA_RELATED_ENTRY_TYPE)
		request.SetHeader('Content-Length',str(len(data)))
		request.rfile.write(data)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==204)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertFalse("ETAG" in request.responseHeaders,"Entity set Orders has no ETag")		
		self.assertTrue(len(request.wfile.getvalue())==0,"Update must return 0 bytes")
		# now go behind the scenes to check the update really worked!
		orders=self.ds['SampleModel.SampleEntities.Orders']
		with orders.OpenCollection() as collection:
			order=collection[3]
		newCustomer=order['Customer'].GetEntity()
		self.assertTrue(newCustomer.Key()=='ALFKI',"Customer updated")

	def testCaseUpdateEntityJSON(self):
		customers=self.ds['SampleModel.SampleEntities.Customers']
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
		customer['CompanyName'].SetFromValue("Example Inc Updated")
		request=MockRequest("/service.svc/Customers('ALFKI')","PUT")
		jsonData=string.join(customer.GenerateEntityTypeInJSON(True))
		request.SetHeader('Accept',"application/json")
		request.SetHeader('Content-Type',"application/json")
		request.SetHeader('Content-Length',str(len(jsonData)))
		request.rfile.write(jsonData)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==204)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag")		
		self.assertTrue(len(request.wfile.getvalue())==0,"Update must return 0 bytes")
		# now go behind the scenes to check the update really worked!
		customers=self.ds['SampleModel.SampleEntities.Customers']
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
			self.assertTrue(customer['CompanyName']=="Example Inc Updated")
		# Now do a case with an updated link
		orders=self.ds['SampleModel.SampleEntities.Orders']
		with orders.OpenCollection() as collection:
			order=collection[3]
		oldCustomer=order['Customer'].GetEntity()
		self.assertTrue(oldCustomer.Key()=='XXX00',"Previous customer")
		order['Customer'].BindEntity(customer)
		request=MockRequest("/service.svc/Orders(3)","PUT")
		jsonData=string.join(order.GenerateEntityTypeInJSON(True))
		request.SetHeader('Accept',"application/json")
		request.SetHeader('Content-Type',"application/json")
		request.SetHeader('Content-Length',str(len(jsonData)))
		request.rfile.write(jsonData.encode('utf-8'))
		request.Send(self.svc)
		self.assertTrue(request.responseCode==204)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertFalse("ETAG" in request.responseHeaders,"Entity set Orders has no ETag")		
		self.assertTrue(len(request.wfile.getvalue())==0,"Update must return 0 bytes")
		# now go behind the scenes to check the update really worked!
		orders=self.ds['SampleModel.SampleEntities.Orders']
		with orders.OpenCollection() as collection:
			order=collection[3]
		newCustomer=order['Customer'].GetEntity()
		self.assertTrue(newCustomer.Key()=='ALFKI',"Customer updated")
		
	def testCaseUpdateComplexType(self):
		customers=self.ds['SampleModel.SampleEntities.Customers']
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
		customer['Address']['Street'].SetFromValue("High Street")
		request=MockRequest("/service.svc/Customers('ALFKI')/Address","PUT")
		doc=Document(root=Property)
		doc.root.SetXMLName((ODATA_DATASERVICES_NAMESPACE,'Address'))
		doc.root.SetValue(customer['Address'])
		data=str(doc)
		request.SetHeader('Content-Type',"application/xml")
		request.SetHeader('Content-Length',str(len(data)))
		request.rfile.write(data)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==204)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag")		
		self.assertTrue(len(request.wfile.getvalue())==0,"Update must return 0 bytes")
		# now go behind the scenes to check the update really worked!
		customers=self.ds['SampleModel.SampleEntities.Customers']
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
			self.assertTrue(customer['Address']['Street'].value=="High Street")

	def testCaseUpdateComplexTypeJSON(self):
		customers=self.ds['SampleModel.SampleEntities.Customers']
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
		customer['Address']['Street'].SetFromValue("High Street")
		request=MockRequest("/service.svc/Customers('ALFKI')/Address","PUT")
		request.SetHeader('Accept',"application/json")
		data=EntityCTInJSON(customer['Address'])
		request.SetHeader('Content-Type',"application/json")
		request.SetHeader('Content-Length',str(len(data)))
		request.rfile.write(str(data))
		request.Send(self.svc)
		self.assertTrue(request.responseCode==204)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag")		
		self.assertTrue(len(request.wfile.getvalue())==0,"Update must return 0 bytes")
		# now go behind the scenes to check the update really worked!
		customers=self.ds['SampleModel.SampleEntities.Customers']
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
			self.assertTrue(customer['Address']['Street'].value=="High Street")

	def testCaseUpdatePrimitiveProperty(self):
		customers=self.ds['SampleModel.SampleEntities.Customers']
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
		customer['CompanyName'].SetFromValue("Example Inc Updated")
		request=MockRequest("/service.svc/Customers('ALFKI')/CompanyName","PUT")
		doc=Document(root=Property)
		doc.root.SetXMLName((ODATA_DATASERVICES_NAMESPACE,'CompanyName'))
		doc.root.SetValue(customer['CompanyName'])
		data=str(doc)
		request.SetHeader('Content-Type',"application/xml")
		request.SetHeader('Content-Length',str(len(data)))
		request.rfile.write(data)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==204)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag")		
		self.assertTrue(len(request.wfile.getvalue())==0,"Update must return 0 bytes")
		# now go behind the scenes to check the update really worked!
		customers=self.ds['SampleModel.SampleEntities.Customers']
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
			self.assertTrue(customer['CompanyName'].value=="Example Inc Updated")

	def testCaseUpdatePrimitivePropertyJSON(self):
		customers=self.ds['SampleModel.SampleEntities.Customers']
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
		customer['CompanyName'].SetFromValue("Example Inc Updated")
		request=MockRequest("/service.svc/Customers('ALFKI')/CompanyName","PUT")
		request.SetHeader('Accept',"application/json")
		data=EntityPropertyInJSON1(customer['CompanyName'])
		request.SetHeader('Content-Type',"application/json")
		request.SetHeader('Content-Length',str(len(data)))
		request.rfile.write(str(data))
		request.Send(self.svc)
		self.assertTrue(request.responseCode==204)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag")		
		self.assertTrue(len(request.wfile.getvalue())==0,"Update must return 0 bytes")
		# now go behind the scenes to check the update really worked!
		customers=self.ds['SampleModel.SampleEntities.Customers']
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
			self.assertTrue(customer['CompanyName'].value=="Example Inc Updated")

	def testCaseUpdateValue(self):
		request=MockRequest("/service.svc/Customers('ALFKI')/CompanyName/$value","PUT")
		data=u"Caf\xe9 Inc".encode("ISO-8859-1")
		request.SetHeader('Content-Type',"text/plain")	# by default we use ISO-8859-1
		request.SetHeader('Content-Length',str(len(data)))
		request.rfile.write(data)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==204)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag")		
		self.assertTrue(len(request.wfile.getvalue())==0,"Update must return 0 bytes")
		# now go behind the scenes to check the update really worked!
		customers=self.ds['SampleModel.SampleEntities.Customers']
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
			self.assertTrue(customer['CompanyName'].value==u"Caf\xe9 Inc")
		# Now use utf-8
		request=MockRequest("/service.svc/Customers('ALFKI')/CompanyName/$value","PUT")
		data=u"Caf\xe9 Incorporated".encode("utf-8")
		request.SetHeader('Content-Type',"text/plain; charset=utf-8")
		request.SetHeader('Content-Length',str(len(data)))
		request.rfile.write(data)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==204)
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
			self.assertTrue(customer['CompanyName'].value==u"Caf\xe9 Incorporated")
	
	def testCaseUpdateLink(self):
		orders=self.ds['SampleModel.SampleEntities.Orders']
		with orders.OpenCollection() as collection:
			order=collection[3]
		oldCustomer=order['Customer'].GetEntity()
		self.assertTrue(oldCustomer.Key()=='XXX00',"Previous customer")
		customers=self.ds['SampleModel.SampleEntities.Customers']
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
		request=MockRequest("/service.svc/Orders(3)/$links/Customer","PUT")
		doc=Document(root=URI)
		doc.root.SetValue(str(customer.GetLocation()))
		data=str(doc)
		request.SetHeader('Content-Type',"application/xml")
		request.SetHeader('Content-Length',str(len(data)))
		request.rfile.write(data)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==204)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertFalse("ETAG" in request.responseHeaders,"ETag not allowed in response")		
		self.assertTrue(len(request.wfile.getvalue())==0,"Update must return 0 bytes")
		# now go behind the scenes to check the update really worked!
		orders=self.ds['SampleModel.SampleEntities.Orders']
		with orders.OpenCollection() as collection:
			order=collection[3]
		newCustomer=order['Customer'].GetEntity()
		self.assertTrue(newCustomer.Key()=='ALFKI',"Customer updated")

	def testCaseUpdateLinkJSON(self):
		orders=self.ds['SampleModel.SampleEntities.Orders']
		with orders.OpenCollection() as collection:
			order=collection[3]
		oldCustomer=order['Customer'].GetEntity()
		self.assertTrue(oldCustomer.Key()=='XXX00',"Previous customer")
		customers=self.ds['SampleModel.SampleEntities.Customers']
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
		request=MockRequest("/service.svc/Orders(3)/$links/Customer","PUT")
		data=str(customer.LinkJSON())
		request.SetHeader('Content-Type',"application/json")
		request.SetHeader('Content-Length',str(len(data)))
		request.rfile.write(data)
		request.Send(self.svc)
		self.assertTrue(request.responseCode==204)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertFalse("ETAG" in request.responseHeaders,"ETag not allowed in response")		
		self.assertTrue(len(request.wfile.getvalue())==0,"Update must return 0 bytes")
		# now go behind the scenes to check the update really worked!
		orders=self.ds['SampleModel.SampleEntities.Orders']
		with orders.OpenCollection() as collection:
			order=collection[3]
		newCustomer=order['Customer'].GetEntity()
		self.assertTrue(newCustomer.Key()=='ALFKI',"Customer updated")
		
	def testCaseUpdateMediaResource(self):
		data="Well, Prince, so Genoa and Lucca are now just family estates of the Buonapartes"
		h=hashlib.sha256()
		h.update(data)
		request=MockRequest("/service.svc/Documents(301)/$value","PUT")
		request.SetHeader('Content-Type',"text/x-tolstoy")
		request.SetHeader('Content-Length',str(len(data)))
		request.rfile.write(data)	
		request.Send(self.svc)
		self.assertTrue(request.responseCode==204)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue("ETAG" in request.responseHeaders,"Entity set ETag")		
		self.assertTrue(request.responseHeaders['ETAG']=="W/\"X'%s'\""%h.hexdigest().upper(),"ETag value")
		self.assertTrue(len(request.wfile.getvalue())==0,"Update must return 0 bytes")
		documents=self.ds['SampleModel.SampleEntities.Documents']
		with documents.OpenCollection() as collection:
			document=collection[301]
		# version should match the etag
		self.assertTrue(document['Version'].value==h.digest(),'Version calculation')
		self.assertTrue(document.GetStreamType()=="text/x-tolstoy")
		self.assertTrue(document.GetStreamSize()==len(data))
		self.assertTrue(string.join(document.GetStreamGenerator(),'')==data)

	def testCaseDeleteEntity(self):
		request=MockRequest("/service.svc/Customers('ALFKI')","DELETE")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==204)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertFalse("ETAG" in request.responseHeaders,"ETag not allowed in response")		
		self.assertTrue(len(request.wfile.getvalue())==0,"Update must return 0 bytes")
		# now go behind the scenes to check the delete really worked!
		orders=self.ds['SampleModel.SampleEntities.Orders']
		with orders.OpenCollection() as collection:
			order=collection[1]
			self.assertTrue(order['Customer'].GetEntity() is None,"order no longer linked to customer")
		customers=self.ds['SampleModel.SampleEntities.Customers']
		with customers.OpenCollection() as collection:
			for customer in collection.itervalues():
				self.assertFalse(customer['CustomerID'].value=='ALFKI',"Customer no longer exists")
	
	def testCaseDeleteLink1(self):
		request=MockRequest("/service.svc/Customers('ALFKI')/$links/Orders(1)","DELETE")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==204)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertFalse("ETAG" in request.responseHeaders,"ETag not allowed in response")		
		self.assertTrue(len(request.wfile.getvalue())==0,"Update must return 0 bytes")
		# now go behind the scenes to check the delete really worked!
		orders=self.ds['SampleModel.SampleEntities.Orders']
		with orders.OpenCollection() as collection:
			order=collection[1]
			self.assertTrue(order['Customer'].GetEntity() is None,"order no longer linked to customer")
		customers=self.ds['SampleModel.SampleEntities.Customers']
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
			with customer['Orders'].OpenCollection() as orders:
				self.assertTrue(len(orders)==1)
				for order in orders.itervalues():
					self.assertFalse(order['OrderID'].value==1,"Order(1) not linked")
		
	def testCaseDeleteLink2(self):
		request=MockRequest("/service.svc/Orders(1)/$links/Customer","DELETE")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==204)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertFalse("ETAG" in request.responseHeaders,"ETag not allowed in response")		
		self.assertTrue(len(request.wfile.getvalue())==0,"Update must return 0 bytes")
		# now go behind the scenes to check the delete really worked!
		orders=self.ds['SampleModel.SampleEntities.Orders']
		with orders.OpenCollection() as collection:
			order=collection[1]
			self.assertTrue(order['Customer'].GetEntity() is None,"order no longer linked to customer")
		customers=self.ds['SampleModel.SampleEntities.Customers']
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
			with customer['Orders'].OpenCollection() as orders:
				self.assertTrue(len(orders)==1)
				for order in orders.itervalues():
					self.assertFalse(order['OrderID'].value==1,"Order(1) not linked")
		
	def testCaseDeleteValue(self):
		request=MockRequest("/service.svc/Customers('ALFKI')/Address/Street","DELETE")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==204)
		self.assertTrue(request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),"DataServiceVersion 2.0 expected")
		self.assertTrue(len(request.wfile.getvalue())==0,"Update must return 0 bytes")
		# now go behind the scenes to check the delete really worked!
		customers=self.ds['SampleModel.SampleEntities.Customers']
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
			self.assertFalse(customer['Address']['Street'])
		# now try and delete a non-nullable value
		request=MockRequest("/service.svc/Customers('ALFKI')/CompanyName","DELETE")
		request.Send(self.svc)
		self.assertTrue(request.responseCode==400)
		with customers.OpenCollection() as collection:
			customer=collection['ALFKI']
			self.assertTrue(customer['CompanyName'].value==u"Example Inc")

			
if __name__ == "__main__":
	logging.basicConfig(level=logging.INFO)
	unittest.main()
