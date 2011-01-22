PyAssess
========

2005-11-27

Introduction
------------

PyAssess is a set of python modules that can be used to help implement
applications that support the IMS Question and Test Interoperability (QTI) data
model.

You might like to try the demonstrator application to get a flavour of what the
toolkit can do (see below).

There is no documentation at the moment (though use of pydoc may tell you
something) and the code is very much work in progress.  However, this release
has a working set of tests that you can run by changing to the top level
PyAssess directory (the one containing this file) and running the test.py
command.

You might also like to look at the testdata directory, which contains a wide
range of QTI items designed to seek out incompatibilities in QTI
implementations.

For more information about QTI, please send an email to:
swl10@cam.ac.uk - I'm not always as fast as I'd like to be
in replying so please be patient.


Installation
------------

To install the PyAssess modules for use from your own scripts just run:

python setup.py install


Demonstrator
------------

This release of the PyAssess toolkit contains a new command-line demonstration
tool.  The tool allows you to play with (and debug) QTI item files.  To run the
demo just run:

python demo.py

The tool has a basic help facility which should get you going.


Release Log
-----------

Notes: 2005-11-27

Added the command-line demonstrator program.

Vastly increased support for response processing, including a tricky routine to
convert regular expressions in the XML Schema reg. exp. language (also used in
QTI) to the python reg. exp. language.


Notes: 2005-07-20

This was the first public release of PyAssess, the main purpose of this release
was to create a snapshot of the code as used at the CETIS/ELF CodeBash, July
20th 2005 in Glasgow.

