#! /usr/bin/env python

import datetime
import decimal
import unittest


from pyslet import iso8601 as iso
from pyslet.py2 import (
    long2,
    uempty)
from pyslet.odata2 import csdl as edm
from pyslet.xml import structures as xml


def suite():
    loader = unittest.TestLoader()
    loader.testMethodPrefix = 'test'
    return unittest.TestSuite((
        loader.loadTestsFromTestCase(CSDLTests),
        loader.loadTestsFromTestCase(EntityTests),
        loader.loadTestsFromTestCase(ValueTests)
    ))


def load_tests(loader, tests, pattern):
    return suite()


class CSDLTests(unittest.TestCase):

    def test_constants(self):
        self.assertTrue(edm.EDM_NAMESPACE ==
                        "http://schemas.microsoft.com/ado/2009/11/edm",
                        "Wrong CSDL namespace: %s" % edm.EDM_NAMESPACE)

    def test_simple_identifier(self):
        # basic tests here:
        for iTest in ("45", "M'", "M;", "M=", "M\\", "M.N",
                      "M+", "M-", "M*", "M/", "M<", "M>", "M=", "M~", "M!",
                      "M@", "M#", "M%", "M^", "M&", "M|", "M`", "M?",
                      "M(", "M)", "M[", "M]", "M,", "M;", "M*", "M."
                      ):
            try:
                self.assertFalse(edm.validate_simple_identifier(iTest),
                                 "%s: Fail" % repr(iTest))
            except ValueError:
                pass
        save_pattern = edm.set_simple_identifier_re(
            edm.SIMPLE_IDENTIFIER_COMPATIBILITY_RE)
        self.assertTrue(edm.validate_simple_identifier("M-"), "hyphen allowed")
        edm.set_simple_identifier_re(save_pattern)

    def test_simple_type(self):
        """Test the SimpleType enumeration."""
        self.assertTrue(edm.SimpleType.Binary == getattr(
            edm.SimpleType, 'Edm.Binary'), "Dual declaration form.")
        # Given a python type value (as returned by the type() function) we
        # find the SimpleType
        self.assertTrue(
            edm.SimpleType.PythonType[type(3.14)] == edm.SimpleType.Double,
            "Bad float type")
        self.assertTrue(
            edm.SimpleType.PythonType[type(3)] == edm.SimpleType.Int64,
            "Bad int type")
        self.assertTrue(
            edm.SimpleType.PythonType[type("Hello")] == edm.SimpleType.String,
            "Bad string type")
        self.assertTrue(
            edm.SimpleType.PythonType[type(uempty)] == edm.SimpleType.String,
            "Bad unicode type")

    def test_schema(self):
        s = edm.Schema(None)
        self.assertTrue(
            isinstance(s, xml.Element), "Schema not an XML element")
        self.assertTrue(s.ns == edm.EDM_NAMESPACE, "CSDL namespace")
        self.assertTrue(s.name == 'Default', 'Namespace default')
        self.assertTrue(s.alias is None, 'Alias default')
        self.assertTrue(
            len(s.Using) == 0, "No Using elements allowed on construction")
        self.assertTrue(len(s.Association) == 0,
                        "No Association elements allowed on construction")
        self.assertTrue(len(s.ComplexType) == 0,
                        "No ComplexType elements allowed on construction")
        self.assertTrue(len(s.EntityType) == 0,
                        "No EntityType elements allowed on construction")
        self.assertTrue(len(s.EntityContainer) == 0,
                        "No EntityContainer elements allowed on construction")
        self.assertTrue(len(s.Function) == 0,
                        "No Function elements allowed on construction")
        self.assertTrue(len(s.Annotations) == 0,
                        "No Annotations elements allowed on construction")
        self.assertTrue(len(s.ValueTerm) == 0,
                        "No ValueTerm elements allowed on construction")
        e = s.add_child(edm.EntityType)
        e.name = "TestType"
        s.content_changed()
        self.assertTrue(
            s['TestType'] is e, "Schema subscripting, EntityType declared")

    def test_entity_type(self):
        et = edm.EntityType(None)
        self.assertTrue(
            isinstance(et, edm.CSDLElement), "EntityType not a CSDLelement")
        self.assertTrue(et.name == "Default", "Default name")
        et.set_attribute('Name', "NewName")
        self.assertTrue(et.name == "NewName", "Name attribute setter")
        self.assertTrue(et.baseType is None, "Default baseType")
        et.set_attribute('BaseType', "ParentClass")
        self.assertTrue(
            et.baseType == "ParentClass", "BaseType attribute setter")
        self.assertTrue(et.abstract is False, "Default abstract")
        et.set_attribute('Abstract', "true")
        self.assertTrue(et.abstract is True, "Abstract attribute setter")
        self.assertTrue(et.Documentation is None,
                        "No Documentation elements allowed on construction")
        self.assertTrue(
            et.Key is None, "No Key elements allowed on construction")
        self.assertTrue(len(et.Property) == 0,
                        "No Property elements allowed on construction")
        self.assertTrue(len(et.NavigationProperty) == 0,
                        "No Property elements allowed on construction")
        self.assertTrue(len(et.TypeAnnotation) == 0,
                        "No TypeAnnotation elements allowed on construction")
        self.assertTrue(len(et.ValueAnnotation) == 0,
                        "No ValueAnnotation elements allowed on construction")

    def test_property(self):
        p = edm.Property(None)
        self.assertTrue(
            isinstance(p, edm.CSDLElement), "Property not a CSDLelement")
        self.assertTrue(p.name == "Default", "Default name")
        p.set_attribute('Name', "NewName")
        self.assertTrue(p.name == "NewName", "Name attribute setter")
        self.assertTrue(p.type == "Edm.String", "Default type")
        p.set_attribute('Type', "Edm.Int32")
        self.assertTrue(p.type == "Edm.Int32", "Type attribute setter")
        self.assertTrue(p.TypeRef is None, "No TypeRef child on construction")
        self.assertTrue(p.nullable is True, "Default nullable value")
        p.set_attribute('Nullable', "false")
        self.assertTrue(p.nullable is False, "Nullable attribute setter")
        self.assertTrue(p.defaultValue is None, "DefaultValue on construction")
        p.set_attribute('DefaultValue', "5")
        self.assertTrue(p.defaultValue == "5", "DefaultValue attribute setter")
        self.assertTrue(p.maxLength is None, "MaxLength on construction")
        p.set_attribute('MaxLength', "5")
        self.assertTrue(p.maxLength == 5, "MaxLength attribute setter")
        self.assertTrue(p.fixedLength is None, "FixedLength on construction")
        p.set_attribute('FixedLength', "false")
        self.assertTrue(p.fixedLength is False, "FixedLength attribute setter")
        self.assertTrue(p.precision is None, "Precision on construction")
        self.assertTrue(p.scale is None, "Scale on construction")
        self.assertTrue(p.unicode is None, "Unicode on construction")
        self.assertTrue(p.collation is None, "Collation on construction")
        self.assertTrue(p.SRID is None, "SRID on construction")
        self.assertTrue(
            p.collectionKind is None, "CollectionKind on construction")
        self.assertTrue(
            p.concurrencyMode is None, "ConcurrencyMode on construction")
        self.assertTrue(p.Documentation is None,
                        "No Documentation elements allowed on construction")
        self.assertTrue(len(p.TypeAnnotation) == 0,
                        "No TypeAnnotation elements allowed on construction")
        self.assertTrue(len(p.ValueAnnotation) == 0,
                        "No ValueAnnotation elements allowed on construction")

    def test_navigation_property(self):
        np = edm.NavigationProperty(None)
        self.assertTrue(isinstance(np, edm.CSDLElement),
                        "NavigationProperty not a CSDLElement")
        self.assertTrue(np.name == "Default", "Default name")
        self.assertTrue(np.relationship is None, "Default relationship")
        self.assertTrue(np.toRole is None, "Default ToRole")
        self.assertTrue(np.fromRole is None, "Default FromRole")
        self.assertTrue(np.Documentation is None,
                        "No Documentation elements allowed on construction")
        self.assertTrue(len(np.TypeAnnotation) == 0,
                        "No TypeAnnotation elements allowed on construction")
        self.assertTrue(len(np.ValueAnnotation) == 0,
                        "No ValueAnnotation elements allowed on construction")

    def test_key(self):
        k = edm.Key(None)
        self.assertTrue(isinstance(k, edm.CSDLElement),
                        "Key not a CSDLElement")
        self.assertTrue(len(k.PropertyRef) == 0,
                        "No PropertyRef elements allowed on construction")

    def test_property_ref(self):
        pr = edm.PropertyRef(None)
        self.assertTrue(
            isinstance(pr, edm.CSDLElement), "PropertyRef not a CSDLElement")
        self.assertTrue(pr.name == "Default", "Default name")

    def test_complex_type(self):
        ct = edm.ComplexType(None)
        self.assertTrue(
            isinstance(ct, edm.CSDLElement), "ComplexType not a CSDLElement")
        self.assertTrue(ct.name == "Default", "Default name")
        self.assertTrue(ct.baseType is None, "Default baseType")
        ct.set_attribute('BaseType', "ParentClass")
        self.assertTrue(
            ct.baseType == "ParentClass", "BaseType attribute setter")
        self.assertTrue(ct.abstract is False, "Default abstract")
        ct.set_attribute('Abstract', "true")
        self.assertTrue(ct.abstract is True, "Abstract attribute setter")
        self.assertTrue(ct.Documentation is None,
                        "No Documentation elements allowed on construction")
        self.assertTrue(len(ct.Property) == 0,
                        "No Property elements allowed on construction")
        self.assertTrue(len(ct.TypeAnnotation) == 0,
                        "No TypeAnnotation elements allowed on construction")
        self.assertTrue(len(ct.ValueAnnotation) == 0,
                        "No ValueAnnotation elements allowed on construction")

    def test_association(self):
        a = edm.Association(None)
        self.assertTrue(
            isinstance(a, edm.CSDLElement), "Association not a CSDLElement")
        self.assertTrue(a.name == "Default", "Default name")
        a.set_attribute('Name', "NewName")
        self.assertTrue(
            a.name == "NewName", "Name attribute setter: %s" % repr(a.name))
        self.assertTrue(a.Documentation is None,
                        "No Documentation elements allowed on construction")
        self.assertTrue(len(a.AssociationEnd) == 0,
                        "No AssociationEnds allowed on construction")
        self.assertTrue(a.ReferentialConstraint is None,
                        "No ReferentialConstraint elements allowed "
                        "on construction")
        self.assertTrue(len(a.TypeAnnotation) == 0,
                        "No TypeAnnotation elements allowed on construction")
        self.assertTrue(len(a.ValueAnnotation) == 0,
                        "No ValueAnnotation elements allowed on construction")

    def test_end(self):
        e = edm.AssociationEnd(None)
        self.assertTrue(
            isinstance(e, edm.CSDLElement), "AssociationEnd not a CSDLElement")
        self.assertTrue(e.type is None, "Default type")
        e.set_attribute('Type', "MySchema.Person")
        self.assertTrue(e.type == "MySchema.Person", "Type attribute setter")
        self.assertTrue(e.name is None, "Default role")
        e.set_attribute('Role', "Source")
        self.assertTrue(e.name == "Source", "Role attribute setter")
        self.assertTrue(
            e.multiplicity == edm.Multiplicity.One, "Default Multiplicity")
        e.set_attribute('Multiplicity', "0..1")
        self.assertTrue(e.multiplicity == edm.Multiplicity.ZeroToOne,
                        "Multiplicity attribute setter")
        e.set_attribute('Multiplicity', "*")
        self.assertTrue(e.multiplicity == edm.Multiplicity.Many,
                        "Multiplicity attribute setter")
        self.assertTrue(e.Documentation is None,
                        "No Documentation elements allowed on construction")
        self.assertTrue(e.OnDelete is None,
                        "No OnDelete elements allowed on construction")

    def test_entity(self):
        min_nav_schema = \
            """<?xml version="1.0" encoding="utf-8" standalone="yes" ?>
<Schema Namespace="SampleModel"
        xmlns="http://schemas.microsoft.com/ado/2006/04/edm">
    <EntityContainer Name="SampleEntities" m:IsDefaultEntityContainer="true">
        <EntitySet Name="Customers" EntityType="SampleModel.Customer"/>
        <EntitySet Name="Orders" EntityType="SampleModel.Order"/>
        <AssociationSet Name="Orders_Customers"
                Association="SampleModel.Orders_Customers">
            <End Role="Customer" EntitySet="Customers"/>
            <End Role="Order" EntitySet="Orders"/>
        </AssociationSet>
    </EntityContainer>
    <EntityType Name="Order">
        <Key>
            <PropertyRef Name="OrderID"/>
        </Key>
        <Property Name="OrderID" Type="Edm.Int32" Nullable="false"/>
    </EntityType>
    <EntityType Name="Customer">
        <Key>
            <PropertyRef Name="CustomerID"/>
        </Key>
        <Property Name="CustomerID" Type="Edm.String"/>
        <NavigationProperty Name="Orders"
            Relationship="SampleModel.Orders_Customers"
            FromRole="Customer" ToRole="Order"/>
    </EntityType>
    <Association Name="Orders_Customers">
        <End Role="Customer" Type="SampleModel.Customer" Multiplicity="0..1"/>
        <End Role="Order" Type="SampleModel.Order" Multiplicity="*"/>
    </Association>
</Schema>"""
        doc = edm.Document()
        doc.read(src=min_nav_schema)
        scope = edm.NameTableMixin()
        scope.declare(doc.root)
        doc.root.update_type_refs(scope)
        doc.root.update_set_refs(scope)
        es = doc.root["SampleEntities.Customers"]
        e = edm.Entity(es)
        # initially the entity is marked as a new entity
        self.assertFalse(e.exists)
        self.assertTrue(isinstance(e['CustomerID'], edm.StringValue),
                        "Type of simple property")
        self.assertTrue(isinstance(e['Orders'], edm.DeferredValue),
                        "Type of navigation property")

    def test_function(self):
        """Tests the FunctionImport class."""
        f = edm.FunctionImport(None)
        self.assertTrue(
            isinstance(f, edm.CSDLElement), "FunctionImport not a CSDLElement")
        # FunctionImport MUST have a Name attribute defined
        self.assertTrue(f.name == "Default", "Default name")
        f.set_attribute('Name', "annualCustomerSales")
        self.assertTrue(
            f.name == "annualCustomerSales",
            "Name attribute setter: %s" % repr(f.name))
        # Name attribute is of type SimpleIdentifier
        try:
            f.set_attribute('Name', "bad-name")
            self.fail("bad-name accepted")
        except ValueError:
            pass
        min_func_schema = \
            """<?xml version="1.0" encoding="utf-8" standalone="yes" ?>
<Schema Namespace="SampleModel"
        xmlns="http://schemas.microsoft.com/ado/2006/04/edm">
    <EntityContainer Name="SampleEntities" m:IsDefaultEntityContainer="true">
        <FunctionImport Name="activeCustomerCount"
            ReturnType="Edm.Int32">
            <Parameter Name="fiscalyear" Mode="In" Type="String" />
        </FunctionImport>
        <FunctionImport Name="annualCustomerSales"
            EntitySet="result_annualCustomerSalesSet"
            ReturnType="Collection(SampleModel.result_annualCustomerSales)">
            <Parameter Name="fiscalyear" Mode="In" Type="String" />
        </FunctionImport>
        <EntitySet Name="result_annualCustomerSalesSet"
            EntityType="SampleModel.result_annualCustomerSales"/>
    </EntityContainer>
    <EntityType Name="result_annualCustomerSales">
        <Key>
            <PropertyRef Name="ID"/>
        </Key>
        <Property Name="ID" Type="Edm.Int32" Nullable="false"/>
    </EntityType>
</Schema>"""
        doc = edm.Document()
        doc.read(src=min_func_schema)
        scope = edm.NameTableMixin()
        scope.declare(doc.root)
        doc.root.update_type_refs(scope)
        doc.root.update_set_refs(scope)
        # the type of ReturnType MUST be a scalar type, EntityType, or
        # ComplexType that is in scope or a collection of one of these
        # in-scope types
        f = doc.root["SampleEntities.activeCustomerCount"]
        self.assertTrue(isinstance(f.returnTypeRef, edm.TypeRef))
        self.assertFalse(f.is_collection())
        self.assertFalse(f.is_entity_collection())
        self.assertTrue(f.returnTypeRef.simpleTypeCode == edm.SimpleType.Int32)
        f = doc.root["SampleEntities.annualCustomerSales"]
        self.assertTrue(isinstance(f.returnTypeRef, edm.TypeRef))
        self.assertTrue(f.is_collection())
        self.assertTrue(f.is_entity_collection())
        self.assertTrue(f.returnTypeRef.simpleTypeCode is None)


class ValueTests(unittest.TestCase):

    def test_simple_value(self):
        """Test the SimpleValue class."""
        p = edm.Property(None)
        p.simpleTypeCode = edm.SimpleType.Boolean
        v = edm.SimpleValue.from_property(p)
        self.assertTrue(
            isinstance(v, edm.EDMValue), "SimpleValue inherits from EDMValue")
        self.assertTrue(v.value is None, "Null value on construction")
        p.name = "flag"
        v = edm.SimpleValue.from_property(p)
        self.assertTrue(v.p_def.name == "flag",
                        "SimpleValue property definition set on constructor")
        self.assertTrue(v.value is None, "Null value on construction")
        v.set_default_value()
        self.assertTrue(v.value is None, "No default value")
        p.defaultValue = "true"
        v = edm.SimpleValue.from_property(p)
        self.assertTrue(v.value is None, "Null value on construction")
        v.set_default_value()
        self.assertTrue(v.value is True, "explicit default value")

    def test_binary_value(self):
        """Test the BinaryValue class."""
        v = edm.EDMValue.from_type(edm.SimpleType.Binary)
        # check __nonzero__
        self.assertFalse(v)
        # check is_null
        self.assertTrue(v.is_null())
        v.set_from_value(b'1234567890')
        # check __nonzero__
        self.assertTrue(v)
        # check is_null
        self.assertFalse(v.is_null())
        # v2 = edm.EDMValue.from_type(edm.SimpleType.Binary)
        # v2.set_random_value(v)
        # self.assertFalse(v2.value == v.value)

    def test_int32_value(self):
        """Test the Int32Value class."""
        v = edm.EDMValue.from_type(edm.SimpleType.Int32)
        # check __nonzero__
        self.assertFalse(v)
        # check is_null
        self.assertTrue(v.is_null())
        v.set_from_value(123)
        # check __nonzero__
        self.assertTrue(v)
        # check is_null
        self.assertFalse(v.is_null())
        v2 = edm.EDMValue.from_type(edm.SimpleType.Int32)
        v2.set_random_value(v)
        self.assertTrue(v2.value >= 0)
        v.set_from_value(-1)
        v2.set_random_value(v)
        self.assertTrue(v2.value <= 0)

    def test_int64_value(self):
        """Test the Int64Value class."""
        v = edm.EDMValue.from_type(edm.SimpleType.Int64)
        # check __nonzero__
        self.assertFalse(v)
        # check is_null
        self.assertTrue(v.is_null())
        v.set_from_value(123)
        # check __nonzero__
        self.assertTrue(v)
        # check is_null
        self.assertFalse(v.is_null())
        v2 = edm.EDMValue.from_type(edm.SimpleType.Int64)
        v2.set_random_value(v)
        self.assertTrue(v2.value >= 0)
        v.set_from_value(-1)
        v2.set_random_value(v)
        self.assertTrue(v2.value <= 0)

    def test_datetime_value(self):
        """Test the DateTimeValue class."""
        v = edm.EDMValue.from_type(edm.SimpleType.DateTime)
        # check __nonzero__
        self.assertFalse(v)
        # check is_null
        self.assertTrue(v.is_null())
        # set from None
        v.set_from_value(None)
        self.assertFalse(v)
        self.assertTrue(v.is_null())
        # set from timepoint
        d = iso.TimePoint(date=iso.Date(century=19, year=69, month=7, day=20),
                          time=iso.Time(hour=20, minute=17, second=40))
        v.set_from_value(d)
        # check __nonzero__
        self.assertTrue(v)
        # check is_null
        self.assertFalse(v.is_null())
        self.assertTrue(isinstance(v.value, iso.TimePoint))
        self.assertTrue(v.value == d)
        # from a numeric time
        dunix = iso.TimePoint(
            date=iso.Date(century=20, year=16, month=10, day=23),
            time=iso.Time(hour=16, minute=14, second=40))
        v.set_from_value(dunix.with_zone(0).get_unixtime())
        self.assertTrue(isinstance(v.value, iso.TimePoint))
        self.assertTrue(v.value == dunix)
        # from a python datetime
        v.set_from_value(datetime.datetime(1969, 7, 20, 20, 17, 40))
        self.assertTrue(isinstance(v.value, iso.TimePoint))
        self.assertTrue(v.value == d)
        # from a python date
        v.set_from_value(datetime.date(1969, 7, 20))
        self.assertTrue(isinstance(v.value, iso.TimePoint))
        d0 = iso.TimePoint(date=iso.Date(century=19, year=69, month=7, day=20),
                           time=iso.Time(hour=0, minute=0, second=0))
        self.assertTrue(v.value == d0)

    def test_string_value(self):
        """Test the StringValue class."""
        v = edm.EDMValue.from_type(edm.SimpleType.String)
        # check __nonzero__
        self.assertFalse(v)
        # check is_null
        self.assertTrue(v.is_null())
        v.set_from_value(123)
        # check __nonzero__
        self.assertTrue(v)
        # check is_null
        self.assertFalse(v.is_null())
        v2 = edm.EDMValue.from_type(edm.SimpleType.String)
        v2.set_random_value()
        self.assertTrue(len(v2.value) == 8,
                        "Expected 8 characters: %s" % v2.value)
        v.set_from_value("stem")
        v2.set_random_value(v)
        self.assertTrue(len(v2.value) == 12 and v2.value[0:4] == "stem")

    def test_casts(self):
        p = edm.Property(None)
        p.simpleTypeCode = edm.SimpleType.Byte
        v = edm.SimpleValue.from_property(p)
        v.value = 13
        cast = edm.Property(None)
        cast.simpleTypeCode = edm.SimpleType.Int16
        v2 = v.cast(edm.EDMValue.from_property(cast))
        self.assertTrue(
            isinstance(v2, edm.SimpleValue), "cast gives a SimpleValue")
        self.assertTrue(
            v2.type_code == edm.SimpleType.Int16, "cast uses passed type")
        self.assertTrue(v2.value == 13, "cast to Int16")
        cast = edm.Property(None)
        cast.simpleTypeCode = edm.SimpleType.Int32
        v2 = v2.cast(edm.EDMValue.from_property(cast))
        self.assertTrue(
            v2.type_code == edm.SimpleType.Int32, "cast uses passed type")
        self.assertTrue(v2.value == 13, "cast to Int32")
        cast = edm.Property(None)
        cast.simpleTypeCode = edm.SimpleType.Int64
        v2 = v2.cast(edm.EDMValue.from_property(cast))
        self.assertTrue(
            v2.type_code == edm.SimpleType.Int64, "cast uses passed type")
        self.assertTrue(isinstance(v2.value, long2), "cast to Int64")
        self.assertTrue(v2.value == long2(13), "cast to Int64")
        cast = edm.Property(None)
        cast.simpleTypeCode = edm.SimpleType.Single
        v3 = v2.cast(edm.EDMValue.from_property(cast))
        self.assertTrue(
            v3.type_code == edm.SimpleType.Single, "cast uses passed type")
        self.assertTrue(isinstance(v3.value, float), "cast to Single")
        cast = edm.Property(None)
        cast.simpleTypeCode = edm.SimpleType.Double
        v3 = v3.cast(edm.EDMValue.from_property(cast))
        self.assertTrue(
            v3.type_code == edm.SimpleType.Double, "cast uses passed type")
        self.assertTrue(isinstance(v3.value, float), "cast to Double")
        self.assertTrue(v3.value == 13.0, "cast to Double")
        cast = edm.Property(None)
        cast.simpleTypeCode = edm.SimpleType.Decimal
        v3 = v2.cast(edm.EDMValue.from_property(cast))
        self.assertTrue(
            v3.type_code == edm.SimpleType.Decimal, "cast uses passed type")
        self.assertTrue(
            isinstance(v3.value, decimal.Decimal), "cast to Decimal")
        self.assertTrue(v3 == 13, "cast to Double")


class EntityTests(unittest.TestCase):

    def setUp(self):        # noqa
        min_es_schema = \
            """<?xml version="1.0" encoding="utf-8" standalone="yes" ?>
<Schema Namespace="SampleModel"
        xmlns="http://schemas.microsoft.com/ado/2006/04/edm">
    <EntityContainer Name="SampleEntities" m:IsDefaultEntityContainer="true">
        <EntitySet Name="Customers" EntityType="SampleModel.Customer"/>
    </EntityContainer>
    <ComplexType Name="Address">
        <Property Name="City" Type="Edm.String"/>
        <Property Name="Street" Type="Edm.String"/>
    </ComplexType>
    <EntityType Name="Customer">
        <Key>
            <PropertyRef Name="CustomerID"/>
        </Key>
        <Property Name="CustomerID" Type="Edm.String"/>
        <Property Name="Name" Type="Edm.String"/>
        <Property Name="Address" Type="SampleModel.Address"/>
        <Property Name="Region" Type="Edm.Int32"/>
    </EntityType>
</Schema>"""
        doc = edm.Document()
        doc.read(src=min_es_schema)
        scope = edm.NameTableMixin()
        scope.declare(doc.root)
        doc.root.update_type_refs(scope)
        doc.root.update_set_refs(scope)
        self.es = doc.root['SampleEntities.Customers']

    def test_init(self):
        e = edm.Entity(self.es)
        self.assertFalse(e.exists)

    def test_merge(self):
        e = edm.Entity(self.es)
        e.set_key("abc")
        e['Name'].set_from_value("Widget Co")
        e['Address']['City'].set_from_value("Smalltown")
        # regions and address street are NULL
        e2 = edm.Entity(self.es)
        e2.set_key("xyz")
        e2['Address']['Street'].set_from_value("1 Main Street")
        e2['Region'].set_from_value(1)
        self.assertFalse(e['Address']['Street'])
        e.merge(e2)
        # merges non-NULL values from e2 into e
        self.assertTrue(e['Address']['Street'])
        self.assertTrue(e['Address']['Street'].value == "1 Main Street")
        self.assertTrue(e['Region'].value == 1)
        # doesn't touch the key!
        self.assertTrue(e.key() == "abc")


if __name__ == "__main__":
    unittest.main()
