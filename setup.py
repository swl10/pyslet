#!/usr/bin/env python

import sys
import pyslet.info

if sys.hexversion < 0x02070000:
	print "pyslet requires Python Version 2.7 (or greater)"
else:
	try:
		from setuptools import setup
	except ImportError:
		from distutils.core import setup
		
	with open('README.rst') as f:
		long_description=f.read()
		
	setup(name=pyslet.info.name,
		version=pyslet.info.version,
		description=pyslet.info.title,
		long_description=long_description,
		author="Steve Lay",
		author_email="steve.w.lay@gmail.com",
		url=pyslet.info.home,
		packages=[
			'pyslet',
			'pyslet.http',
			'pyslet.xml20081126',
			'pyslet.qtiv1',
			'pyslet.qtiv2',
			'pyslet.odata2'],
		package_data={
			'pyslet':[
				'unicode5_blocks.pck',
				'unicode5_catogories.pck' ],
			'pyslet.odata2':[
			    'streamstore.xml']
			},
		classifiers=[
			'Development Status :: 3 - Alpha',
			'Intended Audience :: Developers',
			'Natural Language :: English',
			'License :: OSI Approved :: BSD License',
			'Operating System :: OS Independent',
			'Programming Language :: Python',
			'Programming Language :: Python :: 2',
			'Programming Language :: Python :: 2.7',
			'Topic :: Education',
			'Topic :: Education :: Computer Aided Instruction (CAI)',
			'Topic :: Education :: Testing',
			'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
			'Topic :: Software Development :: Libraries :: Python Modules'
			]
		)
	

