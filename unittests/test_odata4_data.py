#! /usr/bin/env python

import logging
import unittest

from pyslet.odata4 import (
    data,
    model,
    types,
    )


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(ValueTests, 'test'),
        unittest.makeSuite(CollectionValueTests, 'test'),
        ))


class ValueTests(unittest.TestCase):

    def test_base(self):
        """Base class for all values"""
        # construct without a type definition
        try:
            v = data.Value()
            self.fail("Value require type definition")
        except TypeError:
            pass
        t = model.edm['PrimitiveType']
        v = data.Value(t)
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

    def test_new_type(self):
        # creates a new type instance with this value type
        t = data.Value.new_type()
        self.assertTrue(isinstance(t, types.NominalType))
        self.assertTrue(t.value_type is data.Value)

    def test_collection_class(self):
        cls = data.Value.collection_class()
        self.assertTrue(cls is data.CollectionValue)


class CollectionValueTests(unittest.TestCase):

    pass


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(message)s")
    unittest.main()
