Compatibility
=============

Pyslet requires Python 2.6 or Python 2.7, with Python 2.7 being
preferred.

Python 2.6
~~~~~~~~~~

When run under Python 2.6 Pyslet will patch the following
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

    .. note::

        When run under Python 2.6, Pyslet may not support certificate
        validation of HTTP connections properly, this seems to depend
        on the version of OpenSSL that Python is linked to.  If you
        have successfully used pip to install Pyslet then your Python
        is probably unaffected though.

Please be aware of the following bug in Python 2.6:
http://bugs.python.org/issue2531  this problem caused a number of
Pyslet's tests to fail initially and remains a potential source of problems
if you are using Decimal types in OData models.

Python 3
~~~~~~~~

Pyslet is not currently compatible with Python 3, though some work has
been towards a Python 3 version and the unittests are regularly run with
the -3 flag to check for issues.  Try running your own code that uses
Pyslet with python options -3Wd to expose any issues that you are likely
to need to fix on any future transition.

PEP-8
~~~~~

The code is not currently PEP-8 compliant but it is slowly being
refactored for compliance as modules are touched during development. 
Where critical methods are renamed from CamelCase to PEP-8 compliant
lower_case_form then the old names are defined as wrappers which raise
deprecation warnings.

