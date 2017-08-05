Compatibility
=============

.. toctree::
   :hidden:

   py26
   py2
   pep8


Pyslet requires Python 2.6, Python 2.7 or Python 3.3+.


Python 3
~~~~~~~~

Pyslet support in Python 3 is at a beta stage.  All unittests are now
running under Python 3 and the setup script can be used to install
Pyslet in Python 3 without errors.  Try running your own code that uses
Pyslet with python options -3Wd to expose any issues that you are likely
to need to fix on any future transition.

Support is currently limited to Python 3.3 and higher as some modules
continue to require use of the 'u' prefix on unicode strings.  There
are only a handful of instances where this is a problem and these could
be resolved if desired - please open an issue on GitHub if you need
earlier Python 3 support.

Pyslet includes it's own module containing compatibility definitions
that target the particular idioms I've used in the package.  You are
obviously free to use these definitions yourself to help you create code
that also targets both Python 2 and 3 from the same source.

:doc:`py2`

The tox configuration has been modified to enable Python3 compatibility
to be checked with::

    tox -e py35
    
which shoud now succeed if you have Python 3.5 and tox installed on your
system.

..  warning::   Due to the dictionary-like approach taken by Pyslet in
                the OData modules the standard 2to3 script will suggest
                changing calls like itervalues() to values() on
                collections of entities.  If you are using OData in
                Pyslet you are likely to need to use "-x dict" to
                prevent these automatic transformations.


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

Python 2.6 support will be withdrawn in a future version, the Travis
continuous integration service no longer supports Python 2.6.


PEP-8
~~~~~

The code has been widely refactored for PEP-8 compliant. Where critical,
methods are renamed from CamelCase to PEP-8 compliant lower_case_form
and the old names are defined as wrappers which raise deprecation
warnings.

You can test your code with the -Wd option to python to check the
warning messages in case you are relying on the old-style names.

Pyslet uses a special module that defines decorators and other code to
help with method renaming.  The purpose of the module is to ensure that
the old names can be used with minimal impact on existing code.

:doc:`pep8`
