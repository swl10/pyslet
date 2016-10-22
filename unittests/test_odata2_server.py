#! /usr/bin/env python

import decimal
import hashlib
import io
import json
import logging
import math
import os
import random
import sys
import time
import traceback
import uuid
import unittest

from threading import Thread

from pyslet import iso8601 as iso
from pyslet import rfc2396 as uri
from pyslet import rfc4287 as atom
from pyslet import rfc5023 as app
from pyslet.http import messages
from pyslet.http import params
from pyslet.odata2 import core
from pyslet.odata2 import csdl as edm
from pyslet.odata2 import memds
from pyslet.odata2 import metadata as edmx
from pyslet.odata2 import server
from pyslet.py2 import (
    dict_values,
    is_unicode,
    long2,
    py2,
    range3,
    u8,
    ul)
from pyslet.vfs import OSFilePath as FilePath
from pyslet.xml import xsdatatypes as xsi

from test_http_server import MockTime
from test_rfc5023 import MockRequest

if py2:
    from SocketServer import ThreadingMixIn
    from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
else:
    from socketserver import ThreadingMixIn
    from http.server import HTTPServer, BaseHTTPRequestHandler


HTTP_PORT = random.randint(1111, 9999)

DOCUMENT_TEXT = b"Well, Prince, so Genoa and Lucca are now " \
                b"just family estates of the Buonapartes"


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    pass


class MockODataServer:

    responseMap = {
        ('GET', '/'): [(200, 'application/xml; charset="utf-8"', 'root.xml')],
        ('GET', '/$metadata'): [(200, 'application/xml; charset="utf-8"',
                                 'metadata.xml')],
        ('GET', '/Categories'): [(200, 'application/xml; charset="utf-8"',
                                  'categories.xml')],
        }

    def __init__(self):
        self.state = 0
        self.dataRoot = FilePath(FilePath(__file__).abspath().split()[0],
                                 'data_odatav2', 'mock_server')

    def check_capability_negotiation(self, handler):
        """Tests on the client:

        "If present on the request, the DataServiceVersion (section
        2.2.5.3) header value states the version of the protocol used by
        the client to generate the request"

        and

        "If present on the request, the MaxDataServiceVersion (section
        2.2.5.7) header value specifies the maximum version number the
        client can accept in a response. The client should set this
        value to the maximum version number of the protocol it is able
        to interpret"

        We require these to be both set to version 2.0."""
        major = minor = 0
        dsv = handler.headers["DataServiceVersion"]
        if dsv is not None:
            major, minor, ua = core.parse_dataservice_version(dsv)
        if major != 2 or minor != 0:
            raise ValueError("DataServiceVersion: %s" % dsv)
        max_dsv = handler.headers["MaxDataServiceVersion"]
        major = minor = 0
        if max_dsv is not None:
            major, minor, sa = server.parse_max_dataservice_version(max_dsv)
        if major != 2 or minor != 0:
            raise ValueError("MaxDataServiceVersion: %s" % max_dsv)

    def handle_request(self, handler):
        try:
            self.check_capability_negotiation(handler)
            r = self.responseMap[('GET', handler.path)]
            if self.state >= len(r):
                r = r[-1]
            else:
                r = r[self.state]
            self.send_response(handler, r[0], r[1], r[2])
        except KeyError:
            handler.send_response(404)
            handler.send_header("Content-Length", "0")
            handler.end_headers()
        except:
            handler.send_response(500)
            logging.error(
                "UnexpectedError in MockODataServer: %s",
                "".join(traceback.format_exception(*sys.exc_info())))
            handler.send_header("Content-Length", "0")
            handler.end_headers()

    def HandlePOST(self, handler):      # noqa
        try:
            self.check_capability_negotiation(handler)
            raise KeyError
        except KeyError:
            handler.send_response(404)
            handler.send_header("Content-Length", "0")
            handler.end_headers()
        except:
            handler.send_response(500)
            logging.error(
                "UnexpectedError in MockODataServer: %s",
                "".join(traceback.format_exception(*sys.exc_info())))
            handler.send_header("Content-Length", "0")
            handler.end_headers()

    def send_response(self, handler, code, rtype, file_name):
        try:
            rpath = self.dataRoot.join(file_name)
            f = rpath.open('rb')
            rdata = f.read() % {'port': HTTP_PORT}
            f.close()
        except IOError as e:
            code = 500
            rtype = 'text/plain'
            rdata = str(e).encode('utf-8')
        handler.send_response(code)
        handler.send_header("Content-type", rtype)
        handler.send_header("Content-Length", str(len(rdata)))
        handler.end_headers()
        handler.wfile.write(rdata)

TEST_SERVER = MockODataServer()


class MockHandler(BaseHTTPRequestHandler):

    def do_GET(self):   # noqa
        TEST_SERVER.handle_request(self)

    def do_POST(self):  # noqa
        TEST_SERVER.handle_request(self)

    def log_request(self, code=None, size=None):
        BaseHTTPRequestHandler.log_request(self, code, size)
        # Prevent successful requests logging to stderr
        pass

    def log_message(self, format, *args):
        logging.info(format, *args)


def run_odata_server():
    server = ThreadingHTTPServer(("localhost", HTTP_PORT), MockHandler)
    server.serve_forever()


def suite(prefix='test'):
    t = Thread(target=run_odata_server)
    t.setDaemon(True)
    t.start()
    logging.info(
        "OData tests starting HTTP server on localhost, port %i", HTTP_PORT)
    loader = unittest.TestLoader()
    loader.testMethodPrefix = prefix
    return unittest.TestSuite((
        loader.loadTestsFromTestCase(ODataTests),
        loader.loadTestsFromTestCase(ODataURILiteralTests),
        loader.loadTestsFromTestCase(ServerTests),
        loader.loadTestsFromTestCase(SampleServerTests)
    ))


def load_tests(loader, tests, pattern):
    """Called when we execute this file directly.

    This rather odd definition includes a larger number of tests,
    including one starting "tesx" which hit the sample OData services on
    the internet."""
    return suite('test')
    # return suite('tes')


TEST_DATA_DIR = os.path.join(
    os.path.split(os.path.abspath(__file__))[0], 'data_odatav2')


class ODataTests(unittest.TestCase):

    def test_constants(self):
        pass

    def test_type_promotion(self):
        """If supported, binary numeric promotion SHOULD consist of the
        application of the following rules in the order specified:

        If either operand is of type Edm.Decimal, the other operand is
        converted to Edm.Decimal unless it is of type Edm.Single or
        Edm.Double."""
        self.assertTrue(
            core.promote_types(edm.SimpleType.Decimal,
                               edm.SimpleType.Int64) ==
            edm.SimpleType.Decimal, "Decimal promotion of Int64")
        self.assertTrue(
            core.promote_types(edm.SimpleType.Decimal, edm.SimpleType.Int32) ==
            edm.SimpleType.Decimal, "Decimal promotion of Int32")
        self.assertTrue(
            core.promote_types(edm.SimpleType.Decimal, edm.SimpleType.Int16) ==
            edm.SimpleType.Decimal, "Decimal promotion of Int16")
        self.assertTrue(
            core.promote_types(edm.SimpleType.Decimal, edm.SimpleType.Byte) ==
            edm.SimpleType.Decimal, "Decimal promotion of Byte")
        # Otherwise, if either operand is Edm.Double, the other operand is
        # converted to type Edm.Double.
        self.assertTrue(
            core.promote_types(edm.SimpleType.Decimal,
                               edm.SimpleType.Double) ==
            edm.SimpleType.Double, "Double promotion of Decimal")
        self.assertTrue(
            core.promote_types(edm.SimpleType.Single, edm.SimpleType.Double) ==
            edm.SimpleType.Double, "Double promotion of Single")
        self.assertTrue(
            core.promote_types(edm.SimpleType.Double, edm.SimpleType.Int64) ==
            edm.SimpleType.Double, "Double promotion of Int64")
        self.assertTrue(
            core.promote_types(edm.SimpleType.Double, edm.SimpleType.Int32) ==
            edm.SimpleType.Double, "Double promotion of Int32")
        self.assertTrue(
            core.promote_types(edm.SimpleType.Double, edm.SimpleType.Int16) ==
            edm.SimpleType.Double, "Double promotion of Int16")
        self.assertTrue(
            core.promote_types(edm.SimpleType.Double, edm.SimpleType.Byte) ==
            edm.SimpleType.Double, "Double promotion of Byte")
        # Otherwise, if either operand is Edm.Single, the other operand is
        # converted to type Edm.Single.
        self.assertTrue(
            core.promote_types(edm.SimpleType.Decimal,
                               edm.SimpleType.Single) == edm.SimpleType.Single,
            "Single promotion of Decimal")
        self.assertTrue(
            core.promote_types(edm.SimpleType.Single, edm.SimpleType.Int64) ==
            edm.SimpleType.Single, "Single promotion of Int64")
        self.assertTrue(
            core.promote_types(edm.SimpleType.Single, edm.SimpleType.Int32) ==
            edm.SimpleType.Single, "Single promotion of Int32")
        self.assertTrue(
            core.promote_types(edm.SimpleType.Single, edm.SimpleType.Int16) ==
            edm.SimpleType.Single, "Single promotion of Int16")
        self.assertTrue(
            core.promote_types(edm.SimpleType.Single, edm.SimpleType.Byte) ==
            edm.SimpleType.Single, "Single promotion of Byte")
        # Otherwise, if either operand is Edm.Int64, the other operand is
        # converted to type Edm.Int64.
        self.assertTrue(
            core.promote_types(edm.SimpleType.Int64, edm.SimpleType.Int32) ==
            edm.SimpleType.Int64, "Int64 promotion of Int32")
        self.assertTrue(
            core.promote_types(edm.SimpleType.Int64, edm.SimpleType.Int16) ==
            edm.SimpleType.Int64, "Int64 promotion of Int16")
        self.assertTrue(
            core.promote_types(edm.SimpleType.Int64, edm.SimpleType.Byte) ==
            edm.SimpleType.Int64, "Int64 promotion of Byte")
        # Otherwise, if either operand is Edm.Int32, the other operand is
        # converted to type Edm.Int32
        self.assertTrue(
            core.promote_types(edm.SimpleType.Int32, edm.SimpleType.Int16) ==
            edm.SimpleType.Int32, "Int32 promotion of Int16")
        self.assertTrue(
            core.promote_types(edm.SimpleType.Int32, edm.SimpleType.Byte) ==
            edm.SimpleType.Int32, "Int32 promotion of Byte")
        # Otherwise, if either operand is Edm.Int16, the other operand is
        # converted to type Edm.Int16.
        self.assertTrue(
            core.promote_types(edm.SimpleType.Int16, edm.SimpleType.Byte) ==
            edm.SimpleType.Int16, "Int16 promotion of Byte")
        # Special case, if either operand is null we return the type of the
        # other operand
        self.assertTrue(
            core.promote_types(edm.SimpleType.Int16, None) ==
            edm.SimpleType.Int16, "Int16 promotion of NULL")
        self.assertTrue(
            core.promote_types(edm.SimpleType.Int32, None) ==
            edm.SimpleType.Int32, "Int32 promotion of NULL")
        self.assertTrue(
            core.promote_types(None, edm.SimpleType.Int64) ==
            edm.SimpleType.Int64, "Int64 promotion of NULL")
        self.assertTrue(
            core.promote_types(None, edm.SimpleType.Single) ==
            edm.SimpleType.Single, "Single promotion of NULL")
        try:
            core.promote_types(edm.SimpleType.String, edm.SimpleType.Single)
            self.fail("Type promotion of String and Single")
        except core.EvaluationError:
            pass


class ODataURILiteralTests(unittest.TestCase):

    def test_null_literal(self):
        """nullLiteral = "null" """
        v = core.uri_literal_from_str("null")
        self.assertTrue(v.is_null(), "null type is_null")
        self.assertTrue(v.type_code is None,
                        "null type: %s" % repr(v.type_code))
        self.assertTrue(v.value is None, "null value: %s" % repr(v.value))

    def test_binary_literal(self):
        """binaryUriLiteral = caseSensitiveToken SQUOTE binaryLiteral SQUOTE
                binaryLiteral = hexDigPair
                caseSensitiveToken = "X" / "binary"
                ; X is case sensitive binary is not
                hexDigPair = 2*HEXDIG [hexDigPair] """
        v = core.uri_literal_from_str("X'0A'")
        self.assertTrue(v.type_code == edm.SimpleType.Binary,
                        "binary type: %s" % repr(v.type_code))
        self.assertTrue(v.value == b'\x0a', "binary type: %s" % repr(v.value))
        v = core.uri_literal_from_str("X'0a'")
        self.assertTrue(v.value == b"\x0a", "binary type: %s" % repr(v.value))
        try:
            v = core.uri_literal_from_str("x'0a'")
            self.fail("Syntax error")
        except ValueError:
            pass
        v = core.uri_literal_from_str("binary'0A'")
        self.assertTrue(v.type_code == edm.SimpleType.Binary,
                        "binary type: %s" % repr(v.type_code))
        self.assertTrue(v.value == b'\x0a', "binary type: %s" % repr(v.value))
        v = core.uri_literal_from_str("BINARY'0A'")
        self.assertTrue(v.type_code == edm.SimpleType.Binary,
                        "binary type: %s" % repr(v.type_code))
        self.assertTrue(v.value == b'\x0a', "binary type: %s" % repr(v.value))
        # gotta love those recursive rules
        v = core.uri_literal_from_str("X'deadBEEF'")
        self.assertTrue(
            v.value == b"\xde\xad\xbe\xef", "binary type: %s" % repr(v.value))
        try:
            v = core.uri_literal_from_str("X'de'ad")
            self.fail("Spurious data")
        except ValueError:
            pass

    def test_boolean_literal(self):
        """booleanLiteral = true / false
                true = "true" / "1"
                false = "false" / "0"

        The spec is ambiguous here because 0 and 1 are valid literals for
        integer types."""
        v = core.uri_literal_from_str("true")
        self.assertTrue(v.type_code == edm.SimpleType.Boolean,
                        "boolean type: %s" % repr(v.type_code))
        self.assertTrue(v.value is True, "boolean value: %s" % repr(v.value))
        v = core.uri_literal_from_str("false")
        self.assertTrue(v.type_code == edm.SimpleType.Boolean,
                        "boolean type: %s" % repr(v.type_code))
        self.assertTrue(v.value is False, "boolean value: %s" % repr(v.value))

    def test_int_literal(self):
        """byteLiteral = 1*3DIGIT;
        int16Literal= sign 1*5DIGIT
        int32Literal= sign 1*10DIGIT
        sbyteliteral= sign 1*3DIGIT
        All returned as an int32 with python int value."""
        v = core.uri_literal_from_str("0")
        self.assertTrue(v.type_code == edm.SimpleType.Int32,
                        "0 type: %s" % repr(v.type_code))
        self.assertTrue(v.value == 0, "0 value: %s" % repr(v.value))
        v = core.uri_literal_from_str("1")
        self.assertTrue(v.type_code == edm.SimpleType.Int32,
                        "1 type: %s" % repr(v.type_code))
        self.assertTrue(v.value == 1, "1 value: %s" % repr(v.value))
        v = core.uri_literal_from_str("2147483647")
        self.assertTrue(v.type_code == edm.SimpleType.Int32,
                        "2147483647 type: %s" % repr(v.type_code))
        self.assertTrue(v.value == 2147483647,
                        "2147483647 value: %s" % repr(v.value))
        v = core.uri_literal_from_str("0000000000")
        self.assertTrue(v.type_code == edm.SimpleType.Int32,
                        "0000000000 type: %s" % repr(v.type_code))
        self.assertTrue(v.value == 0, "0000000000 value: %s" % repr(v.value))
        v = core.uri_literal_from_str("-2147483648")
        self.assertTrue(v.type_code == edm.SimpleType.Int32,
                        "-2147483648 type: %s" % repr(v.type_code))
        self.assertTrue(v.value == -2147483648,
                        "-2147483648 value: %s" % repr(v.value))
        for bad in ["00000000000", "2147483648", "-2147483649", "+1"]:
            try:
                v = core.uri_literal_from_str(bad)
                self.fail("Bad parse: %s" % bad)
            except ValueError:
                pass

    def test_date_time_literal(self):
        """
            datetimeUriLiteral = "datetime" SQUOTE dateTimeLiteral SQUOTE

            dateTimeLiteral = year "-" month "-" day "T" hour ":"
                minute [":" second ["." nanoSeconds]]

            year = 4 *Digit;
            month = <any number between 1 and 12 inclusive>
            day = nonZeroDigit /("1" DIGIT) / ("2" DIGIT ) / "3" ("0" / "1")
            hour = nonZeroDigit / ("1" DIGIT) / ("2" zeroToFour)
            zeroToFour= <any nuumber between 0 and 4 inclusive>
            minute = doubleZeroToSixty
            second = doubleZeroToSixty
            nanoSeconds= 1*7Digit

        Strangely annoying but this is very close to iso, except the
        relaxed attitude to single-digits variants. """
        v = core.uri_literal_from_str("datetime'2012-06-30T23:59'")
        self.assertTrue(v.type_code == edm.SimpleType.DateTime,
                        "date time type: %s" % repr(v.type_code))
        self.assertTrue(isinstance(v.value, iso.TimePoint),
                        "value type: %s" % repr(v.value))
        self.assertTrue(str(v.value) == "2012-06-30T23:59:00",
                        "value: %s" % str(v.value))
        v = core.uri_literal_from_str("datetime'2012-06-30T23:59:59'")
        self.assertTrue(v.type_code == edm.SimpleType.DateTime,
                        "date time type: %s" % repr(v.type_code))
        self.assertTrue(str(v.value) == "2012-06-30T23:59:59",
                        "value: %s" % str(v.value))
        v = core.uri_literal_from_str("datetime'2012-06-30T23:59:59.9999999'")
        self.assertTrue(v.type_code == edm.SimpleType.DateTime,
                        "date time type: %s" % repr(v.type_code))
        self.assertTrue(v.value.get_calendar_string(ndp=7, dp=".") ==
                        "2012-06-30T23:59:59.9999999")
        # Now for the big one!
        v = core.uri_literal_from_str("datetime'2012-06-30T23:59:60'")
        self.assertTrue(v.type_code == edm.SimpleType.DateTime,
                        "date time type for leap second: %s" %
                        repr(v.type_code))
        self.assertTrue(str(v.value) == "2012-06-30T23:59:60",
                        "value for leap second: %s" % str(v.value))
        v = core.uri_literal_from_str("datetime'2012-06-30T24:00:00'")
        self.assertTrue(v.type_code == edm.SimpleType.DateTime,
                        "date time extreme: %s" % repr(v.type_code))
        self.assertTrue(str(v.value) == "2012-06-30T24:00:00",
                        "date time extreme: %s" % str(v.value))
        # and now the crappy ones
        for crappy in [
                "datetime'2012-6-30T23:59:59'",
                "datetime'2012-06-1T23:59:59'",
                "datetime'2012-06-30T3:59:59'"]:
            v = core.uri_literal_from_str(crappy)
            self.assertTrue(v.type_code == edm.SimpleType.DateTime,
                            "date time type: %s" % repr(v.type_code))
        for bad in [
                "datetime'2012-02-30T23:59:59'",
                "datetime'12012-06-30T23:59:59'",
                "datetime'2012-00-30T23:59:59'",
                "datetime'2012-13-30T23:59:59'",
                "datetime'2012-06-00T23:59:59'",
                "datetime'2012-07-32T23:59:59'",
                "datetime'2012-06-30T24:59:59'",
                "datetime'2012-07-32T23:60:59'",  # surely illegal!
                "datetime'2012-06-30T23:59:61'",
                "datetime'2012-06-30T23:59:59.99999999'",
                "datetime'2012-06-30T23:59",
                "datetime2012-06-30T23:59'",
                "2012-06-30T23:59"]:
            try:
                v = core.uri_literal_from_str(bad)
                self.fail("Bad parse: %s resulted in %s (%s)" % (
                    bad, repr(v.value), edm.SimpleType.to_str(v.type_code)))
            except ValueError:
                pass

    def test_decimal_literal(self):
        """decimalUriLiteral = decimalLiteral
                ("M"/"m")
                decimalLiteral = sign 1*29DIGIT
                ["." 1*29DIGIT]
        All returned as a python Decimal instance."""
        v = core.uri_literal_from_str("0M")
        self.assertTrue(v.type_code == edm.SimpleType.Decimal,
                        "0M type: %s" % repr(v.type_code))
        self.assertTrue(isinstance(v.value, decimal.Decimal),
                        "0M value type: %s" % repr(v.value))
        self.assertTrue(v.value == 0, "0M value: %s" % repr(v.value))
        v = core.uri_literal_from_str("1.1m")
        self.assertTrue(v.type_code == edm.SimpleType.Decimal,
                        "1.1m type: %s" % repr(v.type_code))
        self.assertTrue(isinstance(v.value, decimal.Decimal),
                        "1.1m value type: %s" % repr(v.value))
        self.assertTrue(v.value * 10 == 11, "1.1m value: %s" % repr(v.value))
        v = core.uri_literal_from_str("12345678901234567890123456789m")
        self.assertTrue(v.type_code == edm.SimpleType.Decimal,
                        "29-digit type: %s" % repr(v.type_code))
        self.assertTrue(int(v.value.log10()) == 28,
                        "29-digit log10 value: %s" % repr(v.value))
        v2 = core.uri_literal_from_str(
            "12345678901234567890123456789.12345678901234567890123456789m")
        self.assertTrue(v2.value - v.value < decimal.Decimal('0.13') and
                        v2.value - v.value > decimal.Decimal('0.12'),
                        "29digit.29digit value: %s" % repr(v2.value - v.value))
        v = core.uri_literal_from_str("-2147483648M")
        self.assertTrue(v.type_code == edm.SimpleType.Decimal,
                        "-2147483648 type: %s" % repr(v.type_code))
        self.assertTrue(v.value == -2147483648,
                        "-2147483648 value: %s" % repr(v.value))
        for bad in ["123456789012345678901234567890m", "1.m",
                    "1.123456789012345678901234567890m", "+1M"]:
            try:
                v = core.uri_literal_from_str(bad)
                self.fail("Bad parse: %s" % bad)
            except ValueError:
                pass

    def test_double_literal(self):
        """doubleLiteral = nonDecimalPoint / nonExp / exp / nan /
                negativeInfinity / postiveInfinity ("D" / "d")
        nonDecimalPoint= sign 1*17DIGIT
        nonExpDecimal = sign *DIGIT "." *DIGIT
        expDecimal = sign 1*DIGIT "." 16DIGIT ("e" / "E") sign 1*3DIGIT

        Is that really supposed to be 16DIGIT or 1*16DIGIT?  or even
        *16DIGIT? We decide to be generous here and accept *16DIGIT

        Also, the production allows .D and -.D as, presumably, valid
        forms of 0"""
        v = core.uri_literal_from_str("0D")
        self.assertTrue(v.type_code == edm.SimpleType.Double,
                        "0D type: %s" % repr(v.type_code))
        self.assertTrue(isinstance(v.value, float),
                        "0D value type: %s" % repr(v.value))
        self.assertTrue(v.value == 0, "0D value: %s" % repr(v.value))
        v = core.uri_literal_from_str("1.1d")
        self.assertTrue(v.type_code == edm.SimpleType.Double,
                        "1.1d type: %s" % repr(v.type_code))
        self.assertTrue(isinstance(v.value, float),
                        "1.1d value type: %s" % repr(v.value))
        self.assertTrue(v.value * 10 == 11, "1.1d value: %s" % repr(v.value))
        v = core.uri_literal_from_str("12345678901234567D")
        self.assertTrue(v.type_code == edm.SimpleType.Double,
                        "17-digit type: %s" % repr(v.type_code))
        self.assertTrue(round(math.log10(v.value), 3) ==
                        16.092, "29-digit log10 value: %s" % repr(v.value))
        v = core.uri_literal_from_str("-12345678901234567D")
        self.assertTrue(v.type_code == edm.SimpleType.Double,
                        "17-digit negative type: %s" % repr(v.type_code))
        self.assertTrue(round(math.log10(-v.value), 3) ==
                        16.092, "29-digit log10 value: %s" % repr(v.value))
        v = core.uri_literal_from_str(
            "123456789012345678901234567890.123456789012345678901234567890D")
        self.assertTrue(v.type_code == edm.SimpleType.Double,
                        "30digit.30digit type: %s" % repr(v.type_code))
        self.assertTrue(round(math.log10(v.value), 3) ==
                        29.092, "30digit.30digit value: %s" % repr(v.value))
        v = core.uri_literal_from_str(
            "-123456789012345678901234567890.123456789012345678901234567890D")
        self.assertTrue(round(math.log10(-v.value), 3) == 29.092,
                        "30digit.30digit negative value: %s" % repr(v.value))
        v = core.uri_literal_from_str(".142D")
        self.assertTrue(v.value == 0.142,
                        "Empty left value: %s" % repr(v.value))
        v = core.uri_literal_from_str("-.142D")
        self.assertTrue(v.value == -0.142,
                        "Empty left neg value: %s" % repr(v.value))
        v = core.uri_literal_from_str("3.D")
        self.assertTrue(v.value == 3, "Empty right value: %s" % repr(v.value))
        v = core.uri_literal_from_str("-3.D")
        self.assertTrue(v.value == -3,
                        "Empty right neg value: %s" % repr(v.value))
        v = core.uri_literal_from_str("3.14159e000d")
        self.assertTrue(round(v.value, 3) == 3.142,
                        "zero exp: %s" % repr(v.value))
        v = core.uri_literal_from_str("NanD")
        self.assertTrue(math.isnan(v.value), "Nan double: %s" % repr(v.value))
        v = core.uri_literal_from_str("INFD")
        self.assertTrue(v.value > 0 and math.isinf(v.value),
                        "Inf double: %s" % repr(v.value))
        v = core.uri_literal_from_str("-INFD")
        self.assertTrue(v.value < 0 and math.isinf(v.value),
                        "Negative Inf double: %s" % repr(v.value))
        for bad in ["123456789012345678D", "+1D", ".1e1d", "+1.0E1d",
                    "1.12345678901234567E10d", "3.141Ed", "3.141E1234d",
                    "3.141E+10d", ".123E1D", "+NanD", "-NanD", "+INFD", ".D",
                    "-.D",
                    "-123456789012345678901234567890.1234567890123456E1d"]:
            try:
                v = core.uri_literal_from_str(bad)
                self.fail("Bad parse: %s" % bad)
            except ValueError:
                pass

    def test_single_literal(self):
        """singleUriLiteral = singleLiteral ("F" / "f")
        singleLiteral = nonDecimalPoint / nonExp / exp / nan /
            negativeInfinity / postiveInfinity
        nonDecimalPoint = sign 1*8DIGIT
        nonExpDecimal = sign *DIGIT "." *DIGIT
        expDecimal = sign 1*DIGIT "." 8DIGIT ("e" / "E") sign 1*2DIGIT

        Float requires 8DIGIT, like double requires 16DIGIT.  Seems odd
        so we decide to be generous here and accept *8DIGIT

        The production allows .F and -.f as, presumably, valid forms of
        0"""
        v = core.uri_literal_from_str("0F")
        self.assertTrue(v.type_code == edm.SimpleType.Single,
                        "0f type: %s" % repr(v.type_code))
        self.assertTrue(isinstance(v.value, float),
                        "0f value type: %s" % repr(v.value))
        self.assertTrue(v.value == 0, "0f value: %s" % repr(v.value))
        v = core.uri_literal_from_str("1.1f")
        self.assertTrue(v.type_code == edm.SimpleType.Single,
                        "1.1f type: %s" % repr(v.type_code))
        self.assertTrue(isinstance(v.value, float),
                        "1.1f value type: %s" % repr(v.value))
        self.assertTrue(v.value * 10 == 11, "1.1f value: %s" % repr(v.value))
        v = core.uri_literal_from_str("12345678F")
        self.assertTrue(v.type_code == edm.SimpleType.Single,
                        "8-digit type: %s" % repr(v.type_code))
        self.assertTrue(v.value == 12345678, "8-digit: %s" % repr(v.value))
        v = core.uri_literal_from_str("-12345678F")
        self.assertTrue(v.type_code == edm.SimpleType.Single,
                        "8-digit negative type: %s" % repr(v.type_code))
        self.assertTrue(v.value == -12345678,
                        "8-digit neg value: %s" % repr(v.value))
        v = core.uri_literal_from_str(
            "123456789012345678901234567890.123456789012345678901234567890f")
        self.assertTrue(v.type_code == edm.SimpleType.Single,
                        "30digit.30digit type: %s" % repr(v.type_code))
        self.assertTrue(round(math.log10(v.value), 3) ==
                        29.092, "30digit.30digit value: %s" % repr(v.value))
        v = core.uri_literal_from_str(
            "-123456789012345678901234567890.123456789012345678901234567890F")
        self.assertTrue(round(math.log10(-v.value), 3) == 29.092,
                        "30digit.30digit negative value: %s" % repr(v.value))
        v = core.uri_literal_from_str(".142f")
        self.assertTrue(v.value == 0.142,
                        "Empty left value: %s" % repr(v.value))
        v = core.uri_literal_from_str("-.142F")
        self.assertTrue(v.value == -0.142,
                        "Empty left neg value: %s" % repr(v.value))
        v = core.uri_literal_from_str("3.F")
        self.assertTrue(v.value == 3, "Empty right value: %s" % repr(v.value))
        v = core.uri_literal_from_str("-3.F")
        self.assertTrue(v.value == -3,
                        "Empty right neg value: %s" % repr(v.value))
        v = core.uri_literal_from_str("3.14159e00F")
        self.assertTrue(round(v.value, 3) == 3.142,
                        "zero exp: %s" % repr(v.value))
        v = core.uri_literal_from_str("3.E1F")
        self.assertTrue(v.value == 30,
                        "Empty right exp value: %s" % repr(v.value))
        v = core.uri_literal_from_str("NanF")
        self.assertTrue(math.isnan(v.value), "Nan single: %s" % repr(v.value))
        v = core.uri_literal_from_str("InfF")
        self.assertTrue(v.value > 0 and math.isinf(v.value),
                        "Inf single: %s" % repr(v.value))
        v = core.uri_literal_from_str("-INFF")
        self.assertTrue(v.value < 0 and math.isinf(v.value),
                        "Negative Inf single: %s" % repr(v.value))
        for bad in ["123456789F", "+1F", ".1e1F", "+1.0E1F",
                    "1.123456789E10F", "3.141EF", "3.141E023F", "3.141E+10F",
                    ".123E1F", "+NanF", "-NanF", "+INFF", ".f", "-.F",
                    "-123456789012345678901234567890.12345678E1F"]:
            try:
                v = core.uri_literal_from_str(bad)
                self.fail("Bad parse: %s" % bad)
            except ValueError:
                pass

    def test_guid_literal(self):
        """guidUriLiteral= "guid" SQUOTE guidLiteral SQUOTE
        guidLiteral = 8*HEXDIG "-" 4*HEXDIG "-" 4*HEXDIG "-" 12*HEXDIG

        This production appears to be in error as the CSDL uses the
        expected 8-4-4-4-12 form.  We add an extra 4 hex digits,
        effectively inserting octets 8-11 of the UUID as the constant
        "FFFF".  This places our padded UUID in the 'reserved for future
        use' range.  We could then use this value to fix up issues when
        converting back to a string in future if desired.

        To be honest, I don't think the person who wrote this rule was
        having a good day because 8*HEXDIG means at least 8 hex-digits
        and not exactly 8 hex digits as the author clearly intended."""
        v = core.uri_literal_from_str("guid'C0DEC0DE-C0DE-C0DE-C0DEC0DEC0DE'")
        self.assertTrue(v.type_code == edm.SimpleType.Guid,
                        "guide type: %s" % repr(v.type_code))
        self.assertTrue(isinstance(v.value, uuid.UUID),
                        "guide type: %s" % repr(v.value))
        self.assertTrue(v.value.hex.lower() ==
                        'c0dec0dec0dec0deffffc0dec0dec0de',
                        "guid value (missing bytes): %s" % repr(v.value))
        v = core.uri_literal_from_str(
            "guid'cd04f705-390c-4736-98dc-a3baa6b3a283'")
        self.assertTrue(v.type_code == edm.SimpleType.Guid,
                        "guide type: %s" % repr(v.type_code))
        self.assertTrue(isinstance(v.value, uuid.UUID),
                        "guide type: %s" % repr(v.value))
        self.assertTrue(v.value.hex.lower() ==
                        'cd04f705390c473698dca3baa6b3a283',
                        "guid value (random): %s" % repr(v.value))
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
                v = core.uri_literal_from_str(bad)
                self.fail("Bad parse: %s" % bad)
            except ValueError:
                pass

    def test_int64_literal(self):
        """int64UriLiteral= int64Literal ("L" / "l")
                int64Literal = sign 1*19DIGIT

                Return as a python long integer"""
        v = core.uri_literal_from_str("0L")
        self.assertTrue(v.type_code == edm.SimpleType.Int64,
                        "0L type: %s" % repr(v.type_code))
        self.assertTrue(isinstance(v.value, long2),
                        "0L value type: %s" % repr(v.value))
        self.assertTrue(v.value == 0, "0L value: %s" % repr(v.value))
        v = core.uri_literal_from_str("1234567890123456789l")
        self.assertTrue(v.type_code == edm.SimpleType.Int64,
                        "19-digit type: %s" % repr(v.type_code))
        self.assertTrue(v.value == long2(1234567890123456789),
                        "19-digit value: %s" % repr(v.value))
        v = core.uri_literal_from_str("-1234567890123456789l")
        self.assertTrue(v.type_code == edm.SimpleType.Int64,
                        "19-digit neg type: %s" % repr(v.type_code))
        self.assertTrue(v.value == long2(-1234567890123456789),
                        "19-digit neg value: %s" % repr(v.value))
        for bad in ["12345678901234567890L", "01234567890123456789l",
                    "+1l", "+0L"]:
            try:
                v = core.uri_literal_from_str(bad)
                self.fail("Bad parse: %s" % bad)
            except ValueError:
                pass

    def test_string_literal(self):
        """stringUriLiteral = SQUOTE [*characters] SQUOTE
                characters = UTF8-char """
        v = core.uri_literal_from_str("'0A'")
        self.assertTrue(v.type_code == edm.SimpleType.String,
                        "string type: %s" % repr(v.type_code))
        self.assertTrue(v.value == '0A', "string type: %s" % repr(v.value))
        v = core.uri_literal_from_str("'0a'")
        self.assertTrue(v.value == "0a", "string type: %s" % repr(v.value))
        v = core.uri_literal_from_str("'Caf%C3%A9'")
        # When parsed from a URL we assume that UTF-8 and then
        # %-encoding has been applied
        self.assertTrue(v.value == ul("Caf\xe9"),
                        "unicode string type: %s" % repr(v.value))
        # This next case is a shocker, the specification provides no way
        # to escape SQUOTE We support the undocumented doubling of the
        # SQUOTE character (now part of the published standard)
        # This particularly problematic because many browsers
        # automatically
        # %-encode single-quote in URLs even though it is not reserved by
        # RFC2396.
        v = core.uri_literal_from_str("'Peter O''Toole'")
        self.assertTrue(v.value == "Peter O'Toole",
                        "double SQUOTE: %s" % repr(v.value))
        v = core.uri_literal_from_str("%27Peter O%27%27Toole%27")
        self.assertTrue(v.value == "Peter O'Toole",
                        "%%-encoding removed: %s" % repr(v.value))
        for bad in ["0A", "'0a", "'Caf\xc3 Curtains'", "'Peter O'Toole'"]:
            try:
                v = core.uri_literal_from_str(bad)
                self.fail("Bad parse: %s" % bad)
            except UnicodeDecodeError:
                pass
            except ValueError:
                pass

    def notest_duration_literal(self):
        """This test is commented out as 'notest'

        It turns out that use of duration was a typo in the OData v2
        specification and that regular 'time' was intended.

        timeUriLiteral = "time" SQUOTE timeLiteral SQUOTE timeLiteral =
        <Defined by the lexical representation for duration in
        [XMLSCHEMA2/2]>

        We test by using the examples from XMLSchema"""
        v = core.uri_literal_from_str("time'P1Y2M3DT10H30M'")
        self.assertTrue(v.type_code == edm.SimpleType.Time,
                        "date time type: %s" % repr(v.type_code))
        self.assertTrue(isinstance(v.value, xsi.Duration),
                        "value type: %s" % repr(v.value))
        self.assertTrue(str(v.value) == "P1Y2M3DT10H30M",
                        "value: %s" % str(v.value))
        v = core.uri_literal_from_str("time'-P120D'")
        self.assertTrue(v.type_code == edm.SimpleType.Time,
                        "date time type: %s" % repr(v.type_code))
        # There is no canonical representation so this is a weak test
        self.assertTrue(str(v.value) == "-P0Y0M120D",
                        "value: %s" % str(v.value))
        for good in [
                "time'P1347Y'",
                "time'P1347M'",
                "time'P1Y2MT2H'",
                "time'P0Y1347M'",
                "time'P0Y1347M0D'",
                "time'-P1347M'"]:
            v = core.uri_literal_from_str(good)
            self.assertTrue(v.type_code == edm.SimpleType.Time,
                            "date time type: %s" % repr(v.type_code))
            self.assertTrue(isinstance(v.value, xsi.Duration),
                            "value type: %s" % repr(v.value))
        for bad in [
                "time'P-1347M'",
                "time'P1Y2MT'",
                "time'P1Y2M3DT10H30M",
                "timeP1Y2M3DT10H30M'",
                "P1Y2M3DT10H30M"]:
            try:
                v = core.uri_literal_from_str(bad)
                self.fail(
                    "Bad parse: %s resulted in %s (%s)" %
                    (bad, str(v.value), edm.SimpleType.to_str(v.type_code)))
            except ValueError:
                pass

    def test_date_time_offset_literal(self):
        """
        dateTimeOffsetUriLiteral = "datetimeoffset" SQUOTE
            dateTimeOffsetLiteral SQUOTE
        dateTimeOffsetLiteral = <Defined by the lexical representation
            for datetime (including timezone offset) in [XMLSCHEMA2/2]>

        We test by using the examples from XMLSchema"""
        v = core.uri_literal_from_str(
            "datetimeoffset'2002-10-10T12:00:00-05:00'")
        self.assertTrue(v.type_code == edm.SimpleType.DateTimeOffset,
                        "date time offset type: %s" % repr(v.type_code))
        self.assertTrue(isinstance(v.value, iso.TimePoint),
                        "value type: %s" % repr(v.value))
        self.assertTrue(isinstance(v.value, iso.TimePoint),
                        "value type: %s" % repr(v.value))
        for good in [
                "datetimeoffset'2002-10-10T17:00:00Z'",
                "datetimeoffset'2002-10-10T12:00:00Z'",
                "datetimeoffset'2002-10-10T12:00:00+05:00'",
                "datetimeoffset'2002-10-10T07:00:00Z'",
                "datetimeoffset'2002-10-10T00:00:00+05:00'",
                "datetimeoffset'2002-10-09T19:00:00Z'"]:
            v = core.uri_literal_from_str(good)
            self.assertTrue(v.type_code == edm.SimpleType.DateTimeOffset,
                            "date time offset type: %s" % repr(v.type_code))
            self.assertTrue(isinstance(v.value, iso.TimePoint),
                            "value type: %s" % repr(v.value))
        for bad in [
                "datetimeoffset'2002-10-10T17:00:00'",  # missing time zone
                "datetimeoffset'2002-10-10T17:00Z'",  # incomplete precision
                "datetimeoffset2002-10-10T17:00:00Z",  # missing quotes
        ]:
            try:
                v = core.uri_literal_from_str(bad)
                self.fail("Bad parse: %s resulted in %s (%s)" % (
                    bad, str(v.value), edm.SimpleType.to_str(v.type_code)))
            except ValueError:
                pass


class MockDocumentCollection(core.EntityCollection):

    def read_stream(self, key, out=None):
        if key == 1801:
            sinfo = core.StreamInfo(type="text/x-tolstoy")
            sinfo.size = len(DOCUMENT_TEXT)
            if out is not None:
                out.write(DOCUMENT_TEXT)
            return sinfo
        else:
            raise KeyError

    def read_stream_close(self, key):
        if key == 1801:
            sinfo = core.StreamInfo(type="text/x-tolstoy")
            sinfo.size = len(DOCUMENT_TEXT)
            return sinfo, [DOCUMENT_TEXT]
        else:
            raise KeyError


class ServerTests(unittest.TestCase):

    def setUp(self):    # noqa
        self.sampleServerData = FilePath(
            FilePath(__file__).abspath().split()[0],
            'data_odatav2', 'sample_server')

    def tearDown(self):     # noqa
        pass

    def load_metadata(self):
        doc = edmx.Document()
        md_path = self.sampleServerData.join('metadata.xml')
        with md_path.open('rb') as f:
            doc.read(f)
        return doc

    def test_constructor(self):
        s = server.Server()
        self.assertTrue(len(s.service.Workspace) == 1,
                        "Service not returning a single Workspace child")
        self.assertTrue(s.service.Workspace[0].Title.get_value(
        ) == "Default", "Service not returning a single Workspace child")
        self.assertTrue(len(s.service.Workspace[0].Collection) == 0,
                        "Workspace not empty")
        self.assertTrue(isinstance(s.service_root, uri.URI),
                        "Service root not a URI")
        # feed=s.GetFeed('Test')
        # self.assertTrue(feed is None,"Missing feed")

    def test_capability(self):
        """Tests capability negotiation of the server:

        "When the server receives a request, it must validate that the
        version number specified in the DataServiceVersion ... is less
        than or equal to the maximum version number it supports. If it
        is not, then the server must return a response with a 4xx
        response code, as described in [RFC2616]. The server should also
        return a description of the error using the error format defined
        in Error Response (section 2.2.8.1)."

        "If present on the request, the MaxDataServiceVersion (section
        2.2.5.7) header value specifies the maximum version number the
        client can accept in a response."

        and...

        "On a response from the server to the client, the
        DataServiceVersion (section 2.2.5.3) header should be
        specified."

        """
        s = server.Server()
        s.debugMode = True
        request = MockRequest('/')
        request.send(s)
        self.assertTrue(request.responseCode == 200,
                        "No DataServiceVersion:\n\n" +
                        repr(request.wfile.getvalue()))
        self.assertTrue('DATASERVICEVERSION' in request.responseHeaders,
                        "Missing DataServiceVersion in response")
        major, minor, ua = core.parse_dataservice_version(
            request.responseHeaders['DATASERVICEVERSION'])
        self.assertTrue(
            major == 2 and minor == 0, "No version should return 2.0")
        request = MockRequest('/')
        request.set_header('DataServiceVersion', "1.0; old request")
        request.send(s)
        self.assertTrue(
            request.responseCode == 200,
            "Version 1.0 request:\n\n" + repr(request.wfile.getvalue()))
        major, minor, ua = core.parse_dataservice_version(
            request.responseHeaders['DATASERVICEVERSION'])
        self.assertTrue(major == 1 and minor == 0,
                        "Version 1.0 request should return 1.0 response")
        request = MockRequest('/')
        request.set_header('DataServiceVersion', "2.0; current request")
        request.send(s)
        self.assertTrue(request.responseCode == 200)
        major, minor, ua = core.parse_dataservice_version(
            request.responseHeaders['DATASERVICEVERSION'])
        self.assertTrue(major == 2 and minor == 0,
                        "Version 2.0 request should return 2.0 response")
        # Should be OK
        request = MockRequest('/')
        request.set_header('DataServiceVersion', "2.1; future request")
        request.send(s)
        self.assertTrue(request.responseCode == 400,
                        "Version mismatch error response: %i" %
                        request.responseCode)
        doc = core.Document()
        doc.read(src=request.wfile.getvalue())
        error = doc.root
        self.assertTrue(
            isinstance(error, core.Error), "Expected an error instance")
        self.assertTrue(error.Code.get_value() == "DataServiceVersionMismatch",
                        "Error code")
        self.assertTrue(
            error.Message.get_value() ==
            "Maximum supported protocol version: 2.0", "Error message")
        self.assertTrue(error.InnerError is None, "No inner error")
        request = MockRequest('/')
        request.set_header('DataServiceVersion', "2.1; future request")
        request.set_header('Accept', "application/json")
        request.send(s)
        self.assertTrue(request.responseCode == 400,
                        "Version mismatch error response")
        self.assertTrue(
            request.responseHeaders['CONTENT-TYPE'] == "application/json",
            "Expected JSON response")
        error_doc = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(len(error_doc) == 1, "Expected a single error object")
        self.assertTrue(len(error_doc['error']) == 2, "Expected two children")
        self.assertTrue(
            error_doc['error']['code'] == "DataServiceVersionMismatch",
            "Error code")
        self.assertTrue(
            error_doc['error']['message'] ==
            "Maximum supported protocol version: 2.0", "Error message")
        self.assertFalse('innererror' in error_doc['error'], "No inner error")
        request = MockRequest('/')
        request.set_header('DataServiceVersion', "1.0; old request")
        request.set_header('MaxDataServiceVersion', "1.0; old max")
        request.send(s)
        self.assertTrue(request.responseCode == 200)
        major, minor, ua = core.parse_dataservice_version(
            request.responseHeaders['DATASERVICEVERSION'])
        self.assertTrue(
            major == 1 and minor == 0,
            "MaxVersion 1.0 request should return 1.0 response: %i.%i" %
            (major, minor))
        request = MockRequest('/')
        request.set_header('DataServiceVersion', "1.0; old request")
        request.set_header('MaxDataServiceVersion', "2.0; current max")
        request.send(s)
        self.assertTrue(request.responseCode == 200)
        major, minor, ua = core.parse_dataservice_version(
            request.responseHeaders['DATASERVICEVERSION'])
        self.assertTrue(major == 2 and minor == 0,
                        "MaxVersion 2.0 request should return 2.0 response")
        request = MockRequest('/')
        request.set_header('DataServiceVersion', "1.0; old request")
        request.set_header('MaxDataServiceVersion', "2.1; future max")
        request.send(s)
        self.assertTrue(request.responseCode == 200)
        major, minor, ua = core.parse_dataservice_version(
            request.responseHeaders['DATASERVICEVERSION'])
        self.assertTrue(major == 2 and minor == 0,
                        "MaxVersion 2.1 request should return 2.0 response")

    def test_service_root(self):
        """The resource identified by [the service root] ... MUST be an
        AtomPub Service Document"""
        s = server.Server()
        request = MockRequest('/')
        request.send(s)
        self.assertTrue(request.responseCode == 200)
        doc = app.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, app.Service),
                        "Service root not an app.Service")
        # An empty server has no workspaces
        self.assertTrue(len(doc.root.Workspace) == 1,
                        "Empty server = 1 workspace")
        self.assertTrue(len(doc.root.Workspace[0].Collection) == 0,
                        "Empty Server = no collections")
        self.assertTrue(doc.root.get_base() == str(s.service_root),
                        "Non-matching service root: base=%s, root=%s" %
                        (repr(doc.root.get_base()), repr(str(s.service_root))))

    def test_model(self):
        """With a simple OData server we set the model manually"""
        s = server.Server()
        self.assertTrue(s.model is None, "no model initially")
        # Load the model document
        doc = self.load_metadata()
        s.set_model(doc)
        # at this point, the server's model root is available as model
        self.assertTrue(s.model is doc.root, "model attribute")

    def test_entity_type_as_atom_entry(self):
        doc = self.load_metadata()
        ds = doc.root.DataServices
        customers = ds['SampleModel.SampleEntities.Customers']
        customer = core.Entity(customers)
        customer['CustomerID'].set_from_value('X')
        customer['CompanyName'].set_from_value('Megacorp')
        # fake existence
        customer.exists = True
        # If the entity represents an AtomPub Entry Resource... the
        # <atom:content> element MUST contain a "type" attribute with
        # the value "application/xml"
        entry = core.Entry(None, customer)
        self.assertTrue(entry.Content.type == "application/xml")
        # The <atom:content> element MUST also contain one
        # <m:properties> child element
        children = list(entry.Content.get_children())
        self.assertTrue(len(children) == 1, "one child element")
        self.assertTrue(isinstance(children[0],
                        core.Properties), "child is properties element")
        children = list(entry.find_children_depth_first(atom.Link))
        links = {}
        navigation = list(customer.navigation_keys())
        for child in children:
            # Each <atom:link> element MUST contain an atom:rel attribute
            # with the value defined by the relNavigationlLinkURI rule
            if child.rel.startswith(core.ODATA_RELATED):
                pname = child.rel[len(core.ODATA_RELATED):]
                # ...servers MUST represent each NavigationProperty of the
                # EntityType as an <atom:link> element that is a child
                # element of the <atom:entry> element.
                self.assertTrue(child.parent is entry,
                                "Link must be a child of the entry element")
                # The element SHOULD also contain an atom:title attribute
                # with the value equal to the NavigationProperty name
                self.assertTrue(pname in navigation,
                                "Link must be a navigation property")
                self.assertTrue(child.title == pname,
                                "Title should be name of navigation property")
                # and MUST contain an atom:href attribute with value
                # equal to the URI which identifies the
                # NavigationProperty on the EntityType.
                links[pname] = (child.href, child.type)
        self.assertTrue(
            links['Orders'][0] == "Customers('X')/Orders", "Orders link")
        # [the atom:type attribute] should have a value of ...
        # "application/atom+xml;type=feed" when the property
        # identifies an EntitySet.
        self.assertTrue(links['Orders'][1] == "application/atom+xml;type=feed",
                        "Orders link type")
        # Entity binding tests...
        customer.exists = False
        customer['Orders'].bind_entity(1)
        customer['Orders'].bind_entity(2)
        # it isn't clear if the spec intends to support mixed cases
        # of deep insert and binding to existing entities on the same
        # request, but in theory there is no reason why we shouldn't
        order = core.Entity(ds['SampleModel.SampleEntities.Orders'])
        order['OrderID'].set_from_value(3)
        customer['Orders'].bind_entity(order)
        # To bind the new entity to an existing entity the "href"
        # attribute of the <atom:link> element must represent the URI
        # of the entity to be linked to.
        entry = core.Entry(None, customer)
        children = list(entry.find_children_depth_first(atom.Link))
        self.assertTrue(len(children) == 3, "Three links present links")
        links = {}
        for child in children:
            if child.rel.startswith(core.ODATA_RELATED):
                self.assertTrue(child.parent is entry,
                                "Link must be a child of the entry element")
                self.assertTrue(child.title == pname,
                                "Title should be name of navigation property")
                self.assertTrue(child.type is None,
                                "We don't need the child type")
                pname = child.rel[len(core.ODATA_RELATED):]
                self.assertTrue(pname == 'Orders', "Only Orders link is bound")
                if child.href == "Customers('X')/Orders":
                    self.assertTrue(child.Inline is not None,
                                    "deep link has child")
                    self.assertTrue(child.Inline.Feed is not None,
                                    "deep link child has Feed")
                    # test the collection in the feed
                    self.assertTrue(len(child.Inline.Feed.collection) == 1,
                                    "one deep-linked child")
                    e = list(child.Inline.Feed.collection.itervalues())[0]
                    self.assertTrue(e['OrderID'].value == 3, "Order number 3")
                else:
                    links[child.href] = True
        self.assertTrue(len(links) == 2, "Two entities bound")
        self.assertTrue("Orders(1)" in links, "Orders(1)")
        self.assertTrue("Orders(2)" in links, "Orders(2)")
        #
        # End of customer tests
        #
        orders = ds['SampleModel.SampleEntities.Orders']
        order = core.Entity(orders)
        order['OrderID'].set_from_value(1)
        order.exists = True
        entry = core.Entry(None, order)
        children = list(entry.find_children_depth_first(atom.Link))
        links = {}
        navigation = list(order.navigation_keys())
        for child in children:
            if child.rel.startswith(core.ODATA_RELATED):
                pname = child.rel[len(core.ODATA_RELATED):]
                links[pname] = (child.href, child.type)
        self.assertTrue(links['Customer'][0] == "Orders(1)/Customer",
                        "Customer link")
        # [the atom:type attribute] should have a value of
        # "application/atom+xml;type=entry" when the
        # NavigationProperty identifies a single entity instance
        self.assertTrue(
            links['Customer'][1] == "application/atom+xml;type=entry",
            "Customer link type")
        self.assertTrue(links['OrderLine'][0] == "Orders(1)/OrderLine",
                        "OrderLine link")
        self.assertTrue(
            links['OrderLine'][1] == "application/atom+xml;type=entry",
            "OrderLine link type")
        #
        # End of order tests
        #
        employees = ds['SampleModel.SampleEntities.Employees']
        employee = core.Entity(employees)
        employee['EmployeeID'].set_from_value('12345')
        employee['EmployeeName'].set_from_value('Joe Bloggs')
        employee['Address']['City'].set_from_value('Chunton')
        employee.exists = True
        entry = core.Entry(None, employee)
        properties = list(entry.Content.get_children())[0]
        plist = list(properties.get_children())
        # Each child element representing a property MUST be
        # defined in the data service namespace... and the
        # element name must be the same as the property it
        # represents.
        for p in plist:
            self.assertTrue(p.ns == core.ODATA_DATASERVICES_NAMESPACE,
                            "Property not in data services namespace")
        pnames = [x.xmlname for x in plist]
        pnames.sort()
        self.assertTrue(pnames == ["Address", "EmployeeID", "Version"],
                        "Property names")
        # The <m:properties> element MUST contain one child
        # element for each EDMSimpleType and ComplexType property
        # of the EntityType instance represented by the
        # <atom:entry> element that is not otherwise mapped
        # through a Customizable Feed property mapping
        self.assertTrue(len(plist) == 3,
                        "3/4 properties due to keep in content = False")
        # If the Entity Type instance represented includes
        # Customizable Feeds annotations in the data services
        # metadata document, then the properties with custom mappings
        # must be represented as directed by the mappings information
        got_location = False
        for child in entry.get_children():
            if child.get_xmlname() == ("http://www.example.com", "Location"):
                self.assertTrue(child.get_value() == "Chunton",
                                "City not mapped to location")
                got_location = True
        self.assertTrue(got_location, "Missing custom feed mapping")
        # If the Entity Type instance being represented was
        # identified with a URI that includes a Select System
        # Query Option (section 2.2.3.6.1.11), then the prior
        # rule is relaxed such that only the properties
        # identified by the $select query option SHOULD be
        # represented as child elements of the <m:properties>
        # element.
        employee.expand({}, {'Address': None})
        entry = core.Entry(None, employee)
        properties = list(list(entry.Content.get_children())[0].get_children())
        self.assertTrue(len(properties) == 1, "A single property selected")
        employee['EmployeeName'].set_from_value(None)
        entry = core.Entry(None, employee)
        # If the property of an Entity Type instance ...includes
        # Customizable Feed annotations ... and has a value of null,
        # then the element ... can be present and MUST be empty.
        self.assertTrue(entry.Title.get_value() == "", "Empty title element")
        #
        # End of employee tests
        #
        documents = ds['SampleModel.SampleEntities.Documents']
        documents.bind(MockDocumentCollection)
        document = core.Entity(documents)
        document['DocumentID'].set_from_value(1801)
        document['Title'].set_from_value('War and Peace')
        document['Author'].set_from_value('Tolstoy')
        h = hashlib.sha256()
        h.update(DOCUMENT_TEXT)
        document['Version'].set_from_value(h.digest())
        document.exists = True
        entry = core.Entry(None, document)
        # If the entity represents an AtomPub Media Link Entry...
        # the <m:properties> element... the <m:properties>
        # element MUST be a direct child of the <atom:entry>
        # element
        children = list(entry.find_children_depth_first(core.Properties))
        self.assertTrue(len(children) == 1, "one properties element")
        self.assertTrue(children[0].parent is entry,
                        "properties is a direct child of *the* entry")
        children = list(entry.find_children_depth_first(atom.Content))
        self.assertTrue(len(children) == 1, "one content element")
        self.assertTrue(entry.Content is not None, "content is child of entry")
        self.assertTrue(str(entry.Content.src) == "Documents(1801)/$value")
        self.assertTrue(entry.Content.type == "text/x-tolstoy")
        children = list(entry.find_children_depth_first(atom.Link))
        links = set()
        for child in children:
            links.add(child.rel)
            if child.rel == "edit-media":
                self.assertTrue(
                    child.href == "Documents(1801)/$value", "edit-media link")
                self.assertTrue(
                    child.get_attribute((core.ODATA_METADATA_NAMESPACE,
                                         "etag")) ==
                    "W/\"X'%s'\"" % h.hexdigest().upper())
            if child.rel == "edit":
                # [the edit link] MUST have an atom:href attribute
                # whose value is a URI that identifies the entity
                self.assertTrue(child.href == "Documents(1801)", "edit link")
        # [for AtomPub Media Link Entries] an <atom:link> element
        # SHOULD be included, which contains an
        # atom:rel="edit-media" attribute
        self.assertTrue("edit-media" in links, "Missing edit-media link")
        # An <atom:link> element SHOULD be included, which contains
        # an atom:rel="edit" or atom:rel="self" attribute
        self.assertTrue(
            "edit" in links or "self" in links, "Missing edit/self link")
        # An <atom:category> element containing an atom:term
        # attribute and an atom:scheme attribute MUST be included if
        # the EntityType of the EntityType instance represented by
        # the <atom:entry> object is part of an inheritance hierarchy
        got_type = False
        for cat in entry.Category:
            # The value of the atom:scheme attribute MUST be a data
            # service specific IRI [or] it SHOULD use the URI shown in
            # grammar rule dataServiceSchemeURI
            if cat.scheme == core.ODATA_SCHEME:
                # The value of the atom:term attribute MUST be the
                # namespace qualified name of the EntityType of the
                # instance
                self.assertTrue(
                    cat.term == "SampleModel.Document",
                    "Expected category term to be SampleModel.Document")
                got_type = True
        # If the EntityType is not part of an inheritance hierarchy,
        # then the <atom:category> element can be included
        self.assertTrue(got_type, "Expected category term")

    def test_entity_type_as_json(self):
        doc = self.load_metadata()
        ds = doc.root.DataServices
        customers = ds['SampleModel.SampleEntities.Customers']
        customer = core.Entity(customers)
        customer['CustomerID'].set_from_value('X')
        customer['CompanyName'].set_from_value('Megacorp')
        customer['Address']['City'].set_from_value('Chunton')
        customer.exists = True
        json_data = ' '.join(customer.generate_entity_type_in_json())
        obj = json.loads(json_data)
        # Each property on the EntityType MUST be represented as a
        # name/value pair
        nprops = 0
        for k in obj:
            if k.startswith("__"):
                continue
            nprops = nprops + 1
        # The default representation of a NavigationProperty is as a
        # JSON name/value pair. The name is equal to "__deferred" and
        # the value is a JSON object that contains a single
        # name/value pair with the name equal to "uri"
        self.assertTrue("Orders" in obj)
        self.assertTrue("__deferred" in obj["Orders"])
        self.assertTrue(
            obj["Orders"]["__deferred"]["uri"] == "Customers('X')/Orders")
        # Each declared property defined on the ComplexType MUST be
        # represented as a name/value pair within the JSON object.
        self.assertTrue("City" in obj["Address"], "City in Address")
        self.assertTrue("Street" in obj["Address"], "Street in Address")
        # Additional name/value pairs that do not represent a
        # declared property of the ComplexType SHOULD NOT be
        # included.
        self.assertTrue(
            len(obj["Address"]) == 2, "Only two properties in Address")
        # Name/value pairs not representing a property defined on the
        # EntityType SHOULD NOT be included
        self.assertTrue(nprops == 5, "5 properties in Customer 4+1 navigation")
        # an EntityType instance MAY include a name/value pair named
        # "__metadata"
        self.assertTrue("__metadata" in obj, "Expected __metadata")
        # The value of the "uri" name/value pair MUST be the
        # canonical URI identifying the EntityType instance
        meta = obj["__metadata"]
        self.assertTrue(meta["uri"] == "Customers('X')", "uri in metadata")
        # The value of the "type" name/value pair MUST be the
        # namespace qualified name... of the EntityType of the
        # instance
        self.assertTrue(
            meta["type"] == "SampleModel.Customer", "type in metadata")
        self.assertFalse("etag" in meta, "etag null case")
        # If the entity being represented is not a Media Link Entry,
        # then the "edit_media", "media_src", "media_etag", and
        # "content_type" name/value pairs MUST NOT be included
        self.assertFalse("media_src" in meta)
        self.assertFalse("content_type" in meta)
        self.assertFalse("edit_media" in meta)
        self.assertFalse("media_etag" in meta)
        # Fake lack of existence
        customer.exists = False
        customer['Orders'].bind_entity(1)
        customer['Orders'].bind_entity(2)
        json_data = ' '.join(customer.generate_entity_type_in_json())
        obj = json.loads(json_data)
        self.assertTrue(isinstance(obj['Orders'], list), "JSON array")
        self.assertTrue(len(obj['Orders']) == 2, "Two bindings")
        links = set()
        for link in obj['Orders']:
            self.assertTrue(isinstance(link, dict), "Each link is an object")
            links.add(link['__metadata']['uri'])
        self.assertTrue("Orders(1)" in links, "Orders(1)")
        self.assertTrue("Orders(2)" in links, "Orders(2)")
        customer.exists = True
        customer.expand({}, {'CustomerID': None, 'CompanyName': None})
        # [if using the] Select System Query Option then only the
        # properties identified by the $select query option MUST be
        # represented by name/value pairs
        json_data = ' '.join(customer.generate_entity_type_in_json())
        obj = json.loads(json_data)
        nprops = 0
        for k in obj:
            if k.startswith("__"):
                continue
            nprops = nprops + 1
        self.assertTrue(
            nprops == 2, "Two properties selected in Customer: %i" % nprops)
        document_set = ds['SampleModel.SampleEntities.Documents']
        container = memds.InMemoryEntityContainer(
            ds['SampleModel.SampleEntities'])
        documents = container.entityStorage['Documents']
        doc_text = DOCUMENT_TEXT
        h = hashlib.sha256()
        h.update(doc_text)
        etag = "W/\"X'%s'\"" % h.hexdigest().upper()
        documents.data[1801] = (1801, 'War and Peace', 'Tolstoy', h.digest())
        with document_set.open() as coll:
            sinfo = core.StreamInfo(type=params.PLAIN_TEXT)
            coll.update_stream(io.BytesIO(doc_text), 1801, sinfo)
            document = coll[1801]
        json_data = ' '.join(document.generate_entity_type_in_json())
        obj = json.loads(json_data)
        meta = obj["__metadata"]
        self.assertTrue(
            meta["etag"] == etag, "document etag: %s" % meta["etag"])
        # The "media_src" and "content_type" name/value pairs MUST be
        # included and the "edit_media" and "media_etag" name/value
        # pairs can be included if the entity being represented is a
        # Media Link Entry
        self.assertTrue(meta["media_src"] == "Documents(1801)/$value",
                        "media src link")
        self.assertTrue(meta["content_type"] == "text/plain",
                        "document content type")
        self.assertTrue(meta["edit_media"] == "Documents(1801)/$value",
                        "edit-media link")
        self.assertTrue(meta["media_etag"] == etag, "document etag")

    def test_entity_type_from_json(self):
        doc = self.load_metadata()
        ds = doc.root.DataServices
        customers = ds['SampleModel.SampleEntities.Customers']
        customer = core.Entity(customers)
        customer['CustomerID'].set_from_value('X')
        customer['CompanyName'].set_from_value('Megacorp')
        json_data = ' '.join(customer.generate_entity_type_in_json())
        obj = json.loads(json_data)
        new_customer = core.Entity(customers)
        new_customer.set_from_json_object(obj)
        self.assertTrue(new_customer['CustomerID'].value == "X",
                        "Check customer ID")
        self.assertTrue(new_customer['CompanyName'].value == "Megacorp",
                        "Check customer name")
        self.assertFalse(new_customer['Address']['Street'], "No street")
        self.assertFalse(new_customer['Address']['City'], "No city")
        self.assertFalse(new_customer['Version'], "No version")
        employees = ds['SampleModel.SampleEntities.Employees']
        employee = core.Entity(employees)
        employee['EmployeeID'].set_from_value('12345')
        employee['EmployeeName'].set_from_value('Joe Bloggs')
        employee['Address']['City'].set_from_value('Chunton')
        json_data = ' '.join(employee.generate_entity_type_in_json())
        obj = json.loads(json_data)
        new_employee = core.Entity(employees)
        new_employee.set_from_json_object(obj)
        self.assertTrue(new_employee['EmployeeID'].value == "12345",
                        "Check employee ID")
        self.assertTrue(new_employee['EmployeeName'].value == "Joe Bloggs",
                        "Check employee name")
        self.assertFalse(new_employee['Address']['Street'], "No street")
        self.assertTrue(new_employee['Address']['City'] == "Chunton",
                        "Check employee city")
        self.assertFalse(new_employee['Version'], "No version")
        document_set = ds['SampleModel.SampleEntities.Documents']
        container = memds.InMemoryEntityContainer(
            ds['SampleModel.SampleEntities'])
        documents = container.entityStorage['Documents']
        doc_text = DOCUMENT_TEXT
        h = hashlib.sha256()
        h.update(doc_text)
        documents.data[1801] = (1801, 'War and Peace', 'Tolstoy', h.digest())
        with document_set.open() as coll:
            sinfo = core.StreamInfo(type=params.PLAIN_TEXT)
            coll.update_stream(io.BytesIO(doc_text), 1801, sinfo)
            document = coll[1801]
        json_data = ' '.join(document.generate_entity_type_in_json())
        obj = json.loads(json_data)
        new_document = core.Entity(document_set)
        new_document.set_from_json_object(obj)
        self.assertTrue(new_document['DocumentID'].value == 1801,
                        "Check document ID")
        self.assertTrue(new_document['Title'].value == "War and Peace",
                        "Check document name")
        self.assertTrue(new_document['Author'] == "Tolstoy",
                        "Check author name")
        self.assertTrue(new_document['Version'].value == h.digest(),
                        "Mismatched version")

    def test_entity_set_as_atom_feed(self):
        doc = self.load_metadata()
        ds = doc.root.DataServices
        container = memds.InMemoryEntityContainer(
            ds['SampleModel.SampleEntities'])
        customers_set = ds['SampleModel.SampleEntities.Customers']
        customers = container.entityStorage['Customers']
        container.entityStorage['Orders']
        container.associationStorage['Orders_Customers']
        customers.data['ALFKI'] = ('ALFKI', 'Example Inc',
                                   ("Mill Road", "Chunton"), None)
        for i in range3(3):
            customers.data['XX=%02X' % i] = (
                'XX=%02X' % i, 'Example-%i Ltd' % i, (None, None), None)
        feed = core.Feed(None, customers_set.open())
        # The <atom:id> element MUST contain the URI that identifies the
        # EntitySet
        self.assertTrue(feed.AtomId.get_value() == "Customers")
        # The <atom:title> element can contain the name of the
        # EntitySet represented by the parent <atom:feed> element...
        # The set name can be qualified with the name of the EDM
        # namespace in which it is defined
        self.assertTrue(
            feed.Title.get_value() == "SampleModel.SampleEntities.Customers")
        children = list(feed.find_children_depth_first(atom.Link, maxDepth=1))
        links = set()
        for child in children:
            links.add(child.rel)
            if child.rel == "self":
                # An <atom:link> element with a rel="self" attribute MUST
                # contain an href attribute with a value equal to the URI
                # used to identify the set that the parent <atom:feed>
                # element represents
                self.assertTrue(child.href == "Customers", "self link")
        self.assertTrue("self" in links, "Missing self link")
        self.assertTrue(
            len(feed.Entry) == 0,
            "Feed uses generator instead of static array of entries")
        nentries = 0
        for child in feed.get_children():
            if isinstance(child, atom.Entry):
                nentries += 1
        self.assertTrue(nentries == 4, "4 entries generated by the feed")
        page = customers_set.open()
        page.set_topmax(2)
        page.set_inlinecount(True)
        feed = core.Feed(None, page)
        nentries = 0
        # [with inlinecount the response] MUST include the count of
        # the number of entities in the collection of entities
        count = None
        for child in feed.get_children():
            if isinstance(child, core.Count):
                # The count value included in the result MUST be
                # enclosed in an <m:count> element
                # The <m:count> element MUST be a direct child
                # element of the <feed> element
                count = child.get_value()
                self.assertTrue(count == 4, "4 total size of collection")
            if isinstance(child, atom.Entry):
                # ...and MUST occur before any <atom:entry> elements in
                # the feed
                self.assertFalse(count is None, "count after Entry")
                nentries += 1
        self.assertTrue(nentries == 2, "2 entries for partial feed")
        children = list(feed.find_children_depth_first(atom.Link))
        links = set()
        # if the server does not include an <atom:entry> element as a
        # child element of the <atom:feed> element for every entity
        # in the collection ... The href attribute of the <atom:link
        # rel="next"> element ... MUST have a value equal to the URI
        # that identifies the next partial set of entities
        for child in children:
            links.add(child.rel)
            if child.rel == "next":
                # Such a URI SHOULD include a Skip Token System Query Option
                self.assertTrue("$skiptoken" in child.href, "skiptoken")
        self.assertTrue("next" in links, "Missing next link")
        customer = customers_set.open()['ALFKI']
        feed = core.Feed(None, customer['Orders'].open())
        # If the URI in the sibling <atom:id> element is of the same
        # form as URI 6 and the NavigationProperty identifies an
        # EntitySet, then the <atom:title> element can contain the
        # name of the NavigationProperty instead of the name of the
        # EntitySet identified by the property
        self.assertTrue(feed.AtomId.get_value() == "Customers('ALFKI')/Orders")
        self.assertTrue(feed.Title.get_value() == "Orders")

    def test_entity_set_as_json(self):
        doc = self.load_metadata()
        ds = doc.root.DataServices
        container = memds.InMemoryEntityContainer(
            ds['SampleModel.SampleEntities'])
        customers_set = ds['SampleModel.SampleEntities.Customers']
        customers = container.entityStorage['Customers']
        container.entityStorage['Orders']
        container.associationStorage['Orders_Customers']
        customers.data['ALFKI'] = (
            'ALFKI', 'Example Inc', ("Mill Road", "Chunton"), None)
        for i in range3(3):
            customers.data['XX=%02X' % i] = (
                'XX=%02X' % i, 'Example-%i Ltd' % i, (None, None), None)
        collection = customers_set.open()
        json_data = ''.join(collection.generate_entity_set_in_json())
        # Version 2 object by default
        obj = json.loads(json_data)
        self.assertTrue(isinstance(obj, dict), "Version 2 type is dictionary")
        self.assertTrue("results" in obj, "results present")
        # An EntitySet or collection of entities MUST be represented
        # as an array of JSON objects, with one object for each
        # EntityType instance within the set
        self.assertTrue(isinstance(obj["results"], list),
                        "EntitySet represented as JSON array")
        self.assertTrue(len(obj["results"]) == 4, "Four entities")
        # Version 1.0 JSON representation
        v1_json_data = ''.join(collection.generate_entity_set_in_json(1))
        obj = json.loads(v1_json_data)
        self.assertTrue(isinstance(obj, list), "Version 1 type is an array")
        self.assertTrue(len(obj) == 4, "Four entities")
        collection.set_topmax(2)
        collection.set_inlinecount(True)
        # if the server does not include an entityTypeInJson ... for
        # every entity in the collection ... a nextLinkNVP name value
        # pair MUST be included
        json_data = ''.join(collection.generate_entity_set_in_json())
        obj = json.loads(json_data)
        self.assertTrue("__next" in obj, "next link included")
        # The URI in the associated nextURINVP name value pair MUST
        # have a value equal to the URI, which identifies the next
        # partial set of entities from the originally identified
        # complete set.
        self.assertTrue(isinstance(obj["__next"],
                        dict), "next link is json object")
        # Such a URI SHOULD include a Skip Token System Query Option
        self.assertTrue("$skiptoken" in obj["__next"]["uri"],
                        "next link contains a skiptoken")
        # If [the URI contains an $inlinecount System Query
        # Option] the response MUST include the countNVP
        # name/value pair (before the results name/value pair) with
        # the value  equal to the count of the total number of
        # entities.
        self.assertTrue("__count" in obj, "count included")
        self.assertTrue(obj["__count"] == 4, "Four entities in total")
        self.assertTrue(json_data.index("__count") < json_data.index(
            "results"), "first __count before results")
        # An empty EntitySet or collection of entities MUST be
        # represented as an empty JSON array.
        entity_collection = collection['ALFKI']["Orders"].open()
        json_data = ''.join(entity_collection.generate_entity_set_in_json())
        obj = json.loads(json_data)
        self.assertTrue(isinstance(obj["results"], list),
                        "Empty EntitySet represented as JSON array")
        self.assertTrue(len(obj["results"]) == 0, "No entities")

    def test_encode_pathinfo(self):
        self.assertTrue(server.Server.encode_pathinfo("/?/'/hello?'/bye") ==
                        "/%3F/'%2Fhello%3F'/bye")
        self.assertTrue(server.Server.encode_pathinfo("/a;b/'/a;b?'/bye") ==
                        "/a;b/'%2Fa%3Bb%3F'/bye")
        self.assertTrue(server.Server.encode_pathinfo("/'a'';b'/bye") ==
                        "/'a''%3Bb'/bye")


class CustomersByCityEntityCollection(core.FunctionEntityCollection):

    def __init__(self, function, params, customers):
        core.FunctionEntityCollection.__init__(self, function, params)
        self.customers = customers
        self.collection = self.entity_set.open()
        self.city = params.get('city').value

    def itervalues(self):
        for customer in dict_values(self.customers.data):
            if customer[2][1] == self.city:
                yield self.collection[customer[0]]


class ShippedAddressByDateCollection(core.FunctionCollection):

    def __init__(self, function, params, customers_entity_set):
        core.FunctionCollection.__init__(self, function, params)
        self.date = params.get('date').value
        if self.date is None:
            self.date = iso.TimePoint.from_now()
        self.collection = customers_entity_set.open()

    def __iter__(self):
        for customer in self.collection.itervalues():
            yield customer['Address']


class ShippedCustomerNamesByDateCollection(core.FunctionCollection):

    def __init__(self, function, params, customers_entity_set):
        core.FunctionCollection.__init__(self, function, params)
        self.date = params.get('date').value
        if self.date is None:
            self.date = iso.TimePoint.from_now()
        self.collection = customers_entity_set.open()

    def __iter__(self):
        for customer in self.collection.itervalues():
            yield customer['CompanyName']


class SampleServerTests(unittest.TestCase):

    def setUp(self):    # noqa
        """
        The scheme and Service Root for this sample is
        http://host/service.svc.

        A Customer Entity Type instance exists with EntityKey value
        ALFKI.

        A total of 91 Customer Entity Type instances exist.

        An Employee Entity Type instance exists with EntityKey value 1.

        Two Order Entity Type instances exist, one with EntityKey value
        1 and the other with EntityKey value 2. Order 1 and 2 are
        associated with Customer ALFKI.

        Two OrderLine Entity Type instances exist, one with EntityKey
        value 100 and the other with EntityKey value 200. OrderLine 100
        is associated with Order 1 and OrderLine 200 with Order 2.

        Two Document Entity Type instances exist, one with EntityKey
        value 300 and the other with EntityKey value 301."""
        # freeze the clock during these tests
        iso.pytime = MockTime
        MockTime.now = time.time()
        self.sampleServerData = FilePath(
            FilePath(__file__).abspath().split()[0], 'data_odatav2',
            'sample_server')
        self.svc = server.Server('http://host/service.svc')
        self.svc.debugMode = True
        doc = edmx.Document()
        md_path = self.sampleServerData.join('metadata.xml')
        with md_path.open('rb') as f:
            doc.read(f)
        self.ds = doc.root.DataServices
        self.svc.set_model(doc)
        self.container = memds.InMemoryEntityContainer(
            self.ds['SampleModel.SampleEntities'])
        customers = self.container.entityStorage['Customers']
        customers.data['ALFKI'] = (
            'ALFKI', 'Example Inc', ("Mill Road", "Chunton"),
            b'\x00\x00\x00\x00\x00\x00\xfa\x01')
        for i in range3(90):
            customers.data['XX=%02X' % i] = (
                'XX=%02X' % i, 'Example-%i Ltd' % i, (None, None), None)
        employees = self.container.entityStorage['Employees']
        employees.data['1'] = (
            '1', 'Joe Bloggs', ("The Elms", "Chunton"), b'DEADBEEF')
        orders = self.container.entityStorage['Orders']
        orders.data[1] = (
            1, iso.TimePoint.from_str('2013-08-01T11:05:00'))
        orders.data[2] = (
            2, iso.TimePoint.from_str('2013-08-13T10:26:00'))
        orders.data[3] = (
            3, iso.TimePoint.from_str('2012-05-29T18:13:00'))
        orders.data[4] = (
            4, iso.TimePoint.from_str('2012-05-29T18:13:00'))
        order_lines = self.container.entityStorage['OrderLines']
        order_lines.data[100] = (100, 12, decimal.Decimal('0.45'))
        order_lines.data[200] = (200, 144, decimal.Decimal('2.50'))
        with orders.entity_set.open() as collOrders:
            order = collOrders[1]
            order['Customer'].bind_entity('ALFKI')
            order['OrderLine'].bind_entity(100)
            collOrders.update_entity(order)
            order = collOrders[2]
            order['Customer'].bind_entity('ALFKI')
            order['OrderLine'].bind_entity(200)
            collOrders.update_entity(order)
            order = collOrders[3]
            order['Customer'].bind_entity('XX=00')
            collOrders.update_entity(order)
        documents = self.container.entityStorage['Documents']
        documents.data[300] = (300, 'The Book', 'The Author', None)
        documents.data[301] = (301, 'A Book', 'An Author', None)
        with memds.EntityCollection(entity_set=documents.entity_set,
                                    entity_store=documents) as collection:
            sinfo = core.StreamInfo(type=params.MediaType.from_str(
                "text/plain; charset=iso-8859-1"))
            collection.update_stream(
                io.BytesIO(b"An opening line written in a Caf\xe9"),
                301, sinfo)
        self.xContainer = memds.InMemoryEntityContainer(
            self.ds['SampleModel.ExtraEntities'])
        bits_and_pieces = self.xContainer.entityStorage['BitsAndPieces']
        bits_and_pieces.data[1] = (1, 'blahblah')
        customers_by_city = self.ds[
            'SampleModel.SampleEntities.CustomersByCity']
        customers_by_city.bind(
            CustomersByCityEntityCollection, customers=customers)
        f_last_customer_by_line = self.ds[
            'SampleModel.SampleEntities.LastCustomerByLine']
        f_last_customer_by_line.bind(self.last_customer_by_line)
        shipped_address_by_date = self.ds[
            'SampleModel.SampleEntities.ShippedAddressByDate']
        shipped_address_by_date.bind(
            ShippedAddressByDateCollection, customers_entity_set=self.ds[
                'SampleModel.SampleEntities.Customers'])
        f_last_shipped_by_line = \
            self.ds['SampleModel.SampleEntities.LastShippedByLine']
        f_last_shipped_by_line.bind(self.last_shipped_by_line)
        f_shipped_customer_names_by_date = self.ds[
            'SampleModel.SampleEntities.ShippedCustomerNamesByDate']
        f_shipped_customer_names_by_date.bind(
            ShippedCustomerNamesByDateCollection,
            customers_entity_set=self.ds[
                'SampleModel.SampleEntities.Customers'])
        f_last_customer_by_line = \
            self.ds['SampleModel.SampleEntities.LastCustomerNameByLine']
        f_last_customer_by_line.bind(self.last_customer_name_by_line)

    def last_customer_by_line(self, function, params):
        with self.ds['SampleModel.SampleEntities.Customers'].open() as \
                customers:
            return customers['ALFKI']

    def last_shipped_by_line(self, function, params):
        with self.ds['SampleModel.SampleEntities.Customers'].open() as \
                customers:
            return customers['ALFKI']['Address']

    def last_customer_name_by_line(self, function, params):
        with self.ds['SampleModel.SampleEntities.Customers'].open() as \
                customers:
            return customers['ALFKI']['CompanyName']

    def tearDown(self):     # noqa
        iso.pytime = time

    def test_entity_type_from_atom_entry(self):
        customers = self.ds['SampleModel.SampleEntities.Customers']
        customer = core.Entity(customers)
        customer['CustomerID'].set_from_value('X')
        customer['CompanyName'].set_from_value('Megacorp')
        customer.exists = True
        entry = core.Entry(None, customer)
        self.assertTrue(entry.entityType is None,
                        "Ensure there is no relation to the model here")
        new_customer = core.Entity(customers)
        new_customer.exists = True
        entry.get_value(new_customer)
        self.assertTrue(new_customer['CustomerID'].value == "X",
                        "Check customer ID")
        self.assertTrue(new_customer['CompanyName'].value == "Megacorp",
                        "Check customer name")
        self.assertFalse(new_customer['Address']['Street'], "No street")
        self.assertFalse(new_customer['Address']['City'], "No city")
        self.assertFalse(new_customer['Version'], "No version")
        self.assertTrue(len(new_customer['Orders'].bindings) == 0,
                        "new customer not bound")
        customer.exists = False
        customer['Orders'].bind_entity(1)
        customer['Orders'].bind_entity(2)
        order = core.Entity(self.ds['SampleModel.SampleEntities.Orders'])
        order['OrderID'].set_from_value(3)
        customer['Orders'].bind_entity(order)
        entry = core.Entry(None, customer)
        new_customer = core.Entity(customers)
        new_customer.exists = False
        entry.get_value(new_customer,
                        lambda x: self.svc.get_resource_from_uri(x))
        # now we need to check the bindings, which is a little hard to do
        # without looking inside the box
        self.assertTrue(len(new_customer['Orders'].bindings) == 3,
                        "new customer has 3 orders bound")
        id_links = set()
        entity_link = None
        for binding in new_customer['Orders'].bindings:
            if isinstance(binding, core.Entity):
                if binding.exists:
                    id_links.add(binding.key())
                else:
                    entity_link = binding
            else:
                id_links.add(binding)
        self.assertTrue(1 in id_links, "OrderID=1 is bound")
        self.assertTrue(2 in id_links, "OrderID=2 is bound")
        self.assertTrue(entity_link['OrderID'] == 3, "OrderID 3 loaded")
        self.assertFalse(entity_link.exists, "OrderID 3 does not exist")
        #
        # End of customer tests
        #
        employees = self.ds['SampleModel.SampleEntities.Employees']
        employee = core.Entity(employees)
        employee['EmployeeID'].set_from_value('12345')
        employee['EmployeeName'].set_from_value('Joe Bloggs')
        employee['Address']['City'].set_from_value('Chunton')
        entry = core.Entry(None, employee)
        self.assertTrue(entry.entityType is None,
                        "Ensure there is no relation to the model here")
        new_employee = entry.get_value(core.Entity(employees))
        self.assertTrue(new_employee['EmployeeID'].value == "12345",
                        "Check employee ID")
        self.assertTrue(new_employee['EmployeeName'].value == "Joe Bloggs",
                        "Check employee name")
        self.assertFalse(new_employee['Address']['Street'], "No street")
        self.assertTrue(new_employee['Address']['City'] == "Chunton",
                        "Check employee city")
        self.assertFalse(new_employee['Version'], "No version")
        documents = self.ds['SampleModel.SampleEntities.Documents']
        documents.bind(MockDocumentCollection)
        document = core.Entity(documents)
        document['DocumentID'].set_from_value(1801)
        document['Title'].set_from_value('War and Peace')
        document['Author'].set_from_value('Tolstoy')
        h = hashlib.sha256()
        h.update(DOCUMENT_TEXT)
        document['Version'].set_from_value(h.digest())
        entry = core.Entry(None, document)
        self.assertTrue(entry.entityType is None,
                        "Ensure there is no relation to the model here")
        new_document = entry.get_value(core.Entity(documents))
        self.assertTrue(new_document['DocumentID'].value == 1801,
                        "Check document ID")
        self.assertTrue(new_document['Title'].value == "War and Peace",
                        "Check document name")
        self.assertTrue(new_document['Author'] == "Tolstoy",
                        "Check author name")
        self.assertTrue(new_document['Version'].value == h.digest(),
                        "Mismatched version")

    def test_evaluate_first_member_expression(self):
        """Back-track a bit to test some basic stuff using the sample
        data set.

        ...the memberExpression can reference an Entity Navigation
        property, or an Entity Complex type property, or an Entity
        Simple Property, the target relationship end must have a
        cardinality of 1 or 0..1.

        The type of the result of evaluating the memberExpression MUST
        be the same type as the property reference in the
        memberExpression.

        ...a data service MUST return null if any of the
        NavigationProperties are null."""
        orders = self.ds['SampleModel.SampleEntities.Orders']
        order = orders.open()[1]
        # Simple Property
        p = core.Parser("OrderID")
        e = p.parse_common_expression()
        value = e.evaluate(order)
        self.assertTrue(value.type_code == edm.SimpleType.Int32,
                        "Expected Int32")
        self.assertTrue(value.value == 1, "Expected 1")
        customers = self.ds['SampleModel.SampleEntities.Customers']
        # customers.data['ALFKI'] =
        #       ('ALFKI','Example Inc', ("Mill-Road", "Chunton"), None)
        customer = customers.open()['ALFKI']
        # Complex Property
        p = core.Parser("Address")
        e = p.parse_common_expression()
        value = e.evaluate(customer)
        self.assertTrue(isinstance(value, edm.Complex),
                        "Expected Complex value")
        self.assertTrue(value['City'].value == 'Chunton', "Expected Chunton")
        # Simple Property (NULL)
        customer00 = customers.open()['XX=00']
        p = core.Parser("Version")
        e = p.parse_common_expression()
        value = e.evaluate(customer00)
        self.assertTrue(
            value.type_code == edm.SimpleType.Binary, "Expected Binary")
        self.assertTrue(value.value is None, "Expected NULL")
        # Navigation property
        p = core.Parser("Customer")
        e = p.parse_common_expression()
        value = e.evaluate(order)
        self.assertTrue(isinstance(value, edm.Entity), "Expected Entity")
        self.assertTrue(value['CustomerID'].value == 'ALFKI',
                        "Expected Customer('ALFKI')")
        # Navigation property with Null
        value = e.evaluate(orders.open()[4])
        self.assertTrue(
            isinstance(value, edm.SimpleValue),
            "Expected SimpleValue (for NULL) found %s" % repr(value))
        self.assertFalse(value, "Expected NULL")
        # Navigation property with multiple cardinality
        p = core.Parser("Orders")
        e = p.parse_common_expression()
        try:
            value = e.evaluate(customer)
            self.fail("Navigation property cardinality")
        except core.EvaluationError:
            pass

    def test_evaluate_member_expression(self):
        """the target of the memberExpression MUST be a known Edm Entity
        or ComplexType.

        the memberExpression can reference an entity NavigationProperty,
        or an Entity Complex type property, or an Entity Simple
        Property.

        For entity NavigationProperties, the target relationship end
        must have a cardinality of 1 or 0..1.

        The type of the result of evaluating the memberExpression MUST
        be the same type as the property reference in the
        memberExpression.

        ...a data service MUST return null if any of the
        NavigationProperties are null."""
        orders = self.ds['SampleModel.SampleEntities.Orders']
        order = orders.open()[1]
        order3 = orders.open()[3]
        # Known Entity: SimpleProperty
        p = core.Parser("Customer/CustomerID")
        e = p.parse_common_expression()
        value = e.evaluate(order)
        self.assertTrue(
            value.type_code == edm.SimpleType.String, "Expected string")
        self.assertTrue(value.value == 'ALFKI', "Expected 'ALKFI'")
        # Known ComplexType: SimpleProperty
        p = core.Parser("Customer/Address/City")
        e = p.parse_common_expression()
        value = e.evaluate(order)
        self.assertTrue(
            value.type_code == edm.SimpleType.String, "Expected string")
        self.assertTrue(value.value == 'Chunton', "Expected 'Chunton'")
        # TODO: a two step navigation, sample data doesn't have one yet
        # navigation / navigation
        # Simple Property (NULL)
        p = core.Parser("Customer/Version")
        e = p.parse_common_expression()
        value = e.evaluate(order3)
        self.assertTrue(
            value.type_code == edm.SimpleType.Binary, "Expected Binary")
        self.assertTrue(value.value is None, "Expected NULL")
        # Navigation property with multiple cardinality
        p = core.Parser("Customer/Orders")
        e = p.parse_common_expression()
        try:
            value = e.evaluate(order)
            self.fail("Navigation property cardinality")
        except core.EvaluationError:
            pass

    def test_evaluate_eq_expression(self):
        """Equality of EntityType instances is harder to test than you
        think, the only way to get an expression to evaluate to an
        entity instance is through a navigation property."""
        orders = self.ds['SampleModel.SampleEntities.Orders']
        order = orders.open()[1]
        # Known Entity: SimpleProperty
        p = core.Parser("Customer eq Customer")
        e = p.parse_common_expression()
        value = e.evaluate(order)
        self.assertTrue(
            value.type_code == edm.SimpleType.Boolean, "Expected boolean")
        self.assertTrue(value.value is True, "Expected True")
        p = core.Parser("Customer eq OrderLine")
        e = p.parse_common_expression()
        value = e.evaluate(order)
        self.assertTrue(value.value is False, "Expected False")

    def test_service_root(self):
        """The resource identified by [the service root] ... MUST be an
        AtomPub Service Document.

        The ServiceRoot of a data service MUST identify the Service
        Document for the data service.

        AtomPub Service Documents MUST be identified with the
        "application/atomsvc+xml" media type.

        JSON Service Documents MUST be identified using the
        "application/json" media type."""
        request = MockRequest('/service.svc')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 307)
        self.assertTrue(request.responseHeaders['LOCATION'] ==
                        'http://host/service.svc/', "Expected redirect")
        request = MockRequest('/service.svc/')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200,
                        "Service root response: %i" % request.responseCode)
        self.assertTrue(
            request.responseHeaders['CONTENT-TYPE'] ==
            'application/atomsvc+xml', "Expected application/atomsvc+xml")
        doc = app.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, app.Service),
                        "Service root not an app.Service")
        self.assertTrue(len(doc.root.Workspace) == 1,
                        "Sample server has 1 workspace")
        # a data service MUST represent each EntitySet ...as an
        # <app:collection> element
        self.assertTrue(len(doc.root.Workspace[0].Collection) == 9,
                        "Sample service has 9 entity sets")
        # The URI identifying the EntitySet MUST be used as the value
        # of the "href" attribute of the <app:collection> element
        feeds = set()
        for c in doc.root.Workspace[0].Collection:
            # The name of the EntitySet can be used as the value of
            # the <atom:title>... child element of the
            # <app:collection> element
            self.assertTrue(c.Title.get_value() == c.href)
            feeds.add(str(c.href))
        for r in ("Customers", "Orders", "OrderLines", "Employees",
                  "Documents", "ExtraEntities.Content",
                  "ExtraEntities.BitsAndPieces"):
            self.assertTrue(r in feeds, "Missing feed: %s" % r)
        request = MockRequest('/service.svc/')
        request.set_header('Accept', "application/json")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200,
                        "Service root response: %i" % request.responseCode)
        self.assertTrue(request.responseHeaders['CONTENT-TYPE'] ==
                        'application/json', "Expected application/json")
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(obj) == 1 and "d" in obj,
                        "JSON object is security wrapped")
        obj = obj["d"]
        self.assertTrue("EntitySets" in obj)
        self.assertTrue(isinstance(obj["EntitySets"], list))
        self.assertTrue(len(obj["EntitySets"]) == 9)
        for c in obj["EntitySets"]:
            self.assertTrue(is_unicode(c))

    def test_entity_set1(self):
        """EntitySet names MAY be directly followed by open and close
        parenthesis."""
        request1 = MockRequest('/service.svc/Customers')
        request2 = MockRequest('/service.svc/Customers()')
        request1.send(self.svc)
        request2.send(self.svc)
        self.assertTrue(request1.responseCode == 200)
        self.assertTrue(request2.responseCode == 200)
        doc1 = app.Document()
        doc1.read(request1.wfile.getvalue())
        doc2 = app.Document()
        doc2.read(request2.wfile.getvalue())
        output = doc1.diff_string(doc2)
        self.assertTrue(request1.wfile.getvalue() == request2.wfile.getvalue(
        ), "Mismatched responses with (): \n%s" % (output))

    def test_entity_set2(self):
        """If an EntitySet is not in the default EntityContainer, then
        the URI MUST qualify the EntitySet name with the EntityContainer
        name.

        Although not explicitly stated, it seems that an entity set MUST
        NOT be prefixed with the container name if it is in the default
        EntityContainer.  Witness the error from
        http://services.odata.org/OData/OData.svc/DemoService.Products"""
        request = MockRequest('/service.svc/Content')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 404,
                        "Unqualified entity set from non-default container")
        request = MockRequest('/service.svc/ExtraEntities.Content')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200,
                        "Qualified entity set from non-default container")
        request = MockRequest('/service.svc/SampleEntities.Customers')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 404,
                        "Qualified entity set from default container")

    def test_entity_property(self):
        """If the prior URI path segment identifies an EntityType
        instance in EntitySet ES1, this value MUST be the name of a
        declared property or dynamic property, of type EDMSimpleType, on
        the base EntityType of set ES1

        If the prior URI path segment represents an instance of
        ComplexType CT1, this value MUST be the name of a declared
        property defined on ComplexType CT1."""
        request = MockRequest("/service.svc/Customers('ALFKI')/CompanyName")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        # Add test case of a property on a sub-type perhaps?
        request = MockRequest("/service.svc/Customers('ALFKI')/Title")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 404)
        request = MockRequest("/service.svc/Customers('ALFKI')/Address/Street")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        request = MockRequest(
            "/service.svc/Customers('ALFKI')/Address/ZipCode")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 404)

    def test_complex_property(self):
        """If the prior URI path segment identifies an instance of an
        EntityType ET1, this value MUST be the name of a declared
        property or dynamic property on type ET1 which represents a
        ComplexType instance.

        If the prior URI path segment identifies an instance of a
        ComplexType CT1, this value MUST be the name of a declared
        property on CT1 which represents a ComplexType instance."""
        request = MockRequest("/service.svc/Customers('ALFKI')/Address")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        # TODO: sample data doesn't have any nested Complex properties

    def test_nav_property(self):
        """If the prior URI path segment identifies an instance of an
        EntityType ET1, this value MUST be the name of a
        NavigationProperty on type ET1.

        If the URI path segment preceding an entityNavProperty segment
        is "$links", then there MUST NOT be any subsequent path segments
        in the URI after the entityNavProperty. If additional segments
        exist, the URI MUST be treated as invalid"""
        request = MockRequest("/service.svc/Customers('ALFKI')/Orders")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        request = MockRequest("/service.svc/Customers('ALFKI')/$links/Orders")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        request = MockRequest(
            "/service.svc/Customers('ALFKI')/$links/Orders/dummy")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 400)

    def test_key_predicate_single(self):
        """An EntityKey consisting of a single EntityType property MAY
        be represented using the "<Entity Type property name> = <Entity
        Type property value>" syntax"""
        request1 = MockRequest("/service.svc/Customers('ALFKI')")
        request2 = MockRequest("/service.svc/Customers(CustomerID='ALFKI')")
        request1.send(self.svc)
        request2.send(self.svc)
        self.assertTrue(request1.responseCode == 200)
        self.assertTrue(request2.responseCode == 200)
        self.assertTrue(request1.wfile.getvalue() == request2.wfile.getvalue(),
                        "Mismatched responses with ()")

    def test_key_predicate_complex(self):
        """The order in which the properties of a compound EntityKey appear in
        the URI MUST NOT be significant"""
        # TODO, sample data has no compound keys
        pass

    def test_uri1(self):
        """URI1 = scheme serviceRoot "/" entitySet

        [URI1] MUST identify all instances of the base EntityType or any
        of the EntityType's subtypes within the specified EntitySet
        specified in the last URI segment."""
        request = MockRequest('/service.svc/Customers')
        request.send(self.svc)
        doc = app.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, atom.Feed),
                        "Expected atom.Feed from /Customers")
        self.assertTrue(
            len(doc.root.Entry) == 91, "Sample server has 91 Customers")
        # the serviceOperation-collEt rule can be substituted for the
        # first occurrence of an entitySet rule in the Resource Path
        request = MockRequest("/service.svc/CustomersByCity?city='Chunton'")
        request.send(self.svc)
        doc = app.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, atom.Feed),
                        "Expected atom.Feed from /CustomersByCity")
        self.assertTrue(len(doc.root.Entry) == 1,
                        "Sample server has 1 Customer in Chunton")
        # If the Entity Data Model... ...does not include an EntitySet
        # with the name specified, the this URI (and any URI created by
        # appending additional path segments) MUST be treated as
        # identifying a non-existent resource.
        request = MockRequest("/service.svc/Prospects")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 404)
        request = MockRequest("/service.svc/Prospects/$count")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 404)
        # all system query options are valid
        request = MockRequest(
            "/service.svc/Customers?$expand=Orders&"
            "$filter=substringof(CompanyName,%20'bikes')&"
            "$orderby=CompanyName%20asc&$top=2&$skip=3&"
            "$skiptoken='Contoso','AKFNU'&$inlinecount=allpages&"
            "$select=CustomerID,CompanyName,Orders&$format=xml")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)

    def test_uri2(self):
        """URI2 = scheme serviceRoot "/" entitySet "(" keyPredicate ")"

        MUST identify a single EntityType instance, which is within the
        EntitySet specified in the URI, where key EntityKey is equal to
        the value of the keyPredicate specified.

        If no entity identified by the keyPredicate exists in the
        EntitySet specified, then this URI (and any URI created by
        appending additional path segments) MUST represent a resource
        that does not exist in the data model"""
        request = MockRequest("/service.svc/Customers('ALFKI')")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(
            isinstance(doc.root, core.Entry),
            "Expected a single Entry, found %s" % doc.root.__class__.__name__)
        self.assertTrue(doc.root['CustomerID'] == 'ALFKI', "Bad CustomerID")
        request = MockRequest("/service.svc/Customers('ALFKJ')")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 404)
        request = MockRequest("/service.svc/Customers('ALFKJ')/Address")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 404)
        # $orderby, $skip, $top, $skiptoken, $inlinecount all banned
        base_uri = "/service.svc/Customers('ALFKI')?$expand=Orders&"\
            "$filter=substringof(CompanyName,%20'bikes')&"\
            "$select=CustomerID,CompanyName,Orders&$format=xml"
        request = MockRequest(base_uri)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        for x in ["$orderby=CompanyName%20asc", "$skip=3", "$top=2",
                  "$skiptoken='Contoso','AKFNU'", "$inlinecount=allpages"]:
            request = MockRequest(base_uri + "&" + x)
            request.send(self.svc)
            self.assertTrue(request.responseCode == 400, "URI2 with %s" % x)

    def test_uri3(self):
        """URI3 = scheme serviceRoot "/" entitySet "(" keyPredicate ")/"
            entityComplexProperty

        MUST identify an instance of a ComplexType on the specified
        EntityType instance."""
        request = MockRequest("/service.svc/Customers('ALFKI')/Address")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, core.Property),
                        "Expected a single Property, found %s" %
                        doc.root.__class__.__name__)
        value = doc.root.get_value()
        self.assertTrue(
            value['Street'] == 'Mill Road', "Bad street in address")
        # $expand, $orderby, $skip, $top, $skiptoken, $inlinecount and
        # $select all banned
        base_uri = "/service.svc/Customers('ALFKI')/Address?"\
            "$filter=substringof(CompanyName,%20'bikes')&$format=xml"
        request = MockRequest(base_uri)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        for x in ["$expand=Orders", "$orderby=CompanyName%20asc", "$skip=3",
                  "$top=2", "$skiptoken='Contoso','AKFNU'",
                  "$inlinecount=allpages",
                  "$select=CustomerID,CompanyName,Orders"]:
            request = MockRequest(base_uri + "&" + x)
            request.send(self.svc)
            self.assertTrue(request.responseCode == 400, "URI3 with %s" % x)

    def test_uri4(self):
        """URI4 = scheme serviceRoot "/" entitySet "(" keyPredicate ")/"
            entityComplexProperty "/" entityProperty

        MUST identify a property of a ComplexType defined on the
        EntityType of the entity whose EntityKey value is specified by
        the keyPredicate and is within the specified EntitySet."""
        request = MockRequest("/service.svc/Customers('ALFKI')/Address/Street")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, core.Property),
                        "Expected a single Property, found %s" %
                        doc.root.__class__.__name__)
        value = doc.root.get_value()
        self.assertTrue(value.value == 'Mill Road', "Bad street")
        request = MockRequest(
            "/service.svc/Customers('ALFKI')/Address/Street/$value")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.wfile.getvalue() == b'Mill Road', "Bad street $vaue")
        base_uri = "/service.svc/Customers('ALFKI')/Address/Street?$format=xml"
        request = MockRequest(base_uri)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        for x in ["$expand=Orders", "$orderby=CompanyName%20asc",
                  "$filter=substringof(CompanyName,%20'bikes')", "$skip=3",
                  "$top=2", "$skiptoken='Contoso','AKFNU'",
                  "$inlinecount=allpages",
                  "$select=CustomerID,CompanyName,Orders"]:
            request = MockRequest(base_uri + "&" + x)
            request.send(self.svc)
            self.assertTrue(request.responseCode == 400, "URI4 with %s" % x)

    def test_uri5(self):
        """URI5 = scheme serviceRoot "/" entitySet "(" keyPredicate ")/"
            entityProperty

        MUST identify a property whose type is an EDMSimpleType on the
        EntityType instance (identified with EntityKey equal to the
        specified key predicate) within the specified EntitySet"""
        request = MockRequest("/service.svc/Customers('ALFKI')/CompanyName")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, core.Property),
                        "Expected a single Property, found %s" %
                        doc.root.__class__.__name__)
        value = doc.root.get_value()
        self.assertTrue(value.value == 'Example Inc', "Bad company")
        request = MockRequest(
            "/service.svc/Customers('ALFKI')/CompanyName/$value")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.wfile.getvalue() == b'Example Inc', "Bad company $vaue")
        base_uri = "/service.svc/Customers('ALFKI')/CompanyName?$format=xml"
        request = MockRequest(base_uri)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        for x in ["$expand=Orders", "$orderby=CompanyName%20asc",
                  "$filter=substringof(CompanyName,%20'bikes')", "$skip=3",
                  "$top=2", "$skiptoken='Contoso','AKFNU'",
                  "$inlinecount=allpages",
                  "$select=CustomerID,CompanyName,Orders"]:
            request = MockRequest(base_uri + "&" + x)
            request.send(self.svc)
            self.assertTrue(request.responseCode == 400, "URI5 with %s" % x)
        """Any media type is a valid value for [the MimeType] attribute.
        If this attribute is present on a property definition, then any
        RetreiveValue Request for the property MUST return a response
        which uses the specified mime type as the content type of the
        response body."""
        request = MockRequest(
            "/service.svc/ExtraEntities.BitsAndPieces(1)/Details/$value")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['CONTENT-TYPE'] == "application/x-details")
        self.assertTrue(
            request.wfile.getvalue() == b'blahblah', "Bad details $value")

    def test_uri6(self):
        """URI6 = scheme serviceRoot "/" entitySet "(" keyPredicate ")/"
            entityNavProperty

        MUST identify a set of entities or an EntityType instance that
        is reached via the specified NavigationProperty on the entity
        identified by the EntitySet name and key predicate specified."""
        request = MockRequest("/service.svc/Customers('ALFKI')/Orders")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, atom.Feed),
                        "Expected atom.Feed from navigation property Orders")
        self.assertTrue(
            len(doc.root.Entry) == 2, "Sample customer has 2 orders")
        # TODO: navigation property pointing to a single Entity (Note 1)
        # base_uri = "/service.svc/Customers('ALFKI')/Orders?$expand=Orders&"\
        #     "$filter=substringof(CompanyName,%20'bikes')&$format=xml&"\
        #     "$select=CustomerID,CompanyName,Orders"
        # request = MockRequest(base_uri)
        # request.send(self.svc)
        # self.assertTrue(request.responseCode==200)
        # for x in ["$orderby=CompanyName%20asc", "$skip=3","$top=2",
        #           "$skiptoken='Contoso','AKFNU'", "$inlinecount=allpages"]:
        #     request = MockRequest(base_uri+"&" + x)
        #     request.send(self.svc)
        #     self.assertTrue(request.responseCode==400, "UR6 with %s" % x)
        # all system query options are valid when the navigation
        # property identifies a set of entities (Note 2)
        request = MockRequest(
            "/service.svc/Customers?$expand=Orders&"
            "$filter=substringof(CompanyName,%20'bikes')&"
            "$orderby=CompanyName%20asc&$top=2&$skip=3&"
            "$skiptoken='Contoso','AKFNU'&$inlinecount=allpages&"
            "$select=CustomerID,CompanyName,Orders&$format=xml")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)

    def test_uri7(self):
        """URI7 = scheme serviceRoot "/" entitySet "(" keyPredicate
            ")/$links/" entityNavProperty

        MUST identify the collection of all Links from the specified
        EntityType instance (identified by the EntitySet name and key
        predicate specified) to all other entities that can be reached
        via the Navigation Property"""
        request = MockRequest("/service.svc/Customers('ALFKI')/$links/Orders")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, core.Links),
                        "Expected Links from $links request, found %s" %
                        doc.root.__class__.__name__)
        self.assertTrue(len(doc.root.URI) == 2, "Sample customer has 2 orders")
        # test json output
        request = MockRequest("/service.svc/Customers('ALFKI')/$links/Orders?"
                              "$inlinecount=allpages&$top=1")
        request.set_header('Accept', "application/json")
        request.send(self.svc)
        self.assertTrue(
            request.responseHeaders['CONTENT-TYPE'] == "application/json")
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(
            obj) == 1 and "d" in obj, "JSON object is security wrapped")
        obj = obj["d"]
        self.assertTrue(
            isinstance(obj, dict), "Version 2 JSON response is object")
        self.assertTrue("__count" in obj and obj["__count"] == 2,
                        "Version 2 JSON supports $inlinecount")
        self.assertTrue("results" in obj,
                        "Version 2 JSON response has 'results'")
        self.assertTrue(isinstance(obj["results"], list), "list of links")
        self.assertTrue(
            len(obj["results"]) == 1,
            "Sample customer has 2 orders but only 1 returned due to $top")
        for link in obj["results"]:
            self.assertTrue(isinstance(link, dict), "link is object")
            self.assertTrue("uri" in link, "link has 'link' propert")
        # similar test but force a version 1 response
        request = MockRequest("/service.svc/Customers('ALFKI')/$links/Orders")
        request.set_header('Accept', "application/json")
        request.set_header('MaxDataServiceVersion', "1.0; old max")
        request.send(self.svc)
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(obj) == 1 and "d" in obj,
                        "JSON object is security wrapped")
        obj = obj["d"]
        self.assertTrue(isinstance(obj, list),
                        "Version 1 JSON response is array")
        self.assertTrue(len(obj) == 2, "2 links in response")
        # end of json tests
        request = MockRequest("/service.svc/Orders(1)/$links/Customer")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(
            isinstance(doc.root, core.URI), "Expected URI from $links request")
        self.assertTrue(
            doc.root.get_value() ==
            "http://host/service.svc/Customers('ALFKI')", "Bad Customer link")
        base_uri = "/service.svc/Customers('ALFKI')/$links/Orders?"\
            "$format=xml&$skip=3&$top=2&$skiptoken='Contoso','AKFNU'&"\
            "$inlinecount=allpages"
        request = MockRequest(base_uri)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        for x in ["$expand=Orders",
                  "$filter=substringof(CompanyName,%20'bikes')",
                  "$orderby=CompanyName%20asc",
                  "$select=CustomerID,CompanyName,Orders"]:
            request = MockRequest(base_uri + "&" + x)
            request.send(self.svc)
            self.assertTrue(request.responseCode == 400, "URI7 with %s" % x)

    def test_uri8(self):
        """URI8 = scheme serviceRoot "/$metadata"

        All data services SHOULD expose a conceptual schema definition
        language (CSDL) based metadata endpoint that...

        MUST identify the Entity Data Model Extensions (EDMX) document,
        as specified in [MC-EDMX], which includes the Entity Data Model
        represented using a conceptual schema definition language
        (CSDL), as specified in [MC-CSDL], for the data service."""
        request = MockRequest("/service.svc/$metadata")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = edmx.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, edmx.Edmx),
                        "Expected Edmx from $metadata request, found %s" %
                        doc.root.__class__.__name__)
        version = doc.validate()
        # MimeType: This attribute MUST be used on a <Property>
        # element... Each <Property> element defining an EDMSimpleType
        # property MAY<48> include exactly one occurrence of this
        # attribute. Any media type (see [IANA-MMT] ) is a valid value
        # for this attribute.
        ptype = doc.root.DataServices["SampleModel.BitsAndPieces.Details"]
        mtype = params.MediaType.from_str(ptype.get_attribute(core.MIME_TYPE))
        self.assertTrue(mtype == "application/x-details",
                        "Expected x-details MimeType")
        self.assertTrue(version == "2.0", "Expected data service version 2.0")
        base_uri = "/service.svc/$metadata?"
        request = MockRequest(base_uri)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        for x in ["$expand=Orders",
                  "$filter=substringof(CompanyName,%20'bikes')",
                  "$format=xml",
                  "$orderby=CompanyName%20asc",
                  "$skip=3",
                  "$top=2",
                  "$skiptoken='Contoso','AKFNU'",
                  "$inlinecount=allpages",
                  "$select=CustomerID,CompanyName,Orders"]:
            request = MockRequest(base_uri + x)
            request.send(self.svc)
            self.assertTrue(request.responseCode == 400, "URI8 with %s" % x)

    def test_uri9(self):
        """URI9 = scheme serviceRoot "/$batch"

        MUST identify the endpoint of a data service which accepts Batch
        Requests.

        ...If a data service does not implement support for a Batch
        Request, it must return a 4xx response code in the response to
        any Batch Request sent to it."""
        request = MockRequest("/service.svc/$batch")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 404)
        base_uri = "/service.svc/$batch?"
        request = MockRequest(base_uri)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 404)
        for x in ["$expand=Orders",
                  "$filter=substringof(CompanyName,%20'bikes')",
                  "$format=xml",
                  "$orderby=CompanyName%20asc",
                  "$skip=3",
                  "$top=2",
                  "$skiptoken='Contoso','AKFNU'",
                  "$inlinecount=allpages",
                  "$select=CustomerID,CompanyName,Orders"]:
            request = MockRequest(base_uri + x)
            request.send(self.svc)
            self.assertTrue(request.responseCode == 400, "URI9 with %s" % x)

    def test_uri10(self):
        """URI10 = scheme serviceRoot "/" serviceOperation-et

        MUST identify a FunctionImport that returns a single EntityType
        instance.

        If no FunctionImport exists in the Entity Data Model associated
        with the data service which has the same name as specified by
        the serviceOperation-et rule, then this URI MUST represent a
        resource that does not exist in the data model.

        If [the HttpMethod] attribute is present, the FunctionImport
        must be callable using the HTTP method specified."""
        # TODO, an actual function that does something that returns a single
        # entity
        request = MockRequest("/service.svc/LastCustomerByLine?line=1")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        request = MockRequest("/service.svc/FirstCustomerByLine?line=1")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 404)
        base_uri = "/service.svc/LastCustomerByLine?line=1&$format=xml"
        request = MockRequest(base_uri)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        for x in ["$expand=Orders",
                  "$filter=substringof(CompanyName,%20'bikes')",
                  "$orderby=CompanyName%20asc",
                  "$skip=3",
                  "$top=2",
                  "$skiptoken='Contoso','AKFNU'",
                  "$inlinecount=allpages",
                  "$select=CustomerID,CompanyName,Orders"]:
            request = MockRequest(base_uri + "&" + x)
            request.send(self.svc)
            self.assertTrue(request.responseCode == 400, "URI10 with %s" % x)
        # TODO, a function import that uses a method other than GET

    def test_uri11(self):
        """URI11 = scheme serviceRoot "/" serviceOperation-collCt

        MUST identify a FunctionImport which returns a collection of
        ComplexType instances.

        If no FunctionImport exists in the Entity Data Model associated
        with the data service that has the same name as specified by the
        serviceOperation-collCt rule, then this URI MUST represent a
        resource that does not exist in the data model."""
        # TODO, an actual function that does something that returns a
        # collection of addresses
        request = MockRequest("/service.svc/ShippedAddressByDate?"
                              "date=datetime'2013-08-02T00:00'")
        request.set_header('Accept', "application/json")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        # check json output
        self.assertTrue(request.responseHeaders['CONTENT-TYPE'] ==
                        "application/json")
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(obj) == 1 and "d" in obj,
                        "JSON object is security wrapped")
        obj = obj["d"]
        # should be version 2 output
        self.assertTrue("results" in obj, "Expected version 2 JSON output")
        i = 0
        fake_p = edm.Property(None)
        fake_p.complexType = self.ds['SampleModel.CAddress']
        for ct in obj["results"]:
            # should be a complex type
            c = edm.Complex(fake_p)
            core.complex_property_from_json(c, obj)
            if c['Street'] == "Mill Road":
                self.assertTrue(c['City'] == "Chunton")
            else:
                self.assertFalse(c['City'], "Unknown address")
            i = i + 1
        # check version 1 json output
        request = MockRequest("/service.svc/ShippedAddressByDate?"
                              "date=datetime'2013-08-02T00:00'")
        request.set_header('Accept', "application/json")
        request.set_header('MaxDataServiceVersion', "1.0; old max")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['CONTENT-TYPE'] == "application/json")
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(
            obj) == 1 and "d" in obj, "JSON object is security wrapped")
        obj = obj["d"]
        self.assertTrue(
            isinstance(obj, list), "Expected version 1 JSON output")
        self.assertTrue(len(obj) == i, "Expected same number of results")
        # End of JSON tests
        request = MockRequest("/service.svc/PendingAddressByDate?"
                              "date=datetime'2013-08-02T00:00'")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 404)
        base_uri = "/service.svc/ShippedAddressByDate?"\
            "date=datetime'2013-08-02T00:00'&$format=xml"
        request = MockRequest(base_uri)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        for x in ["$expand=Orders",
                  "$filter=substringof(CompanyName,%20'bikes')",
                  "$orderby=CompanyName%20asc",
                  "$skip=3",
                  "$top=2",
                  "$skiptoken='Contoso','AKFNU'",
                  "$inlinecount=allpages",
                  "$select=CustomerID,CompanyName,Orders"]:
            request = MockRequest(base_uri + "&" + x)
            request.send(self.svc)
            self.assertTrue(request.responseCode == 400, "URI11 with %s" % x)

    def test_uri12(self):
        """URI12 = scheme serviceRoot "/" serviceOperation-ct

        MUST identify a FunctionImport which returns a ComplexType
        instance.

        If no FunctionImport exists in the Entity Data Model associated
        with the data service that has the same name as specified by the
        serviceOperation-ct rule, then this URI MUST represent a
        resource that does not exist in the data model."""
        # TODO, an actual function that does something that returns a single
        # entity
        request = MockRequest("/service.svc/LastShippedByLine?line=1")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        request = MockRequest("/service.svc/FirstShippedByLine?line=1")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 404)
        base_uri = "/service.svc/LastShippedByLine?line=1&$format=xml"
        request = MockRequest(base_uri)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        for x in ["$expand=Orders",
                  "$filter=substringof(CompanyName,%20'bikes')",
                  "$orderby=CompanyName%20asc",
                  "$skip=3",
                  "$top=2",
                  "$skiptoken='Contoso','AKFNU'",
                  "$inlinecount=allpages",
                  "$select=CustomerID,CompanyName,Orders"]:
            request = MockRequest(base_uri + "&" + x)
            request.send(self.svc)
            self.assertTrue(request.responseCode == 400, "URI12 with %s" % x)

    def test_uri13(self):
        """URI13 = scheme serviceRoot "/" serviceOperation-collPrim

        MUST identify a FunctionImport which returns a collection of
        Primitive type values

        If no FunctionImport exists in the Entity Data Model associated
        with the data service that has the same name as specified by the
        serviceOperation-collPrim rule, then this URI MUST represent a
        resource that does not exist in the data model."""
        request = MockRequest("/service.svc/ShippedCustomerNamesByDate?"
                              "date=datetime'2013-08-02T00:00'")
        request.set_header('Accept', "application/json")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        # check json version 2 ouptput
        self.assertTrue(
            request.responseHeaders['CONTENT-TYPE'] == "application/json")
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(
            obj) == 1 and "d" in obj, "JSON object is security wrapped")
        obj = obj["d"]
        # should be version 2 output
        self.assertTrue("results" in obj, "Expected version 2 JSON output")
        i = 0
        for prim in obj["results"]:
            # should be a simple type
            v = edm.StringValue()
            core.simple_value_from_json(v, prim)
            i = i + 1
        # check version 1 json output
        request = MockRequest("/service.svc/ShippedCustomerNamesByDate?"
                              "date=datetime'2013-08-02T00:00'")
        request.set_header('Accept', "application/json")
        request.set_header('MaxDataServiceVersion', "1.0; old max")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['CONTENT-TYPE'] == "application/json")
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(
            obj) == 1 and "d" in obj, "JSON object is security wrapped")
        obj = obj["d"]
        self.assertTrue(
            isinstance(obj, list), "Expected version 1 JSON output")
        self.assertTrue(len(obj) == i, "Expected same number of results")
        # End of JSON tests
        request = MockRequest("/service.svc/PendingCustomerNamesByDate?"
                              "date=datetime'2013-08-02T00:00'")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 404)
        base_uri = "/service.svc/ShippedCustomerNamesByDate?"\
            "date=datetime'2013-08-02T00:00'&$format=xml"
        request = MockRequest(base_uri)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        for x in ["$expand=Orders",
                  "$filter=substringof(CompanyName,%20'bikes')",
                  "$orderby=CompanyName%20asc",
                  "$skip=3",
                  "$top=2",
                  "$skiptoken='Contoso','AKFNU'",
                  "$inlinecount=allpages",
                  "$select=CustomerID,CompanyName,Orders"]:
            request = MockRequest(base_uri + "&" + x)
            request.send(self.svc)
            self.assertTrue(request.responseCode == 400, "URI13 with %s" % x)

    def test_uri14(self):
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
        # TODO, an actual function that does something that returns a single
        # entity
        request = MockRequest("/service.svc/LastCustomerNameByLine?line=1")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        request = MockRequest(
            "/service.svc/LastCustomerNameByLine/$value?line=1")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        request = MockRequest("/service.svc/FirstCustomerNameByLine?line=1")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 404)
        base_uri = "/service.svc/LastCustomerNameByLine?line=1&$format=xml"
        request = MockRequest(base_uri)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        for x in ["$expand=Orders",
                  "$filter=substringof(CompanyName,%20'bikes')",
                  "$orderby=CompanyName%20asc",
                  "$skip=3",
                  "$top=2",
                  "$skiptoken='Contoso','AKFNU'",
                  "$inlinecount=allpages",
                  "$select=CustomerID,CompanyName,Orders"]:
            request = MockRequest(base_uri + "&" + x)
            request.send(self.svc)
            self.assertTrue(request.responseCode == 400, "URI14 with %s" % x)

    def test_uri15(self):
        """URI15 = scheme serviceRoot "/" entitySet count

        MUST identify the count of all instances of the base EntityType
        or any of the EntityType's subtypes within the specified
        EntitySet specified in the last URI segment"""
        request = MockRequest('/service.svc/Customers/$count')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(request.wfile.getvalue() == b"91",
                        "Sample server has 91 Customers")
        base_uri = "/service.svc/Customers/$count?$expand=Orders&"\
            "$filter=substringof(CompanyName,%20'bikes')&"\
            "$orderby=CompanyName%20asc&$skip=3&$top=2"
        request = MockRequest(base_uri)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        for x in ["$format=xml",
                  "$skiptoken='Contoso','AKFNU'",
                  "$inlinecount=allpages",
                  "$select=CustomerID,CompanyName,Orders"]:
            request = MockRequest(base_uri + "&" + x)
            request.send(self.svc)
            self.assertTrue(request.responseCode == 400, "URI15 with %s" % x)

    def test_uri16(self):
        """URI16 = scheme serviceRoot "/" entitySet "(" keyPredicate ")"
            count

        MAY identify the count of a single EntityType instance (the
        count value SHOULD always equal one), which is within the
        EntitySet specified in the URI, where key EntityKey is equal to
        the value of the keyPredicate specified."""
        request = MockRequest("/service.svc/Customers('ALFKI')/$count")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(request.wfile.getvalue() == b"1",
                        "the count value SHOULD always equal one")
        request = MockRequest("/service.svc/Customers('ALFKJ')/$count")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 404)
        base_uri = "/service.svc/Customers('ALFKI')/$count?$expand=Orders&"\
            "$filter=substringof(CompanyName,%20'bikes')"
        request = MockRequest(base_uri)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        for x in ["$format=xml",
                  "$orderby=CompanyName%20asc",
                  "$skip=3",
                  "$top=2",
                  "$skiptoken='Contoso','AKFNU'",
                  "$inlinecount=allpages",
                  "$select=CustomerID,CompanyName,Orders"]:
            request = MockRequest(base_uri + "&" + x)
            request.send(self.svc)
            self.assertTrue(request.responseCode == 400, "URI16 with %s" % x)

    def test_uri17(self):
        """URI17 = scheme serviceRoot "/" entitySet "(" keyPredicate ")"
            value

        MUST identify the Media Resource [RFC5023] associated with the
        identified EntityType instance. The EntityType that defines the
        entity identified MUST be annotated with the "HasStream"
        attribute."""
        request = MockRequest("/service.svc/Documents(301)/$value")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        base_uri = "/service.svc/Documents(301)/$value?"\
            "$format=application/octet-stream"
        request = MockRequest(base_uri)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        for x in ["$expand=Orders",
                  "$filter=substringof(CompanyName,%20'bikes')",
                  "$orderby=CompanyName%20asc",
                  "$skip=3",
                  "$top=2",
                  "$skiptoken='Contoso','AKFNU'",
                  "$inlinecount=allpages",
                  "$select=CustomerID,CompanyName,Orders"]:
            request = MockRequest(base_uri + "&" + x)
            request.send(self.svc)
            self.assertTrue(request.responseCode == 400, "URI17 with %s" % x)

    def test_query_options(self):
        """If a data service does not support a System Query Option, it
        MUST reject any requests which contain the unsupported option"""
        request = MockRequest("/service.svc/Documents(301)?$unsupported=1")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 400)
        request = MockRequest(
            "/service.svc/Documents(301)?$filter=true%20nand%20false")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 400)
        """A data service URI with more than one query option present
        MUST be evaluated as if the query options were applied to the
        resource(s) identified by the Resource Path section of the URI,
        in the following order: $format, $inlinecount, $filter,
        $orderby, $skiptoken, $skip, $top, $expand"""
        # TODO

    def test_expand(self):
        """The left most entityNavProperty in an expandClause MUST
        represent a NavigationProperty defined in the EntityType, or a
        sub type thereof

        A subsequent NavigationProperty in the same expandClause must
        represent a NavigationProperty defined on the EntityType, or a
        sub type thereof, represented by the prior NavigationProperty in
        the expandClause."""
        request = MockRequest("/service.svc/Customers?$expand=Orders")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, atom.Feed),
                        "Expected atom.Feed from /Customers?$expand=Orders")
        for e in doc.root.Entry:
            link_inline = None
            for link in e.find_children_depth_first(core.Link):
                if link.title == "Orders":
                    link_inline = link.Inline
                    if link_inline is not None:
                        link_inline = link_inline.Entry if link_inline.Feed \
                            is None else link_inline.Feed
            if e['CustomerID'].value == 'ALFKI':
                # A NavigationProperty that represents an EntityType
                # instance or a group of entities and that is
                # serialized inline MUST be placed within a single
                # <m:inline> element that is a child element of the
                # <atom:link> element.
                self.assertTrue(isinstance(link_inline, atom.Feed),
                                "Expected atom.Feed in Orders link")
                self.assertTrue(len(link_inline.Entry) == 2,
                                "Expected 2 Orders in expand")
            elif e['CustomerID'].value != 'XX=00':
                self.assertTrue(link_inline is None,
                                "Expected no inline content for Orders link")
        # Test json format
        request = MockRequest("/service.svc/Customers?$expand=Orders")
        request.set_header('Accept', "application/json")
        request.send(self.svc)
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(
            obj) == 1 and "d" in obj, "JSON object is security wrapped")
        obj = obj["d"]
        # A NavigationProperty which is serialized inline MUST be
        # represented as a name/value pair ...with the name equal to
        # the NavigationProperty name.... If the NavigationProperty
        # represents an EntitySet, the value MUST be as specified in
        # Entity Set (as a JSON array)
        for objItem in obj["results"]:
            orders = objItem["Orders"]
            if objItem["CustomerID"] == 'ALFKI':
                self.assertTrue("results" in orders,
                                "Version 2 expanded entity set as array")
                self.assertTrue(len(orders["results"]) == 2,
                                "Expected 2 Orders in expand")
            elif objItem["CustomerID"] != 'XX=00':
                self.assertTrue(len(orders["results"]) == 0,
                                "Expected no inline content for Orders link")
        request = MockRequest("/service.svc/Orders(1)?$expand=Customer")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, atom.Entry),
                        "Expected atom.Entry from /Orders(1)?$expand=Customer")
        link_inline = None
        for link in doc.root.find_children_depth_first(core.Link):
            if link.title == "Customer":
                link_inline = link.Inline
                if link_inline is not None:
                    link_inline = link_inline.Entry if link_inline.Feed is \
                        None else link_inline.Feed
        self.assertTrue(isinstance(link_inline, atom.Entry),
                        "Expected atom.Entry in Customer link")
        # Test json format
        request = MockRequest("/service.svc/Orders(1)?$expand=Customer")
        request.set_header('Accept', "application/json")
        request.send(self.svc)
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(
            obj) == 1 and "d" in obj, "JSON object is security wrapped")
        obj = obj["d"]
        # If the NavigationProperty identifies a single EntityType
        # instance, the value MUST be a JSON object representation of
        # that EntityType instance, as specified in Entity Type (as a
        # JSON object)
        customer = obj["Customer"]
        self.assertTrue(isinstance(customer, dict), "Single object result")
        self.assertTrue(customer["CustomerID"] == 'ALFKI', "Matching customer")
        request = MockRequest("/service.svc/Orders(4)?$expand=Customer")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, atom.Entry),
                        "Expected atom.Entry from /Orders(4)?$expand=Customer")
        link_inline = None
        for link in doc.root.find_children_depth_first(core.Link):
            if link.title == "Customer":
                link_inline = link.Inline
                if link_inline is not None:
                    link_inline = link_inline.Entry if link_inline.Feed is \
                        None else link_inline.Feed
        # If the value of a NavigationProperty is null, then an empty
        # <m:inline> element MUST appear under the <atom:link>
        # element which represents the NavigationProperty
        self.assertTrue(
            link_inline is None, "Expected empty inline in Customer link")
        # Test json format
        request = MockRequest("/service.svc/Orders(4)?$expand=Customer")
        request.set_header('Accept', "application/json")
        request.send(self.svc)
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(
            obj) == 1 and "d" in obj, "JSON object is security wrapped")
        obj = obj["d"]
        customer = obj["Customer"]
        self.assertTrue(customer is None, "null json response")
        # test a property we can't expand!
        request = MockRequest("/service.svc/Customers?$expand=Address")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 400)

    def test_filter(self):
        request = MockRequest(
            "/service.svc/Orders?"
            "$filter=ShippedDate%20lt%20datetime'2013-08-05T00:00'")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, atom.Feed),
                        "Expected atom.Feed from /Orders?$filter=...")
        self.assertTrue(len(doc.root.Entry) == 3,
                        "Expected 3 Order after filtering")

    def test_format(self):
        """The $format query option ... SHOULD take precedence over the
        value(s) specified in the Accept request header.

        If the value of the query option is "atom", then the media type
        used in the response MUST be "application/atom+xml".

        If the value of the query option is "json", then the media type
        used in the response MUST be "application/json".

        If the value of the query option is "xml", then the media type
        used in the response MUST be "application/xml"  """
        request = MockRequest("/service.svc/Orders?$format=xml")
        request.set_header('Accept', "application/json")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['CONTENT-TYPE'] == "application/xml")
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, atom.Feed),
                        "Expected atom.Feed from /Orders?$format=xml")
        self.assertTrue(len(doc.root.Entry) == 4, "Expected 4 Orders")
        request = MockRequest("/service.svc/Orders?$format=atom")
        request.set_header('Accept', "application/xml")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(request.responseHeaders['CONTENT-TYPE'] ==
                        "application/atom+xml")
        request = MockRequest("/service.svc/Orders(1)?$format=json")
        request.set_header('Accept', "application/xml")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(request.responseHeaders['CONTENT-TYPE'] ==
                        "application/json")
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(obj) == 1 and "d" in obj,
                        "JSON object is security wrapped")
        obj = obj["d"]
        self.assertTrue("OrderID" in obj, "Expected a single entry object")
        # self.assertTrue(len(doc['error']) == 2, "Expected two children")
        # self.assertTrue(doc['error']['code'] == "DataServiceVersionMismatch",
        #    "Error code")
        # self.assertTrue(doc['error']['message'] ==
        #    "Maximum supported protocol version: 2.0", "Error message")
        #
        # TODO: if ever, support custom format specifiers (note that
        # media types are supported)
        # request.MockRequest("/Orders(1)/ShipCountry/$value/?$format=example")
        # request.set_header('Accept',"application/json")

    def test_orderby(self):
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
        request = MockRequest("/service.svc/Orders?$orderby=ShippedDate")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, atom.Feed),
                        "Expected atom.Feed from /Orders?$orderby=...")
        self.assertTrue(len(doc.root.Entry) == 4, "Expected 4 Orders")
        # default is ascending order, later dates are later in the list
        last_time = iso.TimePoint.from_str("19000101T000000")
        for e in doc.root.Entry:
            # These entries are just that, they aren't entities
            curr_time = iso.TimePoint.from_str(e['ShippedDate'].value)
            self.assertTrue(curr_time >= last_time, "ShippedDate increasing")
            last_time = curr_time
        request = MockRequest(
            "/service.svc/Orders?$orderby=ShippedDate,OrderID%20desc")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        last_time = iso.TimePoint.from_str("19000101T000000")
        last_id = 10000
        fail_flag = True
        for e in doc.root.Entry:
            curr_time = iso.TimePoint.from_str(e['ShippedDate'].value)
            curr_id = e['OrderID'].value
            self.assertTrue(curr_time >= last_time, "ShippedDate increasing")
            if curr_time == last_time:
                fail_flag = False
                self.assertTrue(curr_id < last_id, "OrderID decreasing")
            last_time = curr_time
            last_id = curr_id
        self.assertFalse(fail_flag, "Expected one equality test")

    def test_skip(self):
        """If the data service URI contains a $skip query option, but
        does not contain an $orderby option, then the entities in the
        set MUST first be fully ordered by the data service. Such a full
        order SHOULD be obtained by sorting the entities based on their
        EntityKey values."""
        request = MockRequest("/service.svc/Orders?$orderby=ShippedDate")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(len(doc.root.Entry) == 4, "Expected 4 Orders")
        # grab the third ID
        third_id = doc.root.Entry[2]['OrderID'].value
        request = MockRequest(
            "/service.svc/Orders?$orderby=ShippedDate&$skip=2")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(len(doc.root.Entry) == 2, "Expected 2 Orders")
        self.assertTrue(
            third_id == doc.root.Entry[0]['OrderID'].value, "Skipped first 2")
        request = MockRequest("/service.svc/Orders?$skip=0")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        last_id = -1
        for e in doc.root.Entry:
            curr_id = int(e['OrderID'].value)
            self.assertTrue(curr_id > last_id, "OrderID increasing")
            last_id = curr_id

    def test_top(self):
        """If the data service URI contains a $top query option, but
        does not contain an $orderby option, then the entities in the
        set MUST first be fully ordered by the data service. Such a full
        order SHOULD be obtained by sorting the entities based on their
        EntityKey values."""
        request = MockRequest("/service.svc/Orders?$orderby=ShippedDate")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(len(doc.root.Entry) == 4, "Expected 4 Orders")
        # grab the first ID
        first_id = doc.root.Entry[0]['OrderID'].value
        request = MockRequest(
            "/service.svc/Orders?$orderby=ShippedDate&$top=2")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(len(doc.root.Entry) == 2, "Expected 2 Orders")
        self.assertTrue(first_id == doc.root.Entry[0]['OrderID'].value,
                        "First one correct")
        request = MockRequest("/service.svc/Orders?$top=4")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        last_id = -1
        for e in doc.root.Entry:
            curr_id = int(e['OrderID'].value)
            self.assertTrue(curr_id > last_id, "OrderID increasing")
            last_id = curr_id
        request = MockRequest("/service.svc/Orders?$top=0")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(len(doc.root.Entry) == 0, "Expected 0 Orders")

    def test_inline_count(self):
        """A data service URI with an $inlinecount System Query Option
        specifies that the response to the request MUST include the
        count of the number of entities in the collection of entities,
        which are identified by the Resource Path section of the URI
        after all $filter System Query Options have been applied

        If a value other than "allpages" or "none" is specified, the
        data service MUST return a 4xx error response code.

        If a value of "none" is specified, the data service MUST NOT
        include the count in the response."""
        request = MockRequest("/service.svc/Orders?$inlinecount=allpages")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(len(doc.root.Entry) == 4, "Expected 4 Orders")
        self.assertTrue(doc.root.Count.get_value() == 4,
                        "Expected count of 4 Orders")
        request = MockRequest("/service.svc/Orders?$inlinecount=none")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(len(doc.root.Entry) == 4, "Expected 4 Orders")
        self.assertTrue(doc.root.Count is None, "Expected no count")
        request = MockRequest(
            "/service.svc/Orders?$top=2&$inlinecount=allpages")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(len(doc.root.Entry) == 2, "Expected 2 Orders")
        self.assertTrue(doc.root.Count.get_value() == 4,
                        "Expected count of 4 Orders")
        request = MockRequest(
            "/service.svc/Orders?$top=2&$inlinecount=somepages")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 400)

    def test_select_clause1(self):
        """The left most selectedProperty or selectedNavProperty in a
        selectedClause MUST be a star or represent a property defined in
        the EntityType, or a subtype thereof, that is identified by the
        Resource Path section of the URI."""
        request = MockRequest(
            "/service.svc/Customers?$select=CustomerID,CompanyName,Address")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        request = MockRequest("/service.svc/Customers?$select=*")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        request = MockRequest("/service.svc/Customers?$select=ShippedDate")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 400)

    def test_select_clause2(self):
        """A subsequent selectedProperty or selectedNavProperty in the
        same selectClause MUST represent a property defined on the
        EntityType, or a subtype thereof, that is represented by the
        prior navigation property in the selectClause."""
        request = MockRequest(
            "/service.svc/Orders?$select=Customer/CompanyName")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        request = MockRequest(
            "/service.svc/Orders?$select=Customer/ShippedDate")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 400)

    def test_select_clause3(self):
        """For AtomPub formatted responses: The value of a selectQueryOp
        applies only to the properties returned within the
        <m:properties> element...
        For example, if a property of an Entity Type is mapped with the
        attribute KeepInContent=false,... then that property must always
        be included in the response according to its Customizable Feed
        mapping."""
        # TODO

    def test_select_clause4(self):
        """For JSON formatted responses: The value of a selectQueryOp
        applies only to the name/value pairs with a name that does not
        begin with two consecutive underscore characters."""
        # TODO

    def test_select_clause5(self):
        """If a property is not requested as a selectItem (explicitly or
        via a star) it SHOULD NOT be included in the response."""
        # TODO

    def test_select_clause6(self):
        """If a selectedProperty appears alone as a selectItem in a
        request URI, then the response MUST contain the value of the
        property."""
        # TODO

    def test_select_clause7(self):
        """If a star appears alone in a selectClause, all properties on
        the EntityType within the collection of entities identified by
        the last path segment in the request URI MUST be included in the
        response."""
        request = MockRequest("/service.svc/Customers?$select=*")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        # TODO

    def test_select_clause8(self):
        """If a star appears in a selectItem following a
        selectedNavProperty, all non-navigation properties of the entity
        or entities represented by the prior selectedNavProperty MUST be
        included in the response."""
        request = MockRequest(
            "/service.svc/Customers?$select=CustomerID,Orders/*&"
            "$expand=Orders/OrderLine")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        # TODO

    def test_select_clause9(self):
        """If a navigation property appears as the last segment of a
        selectItem and does not appear in an $expand query option, then
        the entity or collection of entities identified by the
        navigation property MUST be represented as deferred content"""
        request = MockRequest(
            "/service.svc/Customers?$select=CustomerID,Orders")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        # TODO

    def test_select_clause10(self):
        """If a navigation property appears as the last segment of a
        selectItem and the same property is specified as a segment of a
        path in an $expand query option, then all the properties of the
        entity identified by the selectItem MUST be in the response. In
        addition, all the properties of the entities identified by
        segments in the $expand path after the segment that matched the
        selectedItem MUST also be included in the response."""
        request = MockRequest(
            "/service.svc/Customers?$select=CustomerID,Orders&"
            "$expand=Orders/OrderLine")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        # TODO

    def test_select_clause11(self):
        """If multiple selectClause instances exist in a $select query
        option, then the total set of property values to be returned is
        equal to the union of the set of properties identified by each
        selectClause."""
        # TODO

    def test_select_clause12(self):
        """Redundant selectClause rules on the same URI can be
        considered valid, but MUST NOT alter the meaning of the URI."""
        # TODO

    def test_service_operation_parameters(self):
        """If a Service Operation requires input parameters, a null
        value may be specified for nullable type parameters by not
        including the parameter in the query string of the request
        URI."""
        # TODO

    def test_content_kind(self):
        """If the FC_ContentKind property is not defined for an
        EntityType property, the value of the property should be assumed
        to be "text"
        """
        request = MockRequest("/service.svc/Employees('1')")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, core.Entry),
                        "Expected a single Entry, found %s" %
                        doc.root.__class__.__name__)
        self.assertTrue(doc.root.Title.type == atom.TextType.text,
                        "title is text")
        self.assertTrue(doc.root.Title.get_value() == "Joe Bloggs",
                        "title is employee name")
        # Now let's go looking for the Location element...
        nlocation = 0
        for e in doc.root.get_children():
            if e.get_xmlname() == ("http://www.example.com", "Location"):
                nlocation += 1
                self.assertTrue(e.get_value() == "Chunton",
                                "Location is employee city name")
        self.assertTrue(nlocation == 1,
                        "Expected 1 and only 1 Location: %i" % nlocation)

    def test_misc_uri(self):
        """Example URIs not tested elsewhere:"""
        for u in [
                "/service.svc/Customers",
                "/service.svc/Customers('ALFKI')/Orders"]:
            request = MockRequest(u)
            request.send(self.svc)
            self.assertTrue(request.responseCode == 200,
                            "misc URI failed (path): %s" % u)

    def test_insert_entity(self):
        # remove a link before running this test
        with self.ds['SampleModel.SampleEntities.Orders'].open() as orders:
            order = orders[3]
            with order['Customer'].open() as navCollection:
                del navCollection['XX=00']
        customers = self.ds[
            'SampleModel.SampleEntities.Customers'].open()
        customer = customers.new_entity()
        customer['CustomerID'].set_from_value('STEVE')
        customer['CompanyName'].set_from_value("Steve's Inc")
        customer['Address']['City'].set_from_value('Cambridge')
        # street left blank
        request = MockRequest("/service.svc/Customers", "POST")
        doc = core.Document(root=core.Entry(None, customer))
        data = str(doc).encode('utf-8')
        request.set_header('Content-Type', core.ODATA_RELATED_ENTRY_TYPE)
        request.set_header('Content-Length', str(len(data)))
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 201)
        # We expect a location header
        self.assertTrue(request.responseHeaders['LOCATION'] ==
                        "http://host/service.svc/Customers('STEVE')")
        self.assertTrue(request.responseHeaders['CONTENT-TYPE'] ==
                        params.MediaType.from_str("application/atom+xml"))
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, core.Entry),
                        "Expected a single Entry, found %s" %
                        doc.root.__class__.__name__)
        new_customer = core.Entity(
            self.ds['SampleModel.SampleEntities.Customers'])
        new_customer.exists = True
        doc.root.get_value(new_customer)
        self.assertTrue(new_customer['CustomerID'].value == "STEVE")
        self.assertTrue(new_customer['CompanyName'].value == "Steve's Inc")
        self.assertTrue(new_customer['Address']['City'].value == "Cambridge")
        self.assertFalse(new_customer['Address']['Street'])
        # insert entity with binding
        customer = customers.new_entity()
        customer['CustomerID'].set_from_value('ASDFG')
        customer['CompanyName'].set_from_value("Contoso Widgets")
        customer['Address']['Street'].set_from_value('58 Contoso St')
        customer['Address']['City'].set_from_value('Seattle')
        customer['Orders'].bind_entity(3)
        customer['Orders'].bind_entity(4)
        request = MockRequest("/service.svc/Customers", "POST")
        doc = core.Document(root=core.Entry(None, customer))
        data = str(doc).encode('utf-8')
        request.set_header('Content-Type', core.ODATA_RELATED_ENTRY_TYPE)
        request.set_header('Content-Length', str(len(data)))
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 201)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        new_customer = core.Entity(
            self.ds['SampleModel.SampleEntities.Customers'])
        new_customer.exists = True
        doc.root.get_value(new_customer)
        self.assertTrue(new_customer['CustomerID'].value == "ASDFG")
        self.assertTrue(
            new_customer['Address']['Street'].value == "58 Contoso St")
        request = MockRequest("/service.svc/Customers('ASDFG')/Orders")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, atom.Feed),
                        "Expected atom.Feed from navigation property Orders")
        self.assertTrue(len(doc.root.Entry) == 2,
                        "Inserted customer has 2 orders")
        order_keys = set()
        for entry in doc.root.Entry:
            order = core.Entity(self.ds['SampleModel.SampleEntities.Orders'])
            order.exists = True
            entry.get_value(order)
            order_keys.add(order['OrderID'].value)
        self.assertTrue(3 in order_keys, "New entity bound to order 3")
        self.assertTrue(4 in order_keys, "New entity bound to order 4")

    def test_insert_entity_json(self):
        # remove a link before running this test
        with self.ds['SampleModel.SampleEntities.Orders'].open() as orders:
            order = orders[3]
            with order['Customer'].open() as navCollection:
                del navCollection['XX=00']
        customers = self.ds[
            'SampleModel.SampleEntities.Customers'].open()
        customer = customers.new_entity()
        customer['CustomerID'].set_from_value('STEVE')
        customer['CompanyName'].set_from_value("Steve's Inc")
        customer['Address']['City'].set_from_value('Cambridge')
        # street left blank
        request = MockRequest("/service.svc/Customers", "POST")
        data = ' '.join(customer.generate_entity_type_in_json(False, 1))
        data = data.encode('utf-8')
        request.set_header('Content-Type', 'application/json')
        request.set_header('Content-Length', str(len(data)))
        request.set_header('Accept', "application/json")
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 201)
        # We expect a location header
        self.assertTrue(request.responseHeaders['LOCATION'] ==
                        "http://host/service.svc/Customers('STEVE')")
        self.assertTrue(request.responseHeaders['CONTENT-TYPE'] ==
                        params.MediaType.from_str('application/json'))
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(obj) == 1 and "d" in obj,
                        "JSON object is security wrapped")
        obj = obj["d"]
        self.assertTrue(
            isinstance(obj, dict),
            "Expected a single JSON object, found %s" % repr(type(obj)))
        new_customer = core.Entity(
            self.ds['SampleModel.SampleEntities.Customers'])
        new_customer.exists = True
        new_customer.set_from_json_object(obj)
        self.assertTrue(new_customer['CustomerID'].value == "STEVE")
        self.assertTrue(new_customer['CompanyName'].value == "Steve's Inc")
        self.assertTrue(new_customer['Address']['City'].value == "Cambridge")
        self.assertFalse(new_customer['Address']['Street'])
        # insert entity with binding
        customer = customers.new_entity()
        customer['CustomerID'].set_from_value('ASDFG')
        customer['CompanyName'].set_from_value("Contoso Widgets")
        customer['Address']['Street'].set_from_value('58 Contoso St')
        customer['Address']['City'].set_from_value('Seattle')
        customer['Orders'].bind_entity(3)
        customer['Orders'].bind_entity(4)
        request = MockRequest("/service.svc/Customers", "POST")
        data = ' '.join(customer.generate_entity_type_in_json(False, 1))
        data = data.encode('utf-8')
        request.set_header('Content-Type', 'application/json')
        request.set_header('Content-Length', str(len(data)))
        request.set_header('Accept', "application/json")
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 201)
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(
            obj) == 1 and "d" in obj, "JSON object is security wrapped")
        obj = obj["d"]
        new_customer = core.Entity(
            self.ds['SampleModel.SampleEntities.Customers'])
        new_customer.exists = True
        new_customer.set_from_json_object(obj)
        self.assertTrue(new_customer['CustomerID'].value == "ASDFG")
        self.assertTrue(
            new_customer['Address']['Street'].value == "58 Contoso St")
        request = MockRequest("/service.svc/Customers('ASDFG')/Orders")
        request.set_header('Accept', "application/json")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(
            obj) == 1 and "d" in obj, "JSON object is security wrapped")
        obj = obj["d"]
        self.assertTrue(isinstance(obj['results'], list),
                        "Expected JSON array from navigation property Orders")
        self.assertTrue(
            len(obj['results']) == 2, "Inserted customer has 2 orders")
        order_keys = set()
        for entry in obj['results']:
            order = core.Entity(self.ds['SampleModel.SampleEntities.Orders'])
            order.exists = True
            order.set_from_json_object(entry)
            order_keys.add(order['OrderID'].value)
        self.assertTrue(3 in order_keys, "New entity bound to order 3")
        self.assertTrue(4 in order_keys, "New entity bound to order 4")

    def test_insert_link(self):
        request = MockRequest(
            "/service.svc/Customers('ALFKI')/$links/Orders", "POST")
        doc = core.Document(root=core.URI)
        orders = self.ds['SampleModel.SampleEntities.Orders'].open()
        order = orders[4]
        doc.root.set_value(str(order.get_location()))
        data = str(doc).encode('utf-8')
        request.set_header('Content-Type', 'application/xml')
        request.set_header('Content-Length', str(len(data)))
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 204)
        self.assertTrue(len(request.wfile.getvalue()) == 0,
                        "empty response body expected")
        request = MockRequest("/service.svc/Customers('ALFKI')/Orders")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(len(doc.root.Entry) == 3, "Customer now has 3 orders")
        order_keys = set()
        for entry in doc.root.Entry:
            order = core.Entity(self.ds['SampleModel.SampleEntities.Orders'])
            order.exists = True
            entry.get_value(order)
            order_keys.add(order['OrderID'].value)
        self.assertTrue(4 in order_keys, "Customer now bound to order 4")

    def test_insert_link_json(self):
        request = MockRequest(
            "/service.svc/Customers('ALFKI')/$links/Orders", "POST")
        orders = self.ds['SampleModel.SampleEntities.Orders'].open()
        order = orders[4]
        obj = {'uri': str(order.get_location())}
        data = json.dumps(obj).encode('utf-8')
        request.set_header('Content-Type', 'application/json')
        request.set_header('Content-Length', str(len(data)))
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 204)
        self.assertTrue(
            len(request.wfile.getvalue()) == 0, "empty response body expected")
        # let's just test the links themselves
        request = MockRequest("/service.svc/Customers('ALFKI')/$links/Orders")
        request.set_header('Accept', 'application/json')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(
            obj) == 1 and "d" in obj, "JSON object is security wrapped")
        obj = obj["d"]
        self.assertTrue(len(obj['results']) == 3, "Customer now has 3 orders")
        order_keys = set()
        for entry in obj['results']:
            order_keys.add(entry['uri'])
        self.assertTrue('http://host/service.svc/Orders(4)' in order_keys,
                        "Customer now bound to order 4")

    def test_insert_media_resource(self):
        data = DOCUMENT_TEXT
        h = hashlib.sha256()
        h.update(data)
        request = MockRequest("/service.svc/Documents", "POST")
        request.set_header('Content-Type', "text/x-tolstoy")
        request.set_header('Content-Length', str(len(data)))
        request.set_header('Slug', 'War and Peace')
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 201)
        # We expect a location header
        location = request.responseHeaders['LOCATION']
        self.assertTrue(
            location.startswith("http://host/service.svc/Documents("))
        self.assertTrue(
            location[len("http://host/service.svc/Documents("):-1].isdigit(),
            "document Id is an integer")
        self.assertTrue(request.responseHeaders['CONTENT-TYPE'] ==
                        params.MediaType.from_str("application/atom+xml"))
        # Document has a concurrency token so we expect an ETag too
        self.assertTrue("ETAG" in request.responseHeaders)
        self.assertTrue(request.responseHeaders['ETAG'] == "W/\"X'%s'\"" %
                        h.hexdigest().upper(), "ETag value: " +
                        repr(request.responseHeaders['ETAG']))
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, core.Entry),
                        "Expected a single Entry, found %s" %
                        doc.root.__class__.__name__)
        new_document = core.Entity(
            self.ds['SampleModel.SampleEntities.Documents'])
        new_document.exists = True
        doc.root.get_value(new_document)
        # version should match the etag
        self.assertTrue(new_document['Version'].value == h.digest(),
                        'Version calculation')
        self.assertTrue(new_document['Title'].value == "War and Peace",
                        "Slug mapped to syndication title")
        self.assertFalse(new_document['Author'].value,
                         "Empty string is a pass - we are reading from Atom")
        doc_id = new_document['DocumentID'].value
        request = MockRequest("/service.svc/Documents(%i)/$value" % doc_id)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(request.responseHeaders['CONTENT-TYPE'] ==
                        "text/x-tolstoy")
        self.assertTrue(request.wfile.getvalue() == data)
        # now try the same thing without the slug mapping to the title
        request = MockRequest("/service.svc/XDocuments", "POST")
        request.set_header('Content-Type', "text/x-tolstoy")
        request.set_header('Content-Length', str(len(data)))
        # set the slug to hint at the desired key
        request.set_header('Slug', "1805")
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 201)
        # We expect a location header
        location = request.responseHeaders['LOCATION']
        self.assertTrue(
            location.startswith("http://host/service.svc/XDocuments("))
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, core.Entry),
                        "Expected a single Entry, found %s" %
                        doc.root.__class__.__name__)
        new_document = core.Entity(
            self.ds['SampleModel.SampleEntities.XDocuments'])
        new_document.exists = True
        doc.root.get_value(new_document)
        self.assertTrue(new_document['DocumentID'].value == 1805,
                        "Slug used for key")
        request = MockRequest("%s/$value" % location)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['CONTENT-TYPE'] == "text/x-tolstoy")
        self.assertTrue(request.wfile.getvalue() == data)
        #
        # now try an alternative with a composite key
        request = MockRequest("/service.svc/XYDocuments", "POST")
        request.set_header('Content-Type', "text/x-tolstoy")
        request.set_header('Content-Length', str(len(data)))
        # set the slug to hint at the desired key
        request.set_header('Slug',
                           "(DocumentIDX=1805,DocumentIDY='War and Peace')")
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 201)
        # We expect a location header
        location = request.responseHeaders['LOCATION']
        self.assertTrue(
            location.startswith("http://host/service.svc/XYDocuments("))
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, core.Entry),
                        "Expected a single Entry, found %s" %
                        doc.root.__class__.__name__)
        new_document = core.Entity(
            self.ds['SampleModel.SampleEntities.XYDocuments'])
        new_document.exists = True
        doc.root.get_value(new_document)
        self.assertTrue(new_document['DocumentIDX'].value == 1805,
                        "Slug used for key X")
        self.assertTrue(new_document['DocumentIDY'].value == "War and Peace",
                        "Slug used for key Y")
        request = MockRequest("%s/$value" % location)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['CONTENT-TYPE'] == "text/x-tolstoy")
        self.assertTrue(request.wfile.getvalue() == data)

    def test_retrieve_entity_set(self):
        request = MockRequest('/service.svc/Customers')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) == "application/atom+xml")
        # Entity set can't have an ETag
        self.assertFalse("ETAG" in request.responseHeaders, "Entity set ETag")
        doc = app.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, atom.Feed),
                        "Expected atom.Feed from /Customers")
        self.assertTrue(len(doc.root.Entry) == 91,
                        "Sample server has 91 Customers")

    def test_retrieve_entity_set_json(self):
        request = MockRequest('/service.svc/Customers')
        request.set_header('Accept', 'application/json')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) == "application/json")
        self.assertFalse("ETAG" in request.responseHeaders, "Entity set ETag")
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(
            obj) == 1 and "d" in obj, "JSON object is security wrapped")
        obj = obj["d"]
        self.assertTrue(
            isinstance(obj, dict),
            "Expected a single JSON object, found %s" % repr(type(obj)))
        # by default we expect version 2 format
        self.assertTrue("results" in obj, "Version 2 format response")
        obj = obj["results"]
        self.assertTrue(isinstance(obj, list), "Expected list of entities")
        self.assertTrue(len(obj) == 91, "Sample server has 91 Customers")
        # make the same request with version 1
        request = MockRequest('/service.svc/Customers')
        request.set_header('DataServiceVersion', "1.0; old request")
        request.set_header('Accept', 'application/json')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) == "application/json")
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("1.0;"),
            "DataServiceVersion 1.0 expected")
        self.assertFalse("ETAG" in request.responseHeaders, "Entity set ETag")
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(
            obj) == 1 and "d" in obj, "JSON object is security wrapped")
        obj = obj["d"]
        # should be version 1 response
        self.assertTrue(isinstance(obj, list), "Expected list of entities")
        self.assertTrue(len(obj) == 91, "Sample server has 91 Customers")

    def test_retrieve_entity(self):
        request = MockRequest("/service.svc/Customers('ALFKI')")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) == "application/atom+xml")
        # Customer does have a version field for optimistic concurrency control
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, core.Entry),
                        "Expected a single Entry, found %s" %
                        doc.root.__class__.__name__)
        self.assertTrue(doc.root['CustomerID'] == 'ALFKI', "Bad CustomerID")

    def test_retrieve_entity_json(self):
        request = MockRequest("/service.svc/Customers('ALFKI')")
        request.set_header('Accept', 'application/json')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) == "application/json")
        # Customer does have a version field for optimistic concurrency control
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(obj) == 1 and "d" in obj,
                        "JSON object is security wrapped")
        obj = obj["d"]
        self.assertTrue(
            isinstance(obj, dict),
            "Expected a single JSON object, found %s" % repr(type(obj)))
        self.assertTrue("__metadata" in obj, "__metadata in response")
        self.assertTrue("CustomerID" in obj, "CustomerID in response")
        self.assertTrue(obj["CustomerID"] == 'ALFKI', "Bad CustomerID")
        request = MockRequest("/service.svc/Customers('ALFKI')")
        request.set_header('DataServiceVersion', "1.0; old request")
        request.set_header('Accept', 'application/json')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("1.0;"),
            "DataServiceVersion 1.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) == "application/json")
        # Customer does have a version field for optimistic concurrency control
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(obj) == 1 and "d" in obj,
                        "JSON object is security wrapped")
        obj = obj["d"]
        # version 1.0 and 2.0 responses are the same
        self.assertTrue(
            isinstance(obj, dict),
            "Expected a single JSON object, found %s" % repr(type(obj)))
        self.assertTrue("__metadata" in obj, "__metadata in response")
        self.assertTrue("CustomerID" in obj, "CustomerID in response")
        self.assertTrue(obj["CustomerID"] == 'ALFKI', "Bad CustomerID")

    def test_retrieve_complex_type(self):
        request = MockRequest("/service.svc/Customers('ALFKI')/Address")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) == "application/xml")
        # Customer does have a version field for optimistic concurrency control
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, core.Property),
                        "Expected a single Property, found %s" %
                        doc.root.__class__.__name__)
        value = doc.root.get_value()
        self.assertTrue(
            value['Street'] == 'Mill Road', "Bad street in address")

    def test_retrieve_complex_type_json(self):
        request = MockRequest("/service.svc/Customers('ALFKI')/Address")
        request.set_header('Accept', 'application/json')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) == "application/json")
        # Customer does have a version field for optimistic concurrency
        # control
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(obj) == 1 and "d" in obj,
                        "JSON object is security wrapped")
        obj = obj["d"]
        self.assertTrue(
            isinstance(obj, dict),
            "Expected a single JSON object, found %s" % repr(type(obj)))
        self.assertTrue("results" in obj, "results in response")
        obj = obj["results"]
        self.assertTrue("Address" in obj,
                        "Expected named object 'Address' in response")
        obj = obj["Address"]
        self.assertTrue(obj["Street"] == 'Mill Road', "Bad street in address")
        request = MockRequest("/service.svc/Customers('ALFKI')/Address")
        request.set_header('DataServiceVersion', "1.0; old request")
        request.set_header('Accept', 'application/json')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("1.0;"),
            "DataServiceVersion 1.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) == "application/json")
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(
            obj) == 1 and "d" in obj, "JSON object is security wrapped")
        obj = obj["d"]
        self.assertTrue(
            isinstance(obj, dict),
            "Expected a single JSON object, found %s" % repr(type(obj)))
        self.assertTrue(
            "Address" in obj, "Expected named object 'Address' in response")
        obj = obj["Address"]
        self.assertTrue(obj["Street"] == 'Mill Road', "Bad street in address")

    def test_retrieve_primitive_property(self):
        request = MockRequest("/service.svc/Customers('ALFKI')/CompanyName")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) == "application/xml")
        # Customer does have a version field for optimistic concurrency control
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, core.Property),
                        "Expected a single Property, found %s" %
                        doc.root.__class__.__name__)
        value = doc.root.get_value()
        self.assertTrue(value.value == 'Example Inc', "Bad company")

    def test_retrieve_primitive_property_json(self):
        request = MockRequest("/service.svc/Customers('ALFKI')/CompanyName")
        request.set_header('Accept', 'application/json')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) == "application/json")
        # Customer does have a version field for optimistic concurrency
        # control
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(
            obj) == 1 and "d" in obj, "JSON object is security wrapped")
        obj = obj["d"]
        self.assertTrue(
            isinstance(obj, dict),
            "Expected a single JSON object, found %s" % repr(type(obj)))
        self.assertTrue("results" in obj, "results in response")
        obj = obj["results"]
        self.assertTrue("CompanyName" in obj,
                        "Expected named object 'CompanyName' in response")
        self.assertTrue(obj["CompanyName"] == 'Example Inc', "Bad company")
        request = MockRequest("/service.svc/Customers('ALFKI')/CompanyName")
        request.set_header('DataServiceVersion', "1.0; old request")
        request.set_header('Accept', 'application/json')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("1.0;"),
            "DataServiceVersion 1.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) == "application/json")
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(
            obj) == 1 and "d" in obj, "JSON object is security wrapped")
        obj = obj["d"]
        self.assertTrue(
            isinstance(obj, dict),
            "Expected a single JSON object, found %s" % repr(type(obj)))
        self.assertTrue("CompanyName" in obj,
                        "Expected named object 'CompanyName' in response")
        self.assertTrue(obj["CompanyName"] == 'Example Inc', "Bad company")

    def test_retrieve_value(self):
        request = MockRequest(
            "/service.svc/Customers('ALFKI')/CompanyName/$value")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(
            messages.MediaRange.from_str("text/plain").match_media_type(
                params.MediaType.from_str(
                    request.responseHeaders['CONTENT-TYPE'])))
        # Customer does have a version field for optimistic concurrency
        # control
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        self.assertTrue(request.wfile.getvalue() == b'Example Inc',
                        "Bad company")
        # check media type customisation
        request = MockRequest(
            "/service.svc/ExtraEntities.BitsAndPieces(1)/Details/$value")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(request.responseHeaders['CONTENT-TYPE'] ==
                        "application/x-details")
        self.assertTrue(request.wfile.getvalue() == b'blahblah',
                        "Bad details $value")
        # check that binary values are received as raw values
        request = MockRequest("/service.svc/Customers('ALFKI')/Version/$value")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) ==
            "application/octet-stream")
        # Customer does have a version field for optimistic concurrency control
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        self.assertTrue(request.wfile.getvalue() ==
                        b'\x00\x00\x00\x00\x00\x00\xfa\x01', "Bad version")
        # check behaviour of null values, this was clarified in the v3
        # specification A $value request for a property that is NULL
        # SHOULD result in a 404 Not Found. response.
        request = MockRequest(
            "/service.svc/Customers('XX%3D00')/Version/$value")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 404)

    def test_retrieve_metadata(self):
        request = MockRequest("/service.svc/$metadata")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) == "application/xml")
        doc = edmx.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, edmx.Edmx),
                        "Expected Edmx from $metadata request, found %s" %
                        doc.root.__class__.__name__)
        doc.validate()
        # The version number returned as the value of the
        # DataServiceVersion response header MUST match the value of
        # the DataServiceVersion attribute
        ds = doc.root.DataServices
        self.assertTrue(ds.data_services_version() == "2.0",
                        "Expected matching data service version")

    def test_retrieve_service_document(self):
        request = MockRequest("/service.svc/")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) ==
            "application/atomsvc+xml")
        doc = app.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, app.Service),
                        "Expected atom service document, found %s" %
                        doc.root.__class__.__name__)

    def test_retrieve_service_document_json(self):
        request = MockRequest("/service.svc/")
        request.set_header('Accept', 'application/json')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) == "application/json")
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(
            obj) == 1 and "d" in obj, "JSON object is security wrapped")
        obj = obj["d"]
        self.assertTrue(
            isinstance(obj, dict),
            "Expected a single JSON object, found %s" % repr(type(obj)))
        self.assertTrue("EntitySets" in obj,
                        "EntitySets in service document response")
        self.assertTrue(isinstance(obj['EntitySets'], list),
                        "EntitySets is an array")

    def test_retrieve_link(self):
        request = MockRequest("/service.svc/Customers('ALFKI')/$links/Orders")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) == "application/xml")
        self.assertFalse("ETAG" in request.responseHeaders, "Entity set ETag")
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, core.Links),
                        "Expected Links from $links request, found %s" %
                        doc.root.__class__.__name__)
        self.assertTrue(len(doc.root.URI) == 2, "Sample customer has 2 orders")
        request = MockRequest("/service.svc/Orders(1)/$links/Customer")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) == "application/xml")
        self.assertFalse("ETAG" in request.responseHeaders, "Entity set ETag")
        doc = core.Document()
        doc.read(request.wfile.getvalue())
        self.assertTrue(isinstance(doc.root, core.URI),
                        "Expected URI from $links request, found %s" %
                        doc.root.__class__.__name__)
        self.assertTrue(doc.root.get_value() ==
                        "http://host/service.svc/Customers('ALFKI')",
                        "Bad customer link")

    def test_retrieve_link_json(self):
        request = MockRequest("/service.svc/Customers('ALFKI')/$links/Orders")
        request.set_header('Accept', 'application/json')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) == "application/json")
        self.assertFalse("ETAG" in request.responseHeaders, "Entity set ETag")
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(
            obj) == 1 and "d" in obj, "JSON object is security wrapped")
        obj = obj["d"]
        self.assertTrue("results" in obj, "results in response")
        obj = obj["results"]
        self.assertTrue(isinstance(obj, list), "Expected json array of links")
        self.assertTrue(len(obj) == 2, "Sample customer has 2 orders")
        # version 1 format
        request = MockRequest("/service.svc/Customers('ALFKI')/$links/Orders")
        request.set_header('DataServiceVersion', "1.0; old request")
        request.set_header('Accept', 'application/json')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("1.0;"),
            "DataServiceVersion 1.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) == "application/json")
        self.assertFalse("ETAG" in request.responseHeaders, "Entity set ETag")
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(
            obj) == 1 and "d" in obj, "JSON object is security wrapped")
        obj = obj["d"]
        self.assertTrue(isinstance(obj, list), "Expected json array of links")
        self.assertTrue(len(obj) == 2, "Sample customer has 2 orders")
        # Now the single link use case: one format for both versions
        request = MockRequest("/service.svc/Orders(1)/$links/Customer")
        request.set_header('Accept', 'application/json')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(params.MediaType.from_str(
            request.responseHeaders['CONTENT-TYPE']) == "application/json")
        self.assertFalse("ETAG" in request.responseHeaders, "Entity set ETag")
        obj = json.loads(request.wfile.getvalue().decode('utf-8'))
        self.assertTrue(isinstance(obj, dict) and len(
            obj) == 1 and "d" in obj, "JSON object is security wrapped")
        obj = obj["d"]
        self.assertTrue("uri" in obj, "uri in response")
        self.assertTrue(obj["uri"] ==
                        "http://host/service.svc/Customers('ALFKI')",
                        "Bad customer link")

    def test_retrieve_count(self):
        request = MockRequest('/service.svc/Customers/$count')
        request.send(self.svc)
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(
            messages.MediaRange.from_str("text/plain").match_media_type(
                params.MediaType.from_str(
                    request.responseHeaders['CONTENT-TYPE'])))
        self.assertFalse("ETAG" in request.responseHeaders, "Count ETag")
        self.assertTrue(request.wfile.getvalue() == b"91",
                        "Sample server has 91 Customers")

    def test_retrieve_media_resource(self):
        request = MockRequest("/service.svc/Documents(301)/$value")
        request.send(self.svc)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(messages.MediaRange.from_str(
            "text/plain ; charset=iso-8859-1").match_media_type(
                params.MediaType.from_str(
                    request.responseHeaders['CONTENT-TYPE'])))
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        self.assertTrue(request.responseCode == 200)
        self.assertTrue(
            request.wfile.getvalue().decode("iso-8859-1") ==
            u8(b'An opening line written in a Caf\xc3\xa9'),
            "media resource characters")

    def test_update_entity(self):
        customers = self.ds['SampleModel.SampleEntities.Customers']
        with customers.open() as collection:
            customer = collection['ALFKI']
        customer['CompanyName'].set_from_value("Example Inc Updated")
        request = MockRequest("/service.svc/Customers('ALFKI')", "PUT")
        doc = core.Document(root=core.Entry)
        doc.root.set_value(customer, True)
        data = str(doc).encode('utf-8')
        request.set_header('Content-Type', core.ODATA_RELATED_ENTRY_TYPE)
        request.set_header('Content-Length', str(len(data)))
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 204)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        self.assertTrue(len(request.wfile.getvalue()) == 0,
                        "Update must return 0 bytes")
        # now go behind the scenes to check the update really worked!
        customers = self.ds['SampleModel.SampleEntities.Customers']
        with customers.open() as collection:
            customer = collection['ALFKI']
            self.assertTrue(customer['CompanyName'] == "Example Inc Updated")
        # Now do a case with an updated link
        orders = self.ds['SampleModel.SampleEntities.Orders']
        with orders.open() as collection:
            order = collection[3]
        old_customer = order['Customer'].get_entity()
        self.assertTrue(old_customer.key() == 'XX=00', "Previous customer")
        order['Customer'].bind_entity(customer)
        request = MockRequest("/service.svc/Orders(3)", "PUT")
        doc = core.Document(root=core.Entry)
        doc.root.set_value(order, True)
        data = str(doc).encode('utf-8')
        request.set_header('Content-Type', core.ODATA_RELATED_ENTRY_TYPE)
        request.set_header('Content-Length', str(len(data)))
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 204)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertFalse("ETAG" in request.responseHeaders,
                         "Entity set Orders has no ETag")
        self.assertTrue(len(request.wfile.getvalue()) == 0,
                        "Update must return 0 bytes")
        # now go behind the scenes to check the update really worked!
        orders = self.ds['SampleModel.SampleEntities.Orders']
        with orders.open() as collection:
            order = collection[3]
        new_customer = order['Customer'].get_entity()
        self.assertTrue(new_customer.key() == 'ALFKI', "Customer updated")

    def test_update_entity_json(self):
        customers = self.ds['SampleModel.SampleEntities.Customers']
        with customers.open() as collection:
            customer = collection['ALFKI']
        customer['CompanyName'].set_from_value("Example Inc Updated")
        request = MockRequest("/service.svc/Customers('ALFKI')", "PUT")
        json_data = ' '.join(customer.generate_entity_type_in_json(True))
        request.set_header('Accept', "application/json")
        request.set_header('Content-Type', "application/json")
        request.set_header('Content-Length', str(len(json_data)))
        request.rfile.write(json_data.encode('utf-8'))
        request.send(self.svc)
        self.assertTrue(request.responseCode == 204)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        self.assertTrue(len(request.wfile.getvalue()) == 0,
                        "Update must return 0 bytes")
        # now go behind the scenes to check the update really worked!
        customers = self.ds['SampleModel.SampleEntities.Customers']
        with customers.open() as collection:
            customer = collection['ALFKI']
            self.assertTrue(customer['CompanyName'] == "Example Inc Updated")
        # Now do a case with an updated link
        orders = self.ds['SampleModel.SampleEntities.Orders']
        with orders.open() as collection:
            order = collection[3]
        old_customer = order['Customer'].get_entity()
        self.assertTrue(old_customer.key() == 'XX=00', "Previous customer")
        order['Customer'].bind_entity(customer)
        request = MockRequest("/service.svc/Orders(3)", "PUT")
        json_data = ' '.join(order.generate_entity_type_in_json(True))
        request.set_header('Accept', "application/json")
        request.set_header('Content-Type', "application/json")
        request.set_header('Content-Length', str(len(json_data)))
        request.rfile.write(json_data.encode('utf-8'))
        request.send(self.svc)
        self.assertTrue(request.responseCode == 204)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertFalse("ETAG" in request.responseHeaders,
                         "Entity set Orders has no ETag")
        self.assertTrue(len(request.wfile.getvalue()) == 0,
                        "Update must return 0 bytes")
        # now go behind the scenes to check the update really worked!
        orders = self.ds['SampleModel.SampleEntities.Orders']
        with orders.open() as collection:
            order = collection[3]
        new_customer = order['Customer'].get_entity()
        self.assertTrue(new_customer.key() == 'ALFKI', "Customer updated")

    def test_update_complex_type(self):
        customers = self.ds['SampleModel.SampleEntities.Customers']
        with customers.open() as collection:
            customer = collection['ALFKI']
        customer['Address']['Street'].set_from_value("High Street")
        request = MockRequest("/service.svc/Customers('ALFKI')/Address", "PUT")
        doc = core.Document(root=core.Property)
        doc.root.set_xmlname((core.ODATA_DATASERVICES_NAMESPACE, 'Address'))
        doc.root.set_value(customer['Address'])
        data = str(doc).encode('utf-8')
        request.set_header('Content-Type', "application/xml")
        request.set_header('Content-Length', str(len(data)))
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 204)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        self.assertTrue(len(request.wfile.getvalue()) == 0,
                        "Update must return 0 bytes")
        # now go behind the scenes to check the update really worked!
        customers = self.ds['SampleModel.SampleEntities.Customers']
        with customers.open() as collection:
            customer = collection['ALFKI']
            self.assertTrue(
                customer['Address']['Street'].value == "High Street")

    def test_update_complex_type_json(self):
        customers = self.ds['SampleModel.SampleEntities.Customers']
        with customers.open() as collection:
            customer = collection['ALFKI']
        customer['Address']['Street'].set_from_value("High Street")
        request = MockRequest("/service.svc/Customers('ALFKI')/Address", "PUT")
        request.set_header('Accept', "application/json")
        data = core.complex_property_to_json_v1(customer['Address'])
        data = data.encode('utf-8')
        request.set_header('Content-Type', "application/json")
        request.set_header('Content-Length', str(len(data)))
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 204)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        self.assertTrue(len(request.wfile.getvalue()) == 0,
                        "Update must return 0 bytes")
        # now go behind the scenes to check the update really worked!
        customers = self.ds['SampleModel.SampleEntities.Customers']
        with customers.open() as collection:
            customer = collection['ALFKI']
            self.assertTrue(customer['Address']['Street'].value ==
                            "High Street")

    def test_update_primitive_property(self):
        customers = self.ds['SampleModel.SampleEntities.Customers']
        with customers.open() as collection:
            customer = collection['ALFKI']
        customer['CompanyName'].set_from_value("Example Inc Updated")
        request = MockRequest(
            "/service.svc/Customers('ALFKI')/CompanyName", "PUT")
        doc = core.Document(root=core.Property)
        doc.root.set_xmlname((core.ODATA_DATASERVICES_NAMESPACE,
                              'CompanyName'))
        doc.root.set_value(customer['CompanyName'])
        data = str(doc).encode('utf-8')
        request.set_header('Content-Type', "application/xml")
        request.set_header('Content-Length', str(len(data)))
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 204)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        self.assertTrue(len(request.wfile.getvalue()) == 0,
                        "Update must return 0 bytes")
        # now go behind the scenes to check the update really worked!
        customers = self.ds['SampleModel.SampleEntities.Customers']
        with customers.open() as collection:
            customer = collection['ALFKI']
            self.assertTrue(
                customer['CompanyName'].value == "Example Inc Updated")

    def test_update_primitive_property_json(self):
        customers = self.ds['SampleModel.SampleEntities.Customers']
        with customers.open() as collection:
            customer = collection['ALFKI']
        customer['CompanyName'].set_from_value("Example Inc Updated")
        request = MockRequest(
            "/service.svc/Customers('ALFKI')/CompanyName", "PUT")
        request.set_header('Accept', "application/json")
        data = core.simple_property_to_json_v1(customer['CompanyName'])
        data = data.encode('utf-8')
        request.set_header('Content-Type', "application/json")
        request.set_header('Content-Length', str(len(data)))
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 204)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        self.assertTrue(len(request.wfile.getvalue()) == 0,
                        "Update must return 0 bytes")
        # now go behind the scenes to check the update really worked!
        customers = self.ds['SampleModel.SampleEntities.Customers']
        with customers.open() as collection:
            customer = collection['ALFKI']
            self.assertTrue(
                customer['CompanyName'].value == "Example Inc Updated")

    def test_update_value(self):
        request = MockRequest(
            "/service.svc/Customers('ALFKI')/CompanyName/$value", "PUT")
        data = ul("Caf\xe9 Inc").encode("ISO-8859-1")
        # by default we use ISO-8859-1
        request.set_header('Content-Type', "text/plain")
        request.set_header('Content-Length', str(len(data)))
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 204)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        self.assertTrue(
            len(request.wfile.getvalue()) == 0, "Update must return 0 bytes")
        # now go behind the scenes to check the update really worked!
        customers = self.ds['SampleModel.SampleEntities.Customers']
        with customers.open() as collection:
            customer = collection['ALFKI']
            self.assertTrue(customer['CompanyName'].value == ul("Caf\xe9 Inc"))
        # Now use utf-8
        request = MockRequest(
            "/service.svc/Customers('ALFKI')/CompanyName/$value", "PUT")
        data = ul("Caf\xe9 Incorporated").encode("utf-8")
        request.set_header('Content-Type', "text/plain; charset=utf-8")
        request.set_header('Content-Length', str(len(data)))
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 204)
        with customers.open() as collection:
            customer = collection['ALFKI']
            self.assertTrue(
                customer['CompanyName'].value == ul("Caf\xe9 Incorporated"))

    def test_update_link(self):
        orders = self.ds['SampleModel.SampleEntities.Orders']
        with orders.open() as collection:
            order = collection[3]
        old_customer = order['Customer'].get_entity()
        self.assertTrue(old_customer.key() == 'XX=00', "Previous customer")
        customers = self.ds['SampleModel.SampleEntities.Customers']
        with customers.open() as collection:
            customer = collection['ALFKI']
        request = MockRequest("/service.svc/Orders(3)/$links/Customer", "PUT")
        doc = core.Document(root=core.URI)
        doc.root.set_value(str(customer.get_location()))
        data = str(doc).encode('utf-8')
        request.set_header('Content-Type', "application/xml")
        request.set_header('Content-Length', str(len(data)))
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 204)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertFalse(
            "ETAG" in request.responseHeaders, "ETag not allowed in response")
        self.assertTrue(
            len(request.wfile.getvalue()) == 0, "Update must return 0 bytes")
        # now go behind the scenes to check the update really worked!
        orders = self.ds['SampleModel.SampleEntities.Orders']
        with orders.open() as collection:
            order = collection[3]
        new_customer = order['Customer'].get_entity()
        self.assertTrue(new_customer.key() == 'ALFKI', "Customer updated")

    def test_update_link_json(self):
        orders = self.ds['SampleModel.SampleEntities.Orders']
        with orders.open() as collection:
            order = collection[3]
        old_customer = order['Customer'].get_entity()
        self.assertTrue(old_customer.key() == 'XX=00', "Previous customer")
        customers = self.ds['SampleModel.SampleEntities.Customers']
        with customers.open() as collection:
            customer = collection['ALFKI']
        request = MockRequest("/service.svc/Orders(3)/$links/Customer", "PUT")
        data = str(customer.link_json()).encode('utf-8')
        request.set_header('Content-Type', "application/json")
        request.set_header('Content-Length', str(len(data)))
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 204)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertFalse(
            "ETAG" in request.responseHeaders, "ETag not allowed in response")
        self.assertTrue(
            len(request.wfile.getvalue()) == 0, "Update must return 0 bytes")
        # now go behind the scenes to check the update really worked!
        orders = self.ds['SampleModel.SampleEntities.Orders']
        with orders.open() as collection:
            order = collection[3]
        new_customer = order['Customer'].get_entity()
        self.assertTrue(new_customer.key() == 'ALFKI', "Customer updated")

    def test_update_media_resource(self):
        data = DOCUMENT_TEXT
        h = hashlib.sha256()
        h.update(data)
        request = MockRequest("/service.svc/Documents(301)/$value", "PUT")
        request.set_header('Content-Type', "text/x-tolstoy")
        request.set_header('Content-Length', str(len(data)))
        request.rfile.write(data)
        request.send(self.svc)
        self.assertTrue(request.responseCode == 204)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue("ETAG" in request.responseHeaders, "Entity set ETag")
        self.assertTrue(request.responseHeaders[
                        'ETAG'] == "W/\"X'%s'\"" % h.hexdigest().upper(),
                        "ETag value: %s; expected %s" %
                        (request.responseHeaders['ETAG'],
                         h.hexdigest().upper()))
        self.assertTrue(
            len(request.wfile.getvalue()) == 0, "Update must return 0 bytes")
        documents = self.ds['SampleModel.SampleEntities.Documents']
        with documents.open() as collection:
            document = collection[301]
            # version should match the etag
            self.assertTrue(document['Version'].value == h.digest(),
                            'Version calculation')
            sread = io.BytesIO()
            sinfo = collection.read_stream(301, sread)
            self.assertTrue(str(sinfo.type) == "text/x-tolstoy")
            self.assertTrue(sinfo.size == len(data))
            self.assertTrue(sread.getvalue() == data)

    def test_delete_entity(self):
        request = MockRequest("/service.svc/Customers('ALFKI')", "DELETE")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 204)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertFalse("ETAG" in request.responseHeaders,
                         "ETag not allowed in response")
        self.assertTrue(len(request.wfile.getvalue()) == 0,
                        "Update must return 0 bytes")
        # now go behind the scenes to check the delete really worked!
        orders = self.ds['SampleModel.SampleEntities.Orders']
        with orders.open() as collection:
            order = collection[1]
            self.assertTrue(order['Customer'].get_entity() is None,
                            "order no longer linked to customer")
        customers = self.ds['SampleModel.SampleEntities.Customers']
        with customers.open() as collection:
            for customer in collection.itervalues():
                self.assertFalse(customer['CustomerID'].value == 'ALFKI',
                                 "Customer no longer exists")

    def test_delete_link1(self):
        request = MockRequest(
            "/service.svc/Customers('ALFKI')/$links/Orders(1)", "DELETE")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 204)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertFalse("ETAG" in request.responseHeaders,
                         "ETag not allowed in response")
        self.assertTrue(len(request.wfile.getvalue()) == 0,
                        "Update must return 0 bytes")
        # now go behind the scenes to check the delete really worked!
        orders = self.ds['SampleModel.SampleEntities.Orders']
        with orders.open() as collection:
            order = collection[1]
            self.assertTrue(order['Customer'].get_entity() is None,
                            "order no longer linked to customer")
        customers = self.ds['SampleModel.SampleEntities.Customers']
        with customers.open() as collection:
            customer = collection['ALFKI']
            with customer['Orders'].open() as orders:
                self.assertTrue(len(orders) == 1)
                for order in orders.itervalues():
                    self.assertFalse(order['OrderID'].value == 1,
                                     "Order(1) not linked")

    def test_delete_link2(self):
        request = MockRequest(
            "/service.svc/Orders(1)/$links/Customer", "DELETE")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 204)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertFalse("ETAG" in request.responseHeaders,
                         "ETag not allowed in response")
        self.assertTrue(len(request.wfile.getvalue()) == 0,
                        "Update must return 0 bytes")
        # now go behind the scenes to check the delete really worked!
        orders = self.ds['SampleModel.SampleEntities.Orders']
        with orders.open() as collection:
            order = collection[1]
            self.assertTrue(order['Customer'].get_entity() is None,
                            "order no longer linked to customer")
        customers = self.ds['SampleModel.SampleEntities.Customers']
        with customers.open() as collection:
            customer = collection['ALFKI']
            with customer['Orders'].open() as orders:
                self.assertTrue(len(orders) == 1)
                for order in orders.itervalues():
                    self.assertFalse(order['OrderID'].value == 1,
                                     "Order(1) not linked")

    def test_delete_value(self):
        request = MockRequest(
            "/service.svc/Customers('ALFKI')/Address/Street", "DELETE")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 204)
        self.assertTrue(
            request.responseHeaders['DATASERVICEVERSION'].startswith("2.0;"),
            "DataServiceVersion 2.0 expected")
        self.assertTrue(len(request.wfile.getvalue()) == 0,
                        "Update must return 0 bytes")
        # now go behind the scenes to check the delete really worked!
        customers = self.ds['SampleModel.SampleEntities.Customers']
        with customers.open() as collection:
            customer = collection['ALFKI']
            self.assertFalse(customer['Address']['Street'])
        # now try and delete a non-nullable value
        request = MockRequest(
            "/service.svc/Customers('ALFKI')/CompanyName", "DELETE")
        request.send(self.svc)
        self.assertTrue(request.responseCode == 400)
        with customers.open() as collection:
            customer = collection['ALFKI']
            self.assertTrue(customer['CompanyName'].value == "Example Inc")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
