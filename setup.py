#!/usr/bin/env python

import sys

if sys.hexversion<0x02000000:
	print "PyAssess requires Python Version 2 (or greater)"
else:
	from distutils.core import setup

	setup(name="PyAssess",
		version="20050607",
		description="PyAssess Library",
		author="Steve Lay",
		author_email="S.W.Lay@ucles-red.cam.ac.uk",
		packages=['PyAssess',
			'PyAssess.ieee',
			'PyAssess.ietf',
			'PyAssess.ims',
			'PyAssess.iso',
			'PyAssess.w3c'])

