.. Pyslet documentation master file, created by
   sphinx-quickstart on Tue Jun 14 08:06:51 2011.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Pyslet's documentation!
==================================

Contents:

.. toctree::
   :maxdepth: 2
   :numbered:
   
   ims
   general


Compatibility
-------------

Pyslet requires Python 2.6 or Python 2.7, with Python 2.7 being
preferred. When run under Python 2.6 Pyslet will patch the following
modules to make them more compatible with Python 2.7 code.

zipfile
    Patches is_zipfile to add support for passing open files which is
    allowed under Python 2.7 but not under 2.6.
    
wsgiref.simple_server
    Modifies the behaviour of the WSGI server when procssing HEAD requests
    so that Content-Length headers are not stripped.  There is an issue
    in Python 2.6 that causes HEAD requests to return a Content-Length of
    0 if the WSGI application does not return any data.  The behaviour
    changed in Python 2.7 to be more as expected.

io
    Benign addition of the SEEK_* constants as defined in Python 2.7.

This patching is done at run time by the pyslet.py26 module and will
affect any script that uses Pyslet. It does not modify your Python
installation!

Earlier versions of Python 2.6 have typically been built with a version
of sqlite3 that does not support validation of foreign key constraints,
the unittests have been designed to skip these tests when such a version
is encountered.

    .. warning::

        When run under Python 2.6, Pyslet does not support certificate
        validation of HTTP connections.

Pyslet is not currently compatible with Python 3, though some work has
been towards a Python 3 version.

The code is not currently PEP-8 compliant but it is slowly being
refactored for compliance as modules are touched during development. 
Where critical methods are renamed from CamelCase to PEP-8 compliant
camel_case then the old names are defined as wrappers which raise
deprecation warnings.

    
Distribution
------------

Pyslet is developed on github: https://github.com/swl10/pyslet but it
can be downloaded and installed from the popular PyPi package
distribution site: https://pypi.python.org/pypi/pyslet using *pip*.

Pyslet is distributed under the 'New' BSD license:
http://opensource.org/licenses/BSD-3-Clause		


Installing from Source
~~~~~~~~~~~~~~~~~~~~~~

The Pyslet package contains a setup.py script so you can install it
by downloading the compressed archive, uncompressing it and then
running the following command inside the package::

    python setup.py install


Format of the Documentation
---------------------------

The documentation has been written using ReStructuredText, a simple
format created as part of the docutils package on SourceForge.  The
documentation files you are most likely reading have been generated
using Sphinx.  Parts of the documentation are auto-generated from the
Python source files to make it easier to automatically discover the
documentation using other tools capable of reading Python docstrings. 
However, this requires that the docstrings be written using
ReStructuredText too, which means there is some additional markup for
python-cross referencing in the code that may not be interpretable by
other system (see below for details).

*   ReStructuredText Primer:
    http://docutils.sourceforge.net/docs/user/rst/quickstart.html	
	*   Quick Reference:
    	http://docutils.sourceforge.net/docs/user/rst/quickref.html
	*   Sphinx: http://sphinx.pocoo.org/
		*   Autodoc externsion: http://sphinx.pocoo.org/ext/autodoc.html
		*   Python-cross references:
    		http://sphinx.pocoo.org/domains.html#python-roles


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

