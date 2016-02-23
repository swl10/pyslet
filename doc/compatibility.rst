Compatibility
=============

.. toctree::
   :hidden:

   py26
   py2
   pep8


Pyslet requires Python 2.6 or Python 2.7, with Python 2.7 being
preferred.

Python 2.6
~~~~~~~~~~

When run under Python 2.6 Pyslet will patch some modules to make them
more compatible with Python 2.7 code.  For details see:

:doc:`py26`

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
been done towards a Python 3 version and the unittests are regularly run
with the -3 flag to check for issues.  Try running your own code that
uses Pyslet with python options -3Wd to expose any issues that you are
likely to need to fix on any future transition.

Work has now started on porting the core modules to be compatible with
Python 3.3 (Pyslet may require use of the 'u' on unicode strings for
some time so compatibility with Python 3 versions earlier than 3.3 is
unlikely).  Rather than just fix up the existing code using a module
like six Pyslet now includes it's own module containing compatibility
definitions that target the particular idioms I've used in the package.

:doc:`py2`

Although the package can't be built for distribution or installed using
pip or setup.py (yet), if you use the source distribution you can
successfully import the following modules in Python 3 (in addition to
the compatibility modules described elsewhere on this page)::

    pyslet.http.grammar
    pyslet.http.params
    pyslet.info
    pyslet.iso8601
    pyslet.rfc2396
    pyslet.unicode5
    pyslet.urn
    pyslet.vfs
    pyslet.xml.namespace
    pyslet.xml.parser
    pyslet.xml.structures

The unittest script (and the tox configuration) has been modified to
enable Python3 compatibility to be checked with::

    tox -e py35
    
shoud now succeed if you have Python 3.5 and tox installed on your
system.


PEP-8
~~~~~

The code is not currently PEP-8 compliant but it is slowly being
refactored for compliance as modules are touched during development,
particularly during Python 3 conversion work. Where critical, methods
are renamed from CamelCase to PEP-8 compliant lower_case_form then the
old names are defined as wrappers which raise deprecation warnings.

You can test your code with the -Wd option to python to check the
warning messages in case you are relying on the old-style names.

For more information see:

:doc:`pep8`
