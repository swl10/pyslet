#! /usr/bin/env python

import unittest

import pyslet.odata2.core as core
import pyslet.odata2.csdl as edm
import decimal
from pyslet.odata2.client import *

VERBOSE=True

def suite(prefix='test'):
	loader=unittest.TestLoader()
	loader.testMethodPrefix=prefix
	return unittest.TestSuite((
		loader.loadTestsFromTestCase(ODataTests),
# 		loader.loadTestsFromTestCase(ODataURILiteralTests),
 		loader.loadTestsFromTestCase(ClientTests),
# 		loader.loadTestsFromTestCase(ODataURITests),
# 		loader.loadTestsFromTestCase(ServerTests),
# 		loader.loadTestsFromTestCase(SampleServerTests),
# 		loader.loadTestsFromTestCase(ODataStoreClientTests)		
		))
		
def load_tests(loader, tests, pattern):
	"""Called when we execute this file directly.
	
	This rather odd definition includes a larger number of tests, including one
	starting "tesx" which hit the sample OData services on the internet."""
	#return suite('test')
	return suite('tes')


#ODATA_SAMPLE_SERVICEROOT="http://services.odata.org/OData/OData.svc/"
#ODATA_SAMPLE_READWRITE="http://services.odata.org/(S(readwrite))/OData/OData.svc/"

ODATA_SAMPLE_SERVICEROOT="http://services.odata.org/Northwind/Northwind.svc/"
ODATA_SAMPLE_READWRITE="http://services.odata.org/(S(readwrite))/OData/OData.svc/"



class ODataTests(unittest.TestCase):
	def testCaseConstants(self):
		# self.assertTrue(IMSCP_NAMESPACE=="http://www.imsglobal.org/xsd/imscp_v1p1","Wrong CP namespace: %s"%IMSCP_NAMESPACE)
		# self.assertTrue(IMSCPX_NAMESPACE=="http://www.imsglobal.org/xsd/imscp_extensionv1p2","Wrong extension namespace: %s"%IMSCPX_NAMESPACE)
		pass


class ClientTests(unittest.TestCase):
	def tesxCaseConstructor(self):
		c=Client(ODATA_SAMPLE_SERVICEROOT)
		if VERBOSE:
			c.SetLog(http.HTTP_LOG_INFO,sys.stdout,256)
		self.assertTrue(isinstance(c,app.Client),"OData client not an APP client")
		self.assertTrue(isinstance(c.service,app.Service),"Service document is present")
		self.assertTrue(len(c.service.Workspace)==1,"Service not returning a single Workspace child")
		self.assertTrue(len(c.service.Workspace[0].Collection)>0,"Workspace empty")
		self.assertTrue(isinstance(c.serviceRoot,uri.URI),"Service root should be a URI instance")
		self.assertTrue(len(c.feeds)>0,"At least one feed loaded from service")
		self.assertTrue("Products" in c.feeds,"One feed called Products required")
		self.assertTrue(isinstance(c.feeds["Products"],edm.EntitySet),"Feeds map to entity sets")
		self.assertTrue(c.pageSize is None,"Default constructor page size")
		
	def tesxCaseFeedEntries(self):
		c=Client(ODATA_SAMPLE_SERVICEROOT)
		if VERBOSE:
			c.SetLog(http.HTTP_LOG_INFO,sys.stdout,256)
		# now open a collection and iterate through it
		names=set()
		with c.feeds['Products'].OpenCollection() as collection:
			n=len(collection)
			self.assertTrue(n>10,"Sample has more than 10 products (found %i)"%n)
			for product in collection.itervalues():
				names.add(product['ProductName'].pyValue)	
			self.assertTrue(n==len(names))
			scottishLongBreads=collection[68]
			self.assertTrue(isinstance(scottishLongBreads['ProductID'],edm.Int32Value))
			self.assertTrue(scottishLongBreads['ProductID'].pyValue==68)
			self.assertTrue(isinstance(scottishLongBreads['ProductName'],edm.StringValue))
			self.assertTrue(scottishLongBreads['ProductName'].pyValue==u"Scottish Longbreads")
			self.assertTrue(isinstance(scottishLongBreads['SupplierID'],edm.Int32Value))
			self.assertTrue(scottishLongBreads['SupplierID'].pyValue==8)
			self.assertTrue(isinstance(scottishLongBreads['CategoryID'],edm.Int32Value))
			self.assertTrue(scottishLongBreads['CategoryID'].pyValue==3)
			self.assertTrue(isinstance(scottishLongBreads['QuantityPerUnit'],edm.StringValue))
			self.assertTrue(scottishLongBreads['QuantityPerUnit'].pyValue==u"10 boxes x 8 pieces")
			self.assertTrue(isinstance(scottishLongBreads['UnitPrice'],edm.DecimalValue))
			self.assertTrue(scottishLongBreads['UnitPrice'].pyValue.as_tuple()==decimal.Decimal("12.5000").as_tuple())
			self.assertTrue(isinstance(scottishLongBreads['UnitsInStock'],edm.Int16Value))
			self.assertTrue(scottishLongBreads['UnitsInStock'].pyValue==6)
			self.assertTrue(isinstance(scottishLongBreads['UnitsOnOrder'],edm.Int16Value))
			self.assertTrue(scottishLongBreads['UnitsOnOrder'].pyValue==10)
			self.assertTrue(isinstance(scottishLongBreads['ReorderLevel'],edm.Int16Value))
			self.assertTrue(scottishLongBreads['ReorderLevel'].pyValue==15)
			self.assertTrue(isinstance(scottishLongBreads['Discontinued'],edm.BooleanValue))
			self.assertTrue(scottishLongBreads['Discontinued'].pyValue==False)
			
		
	def tesxCaseOrderBy(self):
		c=Client(ODATA_SAMPLE_SERVICEROOT)
		if VERBOSE:
			c.SetLog(http.HTTP_LOG_INFO,sys.stdout,256)
		names=set()
		with c.feeds['Products'].OpenCollection() as collection:
			collection.OrderBy(core.CommonExpression.OrderByFromString("ProductName asc"))
			firstValue=None
			lastValue=None
			for product in collection.itervalues():
				lastValue=product['ProductName'].pyValue
				if firstValue is None:
					firstValue=lastValue
		self.assertTrue(firstValue=="Alice Mutton","Bad first value: %s"%firstValue)
		self.assertTrue(lastValue=="Zaanse koeken","Bad last value: %s"%lastValue)
	
	def tesxCaseFilter(self):
		c=Client(ODATA_SAMPLE_SERVICEROOT)
		if VERBOSE:
			c.SetLog(http.HTTP_LOG_INFO,sys.stdout,256)
		names=set()		
		with c.feeds['Products'].OpenCollection() as collection:
			collection.Filter(core.CommonExpression.FromString("substringof('bread',ProductName)"))
			self.assertTrue(len(collection)==1)
			product=collection.values()[0]
			self.assertTrue(product['ProductName']=="Scottish Longbreads")
			scottishLongBreads=collection[68]
			self.assertTrue(scottishLongBreads['ProductID'].pyValue==68)
			try:
				aliceMutton=collection[17]
				self.fail("Alice Mutton wasn't filtered")
			except KeyError:
				pass
	
	def tesxCaseNavigation(self):
		c=Client(ODATA_SAMPLE_SERVICEROOT)
		if VERBOSE:
			c.SetLog(http.HTTP_LOG_INFO,sys.stdout,256)
		with c.feeds['Customers'].OpenCollection() as collection:
			customer=collection['ALFKI']
			self.assertFalse(customer['Orders'].isExpanded)
			with customer['Orders'].OpenCollection() as orders:
				self.assertTrue(len(orders)==6,"Number of orders")
				self.assertFalse(isinstance(orders,edm.ExpandedEntityCollection))
			# now test expansion
			collection.Expand({"Orders":None})
			customer=collection['ALFKI']
			self.assertTrue(customer['Orders'].isExpanded)
			with customer['Orders'].OpenCollection() as orders:
				self.assertTrue(len(orders)==6,"Number of orders")
				self.assertTrue(isinstance(orders,core.ExpandedEntityCollection))
									
				
# 	def tesxCaseProperties(self):
# 		c=Client(ODATA_SAMPLE_SERVICEROOT)
# 		c.pageSize=1
# 		fURL=c.feedTitles['Products']
# 		entries=c.RetrieveEntries(fURL)
# 		e=entries.next()
# 		self.assertTrue(isinstance(e,Entry),"OData entry type override")
# 		self.assertTrue(e['Rating']==4,"Rating property")
# 		self.assertTrue(e['Price']==2.5,"Price property")
# 		self.assertTrue(isinstance(e['ReleaseDate'],iso.TimePoint),"ReleaseDate type")
# 		self.assertTrue(e['ReleaseDate'].date.century==19 and e['ReleaseDate'].date.year==92,"ReleaseDate year")		
# 		self.assertTrue(e['DiscontinuedDate'] is None,"DiscontinuedDate NULL test")		
# 		for link in e.Link:
# 			if link.title=="Category":
# 				eCat=c.RetrieveEntry(link.ResolveURI(link.href))
# 				
# 	def tesxCaseReadWrite(self):
# 		c=Client(ODATA_SAMPLE_READWRITE)
# 		fURL=c.feedTitles['Categories']
# 		entries=c.RetrieveEntries(fURL)
# 		catID=None
# 		for e in entries:
# 			if e.Title.GetValue()=='Electronics':
# 				catID=e.AtomId.GetValue()		
# 		fURL=c.feedTitles['Products']
# 		e=Entry(None)
# 		now=iso.TimePoint()
# 		now.NowUTC()
# 		e.Title.SetValue("Pyslet Python Package")
# 		e.ChildElement(atom.Summary).SetValue("Python package for Standards in Learning, Education and Training")
# 		e['ID']=100
# 		e['ReleaseDate']=now.GetCalendarString()
# 		e['Rating']=5
# 		e['Price']=0.0
# 		if catID is not None:
# 			# Link this to Electronics
# 			e.AddLink('Category',catID)
# 		eResult=c.AddEntry(fURL,e)
# 		self.assertTrue(isinstance(eResult,Entry),"OData entry type POST result")
# 		self.assertTrue(eResult['Rating']==5,"Rating property on POST")
# 		self.assertTrue(eResult['Price']==0.0,"Price property on POST")
# 		self.assertTrue(isinstance(eResult['ReleaseDate'],iso.TimePoint),"ReleaseDate type on POST: %s"%repr(eResult['ReleaseDate']))
# 		self.assertTrue(eResult['ReleaseDate']==now,"ReleaseDate match on POST")		
# 		self.assertTrue(eResult['DiscontinuedDate'] is None,"DiscontinuedDate NULL test on POST")
# 		for link in eResult.Link:
# 			if link.title=="Category":
# 				eCat=c.RetrieveEntry(link.ResolveURI(link.href))
# 				self.assertTrue(eCat['Name']=='Electronics')
# 
# 	def tesxCaseMetadata(self):
# 		c=Client()
# 		if VERBOSE:
# 			c.SetLog(http.HTTP_LOG_INFO,sys.stdout,80)
# 		c.SetService(ODATA_SAMPLE_SERVICEROOT)
# 		# By default this should load the metadata document, if present
# 		self.assertTrue(isinstance(c.schemas['ODataDemo'],edm.Schema),"Failed to load metadata document")
# 		fURL=c.feedTitles['Products']
# 		f=c.RetrieveFeed(fURL)
# 		for e in f.Entry:
# 			self.assertTrue(e.entityType is c.schemas['ODataDemo']['Product'],"Entry not associated with EntityType")
# 		e=c.Entry('ODataDemo.Product')
# 		self.assertTrue(isinstance(e,Entry),"Entry creation from client")
# 		self.assertTrue(e.entityType is c.schemas['ODataDemo']['Product'],"New entry not associated with EntityType")

if __name__ == "__main__":
	VERBOSE=True
	unittest.main()
