Change History
==============

As part of moving towards PEP-8 compliance a number of name changes are
being made to methods and class attributes with each release.  There is
a module, pyslet.pep8, which contains a compatibility class for
remapping missing class attribute names to their new forms and
generating deprecation warnings, run your code with "python -Wd" to
force these warnings to appear.  If/When Pyslet makes the transition to
Python 3 the old names will go away completely. 
 
It is still possible that some previously documented names could now
fail (module level functions, function arguments, etc.) but I've tried
to include wrappers or aliases so please raise an issue on Github_ if you
discover a bug caused by the renaming.  I'll restore any missing
old-style names to improve backwards compatibility on request.

Finally, in some cases you are encouraged to derive classes from those
defined by Pyslet and to override default method implementations.  If
you have done this using old-style names you will *have* to update your
method names to prevent ambiguity.  I have added code to automatically
detect most problems and force fatal errors on construction. 
 
..  _Github: https://github.com/swl10/pyslet


Version 0.6.2014XXXX
--------------------

#3 PEP-8 driven refactoring (ongoing)

Added new method decorators to make supporting renamed and redirected
methods easier.  Added checks for ambiguous names in classes likely
to have been sub-classed by third-party code.

#9 Improved HTTP retries with simple Fibonacci-based back-off 

#12 Fixed a bug to support SQL databases that use numeric or named
#parameters

#14 Fixed a missing content element in atom xml formatted entities
when the entity represents a media-link entry


Version 0.5.20140801
--------------------

Summary of New Features:

*   OData Media Resources 

*   HTTP Package refactoring and retry handling

*   Python 2.6 Support

Tracked issues addressed in this release:

#1 added a Makefile to make it easier for others to build and develop
the code

Added a tox.ini file to enable support for tox (a tool for running the
unittests in multiple Python environments).

#3 PEP-8 driven refactoring (ongoing)

#2 Migrated the code from SVN to git:
https://github.com/swl10/pyslet

#4 Added support for read-only properties and tests for auto generated
primary and foreign key values

#6 added integration between git and travis ci (thanks @sassman for your
help with this)

#10 restored support for Python 2.6

Other Fixes
~~~~~~~~~~~

OData URLs with reserved values in their keys were failing.  For example
Entity('why%3F') was not being correctly percent-decoded by the URI
parsing class ODataURI.  Furthermore, the server implementation was
fixed to deal with the fact that PATH_INFO in the WSGI environ
dictionary follows the CGI convention of being URL-decoded.
 
 
Version 0.4 and earlier 
-----------------------

These are obsolete, version 0.4 was developed on Google Code as an integral
part of the QTI Migration tool.


PyAssess
--------

A precursor to Pyslet.  For more information see:
https://code.google.com/p/qtimigration/wiki/PyAssess