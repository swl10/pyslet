#!/usr/bin/env python

import sys
import pyslet.info

if sys.hexversion<0x02060000:
	print "pyslet requires Python Version 2.6 (or greater)"
else:
	from distutils.core import setup
	from distutils.sysconfig import get_python_lib
	pkgBase=get_python_lib()
	
	setup(name=pyslet.info.name,
		version=pyslet.info.version,
		description=pyslet.info.title,
		author="Steve Lay",
		author_email="steve.w.lay@googlemail.com",
		url=pyslet.info.home,
		packages=[
			'pyslet',
			'pyslet.xml20081126',
			'pyslet.qtiv1',
			'pyslet.qtiv2'],
		package_data={
			'pyslet':[
				'unicode5_blocks.pck',
				'unicode5_catogories.pck' ]
			}
		)
	

