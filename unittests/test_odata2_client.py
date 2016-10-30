#! /usr/bin/env python

import decimal
import logging
import random
import threading
import time
import unittest

from wsgiref.simple_server import make_server, WSGIRequestHandler

from pyslet import rfc2396 as uri
from pyslet import rfc5023 as app
from pyslet.odata2 import core
from pyslet.odata2 import csdl as edm
from pyslet.odata2 import client
from pyslet.odata2.memds import InMemoryEntityContainer
from pyslet.odata2.server import Server
from pyslet.py26 import py26

from test_odata2_core import DataServiceRegressionTests


HTTP_PORT = random.randint(1111, 9999)


def suite(prefix='test'):
    loader = unittest.TestLoader()
    loader.testMethodPrefix = prefix
    return unittest.TestSuite((
        loader.loadTestsFromTestCase(ODataTests),
        loader.loadTestsFromTestCase(ClientTests),
        loader.loadTestsFromTestCase(RegressionTests)
    ))


def load_tests(loader, tests, pattern):
    """Called when we execute this file directly.

    This rather odd definition includes a larger number of tests,
    including one starting "tesx" which hit the sample OData services on
    the internet."""
    # return suite('test')
    return suite('tes')


ODATA_SAMPLE_SERVICEROOT = \
    "http://services.odata.org/V2/Northwind/Northwind.svc/"
ODATA_SAMPLE_READWRITE = \
    "http://services.odata.org/(S(readwrite))/OData/OData.svc/"


class ODataTests(unittest.TestCase):

    def test_constants(self):
        pass


class ClientTests(unittest.TestCase):

    def tesx_constructor(self):
        c = client.Client(ODATA_SAMPLE_SERVICEROOT)
        self.assertTrue(isinstance(c, app.Client),
                        "OData client not an APP client")
        self.assertTrue(isinstance(c.service, app.Service),
                        "Service document is present")
        self.assertTrue(len(c.service.Workspace) == 1,
                        "Service not returning a single Workspace child")
        self.assertTrue(len(c.service.Workspace[0].Collection) > 0,
                        "Workspace empty")
        self.assertTrue(isinstance(c.serviceRoot, uri.URI),
                        "Service root should be a URI instance")
        self.assertTrue(len(c.feeds) > 0,
                        "At least one feed loaded from service")
        self.assertTrue("Products" in c.feeds,
                        "One feed called Products required")
        self.assertTrue(isinstance(c.feeds["Products"], edm.EntitySet),
                        "Feeds map to entity sets")

    def tesx_feed_entries(self):
        c = client.Client(ODATA_SAMPLE_SERVICEROOT)
        # now open a collection and iterate through it
        names = set()
        with c.feeds['Products'].open() as collection:
            n = len(collection)
            self.assertTrue(
                n > 10, "Sample has more than 10 products (found %i)" % n)
            for product in collection.itervalues():
                names.add(product['ProductName'].value)
            self.assertTrue(n == len(names))
            scottish_long_breads = collection[68]
            self.assertTrue(isinstance(scottish_long_breads['ProductID'],
                            edm.Int32Value))
            self.assertTrue(scottish_long_breads['ProductID'].value == 68)
            self.assertTrue(isinstance(scottish_long_breads['ProductName'],
                            edm.StringValue))
            self.assertTrue(scottish_long_breads['ProductName'].value ==
                            "Scottish Longbreads")
            self.assertTrue(isinstance(scottish_long_breads['SupplierID'],
                            edm.Int32Value))
            self.assertTrue(scottish_long_breads['SupplierID'].value == 8)
            self.assertTrue(isinstance(scottish_long_breads['CategoryID'],
                            edm.Int32Value))
            self.assertTrue(scottish_long_breads['CategoryID'].value == 3)
            self.assertTrue(isinstance(scottish_long_breads['QuantityPerUnit'],
                            edm.StringValue))
            self.assertTrue(
                scottish_long_breads['QuantityPerUnit'].value ==
                "10 boxes x 8 pieces")
            self.assertTrue(isinstance(scottish_long_breads['UnitPrice'],
                            edm.DecimalValue))
            self.assertTrue(
                scottish_long_breads['UnitPrice'].value.as_tuple() ==
                decimal.Decimal("12.5000").as_tuple())
            self.assertTrue(isinstance(scottish_long_breads['UnitsInStock'],
                            edm.Int16Value))
            self.assertTrue(scottish_long_breads['UnitsInStock'].value == 6)
            self.assertTrue(isinstance(scottish_long_breads['UnitsOnOrder'],
                            edm.Int16Value))
            self.assertTrue(scottish_long_breads['UnitsOnOrder'].value == 10)
            self.assertTrue(isinstance(scottish_long_breads['ReorderLevel'],
                            edm.Int16Value))
            self.assertTrue(scottish_long_breads['ReorderLevel'].value == 15)
            self.assertTrue(isinstance(scottish_long_breads['Discontinued'],
                            edm.BooleanValue))
            self.assertFalse(scottish_long_breads['Discontinued'].value)

    def tesx_orderby(self):
        c = client.Client(ODATA_SAMPLE_SERVICEROOT)
        with c.feeds['Products'].open() as collection:
            collection.set_orderby(
                core.CommonExpression.orderby_from_str("ProductName asc"))
            first_value = None
            last_value = None
            for product in collection.itervalues():
                last_value = product['ProductName'].value
                if first_value is None:
                    first_value = last_value
        self.assertTrue(
            first_value == "Alice Mutton", "Bad first value: %s" % first_value)
        self.assertTrue(
            last_value == "Zaanse koeken", "Bad last value: %s" % last_value)

    def tesx_filter(self):
        c = client.Client(ODATA_SAMPLE_SERVICEROOT)
        with c.feeds['Products'].open() as collection:
            collection.set_filter(
                core.CommonExpression.from_str(
                    "substringof('bread',ProductName)"))
            self.assertTrue(len(collection) == 1)
            product = collection.values()[0]
            self.assertTrue(product['ProductName'] == "Scottish Longbreads")
            scottish_long_breads = collection[68]
            self.assertTrue(scottish_long_breads['ProductID'].value == 68)
            try:
                collection[17]
                self.fail("Alice Mutton wasn't filtered")
            except KeyError:
                pass

    def tesx_navigation(self):
        c = client.Client(ODATA_SAMPLE_SERVICEROOT)
        with c.feeds['Customers'].open() as collection:
            customer = collection['ALFKI']
            self.assertFalse(customer['Orders'].isExpanded)
            with customer['Orders'].open() as orders:
                self.assertTrue(len(orders) == 6, "Number of orders")
                self.assertFalse(
                    isinstance(orders, edm.ExpandedEntityCollection))
            # now test expansion
            collection.set_expand({"Orders": None})
            customer = collection['ALFKI']
            self.assertTrue(customer['Orders'].isExpanded)
            with customer['Orders'].open() as orders:
                self.assertTrue(len(orders) == 6, "Number of orders")
                self.assertTrue(
                    isinstance(orders, core.ExpandedEntityCollection))


class LoggingHandler(WSGIRequestHandler):

    def log_message(self, format, *args):
        logging.info(format, *args)

regressionServerApp = None
regressionTestsDone = False


def run_regression_server():
    server = make_server(
        '', HTTP_PORT, regressionServerApp, handler_class=LoggingHandler)
    server.timeout = 10
    logging.info("Serving HTTP on port %i... (timeout %s)", HTTP_PORT,
                 repr(server.timeout))
    while not regressionTestsDone:
        server.handle_request()


class RegressionTests(DataServiceRegressionTests):

    def setUp(self):     # noqa
        global regressionServerApp
        DataServiceRegressionTests.setUp(self)
        self.container = InMemoryEntityContainer(
            self.ds['RegressionModel.RegressionContainer'])
        regressionServerApp = Server("http://localhost:%i/" % HTTP_PORT)
        regressionServerApp.SetModel(self.ds.get_document())
        t = threading.Thread(target=run_regression_server)
        t.setDaemon(True)
        t.start()
        logging.info("OData Client/Server combined tests starting HTTP "
                     "server on localhost, port %i" % HTTP_PORT)
        # yield time to allow the server to start up
        time.sleep(2)
        self.svcDS = self.ds
        self.client = client.Client("http://localhost:%i/" % HTTP_PORT)
        self.ds = self.client.model.DataServices

    def tearDown(self):     # noqa
        global regressionTestsDone
        DataServiceRegressionTests.tearDown(self)
        regressionTestsDone = True

    def test_all_tests(self):
        self.run_combined()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="[%(thread)d] %(levelname)s %(message)s")
    if py26:
        unittest.TextTestRunner().run(suite('tes'))
    else:
        unittest.main()
