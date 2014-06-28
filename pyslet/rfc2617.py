#! /usr/bin/env python

import warnings

from pyslet.http.auth import *


warnings.warn("rfc2617 module is deprecated, use http.auth package instead",
              DeprecationWarning,
              stacklevel=2)
