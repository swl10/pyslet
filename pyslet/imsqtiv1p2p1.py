#! /usr/bin/env python
"""This module implements the QTI 1.2.1 specification defined by IMS GLC"""

import warnings

from .qtiv1.assessment import *     # noqa
from .qtiv1.common import *         # noqa
from .qtiv1.core import *           # noqa
from .qtiv1.item import *           # noqa
from .qtiv1.objectbank import *     # noqa
from .qtiv1.outcomes import *       # noqa
from .qtiv1.sao import *            # noqa
from .qtiv1.section import *        # noqa
from .qtiv1.xml import *            # noqa


warnings.warn(
    "pyslet.imsqtiv1p2p1 is deprecated, use pyslet.qtiv1 package instead",
    DeprecationWarning, stacklevel=3)
