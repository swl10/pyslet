#!/usr/bin/env python

import logging
import sys
import pyslet.info

if sys.hexversion < 0x02060000:
    logging.error("pyslet requires Python Version 2.6 (or greater)")
else:
    try:
        from setuptools import setup
    except ImportError:
        from distutils.core import setup

    with open('README.rst') as f:
        long_description = f.read()

    setup(name=pyslet.info.name,
          version=pyslet.info.version,
          description=pyslet.info.title,
          long_description=long_description,
          author="Steve Lay",
          author_email="steve.w.lay@gmail.com",
          url=pyslet.info.home,
          packages=['pyslet',
                    'pyslet.http',
                    'pyslet.xml',
                    'pyslet.qtiv1',
                    'pyslet.qtiv2',
                    'pyslet.odata2'],
          package_data={'pyslet': ['imsbltiv1p0_metadata.xml',
                                   'wsgi_metadata.xml',
                                   'unicode5_blocks.pck',
                                   'unicode5_catogories.pck',
                                   'unicode5_blocks3.pck',
                                   'unicode5_catogories3.pck'],
                        'pyslet.odata2': ['streamstore.xml']},
          classifiers=['Development Status :: 3 - Alpha',
                       'Intended Audience :: Developers',
                       'Natural Language :: English',
                       'License :: OSI Approved :: BSD License',
                       'Operating System :: OS Independent',
                       'Programming Language :: Python',
                       'Programming Language :: Python :: 2',
                       'Programming Language :: Python :: 2.6',
                       'Programming Language :: Python :: 2.7',
                       'Programming Language :: Python :: 3',
                       'Programming Language :: Python :: 3.5',
                       'Topic :: Education',
                       'Topic :: Education :: '
                       'Computer Aided Instruction (CAI)',
                       'Topic :: Education :: Testing',
                       'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
                       'Topic :: Software Development :: '
                       'Libraries :: Python Modules']
          )
