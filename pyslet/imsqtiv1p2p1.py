#! /usr/bin/env python
"""This module implements the QTI 1.2.1 specification defined by IMS GLC"""

import warnings

from .qtiv1 import (     # noqa
    assessment,
    common,
    core,
    item,
    objectbank,
    outcomes,
    sao,
    section,
    xml as qtixml)

warnings.warn(
    "pyslet.imsqtiv1p2p1 is deprecated, use pyslet.qtiv1 package instead",
    DeprecationWarning, stacklevel=3)
