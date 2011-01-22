#! /usr/bin/env python

"""Runs unit tests on the pyslet.rfc2234 module"""

import unittest

from pyslet.rfc2234 import *

def suite():
	return unittest.TestSuite()


if __name__ == "__main__":
	unittest.main()