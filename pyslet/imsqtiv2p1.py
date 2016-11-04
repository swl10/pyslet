#! /usr/bin/env python
"""This module implements the QTI 2.1 specification defined by IMS GLC
"""

import warnings

from .qtiv2 import (      # noqa
    core,
    variables,
    expressions,
    processing,
    content,
    interactions,
    items,
    tests,
    metadata as md,
    xml as qtixml)

warnings.warn(
    "pyslet.imsqtiv2p1 is deprecated, use pyslet.qtiv2 package instead",
    DeprecationWarning, stacklevel=3)
