#! /usr/bin/env python

import unittest
import logging
import random

import pyslet.odata2.csdl as edm
import pyslet.odata2.edmx as edmx
from pyslet.vfs import OSFilePath as FilePath

from test_odata2_core import DataServiceRegressionTests

from pyslet.odata2.sqlds import *  # noqa


TEST_DATA_DIR = FilePath(
    FilePath(__file__).abspath().split()[0],
    'data_odatav2')


def suite():
    loader = unittest.TestLoader()
    loader.testMethodPrefix = 'test'
    return unittest.TestSuite((
        loader.loadTestsFromTestCase(ThreadTests),
        loader.loadTestsFromTestCase(SQLDSTests),
        loader.loadTestsFromTestCase(RegressionTests),
    ))


def load_tests(loader, tests, pattern):
    return suite()


class MockCursor(object):

    def execute(self, query):
        pass

    def close(self):
        pass


class MockConnection(object):

    nOpen = 0

    def __init__(self, **kwargs):
        self.args = kwargs

    def close(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass

    def cursor(self):
        return MockCursor()


class MockAPI(object):

    def __init__(self, threadsafety=0):
        self.threadsafety = threadsafety

    Error = SQLError

    paramstyle = 'qmark'

    def connect(self, **kwargs):
        return MockConnection(**kwargs)


class MockContainer(SQLEntityContainer):

    def __init__(self, container, dbapi, max_connections=10):
        super(
            MockContainer,
            self).__init__(
            container,
            dbapi,
            max_connections)
        self.acquired = None
        self.acquired2 = None

    def open(self):
        return self.dbapi.connect()


def mock_runner(container):
    # a simple, short-lived thread to see if we can acquire a
    # connection, wait 1 seconds
    connection = container.acquire_connection(1)
    container.acquired = connection
    if connection is not None:
        container.release_connection(connection)


def mock_runner2(container):
    connection = container.acquire_connection(1)
    container.acquired2 = connection
    if connection is not None:
        t = threading.Thread(target=mock_runner, args=(container,))
        t.start()
        t.join()
        container.release_connection(connection)


def deep_runner(container):
    depth = random.randint(1, 10)
    i = 0
    connections = [None] * depth
    for i in xrange(depth):
        connections[i] = container.acquire_connection()
    for i in xrange(depth - 1, -1, -1):
        container.release_connection(connections[i])


class ThreadTests(unittest.TestCase):

    def setUp(self):  # noqa
        self.doc = edmx.Document()
        md_path = TEST_DATA_DIR.join('sample_server', 'metadata.xml')
        with md_path.open('rb') as f:
            self.doc.Read(f)
        self.container = self.doc.root.DataServices[
            "SampleModel.SampleEntities"]

    def tearDown(self):  # noqa
        pass

    def test_level0(self):
        # we ask for 5 connections, but should only get one due to level 0
        container = MockContainer(self.container, MockAPI(0), 5)
        self.assertTrue(
            container.cPoolMax == 1,
            "A pool with a single connection")
        # check we can acquire and release a connection from a different
        # thread
        container.acquired = None
        t = threading.Thread(target=mock_runner, args=(container,))
        t.start()
        t.join()
        self.assertTrue(
            isinstance(
                container.acquired,
                MockConnection),
            "thread should have acquired the connection")
        cmatch = container.acquired
        c1 = container.acquire_connection()
        self.assertFalse(
            c1 is cmatch,
            "shared connection objects not allowed at level 0")
        container.acquired = None
        t = threading.Thread(target=mock_runner, args=(container,))
        t.start()
        t.join()
        self.assertTrue(
            container.acquired is None,
            "thread should have failed to acquire the connection")
        # with thread safety level 0, we should still be able to acquire a
        # single connection twice
        c2 = container.acquire_connection()
        self.assertFalse(
            c2 is cmatch,
            "shared connection objects not allowed at level 0")
        container.release_connection(c2)
        # we should still have a lock on the connection
        container.acquired = None
        t = threading.Thread(target=mock_runner, args=(container,))
        t.start()
        t.join()
        self.assertTrue(
            container.acquired is None,
            "thread should have failed to acquire the connection")
        container.release_connection(c1)
        container.acquired = None
        t = threading.Thread(target=mock_runner, args=(container,))
        t.start()
        t.join()
        self.assertFalse(
            container.acquired is cmatch,
            "shared connection objects not allowed at level 0")

    def test_level1(self):
        # we ask for 2 connections and should get them
        container = MockContainer(self.container, MockAPI(1), 2)
        self.assertTrue(container.cPoolMax == 2, "Expected 2 connections")
        # check we can acquire and release a connection from a different
        # thread
        container.acquired = None
        t = threading.Thread(target=mock_runner, args=(container,))
        t.start()
        t.join()
        self.assertTrue(
            isinstance(
                container.acquired,
                MockConnection),
            "thread should have acquired the connection")
        c1 = container.acquire_connection()
        self.assertTrue(
            isinstance(
                container.acquired,
                MockConnection),
            "we should have acquired a connection")
        container.acquired = None
        t = threading.Thread(target=mock_runner, args=(container,))
        t.start()
        t.join()
        self.assertTrue(
            container.acquired is not c1,
            "thread should have acquired a different the connection")
        # with thread safety level 1, we should still be able to acquire a
        # single connection twice
        c2 = container.acquire_connection()
        self.assertTrue(c2 is c1, "Must be the same connection")
        container.release_connection(c2)
        # now do the double runner
        container.acquired = None
        container.acquired2 = None
        t = threading.Thread(target=mock_runner2, args=(container,))
        t.start()
        t.join()
        self.assertTrue(
            container.acquired2 is not None,
            "thread 2 should have acquired the connection")
        self.assertTrue(
            container.acquired is None,
            "thread 1 should not have acquired the connection")
        container.release_connection(c1)
        # now we released our connection, we should be able to do the double
        container.acquired = None
        container.acquired2 = None
        t = threading.Thread(target=mock_runner2, args=(container,))
        t.start()
        t.join()
        self.assertTrue(
            container.acquired2 is not None,
            "thread 2 should have acquired the connection")
        self.assertTrue(
            container.acquired is not None,
            "thread 1 should also have acquired the connection")

    def test_level2(self):
        # we ask for 5 connections and should get them
        container = MockContainer(self.container, MockAPI(2), 5)
        self.assertTrue(container.cPoolMax == 5, "Expected 5 connections")
        c1 = container.acquire_connection()
        self.assertTrue(
            isinstance(
                c1,
                MockConnection),
            "we should have acquired a connection")
        cmatch = c1
        container.acquired = None
        t = threading.Thread(target=mock_runner, args=(container,))
        t.start()
        t.join()
        self.assertTrue(
            container.acquired is not cmatch,
            "thread should not have acquired the same connection")
        # with thread safety level 2, we should still be able to acquire a
        # single connection twice
        c2 = container.acquire_connection()
        self.assertTrue(c2 is c1, "Must be the same connection")
        container.release_connection(c2)
        # now do the double runner
        container.acquired = None
        container.acquired2 = None
        t = threading.Thread(target=mock_runner2, args=(container,))
        t.start()
        t.join()
        self.assertTrue(
            container.acquired2 is not cmatch,
            "thread 2 should have acquired a different connection")
        self.assertTrue(
            container.acquired is not cmatch,
            "thread 1 should have acquired a different connection too")
        container.release_connection(c1)

    def test_multithread(self):
        # we ask for 5 connections and should get them
        container = MockContainer(self.container, MockAPI(1), 5)
        self.assertTrue(container.cPoolMax == 5, "Expected 5 connections")
        threads = []
        for i in xrange(100):
            threads.append(
                threading.Thread(
                    target=deep_runner,
                    args=(
                        container,
                    )))
        for t in threads:
            t.start()
        while threads:
            t = threads.pop()
            t.join()
        # success criteria?  that we survived
        pass


class SQLDSTests(unittest.TestCase):

    def setUp(self):  # noqa
        self.cwd = FilePath.getcwd()
        TEST_DATA_DIR.chdir()
        self.doc = edmx.Document()
        md_path = TEST_DATA_DIR.join('sample_server', 'metadata.xml')
        with md_path.open('rb') as f:
            self.doc.Read(f)
        self.schema = self.doc.root.DataServices['SampleModel']
        self.container = self.doc.root.DataServices[
            "SampleModel.SampleEntities"]
        self.d = FilePath.mkdtemp('.d', 'pyslet-test_odata2_sqlds-')
        self.db = SQLiteEntityContainer(
            file_path=self.d.join('test.db'),
            container=self.container)

    def tearDown(self):  # noqa
        if self.db is not None:
            self.db.close()
        self.cwd.chdir()
        self.d.rmtree(True)

    def test_constructors(self):
        es = self.schema['SampleEntities.Employees']
        self.assertTrue(isinstance(es.OpenCollection(), SQLEntityCollection))
        with es.OpenCollection() as collection:
            collection.create_table()
            self.assertTrue(collection.entity_set is es, "Entity set pointer")
            self.assertTrue(len(collection) == 0, "Length on load")

    def test_insert(self):
        es = self.schema['SampleEntities.Employees']
        with es.OpenCollection() as collection:
            # we'll need to create this table first
            collection.create_table()
            new_hire = collection.new_entity()
            self.assertTrue(isinstance(new_hire, core.Entity))
            self.assertTrue(
                list(
                    new_hire.DataKeys()) == [
                    "EmployeeID",
                    "EmployeeName",
                    "Address",
                    "Version"])
            new_hire.SetKey('00001')
            new_hire["EmployeeName"].SetFromValue('Joe Bloggs')
            new_hire["Address"]["City"].SetFromValue('Chunton')
            new_hire["Address"]["Street"].SetFromValue('Mill Road')
            # we leave the version concurrency token as NULL and assume
            # it will be autofilled
            collection.insert_entity(new_hire)
            self.assertTrue(new_hire.exists)
            self.assertTrue(new_hire['EmployeeID'])
            self.assertTrue(new_hire['Version'])
            self.assertTrue(len(collection) == 1, "Length after insert")
            new_hire = collection.new_entity()
            new_hire.SetKey('00001')
            new_hire["EmployeeName"].SetFromValue('Jane Doe')
            try:
                collection.insert_entity(new_hire)
                self.fail("Double insert")
            except edm.ConstraintError:
                pass

    def test_update(self):
        es = self.schema['SampleEntities.Employees']
        with es.OpenCollection() as collection:
            collection.create_table()
            new_hire = collection.new_entity()
            self.assertTrue(isinstance(new_hire, core.Entity))
            self.assertTrue(
                list(
                    new_hire.DataKeys()) == [
                    "EmployeeID",
                    "EmployeeName",
                    "Address",
                    "Version"])
            new_hire.SetKey('00001')
            new_hire["EmployeeName"].SetFromValue('Joe Bloggs')
            new_hire["Address"]["City"].SetFromValue('Chunton')
            new_hire["Address"]["Street"].SetFromValue('Mill Road')
            # we leave the version concurrency token as NULL and assume
            # it will be autofilled
            collection.insert_entity(new_hire)
            self.assertTrue(new_hire['Version'])
            # employee moves house some time later...
            talent = collection['00001']
            talent["Address"]["City"].SetFromValue('Chunton')
            talent["Address"]["Street"].SetFromValue('Main Street')
            collection.update_entity(talent)
            self.assertTrue(talent['Version'])
            self.assertFalse(
                talent['Version'].value == new_hire['Version'],
                "Concurrency token updated")
            # now let's try and change the name of the original entity too
            new_hire["Address"]["Street"].SetFromValue('Main Street')
            try:
                collection.update_entity(new_hire)
                self.fail("Concurrency failure")
            except edm.ConcurrencyError:
                pass

    def test_delete(self):
        es = self.schema['SampleEntities.Employees']
        with es.OpenCollection() as collection:
            collection.create_table()
            new_hire = collection.new_entity()
            self.assertTrue(isinstance(new_hire, core.Entity))
            self.assertTrue(
                list(
                    new_hire.DataKeys()) == [
                    "EmployeeID",
                    "EmployeeName",
                    "Address",
                    "Version"])
            new_hire.SetKey('00001')
            new_hire["EmployeeName"].SetFromValue('Joe Bloggs')
            new_hire["Address"]["City"].SetFromValue('Chunton')
            new_hire["Address"]["Street"].SetFromValue('Mill Road')
            # we leave the version concurrency token as NULL and assume
            # it will be autofilled
            collection.insert_entity(new_hire)
            talent = collection['00001']
            self.assertTrue(talent['EmployeeName'].value == "Joe Bloggs")
            self.assertTrue(len(collection) == 1)
            try:
                del collection['00002']
                self.fail("Deleted non-existent entity")
            except KeyError:
                pass
            self.assertTrue(len(collection) == 1)
            del collection['00001']
            self.assertTrue(len(collection) == 0)
            try:
                collection['00001']
                self.fail("Deleted entity still retrieved")
            except KeyError:
                pass

    def test_iter(self):
        es = self.schema['SampleEntities.Employees']
        with es.OpenCollection() as collection:
            collection.create_table()
            for i in xrange(10):
                new_hire = collection.new_entity()
                new_hire.SetKey('%05X' % i)
                new_hire["EmployeeName"].SetFromValue('Talent #%i' % i)
                new_hire["Address"]["City"].SetFromValue('Chunton')
                new_hire["Address"]["Street"].SetFromValue(
                    random.choice(
                        ('Mill Road', 'Main Street', 'Privet Drive')))
                collection.insert_entity(new_hire)
            self.assertTrue(len(collection) == 10)
            keys = set()
            for talent in collection.values():
                self.assertTrue(
                    talent['EmployeeName'].value.startswith('Talent '))
                keys.add(talent['EmployeeID'].value)
            self.assertTrue(len(keys) == 10)

    def test_filter(self):
        es = self.schema['SampleEntities.Employees']
        with es.OpenCollection() as collection:
            collection.create_table()
            for i in xrange(20):
                new_hire = collection.new_entity()
                new_hire.SetKey('%05X' % i)
                new_hire["EmployeeName"].SetFromValue('Talent #%i' % i)
                new_hire["Address"]["City"].SetFromValue('Chunton')
                new_hire["Address"]["Street"].SetFromValue(
                    random.choice(
                        ('Mill Road', 'Main Street', 'Privet Drive')))
                collection.insert_entity(new_hire)
            self.assertTrue(len(collection) == 20)
            collection.set_filter(
                core.CommonExpression.FromString(
                    "substringof('Road',Address/Street)"))
            roads = len(collection)
            collection.set_filter(
                core.CommonExpression.FromString(
                    "endswith(Address/Street,'Street')"))
            streets = len(collection)
            collection.set_filter(
                core.CommonExpression.FromString(
                    "startswith(Address/Street,'Privet')"))
            drives = len(collection)
            self.assertTrue(
                roads +
                streets +
                drives == 20,
                "Failed to match all records: %i found" %
                (roads +
                 streets +
                 drives))
            collection.set_filter(
                core.CommonExpression.FromString(
                    "EmployeeName eq 'Talent #13'"))
            self.assertTrue(len(collection) == 1, "Just one matching employee")
            talent = collection.values()[0]
            self.assertTrue(talent['EmployeeID'].value == '0000D')

    def test_orderby(self):
        es = self.schema['SampleEntities.Employees']
        with es.OpenCollection() as collection:
            collection.create_table()
            for i in xrange(20):
                new_hire = collection.new_entity()
                new_hire.SetKey('%05X' % i)
                new_hire["EmployeeName"].SetFromValue(
                    'Talent #%02i' %
                    random.randint(
                        1,
                        99))  # Force alphabetic sorting
                new_hire["Address"]["City"].SetFromValue('Chunton')
                new_hire["Address"]["Street"].SetFromValue(
                    random.choice(
                        ('Mill Road', 'Main Street', 'Privet Drive')))
                collection.insert_entity(new_hire)
            self.assertTrue(len(collection) == 20)
            collection.set_orderby(
                core.CommonExpression.OrderByFromString(
                    "EmployeeName asc,Address/City desc"))
            last_talent = None
            for talent in collection.values():
                if last_talent is not None:
                    self.assertTrue(
                        talent['EmployeeName'].value >=
                        last_talent['EmployeeName'].value)
                last_talent = talent
            # add a filter and check again
            collection.set_filter(
                core.CommonExpression.FromString(
                    "endswith(Address/Street,'Drive')"))
            last_talent = None
            for talent in collection.values():
                self.assertTrue(
                    talent["Address"]["Street"].value == u'Privet Drive')
                if last_talent is not None:
                    self.assertTrue(
                        talent['EmployeeName'].value >=
                        last_talent['EmployeeName'].value)
                last_talent = talent

    def test_navigation(self):
        # <Property Name="CustomerID" Type="Edm.String" Nullable="false"
        #     MaxLength="5" Unicode="true" FixedLength="true"/>
        # <Property Name="CompanyName" Type="Edm.String" Nullable="false"
        #     MaxLength="40" Unicode="true" FixedLength="false"/>
        # <Property Name="Address" Type="SampleModel.CAddress"
        #     Nullable="false"/>
        # <Property Name="Version" Type="Edm.Binary" Nullable="true"
        #     MaxLength="8" FixedLength="true" ConcurrencyMode="Fixed"/>
        # <NavigationProperty Name="Orders"
        #     Relationship="SampleModel.Orders_Customers"
        #     FromRole="Customer" ToRole="Order"/>
        es = self.schema['SampleEntities.Customers']
        with es.OpenCollection() as collection:
            # we'll need to create this table first
            collection.create_table()
            customer = collection.new_entity()
            customer.SetKey('ALFKI')
            customer["CompanyName"].SetFromValue('Widget Inc')
            customer["Address"]["City"].SetFromValue('Chunton')
            customer["Address"]["Street"].SetFromValue('Factory Lane')
            # we leave the version concurrency token as NULL and assume
            # it will be autofilled
            collection.insert_entity(customer)
        es = self.schema['SampleEntities.Orders']
        # <Property Name="OrderID" Type="Edm.Int32" Nullable="false"/>
        # <Property Name="ShippedDate" Type="Edm.DateTime" Nullable="true"
        #     DateTimeKind="Unspecified" PreserveSeconds="true"/>
        # <NavigationProperty Name="Customer"
        #     Relationship="SampleModel.Orders_Customers"
        #     FromRole="Order" ToRole="Customer"/>
        # <NavigationProperty Name="OrderLine"
        #     Relationship="SampleModel.OrderLines_Orders"
        #     FromRole="Order" ToRole="OrderLine"/>
        with es.OpenCollection() as collection:
            # we'll need to create this table first too
            collection.create_table()
            order = collection.new_entity()
            order.SetKey(1)
            order["ShippedDate"].SetFromLiteral('2013-10-02T10:20:59')
            collection.insert_entity(order)
            with order['Customer'].OpenCollection() as parentCollection:
                parentCollection[customer.Key()] = customer
            # now check that get entity works
            match_customer = order['Customer'].GetEntity()
            self.assertTrue(match_customer is not None)
            self.assertTrue(match_customer.Key() == customer.Key())
        # now check the association the other way
        with customer['Orders'].OpenCollection() as collection:
            self.assertTrue(len(collection) == 1)
            self.assertTrue(order.Key() in collection)
        # now add a second order for this customer
        with es.OpenCollection() as collection:
            # we'll need to create this table first too
            order = collection.new_entity()
            order.SetKey(2)
            order["ShippedDate"].SetFromLiteral('2013-11-05T08:30:00')
            collection.insert_entity(order)
            with order['Customer'].OpenCollection() as parentCollection:
                parentCollection[customer.Key()] = customer
                self.assertTrue(len(parentCollection) == 1)
                # check with a filter
                parentCollection.set_filter(
                    core.CommonExpression.FromString(
                        "Address/City eq 'Chunton'"))
                self.assertTrue(len(parentCollection) == 1)
        # now check the association is working with filter and orderby too
        with customer['Orders'].OpenCollection() as collection:
            collection.set_orderby(
                core.CommonExpression.OrderByFromString("ShippedDate desc"))
            self.assertTrue(len(collection) == 2)
            orders = collection.values()
            self.assertTrue(
                orders[0]['ShippedDate'].value >
                orders[1]['ShippedDate'].value)
            collection.set_orderby(
                core.CommonExpression.OrderByFromString("ShippedDate asc"))
            self.assertTrue(len(collection) == 2)
            orders = collection.values()
            self.assertTrue(
                orders[1]['ShippedDate'].value >
                orders[0]['ShippedDate'].value)
            collection.set_filter(
                core.CommonExpression.FromString(
                    "ShippedDate ge datetime'2013-11-01T00:00:00'"))
            self.assertTrue(len(collection) == 1)
            self.assertTrue(order.Key() in collection)

    def test_all_tables(self):
        self.db.create_all_tables()
        # run through each entity set and check there is no data in it
        container = self.schema['SampleEntities']
        for es in container.EntitySet:
            with es.OpenCollection() as collection:
                self.assertTrue(
                    len(collection) == 0,
                    "No data in %s" %
                    es.name)


class AutoFieldTests(unittest.TestCase):

    def setUp(self):  # noqa
        self.cwd = FilePath.getcwd()
        TEST_DATA_DIR.chdir()
        self.doc = edmx.Document()
        md_path = TEST_DATA_DIR.join('sample_server', 'metadata.xml')
        with md_path.open('rb') as f:
            self.doc.Read(f)
        self.schema = self.doc.root.DataServices['SampleModel']
        self.container = self.doc.root.DataServices[
            "SampleModel.SampleEntities"]
        self.d = FilePath.mkdtemp('.d', 'pyslet-test_odata2_sqlds-')
        self.db = SQLiteEntityContainer(
            file_path=self.d.join('test.db'),
            container=self.container)


class RegressionTests(DataServiceRegressionTests):

    def setUp(self):  # noqa
        DataServiceRegressionTests.setUp(self)
        self.container = self.ds['RegressionModel.RegressionContainer']
        self.d = FilePath.mkdtemp('.d', 'pyslet-test_odata2_sqlds-')
        self.db = SQLiteEntityContainer(
            file_path=self.d.join('test.db'),
            container=self.container)
        self.db.create_all_tables()

    def tearDown(self):  # noqa
        if self.db is not None:
            self.db.close()
        self.d.rmtree(True)
        DataServiceRegressionTests.tearDown(self)

    def test_all_tests(self):
        self.RunAllCombined()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
