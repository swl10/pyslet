What's New?
===========

As part of moving towards PEP-8 compliance a number of name changes are
being made to methods and class attributes with each release.  There is
a module, pyslet.pep8, which contains a compatibility class for
remapping missing class attribute names to their new forms and
generating deprecation warnings, run your code with "python -Wd" to
force these warnings to appear.  As Pyslet makes the transition to
Python 3 some of the old names will go away completely. 
 
It is still possible that some previously documented names could now
fail (module level functions, function arguments, etc.) but I've tried
to include wrappers or aliases so please raise an issue on Github_ if you
discover a bug caused by the renaming.  I'll restore any missing
old-style names to improve backwards compatibility on request.

Finally, in some cases you are encouraged to derive classes from those
defined by Pyslet and to override default method implementations.  If
you have done this using old-style names you will *have* to update your
method names to prevent ambiguity.  I have added code to automatically
detect most problems and force fatal errors at runtime on construction,
the error messages should explain which methods need to be renamed.
 
..  _Github: https://github.com/swl10/pyslet


Version Numbering
-----------------

Pyslet version numbers use the check-in date as their last component so
you can always tell if one build is newer than another.  At the moment
there is only one actively maintained branch of the code: version '0".
Changes are reported against the versions released to PyPi.  The main
version number increases with each PyPi release.  Starting with version
0.7 changes are documented in order of build date to make it easier to
see what is changing in the master branch on GitHub.

Not sure which version you are using?  Try::

    from pyslet.info import version
    print version


Version 0.7
-----------

Build 20160205:

#38 Python 3 compatibility work

http.params module now works in Python 3
http.grammar module now works in Python 3
urn module now works in Python 3

Added SortableMixin to emulate Python 3 TypeErrors in comparisons and to
simplify implementation of comparison/hash operators in custom classes.
As a result, some Time/TimePoint comparisons which used to raise
ValueError (e.g., due to incompatible precision) now return False for ==
and != operators and raise TypeError for inequalities (<, >, etc). 
OData is unaffected as OData time values of the same EDM type are always
comparable.


Version 0.6.20160201
--------------------

Summary of New Features:
    LTI module rewritten, now suitable for real applications!
    WSGI-based web-app framework built using Pyslet's DAL
    MySQL Database connector for Pyslet's DAL
    SSL, Certificates and HTTP Basic Authentication
    HTTP Cookies
    URNs

#3 PEP-8 driven refactoring (ongoing)

Added new method decorators to make supporting renamed and redirected
methods easier.  Added checks for ambiguous names in classes likely
to have been sub-classed by third-party code.

#8 Support for SSL Certificates in HTTP Clients

Fixed certificate support in OData and Atom clients.  See blog post for
further information on how to use certificates:
http://swl10.blogspot.co.uk/2014/11/basic-authentication-ssl-and-pyslets.html

#9 HTTP client retry strategy

Improved HTTP retries with simple Fibonacci-based back-off.  Also fixed
a bug where, if the first request after a server timed out an idle
connection is a POST, the request would fail.  

#12 bug when using numeric or named parameters in DB API

The basic bug is fixed and I've also added support for paramstyle
'format'.

#14 content element missing in media-link entries

Fixed. Affected atom xml formatted entities only.

#15 MySQL implementation of Pyslet's DAL (ongoing)

Changes to the core DAL to deal to better support other DB modules.
These included added support for LIMIT clauses to speed up paged access
to large entity sets.  Implementation of a retry strategy when database
commands return OperationalError (e.g., MySQL idle timeouts).  An
updated connection pool manager and an optional pool cleaner method to
clean up idle database connections.

#18 Possible bug in parsing AssociationSet names

Added a compatibility mode to odata2.csdl to enable the metadata model
to optionally accept hyphen or dash characters in simple identifiers
using::

    import pyslet.odata2.csdl as edm
    edm.set_simple_identifier_re(edm.SIMPLE_IDENTIFIER_COMPATIBILITY_RE)

#19 OData Function parameter handling

Enabled function parameter passing in OData service operations.  Only
primitive types are supported but they are now parsed correctly from the
query string and coerced to the declared parameter type.  Bound
functions now receive them as a dictionary of SimpleValue instances.

#20 HTTP Basic Authentication

Fixed an issue with the OData basic authentication support, in some
cases the HTTP client was waiting for a 401 when it could have offered
the credentials preemptively.  See also the following blog article:
http://swl10.blogspot.co.uk/2014/11/basic-authentication-ssl-and-pyslets.html

#22 Support for navigation properties in OData expressions

Although the code always contained support in general, the mapping to
SQL did not previously support the use of table joins in SQL
expressions.  This release adds support for joins (but not for nested
joins).

#23 A Framework for WSGI-based LTI Applications

Added a new module to make it easier to write WSGI-based applications.
Re-factored the existing Basic LTI module to use the new oauthlib
and Pyslet's own OData-inspired data access layer.

#24 ESA Sentinel mission compatibility

Added the capability to override the metadata used by an OData server to
deal with validation issues in some services.  Clients can now also be
created from an offline copy of the service root document.

#26 HTTP client eats memory when downloading large unchunked files

Fixed the download buffer which was failing to write out data until an
entire chunk (or the entire download) was complete.

#29 https connections fail on POST after remote server hangup

Partial mitigation with an agressive 2s window in which to start sending
a follow-up request when pipelining through https.  This is a crude
solution and the bug remains open for a more robust solution based
around use of the Expect header in HTTP/1.1.

#30 HTTP client cleanup thread

Added an optional parameter to the HTTP client constructor that creates
a cleanup thread to close down idle connections periodically.

#31 Removed reliance on Host header in wsgi app class

There are a number of ways an application can be attacked using a forged
Host header, wsgi now ignores the Host header and uses a new setting for
the preferred scheme//host:port.

#32 get_certificate_chain

Implemented a function to create a complete certificate chain. 
Implemented using pyOpenSSL with a lot of help from `this article`__

..  __:
    http://blog.san-ss.com.ar/2012/05/validating-ssl-certificate-in-python.html

#33 Fixed exception: 'NoneType' object has no attribute 'current_thread'
on exit

Caused by an overly ambitious __del__ method in SQLEntityContainer.


#34 Fixed missing Edm prefix in OData sample code
#35 Fixed missing import in rfc5023 (atom protocol) module
#36 Fixed incorrect error messages in OData $filter queries
#37 Extended comparison operators in OData to include DateTimeOffset values

All thanks to @ianwj5int for spotting

#38 Python 3 compatibility work

I have started revising modules to support Python 3.  This is not yet
production ready but it is a small impact on existing modules.  I have
done my best to maintain compatibility, in practice code should continue
to work with no changes required.

The most likely failure mode is that you may find a unicode string in
Python 2 where you expected a plain str.  This can have a knock-on
effect of promoting data to unicode, e.g., through formatting
operations.  In general the returned types of methods are just being
clarified and unicode values are returned only where they may have been
returned previously anyway.  However, in the case of the URI attributes
in the rfc2396 module the types have changed from str to unicode in this
release.

This is work in progress but the impact is likely to be minimal
at this stage.

#40 & #41 Composite keys and Slug headers

Key hints were not working properly between the OData client and server
implementations, and were not working at all when the key was composite.
It is now possible to pass the formatted entity key predicate (including
the brackets) as a Slug to the OData server and it will attempt to parse
it and use that key where allowed by the underlying data layer.

#43 Fixes for Python running on Windows

The only substantive changes required were to the way we check for io
failures when IOError is raised and the way we handle URI containing
non-ASCII characters.  Some of the unit tests were also affected due to
issues with timing, including the reduced precision of time.time() on
Windows-based systems.

    
Untracked enhancements:

Added a new module to support HTTP cookies.  The HTTP/OData client can
now be configured to accept cookies.  The default behaviour is to
*ignore* them so this won't affect existing applications.

Added a new module to support URN syntax to provide a better
implementation of the IMS LTI vocabularies.

Added an optional params dictionary to the OData expression parser to
make it *much* easier to parse parameterized OData queries.

Added new methods for creating and executing drop table statements in
the DAL.

Reworked sample code for the weather data server, included example
driver files for mod_wsgi


Other fixes:

Fixed an issue in the OData client that caused basic key lookup in
filtered entity collections to use both a key predicate and a $filter
query option. This was causing the filter to be ignored, now the key
predicate will be added to the filter rather than the path segment.

Fixed the OData DateTime parser to accept (and discard)
any time zone specifier given in the literal form as it is now allowed
in the ABNF and may therefore be generated by OData servers.

Fixed a bug in the OData server which meant that requests for JSON
format responses were not being limited by the builtin topmax and would
therefore attempt to return all matching entities in a single response.

Fixed a bug in the OData server which meant that use of $count was
causing the $filter to be ignored!

Fixed a bug in the OData URI parser that prevent compound keys from
working properly when zealous escaping was used.

Fixed a bug in the OData server which meant that error messages that
contained non-ASCII characters were causing a 500 error due to character
encoding issues when outputting the expected OData error format.

Fixed a bug in the OData expression evaluator when evaluating
expressions that traversed navigation properties over optional
relations.  If there was no associated entity an error was being raised.

Fixed a bug in the SQL DAL implementation which means that navigation
properties that require joining across a composite key were generating
syntax errors, e.g., in SQLite the message 'near "=": syntax error'
would be seen.

Fixed a bug in the SQLite DAL implementation which means that in-memory
databases were not working correctly in multi-threaded environments.

Fixed XML parser bug, ID elements in namespaced documents were not
being handled properly. 

Fixed bug in the OData server when handling non-URI characters in entity
keys

Fixed a bug with composite key handling in media streams when using the
SQL layer 


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