#! /usr/bin/env python

import unittest

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(XSDatatypes20041028Tests,'test'),
		unittest.makeSuite(XSDatatypesBooleanTests,'test')
		))

from pyslet.xsdatatypes20041028 import *

class XSDatatypes20041028Tests(unittest.TestCase):		
	def testCaseConstants(self):
		pass
		#self.failUnless(APP_NAMESPACE=="http://www.w3.org/2007/app","Wrong APP namespace: %s"%APP_NAMESPACE)
		#self.failUnless(ATOMSVC_MIMETYPE=="application/atomsvc+xml","Wrong APP service mime type: %s"%ATOMSVC_MIMETYPE)
		#self.failUnless(ATOMCAT_MIMETYPE=="application/atomcat+xml","Wrong APP category mime type: %s"%ATOMCAT_MIMETYPE)

class XSDatatypesBooleanTests(unittest.TestCase):		
	def testCaseDencode(self):
		self.failUnless(DecodeBoolean('true') is True,'true')
		self.failUnless(DecodeBoolean('1') is True,'1')
		self.failUnless(DecodeBoolean('false') is False,'false')
		self.failUnless(DecodeBoolean('0') is False,'0')
		self.failUnless(DecodeBoolean(None) is None,'None')
		try:
			DecodeBoolean('False'); self.fail('False')
		except ValueError:
			pass
		try:
			DecodeBoolean('True'); self.fail('True')
		except ValueError:
			pass
		try:
			DecodeBoolean('yes'); self.fail('yes')
		except ValueError:
			pass

	def testCaseEncode(self):
		self.failUnless(EncodeBoolean(True)=="true",'True')
		self.failUnless(EncodeBoolean(False)=="false",'False')
		self.failUnless(EncodeBoolean(1)=="true",'1')
		self.failUnless(EncodeBoolean(0)=="false",'0')
		self.failUnless(EncodeBoolean(['a'])=="true",'Non-empty list')
		self.failUnless(EncodeBoolean([])=="false",'Empty list')
		try:
			EncodeBoolean(None); self.fail('None')
		except ValueError:
			pass
