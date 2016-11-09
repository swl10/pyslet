Python 2 Compatibility
======================

.. py:module:: pyslet.py2

The goal of Pyslet is to work using the same code in both Python 3 and
Python 2. Pyslet was originally developed in very early versions of
Python 2, it then became briefly dependent on Python 2.7 before settling
down to target Python 2.6 and Python 2.7.

One approach to getting the code working with Python 3 would be to
implement a compatibility module like six which helps code targeted at
Python 2 to run more easily in Python 3.  Unfortunately, the changes
required are still extensive and so more significant transformation is
required.

The purpose of this module is to group together the compatibility issues
that specifically affect Pyslet.  It provides definitions that make the
intent of the Pyslet code clearer.

..	autodata::	py2

..  data::   suffix

    In some cases you may want to use a suffix to differentiate
    something that relates specifically to Python 3 versus Python 2. 
    This string takes the value '3' when Python 3 is in use and is an
    empty string otherwise.
    
    One example where Pyslet uses this is in the stem of a pickled file
    name as such objects tend to be version specific.


Text, Characters, Strings and Bytes 
-----------------------------------

This is the main area where Pyslet has had to change.  In most cases,
Pyslet explicitly wants either Text or Binary data so the Python 3
handling of these concepts makes a lot of sense.

..  function::  u8(arg)

    A wrapper for string literals, obviating the need to use the 'u'
    character that is not allowed in Python 3 prior to 3.3.  The return
    result is a unicode string in Python 2 and a str object in Python 3.
    The argument should be a binary string in UTF-8 format, it is not a
    simple replacement for 'u'.  There are other approaches to this
    problem such as the *u* function defined by compatibility libraries
    such as six.  Use whichever strategy best suits your application.
    
    u8 is forgiving if you accidentally pass a unicode string provided
    that string contains only ASCII characters.  Recommended usage::
    
        my_string = u8(b'hello')
        my_string = u8('hello') # works for ASCII text
        my_string = u8(u'hello') # wrong, but will work for ASCII text
        my_string = u8(b'\xe8\x8b\xb1\xe5\x9b\xbd')
        my_string = u8('\xe8\x8b\xb1\xe5\x9b\xbd') # raises ValueError
        my_string = u8(u'\u82f1\u56fd') # raises ValueError
        my_string = u8('\u82f1\u56fd') # raises ValueError in Python 3 only
    
    The latter examples above resolve to the following two characters:
    "|GB|".
    
    ..  |GB| unicode:: &#x82f1; &#x56fd;
    
    In cases where you only want to encode characters from the
    ISO-8859-1 aka Latin-1 character set you may prefer to use the ul
    function instead.


..  function::  ul(arg)
    
    An alternative wrapper for string literals, similar to :func:`u8`
    but using the latin-1 codec.  ul is a little more forgiving than
    u8::
    
        my_string = ul(b'Caf\xe9')
        my_string = ul('Caf\xe9') # works for Latin text
        my_string = ul(u'Caf\xe9') # wrong, but will work for Latin text

Notice that unicode escapes for characters outside the first 256 are not
allowed in either wrapper.  If you want to use a wrapper that interprets
strings like '\\u82f1\\u56fd' in both major Python versions you should
use a module like six which will pass strings to the unicode_literal
codec.  The approach taken by Pyslet is deliberately different, but has
the advantage of dealing with some awkward cases::

    ul(b'\\user')

The u wrapper in six will throw an error for strings like this::

    six.u('\\user')
    Traceback (most recent call last):
        ...
    UnicodeDecodeError: 'unicodeescape' codec can't decode bytes in
        position 0-4: end of string in escape sequence

Finally, given the increased overhead in calling a function when
interpreting literals consider moving literal definitions to module
level where they appear in performance critical functions::

    CAFE = ul(b"Caf\xe9")
    
    def at_cafe_1(location):
        return location == u"Caf\xe9"

    def at_cafe_2(location):
        return location == CAFE

    def at_cafe_3(location):
        return location == ul(b"Caf\xe9")
    
In a quick test with Python 2, using the execution time of version 1 as
a bench mark version 2 was approximately 1.1 times slower but version 3
was 19 times slower (the results from six.u are about 16 times slower).
The same tests with Python 3 yield about 9 and 3 times slower for ul and
six.u respectvely.

Compatibility comes with a cost, if you only need to support Python 3.3
and higher (while retaining compatibility with Python 2) then you should
use the first form and ignore these literal functions in performance
critical code.  If you want more compatibility then define all string
literals ahead of time, e.g., at module level.

Character Constants
~~~~~~~~~~~~~~~~~~~

These constants are provided to define common character strings (forcing
the unicode type in Python 2).

..  data:: uempty

The empty string.

..  data:: uspace

Single space character, character(0x20).


Text Functions
~~~~~~~~~~~~~~

..  function::  is_string(org)

    Returns True if *arg* is either a character or binary string.

    
..  function::  is_text(arg)

    Returns True if *arg* is text and False otherwise.  In Python 3 this
    is simply a test of whether arg is of type str but in Python 2 both
    str and unicode types return True.  An example usage of this
    function is when checking arguments that may be either text or some
    other type of object.


..  function::  force_text(arg)

    Returns *arg* as text or raises TypeError.  In Python 3 this
    simply checks that arg is of type str, in Python 2 this allows
    either string type but always returns a unicode string.  No codec
    is used so this has the side effect of ensuring that only ASCII
    compatible str instances will be acceptable in Python 2.


..  function::  to_text(arg)

    Returns *arg* as text, converting it if necessary.  In Python 2 this
    always returns a unicode string.  In Python 3, this function is
    almost identical to the built-in *str* except that it takes binary
    data that can be interpreted as ascii and converts it to text.  In
    other words::
    
        to_text(b"hello") == "hello"
    
    In both Python 2 and Python 3.  Whereas the following is only true
    in Python 2::
    
        str(b"hello") == "hello"  

    arg need not be a string, this function will cause an arbitrary
    object's __str__ (or __unicode__ in Python 2) method to be
    evaluated.  


..  function::  is_ascii(arg)

    Returns True if arg is of type str in both Python 2 and Python 3.
    The only difference is that in Python 3 unicode errors will be
    raised if arg contains non-ascii characters.  If arg is not of str
    type then False is returned.
    
    This function is used to check a value in situations where unicode
    is not expected in Python 2.
    
    
..  function::  force_ascii(arg)

    Returns *arg* as ascii text, converting it if necessary.  The result
    is an object of type str, in both python 2 and python 3.  The
    difference is that in Python 2 unicode strings are accepted and
    forced to type str by *encoding* with the 'ascii' codec whereas in
    Python 3 bytes instances are accepted and forced to type str by
    *decoding* with the 'ascii' codec. 

    This function is not needed very often but in some cases Python
    interfaces required type str in Python 2 when the intention was to
    accept ASCII text rather than arbitrary bytes.  When migrated to
    Python 3 these interfaces can be problematic as inputs may be
    generated as ASCII bytes rather than strings in Python 3, e.g., the
    output of base64 encoding.


..	autoclass:: UnicodeMixin
	:members:
	:show-inheritance:


..  function::  is_unicode(arg)

    Returns True if *arg* is unicode text and False otherwise.  In
    Python 3 this is simply a test of whether arg is of type str but in
    Python 2 arg must be a *unicode* string.  This is used in contexts
    where we want to discriminate between bytes and text in all Python
    versions.


..  function::  character(codepoint)

    Given an integer codepoint returns a single unicode character.  You
    can also pass a single byte value (defined as the type returned by
    indexing a binary string).  Bear in mind that in Python 2 this is a
    single-character string, not an integer.  See :func:`byte` for how
    to create byte values dynamically.


..  function::  join_characters(iterable)

    Convenience function for concatenating an iterable of characters (or
    character strings).  In Python 3 this is just::

        ''.join

    In Python 2 it ensures the result is a unicode string.


Bytes
~~~~~

..  function::  to_bytes(arg)

    Returns *arg* as bytes, converting it if necessary.  In Python 2 this
    always returns a plain string and is in fact just an alias for the
    builtin str.  In Python 3, this function is more complex.  If arg
    is an object with a __bytes__ attribute then this is called, otherwise
    the object is converted to a string (using str) and then encoded using
    the 'ascii' codec.
    
    The behaviour of to_bytes in Python 3 may appear similar to the built
    in bytes function but there is an important exception::
    
        x = 2
        str(x) == '2'               # in python 2 and 3
        bytes(x) == b'2'            # in python 2
        bytes(x) == b'\x00\x00'     # in python 3
        to_bytes(x) == b'2'         # in python 2 and 3


..  function::  force_bytes(arg)

    Given either a binary string or a character string, returns a binary
    string of bytes.  If arg is a character string then it is encoded
    with the 'ascii' codec.

    
..  function::  byte(value)

    Given either an integer value in the range 0..255, a
    single-character binary string or a single-character with Unicode
    codepoint in the range 0..255: returns a single byte representing
    that value.  This is one of the main differences between Python 2
    and 3.  In Python 2 bytes are characters and in Python 3 they're
    integers.


..  function::  byte_value(b)

    Given a value such as would be returned by :func:`byte` or by
    indexing a binary string, returns the corresponding integer value. 
    In Python 3 this a no-op but in Python 2 it maps to the builtin
    function ord.


..  function::  join_bytes(arg)

    Given an arg that iterates to yield bytes, returns a bytes object
    containing those bytes.  It is important not to confuse this
    operation with the more common joining of binary strings.  No
    function is provided for that as the following construct works
    as expected in both Python 2 and Python 3::
    
        b''.join(bstr_list)
    
    The usage of join_bytes can best be illustrated by the following two
    interpreter sessions.

    Python 2.7.10::

        >>> from pyslet.py2 import join_bytes
        >>> join_bytes(list(b'abc'))
        'abc'
        >>> b''.join(list(b'abc'))
        'abc'

    Python 3.5.1::

        >>> from pyslet.py2 import join_bytes
        >>> join_bytes(list(b'abc'))
        b'abc'
        >>> b''.join(list(b'abc'))
        Traceback (most recent call last):
          File "<stdin>", line 1, in <module>
        TypeError: sequence item 0: expected a bytes-like object, int found


..  function::  byte_to_bstr(arg)

    Given a single byte, returns a bytes object of length 1 containing
    that byte.  This is a more efficient way of writing::
    
        join_bytes([arg])

    In Python 2 this is a no-operation but in Python 3 it is effectively
    the same as the above.


Printing to stdout
------------------

..	autofunction:: output


Numeric Definitions
-------------------

..  function:: long2

    Missing from Python 3, equivalent to the builtin int.
    

Iterable Fixes 
--------------

Python 3 made a number of changes to the way objects are iterated.

..  function::  range3(*args)

    Uses Python 3 range semantics, maps to xrange in Python 2.


..  function::  dict_keys(d)

    Returns an iterable object representing the keys in the dictionary
    *d*.

..  function::  dict_values(d)

    Returns an iterable object representing the values in the dictionary
    *d*.


Comparisons
-----------

..	autoclass:: SortableMixin
	:members:
	:show-inheritance:

..	autoclass:: CmpMixin
	:members:
	:show-inheritance:


Misc Fixes
----------

Imports the builtins module enabling you to import it from py2 instead
of having to guess between __builtin__ (Python 2) and builtins (Python 3).

..  function::  urlopen(*args, **kwargs)
    
    Imported from urllib.request in Python 3, from urlib in Python 2.


..  function::  urlencode(*args, **kwargs)

    Imported from urllib.parse in Python 3, from urlib in Python 2.


..  function::  urlquote(*args, **kwargs)

    Imported from urllib.parse.quote in Python 3, from urlib.quote in
    Python 2.

..  function::  parse_qs(*args, **kwargs)

    Imported from urllib.parse in Python 3, from urlparse in Python 2.


