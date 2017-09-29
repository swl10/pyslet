#! /usr/bin/env python

import collections
import logging
import unittest

from pyslet.odata4 import errors
from pyslet.odata4 import model as odata
from pyslet.odata4 import primitive
from pyslet.odata4 import types
from pyslet.py2 import (
    is_text,
    to_text,
    u8,
    ul,
    )


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(QualifiedNameTests, 'test'),
        unittest.makeSuite(NameTableTests, 'test'),
        unittest.makeSuite(AnnotationTests, 'test'),
        unittest.makeSuite(NominalTypeTests, 'test'),
        unittest.makeSuite(ValueTests, 'test'),
        unittest.makeSuite(SystemQueryTests, 'test'),
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


class QualifiedNameTests(unittest.TestCase):

    def test_simple(self):
        qname = types.QualifiedName(
            namespace="Some.Vocabulary.V1", name="Hello")
        self.assertTrue(qname.namespace == "Some.Vocabulary.V1")
        self.assertTrue(qname.name == "Hello")
        self.assertTrue(
            to_text(qname) == "Some.Vocabulary.V1.Hello")

    def test_invalid(self):
        # check that NO value checking is performed
        qname = types.QualifiedName(namespace="45", name="*")
        self.assertTrue(to_text(qname) == "45.*")


class NameTableTests(unittest.TestCase):

    def setUp(self):        # noqa

        class MockSchema(types.NameTable):

            def check_name(self, name):
                pass

            def check_value(self, value):
                pass

        self.mock_class = MockSchema
        self.mock_ns = MockSchema()

    def test_simple_identifier(self):
        for s in good_simple_identifiers:
            self.assertTrue(types.NameTable.is_simple_identifier(s),
                            "%s failed" % repr(s))
        for s in bad_simple_identifiers:
            self.assertFalse(types.NameTable.is_simple_identifier(s),
                             "%s failed" % repr(s))

    def test_namespace(self):
        for s in good_namespaces:
            self.assertTrue(types.NameTable.is_namespace(s),
                            "%s failed" % repr(s))
        for s in bad_namespaces:
            self.assertFalse(types.NameTable.is_namespace(s),
                             "%s failed" % repr(s))

    def test_qualified_name(self):
        qname = types.QualifiedName("schema", "name")
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
                    types.NameTable.is_qualified_name(s),
                    "%s failed" % repr(s))
                q = "%s.%s" % (ns, s)
                self.assertTrue(
                    types.NameTable.is_qualified_name(q),
                    "%s failed" % repr(q))
                # if we split this it should get us back to where
                # we started
                qname = types.NameTable.split_qname(q)
                self.assertTrue(qname.name == s)
                self.assertTrue(qname.namespace == ns)
            for s in bad_simple_identifiers:
                if s is None or types.NameTable.is_namespace(s):
                    # exclude valid namespaces as a namespace +
                    # namespace = qname
                    continue
                q = "%s.%s" % (ns, s)
                self.assertFalse(
                    types.NameTable.is_qualified_name(q),
                    "%s failed" % repr(q))
        for ns in bad_namespaces:
            if ns is None:
                continue
            for s in good_simple_identifiers + bad_simple_identifiers:
                if s is None:
                    continue
                q = "%s.%s" % (ns, s)
                self.assertFalse(
                    types.NameTable.is_qualified_name(q),
                    "%s failed" % repr(q))
        # for completeness
        self.assertFalse(types.NameTable.is_qualified_name(None), "None fail")
        # a couple of special cases on split_qname
        for q in ("", "A", ".A", "A."):
            try:
                types.NameTable.split_qname(q)
                self.fail("%s failed" % repr(q))
            except ValueError:
                pass

    def test_named(self):
        n = types.Named()
        self.assertTrue(n.name is None)
        self.assertTrue(n.nametable is None)
        self.assertTrue(n.qname is None)
        self.assertTrue(to_text(n) == "Named")
        self.assertFalse(n.is_owned_by(self.mock_ns))
        self.assertTrue(n.root_nametable() is None)

    def test_abstract(self):
        ns = types.NameTable()
        # abstract class...
        n = types.Named()
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
        n = types.Named()
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
        self.mock_ns.tell("Ciao", c)
        self.assertTrue(c.call_count == 1)
        self.assertTrue(c.last_value is x)
        self.mock_ns["Bye"] = y
        self.assertTrue(c.call_count == 2)
        self.assertTrue(c.last_value is y)
        self.mock_ns.close()
        self.assertTrue(c.call_count == 3)
        self.assertTrue(c.last_value is None)

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
        types.NameTable.tell_all_closed((ns1, ns2, ns3), c)
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
        o1 = types.Named()
        self.assertTrue(o1.root_nametable() is None)
        o1.declare(s3, "o1")
        self.assertTrue(o1.root_nametable() is s1)


class AnnotatableMapping(types.Annotatable, collections.MutableMapping):

    def __init__(self):
        super(AnnotatableMapping, self).__init__()
        self.d = {}

    def __delitem__(self, key):
        del self.d[key]

    def __getitem__(self, key):
        return self.d[key]

    def __iter__(self):
        return self.d.__iter__()

    def __len__(self):
        return len(self.d)

    def __setitem__(self, key, value):
        self.d[key] = value


class AnnotationTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.em = odata.EntityModel()
        self.s = odata.Schema()
        self.s.declare(self.em, "Vocab")
        self.term = types.Term()
        self.term.declare(self.s, "Description")
        self.term.set_type(odata.edm['String'])
        self.s.close()
        self.em.close()
        self.undeclared_term = types.Term()
        self.undeclared_term.set_type(odata.edm['String'])

    def test_constructors(self):
        # annotatable object
        annotated = types.Annotatable()
        self.assertTrue(isinstance(annotated.annotations, types.Annotations))
        self.assertTrue(len(annotated.annotations) == 0)
        # annotations table
        atable = types.Annotations()
        self.assertTrue(len(atable) == 0, "No annotations initially")
        # annotation (table of QualifiedAnnotation keyed on qualifier)
        a = types.Annotation()
        self.assertTrue(len(a) == 0, "No qualified annotations initially")
        self.assertTrue(a.name is None)     # the qualified name of the term
        try:
            types.QualifiedAnnotation(None)
            self.fail("No term")
        except ValueError:
            pass
        qa = types.QualifiedAnnotation(self.term)
        self.assertTrue(qa.name is None, "undeclared")
        self.assertTrue(qa.term is self.term, "defining term")
        self.assertTrue(qa.qualifier is None, "qualifier is optional")
        self.assertTrue(isinstance(qa.value, primitive.StringValue),
                        "value type")

    def test_split_json(self):
        try:
            types.QualifiedAnnotation.split_json_name("Vocab.Description")
            self.fail("name must contain '@'")
        except ValueError:
            pass
        target, qname, qualifier = types.QualifiedAnnotation.split_json_name(
            "@Vocab.Description")
        self.assertTrue(target is None)
        self.assertTrue(isinstance(qname, types.QualifiedName))
        self.assertTrue(qname.namespace == "Vocab")
        self.assertTrue(qname.name == "Description")
        self.assertTrue(qualifier is None)
        qa = types.QualifiedAnnotation.from_qname(
            qname, self.em, qualifier=qualifier)
        # no target, no qualifier
        self.assertTrue(qa.name is None, "undeclared")
        self.assertTrue(qa.term is self.term, "defining term")
        self.assertTrue(qa.qualifier is None, "no qualifier")
        self.assertTrue(isinstance(qa.value, primitive.StringValue),
                        "value type")
        target, qname, qualifier = types.QualifiedAnnotation.split_json_name(
            "@Vocab.Description#en")
        self.assertTrue(target is None)
        self.assertTrue(qname.namespace == "Vocab")
        self.assertTrue(qname.name == "Description")
        self.assertTrue(qualifier == "en")
        qa = types.QualifiedAnnotation.from_qname(
            qname, self.em, qualifier=qualifier)
        self.assertTrue(qa.name is None, "undeclared")
        self.assertTrue(qa.term is self.term, "defining term")
        self.assertTrue(qa.qualifier == "en", "qualifier present")
        target, qname, qualifier = types.QualifiedAnnotation.split_json_name(
            "Primitive@Vocab.Description")
        self.assertTrue(target == "Primitive")
        self.assertTrue(qname.namespace == "Vocab")
        self.assertTrue(qname.name == "Description")
        self.assertTrue(qualifier is None)
        target, qname, qualifier = types.QualifiedAnnotation.split_json_name(
            "Primitive@Vocab.Description#en")
        self.assertTrue(target == "Primitive")
        self.assertTrue(qname.namespace == "Vocab")
        self.assertTrue(qname.name == "Description")
        self.assertTrue(qualifier == "en")
        qa = types.QualifiedAnnotation.from_qname(
            qname, self.em, qualifier=qualifier)
        self.assertTrue(qa.name is None, "undeclared")
        self.assertTrue(qa.term is self.term, "defining term")
        self.assertTrue(qa.qualifier == "en", "qualifier present")
        target, qname, qualifier = types.QualifiedAnnotation.split_json_name(
            "Primitive@Vocab.Unknown#en")
        self.assertTrue(target == "Primitive")
        self.assertTrue(qname.namespace == "Vocab")
        self.assertTrue(qname.name == "Unknown")
        self.assertTrue(qualifier == "en")
        qa = types.QualifiedAnnotation.from_qname(
            qname, self.em, qualifier=qualifier)
        self.assertTrue(qa is None, "Undefined Term")

    def test_qualified_annotation_checks(self):
        a = types.Annotation()
        # name must be a qualifier (simple identifier), type is
        # QualifiedAnnotation
        qa = types.NominalType()
        try:
            a["Tablet"] = qa
            self.fail("check_type failed")
        except NotImplementedError:
            self.fail("check_name or check_value not implemented")
        except TypeError:
            # correct, that was a good identifier but a bad value
            pass
        qa = types.QualifiedAnnotation(self.term)
        try:
            qa.declare(a, "+Tablet")
            self.fail("QualifiedAnnotation.declare with bad name")
        except ValueError:
            pass
        self.assertTrue(qa.name is None)
        try:
            a.check_name(None)
            self.fail("QualifiedAnnotation qualifiers must not be None")
        except ValueError:
            pass
        # but empty string is OK
        a.check_name("")
        try:
            qa.declare(a, None)
            self.fail("QualifiedAnnotation.declare with no name")
        except ValueError:
            pass
        self.assertTrue(qa.name is None)
        try:
            qa.declare(a, "Tablet")
        except ValueError:
            self.fail("Good name raised ValueError")
        except TypeError:
            self.fail("Good name and type raised TypeError")
        self.assertTrue(qa.name == "Tablet")
        self.assertTrue(qa.qname == "#Tablet")

    def test_annotation_checks(self):
        aa = types.Annotations()
        # name must be a: [simple identifier @] qualified name, type is
        # Annotation
        a = types.NominalType()
        try:
            aa["Vocab.Description"] = a
            self.fail("check_type failed")
        except NotImplementedError:
            self.fail("check_name or check_value not implemented")
        except TypeError:
            # correct, that was a good identifier but a bad value
            pass
        a = types.Annotation()
        try:
            a.declare(aa, "Description")
            self.fail("Annotation.declare with bad name")
        except ValueError:
            pass
        try:
            aa.check_name(None)
            self.fail("Annotation names must be qualified names")
        except ValueError:
            pass
        try:
            a.declare(aa, None)
            self.fail("Annotation.declare with no name")
        except ValueError:
            pass
        try:
            a.declare(aa, "Vocab.Description")
        except ValueError:
            self.fail("Good name raised ValueError")
        except TypeError:
            self.fail("Good name and type raised TypeError")
        self.assertTrue(a.name == "Vocab.Description")
        self.assertTrue(a.qname == "Vocab.Description")

    def test_declare(self):
        aa = types.Annotations()
        # check that the term declaration is required
        qa = types.QualifiedAnnotation(self.undeclared_term, "Tablet")
        try:
            qa.qualified_declare(aa)
            self.fail("Term must be qualified")
        except ValueError:
            pass
        qa = types.QualifiedAnnotation(self.term, "Tablet")
        qa.qualified_declare(aa)
        self.assertTrue(len(aa) == 1)
        self.assertTrue(len(aa['Vocab.Description']) == 1)
        self.assertTrue(aa['Vocab.Description']['Tablet'] is qa)
        # an unqualified name goes in with an empty string qualifier
        uqa = types.QualifiedAnnotation(self.term)
        uqa.qualified_declare(aa)   # automatically declared as ""
        self.assertTrue(len(aa) == 1)
        self.assertTrue(len(aa['Vocab.Description']) == 2)
        self.assertTrue(aa['Vocab.Description'][''] is uqa)
        # you can't declare a qualified name twice
        dqa = types.QualifiedAnnotation(self.term, "Tablet")
        try:
            dqa.qualified_declare(aa)
            self.fail("Duplicate qualified annotation")
        except errors.DuplicateNameError:
            pass
        # test the lookup
        self.assertTrue(len(aa['Vocab.Description']) == 2)
        self.assertTrue(aa.qualified_get('Vocab.Description') is uqa)
        self.assertTrue(aa.qualified_get('Vocab.Description', 'Tablet') is qa)
        self.assertTrue(aa.qualified_get('Vocab.Description',
                        ('Tablet', '')) is qa)
        self.assertTrue(aa.qualified_get('Vocab.Description',
                        ('', 'Tablet')) is uqa)
        self.assertTrue(aa.qualified_get('Vocab.Description', 'Phone') is
                        None)
        self.assertTrue(aa.qualified_get('Vocab.Description', 'Phone', qa) is
                        qa)
        self.assertTrue(aa.qualified_get('Vocab.Description',
                                         ('Phone', 'Desktop'), qa) is qa)

    def test_annotate(self):
        # start with a simple annotatable object
        x = types.Annotatable()
        qa = types.QualifiedAnnotation.from_qname(
            "Vocab.Description", self.em)
        x.annotate(qa)
        self.assertTrue(
            x.annotations.qualified_get("Vocab.Description") is qa)
        qaq = types.QualifiedAnnotation.from_qname(
            "Vocab.Description", self.em, qualifier="en")
        x.annotate(qaq)
        self.assertTrue(
            x.annotations.qualified_get("Vocab.Description") is qa)
        self.assertTrue(
            x.annotations.qualified_get("Vocab.Description", "en") is qaq)
        tqa = types.QualifiedAnnotation.from_qname(
            "Vocab.Description", self.em, qualifier="en")
        try:
            x.annotate(tqa, target="Primitive")
            self.fail("Targeted annotation with no possible targets")
        except TypeError:
            pass
        x = AnnotatableMapping()
        try:
            x.annotate(tqa, target="Primitive")
            self.fail("Targeted annotation with no target declared")
        except KeyError:
            pass
        x["Primitive"] = odata.edm['String']()
        x.annotate(tqa, target="Primitive")
        self.assertTrue("Vocab.Description" not in x.annotations)
        self.assertTrue(x.annotations.qualified_get(
                            "Vocab.Description", "en") is None)
        self.assertTrue("Vocab.Description" in x["Primitive"].annotations)
        self.assertTrue(x["Primitive"].annotations.qualified_get(
                            "Vocab.Description", "en") is tqa)
        tqa2 = types.QualifiedAnnotation.from_qname(
            "Vocab.Description", self.em, qualifier="en")
        try:
            x.annotate(tqa2, target="Primitive")
            self.fail("Duplicate annotations")
        except errors.DuplicateNameError:
            pass
        y = AnnotatableMapping()
        y["Primitive"] = types.Named()
        try:
            y.annotate(tqa, target="Primitive")
            self.fail("Can't target an object that is not annotatable")
        except TypeError:
            pass


class NominalTypeTests(unittest.TestCase):

    def test_constructor(self):
        n = types.NominalType()
        self.assertTrue(n.base is None)
        # callable, returns a null of type n
        v = n()
        self.assertTrue(isinstance(v, types.Value))
        self.assertTrue(v.type_def is n)
        self.assertTrue(v.is_null())

    def test_namespace_declare(self):
        ns = odata.Schema()
        # abstract class...
        n = types.NominalType()
        # This should work fine!
        n.declare(ns, "Hello")
        self.assertTrue(n.name == "Hello", "Declaration OK")
        self.assertTrue(ns["Hello"] is n, "Can look-up value")
        try:
            n.declare(ns, "+Hello")
            self.fail("Named.declare with bad name")
        except ValueError:
            pass
        n.declare(ns, "_Hello")
        self.assertTrue(len(ns) == 2)
        self.assertTrue(n.nametable is not None, "nametable set on declare")
        self.assertTrue(n.nametable() is ns, "nametable callable (weakref)")

    def test_abstract_types(self):
        # Edm namespace should contain the abstract types
        t1 = odata.edm['PrimitiveType']
        self.assertTrue(t1.name == 'PrimitiveType')
        try:
            odata.edm['Primitivetype']
            self.fail('case insensitive namespace look-up')
        except KeyError:
            pass
        t2 = odata.edm['ComplexType']
        self.assertTrue(t2.name == 'ComplexType')
        self.assertTrue(t1 is not t2)
        t3 = odata.edm['EntityType']
        self.assertTrue(t3.name == 'EntityType')
        self.assertTrue(t1 is not t3)
        self.assertTrue(t2 is not t3)


class ValueTests(unittest.TestCase):

    def test_base(self):
        """Base class for all values"""
        # construct without a type definition
        try:
            v = types.Value()
            self.fail("Value require type definition")
        except TypeError:
            pass
        t = odata.edm['PrimitiveType']
        v = types.Value(t)
        # this is a NULL value of an unspecified type
        self.assertFalse(v)
        self.assertTrue(v.is_null())
        self.assertTrue(v.type_def is t)
        d = {}
        try:
            d[v] = 1
            self.fail("Unspecified Value is hashable")
        except TypeError:
            pass


class SystemQueryTests(unittest.TestCase):

    def test_entity_options(self):
        options = types.ExpandOptions()
        self.assertTrue(isinstance(options.select, list))
        self.assertTrue(len(options.select) == 0)
        self.assertTrue(isinstance(options.expand, list))
        self.assertTrue(len(options.expand) == 0)

    def test_select_path(self):
        options = types.ExpandOptions()
        options.add_select_path(("PropertyA", ))
        self.assertTrue(len(options.select) == 1)
        sitem = options.select[0]
        self.assertTrue(isinstance(sitem, types.SelectItem))
        self.assertTrue(len(sitem.path) == 1)
        self.assertTrue(sitem.type_cast is None)
        options.add_select_path(
            ("PropertyB", types.QualifiedName("Schema", "Subtype")))
        self.assertTrue(len(options.select) == 2)
        sitem = options.select[1]
        self.assertTrue(len(sitem.path) == 1)
        self.assertTrue(sitem.type_cast == ("Schema", "Subtype"))
        # allow strings
        options.add_select_path("PropertyC/PropertyC1")
        sitem = options.select[2]
        self.assertTrue(len(sitem.path) == 2)
        self.assertTrue(sitem.type_cast is None)
        # but don't allow non-iterabls objects
        try:
            options.add_select_path(object())
            self.fail("select path accepts object")
        except TypeError:
            pass
        # and don't allow empty paths
        try:
            options.add_select_path("")
            self.fail("select path accepts empty path")
        except ValueError:
            pass
        options.clear_select()
        self.assertTrue(len(options.select) == 0)

    def test_selected(self):
        options = types.ExpandOptions()
        # implicit select rules
        self.assertTrue(options.selected(None, "PropertyA") is True)
        self.assertTrue(options.selected("Schema.Type", "PropertyA") is True)
        self.assertTrue(options.selected(None, "NavX", nav=True) is False)
        # explicit select rules
        options.add_select_path("NavY")
        self.assertTrue(options.selected(None, "PropertyA") is False)
        self.assertTrue(options.selected("Schema.Type", "PropertyA") is False)
        self.assertTrue(options.selected(None, "NavX", nav=True) is False)
        self.assertTrue(options.selected(None, "NavY", nav=True) is True)
        # check cache by rereading...
        self.assertTrue(options.selected(None, "PropertyA") is False)
        self.assertTrue(options.selected("Schema.Type", "PropertyA") is False)
        self.assertTrue(options.selected(None, "NavX", nav=True) is False)
        self.assertTrue(options.selected(None, "NavY", nav=True) is True)
        # check rules are not cached on change
        options.add_select_path("*")
        self.assertTrue(options.selected(None, "PropertyA") is True)
        self.assertTrue(options.selected("Schema.Type", "PropertyA") is True)
        self.assertTrue(options.selected(None, "NavX", nav=True) is False)
        self.assertTrue(options.selected(None, "NavY", nav=True) is True)
        options.clear_select()
        self.assertTrue(options.selected(None, "PropertyA") is True)
        self.assertTrue(options.selected(None, "NavY", nav=True) is False)
        # test type cast
        options.add_select_path("Schema.Type/PropertyA")
        self.assertTrue(options.selected(None, "PropertyA") is False)
        self.assertTrue(options.selected("Schema.Type", "PropertyA") is True)
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
        options = types.ExpandOptions()
        options.add_expand_path(("PropertyA", ))
        self.assertTrue(len(options.expand) == 1)
        xitem = options.expand[0]
        self.assertTrue(isinstance(xitem, types.ExpandItem))
        self.assertTrue(isinstance(xitem.path, tuple))
        self.assertTrue(len(xitem.path) == 1)
        self.assertTrue(xitem.path == ("PropertyA", ))
        self.assertTrue(xitem.type_cast is None)
        self.assertTrue(xitem.qualifier is None)
        self.assertTrue(isinstance(xitem.options, types.ExpandOptions))
        options.add_expand_path(("PropertyB", "PropertyB1"))
        self.assertTrue(len(options.expand) == 2)
        xitem = options.expand[1]
        self.assertTrue(len(xitem.path) == 2)
        suboptions = types.ExpandOptions()
        suboptions.top = 10
        options.add_expand_path(
            ("PropertyC", types.QualifiedName("Schema", "Subtype")),
            qualifier=types.PathQualifier.ref, options=suboptions)
        self.assertTrue(len(options.expand) == 3)
        xitem = options.expand[2]
        self.assertTrue(len(xitem.path) == 1)
        self.assertTrue(to_text(xitem.type_cast) == "Schema.Subtype")
        self.assertTrue(xitem.qualifier == types.PathQualifier.ref)
        self.assertTrue(xitem.options is suboptions)
        self.assertTrue(xitem.options.top == 10)
        options.add_expand_path(
            "PropertyC/PropertyC1", types.PathQualifier.count)
        xitem = options.expand[3]
        self.assertTrue(len(xitem.path) == 2)
        self.assertTrue(xitem.type_cast is None)
        # but don't allow non-iterable objects
        try:
            options.add_expand_path(object())
            self.fail("expand path accepts object")
        except TypeError:
            pass
        options.clear_expand()
        self.assertTrue(len(options.expand) == 0)

    def test_complex_selected(self):
        options = types.ExpandOptions()
        # implicit select rules
        suboptions, type_cast = options.complex_selected(None, "PropertyA")
        self.assertTrue(isinstance(suboptions, types.ExpandOptions))
        # degenerate case, options are explicit for complex types!
        self.assertFalse(suboptions.select_default)
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].path == ("*", ))
        self.assertTrue(type_cast is None)
        # check cache
        suboptions_cached, type_cast = options.complex_selected(
            None, "PropertyA")
        self.assertTrue(suboptions_cached is suboptions, "Cache check")
        suboptions, type_cast = options.complex_selected(
            "Schema.Type", "PropertyA")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].path == ("*", ))
        self.assertTrue(type_cast is None)
        # explicit select rules, setup auto cache clear check
        suboptionsB, type_cast = options.complex_selected(None, "PropertyB")
        options.add_select_path("PropertyB")
        suboptions, type_cast = options.complex_selected(None, "PropertyA")
        self.assertTrue(suboptions is None)
        suboptions, type_cast = options.complex_selected(
            "Schema.Type", "PropertyA")
        self.assertTrue(suboptions is None)
        suboptions, type_cast = options.complex_selected(None, "PropertyB")
        self.assertTrue(suboptions is not suboptionsB, "auto cache clear")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].path == ("*", ))
        options.clear_select()
        options.add_select_path("*")
        suboptions, type_cast = options.complex_selected(None, "PropertyA")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].path == ("*", ))
        suboptions, type_cast = options.complex_selected(
            "Schema.Type", "PropertyA")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].path == ("*", ))
        suboptions, type_cast = options.complex_selected(None, "PropertyB")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].path == ("*", ))
        self.assertFalse(suboptions is suboptionsB, "cache clear check")
        options.clear_select()
        options.add_select_path("Schema.Type/PropertyA")
        options.add_select_path("PropertyB")
        suboptions, type_cast = options.complex_selected(None, "PropertyA")
        self.assertTrue(suboptions is None)
        suboptions, type_cast = options.complex_selected(
            "Schema.Type", "PropertyA")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].path == ("*", ))
        self.assertTrue(type_cast is None)
        suboptions, type_cast = options.complex_selected(
            "Schema.Type2", "PropertyA")
        self.assertTrue(suboptions is None)
        suboptions, type_cast = options.complex_selected(
            "Schema.Type", "PropertyB")
        self.assertTrue(suboptions is None)
        suboptions, type_cast = options.complex_selected(None, "PropertyB")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].path == ("*", ))
        # select individual complex property
        options.add_select_path("PropertyC/PropertyC1")
        suboptions, type_cast = options.complex_selected(None, "PropertyC")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].path == ("PropertyC1", ))
        self.assertTrue(type_cast is None)
        # select a complex property with type cast
        options.add_select_path("PropertyD/Schema.Type1")
        suboptions, type_cast = options.complex_selected(None, "PropertyD")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].path == ("*", ))
        self.assertTrue(isinstance(type_cast, types.QualifiedName))
        self.assertTrue(type_cast == ("Schema", "Type1"))
        # check conflict
        options.add_select_path("PropertyD/Schema.Type2")
        try:
            suboptions, type_cast = options.complex_selected(
                None, "PropertyD")
            self.fail("Conflicting type-cast rules")
        except errors.PathError:
            pass

    def test_complex_expanded(self):
        options = types.ExpandOptions()
        options.add_expand_path("*")
        suboptions, type_cast = options.complex_selected(None, "PropertyA")
        # PropertyA selected (by default) so will contain expand rule
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].path == ("*", ))
        self.assertTrue(len(suboptions.expand) == 1)
        self.assertTrue(suboptions.expand[0].path == ("*", ))
        options.add_select_path("PropertyB")
        suboptions, type_cast = options.complex_selected(None, "PropertyA")
        # PropertyA no longer selected so expand rule does not propagate
        self.assertTrue(suboptions is None)
        suboptionsB, type_cast = options.complex_selected(None, "PropertyB")
        self.assertTrue(len(suboptionsB.select) == 1)
        self.assertTrue(suboptionsB.select[0].path == ("*", ))
        self.assertTrue(len(suboptionsB.expand) == 1)
        self.assertTrue(suboptionsB.expand[0].path == ("*", ))
        options.clear_expand()
        # check negative cache clear
        suboptions, type_cast = options.complex_selected(None, "PropertyB")
        self.assertTrue(suboptions is not suboptionsB)
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].path == ("*", ))
        self.assertTrue(len(suboptions.expand) == 0)
        options.clear_select()
        options.add_expand_path("PropertyA/NavX")
        options.add_expand_path("Schema.Type1/PropertyA/NavY")
        options.add_expand_path("NavZ")
        suboptions, type_cast = options.complex_selected(None, "PropertyA")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].path == ("*", ))
        self.assertTrue(len(suboptions.expand) == 1)
        self.assertTrue(suboptions.expand[0].path == ("NavX", ))
        suboptions, type_cast = options.complex_selected(None, "PropertyB")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].path == ("*", ))
        self.assertTrue(len(suboptions.expand) == 0)
        suboptions, type_cast = options.complex_selected(
            "Schema.Type1", "PropertyA")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].path == ("*", ))
        self.assertTrue(len(suboptions.expand) == 1)
        self.assertTrue(suboptions.expand[0].path == ("NavY", ))
        suboptions, type_cast = options.complex_selected(
            "Schema.Type2", "PropertyA")
        self.assertTrue(len(suboptions.select) == 1)
        self.assertTrue(suboptions.select[0].path == ("*", ))
        self.assertTrue(len(suboptions.expand) == 0)
        try:
            suboptions, type_cast = options.complex_selected(None, "NavZ")
            self.fail("Complex path matches expand rule")
        except errors.PathError:
            pass


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(levelname)s %(message)s")
    unittest.main()
