#! /usr/bin/env python

import logging
import unittest

from pyslet import mysqldbds as mysql

from test_odata2_core import DataServiceRegressionTests


MYSQL_HOST = "localhost"
MYSQL_USER = "pyslet"
MYSQL_PASSWORD = "pyslet"
MYSQL_DB = "pyslet"
MYSQL_TABLE_PREFIX = "test_"
MYSQL_STREAM_PREFIX = "strm_"


def suite():
    loader = unittest.TestLoader()
    loader.testMethodPrefix = 'test'
    return unittest.TestSuite((
        loader.loadTestsFromTestCase(RegressionTests),
    ))


def load_tests(loader, tests, pattern):
    return suite()


class RegressionTests(DataServiceRegressionTests):

    def setUp(self):  # noqa
        DataServiceRegressionTests.setUp(self)
        self.container = self.ds['RegressionModel.RegressionContainer']
        self.streamstore = mysql.MySQLStreamStore(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            passwd=MYSQL_PASSWORD,
            db=MYSQL_DB,
            prefix=MYSQL_STREAM_PREFIX)
        self.db = mysql.MySQLEntityContainer(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            passwd=MYSQL_PASSWORD,
            db=MYSQL_DB,
            prefix='',
            container=self.container,
            streamstore=self.streamstore)
        # drop all the tables first to clean down
        self.db.drop_all_tables()
        self.streamstore.container.drop_all_tables()
        self.db.create_all_tables()
        self.streamstore.container.create_all_tables()

    def tearDown(self):  # noqa
        if self.db is not None:
            self.db.close()
        DataServiceRegressionTests.tearDown(self)

    def test_all_tests(self):
        self.run_combined()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
