#!/usr/bin/env python

import sys

if sys.hexversion<0x02050000:
	print "pyslet requires Python Version 2.5 (or greater)"
else:
	from distutils.core import setup
	from distutils.sysconfig import get_python_lib
	pkgBase=get_python_lib()
	
	setup(name="pyslet",
		version="0.2.20110627",
		description="pyslet: standards for learning education and training",
		author="Steve Lay",
		author_email="steve.w.lay@googlemail.com",
		url="http://code.google.com/p/qtimigration/",
		packages=['pyslet'],
		package_data={'pyslet': [ ] }
		)
	

