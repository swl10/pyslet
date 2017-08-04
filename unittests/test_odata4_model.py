#! /usr/bin/env python

import collections
import datetime
import logging
import unittest
import uuid

from decimal import Decimal, getcontext

from pyslet.iso8601 import (
    Date,
    Time,
    TimePoint
    )
import pyslet.odata4.errors as errors
import pyslet.odata4.geotypes as geo
import pyslet.odata4.metadata as csdl
import pyslet.odata4.model as odata
from pyslet.py2 import (
    BoolMixin,
    is_text,
    long2,
    to_text,
    u8,
    uempty,
    ul,
    UnicodeMixin,
    )
from pyslet.rfc2396 import URI
from pyslet.vfs import OSFilePath
from pyslet.xml.xsdatatypes import Duration


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(NameTableTests, 'test'),
        unittest.makeSuite(EntityModelTests, 'test'),
        unittest.makeSuite(AnnotationTests, 'test'),
        unittest.makeSuite(SchemaTests, 'test'),
        unittest.makeSuite(NominalTypeTests, 'test'),
        unittest.makeSuite(PrimitiveTypeTests, 'test'),
        unittest.makeSuite(StructuredTypeTests, 'test'),
        unittest.makeSuite(CollectionTests, 'test'),
        unittest.makeSuite(EnumerationTests, 'test'),
        unittest.makeSuite(ValueTests, 'test'),
        unittest.makeSuite(PrimitiveValueTests, 'test'),
        unittest.makeSuite(OperatorTests, 'test'),
        unittest.makeSuite(ParserTests, 'test')
        ))


TEST_DATA_DIR = OSFilePath(__file__).split()[0].join('data_odata4')


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


def load_trippin():
    dpath = TEST_DATA_DIR.join('trippin.xml')
    uri = URI.from_virtual_path(dpath)
    doc = csdl.CSDLDocument(base_uri=uri)
    doc.read()
    return doc.root.entity_model


class NameTableTests(unittest.TestCase):

    def setUp(self):        # noqa

        class MockSchema(odata.NameTable):

            def check_name(self, name):
                pass

            def check_value(self, value):
                pass

        self.mock_class = MockSchema
        self.mock_ns = MockSchema()

    def test_simple_identifier(self):
        for s in good_simple_identifiers:
            self.assertTrue(odata.NameTable.is_simple_identifier(s),
                            "%s failed" % repr(s))
        for s in bad_simple_identifiers:
            self.assertFalse(odata.NameTable.is_simple_identifier(s),
                             "%s failed" % repr(s))

    def test_namespace(self):
        for s in good_namespaces:
            self.assertTrue(odata.NameTable.is_namespace(s),
                            "%s failed" % repr(s))
        for s in bad_namespaces:
            self.assertFalse(odata.NameTable.is_namespace(s),
                             "%s failed" % repr(s))

    def test_qualified_name(self):
        qname = odata.QualifiedName("schema", "name")
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
                    odata.NameTable.is_qualified_name(s),
                    "%s failed" % repr(s))
                q = "%s.%s" % (ns, s)
                self.assertTrue(
                    odata.NameTable.is_qualified_name(q),
                    "%s failed" % repr(q))
                # if we split this it should get us back to where
                # we started
                qname = odata.NameTable.split_qname(q)
                self.assertTrue(qname.name == s)
                self.assertTrue(qname.namespace == ns)
            for s in bad_simple_identifiers:
                if s is None or odata.NameTable.is_namespace(s):
                    # exclude valid namespaces as a namespace +
                    # namespace = qname
                    continue
                q = "%s.%s" % (ns, s)
                self.assertFalse(
                    odata.NameTable.is_qualified_name(q),
                    "%s failed" % repr(q))
        for ns in bad_namespaces:
            if ns is None:
                continue
            for s in good_simple_identifiers + bad_simple_identifiers:
                if s is None:
                    continue
                q = "%s.%s" % (ns, s)
                self.assertFalse(
                    odata.NameTable.is_qualified_name(q),
                    "%s failed" % repr(q))
        # for completeness
        self.assertFalse(odata.NameTable.is_qualified_name(None), "None fail")
        # a couple of special cases on split_qname
        for q in ("", "A", ".A", "A."):
            try:
                odata.NameTable.split_qname(q)
                self.fail("%s failed" % repr(q))
            except ValueError:
                pass

    def test_named(self):
        n = odata.Named()
        self.assertTrue(n.name is None)
        self.assertTrue(n.nametable is None)
        self.assertTrue(n.qname is None)
        self.assertTrue(to_text(n) == "Named")
        self.assertFalse(n.is_owned_by(self.mock_ns))
        self.assertTrue(n.root_nametable() is None)

    def test_abstract(self):
        ns = odata.NameTable()
        # abstract class...
        n = odata.Named()
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
        n = odata.Named()
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
        odata.NameTable.tell_all_closed((ns1, ns2, ns3), c)
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
        o1 = odata.Named()
        self.assertTrue(o1.root_nametable() is None)
        o1.declare(s3, "o1")
        self.assertTrue(o1.root_nametable() is s1)


class EntityModelTests(unittest.TestCase):

    def test_constructor(self):
        em = odata.EntityModel()
        self.assertTrue(len(em) == 2, "Predefined Edm and odata schemas")
        self.assertTrue("Edm" in em)
        self.assertTrue("odata" in em)

    def test_namespace(self):
        em = odata.EntityModel()
        for s in good_namespaces:
            try:
                em.check_name(s)
            except ValueError:
                self.fail("%s failed" % repr(s))
        for s in bad_namespaces:
            try:
                em.check_name(s)
                self.fail("%s failed" % repr(s))
            except ValueError:
                pass

    def test_entitymodel_declare(self):
        em = odata.EntityModel()
        ns = odata.Schema()
        # This should work fine!
        ns.declare(em, "Hello")
        self.assertTrue(ns.name == "Hello", "Declaration OK")
        self.assertTrue(em["Hello"] is ns, "Can look-up value")
        try:
            ns.declare(em, "+Hello")
            self.fail("check_name failed")
        except ValueError:
            pass
        try:
            ns.declare(em, "Some.Vocabulary.")
            self.fail("Schema.declare with bad name")
        except ValueError:
            pass
        n = odata.Named()
        try:
            n.declare(em, "BadType")
            self.fail("Named.declare in EntityModel")
        except TypeError:
            pass
        ns.declare(em, "Some.Vocabulary.V1")
        self.assertTrue(len(em) == 4)       # includes Edm and odata
        self.assertTrue(ns.nametable is not None, "nametable set on declare")
        self.assertTrue(ns.nametable() is em, "nametable callable (weakref)")

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
        em = odata.EntityModel()
        self.assertTrue(em.qualified_get("com.example._X.x") is None)
        nsx = odata.Schema()
        nsy = odata.Schema()
        x = odata.NominalType()
        x.declare(nsx, "x")
        y = odata.NominalType()
        y.declare(nsy, "y")
        z = odata.NominalType()
        nsx.declare(em, "com.example._X")
        em.qualified_tell("com.example._X.x", c)
        self.assertTrue(c.call_count == 1)
        self.assertTrue(em.qualified_get("com.example._X.x") is x)
        self.assertTrue(
            em.qualified_get(odata.QualifiedName("com.example._X", "x")) is x)
        self.assertTrue(c.last_value is x)
        em.qualified_tell("com.example._X.z", c)
        em.qualified_tell("_Y.y", c)
        em.qualified_tell("_Y.ciao", c)
        em.qualified_tell("_Z.ciao", c)
        self.assertTrue(c.call_count == 1)
        self.assertTrue(c.last_value is x)
        z.declare(nsx, "z")
        self.assertTrue(c.call_count == 2)
        self.assertTrue(c.last_value is z)
        nsy.declare(em, "_Y")
        self.assertTrue(c.call_count == 3)
        self.assertTrue(c.last_value is y)
        nsy.close()
        self.assertTrue(c.call_count == 4)
        self.assertTrue(c.last_value is None)
        nsx.close()
        # no change
        self.assertTrue(c.call_count == 4)
        self.assertTrue(c.last_value is None)
        em.close()
        # one more call due to the namespace _Z never appearing
        self.assertTrue(c.call_count == 5)
        self.assertTrue(c.last_value is None)

    def test_close(self):
        em = odata.EntityModel()
        ns = odata.Schema()
        # attempting to close an entity model containing an open
        # schema will fail
        ns.declare(em, "Hello")
        try:
            em.close()
        except errors.ModelError:
            pass

    def test_trippin(self):
        trippin = load_trippin()
        person = trippin[
            "Microsoft.OData.Service.Sample.TrippinInMemory.Models"]["Person"]
        people = [t for t in trippin.derived_types(person)]
        self.assertTrue(len(people) == 2)
        # there should be a single container
        container = trippin.get_container()
        self.assertTrue(isinstance(container, odata.EntityContainer))
        # now simulate two containers
        schema = trippin["Trippin"]     # an extra alias
        schema._reopen()
        xcontainer = odata.EntityContainer()
        xcontainer.declare(schema, "XContainer")
        schema.close()
        try:
            trippin.get_container()
            self.fail("One container only")
        except errors.ModelError:
            pass

    def test_context(self):
        em = odata.EntityModel()
        try:
            em.get_context_url()
            self.fail("Unbound EntityModel has no context URL")
        except errors.UnboundValue:
            pass


class AnnotatableMapping(odata.Annotatable, collections.MutableMapping):

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
        self.term = odata.Term()
        self.term.declare(self.s, "Description")
        self.term.set_type(odata.edm['String'])
        self.s.close()
        self.em.close()
        self.undeclared_term = odata.Term()
        self.undeclared_term.set_type(odata.edm['String'])

    def test_constructors(self):
        # annotatable object
        annotated = odata.Annotatable()
        self.assertTrue(isinstance(annotated.annotations, odata.Annotations))
        self.assertTrue(len(annotated.annotations) == 0)
        # annotations table
        atable = odata.Annotations()
        self.assertTrue(len(atable) == 0, "No annotations initially")
        # annotation (table of QualifiedAnnotation keyed on qualifier)
        a = odata.Annotation()
        self.assertTrue(len(a) == 0, "No qualified annotations initially")
        self.assertTrue(a.name is None)     # the qualified name of the term
        try:
            odata.QualifiedAnnotation(None)
            self.fail("No term")
        except ValueError:
            pass
        qa = odata.QualifiedAnnotation(self.term)
        self.assertTrue(qa.name is None, "undeclared")
        self.assertTrue(qa.target is None, "target is optional")
        self.assertTrue(qa.term is self.term, "defining term")
        self.assertTrue(qa.qualifier is None, "qualifier is optional")
        self.assertTrue(isinstance(qa.value, odata.StringValue), "value type")

    def test_from_json(self):
        try:
            odata.QualifiedAnnotation.from_json_name(
                "Vocab.Description", self.em)
            self.fail("name must contain '@'")
        except ValueError:
            pass
        qa = odata.QualifiedAnnotation.from_json_name(
            "@Vocab.Description", self.em)
        # no target, no qualifier
        self.assertTrue(qa.name is None, "undeclared")
        self.assertTrue(qa.target is None, "no target")
        self.assertTrue(qa.term is self.term, "defining term")
        self.assertTrue(qa.qualifier is None, "no qualifier")
        self.assertTrue(isinstance(qa.value, odata.StringValue), "value type")
        qa = odata.QualifiedAnnotation.from_json_name(
            "@Vocab.Description#en", self.em)
        self.assertTrue(qa.name is None, "undeclared")
        self.assertTrue(qa.target is None, "no target")
        self.assertTrue(qa.term is self.term, "defining term")
        self.assertTrue(qa.qualifier == "en", "qualifier present")
        qa = odata.QualifiedAnnotation.from_json_name(
            "Primitive@Vocab.Description", self.em)
        self.assertTrue(qa.name is None, "undeclared")
        self.assertTrue(qa.target == "Primitive", "target present")
        self.assertTrue(qa.term is self.term, "defining term")
        self.assertTrue(qa.qualifier is None, "no qualifier")
        qa = odata.QualifiedAnnotation.from_json_name(
            "Primitive@Vocab.Description#en", self.em)
        self.assertTrue(qa.name is None, "undeclared")
        self.assertTrue(qa.target == "Primitive", "target present")
        self.assertTrue(qa.term is self.term, "defining term")
        self.assertTrue(qa.qualifier == "en", "qualifier present")
        qa = odata.QualifiedAnnotation.from_json_name(
            "Primitive@Vocab.Unknown#en", self.em)
        self.assertTrue(qa is None, "Undefined Term")

    def test_qualified_annotation_checks(self):
        a = odata.Annotation()
        # name must be a qualifier (simple identifier), type is
        # QualifiedAnnotation
        qa = odata.NominalType()
        try:
            a["Tablet"] = qa
            self.fail("check_type failed")
        except NotImplementedError:
            self.fail("check_name or check_value not implemented")
        except TypeError:
            # correct, that was a good identifier but a bad value
            pass
        qa = odata.QualifiedAnnotation(self.term)
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
        aa = odata.Annotations()
        # name must be a: [simple identifier @] qualified name, type is
        # Annotation
        a = odata.NominalType()
        try:
            aa["Vocab.Description"] = a
            self.fail("check_type failed")
        except NotImplementedError:
            self.fail("check_name or check_value not implemented")
        except TypeError:
            # correct, that was a good identifier but a bad value
            pass
        a = odata.Annotation()
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
        self.assertTrue(a.qname == "@Vocab.Description")
        # now try declaring with a target
        ta = odata.Annotation()
        try:
            ta.declare(aa, "Primitive@Description")
            self.fail("Annotation declare with bad qname")
        except ValueError:
            pass
        try:
            ta.declare(aa, "Primitive-Value@Vocab.Description")
            self.fail("Annotation declare with bad target name")
        except ValueError:
            pass
        ta.declare(aa, "Primitive@Vocab.Description")
        self.assertTrue(ta.name == "Primitive@Vocab.Description")
        self.assertTrue(ta.qname == "Primitive@Vocab.Description")

    def test_declare(self):
        aa = odata.Annotations()
        # check that the term declaration is required
        qa = odata.QualifiedAnnotation(self.undeclared_term)
        try:
            qa.qualified_declare(aa, "Tablet")
            self.fail("Term must be qualified")
        except ValueError:
            pass
        qa = odata.QualifiedAnnotation(self.term)
        qa.qualified_declare(aa, "Tablet")
        self.assertTrue(len(aa) == 1)
        self.assertTrue(len(aa['Vocab.Description']) == 1)
        self.assertTrue(aa['Vocab.Description']['Tablet'] is qa)
        # an unqualified name goes in with an empty string qualifier
        uqa = odata.QualifiedAnnotation(self.term)
        uqa.qualified_declare(aa)   # automatically declared as ""
        self.assertTrue(len(aa) == 1)
        self.assertTrue(len(aa['Vocab.Description']) == 2)
        self.assertTrue(aa['Vocab.Description'][''] is uqa)
        # you can't declare a qualified name twice
        dqa = odata.QualifiedAnnotation(self.term)
        try:
            dqa.qualified_declare(aa, "Tablet")
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
        x = odata.Annotatable()
        qa = odata.QualifiedAnnotation.from_json_name(
            "@Vocab.Description", self.em)
        x.annotate(qa)
        self.assertTrue(
            x.annotations.qualified_get("Vocab.Description") is qa)
        qaq = odata.QualifiedAnnotation.from_json_name(
            "@Vocab.Description#en", self.em)
        x.annotate(qaq)
        self.assertTrue(
            x.annotations.qualified_get("Vocab.Description") is qa)
        self.assertTrue(
            x.annotations.qualified_get("Vocab.Description", "en") is qaq)
        tqa = odata.QualifiedAnnotation.from_json_name(
            "Primitive@Vocab.Description#en", self.em)
        try:
            x.annotate(tqa)
            self.fail("Targeted annotation with no target")
        except TypeError:
            pass
        x = AnnotatableMapping()
        try:
            x.annotate(tqa)
            self.fail("Targeted annotation with no target declared")
        except KeyError:
            pass
        x["Primitive"] = odata.StringValue()
        x.annotate(tqa)
        self.assertTrue("Primitive@Vocab.Description" in x.annotations)
        self.assertTrue(x.annotations.qualified_get(
                            "Primitive@Vocab.Description", "en") is tqa)
        tqa2 = odata.QualifiedAnnotation.from_json_name(
            "Primitive@Vocab.Description#en", self.em)
        try:
            x.annotate(tqa2)
            self.fail("Duplicate annotations")
        except errors.DuplicateNameError:
            pass
        y = AnnotatableMapping()
        y["Primitive"] = odata.Annotatable()
        try:
            y.annotate(tqa)
            self.fail("Can't target an annotatable object")
        except TypeError:
            pass


class SchemaTests(unittest.TestCase):

    def test_constructor(self):
        ns = odata.Schema()
        self.assertTrue(len(ns) == 0, "no definitions on init")

    def test_checks(self):
        ns = odata.Schema()
        n = odata.Named()
        try:
            n.declare(ns, "Hello")
            self.fail("check_type failed")
        except NotImplementedError:
            self.fail("check_name or check_value not implemented")
        except TypeError:
            # correct, that was a good identifier but a bad value
            pass
        n = odata.NominalType()
        try:
            n.declare(ns, "")
            self.fail("Named.declare with no name")
        except NotImplementedError:
            self.fail("check_name or check_value not implemented")
        except TypeError:
            self.fail("check_name with None")
        except ValueError:
            pass
        try:
            n.declare(ns, "+Hello")
            self.fail("Named.declare with bad name")
        except ValueError:
            pass
        try:
            n.declare(ns, "_Hello")
        except ValueError:
            self.fail("Good name raised ValueError")
        except TypeError:
            self.fail("Good name and type raised TypeError")
        # you can't declare something twice (with the same name)
        try:
            n.declare(ns, "_Hello")
            self.fail("NominalType redeclared (same namespace and name)")
        except errors.DuplicateNameError:
            pass
        ns2 = odata.Schema()
        # declare in an alternate namespace
        n.declare(ns2, "Hello")
        self.assertTrue(n.name == "_Hello")
        self.assertTrue(n.nametable() is ns)
        self.assertTrue(ns2["Hello"] is n)
        # declare alias in same namespace
        n.declare(ns, "HelloAgain")
        self.assertTrue(n.name == "_Hello")
        self.assertTrue(n.nametable() is ns)
        self.assertTrue(ns["HelloAgain"] is n)

    def test_qname(self):
        ns = odata.Schema()
        n = odata.NominalType()
        # if the schema has no name, the qualified name is just name
        n.declare(ns, "Hello")
        self.assertTrue(n.qname == "Hello")
        self.assertTrue(n.nametable is not None)
        self.assertTrue(n.nametable() is ns)
        self.assertTrue(n.is_owned_by(ns))
        # if we delete the schema we should lose the link
        del ns
        self.assertTrue(n.nametable is not None)
        self.assertTrue(n.nametable() is None)
        # we're just an orphan
        ns2 = odata.Schema()
        # fake declaration of schema
        ns2.name = "my.namespace"
        n.declare(ns2, "HelloAgain")
        self.assertTrue(n.name == "Hello")
        self.assertTrue(n.nametable() is None)
        self.assertTrue(n.qname == "Hello")
        n = odata.NominalType()
        n.declare(ns2, "Hello")
        self.assertTrue(n.qname == "my.namespace.Hello")

    def test_edm(self):
        # There should be a default Edm Schema
        self.assertTrue(isinstance(odata.edm, odata.Schema))
        self.assertTrue(odata.edm.name == "Edm")
        self.assertTrue(len(odata.edm) == 36, sorted(odata.edm.keys()))

    def test_odata(self):
        # There should be a default odata Schema
        self.assertTrue(isinstance(odata.odata, odata.Schema))
        self.assertTrue(odata.odata.name == "odata")
        self.assertTrue(len(odata.odata) == 16, sorted(odata.odata.keys()))


class NominalTypeTests(unittest.TestCase):

    def test_constructor(self):
        n = odata.NominalType()
        self.assertTrue(n.base is None)
        # callable, returns a null of type n
        v = n()
        self.assertTrue(isinstance(v, odata.Value))
        self.assertTrue(v.type_def is n)
        self.assertTrue(v.is_null())

    def test_namespace_declare(self):
        ns = odata.Schema()
        # abstract class...
        n = odata.NominalType()
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


ALL_TYPES = (
    # Value type, example value, True if it is the default value type
    # for this example value
    (odata.BinaryValue, b'3.14', True),
    (odata.BooleanValue, True, True),
    (odata.ByteValue, 3, False),
    (odata.DateValue, Date(), True),
    (odata.DateTimeOffsetValue, TimePoint().with_zone(0), True),
    (odata.DecimalValue, Decimal('3.14'), True),
    (odata.DoubleValue, 3.14, True),
    (odata.DurationValue, Duration(), True),
    (odata.GuidValue, uuid.UUID(int=3), True),
    (odata.Int16Value, 3, False),
    (odata.Int32Value, 3, False),
    (odata.Int64Value, 3, True),
    (odata.SByteValue, 3, False),
    (odata.SingleValue, 3.14, False),
    # odata.StreamValue is handled specially
    (odata.StringValue, ul('3.14'), True),
    (odata.TimeOfDayValue, Time(), True),
    # odata.Geography is abstract
    (odata.GeographyPointValue, geo.PointLiteral(
        srid=4326, point=geo.Point(-1.00244140625, 51.44775390625)), True),
    (odata.GeographyLineStringValue, geo.LineStringLiteral(
        srid=4326, line_string=geo.LineString(
            ((-1.00244140625, 51.44775390625),
             (-0.9964599609375, 51.455810546875)))), True),
    (odata.GeographyPolygonValue, geo.PolygonLiteral(
        srid=4326, polygon=geo.Polygon(
            (((-1.003173828125, 51.439697265625),
              (-1.0029296875, 51.4437255859375),
              (-1.001708984375, 51.4437255859375),
              (-1.001708984375, 51.439697265625),
              (-1.003173828125, 51.439697265625)),
             ))), True),
    (odata.GeographyMultiPointValue, geo.MultiPointLiteral(
        srid=4326, multipoint=(
            geo.Point(-1.00244140625, 51.44775390625),
            geo.Point(-0.9964599609375, 51.455810546875))), True),
    (odata.GeographyMultiLineStringValue, geo.MultiLineStringLiteral(
        srid=4326, multi_line_string=(
            geo.LineString(((-1.00244140625, 51.44775390625),
                            (-0.9964599609375, 51.455810546875))),
            )), True),
    (odata.GeographyMultiPolygonValue, geo.MultiPolygonLiteral(
        srid=4326, multi_polygon=(
            geo.Polygon((((-1.003173828125, 51.439697265625),
                          (-1.0029296875, 51.4437255859375),
                          (-1.001708984375, 51.4437255859375),
                          (-1.001708984375, 51.439697265625),
                          (-1.003173828125, 51.439697265625)),
                         )),
            )), True),
    (odata.GeographyCollectionValue, geo.GeoCollectionLiteral(
        srid=4326, items=(
            geo.Point(-1.00244140625, 51.44775390625),
            geo.LineString(((-1.00244140625, 51.44775390625),
                            (-0.9964599609375, 51.455810546875)))
            )), True),
    # odata.Geometry is abstract
    (odata.GeometryPointValue, geo.PointLiteral(
        srid=0, point=geo.Point(1.0, -1.0)), True),
    (odata.GeometryLineStringValue, geo.LineStringLiteral(
        srid=0, line_string=geo.LineString(
            ((1.0, -1.0), (-1.0, 1.0)))), True),
    (odata.GeometryPolygonValue, geo.PolygonLiteral(
        srid=0, polygon=geo.Polygon(
            (((1.0, -1.0), (1.0, 1.0), (-1.0, 1.0), (-1.0, -1.0),
              (1.0, -1.0)), ))), True),
    (odata.GeometryMultiPointValue, geo.MultiPointLiteral(
        srid=0, multipoint=(
            geo.Point(1.0, -1.0), geo.Point(-1.0, 1.0))), True),
    (odata.GeometryMultiLineStringValue, geo.MultiLineStringLiteral(
        srid=0, multi_line_string=(
            geo.LineString(((1.0, -1.0), (-1.0, 1.0))),
            geo.LineString(((1.0, 1.0), (-1.0, -1.0))),
            )), True),
    (odata.GeometryMultiPolygonValue, geo.MultiPolygonLiteral(
        srid=0, multi_polygon=(
            geo.Polygon((((1.0, -1.0), (1.0, 1.0), (-1.0, 1.0),
                          (-1.0, -1.0), (1.0, -1.0)), )),
            geo.Polygon((((4.0, -1.0), (4.0, 1.0), (2.0, 1.0),
                          (2.0, -1.0), (4.0, -1.0)), ))
            )), True),
    (odata.GeometryCollectionValue, geo.GeoCollectionLiteral(
        srid=0, items=(
            geo.LineString(((1.0, -1.0), (-1.0, 1.0))),
            geo.LineString(((1.0, 1.0), (-1.0, -1.0))),
            geo.Polygon((((1.0, -1.0), (1.0, 1.0), (-1.0, 1.0),
                          (-1.0, -1.0), (1.0, -1.0)), )),
            )), True)
    )


class PrimitiveTypeTests(unittest.TestCase):

    def test_constructor(self):
        t = odata.PrimitiveType()
        self.assertTrue(t.base is None, "No base by default")
        self.assertTrue(t.max_length is None, "No MaxLength by default")
        # callable, returns a null of PrimitiveValue
        v = t()
        self.assertTrue(isinstance(v, odata.PrimitiveValue))
        self.assertTrue(v.type_def is t)
        self.assertTrue(v.is_null())

    def test_max_length_binary(self):
        # For binary or stream properties this is the octet length of
        # the binary data
        t = odata.edm['Binary']
        self.assertTrue(t.max_length is None, "No MaxLength by default")
        # create a derived class with max_length
        t1 = odata.PrimitiveType()
        # should inherit the value_type from t
        t1.set_base(t)
        # max_length is None, unknown restriction
        v = t1()
        self.assertTrue(isinstance(v, odata.BinaryValue))
        v.set_value(b'Hello')
        # set a weak value: max_length of 3
        t1.set_max_length(3, can_override=True)
        v = t1()
        try:
            v.set_value(b'Hello')
            self.fail("Would truncate")
        except ValueError:
            pass
        v.set_value(b'Hel')
        # 0 => max size, treated the same as None in our case
        t1.set_max_length(0)
        v = t1()
        v.set_value(b'Hello')
        try:
            t1.set_max_length(4)
            self.fail("Strong facet redefined")
        except errors.ModelError:
            pass

    def test_max_length_stream(self):
        # TODO
        pass

    def test_max_length_string(self):
        cafe = ul('Caf\xe9')
        t = odata.edm['String']
        self.assertTrue(t.max_length is None, "No MaxLength by default")
        # create a derived class with max_length
        t1 = odata.PrimitiveType()
        # should inherit the value_type from t
        t1.set_base(t)
        # max_length is None, unknown restriction
        v = t1()
        self.assertTrue(isinstance(v, odata.StringValue))
        v.set_value(cafe)
        # set a weak value
        t1.set_max_length(4, can_override=True)
        v = t1()
        v.set_value(cafe)     # OK as character length is 4, utf8 length check
        # set another weak value
        t1.set_max_length(3, can_override=True)
        try:
            v.set_value(cafe)
            self.fail("Would truncate")
        except ValueError:
            pass
        v.set_value(cafe[1:])
        # 0 => max size, treated the same as None in our case
        t1.set_max_length(0)
        v = t1()
        v.set_value(cafe)
        try:
            t1.set_max_length(4)
            self.fail("Strong facet redefined")
        except errors.ModelError:
            pass

    def test_precision_datetimeoffset(self):
        """For a temporal property the value of this attribute specifies
        the number of decimal places allowed in the seconds portion of
        the property's value..."""
        dt20 = TimePoint.from_str("2017-06-05T20:44:14.12345678901234567890Z")
        t = odata.edm['DateTimeOffset']
        self.assertTrue(t.precision is None, "Default unspecified Precision")
        # create a derived class (does not inherit precision)
        t1 = odata.PrimitiveType()
        t1.set_base(t)
        v = t1()
        self.assertTrue(isinstance(v, odata.DateTimeOffsetValue))
        # If no value is specified, the temporal property has a
        # precision of zero.
        v.set_value(dt20)
        self.assertTrue(v.value == "2017-06-05T20:44:14Z")
        self.assertFalse(v.value == dt20)
        # set a weak value for precision
        t1.set_precision(6, can_override=True)
        v = t1()
        v.set_value(dt20)
        self.assertTrue(v.value == "2017-06-05T20:44:14.123456Z",
                        v.value.time.second)
        self.assertFalse(v.value == dt20)
        # set a strong value for precision
        try:
            t1.set_precision(15)
            self.fail("Max temporal precision")
        except errors.ModelError:
            pass
        t1.set_precision(12)
        # max precision is 12
        v = t1()
        v.set_value(dt20)
        self.assertTrue(v.value == "2017-06-05T20:44:14.123456789012Z")
        self.assertFalse(v.value == dt20)
        # set another strong value should now fail
        try:
            t1.set_precision(6)
            self.fail("Strong Precision redefined")
        except errors.ModelError:
            pass

    def test_precision_duration(self):
        d20 = Duration("PT0.12345678901234567890S")
        t = odata.edm['Duration']
        self.assertTrue(t.precision is None, "Default unspecified Precision")
        # create a derived class with precision
        t1 = odata.PrimitiveType()
        t1.set_base(t)
        v = t1()
        self.assertTrue(isinstance(v, odata.DurationValue))
        # If no value is specified, the temporal property has a
        # precision of zero.
        v.set_value(d20)
        self.assertTrue(v.value == "PT0S", str(v.value))
        self.assertFalse(v.value == d20)
        # set a weak value for precision
        t1.set_precision(6, can_override=True)
        v = t1()
        v.set_value(d20)
        self.assertTrue(v.value == "PT0.123456S")
        self.assertFalse(v.value == d20)
        # set a strong value for precision
        try:
            t1.set_precision(15)
            self.fail("Max temporal precision")
        except errors.ModelError:
            pass
        t1.set_precision(12)
        # max precision is 12
        v = t1()
        v.set_value(d20)
        self.assertTrue(v.value == "PT0.123456789012S")
        self.assertFalse(v.value == d20)
        # set another strong value should now fail
        try:
            t1.set_precision(6)
            self.fail("Strong Precision redefined")
        except errors.ModelError:
            pass

    def test_precision_timeofday(self):
        t20 = Time.from_str("20:44:14.12345678901234567890")
        t = odata.edm['TimeOfDay']
        self.assertTrue(t.precision is None, "Default unspecified Precision")
        # create a derived class with precision
        t1 = odata.PrimitiveType()
        t1.set_base(t)
        v = t1()
        self.assertTrue(isinstance(v, odata.TimeOfDayValue))
        # If unspecified the precision is 0
        v.set_value(t20)
        self.assertTrue(v.value == "20:44:14")
        self.assertFalse(v.value == t20)
        # set a weak value for precision
        t1.set_precision(6, can_override=True)
        v = t1()
        v.set_value(t20)
        self.assertTrue(v.value == "20:44:14.123456")
        self.assertFalse(v.value == t20)
        # set a strong value for precision
        try:
            t1.set_precision(15)
            self.fail("Max temporal precision")
        except errors.ModelError:
            pass
        t1.set_precision(12)
        # max precision is 12
        v = t1()
        v.set_value(t20)
        self.assertTrue(v.value == "20:44:14.123456789012")
        self.assertFalse(v.value == t20)
        # set another strong value should now fail
        try:
            t1.set_precision(6)
            self.fail("Strong Precision redefined")
        except errors.ModelError:
            pass

    def test_decimal_precision(self):
        """For a decimal property the value of this attribute specifies
        the maximum number of significant decimal digits of the
        property's value"""
        self.assertTrue(getcontext().prec >= 28,
                        "Tests require decimal precision of 28 or greater")
        d20str = "0.12345678901234567890"
        i20str = "12345678901234567890"
        f20str = "1234567890.1234567890"
        d20 = Decimal(d20str)
        i20 = Decimal(i20str)
        f20 = Decimal(f20str)
        t = odata.edm['Decimal']
        self.assertTrue(t.precision is None, "No Precision by default")
        t1 = odata.PrimitiveType()
        t1.set_base(t)
        v = t1()
        self.assertTrue(isinstance(v, odata.DecimalValue))
        # If no value is specified, the decimal property has unspecified
        # precision.  Python's default of 28 is larger than the 20 used
        # in these tests.  The scale property, however, defaults to 0!
        v.set_value(d20)
        self.assertTrue(v.value == Decimal("0"))
        v.set_value(i20)
        self.assertTrue(v.value == i20)
        v.set_value(f20)
        self.assertTrue(v.value == Decimal("1234567890"))
        # a specified precision, unspecified scale defaults to 0
        t1.set_precision(6, can_override=True)
        v = t1()
        # these results should be rounded
        v.set_value(d20)
        self.assertTrue(v.value == Decimal("0"))
        self.assertFalse(v.value == d20)
        try:
            v.set_value(i20)
            self.fail("Integer larger than precision")
        except ValueError:
            pass
        # a specified precision with a variable scale
        t1.set_precision(6, -1, can_override=True)
        v = t1()
        v.set_value(d20)
        self.assertTrue(v.value == Decimal("0.123457"))
        v.set_value(i20)
        self.assertTrue(v.value == Decimal("12345700000000000000"))
        v.set_value(f20)
        self.assertTrue(v.value == Decimal("1234570000"))
        # if we exceed the digits we had originally we do not add 0s as
        # this is a maximum number of digits, not an absolute number of
        # digits.
        t1.set_precision(42, 21, can_override=True)
        v = t1()
        v.set_value(d20)
        self.assertTrue(v.value == d20)
        self.assertTrue(str(v) == d20str, str(v))
        v.set_value(i20)
        self.assertTrue(v.value == i20)
        self.assertTrue(str(v) == i20str, str(v))
        v.set_value(f20)
        self.assertTrue(v.value == f20)
        self.assertTrue(str(v) == f20str, str(v))
        # Unspecified precision, variable scale (uses -1)
        # sig fig limited by python defaults, decimal places unlimited
        t1.set_precision(None, -1, can_override=True)
        v = t1()
        v.set_value(d20)
        self.assertTrue(v.value == d20)
        self.assertTrue(str(v) == d20str, str(v))
        v.set_value(i20)
        self.assertTrue(v.value == i20)
        self.assertTrue(str(v) == i20str, str(v))
        v.set_value(f20)
        self.assertTrue(v.value == f20)
        self.assertTrue(str(v) == f20str, str(v))
        # unspecified precision, scale is OK
        t1.set_precision(None, 3, can_override=True)
        v = t1()
        v.set_value(d20)
        self.assertTrue(v.value == Decimal("0.123"))
        v.set_value(i20)
        self.assertTrue(v.value == i20)
        v.set_value(f20)
        self.assertTrue(v.value == Decimal("1234567890.123"))
        try:
            t1.set_precision(2, 3, can_override=True)
            self.fail("scale must be <= precision")
        except errors.ModelError:
            pass
        # try scale > 0
        t1.set_precision(6, 3, can_override=True)
        v = t1()
        v.set_value(d20)
        # scale beats precision
        self.assertTrue(v.value == Decimal("0.123"))
        try:
            v.set_value(i20)
            self.fail("Value exceeds precision-scale left digitis")
        except ValueError:
            pass
        v.set_value(Decimal("123.4567"))
        self.assertTrue(v.value == Decimal("123.457"))
        # try scale = 0
        t1.set_precision(6, 0, can_override=True)
        v = t1()
        v.set_value(d20)
        self.assertTrue(v.value == Decimal("0"))
        try:
            v.set_value(f20)
            self.fail("Value exceeds precision-scale left digitis")
        except ValueError:
            pass
        # try scale = precision
        t1.set_precision(6, 6, can_override=True)
        v = t1()
        v.set_value(d20)
        self.assertTrue(v.value == Decimal("0.123457"))
        try:
            v.set_value(1)
            self.fail("Value exceeds precision-scale left digitis")
        except ValueError:
            pass
        # There's a strange note about negative scale in the
        # specification.  Internally Python can support negative scale
        # but the suggestion is that this translates to a Precision
        # value that exceeds the maximum supported native precision.
        # For example, if Python's default precision is 28 then we could
        # allow precision to be set to 30 with an implied negative scale
        # of -2, this would result in values being rounded such that the
        # last two digits are always zero.  Given that scale cannot be
        # negative it would have to be omitted (implied 0 behaviour).
        t1.set_precision(getcontext().prec + 2)
        xstr = "1" * (getcontext().prec + 2)
        v.set_value(Decimal(xstr))
        self.assertTrue(v.value == Decimal(xstr[:-2] + "00"))
        # TOD: testing of strong values in set_precision

    def test_unicode_string(self):
        cafe = ul('Caf\xe9')
        t = odata.edm['String']
        self.assertTrue(t.unicode is None, "Facet unspecified by default")
        t1 = odata.PrimitiveType()
        # should inherit the value_type from t
        t1.set_base(t)
        # by default we accept unicode characters
        v = t1()
        self.assertTrue(isinstance(v, odata.StringValue))
        v.set_value(cafe)
        # set a weak value
        t1.set_unicode(False, can_override=True)
        v = t1()
        try:
            v.set_value(cafe)
            self.fail("ASCII required")
        except ValueError:
            pass
        v.set_value(cafe[:-1])    # OK
        # set a strong value
        t1.set_unicode(True)
        v = t1()
        v.set_value(cafe)
        try:
            t1.set_unicode(False)
            self.fail("Strong facet can't be changed")
        except errors.ModelError:
            pass

    def test_srid_geo(self):
        for t, pv, default in ALL_TYPES:
            if issubclass(t, (odata.GeographyValue, odata.GeometryValue)):
                edm_type = odata.edm[t.edm_name]
                self.assertTrue(edm_type.value_type is t)
                self.assertTrue(edm_type.srid is None)
                t1 = odata.PrimitiveType()
                t1.set_base(edm_type)
                # value_type inherited from edm_type
                self.assertTrue(t1.value_type is edm_type.value_type)
                self.assertTrue(t1.srid is None)
                v = t1()
                self.assertTrue(isinstance(v, t))
                v.set_value(pv)
                if issubclass(t, odata.GeographyValue):
                    def_srid = 4326
                else:
                    def_srid = 0
                self.assertTrue(v.value.srid == def_srid)
                # make up a similar value with a different srid
                pv1 = pv.__class__(27700, pv[1])
                v.set_value(pv1)
                # we don't force points to match the implied default!
                self.assertTrue(v.value.srid == 27700)
                # but we will convert raw points to literals with the
                # default SRID
                v.set_value(pv1[1])
                self.assertTrue(v.value.srid == def_srid)
                self.assertTrue(v.value == pv)


class StructuredTypeTests(unittest.TestCase):

    def test_constructors(self):
        # structured types are composed of structural properties they
        # are themselves name tables!
        t = odata.StructuredType()
        # abstract class
        self.assertTrue(isinstance(t, odata.NominalType),
                        "structured types are nominal types")
        self.assertTrue(isinstance(t, odata.NameTable),
                        "structured types define scope")
        pt = odata.PrimitiveType()
        p = odata.Property()
        self.assertTrue(isinstance(p, odata.Named), "properties are nameable")
        self.assertTrue(p.type_def is None)
        p.set_type(pt)
        self.assertTrue(p.type_def is pt)

    def test_declare(self):
        t = odata.StructuredType()
        # fake declaration
        t.name = "TypeA"
        # they require properties with simple identifier names
        n = odata.NominalType()
        try:
            n.declare(t, "Dimension")
            self.fail("NominalType declared in StructuredType")
        except TypeError:
            pass
        pt = odata.PrimitiveType()
        p = odata.Property()
        p.set_type(pt)
        try:
            p.declare(t, "Max.Dimension")
            self.fail("Property declared with bad name")
        except ValueError:
            pass
        p.declare(t, "Dimension")
        self.assertTrue(p.qname == "TypeA/Dimension")
        np = odata.NavigationProperty()
        np.declare(t, "Related")
        self.assertTrue(np.qname == "TypeA/Related")
        self.assertTrue(t["Dimension"] is p)
        self.assertTrue(t["Related"] is np)

    def test_base(self):
        ta = odata.StructuredType()
        pa = odata.Property()
        pa.set_type(odata.edm['PrimitiveType'])
        pa.declare(ta, "PA1")
        tb = odata.StructuredType()
        pb = odata.Property()
        pb.declare(tb, "PB1")
        pb.set_type(odata.edm['PrimitiveType'])
        pt = odata.PrimitiveType()
        try:
            tb.set_base(pt)
            self.fail("StructuredType with PrimitiveType base")
        except TypeError:
            pass
        self.assertTrue(len(tb) == 1)
        tb.set_base(ta)
        self.assertTrue(len(tb) == 1)
        self.assertFalse("PA1" in tb)
        self.assertTrue(tb.base is ta)
        # the additional properties appear on closure only
        try:
            tb.close()
            # the base is incomplete
        except errors.ModelError:
            pass
        ta.close()
        tb.close()
        self.assertTrue(len(tb) == 2)
        self.assertTrue("PA1" in tb)
        self.assertTrue(tb.base is ta)

    def test_derived(self):
        dpath = TEST_DATA_DIR.join('valid', 'atest.xml')
        uri = URI.from_virtual_path(dpath)
        doc = csdl.CSDLDocument(base_uri=uri)
        doc.read()
        em = doc.root.entity_model
        ta = em['a.test.pyslet.org']['TypeA']
        derived = list(em.derived_types(ta))
        self.assertTrue(len(derived) == 2)
        tnames = [t.name for t in derived]
        self.assertTrue('TypeB' in tnames)
        self.assertTrue('TypeC' in tnames)
        tx = em['b.test.pyslet.org']['TypeX']
        derived = list(em.derived_types(tx))
        self.assertTrue(len(derived) == 3)
        tnames = [t.name for t in derived]
        self.assertTrue('TypeQ' not in tnames)

    def test_nppath(self):
        dpath = TEST_DATA_DIR.join('valid', 'structure-paths.xml')
        uri = URI.from_virtual_path(dpath)
        doc = csdl.CSDLDocument(base_uri=uri)
        doc.read()
        em = doc.root.entity_model
        # simple case, just a navigation property name
        a = em['test.pyslet.org']['TypeA']
        b = em['test.pyslet.org']['TypeB']
        x = em['test.pyslet.org']['TypeX']
        np = x.resolve_nppath(["XP"], em)
        self.assertTrue(np.name == "XP")
        self.assertTrue(isinstance(np, odata.NavigationProperty))
        self.assertTrue(np is x["XP"])
        # simple case resulting in simple property
        try:
            x.resolve_nppath(["X1"], em)
            self.fail("resolve_nppath resolved simpled property")
        except errors.PathError:
            pass
        # simple case with non-existent property name
        try:
            x.resolve_nppath(["X9"], em)
            self.fail("resolve_nppath: X9")
        except errors.PathError:
            pass
        # now follow a path using a complex type
        np = x.resolve_nppath(["X2", "AP"], em)
        self.assertTrue(np is a['AP'])
        try:
            x.resolve_nppath(["X2", "A1"], em)
            # can't resolve to simple property
            self.fail("TypeX/X2/A1")
        except errors.PathError:
            pass
        # now follow a path using a derived complex type
        np = x.resolve_nppath(
            ["X2", odata.QualifiedName("test.pyslet.org", "TypeB"), "BP"], em)
        self.assertTrue(np is b['BP'])
        # but if we miss the type cast segment it fails...
        try:
            x.resolve_nppath(["X2", "BP"], em)
            self.fail("TypeX/X2/BP")
        except errors.PathError:
            pass
        # derived types inherit properties so it's ok to do this...
        np = x.resolve_nppath(
            ["X2", odata.QualifiedName("test.pyslet.org", "TypeB"), "AP"], em)
        self.assertTrue(np is a['AP'])
        self.assertTrue(np is b['AP'])
        # it is OK to do a nop-cast like this too
        np = x.resolve_nppath(
            ["X2", odata.QualifiedName("test.pyslet.org", "TypeA"), "AP"], em)
        self.assertTrue(np is a['AP'])
        # but a cast to a parent is not OK as it opens the door to
        # further casts that descend a different branch of the type tree
        # resulting in a type that is (derived from) TypeX.
        try:
            x.resolve_nppath(
                ["X3", odata.QualifiedName("test.pyslet.org", "TypeA"), "AP"],
                em)
            self.fail("TypeX/X3/TypeA/AP")
        except errors.PathError:
            pass
        self.assertTrue(np is a['AP'])
        # ...but doing so places derived type properties out of reach
        try:
            x.resolve_nppath(
                ["X3", odata.QualifiedName("test.pyslet.org", "TypeA"), "BP"],
                em)
            self.fail("TypeX/X3/TypeA/BP")
        except errors.PathError:
            pass


class CollectionTests(unittest.TestCase):

    def test_constructor(self):
        # collection types are collection wrappers for some other
        # primitive, complex or enumeration type.
        pt = odata.PrimitiveType()
        t = odata.CollectionType(pt)
        self.assertTrue(isinstance(t, odata.NominalType),
                        "Collection types are nominal types")
        self.assertTrue(t.item_type is pt,
                        "Collection types must have an item type")

    def test_value(self):
        pt = odata.PrimitiveType()
        t = odata.CollectionType(pt)
        # types are callable to obtain values
        v = t()
        self.assertTrue(isinstance(v, odata.CollectionValue))
        # never null
        self.assertTrue(v)
        self.assertFalse(v.is_null())


class EnumerationTests(unittest.TestCase):

    def test_constructor(self):
        # enumeration types are wrappers for one of a limited number of
        # integer types: Edm.Byte, Edm.SByte, Edm.Int16, Edm.Int32, or
        # Edm.Int64 - defaulting to Edm.Int32
        et = odata.EnumerationType()
        self.assertTrue(isinstance(et, odata.NominalType),
                        "Enumeration types are nominal types")
        self.assertTrue(isinstance(et, odata.NameTable),
                        "Enumeration types define scope for members")
        self.assertTrue(et.base is odata.edm['Int32'],
                        "Default base type is Int32")
        self.assertTrue(et.assigned_values is None,
                        "Whether or not")
        self.assertTrue(et.is_flags is False, "Default to no flags")
        self.assertTrue(isinstance(et.members, list), "Members type")
        self.assertTrue(len(et.members) == 0, "No Members")
        for base in ('Byte', 'SByte', 'Int16', 'Int32', 'Int64'):
            et = odata.EnumerationType(odata.edm[base])
            self.assertTrue(et.base is odata.edm[base])
        for base in ('Binary', 'String', 'Guid', 'Double', 'Decimal'):
            try:
                et = odata.EnumerationType(odata.edm[base])
                self.fail("EnumerationType(%s) should fail" % base)
            except errors.ModelError:
                pass

    def test_declare(self):
        et = odata.EnumerationType()
        # they require Members with simple identifier names
        n = odata.NominalType()
        try:
            n.declare(et, "Dimension")
            self.fail("NominalType declared in EnumerationType")
        except TypeError:
            pass
        m = odata.Member()
        try:
            m.declare(et, "Game.Rock")
            self.fail("Member declared with bad name")
        except ValueError:
            pass
        m.declare(et, "Rock")

    def test_auto_members(self):
        et = odata.EnumerationType()
        m0 = odata.Member()
        self.assertTrue(m0.value is None, "No value by default")
        m0.declare(et, "Rock")
        self.assertTrue(et.assigned_values is True)
        self.assertTrue(len(et.members) == 1)
        self.assertTrue(et.members[0] is m0)
        self.assertTrue(et['Rock'] is m0)
        self.assertTrue(m0.value == 0, "Auto-assigned starts at 0")
        m1 = odata.Member()
        m1.declare(et, "Paper")
        self.assertTrue(m1.value == 1, "Auto-assigned 1")
        m2 = odata.Member()
        m2.value = 2
        try:
            m2.declare(et, "Scissors")
            self.fail("Can't declare value with auto-assigned enum")
        except errors.ModelError:
            pass
        m2.value = None
        m2.declare(et, "Scissors")
        self.assertTrue(m2.value == 2)

    def test_auto_value(self):
        et = odata.EnumerationType()
        for n in ("Rock", "Paper", "Scissors"):
            m = odata.Member()
            m.declare(et, n)
        v = et()
        self.assertTrue(isinstance(v, odata.EnumerationValue))
        # is null
        self.assertFalse(v)
        self.assertTrue(v.is_null())
        # we can set from string
        v.set_value("Rock")
        self.assertTrue(v.value == 0)
        try:
            v.set_value("Red")
            self.fail("Bad enumeration string")
        except ValueError:
            pass
        # can't set multiple values when is_flags is False
        try:
            v.set_value("Rock,Paper")
            self.fail("Single value required")
        except ValueError:
            pass
        # we can set from an integer
        v.set_value(1)
        self.assertTrue(v.value == 1)
        self.assertTrue(str(v) == "Paper", to_text(v))
        try:
            v.set_value(4)
            self.fail("Enum member must be a member")
        except ValueError:
            pass
        try:
            v.set_value(3)
            self.fail("Enum value must be a member (no bitwise or)")
        except ValueError:
            pass
        try:
            v.set_value(1.0)
            self.fail("Enum set from float")
        except TypeError:
            pass

    def test_manual_members(self):
        et = odata.EnumerationType()
        m3 = odata.Member()
        m3.value = 3
        m3.declare(et, "Rock")
        self.assertTrue(et.assigned_values is False)
        self.assertTrue(len(et.members) == 1)
        self.assertTrue(et.members[0] is m3)
        self.assertTrue(et['Rock'] is m3)
        self.assertTrue(m3.value == 3, "Manual value 3")
        m2 = odata.Member()
        m2.value = 2
        m2.declare(et, "Paper")
        self.assertTrue(m2.value == 2, "Manual value 2")
        m1 = odata.Member()
        try:
            m1.declare(et, "Scissors")
            self.fail("Manual member requires value")
        except errors.ModelError:
            pass
        m3alt = odata.Member()
        m3alt.value = 3
        # aliases are OK
        m3alt.declare(et, "Stone")

    def test_manual_value(self):
        et = odata.EnumerationType()
        for name, value in (("Rock", 3), ("Paper", 2), ("Scissors", 1)):
            m = odata.Member()
            m.value = value
            m.declare(et, name)
        # we can set from an integer
        v = et()
        v.set_value(1)
        self.assertTrue(v.value == 1)
        self.assertTrue(str(v) == "Scissors")
        try:
            v.set_value(0)
            self.fail("No zero value")
        except ValueError:
            pass
        v.set_value("Paper")
        self.assertTrue(v.value == 2)

    def test_flags(self):
        # If the IsFlags attribute has a value of true, a non-negative
        # integer value MUST be specified for the Value attribute
        et = odata.EnumerationType()
        m = odata.Member()
        m.declare(et, "Red")
        # you can't set is_flags if there are already members
        try:
            et.set_is_flags()
            self.fail("flags with auto-members")
        except errors.ModelError:
            pass
        et = odata.EnumerationType()
        et.set_is_flags()
        self.assertTrue(et.is_flags is True)
        self.assertTrue(et.assigned_values is False)
        m = odata.Member()
        try:
            m.declare(et, "Red")
            self.fail("flags requires member values")
        except errors.ModelError:
            pass
        m.value = 1
        m.declare(et, "Red")
        m = odata.Member()
        m.value = 2
        m.declare(et, "Green")
        self.assertTrue(len(et.members) == 2)

    def test_flag_values(self):
        et = odata.EnumerationType()
        et.set_is_flags()
        for name, value in (
                ("Red", 1), ("Green", 2), ("Blue", 4),
                ("Yellow", 3), ("Magenta", 5),
                # ("Cyan", 6),
                ("White", 7)):
            m = odata.Member()
            m.value = value
            m.declare(et, name)
        v = et()
        v.set_value(1)
        self.assertTrue(v.value == 1)
        self.assertTrue(str(v) == "Red")
        # you can't use a value that isn't defined even if it makes sense.
        try:
            v.set_value(0)
            self.fail("0 for flags when unspecified")
        except ValueError:
            pass
        v.set_value("White")
        self.assertTrue(v.value == 7)
        # when converting to strings, use an exact match if there is one
        self.assertTrue(str(v) == "White")
        v.set_value(["Red", "Green"])
        self.assertTrue(str(v) == "Yellow")
        v.set_value(["Green", "Blue"])
        # otherwise use the composed flags preserving definition order
        self.assertTrue(str(v) == "Green,Blue")


class ValueTests(unittest.TestCase):

    def test_base(self):
        """Base class for all values"""
        # construct without a type definition
        try:
            v = odata.Value()
            self.fail("Value require type definition")
        except TypeError:
            pass
        t = odata.edm['PrimitiveType']
        v = odata.Value(t)
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


class GoodBytes(object):

    def __str__(self):
        return b'HiBytes'

    def __bytes__(self):
        return b'HiBytes'


class BadBytes(object):

    def __str__(self):
        raise ValueError

    def __bytes__(self):
        raise ValueError


class GoodBoolean(BoolMixin):

    def __bool__(self):
        return True


class BadBoolean(BoolMixin):

    def __bool__(self):
        raise ValueError


class GoodStr(UnicodeMixin):

    def __unicode__(self):
        return ul('Hello')


class BadStr(UnicodeMixin):

    def __unicode__(self):
        raise ValueError


class PrimitiveValueTests(unittest.TestCase):

    def test_base(self):
        """Base class for all Primitive values"""
        # construct without a property declaration
        v = odata.PrimitiveValue()
        # this is a NULL value of an unspecified type
        self.assertTrue(isinstance(v, odata.Value))
        self.assertFalse(v)
        self.assertTrue(v.is_null())
        self.assertTrue(v.value is None, "Null value on construction")
        # the associated type must be the built-in Edm.PrimitiveType
        self.assertTrue(v.type_def is odata.edm['PrimitiveType'])
        d = {}
        try:
            d[v] = 1
            self.fail("PrimitiveValue hashable")
        except TypeError:
            pass
        # construct a value from the abstract type
        primitive = odata.edm['PrimitiveType']
        v = primitive()
        self.assertTrue(isinstance(v, odata.PrimitiveValue))
        self.assertFalse(v)
        self.assertTrue(v.is_null())
        self.do_set(
            odata.PrimitiveValue,
            good=(),
            bad_values=(),
            bad_types=(True, 0, 'null'))

    def test_all_constructors(self):
        for t, pv, default in ALL_TYPES:
            t_def = odata.edm[t.__name__[:-5]]
            self.assertTrue(isinstance(t_def, odata.PrimitiveType))
            v = t()
            self.assertTrue(isinstance(v, odata.PrimitiveValue))
            self.assertFalse(v)
            self.assertTrue(v.is_null())
            self.assertTrue(v.value is None, "Null value on construction")
            self.assertTrue(
                v.type_def is t_def,
                "type_def mismatch %s != %s" % (repr(t), repr(v.type_def)))
            # now construct from the type
            v1 = t_def()
            self.assertTrue(isinstance(v1, type(v)))
            self.assertFalse(v1)
            self.assertTrue(v1.is_null())
            self.assertTrue(v1.value is None, "Null value on construction")
            self.assertTrue(v1.type_def is t_def)
        for t, pv, default in ALL_TYPES:
            t_def = odata.edm[t.__name__[:-5]]
            # null constructor
            v = t()
            self.assertTrue(isinstance(v, odata.PrimitiveValue))
            self.assertFalse(v)
            self.assertTrue(v.is_null())
            self.assertTrue(v.value is None, "Null value on construction")
            self.assertTrue(v.type_def is t_def)
            # now construct from the type
            v1 = t_def()
            self.assertTrue(isinstance(v1, type(v)))
            self.assertFalse(v1)
            self.assertTrue(v1.is_null())
            self.assertTrue(v1.value is None, "Null value on construction")
            self.assertTrue(v1.type_def is t_def)
            # non-null constructor
            v = t(pv)
            self.assertTrue(v)
            self.assertFalse(v.is_null())
            self.assertTrue(v.value == pv,
                            "Non-null value on construction: %s" % repr(t))
            self.assertTrue(v.type_def is t_def)

    def test_from_value(self):
        v = odata.PrimitiveValue.from_value(None)
        self.assertFalse(v)
        self.assertTrue(v.is_null())
        self.assertTrue(v.value is None, "Null value from_value")
        self.assertTrue(v.type_def is odata.edm['PrimitiveType'])
        for t, pv, default in ALL_TYPES:
            if default:
                v = odata.PrimitiveValue.from_value(pv)
                self.assertTrue(isinstance(v, t), "from_value default type")
            # you can't create a value from an existing value using this
            # method - use an OData operation like cast instead
            try:
                odata.PrimitiveValue.from_value(t(pv))
                self.fail("from_value(%s) non-null" % repr(t))
            except TypeError:
                pass
            try:
                odata.PrimitiveValue.from_value(t())
                self.fail("from_value(%s) null" % repr(t))
            except TypeError:
                pass

    def do_set(self, cls, good, bad_values, bad_types):
        type_msg = "%s: " % repr(cls)
        for pv, ov in good:
            value_msg = type_msg + "%s " % repr(pv)
            logging.debug("Checking good value: %s", value_msg)
            v = cls(pv)
            self.assertTrue(v, value_msg + "False")
            self.assertTrue(v.value == ov,
                            value_msg + " == %s" % repr(v.value))
            v.set_value(None)
            self.assertFalse(v)
            self.assertTrue(v.value is None, type_msg + "set_value(None)")
            v.set_value(pv)
            self.assertTrue(v.value == ov,
                            value_msg + " == %s" % repr(v.value))

        for pv in bad_values:
            value_msg = type_msg + "%s " % repr(pv)
            try:
                v = cls(pv)
                self.fail(value_msg + "constructor")
            except ValueError:
                pass
            v = cls()
            try:
                v.set_value(pv)
                self.fail(value_msg + "set_value")
            except ValueError:
                pass
        for pv in bad_types:
            value_msg = type_msg + "%s " % repr(pv)
            try:
                v = cls(pv)
                self.fail(value_msg + "constructor")
            except TypeError:
                pass
            v = cls()
            try:
                v.set_value(pv)
                self.fail(value_msg + "set_value")
            except TypeError:
                pass
        for t, pv, default in ALL_TYPES:
            # you can't create a value from an existing value using this
            # method - use an OData operation like cast instead
            xv = t(pv)
            try:
                v = cls(xv)
                self.fail(type_msg + "constructor(%s) non-null" % repr(t))
            except TypeError:
                pass
            v = cls()
            try:
                v.set_value(xv)
                self.fail("set_value(%s) non-null" % repr(t))
            except TypeError:
                pass

    def do_text(self, cls, test_items):
        type_msg = "%s: " % repr(cls)
        for pv, sv in test_items:
            value_msg = type_msg + "%s " % repr(pv)
            v = cls(pv)
            self.assertTrue(to_text(v) == sv,
                            value_msg + " str -> %s" % repr(to_text(v)))
        v = cls()
        try:
            to_text(v)
            self.fail(type_msg + "text of null")
        except ValueError:
            pass

    def test_binary(self):
        self.do_set(
            odata.BinaryValue,
            good=((b'Hello', b'Hello'),
                  (b'', b''),
                  (b'null', b'null'),
                  (ul(b'Caf\xe9'), b'Caf\xc3\xa9'),
                  (GoodBytes(), b'HiBytes')),
            bad_values=(BadBytes(), ),
            bad_types=())
        self.do_text(
            odata.BinaryValue,
            ((b'Hello', 'SGVsbG8='),
             (b'Caf\xc3\xa9', 'Q2Fmw6k='),
             (b'ab?de>g', 'YWI_ZGU-Zw==')))

    def test_boolean(self):
        """Boolean values"""
        self.do_set(
            odata.BooleanValue,
            good=((True, True),
                  (False, False),
                  (1, True),
                  (0, False),
                  ("", False),
                  ("False", True),
                  ([], False),
                  (GoodBoolean(), True),
                  ),
            bad_values=(BadBoolean(), ),
            bad_types=())
        self.do_text(
            odata.BooleanValue,
            ((True, 'true'),
             (False, 'false')))

    def test_byte(self):
        """Byte values"""
        self.do_set(
            odata.ByteValue,
            good=((1, 1),
                  (0, 0),
                  (True, 1),
                  (False, 0),
                  (1.9, 1),
                  (255.9, 255),
                  (255, 255),
                  (-0.9, 0),
                  (Decimal('-0.999'), 0),
                  (long2(100), 100),
                  (Decimal('255.999'), 255),
                  ),
            bad_values=(-1, long2(-1), -1.0, Decimal('-1.0'),
                        256, long2(256), 256.0, Decimal('256.0')),
            bad_types=(GoodBoolean(),))
        self.do_text(
            odata.ByteValue,
            ((0, '0'), (1, '1'), (255, '255')))
        # check limits
        self.assertTrue(odata.ByteValue.MAX == 255)
        self.assertTrue(odata.ByteValue.MIN == 0)

    def test_date(self):
        """Date values"""
        eagle_day = Date.from_str("19690720")
        rome_day = Date.from_str("-07520421", xdigits=0)
        self.do_set(
            odata.DateValue,
            good=((eagle_day, eagle_day),
                  (datetime.date(1969, 7, 20), eagle_day),
                  (rome_day, rome_day),
                  (datetime.datetime(1969, 7, 20, 20, 17, 40), eagle_day),
                  ),
            bad_values=(Date.from_str("1969-07"),
                        Date.from_str("1969")),
            bad_types=(19690720, 19690720.0, '19690720'))
        self.do_text(
            odata.DateValue,
            ((eagle_day, '1969-07-20'), (rome_day, '-0752-04-21')))

    def test_date_time_offset(self):
        """DateTimeOffset values"""
        eagle_time = TimePoint.from_str("19690720T201740Z")
        eagle_time_ms = TimePoint.from_str("19690720T201740.000Z")
        eagle_day = TimePoint.from_str("19690720T000000Z")
        future_time = TimePoint.from_str("20190720T201740Z")
        future_unix = future_time.get_unixtime()
        rome_time = TimePoint.from_str("-07520421T160000+0100", xdigits=0)
        leap_actual = TimePoint.from_str("2016-12-31T23:59:60Z")
        leap_adjusted = TimePoint.from_str("2016-12-31T23:59:59Z")
        leap_factual = TimePoint.from_str("2016-12-31T23:59:60.123Z")
        leap_fadjusted = TimePoint.from_str("2016-12-31T23:59:59.999999Z")
        self.do_set(
            odata.DateTimeOffsetValue,
            good=((eagle_time, eagle_time),
                  (eagle_time_ms, eagle_time),
                  (datetime.datetime(1969, 7, 20, 20, 17, 40), eagle_time),
                  (datetime.date(1969, 7, 20), eagle_day),
                  (rome_time, rome_time),
                  (future_time, future_time),
                  (future_unix, future_time),
                  (long2(future_unix), future_time),
                  (float(future_unix), future_time),
                  (leap_actual, leap_adjusted),
                  (TimePoint.from_str("2016-12-31T24:00:00Z"),
                   TimePoint.from_str("2017-01-01T00:00:00Z"))
                  ),
            bad_values=(TimePoint.from_str("19690720T201740"),
                        TimePoint.from_str("19690720T2017Z"),
                        -1),
            bad_types=('19690720T201740Z'))
        self.do_text(
            odata.DateTimeOffsetValue,
            ((eagle_time, '1969-07-20T20:17:40Z'),
             (rome_time, '-0752-04-21T16:00:00+01:00'),
             (eagle_time_ms, '1969-07-20T20:17:40.000000Z')))
        # check the correct operation of leap seconds with high precision
        t = odata.PrimitiveType()
        t.set_base(odata.edm['DateTimeOffset'])
        t.set_precision(6)
        v = t()
        v.set_value(leap_factual)
        self.assertTrue(v.value == leap_fadjusted)
        v.set_value(eagle_time_ms)
        self.assertTrue(to_text(v) == '1969-07-20T20:17:40.000000Z')

    def test_decimal(self):
        """Decimal values"""
        self.do_set(
            odata.DecimalValue,
            good=((Decimal(1), Decimal(1)),
                  (1, Decimal(1)),
                  (1.0, Decimal('1.0')),
                  (3.5, Decimal('3.5')),
                  (0, Decimal(0)),
                  (True, Decimal(1)),
                  (False, Decimal(0)),
                  (-1, Decimal(-1)),
                  (long2(100), Decimal(100)),
                  ),
            bad_values=(),
            bad_types=(GoodBoolean(),))
        self.do_text(
            odata.DecimalValue,
            ((Decimal(0), '0'), (Decimal(1), '1'), (Decimal('1.00'), '1.00'),
             (Decimal(-1), '-1'), (Decimal('3.5'), '3.5')))

    def test_duration(self):
        """Duration values"""
        t12345 = Duration("P1DT2H3M4.5S")
        t1234 = Duration("P1DT2H3M4S")
        # OData only allows Days, Hours, Minutes and Seconds.
        self.do_set(
            odata.DurationValue,
            good=((t12345, t12345),
                  (t1234, t1234),
                  (Duration("P01DT02H03M04S"), t1234)),
            bad_values=(Duration("P1Y"), Duration("P1M"), Duration("P1W")),
            bad_types=(1, 1.0, Time.from_str("02:03:04.5")))
        # by default, unspecified precision
        self.do_text(
            odata.DurationValue,
            ((t12345, 'P1DT2H3M4.5S'),
             (t1234, 'P1DT2H3M4S')))
        # check the correct operation of precision
        t = odata.PrimitiveType()
        t.set_base(odata.edm['Duration'])
        t.set_precision(1)
        v = t()
        v.set_value(t12345)
        self.assertTrue(v.value == t12345)
        self.assertTrue(to_text(v) == 'P1DT2H3M4.5S')

    def test_float_value(self):
        """Double and Single values"""
        for cls in (odata.DoubleValue, odata.SingleValue):
            self.do_set(
                cls,
                good=((Decimal(1), 1.0),
                      (1, 1.0),
                      (1.0, 1.0),
                      (3.5, 3.5),
                      (0, 0.0),
                      (True, 1.0),
                      (False, 0.0),
                      (-1, -1.0),
                      (long2(100), 100.0),
                      (cls.MAX * 2, float('inf')),
                      (cls.MAX * -2, float('-inf')),
                      (cls.MIN * 2, float('-inf')),
                      (cls.MIN * -2, float('inf')),
                      # nan will never compare equal! no test
                      # (float('nan'), float('nan')),
                      ),
                bad_values=(),
                bad_types=(GoodBoolean(),))
            self.do_text(
                cls,
                ((1.0, '1.0'), (0.0, '0.0'), (-1.0, '-1.0')))

    def test_point(self):
        """Geography and Geometry points"""
        p = geo.Point(1.0, -1.0)
        self.assertTrue(p.x == 1.0)
        self.assertTrue(p.y == -1.0)
        self.assertTrue(p[0] == 1.0)
        self.assertTrue(p[1] == -1.0)
        p = geo.Point(y=-1.0, x=1.0)
        self.assertTrue(p.x == 1.0)
        self.assertTrue(p.y == -1.0)
        self.assertTrue(p[0] == 1.0)
        self.assertTrue(p[1] == -1.0)
        p = geo.Point(1, -1)
        self.assertTrue(isinstance(p.x, float), "force float")
        try:
            p = geo.Point("x", "y")
            self.fail("force float fail")
        except ValueError:
            pass
        # from_arg will accept any iterable
        pa = geo.Point.from_arg(p)
        self.assertTrue(pa == p)
        pa = geo.Point.from_arg((1.0, -1.0))
        self.assertTrue(pa == p)

        def genxy():
            for xy in (1.0, -1.0):
                yield xy

        p = geo.Point.from_arg(genxy())
        self.assertTrue(pa == p)
        # Now on to PointLiteral values...
        p1 = geo.PointLiteral(0, geo.Point(1.0, -1.0))
        p2 = geo.PointLiteral(0, geo.Point(1.5, -1.5))
        p3 = geo.PointLiteral(
            4326, geo.Point(-127.89734578345, 45.234534534))
        try:
            geo.PointLiteral(-1, geo.Point(1.0, -1.0))
            self.fail("negative SRID")
        except ValueError:
            pass
        for cls in (odata.GeographyPointValue, odata.GeometryPointValue):
            self.do_set(
                cls,
                good=((p1, p1),
                      (p2, p2),
                      (p3, p3)),
                bad_values=(),
                bad_types=(1.0, ))
            self.do_text(
                cls,
                ((p1, "SRID=0;Point(1 -1)"),
                 (p2, "SRID=0;Point(1.5 -1.5)"),
                 (p3, "SRID=4326;Point(-127.89734578345 45.234534534)"),
                 ))

    def gen_square_ring(self, reverse=False, size=1.0):
        # generates a closed square ring turning anticlockwise
        x = 1.5 * size
        y = -1.5 * size
        n = 5
        while n:
            yield geo.Point(x, y)
            new_x = y if reverse else -y
            y = -x if reverse else x
            x = new_x
            n -= 1

    def gen_spiral(self, n):
        # generates an open line that spirals out
        x = 1.5
        y = -1.5
        while n:
            yield geo.Point(x, y)
            new_x = -1.125 * y
            y = 1.125 * x
            x = new_x
            n -= 1

    def test_line_string(self):
        """Geography and Geometry line strings"""
        l1 = geo.LineStringLiteral(
            0, geo.LineString(((1.0, -1.0), (-1.0, 1.0))))
        l2 = geo.LineStringLiteral(
            0, geo.LineString(((1.5, -1.5), (-1.5, 1.5))))
        l3 = geo.LineStringLiteral(
            4326, geo.LineString(((1.5, -1.5), (1.5, 1.5), (-1.5, 1.5),
                                  (-1.5, -1.5))))
        for arg in [
                (),                     # No points
                (1, 0),                 # Integers, not points
                ((1, 0), ),             # Only 1 point
                (geo.Point(1, 0), ),  # Only 1 point instance
                ]:
            try:
                geo.LineString(arg)
                self.fail("Bad LineString arg: %s" % repr(arg))
            except (ValueError, TypeError):
                pass
        try:
            geo.LineStringLiteral(
                -1, geo.LineString(((1.0, -1.0), (-1.0, 1.0))))
            self.fail("negative SRID")
        except ValueError:
            pass
        for cls in (odata.GeographyLineStringValue,
                    odata.GeometryLineStringValue):
            self.do_set(
                cls,
                good=((l1, l1),
                      (l2, l2),
                      (l3, l3),
                      (geo.LineStringLiteral(
                        0, geo.LineString(((30, 10), (10, 30), (40, 40)))),
                       # compares to regular tuple OK
                       (0, ((30, 10), (10, 30), (40, 40)))),
                      ),
                bad_values=(),
                bad_types=(1.0,
                           )
                )
            self.do_text(
                cls,
                ((l1, "SRID=0;LineString(1 -1,-1 1)"),
                 (l2, "SRID=0;LineString(1.5 -1.5,-1.5 1.5)"),
                 (l3, "SRID=4326;LineString(1.5 -1.5,1.5 1.5,-1.5 1.5,"
                  "-1.5 -1.5)"),
                 ))

    def test_polygon(self):
        """Geography and Geometry polygons"""
        p1 = geo.PolygonLiteral(
            0, geo.Polygon(
                (geo.Ring(
                    (geo.Point(1.5, -1.5), geo.Point(1.5, 1.5),
                     geo.Point(-1.5, 1.5), geo.Point(-1.5, -1.5),
                     geo.Point(1.5, -1.5))), )))
        try:
            geo.PolygonLiteral(-1, p1.polygon)
            self.fail("negative SRID")
        except ValueError:
            pass
        try:
            geo.PolygonLiteral(0, [])
            self.fail("no rings")
        except ValueError:
            pass
        try:
            geo.PolygonLiteral(0, 1.0)
            self.fail("non-iterable rings")
        except TypeError:
            pass
        try:
            geo.Polygon([])
            self.fail("no rings")
        except ValueError:
            pass
        try:
            geo.Ring([geo.Point(1.5, -1.5), geo.Point(1.5, 1.5),
                      geo.Point(-1.5, 1.5), geo.Point(-1.5, -1.5)])
            self.fail("unclosed ring")
        except ValueError:
            pass
        for cls in (odata.GeographyPolygonValue,
                    odata.GeometryPolygonValue):
            self.do_set(
                cls,
                good=((p1, p1),
                      ),
                bad_values=(),
                bad_types=(1.0,
                           geo.PointLiteral(0, geo.Point(1.0, -1.0)),
                           geo.LineStringLiteral(
                            4326, (geo.Point(1.5, -1.5),
                                   geo.Point(1.5, 1.5),
                                   geo.Point(-1.5, 1.5),
                                   geo.Point(-1.5, -1.5))), )
                )
            self.do_text(
                cls,
                ((p1, "SRID=0;Polygon((1.5 -1.5,1.5 1.5,-1.5 1.5,"
                  "-1.5 -1.5,1.5 -1.5))"),
                 ))

    def test_multi_point(self):
        # a tuple of points
        mp = geo.MultiPoint((geo.Point(1, -1), ))
        self.assertTrue(len(mp) == 1)
        self.assertTrue(mp[0] == (1, -1))
        # can be created from anything that generates points
        mp = geo.MultiPoint(self.gen_spiral(10))
        self.assertTrue(len(mp) == 10)
        self.assertTrue(mp[0] == geo.Point(1.5, -1.5))
        # empty list is OK
        mp = geo.MultiPoint(())
        self.assertTrue(len(mp) == 0)
        # Now move on to the literal
        square = geo.MultiPoint(self.gen_square_ring())
        mp1 = geo.MultiPointLiteral(0, square)
        mp2 = geo.MultiPointLiteral(0, self.gen_square_ring())
        self.assertTrue(mp1 == mp2)
        mp3 = geo.MultiPointLiteral(
            4326, (geo.Point(-127.89734578345, 45.234534534), ))
        try:
            geo.MultiPointLiteral(-1, square)
            self.fail("negative SRID")
        except ValueError:
            pass
        for cls in (odata.GeographyMultiPointValue,
                    odata.GeometryMultiPointValue):
            self.do_set(
                cls,
                good=((mp1, mp1),
                      (mp2, mp2),
                      (mp3, mp3)
                      ),
                bad_values=(),
                bad_types=(1.0,
                           )
                )
            self.do_text(
                cls,
                ((mp1, "SRID=0;MultiPoint((1.5 -1.5),(1.5 1.5),(-1.5 1.5),"
                  "(-1.5 -1.5),(1.5 -1.5))"),
                 ))

    def test_multi_line_string(self):
        # a tuple of points
        square = geo.LineString(self.gen_square_ring())
        spiral2 = geo.LineString(self.gen_spiral(2))
        mls = geo.MultiLineString((spiral2, ))
        self.assertTrue(len(mls) == 1)
        self.assertTrue(mls[0][0] == (1.5, -1.5))
        # can be created from anything that can be converted to line strings
        mls = geo.MultiLineString((square, ((1, 0), (0, 1))))
        self.assertTrue(len(mls) == 2)
        self.assertTrue(mls[1][0] == (1.0, 0))
        # empty list is OK
        mls = geo.MultiLineString(())
        self.assertTrue(len(mls) == 0)
        # Now move on to the literal
        mls1 = geo.MultiLineStringLiteral(0, (square, ))
        mls2 = geo.MultiLineStringLiteral(0, (self.gen_square_ring(), ))
        self.assertTrue(mls1 == mls2)
        mls3 = geo.MultiLineStringLiteral(
            4326, (self.gen_spiral(5), self.gen_spiral(2)))
        try:
            geo.MultiLineStringLiteral(-1, (square, ))
            self.fail("negative SRID")
        except ValueError:
            pass
        for cls in (odata.GeographyMultiLineStringValue,
                    odata.GeometryMultiLineStringValue):
            self.do_set(
                cls,
                good=((mls1, mls1),
                      (mls2, mls2),
                      (mls3, mls3)
                      ),
                bad_values=(),
                bad_types=(1.0,
                           )
                )
            self.do_text(
                cls,
                ((mls1, "SRID=0;MultiLineString((1.5 -1.5,1.5 1.5,-1.5 1.5,"
                  "-1.5 -1.5,1.5 -1.5))"),
                 (geo.MultiLineStringLiteral(4326, ()),
                  "SRID=4326;MultiLineString()")
                 ))

    def test_multi_polygon(self):
        # a tuple of points
        square1 = geo.Ring(self.gen_square_ring())
        rsquare1 = geo.Ring(self.gen_square_ring(reverse=True, size=0.5))
        square2 = geo.Ring(self.gen_square_ring(size=2))
        rsquare2 = geo.Ring(self.gen_square_ring(reverse=True))
        p1 = geo.Polygon((square1, rsquare1))
        p2 = geo.Polygon((square2, rsquare2))
        mp = geo.MultiPolygon((p1, p2))
        self.assertTrue(len(mp) == 2)
        self.assertTrue(mp[0][0][0] == (1.5, -1.5))
        # can be created from anything that can be converted to Polygon
        mp = geo.MultiPolygon((p1, (square2, )))
        self.assertTrue(len(mp) == 2)
        self.assertTrue(mp[1][0][0] == (3, -3))
        # empty list is OK
        mp = geo.MultiPolygon([])
        self.assertTrue(len(mp) == 0)
        # Now move on to the literal
        mp1 = geo.MultiPolygonLiteral(0, (p1, ))
        mp2 = geo.MultiPolygonLiteral(
            0, [(self.gen_square_ring(),
                 self.gen_square_ring(reverse=True, size=0.5))])
        self.assertTrue(mp1 == mp2, "%s == %s" % (mp1, mp2))
        mp3 = geo.MultiPolygonLiteral(
            4326, geo.MultiPolygon((p2, p1)))
        try:
            geo.MultiPolygonLiteral(-1, (p1, ))
            self.fail("negative SRID")
        except ValueError:
            pass
        for cls in (odata.GeographyMultiPolygonValue,
                    odata.GeometryMultiPolygonValue):
            self.do_set(
                cls,
                good=((mp1, mp1),
                      (mp2, mp2),
                      (mp3, mp3)
                      ),
                bad_values=(),
                bad_types=(1.0,
                           )
                )
            self.do_text(
                cls,
                ((mp1, "SRID=0;MultiPolygon(("
                    "(1.5 -1.5,1.5 1.5,-1.5 1.5,-1.5 -1.5,1.5 -1.5),"
                    "(0.75 -0.75,-0.75 -0.75,-0.75 0.75,0.75 0.75,"
                    "0.75 -0.75)))"),
                 (geo.MultiPolygonLiteral(4326, ()),
                  "SRID=4326;MultiPolygon()")
                 ))

    def test_geo_collection(self):
        c0 = geo.GeoCollection([])
        self.assertTrue(len(c0) == 0)
        p = geo.Point(1.5, -1.5)
        l = geo.LineString(self.gen_spiral(2))
        square = geo.Ring(self.gen_square_ring())
        rsquare = geo.Ring(self.gen_square_ring(reverse=True, size=0.5))
        pg = geo.Polygon((square, rsquare))
        mp = geo.MultiPoint([p])
        ml = geo.MultiLineString([l])
        mpn = geo.MultiPolygon([pg])
        c = geo.GeoCollection([p, l, pg, mp, ml, mpn])
        rc = geo.GeoCollection([c, p])
        self.assertTrue(len(c) == 6)
        self.assertTrue(c[0] == (1.5, -1.5))
        self.assertTrue(rc[0] == c)
        # Now the literal form
        c_lit = geo.GeoCollectionLiteral(0, c)
        rc_lit = geo.GeoCollectionLiteral(0, rc)
        c_lit2 = geo.GeoCollectionLiteral(0, [p, l, pg, mp, ml, mpn])
        self.assertTrue(c_lit == c_lit2)
        try:
            geo.GeoCollectionLiteral(-1, c)
            self.fail("negative SRID")
        except ValueError:
            pass
        for cls in (odata.GeographyCollectionValue,
                    odata.GeometryCollectionValue):
            self.do_set(
                cls,
                good=((c_lit, c_lit),
                      (rc_lit, rc_lit),
                      ),
                bad_values=(),
                bad_types=(1.0,
                           )
                )
            self.do_text(
                cls,
                ((rc_lit,
                  "SRID=0;Collection("
                  "Collection("
                  "Point(1.5 -1.5),"
                  "LineString(1.5 -1.5,1.6875 1.6875),"
                  "Polygon((1.5 -1.5,1.5 1.5,-1.5 1.5,-1.5 -1.5,1.5 -1.5),"
                  "(0.75 -0.75,-0.75 -0.75,-0.75 0.75,0.75 0.75,0.75 -0.75)),"
                  "MultiPoint((1.5 -1.5)),"
                  "MultiLineString((1.5 -1.5,1.6875 1.6875)),"
                  "MultiPolygon(("
                  "(1.5 -1.5,1.5 1.5,-1.5 1.5,-1.5 -1.5,1.5 -1.5),"
                  "(0.75 -0.75,-0.75 -0.75,-0.75 0.75,0.75 0.75,0.75 -0.75)"
                  "))"      # MultiPolygon
                  "),"      # Collection
                  "Point(1.5 -1.5))"),
                 (geo.GeoCollectionLiteral(4326, ()),
                  "SRID=4326;Collection()")
                 ))

    def test_guid(self):
        """Guid values"""
        u1 = uuid.UUID(int=1)
        u2 = uuid.UUID(int=2)
        u3 = uuid.UUID(int=3)
        self.do_set(
            odata.GuidValue,
            good=((u1, u1),
                  (u2, u2),
                  (u3.bytes, u3),
                  (u3.hex, u3),
                  # from a unicode string (must be hex)
                  (ul('00000000000000000000000000000003'), u3),
                  ),
            bad_values=('00000000-0000-0000-0000-000000000001',
                        ul('00000000-0000-0000-0000-000000000001'),
                        '{00000000-0000-0000-0000-000000000001}',
                        ul('{00000000-0000-0000-0000-000000000001}')),
            bad_types=(GoodBoolean(), 1, 1.0, GoodBytes()))
        self.do_text(
            odata.GuidValue,
            ((u1, '00000000-0000-0000-0000-000000000001'),
             (u3, '00000000-0000-0000-0000-000000000003'),
             (uuid.UUID(int=3735928559),
              '00000000-0000-0000-0000-0000deadbeef'),
             ))

    def test_string(self):
        """String data"""
        uhello = ul('Hello')
        ucafe = ul(b'Caf\xe9')
        self.do_set(
            odata.StringValue,
            good=(('Hello', uhello),
                  (ul('Hello'), uhello),
                  (b'Hello', uhello),
                  (ucafe, ucafe),
                  ('', uempty),
                  (ul(''), uempty),
                  (b'', uempty),
                  (True, ul('True')),
                  (1, ul('1')),
                  (3.5, ul('3.5')),
                  (GoodStr(), uhello),
                  ),
            bad_values=(b'Caf\xe9', BadStr()),
            bad_types=())
        self.do_text(
            odata.StringValue,
            ((uhello, uhello),
             (ucafe, ucafe),
             ))

    def test_time(self):
        """TimeOfDay values"""
        slast = Time.from_str("235959")
        eagle_time = Time.from_str("201740")
        eagle_time_ms = Time.from_str("201740.000")
        self.do_set(
            odata.TimeOfDayValue,
            good=((slast, slast),
                  (datetime.time(second=10), Time.from_str("000010")),
                  (eagle_time, eagle_time),
                  (eagle_time_ms, eagle_time_ms),
                  (Time.from_str("235960"), Time.from_str("235959")),
                  (Time.from_str("235960.5"),
                   Time.from_str("235959.999999")),
                  (Time.from_str("235960.55"),
                   Time.from_str("235959.999999")),
                  ),
            bad_values=(Time.from_str("2017"),
                        Time.from_str("20"),
                        Time.from_str("201740Z"),
                        Time.from_str("151740Z-0500"),
                        Time.from_str("240000")),
            bad_types=(201740, 201740.0, '201740'))
        self.do_text(
            odata.TimeOfDayValue,
            ((eagle_time, '20:17:40'), (eagle_time_ms, '20:17:40.000000')))
        # check the correct operation of precision
        t = odata.PrimitiveType()
        t.set_base(odata.edm['TimeOfDay'])
        t.set_precision(6)
        v = t()
        v.set_value(Time.from_str("235960.5"))
        self.assertTrue(v.value == Time.from_str("235959.999999"))
        v.set_value(Time.from_str("235960.55"))
        self.assertTrue(v.value == Time.from_str("235959.999999"))
        v.set_value(eagle_time_ms)
        self.assertTrue(v.value == eagle_time_ms)
        self.assertTrue(to_text(v) == '20:17:40.000000')


NUMERIC_TYPES = (
    odata.ByteValue,
    odata.DecimalValue,
    odata.DoubleValue,
    odata.Int16Value,
    odata.Int32Value,
    odata.Int64Value,
    odata.SByteValue,
    odata.SingleValue)


class OperatorTests(unittest.TestCase):

    def type_gen(self):
        for t in odata.edm.values():
            yield t

    def value_gen(self):
        for t, pv, default in ALL_TYPES:
            yield t(pv)

    def test_cast(self):
        # the null value can be cast to any type
        for t1 in self.type_gen():
            v1 = t1()
            v1.set_value(None)
            for t2 in self.type_gen():
                # a null instance of type t1 can be cast to t2
                logging.debug("Casting null of type %s to type: %s",
                              str(t1), str(t2))
                v2 = v1.cast(t2)
                self.assertTrue(
                    v2.is_null(), "%s -> %s" %
                    (v1.__class__.__name__, v2.__class__.__name__))
        # primitive types are cast to Edm.String using literal
        # representation used in payloads and WKT for Geo types.
        stype = odata.edm['String']
        for t, pv, default in ALL_TYPES:
            v1 = t(pv)
            v2 = v1.cast(stype)
            self.assertFalse(v2.is_null())
            self.assertTrue(isinstance(v2, odata.StringValue))
            self.assertTrue(v2.value == str(v1), "%s -> %s" %
                            (repr(v1), repr(v2)))
        # TODO: cast fails if the target type specifies an insufficient
        # MaxLength
        #
        # Numeric primitive types are cast to each other with
        # appropriate rounding.
        for t1 in NUMERIC_TYPES:
            v1 = t1(3.75)
            for t2 in NUMERIC_TYPES:
                v2 = v1.cast(odata.edm[t2.edm_name])
                # should succeed!
                self.assertFalse(v2.is_null(), "%s -> %s is null" %
                                 (repr(v1), repr(v2)))
                if isinstance(v1, odata.IntegerValue) or \
                        isinstance(v2, odata.IntegerValue):
                    # appropriate round = truncation to integer
                    self.assertTrue(v2.value == 3, "%s -> %s is %s" %
                                    (repr(v1), repr(v2), str(v2)))
                else:
                    self.assertTrue(str(v2) == '3.75', "%s -> %s is %s" %
                                    (repr(v1), repr(v2), str(v2)))
                # the cast fails if the integer part doesn't fit into
                # the target type
                if isinstance(v2, odata.DecimalValue):
                    # no max for Decimal
                    continue
                if isinstance(v1, odata.DecimalValue):
                    # Decimal to something else
                    vmax = t1(Decimal(str(t2.MAX)) * 2)
                    v2 = vmax.cast(odata.edm[t2.edm_name])
                    self.assertTrue(v2.is_null(), "%s -> %s not null" %
                                    (str(vmax), repr(v2)))
                    vmin = t1(Decimal(str(t2.MIN - 1)) * 2)
                    v2 = vmin.cast(odata.edm[t2.edm_name])
                    self.assertTrue(v2.is_null(), "MIN(%s) -> %s not null" %
                                    (repr(vmin), repr(v2)))
                else:
                    if t2.MAX < t1.MAX:
                        vmax = t1(t1.MAX)
                        v2 = vmax.cast(odata.edm[t2.edm_name])
                        self.assertTrue(v2.is_null())
                    if t2.MIN > t1.MIN:
                        vmin = t1(t1.MIN)
                        v2 = vmin.cast(odata.edm[t2.edm_name])
                        self.assertTrue(
                            v2.is_null(), "MIN(%s) -> %s not null" %
                            (repr(vmin), repr(v2)))
        # TODO: Edm.DateTimeOffset, Edm.Duration, and Edm.TimeOfDay
        # values can be cast to the same type with a different precision
        # with appropriate rounding
        #
        # TODO: Structured types are assignable to their type or a
        # direct or indirect base type.
        #
        # TODO: collections are cast item by item
        #
        # TODO: Services MAY support structural casting of entities and
        # complex type instances to a derived type, or arbitrary
        # structured type, by assigning values of identically named
        # properties and casting them recursively. The cast fails if one
        # of the property-value casts fails or the target type contains
        # nonnullable properties that have not been assigned a value.
        #
        # Catch all: if the cast fails the cast function returns null
        for v1 in self.value_gen():
            for t2 in self.type_gen():
                # exclude Primitive -> Primitive of same type
                if isinstance(v1, odata.PrimitiveValue) and \
                        issubclass(t2.value_type, type(v1)):
                    continue
                # exclude PrimitiveType -> String
                if isinstance(v1, odata.PrimitiveValue) and \
                        issubclass(t2.value_type, odata.StringValue):
                    continue
                # exclude Numeric -> Numeric
                if isinstance(v1, odata.NumericValue) and \
                        issubclass(t2.value_type, odata.NumericValue):
                    continue
                if isinstance(v1, odata.PrimitiveValue) or \
                        issubclass(t2.value_type, odata.PrimitiveValue):
                    # primitive -> structured/collection
                    # structured/collection -> primitive
                    logging.debug("Casting value of %s to type: %s",
                                  str(t1), str(t2))
                    v2 = v1.cast(t2)
                    self.assertTrue(v2.is_null(), "%s -> %s not null" %
                                    (repr(v1), repr(v2)))
                else:
                    self.fail("Unexpected cast: %s to %s" %
                              (repr(v1), repr(t2)))


class ParserTests(unittest.TestCase):

    # literals enclosed in single quotes are treated case-sensitive

    def from_str(self, cls, good, bad):
        for s in good:
            logging.debug("Parsing %s from %s", cls.__name__, repr(s))
            try:
                v = cls.from_str(s)
                self.assertTrue(v, "%s.from_str(%s) is False" %
                                (cls.__name__, repr(s)))
            except ValueError as e:
                logging.error(str(e))
                self.fail("%s.from_str(%s) failed" % (cls.__name__, repr(s)))
        for s in bad:
            try:
                cls.from_str(s)
                self.fail("%s.from_str(%s) succeeded" %
                          (cls.__name__, repr(s)))
            except ValueError:
                pass

    def test_boolean_value(self):
        """booleanValue = "true" / "false" """
        v = odata.BooleanValue.from_str("true")
        self.assertTrue(v.value is True)
        v = odata.BooleanValue.from_str("false")
        self.assertTrue(v.value is False)
        good = ("True", "TRUE", "False", "FALSE")
        bad = ('1', '0', 'yes', 'no', ' true', 'true ', "'true'", "null", "")
        self.from_str(odata.BooleanValue, good, bad)

    def test_guid_value(self):
        """guidValue =  8HEXDIG "-" 4HEXDIG "-" 4HEXDIG "-" 4HEXDIG "-"
                        12HEXDIG"""
        v = odata.GuidValue.from_str("00000000-0000-0000-0000-00000000002A")
        self.assertTrue(v.value == uuid.UUID(int=42))
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
        self.from_str(odata.GuidValue, good, bad)

    def test_duration_value(self):
        """durationValue = [ sign ] "P" [ 1*DIGIT "D" ]
                [ "T" [ 1*DIGIT "H" ] [ 1*DIGIT "M" ]
                 [ 1*DIGIT [ "." 1*DIGIT ] "S" ] ]"""
        v = odata.DurationValue.from_str("-P3DT1H4M1.5S")
        self.assertTrue(v.value.sign == -1)
        self.assertTrue(v.value.years == 0)
        self.assertTrue(v.value.months == 0)
        self.assertTrue(v.value.weeks is None)
        self.assertTrue(v.value.days == 3)
        self.assertTrue(v.value.hours == 1)
        self.assertTrue(v.value.minutes == 4)
        self.assertTrue(v.value.seconds == 1.5)
        good = (
            "P", "+P", "PT1S", "PT1.1S", "P1D",
            )
        bad = (
            "", "P1H", "1H", "P1D1H", "P1DT1M1H", "1S",
            )
        self.from_str(odata.DurationValue, good, bad)

    def test_date_value(self):
        """dateValue = year "-" month "-" day

        year  = [ "-" ] ( "0" 3DIGIT / oneToNine 3*DIGIT )
        month = "0" oneToNine
              / "1" ( "0" / "1" / "2" )
        day   = "0" oneToNine
              / ( "1" / "2" ) DIGIT
              / "3" ( "0" / "1" )"""
        v = odata.DateValue.from_str("0000-01-01")
        self.assertTrue(v.value.get_xcalendar_day() == (False, 0, 0, 1, 1))
        v = odata.DateValue.from_str("-0999-01-01")
        self.assertTrue(v.value.get_xcalendar_day() == (True, 9, 99, 1, 1))
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
        self.from_str(odata.DateValue, good, bad)

    def test_date_time_offset_value(self):
        """dateTimeOffsetValue =
            year "-" month "-" day "T" hour ":" minute
            [ ":" second [ "." fractionalSeconds ] ]
            ( "Z" / sign hour ":" minute )

        hour   = ( "0" / "1" ) DIGIT / "2" ( "0" / "1" / "2" / "3" )
        minute = zeroToFiftyNine
        second = zeroToFiftyNine
        fractionalSeconds = 1*12DIGIT"""
        v = odata.DateTimeOffsetValue.from_str("0000-01-01T00:00:00Z")
        self.assertTrue(v.value.get_xcalendar_time_point() ==
                        (False, 0, 0, 1, 1, 0, 0, 0))
        self.assertTrue(v.value.get_zone() == (0, 0))
        v = odata.DateTimeOffsetValue.from_str("-0752-04-21T16:00:00+01:00")
        self.assertTrue(v.value.get_xcalendar_time_point() ==
                        (True, 7, 52, 4, 21, 16, 0, 0))
        self.assertTrue(v.value.get_zone() == (1, 60))
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
        self.from_str(odata.DateTimeOffsetValue, good, bad)

    def test_time_of_day_value(self):
        """timeOfDayValue = hour ":" minute
                            [ ":" second [ "." fractionalSeconds ] ]"""
        v = odata.TimeOfDayValue.from_str("00:00:00")
        self.assertTrue(v.value.get_time() == (0, 0, 0))
        self.assertTrue(v.value.get_zone() == (None, None))
        v = odata.TimeOfDayValue.from_str("00:00")
        self.assertTrue(v.value.get_time() == (0, 0, 0))
        self.assertTrue(v.value.get_zone() == (None, None))
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
        self.from_str(odata.TimeOfDayValue, good, bad)

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
            p = odata.ODataParser(src)
            try:
                v = p.require_enum_value()
            except ValueError as err:
                self.fail("%s raised %s" % (src, str(err)))
            self.assertTrue(v == value, "failed to parse %s" % src)
            p.require_end()
        for src in bad:
            p = odata.ODataParser(src)
            try:
                v = p.require_enum_value()
                p.require_end()
                self.fail("%s validated for enumValue" % repr(src))
            except ValueError:
                pass

    def test_decimal_value(self):
        """decimalValue = [SIGN] 1*DIGIT ["." 1*DIGIT]"""
        v = odata.DecimalValue.from_str("3.14")
        self.assertTrue(v.value == Decimal('3.14'))
        v = odata.DecimalValue.from_str("-02.0")
        self.assertTrue(v.value == Decimal('-2'))
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
        self.from_str(odata.DecimalValue, good, bad)

    def test_double_value(self):
        """doubleValue = decimalValue [ "e" [SIGN] 1*DIGIT ] / nanInfinity
            nanInfinity = 'NaN' / '-INF' / 'INF'
        """
        v = odata.DoubleValue.from_str("3.14")
        self.assertTrue(v.value == 3.14)
        v = odata.DoubleValue.from_str("-02.0")
        self.assertTrue(v.value == -2.0)
        v = odata.DoubleValue.from_str("3.14e8")
        self.assertTrue(v.value == 3.14e8)
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
        self.from_str(odata.DoubleValue, good, bad)
        self.from_str(odata.SingleValue, good, bad)

    def test_sbyte_value(self):
        """decimalValue = [ sign ] 1*3DIGIT"""
        v = odata.SByteValue.from_str("+123")
        self.assertTrue(v.value == 123)
        v = odata.SByteValue.from_str("-9")
        self.assertTrue(v.value == -9)
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
        self.from_str(odata.SByteValue, good, bad)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(levelname)s %(message)s")
    unittest.main()
