XML: Introduction
=================

XML is an integral part of many standards for LET but Pyslet takes a
slightly different approach from the pre-existing XML support in the
Python language.  XML elements are represented by instances of a basic
:class:`Element` class which can be used as a base class to customize
document processing for specific types of XML document.  It also allows
these XML elements to 'come live' with additional methods and behaviours.
