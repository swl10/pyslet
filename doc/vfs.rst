File System Abstraction
=======================

.. py:module:: pyslet.vfs

The purpose of this module is to provide an abstraction over the top the
native file system, potentially allowing alternative implementations to
be provided in the future.  This module was particularly developed with
operating environments where access to the file system is limited or
not-allowed.  Pyslet modules that use these classes to access the file
system can be easily repointed at some other implementation.

..	autoclass:: VirtualFilePath
	:members:
	:show-inheritance:


Accessing the Local File System
-------------------------------

..  autoclass:: OSFilePath
	:members:
	:show-inheritance:


Misc Definitions
----------------

..  autoclass:: ZipHooks
	:members:
	:show-inheritance:


