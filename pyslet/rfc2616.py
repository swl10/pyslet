#! /usr/bin/env python

import warnings

from pyslet.http.client import *        # noqa


warnings.warn("rfc2616 module is deprecated, use http package instead",
              DeprecationWarning,
              stacklevel=2)
