#!/usr/bin/env python

import sys

if sys.hexversion<0x02060000:
	print "pyslet requires Python Version 2.6 (or greater)"
else:
	from distutils.core import setup
	from distutils.sysconfig import get_python_lib
	pkgBase=get_python_lib()
	
	setup(name="pyslet",
		version="0.2.20110715",
		description="pyslet: standards for learning education and training",
		author="Steve Lay",
		author_email="steve.w.lay@googlemail.com",
		url="http://code.google.com/p/qtimigration/",
		packages=['pyslet','pyslet.xml20081126'],
		package_data={'pyslet': [ ] }
		)
	

