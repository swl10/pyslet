#! /usr/bin/env python
"""This module implements the QTI 2.1 specification defined by IMS GLC
"""

import warnings

from .qtiv2.core import *           # noqa
from .qtiv2.variables import *      # noqa
from .qtiv2.expressions import *    # noqa
from .qtiv2.processing import *     # noqa
from .qtiv2.content import *        # noqa
from .qtiv2.interactions import *   # noqa
from .qtiv2.items import *          # noqa
from .qtiv2.tests import *          # noqa
from .qtiv2.metadata import *       # noqa
from .qtiv2.xml import *            # noqa


warnings.warn(
    "pyslet.imsqtiv2p1 is deprecated, use pyslet.qtiv2 package instead",
    DeprecationWarning, stacklevel=3)
