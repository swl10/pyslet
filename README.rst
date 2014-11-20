Welcome to Pyslet
=================

Pyslet_ is a Python package for Standards in Learning Education and
Training (LET). It implements a number of LET-specific standards,
including IMS QTI, Content Packaging and Basic LTI.  It also includes
support for some general standards, including the data access standard
OData (see http://www.odata.org).

..  _Pyslet: http://www.pyslet.org

Pyslet was originally written to be the engine behind the QTI migration
tool but it can be used independently as a support module for your own
Python applications.

Full documentation is hosted at http://pyslet.readthedocs.org

Pyslet currently supports Python 2.6 and 2.7, see docs for details.


Distribution
------------

Pyslet is developed on GitHub: https://github.com/swl10/pyslet but it
can be downloaded and installed from the popular PyPi package
distribution site: https://pypi.python.org/pypi/pyslet using *pip*.

While Pyslet is being actively developed the version on PyPi may lag
a few months behind the master branch on GitHub.  The unittests are
fairly comprehensive and are automatically run against the master
branch using TravisCI_:

.. image:: https://secure.travis-ci.org/swl10/pyslet.png
   :alt: Build Status
   :target: https://travis-ci.org/swl10/pyslet

.. _TravisCI: https://travis-ci.org/swl10/pyslet

Users of older Python builds (e.g., the current Python 2.6 installed on
OS X as of August 2014) should be aware that pip may well fail to
install itself or other modules due to a failure to connect to the PyPi
repository.  Fixing this is hard and installing from source is
recommended instead if you are afflicted by this issue.


Installing from Source
~~~~~~~~~~~~~~~~~~~~~~

The Pyslet package contains a setup.py script so you can install it
by downloading the compressed archive, uncompressing it and then
running the following command inside the package::

    python setup.py install


Current Status & Road Map
~~~~~~~~~~~~~~~~~~~~~~~~~

Pyslet is going through a transition process at the moment as the QTI
migration tool that drives its development is gradually moving towards
being distributed as an LTI tool rather than a desktop application.

The OData support is fairly robust, it is used to run the Cambridge Weather
OData service which can be found at http://odata.pyslet.org/weather

What's next?

*   Proper Media stream support in the OData SQL storage model (now
    complete in master)

*   MySQL shim for the OData SQL storage model (90% complete in master
    and functional)

*   Improved support for LTI to take it beyond 'basic' (10% complete in
    master)

I'm also slowly transforming the code for better PEP-8 compliance as
reported by the fantastic flake8_.  For important information about how
this affects existing Pyslet users see the What's New? section of the
documentation or the CHANGES.rst file in the distribution package. 

..  _flake8: https://pypi.python.org/pypi/flake8

I also write about Pyslet on my blog:
http://swl10.blogspot.co.uk/search/label/Pyslet


Feedback
~~~~~~~~

The best way to get something changed is to create an issue or Pull
request on GitHub, however, my contact details are available there on my
profile page if you just want to drop me an email with a suggestion or
question.


License
~~~~~~~

Pyslet is distributed under the 'New' BSD license:
http://opensource.org/licenses/BSD-3-Clause, this decision was inherited
from the early days of the code.  Although Copyright to much of the
source is owned by the author personally earlier parts are owned by the
University of Cambridge and are marked as such.

Pyslet is written and maintained by the main author on a spare time
basis and is not connected to my current employer.


Acknowledgements
~~~~~~~~~~~~~~~~

Some historical information is available on the QTI Migration tool's
Google Code project:
https://code.google.com/p/qtimigration/

Some of the code was written almost 20 years ago and it owes a lot to
the University of Cambridge and, in particular, to the team I worked
with at UCLES (aka Cambridge Assessment) who were instrumental in
getting this project started.





