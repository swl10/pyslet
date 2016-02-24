#! /usr/bin/env python

import warnings

warnings.warn(
    "pyslet.xmlnames20091208 is deprecated, use pyslet.xml.namespace instead",
    DeprecationWarning, stacklevel=3)

from pyslet.xml.namespace import *
