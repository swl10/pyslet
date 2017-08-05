What's New?
===========

To improve PEP-8 compliance a number of name changes are being made to
methods and class attributes with each release.  There is a module,
pyslet.pep8, which contains a compatibility class for remapping missing
class attribute names to their new forms and generating deprecation
warnings, run your code with "python -Wd" to force these warnings to
appear.  As Pyslet makes the transition to Python 3 some of the old
names may go away completely.  The warning messages explain any changes
you need to make.  Although backwards compatible, using the new names is
slightly faster as they don't go through the extra deprecation wrapper.
 
It is still possible that some previously documented names could now
fail (module level functions, function arguments, etc.) but I've tried
to include wrappers or aliases so please raise an issue on Github_ if you
discover a bug caused by the renaming.  I'll restore any missing
old-style names to improve backwards compatibility on request.
 
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


Version 0.7.20170805
--------------------

Summary of new features
~~~~~~~~~~~~~~~~~~~~~~~

Pyslet now supports Python 3, all tests are passing in Python 3.

Travis now builds and tests Python 2.7 and Python 3.5, I've dropped 2.6
from the continuous integration testing because the latest Ubuntu images
have dropped Python2.6 but you can still run tox on your own
environments as it includes 2.6 in tox.ini.

Various bug fixes in OData and HTTP code.

Warning: for future compatibility with Python 3 you should ensure that
you use the bytes type (and the 'b' prefix on any string constants) when
initialising OData entity properties of type Edm.Binary.  Failure to do
so will raise an error in Python 3.


Tracked issues
~~~~~~~~~~~~~~

The following issues are resolved (or substantially resolved) in this
release.


#3 PEP-8 Compliance

The pep8-regression.py script now checks all source files using flake8;
all reported errors have been resolved

Added a new metaclass-based solution to enable method renaming while
maintaining support for derived classes that override using the old
names.  Crazy I know, but it works.


#12 Bug in odata2/sqlds.py

Bug when using numeric or named parameters in DB API.  Added support for
pyformat in DB APIs as part of enabling support for PyMySQL.


#23 Framework for WSGI-based LTI Applications (beta quality)

Re-engineered Session support in the wsgi module to reduce database
load, replacing the Session table completely with signed cookies.  If
you have used the wsgi.SessionApp class directly this will be a breaking
change but these classes will remain experimental until this item is
closed out.  The database schema required to support LTI has changed
slightly as a result.

Changed from Django templates to use Jinja2 (this requires almost no
changes to the actual sample code templates and makes the intention of
the samples much clearer).  Thanks to Christopher Lee for recommending
this change.

Possible breaking change to wsgi module to refactor authority setting to
"canonical_root", modified WSGIContext object to accept an optional
canonical_root argument and removed the optional authority argument from
get_app_root and get_url.  The authority setting was previously a
misnomer and the wsgi sammples were not working properly with localhost.

Changed wsgi module to use the OSFilePath wrapper for file paths for
better compatibility with Posix file systems that use binary strings for
file paths.  This module was causing test failures due to some use of
os.path module with mixed string types.


#29 https connections fail on POST after remote server hangup

The currently implemented solution is to allow an open ssl socket to be
idle in the 'blocked' state for a maximum of 2s before sending a new
request. After that time we tear down the socket and build a new one.
This may now be a bit aggressive given the newer SSL behaviour (which
differentiates issues in the underlying socket with different SSL
exceptions).


#30 Provide http connection clean-up thread

The implementation is not as intelligent as I'd like it to be. The
protocol version that a server last used is stored on the connection
object and is lost when we clean up idle connections. Although it is
likely that a new connection will speak the same protocol as the
previous one there is little harm in going in to protocol detection mode
again (we declare ourselves HTTP/1.1) other than the problem of using
transfer encodings on an initial POST. In particular, we only drop out
of keep-alive mode when the server has actually responded with an
HTTP/1.0 response.


#38 Make Pyslet run under Python 3

See above for details.


#43 Fixes for Python running on Windows

This issue came back again, both unicode file name problems and further
problems due to timing in unittests.  Fixed this time by mocking and
monkey-patching the time.time function in the QTI tests.


#47 Improve CharClass-derived doc strings

Fixed - no functional changes.


#49 Typo in pyslet/odata2/csdl.py

Fixed OData serialisation of LongDescription element - thanks to
@thomaseitler


#51 Fix processing of dates in JSON format OData communication by the
#server

We now accept ISO string formatted dates for both DateTime and
DateTimeOffset.  Note that providing a timezone other than Z (+00:00)
when setting a DateTime will cause the time to be zone-shifted to UTC
*before* the value is set.  Thanks to @ianwj5int.


#53 Use datetime.date to create datetime object 

You can now set DateTimeValue using a standard python datetime.date, the
value is extended to be 00:00:00 on that date.  Thanks to @nmichaud


#54 Fix use of super to remove self

Fixed Atom Date handling bug, thanks to @nmichaud


#55 Replace `print_exception` with logging (this includes the traceback)

Thanks to @ianwj5int for reporting.


#56 Garbage received when server delays response

This was caused by a bug when handling 401 responses in HTTP client

The issue affected any response that was received as a result of a
resend (after a redirect or 401 response). The stream used to receive
the data in the follow-up request was not being reset correctly and this
resulted in a chunk of 0x00 bytes being written before the actual
content.

This bug was discovered following changes in the 20160209 build when
StringIO was replaced with BytesIO for Python 3 compatibility.
StringIO.truncate moves the stream pointer, BytesIO.truncate does not.
As a result all resends where the 3xx or 401 response had a non-zero
length body were being affected.  Previously the bug only affected the
rarer use case of resends of streamed downloads to real files, i.e.,
requests created by passing an open file in the res_body argument of
ClientRequest.

With thanks to @karurosu for reporting.


#58 OData default values (PUT/PATCH/MERGE)

Warning: if you use Pyslet for an OData server please check that PUTs
are still working as required.

Changed the SQL data stores to use DEFAULT values from the metadata file
as part of the CREATE TABLE queries.  Modified update_entity in memds,
and SQL storage layers to use MERGE semantics by default, added option
to enable replace (PUT) semantics using column defaults. This differs
from the previous (incorrect behaviour) where unselected properties were
set to NULL.

Updated OData server to support MERGE and ensured that PUT now uses the
correct semantics (set to default instead of NULL) for values missing
from the incoming request.

Improved error handling to reduce log noise in SQL layer.


#60 authentication example in docs

Added a first cut at a documentation page for HTTP auth.


#61 Add support for NTLM

Experimental support for NTLM authentication now available using the
python-ntlm3 module from pip/GitHub which must be installed before you
can use NTLM.  The module is in pyslet.ntlmauth and it can be used in a
similar way to Basic auth (see set_ntlm_credentials for details.)

Improved handling of error responses in all HTTP requests (includes a
Python 3 bug fix) to enable the connection to be kept open more easily
during pipelined requests that are terminated early by a final response
from the server. This allows a large POST that generates a 401 response
to abort sending of chunked bodies and retry without opening a new
connection - vital for NTLM which is connection based.

Added automated resend after 417 Expectation failed responses as per
latest HTTP guidance.  (Even for POST requests!)


#64 Add a LICENSE file

Added to distribution


#65 syntax error in sqlds.SQLCollectionBase.sql_expression_substring

Also added an override for SQLite given the lack of support for the
standard substring syntax.


#70 Fix for grouped unary expressions

The bug is best illustrated by attempting to parse OData expressions
containing "(not false)".  Thanks to @torokokill for spotting the issue.


#71 $filter fails when querying fieldnames matching OData literal types

The names that introduce typed literals such as time, datetime, guid,
binary, X, etc. can now be used in URL expressions without raising
parser errors.  The reserved names null, true and false continue to be
interpreted as literals so properties with any of those names cannot be
referred to in expressions.  Thanks to @soundstripe for reporting this.


#72 Travis CI tests failing in Python 3.5

Resolved but Travis no longer builds Python 2.6, see above for details.


#74 New release with bugfixes?

Resolved with the release of 0.7


Untracked Fixes
~~~~~~~~~~~~~~~

HTTP related:

Fixed an issue with HTTP resends (e.g., when following redirects) that
meant that the retry algorithm was causing the client to back off when
more than 1 resend was required.

Added compatibility in HTTP client for parsing dates from headers where
the server uses the zone designator "UTC" instead of the required "GMT".

Fixed a bug where the HTTP client would fail if it received multiple
WWW-Authenticate headers in the same response (parser bug).

Better handling of non-blocking io in HTTP client fixing issues when a
message body is being received to a local stream that is itself blocked.
Includes a new wrapper for RawIOBase in Python 2.6 (with a fix for
blocking stream bug)

Fixed bug in HTTP client when following relative path redirects


XML/HTML Parser:

Deprecated XML Element construction with name override to improve
handling of super.

Fixed a bug in the parsing of HTML content where unexpected elements
that belong in the <head> were causing any preceding <body> content to
be ignored.  Added the get_or_add_child method to XML Elements to deal
with cases where add_child's 'reset' of the element's children is
undesired.

Fixed a bug in the XML parser where the parsed DTD was not being set
in the Document instance.

CDATA sections were not being generated properly by the (old) function
:meth:`pyslet.xml.structures.EscapeCDSect`, causing the HTML style
and script tags to have their content rendered incorrectly.  These tags
are not part of the QTI content model so this bug is unlikely to have
had an impact on real data.

XMLEntity class is now a context manager to help ensure that files are
closed before garbage collection.  Unittests were triggering resource
leak warnings in Python 3.

Fixed a bug in the XML tests that shows up on Windows if the xml test
files are checked out with auto-translation of line ends.


Misc:

Fixed a bug in the detect_encoding function in unicode5 module (most
likely benign).

Added support for expanded dates to iso8601 module (merged from OData v4
branch).

Refactoring of second truncation in iso8601 to use Python decimals.

Fix for comparison of midnight TimePoints not in canonical form

vfs: VirtualFilePath objects are now sortable.

Use of nested generators was triggering future warnings in Python 3,
refactored to catch StopIteration as per:
https://www.python.org/dev/peps/pep-0479/

Added SortableMixin to emulate Python 3 TypeErrors in comparisons and to
simplify implementation of comparison/hash operators in custom classes.
As a result, some Time/TimePoint comparisons which used to raise
ValueError (e.g., due to incompatible precision) now return False for ==
and != operators and raise TypeError for inequalities (<, >, etc). OData
is unaffected as OData time values of the same EDM type are always
comparable.

Re-factored previously undocumented stream classes into their own
module, in particular the Pipe implementation used for inter-thread
communication.  Adding documentation for them.

Re-factored the WSGI InputWrapper from rfc5023 into the http modules.


Sample code:

The sample code has also been updated to work in Python 3, including the
weather OData service using MySQL but this now connects through PyMySQL
as MySQLdb is not supported in Python 3.

scihub.esa.int has been renamed to scihub.copernicus.eu and the sample
code has been updated accordingly with the latest metadata-fixes and
tested using Python 3.


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
