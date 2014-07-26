Change History
==============

Version 0.5.2014####
--------------------

Summary New of Features:

*   Python 2.6 Support
*   HTTP Package refactoring


As part of moving towards PEP-8 compliance a number of name changes have
been made to methods and class attributes.  I've tried to ensure that
names that are likely to have been imported and used externally have
wrappers defined with deprecation warnings.  This has not been done for
all names so if your code breaks as a result of this renaming please
raise an issue on Github and, where possible and I'll restore the
missing names for backwards compatibility.


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

 
Version 0.4 and earlier 
-----------------------

These are obsolete, version 0.4 was developed on Google Code as an integral
part of the QTI Migration tool.


PyAssess
--------

A precursor to Pyslet.  For more information see:
https://code.google.com/p/qtimigration/wiki/PyAssess