#! /usr/bin/env python

import unittest
import StringIO

try:
    import pkg_resources
except ImportError:
    pkg_resources = None

import pyslet.imsbltiv1p0 as lti


if lti.oauth is None:
    print "Basic LTI tests skipped"
    print "\tTry installing oath from http://code.google.com/p/oauth  "\
        "(oauth-1.0.1)"

    def suite():
        return unittest.TestSuite((
            unittest.makeSuite(BLTITests, 'test')
        ))

else:
    if pkg_resources:
        v = pkg_resources.get_distribution("oauth").version
        if v != "1.0.1":
            print "\tDesigned for oauth-1.0.1, testing with version %s" % v
    else:
        print "\tCannot determine oauth installed package version; "\
            "install setuptools to remove this message"

    def suite():
        return unittest.TestSuite((
            unittest.makeSuite(BLTITests, 'test'),
            unittest.makeSuite(BLTIProviderTests, 'test')
        ))


class BLTITests(unittest.TestCase):

    def test_constants(self):
        self.assertTrue(lti.BLTI_VERSION == "LTI-1p0")
        self.assertTrue(lti.BLTI_LAUNCH_REQUEST == "basic-lti-launch-request")


EXAMPLE_CONSUMERS = """www.example.com Secret
www.questionmark.com password
"""


class BLTIProviderTests(unittest.TestCase):

    def test_constructor(self):
        lti.BLTIToolProvider()

    def test_new_consumer(self):
        tp = lti.BLTIToolProvider()
        keys = {}
        secrets = {}
        for i in xrange(100):
            key, secret = tp.new_consumer()
            self.assertFalse(key in keys, "Repeated key from TP")
            keys[key] = secret
            self.assertFalse(secret in secrets, "Repeated secret from IP")
            secrets[secret] = key
        key, secret = tp.new_consumer("www.example.com")
        try:
            key, secret = tp.new_consumer("www.example.com")
            self.fail("Failure to spot duplicate key")
        except lti.BLTIDuplicateKeyError:
            pass

    def test_lookup(self):
        tp = lti.BLTIToolProvider()
        key, secret = tp.new_consumer('hello')
        consumer = tp.lookup_consumer('hello')
        self.assertTrue(consumer.key == 'hello')
        self.assertTrue(consumer.secret == secret)

    def test_load_save(self):
        tp = lti.BLTIToolProvider()
        tp.load_from_file(StringIO.StringIO(EXAMPLE_CONSUMERS))
        consumer = tp.lookup_consumer('www.example.com')
        self.assertTrue(consumer.secret == "Secret")
        try:
            tp.load_from_file(StringIO.StringIO(EXAMPLE_CONSUMERS))
            self.fail("Faiure to spot duplicate key on reload")
        except lti.BLTIDuplicateKeyError:
            pass
        f = StringIO.StringIO()
        tp.save_to_file(f)
        self.assertTrue(f.getvalue() == EXAMPLE_CONSUMERS)

    def test_launch(self):
        tp = lti.BLTIToolProvider()
        tp.load_from_file(StringIO.StringIO(EXAMPLE_CONSUMERS))

if __name__ == "__main__":
    unittest.main()
