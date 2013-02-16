#! /usr/bin/env python

import unittest

def suite():
	loader=unittest.TestLoader()
	loader.testMethodPrefix='test'
	return unittest.TestSuite((
		loader.loadTestsFromTestCase(CSDLTests),
		loader.loadTestsFromTestCase(ERStoreTests)
		))

def load_tests(loader, tests, pattern):
	return suite()

from pyslet.mc_csdl import *

import pyslet.xml20081126.structures as xml
import pyslet.mc_edmx as edmx
from pyslet.vfs import OSFilePath as FilePath

TEST_DATA_DIR=FilePath(FilePath(__file__).abspath().split()[0],'data_mc_csdl')


class CSDLTests(unittest.TestCase):
	def testCaseConstants(self):
		self.failUnless(EDM_NAMESPACE=="http://schemas.microsoft.com/ado/2009/11/edm","Wrong CSDL namespace: %s"%EDM_NAMESPACE)

	def testCaseSimpleIdentifier(self):
		# basic tests here:
		for iTest in ("45",
			"M'",
			"M;",
			"M=",
			"M\\",
			"M.N",
			"M+","M-","M*","M/","M<","M>","M=","M~","M!","M@","M#","M%","M^","M&","M|","M`","M?",
			"M(","M)","M[","M]","M,","M;","M*","M."
			):
			try:
				self.failIf(ValidateSimpleIdentifier(iTest),"%s: Fail"%repr(iTest))
			except ValueError,e:
				pass
		
	def testCaseSchema(self):
		s=Schema(None)
		self.failUnless(isinstance(s,xml.Element),"Schema not an XML element")
		self.failUnless(s.ns==EDM_NAMESPACE,"CSDL namespace")
		self.failUnless(s.name=='Default','Namespace default')
		self.failUnless(s.alias==None,'Alias default')
		self.failUnless(len(s.Using)==0,"No Using elements allowed on construction")
		self.failUnless(len(s.Association)==0,"No Association elements allowed on construction")
		self.failUnless(len(s.ComplexType)==0,"No ComplexType elements allowed on construction")
		self.failUnless(len(s.EntityType)==0,"No EntityType elements allowed on construction")
		self.failUnless(len(s.EntityContainer)==0,"No EntityContainer elements allowed on construction")
		self.failUnless(len(s.Function)==0,"No Function elements allowed on construction")
		self.failUnless(len(s.Annotations)==0,"No Annotations elements allowed on construction")
		self.failUnless(len(s.ValueTerm)==0,"No ValueTerm elements allowed on construction")
		e=s.ChildElement(EntityType)
		e.name="TestType"
		s.ContentChanged()
		self.failUnless(s['TestType'] is e,"Schema subscripting, EntityType declared")
		
	def testCaseEntityType(self):
		et=EntityType(None)
		self.failUnless(isinstance(et,CSDLElement),"EntityType not a CSDLelement")
		self.failUnless(et.name=="Default","Default name")
		et.SetAttribute('Name',"NewName")
		self.failUnless(et.name=="NewName","Name attribute setter")
		self.failUnless(et.baseType is None,"Default baseType")
		et.SetAttribute('BaseType',"ParentClass")
		self.failUnless(et.baseType=="ParentClass","BaseType attribute setter")
		self.failUnless(et.abstract is False,"Default abstract")
		et.SetAttribute('Abstract',"true")
		self.failUnless(et.abstract is True,"Abstract attribute setter")
		self.failUnless(et.Documentation is None,"No Documentation elements allowed on construction")
		self.failUnless(et.Key is None,"No Key elements allowed on construction")
		self.failUnless(len(et.Property)==0,"No Property elements allowed on construction")
		self.failUnless(len(et.NavigationProperty)==0,"No Property elements allowed on construction")
		self.failUnless(len(et.TypeAnnotation)==0,"No TypeAnnotation elements allowed on construction")
		self.failUnless(len(et.ValueAnnotation)==0,"No ValueAnnotation elements allowed on construction")

	def testCaseProperty(self):
		p=Property(None)
		self.failUnless(isinstance(p,CSDLElement),"Property not a CSDLelement")
		self.failUnless(p.name=="Default","Default name")
		p.SetAttribute('Name',"NewName")
		self.failUnless(p.name=="NewName","Name attribute setter")
		self.failUnless(p.type=="Edm.String","Default type")
		p.SetAttribute('Type',"Edm.Int")
		self.failUnless(p.type=="Edm.Int","Type attribute setter")
		self.failUnless(p.TypeRef is None,"No TypeRef child on construction")
		self.failUnless(p.nullable==True,"Default nullable value")
		p.SetAttribute('Nullable',"false")
		self.failUnless(p.nullable is False,"Nullable attribute setter")
		self.failUnless(p.defaultValue is None,"DefaultValue on construction")
		p.SetAttribute('DefaultValue',"5")
		self.failUnless(p.defaultValue=="5","DefaultValue attribute setter")
		self.failUnless(p.maxLength is None,"MaxLength on construction")
		p.SetAttribute('MaxLength',"5")
		self.failUnless(p.maxLength==5,"MaxLength attribute setter")
		self.failUnless(p.fixedLength is None,"FixedLength on construction")
		p.SetAttribute('FixedLength',"false")
		self.failUnless(p.fixedLength is False,"FixedLength attribute setter")
		self.failUnless(p.precision is None,"Precision on construction")
		self.failUnless(p.scale is None,"Scale on construction")
		self.failUnless(p.unicode is None,"Unicode on construction")
		self.failUnless(p.collation is None,"Collation on construction")
		self.failUnless(p.SRID is None,"SRID on construction")
		self.failUnless(p.collectionKind is None,"CollectionKind on construction")
		self.failUnless(p.concurrencyMode is None,"ConcurrencyMode on construction")
		self.failUnless(p.Documentation is None,"No Documentation elements allowed on construction")
		self.failUnless(len(p.TypeAnnotation)==0,"No TypeAnnotation elements allowed on construction")
		self.failUnless(len(p.ValueAnnotation)==0,"No ValueAnnotation elements allowed on construction")

	def testCaseNavigationProperty(self):
		np=NavigationProperty(None)
		self.failUnless(isinstance(np,CSDLElement),"NavigationProperty not a CSDLElement")
		self.failUnless(np.name=="Default","Default name")
		self.failUnless(np.relationship is None,"Default relationship")
		self.failUnless(np.toRole is None,"Default ToRole")
		self.failUnless(np.fromRole is None,"Default FromRole")
		self.failUnless(np.Documentation is None,"No Documentation elements allowed on construction")
		self.failUnless(len(np.TypeAnnotation)==0,"No TypeAnnotation elements allowed on construction")
		self.failUnless(len(np.ValueAnnotation)==0,"No ValueAnnotation elements allowed on construction")
	
	def testCaseKey(self):
		k=Key(None)
		self.failUnless(isinstance(k,CSDLElement),"Key not a CSDLElement")
		self.failUnless(len(k.PropertyRef)==0,"No PropertyRef elements allowed on construction")
	
	def testCasePropertyRef(self):
		pr=PropertyRef(None)
		self.failUnless(isinstance(pr,CSDLElement),"PropertyRef not a CSDLElement")
		self.failUnless(pr.name=="Default","Default name")

	def testCaseComplexType(self):
		ct=ComplexType(None)
		self.failUnless(isinstance(ct,CSDLElement),"ComplexType not a CSDLElement")
		self.failUnless(ct.name=="Default","Default name")
		self.failUnless(ct.baseType is None,"Default baseType")
		ct.SetAttribute('BaseType',"ParentClass")
		self.failUnless(ct.baseType=="ParentClass","BaseType attribute setter")
		self.failUnless(ct.abstract is False,"Default abstract")
		ct.SetAttribute('Abstract',"true")
		self.failUnless(ct.abstract is True,"Abstract attribute setter")
		self.failUnless(ct.Documentation is None,"No Documentation elements allowed on construction")
		self.failUnless(len(ct.Property)==0,"No Property elements allowed on construction")
		self.failUnless(len(ct.TypeAnnotation)==0,"No TypeAnnotation elements allowed on construction")
		self.failUnless(len(ct.ValueAnnotation)==0,"No ValueAnnotation elements allowed on construction")

	def testCaseAssociation(self):
		a=Association(None)
		self.failUnless(isinstance(a,CSDLElement),"Association not a CSDLElement")
		self.failUnless(a.name=="Default","Default name")
		a.SetAttribute('Name',"NewName")
		self.failUnless(a.name=="NewName","Name attribute setter: %s"%repr(a.name))
		self.failUnless(a.Documentation is None,"No Documentation elements allowed on construction")
		self.failUnless(len(a.AssociationEnd)==0,"No AssociationEnds allowed on construction")
		self.failUnless(a.ReferentialConstraint is None,"No ReferentialConstraint elements allowed on construction")
		self.failUnless(len(a.TypeAnnotation)==0,"No TypeAnnotation elements allowed on construction")
		self.failUnless(len(a.ValueAnnotation)==0,"No ValueAnnotation elements allowed on construction")

	def testCaseEnd(self):
		e=AssociationEnd(None)
		self.failUnless(isinstance(e,CSDLElement),"AssociationEnd not a CSDLElement")
		self.failUnless(e.type is None,"Default type")
		e.SetAttribute('Type',"MySchema.Person")
		self.failUnless(e.type=="MySchema.Person","Type attribute setter")
		self.failUnless(e.name is None,"Default role")
		e.SetAttribute('Role',"Source")
		self.failUnless(e.name=="Source","Role attribute setter")
		self.failUnless(e.multiplicity==Multiplicity.One,"Default Multiplicity")
		e.SetAttribute('Multiplicity',"0..1")
		self.failUnless(e.multiplicity==Multiplicity.ZeroToOne,"Multiplicity attribute setter")
		e.SetAttribute('Multiplicity',"*")
		self.failUnless(e.multiplicity==Multiplicity.Many,"Multiplicity attribute setter")
		self.failUnless(e.Documentation is None,"No Documentation elements allowed on construction")
		self.failUnless(e.OnDelete is None,"No OnDelete elements allowed on construction")

	def testCaseEntity(self):
		es=EntitySet(None)
		es.entityType=EntityType(None)
		e=Entity(es)
		

class ERStoreTests(unittest.TestCase):
	def setUp(self):
		self.cwd=FilePath.getcwd()
		TEST_DATA_DIR.chdir()
		# load the base schema document
		self.doc=edmx.Document(baseURI="Schema-01.xml")
		self.doc.Read()
		# now create a temporary file ready for SQL database
		self.d=FilePath.mkdtemp('.d','pyslet-test_mc_csdl-')
		self.store=SQLiteDB(self.d.join('test.db'))
		
	def tearDown(self):
		self.store.close()
		self.cwd.chdir()
		self.d.rmtree(True)
		
	def testCaseConstruction(self):
		self.failUnless(isinstance(self.store,ERStore),"DB is a basic implementation of ERStore")
		# This creates an empty datastore which behaves like a dictionary
		self.failUnless(len(self.store)==0,"Initially empty")
		
	def testCaseAddSchema(self):
		saveFingerprint=self.store.fingerprint
		self.store.AddSchema(self.doc.root)
		self.failUnless(self.store.fingerprint!=saveFingerprint,"Fingerprint unchanged")
		sc=self.store["SchemaA"]
		self.failUnless(isinstance(sc,Schema),"Schema")
		self.failUnless(sc.name=="SchemaA","SchemaA name")
		self.failUnless(isinstance(self.store["SchemaA.Database"],EntityContainer),"Database")
		t1=self.store["SchemaA.Database.Table01"]
		self.failUnless(isinstance(t1,EntitySet),"Table")
		self.failUnless(t1.name=="Table01","Table")
		self.failUnless(t1.entityTypeName=="SchemaA.Type01","Table entity mapping")
		self.failUnless(len(self.store)==6,"Expected 6 names: %s"%repr(self.store.keys()))
		try:
			self.store.AddSchema(self.doc.root)
			self.fail("Attempt to add an existing schema")
		except DuplicateName:
			pass
		doc=edmx.Document(baseURI="SchemaB.xml")
		doc.Read()
		saveFingerprint=self.store.fingerprint
		self.store.AddSchema(doc.root)
		self.failUnless(self.store.fingerprint!=saveFingerprint,"Fingerprint unchanged")
		self.failUnless(len(self.store)==12,"SchemaB declared")
		# open a second view on this database
		saveFingerprint=self.store.fingerprint
		self.store.close()
		self.store=SQLiteDB(self.d.join('test.db'))
		self.failUnless(self.store.fingerprint==saveFingerprint,"Fingerprint preserved after reload")
		self.failUnless(len(self.store)==12,"SchemaA and SchemaB declared")
		
		
	def testCaseCreateContainer(self):
		self.store.AddSchema(self.doc.root)
		try:
			self.store.CreateContainer("SchemaA")
			self.fail("CreateContainer: requires an entity container")
		except ValueError:
			pass
		try:
			for row in self.store.EntityReader("SchemaA.Database.Table01"):
				self.fail("Table01 exists and is not empty!")
		except KeyError:
			pass
		self.store.CreateContainer("SchemaA.Database")
		try:
			self.store.CreateContainer("SchemaA.Database")
			self.fail("CreateContainer: container already exists")
		except ContainerExists:
			pass
		try:
			for row in self.store.EntityReader("SchemaA.Database.Table01"):
				self.fail("Table01 is not empty!")
		except KeyError:
			self.fail("Table01 should now exist!")
		saveFingerprint=self.store.fingerprint
		self.store.close()
		self.store=SQLiteDB(self.d.join('test.db'))
		self.failUnless(self.store.fingerprint==saveFingerprint,"Fingerprint preserved after reload")
	
	def testCaseSelectUpdate(self):	
		self.store.AddSchema(self.doc.root)
		self.store.CreateContainer("SchemaA.Database")
		newEntry={"ID":"A","Name":"Alfred"}
		self.store.InsertEntity("SchemaA.Database.Table01",newEntry)
		count=0
		for row in self.store.EntityReader("SchemaA.Database.Table01"):
			self.failIf(count>0,"Too many results")
			self.failUnless(row["ID"]=="A","Inserted item ID")
			self.failUnless(row["Name"]=="Alfred","Inserted item Name")
			count+=1
		newEntry={"Name":"Borace"}
		try:
			self.store.InsertEntity("SchemaA.Database.Table01",newEntry)
			self.fail("ID not Nullable")
		except StorageError:
			pass
		newEntry["ID"]="B"
		self.store.InsertEntity("SchemaA.Database.Table01",newEntry)
	
	def noTestCaseUpgradeSchema(self):
		self.store.AddSchema(self.doc.root)
		self.store.CreateContainer("SchemaA.Database")
		newEntry={"ID":"A","Name":"Alfred"}
		self.store.InsertEntity("SchemaA.Database.Table01",newEntry)
		doc=edmx.Document(baseURI="Schema-02.xml")
		doc.Read()
		self.store.UpgradeSchema(doc.root)
		for row in self.store.EntityReader("SchemaA.Database.Table01"):
			self.failUnless(row["Email"] is None,"Created column no default")
			self.failUnless(row["Inactive"] is True,"Created column with default %s"%repr(row["Inactive"]))
		newEntry={"ID":"B","Name":"Borace","Inactive":"false"}
		self.store.InsertEntity("SchemaA.Database.Table01",newEntry)
		foundB=False
		for row in self.store.EntityReader("SchemaA.Database.Table01"):
			if row["ID"]=="B":
				foundB=True
				self.failUnless(row["Email"] is None,"Created column no default")
				self.failUnless(row["Inactive"] is False,"Created column with default %s"%repr(row["Inactive"]))		
		self.failUnless(foundB,"Failed to find ID='B'")				
				
if __name__ == "__main__":
	unittest.main()
