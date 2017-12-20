#! /usr/bin/env python

from decimal import Decimal, getcontext
import logging
import unittest
import weakref

from pyslet.odata4 import (
    data,
    errors,
    model,
    names,
    types,
    )
from pyslet.py2 import (
    to_text,
    )
from pyslet import rfc2396 as uri


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(AnnotationsTests, 'test'),
        unittest.makeSuite(AnnotationTests, 'test'),
        unittest.makeSuite(AnnotatableTests, 'test'),
        unittest.makeSuite(TermTests, 'test'),
        unittest.makeSuite(NominalTypeTests, 'test'),
        unittest.makeSuite(CollectionTypeTests, 'test'),
        unittest.makeSuite(PrimitiveTypeTests, 'test'),
        unittest.makeSuite(StructuredTypeTests, 'test'),
        unittest.makeSuite(SystemQueryTests, 'test'),
        ))


class AnnotationsTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.em = model.EntityModel()
        self.s = model.Schema()
        self.s.declare(self.em, "Vocab")
        self.term = types.Term()
        self.term.declare(self.s, "Description")
        self.term.set_type(model.edm['String'])
        self.s.close()
        self.em.close()

    def test_constructor(self):
        # annotations (table of Annotation keyed on TermRef)
        atable = types.Annotations()
        self.assertTrue(len(atable) == 0, "No annotations initially")

    def test_annotations_checks(self):
        aa = types.Annotations()
        # name must be a TermRef, type is Annotation
        a = types.NominalType(value_type=data.Value)
        try:
            aa[names.TermRef.from_str("@Vocab.Description")] = a
            self.fail("check_type failed")
        except NotImplementedError:
            self.fail("check_name or check_value not implemented")
        except TypeError:
            # correct, that was a reference but a bad value
            pass
        try:
            aa.check_name(None)
            self.fail("Annotations.check_name accepted None")
        except ValueError:
            pass
        try:
            aa.check_name("Vocab.Description")
            self.fail("Annotations.check_name accepted str")
        except ValueError:
            pass
        a = types.Annotation(self.term)
        try:
            a.declare(aa, names.TermRef.from_str("@Vocab.Description"))
        except ValueError:
            self.fail("Good name raised ValueError")
        except TypeError:
            self.fail("Good name and type raised TypeError")
        self.assertTrue(a.name == (("Vocab", "Description"), None))
        self.assertTrue(a.qname == "@Vocab.Description")

    def test_annotations_qname(self):
        aa = types.Annotations()
        t = names.TermRef.from_str("@Vocab.Description")
        self.assertTrue(aa.qualify_name(t) == "@Vocab.Description")

    def test_qualified_get(self):
        aa = types.Annotations()
        a = types.Annotation(self.term)
        qa = types.Annotation(self.term, qualifier="en")
        self.assertTrue(aa.qualified_get("Vocab.Description") is None)
        self.assertTrue(
            aa.qualified_get("Vocab.Description", "") is None)
        self.assertTrue(
            aa.qualified_get("Vocab.Description", "", qa) is qa)
        a.declare(aa, names.TermRef.from_str("@Vocab.Description"))
        self.assertTrue(aa.qualified_get("Vocab.Description") is a)
        self.assertTrue(
            aa.qualified_get("Vocab.Description", "") is a)
        self.assertTrue(
            aa.qualified_get("Vocab.Description", "", qa) is a)
        self.assertTrue(
            aa.qualified_get("Vocab.Description", "en", qa) is qa)
        qa.declare(aa, names.TermRef.from_str("@Vocab.Description#en"))
        self.assertTrue(
            aa.qualified_get("Vocab.Description") is a)
        self.assertTrue(
            aa.qualified_get("Vocab.Description", "en") is qa)


class AnnotationTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.em = model.EntityModel()
        self.s = model.Schema()
        self.s.declare(self.em, "Vocab")
        self.term = types.Term()
        self.term.declare(self.s, "Description")
        self.term.set_type(model.edm['String'])
        self.s.close()
        self.em.close()
        self.undeclared_term = types.Term()
        self.undeclared_term.set_type(model.edm['String'])

    def test_constructor(self):
        a = types.Annotation(self.term)
        self.assertTrue(isinstance(a.term, weakref.ref))
        self.assertTrue(a.term() is self.term, "defining term")
        self.assertTrue(a.qualifier is None, "qualifier is optional")
        # The expression will evaluate to the default value later
        self.assertTrue(a.expression is None)
        a = types.Annotation(self.term, "en")
        self.assertTrue(a.term() is self.term, "defining term")
        self.assertTrue(a.qualifier == "en", "qualifier specified")
        self.assertTrue(a.expression is None)

    def test_expression(self):
        a = types.Annotation(self.term)
        e = types.LiteralExpression(None)
        a.set_expression(e)
        self.assertTrue(a.expression is e)

    def test_ref(self):
        a = types.Annotation(self.term)
        tref = a.get_term_ref()
        self.assertTrue(isinstance(tref, names.TermRef))
        self.assertTrue(to_text(tref) == "@Vocab.Description")
        a = types.Annotation(self.term, "en")
        tref = a.get_term_ref()
        self.assertTrue(to_text(tref) == "@Vocab.Description#en")
        vocab_desc = names.TermRef.from_str("@Vocab.Description")
        vocab_desc_tab = names.TermRef.from_str("@Vocab.Description#Tablet")
        a = types.Annotation.from_term_ref(vocab_desc, self.em)
        self.assertTrue(a.term() is self.term)
        self.assertTrue(a.qualifier is None)
        a = types.Annotation.from_term_ref("@Vocab.Description", self.em)
        self.assertTrue(a.term() is self.term)
        self.assertTrue(a.qualifier is None)
        a = types.Annotation.from_term_ref(vocab_desc_tab, self.em)
        self.assertTrue(a.term() is self.term)
        self.assertTrue(a.qualifier == "Tablet")

    def test_declare(self):
        aa = types.Annotations()
        vocab_desc = names.TermRef.from_str("@Vocab.Description")
        vocab_desc_tab = names.TermRef.from_str("@Vocab.Description#Tablet")
        # check that the term declaration is required
        try:
            a = types.Annotation(self.undeclared_term, "Tablet")
            self.fail("Undeclared terms can't be used")
        except ValueError:
            pass
        a = types.Annotation(self.term, "Tablet")
        try:
            a.declare(aa, vocab_desc)
            self.fail("Name is automatic, no aliases allowed")
        except ValueError:
            pass
        a.declare(aa, vocab_desc_tab)
        self.assertTrue(len(aa) == 1)
        self.assertTrue(aa[vocab_desc_tab] is a)
        # an unqualified name goes in with an empty string qualifier
        ua = types.Annotation(self.term)
        # name defaults
        ua.declare(aa)
        self.assertTrue(len(aa) == 2)
        self.assertTrue(aa[vocab_desc] is ua)
        # you can't declare a qualified name twice
        da = types.Annotation(self.term, "Tablet")
        try:
            da.declare(aa)
            self.fail("Duplicate qualified annotation")
        except errors.DuplicateNameError:
            pass
        # test the lookup
        self.assertTrue(aa.qualified_get('Vocab.Description') is ua)
        self.assertTrue(aa.qualified_get('Vocab.Description', 'Tablet') is a)
        self.assertTrue(aa.qualified_get('Vocab.Description',
                        ('Tablet', '')) is a)
        self.assertTrue(aa.qualified_get('Vocab.Description',
                        ('', 'Tablet')) is ua)
        self.assertTrue(aa.qualified_get('Vocab.Description', 'Phone') is
                        None)
        self.assertTrue(aa.qualified_get('Vocab.Description', 'Phone', a) is a)
        self.assertTrue(aa.qualified_get('Vocab.Description',
                                         ('Phone', 'Desktop'), a) is a)

    def test_split_json(self):
        try:
            types.Annotation.split_json_name("Vocab.Description")
            self.fail("name must contain '@'")
        except ValueError:
            pass
        target, term_ref = types.Annotation.split_json_name(
            "@Vocab.Description")
        self.assertTrue(target is None)
        self.assertTrue(isinstance(term_ref, names.TermRef))
        self.assertTrue(term_ref.name.namespace == "Vocab")
        self.assertTrue(term_ref.name.name == "Description")
        self.assertTrue(term_ref.qualifier is None)
        a = types.Annotation.from_term_ref(term_ref, self.em)
        # no target, no qualifier
        self.assertTrue(a.name is None, "undeclared")
        self.assertTrue(a.term() is self.term, "defining term")
        self.assertTrue(a.qualifier is None, "no qualifier")
        self.assertTrue(a.expression is None)
        target, term_ref = types.Annotation.split_json_name(
            "@Vocab.Description#en")
        self.assertTrue(target is None)
        self.assertTrue(term_ref.name.namespace == "Vocab")
        self.assertTrue(term_ref.name.name == "Description")
        self.assertTrue(term_ref.qualifier == "en")
        a = types.Annotation.from_term_ref(term_ref, self.em)
        self.assertTrue(a.name is None, "undeclared")
        self.assertTrue(a.term() is self.term, "defining term")
        self.assertTrue(a.qualifier == "en", "qualifier present")
        target, term_ref = types.Annotation.split_json_name(
            "Primitive@Vocab.Description")
        self.assertTrue(target == "Primitive")
        self.assertTrue(term_ref.name.namespace == "Vocab")
        self.assertTrue(term_ref.name.name == "Description")
        self.assertTrue(term_ref.qualifier is None)
        target, term_ref = types.Annotation.split_json_name(
            "Primitive@Vocab.Description#en")
        self.assertTrue(target == "Primitive")
        self.assertTrue(term_ref.name.namespace == "Vocab")
        self.assertTrue(term_ref.name.name == "Description")
        self.assertTrue(term_ref.qualifier == "en")
        a = types.Annotation.from_term_ref(term_ref, self.em)
        self.assertTrue(a.name is None, "undeclared")
        self.assertTrue(a.term() is self.term, "defining term")
        self.assertTrue(a.qualifier == "en", "qualifier present")
        target, term_ref = types.Annotation.split_json_name(
            "Primitive@Vocab.Unknown#en")
        self.assertTrue(target == "Primitive")
        self.assertTrue(term_ref.name.namespace == "Vocab")
        self.assertTrue(term_ref.name.name == "Unknown")
        self.assertTrue(term_ref.qualifier == "en")
        a = types.Annotation.from_term_ref(term_ref, self.em)
        self.assertTrue(a is None, "Undefined Term")


class AnnotatableTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.em = model.EntityModel()
        self.s = model.Schema()
        self.s.declare(self.em, "Vocab")
        self.term = types.Term()
        self.term.declare(self.s, "Description")
        self.term.set_type(model.edm['String'])
        self.s.close()
        self.em.close()

    def test_constructors(self):
        # annotatable object
        annotated = types.Annotatable()
        self.assertTrue(isinstance(annotated.annotations, types.Annotations))
        self.assertTrue(len(annotated.annotations) == 0)
        # annotation
        try:
            types.Annotation(None)
            self.fail("No term")
        except ValueError:
            pass

    def test_annotate(self):
        vocab_desc = names.TermRef.from_str("@Vocab.Description")
        vocab_desc_en = names.TermRef.from_str("@Vocab.Description#en")
        # start with a simple annotatable object
        x = types.Annotatable()
        a = types.Annotation.from_term_ref(vocab_desc, self.em)
        x.annotate(a)
        self.assertTrue(
            x.annotations.qualified_get('Vocab.Description') is a)
        qa = types.Annotation.from_term_ref(vocab_desc_en, self.em)
        x.annotate(qa)
        self.assertTrue(
            x.annotations.qualified_get("Vocab.Description") is a)
        self.assertTrue(
            x.annotations.qualified_get("Vocab.Description", "en") is qa)
        qa2 = types.Annotation.from_term_ref(vocab_desc_en, self.em)
        try:
            x.annotate(qa2)
            self.fail("Duplicate annotations")
        except errors.DuplicateNameError:
            pass


class TermTests(unittest.TestCase):

    def test_constructor(self):
        t = types.Term()
        self.assertTrue(t.type_def is None)
        t.set_type(model.edm['String'])
        self.assertTrue(t.type_def is model.edm['String'])
        self.assertTrue(t.base is None)
        bt = types.Term()
        t.set_base(bt)
        self.assertTrue(t.base is bt)
        self.assertTrue(t.nullable is True)
        t.set_nullable(False)
        self.assertTrue(t.nullable is False)
        self.assertTrue(t.default_value is None)
        t.set_default(t.type_def("Hello"))
        self.assertTrue(t.default_value.get_value() == "Hello")
        self.assertTrue(t.applies_to == [])
        t.set_applies_to(["EntityType", "EntitySet"])
        self.assertTrue(t.applies_to == ["EntityType", "EntitySet"])

    def test_default(self):
        t = types.Term()
        t.set_type(model.edm['String'])
        t.set_default(t.type_def("Hello"))
        v = t.get_default()
        self.assertTrue(v.get_value() == "Hello")
        self.assertTrue(v is not t.default_value, "get_default copy")


class MockValue(object):

    def __init__(self, type_def):
        self.type_def = type_def
        self.value = None

    @classmethod
    def collection_class(cls):
        return MockCollectionValue

    @classmethod
    def singleton_class(cls):
        return MockSingletonValue

    @classmethod
    def entity_set_class(cls):
        return MockEntitySetValue

    def set_value(self, value):
        self.value = value


class MockCollectionValue(MockValue):
    pass


class MockSingletonValue(MockValue):
    pass


class MockEntitySetValue(MockValue):
    pass


class DerivedType(types.NominalType):
    pass


class MockEntityModel(names.QNameTable):

    def check_value(self, value):
        pass


class MockSchema(names.NameTable):

    def check_name(self, name):
        names.simple_identifier_from_str(name)

    def check_value(self, value):
        pass


class MockService(object):
    pass


class NominalTypeTests(unittest.TestCase):

    def test_constructor(self):
        n = types.NominalType(value_type=MockValue)
        self.assertTrue(n.base is None)
        self.assertTrue(n.value_type is MockValue)
        self.assertTrue(n.abstract is False)
        self.assertTrue(n.abstract is False)
        # callable, returns a null of type n
        v = n()
        self.assertTrue(isinstance(v, MockValue))
        self.assertTrue(v.type_def is n, n)
        self.assertTrue(v.value is None)
        # callable, with optional value
        v = n("Hello")
        self.assertTrue(v.type_def, n)
        self.assertTrue(v.value == "Hello")
        # null value type is not callable
        n = types.NominalType(value_type=None)
        try:
            n()
            self.fail("Value created from abstract type")
        except errors.ODataError:
            pass

    def test_str(self):
        # undeclared type, no base
        n = types.NominalType(value_type=MockValue)
        self.assertTrue(to_text(n) == "<NominalType>")
        n = DerivedType(value_type=MockValue)
        self.assertTrue(to_text(n) == "<DerivedType>")
        # declared type
        n = types.NominalType(value_type=MockValue)
        qtable = MockEntityModel()
        ntable = MockSchema()
        ntable.declare(qtable, "org.pyslet.test")
        n.declare(ntable, "MyType")
        self.assertTrue(to_text(n) == "org.pyslet.test.MyType")
        # undeclared type with base
        n2 = types.NominalType(value_type=MockValue)
        n2.set_base(n)
        self.assertTrue(to_text(n2) == "org.pyslet.test.MyType")

    def test_derive(self):
        n = types.NominalType(value_type=MockValue)
        n2 = n.derive_type()
        self.assertTrue(isinstance(n2, types.NominalType))
        self.assertTrue(n2.base is n)
        self.assertTrue(n2.value_type is MockValue)
        self.assertTrue(n2.abstract is False)
        self.assertTrue(n2.service_ref is None)

    def test_namespace_declare(self):
        qtable = MockEntityModel()
        ns = MockSchema()
        ns.declare(qtable, "org.pyslet.test")
        # abstract class...
        n = types.NominalType(value_type=MockValue)
        try:
            n.get_qname()
            self.fail("Undeclared type returned QName")
        except errors.ObjectNotDeclaredError:
            pass
        # This should work fine!
        n.declare(ns, "Hello")
        self.assertTrue(n.name == "Hello", "Declaration OK")
        self.assertTrue(n.qname == "org.pyslet.test.Hello", "qname calculated")
        self.assertTrue(ns["Hello"] is n, "Can look-up value")
        qname = n.get_qname()
        self.assertTrue(qname.namespace == "org.pyslet.test")
        self.assertTrue(qname.name == "Hello")
        msg = ""
        try:
            n.declare(ns, "+Hello")
            self.fail("Named.declare with bad name")
        except ValueError as err:
            msg = to_text(err)
        self.assertTrue(errors.Requirement.type_name in msg)
        n.declare(ns, "_Hello")
        self.assertTrue(len(ns) == 2)
        self.assertTrue(n.nametable is not None, "nametable set on declare")
        self.assertTrue(n.nametable() is ns, "nametable callable (weakref)")
        # our QualifiedName should still be the original...
        qname = n.get_qname()
        self.assertTrue(qname.namespace == "org.pyslet.test")
        self.assertTrue(qname.name == "Hello")

    def test_abstract(self):
        n = types.NominalType(value_type=MockValue)
        self.assertTrue(n.abstract is False)
        n.set_abstract(False)
        self.assertTrue(n.abstract is False)
        n.set_abstract(True)
        self.assertTrue(n.abstract is True)
        n2 = types.NominalType(value_type=MockValue)
        self.assertTrue(n2.abstract is False)
        # you can derive a concrete type from an abstract one
        n2.set_base(n)
        self.assertTrue(n2.abstract is False)
        # and make it abstract
        n2.set_abstract(True)
        self.assertTrue(n2.abstract is True)
        # but if you derive a type from a concrete type it's got to be
        # concrete
        n = types.NominalType(value_type=MockValue)
        n2 = types.NominalType(value_type=MockValue)
        n2.set_base(n)
        try:
            n2.set_abstract(True)
            self.fail("Concrete base for abstract Type")
        except errors.ModelError:
            pass
        n = types.NominalType(value_type=MockValue)
        n2 = types.NominalType(value_type=MockValue)
        n2.set_abstract(True)
        try:
            n2.set_base(n)
            self.fail("Concrete base for abstract Type")
        except errors.ModelError:
            pass
        # you can't change the abstract status of a type once it's
        # declared
        ns = MockSchema()
        n = types.NominalType(value_type=MockValue)
        n.declare(ns, "Hello")
        self.assertTrue(n.abstract is False)
        try:
            n.set_abstract(False)
            self.fail("set_abstract after declaration")
        except errors.ModelError:
            pass

    def test_base(self):
        # check for cycles
        n = types.NominalType(value_type=MockValue)
        n2 = n.derive_type()
        try:
            n.set_base(n2)
            self.fail("Inheritence cycle")
        except errors.ModelError:
            pass

        class TypeA(types.NominalType):
            pass

        class TypeB(types.NominalType):
            pass

        n = types.NominalType(value_type=MockValue)
        a = TypeA(value_type=MockValue)
        # this is OK
        a.set_base(n)
        a = TypeA(value_type=MockValue)
        b = TypeB(value_type=MockValue)
        # this is not OK
        try:
            b.set_base(a)
            self.fail("Incompatible type implementations")
        except TypeError:
            pass

        class ValueA(MockValue):
            pass

        class ValueB(MockValue):
            pass

        n = types.NominalType(value_type=ValueA)
        n2 = types.NominalType(value_type=MockValue)
        n2.set_base(n)
        # our value_type implementation should be updated
        self.assertTrue(n2.value_type is ValueA)
        # the other way around is OK but isn't updated
        n = types.NominalType(value_type=MockValue)
        n2 = types.NominalType(value_type=ValueA)
        n2.set_base(n)
        self.assertTrue(n2.value_type is ValueA)
        # but incompatible value implementations is TypeError
        a = types.NominalType(value_type=ValueA)
        b = types.NominalType(value_type=ValueB)
        try:
            b.set_base(a)
            self.fail("Incompatible value implementations")
        except TypeError:
            pass

    def test_derived_from(self):
        n1 = types.NominalType(value_type=MockValue)
        n2 = n1.derive_type()
        n3 = n2.derive_type()
        self.assertTrue(n2.is_derived_from(n1))
        self.assertTrue(n3.is_derived_from(n1))
        self.assertFalse(n1.is_derived_from(n2))
        self.assertTrue(n1.is_derived_from(n1))
        self.assertTrue(n3.is_derived_from(n3))
        # now check strict mode
        self.assertTrue(n2.is_derived_from(n1, strict=True))
        self.assertTrue(n3.is_derived_from(n1, True))
        self.assertFalse(n1.is_derived_from(n2, True))
        self.assertFalse(n1.is_derived_from(n1, True))
        self.assertFalse(n3.is_derived_from(n3, True))

    def test_bases(self):
        n1 = types.NominalType(value_type=MockValue)
        n2 = n1.derive_type()
        n3 = n2.derive_type()
        bases = [n for n in n1.bases()]
        self.assertTrue(len(bases) == 1)
        self.assertTrue(bases[0] is n1)
        bases = [n for n in n2.bases()]
        self.assertTrue(len(bases) == 2)
        self.assertTrue(bases[0] is n2)
        self.assertTrue(bases[1] is n1)
        bases = [n for n in n3.bases()]
        self.assertTrue(len(bases) == 3)
        self.assertTrue(bases[0] is n3)
        self.assertTrue(bases[1] is n2)
        self.assertTrue(bases[2] is n1)
        # check the common ancestor
        self.assertTrue(n1.common_ancestor(n1) is n1)
        self.assertTrue(n1.common_ancestor(n2) is n1)
        self.assertTrue(n2.common_ancestor(n1) is n1)
        self.assertTrue(n1.common_ancestor(n3) is n1)
        self.assertTrue(n3.common_ancestor(n1) is n1)
        p2 = n1.derive_type()
        self.assertTrue(p2.common_ancestor(n2) is n1)
        self.assertTrue(n2.common_ancestor(p2) is n1)
        self.assertTrue(p2.common_ancestor(n3) is n1)
        self.assertTrue(n3.common_ancestor(p2) is n1)
        p3 = n2.derive_type()
        self.assertTrue(p3.common_ancestor(p2) is n1)
        self.assertTrue(p2.common_ancestor(p3) is n1)
        p4 = n2.derive_type()
        self.assertTrue(p3.common_ancestor(p4) is n2)
        self.assertTrue(p4.common_ancestor(p3) is n2)
        q1 = types.NominalType(value_type=MockValue)
        self.assertTrue(p4.common_ancestor(q1) is None)
        self.assertTrue(q1.common_ancestor(p4) is None)

    def test_declared_bases(self):
        qtable = MockEntityModel()
        ns = MockSchema()
        ns.declare(qtable, "org.pyslet.test")
        db = types.NominalType(value_type=MockValue)
        db.declare(ns, "DeclaredBase")
        dd_db = db.derive_type()
        dd_db.declare(ns, "DeclaredDerived")
        undd_db = db.derive_type()
        undb = types.NominalType(value_type=MockValue)
        undd_undb = undb.derive_type()
        bases = [n for n in db.declared_bases()]
        self.assertTrue(len(bases) == 1)
        self.assertTrue(bases[0] is db)
        self.assertTrue(db.declared_base() is db)
        bases = [n for n in dd_db.declared_bases()]
        self.assertTrue(len(bases) == 2)
        self.assertTrue(bases[0] is dd_db)
        self.assertTrue(bases[1] is db)
        self.assertTrue(dd_db.declared_base() is dd_db)
        bases = [n for n in undd_db.declared_bases()]
        self.assertTrue(len(bases) == 1)
        self.assertTrue(bases[0] is db)
        self.assertTrue(undd_db.declared_base() is db)
        bases = [n for n in undb.declared_bases()]
        self.assertTrue(len(bases) == 0)
        self.assertTrue(undb.declared_base() is None)
        bases = [n for n in undd_undb.declared_bases()]
        self.assertTrue(len(bases) == 0)
        self.assertTrue(undd_undb.declared_base() is None)

    def test_derived_types(self):
        qtable1 = MockEntityModel()
        qtable2 = MockEntityModel()
        ns1 = MockSchema()
        ns1.declare(qtable1, "org.pyslet.test1")
        ns1.declare(qtable2, "org.pyslet.test1")
        ns2 = MockSchema()
        ns2.declare(qtable2, "org.pyslet.test2")
        t1 = types.NominalType(value_type=MockValue)
        t1.declare(ns1, "T1")
        t2 = t1.derive_type()
        t2.declare(ns1, "T2")
        t3 = t1.derive_type()
        t3.declare(ns2, "T3")
        # no context
        tlist = [to_text(t) for t in t1.derived_types()]
        self.assertTrue(tlist == ["org.pyslet.test1.T2"], repr(tlist))
        tlist = sorted(
            [to_text(t) for t in t1.derived_types(context=qtable2)])
        self.assertTrue(
            tlist == ["org.pyslet.test1.T2", "org.pyslet.test2.T3"],
            repr(tlist))

    def test_compatibility(self):
        n1 = types.NominalType(value_type=MockValue)
        self.assertTrue(n1.compatible(n1))
        n2 = n1.derive_type()
        self.assertTrue(n1.compatible(n2))
        self.assertTrue(n2.compatible(n1))
        p1 = types.NominalType(value_type=MockValue)
        self.assertFalse(p1.compatible(n1))
        self.assertFalse(p1.compatible(n2))

    def test_model(self):
        n1 = types.NominalType(value_type=MockValue)
        self.assertTrue(n1.get_model() is None)
        ns = MockSchema()
        n1.declare(ns, "TypeA")
        self.assertTrue(n1.get_model() is None)
        n2 = n1.derive_type()
        self.assertTrue(n2.get_model() is None)
        qtable = MockEntityModel()
        ns = MockSchema()
        ns.declare(qtable, "org.pyslet.test")
        n1 = types.NominalType(value_type=MockValue)
        n1.declare(ns, "TypeA")
        self.assertTrue(n1.get_model() is qtable)
        n2 = n1.derive_type()
        self.assertTrue(n2.get_model() is qtable)

    def test_fragment(self):
        n1 = types.NominalType(value_type=MockValue)
        # undeclared types raise an error
        try:
            n1.get_odata_type_fragment()
            self.fail("undeclared type fragment")
        except errors.ObjectNotDeclaredError:
            pass
        qtable = MockEntityModel()
        ns = MockSchema()
        ns.declare(qtable, "org.pyslet.test")
        n1.declare(ns, "TypeA")
        # declared types return the type name...
        self.assertTrue(
            n1.get_odata_type_fragment() == "#org.pyslet.test.TypeA")
        # ...unless they are in the Edm namespace!
        edm = MockSchema()
        edm.declare(qtable, "Edm")
        n2 = types.NominalType(value_type=MockValue)
        n2.declare(edm, "TypeB")
        self.assertTrue(
            n2.get_odata_type_fragment() == "#TypeB")
        # an undeclared type derived from a declared type returns the
        # fragment for the base
        n3 = n1.derive_type()
        self.assertTrue(
            n3.get_odata_type_fragment() == "#org.pyslet.test.TypeA")
        # but abstract types are not allowed
        n4 = types.NominalType(value_type=MockValue)
        n4.set_abstract(True)
        n4.declare(ns, "TypeD")
        try:
            n4.get_odata_type_fragment()
            self.fail("abstract type fragment")
        except errors.ODataError:
            pass

    def test_binding(self):
        n = types.NominalType(value_type=MockValue)
        s = MockService()
        sref = weakref.ref(s)
        n.bind_to_service(sref)
        self.assertTrue(n.service_ref() is s)
        # you can't double bind...
        s2 = MockService()
        sref2 = weakref.ref(s2)
        try:
            n.bind_to_service(sref2)
            self.fail("double service bind")
        except errors.ModelError:
            pass
        self.assertTrue(n.service_ref() is s)

    def test_url(self):
        s1 = MockService()
        sref1 = weakref.ref(s1)
        s1.context_base = uri.URI.from_octets(
            "http://www.example.com/service1/$metadata")
        s2 = MockService()
        s2.context_base = uri.URI.from_octets(
            "http://www.example.com/service2/$metadata")
        qtable = MockEntityModel()
        ns = MockSchema()
        ns.declare(qtable, "org.pyslet.test")
        n1 = types.NominalType(value_type=MockValue)
        n1.declare(ns, "TypeA")
        # firstly, unbound raises an error
        try:
            n1.get_odata_type_url(s1)
            self.fail("Unbound type URL")
        except errors.ODataError:
            pass
        # bound to the same service, just the fragment
        n1.bind_to_service(sref1)
        url = n1.get_odata_type_url(s1)
        self.assertTrue(isinstance(url, uri.URI))
        self.assertTrue(to_text(url) == "#org.pyslet.test.TypeA")
        # bound to a different service, the full URL
        url = n1.get_odata_type_url(s2)
        self.assertTrue(
            to_text(url) ==
            "http://www.example.com/service1/$metadata#org.pyslet.test.TypeA")

    def test_abstract_types(self):
        # Edm namespace should contain the abstract types
        t1 = model.edm['PrimitiveType']
        self.assertTrue(t1.name == 'PrimitiveType')
        try:
            model.edm['Primitivetype']
            self.fail('case insensitive namespace look-up')
        except KeyError:
            pass
        t2 = model.edm['ComplexType']
        self.assertTrue(t2.name == 'ComplexType')
        self.assertTrue(t1 is not t2)
        t3 = model.edm['EntityType']
        self.assertTrue(t3.name == 'EntityType')
        self.assertTrue(t1 is not t3)
        self.assertTrue(t2 is not t3)


class CollectionTypeTests(unittest.TestCase):

    def test_constructor(self):
        n = types.NominalType(value_type=MockValue)
        cn = types.CollectionType(item_type=n, value_type=MockCollectionValue)
        self.assertTrue(cn.base is None)
        self.assertTrue(cn.value_type is MockCollectionValue)
        self.assertTrue(cn.abstract is False)
        self.assertTrue(cn.service_ref is None)
        self.assertTrue(cn.item_type is n)
        # you can't create a Collection of Collections!
        try:
            types.CollectionType(item_type=cn, value_type=MockCollectionValue)
            self.fail("Collection(Collection())")
        except TypeError:
            pass
        # callable, returns a null of type cn
        cv = cn()
        self.assertTrue(isinstance(cv, MockCollectionValue))
        self.assertTrue(cv.type_def is cn, cn)
        self.assertTrue(cv.value is None)
        # callable, with optional value
        cv = cn(["Hello"])
        self.assertTrue(cv.type_def, cn)
        self.assertTrue(cv.value == ["Hello"])
        # null value type is not callable
        try:
            cn = types.CollectionType(item_type=None, value_type=None)
            self.fail("CollecionValue created without item_type")
        except TypeError:
            pass

    def test_get_collection(self):
        n = types.NominalType(value_type=MockValue)
        cn = n.collection_type()
        self.assertTrue(isinstance(cn, types.CollectionType))
        self.assertTrue(cn.base is None)
        self.assertTrue(cn.value_type is MockCollectionValue)
        self.assertTrue(cn.abstract is False)
        self.assertTrue(cn.service_ref is None)
        self.assertTrue(cn.item_type is n)
        # always returns the same type
        self.assertTrue(n.collection_type() is cn)

    def test_str(self):
        # undeclared type, no base
        n = types.NominalType(value_type=MockValue)
        cn = n.collection_type()
        self.assertTrue(to_text(cn) == "Collection(<NominalType>)")
        n = DerivedType(value_type=MockValue)
        # declared type
        n = types.NominalType(value_type=MockValue)
        qtable = MockEntityModel()
        ntable = MockSchema()
        ntable.declare(qtable, "org.pyslet.test")
        n.declare(ntable, "MyType")
        cn = n.collection_type()
        self.assertTrue(to_text(cn) == "Collection(org.pyslet.test.MyType)")
        # undeclared type with base
        n2 = types.NominalType(value_type=MockValue)
        n2.set_base(n)
        cn = n.collection_type()
        self.assertTrue(to_text(cn) == "Collection(org.pyslet.test.MyType)")

    def test_derive(self):
        n = types.NominalType(value_type=MockValue)
        cn = n.collection_type()
        # you can't derive a new type from a collection
        try:
            cn.derive_type()
            self.fail("Derived type of Collection()")
        except TypeError:
            pass

    def test_declare(self):
        qtable = MockEntityModel()
        ns = MockSchema()
        ns.declare(qtable, "org.pyslet.test")
        # you can't declare a Collection type
        n = types.NominalType(value_type=MockValue)
        cn = n.collection_type()
        try:
            cn.declare(ns, "Hello")
            self.fail("Declaration of collection")
        except TypeError:
            pass
        # even if the item type is declared!
        n.declare(ns, "Hello")
        self.assertTrue(to_text(cn) == "Collection(org.pyslet.test.Hello)")
        try:
            cn.declare(ns, "CType")
            self.fail("Declaration of collection")
        except TypeError:
            pass
        try:
            cn.get_qname()
            self.fail("Qualified name of collection type")
        except errors.ObjectNotDeclaredError:
            pass

    def test_abstract(self):
        n = types.NominalType(value_type=MockValue)
        cn = n.collection_type()
        self.assertTrue(cn.abstract is False)
        cn.set_abstract(False)
        self.assertTrue(cn.abstract is False)
        # Collection types are never abstract
        try:
            cn.set_abstract(True)
            self.fail("Abstract Collection()")
        except TypeError:
            pass

    def test_base(self):
        n1 = types.NominalType(value_type=MockValue)
        n2 = n1.derive_type()
        cn1 = n1.collection_type()
        self.assertTrue(cn1.base is None)
        cn2 = n2.collection_type()
        # the relationship between n2 and n1 is mirrored by the collections
        self.assertTrue(cn2.base is cn1)
        # now repeat the test but setting the base afterwards
        n1 = types.NominalType(value_type=MockValue)
        n2 = types.NominalType(value_type=MockValue)
        cn1 = n1.collection_type()
        self.assertTrue(cn1.base is None)
        cn2 = n2.collection_type()
        self.assertTrue(cn2.base is None)
        n2.set_base(n1)
        self.assertTrue(cn2.base is cn1)
        cn2 = types.CollectionType(
            item_type=n2, value_type=MockCollectionValue)
        # you can set the base relationship yourself
        try:
            cn2.set_base(cn1)
            self.fail("explicit set_base on collection")
        except TypeError:
            pass

    def test_declared_bases(self):
        qtable = MockEntityModel()
        ns = MockSchema()
        ns.declare(qtable, "org.pyslet.test")
        db = types.NominalType(value_type=MockValue)
        cdb = db.collection_type()
        db.declare(ns, "DeclaredBase")
        dd_db = db.derive_type()
        cdd_db = dd_db.collection_type()
        dd_db.declare(ns, "DeclaredDerived")
        undd_db = db.derive_type()
        cundd_db = undd_db.collection_type()
        undb = types.NominalType(value_type=MockValue)
        cundb = undb.collection_type()
        undd_undb = undb.derive_type()
        cundd_undb = undd_undb.collection_type()
        bases = [n for n in cdb.declared_bases()]
        self.assertTrue(len(bases) == 1)
        self.assertTrue(bases[0] is cdb)
        self.assertTrue(cdb.declared_base() is cdb)
        bases = [n for n in cdd_db.declared_bases()]
        self.assertTrue(len(bases) == 2)
        self.assertTrue(bases[0] is cdd_db)
        self.assertTrue(bases[1] is cdb)
        self.assertTrue(cdd_db.declared_base() is cdd_db)
        bases = [n for n in cundd_db.declared_bases()]
        self.assertTrue(len(bases) == 1)
        self.assertTrue(bases[0] is cdb)
        self.assertTrue(cundd_db.declared_base() is cdb)
        bases = [n for n in cundb.declared_bases()]
        self.assertTrue(len(bases) == 0)
        self.assertTrue(cundb.declared_base() is None)
        bases = [n for n in cundd_undb.declared_bases()]
        self.assertTrue(len(bases) == 0)
        self.assertTrue(cundd_undb.declared_base() is None)

    def test_derived_types(self):
        qtable1 = MockEntityModel()
        qtable2 = MockEntityModel()
        ns1 = MockSchema()
        ns1.declare(qtable1, "org.pyslet.test1")
        ns1.declare(qtable2, "org.pyslet.test1")
        ns2 = MockSchema()
        ns2.declare(qtable2, "org.pyslet.test2")
        t1 = types.NominalType(value_type=MockValue)
        t1.declare(ns1, "T1")
        t2 = t1.derive_type()
        t2.declare(ns1, "T2")
        t3 = t1.derive_type()
        t3.declare(ns2, "T3")
        ct1 = t1.collection_type()
        # no context
        tlist = [to_text(t) for t in ct1.derived_types()]
        self.assertTrue(
            tlist == ["Collection(org.pyslet.test1.T2)"], repr(tlist))
        tlist = sorted(
            [to_text(t) for t in ct1.derived_types(context=qtable2)])
        self.assertTrue(
            tlist == ["Collection(org.pyslet.test1.T2)",
                      "Collection(org.pyslet.test2.T3)"],
            repr(tlist))

    def test_compatibility(self):
        n1 = types.NominalType(value_type=MockValue)
        cn1 = n1.collection_type()
        self.assertTrue(cn1.compatible(cn1))
        self.assertFalse(cn1.compatible(n1))
        self.assertFalse(n1.compatible(cn1))
        n2 = n1.derive_type()
        cn2 = n2.collection_type()
        self.assertTrue(cn1.compatible(cn2))
        self.assertTrue(cn2.compatible(cn1))
        p1 = types.NominalType(value_type=MockValue)
        cp1 = p1.collection_type()
        self.assertFalse(cp1.compatible(cn1))
        self.assertFalse(cp1.compatible(cn2))

    def test_model(self):
        n1 = types.NominalType(value_type=MockValue)
        cn1 = n1.collection_type()
        self.assertTrue(cn1.get_model() is None)
        ns = MockSchema()
        n1.declare(ns, "TypeA")
        self.assertTrue(cn1.get_model() is None)
        n2 = n1.derive_type()
        cn2 = n2.collection_type()
        self.assertTrue(n2.get_model() is None)
        # now with a model...
        qtable = MockEntityModel()
        ns = MockSchema()
        ns.declare(qtable, "org.pyslet.test")
        n1 = types.NominalType(value_type=MockValue)
        cn1 = n1.collection_type()
        n1.declare(ns, "TypeA")
        self.assertTrue(cn1.get_model() is qtable)
        n2 = n1.derive_type()
        cn2 = n2.collection_type()
        self.assertTrue(cn2.get_model() is qtable)

    def test_fragment(self):
        n1 = types.NominalType(value_type=MockValue)
        cn1 = n1.collection_type()
        # undeclared types raise an error
        try:
            cn1.get_odata_type_fragment()
            self.fail("undeclared type fragment")
        except errors.ObjectNotDeclaredError:
            pass
        qtable = MockEntityModel()
        ns = MockSchema()
        ns.declare(qtable, "org.pyslet.test")
        n1.declare(ns, "TypeA")
        # declared types return Collection(<type name>) as a fragment...
        self.assertTrue(
            cn1.get_odata_type_fragment() ==
            "#Collection(org.pyslet.test.TypeA)")
        # ...even if they are in the Edm namespace! (not sure about this)
        edm = MockSchema()
        edm.declare(qtable, "Edm")
        n2 = types.NominalType(value_type=MockValue)
        cn2 = n2.collection_type()
        n2.declare(edm, "TypeB")
        self.assertTrue(
            cn2.get_odata_type_fragment() == "#Collection(Edm.TypeB)")
        # an undeclared type derived from a declared type returns the
        # fragment for the base
        n3 = n1.derive_type()
        cn3 = n3.collection_type()
        self.assertTrue(
            cn3.get_odata_type_fragment() ==
            "#Collection(org.pyslet.test.TypeA)")
        # but unlike single types, abstract collections are allowed
        n4 = types.NominalType(value_type=MockValue)
        n4.set_abstract(True)
        cn4 = n4.collection_type()
        n4.declare(ns, "TypeD")
        self.assertTrue(
            cn4.get_odata_type_fragment() ==
            "#Collection(org.pyslet.test.TypeD)")

    def test_binding(self):
        # late binding of item_type, should bind collection type too
        n = types.NominalType(value_type=MockValue)
        cn = n.collection_type()
        s = MockService()
        sref = weakref.ref(s)
        n.bind_to_service(sref)
        self.assertTrue(cn.service_ref() is s)
        # early binding of item_type, collection inherits
        n = types.NominalType(value_type=MockValue)
        s = MockService()
        sref = weakref.ref(s)
        n.bind_to_service(sref)
        cn = n.collection_type()
        self.assertTrue(cn.service_ref() is s)
        # you can't bind a collection directly
        n = types.NominalType(value_type=MockValue)
        cn = n.collection_type()
        try:
            cn.bind_to_service(sref)
            self.fail("Collection bound to service")
        except TypeError:
            pass

    def test_url(self):
        s1 = MockService()
        sref1 = weakref.ref(s1)
        s1.context_base = uri.URI.from_octets(
            "http://www.example.com/service1/$metadata")
        s2 = MockService()
        s2.context_base = uri.URI.from_octets(
            "http://www.example.com/service2/$metadata")
        qtable = MockEntityModel()
        ns = MockSchema()
        ns.declare(qtable, "org.pyslet.test")
        n1 = types.NominalType(value_type=MockValue)
        n1.declare(ns, "TypeA")
        cn1 = n1.collection_type()
        # firstly, unbound raises an error
        try:
            cn1.get_odata_type_url(s1)
            self.fail("Unbound type URL")
        except errors.ODataError:
            pass
        # bound to the same service, just the fragment
        n1.bind_to_service(sref1)
        url = cn1.get_odata_type_url(s1)
        self.assertTrue(isinstance(url, uri.URI))
        self.assertTrue(to_text(url) == "#Collection(org.pyslet.test.TypeA)")
        # bound to a different service, the full URL
        url = cn1.get_odata_type_url(s2)
        self.assertTrue(
            to_text(url) == "http://www.example.com/service1/$metadata#"
            "Collection(org.pyslet.test.TypeA)")


class PrimitiveTypeTests(unittest.TestCase):

    def test_constructor(self):
        t = types.PrimitiveType(value_type=MockValue)
        self.assertTrue(t.base is None, "No base by default")
        self.assertTrue(t.value_type is MockValue)
        self.assertTrue(t.abstract is False)
        self.assertTrue(t.abstract is False)
        self.assertTrue(t.max_length is None, "No MaxLength by default")
        self.assertTrue(t.unicode is None, "No Unicode by default")
        self.assertTrue(t.precision is None, "No Precision by default")
        self.assertTrue(t.scale is None, "No Scale by default")
        self.assertTrue(t.srid is None, "No SRID by default")

    def test_str(self):
        # undeclared type, no base
        t = types.PrimitiveType(value_type=MockValue)
        self.assertTrue(to_text(t) == "<PrimitiveType>")
        t = types.BinaryType(value_type=MockValue)
        self.assertTrue(to_text(t) == "<BinaryType>")
        t = types.StreamType(value_type=MockValue)
        self.assertTrue(to_text(t) == "<StreamType>")
        t = types.StringType(value_type=MockValue)
        self.assertTrue(to_text(t) == "<StringType>")

    def test_derive(self):
        t1 = types.PrimitiveType(value_type=MockValue)
        t2 = t1.derive_type()
        self.assertTrue(t2.max_length is None)
        self.assertTrue(t2.unicode is None)
        self.assertTrue(t2.precision is None)
        self.assertTrue(t2.scale is None)
        self.assertTrue(t2.srid is None)
        # now set the facets and check they're inherited
        t1 = types.PrimitiveType(value_type=MockValue)
        t1.set_max_length(255)
        t1.set_unicode(True)
        t1.set_precision(6, 10)
        t1.set_srid(4326)
        t2 = t1.derive_type()
        self.assertTrue(t2.max_length == 255)
        self.assertTrue(t2.unicode is True)
        self.assertTrue(t2.precision == 6)
        self.assertTrue(t2.scale == 10)
        self.assertTrue(t2.srid == 4326)

    def test_max_length(self):
        t1 = types.PrimitiveType(value_type=MockValue)
        self.assertTrue(t1.max_length is None, "No value specified")
        self.assertTrue(t1.get_max_length() == 0, "Default 0")
        try:
            t1.set_max_length(-1)
            self.fail("Negative max length")
        except ValueError:
            pass
        self.assertTrue(t1.max_length is None)
        self.assertTrue(t1.get_max_length() == 0, "Default 0")
        # 0 indicates max
        t1.set_max_length(0)
        self.assertTrue(t1.max_length == 0)
        self.assertTrue(t1.get_max_length() == 0, "Strong 0")
        # weak value is ignored
        t1.set_max_length(255, can_override=True)
        self.assertTrue(t1.max_length == 0)
        self.assertTrue(t1.get_max_length() == 0, "Strong 0")
        t2 = types.PrimitiveType(value_type=MockValue)
        t2.set_max_length(255, can_override=True)
        self.assertTrue(t2.get_max_length() == 255, "Weak 255")
        self.assertTrue(t2.max_length is None)
        t2.set_max_length(31)
        self.assertTrue(t2.get_max_length() == 31, "Strong 31")
        self.assertTrue(t2.max_length == 31)
        # strong on strong: error
        try:
            t2.set_max_length(255)
            self.fail("max_length respecified")
        except errors.ModelError:
            pass

    def test_unicode(self):
        t1 = types.PrimitiveType(value_type=MockValue)
        self.assertTrue(t1.unicode is None, "No value specified")
        self.assertTrue(t1.get_unicode() is True, "Default True")
        t1.set_unicode(False)
        self.assertTrue(t1.unicode is False)
        self.assertTrue(t1.get_unicode() is False, "Strong False")
        # weak value is ignored
        t1.set_unicode(True, can_override=True)
        self.assertTrue(t1.unicode is False)
        self.assertTrue(t1.get_unicode() is False, "Strong False")
        t2 = types.PrimitiveType(value_type=MockValue)
        t2.set_unicode(True, can_override=True)
        self.assertTrue(t2.get_unicode() is True, "Weak True")
        self.assertTrue(t2.unicode is None)
        t2.set_unicode(False)
        self.assertTrue(t2.get_unicode() is False, "Strong False")
        self.assertTrue(t2.unicode is False)
        # strong on strong: error
        try:
            t2.set_unicode(False)
            self.fail("unicode respecified")
        except errors.ModelError:
            pass

    def test_precision(self):
        t1 = types.PrimitiveType(value_type=MockValue)
        self.assertTrue(t1.precision is None, "No value specified")
        self.assertTrue(t1.scale is None, "No value specified")
        t1.set_precision(9)
        self.assertTrue(t1.precision == 9)
        self.assertTrue(t1.scale is None)
        # just scale, that should be OK
        t1.set_precision(None, 6)
        self.assertTrue(t1.precision == 9)
        self.assertTrue(t1.scale == 6)
        # and reverse...
        t2 = types.PrimitiveType(value_type=MockValue)
        t2.set_precision(None, 6)
        self.assertTrue(t2.precision is None)
        self.assertTrue(t2.scale == 6)
        t2.set_precision(9, None)
        self.assertTrue(t2.precision == 9)
        self.assertTrue(t2.scale == 6)
        # check that weak values are ignored
        t2.set_precision(10, 7, can_override=True)
        self.assertTrue(t2.precision == 9)
        self.assertTrue(t2.scale == 6)
        # and now check that weak values are replace
        t3 = types.PrimitiveType(value_type=MockValue)
        t3.set_precision(10, 7, can_override=True)
        self.assertTrue(t3.precision is None)
        self.assertTrue(t3.scale is None)
        t3.set_precision(9, 6)
        self.assertTrue(t3.precision == 9)
        self.assertTrue(t3.scale == 6)
        # strong on strong: error
        try:
            t3.set_precision(9, None)
            self.fail("Precision respecified")
        except errors.ModelError:
            pass
        try:
            t3.set_precision(None, 6)
            self.fail("Scale respecified")
        except errors.ModelError:
            pass

    def test_decimal_round(self):
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
        t = types.DecimalType(value_type=MockValue)
        self.assertTrue(t.precision is None, "No Precision by default")
        self.assertTrue(t.scale is None, "No Scale by default")
        # If no value is specified, the decimal property has unspecified
        # precision.  Python's default of 28 is larger than the 20 used
        # in these tests.  The scale property defaults to 0 only for
        # custom type definitions declared in the metadata document the
        # class itself uses the default decimal context scale
        self.assertTrue(t.round(d20) == Decimal(d20str))
        self.assertTrue(t.round(i20) == i20)
        self.assertTrue(t.round(f20) == Decimal(f20str))
        # a specified precision, unspecified scale defaults to 0
        t.set_precision(6, can_override=True)
        # these results should be rounded
        self.assertTrue(t.round(d20) == Decimal("0"))
        try:
            t.round(i20)
            self.fail("Integer larger than precision")
        except ValueError:
            pass
        # a specified precision with a variable scale
        t.set_precision(6, -1, can_override=True)
        self.assertTrue(t.round(d20) == Decimal("0.123457"))
        self.assertTrue(t.round(i20) == Decimal("12345700000000000000"))
        self.assertTrue(t.round(f20) == Decimal("1234570000"))
        # if we exceed the digits we had originally we do not add 0s as
        # this is a maximum number of digits, not an absolute number of
        # digits.
        t.set_precision(42, 21, can_override=True)
        self.assertTrue(t.round(d20) == d20)
        self.assertTrue(str(t.round(d20)) == d20str, str(t.round(d20)))
        self.assertTrue(t.round(i20) == i20)
        self.assertTrue(str(t.round(i20)) == i20str, str(t.round(i20)))
        self.assertTrue(t.round(f20) == f20)
        self.assertTrue(str(t.round(f20)) == f20str, str(t.round(f20)))
        # Unspecified precision, variable scale (uses -1)
        # sig fig limited by python defaults, decimal places unlimited
        t.set_precision(None, -1, can_override=True)
        self.assertTrue(t.round(d20) == d20)
        self.assertTrue(str(t.round(d20)) == d20str, str(t.round(d20)))
        self.assertTrue(t.round(i20) == i20)
        self.assertTrue(str(t.round(i20)) == i20str, str(t.round(i20)))
        self.assertTrue(t.round(f20) == f20)
        self.assertTrue(str(t.round(f20)) == f20str, str(t.round(f20)))
        # unspecified precision, scale is OK
        t.set_precision(None, 3, can_override=True)
        self.assertTrue(t.round(d20) == Decimal("0.123"))
        self.assertTrue(t.round(i20) == i20)
        self.assertTrue(t.round(f20) == Decimal("1234567890.123"))
        try:
            t.set_precision(2, 3, can_override=True)
            self.fail("scale must be <= precision")
        except errors.ModelError:
            pass
        # try scale > 0
        t.set_precision(6, 3, can_override=True)
        # scale beats precision
        self.assertTrue(t.round(d20) == Decimal("0.123"))
        try:
            t.round(i20)
            self.fail("Value exceeds precision-scale left digitis")
        except ValueError:
            pass
        self.assertTrue(t.round(Decimal("123.4567")) == Decimal("123.457"))
        # try scale = 0
        t.set_precision(6, 0, can_override=True)
        self.assertTrue(t.round(d20) == Decimal("0"))
        try:
            t.round(f20)
            self.fail("Value exceeds precision-scale left digitis")
        except ValueError:
            pass
        # try scale = precision
        t.set_precision(6, 6, can_override=True)
        self.assertTrue(t.round(d20) == Decimal("0.123457"))
        try:
            t.round(Decimal(1))
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
        t.set_precision(getcontext().prec + 2)
        xstr = "1" * (getcontext().prec + 2)
        self.assertTrue(t.round(Decimal(xstr)) == Decimal(xstr[:-2] + "00"))

    def test_seconds_round(self):
        i2 = 14
        t20 = 14.12345678901234567890
        t = types.TemporalSecondsType(value_type=MockValue)
        self.assertTrue(t.precision is None, "Default unspecified Precision")
        # If unspecified the precision is 0
        self.assertTrue(type(t.truncate(t20)) is int)
        self.assertTrue(type(t.truncate(i2)) is int)
        self.assertTrue(t.truncate(t20) == 14)
        self.assertTrue(t.truncate(i2) == 14)
        # set a weak value for precision
        t.set_precision(6, can_override=True)
        self.assertTrue(type(t.truncate(t20)) is float)
        self.assertTrue(type(t.truncate(i2)) is int)
        self.assertTrue("%.10f" % t.truncate(t20) == "14.1234560000")
        # set a strong value for precision
        try:
            t.set_precision(15)
            self.fail("Max temporal precision")
        except errors.ModelError:
            pass
        t.set_precision(12, can_override=True)
        # max precision is 12
        self.assertTrue("%.14f" % t.truncate(t20) == "14.12345678901200")

    def test_srid(self):
        t1 = types.PrimitiveType(value_type=MockValue)
        self.assertTrue(t1.srid is None, "No value specified")
        self.assertTrue(t1.get_srid() == -1, "Default variable")
        t1.set_srid(4326)
        self.assertTrue(t1.srid == 4326)
        self.assertTrue(t1.get_srid() == 4326, "Strong value")
        # weak value is ignored
        t1.set_srid(0, can_override=True)
        self.assertTrue(t1.srid == 4326)
        self.assertTrue(t1.get_srid() == 4326, "Weak value ignored")
        t2 = types.PrimitiveType(value_type=MockValue)
        t2.set_srid(4326, can_override=True)
        self.assertTrue(t2.get_srid() == 4326, "Weak value")
        self.assertTrue(t2.srid is None)
        t2.set_srid(-1)
        self.assertTrue(t2.get_srid() == -1, "Weak value replaced")
        self.assertTrue(t2.srid == -1)
        # strong on strong: error
        try:
            t2.set_srid(0)
            self.fail("srid respecified")
        except errors.ModelError:
            pass
        # when deriving types we have slightly different rules
        base = types.PrimitiveType(value_type=MockValue)
        t3 = types.GeometryType(value_type=MockValue)
        self.assertTrue(t3.srid is None, "No value specified")
        self.assertTrue(t3.get_srid() == 0, "Default 0")
        # when we set the base the default does not change
        t3.set_base(base)
        self.assertTrue(t3.srid is None, "No value specified")
        self.assertTrue(t3.get_srid() == 0, "Default 0")
        t4 = types.GeographyType(value_type=MockValue)
        self.assertTrue(t4.srid is None, "No value specified")
        self.assertTrue(t4.get_srid() == 4326, "Default 4326")
        # when we set the base the default does not change
        t4.set_base(base)
        self.assertTrue(t4.srid is None, "No value specified")
        self.assertTrue(t4.get_srid() == 4326, "Default 4326")


class StructuredTypeTests(unittest.TestCase):

    def test_constructor(self):
        t = types.StructuredType(value_type=MockValue)
        self.assertTrue(isinstance(t, names.NameTable))
        self.assertTrue(isinstance(t, types.NominalType))
        self.assertTrue(t.base is None)
        self.assertTrue(t.value_type is MockValue)
        self.assertTrue(t.abstract is False)
        self.assertTrue(t.service_ref is None)
        self.assertTrue(t.open_type is False)
        self.assertTrue(t.closed is False)

    def test_str(self):
        # undeclared type, no base
        n = types.StructuredType(value_type=MockValue)
        self.assertTrue(to_text(n) == "<StructuredType>")

    def test_derive(self):
        t1 = types.StructuredType(value_type=MockValue)
        t1.close()
        t2 = t1.derive_type()
        self.assertTrue(isinstance(t2, types.StructuredType))
        self.assertTrue(t2.open_type is False)
        self.assertTrue(t2.closed is False)
        # if you derive from an open type you get an open type
        t1 = types.StructuredType(value_type=MockValue)
        t1.set_open_type(True)
        t1.close()
        t2 = t1.derive_type()
        self.assertTrue(t2.open_type is True)
        self.assertTrue(t2.closed is False)
        # if the type is closed, you can still derive from it
        t1 = types.StructuredType(value_type=MockValue)
        t1.close()
        self.assertTrue(t1.closed is True)
        t2 = t1.derive_type()
        self.assertTrue(t2.closed is False)

    def test_property_declare(self):
        t1 = types.StructuredType(value_type=MockValue)
        p1 = names.Named()
        try:
            p1.declare(t1, "Dimension")
            self.fail("Plain Named instance declared in StructuredType")
        except TypeError:
            pass
        self.assertTrue(p1.qname is None)
        p2 = types.Property()
        try:
            p2.declare(t1, "Max.Dimension")
            self.fail("Property declared with bad name")
        except ValueError:
            pass
        self.assertTrue(p2.qname is None)
        p2.declare(t1, "Dimension")
        # t1 is undeclared so qname is just the property name
        self.assertTrue(p2.qname == "Dimension")
        np1 = types.NavigationProperty()
        np1.declare(t1, "Related")
        self.assertTrue(np1.qname == "Related")
        # now test the qnames with a declared type
        qtable = MockEntityModel()
        ns = MockSchema()
        ns.declare(qtable, "org.pyslet.test")
        t2 = types.StructuredType(value_type=MockValue)
        t2.declare(ns, "TypeA")
        p3 = types.Property()
        p3.declare(t2, "Dimension")
        self.assertTrue(p3.qname == "TypeA/Dimension")
        np2 = types.NavigationProperty()
        np2.declare(t2, "Related")
        self.assertTrue(np2.qname == "TypeA/Related")

    def test_abstract(self):
        # can't change abstract status after closure
        t1 = types.StructuredType(value_type=MockValue)
        t1.set_abstract(False)
        self.assertTrue(t1.abstract is False)
        t2 = types.StructuredType(value_type=MockValue)
        t2.set_abstract(True)
        self.assertTrue(t2.abstract is True)
        t3 = types.StructuredType(value_type=MockValue)
        t3.close()
        for abstract in (False, True):
            try:
                t3.set_abstract(abstract)
                self.fail("set_abstract on closed type")
            except errors.ModelError:
                pass
            self.assertTrue(t3.abstract is False)

    def test_base(self):
        # type must be incomplete when base is set
        t1 = types.StructuredType(value_type=MockValue)
        t1.close()
        t2 = types.StructuredType(value_type=MockValue)
        t2.set_base(t1)
        self.assertTrue(t2.base is t1)
        # test set_base after closure
        t3 = types.StructuredType(value_type=MockValue)
        t3.close()
        try:
            t3.set_base(t1)
            self.fail("set_base on complete StructuredType")
        except errors.ModelError:
            pass
        # test set_base with unclosed base
        t1 = types.StructuredType(value_type=MockValue)
        t2 = types.StructuredType(value_type=MockValue)
        try:
            t2.set_base(t1)
            self.fail("set_base with incomplete base")
        except errors.ModelError:
            pass
        # You can't derive a closed type from an open type not to be
        # confused with close/closed of the nametable!
        t1 = types.StructuredType(value_type=MockValue)
        t1.set_open_type(True)
        t1.close()
        t2 = types.StructuredType(value_type=MockValue)
        try:
            t2.set_base(t1)
            self.fail("closed type derived from open type")
        except errors.ModelError:
            pass

    def test_inherited_properties(self):
        # test that properties are copied over...
        t1 = types.StructuredType(value_type=MockValue)
        p1 = types.Property()
        p1.set_type(types.NominalType(value_type=MockValue))
        p1.declare(t1, "Dimension")
        t1.close()
        self.assertTrue(len(t1) == 1)
        t2 = t1.derive_type()
        self.assertFalse("Dimension" in t2)
        self.assertTrue(len(t2) == 0)
        t2.close()
        self.assertTrue("Dimension" in t2)
        self.assertTrue(len(t2) == 1)

    def test_open_type(self):
        t1 = types.StructuredType(value_type=MockValue)
        self.assertTrue(t1.open_type is False)
        t1.set_open_type(True)
        self.assertTrue(t1.open_type is True)
        t1.set_open_type(False)
        self.assertTrue(t1.open_type is False)
        # Like the abstract attribute, needs to be trustable for
        # complete types...
        t1.close()
        for state in (True, False):
            try:
                t1.set_open_type(True)
                self.fail("set_open_type on complete type")
            except errors.ModelError:
                pass
            self.assertTrue(t1.open_type is False)
        # and even on declared types!
        qtable = MockEntityModel()
        ns = MockSchema()
        ns.declare(qtable, "org.pyslet.test")
        t2 = types.StructuredType(value_type=MockValue)
        t2.declare(ns, "TypeA")
        # still incomplete...
        for state in (True, False):
            try:
                t2.set_open_type(True)
                self.fail("set_open_type on declared type")
            except errors.ModelError:
                pass
            self.assertTrue(t2.open_type is False)

    def test_properties(self):
        qtable = MockEntityModel()
        ns = MockSchema()
        ns.declare(qtable, "org.pyslet.test")
        t1 = types.StructuredType(value_type=MockValue)
        t1.declare(ns, "T1")
        # an empty type generates no properties
        plist = [p for p in t1.properties()]
        self.assertTrue(len(plist) == 0)
        # Add a simple property
        p1 = types.Property()
        p1.set_type(types.NominalType(value_type=MockValue))
        p1.declare(t1, "P1")
        # Add a complex property with simple + navigation properties
        t2 = types.ComplexType(value_type=MockValue)
        t2.declare(ns, "T2")
        p21 = types.Property()
        p21.set_type(types.NominalType(value_type=MockValue))
        p21.declare(t2, "P21")
        p22 = types.NavigationProperty()
        # contained entity with no properties!
        p22.set_type(types.EntityType(value_type=MockValue), False, True)
        p22.declare(t2, "P22")
        t2.close()
        p2 = types.Property()
        p2.set_type(t2)
        p2.declare(t1, "P2")
        t2x = t2.derive_type()
        t2x.declare(ns, "T2X")
        p2x1 = types.Property()
        p2x1.set_type(types.NominalType(value_type=MockValue))
        p2x1.declare(t2x, "P2X1")
        t2x.close()
        p2c = types.Property()
        p2c.set_type(t2.collection_type())
        p2c.declare(t1, "P2C")
        # Add 4 flavours of navigation property
        t3 = types.EntityType(value_type=MockValue)
        t3.set_abstract(True)       # to avoid having to define a key
        t3.declare(ns, "T3")
        p31 = types.Property()
        p31.set_type(types.NominalType(value_type=MockValue))
        p31.declare(t3, "P31")
        p32 = types.NavigationProperty()
        p32.set_type(t3, False, False)  # recursive
        p32.set_nullable(True)
        p32.declare(t3, "P32")
        t3.close()
        p3ff = types.NavigationProperty()
        p3ff.set_type(t3, False, False)
        p3ff.declare(t1, "P3FF")
        p3tf = types.NavigationProperty()
        p3tf.set_type(t3, True, False)
        p3tf.declare(t1, "P3TF")
        p3ft = types.NavigationProperty()
        p3ft.set_type(t3, False, True)
        p3ft.declare(t1, "P3FT")
        p3tt = types.NavigationProperty()
        p3tt.set_type(t3, True, True)
        p3tt.declare(t1, "P3TT")
        plist = [p for p in t1.properties()]
        self.assertTrue(len(plist) == 7)
        self.assertTrue(
            [names.path_to_str(p[0]) for p in plist] ==
            ["P1", "P2", "P2C", "P3FF", "P3TF", "P3FT", "P3TT"])
        for path, p in plist:
            self.assertTrue(t1[path[0]] is p)
        # now test complex expansion
        plist = [p for p in t1.properties(expand_complex=True)]
        self.assertTrue(
            [names.path_to_str(p[0]) for p in plist] ==
            ["P1", "P2", "P2/P21", "P2/P22", "P2C", "P3FF", "P3TF", "P3FT",
             "P3TT"])
        t1.close()
        t4 = t1.derive_type()
        t4.declare(ns, "T4")
        p41 = types.NavigationProperty()
        t5 = types.EntityType(value_type=MockValue)
        t5.set_abstract(True)
        t5.declare(ns, "T5")
        t5.close()
        t5x = t5.derive_type()
        t5x.set_abstract(True)
        t5x.declare(ns, "T5X")
        p5x1 = types.Property()
        p5x1.set_type(types.NominalType(value_type=MockValue))
        p5x1.declare(t5x, "P5X1")
        t5x.close()
        p41.set_type(t5, False, True)
        p41.declare(t4, "P41")
        p42 = types.Property()
        p42.set_type(types.NominalType(value_type=MockValue))
        p42.declare(t4, "P42")
        # inherited properties are added only on closure
        plist = [p for p in t4.properties()]
        self.assertTrue(len(plist) == 2)
        t4.close()
        plist = [p for p in t4.properties()]
        self.assertTrue(
            [names.path_to_str(p[0]) for p in plist] ==
            ["P1", "P2", "P2C", "P3FF", "P3TF", "P3FT", "P3TT", "P41", "P42"])
        # expand_contained
        plist = [p for p in t4.properties(expand_contained=True)]
        self.assertTrue(
            [names.path_to_str(p[0]) for p in plist] ==
            ["P1", "P2", "P2C", "P3FF", "P3TF", "P3FT", "P3FT/P31", "P3FT/P32",
             "P3TT", "P41", "P42"], plist)
        plist = [p for p in t4.properties(expand_all_nav=True)]
        self.assertTrue(
            [names.path_to_str(p[0]) for p in plist] ==
            ["P1", "P2", "P2C", "P3FF", "P3FF/P31", "P3FF/P32", "P3TF", "P3FT",
             "P3FT/P31", "P3FT/P32", "P3TT", "P41", "P42"], plist)
        plist = [p for p in t4.properties(expand_collections=True)]
        self.assertTrue(
            [names.path_to_str(p[0]) for p in plist] ==
            ["P1", "P2", "P2C", "P3FF", "P3TF", "P3FT", "P3TT", "P41", "P42"],
            plist)
        plist = [p for p in t4.properties(
            expand_complex=True, expand_collections=True)]
        self.assertTrue(
            [names.path_to_str(p[0]) for p in plist] ==
            ["P1", "P2", "P2/P21", "P2/P22", "P2C", "P2C/P21", "P2C/P22",
             "P3FF", "P3TF", "P3FT", "P3TT", "P41", "P42"], plist)
        plist = [p for p in t4.properties(
            expand_contained=True, expand_collections=True)]
        self.assertTrue(
            [names.path_to_str(p[0]) for p in plist] ==
            ["P1", "P2", "P2C", "P3FF", "P3TF", "P3FT", "P3FT/P31", "P3FT/P32",
             "P3TT", "P3TT/P31", "P3TT/P32", "P41", "P42"], plist)
        plist = [p for p in t4.properties(
            expand_all_nav=True, expand_collections=True)]
        self.assertTrue(
            [names.path_to_str(p[0]) for p in plist] ==
            ["P1", "P2", "P2C", "P3FF", "P3FF/P31", "P3FF/P32", "P3TF",
             "P3TF/P31", "P3TF/P32", "P3FT", "P3FT/P31", "P3FT/P32", "P3TT",
             "P3TT/P31", "P3TT/P32", "P41", "P42"], plist)
        plist = [p for p in t4.properties(expand_derived=qtable)]
        self.assertTrue(
            [names.path_to_str(p[0]) for p in plist] ==
            ["P1", "P2", "P2C", "P3FF", "P3TF", "P3FT", "P3TT", "P41",
             "P42"], plist)
        plist = [p for p in t4.properties(
            expand_complex=True, expand_derived=qtable)]
        self.assertTrue(
            [names.path_to_str(p[0]) for p in plist] ==
            ["P1", "P2", "P2/P21", "P2/P22", "P2/org.pyslet.test.T2X/P2X1",
             "P2C", "P3FF", "P3TF", "P3FT", "P3TT", "P41", "P42"], plist)
        plist = [p for p in t4.properties(
            expand_contained=True, expand_derived=qtable)]
        self.assertTrue(
            [names.path_to_str(p[0]) for p in plist] ==
            ["P1", "P2", "P2C", "P3FF", "P3TF", "P3FT", "P3FT/P31", "P3FT/P32",
             "P3TT", "P41", "P41/org.pyslet.test.T5X/P5X1", "P42"], plist)
        plist = [p for p in t4.properties(
            expand_all_nav=True, expand_derived=qtable)]
        self.assertTrue(
            [names.path_to_str(p[0]) for p in plist] ==
            ["P1", "P2", "P2C", "P3FF", "P3FF/P31", "P3FF/P32", "P3TF", "P3FT",
             "P3FT/P31", "P3FT/P32", "P3TT", "P41",
             "P41/org.pyslet.test.T5X/P5X1", "P42"], plist)
        plist = [p for p in t4.properties(
            expand_complex=True, expand_all_nav=True,
            expand_collections=True, expand_derived=qtable)]
        self.assertTrue(
            [names.path_to_str(p[0]) for p in plist] ==
            ["P1", "P2", "P2/P21", "P2/P22", "P2/org.pyslet.test.T2X/P2X1",
             "P2C", "P2C/P21", "P2C/P22", "P2C/org.pyslet.test.T2X/P2X1",
             "P3FF", "P3FF/P31", "P3FF/P32", "P3TF", "P3TF/P31", "P3TF/P32",
             "P3FT", "P3FT/P31", "P3FT/P32", "P3TT", "P3TT/P31", "P3TT/P32",
             "P41", "P41/org.pyslet.test.T5X/P5X1", "P42"], plist)
        plist = [p for p in t4.properties(
            expand_complex=True, expand_all_nav=True,
            expand_collections=True, expand_derived=qtable, max_depth=2)]
        self.assertTrue(
            [names.path_to_str(p[0]) for p in plist] ==
            ["P1", "P2", "P2/P21", "P2/P22", "P2/org.pyslet.test.T2X/P2X1",
             "P2C", "P2C/P21", "P2C/P22", "P2C/org.pyslet.test.T2X/P2X1",
             "P3FF", "P3FF/P31", "P3FF/P32", "P3FF/P32/P31", "P3FF/P32/P32",
             "P3TF", "P3TF/P31", "P3TF/P32", "P3TF/P32/P31", "P3TF/P32/P32",
             "P3FT", "P3FT/P31", "P3FT/P32", "P3FT/P32/P31", "P3FT/P32/P32",
             "P3TT", "P3TT/P31", "P3TT/P32", "P3TT/P32/P31", "P3TT/P32/P32",
             "P41", "P41/org.pyslet.test.T5X/P5X1", "P42"], plist)

    def test_navigation_properties(self):
        t1 = types.StructuredType(value_type=MockValue)
        # an empty type generates no navigation properties
        nps = [np for np in t1.navigation_properties(t1.properties())]
        self.assertTrue(len(nps) == 0)
        p1 = types.Property()
        p1.set_type(types.NominalType(value_type=MockValue))
        p1.declare(t1, "P1")
        nps = [np for np in t1.navigation_properties(t1.properties())]
        self.assertTrue(len(nps) == 0, "structural properties ignored")
        np1 = types.NavigationProperty()
        np1.declare(t1, "NP1")
        nps = [np for np in t1.navigation_properties(t1.properties())]
        self.assertTrue(len(nps) == 1)
        n, p = nps[0]
        self.assertTrue(n == ("NP1", ))
        self.assertTrue(p is np1)

    def test_check_navigation(self):
        # complex type has a navigation property that contains the entity
        c1 = types.ComplexType(value_type=MockValue)
        np1 = types.NavigationProperty()
        np1.set_type(types.EntityType(value_type=MockValue), False, True)
        np1.declare(c1, "NP1")
        c1.close()
        # complex type has a navigation property that does not contain
        # the entity
        c2 = types.ComplexType(value_type=MockValue)
        np2 = types.NavigationProperty()
        np2.set_type(types.EntityType(value_type=MockValue), False, False)
        np2.declare(c2, "NP2")
        c2.close()
        # complex + containment OK
        t1 = types.StructuredType(value_type=MockValue)
        p1 = types.Property()
        p1.set_type(c1, False)
        p1.declare(t1, "P1")
        t1.close()
        t1.check_navigation()
        # complex collection + containment: FAIL
        t2 = types.StructuredType(value_type=MockValue)
        p2 = types.Property()
        p2.set_type(c1, True)
        p2.declare(t2, "P2")
        t2.close()
        try:
            t2.check_navigation()
            self.fail("Complex collection with containment navigation")
        except errors.ModelError:
            pass
        # complex + uncontained OK
        t3 = types.StructuredType(value_type=MockValue)
        p3 = types.Property()
        p3.set_type(c2, False)
        p3.declare(t3, "P3")
        t3.close()
        t3.check_navigation()
        # complex collection + uncontained OK
        t4 = types.StructuredType(value_type=MockValue)
        p4 = types.Property()
        p4.set_type(c2, True)
        p4.declare(t4, "P4")
        t4.close()
        t4.check_navigation()


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
            ("PropertyB", names.QualifiedName("Schema", "Subtype")))
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
            ("PropertyC", names.QualifiedName("Schema", "Subtype")),
            qualifier=names.PathQualifier.ref, options=suboptions)
        self.assertTrue(len(options.expand) == 3)
        xitem = options.expand[2]
        self.assertTrue(len(xitem.path) == 1)
        self.assertTrue(to_text(xitem.type_cast) == "Schema.Subtype")
        self.assertTrue(xitem.qualifier == names.PathQualifier.ref)
        self.assertTrue(xitem.options is suboptions)
        self.assertTrue(xitem.options.top == 10)
        options.add_expand_path(
            "PropertyC/PropertyC1", names.PathQualifier.count)
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
        self.assertTrue(isinstance(type_cast, names.QualifiedName))
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
