#! /usr/bin/env python

import logging
import unittest

from pyslet import pep8


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(MethodTests, 'test'),
        unittest.makeSuite(FunctionTests, 'test')
    ))


class Base(pep8.MigratedClass):

    @pep8.old_method('OldMethod')
    def new_method(self):
        return "Base.new_method"

    @classmethod
    @pep8.old_method('OldClassMethod')
    def new_class_method(cls):
        return "Base.new_class_method"

    @staticmethod
    @pep8.old_method('OldStaticMethod')
    def new_static_method():
        return "Base.new_static_method"


class MethodTests(unittest.TestCase):

    def test_base(self):
        # firstly, let's check that the Base class is working
        self.assertTrue(Base.new_class_method() == "Base.new_class_method")
        self.assertTrue(Base.OldClassMethod() == "Base.new_class_method")
        self.assertTrue(Base.new_static_method() == "Base.new_static_method")
        self.assertTrue(Base.OldStaticMethod() == "Base.new_static_method")

    def test_base_instance(self):
        # now check that instances of Base work with new and old code
        b = Base()
        self.assertTrue(b.new_method() == "Base.new_method")
        self.assertTrue(b.OldMethod() == "Base.new_method")

    def test_derived(self):
        class NoTreble(Base):

            @classmethod
            def OldClassMethod(cls):    # noqa
                return "NoTreble.OldClassMethod"

        # it's simple, we expect to be able to call the new methods even
        # though they weren't declared.
        self.assertTrue(NoTreble.OldClassMethod() ==
                        "NoTreble.OldClassMethod")
        self.assertTrue(NoTreble.new_class_method() ==
                        "NoTreble.OldClassMethod")

    def test_derived_pass(self):
        class NoTreble(Base):

            @classmethod
            def OldClassMethod(cls):    # noqa
                return Base.OldClassMethod() + ", NoTreble.OldClassMethod"

        # it's simple, we expect to be able to call the new methods even
        # though they weren't declared.
        self.assertTrue(NoTreble.OldClassMethod() ==
                        "Base.new_class_method, NoTreble.OldClassMethod")
        self.assertTrue(NoTreble.new_class_method() ==
                        "Base.new_class_method, NoTreble.OldClassMethod")

    def test_derived_super(self):
        class NoTreble(Base):

            @classmethod
            def OldClassMethod(cls):    # noqa
                return super(NoTreble, cls).OldClassMethod() + \
                    ", NoTreble.OldClassMethod"

        # it's simple, we expect to be able to call the new methods even
        # though they weren't declared.
        self.assertTrue(NoTreble.OldClassMethod() ==
                        "Base.new_class_method, NoTreble.OldClassMethod")
        self.assertTrue(NoTreble.new_class_method() ==
                        "Base.new_class_method, NoTreble.OldClassMethod")

    def test_derived_new(self):
        class NoTreble(Base):

            @classmethod
            def new_class_method(cls):
                return "NoTreble.new_class_method"

        # we expect to be able to call the new method by both old and
        # new names.
        self.assertTrue(NoTreble.new_class_method() ==
                        "NoTreble.new_class_method")
        self.assertTrue(NoTreble.OldClassMethod() ==
                        "NoTreble.new_class_method")

    def test_static(self):
        class NoStatic(Base):

            @staticmethod
            def OldStaticMethod():    # noqa
                return "NoStatic.OldStaticMethod"

        # it's simple, we expect to be able to call the new methods even
        # though they weren't declared.
        self.assertTrue(NoStatic.OldStaticMethod() ==
                        "NoStatic.OldStaticMethod")
        self.assertTrue(NoStatic.new_static_method() ==
                        "NoStatic.OldStaticMethod")

    def test_derived_instance(self):
        class NoTreble(Base):

            def OldMethod(self):    # noqa
                return "NoTreble.OldMethod"

        # it's simple, we expect to be able to call the new methods even
        # though they weren't declared.
        i = NoTreble()
        self.assertTrue(i.OldMethod() == "NoTreble.OldMethod")
        self.assertTrue(i.new_method() == "NoTreble.OldMethod")

    def test_derived_instance_pass(self):
        class NoTreble(Base):

            def OldMethod(self):    # noqa
                return Base.OldMethod(self) + ", NoTreble.OldMethod"

        # it's simple, we expect to be able to call the new methods even
        # though they weren't declared.
        i = NoTreble()
        self.assertTrue(i.OldMethod() ==
                        "Base.new_method, NoTreble.OldMethod")
        self.assertTrue(i.new_method() ==
                        "Base.new_method, NoTreble.OldMethod")

    def test_derived_instance_new(self):
        class NoTreble(Base):

            def new_method(self):
                return "NoTreble.new_method"

        i = NoTreble()
        self.assertTrue(i.new_method() == "NoTreble.new_method")
        self.assertTrue(i.OldMethod() == "NoTreble.new_method")

    def test_double_derived(self):
        class NoTreble(Base):

            @classmethod
            def OldClassMethod(cls):    # noqa
                return "NoTreble.OldClassMethod"

        class AbsolutelyNoTreble(NoTreble):

            @classmethod
            def OldClassMethod(cls):    # noqa
                return "AbsolutelyNoTreble.OldClassMethod"

        # it's simple, we expect to be able to call the new methods even
        # though they weren't declared.
        self.assertTrue(AbsolutelyNoTreble.OldClassMethod() ==
                        "AbsolutelyNoTreble.OldClassMethod")
        self.assertTrue(AbsolutelyNoTreble.new_class_method() ==
                        "AbsolutelyNoTreble.OldClassMethod")

    def test_double_static(self):
        class NoStatic(Base):

            @staticmethod
            def OldStaticMethod():    # noqa
                return "NoStatic.OldStaticMethod"

        class AobsolutelyNoStatic(NoStatic):

            @staticmethod
            def OldStaticMethod():    # noqa
                return "AobsolutelyNoStatic.OldStaticMethod"

        # it's simple, we expect to be able to call the new methods even
        # though they weren't declared.
        self.assertTrue(AobsolutelyNoStatic.OldStaticMethod() ==
                        "AobsolutelyNoStatic.OldStaticMethod")
        self.assertTrue(AobsolutelyNoStatic.new_static_method() ==
                        "AobsolutelyNoStatic.OldStaticMethod")

    def test_double_derived_instance(self):
        class NoTreble(Base):

            def OldMethod(self):    # noqa
                return "NoTreble.OldMethod"

        class AbsolutelyNoTreble(Base):

            def OldMethod(self):    # noqa
                return "AbsolutelyNoTreble.OldMethod"

        # it's simple, we expect to be able to call the new methods even
        # though they weren't declared.
        i = AbsolutelyNoTreble()
        self.assertTrue(i.OldMethod() == "AbsolutelyNoTreble.OldMethod")
        self.assertTrue(i.new_method() == "AbsolutelyNoTreble.OldMethod")

    def test_method_collision(self):
        try:
            class BadOverride(Base):

                def OldMethod(self):    # noqa
                    return "BadOverride.OldMethod"

                def new_method(self):
                    # already got a new method here
                    return "BadOverride.new_method"

            self.fail("Bad override of method")
        except TypeError:
            pass

    def test_classmethod_collision(self):
        try:
            class BadOverride(Base):

                @classmethod
                def OldClassMethod(cls):    # noqa
                    return "BadOverride.OldMethod"

                def new_class_method(self):
                    # already got a new method here
                    return "BadOverride.new_method"

            self.fail("Bad override of class method")
        except TypeError:
            pass


@pep8.old_function('OldFunction')
def new_function():
    return "new_function"


class FunctionTests(unittest.TestCase):

    def test_basic(self):
        self.assertTrue(new_function() == "new_function")
        # OldFunction is defined by decorator, flake8 doesn't spot this
        self.assertTrue(OldFunction() == "new_function")    # noqa


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
