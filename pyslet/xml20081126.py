#! /usr/bin/env python

import warnings

from pyslet.xml import structures, parser   # noqa

warnings.warn(
    "pyslet.xml20081126 is deprecated, use pyslet.xml.structures "
    "or pyslet.xml.parser instead", DeprecationWarning, stacklevel=3)
