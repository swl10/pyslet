#! /usr/bin/env python

import decimal
import logging
import unittest
import uuid

from pyslet.odata4 import (
    comex,
    names,
    parser,
    query,
    )
from pyslet.py2 import (
    is_text,
    to_text,
    u8,
    ul,
    )


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(ParserTests, 'test'),
        ))


class ParserTests(unittest.TestCase):

    # literals enclosed in single quotes are treated case-sensitive

    def from_str(self, meth, good, bad):
        for s in good:
            logging.debug("%s(%s)", meth.__name__, repr(s))
            p = parser.Parser(s)
            try:
                meth(p)
                p.require_end()
            except ValueError as e:
                logging.error(str(e))
                self.fail("%s(%s) failed" % (meth.__name__, repr(s)))
        for s in bad:
            p = parser.Parser(s)
            try:
                meth(p)
                p.require_end()
                self.fail("%s(%s) succeeded" % (meth.__name__, repr(s)))
            except ValueError:
                pass

    def test_expand(self):
        # work through examples from the specification
        p = parser.Parser("Category")
        expand = p.require_expand()
        self.assertTrue(len(expand) == 1)
        cat = expand[0]
        self.assertTrue(isinstance(cat, query.ExpandItem))
        self.assertTrue(isinstance(cat.path, tuple))
        self.assertTrue(len(cat.path) == 1)
        self.assertTrue(cat.path == ("Category", ))
        self.assertTrue(cat.options.select == [])
        self.assertTrue(cat.options.expand == [])
        self.assertTrue(cat.options.skip is None)
        self.assertTrue(cat.options.top is None)
        self.assertTrue(cat.options.count is None)
        self.assertTrue(cat.options.filter is None)
        self.assertTrue(cat.options.search is None)
        self.assertTrue(cat.options.orderby == ())
        self.assertTrue(cat.options.levels is None)
        p = parser.Parser("Addresses/Country")
        expand = p.require_expand()
        self.assertTrue(len(expand) == 1)
        item = expand[0]
        self.assertTrue(item.path == ("Addresses", "Country"))
        p = parser.Parser("Products($filter=DiscontinuedDate eq null)")
        expand = p.require_expand()
        self.assertTrue(len(expand) == 1)
        item = expand[0]
        self.assertTrue(item.path == ("Products", ))
        filter = item.options.filter
        self.assertTrue(isinstance(filter, comex.BinaryExpression))
        self.assertTrue(filter.op_code == comex.Operator.eq)
        self.assertTrue(len(filter.operands) == 2)
        lop = filter.operands[0]
        self.assertTrue(isinstance(lop, comex.IdentifierExpression))
        self.assertTrue(lop.identifier == "DiscontinuedDate")
        rop = filter.operands[1]
        self.assertTrue(isinstance(rop, comex.IdentifierExpression), rop)
        self.assertTrue(rop.identifier == "null")
        p = parser.Parser("Products/$count")
        expand = p.require_expand()
        item = expand[0]
        self.assertTrue(item.path == ("Products", "$count"))
        p = parser.Parser("Products/$count($search=blue)")
        expand = p.require_expand()
        item = expand[0]
        self.assertTrue(item.path == ("Products", "$count"))
        search = item.options.search
        self.assertTrue(isinstance(search, comex.WordExpression))
        self.assertTrue(search.word == "blue")
        p = parser.Parser("Products/$ref")
        expand = p.require_expand()
        item = expand[0]
        self.assertTrue(item.path == ("Products", "$ref"))
        p = parser.Parser("Products/Sales.PremierProduct/$ref")
        expand = p.require_expand()
        self.assertTrue(len(expand) == 1)
        item = expand[0]
        self.assertTrue(len(item.path) == 3)
        self.assertTrue(
            item.path == (
                "Products",
                names.QualifiedName("Sales", "PremierProduct"), "$ref"),
            item.path)
        p = parser.Parser("Products/Sales.PremierProduct/$ref"
                          "($filter=CurrentPromotion eq null)")
        expand = p.require_expand()
        self.assertTrue(len(expand) == 1)
        item = expand[0]
        self.assertTrue(
            names.path_to_str(item.path) ==
            "Products/Sales.PremierProduct/$ref")
        filter = item.options.filter
        self.assertTrue(filter.op_code == comex.Operator.eq)
        p = parser.Parser("ReportsTo($levels=3)")
        expand = p.require_expand()
        self.assertTrue(len(expand) == 1)
        item = expand[0]
        self.assertTrue(item.path == ("ReportsTo", ))
        self.assertTrue(item.options.levels == 3)
        p = parser.Parser("*/$ref,Supplier")
        expand = p.require_expand()
        self.assertTrue(len(expand) == 2)
        item = expand[0]
        self.assertTrue(item.path == ("*", "$ref"))
        item = expand[1]
        self.assertTrue(item.path == ("Supplier", ))
        p = parser.Parser("*($levels=2)")
        expand = p.require_expand()
        self.assertTrue(len(expand) == 1)
        item = expand[0]
        self.assertTrue(item.path == ("*", ))
        self.assertTrue(item.options.levels == 2)

    def test_common_expr(self):
        # primitiveLiteral
        e = parser.Parser("3").require_common_expr()
        self.assertTrue(isinstance(e, comex.Int64Expression))
        self.assertTrue(e.value == 3)
        e = parser.Parser("+3").require_common_expr()
        self.assertTrue(isinstance(e, comex.Int64Expression))
        self.assertTrue(e.value == 3)
        # deceptive forms:
        e = parser.Parser(
            'deadbeef-0000-0000-0000-0000deadbeef').require_common_expr()
        self.assertTrue(isinstance(e, comex.GuidExpression))
        self.assertTrue(
            e.value == uuid.UUID('deadbeef-0000-0000-0000-0000deadbeef'))
        # parameterAlias
        e = parser.Parser("@param").require_common_expr()
        self.assertTrue(isinstance(e, comex.ParameterExpression))
        self.assertTrue(e.name == "param")
        # arrayOrObject
        e = parser.Parser("[]").require_common_expr()
        self.assertTrue(isinstance(e, comex.CollectionExpression))
        e = parser.Parser("{}").require_common_expr()
        self.assertTrue(isinstance(e, comex.RecordExpression))
        # rootExpr
        e = parser.Parser("$root/Products(3)").require_common_expr()
        self.assertTrue(isinstance(e, comex.MemberExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.RootExpression))
        e = e.operands[1]
        self.assertTrue(isinstance(e, comex.CallExpression))
        # firstMemberExpr
        e = parser.Parser("Property").require_common_expr()
        self.assertTrue(isinstance(e, comex.IdentifierExpression))
        self.assertTrue(e.identifier == "Property")
        # functionExpr
        e = parser.Parser("Schema.Function()").require_common_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.QNameExpression))
        # negateExpr
        e = parser.Parser("-Value").require_common_expr()
        self.assertTrue(isinstance(e, comex.NegateExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.IdentifierExpression))
        # methodCallExpr
        e = parser.Parser("now()").require_common_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.IdentifierExpression))
        # parenExpr
        e = parser.Parser("(2 add 2)").require_common_expr()
        self.assertTrue(isinstance(e, comex.AddExpression))
        self.assertTrue(e.bracket_hint is True)
        # castExpr
        e = parser.Parser("cast(Schema.Type)").require_common_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.IdentifierExpression))
        # primitiveLiteral addExpr
        e = parser.Parser("2 add 2").require_common_expr()
        self.assertTrue(isinstance(e, comex.AddExpression))
        self.assertTrue(e.bracket_hint is False)
        # primitiveLiteral subExpr
        e = parser.Parser("2 sub 2").require_common_expr()
        self.assertTrue(isinstance(e, comex.SubExpression))
        # primitiveLiteral mulExpr
        e = parser.Parser("2 mul 2").require_common_expr()
        self.assertTrue(isinstance(e, comex.MulExpression))
        # primitiveLiteral divExpr
        e = parser.Parser("2 div 2").require_common_expr()
        self.assertTrue(isinstance(e, comex.DivExpression))
        # primitiveLiteral modExpr
        e = parser.Parser("2 mod 2").require_common_expr()
        self.assertTrue(isinstance(e, comex.ModExpression))
        for bad in (
                "Products/$unknown",
                'x add "3"',
                ):
            try:
                parser.Parser(bad).require_common_expr()
                self.fail("Parsed %s" % bad)
            except ValueError:
                pass

    def test_root_expr(self):
        # '$root/' entitySetName keyPredicate
        e = parser.Parser("$root/Products(3)").require_root_expr()
        self.assertTrue(isinstance(e, comex.MemberExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.RootExpression))
        self.assertTrue(isinstance(e.operands[1], comex.CallExpression))
        # '$root/' singletonEntity
        e = parser.Parser("$root/BestSeller").require_root_expr()
        self.assertTrue(isinstance(e, comex.MemberExpression))
        self.assertTrue(isinstance(e.operands[0], comex.RootExpression))
        self.assertTrue(isinstance(e.operands[1], comex.IdentifierExpression))
        # '$root/' entitySetName keyPredicate singleNavigationExpr
        e = parser.Parser("$root/Products(3)/Name").require_root_expr()
        self.assertTrue(isinstance(e, comex.MemberExpression))
        self.assertTrue(isinstance(e.operands[0], comex.RootExpression))
        self.assertTrue(isinstance(e.operands[1], comex.MemberExpression))
        rop = e.operands[1]
        self.assertTrue(isinstance(rop.operands[0], comex.CallExpression))
        self.assertTrue(
            isinstance(rop.operands[1], comex.IdentifierExpression))
        # '$root/' singletonEntity singleNavigationExpr
        e = parser.Parser("$root/BestSeller/Name").require_root_expr()
        self.assertTrue(isinstance(e, comex.MemberExpression))
        self.assertTrue(isinstance(e.operands[0], comex.RootExpression))
        self.assertTrue(isinstance(e.operands[1], comex.MemberExpression))
        rop = e.operands[1]
        self.assertTrue(
            isinstance(rop.operands[0], comex.IdentifierExpression))
        self.assertTrue(
            isinstance(rop.operands[1], comex.IdentifierExpression))
        # what is NOT a root expression?
        try:
            parser.Parser("Products").require_root_expr()
            self.fail("Products is not a rootExpr")
        except ValueError:
            pass

    def test_first_member_expr(self):
        # propertyPathExpr
        e = parser.Parser("Products").require_first_member_expr()
        self.assertTrue(isinstance(e, comex.IdentifierExpression))
        self.assertTrue(e.identifier == "Products")
        # inscopeVariableExpr
        e = parser.Parser("$it").require_first_member_expr()
        self.assertTrue(isinstance(e, comex.ItExpression))
        # inscopeVariableExpr "/" memberExpr
        e = parser.Parser("lambda/Products").require_first_member_expr()
        self.assertTrue(isinstance(e, comex.MemberExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.IdentifierExpression))
        self.assertTrue(e.operands[0].identifier == "lambda")
        self.assertTrue(isinstance(e.operands[1], comex.IdentifierExpression))
        self.assertTrue(e.operands[1].identifier == "Products")
        # what is NOT a first member expression?
        try:
            parser.Parser("$root/Products").require_first_member_expr()
            self.fail("$root/Products is not a firstMemberExpr")
        except ValueError:
            pass

    def test_member_expr(self):
        # propertyPathExpr
        e = parser.Parser("Products").require_member_expr()
        self.assertTrue(isinstance(e, comex.IdentifierExpression))
        self.assertTrue(e.identifier == "Products")
        # boundFunctionExpr
        e = parser.Parser(
            "Sales.SalesRegion(City=$it/City)").require_member_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        self.assertTrue(len(e.operands) == 2)
        ename, args = e.operands
        self.assertTrue(
            ename.identifier == names.QualifiedName("Sales", "SalesRegion"))
        self.assertTrue(len(args.operands) == 1)
        bind = args.operands[0]
        self.assertTrue(isinstance(bind, comex.BindExpression))
        self.assertTrue(bind.name == "City")
        # qualifiedEntityTypeName "/" propertyPathExpr : TODO
        e = parser.Parser("Sales.Special/Products(3)").require_member_expr()
        self.assertTrue(isinstance(e, comex.MemberExpression))
        self.assertTrue(len(e.operands) == 2)
        qname = e.operands[0]
        self.assertTrue(isinstance(qname, comex.QNameExpression))
        self.assertTrue(
            qname.identifier == names.QualifiedName("Sales", "Special"))
        prop = e.operands[1]
        self.assertTrue(isinstance(prop, comex.CallExpression))
        # qualifiedEntityTypeName "/" boundFunctionExpr
        e = parser.Parser(
            "Sales.Special/"
            "Sales.SalesRegion(City='Kansas')").require_member_expr()
        self.assertTrue(isinstance(e, comex.MemberExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[1], comex.CallExpression))
        # what is NOT a memberExpr?
        try:
            parser.Parser("$it/Products").require_member_expr()
            self.fail("$it/Products is not a memberExpr")
        except ValueError:
            pass

    def test_property_path_expr(self):
        # entityColNavigationProperty
        # entityNavigationProperty
        # complexColProperty
        # complexProperty
        # primitiveColProperty
        # primitiveProperty
        # streamProperty
        e = parser.Parser("Products").require_property_path_expr()
        self.assertTrue(isinstance(e, comex.IdentifierExpression))
        self.assertTrue(e.identifier == "Products")
        # entityColNavigationProperty collectionNavigationExpr
        e = parser.Parser("Products(3)").require_property_path_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.IdentifierExpression))
        self.assertTrue(e.operands[0].identifier == "Products")
        self.assertTrue(isinstance(e.operands[1], comex.ArgsExpression))
        self.assertTrue(len(e.operands[1].operands) == 1)
        self.assertTrue(
            isinstance(e.operands[1].operands[0], comex.Int64Expression))
        # entityNavigationProperty singleNavigationExpr
        # complexProperty complexPathExpr
        e = parser.Parser("Category/Name").require_property_path_expr()
        self.assertTrue(isinstance(e, comex.MemberExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.IdentifierExpression))
        self.assertTrue(e.operands[0].identifier == "Category")
        self.assertTrue(isinstance(e.operands[1], comex.IdentifierExpression))
        self.assertTrue(e.operands[1].identifier == "Name")
        # complexColProperty collectionPathExpr
        # primitiveColProperty collectionPathExpr
        e = parser.Parser("Addresses/$count").require_property_path_expr()
        self.assertTrue(isinstance(e, comex.MemberExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.IdentifierExpression))
        self.assertTrue(e.operands[0].identifier == "Addresses")
        self.assertTrue(isinstance(e.operands[1], comex.CountExpression))
        # primitiveProperty singlePathExpr
        # streamProperty singlePathExpr
        e = parser.Parser(
            "MaxTemp/schema.Farenheit()").require_property_path_expr()
        self.assertTrue(isinstance(e, comex.MemberExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.IdentifierExpression))
        self.assertTrue(e.operands[0].identifier == "MaxTemp")
        self.assertTrue(isinstance(e.operands[1], comex.CallExpression))
        ename, args = e.operands[1].operands
        self.assertTrue(
            ename.identifier == names.QualifiedName("schema", "Farenheit"))
        self.assertTrue(len(args.operands) == 0)
        # what is NOT a propertyPathExpr?
        try:
            parser.Parser("$it/Products").require_member_expr()
            self.fail("$it/Products is not a memberExpr")
        except ValueError:
            pass

    def test_inscope_variable_expr(self):
        # implicitVariableExpr
        e = parser.Parser("$it").require_inscope_variable_expr()
        self.assertTrue(isinstance(e, comex.ItExpression))
        # lambdaVariableExpr
        e = parser.Parser("x").require_inscope_variable_expr()
        self.assertTrue(isinstance(e, comex.IdentifierExpression))
        self.assertTrue(e.identifier == "x")
        try:
            parser.Parser("$root").require_inscope_variable_expr()
            self.fail("$root is not an inscopeVariableExpr")
        except ValueError:
            pass

    def test_implicit_variable_expr(self):
        e = parser.Parser("$it")
        self.assertTrue(e.implicit_variable_expr == "$it")

    def test_labda_variable_expr(self):
        e = parser.Parser("x").require_lambda_variable_expr()
        self.assertTrue(isinstance(e, comex.IdentifierExpression))
        self.assertTrue(e.identifier == "x")

    def test_collection_navigation_expr(self):
        # there is no require_collection_navigation_expr we prefix these
        # cases with entityColNavigationProperty (an odataIdentifier)
        # and use propertyPathExpr to parse them.
        # keyPredicate
        e = parser.Parser("Products(3)").require_property_path_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        self.assertTrue(isinstance(e.operands[0], comex.IdentifierExpression))
        self.assertTrue(isinstance(e.operands[1], comex.ArgsExpression))
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 1)
        self.assertTrue(isinstance(e.operands[0], comex.Int64Expression))
        # keyPredicate singleNavigationExpr
        e = parser.Parser(
            "Products(3)/Name").require_property_path_expr()
        self.assertTrue(isinstance(e, comex.MemberExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.CallExpression))
        self.assertTrue(isinstance(e.operands[1], comex.IdentifierExpression))
        # collectionPathExpr
        e = parser.Parser("Products/$count").require_property_path_expr()
        self.assertTrue(isinstance(e, comex.MemberExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[1], comex.CountExpression))
        # "/" qualifiedEntityTypeName keyPredicate
        e = parser.Parser(
            "Products/Schema.Type(3)").require_property_path_expr()
        self.assertTrue(isinstance(e, comex.MemberExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.IdentifierExpression))
        self.assertTrue(isinstance(e.operands[1], comex.CallExpression))
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.QNameExpression))
        self.assertTrue(isinstance(e.operands[1], comex.ArgsExpression))
        self.assertTrue(len(e.operands[1].operands) == 1)
        # "/" qualifiedEntityTypeName keyPredicate singleNavigationExpr
        e = parser.Parser(
            "Products/Schema.Type(3)/Name").require_property_path_expr()
        # *right* associativity on paths
        self.assertTrue(isinstance(e, comex.MemberExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.IdentifierExpression))
        self.assertTrue(isinstance(e.operands[1], comex.MemberExpression))
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.CallExpression))
        self.assertTrue(isinstance(e.operands[1], comex.IdentifierExpression))
        e = e.operands[0]
        self.assertTrue(isinstance(e.operands[0], comex.QNameExpression))
        self.assertTrue(isinstance(e.operands[1], comex.ArgsExpression))
        # "/" qualifiedEntityTypeName collectionPathExpr
        e = parser.Parser(
            "Products/Schema.Type/$count").require_property_path_expr()
        self.assertTrue(isinstance(e, comex.MemberExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.IdentifierExpression))
        self.assertTrue(isinstance(e.operands[1], comex.MemberExpression))
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.QNameExpression))
        self.assertTrue(isinstance(e.operands[1], comex.CountExpression))
        try:
            # this must be a keyPredicate, not a function
            parser.Parser(
                "Products/Schema.Type(3)/$count"
                ).require_property_path_expr()
            self.fail("keyPredicate followed by collectionPathExpr")
        except ValueError:
            pass

    def test_single_navigation_expr(self):
        # nothing to do, same as memberExpr, parsed without the leading
        # operator
        e = parser.Parser("Products").require_single_navigation_expr()
        self.assertTrue(isinstance(e, comex.IdentifierExpression))
        self.assertTrue(e.identifier == "Products")

    def test_collection_path_expr(self):
        # count
        e = parser.Parser("$count").require_collection_path_expr()
        self.assertTrue(isinstance(e, comex.CountExpression))
        # "/" boundFunctionExpr
        e = parser.Parser(
            "Schema.Func(a=1,b=2)").require_collection_path_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        self.assertTrue(isinstance(e.operands[0], comex.QNameExpression))
        self.assertTrue(isinstance(e.operands[1], comex.ArgsExpression))
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 2)
        for bind in e.operands:
            self.assertTrue(isinstance(bind, comex.BindExpression))
            self.assertTrue(len(bind.operands) == 1)
            self.assertTrue(len(bind.name) == 1)
            self.assertTrue(
                isinstance(bind.operands[0], comex.Int64Expression))
        # "/" anyExpr
        e = parser.Parser("any()").require_collection_path_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        self.assertTrue(isinstance(e.operands[0], comex.IdentifierExpression))
        self.assertTrue(isinstance(e.operands[1], comex.ArgsExpression))
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 0)
        # "/" allExpr
        e = parser.Parser("all(x:x/Name eq 2)").require_collection_path_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        self.assertTrue(isinstance(e.operands[0], comex.IdentifierExpression))
        self.assertTrue(isinstance(e.operands[1], comex.ArgsExpression))
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.LambdaBindExpression))
        try:
            parser.Parser("Name").require_collection_path_expr()
            self.fail("Name is not collectionPathExpr")
        except ValueError:
            pass

    def test_complex_path_expr(self):
        # nothing to do, same as memberExpr, parsed without the leading
        # operator
        e = parser.Parser("Address").require_complex_path_expr()
        self.assertTrue(isinstance(e, comex.IdentifierExpression))
        self.assertTrue(e.identifier == "Address")

    def test_single_path_expr(self):
        # nothing to do, same as functionExpr, parsed without the
        # leading operator
        e = parser.Parser("Schema.Func(a=1)").require_single_path_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.QNameExpression))
        self.assertTrue(isinstance(e.operands[1], comex.ArgsExpression))
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 1)
        self.assertTrue(isinstance(e.operands[0], comex.BindExpression))

    def test_bound_function_expr(self):
        # nothing to do, same as functionExpr
        e = parser.Parser("Schema.Func(a=1)").require_bound_function_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))

    def test_function_expr(self):
        # namespace "." entityColFunction functionExprParameters
        # namespace "." entityFunction functionExprParameters
        # namespace "." complexColFunction functionExprParameters
        # namespace "." complexFunction functionExprParameters
        # namespace "." primitiveColFunction functionExprParameters
        # namespace "." primitiveFunction functionExprParameters
        # all reduce to...
        # namespace "." odataIdentifier functionExprParameters
        e = parser.Parser("Schema.Func(a=1)").require_function_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.QNameExpression))
        self.assertTrue(isinstance(e.operands[1], comex.ArgsExpression))
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 1)
        # namespace "." entityColFunction functionExprParameters
        #   collectionNavigationExpr
        e = parser.Parser("Schema.Func(a=1)(3)").require_function_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.CallExpression))
        self.assertTrue(isinstance(e.operands[1], comex.ArgsExpression))
        e0 = e.operands[0]
        self.assertTrue(len(e0.operands) == 2)
        self.assertTrue(isinstance(e0.operands[0], comex.QNameExpression))
        self.assertTrue(isinstance(e0.operands[1], comex.ArgsExpression))
        self.assertTrue(
            e0.operands[0].identifier == names.QualifiedName("Schema", "Func"))
        e01 = e0.operands[1]
        self.assertTrue(len(e01.operands) == 1)
        self.assertTrue(isinstance(e01.operands[0], comex.BindExpression))
        e1 = e.operands[1]
        self.assertTrue(len(e1.operands) == 1)
        self.assertTrue(isinstance(e1.operands[0], comex.Int64Expression))
        # namespace "." entityFunction functionExprParameters
        #   singleNavigationExpr
        # namespace "." complexFunction functionExprParameters complexPathExpr
        e = parser.Parser("Schema.Func(a=1)/Name").require_function_expr()
        self.assertTrue(isinstance(e, comex.MemberExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.CallExpression))
        self.assertTrue(isinstance(e.operands[1], comex.IdentifierExpression))
        # namespace "." complexColFunction functionExprParameters
        #   collectionPathExpr
        # namespace "." primitiveColFunction functionExprParameters
        #   collectionPathExpr
        e = parser.Parser("Schema.Func(a=1)/$count").require_function_expr()
        self.assertTrue(isinstance(e, comex.MemberExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.CallExpression))
        self.assertTrue(isinstance(e.operands[1], comex.CountExpression))
        # namespace "." primitiveFunction functionExprParameters singlePathExpr
        e = parser.Parser(
            "Schema.FuncA(a=1)/Schema.FuncB(b=1)").require_function_expr()
        self.assertTrue(isinstance(e, comex.MemberExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.CallExpression))
        self.assertTrue(isinstance(e.operands[1], comex.CallExpression))
        try:
            parser.Parser("now()").require_function_expr()
            self.fail("callme is not functionExpr")
        except ValueError:
            pass

    def test_function_expr_parameters(self):
        # parsed only as part of a function, deeper dive
        # OPEN CLOSE
        e = parser.Parser("Schema.Func()").require_function_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        self.assertTrue(len(e.operands) == 2)
        e = e.operands[1]
        self.assertTrue(isinstance(e, comex.ArgsExpression))
        self.assertTrue(len(e.operands) == 0)
        # OPEN functionExprParameter CLOSE
        e = parser.Parser("Schema.Func(a=1)").require_function_expr()
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 1)
        # OPEN functionExprParameter COMMA functionExprParameter CLOSE
        e = parser.Parser("Schema.Func(a=1,b=2)").require_function_expr()
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 2)
        # OPEN functionExprParameter COMMA functionExprParameter COMMA
        #   functionExprParameter CLOSE
        e = parser.Parser("Schema.Func(a=1,b=2,c=3)").require_function_expr()
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 3)

    def test_function_expr_parameter(self):
        # parsed only as part of a function, deeper dive
        # parameterName EQ parameterAlias
        e = parser.Parser("Schema.Func(a=@a)").require_function_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        self.assertTrue(len(e.operands) == 2)
        e = e.operands[1]
        self.assertTrue(isinstance(e, comex.ArgsExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.BindExpression))
        self.assertTrue(e.name == "a")
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.ParameterExpression))
        self.assertTrue(e.name == "a")
        # parameterName EQ parameterValue
        e = parser.Parser("Schema.Func(a=2 add 2)").require_function_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        e = e.operands[1].operands[0].operands[0]
        self.assertTrue(isinstance(e, comex.AddExpression))

    def test_any_expr(self):
        # 'any' OPEN CLOSE
        e = parser.Parser("any()").require_any_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.IdentifierExpression))
        e = e.operands[1]
        self.assertTrue(isinstance(e, comex.ArgsExpression))
        self.assertTrue(len(e.operands) == 0)
        # 'any' OPEN BWS CLOSE
        e = parser.Parser("any(  )").require_any_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        self.assertTrue(len(e.operands) == 2)
        e = e.operands[1]
        self.assertTrue(isinstance(e, comex.ArgsExpression))
        self.assertTrue(len(e.operands) == 0)
        # 'any' OPEN lambdaVariableExpr COLON lambdaPredicateExpr CLOSE
        e = parser.Parser("any(x:x/Name eq 'Hi')").require_any_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        self.assertTrue(len(e.operands) == 2)
        e = e.operands[1]
        self.assertTrue(isinstance(e, comex.ArgsExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.LambdaBindExpression))
        self.assertTrue(e.name == "x")
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.EqExpression))
        # 'any' OPEN BWS lambdaVariableExpr BWS COLON BWS
        #   lambdaPredicateExpr BWS CLOSE
        e = parser.Parser("any( x  : x/Name eq 'Hi'  )").require_any_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        self.assertTrue(len(e.operands) == 2)
        e = e.operands[1].operands[0].operands[0]
        self.assertTrue(isinstance(e, comex.EqExpression))
        try:
            parser.Parser("some(x:x/Name eq 'Hi')").require_any_expr()
            self.fail("any expression bad name")
        except ValueError:
            pass
        try:
            parser.Parser("any(x=1)").require_any_expr()
            self.fail("any expression bad lambda expression")
        except ValueError:
            pass

    def test_all_expr(self):
        # 'all' OPEN lambdaVariableExpr COLON lambdaPredicateExpr CLOSE
        e = parser.Parser("all(x:x/Name eq 'Hi')").require_all_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        self.assertTrue(len(e.operands) == 2)
        e = e.operands[1]
        self.assertTrue(isinstance(e, comex.ArgsExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.LambdaBindExpression))
        self.assertTrue(e.name == "x")
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.EqExpression))
        # 'all' OPEN BWS lambdaVariableExpr BWS COLON BWS
        #   lambdaPredicateExpr BWS CLOSE
        e = parser.Parser("all( x  : x/Name eq 'Hi'  )").require_all_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        self.assertTrue(len(e.operands) == 2)
        e = e.operands[1].operands[0].operands[0]
        self.assertTrue(isinstance(e, comex.EqExpression))
        try:
            parser.Parser("all()").require_all_expr()
            self.fail("all expression no lambda")
        except ValueError:
            pass
        try:
            parser.Parser("some(x:x/Name eq 'Hi')").require_all_expr()
            self.fail("all expression bad name")
        except ValueError:
            pass
        try:
            parser.Parser("any(x=1)").require_all_expr()
            self.fail("all expression bad lambda expression")
        except ValueError:
            pass

    def test_lambda_predicate_expr(self):
        e = parser.Parser("x/Name eq 'Hi'").require_lambda_predicate_expr()
        self.assertTrue(isinstance(e, comex.EqExpression))
        try:
            parser.Parser("x/Age add 2").require_lambda_predicate_expr()
            self.fail("Lambda expected boolean expression")
        except ValueError:
            pass

    def test_method_call_expr(self):
        # 'now()'
        e = parser.Parser("now()").require_method_call_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.IdentifierExpression))
        self.assertTrue(isinstance(e.operands[1], comex.ArgsExpression))
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 0)
        # 'now(' BWS ')'
        e = parser.Parser("now(  )").require_method_call_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 0)
        # 'round' OPEN commonExpr CLOSE
        e = parser.Parser("round(x add 0.5)").require_method_call_expr()
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.AddExpression))
        # 'round' OPEN BWS commonExpr BWS CLOSE
        e = parser.Parser("round(  x add 0.5 )").require_method_call_expr()
        e = e.operands[1].operands[0]
        self.assertTrue(isinstance(e, comex.AddExpression))
        # 'concat' OPEN commonExpr COMMA commonExpr CLOSE
        e = parser.Parser(
            "concat('<',concat(x,'>'))").require_method_call_expr()
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.StringExpression))
        self.assertTrue(isinstance(e.operands[1], comex.CallExpression))
        # 'concat' OPEN BWS commonExpr BWS COMMA BWS commonExpr BWS CLOSE
        e = parser.Parser(
            "concat(  'Hello ' , 'Mum' )").require_method_call_expr()
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.StringExpression))
        self.assertTrue(isinstance(e.operands[1], comex.StringExpression))
        # 'substring' OPEN commonExpr COMMA commonExpr COMMA commonExpr CLOSE
        e = parser.Parser(
            "substring('Hello Mum',6,3)").require_method_call_expr()
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 3)
        self.assertTrue(isinstance(e.operands[0], comex.StringExpression))
        self.assertTrue(isinstance(e.operands[1], comex.Int64Expression))
        self.assertTrue(isinstance(e.operands[2], comex.Int64Expression))
        # 'substring' OPEN BWS commonExpr BWS COMMA BWS commonExpr BWS
        #   COMMA BWS commonExpr BWS CLOSE
        e = parser.Parser(
            "substring(  'Hello Mum'  , 6 ,  3 )").require_method_call_expr()
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 3)
        self.assertTrue(isinstance(e.operands[0], comex.StringExpression))
        self.assertTrue(isinstance(e.operands[1], comex.Int64Expression))
        self.assertTrue(isinstance(e.operands[2], comex.Int64Expression))
        # 'substring' OPEN commonExpr COMMA commonExpr CLOSE
        e = parser.Parser(
            "substring('Hello Mum',6)").require_method_call_expr()
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.StringExpression))
        self.assertTrue(isinstance(e.operands[1], comex.Int64Expression))
        # 'substring' OPEN BWS commonExpr BWS COMMA BWS commonExpr BWS CLOSE
        e = parser.Parser(
            "substring( 'Hello Mum' , 6 )").require_method_call_expr()
        e = e.operands[1]
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.StringExpression))
        self.assertTrue(isinstance(e.operands[1], comex.Int64Expression))

    def test_method_calls(self):
        for src, op in (
                ("contains(CompanyName,'Alfreds')", comex.Method.contains),
                ("startswith(CompanyName,'Alfr')", comex.Method.startswith),
                ("endswith(CompanyName,'Futterkiste')", comex.Method.endswith),
                ("length(CompanyName)", comex.Method.length),
                ("indexof(CompanyName,'lfreds')", comex.Method.indexof),
                ("substring(CompanyName, 1)", comex.Method.substring),
                ("substring(CompanyName,1,2)", comex.Method.substring),
                ("tolower(CompanyName)", comex.Method.tolower),
                ("toupper(CompanyName)", comex.Method.toupper),
                ("trim(CompanyName)", comex.Method.trim),
                ("concat(concat(City,', '), Country)", comex.Method.concat),
                ("year(BirthDate)", comex.Method.year),
                ("year(BirthDate)", comex.Method.year),
                ("month(BirthDate)", comex.Method.month),
                ("day(BirthDate)", comex.Method.day),
                ("hour(BirthDate)", comex.Method.hour),
                ("minute(BirthDate)", comex.Method.minute),
                ("second(BirthDate)", comex.Method.second),
                ("fractionalseconds(BirthDate)",
                 comex.Method.fractionalseconds),
                ("totalseconds(Property)", comex.Method.totalseconds),
                ("date(Property)", comex.Method.date),
                ("time(Property)", comex.Method.time),
                ("totaloffsetminutes(Property)",
                 comex.Method.totaloffsetminutes),
                ("mindatetime()", comex.Method.mindatetime),
                ("maxdatetime()", comex.Method.maxdatetime),
                ("now()", comex.Method.now),
                ("round(Freight)", comex.Method.round),
                ("floor(Freight)", comex.Method.floor),
                ("ceiling(Freight)", comex.Method.ceiling),
                ("geo.distance(PointA,PointB)", comex.Method.geo_distance),
                ("geo.length(Route)", comex.Method.geo_length),
                ("geo.intersects(RouteA,RoutB)", comex.Method.geo_intersects)
                ):
            e = parser.Parser(src).require_method_call_expr()
            self.assertTrue(isinstance(e, comex.CallExpression))
            self.assertTrue(len(e.operands) == 2)
            self.assertTrue(e.method == op)
        try:
            e = parser.Parser("unknown(Property)").require_method_call_expr()
            self.fail("unknown method")
        except ValueError:
            pass

    def test_paran_expr(self):
        # OPEN commonExpr CLOSE
        e = parser.Parser("(2 add 2)").require_common_expr()
        self.assertTrue(isinstance(e, comex.AddExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(e.bracket_hint is True)
        self.assertTrue(isinstance(e.operands[0], comex.Int64Expression))
        self.assertTrue(isinstance(e.operands[0], comex.Int64Expression))
        # OPEN BWS commonExpr     BWS CLOSE
        e = parser.Parser("( 2 add 2  )").require_common_expr()
        self.assertTrue(isinstance(e, comex.AddExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.Int64Expression))
        self.assertTrue(isinstance(e.operands[0], comex.Int64Expression))

    def test_binary_expr(self):
        for src, cls, op in (
                ("true and false", comex.AndExpression,
                 comex.Operator.bool_and),
                ("true or false", comex.OrExpression,
                 comex.Operator.bool_or),
                ("1 eq 2", comex.EqExpression, comex.Operator.eq),
                ("1 ne 2", comex.NeExpression, comex.Operator.ne),
                ("1 lt 2", comex.LtExpression, comex.Operator.lt),
                ("1 le 2", comex.LeExpression, comex.Operator.le),
                ("1 gt 2", comex.GtExpression, comex.Operator.gt),
                ("1 ge 2", comex.GeExpression, comex.Operator.ge),
                ("Color has Schema.Color'Red'", comex.HasExpression,
                 comex.Operator.has),
                ("1 add 2", comex.AddExpression, comex.Operator.add),
                ("1 sub 2", comex.SubExpression, comex.Operator.sub),
                ("1 mul 2", comex.MulExpression, comex.Operator.mul),
                ("1 div 2", comex.DivExpression, comex.Operator.div),
                ("1 mod 2", comex.ModExpression, comex.Operator.mod),
                ):
            e = parser.Parser(src).require_common_expr()
            self.assertTrue(isinstance(e, cls))
            self.assertTrue(isinstance(e, comex.BinaryExpression))
            self.assertTrue(len(e.operands) == 2)
            self.assertTrue(e.op_code == op)
        p = parser.Parser("true not false")
        e = p.require_common_expr()
        self.assertFalse(isinstance(e, comex.BinaryExpression))
        self.assertTrue(isinstance(e, comex.IdentifierExpression))
        try:
            p.require_end()
            self.fail("Bad binary operator")
        except ValueError:
            pass
        # and now for something completely different
        e = parser.Parser("and and and").require_common_expr()
        self.assertTrue(isinstance(e, comex.AndExpression))
        self.assertTrue(len(e.operands) == 2)
        self.assertTrue(isinstance(e.operands[0], comex.IdentifierExpression))
        self.assertTrue(isinstance(e.operands[1], comex.IdentifierExpression))
        self.assertTrue(e.operands[0].identifier == "and")
        self.assertTrue(e.operands[1].identifier == "and")

    def test_negate_expr(self):
        # "-" commonExpr
        e = parser.Parser("--2").require_common_expr()
        self.assertTrue(isinstance(e, comex.NegateExpression))
        self.assertTrue(isinstance(e, comex.UnaryExpression))
        self.assertTrue(len(e.operands) == 1)
        self.assertTrue(e.op_code == comex.Operator.negate)
        e = e.operands[0]
        # you might be surprised but -2 on its own is a literal rather
        # than a negate unary operator
        self.assertTrue(isinstance(e, comex.Int64Expression))
        self.assertTrue(e.value == -2)
        # "-" BWS commonExpr
        e = parser.Parser("-  2").require_common_expr()
        self.assertTrue(isinstance(e, comex.NegateExpression))
        self.assertTrue(len(e.operands) == 1)
        self.assertTrue(e.op_code == comex.Operator.negate)
        self.assertTrue(isinstance(e.operands[0], comex.Int64Expression))
        # now to the harder cases:
        e = parser.Parser("- - 2").require_common_expr()
        self.assertTrue(isinstance(e, comex.NegateExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.NegateExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.Int64Expression))
        self.assertTrue(e.value == 2)

    def test_not_expr(self):
        # 'not' RWS boolCommonExpr
        e = parser.Parser("not true").require_common_expr()
        self.assertTrue(isinstance(e, comex.NotExpression))
        self.assertTrue(isinstance(e, comex.UnaryExpression))
        self.assertTrue(len(e.operands) == 1)
        self.assertTrue(e.op_code == comex.Operator.bool_not)
        e = parser.Parser("not not true").require_common_expr()
        self.assertTrue(isinstance(e, comex.NotExpression))
        self.assertTrue(len(e.operands) == 1)
        self.assertTrue(e.op_code == comex.Operator.bool_not)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.NotExpression))
        # 'not' on its own isn't a unary operator, must be an identifier
        e = parser.Parser("not").require_common_expr()
        self.assertTrue(isinstance(e, comex.IdentifierExpression))
        self.assertTrue(e.identifier == "not")
        # 'not ' on its own should be treated the same
        e = parser.Parser("(not )").require_common_expr()
        self.assertTrue(isinstance(e, comex.IdentifierExpression))
        self.assertTrue(e.identifier == "not")
        # Here's a thing,do we allow "not not"?
        # Strictly speaking, by the syntax, this is a unary operator
        # 'not ' followed by something that can't be a unary operator
        # (no space) and therefore is parsed as per "not" above.
        e = parser.Parser("not not").require_common_expr()
        self.assertTrue(isinstance(e, comex.NotExpression))
        self.assertTrue(len(e.operands) == 1)
        self.assertTrue(e.op_code == comex.Operator.bool_not)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.IdentifierExpression))
        self.assertTrue(e.identifier == "not")
        # which sort of dictates what we must do here too...
        e = parser.Parser("(not not )").require_common_expr()
        self.assertTrue(isinstance(e, comex.NotExpression))
        self.assertTrue(len(e.operands) == 1)
        self.assertTrue(e.op_code == comex.Operator.bool_not)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.IdentifierExpression))
        self.assertTrue(e.identifier == "not")
        # These corner cases are horrible, but we're consistent with the
        # parsing of "and and and".

    def test_isof_expr(self):
        for name in ('isof', 'cast'):
            # 'isof' OPEN qualifiedTypeName CLOSE
            e = parser.Parser("%s(Schema.Type)" % name).require_common_expr()
            self.assertTrue(isinstance(e, comex.CallExpression))
            self.assertTrue(e.method is None, "%s is not a method" % name)
            self.assertTrue(e.is_type_call())
            self.assertTrue(len(e.operands) == 2)
            e, args = e.operands
            self.assertTrue(isinstance(e, comex.IdentifierExpression))
            self.assertTrue(e.identifier == name)
            self.assertTrue(isinstance(args, comex.ArgsExpression))
            self.assertTrue(args.is_type_args())
            type_arg, expr_arg = args.get_type_args()
            self.assertTrue(isinstance(type_arg, comex.QNameExpression))
            self.assertTrue(
                type_arg.identifier == names.QualifiedName("Schema", "Type"))
            self.assertTrue(expr_arg is None)
            # 'isof' OPEN BWS qualifiedTypeName BWS CLOSE
            e = parser.Parser(
                "%s(  Schema.Type )" % name).require_common_expr()
            self.assertTrue(isinstance(e, comex.CallExpression))
            self.assertTrue(e.is_type_call())
            e, args = e.operands
            self.assertTrue(args.is_type_args())
            type_arg, expr_arg = args.get_type_args()
            self.assertTrue(
                type_arg.identifier == names.QualifiedName("Schema", "Type"))
            self.assertTrue(expr_arg is None)
            # 'isof' OPEN commonExpr COMMA qualifiedTypeName CLOSE
            e = parser.Parser(
                "%s(Property,Schema.Type)" % name).require_common_expr()
            self.assertTrue(e.is_type_call())
            e, args = e.operands
            self.assertTrue(args.is_type_args())
            type_arg, expr_arg = args.get_type_args()
            self.assertTrue(
                type_arg.identifier == names.QualifiedName("Schema", "Type"))
            self.assertTrue(isinstance(expr_arg, comex.IdentifierExpression))
            self.assertTrue(expr_arg.identifier == "Property")
            # 'isof' OPEN BWS commonExpr BWS COMMA BWS qualifiedTypeName
            #   BWS CLOSE
            e = parser.Parser(
                "%s( Property , Schema.Type )" % name).require_common_expr()
            self.assertTrue(e.is_type_call())
            e, args = e.operands
            self.assertTrue(args.is_type_args())
            type_arg, expr_arg = args.get_type_args()
            self.assertTrue(
                type_arg.identifier == names.QualifiedName("Schema", "Type"))
            self.assertTrue(expr_arg.identifier == "Property")
        e = parser.Parser("is(Schema.Type)").require_common_expr()
        self.assertTrue(isinstance(e, comex.CallExpression))
        self.assertTrue(e.method is None, "%s is not a method" % name)
        self.assertFalse(e.is_type_call(), "must be isof or cast")
        e, args = e.operands
        self.assertTrue(args.is_type_args())

    def test_array_or_object(self):
        # complexColInUri
        e = parser.Parser("[{}]").require_array_or_object()
        self.assertTrue(isinstance(e, comex.CollectionExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.RecordExpression))
        # complexInUri
        e = parser.Parser("{}").require_array_or_object()
        self.assertTrue(isinstance(e, comex.RecordExpression))
        self.assertTrue(len(e.operands) == 0)
        # rootExprCol
        e = parser.Parser("[$root/Products(3)]").require_array_or_object()
        self.assertTrue(isinstance(e, comex.CollectionExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.MemberExpression))
        # primitiveColInUri
        e = parser.Parser("[3]").require_array_or_object()
        self.assertTrue(isinstance(e, comex.CollectionExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.Int64Expression))
        try:
            parser.Parser("Products").require_array_or_object()
            self.fail("identifier is not arrayOrObject")
        except ValueError:
            pass

    def test_complex_col_in_uri(self):
        # begin-array end-array
        e = parser.Parser("[]").require_array_or_object()
        self.assertTrue(isinstance(e, comex.CollectionExpression))
        self.assertTrue(len(e.operands) == 0)
        # begin-array complexInUri end-array
        e = parser.Parser('[{"a":null}]').require_array_or_object()
        self.assertTrue(isinstance(e, comex.CollectionExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.RecordExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.MemberBindExpression))
        self.assertTrue(e.name == "a")
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.NullExpression))
        # begin-array complexInUri value-separator complexInUri end-array
        e = parser.Parser('[{"a":null},{"a":1}]').require_array_or_object()
        self.assertTrue(isinstance(e, comex.CollectionExpression))
        self.assertTrue(len(e.operands) == 2)
        e = e.operands[1].operands[0].operands[0]
        self.assertTrue(isinstance(e, comex.Int64Expression))
        self.assertTrue(e.value == 1)
        # begin-array complexInUri value-separator complexInUri
        #   value-separator complexInUri end-array
        e = parser.Parser(
            '[{"a":null},{"a":1}, { "a" : 2 } ]').require_array_or_object()
        self.assertTrue(isinstance(e, comex.CollectionExpression))
        self.assertTrue(len(e.operands) == 3)
        e = e.operands[2].operands[0].operands[0]
        self.assertTrue(isinstance(e, comex.Int64Expression))
        self.assertTrue(e.value == 2)
        # complex collections must not be mixed
        try:
            parser.Parser('[{"a":null},1]').require_array_or_object()
            self.fail("Mixed collection in arrayOrObject")
        except ValueError:
            pass

    def test_complex_in_uri(self):
        # begin-object end-object
        e = parser.Parser(" {  } ").require_complex_in_uri()
        self.assertTrue(isinstance(e, comex.RecordExpression))
        self.assertTrue(len(e.operands) == 0)
        # begin-object annotationInUri end-object
        e = parser.Parser('{"@Schema.Term#q" : 3}').require_complex_in_uri()
        self.assertTrue(isinstance(e, comex.RecordExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.MemberBindExpression))
        self.assertTrue(e.name == names.TermRef(
                            names.QualifiedName("Schema", "Term"), "q"))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.Int64Expression))
        # begin-object primitivePropertyInUri end-object
        e = parser.Parser('{"a": "x"}').require_complex_in_uri()
        self.assertTrue(isinstance(e, comex.RecordExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.MemberBindExpression))
        self.assertTrue(e.name == "a")
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.StringExpression))
        # begin-object complexPropertyInUri end-object
        e = parser.Parser(
            '{"a": {"a0": 3, "a1": 4} }').require_complex_in_uri()
        self.assertTrue(isinstance(e, comex.RecordExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.MemberBindExpression))
        self.assertTrue(e.name == "a")
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.RecordExpression))
        self.assertTrue(len(e.operands) == 2)
        # begin-object collectionPropertyInUri end-object
        e = parser.Parser(
            '{"a": [ 1, 2 ,3 ]}').require_complex_in_uri()
        self.assertTrue(isinstance(e, comex.RecordExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0].operands[0]
        self.assertTrue(isinstance(e, comex.CollectionExpression))
        self.assertTrue(len(e.operands) == 3)
        # begin-object navigationPropertyInUri end-object
        e = parser.Parser(
            '{"a": $root/Products(3)}').require_complex_in_uri()
        self.assertTrue(isinstance(e, comex.RecordExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0].operands[0]
        self.assertTrue(isinstance(e, comex.MemberExpression))
        # begin-object annotationInUri value-separator
        #   primitivePropertyInUri value-separator
        #   complexPropertyInUri value-separator
        #   collectionPropertyInUri value-separator
        #   navigationPropertyInUri value-separator end-object
        # etc...
        e = parser.Parser(
            "{"
            '       "@Schema.Term#q" : 3,'
            '       "a": "x",'
            '       "b": {"a0": 3, "a1": 4},'
            '       "c": [ 1, 2 ,3 ],'
            '       "d": $root/Products(3)'
            "  }").require_complex_in_uri()
        self.assertTrue(isinstance(e, comex.RecordExpression))
        self.assertTrue(len(e.operands) == 5)
        try:
            parser.Parser('{"@Schema.Term": [ $root/Products(3) ]}'
                          ).require_complex_in_uri()
            self.fail("Annotation cannot be rootColExpr")
        except ValueError:
            pass

    def test_collection_property_in_uri(self):
        # quotation-mark primitiveColProperty quotation-mark name-separator
        #   primitiveColInUri
        e = parser.Parser('{"a": ["x", "y", "z"]}').require_complex_in_uri()
        self.assertTrue(isinstance(e, comex.RecordExpression))
        e = e.operands[0].operands[0]
        self.assertTrue(isinstance(e, comex.CollectionExpression))
        self.assertTrue(len(e.operands) == 3)
        for item in e.operands:
            self.assertTrue(isinstance(item, comex.StringExpression))
        # quotation-mark complexColProperty quotation-mark name-separator
        #   complexColInUri
        e = parser.Parser(
            '{"a": [{"a":null},{"a":1},{"a":2}]}').require_complex_in_uri()
        self.assertTrue(isinstance(e, comex.RecordExpression))
        e = e.operands[0].operands[0]
        self.assertTrue(isinstance(e, comex.CollectionExpression))
        self.assertTrue(len(e.operands) == 3)
        for item in e.operands:
            self.assertTrue(isinstance(item, comex.RecordExpression))

    def test_primitive_col_in_uri(self):
        # begin-array end-array
        e = parser.Parser("[]").require_array_or_object()
        self.assertTrue(isinstance(e, comex.CollectionExpression))
        self.assertTrue(len(e.operands) == 0)
        # begin-array primitiveLiteralInJSON end-array
        e = parser.Parser("[1]").require_array_or_object()
        self.assertTrue(isinstance(e, comex.CollectionExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.Int64Expression))
        # begin-array primitiveLiteralInJSON value-separator
        #   primitiveLiteralInJSON end-array
        e = parser.Parser("[ 1 , 2 ]").require_array_or_object()
        self.assertTrue(isinstance(e, comex.CollectionExpression))
        self.assertTrue(len(e.operands) == 2)
        for item in e.operands:
            self.assertTrue(isinstance(item, comex.Int64Expression))
        # begin-array primitiveLiteralInJSON value-separator
        #   primitiveLiteralInJSON value-separator
        #   primitiveLiteralInJSON end-array
        # mixed collections of primitives are OK
        e = parser.Parser('[1,"y",3]').require_array_or_object()
        self.assertTrue(isinstance(e, comex.CollectionExpression))
        self.assertTrue(len(e.operands) == 3)
        self.assertTrue(isinstance(e.operands[1], comex.StringExpression))

    def test_complex_property_in_uri(self):
        # quotation-mark complexProperty quotation-mark name-separator
        #   complexInUri
        e = parser.Parser(
            '{"a": {"a0": 3, "a1": "x"} }').require_complex_in_uri()
        self.assertTrue(isinstance(e, comex.RecordExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.MemberBindExpression))
        self.assertTrue(e.name == "a")
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.RecordExpression))
        self.assertTrue(len(e.operands) == 2)
        e = e.operands[1]
        self.assertTrue(isinstance(e, comex.MemberBindExpression))
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.StringExpression))

    def test_annotation_in_uri(self):
        # quotation-mark AT namespace "." termName quotation-mark
        #   name-separator complexInUri
        e = parser.Parser(
            '{"@Schema.Term#a": {} }').require_complex_in_uri()
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.MemberBindExpression))
        self.assertTrue(isinstance(e.name, names.TermRef))
        self.assertTrue(to_text(e.name) == "@Schema.Term#a")
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.RecordExpression))
        # quotation-mark AT namespace "." termName quotation-mark
        #   name-separator complexColInUri
        e = parser.Parser(
            '{"@Schema.Term#a": [{}] }').require_complex_in_uri()
        e = e.operands[0].operands[0]
        self.assertTrue(isinstance(e, comex.CollectionExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.RecordExpression))
        # quotation-mark AT namespace "." termName quotation-mark
        #   name-separator primitiveLiteralInJSON
        e = parser.Parser(
            '{"@Schema.Term#a": "x" }').require_complex_in_uri()
        e = e.operands[0].operands[0]
        self.assertTrue(isinstance(e, comex.StringExpression))
        # quotation-mark AT namespace "." termName quotation-mark
        #   name-separator primitiveColInUri
        e = parser.Parser(
            '{"@Schema.Term#a": [1,2] }').require_complex_in_uri()
        e = e.operands[0].operands[0]
        self.assertTrue(isinstance(e, comex.CollectionExpression))
        self.assertTrue(len(e.operands) == 2)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.Int64Expression))
        try:
            parser.Parser(
                '{"@Schema.Term#a": $root/Products(3) }'
                ).require_complex_in_uri()
            self.fail("rootExpr in annotationInUri")
        except ValueError:
            pass

    def test_primitive_property_in_uri(self):
        # quotation-mark primitiveProperty quotation-mark name-separator
        #   primitiveLiteralInJSON
        e = parser.Parser('{"a": true}').require_array_or_object()
        self.assertTrue(isinstance(e, comex.RecordExpression))
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.MemberBindExpression))
        self.assertTrue(e.name == "a")
        self.assertTrue(len(e.operands) == 1)
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.BooleanExpression))
        self.assertTrue(e.value is True)

    def test_navigation_property_in_uri(self):
        # singleNavPropInJSON
        e = parser.Parser('{"a": $root/Products(3)}').require_array_or_object()
        e = e.operands[0].operands[0]
        self.assertTrue(isinstance(e, comex.MemberExpression))
        e = e.operands[0]
        self.assertTrue(isinstance(e, comex.RootExpression))
        # collectionNavPropInJSON
        e = parser.Parser(
            '{"a": [$root/Products(3),$root/Products(4)]}'
            ).require_array_or_object()
        e = e.operands[0].operands[0]
        self.assertTrue(isinstance(e, comex.CollectionExpression))
        self.assertTrue(len(e.operands) == 2)
        for item in e.operands:
            self.assertTrue(isinstance(item, comex.MemberExpression))
            self.assertTrue(
                isinstance(item.operands[0], comex.RootExpression))

    def test_single_nav_prop_in_json(self):
        # quotation-mark entityNavigationProperty quotation-mark
        #   name-separator rootExpr
        # nothing more to do: see test_navigation_property_in_uri
        pass

    def test_collection_nav_prop_in_json(self):
        # quotation-mark entityColNavigationProperty quotation-mark
        #   name-separator rootExprCol
        # nothing more to do: see test_navigation_property_in_uri
        pass

    def test_root_expr_col(self):
        # begin-array end-array
        # begin-array rootExpr end-array
        # begin-array rootExpr value-separator rootExpr end-array
        # begin-array rootExpr value-separator rootExpr value-separator
        #   rootExpr end-array
        e = parser.Parser(
            '[$root/Products(3),$root/Products(4),$root/Products(5)]'
            ).require_array_or_object()
        self.assertTrue(isinstance(e, comex.CollectionExpression))
        self.assertTrue(len(e.operands) == 3)
        for item in e.operands:
            self.assertTrue(isinstance(item, comex.MemberExpression))
        # Just try the negative case of a mixed expression
        try:
            parser.Parser(
                '[$root/Products(3),$root/Products(4),[]]'
                ).require_array_or_object()
            self.fail("Mixed rootExpr")
        except ValueError:
            pass
        try:
            parser.Parser(
                '[$root/Products(3),$root/Products(4),Products(5)]'
                ).require_array_or_object()
            self.fail("relative not rootExpr")
        except ValueError:
            pass

    def test_json_syntax(self):
        self.assertTrue(parser.Parser.begin_object == "{")
        self.assertTrue(parser.Parser.end_object == "}")
        self.assertTrue(parser.Parser.begin_array == "[")
        self.assertTrue(parser.Parser.end_array == "]")
        self.assertTrue(parser.Parser.name_separator == ":")
        self.assertTrue(parser.Parser.value_separator == ",")
        self.assertTrue(parser.Parser.escape == "\\")

    def test_primitive_literal_in_json(self):
        # stringInJSON
        cafe = ul("Caf\xe9")
        e = parser.Parser('"%s"' % cafe).require_primitive_literal_in_json()
        self.assertTrue(isinstance(e, comex.StringExpression))
        self.assertTrue(e.value == cafe, e.value)
        # numberInJSON
        e = parser.Parser('-3').require_primitive_literal_in_json()
        self.assertTrue(isinstance(e, comex.Int64Expression))
        self.assertTrue(e.value == -3)
        # 'true'
        e = parser.Parser("true").require_primitive_literal_in_json()
        self.assertTrue(isinstance(e, comex.BooleanExpression))
        self.assertTrue(e.value is True)
        # 'false'
        e = parser.Parser("false").require_primitive_literal_in_json()
        self.assertTrue(isinstance(e, comex.BooleanExpression))
        self.assertTrue(e.value is False)
        # 'null'
        e = parser.Parser("null").require_primitive_literal_in_json()
        self.assertTrue(isinstance(e, comex.NullExpression))
        for bad in ("True", "TRUE", "Null", "NULL", "False", "FALSE"):
            try:
                parser.Parser(bad).require_primitive_literal_in_json()
                self.fail("%s is not primitiveLiteralInJSON" % bad)
            except ValueError:
                pass

    def test_string_in_json(self):
        # quotation-mark quotation-mark
        v = parser.Parser('""').require_string_in_json()
        self.assertTrue(is_text(v))
        self.assertTrue(v == "")
        # quotation-mark charInJSON quotation-mark
        v = parser.Parser('"a"').require_string_in_json()
        self.assertTrue(is_text(v))
        self.assertTrue(v == "a")
        # quotation-mark charInJSON charInJSON quotation-mark
        v = parser.Parser('"abc"').require_string_in_json()
        self.assertTrue(is_text(v))
        self.assertTrue(v == "abc")
        try:
            parser.Parser('"Missing quotation-mark').require_string_in_json()
            self.fail("Unclosed json string")
        except ValueError:
            pass

    def test_char_in_json(self):
        # qchar-unescaped
        unreserved = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ" \
            "0123456789-._~"
        other_delims = "!()*+,;"
        others = ":@/?$'="
        for c in unreserved + other_delims + others:
            self.assertTrue(parser.Parser(c).require_char_in_json() == c)
        # Ignore percent encoded forms: assume these have all been
        # unescpaed before processing the OData syntax; the syntax goes
        # to some length to transform the rules into percent-encoded
        # form by excluding %22 (quotation-mark) and %5C (escape) from
        # the URI-encoded syntax.
        c = ul(b'\xe9')
        self.assertTrue(parser.Parser(c).require_char_in_json() == c)
        c = u8(b'\xe2\x9d\x80')
        self.assertTrue(parser.Parser(c).require_char_in_json() == c)
        # qchar-JSON-special        ; assume unescaped anyway
        special = " :{}[]"
        for c in special:
            self.assertTrue(parser.Parser(c).require_char_in_json() == c)
        # escape quotation-mark
        self.assertTrue(parser.Parser('\\"').require_char_in_json() == '"')
        # escape escape
        self.assertTrue(parser.Parser('\\\\').require_char_in_json() == '\\')
        # escape "/"            ; solidus         U+002F
        self.assertTrue(parser.Parser('\\/').require_char_in_json() == '/')
        # escape 'b'            ; backspace       U+0008
        self.assertTrue(parser.Parser(
            '\\b').require_char_in_json() == u8(b'\x08'))
        # escape 'f'            ; form feed       U+000C
        self.assertTrue(parser.Parser(
            '\\f').require_char_in_json() == u8(b'\x0c'))
        # escape 'n'            ; line feed       U+000A
        self.assertTrue(parser.Parser(
            '\\n').require_char_in_json() == u8(b'\x0a'))
        # escape 'r'            ; carriage return U+000D
        self.assertTrue(parser.Parser(
            '\\r').require_char_in_json() == u8(b'\x0d'))
        # escape 't'            ; tab             U+0009
        self.assertTrue(parser.Parser(
            '\\t').require_char_in_json() == u8(b'\x09'))
        # escape 'u' 4HEXDIG    ;                 U+XXXX
        self.assertTrue(parser.Parser(
            '\\u2740').require_char_in_json() == u8(b'\xe2\x9d\x80'))
        for bad in ('\\u123G', '\\a', '\\', '\\ ', ''):
            try:
                parser.Parser(bad).require_char_in_json()
                self.fail("%r in json" % bad)
            except ValueError:
                pass

    def test_number_in_json(self):
        for src, etype, value in (
                # int
                #   = "0"
                ("0", comex.Int64Expression, 0),
                #   = oneToNine
                ("1", comex.Int64Expression, 1),
                #   = oneToNine DIGIT
                ("10", comex.Int64Expression, 10),
                #   = oneToNine DIGIT DIGIT
                ("101", comex.Int64Expression, 101),
                # "-" int
                ("-3", comex.Int64Expression, -3),
                # int frac
                #   = "." DIGIT
                ("0.5", comex.DecimalExpression, decimal.Decimal('0.5')),
                #   = "." DIGIT DIGIT
                ("0.25", comex.DecimalExpression, decimal.Decimal('0.25')),
                # "-" int frac
                ("-0.5", comex.DecimalExpression, decimal.Decimal('-0.5')),
                # int exp
                #   = "e" DIGIT
                ("1e1", comex.DoubleExpression, decimal.Decimal(10)),
                ("1E1", comex.DoubleExpression, decimal.Decimal(10)),
                #   = "e" DIGIT DIGIT
                ("1e10", comex.DoubleExpression, decimal.Decimal(10000000000)),
                #   = "e" "-" DIGIT
                ("5e-1", comex.DoubleExpression, decimal.Decimal('0.5')),
                #   = "e" "+" DIGIT
                ("5e+1", comex.DoubleExpression, decimal.Decimal(50)),
                # "-" int exp
                ("-5e-1", comex.DoubleExpression, decimal.Decimal('-0.5')),
                # int frac exp
                ("0.5e1", comex.DoubleExpression, decimal.Decimal(5)),
                # "-" int frac exp
                ("-0.5e1", comex.DoubleExpression, decimal.Decimal(-5)),
                ):
            e = parser.Parser(src).require_number_in_json()
            self.assertTrue(isinstance(e, etype))
            self.assertTrue(type(e.value) is type(value))
            self.assertTrue(e.value == value)

    def test_boolean_value(self):
        """booleanValue = "true" / "false" """
        v = parser.Parser("true").require_boolean_value()
        self.assertTrue(v is True)
        v = parser.Parser("false").require_boolean_value()
        self.assertTrue(v is False)
        good = ("True", "TRUE", "False", "FALSE")
        bad = ('1', '0', 'yes', 'no', ' true', 'true ', "'true'", "null", "")
        self.from_str(parser.Parser.require_boolean_value, good, bad)

    def test_guid_value(self):
        """guidValue =  8HEXDIG "-" 4HEXDIG "-" 4HEXDIG "-" 4HEXDIG "-"
                        12HEXDIG"""
        v = parser.Parser(
            "00000000-0000-0000-0000-00000000002A").require_guid_value()
        self.assertTrue(v == uuid.UUID(int=42))
        good = (
            "00000000-0000-0000-0000-00000000002a",
            "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
            "01234567-89AB-CDEF-0123-456789abcdef",
            )
        bad = (
            "0000000000000000000000000000002A",
            "000H3110-0000-0000-0000-00000000002A",
            "0000000-00000-0000-0000-00000000002A",
            "000000-000000-0000-0000-00000000002A",
            " 00000000-0000-0000-0000-00000000002A",
            "00000000-0000-0000-0000-00000000002A ",
            "00000000-0000-0000-0000-00000000002AB",
            "null", "")
        self.from_str(parser.Parser.require_guid_value, good, bad)

    def test_duration_value(self):
        """durationValue = [ sign ] "P" [ 1*DIGIT "D" ]
                [ "T" [ 1*DIGIT "H" ] [ 1*DIGIT "M" ]
                 [ 1*DIGIT [ "." 1*DIGIT ] "S" ] ]"""
        p = parser.Parser("-P3DT1H4M1.5S")
        try:
            v = p.require_duration_value()
            p.require_end()
        except ValueError as err:
            self.fail(str(err))
        self.assertTrue(v.sign == -1)
        self.assertTrue(v.years == 0)
        self.assertTrue(v.months == 0)
        self.assertTrue(v.weeks is None)
        self.assertTrue(v.days == 3)
        self.assertTrue(v.hours == 1)
        self.assertTrue(v.minutes == 4)
        self.assertTrue(v.seconds == 1.5)
        good = (
            "P", "+P", "PT1S", "PT1.1S", "P1D",
            )
        bad = (
            "", "P1H", "1H", "P1D1H", "P1DT1M1H", "1S",
            )
        self.from_str(parser.Parser.require_duration_value, good, bad)

    def test_date_value(self):
        """dateValue = year "-" month "-" day

        year  = [ "-" ] ( "0" 3DIGIT / oneToNine 3*DIGIT )
        month = "0" oneToNine
              / "1" ( "0" / "1" / "2" )
        day   = "0" oneToNine
              / ( "1" / "2" ) DIGIT
              / "3" ( "0" / "1" )"""
        v = parser.Parser("0000-01-01").require_date_value()
        self.assertTrue(v.get_xcalendar_day() == (False, 0, 0, 1, 1))
        v = parser.Parser("-0999-01-01").require_date_value()
        self.assertTrue(v.get_xcalendar_day() == (True, 9, 99, 1, 1))
        good = (
            "-0000-01-01",
            "0999-01-01",
            "11234-01-01",
            )
        bad = (
            "01234-01-01",
            "-01234-01-01",
            "100-01-01",
            "-100-01-01",
            "9999-13-01",
            "9999-12-32",
            "1234-7-04",
            "1234-07-4",
            "1234-007-04",
            "1234-07-004",
            "2017-02-29",
            "2017-03-40",
            "null", "")
        self.from_str(parser.Parser.require_date_value, good, bad)

    def test_date_time_offset_value(self):
        """dateTimeOffsetValue =
            year "-" month "-" day "T" hour ":" minute
            [ ":" second [ "." fractionalSeconds ] ]
            ( "Z" / sign hour ":" minute )

        hour   = ( "0" / "1" ) DIGIT / "2" ( "0" / "1" / "2" / "3" )
        minute = zeroToFiftyNine
        second = zeroToFiftyNine
        fractionalSeconds = 1*12DIGIT"""
        v = parser.Parser(
            "0000-01-01T00:00:00Z").require_date_time_offset_value()
        self.assertTrue(v.get_xcalendar_time_point() ==
                        (False, 0, 0, 1, 1, 0, 0, 0))
        self.assertTrue(v.get_zone() == (0, 0))
        v = parser.Parser(
            "-0752-04-21T16:00:00+01:00").require_date_time_offset_value()
        self.assertTrue(v.get_xcalendar_time_point() ==
                        (True, 7, 52, 4, 21, 16, 0, 0))
        self.assertTrue(v.get_zone() == (1, 60))
        good = (
            "99999999-12-31T23:59:59.999999999999+23:59",
            "0000-01-01T00:00:00.000000000000+00:00",
            "1969-07-20T20:17Z",
            "1969-07-20T20:17+00:00",
            "1969-07-20T20:17:40.0Z",
            "1969-07-20T20:17:40.0Z",
            "1969-07-20T20:12:40.0-05:00",
            )
        bad = (
            "1969-07-20T-01:17Z",
            "1969-07-20T-1:17Z",
            "1969-07-20T60:17Z",
            "1969-07-20T20:-01Z",
            "1969-07-20T20:-1Z",
            "1969-07-20T20:60Z",
            "1969-07-20T20:17:+1Z",
            "1969-07-20T20:17:-1Z",
            "1969-07-20T20:17:-01Z",
            "1969-07-20T20:17:60Z",
            "1969-07-20T20:17:40.0000000000000Z",   # 13 fractional digits
            "1969-07-20T20:17:59.9999999999999Z",   # 13 fractional digits
            "1969-07-20T20:12:40.0+24:00",
            "1969-07-20T20:12:40.0-24:00",
            "1969-07-20T20:12:40.0-05:-1",
            "1969-07-20T20:12:40.0-05:-01",
            "1969-07-20T20:12:40.0-05:+1",
            "1969-07-20T20:12:40.0-05:60",
            "1969-07-20T20:17:40.Z",
            "null", ""
            )
        self.from_str(parser.Parser.require_date_time_offset_value, good, bad)

    def test_time_of_day_value(self):
        """timeOfDayValue = hour ":" minute
                            [ ":" second [ "." fractionalSeconds ] ]"""
        v = parser.Parser("00:00:00").require_time_of_day_value()
        self.assertTrue(v.get_time() == (0, 0, 0))
        self.assertTrue(v.get_zone() == (None, None))
        v = parser.Parser("00:00").require_time_of_day_value()
        self.assertTrue(v.get_time() == (0, 0, 0))
        self.assertTrue(v.get_zone() == (None, None))
        good = (
            "23:59:59.999999999999",
            "00:00:00.000000000000",
            "20:17",
            "20:17",
            "20:17:40.0",
            )
        bad = (
            "-01:17",
            "-1:17",
            "60:17",
            "20:-01",
            "20:-1",
            "20:60",
            "20:17:+1",
            "20:17:-1",
            "20:17:-01",
            "20:17:60",
            "20:17:40.0000000000000",   # 13 fractional digits
            "20:17:59.9999999999999",   # 13 fractional digits
            "20:12:40.0Z"
            "20:12:40.0+00:00"
            "20:17:40.",
            "null", ""
            )
        self.from_str(parser.Parser.require_time_of_day_value, good, bad)

    def test_enum_value(self):
        """enumValue = singleEnumValue *( COMMA singleEnumValue )
        singleEnumValue = enumerationMember / enumMemberValue
        enumMemberValue = int64Value
        enumerationMember   = odataIdentifier"""
        good = (
            ("Rock,Paper,Scissors", ["Rock", "Paper", "Scissors"]),
            ("Rock", ["Rock"]),
            ("1", [1]),
            ("-1", [-1]),   # negatives are OK
            )
        bad = (
            "1.0",      # floats are not
            "Rock+Paper",
            )
        for src, value in good:
            p = parser.Parser(src)
            try:
                v = p.require_enum_value()
            except ValueError as err:
                self.fail("%s raised %s" % (src, str(err)))
            self.assertTrue(v == value, "failed to parse %s" % src)
            p.require_end()
        for src in bad:
            p = parser.Parser(src)
            try:
                v = p.require_enum_value()
                p.require_end()
                self.fail("%s validated for enumValue" % repr(src))
            except ValueError:
                pass

    def test_decimal_value(self):
        """decimalValue = [SIGN] 1*DIGIT ["." 1*DIGIT]"""
        v = parser.Parser("3.14").require_decimal_value()
        self.assertTrue(v == decimal.Decimal('3.14'))
        v = parser.Parser("-02.0").require_decimal_value()
        self.assertTrue(v == decimal.Decimal('-2'))
        good = (
            "+12345678901234567890.12345678901234567890",
            "-12345678901234567890.12345678901234567890",
            "12345678901234567890.12345678901234567890",
            "1",
            "12345678901234567890",
            "0",
            "-1"
            "0002",
            )
        bad = (
            "%2B1.1",
            "%2b1.1",
            " 1",
            "1.",
            "2b",
            "2B",
            "0x09",
            "null", ""
            )
        self.from_str(parser.Parser.require_decimal_value, good, bad)

    def test_double_value(self):
        """doubleValue = decimalValue [ "e" [SIGN] 1*DIGIT ] / nanInfinity
            nanInfinity = 'NaN' / '-INF' / 'INF'
        """
        v = parser.Parser("3.14").require_double_value()
        self.assertTrue(v == 3.14)
        v = parser.Parser("-02.0").require_double_value()
        self.assertTrue(v == -2.0)
        v = parser.Parser("3.14e8").require_double_value()
        self.assertTrue(v == 3.14e8)
        good = (
            "+12345678901234567890.12345678901234567890e+00000000000000000008",
            "-12345678901234567890.12345678901234567890E-00000000000000000008",
            "12345678901234567890.12345678901234567890e00000000000000000008",
            "1",
            "12345678901234567890",
            "0",
            "-1"
            "0002",
            "1e1",
            "1E8",
            "NaN",
            "INF",
            "-INF",
            "1e0"
            )
        bad = (
            "%2B1.1",
            "%2b1.1",
            " 1",
            "1.",
            "2b",
            "2B",
            "0x09",
            "NAN",
            "inf",
            "-inf",
            "1e",
            "1.e1",
            "null", ""
            )
        self.from_str(parser.Parser.require_double_value, good, bad)
        self.from_str(parser.Parser.require_single_value, good, bad)

    def test_sbyte_value(self):
        """decimalValue = [ sign ] 1*3DIGIT"""
        v = parser.Parser("+123").require_sbyte_value()
        self.assertTrue(v == 123)
        v = parser.Parser("-9").require_sbyte_value()
        self.assertTrue(v == -9)
        good = (
            "+127",
            "127",
            "-128",
            "12",
            "1",
            "0",
            "-1",
            "001",
            )
        bad = (
            "128",
            "-129",
            "%2B1",
            "%2b1",
            " 1",
            "1.",
            "2b",
            "2B",
            "0x09",
            "0002",
            "2 ",
            "null", ""
            )
        self.from_str(parser.Parser.require_sbyte_value, good, bad)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(message)s")
    unittest.main()
