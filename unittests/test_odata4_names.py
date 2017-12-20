#! /usr/bin/env python

import logging
import unittest

from pyslet.odata4 import (
    errors,
    names,
    )
from pyslet.py2 import (
    is_text,
    to_text,
    u8,
    ul,
    )


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(TupleTests, 'test'),
        unittest.makeSuite(NameTableTests, 'test'),
        ))


good_simple_identifiers = (
    "Hello",
    ul(b"Caf\xe9"),
    ul(b'\xe9faC'),
    u8(b'\xe3\x80\x87h'),
    "_Hello",
    "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
    "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
    "LongOne_LongOne_"
    )

bad_simple_identifiers = (
    "45", "M'", "M;", "M=", "M\\", "M.N", "M+", "M-", "M*",
    "M/", "M<", "M>", "M=", "M~", "M!", "M@", "M#", "M%",
    "M^", "M&", "M|", "M`", "M?", "M(", "M)", "M[", "M]",
    "M,", "M;", "M*", "M.M", "", None,
    "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
    "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
    "LongOne_LongOne_L")

good_namespaces = (
    "Edm", "Some.Vocabulary.V1", "Hello", ul(b"Caf\xe9"),
    ul(b'\xe9faC'), u8(b'\xe3\x80\x87h'), "_Hello",
    "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
    "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
    "LongOne_LongOne_",
    "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
    "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
    "LongOne_LongOne_."
    "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
    "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
    "LongOne_LongOne_",
    "M.M"
    )

bad_namespaces = (
    "45", "M'", "M;", "M=", "M\\", "M.", "M+", "M-", "M*",
    "M/", "M<", "M>", "M=", "M~", "M!", "M@", "M#", "M%",
    "M^", "M&", "M|", "M`", "M?", "M(", "M)", "M[", "M]",
    "M,", "M;", "M*", "", None,
    "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
    "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
    "LongOne_LongOne_L."
    "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
    "LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_LongOne_"
    "LongOne_LongOne_"
    )


class TupleTests(unittest.TestCase):

    def test_simple_identifier(self):
        for s in good_simple_identifiers:
            try:
                self.assertTrue(names.simple_identifier_from_str(s) == s)
            except ValueError:
                self.fail("Good identifier: %s" % repr(s))
        for s in bad_simple_identifiers:
            try:
                names.simple_identifier_from_str(s)
                self.fail("Bad identifier: %s" % repr(s))
            except ValueError:
                pass

    def test_simple_qname(self):
        qname = names.QualifiedName(
            namespace="Some.Vocabulary.V1", name="Hello")
        self.assertTrue(qname.namespace == "Some.Vocabulary.V1")
        self.assertTrue(qname.name == "Hello")
        self.assertTrue(
            to_text(qname) == "Some.Vocabulary.V1.Hello")
        qname2 = names.QualifiedName.from_str(to_text(qname))
        self.assertTrue(qname == qname2)

    def test_invalid_qname(self):
        # check that NO value checking is performed
        qname = names.QualifiedName(namespace="45", name="*")
        self.assertTrue(to_text(qname) == "45.*")
        try:
            names.QualifiedName.from_str(to_text(qname))
            self.fail("45.* invalid QualifiedName")
        except ValueError:
            pass

    def test_simple_tname(self):
        tname = names.TypeName(
            qname=names.QualifiedName(
                namespace="Some.Vocabulary.V1", name="Hello"),
            collection=False)
        self.assertTrue(to_text(tname.qname) == "Some.Vocabulary.V1.Hello")
        self.assertTrue(tname.collection is False)
        self.assertTrue(
            to_text(tname) == "Some.Vocabulary.V1.Hello")
        tname2 = names.TypeName.from_str(to_text(tname))
        self.assertTrue(tname == tname2)

    def test_collection_tname(self):
        tname = names.TypeName(
            qname=names.QualifiedName(
                namespace="Some.Vocabulary.V1", name="Hello"),
            collection=True)
        self.assertTrue(to_text(tname.qname) == "Some.Vocabulary.V1.Hello")
        self.assertTrue(tname.collection is True)
        self.assertTrue(
            to_text(tname) == "Collection(Some.Vocabulary.V1.Hello)")
        tname2 = names.TypeName.from_str(to_text(tname))
        self.assertTrue(tname == tname2)

    def test_invalid_tname(self):
        for bad in (
                "Collection()",
                "Collection(",
                "Collection(Some.Vocabulary.V1.Hello",
                "Collection(45.Hello)",
                "Collection(Hello)",
                "45.Hello",
                ):
            try:
                names.TypeName.from_str(to_text(bad))
                self.fail("%s invalid TypeName" % bad)
            except ValueError:
                pass

    def test_simple_tref(self):
        tref = names.TermRef(
            name=names.QualifiedName(
                namespace="Some.Vocabulary.V1", name="Hello"),
            qualifier=None)
        self.assertTrue(to_text(tref.name) == "Some.Vocabulary.V1.Hello")
        self.assertTrue(tref.qualifier is None)
        self.assertTrue(
            to_text(tref) == "@Some.Vocabulary.V1.Hello")
        tref2 = names.TermRef.from_str(to_text(tref))
        self.assertTrue(tref == tref2)

    def test_qualified_tref(self):
        tref = names.TermRef(
            name=names.QualifiedName(
                namespace="Some.Vocabulary.V1", name="Hello"),
            qualifier="Bye")
        self.assertTrue(to_text(tref.name) == "Some.Vocabulary.V1.Hello")
        self.assertTrue(tref.qualifier == "Bye")
        self.assertTrue(
            to_text(tref) == "@Some.Vocabulary.V1.Hello#Bye")
        tref2 = names.TermRef.from_str(to_text(tref))
        self.assertTrue(tref == tref2)

    def test_invalid_tref(self):
        for bad in (
                "Some.Vocabulary.V1.Hello",
                "Some.Vocabulary.V1.Hello#Bye",
                "@45.Hello#Bye",
                ):
            try:
                names.TermRef.from_str(to_text(bad))
                self.fail("%s invalid TermRef" % bad)
            except ValueError:
                pass

    def test_path_from_str(self):
        path = names.path_from_str("")
        self.assertTrue(isinstance(path, tuple), "path is tuple")
        self.assertTrue(len(path) == 0, "empty path")
        path = names.path_from_str("Hello")
        self.assertTrue(is_text(path[0]))
        self.assertTrue(path == ('Hello', ), "simple path")
        path = names.path_from_str("Hello/Mum")
        self.assertTrue(is_text(path[1]))
        self.assertTrue(path == ('Hello', 'Mum'))
        path = names.path_from_str("Hello/Schema.Mum")
        self.assertTrue(isinstance(path[1], names.QualifiedName))
        self.assertTrue(path[1] == ('Schema', 'Mum'))
        path = names.path_from_str("Hello/@Schema.Mum#Dad")
        self.assertTrue(isinstance(path[1], names.TermRef))
        self.assertTrue(path[1] == (('Schema', 'Mum'), 'Dad'))

    def test_invalid_path(self):
        for bad in (
                "45/Hello",
                "Hello/45",
                "Hello/Schema.45",
                "Hello/$count/howmany",
                ):
            try:
                names.path_from_str(bad)
                self.fail("%s invalid Path" % bad)
            except ValueError:
                pass

    def test_path_to_str(self):
        for p in (
                "",
                "Hello",
                "Hello/Mum",
                "Hello/Schema.Mum",
                "Schema/Mum",
                "Hello/@Schema.Mum#Dad",
                ):
            path = names.path_from_str(p)
            self.assertTrue(p == names.path_to_str(path), repr(path))

    def test_bad_paths(self):
        # The at (@) character MUST be followed by a QualifiedName
        for src in ("@BadQname", "Bad/45", "Bad/Qualifier/@A.B#45"):
            try:
                names.path_from_str(src)
                self.fail("Bad path: %s" % src)
            except ValueError:
                pass

    def test_apath_from_str(self):
        apath = names.annotation_path_from_str("Hello/@Schema.Mum#Dad")
        self.assertTrue(isinstance(apath[1], names.TermRef))
        self.assertTrue(apath[1] == (('Schema', 'Mum'), 'Dad'))
        apath = names.annotation_path_from_str("Hello/@Schema.Mum")
        self.assertTrue(isinstance(apath[1], names.TermRef))
        self.assertTrue(apath[1] == (('Schema', 'Mum'), None))
        for src in (
                "", "Hello", "Hello/Mum", "@BadQname",
                "Bad/Qualifier/@A.B#", "BadSegment/45/@Schema.Mum#Dad"):
            try:
                apath = names.annotation_path_from_str(src)
                self.fail("Bad path: %s" % src)
            except ValueError:
                pass

    def test_enum_literal(self):
        elit = names.EnumLiteral(
            qname=names.QualifiedName.from_str('org.example.Pattern'),
            value=('Red', ))
        self.assertTrue(elit.qname == ('org.example', 'Pattern'))
        self.assertTrue(elit.value == ('Red', ))
        self.assertTrue(
            to_text(elit) == "org.example.Pattern'Red'", to_text(elit))
        self.assertTrue(
            elit.to_xml_str() == "org.example.Pattern/Red")
        elit = names.EnumLiteral(
            qname=names.QualifiedName.from_str('org.example.Pattern'),
            value=(1, ))
        self.assertTrue(elit.qname == ('org.example', 'Pattern'))
        self.assertTrue(elit.value == (1, ))
        self.assertTrue(
            to_text(elit) == "org.example.Pattern'1'")
        try:
            elit.to_xml_str()
            self.fail("Numeric literal in xml notation")
        except ValueError:
            pass
        elit = names.EnumLiteral(
            qname=names.QualifiedName.from_str('org.example.Pattern'),
            value=('Red', 'Green', 'Blue'))
        self.assertTrue(
            to_text(elit) == "org.example.Pattern'Red,Green,Blue'")
        self.assertTrue(
            elit.to_xml_str() == "org.example.Pattern/Red "
            "org.example.Pattern/Green org.example.Pattern/Blue")
        elit = names.EnumLiteral(
            qname=names.QualifiedName.from_str('org.example.Pattern'),
            value=('Red', 2, 'Blue'))
        self.assertTrue(
            to_text(elit) == "org.example.Pattern'Red,2,Blue'")
        try:
            elit.to_xml_str()
            self.fail("Numeric literal in xml notation")
        except ValueError:
            pass

    def test_enum_literal_from_str(self):
        elit = names.EnumLiteral.from_str("org.example.Pattern'Red'")
        self.assertTrue(isinstance(elit, names.EnumLiteral))
        self.assertTrue(elit.qname == ('org.example', 'Pattern'))
        self.assertTrue(elit.value == ('Red', ))
        elit = names.EnumLiteral.from_str(
            "org.example.Pattern'Red,Green,Blue'")
        self.assertTrue(elit.qname == ('org.example', 'Pattern'))
        self.assertTrue(elit.value == ('Red', 'Green', 'Blue'))
        elit = names.EnumLiteral.from_str(
            "org.example.Pattern'Red,2,Blue'")
        self.assertTrue(elit.qname == ('org.example', 'Pattern'))
        self.assertTrue(elit.value == ('Red', 2, 'Blue'))
        for src in (
                "", "org.example.Pattern", "org.example.Pattern''",
                "org.example.Pattern'Red Green'",
                "org.example.Pattern'Red 2'",
                "org.example.Pattern'Red' org.example.Pattern'Green'"
                ):
            try:
                elit = names.EnumLiteral.from_str(src)
                self.fail("Bad enum xml literal: %s" % src)
            except ValueError:
                pass

    def test_enum_literal_from_xml_str(self):
        elit = names.EnumLiteral.from_xml_str("org.example.Pattern/Red")
        self.assertTrue(isinstance(elit, names.EnumLiteral))
        self.assertTrue(elit.qname == ('org.example', 'Pattern'))
        self.assertTrue(elit.value == ('Red', ))
        elit = names.EnumLiteral.from_xml_str(
            "org.example.Pattern/Red org.example.Pattern/Green "
            "org.example.Pattern/Blue")
        self.assertTrue(elit.qname == ('org.example', 'Pattern'))
        self.assertTrue(elit.value == ('Red', 'Green', 'Blue'))
        for src in (
                "", "org.example.Pattern", "org.example.Pattern/1",
                "org.example.Pattern/Red/Green",
                "org.example.Pattern/Red,org.example.Pattern/Green",
                "org.example.Pattern/Red gro.example.Pattern/Green",
                "org.example.Pattern'Red'",
                "org.example.Pattern'1'"
                ):
            try:
                elit = names.EnumLiteral.from_xml_str(src)
                self.fail("Bad enum xml literal: %s" % src)
            except ValueError:
                pass


class MockSchema(names.NameTable):

    def check_name(self, name):
        pass

    def check_value(self, value):
        pass


class NameTableTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.mock_class = MockSchema
        self.mock_ns = MockSchema()

    def test_namespace(self):
        for s in good_namespaces:
            self.assertTrue(names.QNameTable.is_namespace(s),
                            "%s failed" % repr(s))
        for s in bad_namespaces:
            self.assertFalse(names.QNameTable.is_namespace(s),
                             "%s failed" % repr(s))

    def test_qualified_name(self):
        qname = names.QualifiedName("schema", "name")
        self.assertTrue(len(qname) == 2)
        self.assertTrue(qname[0] == "schema")
        self.assertTrue(qname[1] == "name")
        self.assertTrue(qname.namespace == "schema")
        self.assertTrue(qname.name == "name")
        self.assertTrue(to_text(qname) == "schema.name")
        for ns in good_namespaces:
            for s in good_simple_identifiers:
                # a valid simple identifier is not a valid qualified name!
                self.assertFalse(
                    names.QNameTable.is_qualified_name(s),
                    "%s failed" % repr(s))
                q = "%s.%s" % (ns, s)
                self.assertTrue(
                    names.QNameTable.is_qualified_name(q),
                    "%s failed" % repr(q))
                # if we split this it should get us back to where
                # we started
                qname = names.QualifiedName.from_str(q)
                self.assertTrue(qname.name == s)
                self.assertTrue(qname.namespace == ns)
            for s in bad_simple_identifiers:
                if s is None or names.QNameTable.is_namespace(s):
                    # exclude valid namespaces as a namespace +
                    # namespace = qname
                    continue
                q = "%s.%s" % (ns, s)
                self.assertFalse(
                    names.QNameTable.is_qualified_name(q),
                    "%s failed" % repr(q))
        for ns in bad_namespaces:
            if ns is None:
                continue
            for s in good_simple_identifiers + bad_simple_identifiers:
                if s is None:
                    continue
                q = "%s.%s" % (ns, s)
                self.assertFalse(
                    names.QNameTable.is_qualified_name(q),
                    "%s failed" % repr(q))
        # for completeness
        self.assertFalse(names.QNameTable.is_qualified_name(None), "None fail")
        # a couple of special cases on split_qname
        for q in ("", "A", ".A", "A."):
            try:
                names.QualifiedName.from_str(q)
                self.fail("%s failed" % repr(q))
            except ValueError:
                pass

    def test_named(self):
        n = names.Named()
        self.assertTrue(n.name is None)
        self.assertTrue(n.nametable is None)
        self.assertTrue(n.qname is None)
        self.assertTrue(to_text(n) == "Named")
        self.assertFalse(n.is_owned_by(self.mock_ns))
        self.assertTrue(n.root_nametable() is None)

    def test_abstract(self):
        ns = names.NameTable()
        # abstract class...
        n = names.Named()
        try:
            n.declare(ns, "Hello")
            self.fail("Named.declare in abstract name space")
        except NotImplementedError:
            pass

        def check_name(name):
            if not is_text(name):
                raise ValueError

        # add the name check to this instance
        ns.check_name = check_name
        try:
            n.declare(ns, 3)
            self.fail("Named.declare in abstract name space")
        except NotImplementedError:
            self.fail("check_name passed")
        except ValueError:
            pass
        try:
            n.declare(ns, "3")
            self.fail("Named.declare in abstract name space")
        except NotImplementedError:
            pass

        def check_value(value):
            pass

        ns.check_value = check_value

        n.declare(ns, "3")
        self.assertTrue(n.name == "3")
        self.assertTrue("3" in ns)

    def test_declare(self):
        n = names.Named()
        try:
            n.declare(self.mock_ns, None)
            self.fail("no name declare")
        except ValueError:
            pass
        self.assertTrue(n.name is None)
        self.assertTrue(n.qname is None)
        self.assertTrue(to_text(n) == "Named")
        self.assertFalse(n.is_owned_by(self.mock_ns))
        # blank string is OK
        n.declare(self.mock_ns, "")
        self.assertTrue(n.name == "")
        self.assertTrue(n.qname == "")
        self.assertTrue(to_text(n) == "")
        self.assertTrue(n.is_owned_by(self.mock_ns))
        self.assertTrue(n.root_nametable() is self.mock_ns)
        self.assertTrue(len(self.mock_ns) == 1)
        self.assertTrue("" in self.mock_ns)
        # declare an alias in the same namespace
        n.declare(self.mock_ns, "Hello")
        self.assertTrue(n.name == "", "alias doesn't change name")
        self.assertTrue(n.qname == "", "alias doesn't change qname")
        self.assertTrue(len(self.mock_ns) == 2)
        self.assertTrue("Hello" in self.mock_ns)
        ns2 = self.mock_class()
        # declare an alias in a different namespace
        n.declare(ns2, "HelloAgain")
        self.assertTrue(n.name == "")
        self.assertTrue(n.qname == "")
        self.assertTrue(to_text(n) == "")
        self.assertTrue(n.is_owned_by(self.mock_ns))
        self.assertTrue(n.root_nametable() is self.mock_ns)
        self.assertTrue(len(self.mock_ns) == 2)
        self.assertTrue(len(ns2) == 1)
        self.assertTrue("HelloAgain" in ns2)

    def test_nonempty_declare(self):
        # the mock namespace starts off undeclared
        self.assertTrue(self.mock_ns.nametable is None)
        child_ns = MockSchema()
        self.assertTrue(child_ns.nametable is None)
        # declare this child
        child_ns.declare(self.mock_ns, "Hello")
        # now declare a child within it
        n = names.Named()
        n.declare(child_ns, "Again")
        self.assertTrue(n.name == "Again", "declared name")
        self.assertTrue(n.qname == "Hello.Again", "dot qualified qname")
        # But you can't do this the other way around
        child_ns = MockSchema()
        self.assertTrue(child_ns.nametable is None)
        n = names.Named()
        n.declare(child_ns, "Again")
        self.assertTrue(n.name == "Again", "declared name")
        self.assertTrue(n.qname == "Again", "unqualified qname")
        try:
            child_ns.declare(self.mock_ns, "HelloAgain")
            self.fail("Non-empty Nametable declared")
        except errors.ModelError:
            pass
        self.assertTrue(child_ns.name is None, "undeclared name")
        self.assertTrue(child_ns.qname is None, "undeclared qualified qname")

    def test_set_item(self):
        x = object()
        y = object()
        z = object()
        self.assertTrue(len(self.mock_ns) == 0)
        self.assertFalse(self.mock_ns.closed)
        self.mock_ns["Hello"] = x
        self.assertTrue(self.mock_ns["Hello"] is x)
        try:
            self.mock_ns["Hello"] = y
            self.fail("Name redeclared")
        except errors.DuplicateNameError:
            pass
        try:
            del self.mock_ns["Hello"]
            self.fail("Name undeclared")
        except errors.UndeclarationError:
            pass
        self.mock_ns["Bye"] = y
        self.assertTrue(len(self.mock_ns) == 2)
        self.mock_ns.close()
        self.assertTrue(self.mock_ns.closed)
        try:
            self.mock_ns["Ciao"] = z
            self.fail("Declartion in closed NameTable")
        except errors.NameTableClosed:
            pass

    def test_tell(self):
        class Callback(object):

            def __init__(self):
                self.call_count = 0
                self.last_value = None

            def __call__(self, value):
                self.call_count += 1
                self.last_value = value

        c = Callback()
        self.assertTrue(c.call_count == 0)
        x = object()
        y = object()
        self.mock_ns["Hello"] = x
        self.mock_ns.tell("Hello", c)
        self.assertTrue(c.call_count == 1)
        self.assertTrue(c.last_value is x)
        self.mock_ns.tell("Bye", c)
        self.assertTrue(self.mock_ns.waiting("Bye") is True)
        self.mock_ns.tell("Ciao", c)
        self.assertTrue(self.mock_ns.waiting("Ciao") is True)
        self.assertTrue(c.call_count == 1)
        self.assertTrue(c.last_value is x)
        self.mock_ns["Bye"] = y
        self.assertTrue(c.call_count == 2)
        self.assertTrue(c.last_value is y)
        self.assertTrue(self.mock_ns.waiting("Bye") is False)
        self.mock_ns.close()
        self.assertTrue(c.call_count == 3)
        self.assertTrue(c.last_value is None)
        self.assertTrue(self.mock_ns.waiting("Bye") is False)
        self.assertTrue(self.mock_ns.waiting("Ciao") is False)

    def test_tell_close(self):
        class Callback(object):

            def __init__(self):
                self.call_count = 0

            def __call__(self):
                self.call_count += 1

        c = Callback()
        x = object()
        self.mock_ns.tell_close(c)
        self.mock_ns.tell_close(c)
        self.mock_ns["Ciao"] = x
        self.assertTrue(c.call_count == 0)
        self.mock_ns.close()
        self.assertTrue(c.call_count == 2)
        self.mock_ns.tell_close(c)
        self.assertTrue(c.call_count == 3)

    def test_tell_multiclose(self):
        class Callback(object):

            def __init__(self):
                self.call_count = 0

            def __call__(self):
                self.call_count += 1

        c = Callback()
        ns1 = self.mock_class()
        ns2 = self.mock_class()
        ns3 = self.mock_class()
        names.NameTable.tell_all_closed((ns1, ns2, ns3), c)
        self.assertTrue(c.call_count == 0)
        ns3.close()
        self.assertTrue(c.call_count == 0)
        ns1.close()
        self.assertTrue(c.call_count == 0)
        ns2.close()
        self.assertTrue(c.call_count == 1)

    def test_root(self):
        s1 = self.mock_class()
        self.assertTrue(s1.root_nametable() is None)
        s2 = self.mock_class()
        s2.declare(s1, "s2")
        s3 = self.mock_class()
        s3.declare(s2, "s3")
        self.assertTrue(s3.root_nametable() is s1)
        o1 = names.Named()
        self.assertTrue(o1.root_nametable() is None)
        o1.declare(s3, "o1")
        self.assertTrue(o1.root_nametable() is s1)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(levelname)s %(message)s")
    unittest.main()
