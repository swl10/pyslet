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


class RegressionTests(DataServiceRegressionTests):

    def setUp(self):     # noqa
        DataServiceRegressionTests.setUp(self)
        self.container = InMemoryEntityContainer(
            self.ds['RegressionModel.RegressionContainer'])
        self.port = random.randint(1111, 9999)
        self.server = Server("http://localhost:%i/" % self.port)
        self.server.set_model(self.ds.get_document())
        self.server_done = False
        t = threading.Thread(target=self.run_regression_server)
        t.setDaemon(True)
        t.start()
        logging.info("OData Client/Server combined tests starting HTTP "
                     "server on localhost, port %i" % self.port)
        # yield time to allow the server to start up
        time.sleep(2)
        self.svcDS = self.ds
        self.client = client.Client("http://localhost:%i/" % self.port)
        self.ds = self.client.model.DataServices

    def tearDown(self):     # noqa
        DataServiceRegressionTests.tearDown(self)
        self.server_done = True

    def run_regression_server(self):
        server = make_server(
            '', self.port, self.server, handler_class=LoggingHandler)
        server.timeout = 10
        logging.info("Serving HTTP on port %i... (timeout %s)", self.port,
                     repr(server.timeout))
        while not self.server_done:
            server.handle_request()

    def test_batch(self):
        # reuse the changeset entity sets
        container = self.ds['RegressionModel.RegressionContainer']
        es_a = container['ChangesetA']
        # start by creating a batch which we do on the client
        batch = self.client.new_batch()
        self.assertTrue(isinstance(batch, client.Batch))
        with es_a.open() as coll_a:
            a100 = coll_a.new_entity()
            a100['K'].set_from_value(100)
            a100['Data'].set_from_value('hello')
            coll_a.insert_entity(a100)
            a101 = coll_a.new_entity()
            a101['K'].set_from_value(101)
            a101['Data'].set_from_value('goodbye')
            coll_a.insert_entity(a101)
            # record the current length for later
            base_len1 = len(coll_a)
            batch.append_len(coll_a)
            batch.append_entity(coll_a, 101)
            # now filter the collection
            filter = core.CommonExpression.from_str("Data eq 'hello'")
            coll_a.set_filter(filter)
            base_len2 = len(coll_a)
            batch.append_len(coll_a)
            batch.append_entity(coll_a, 101)
            batch.append_entity(coll_a, 100)
            # the batch is like a read-only list
            self.assertTrue(len(batch) == 5)
            for i in range(5):
                # all items are None prior to execution
                self.assertTrue(batch[i] is None)
            # execute the batch
            batch.run()
            # same length
            self.assertTrue(len(batch) == 5)
            # items are now either the result of an exception...
            self.assertTrue(batch[0] == base_len1)
            result = batch[1]
            self.assertTrue(isinstance(result, edm.Entity))
            self.assertTrue(result['K'].value == 101)
            # with the filter, just 1 entity
            self.assertTrue(batch[2] == base_len2)
            result = batch[3]
            self.assertTrue(isinstance(result, KeyError))
            result = batch[4]
            self.assertTrue(isinstance(result, edm.Entity))
            self.assertTrue(result['K'].value == 100)

    def test_changesets(self):
        # temporary while we build out this feature
        try:
            self.runtest_changeset()
        except NotImplementedError:
            logging.warning("Changesets not supported, tests skipped")

    def test_all_tests(self):
        self.run_combined()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="[%(thread)d] %(levelname)s %(message)s")
    if py26:
        unittest.TextTestRunner().run(suite('tes'))
    else:
        unittest.main()
