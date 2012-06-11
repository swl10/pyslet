#! /usr/bin/env python

import unittest

def suite():
	loader=unittest.TestLoader()
	loader.testMethodPrefix='test'
	return unittest.TestSuite((
		loader.loadTestsFromTestCase(CSDLTests)
		))

def load_tests(loader, tests, pattern):
	return suite()


from pyslet.mc_csdl import *
import pyslet.xml20081126.structures as xml

class CSDLTests(unittest.TestCase):
	def testCaseConstants(self):
		self.failUnless(EDM_NAMESPACE=="http://schemas.microsoft.com/ado/2009/11/edm","Wrong CSDL namespace: %s"%EDM_NAMESPACE)

	def testCaseSchema(self):
		s=Schema(None)
		self.failUnless(isinstance(s,xml.Element),"Schema not an XML element")
		self.failUnless(s.ns==EDM_NAMESPACE,"CSDL namespace")
		self.failUnless(s.namespace=='Default','Namespace default')
		self.failUnless(s.alias==None,'Alias default')
		self.failUnless(len(s.Using)==0,"No Using elements allowed on construction")
		self.failUnless(len(s.Assocation)==0,"No Association elements allowed on construction")
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
		et.SetAttribute((None,'Name'),"NewName")
		self.failUnless(et.name=="NewName","Name attribute setter")
		self.failUnless(et.baseType is None,"Default baseType")
		et.SetAttribute((None,'BaseType'),"ParentClass")
		self.failUnless(et.baseType=="ParentClass","BaseType attribute setter")
		self.failUnless(et.abstract is False,"Default abstract")
		et.SetAttribute((None,'Abstract'),"true")
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
		p.SetAttribute((None,'Name'),"NewName")
		self.failUnless(p.name=="NewName","Name attribute setter")
		self.failUnless(p.type=="Edm.String","Default type")
		p.SetAttribute((None,'Type'),"Edm.Int")
		self.failUnless(p.type=="Edm.Int","Type attribute setter")
		self.failUnless(p.TypeRef is None,"No TypeRef child on construction")
		self.failUnless(p.nullable==True,"Default nullable value")
		p.SetAttribute((None,'Nullable'),"false")
		self.failUnless(p.nullable is False,"Nullable attribute setter")
		self.failUnless(p.defaultValue is None,"DefaultValue on construction")
		p.SetAttribute((None,'DefaultValue'),"5")
		self.failUnless(p.defaultValue=="5","DefaultValue attribute setter")
		self.failUnless(p.maxLength is None,"MaxLength on construction")
		p.SetAttribute((None,'MaxLength'),"5")
		self.failUnless(p.maxLength==5,"MaxLength attribute setter")
		self.failUnless(p.fixedLength is None,"FixedLength on construction")
		p.SetAttribute((None,'FixedLength'),"5")
		self.failUnless(p.fixedLength==5,"FixedLength attribute setter")
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
	
	def testCaseEntityKey(self):
		k=EntityKey(None)
		self.failUnless(isinstance(k,CSDLElement),"EntityKey not a CSDLElement")
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
		ct.SetAttribute((None,'BaseType'),"ParentClass")
		self.failUnless(ct.baseType=="ParentClass","BaseType attribute setter")
		self.failUnless(ct.abstract is False,"Default abstract")
		ct.SetAttribute((None,'Abstract'),"true")
		self.failUnless(ct.abstract is True,"Abstract attribute setter")
		self.failUnless(ct.Documentation is None,"No Documentation elements allowed on construction")
		self.failUnless(len(ct.Property)==0,"No Property elements allowed on construction")
		self.failUnless(len(ct.TypeAnnotation)==0,"No TypeAnnotation elements allowed on construction")
		self.failUnless(len(ct.ValueAnnotation)==0,"No ValueAnnotation elements allowed on construction")

	def testCaseAssociation(self):
		a=Association(None)
		self.failUnless(isinstance(a,CSDLElement),"Association not a CSDLElement")
		self.failUnless(a.name=="Default","Default name")
		a.SetAttribute((None,'Name'),"NewName")
		self.failUnless(a.name=="NewName","Name attribute setter")
		self.failUnless(a.Documentation is None,"No Documentation elements allowed on construction")
		self.failUnless(len(a.End)==0,"No Ends allowed on construction")
		self.failUnless(a.ReferentialConstraint is None,"No ReferentialConstraint elements allowed on construction")
		self.failUnless(len(a.TypeAnnotation)==0,"No TypeAnnotation elements allowed on construction")
		self.failUnless(len(a.ValueAnnotation)==0,"No ValueAnnotation elements allowed on construction")

	def testCaseEnd(self):
		e=End(None)
		self.failUnless(isinstance(e,CSDLElement),"End not a CSDLElement")
		self.failUnless(e.type is None,"Default type")
		e.SetAttribute((None,'Type'),"MySchema.Person")
		self.failUnless(e.type=="MySchema.Person","Type attribute setter")
		self.failUnless(e.role is None,"Default role")
		e.SetAttribute((None,'Role'),"Source")
		self.failUnless(e.role=="Source","Role attribute setter")
		self.failUnless(e.multiplicity==Multiplicity.One,"Default Multiplicity")
		e.SetAttribute((None,'Multiplicity'),"0..1")
		self.failUnless(e.multiplicity==Multiplicity.ZeroToOne,"Multiplicity attribute setter")
		e.SetAttribute((None,'Multiplicity'),"*")
		self.failUnless(e.multiplicity==Multiplicity.Many,"Multiplicity attribute setter")
		self.failUnless(e.Documentation is None,"No Documentation elements allowed on construction")
		self.failUnless(e.OnDelete is None,"No OnDelete elements allowed on construction")
		
				
if __name__ == "__main__":
	unittest.main()
