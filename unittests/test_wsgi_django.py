#! /usr/bin/env python

import logging
import optparse
import os.path
import unittest


from pyslet.wsgi_django import DjangoApp


def suite(prefix='test'):
    loader = unittest.TestLoader()
    loader.testMethodPrefix = prefix
    return unittest.TestSuite((
        loader.loadTestsFromTestCase(DjangoAppTests),
    ))


SETTINGS_FILE = os.path.join(
    os.path.join(os.path.split(__file__)[0], 'data_django'), 'settings.json')


class DjangoAppTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.settings_file = os.path.abspath(SETTINGS_FILE)

    def tearDown(self):     # noqa
        pass

    def test_debug_option(self):
        class DebugApp(DjangoApp):
            settings_file = self.settings_file
        p = optparse.OptionParser()
        DebugApp.add_options(p)
        options, args = p.parse_args([])
        self.assertTrue(options.debug is False)
        DebugApp.setup(options=options, args=args)
        # check setting value
        self.assertTrue(DebugApp.debug is False)

        class DebugApp(DjangoApp):
            settings_file = self.settings_file
        options, args = p.parse_args(['-d'])
        self.assertTrue(options.debug is True)
        DebugApp.setup(options=options, args=args)
        self.assertTrue(DebugApp.debug is True)

        class DebugApp(DjangoApp):
            settings_file = self.settings_file
        options, args = p.parse_args(['--debug'])
        self.assertTrue(options.debug is True)
        DebugApp.setup(options=options, args=args)
        self.assertTrue(DebugApp.debug is True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
