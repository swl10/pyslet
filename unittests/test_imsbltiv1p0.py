#! /usr/bin/env python

import unittest, pkg_resources, StringIO

from pyslet.imsbltiv1p0 import *

if oauth is None:
	print "Basic LTI tests skipped"
	print "\tTry installing oath from http://code.google.com/p/oauth  (oauth-1.0.1)"
	
	def suite():
		return unittest.TestSuite((
			unittest.makeSuite(BLTITests,'test')
			))		

else:
	print "Designed for oauth-1.0.1"
	print "\tTesting with oauth: %s"%pkg_resources.get_distribution("oauth").version

	def suite():		
		return unittest.TestSuite((
			unittest.makeSuite(BLTITests,'test'),
			unittest.makeSuite(BLTIProviderTests,'test')
			))


class BLTITests(unittest.TestCase):
	def testCaseConstants(self):
		self.failUnless(BLTI_VERSION=="LTI-1p0")
		self.failUnless(BLTI_LAUNCH_REQUEST=="basic-lti-launch-request")


EXAMPLE_CONSUMERS="""www.example.com Secret
www.questionmark.com password
"""

class BLTIProviderTests(unittest.TestCase):
	def testCaseConstructor(self):
		tp=BLTIToolProvider()
	
	def testCaseNewConsumer(self):
		tp=BLTIToolProvider()
		keys={}
		secrets={}
		for i in xrange(100):
			key,secret=tp.NewConsumer()
			self.failIf(keys.has_key(key),"Repeated key from TP")
			keys[key]=secret
			self.failIf(secrets.has_key(secret),"Repeated secret from IP")
			secrets[secret]=key
		key,secret=tp.NewConsumer("www.example.com")
		try:
			key,secret=tp.NewConsumer("www.example.com")
			self.fail("Failure to spot duplicate key")
		except BLTIDuplicateKeyError:
			pass
	
	def testCaseLookup(self):
		tp=BLTIToolProvider()
		key,secret=tp.NewConsumer('hello')
		consumer=tp.lookup_consumer('hello')
		self.failUnless(consumer.key=='hello')
		self.failUnless(consumer.secret==secret)

	def testCaseLoadSave(self):
		tp=BLTIToolProvider()
		tp.LoadFromFile(StringIO.StringIO(EXAMPLE_CONSUMERS))
		consumer=tp.lookup_consumer('www.example.com')
		self.failUnless(consumer.secret=="Secret")
		try:
			tp.LoadFromFile(StringIO.StringIO(EXAMPLE_CONSUMERS))
			self.fail("Faiure to spot duplicate key on reload")
		except BLTIDuplicateKeyError:
			pass
		f=StringIO.StringIO()
		tp.SaveToFile(f)
		self.failUnless(f.getvalue()==EXAMPLE_CONSUMERS)

	def testCaseLaunch(self):
		tp=BLTIToolProvider()
		tp.LoadFromFile(StringIO.StringIO(EXAMPLE_CONSUMERS))
		
if __name__ == "__main__":
	unittest.main()

