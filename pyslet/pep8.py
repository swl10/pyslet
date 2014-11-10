#! /usr/bin/env python
"""Module for PEP-8 compatibility"""

import warnings
import logging
import string
import sys


def make_attr_name(name):
    """Converts name to pep8_style

    Upper case letters are replaced with their lower-case equivalent
    optionally preceded by '_' if one of the following conditions is
    met:

    *   it was preceded by a lower case letter

    *   it is preceded by an upper case letter and followed by a
        lower-case one

    As a result::

        make_attr_name('aName') == 'a_name'
        make_attr_name('ABCName') == 'abc_name'
        make_attr_name('Name') == 'name'
    """
    if name.islower():
        result = name
    else:
        result = []
        l0 = ''     # char already added
        l1 = ''     # char yet to be added
        for c in name:
            if c.islower():
                if l1.isupper():
                    if l0.isupper() or l0.islower():
                        # ABc -> a_bc
                        # aBc -> a_bc
                        result.append('_')
                        result.append(l1.lower())
                    else:
                        # _Bc -> _bc
                        result.append(l1.lower())
                else:
                    result.append(l1)
            else:
                # same rules for upper or non-letter
                if l1.isupper():
                    if l0.isupper():
                        # ABC -> ab...
                        # AB_ -> ab_
                        result.append(l1.lower())
                    elif l0.islower():
                        # aBC -> a_b...
                        # aB_ -> a_b_
                        result.append('_')
                        result.append(l1.lower())
                    else:
                        # _BC -> _b...
                        # _B_ -> _b_
                        result.append(l1.lower())
                else:
                    result.append(l1)
            l0 = l1
            l1 = c
        # name finishes with upper rules
        if l1.isupper():
            if l0.isupper():
                # AB -> ab
                result.append(l1.lower())
            elif l0.islower():
                # aB -> a_b
                result.append('_')
                result.append(l1.lower())
            else:
                # _B -> _b
                result.append(l1.lower())
        else:
            result.append(l1)
        result = string.join(result, '')
    return result


class RenamedMethod(object):

    """Represents a renamed method

    func
        A function object"""

    def __init__(self, func, new_name=None):
        self.old_name = func.__name__
        if new_name is None:
            self.new_name = make_attr_name(self.old_name)
        else:
            self.new_name = new_name
        self.warned = False

    def target(self, obj):
        if not self.warned:
            if isinstance(obj, type):
                cname = obj.__name__
            else:
                cname = obj.__class__.__name__
            warnings.warn(
                "%s.%s is deprecated, use, %s instead" %
                (cname, self.old_name, self.new_name),
                DeprecationWarning, stacklevel=3)
            self.warned = True
        return getattr(obj, self.new_name)


def renamed_method(func):
    """Provides a decorator for an single renamed method.

    Intended usage::

        class X(object):

            @renamed_method
            def MyMethod(self,....): pass       # noqa

            def my_method(self,....):
                # implementation goes here"""

    func_renamed = RenamedMethod(func)

    def call_renamed(obj, *args, **kwargs):
        return func_renamed.target(obj)(*args, **kwargs)

    return call_renamed


def redirected_method(name):
    """Provides a factory decorator for a custom renamed method.

    Intended usage::

        class X(object):

            @redirected_method('new_method')
            def MyMethod(self,....): pass       # noqa

            def new_method(self,....):
                # implementation goes here"""

    def custom_renamed_method(func):
        func_renamed = RenamedMethod(func, name)

        def call_renamed(obj, *args, **kwargs):
            return func_renamed.target(obj)(*args, **kwargs)

        return call_renamed

    return custom_renamed_method


class RenamedFunction(object):

    """Represents a renamed function

    func
        A function object"""

    def __init__(self, func, new_func=None):
        self.module = func.__module__
        self.old_name = func.__name__
        if new_func is None:
            self.new_func = getattr(sys.modules[func.__module__],
                                    make_attr_name(self.old_name))
        else:
            self.new_func = new_func
        self.warned = False

    def target(self):
        if not self.warned:
            print "Warning!"
            warnings.warn(
                "%s.%s is deprecated, use, %s instead" %
                (self.module, self.old_name, self.new_func.__name__),
                DeprecationWarning, stacklevel=3)
            self.warned = True
        return self.new_func


def renamed_function(func):
    """Provides a decorator for an single renamed function.

    Intended usage::

        @renamed_function
        def MyFunc(self,....): pass     # noqa

        def my_func(self,....):
            # implementation goes here

    IMPORTANT: note that the new function must be defined before the
    renamed function."""

    func_renamed = RenamedFunction(func)

    def call_renamed(*args, **kwargs):
        return func_renamed.target()(*args, **kwargs)

    return call_renamed


def redirected_function(name):
    """Provides a factory decorator for a custom renamed function.

    Intended usage::

        def new_function(self,....):
            # implementation goes here

        @redirected_function(new_function)
        def MyFunction(self,....): pass     # noqa
    
    IMPORTANT: note that the new function must be defined before the
    redirected function."""

    def custom_renamed_method(func):
        func_renamed = RenamedMethod(func, name)

        def call_renamed(obj, *args, **kwargs):
            return func_renamed.target(obj)(*args, **kwargs)

        return call_renamed

    return custom_renamed_method


class PEP8AmbiguousNameError(Exception):
    pass


_pep8_class_dict = {}


def check_class(cls):
    """Checks a class for ambiguous names"""
    if cls not in _pep8_class_dict:
        new_names = {}
        for name in dir(cls):
            new_name = make_attr_name(name)
            if new_name in new_names:
                # we have a name clash!
                if new_name == name:
                    old_name = new_names[name]
                else:
                    old_name = name
                logging.error("%s has dictionary:\n%s", cls.__name__, dir(cls))
                raise PEP8AmbiguousNameError(
                    "%s.%s must be renamed to %s.%s" %
                    (cls.__name__, old_name, cls.__name__, new_name))
            else:
                new_names[new_name] = name
        _pep8_class_dict[cls] = True


class PEP8Compatibility(object):

    _pep8_dict = {}

    def __init__(self):
        check_class(self.__class__)

    def __getattr__(self, name):
        """Retries name in pep8_style

        Converts from WordCaps (or camelCase) as necessary and attempts
        to return an alternative attribute.  If successful it returns
        the computed attribute while raising a deprecation warning.  If
        unsuccessful it raises AttributeError.

        Although this method clearly slows scripts that rely on it,
        __getattr__ is only called when the usual methods of attribute
        resolution have failed so it has a minimal impact on scripts
        that use the new PEP-8 compatible names.

        Warning: the hasattr method will call this method so you can't
        use hasattr to test if a camelCase name is defined when the
        equivalent camel_case does exist as it will return True!

        This method is thread safe but relies on the thread-safety of
        Python's builtin dictionary.  Essentially we keep a cache of
        names so we only have to calculate the mapping once per run.
        Hence we do a {}.get followed by a {}[key] = value, but we don't
        bother with locks between the calls as it is benign if two
        threads both calculate and update the dictionary value
        simultaneously."""
        new_name = self._pep8_dict.get(name, None)
        if new_name is None:
            new_name = make_attr_name(name)
            if new_name == name:
                # we have nothing to add here
                self._pep8_dict[name] = ''
            else:
                self._pep8_dict[name] = new_name
        if new_name:
            result = getattr(self, new_name)
        else:
            # raise attribute error straight away
            raise AttributeError(name)
        warnings.warn(
            "%s.%s is deprecated, use, %s instead" %
            (self.__class__.__name__, name, new_name),
            DeprecationWarning,
            stacklevel=3)
        return result
