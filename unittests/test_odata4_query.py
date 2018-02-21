#! /usr/bin/env python

import logging
import unittest

from pyslet.odata4 import (
    comex,
    errors,
    names,
    query,
    )
from pyslet.py2 import (
    is_text,
    to_text,
    )


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(SelectPathTests, 'test'),
        unittest.makeSuite(EntityOptionsTests, 'test'),
        unittest.makeSuite(OrderItemTests, 'test'),
        unittest.makeSuite(CollectionOptionsTests, 'test'),
        unittest.makeSuite(SystemQueryTests, 'test'),
        ))


class SelectPathTests(unittest.TestCase):

    def test_constructor(self):
        try:
            sitem = query.SelectItem()
            self.fail("no args")
        except TypeError:
            pass
        try:
            sitem = query.SelectItem(None)
            self.fail("empty path")
        except ValueError:
            pass
        # from path tuple
        sitem = query.SelectItem(("Rating", ))
        self.assertTrue(sitem.wildcard is None)
        self.assertTrue(sitem.path == ("Rating", ))
        sitem = query.SelectItem(("Complex", "Rating"))
        self.assertTrue(sitem.wildcard is None)
        self.assertTrue(sitem.path == ("Complex", "Rating"))
        path = ("Complex", names.QualifiedName.from_str("schema.type"),
                "Rating")
        sitem = query.SelectItem(path)
        self.assertTrue(sitem.wildcard is None)
        self.assertTrue(sitem.path == path)
        path = (names.QualifiedName.from_str("schema.type"), "Complex",
                "Rating")
        sitem = query.SelectItem(path)
        self.assertTrue(sitem.wildcard is None)
        self.assertTrue(sitem.path == path)
        path = (names.QualifiedName.from_str("schema.action"), )
        sitem = query.SelectItem(path)
        self.assertTrue(sitem.wildcard is None)
        self.assertTrue(sitem.path == path)
        # the special path '*' represents a wildcard selecting all
        # declared and dynamic properties
        sitem = query.SelectItem(("*", ))
        self.assertTrue(sitem.wildcard == "*")
        self.assertTrue(sitem.path is None)
        path = ("Rating", "*")
        try:
            sitem = query.SelectItem(path)
            self.fail("non-empty select path with * qualifier")
        except ValueError:
            pass
        path = ("Rating", "$count")
        try:
            sitem = query.SelectItem(path)
            self.fail("select path with $count qualifier")
        except ValueError:
            pass

    def test_str_constructor(self):
        try:
            sitem = query.SelectItem("")
            self.fail("empty path")
        except ValueError:
            pass
        sitem = query.SelectItem("Rating")
        self.assertTrue(sitem.wildcard is None)
        self.assertTrue(sitem.path == ("Rating", ))
        sitem = query.SelectItem("Complex/Rating")
        self.assertTrue(sitem.wildcard is None)
        self.assertTrue(sitem.path == ("Complex", "Rating"))
        path = ("Complex", names.QualifiedName.from_str("schema.type"),
                "Rating")
        sitem = query.SelectItem("Complex/schema.type/Rating")
        self.assertTrue(sitem.wildcard is None)
        self.assertTrue(sitem.path == path)
        path = (names.QualifiedName.from_str("schema.type"), "Complex",
                "Rating")
        sitem = query.SelectItem("schema.type/Complex/Rating")
        self.assertTrue(sitem.wildcard is None)
        self.assertTrue(sitem.path == path)
        path = (names.QualifiedName.from_str("schema.action"), )
        sitem = query.SelectItem("schema.action")
        self.assertTrue(sitem.wildcard is None)
        self.assertTrue(sitem.path == path)
        sitem = query.SelectItem("*")
        self.assertTrue(sitem.wildcard == "*")
        self.assertTrue(sitem.path is None)
        # similarly, the namespace wild card is used to identify all
        # operations from an identified namespace
        sitem = query.SelectItem("DemoService.*")
        self.assertTrue(sitem.wildcard == "DemoService")
        self.assertTrue(sitem.path is None)

    def test_bad_paths(self):
        for pstr in (
                "@schema.term", "Complex/Property/@schema.term",
                "Complex/schema.cast/other.operation/bad",
                "Rating/*", "Rating/$count", "$ref", "*/$ref"):
            path = names.path_from_str(pstr)
            try:
                query.SelectItem(path)
                self.fail("SelectItem from %s" % pstr)
            except ValueError:
                pass
        # now try some that won't convert to paths
        for pstr in (
                ".*", "@schema.term.*"):
            try:
                query.SelectItem(pstr)
                self.fail("SelectItem from %s" % pstr)
            except ValueError:
                pass

    def test_to_str(self):
        for pstr in (
                "Rating", "Complex/Rating", "schema.type/Complex/Rating",
                "schema.action", "*", "DemoService.*"):
            self.assertTrue(to_text(query.SelectItem(pstr)) == pstr)

    def test_match_cast(self):
        qaction = names.QualifiedName.from_str("Schema.Action")
        qrating = names.QualifiedName.from_str("Schema.Rating")
        type_a = names.QualifiedName.from_str("Schema.TypeA")
        type_b = names.QualifiedName.from_str("Schema.TypeB")
        match_exact_tests = [
            (None, "Rating", False),
            (None, "Rating", True),
            (None, "Complex", False),
            (None, "Complex", True),
            (None, qrating, False),
            (None, qaction, False),
            (type_a, "Rating", False),
            (type_a, "Rating", True),
            (type_a, "Complex", False),
            (type_a, "Complex", True),
            (type_a, qrating, False),
            (type_a, qaction, False),
            (type_b, "Rating", False),
            (type_b, "Rating", True),
            (type_b, "Complex", False),
            (type_b, "Complex", True),
            (type_b, qrating, False),
            (type_b, qaction, False),
            ]
        match_complex_tests = [
            (None, "Rating"),
            (None, "Complex"),
            (type_a, "Rating"),
            (type_a, "Complex"),
            (type_b, "Rating"),
            (type_b, "Complex"),
            ]
        rules = {
            # plain
            "Rating":
                ((True, True, False, False, False, False,
                  False, False, False, False, False, False,
                  False, False, False, False, False, False,
                  ),
                 (True, False, False, False, False, False)),
            "Complex/Rating":
                ((False, False, None, None, False, False,
                  False, False, False, False, False, False,
                  False, False, False, False, False, False,
                  ),
                 (False, "Rating", False, False, False, False)),
            "Complex/Schema.TypeA/Rating":
                ((False, False, None, None, False, False,
                  False, False, False, False, False, False,
                  False, False, False, False, False, False,
                  ),
                 (False, "Schema.TypeA/Rating", False, False, False, False)),
            "Schema.Action":
                ((False, False, False, False, False, True,
                  False, False, False, False, False, False,
                  False, False, False, False, False, False,
                  ),
                 (False, False, False, False, False, False)),
            # type cast appended
            "Rating/Schema.TypeA":
                ((None, None, False, False, False, False,
                  False, False, False, False, False, False,
                  False, False, False, False, False, False,
                  ),
                 ("Schema.TypeA", False, False, False, False, False)),
            "Complex/Rating/Schema.TypeA":
                ((False, False, None, None, False, False,
                  False, False, False, False, False, False,
                  False, False, False, False, False, False,
                  ),
                 (False, "Rating/Schema.TypeA", False, False, False, False)),
            "Complex/Schema.TypeB/Rating/Schema.TypeA":
                ((False, False, None, None, False, False,
                  False, False, False, False, False, False,
                  False, False, False, False, False, False,
                  ),
                 (False, "Schema.TypeB/Rating/Schema.TypeA", False, False,
                  False, False)),
            "Schema.Action/Schema.TypeA":
                ((False, False, False, False, False, None,
                  False, False, False, False, False, False,
                  False, False, False, False, False, False,
                  ),
                 (False, False, False, False, False, False)),
            # type cast pre-pended
            "Schema.TypeA/Rating":
                ((False, False, False, False, False, False,
                  True, True, False, False, False, False,
                  False, False, False, False, False, False,
                  ),
                 (False, False, True, False, False, False)),
            "Schema.TypeA/Complex/Rating":
                ((False, False, False, False, False, False,
                  False, False, None, None, False, False,
                  False, False, False, False, False, False,
                  ),
                 (False, False, False, "Rating", False, False)),
            "Schema.TypeA/Complex/Schema.TypeB/Rating":
                ((False, False, False, False, False, False,
                  False, False, None, None, False, False,
                  False, False, False, False, False, False,
                  ),
                 (False, False, False, "Schema.TypeB/Rating", False, False)),
            "Schema.TypeA/Schema.Action":
                ((False, False, False, False, False, False,
                  False, False, False, False, False, True,
                  False, False, False, False, False, False,
                  ),
                 (False, False, False, False, False, False)),
            # type cast pre-pended and appended
            "Schema.TypeA/Rating/Schema.TypeB":
                ((False, False, False, False, False, False,
                  None, None, False, False, False, False,
                  False, False, False, False, False, False,
                  ),
                 (False, False, "Schema.TypeB", False, False, False)),
            "Schema.TypeA/Complex/Rating/Schema.TypeB":
                ((False, False, False, False, False, False,
                  False, False, None, None, False, False,
                  False, False, False, False, False, False,
                  ),
                 (False, False, False, "Rating/Schema.TypeB", False, False)),
            "Schema.TypeA/Complex/Schema.TypeC/Rating/Schema.TypeB":
                ((False, False, False, False, False, False,
                  False, False, None, None, False, False,
                  False, False, False, False, False, False,
                  ),
                 (False, False, False, "Schema.TypeC/Rating/Schema.TypeB",
                  False, False)),
            # bad path: "Schema.TypeA/Schema.Action/Schema.TypeB"
            # wild cards
            "*":
                ((True, False, True, False, False, False,
                  True, False, True, False, False, False,
                  True, False, True, False, False, False,
                  ),
                 (True, True, False, False, False, False)),
            "Schema.*":
                ((False, False, False, False, True, True,
                  False, False, False, False, True, True,
                  False, False, False, False, True, True,
                  ),
                 (False, False, False, False, False, False)),
            "Other.*":
                ((False, False, False, False, False, False,
                  False, False, False, False, False, False,
                  False, False, False, False, False, False,
                  ),
                 (False, False, False, False, False, False)),
            }
        for rule, results in rules.items():
            sitem = query.SelectItem(rule)
            for t, result in zip(match_exact_tests, results[0]):
                msg = "select match: %s with rule %s" % \
                    (to_text(t), to_text(sitem))
                if result is None:
                    try:
                        sitem.match_simple(t[0], t[1], nav=t[2])
                        self.fail(msg)
                    except errors.PathError:
                        pass
                else:
                    m = sitem.match_simple(t[0], t[1], nav=t[2])
                    if result is True:
                        self.assertTrue(m is True, msg)
                    elif result is False:
                        self.assertTrue(m is False, msg)
                    else:
                        self.fail("Unexpected result: %r" % result)
            for t, result in zip(match_complex_tests, results[1]):
                msg = "complex match: %s with rule %s" % \
                    (to_text(t), to_text(sitem))
                if result is None:
                    try:
                        sitem.match_complex(t[0], t[1])
                        self.fail(msg)
                    except errors.PathError:
                        pass
                else:
                    m, cast_or_rule = sitem.match_complex(t[0], t[1])
                    if result is True:
                        # exact match, no trailing path
                        self.assertTrue(m is True, msg)
                        self.assertTrue(cast_or_rule is None, msg)
                    elif result is False:
                        self.assertTrue(m is False, msg)
                        self.assertTrue(cast_or_rule is None, msg)
                    elif is_text(result):
                        # match with select rule
                        self.assertTrue(m is True, msg)
                        self.assertTrue(
                            isinstance(cast_or_rule, query.SelectItem), msg)
                        self.assertTrue(to_text(cast_or_rule) == result, msg)
                    else:
                        self.fail("Unexpected result: %s" % repr(result))
        sitem = query.SelectItem("Schema.Action")
        try:
            sitem.match_simple(None, qaction, nav=True)
            self.fail("operation and nav illegal")
        except ValueError:
            pass
        sitem = query.SelectItem("Schea.TypeA/Schema.Action")
        try:
            sitem.match_simple(type_a, qaction, nav=True)
            self.fail("operation and nav illegal")
        except ValueError:
            pass
        try:
            sitem.match_complex(None, qaction)
            self.fail("qualified complex name")
        except ValueError:
            pass


class ExpandPathTests(unittest.TestCase):

    def test_constructor(self):
        try:
            xitem = query.ExpandItem()
            self.fail("no args")
        except TypeError:
            pass
        try:
            xitem = query.ExpandItem(None)
            self.fail("None path, no wildcard")
        except ValueError:
            pass
        try:
            xitem = query.ExpandItem(())
            self.fail("Empty path, no wildcard")
        except ValueError:
            pass
        # from path tuple
        for path in (
                ("Category", ),
                ("Addresses", "Country"),
                ("Products", "$count"),
                ("Products", "$ref"),
                ("Products", "Sales.PremierProduct", "$ref"),
                ("*", "$ref"),
                ("*", ),
                # these work with the syntax but are they legal?
                ("Sales.Customer", "*"),
                ("Sales.Customer", "*", "$ref"),
                ("Addresses", "*", "$count"),
                ):
            xitem = query.ExpandItem(path)
            self.assertTrue(
                xitem.path == path,
                "ExpandItem(%r) resulted in %r" % (path, xitem.path))

    def test_str_constructor(self):
        for path in (
                "Category",
                "Addresses/Country",
                "Products/$count",
                "Products/$ref",
                "Products/Sales.PremierProduct/$ref",
                "*/$ref",
                "*",
                # these work with the syntax but are they legal?
                "Sales.Customer/*",
                "Sales.Customer/*/$ref",
                "Addresses/*/$count",
                ):
            xitem = query.ExpandItem(path)
            self.assertTrue(isinstance(xitem.path, tuple))
            self.assertTrue(to_text(xitem) == path,
                            "%s => %r" % (path, to_text(xitem)))

    def test_bad_paths(self):
        for pstr in (
                "", "@schema.term", "Addresses/Country/@schema.term",
                "Addresses/schema.cast/other.cast/Country",
                "schema.action", "$ref", "*/$value",
                "Category/$value"):
            path = names.path_from_str(pstr)
            try:
                query.ExpandItem(path)
                self.fail("ExpandItem from %s" % pstr)
            except ValueError:
                pass
        for path in (
                ("*", "$ref", "bad"),
                ("*", "ref"),
                ("*", names.QualifiedName("Schema", "type")),
                ):
            try:
                query.ExpandItem(path)
                self.fail(repr(path))
            except ValueError:
                pass

    def test_match_cast(self):
        type_a = names.QualifiedName.from_str("Schema.TypeA")
        type_b = names.QualifiedName.from_str("Schema.TypeB")
        match_tests = [
            (None, "Products"),
            (None, "Category"),
            (type_a, "Products"),
            (type_a, "Category"),
            (type_b, "Products"),
            (type_b, "Category"),
            ]
        rules = {
            # plain
            "Products":
                (("Products//", "//", "//", "//", "//", "//"),
                 (None, "", "", "", "", "")),
            "Category":
                (("//", "Category//", "//", "//", "//", "//"),
                 ("", None, "", "", "", "")),
            "Category/Owner":
                (("//", None, "//", "//", "//", "//"),
                 ("", "Owner", "", "", "", "")),
            "Products/$count":
                (("Products//$count", "//", "//", "//", "//", "//"),
                 (None, "", "", "", "", "")),
            "Products/$ref":
                (("Products//$ref", "//", "//", "//", "//", "//"),
                 (None, "", "", "", "", "")),
            "Products/Sales.PremierProduct/$ref":
                (("Products/Sales.PremierProduct/$ref", "//", "//", "//",
                  "//", "//"),
                 (None, "", "", "", "", "")),
            "*/$ref":
                (("*//$ref", "*//$ref", "*//$ref", "*//$ref", "*//$ref",
                  "*//$ref"),
                 ("*/$ref", "*/$ref", "*/$ref", "*/$ref", "*/$ref", "*/$ref")),
            "*":
                (("*//", "*//", "*//", "*//", "*//", "*//"),
                 ("*", "*", "*", "*", "*", "*")),
            # these work with the syntax but are they legal?
            "Category/*":
                (("//", None, "//", "//", "//", "//"),
                 ("", "*", "", "", "", "")),
            "Category/*/$ref":
                (("//", None, "//", "//", "//", "//"),
                 ("", "*/$ref", "", "", "", "")),
            "Schema.TypeA/Category":
                (("//", "//", "//", "Category//", "//", "//"),
                 ("", "", "", None, "", "")),
            }
        for rule, results in rules.items():
            xitem = query.ExpandItem(rule)
            for t, result in zip(match_tests, results[0]):
                msg = "expand match: %s with rule %s" % \
                    (to_text(t), to_text(xitem))
                if result is None:
                    try:
                        xitem.match_navigation(t[0], t[1])
                        self.fail(msg)
                    except errors.PathError:
                        pass
                else:
                    m, type_cast, qualifier = xitem.match_navigation(
                        t[0], t[1])
                    rmatch, rcast, rqualifier = result.split('/')
                    self.assertTrue(m == rmatch, msg)
                    if rcast:
                        self.assertTrue(
                            isinstance(type_cast, names.QualifiedName))
                        self.assertTrue(to_text(type_cast) == rcast, msg)
                    else:
                        self.assertTrue(type_cast is None, msg)
                    if rqualifier:
                        self.assertTrue(
                            names.PathQualifier.to_str(qualifier) ==
                            rqualifier, msg)
                    else:
                        self.assertTrue(qualifier is None, msg)
            for t, result in zip(match_tests, results[1]):
                msg = "complex match: %s with rule %s" % \
                    (to_text(t), to_text(xitem))
                if result is None:
                    try:
                        xitem.match_complex(t[0], t[1])
                        self.fail(msg)
                    except errors.PathError:
                        pass
                else:
                    new_xitem = xitem.match_complex(t[0], t[1])
                    if result:
                        self.assertTrue(to_text(new_xitem) == result)
                    else:
                        self.assertTrue(new_xitem is None)


class EntityOptionsTests(unittest.TestCase):

    def test_constructor(self):
        options = query.EntityOptions()
        self.assertTrue(isinstance(options.select, list))
        self.assertTrue(len(options.select) == 0)
        self.assertTrue(isinstance(options.expand, list))
        self.assertTrue(len(options.expand) == 0)

    def test_clone(self):
        options1 = query.EntityOptions()
        options2 = options1.clone()
        self.assertTrue(isinstance(options2.select, list))
        self.assertFalse(options2.select is options1.select)
        self.assertTrue(len(options2.select) == 0)
        self.assertTrue(isinstance(options2.expand, list))
        self.assertFalse(options2.expand is options1.expand)
        self.assertTrue(len(options2.expand) == 0)
        options1 = query.EntityOptions()
        options1.add_select_path("SimpleProperty")
        options1.add_expand_path("NavigationProperty")
        options2 = options1.clone()
        self.assertFalse(options2.select is options1.select)
        self.assertTrue(len(options2.select) == 1)
        self.assertTrue(
            options1.select[0] is options2.select[0], "SelectItem reuse")
        self.assertFalse(options2.expand is options1.expand)
        self.assertTrue(len(options2.expand) == 1)
        self.assertFalse(
            options1.expand[0] is options2.expand[0], "ExpandItem reuse")

    def test_bool(self):
        options = query.EntityOptions()
        self.assertFalse(options)
        options.add_select_path("Property")
        self.assertTrue(options)
        options.add_expand_path("Navigation")
        self.assertTrue(options)
        options = query.EntityOptions()
        self.assertFalse(options)
        options.add_expand_path("Navigation")
        self.assertTrue(options)

    def test_str(self):
        options = query.EntityOptions()
        self.assertTrue(to_text(options) == "")
        options.add_select_path("Property")
        self.assertTrue(to_text(options) == "$select=Property")
        options.add_expand_path("NavigationA")
        self.assertTrue(
            to_text(options) == "$select=Property;$expand=NavigationA")
        suboptions = query.ExpandOptions()
        suboptions.add_select_path("SubProperty")
        options.add_expand_path("NavigationB", suboptions)
        self.assertTrue(
            to_text(options) == "$select=Property;"
            "$expand=NavigationA,NavigationB($select=SubProperty)")

    def test_select_path(self):
        options = query.EntityOptions()
        options.add_select_path("PropertyA")
        self.assertTrue(len(options.select) == 1)
        self.assertTrue(isinstance(options.select[0], query.SelectItem))
        self.assertTrue(to_text(options.select[0]) == "PropertyA")
        options.add_select_path("PropertyB")
        self.assertTrue(len(options.select) == 2)
        self.assertTrue(to_text(options.select[1]) == "PropertyB")
        options.remove_select_path("PropertyA")
        self.assertTrue(to_text(options) == "$select=PropertyB")
        options.remove_select_path("PropertyA")
        self.assertTrue(to_text(options) == "$select=PropertyB")
        options.remove_select_path("PropertyB/Schema.SubType")
        self.assertTrue(to_text(options) == "$select=PropertyB")
        options.add_select_path("PropertyA/Schema.SubType")
        self.assertTrue(
            to_text(options) == "$select=PropertyB,PropertyA/Schema.SubType")
        options.remove_select_path("PropertyA")
        self.assertTrue(
            to_text(options) == "$select=PropertyB,PropertyA/Schema.SubType")
        options.remove_select_path("PropertyA/Schema.OtherSubType")
        self.assertTrue(
            to_text(options) == "$select=PropertyB,PropertyA/Schema.SubType")
        options.remove_select_path("PropertyA/Schema.SubType")
        self.assertTrue(to_text(options) == "$select=PropertyB")
        # multiple matching rules are removed
        item = query.SelectItem("PropertyA")
        options.add_select_item(item)
        try:
            options.add_select_item("PropertyA")
            self.fail("add_select_item takes SelectItem only")
        except TypeError:
            pass
        options.add_select_path("PropertyA")
        self.assertTrue(
            to_text(options) == "$select=PropertyB,PropertyA",
            "ignore duplicates")
        options.remove_select_path("PropertyA")
        self.assertTrue(to_text(options) == "$select=PropertyB")
        options.add_select_path("PropertyA")
        self.assertTrue(to_text(options) == "$select=PropertyB,PropertyA")
        options.clear_select()
        self.assertTrue(len(options.select) == 0)

    def test_selected(self):
        options = query.EntityOptions()
        # implicit select rules
        self.assertTrue(options.selected(None, "PropertyA") is True)
        self.assertTrue(options.selected("Schema.Type", "PropertyA") is True)
        # explicit select rules
        options.add_select_path("PropertyB")
        self.assertTrue(options.selected(None, "PropertyA") is False)
        self.assertTrue(options.selected("Schema.Type", "PropertyA") is False)
        self.assertTrue(options.selected(None, "PropertyB") is True)
        # check cache code by rereading...
        self.assertTrue(options.selected(None, "PropertyA") is False)
        self.assertTrue(options.selected("Schema.Type", "PropertyA") is False)
        self.assertTrue(options.selected(None, "PropertyB") is True)
        # check rules are not cached on change
        options.add_select_path("*")
        self.assertTrue(options.selected(None, "PropertyA") is True)
        self.assertTrue(options.selected("Schema.Type", "PropertyA") is True)
        self.assertTrue(options.selected(None, "PropertyB") is True)
        options.clear_select()
        self.assertTrue(options.selected(None, "PropertyA") is True)
        self.assertTrue(options.selected("Schema.Type", "PropertyA") is True)
        self.assertTrue(options.selected(None, "PropertyB") is True)
        # test required type cast
        options.add_select_path("Schema.Type/PropertyA")
        self.assertTrue(options.selected(None, "PropertyA") is False)
        self.assertTrue(options.selected("Schema.Type", "PropertyA") is True)
        self.assertTrue(options.selected(None, "PropertyB") is False)
        # test
        options.add_select_path("PropertyB")
        self.assertTrue(options.selected(None, "PropertyB") is True)
        self.assertTrue(options.selected("Schema.Type", "PropertyB") is False)
        # complex paths should raise an error if matched
        options.add_select_path("PropertyP/PropertyQ")
        self.assertTrue(options.selected(None, "PropertyB") is True)
        try:
            options.selected(None, "PropertyP")
            self.fail("Complex match")
        except errors.PathError:
            pass

    def test_expand_path(self):
        options = query.EntityOptions()
        options.add_expand_path(("PropertyA", ))
        self.assertTrue(len(options.expand) == 1)
        xitem = options.expand[0]
        self.assertTrue(isinstance(xitem, query.ExpandItem))
        self.assertTrue(to_text(xitem) == "PropertyA")
        self.assertTrue(options.get_expand_item("PropertyA") is xitem)
        options.add_expand_path(("PropertyB", "PropertyB1"))
        xitem = options.expand[1]
        self.assertTrue(to_text(xitem) == "PropertyB/PropertyB1")
        suboptions = query.ExpandOptions()
        suboptions.top = 10
        options.add_expand_path(
            ("PropertyC", names.QualifiedName("Schema", "Subtype"), "$ref"),
            options=suboptions)
        xitem = options.expand[2]
        self.assertTrue(
            to_text(xitem) == "PropertyC/Schema.Subtype/$ref($top=10)",
            to_text(xitem))
        self.assertTrue(options.get_expand_item("PropertyC") is xitem)
        options.add_expand_path("PropertyC/PropertyC1/$count")
        xitem = options.expand[3]
        self.assertTrue(
            to_text(xitem) == "PropertyC/PropertyC1/$count")
        # check replacement, differing qualifiers
        options.add_expand_path("PropertyC/PropertyC1/$ref")
        self.assertTrue(len(options.expand) == 4)
        xitem = options.expand[3]
        self.assertTrue(
            to_text(xitem) == "PropertyC/PropertyC1/$ref")
        options.add_expand_path("PropertyA/Schema.SubtypeA")
        self.assertTrue(len(options.expand) == 4)
        xitem = options.expand[3]
        self.assertTrue(
            to_text(xitem) == "PropertyA/Schema.SubtypeA")
        xitem = options.expand[0]
        self.assertTrue(to_text(xitem) == "PropertyB/PropertyB1")
        options.add_expand_path("PropertyC/Schema.Subtype2")
        self.assertTrue(len(options.expand) == 4)
        self.assertTrue(
            to_text(options) ==
            "$expand=PropertyB/PropertyB1,PropertyC/PropertyC1/$ref,"
            "PropertyA/Schema.SubtypeA,PropertyC/Schema.Subtype2")
        try:
            options.add_expand_item("PropertyE")
            self.fail("expected ExpandItem")
        except TypeError:
            pass
        # check removal
        self.assertTrue(options.get_expand_item("PropertyX") is None)
        options.remove_expand_path("PropertyX")
        self.assertTrue(
            to_text(options) ==
            "$expand=PropertyB/PropertyB1,PropertyC/PropertyC1/$ref,"
            "PropertyA/Schema.SubtypeA,PropertyC/Schema.Subtype2")
        options.remove_expand_path("PropertyB/PropertyB1")
        self.assertTrue(
            to_text(options) ==
            "$expand=PropertyC/PropertyC1/$ref,PropertyA/Schema.SubtypeA,"
            "PropertyC/Schema.Subtype2")
        options.remove_expand_path("PropertyC/PropertyC1")
        self.assertTrue(
            to_text(options) ==
            "$expand=PropertyA/Schema.SubtypeA,PropertyC/Schema.Subtype2")
        options.remove_expand_path("PropertyC")
        self.assertTrue(to_text(options) ==
                        "$expand=PropertyA/Schema.SubtypeA")
        options.clear_expand()
        self.assertTrue(len(options.expand) == 0)

    def test_complex_selected(self):
        options = query.ExpandOptions()
        # implicit select rules
        suboptions = options.complex_selected(None, "PropertyA")
        self.assertTrue(isinstance(suboptions, query.ExpandOptions))
        # degenerate case, options are explicit for complex types!
        self.assertFalse(suboptions._select_default)
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].wildcard == "*")
        self.assertTrue(suboptions.select[0].path is None)
        # check cache
        suboptions_cached = options.complex_selected(
            None, "PropertyA")
        self.assertTrue(suboptions_cached is suboptions, "Cache check")
        suboptions = options.complex_selected(
            "Schema.Type", "PropertyA")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].wildcard == "*")
        self.assertTrue(suboptions.select[0].path is None)
        # explicit select rules, setup auto cache clear check
        suboptions_b = options.complex_selected(None, "PropertyB")
        options.add_select_path("PropertyB")
        suboptions = options.complex_selected(None, "PropertyA")
        self.assertTrue(suboptions is None)
        suboptions = options.complex_selected("Schema.Type", "PropertyA")
        self.assertTrue(suboptions is None)
        suboptions = options.complex_selected(None, "PropertyB")
        self.assertTrue(suboptions is not suboptions_b, "auto cache clear")
        self.assertTrue(len(suboptions.select) == 1, to_text(options))
        self.assertTrue(suboptions.select[0].wildcard == "*")
        self.assertTrue(suboptions.select[0].path is None)
        options.clear_select()
        options.add_select_path("*")
        suboptions = options.complex_selected(None, "PropertyA")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].wildcard == "*")
        self.assertTrue(suboptions.select[0].path is None)
        suboptions = options.complex_selected("Schema.Type", "PropertyA")
        self.assertTrue(suboptions is None)
        # self.assertTrue(len(suboptions.select) == 1)
        # self.assertTrue(suboptions.select[0].wildcard == "*")
        # self.assertTrue(suboptions.select[0].path is None)
        suboptions = options.complex_selected(None, "PropertyB")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].wildcard == "*")
        self.assertTrue(suboptions.select[0].path is None)
        self.assertFalse(suboptions is suboptions_b, "cache clear check")
        options.clear_select()
        options.add_select_path("Schema.Type/PropertyA")
        options.add_select_path("PropertyB")
        suboptions = options.complex_selected(None, "PropertyA")
        self.assertTrue(suboptions is None)
        suboptions = options.complex_selected("Schema.Type", "PropertyA")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].wildcard == "*")
        self.assertTrue(suboptions.select[0].path is None)
        suboptions = options.complex_selected("Schema.Type2", "PropertyA")
        self.assertTrue(suboptions is None)
        suboptions = options.complex_selected("Schema.Type", "PropertyB")
        self.assertTrue(suboptions is None)
        suboptions = options.complex_selected(None, "PropertyB")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].wildcard == "*")
        self.assertTrue(suboptions.select[0].path is None)
        # select individual complex property
        options.add_select_path("PropertyC/PropertyC1")
        suboptions = options.complex_selected(None, "PropertyC")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].path == ("PropertyC1", ))
        # select an operation within a complex property
        options.add_select_path("PropertyD/Schema.Action")
        suboptions = options.complex_selected(None, "PropertyD")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].wildcard is None)
        self.assertTrue(
            suboptions.select[0].path ==
            (names.QualifiedName("Schema", "Action"), ))

    def test_complex_expanded(self):
        options = query.EntityOptions()
        options.add_expand_path("*")
        suboptions = options.complex_selected(None, "PropertyA")
        # PropertyA selected (by default) so will contain expand rule
        self.assertTrue(suboptions._select_default is False)
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].wildcard == "*")
        self.assertTrue(suboptions.select[0].path is None)
        self.assertTrue(len(suboptions.expand) == 1)
        self.assertTrue(to_text(suboptions.expand[0]) == "*")
        options.add_select_path("PropertyB")
        suboptions = options.complex_selected(None, "PropertyA")
        # PropertyA no longer selected but expand rule still propagates
        self.assertTrue(suboptions._select_default is False)
        self.assertTrue(len(suboptions.select) == 0)
        self.assertTrue(len(suboptions.expand) == 1)
        self.assertTrue(to_text(suboptions.expand[0]) == "*")
        suboptions_b = options.complex_selected(None, "PropertyB")
        self.assertTrue(suboptions._select_default is False)
        self.assertTrue(len(suboptions_b.select) == 1)
        self.assertTrue(suboptions_b.select[0].wildcard == "*")
        self.assertTrue(suboptions_b.select[0].path is None)
        self.assertTrue(len(suboptions_b.expand) == 1)
        self.assertTrue(to_text(suboptions_b.expand[0]) == "*")
        options.clear_expand()
        # check negative cache clear
        suboptions = options.complex_selected(None, "PropertyB")
        self.assertTrue(suboptions is not suboptions_b)
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].wildcard == "*")
        self.assertTrue(len(suboptions.expand) == 0)
        options.clear_select()
        options.add_expand_path("PropertyA/NavX")
        options.add_expand_path("Schema.Type1/PropertyA/NavY")
        options.add_expand_path("NavZ")
        suboptions = options.complex_selected(None, "PropertyA")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].wildcard == "*")
        self.assertTrue(len(suboptions.expand) == 1)
        self.assertTrue(suboptions.expand[0].path == ("NavX", ))
        suboptions = options.complex_selected(None, "PropertyB")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].wildcard == "*")
        self.assertTrue(len(suboptions.expand) == 0)
        suboptions = options.complex_selected(
            "Schema.Type1", "PropertyA")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].wildcard == "*")
        self.assertTrue(len(suboptions.expand) == 1)
        self.assertTrue(suboptions.expand[0].path == ("NavY", ))
        suboptions = options.complex_selected("Schema.Type2", "PropertyA")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].wildcard == "*")
        self.assertTrue(len(suboptions.expand) == 0)
        try:
            suboptions = options.complex_selected(None, "NavZ")
            self.fail("Complex path matches expand rule")
        except errors.PathError:
            pass

    def test_expanded(self):
        options = query.EntityOptions()
        # implicit expand rules
        xitem, type_cast, qualifier = options.expanded(None, "PropertyA")
        self.assertTrue(xitem is None)
        self.assertTrue(type_cast is None)
        self.assertTrue(qualifier is None)
        xitem, type_cast, qualifier = options.expanded(
            "Schema.Type", "PropertyA")
        self.assertTrue(xitem is None)
        self.assertTrue(type_cast is None)
        self.assertTrue(qualifier is None)
        # explicit expand rules
        options.add_expand_path("PropertyA")
        xitem, type_cast, qualifier = options.expanded(None, "PropertyA")
        self.assertTrue(isinstance(xitem, query.ExpandItem))
        self.assertTrue(to_text(xitem) == "PropertyA")
        self.assertTrue(type_cast is None)
        self.assertTrue(qualifier is None)
        xitem, type_cast, qualifier = options.expanded(
            "Schema.Type", "PropertyA")
        self.assertTrue(xitem is None)
        self.assertTrue(type_cast is None)
        self.assertTrue(qualifier is None)
        # check cache code by rereading...
        xitem1, type_cast, qualifier = options.expanded(None, "PropertyA")
        xitem2, type_cast, qualifier = options.expanded(None, "PropertyA")
        xitem3, type_cast, qualifier = options.expanded(None, "PropertyB")
        xitem4, type_cast, qualifier = options.expanded(None, "PropertyB")
        self.assertTrue(xitem1 is xitem2)
        self.assertTrue(xitem3 is None)
        self.assertTrue(xitem4 is None)
        # check rules are not cached on change
        options.add_expand_path("*")    # now PropertyA,*
        xitem, type_cast, qualifier = options.expanded(None, "PropertyB")
        self.assertTrue(to_text(xitem) == "*")
        # Test a cast
        options.add_expand_path("PropertyA/Schema.SubType")
        xitem, type_cast, qualifier = options.expanded(None, "PropertyA")
        self.assertTrue(isinstance(xitem, query.ExpandItem))
        self.assertTrue(to_text(xitem) == "PropertyA/Schema.SubType")
        self.assertTrue(isinstance(type_cast, names.QualifiedName))
        self.assertTrue(type_cast == names.QualifiedName("Schema", "SubType"))
        self.assertTrue(qualifier is None)
        # Test a qualifier
        options.add_expand_path("PropertyA/$count")
        xitem, type_cast, qualifier = options.expanded(None, "PropertyA")
        self.assertTrue(isinstance(xitem, query.ExpandItem))
        self.assertTrue(to_text(xitem) == "PropertyA/$count")
        self.assertTrue(type_cast is None)
        self.assertTrue(qualifier == names.PathQualifier.count)
        options.add_expand_path("PropertyA/Schema.SubType/$ref")
        xitem, type_cast, qualifier = options.expanded(None, "PropertyA")
        self.assertTrue(isinstance(xitem, query.ExpandItem))
        self.assertTrue(to_text(xitem) == "PropertyA/Schema.SubType/$ref")
        self.assertTrue(isinstance(type_cast, names.QualifiedName))
        self.assertTrue(type_cast == names.QualifiedName("Schema", "SubType"))
        self.assertTrue(qualifier == names.PathQualifier.ref)
        # test required type cast
        options.clear_expand()
        options.add_expand_path("Schema.Type/PropertyA")
        xitem, type_cast, qualifier = options.expanded(None, "PropertyA")
        self.assertTrue(xitem is None)
        xitem, type_cast, qualifier = options.expanded(
            "Schema.Type", "PropertyA")
        self.assertTrue(to_text(xitem) == "Schema.Type/PropertyA")
        # complex paths should raise an error if matched
        options.add_expand_path("PropertyP/PropertyQ")
        try:
            options.expanded(None, "PropertyP")
            self.fail("Complex match")
        except errors.PathError:
            pass


class OrderItemTests(unittest.TestCase):

    def test_constructor(self):
        try:
            oitem = query.OrderbyItem()
            self.fail("no args")
        except TypeError:
            pass
        try:
            oitem = query.OrderbyItem(None)
            self.fail("empty expression")
        except TypeError:
            pass
        # from an expression
        expr = comex.Int64Expression(1)
        oitem = query.OrderbyItem(expr)
        self.assertTrue(oitem.expr is expr)
        self.assertTrue(oitem.direction == 1)
        oitem = query.OrderbyItem(expr, -1)
        self.assertTrue(oitem.expr is expr)
        self.assertTrue(oitem.direction == -1)
        try:
            oitem = query.OrderbyItem(expr, 0)
            self.fail("no direction")
        except ValueError:
            pass


class CollectionOptionsTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.filter = comex.EqExpression()
        self.filter.add_operand(comex.IdentifierExpression("SimpleProperty"))
        self.filter.add_operand(comex.Int64Expression(1))
        self.search = comex.WordExpression("HolyGrail")
        self.orderby = [
            query.OrderbyItem(comex.IdentifierExpression("PropertyA"), -1),
            query.OrderbyItem(comex.IdentifierExpression("PropertyB"))]

    def test_constructor(self):
        options = query.CollectionOptions()
        self.assertTrue(isinstance(options, query.EntityOptions))
        self.assertTrue(len(options.select) == 0)
        self.assertTrue(len(options.expand) == 0)
        self.assertTrue(options.skip is None)
        self.assertTrue(options.top is None)
        self.assertTrue(options.count is None)
        self.assertTrue(options.filter is None)
        self.assertTrue(options.search is None)
        self.assertTrue(isinstance(options.orderby, tuple))
        self.assertTrue(len(options.orderby) == 0)

    def test_clone(self):
        options1 = query.CollectionOptions()
        options2 = options1.clone()
        self.assertTrue(len(options2.select) == 0)
        self.assertTrue(len(options2.expand) == 0)
        self.assertTrue(options2.skip is None)
        self.assertTrue(options2.top is None)
        self.assertTrue(options2.count is None)
        self.assertTrue(options2.filter is None)
        self.assertTrue(options2.search is None)
        self.assertTrue(options2.orderby is options1.orderby, "orderby reuse")
        options1 = query.CollectionOptions()
        options1.add_select_path("SimpleProperty")
        options1.add_expand_path("NavigationProperty")
        options1.set_skip(10)
        options1.set_top(5)
        options1.set_count(True)
        options1.set_filter(self.filter)
        options1.set_search(self.search)
        options1.set_orderby(self.orderby)
        options2 = options1.clone()
        self.assertTrue(len(options2.select) == 1)
        self.assertTrue(len(options2.expand) == 1)
        self.assertTrue(options2.skip == 10)
        self.assertTrue(options2.top == 5)
        self.assertTrue(options2.count is True)
        self.assertTrue(options2.filter is options1.filter, "filter reuse")
        self.assertTrue(options2.search is options1.search, "search reuse")
        self.assertTrue(options2.orderby is options1.orderby, "orderby reuse")

    def test_bool(self):
        options = query.CollectionOptions()
        self.assertFalse(options)
        options.add_select_path("Property")
        self.assertTrue(options)
        options = query.CollectionOptions()
        options.add_expand_path("Navigation")
        self.assertTrue(options)
        options = query.CollectionOptions()
        options.set_skip(10)
        self.assertTrue(options)
        options = query.CollectionOptions()
        options.set_top(5)
        self.assertTrue(options)
        options = query.CollectionOptions()
        options.set_count(False)
        self.assertFalse(options)
        options.set_count(True)
        self.assertTrue(options)
        options = query.CollectionOptions()
        options.set_filter(self.filter)
        self.assertTrue(options)
        options = query.CollectionOptions()
        options.set_search(self.search)
        self.assertTrue(options)
        options = query.CollectionOptions()
        options.set_orderby(self.orderby)
        self.assertTrue(options)

    def test_str(self):
        options = query.CollectionOptions()
        self.assertTrue(to_text(options) == "")
        options.add_select_path("SimpleProperty")
        options.add_expand_path("NavigationProperty")
        options.set_skip(10)
        options.set_top(5)
        options.set_count(True)
        options.set_filter(self.filter)
        options.set_search(self.search)
        options.set_orderby(self.orderby)
        self.assertTrue(
            to_text(options) == "$skip=10;$top=5;$count=true;"
            "$filter=SimpleProperty eq 1;$search=HolyGrail;"
            "$orderby=PropertyA desc,PropertyB;"
            "$select=SimpleProperty;$expand=NavigationProperty",
            to_text(options))

    def test_skip(self):
        options = query.CollectionOptions()
        self.assertTrue(options.skip is None)
        options.set_skip(10)
        self.assertTrue(options.skip == 10)
        options.set_skip(0)
        self.assertTrue(options.skip == 0)
        options.set_skip(None)
        self.assertTrue(options.skip is None)
        try:
            options.set_skip(-1)
            self.fail("negative skip")
        except ValueError:
            pass
        try:
            options.set_skip("100")
            self.fail("string skip")
        except TypeError:
            pass

    def test_top(self):
        options = query.CollectionOptions()
        self.assertTrue(options.top is None)
        options.set_top(10)
        self.assertTrue(options.top == 10)
        options.set_top(0)
        self.assertTrue(options.top == 0)
        options.set_top(None)
        self.assertTrue(options.top is None)
        try:
            options.set_top(-1)
            self.fail("negative top")
        except ValueError:
            pass
        try:
            options.set_top("100")
            self.fail("string top")
        except TypeError:
            pass

    def test_count(self):
        options = query.CollectionOptions()
        self.assertTrue(options.count is None)
        options.set_count(True)
        self.assertTrue(options.count is True)
        options.set_count(False)
        self.assertTrue(options.count is False)
        options.set_count(None)
        self.assertTrue(options.count is None)
        options.set_count(100)
        self.assertTrue(options.count is True)
        options.set_count(0)
        self.assertTrue(options.count is False)

    def test_filter(self):
        options = query.CollectionOptions()
        self.assertTrue(options.filter is None)
        options.set_filter(self.filter)
        self.assertTrue(options.filter is self.filter)
        options.set_filter(None)
        self.assertTrue(options.filter is None)
        # must be a common expression
        try:
            options.set_filter("x eq 1")
            self.fail("string filter")
        except TypeError:
            pass

    def test_search(self):
        options = query.CollectionOptions()
        self.assertTrue(options.search is None)
        options.set_search(self.search)
        self.assertTrue(options.search is self.search)
        options.set_search(None)
        self.assertTrue(options.search is None)
        # must be a common expression
        try:
            options.set_search("dog AND cat")
            self.fail("string search")
        except TypeError:
            pass

    def test_orderby(self):
        options = query.CollectionOptions()
        self.assertTrue(isinstance(options.orderby, tuple))
        self.assertTrue(len(options.orderby) == 0)
        options.set_orderby([])
        self.assertTrue(isinstance(options.orderby, tuple))
        self.assertTrue(len(options.orderby) == 0)
        options.set_orderby(self.orderby)
        self.assertTrue(isinstance(options.orderby, tuple))
        self.assertTrue(len(options.orderby) == 2)
        for a, b in zip(options.orderby, self.orderby):
            self.assertTrue(a is b)
        options.set_orderby(None)
        self.assertTrue(isinstance(options.orderby, tuple))
        self.assertTrue(len(options.orderby) == 0)
        # must be common expressions
        try:
            options.set_orderby(["x desc", "y asc"])
            self.fail("string in orderby")
        except TypeError:
            pass


class ExpandOptionsTests(unittest.TestCase):

    def test_constructor(self):
        options = query.ExpandOptions()
        self.assertTrue(isinstance(options, query.CollectionOptions))
        self.assertTrue(len(options.select) == 0)
        self.assertTrue(options.top is None)
        self.assertTrue(options.levels is None)

    def test_clone(self):
        options1 = query.ExpandOptions()
        options2 = options1.clone()
        self.assertTrue(options2.levels is None)
        options1 = query.ExpandOptions()
        options1.add_select_path("SimpleProperty")
        options1.set_top(5)
        options1.set_levels(3)
        options2 = options1.clone()
        self.assertTrue(len(options2.select) == 1)
        self.assertTrue(options2.top == 5)
        self.assertTrue(options2.levels == 3)

    def test_bool(self):
        options = query.ExpandOptions()
        self.assertFalse(options)
        options.add_select_path("Property")
        self.assertTrue(options)
        options = query.ExpandOptions()
        options.set_top(5)
        self.assertTrue(options)
        options = query.ExpandOptions()
        options.set_levels(3)
        self.assertTrue(options)

    def test_str(self):
        options = query.ExpandOptions()
        self.assertTrue(to_text(options) == "")
        options.add_select_path("SimpleProperty")
        options.add_expand_path("NavigationProperty")
        options.set_skip(10)
        options.set_top(5)
        options.set_count(True)
        options.set_levels(3)
        self.assertTrue(
            to_text(options) == "$skip=10;$top=5;$count=true;"
            "$select=SimpleProperty;$expand=NavigationProperty;$levels=3",
            to_text(options))
        options.set_levels(-1)
        self.assertTrue(
            to_text(options) == "$skip=10;$top=5;$count=true;"
            "$select=SimpleProperty;$expand=NavigationProperty;$levels=max",
            to_text(options))

    def test_levels(self):
        options = query.ExpandOptions()
        self.assertTrue(options.levels is None)
        options.set_levels(3)
        self.assertTrue(options.levels == 3)
        options.set_levels(0)
        self.assertTrue(options.levels == 0)
        options.set_levels(-1)
        self.assertTrue(options.levels == -1)
        options.set_levels(-2)
        self.assertTrue(options.levels == -1)
        options.set_levels(None)
        self.assertTrue(options.levels is None)
        try:
            options.set_levels("100")
            self.fail("string levels")
        except TypeError:
            pass


class SystemQueryTests(unittest.TestCase):

    def test_entity_options(self):
        options = query.ExpandOptions()
        self.assertTrue(isinstance(options.select, list))
        self.assertTrue(len(options.select) == 0)
        self.assertTrue(isinstance(options.expand, list))
        self.assertTrue(len(options.expand) == 0)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(levelname)s %(message)s")
    unittest.main()
