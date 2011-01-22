#!/usr/bin/env python

import sys

if sys.hexversion<0x02020000:
	print "PyAssess requires Python Version 2.2 (or greater)"
else:
	from distutils.core import setup
	from distutils.sysconfig import get_python_lib
	pkgBase=get_python_lib()
	
	setup(name="PyAssess",
		version="20051127",
		description="PyAssess Library",
		author="Steve Lay",
		author_email="S.W.Lay@ucles-red.cam.ac.uk",
		packages=['PyAssess',
			'PyAssess.ieee',
			'PyAssess.ietf',
			'PyAssess.ims',
			'PyAssess.ims.qti',
			'PyAssess.iso',
			'PyAssess.unicode',
			'PyAssess.w3c'],
		data_files=[(pkgBase+'/PyAssess/unicode',['PyAssess/unicode/ucd_tables.pck'])]
		# package_data={'PyAssess.unicode':['ucd_tables.pck']} - wait for Python 2.4
		)
	

