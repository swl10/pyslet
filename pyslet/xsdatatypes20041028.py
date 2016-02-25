#! /usr/bin/env python

import warnings

from .xml.xsdatatypes import *  	# noqa

warnings.warn(
    "pyslet.xsdatatypes20041029 is deprecated, use pyslet.xml.xsdatatypes "
    "instead", DeprecationWarning, stacklevel=3)
