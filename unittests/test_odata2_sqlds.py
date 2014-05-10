#! /usr/bin/env python

import unittest, logging
from test_odata2_core import DataServiceRegressionTests

def suite():
	loader=unittest.TestLoader()
	loader.testMethodPrefix='test'
	return unittest.TestSuite((
		loader.loadTestsFromTestCase(ThreadTests),
		loader.loadTestsFromTestCase(SQLDSTests),
		loader.loadTestsFromTestCase(RegressionTests),
		))

def load_tests(loader, tests, pattern):
	return suite()

from pyslet.odata2.sqlds import *
from pyslet.vfs import OSFilePath as FilePath
TEST_DATA_DIR=FilePath(FilePath(__file__).abspath().split()[0],'data_odatav2')


import random
import pyslet.odata2.csdl as edm
import pyslet.odata2.edmx as edmx


class MockCursor:
	def execute(self,query):
		pass
		
	def close(self):
		pass
	
	
class MockConnection:
	
	nOpen=0
	
	def __init__(self,**kwargs):
		self.args=kwargs
	
	def close(self):
		pass
	
	def commit(self):
		pass
	
	def rollback(self):
		pass
	
	def cursor(self):
		return MockCursor()

		
class MockAPI:
	def __init__(self,threadsafety=0):
		self.threadsafety=threadsafety
	
	Error=SQLError
	
	paramstyle='qmark'
	
	def connect(self,**kwargs):
		return MockConnection(**kwargs)


class MockContainer(SQLEntityContainer):
	def __init__(self,containerDef,dbapi,maxConnections=10):
		super(MockContainer,self).__init__(containerDef,dbapi,maxConnections)
		self.acquired=None
		self.acquired2=None
		
	def OpenConnection(self):
		return self.dbapi.connect()


def MockRunner(container):
	# a simple, short-lived thread to see if we can acquire a connection, wait 1 seconds
	connection=container.AcquireConnection(1)
	container.acquired=connection
	if connection is not None:
		container.ReleaseConnection(connection)


def MockRunner2(container):
	connection=container.AcquireConnection(1)
	container.acquired2=connection
	if connection is not None:
		t=threading.Thread(target=MockRunner,args=(container,))
		t.start()
		t.join()
		container.ReleaseConnection(connection)

def DeepRunner(container):
	depth=random.randint(1,10)
	i=0
	connections=[None]*depth
	for i in xrange(depth):
		connections[i]=container.AcquireConnection()
	for i in xrange(depth-1,-1,-1):
		container.ReleaseConnection(connections[i])

						
class ThreadTests(unittest.TestCase):

	def setUp(self):
		self.doc=edmx.Document()
		mdPath=TEST_DATA_DIR.join('sample_server','metadata.xml')
		with mdPath.open('rb') as f:
			self.doc.Read(f)
		self.containerDef=self.doc.root.DataServices["SampleModel.SampleEntities"]
		
	def tearDown(self):
		pass
		
	def testCaseLevel0(self):
		# we ask for 5 connections, but should only get one due to level 0
		container=MockContainer(self.containerDef,MockAPI(0),5)
		self.assertTrue(container.cPoolMax==1,"A pool with a single connection")
		# check we can acquire and release a connection from a different thread
		container.acquired=None
		t=threading.Thread(target=MockRunner,args=(container,))
		t.start()
		t.join()
		self.assertTrue(isinstance(container.acquired,MockConnection),"thread should have acquired the connection")
		cMatch=container.acquired
		c1=container.AcquireConnection()
		self.assertFalse(c1 is cMatch,"shared connection objects not allowed at level 0")
		container.acquired=None
		t=threading.Thread(target=MockRunner,args=(container,))
		t.start()
		t.join()
		self.assertTrue(container.acquired is None,"thread should have failed to acquire the connection")
		# with thread safety level 0, we should still be able to acquire a single connection twice
		c2=container.AcquireConnection()
		self.assertFalse(c2 is cMatch,"shared connection objects not allowed at level 0")
		container.ReleaseConnection(c2)
		# we should still have a lock on the connection
		container.acquired=None
		t=threading.Thread(target=MockRunner,args=(container,))
		t.start()
		t.join()
		self.assertTrue(container.acquired is None,"thread should have failed to acquire the connection")
		container.ReleaseConnection(c1)
		container.acquired=None
		t=threading.Thread(target=MockRunner,args=(container,))
		t.start()
		t.join()
		self.assertFalse(container.acquired is cMatch,"shared connection objects not allowed at level 0")

	def testCaseLevel1(self):
		# we ask for 2 connections and should get them
		container=MockContainer(self.containerDef,MockAPI(1),2)
		self.assertTrue(container.cPoolMax==2,"Expected 2 connections")
		# check we can acquire and release a connection from a different thread
		container.acquired=None
		t=threading.Thread(target=MockRunner,args=(container,))
		t.start()
		t.join()
		self.assertTrue(isinstance(container.acquired,MockConnection),"thread should have acquired the connection")
		c1=container.AcquireConnection()
		self.assertTrue(isinstance(container.acquired,MockConnection),"we should have acquired a connection")
		container.acquired=None
		t=threading.Thread(target=MockRunner,args=(container,))
		t.start()
		t.join()
		self.assertTrue(container.acquired is not c1,"thread should have acquired a different the connection")
		# with thread safety level 1, we should still be able to acquire a single connection twice
		c2=container.AcquireConnection()
		self.assertTrue(c2 is c1,"Must be the same connection")
		container.ReleaseConnection(c2)
		# now do the double runner
		container.acquired=None
		container.acquired2=None
		t=threading.Thread(target=MockRunner2,args=(container,))
		t.start()
		t.join()
		self.assertTrue(container.acquired2 is not None,"thread 2 should have acquired the connection")
		self.assertTrue(container.acquired is None,"thread 1 should not have acquired the connection")
		container.ReleaseConnection(c1)
		# now we released our connection, we should be able to do the double
		container.acquired=None
		container.acquired2=None
		t=threading.Thread(target=MockRunner2,args=(container,))
		t.start()
		t.join()
		self.assertTrue(container.acquired2 is not None,"thread 2 should have acquired the connection")
		self.assertTrue(container.acquired is not None,"thread 1 should also have acquired the connection")

	def testCaseLevel2(self):
		# we ask for 5 connections and should get them
		container=MockContainer(self.containerDef,MockAPI(2),5)
		self.assertTrue(container.cPoolMax==5,"Expected 5 connections")
		c1=container.AcquireConnection()
		self.assertTrue(isinstance(c1,MockConnection),"we should have acquired a connection")
		cMatch=c1
		container.acquired=None
		t=threading.Thread(target=MockRunner,args=(container,))
		t.start()
		t.join()
		self.assertTrue(container.acquired is not cMatch,"thread should not have acquired the same connection")
		# with thread safety level 2, we should still be able to acquire a single connection twice
		c2=container.AcquireConnection()
		self.assertTrue(c2 is c1,"Must be the same connection")
		container.ReleaseConnection(c2)
		# now do the double runner
		container.acquired=None
		container.acquired2=None
		t=threading.Thread(target=MockRunner2,args=(container,))
		t.start()
		t.join()
		self.assertTrue(container.acquired2 is not cMatch,"thread 2 should have acquired a different connection")
		self.assertTrue(container.acquired is not cMatch,"thread 1 should have acquired a different connection too")
		container.ReleaseConnection(c1)

	def testCaseMultiThread(self):
		# we ask for 5 connections and should get them
		container=MockContainer(self.containerDef,MockAPI(1),5)
		self.assertTrue(container.cPoolMax==5,"Expected 5 connections")
		threads=[]
		for i in xrange(100):
			threads.append(threading.Thread(target=DeepRunner,args=(container,)))
		for t in threads:
			t.start()
		while threads:
			t=threads.pop()
			t.join()
		# success criteria?  that we survived
		pass

	
class SQLDSTests(unittest.TestCase):

	def setUp(self):
		self.cwd=FilePath.getcwd()
		TEST_DATA_DIR.chdir()
		self.doc=edmx.Document()
		mdPath=TEST_DATA_DIR.join('sample_server','metadata.xml')
		with mdPath.open('rb') as f:
			self.doc.Read(f)
		self.schema=self.doc.root.DataServices['SampleModel']
		self.container=self.doc.root.DataServices["SampleModel.SampleEntities"]
		self.d=FilePath.mkdtemp('.d','pyslet-test_odata2_sqlds-')
		self.db=SQLiteEntityContainer(filePath=self.d.join('test.db'),containerDef=self.container)
				
	def tearDown(self):
		if self.db is not None:
			self.db.close()
		self.cwd.chdir()
		self.d.rmtree(True)
		
	def testCaseConstructors(self):
		es=self.schema['SampleEntities.Employees']
		self.assertTrue(isinstance(es.OpenCollection(),SQLEntityCollection))
		with es.OpenCollection() as collection:
			collection.CreateTable()
			self.assertTrue(collection.entitySet is es,"Entity set pointer")
			self.assertTrue(len(collection)==0,"Length on load")
		
	def testCaseInsert(self):
		es=self.schema['SampleEntities.Employees']
		with es.OpenCollection() as collection:
			# we'll need to create this table first
			collection.CreateTable()
			newHire=collection.NewEntity()
			self.assertTrue(isinstance(newHire,core.Entity))
			self.assertTrue(list(newHire.DataKeys())==["EmployeeID","EmployeeName","Address","Version"])
			newHire.SetKey('00001')
			newHire["EmployeeName"].SetFromValue('Joe Bloggs')
			newHire["Address"]["City"].SetFromValue('Chunton')
			newHire["Address"]["Street"].SetFromValue('Mill Road')
			# we leave the version concurrency token as NULL and assume it will be autofilled
			collection.InsertEntity(newHire)
			self.assertTrue(newHire.exists)
			self.assertTrue(newHire['EmployeeID'])
			self.assertTrue(newHire['Version'])
			self.assertTrue(len(collection)==1,"Length after insert")
			newHire=collection.NewEntity()
			newHire.SetKey('00001')
			newHire["EmployeeName"].SetFromValue('Jane Doe')
			try:
				collection.InsertEntity(newHire)
				self.fail("Double insert")
			except edm.ConstraintError:
				pass
	
	def testCaseUpdate(self):
		es=self.schema['SampleEntities.Employees']
		with es.OpenCollection() as collection:
			collection.CreateTable()
			newHire=collection.NewEntity()
			self.assertTrue(isinstance(newHire,core.Entity))
			self.assertTrue(list(newHire.DataKeys())==["EmployeeID","EmployeeName","Address","Version"])
			newHire.SetKey('00001')
			newHire["EmployeeName"].SetFromValue('Joe Bloggs')
			newHire["Address"]["City"].SetFromValue('Chunton')
			newHire["Address"]["Street"].SetFromValue('Mill Road')
			# we leave the version concurrency token as NULL and assume it will be autofilled
			collection.InsertEntity(newHire)
			self.assertTrue(newHire['Version'])
			# employee moves house some time later...
			talent=collection['00001']
			talent["Address"]["City"].SetFromValue('Chunton')
			talent["Address"]["Street"].SetFromValue('Main Street')
			collection.UpdateEntity(talent)
			self.assertTrue(talent['Version'])
			self.assertFalse(talent['Version'].value==newHire['Version'],"Concurrency token updated")
			# now let's try and change the name of the original entity too
			newHire["Address"]["Street"].SetFromValue('Main Street')
			try:
				collection.UpdateEntity(newHire)
				self.fail("Concurrency failure")
			except edm.ConcurrencyError:
				pass
	
	def testCaseDelete(self):
		es=self.schema['SampleEntities.Employees']
		with es.OpenCollection() as collection:
			collection.CreateTable()
			newHire=collection.NewEntity()
			self.assertTrue(isinstance(newHire,core.Entity))
			self.assertTrue(list(newHire.DataKeys())==["EmployeeID","EmployeeName","Address","Version"])
			newHire.SetKey('00001')
			newHire["EmployeeName"].SetFromValue('Joe Bloggs')
			newHire["Address"]["City"].SetFromValue('Chunton')
			newHire["Address"]["Street"].SetFromValue('Mill Road')
			# we leave the version concurrency token as NULL and assume it will be autofilled
			collection.InsertEntity(newHire)
			talent=collection['00001']			
			self.assertTrue(talent['EmployeeName'].value=="Joe Bloggs")
			self.assertTrue(len(collection)==1)
			try:
				del collection['00002']
				self.fail("Deleted non-existent entity")
			except KeyError:
				pass
			self.assertTrue(len(collection)==1)
			del collection['00001']
			self.assertTrue(len(collection)==0)
			try:
				leaver=collection['00001']
				self.fail("Deleted entity still retrieved")
			except KeyError:
				pass
	
	def testCaseIter(self):
		es=self.schema['SampleEntities.Employees']
		with es.OpenCollection() as collection:
			collection.CreateTable()
			for i in xrange(10):
				newHire=collection.NewEntity()
				newHire.SetKey('%05X'%i)
				newHire["EmployeeName"].SetFromValue('Talent #%i'%i)
				newHire["Address"]["City"].SetFromValue('Chunton')
				newHire["Address"]["Street"].SetFromValue(random.choice(('Mill Road','Main Street','Privet Drive')))
				collection.InsertEntity(newHire)
			self.assertTrue(len(collection)==10)
			keys=set()
			for talent in collection.values():
				self.assertTrue(talent['EmployeeName'].value.startswith('Talent '))
				keys.add(talent['EmployeeID'].value)
			self.assertTrue(len(keys)==10)

	def testCaseFilter(self):
		es=self.schema['SampleEntities.Employees']
		with es.OpenCollection() as collection:
			collection.CreateTable()
			for i in xrange(20):
				newHire=collection.NewEntity()
				newHire.SetKey('%05X'%i)
				newHire["EmployeeName"].SetFromValue('Talent #%i'%i)
				newHire["Address"]["City"].SetFromValue('Chunton')
				newHire["Address"]["Street"].SetFromValue(random.choice(('Mill Road','Main Street','Privet Drive')))
				collection.InsertEntity(newHire)
			self.assertTrue(len(collection)==20)
			collection.Filter(core.CommonExpression.FromString("substringof('Road',Address/Street)"))
			roads=len(collection)
			collection.Filter(core.CommonExpression.FromString("endswith(Address/Street,'Street')"))
			streets=len(collection)
			collection.Filter(core.CommonExpression.FromString("startswith(Address/Street,'Privet')"))
			drives=len(collection)
			self.assertTrue(roads+streets+drives==20,"Failed to match all records: %i found"%(roads+streets+drives))
			collection.Filter(core.CommonExpression.FromString("EmployeeName eq 'Talent #13'"))
			self.assertTrue(len(collection)==1,"Just one matching employee")
			talent=collection.values()[0]
			self.assertTrue(talent['EmployeeID'].value=='0000D')

	def testCaseOrderBy(self):
		es=self.schema['SampleEntities.Employees']
		with es.OpenCollection() as collection:
			collection.CreateTable()
			for i in xrange(20):
				newHire=collection.NewEntity()
				newHire.SetKey('%05X'%i)
				newHire["EmployeeName"].SetFromValue('Talent #%02i'%random.randint(1,99))	# Force alphabetic sorting
				newHire["Address"]["City"].SetFromValue('Chunton')
				newHire["Address"]["Street"].SetFromValue(random.choice(('Mill Road','Main Street','Privet Drive')))
				collection.InsertEntity(newHire)
			self.assertTrue(len(collection)==20)
			collection.OrderBy(core.CommonExpression.OrderByFromString("EmployeeName asc,Address/City desc"))
			lastTalent=None
			for talent in collection.values():
				if lastTalent is not None:
					self.assertTrue(talent['EmployeeName'].value>=lastTalent['EmployeeName'].value)
				lastTalent=talent
			# add a filter and check again
			collection.Filter(core.CommonExpression.FromString("endswith(Address/Street,'Drive')"))
			lastTalent=None
			for talent in collection.values():
				self.assertTrue(talent["Address"]["Street"].value==u'Privet Drive')
				if lastTalent is not None:
					self.assertTrue(talent['EmployeeName'].value>=lastTalent['EmployeeName'].value)
				lastTalent=talent			

	def testCaseNavigation(self):
# 		<Property Name="CustomerID" Type="Edm.String" Nullable="false" MaxLength="5"
# 			Unicode="true" FixedLength="true"/>
# 		<Property Name="CompanyName" Type="Edm.String" Nullable="false" MaxLength="40"
# 			Unicode="true" FixedLength="false"/>
# 		<Property Name="Address" Type="SampleModel.CAddress" Nullable="false"/>
# 		<Property Name="Version" Type="Edm.Binary" Nullable="true" MaxLength="8"
# 			FixedLength="true" ConcurrencyMode="Fixed"/>
# 		<NavigationProperty Name="Orders" Relationship="SampleModel.Orders_Customers"
# 			FromRole="Customer" ToRole="Order"/>
		es=self.schema['SampleEntities.Customers']
		with es.OpenCollection() as collection:
			# we'll need to create this table first
			collection.CreateTable()
			customer=collection.NewEntity()
			customer.SetKey('ALFKI')
			customer["CompanyName"].SetFromValue('Widget Inc')
			customer["Address"]["City"].SetFromValue('Chunton')
			customer["Address"]["Street"].SetFromValue('Factory Lane')
			# we leave the version concurrency token as NULL and assume it will be autofilled
			collection.InsertEntity(customer)
		es=self.schema['SampleEntities.Orders']
# 		<Property Name="OrderID" Type="Edm.Int32" Nullable="false"/>
# 		<Property Name="ShippedDate" Type="Edm.DateTime" Nullable="true"
# 			DateTimeKind="Unspecified" PreserveSeconds="true"/>
# 		<NavigationProperty Name="Customer" Relationship="SampleModel.Orders_Customers"
# 			FromRole="Order" ToRole="Customer"/>
# 		<NavigationProperty Name="OrderLine" Relationship="SampleModel.OrderLines_Orders"
# 			FromRole="Order" ToRole="OrderLine"/>
		with es.OpenCollection() as collection:
			# we'll need to create this table first too
			collection.CreateTable()
			order=collection.NewEntity()
			order.SetKey(1)
			order["ShippedDate"].SetFromLiteral('2013-10-02T10:20:59')
			collection.InsertEntity(order)
			with order['Customer'].OpenCollection() as parentCollection:
				parentCollection[customer.Key()]=customer
			# now check that get entity works
			matchCustomer=order['Customer'].GetEntity()
			self.assertTrue(matchCustomer is not None)
			self.assertTrue(matchCustomer.Key()==customer.Key())
		# now check the association the other way
		with customer['Orders'].OpenCollection() as collection:
			self.assertTrue(len(collection)==1)
			self.assertTrue(order.Key() in collection)
		# now add a second order for this customer
		with es.OpenCollection() as collection:
			# we'll need to create this table first too
			order=collection.NewEntity()
			order.SetKey(2)
			order["ShippedDate"].SetFromLiteral('2013-11-05T08:30:00')
			collection.InsertEntity(order)
			with order['Customer'].OpenCollection() as parentCollection:
				parentCollection[customer.Key()]=customer
				self.assertTrue(len(parentCollection)==1)
				# check with a filter
				parentCollection.Filter(core.CommonExpression.FromString("Address/City eq 'Chunton'"))
				self.assertTrue(len(parentCollection)==1)				
		# now check the association is working with filter and orderby too
		with customer['Orders'].OpenCollection() as collection:
			collection.OrderBy(core.CommonExpression.OrderByFromString("ShippedDate desc"))
			self.assertTrue(len(collection)==2)
			orders=collection.values()
			self.assertTrue(orders[0]['ShippedDate'].value>orders[1]['ShippedDate'].value)
			collection.OrderBy(core.CommonExpression.OrderByFromString("ShippedDate asc"))
			self.assertTrue(len(collection)==2)
			orders=collection.values()
			self.assertTrue(orders[1]['ShippedDate'].value>orders[0]['ShippedDate'].value)
			collection.Filter(core.CommonExpression.FromString("ShippedDate ge datetime'2013-11-01T00:00:00'"))
			self.assertTrue(len(collection)==1)
			self.assertTrue(order.Key() in collection)

	def testCaseAllTables(self):
		self.db.CreateAllTables()
		# run through each entity set and check there is no data in it
		container=self.schema['SampleEntities']
		for es in container.EntitySet:
			with es.OpenCollection() as collection:
				self.assertTrue(len(collection)==0,"No data in %s"%es.name)


class AutoFieldTests(unittest.TestCase):

	def setUp(self):
		self.cwd=FilePath.getcwd()
		TEST_DATA_DIR.chdir()
		self.doc=edmx.Document()
		mdPath=TEST_DATA_DIR.join('sample_server','metadata.xml')
		with mdPath.open('rb') as f:
			self.doc.Read(f)
		self.schema=self.doc.root.DataServices['SampleModel']
		self.container=self.doc.root.DataServices["SampleModel.SampleEntities"]
		self.d=FilePath.mkdtemp('.d','pyslet-test_odata2_sqlds-')
		self.db=SQLiteEntityContainer(filePath=self.d.join('test.db'),containerDef=self.container)

		
class RegressionTests(DataServiceRegressionTests):
	
	def setUp(self):
		DataServiceRegressionTests.setUp(self)
		self.container=self.ds['RegressionModel.RegressionContainer']
		self.d=FilePath.mkdtemp('.d','pyslet-test_odata2_sqlds-')
		self.db=SQLiteEntityContainer(filePath=self.d.join('test.db'),containerDef=self.container)
		self.db.CreateAllTables()
		
	def tearDown(self):
		if self.db is not None:
			self.db.close()
		self.d.rmtree(True)
		DataServiceRegressionTests.tearDown(self)
		
	def testCaseAllTests(self):
		self.RunAllCombined()		

			
if __name__ == "__main__":
	logging.basicConfig(level=logging.INFO)
	unittest.main()
