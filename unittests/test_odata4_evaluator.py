#! /usr/bin/env python

from decimal import Decimal
import logging
import unittest
import uuid
import weakref

from pyslet.iso8601 import (
    Date,
    Time,
    TimePoint,
    )
from pyslet.odata4 import (
    comex,
    data,
    errors,
    evaluator,
    geotypes as geo,
    metadata as csdl,
    model,
    names,
    parser,
    primitive,
    service,
    types as datatypes,
    )
from pyslet.py2 import (
    to_text,
    )
from pyslet.rfc2396 import URI
from pyslet.vfs import OSFilePath
from pyslet.xml.xsdatatypes import(
    Duration,
    )


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(ContextualTests, 'test'),
        unittest.makeSuite(TypeCheckerTests, 'test'),
        unittest.makeSuite(EvaluatorTests, 'test'),
        ))


TEST_DATA_DIR = OSFilePath(__file__).split()[0].join('data_odata4')


regression_model = None


def _load_regression():
    global regression_model
    # save loading this schema for every setUp
    if regression_model is None:
        dpath = TEST_DATA_DIR.join('regression.xml')
        uri = URI.from_virtual_path(dpath)
        doc = csdl.CSDLDocument(base_uri=uri)
        doc.read()
        regression_model = doc.root.entity_model


class ContextualTests(unittest.TestCase):

    def setUp(self):        # noqa
        _load_regression()

    def test_nocontext(self):
        e = evaluator.ContextualProcessor()
        self.assertTrue(e.em is None)
        self.assertTrue(e.it is None)
        self.assertTrue(e.context is None)

    def test_context(self):
        e = evaluator.ContextualProcessor(model=regression_model)
        self.assertTrue(e.em is regression_model)
        self.assertTrue(e.it is None)
        self.assertTrue(e.context is None)

    def test_reference(self):
        # References are handled directly by the parent class
        e = evaluator.ContextualProcessor()
        try:
            e.reference("Self.LastCommaFirst")
            self.fail("No context for reference")
        except errors.ExpressionError:
            pass
        # must be a LabeledExpression!
        e = evaluator.ContextualProcessor(model=regression_model)
        try:
            e.reference("Self.Person")
            self.fail("EntityType is not reference")
        except errors.ExpressionError:
            pass
        try:
            e.reference("Self.LastCommaFirst")
            self.fail("Reference evaluation not implemented")
        except NotImplementedError:
            pass


class TypeCheckerTests(unittest.TestCase):

    def setUp(self):        # noqa
        _load_regression()

    def test_constructor(self):
        tc = evaluator.TypeChecker()
        self.assertTrue(isinstance(tc, evaluator.ContextualProcessor))
        self.assertTrue(tc.em is None)
        self.assertTrue(tc.it is data.null_type)
        # you may not use a Value instance as the implicit variable
        type_def = regression_model.qualified_get("Self.String10")
        context = type_def("Hello")
        try:
            tc = evaluator.TypeChecker(it=context)
            self.fail("TypeChecker with Value context")
        except errors.ExpressionError:
            pass

    def test_unbound_primitive_context(self):
        context = regression_model.qualified_get("Self.String10")
        tc = evaluator.TypeChecker(it=context)
        self.assertTrue(tc.em is regression_model)
        self.assertTrue(tc.it is context)
        # check that model argument overrides it's model
        em = model.EntityModel()
        tc = evaluator.TypeChecker(it=context, model=em)
        self.assertTrue(tc.em is em)
        self.assertTrue(tc.it is context)

    def test_bound_primitive_context(self):
        svc = service.DataService()
        svc.model = regression_model
        context = datatypes.StringType.edm_base.derive_type()
        context.bind_to_service(weakref.ref(svc))
        tc = evaluator.TypeChecker(it=context)
        self.assertTrue(tc.em is regression_model)
        self.assertTrue(tc.it is context)
        # check that model argument overrides it's model
        em = model.EntityModel()
        tc = evaluator.TypeChecker(it=context, model=em)
        self.assertTrue(tc.em is em)
        self.assertTrue(tc.it is context)

    def test_type_context(self):
        context = regression_model.qualified_get("Self.String10")
        tc = evaluator.TypeChecker(it=context)
        self.assertTrue(tc.em is regression_model)
        self.assertTrue(tc.it is context)
        # check that model argument overrides it's model
        em = model.EntityModel()
        tc = evaluator.TypeChecker(it=context, model=em)
        self.assertTrue(tc.em is em)
        self.assertTrue(tc.it is context)

    def test_container_context(self):
        context = regression_model.qualified_get("Self.RegressionDB")
        tc = evaluator.TypeChecker(it=context)
        self.assertTrue(tc.em is regression_model)
        self.assertTrue(tc.it is context)
        # check that model argument overrides it's model
        em = model.EntityModel()
        tc = evaluator.TypeChecker(it=context, model=em)
        self.assertTrue(tc.em is em)
        self.assertTrue(tc.it is context)

    def test_property_context(self):
        # undeclared property has no context
        context = datatypes.Property()
        tc = evaluator.TypeChecker(it=context)
        self.assertTrue(tc.em is None)
        self.assertTrue(tc.it is context)
        # declared property uses containing type's context
        address = regression_model.qualified_get("Self.Address")
        context = address['Street1']
        tc = evaluator.TypeChecker(it=context)
        self.assertTrue(tc.em is regression_model)
        self.assertTrue(tc.it is context)
        # but can be overridden of course
        em = model.EntityModel()
        tc = evaluator.TypeChecker(it=context, model=em)
        self.assertTrue(tc.em is em)
        self.assertTrue(tc.it is context)

    def test_unknown_context(self):
        context = "Hello"
        try:
            evaluator.TypeChecker(it=context)
            self.fail("Unexpected context")
        except errors.ExpressionError:
            pass

    def test_null(self):
        tc = evaluator.TypeChecker()
        e = parser.Parser("null").require_common_expr()
        self.assertTrue(tc.evaluate(e) is data.null_type)

    def test_boolean(self):
        tc = evaluator.TypeChecker()
        e = parser.Parser("true").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.BooleanType.edm_base)

    def test_guid(self):
        tc = evaluator.TypeChecker()
        e = parser.Parser(
            "eb7b9f5f-7aae-4152-a920-689986c964d3").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.GuidType.edm_base)

    def test_date(self):
        tc = evaluator.TypeChecker()
        e = parser.Parser("2018-01-01").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.DateType.edm_base)

    def test_date_time_offset(self):
        tc = evaluator.TypeChecker()
        e = parser.Parser("2018-01-01T00:00:00Z").require_common_expr()
        self.assertTrue(tc.evaluate(e) is
                        datatypes.DateTimeOffsetType.edm_base)

    def test_time_of_day(self):
        tc = evaluator.TypeChecker()
        e = parser.Parser("00:00:00.001").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.TimeOfDayType.edm_base)

    def test_decimal(self):
        tc = evaluator.TypeChecker()
        e = parser.Parser("3.14159").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.DecimalType.edm_base)

    def test_double(self):
        tc = evaluator.TypeChecker()
        e = parser.Parser("3.14159e+0").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.DoubleType.edm_base)

    def test_int64(self):
        tc = evaluator.TypeChecker()
        e = parser.Parser("3").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.Int64Type.edm_base)

    def test_string(self):
        tc = evaluator.TypeChecker()
        e = parser.Parser("'It wasn''t me'").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.StringType.edm_base)

    def test_duration(self):
        tc = evaluator.TypeChecker()
        e = parser.Parser("duration'P1D'").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.DurationType.edm_base)

    def test_binary(self):
        tc = evaluator.TypeChecker()
        e = parser.Parser("binary'SXQgd2Fzbid0IG1l'").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.BinaryType.edm_base)

    def test_enum(self):
        tc = evaluator.TypeChecker()
        e = parser.Parser("Self.RGB'Red,Green'").require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("Type check enum without context")
        except errors.ExpressionError:
            pass
        tc = evaluator.TypeChecker(model=regression_model)
        e = parser.Parser("Self.CMY'Yellow'").require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("Type check undeclared enum")
        except errors.ExpressionError:
            pass
        e = parser.Parser("Self.Person'FirstName'").require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("Type check enum with incompatible context")
        except errors.ExpressionError:
            pass
        e = parser.Parser("Self.RGB'Red,Green'").require_common_expr()
        self.assertTrue(
            tc.evaluate(e) is regression_model.qualified_get('Self.RGB'))

    def test_geography(self):
        tc = evaluator.TypeChecker()
        e = parser.Parser(
            "geography'SRID=4326;Point(-127.89734578345 45.234534534)'"
            ).require_common_expr()
        self.assertTrue(tc.evaluate(e) is
                        datatypes.GeographyPointType.edm_base)

    def test_geometry(self):
        tc = evaluator.TypeChecker()
        e = parser.Parser(
            "geometry'SRID=0;Point(1.0 -1.0)'").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.GeometryPointType.edm_base)

    def test_parameter(self):
        tc = evaluator.TypeChecker()
        e = parser.Parser("@param").require_common_expr()
        # undeclared parameters are treated as null so could be any
        # type
        self.assertTrue(tc.evaluate(e) is data.null_type)
        tc.declare_param("param", comex.Int64Expression(3))
        self.assertTrue(tc.evaluate(e) is datatypes.Int64Type.edm_base)

    def test_root(self):
        tc = evaluator.TypeChecker()
        e = comex.RootExpression()
        try:
            tc.evaluate(e)
            self.fail("$root without context")
        except errors.ExpressionError:
            pass
        core_model = csdl.CSDLDocument.load_core().get_model()
        tc = evaluator.TypeChecker(model=core_model)
        try:
            tc.evaluate(e)
            self.fail("$root context but no container")
        except errors.ExpressionError:
            pass
        tc = evaluator.TypeChecker(model=regression_model)
        self.assertTrue(isinstance(tc.evaluate(e), model.EntityContainer))

    def test_implicit_variable(self):
        it = comex.ItExpression()
        # For a collection-valued resource the current instance: i.e.,
        # the type of $it is the item type of the collection not the
        # type of the collection itself!
        person = regression_model.qualified_get("Self.Person")
        tc = evaluator.TypeChecker(it=person)
        self.assertTrue(tc.evaluate(it) is person)
        # For a single-valued resource it is the resource itself
        address = regression_model.qualified_get("Self.Address")
        tc = evaluator.TypeChecker(it=address)
        self.assertTrue(tc.evaluate(it) is address)
        # If there is no current value (it was None on creation) then
        # it could be any type and we should return the null type
        tc = evaluator.TypeChecker()
        self.assertTrue(tc.evaluate(it) is data.null_type)

    def test_collection(self):
        # simple collection
        tc = evaluator.TypeChecker()
        e = parser.Parser('["Red","Green","Blue"]').require_common_expr()
        c = tc.evaluate(e)
        self.assertTrue(isinstance(c, datatypes.CollectionType))
        self.assertTrue(c.item_type is datatypes.StringType.edm_base)
        # The items in a collection must be type compatible
        e = parser.Parser('["Red",2,"Blue"]').require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("Edm.String and Edm.Int64 in Collection")
        except errors.ExpressionError:
            pass
        # All numeric types are compatible with each other
        e = parser.Parser('[1,2.0,3.0E+30]').require_common_expr()
        c = tc.evaluate(e)
        self.assertTrue(isinstance(c, datatypes.CollectionType))
        self.assertTrue(c.item_type is
                        datatypes.DoubleType.edm_base, to_text(c))
        e = parser.Parser('[1,2.0,3.0]').require_common_expr()
        c = tc.evaluate(e)
        self.assertTrue(isinstance(c, datatypes.CollectionType))
        self.assertTrue(c.item_type is datatypes.DecimalType.edm_base)
        e = parser.Parser('[1,2,3]').require_common_expr()
        c = tc.evaluate(e)
        self.assertTrue(isinstance(c, datatypes.CollectionType))
        self.assertTrue(c.item_type is datatypes.Int64Type.edm_base)
        # unknown types are ignored when type checking
        e = comex.CollectionExpression()
        e.add_operand(comex.StringExpression('Red'))
        e.add_operand(comex.NullExpression())
        c = tc.evaluate(e)
        self.assertTrue(isinstance(c, datatypes.CollectionType))
        self.assertTrue(c.item_type is datatypes.StringType.edm_base)
        # bad type: ID to be resolved to Int64
        person = regression_model.qualified_get("Self.Person")
        e = comex.CollectionExpression()
        e.add_operand(comex.StringExpression('Red'))
        e.add_operand(comex.IdentifierExpression('ID'))
        tc = evaluator.TypeChecker(it=person)
        try:
            tc.evaluate(e)
            self.fail("Edm.String and Edm.Int64 in Collection")
        except errors.ExpressionError:
            pass
        # For complex types (not allowed in inline expressions) things
        # are more complex as a type hierarchy with TypeA and TypeB both
        # independently derived from TypeC means that TypeA and TypeB
        # are not compatible (there are no values that are both A and B)
        # but they clearly could both appear in Collection(TypeC).  We
        # therefore have to extend our notion of compatible to include
        # an implicit ancestor.
        person = regression_model.qualified_get("Self.Person")
        location = regression_model.qualified_get("Self.Location")
        tc = evaluator.TypeChecker(it=person)
        e = comex.CollectionExpression()
        e.add_operand(comex.IdentifierExpression('Address'))
        e.add_operand(comex.IdentifierExpression('Region'))
        # Address and Region share a common ancestor type
        c = tc.evaluate(e)
        self.assertTrue(isinstance(c, datatypes.CollectionType))
        self.assertTrue(c.item_type is location)
        # Like Edm.PrimitiveType, Collection(Edm.ComplexType) is not
        # allowed.  The unknown type created by record values (JSON
        # objects in inline notation) is a special undeclared complex
        # type derived from Edm.ComplexType so this rule means we don't
        # support collections (defined in Annotations) such as
        # [Address,{"Street":"5 High St"}] even though the undeclared
        # Record is likely to be assignable to the complex type used for
        # Address.
        r = parser.Parser('{"Country":"UK"}').require_common_expr()
        e.add_operand(r)
        try:
            tc.evaluate(e)
            self.fail("Collection(ComplexType) not allowed")
        except errors.ExpressionError:
            pass
        # obviously you can't mix complex types and primitive types
        e = comex.CollectionExpression()
        e.add_operand(comex.IdentifierExpression('Address'))
        e.add_operand(comex.IdentifierExpression('ID'))
        try:
            tc.evaluate(e)
            self.fail("Collection(ComplexType) not allowed")
        except errors.ExpressionError:
            pass
        # EntityTypes are treated like ComplexType except that you are
        # allowed to have Collection(EntityType) if you want. You still
        # can't mix records in with EntityType though as there is no
        # common ancestor, even though they may be assignable.
        order = regression_model.qualified_get("Self.Order")
        tc = evaluator.TypeChecker(it=order)
        e = comex.CollectionExpression()
        e.add_operand(comex.IdentifierExpression('Customer'))
        e.add_operand(comex.IdentifierExpression('Salesperson'))
        # Customer and Salesperson share a common ancestor type
        c = tc.evaluate(e)
        self.assertTrue(isinstance(c, datatypes.CollectionType))
        self.assertTrue(c.item_type is person)
        e.add_operand(comex.IdentifierExpression('ShippingAgent'))
        # but not with ShippingAgent
        c = tc.evaluate(e)
        self.assertTrue(isinstance(c, datatypes.CollectionType))
        self.assertTrue(c.item_type is data.edm_entity_type)
        # you can't mix complex and entity types
        e.add_operand(comex.IdentifierExpression('ShippingAddress'))
        try:
            tc.evaluate(e)
            self.fail("Collection(ComplexType) not allowed")
        except errors.ExpressionError:
            pass

    def test_record(self):
        # simple record
        tc = evaluator.TypeChecker()
        e = parser.Parser('{"Colour": "Red"}').require_common_expr()
        c = tc.evaluate(e)
        self.assertTrue(isinstance(c, datatypes.ComplexType))
        # you can't have duplicate names
        e = parser.Parser(
            '{"Colour": "Red", "Colour": "Green"}').require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("Dupicate member name in Record")
        except errors.ExpressionError:
            pass

    def test_member(self):
        tc = evaluator.TypeChecker()
        # no context, non-reserved name requires a context
        e = comex.IdentifierExpression('Address')
        try:
            tc.evaluate(e)
            self.fail("Address without context")
        except errors.PathError:
            pass
        # no context, reserved name is resolved correctly
        e = comex.IdentifierExpression('true')
        t = tc.evaluate(e)
        self.assertTrue(t is datatypes.BooleanType.edm_base)
        # no context, qualified name cannot be resolved
        e = parser.Parser('Self.Employee/EmployeeNumber').require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("qualified name without context")
        except errors.ExpressionError:
            pass
        person = regression_model.qualified_get("Self.Person")
        tc = evaluator.TypeChecker(it=person)
        # property name is valid
        address = regression_model.qualified_get("Self.Address")
        e = comex.IdentifierExpression('Address')
        t = tc.evaluate(e)
        self.assertTrue(t is address)
        # property path is valid
        e = parser.Parser('Address/Country').require_common_expr()
        t = tc.evaluate(e)
        self.assertTrue(t is datatypes.StringType.edm_base)
        # property path is invalid
        e = parser.Parser('Address/Unknown').require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("Invalid path")
        except errors.PathError:
            pass
        e = parser.Parser('Address/Country/Region').require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("Invalid path")
        except errors.PathError:
            pass
        e = parser.Parser('Self.Employee/EmployeeNumber').require_common_expr()
        t = tc.evaluate(e)
        self.assertTrue(t is datatypes.StringType.edm_base)
        e = parser.Parser(
            'Self.Employee/EmployeeNumber/Self.Address').require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("Cast requires complex or entity type")
        except errors.PathError:
            pass
        e = parser.Parser('Self.Company/Name').require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("Invalid cast")
        except errors.PathError:
            pass
        e = parser.Parser('Self.HomeAddress/Country').require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("Invalid cast object")
        except errors.PathError:
            pass
        # unbound function
        employee = regression_model.qualified_get("Self.Employee")
        e = parser.Parser('Self.TopSalesperson()').require_common_expr()
        t = tc.evaluate(e)
        self.assertTrue(t is employee, t)
        # entity set obtained through $root
        e = parser.Parser('$root/People(23)').require_common_expr()
        t = tc.evaluate(e)
        self.assertTrue(t is person, t)
        # unknown name obtained through $root
        e = parser.Parser('$root/Unknown(23)').require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("$root/Unknown")
        except errors.PathError:
            pass
        # Function import obtained through $root (not allowed!)
        e = parser.Parser('$root/TopSalesperson').require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("$root/TopSalesperson")
        except errors.ExpressionError:
            pass
        # unexpected type
        e = comex.MemberExpression()
        e.add_operand(comex.Int64Expression(42))
        e.add_operand(comex.IdentifierExpression("Country"))
        try:
            tc.evaluate(e)
            self.fail("42/Country")
        except errors.PathError:
            pass
        #
        # if there is not context, cast doesn't work
        tc = evaluator.TypeChecker(model=regression_model)
        e = parser.Parser('Self.Employee/EmployeeNumber').require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("cast without context")
        except errors.PathError:
            pass
        # unbound function still works
        e = parser.Parser('Self.TopSalesperson()').require_common_expr()
        t = tc.evaluate(e)
        self.assertTrue(t is employee, t)

    def test_member_args(self):
        person = regression_model.qualified_get("Self.Person")
        tc = evaluator.TypeChecker(it=person)
        # bound function
        address = regression_model.qualified_get("Self.Address")
        e = parser.Parser('Self.PreviousAddresses()').require_common_expr()
        t = tc.evaluate(e)
        self.assertTrue(isinstance(t, datatypes.CollectionType))
        self.assertTrue(t.item_type is address)
        # unbound function
        employee = regression_model.qualified_get("Self.Employee")
        e = parser.Parser('Self.TopSalesperson()').require_common_expr()
        t = tc.evaluate(e)
        self.assertTrue(t is employee, t)
        # key predicate
        company = regression_model.qualified_get("Self.Company")
        tc = evaluator.TypeChecker(it=company)
        e = parser.Parser('Contacts(23)').require_common_expr()
        t = tc.evaluate(e)
        self.assertTrue(t is person)
        # badly bound function
        e = parser.Parser('Self.PreviousAddresses()').require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("Company/Self.PreviousAddresses()")
        except errors.ExpressionError:
            pass
        # unbound call of bound function
        tc = evaluator.TypeChecker(model=regression_model)
        e = parser.Parser('Self.PreviousAddresses()').require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("[$root]/Self.PreviousAddresses()")
        except errors.ExpressionError:
            pass
        # anything other than FunctionOverload or EntitySet/Collection
        key = comex.ArgsExpression()
        key.add_operand(comex.Int64Expression(42))
        try:
            with tc.new_context(person):
                tc.member_args(key)
            self.fail("Person(42)")
        except errors.ExpressionError:
            pass
        people = person.collection_type()
        with tc.new_context(people):
            t = tc.member_args(key)
        self.assertTrue(t is person)
        key = comex.ArgsExpression()
        id = comex.BindExpression()
        id.add_operand(comex.IdentifierExpression("ID"))
        id.add_operand(comex.Int64Expression(42))
        key.add_operand(id)
        # explicit key
        with tc.new_context(people):
            t = tc.member_args(key)
        self.assertTrue(t is person)
        # key with wrong name
        id.name = "Wrong"
        try:
            with tc.new_context(people):
                tc.member_args(key)
            self.fail("People(Wrong=42)")
        except errors.ExpressionError:
            pass
        # key with too many values
        id.name = "ID"
        xid = comex.BindExpression()
        xid.add_operand(comex.IdentifierExpression("XID"))
        xid.add_operand(comex.Int64Expression(3))
        key.add_operand(xid)
        try:
            with tc.new_context(people):
                tc.member_args(key)
            self.fail("People(ID=42,XID=3)")
        except errors.ExpressionError:
            pass
        # key with duplicate value
        xid.name = "ID"
        try:
            with tc.new_context(people):
                tc.member_args(key)
            self.fail("People(ID=42,ID=3)")
        except errors.ExpressionError:
            pass
        # key with bad type
        key = comex.ArgsExpression()
        id = comex.BindExpression()
        id.add_operand(comex.IdentifierExpression("ID"))
        id.add_operand(comex.StringExpression("42"))
        key.add_operand(id)
        try:
            with tc.new_context(people):
                tc.member_args(key)
            self.fail("People(ID='42')")
        except errors.ExpressionError:
            pass
        # key with undeclared parameter alias
        e = parser.Parser('$root/People(@ID)').require_common_expr()
        t = tc.evaluate(e)
        self.assertTrue(t is person)

    def test_member_count(self):
        tc = evaluator.TypeChecker()
        person = regression_model.qualified_get("Self.Person")
        people = person.collection_type()
        with tc.new_context(people):
            t = tc.member_count()
        self.assertTrue(t is datatypes.Int64Type.edm_base)
        address = regression_model.qualified_get("Self.Address")
        with tc.new_context(address.collection_type()):
            t = tc.member_count()
        self.assertTrue(t is datatypes.Int64Type.edm_base)
        with tc.new_context(datatypes.StringType.edm_base.collection_type()):
            t = tc.member_count()
        self.assertTrue(t is datatypes.Int64Type.edm_base)
        db = regression_model.qualified_get("Self.RegressionDB")
        try:
            with tc.new_context(db['People'].type_def):
                tc.member_count()
            self.fail("$root/People/$count")
        except errors.ExpressionError:
            pass

    def test_member_any(self):
        person = regression_model.qualified_get("Self.Person")
        tc = evaluator.TypeChecker(it=person)
        people = person.collection_type()
        # Collection(Person)/any()
        with tc.new_context(people):
            t = tc.member_any()
        self.assertTrue(t is datatypes.BooleanType.edm_base)
        # Collection(Address)/any()
        address = regression_model.qualified_get("Self.Address")
        with tc.new_context(address.collection_type()):
            t = tc.member_any()
        self.assertTrue(t is datatypes.BooleanType.edm_base)
        # Collection(Edm.String)/any()
        with tc.new_context(datatypes.StringType.edm_base.collection_type()):
            t = tc.member_any()
        self.assertTrue(t is datatypes.BooleanType.edm_base)
        # check parameter forms
        e = parser.Parser("x/FirstName eq 'Jane'").require_common_expr()
        with tc.new_context(people):
            t = tc.member_any("x", e)
        self.assertTrue(t is datatypes.BooleanType.edm_base)
        e = parser.Parser("x/Country eq 'gb'").require_common_expr()
        with tc.new_context(address.collection_type()):
            t = tc.member_any("x", e)
        self.assertTrue(t is datatypes.BooleanType.edm_base)
        e = parser.Parser("x eq 'gb'").require_common_expr()
        with tc.new_context(datatypes.StringType.edm_base.collection_type()):
            t = tc.member_any("x", e)
        self.assertTrue(t is datatypes.BooleanType.edm_base)
        # check that $it still works
        e = parser.Parser("x/LastName eq $it/LastName").require_common_expr()
        with tc.new_context(people):
            t = tc.member_any("x", e)
        self.assertTrue(t is datatypes.BooleanType.edm_base)

    def test_member_all(self):
        person = regression_model.qualified_get("Self.Person")
        tc = evaluator.TypeChecker(it=person)
        people = person.collection_type()
        # Collection(Person)/all(x:x/FirstName eq 'Jane')
        e = parser.Parser("x/FirstName eq 'Jane'").require_common_expr()
        with tc.new_context(people):
            t = tc.member_all("x", e)
        self.assertTrue(t is datatypes.BooleanType.edm_base)
        # Collection(Address)/all(x:x/Country eq 'gb')
        e = parser.Parser("x/Country eq 'gb'").require_common_expr()
        address = regression_model.qualified_get("Self.Address")
        with tc.new_context(address.collection_type()):
            t = tc.member_all("x", e)
        self.assertTrue(t is datatypes.BooleanType.edm_base)
        # Collection(Edm.String)/all(x:x eq 'gb')
        e = parser.Parser("x eq 'gb'").require_common_expr()
        with tc.new_context(datatypes.StringType.edm_base.collection_type()):
            t = tc.member_all("x", e)
        self.assertTrue(t is datatypes.BooleanType.edm_base)
        # check that $it still works
        # Collection(Person)/all(x:x/LastName eq $it/LastName)
        e = parser.Parser("x/LastName eq $it/LastName").require_common_expr()
        with tc.new_context(people):
            t = tc.member_all("x", e)
        self.assertTrue(t is datatypes.BooleanType.edm_base)

    def test_mindatetime(self):
        e = parser.Parser("mindatetime()").require_common_expr()
        tc = evaluator.TypeChecker()
        self.assertTrue(tc.evaluate(e) is
                        datatypes.DateTimeOffsetType.edm_base)

    def test_maxdatetime(self):
        e = parser.Parser("maxdatetime()").require_common_expr()
        tc = evaluator.TypeChecker()
        self.assertTrue(tc.evaluate(e) is
                        datatypes.DateTimeOffsetType.edm_base)

    def test_now(self):
        e = parser.Parser("now()").require_common_expr()
        tc = evaluator.TypeChecker()
        self.assertTrue(tc.evaluate(e) is
                        datatypes.DateTimeOffsetType.edm_base)

    def test_length(self):
        company = regression_model.qualified_get("Self.Company")
        tc = evaluator.TypeChecker(it=company)
        e = parser.Parser("length('Hello')").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.Int64Type.edm_base)
        e = parser.Parser("length(Contacts)").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.Int64Type.edm_base)
        e = parser.Parser("length(ID)").require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("length(Edm.Int64)")
        except errors.ExpressionError:
            pass

    def test_string_methods(self):
        company = regression_model.qualified_get("Self.Company")
        tc = evaluator.TypeChecker(it=company)
        for m in ("tolower", "toupper", "trim"):
            e = parser.Parser("%s('Hello')" % m).require_common_expr()
            self.assertTrue(tc.evaluate(e) is datatypes.StringType.edm_base)
            e = parser.Parser("%s(Name)" % m).require_common_expr()
            self.assertTrue(tc.evaluate(e) is datatypes.StringType.edm_base)
            e = parser.Parser("%s(ID)" % m).require_common_expr()
            try:
                tc.evaluate(e)
                self.fail("%s(Edm.Int64)" % m)
            except errors.ExpressionError:
                pass

    def test_date_methods(self):
        order = regression_model.qualified_get("Self.Order")
        tc = evaluator.TypeChecker(it=order)
        for m in ("year", "month", "day"):
            e = parser.Parser("%s(2018-01-01)" % m).require_common_expr()
            self.assertTrue(tc.evaluate(e) is primitive.edm_int32)
            e = parser.Parser("%s(WhenReceived)" % m).require_common_expr()
            self.assertTrue(tc.evaluate(e) is primitive.edm_int32)
            e = parser.Parser("%s(ID)" % m).require_common_expr()
            try:
                tc.evaluate(e)
                self.fail("%s(Edm.Int64)" % m)
            except errors.ExpressionError:
                pass

    def test_time_methods(self):
        order = regression_model.qualified_get("Self.Order")
        tc = evaluator.TypeChecker(it=order)
        for m in ("hour", "minute", "second"):
            e = parser.Parser("%s(16:00:00)" % m).require_common_expr()
            self.assertTrue(tc.evaluate(e) is primitive.edm_int32)
            e = parser.Parser("%s(WhenReceived)" % m).require_common_expr()
            self.assertTrue(tc.evaluate(e) is primitive.edm_int32)
            e = parser.Parser("%s(ID)" % m).require_common_expr()
            try:
                tc.evaluate(e)
                self.fail("%s(Edm.Int64)" % m)
            except errors.ExpressionError:
                pass

    def test_fractionalseconds(self):
        order = regression_model.qualified_get("Self.Order")
        tc = evaluator.TypeChecker(it=order)
        e = parser.Parser("fractionalseconds(16:00:00)").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.DecimalType.edm_base)
        e = parser.Parser(
            "fractionalseconds(WhenReceived)").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.DecimalType.edm_base)
        e = parser.Parser("fractionalseconds(ID)").require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("fractionalseconds(Edm.Int64)")
        except errors.ExpressionError:
            pass

    def test_totalseconds(self):
        order = regression_model.qualified_get("Self.Order")
        tc = evaluator.TypeChecker(it=order)
        e = parser.Parser("totalseconds(duration'P1D')").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.DecimalType.edm_base)
        e = parser.Parser("totalseconds(ID)").require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("totalseconds(Edm.Int64)")
        except errors.ExpressionError:
            pass

    def test_date_method(self):
        order = regression_model.qualified_get("Self.Order")
        tc = evaluator.TypeChecker(it=order)
        e = parser.Parser("date(WhenReceived)").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.DateType.edm_base)
        e = parser.Parser("date(ID)").require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("date(Edm.Int64)")
        except errors.ExpressionError:
            pass

    def test_time_method(self):
        order = regression_model.qualified_get("Self.Order")
        tc = evaluator.TypeChecker(it=order)
        e = parser.Parser("time(WhenReceived)").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.TimeOfDayType.edm_base)
        e = parser.Parser("time(ID)").require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("time(Edm.Int64)")
        except errors.ExpressionError:
            pass

    def test_totaloffsetminutes(self):
        order = regression_model.qualified_get("Self.Order")
        tc = evaluator.TypeChecker(it=order)
        e = parser.Parser(
            "totaloffsetminutes(WhenReceived)").require_common_expr()
        self.assertTrue(tc.evaluate(e) is primitive.edm_int32)
        e = parser.Parser("totaloffsetminutes(ID)").require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("totaloffsetminutes(Edm.Int64)")
        except errors.ExpressionError:
            pass

    def test_math_methods(self):
        order = regression_model.qualified_get("Self.Order")
        tc = evaluator.TypeChecker(it=order)
        for m in ("round", "floor", "ceiling"):
            e = parser.Parser("%s(3.1E20)" % m).require_common_expr()
            self.assertTrue(tc.evaluate(e) is datatypes.DoubleType.edm_base)
            e = parser.Parser("%s(3.1)" % m).require_common_expr()
            self.assertTrue(tc.evaluate(e) is datatypes.DecimalType.edm_base)
            e = parser.Parser("%s(ID)" % m).require_common_expr()
            self.assertTrue(tc.evaluate(e) is datatypes.DecimalType.edm_base)
            e = parser.Parser("%s(null)" % m).require_common_expr()
            self.assertTrue(tc.evaluate(e) is datatypes.DecimalType.edm_base)
            e = parser.Parser("%s(WhenReceived)" % m).require_common_expr()
            try:
                tc.evaluate(e)
                self.fail("%s(Edm.DateTimeOffset)" % m)
            except errors.ExpressionError:
                pass

    def test_geo_length(self):
        tc = evaluator.TypeChecker()
        e = parser.Parser(
            "geo.length(geography'SRID=4326;LineString(1 -1,-1 1)')"
            ).require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.DoubleType.edm_base)
        e = parser.Parser(
            "geo.length(geometry'SRID=0;LineString(1 -1,-1 1)')"
            ).require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.DoubleType.edm_base)
        e = parser.Parser(
            "geo.length(geography'SRID=4326;Point(1 -1)')"
            ).require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("geo.length(Edm.GeographyPoint)")
        except errors.ExpressionError:
            pass

    def test_string_test_methods(self):
        company = regression_model.qualified_get("Self.Company")
        tc = evaluator.TypeChecker(it=company)
        for m in ("contains", "startswith", "endswith"):
            e = parser.Parser("%s('Hello','H')" % m).require_common_expr()
            self.assertTrue(tc.evaluate(e) is datatypes.BooleanType.edm_base)
            e = parser.Parser("%s(Name,'H')" % m).require_common_expr()
            self.assertTrue(tc.evaluate(e) is datatypes.BooleanType.edm_base)
            e = parser.Parser("%s(ID,'H')" % m).require_common_expr()
            try:
                tc.evaluate(e)
                self.fail("%s(Edm.Int64,Edm.String)" % m)
            except errors.ExpressionError:
                pass
            e = parser.Parser("%s('H',ID)" % m).require_common_expr()
            try:
                tc.evaluate(e)
                self.fail("%s(Edm.String,Edm.Int64)" % m)
            except errors.ExpressionError:
                pass
            e = parser.Parser("%s('H')" % m).require_common_expr()
            try:
                tc.evaluate(e)
                self.fail("%s(Edm.String)" % m)
            except errors.ExpressionError:
                pass

    def test_indexof(self):
        company = regression_model.qualified_get("Self.Company")
        tc = evaluator.TypeChecker(it=company)
        e = parser.Parser("indexof('Hello','H')").require_common_expr()
        self.assertTrue(tc.evaluate(e) is primitive.edm_int32)
        e = parser.Parser("indexof(Name,'H')").require_common_expr()
        self.assertTrue(tc.evaluate(e) is primitive.edm_int32)
        e = parser.Parser("indexof(ID,'H')").require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("indexof(Edm.Int64,Edm.String)")
        except errors.ExpressionError:
            pass
        e = parser.Parser("indexof('H',ID)").require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("indexof(Edm.String,Edm.Int64)")
        except errors.ExpressionError:
            pass
        e = parser.Parser("indexof('H')").require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("indexof(Edm.String)")
        except errors.ExpressionError:
            pass

    def test_concat(self):
        company = regression_model.qualified_get("Self.Company")
        tc = evaluator.TypeChecker(it=company)
        e = parser.Parser("concat('Hello','H')").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.StringType.edm_base)
        e = parser.Parser("concat(Name,'H')").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.StringType.edm_base)
        e = parser.Parser("concat(ID,'H')").require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("concat(Edm.Int64,Edm.String)")
        except errors.ExpressionError:
            pass
        e = parser.Parser("concat('H',ID)").require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("concat(Edm.String,Edm.Int64)")
        except errors.ExpressionError:
            pass
        e = parser.Parser("concat('H')").require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("concat(Edm.String)")
        except errors.ExpressionError:
            pass

    def test_geo_distance(self):
        tc = evaluator.TypeChecker()
        e = parser.Parser(
            "geo.distance(geography'SRID=4326;Point(1 -1)',"
            "geography'SRID=4326;Point(-1 1)')"
            ).require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.DoubleType.edm_base)
        e = parser.Parser(
            "geo.distance(geometry'SRID=4326;Point(1 -1)',"
            "geometry'SRID=4326;Point(-1 1)')"
            ).require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.DoubleType.edm_base)
        e = parser.Parser(
            "geo.distance(geometry'SRID=4326;Point(1 -1)',"
            "geography'SRID=4326;Point(-1 1)')"
            ).require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.DoubleType.edm_base)
        e = parser.Parser(
            "geo.distance(geography'SRID=4326;Point(1 -1)',"
            "geography'SRID=4326;LineString(1 -1,-1 1)')')"
            ).require_common_expr()
        try:
            tc.evaluate(e)
            self.fail(
                "geo.distance(Edm.GeographyPoint,Edm.GeographyLineString)")
        except errors.ExpressionError:
            pass

    def test_geo_intersects(self):
        tc = evaluator.TypeChecker()
        e = parser.Parser(
            "geo.intersects(geography'SRID=4326;Point(1 -1)',"
            "geography'SRID=4326;Polygon((1.5 -1.5,1.5 1.5,-1.5 1.5,"
            "-1.5 -1.5,1.5 -1.5))')"
            ).require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.BooleanType.edm_base)
        e = parser.Parser(
            "geo.intersects(geometry'SRID=4326;Point(1 -1)',"
            "geometry'SRID=4326;Polygon((1.5 -1.5,1.5 1.5,-1.5 1.5,"
            "-1.5 -1.5,1.5 -1.5))')"
            ).require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.BooleanType.edm_base)
        e = parser.Parser(
            "geo.intersects(geometry'SRID=4326;Point(1 -1)',"
            "geography'SRID=4326;Polygon((1.5 -1.5,1.5 1.5,-1.5 1.5,"
            "-1.5 -1.5,1.5 -1.5))')"
            ).require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.BooleanType.edm_base)
        e = parser.Parser(
            "geo.distance(geography'SRID=4326;Point(1 -1)',"
            "geography'SRID=4326;LineString(1 -1,-1 1)')')"
            ).require_common_expr()
        try:
            tc.evaluate(e)
            self.fail(
                "geo.intersects(Edm.GeographyPoint,Edm.GeographyLineString)")
        except errors.ExpressionError:
            pass
        e = parser.Parser(
            "geo.intersects(geography'SRID=4326;LineString(1 -1,-1 1)',"
            "geography'SRID=4326;Polygon((1.5 -1.5,1.5 1.5,-1.5 1.5,"
            "-1.5 -1.5,1.5 -1.5))')"
            ).require_common_expr()
        try:
            tc.evaluate(e)
            self.fail(
                "geo.intersects(Edm.GeographyLineString,Edm.GeographyPolygon)")
        except errors.ExpressionError:
            pass

    def test_substring(self):
        company = regression_model.qualified_get("Self.Company")
        tc = evaluator.TypeChecker(it=company)
        e = parser.Parser("substring('Hello',1)").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.StringType.edm_base)
        e = parser.Parser("substring(Name,2)").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.StringType.edm_base)
        e = parser.Parser("substring(ID,1)").require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("substring(Edm.Int64,Edm.Int64)")
        except errors.ExpressionError:
            pass
        e = parser.Parser("substring('Hello','lo')").require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("substring(Edm.String,Edm.String)")
        except errors.ExpressionError:
            pass
        # 3-argument forms
        e = parser.Parser("substring('Hello',1,2)").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.StringType.edm_base)
        e = parser.Parser("substring('Hello',1,'lo')").require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("substring(Edm.String,Edm.Int64,Edm.String)")
        except errors.ExpressionError:
            pass

    def test_boolean_ops(self):
        company = regression_model.qualified_get("Self.Company")
        tc = evaluator.TypeChecker(it=company)
        for op in ("and", "or"):
            e = parser.Parser("true %s false" % op).require_common_expr()
            self.assertTrue(tc.evaluate(e) is datatypes.BooleanType.edm_base)
            e = parser.Parser("true %s null" % op).require_common_expr()
            self.assertTrue(tc.evaluate(e) is datatypes.BooleanType.edm_base)
            e = parser.Parser("null %s false" % op).require_common_expr()
            self.assertTrue(tc.evaluate(e) is datatypes.BooleanType.edm_base)
            e = parser.Parser("null %s null" % op).require_common_expr()
            self.assertTrue(tc.evaluate(e) is datatypes.BooleanType.edm_base)
            e = parser.Parser("true %s ID" % op).require_common_expr()
            try:
                tc.evaluate(e)
                self.fail("Edm.Boolean %s Edm.Int64" % op)
            except errors.ExpressionError:
                pass
            e = parser.Parser("Name %s false" % op).require_common_expr()
            try:
                tc.evaluate(e)
                self.fail("Edm.String %s Edm.Boolean" % op)
            except errors.ExpressionError:
                pass
        e = parser.Parser("not true").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.BooleanType.edm_base)
        e = parser.Parser("not Name").require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("not Edm.String")
        except errors.ExpressionError:
            pass

    numeric = set(
            ('Byte', 'SByte', 'Int16', 'Int32', 'Int64', 'Decimal', 'Single',
             'Double'))

    def test_comparisons(self):
        allprim = regression_model.qualified_get("Self.AllPrimitives")
        tc = evaluator.TypeChecker(it=allprim)
        pnames = list(allprim.keys()) + ["null"]
        unsupported = set(('Binary', 'Stream'))
        for left in pnames:
            for right in pnames:
                # test eq
                eq = parser.Parser(
                    "%s eq %s" % (left, right)).require_common_expr()
                ne = parser.Parser(
                    "%s ne %s" % (left, right)).require_common_expr()
                gt = parser.Parser(
                    "%s gt %s" % (left, right)).require_common_expr()
                ge = parser.Parser(
                    "%s ge %s" % (left, right)).require_common_expr()
                le = parser.Parser(
                    "%s lt %s" % (left, right)).require_common_expr()
                lt = parser.Parser(
                    "%s le %s" % (left, right)).require_common_expr()
                if left.startswith("Geo") or left in unsupported:
                    # Edm.Binary, Edm.Stream and Edm.Geo can only be
                    # compared to the null value using eq and ne
                    if right == "null":
                        for e in (eq, ne):
                            self.assertTrue(tc.evaluate(e) is
                                            datatypes.BooleanType.edm_base)
                        for e in (gt, ge, lt, le):
                            try:
                                tc.evaluate(e)
                                self.fail(
                                    "Unsupported comparison: %s" %
                                    comex.ExpressionFormatter().evaluate(e)[1])
                            except errors.ExpressionError:
                                pass
                    else:
                        for e in (eq, ne, gt, ge, lt, le):
                            try:
                                tc.evaluate(e)
                                self.fail(
                                    "Unsupported comparison: %s" %
                                    comex.ExpressionFormatter().evaluate(e)[1])
                            except errors.ExpressionError:
                                pass
                elif (left == right or
                        (left in self.numeric and right in self.numeric) or
                        right == "null"):
                    for e in (eq, ne, gt, ge, lt, le):
                        self.assertTrue(
                            tc.evaluate(e) is datatypes.BooleanType.edm_base)
                elif left == "null":
                    if right.startswith("Geo") or right in unsupported:
                        for e in (eq, ne):
                            self.assertTrue(tc.evaluate(e) is
                                            datatypes.BooleanType.edm_base)
                        for e in (gt, ge, lt, le):
                            try:
                                tc.evaluate(e)
                                self.fail("Unsupported comparison")
                            except errors.ExpressionError:
                                pass
                    else:
                        for e in (eq, ne, gt, ge, lt, le):
                            self.assertTrue(tc.evaluate(e) is
                                            datatypes.BooleanType.edm_base)
                else:
                    # non-matching non-null primitive types
                    for e in (eq, ne, gt, ge, lt, le):
                        try:
                            tc.evaluate(e)
                            self.fail(
                                "Mismatched types for comparison: %s" %
                                comex.ExpressionFormatter().evaluate(e)[1])
                        except errors.ExpressionError:
                            pass

    def test_has(self):
        order = regression_model.qualified_get("Self.Order")
        tc = evaluator.TypeChecker(it=order)
        e = parser.Parser(
            "Self.RGB'Red,Blue' has Self.RGB'Green'").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.BooleanType.edm_base)
        e = parser.Parser(
            "null has Self.RGB'Green,Blue'").require_common_expr()
        self.assertTrue(tc.evaluate(e) is datatypes.BooleanType.edm_base)
        # it's an error if the flags are from a different enumeration
        e = parser.Parser(
            "Self.RGB'Red,Blue' has Self.FileAccess'Read'"
            ).require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("mismatched flags enum in has")
        except errors.ExpressionError:
            pass
        e = parser.Parser(
            "ShippingMethod has Self.ShippingMethod'FirstClass'"
            ).require_common_expr()
        try:
            tc.evaluate(e)
            self.fail("non-flags")
        except errors.ExpressionError:
            pass

    _pmap = {"Double": 0, "Single": 1, "Decimal": 2, "Int64": 3,
             "Int32": 4, "Int16": 5, "Byte": 6, "SByte": 7, "null": 8}

    _plist = [datatypes.DoubleType.edm_base,
              primitive.edm_single,
              datatypes.DecimalType.edm_base,
              datatypes.Int64Type.edm_base,
              primitive.edm_int32,
              primitive.edm_int16,
              primitive.edm_int16,
              primitive.edm_sbyte,
              primitive.edm_int16]  # null add null

    def arithmetic_promotion(self, a, b):
        a = self._pmap.get(a, -1)
        b = self._pmap.get(b, -1)
        if a < 0 or b < 0:
            return None
        else:
            return self._plist[min(a, b)]

    def test_add(self):
        allprim = regression_model.qualified_get("Self.AllPrimitives")
        tc = evaluator.TypeChecker(it=allprim)
        pnames = list(allprim.keys()) + ["null"]
        for left in pnames:
            for right in pnames:
                e = parser.Parser(
                    "%s add %s" % (left, right)).require_common_expr()
                atype = self.arithmetic_promotion(left, right)
                if (left == "DateTimeOffset" and
                        right in ("Duration", "null")):
                    self.assertTrue(tc.evaluate(e) is
                                    datatypes.DateTimeOffsetType.edm_base)
                elif (left == "Duration" and right in ("Duration", "null")):
                    self.assertTrue(
                        tc.evaluate(e) is datatypes.DurationType.edm_base)
                elif left == "Date" and right in ("Duration", "null"):
                    self.assertTrue(
                        tc.evaluate(e) is datatypes.DateType.edm_base)
                elif left == "null" and right == "Duration":
                    self.assertTrue(tc.evaluate(e) is data.null_type)
                elif left == "null" and right == "null":
                    self.assertTrue(tc.evaluate(e) is data.null_type)
                elif atype is not None:
                    self.assertTrue(
                        tc.evaluate(e) is atype, (left, right, atype))
                else:
                    try:
                        tc.evaluate(e)
                        self.fail(
                            "Unsupported add operation %s" %
                            repr((left, right, atype)))
                    except errors.ExpressionError:
                        pass

    def test_sub(self):
        allprim = regression_model.qualified_get("Self.AllPrimitives")
        tc = evaluator.TypeChecker(it=allprim)
        pnames = list(allprim.keys()) + ["null"]
        for left in pnames:
            for right in pnames:
                e = parser.Parser(
                    "%s sub %s" % (left, right)).require_common_expr()
                atype = self.arithmetic_promotion(left, right)
                if left == "DateTimeOffset" and right == "Duration":
                    self.assertTrue(tc.evaluate(e) is
                                    datatypes.DateTimeOffsetType.edm_base)
                elif left == "DateTimeOffset" and right == "DateTimeOffset":
                    self.assertTrue(
                        tc.evaluate(e) is datatypes.DurationType.edm_base)
                elif left == "DateTimeOffset" and right == "null":
                    self.assertTrue(tc.evaluate(e) is data.null_type)
                elif left == "Duration" and right in ("Duration", "null"):
                    self.assertTrue(
                        tc.evaluate(e) is datatypes.DurationType.edm_base)
                elif left == "Date" and right == "Duration":
                    self.assertTrue(
                        tc.evaluate(e) is datatypes.DateType.edm_base)
                elif left == "Date" and right == "Date":
                    self.assertTrue(
                        tc.evaluate(e) is datatypes.DurationType.edm_base)
                elif left == "Date" and right == "null":
                    self.assertTrue(tc.evaluate(e) is data.null_type)
                elif left == "null" and right in ("DateTimeOffset", "Date"):
                    self.assertTrue(
                        tc.evaluate(e) is datatypes.DurationType.edm_base)
                elif left == "null" and right in ("Duration", "null"):
                    self.assertTrue(tc.evaluate(e) is data.null_type)
                elif atype is not None:
                    self.assertTrue(tc.evaluate(e) is atype)
                else:
                    try:
                        tc.evaluate(e)
                        self.fail("Unsupported sub operation")
                    except errors.ExpressionError:
                        pass

    def test_mul(self):
        allprim = regression_model.qualified_get("Self.AllPrimitives")
        tc = evaluator.TypeChecker(it=allprim)
        pnames = list(allprim.keys()) + ["null"]
        for left in pnames:
            for right in pnames:
                e = parser.Parser(
                    "%s mul %s" % (left, right)).require_common_expr()
                atype = self.arithmetic_promotion(left, right)
                if left == "Duration" and (
                        right in self.numeric or right == "null"):
                    self.assertTrue(
                        tc.evaluate(e) is datatypes.DurationType.edm_base)
                elif right == "Duration" and (
                        left in self.numeric or left == "null"):
                    self.assertTrue(
                        tc.evaluate(e) is datatypes.DurationType.edm_base,
                        (left, right, atype))
                elif atype is not None:
                    if left == "null" or right == "null":
                        # could be numeric or duration
                        self.assertTrue(
                            tc.evaluate(e) is data.null_type,
                            (left, right, atype))
                    else:
                        self.assertTrue(tc.evaluate(e) is atype)
                else:
                    try:
                        tc.evaluate(e)
                        self.fail("Unsupported mul operation")
                    except errors.ExpressionError:
                        pass

    def test_div(self):
        allprim = regression_model.qualified_get("Self.AllPrimitives")
        tc = evaluator.TypeChecker(it=allprim)
        pnames = list(allprim.keys()) + ["null"]
        for left in pnames:
            for right in pnames:
                e = parser.Parser(
                    "%s div %s" % (left, right)).require_common_expr()
                atype = self.arithmetic_promotion(left, right)
                if left == "Duration" and (
                        right in self.numeric or right == "null"):
                    self.assertTrue(
                        tc.evaluate(e) is datatypes.DurationType.edm_base)
                elif atype is not None:
                    if left == "null":
                        # could be numeric or duration
                        self.assertTrue(
                            tc.evaluate(e) is data.null_type,
                            (left, right, atype))
                    else:
                        self.assertTrue(tc.evaluate(e) is atype)
                else:
                    try:
                        tc.evaluate(e)
                        self.fail("Unsupported div operation")
                    except errors.ExpressionError:
                        pass

    def test_mod(self):
        allprim = regression_model.qualified_get("Self.AllPrimitives")
        tc = evaluator.TypeChecker(it=allprim)
        pnames = list(allprim.keys()) + ["null"]
        for left in pnames:
            for right in pnames:
                e = parser.Parser(
                    "%s mod %s" % (left, right)).require_common_expr()
                atype = self.arithmetic_promotion(left, right)
                if left == "null" and right == "null":
                    # could be any numeric, we return null by convention
                    # (in part because we can't navigate the model from
                    # null type as it isn't declared anywhere).
                    self.assertTrue(tc.evaluate(e) is data.null_type)
                elif atype is not None:
                    self.assertTrue(tc.evaluate(e) is atype)
                else:
                    try:
                        tc.evaluate(e)
                        self.fail("Unsupported mod operation")
                    except errors.ExpressionError:
                        pass

    def test_negate(self):
        allprim = regression_model.qualified_get("Self.AllPrimitives")
        tc = evaluator.TypeChecker(it=allprim)
        pnames = list(allprim.keys()) + ["null"]
        for p in pnames:
            e = parser.Parser("-%s" % p).require_common_expr()
            atype = self.arithmetic_promotion("null", p)
            if p == "Duration":
                self.assertTrue(
                    tc.evaluate(e) is datatypes.DurationType.edm_base)
            elif p == "null":
                self.assertTrue(tc.evaluate(e) is data.null_type)
            elif atype is not None:
                self.assertTrue(
                    tc.evaluate(e) is atype, (p, atype))
            else:
                try:
                    tc.evaluate(e)
                    self.fail("Unsupported negate operation")
                except errors.ExpressionError:
                    pass


class EvaluatorTests(unittest.TestCase):

    def setUp(self):        # noqa
        _load_regression()

    def test_constructor(self):
        ev = evaluator.Evaluator()
        self.assertTrue(isinstance(ev, evaluator.ContextualProcessor))
        self.assertTrue(ev.em is None)
        self.assertTrue(isinstance(ev.it, data.Value))
        self.assertTrue(ev.it.is_null())
        self.assertTrue(ev.it.type_def is datatypes.NullType.edm_base)

    def test_unbound_primitive_context(self):
        context = regression_model.qualified_get("Self.String10")("Hello")
        ev = evaluator.Evaluator(it=context)
        self.assertTrue(ev.em is regression_model)
        self.assertTrue(ev.it is context)
        # check that model argument overrides it's model
        em = model.EntityModel()
        ev = evaluator.Evaluator(it=context, model=em)
        self.assertTrue(ev.em is em)
        self.assertTrue(ev.it is context)

    def test_bound_primitive_context(self):
        svc = service.DataService()
        svc.model = regression_model
        context = datatypes.StringType.edm_base.derive_type()("Hello")
        context.bind_to_service(svc)
        ev = evaluator.Evaluator(it=context)
        self.assertTrue(ev.em is regression_model)
        self.assertTrue(ev.it is context)
        # check that model argument overrides it's model
        em = model.EntityModel()
        ev = evaluator.Evaluator(it=context, model=em)
        self.assertTrue(ev.em is em)
        self.assertTrue(ev.it is context)

    def test_type_context(self):
        context = regression_model.qualified_get("Self.String10")
        ev = evaluator.Evaluator(it=context)
        self.assertTrue(ev.em is regression_model)
        self.assertTrue(ev.it is context)
        # check that model argument overrides it's model
        em = model.EntityModel()
        ev = evaluator.Evaluator(it=context, model=em)
        self.assertTrue(ev.em is em)
        self.assertTrue(ev.it is context)

    def test_container_context(self):
        context = regression_model.qualified_get("Self.RegressionDB")
        ev = evaluator.Evaluator(it=context)
        self.assertTrue(ev.em is regression_model)
        self.assertTrue(ev.it is context)
        # check that model argument overrides it's model
        em = model.EntityModel()
        ev = evaluator.Evaluator(it=context, model=em)
        self.assertTrue(ev.em is em)
        self.assertTrue(ev.it is context)

    def test_property_context(self):
        # undeclared property has no context
        context = datatypes.Property()
        ev = evaluator.Evaluator(it=context)
        self.assertTrue(ev.em is None)
        self.assertTrue(ev.it is context)
        # declared property uses containing type's context
        address = regression_model.qualified_get("Self.Address")
        context = address['Street1']
        ev = evaluator.Evaluator(it=context)
        self.assertTrue(ev.em is regression_model)
        self.assertTrue(ev.it is context)
        # but can be overridden of course
        em = model.EntityModel()
        ev = evaluator.Evaluator(it=context, model=em)
        self.assertTrue(ev.em is em)
        self.assertTrue(ev.it is context)

    def test_unknown_context(self):
        context = "Hello"
        try:
            evaluator.Evaluator(it=context)
            self.fail("Unexpected context")
        except errors.ExpressionError:
            pass

    def test_common(self):
        e = comex.CommonExpression()
        # we don't need a context for this test
        ev = evaluator.Evaluator()
        try:
            ev.evaluate(e)
            self.fail("Evaluator evaluated CommonExpression")
        except NotImplementedError:
            pass

    def test_null(self):
        e = comex.NullExpression()
        ev = evaluator.Evaluator()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, data.Value))
        self.assertTrue(value.type_def is datatypes.NullType.edm_base)
        self.assertTrue(value.is_null())

    def test_boolean(self):
        e = comex.BooleanExpression(True)
        ev = evaluator.Evaluator()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, primitive.BooleanValue))
        self.assertTrue(value.type_def is datatypes.BooleanType.edm_base)
        self.assertFalse(value.is_null())
        self.assertTrue(value.get_value() is True)
        e = comex.BooleanExpression(False)
        value = ev.evaluate(e)
        self.assertTrue(value.get_value() is False)

    def test_guid(self):
        pv = uuid.UUID(int=3)
        e = comex.GuidExpression(pv)
        ev = evaluator.Evaluator()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, primitive.GuidValue))
        self.assertTrue(value.type_def is datatypes.GuidType.edm_base)
        self.assertFalse(value.is_null())
        self.assertTrue(value.get_value() == pv)

    def test_date(self):
        pv = Date.from_str('2017-12-30')
        e = comex.DateExpression(pv)
        ev = evaluator.Evaluator()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, primitive.DateValue))
        self.assertFalse(value.is_null())
        self.assertTrue(value.get_value() == pv)

    def test_date_time_offset(self):
        pv = TimePoint.from_str('2017-12-30T15:00:00Z')
        e = comex.DateTimeOffsetExpression(pv)
        ev = evaluator.Evaluator()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, primitive.DateTimeOffsetValue))
        self.assertFalse(value.is_null())
        self.assertTrue(value.get_value() == pv)

    def test_time_of_day(self):
        pv = Time.from_str('15:00:00')
        e = comex.TimeOfDayExpression(pv)
        ev = evaluator.Evaluator()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, primitive.TimeOfDayValue))
        self.assertFalse(value.is_null())
        self.assertTrue(value.get_value() == pv)

    def test_decimal(self):
        pv = Decimal('1.50')
        e = comex.DecimalExpression(pv)
        ev = evaluator.Evaluator()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, primitive.DecimalValue))
        self.assertFalse(value.is_null())
        self.assertTrue(value.get_value() == pv)

    def test_double(self):
        e = comex.DoubleExpression(1.5)
        ev = evaluator.Evaluator()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, primitive.DoubleValue))
        self.assertFalse(value.is_null())
        self.assertTrue(value.get_value() == 1.5)

    def test_int64(self):
        e = comex.Int64Expression(3)
        ev = evaluator.Evaluator()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, primitive.Int64Value))
        self.assertFalse(value.is_null())
        self.assertTrue(value.get_value() == 3)

    def test_string(self):
        pv = "It's My Life"
        e = comex.StringExpression(pv)
        ev = evaluator.Evaluator()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, primitive.StringValue))
        self.assertFalse(value.is_null())
        self.assertTrue(value.get_value() == pv)

    def test_duration(self):
        pv = Duration('PT15H1.5S')
        e = comex.DurationExpression(pv)
        ev = evaluator.Evaluator()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, primitive.DurationValue))
        self.assertFalse(value.is_null())
        self.assertTrue(value.get_value() == pv)

    def test_binary(self):
        pv = b"It's My Life"
        e = comex.BinaryDataExpression(pv)
        ev = evaluator.Evaluator()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, primitive.BinaryValue))
        self.assertFalse(value.is_null())
        self.assertTrue(value.get_value() == pv)

    def test_enum(self):
        bad_schema = names.QualifiedName("Schema", "RGB")
        bad_type = names.QualifiedName("Self", "RedGreenBlue")
        wrong_type = names.QualifiedName("Self", "String10")
        qname = names.QualifiedName("Self", "RGB")
        pv = names.EnumLiteral(qname, ("Red", "Green", "Blue"))
        e = comex.EnumExpression(pv)
        ev = evaluator.Evaluator()
        try:
            ev.evaluate(e)
            self.fail("Evaluator evaluated enum without a context")
        except errors.ExpressionError:
            pass
        for q in (bad_schema, bad_type, wrong_type):
            pv = names.EnumLiteral(q, ("Red", "Green", "Blue"))
            e = comex.EnumExpression(pv)
            ev = evaluator.Evaluator(model=regression_model)
            try:
                ev.evaluate(e)
                self.fail("Evaluator evaluated %s" % to_text(pv))
            except errors.ExpressionError:
                pass
        pv = names.EnumLiteral(qname, ("Red", "Green", "Blue"))
        e = comex.EnumExpression(pv)
        ev = evaluator.Evaluator(model=regression_model)
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, primitive.EnumerationValue))
        self.assertFalse(value.is_null())
        self.assertTrue(value.get_value() == pv.value, to_text(value))

    def test_geography(self):
        pv = geo.PointLiteral(
                srid=4326,
                point=geo.Point(-1.00244140625, 51.44775390625))
        e = comex.GeographyExpression(pv)
        ev = evaluator.Evaluator()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, primitive.GeographyPointValue))
        self.assertFalse(value.is_null())
        self.assertTrue(value.get_value() == pv)

    def test_geometry(self):
        pv = geo.PointLiteral(
                srid=0,
                point=geo.Point(-1.00244140625, 51.44775390625))
        e = comex.GeometryExpression(pv)
        ev = evaluator.Evaluator()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, primitive.GeometryPointValue))
        self.assertFalse(value.is_null())
        self.assertTrue(value.get_value() == pv)

    def test_parameter(self):
        e = comex.ParameterExpression("param")
        ev = evaluator.Evaluator()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, data.Value))
        self.assertTrue(value.is_null())
        # now check that the evaluator will accept parameters
        ev.declare_param("param", comex.Int64Expression(3))
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, primitive.Int64Value))
        self.assertFalse(value.is_null())
        self.assertTrue(value.get_value() == 3)
        ev.declare_param("param", comex.StringExpression("Three"))
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, primitive.StringValue))
        self.assertFalse(value.is_null())
        self.assertTrue(value.get_value() == "Three")

    def test_root(self):
        e = comex.RootExpression()
        ev = evaluator.Evaluator()
        try:
            # root expression requires a context
            ev.evaluate(e)
            self.fail("$root without context")
        except errors.ExpressionError:
            pass
        core_model = csdl.CSDLDocument.load_core().get_model()
        ev = evaluator.Evaluator(model=core_model)
        try:
            ev.evaluate(e)
            self.fail("$root context but no container")
        except errors.ExpressionError:
            pass
        ev = evaluator.Evaluator(model=regression_model)
        # the TypeChecker and Evaluator return the same object for $root
        # as there is not "EntityContainer" type.
        self.assertTrue(isinstance(ev.evaluate(e), model.EntityContainer))

    def test_implicit_variable(self):
        it = comex.ItExpression()
        # For a collection-valued resource the current instance
        person = regression_model.qualified_get("Self.Person")()
        ev = evaluator.Evaluator(it=person)
        self.assertTrue(ev.evaluate(it) is person)
        # For a single-valued resource it is the resource itself
        address = regression_model.qualified_get("Self.Address")()
        ev = evaluator.Evaluator(it=address)
        self.assertTrue(ev.evaluate(it) is address)
        # If there is no current value (it was None on creation) then it
        # defaults to null and should evaluate as such
        ev = evaluator.Evaluator()
        value = ev.evaluate(it)
        self.assertTrue(isinstance(value, data.Value))
        self.assertTrue(value.is_null())

    def test_collection(self):
        # simple collection
        ev = evaluator.Evaluator()
        e = parser.Parser('["Red","Green","Blue"]').require_common_expr()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, data.CollectionValue))
        self.assertTrue(len(value) == 3)
        blue = value[2]
        self.assertTrue(isinstance(blue, primitive.StringValue))
        self.assertTrue(blue.get_value() == "Blue")
        # The items in a collection must be type compatible
        e = parser.Parser('["Red",2,"Blue"]').require_common_expr()
        try:
            ev.evaluate(e)
            self.fail("Edm.String and Edm.Int64 in Collection")
        except errors.ExpressionError:
            pass
        # All numeric types are compatible with each other
        e = parser.Parser('[1,2.0,3.0E+30]').require_common_expr()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, data.CollectionValue))
        self.assertTrue(len(value) == 3)
        v0 = value[0]
        self.assertTrue(isinstance(v0, primitive.DoubleValue))
        self.assertTrue(v0.get_value() == 1.0)
        v1 = value[1]
        self.assertTrue(isinstance(v1, primitive.DoubleValue))
        self.assertTrue(v1.get_value() == 2.0)
        e = parser.Parser('[1,2.0,3.0]').require_common_expr()
        value = ev.evaluate(e)
        v0 = value[0]
        self.assertTrue(isinstance(v0, primitive.DecimalValue))
        self.assertTrue(v0.get_value() == Decimal('1'))
        e = parser.Parser('[1,2,3]').require_common_expr()
        value = ev.evaluate(e)
        v0 = value[0]
        self.assertTrue(isinstance(v0, primitive.Int64Value))
        self.assertTrue(v0.get_value() == 1)
        # null values are permitted
        e = parser.Parser('[1,null,3]').require_common_expr()
        value = ev.evaluate(e)
        self.assertTrue(len(value) == 3)
        v1 = value[1]
        self.assertTrue(isinstance(v1, primitive.Int64Value))
        self.assertTrue(v1.is_null())
        # special case: collection of nulls
        e = parser.Parser('[null,null,null]').require_common_expr()
        value = ev.evaluate(e)
        self.assertTrue(len(value) == 3)
        self.assertTrue(
            value.type_def.item_type is datatypes.NullType.edm_base)
        for v in value:
            self.assertTrue(type(v) is data.Value)
            self.assertTrue(v.is_null())
        # special case: empty collection
        e = comex.CollectionExpression()
        value = ev.evaluate(e)
        self.assertTrue(len(value) == 0)
        self.assertTrue(
            value.type_def.item_type is datatypes.NullType.edm_base)
        # for annotation expressions, collections may contain more
        # complex children such as PathExpressions that are evaluated
        # using the current context, we simulate this for the moment to
        # defer the evaluation of PathExpression.
        person = regression_model.qualified_get("Self.Person")()
        person.set_defaults()
        person['ID'].set_value(1)
        e = comex.CollectionExpression()
        e.add_operand(comex.StringExpression('Red'))
        e.add_operand(comex.IdentifierExpression('ID'))
        ev = evaluator.Evaluator(it=person)
        try:
            ev.evaluate(e)
            self.fail("Edm.String and Edm.Int64 in Collection")
        except errors.ExpressionError:
            pass
        # tricky case, the null value is always considered to have no
        # type and is assignable to any type so if ID is null this will
        # evaluate correctly overriding the type mismatch that is
        # evident in the expression itself.
        person['ID'].set_value(None)
        value = ev.evaluate(e)
        self.assertTrue(len(value) == 2)
        v1 = value[1]
        self.assertTrue(isinstance(v1, primitive.StringValue))
        self.assertTrue(v1.is_null())
        # check determination of common ancestor
        location = regression_model.qualified_get("Self.Location")
        person['Address']['Country'].set_value("gb")
        person['Region']['Country'].set_value("us")
        e = comex.CollectionExpression()
        e.add_operand(comex.IdentifierExpression('Address'))
        e.add_operand(comex.IdentifierExpression('Region'))
        value = ev.evaluate(e)
        self.assertTrue(len(value) == 2)
        self.assertTrue(value.type_def.item_type is location)

    def test_record(self):
        # simple record
        ev = evaluator.Evaluator()
        e = parser.Parser('{"Colour": "Red"}').require_common_expr()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, data.ComplexValue))
        self.assertTrue("Colour" in value)
        colour = value['Colour']
        self.assertTrue(isinstance(colour, primitive.StringValue))
        self.assertTrue(colour.get_value() == "Red")
        # you can't have duplicate names
        e = parser.Parser(
            '{"Colour": "Red", "Colour": "Green"}').require_common_expr()
        try:
            ev.evaluate(e)
            self.fail("Dupicate member name in Record")
        except errors.ExpressionError:
            pass

    def test_member(self):
        ev = evaluator.Evaluator()
        # no context, non-reserved name requires a context
        e = comex.IdentifierExpression('Address')
        try:
            ev.evaluate(e)
            self.fail("Address without context")
        except errors.PathError:
            pass
        # no context, reserved name is resolved correctly
        e = comex.IdentifierExpression('true')
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, primitive.BooleanValue))
        self.assertTrue(value.get_value() is True)
        # no context, qualified name cannot be resolved
        e = parser.Parser('Self.Employee/EmployeeNumber').require_common_expr()
        try:
            ev.evaluate(e)
            self.fail("qualified name without context")
        except errors.ExpressionError:
            pass
        employee_type = regression_model.qualified_get("Self.Employee")
        person = regression_model.qualified_get("Self.Person")()
        person.set_defaults()
        ev = evaluator.Evaluator(it=person)
        # can't cast an actual person to an employee, return a null
        # typed to the expected path
        value = ev.evaluate(e)
        self.assertTrue(value.is_null())
        self.assertTrue(value.type_def is datatypes.StringType.edm_base)
        employee = employee_type()
        employee.set_defaults()
        employee['EmployeeNumber'].set_value("1")
        employee['Address']['Country'].set_value('gb')
        ev = evaluator.Evaluator(it=employee)
        # type cast is OK
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, primitive.StringValue))
        self.assertTrue(value.get_value() == "1")
        # test valid property name
        address_type = regression_model.qualified_get("Self.Address")
        e = comex.IdentifierExpression('Address')
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, data.ComplexValue))
        self.assertTrue(value.type_def is address_type)
        # test valid property path
        e = parser.Parser('Address/Country').require_common_expr()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, primitive.StringValue))
        self.assertTrue(value.get_value() == "gb")
        e = parser.Parser('Address/Unknown').require_common_expr()
        try:
            ev.evaluate(e)
            self.fail("Invalid path")
        except errors.PathError:
            pass
        e = parser.Parser('Address/Country/Region').require_common_expr()
        try:
            ev.evaluate(e)
            self.fail("Invalid path")
        except errors.PathError:
            pass
        e = parser.Parser(
            'Self.Employee/EmployeeNumber/Self.Address').require_common_expr()
        try:
            ev.evaluate(e)
            self.fail("Cast requires complex or entity type")
        except errors.PathError:
            pass
        e = parser.Parser('Self.Company/Name').require_common_expr()
        # although this cast can never work and will fail the
        # TypeChecker we return null
        value = ev.evaluate(e)
        self.assertTrue(value.is_null())
        self.assertTrue(value.type_def is datatypes.StringType.edm_base)
        e = parser.Parser('Self.HomeAddress/Country').require_common_expr()
        try:
            ev.evaluate(e)
            self.fail("Invalid cast object")
        except errors.PathError:
            pass
        # Function import obtained through $root (not allowed!)
        e = parser.Parser('$root/TopSalesperson').require_common_expr()
        try:
            ev.evaluate(e)
            self.fail("$root/TopSalesperson")
        except errors.ExpressionError:
            pass
        # unexpected type
        e = comex.MemberExpression()
        e.add_operand(comex.Int64Expression(42))
        e.add_operand(comex.IdentifierExpression("Country"))
        try:
            ev.evaluate(e)
            self.fail("42/Country")
        except errors.PathError:
            pass
        #
        # if there is not context, cast doesn't work
        ev = evaluator.Evaluator(model=regression_model)
        e = parser.Parser('Self.Employee/EmployeeNumber').require_common_expr()
        try:
            ev.evaluate(e)
            self.fail("cast without context")
        except errors.PathError:
            pass
        # unbound function still works
        e = parser.Parser('Self.TopSalesperson()').require_common_expr()
        try:
            value = ev.evaluate(e)
            self.fail("Unbound call")
        except errors.UnboundValue:
            # the callable is not bound, we'll check bound cases as
            # part of testing member_args
            pass

    def test_member_args(self):
        person_type = regression_model.qualified_get("Self.Person")
        employee_type = regression_model.qualified_get("Self.Employee")
        address_type = regression_model.qualified_get("Self.Address")

        class MockCall(service.DataRequest):

            def execute_request(self, track_changes=None, callback=None):
                if self.target.type_def.name == "PreviousAddresses":
                    self.result = address_type.collection_type()()
                elif self.target.type_def.name == "TopSalesperson":
                    self.result = employee_type()
                else:
                    self.result = ValueError()

        class MockService(service.DataService):

            def call_function(self, function):
                return MockCall(self, function)

        svc = MockService()
        svc.model = regression_model
        person = person_type()
        # bind this value to the service
        person.bind_to_service(svc)
        ev = evaluator.Evaluator(it=person)
        # bound function
        e = parser.Parser('Self.PreviousAddresses()').require_common_expr()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, data.CollectionValue))
        self.assertTrue(value.type_def.item_type is address_type)
        # unbound function
        e = parser.Parser('Self.TopSalesperson()').require_common_expr()
        ubcall = regression_model.qualified_get(
            "Self.TopSalesperson").name_bindings[("", )]
        try:
            # need to simulate this function being bound to a service
            ubcall.service_ref = weakref.ref(svc)
            value = ev.evaluate(e)
        finally:
            ubcall.service_ref = None
        self.assertTrue(isinstance(value, data.EntityValue))
        self.assertTrue(value.type_def is employee_type)
        # key predicate: we need an entity bound to an entity set to
        # trigger the navigation binding for the Contacts property
        companies = regression_model['Self']['RegressionDB']['Companies']()
        company = companies.new_item()
        company.set_defaults()
        company.expand('Contacts')
        contacts = company['Contacts']
        person23 = contacts.new_item()
        person23.set_defaults()
        person23['ID'].set_value(23)
        contacts.insert(person23)
        ev = evaluator.Evaluator(it=company)
        e = parser.Parser('Contacts(23)').require_common_expr()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, data.EntityValue))
        self.assertTrue(value.type_def is person_type)
        self.assertTrue(value.get_key() == 23)
        # explicit key
        e = parser.Parser('Contacts(ID=23)').require_common_expr()
        value = ev.evaluate(e)
        self.assertTrue(isinstance(value, data.EntityValue))
        self.assertTrue(value.type_def is person_type)
        self.assertTrue(value.get_key() == 23)
        # bad key
        e = parser.Parser('Contacts(Wrong=23)').require_common_expr()
        try:
            ev.evaluate(e)
            self.fail("Contacts(Wrong=23)")
        except errors.ExpressionError:
            pass
        e = parser.Parser('Contacts(ID=23,Wrong=24)').require_common_expr()
        try:
            ev.evaluate(e)
            self.fail("Contacts(ID=23,Wrong=24)")
        except errors.ExpressionError:
            pass
        e = parser.Parser('Contacts(ID=23,ID=24)').require_common_expr()
        try:
            ev.evaluate(e)
            self.fail("Contacts(ID=23,ID=24)")
        except errors.ExpressionError:
            pass
        # key with bad type
        e = parser.Parser("Contacts(ID='23')").require_common_expr()
        try:
            ev.evaluate(e)
            self.fail("Contacts(ID='23')")
        except errors.ExpressionError:
            pass
        # key with undeclared parameter alias
        e = parser.Parser('Contacts(@ID)').require_common_expr()
        try:
            ev.evaluate(e)
            self.fail("Contacts(@ID)")
        except errors.ExpressionError:
            pass
        # key with declared parameter alias
        ev.declare_param('ID', comex.Int64Expression(23))
        try:
            # this looks like it should work but key predicates may not
            # use parameter aliases according to the ABNF so this is
            # always interpreted as a method call.
            ev.evaluate(e)
            self.fail("Contacts(@ID); @ID=23")
        except errors.ExpressionError:
            pass
        # anything other than FunctionOverload or EntitySet/Collection
        key = comex.ArgsExpression()
        key.add_operand(comex.Int64Expression(42))
        try:
            with ev.new_context(person23):
                ev.member_args(key)
            self.fail("Person(42)")
        except errors.ExpressionError:
            pass
        # badly bound function
        e = parser.Parser('Self.PreviousAddresses()').require_common_expr()
        try:
            ev.evaluate(e)
            self.fail("Company/Self.PreviousAddresses()")
        except errors.ExpressionError:
            pass
        # unbound call of bound function
        ev = evaluator.Evaluator(model=regression_model)
        e = parser.Parser('Self.PreviousAddresses()').require_common_expr()
        try:
            ev.evaluate(e)
            self.fail("[$root]/Self.PreviousAddresses()")
        except errors.ExpressionError:
            pass

    def test_bool_common_expressions(self):
        for estr, value in (
                ("2 eq 2", True),
                ("2 eq 3", False),
                ("null eq null", True),
                ("null eq 3", False),
                ("2 ne 3", True),
                ("2 ne 2", False),
                ("null ne 3", True),
                ("null ne null", False),
                ("3 gt 2", True),
                ("3 gt 3", False),
                ("2 gt null", None),
                ("null gt 2", None),
                ("null gt null", None),
                # For Boolean Values, true is greater than false
                ("true gt false", True),
                ("3 ge 2", True),
                ("3 ge 3", True),
                ("3 ge 4", False),
                ("2 ge null", None),
                ("null ge 2", None),
                # If both operands are null it return true
                ("null ge null", True),
                ("2 lt 3", True),
                ("2 lt 2", False),
                ("2 lt null", None),
                ("null lt 2", None),
                ("null lt null", None),
                ("2 le 3", True),
                ("2 le 2", True),
                ("2 le 1", False),
                ("2 le null", None),
                ("null le 2", None),
                # If both operands are null it return true
                ("null le null", True),
                ("false and false", False),
                ("false and true", False),
                ("true and false", False),
                ("true and true", True),
                # if one operand evaluates to null and the other operand
                # to false the and operator returns false
                ("false and null", False),
                ("null and false", False),
                # all other combinations with null return null
                ("true and null", None),
                ("null and true", None),
                ("null and null", None),
                ("false or false", False),
                ("false or true", True),
                ("true or false", True),
                ("true or true", True),
                # if one operand evaluates to null and the other operand
                # to true the or operator returns true
                ("true or null", True),
                ("null or true", True),
                # All other combinations with null return null
                ("false or null", None),
                ("null or false", None),
                ("null or null", None),
                ("not true", False),
                ("not false", True),
                # not null returns null
                ("not null", None),
                ):
            try:
                e = parser.Parser(estr).require_bool_common_expr()
            except parser.ParserError as err:
                self.fail(
                    "%s failed to parse: %s" % (repr(estr), to_text(err)))
            result = evaluator.Evaluator().evaluate(e)
            self.assertTrue(isinstance(result, primitive.BooleanValue),
                            "%s returned %s" % (repr(estr), repr(result)))
            self.assertTrue(
                result.value is value, "%s returned %s" %
                (repr(estr), to_text(result) if result else 'null'))

    def test_cast(self):
        # The null value can be cast to any type
        e = parser.Parser("cast(Edm.String)").require_common_expr()
        it = primitive.Int64Value()
        result = evaluator.Evaluator(it=it).evaluate(e)
        self.assertTrue(isinstance(result, primitive.StringValue))
        self.assertTrue(result.is_null())
        # Primitives use literal representation
        it.set_value(3)
        result = evaluator.Evaluator(it=it).evaluate(e)
        self.assertTrue(isinstance(result, primitive.StringValue))
        self.assertTrue(result.get_value() == "3")
        # and WKT for Geo types
        p = geo.PointLiteral(4326, geo.Point(-127.89734578345, 45.234534534))
        it = primitive.GeographyPointValue(p)
        result = evaluator.Evaluator(it=it).evaluate(e)
        self.assertTrue(isinstance(result, primitive.StringValue))
        self.assertTrue(result.get_value() ==
                        "SRID=4326;Point(-127.89734578345 45.234534534)")
        # cast fails if the target type specifies insufficient length
        e = parser.Parser("cast(Self.String10)").require_common_expr()
        it = primitive.Int64Value(12345678901)
        result = evaluator.Evaluator(
            it=it, model=regression_model).evaluate(e)
        self.assertTrue(isinstance(result, primitive.StringValue))
        self.assertTrue(result.is_null())
        # the rest of the cast tests are done by testing the cast
        # method on the appropriate Value instances.


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(levelname)s %(message)s")
    unittest.main()
