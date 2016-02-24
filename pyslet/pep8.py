#! /usr/bin/env python
"""Module for PEP-8 compatibility"""

import inspect
import logging
import types
import warnings

from .py2 import dict_values, py2
from .py26 import get_method_function


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
        result = ''.join(result)
    return result


class MigratedMetaclass(type):

    def __new__(cls, name, bases, dct):
        # firstly, search the bases for renamed methods and check if we
        # have provided overrides
        all_bases = set()
        for base in bases:
            for b in inspect.getmro(base):
                all_bases.add(b)
        # the odd thing is, it doesn't matter which order we look at the
        # bases in, we have to deal with any overrides.  This means we
        # don't have to worry about merging the results of getmro.
        for base in all_bases:
            for m in dict_values(base.__dict__):
                im = get_method_function(m)
                if hasattr(im, 'old_method'):
                    # have we provided an updated definition?
                    if im.old_method.__name__ in dct:
                        override = dct[im.old_method.__name__]
                        if type(m) != type(override):
                            raise TypeError(
                                "%s.%s incorrect method type for override "
                                "%s.%s" % (name, im.__name__, base.__name__,
                                           im.old_method.__name__))
                        # check the new name too
                        if im.__name__ in dct:
                            raise TypeError(
                                "%s.%s collides with renamed %s.%s" % (
                                    name, im.__name__, base.__name__,
                                    im.old_method.__name__))
                        # rename the method
                        dct[im.__name__] = override
                        # remove the old definition
                        del dct[im.old_method.__name__]
                        # Manually patch in something as-if @old_method
                        # had been used here too, that needs a name
                        # change, which will make debugging a little
                        # easier too
                        sm = get_method_function(override)
                        sm.__name__ = im.__name__
                        # This is a bit opaque, but the effect is to
                        # adorn sm with a newly created old_method, we
                        # already have something assigned to the new
                        # name.  The rest of the puzzle will be put in
                        # place below...
                        old_method(im.old_method.__name__, doc=False)(sm)
                    elif im.__name__ in dct:
                        # new code, provides an override, manually
                        # provide an old method wrapper, this reduces
                        # the burden on derived classes and allows us to
                        # rely on a base class to indicate if such
                        # mappings are required.
                        override = dct[im.__name__]
                        sm = get_method_function(override)
                        old_method(im.old_method.__name__, doc=False)(sm)
        # the second part of the metaclass is for class authors who were
        # expecting us (and overrides patched above)... search our
        # dictionary for renamed methods and add the old names pointing
        # to the special logging wrappers before the class is created
        patched_methods = []
        for m in list(dict_values(dct)):
            im = get_method_function(m)
            if hasattr(im, 'old_method'):
                patched_methods.append(im)
                if isinstance(m, (classmethod, staticmethod)):
                    # I want a new class/staticmethod that wraps old_method
                    dct[im.old_method.__name__] = type(m)(im.old_method)
                else:
                    dct[m.old_method.__name__] = im.old_method
        migrated_class = super(MigratedMetaclass, cls).__new__(
            cls, name, bases, dct)
        # to improve to warnings for static overrides, tell these
        # methods where they were originally defined, we have to do this
        # as they won't receive any type of object when called.
        for im in patched_methods:
            im.base = migrated_class
        return migrated_class


if py2:
    class MigratedClass(object):
        __metaclass__ = MigratedMetaclass
else:
    MigratedClass = types.new_class("MigratedClass", (object, ),
                                    {'metaclass': MigratedMetaclass})


class DeprecatedMethod(object):

    """Represents a renamed method

    func
        A function object"""

    def __init__(self, new_func, old_name):
        self.old_name = old_name
        self.new_func = new_func
        self.new_name = new_func.__name__
        self.warned = False

    def call(self, *args, **kwargs):
        if not self.warned:
            cname = self.new_func.base.__name__
            warnings.warn(
                "%s.%s is deprecated, use, %s instead" %
                (cname, self.old_name, self.new_name),
                DeprecationWarning, stacklevel=3)
            self.warned = True
        return self.new_func(*args, **kwargs)


def old_method(name, doc=True):

    def custom_renamed_method(func):
        func_renamed = DeprecatedMethod(func, name)

        def call_renamed(*args, **kwargs):
            return func_renamed.call(*args, **kwargs)

        # here's the clever bit, add the old method as an attribute to
        # the func being defined.
        call_renamed.__name__ = name
        func.old_method = call_renamed
        if doc:
            func.old_method.__doc__ = "Deprecated equivalent to "\
                ":meth:`%s`" % func.__name__
        return func

    return custom_renamed_method


class DeprecatedFunction(object):

    """Represents a renamed function

    new_func
        A function object

    old_name
        The old name"""

    def __init__(self, new_func, old_name):
        self.old_name = old_name
        self.new_func = new_func
        self.new_name = new_func.__name__
        self.module = new_func.__module__
        self.warned = False

    def call(self, *args, **kwargs):
        if not self.warned:
            warnings.warn(
                "%s.%s is deprecated, use, %s instead" %
                (self.module, self.old_name, self.new_name),
                DeprecationWarning, stacklevel=3)
            self.warned = True
        return self.new_func(*args, **kwargs)


def old_function(name):
    """Provides a factory decorator for a renamed function

    Intended usage::

        @old_function('OldFunction')
        def new_function(....):
            # implementation here

    The old function is created using a wrapper that issues a
    deprecation warning and is added to the global scope in which the
    new function is being defined."""

    def custom_renamed_function(func):
        func_renamed = DeprecatedFunction(func, name)

        def call_renamed(*args, **kwargs):
            return func_renamed.call(*args, **kwargs)

        call_renamed.__name__ = name
        func.old_function = call_renamed
        func.old_function.__doc__ = "Deprecated equivalent to "\
            ":func:`%s`" % func.__name__
        func.__globals__[name] = call_renamed
        return func

    return custom_renamed_function


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


class PEP8Compatibility(MigratedClass):

    _pep8_dict = {}

    def __init__(self):
        # check_class(self.__class__)
        pass

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

        Warning: the hasattr function will call this method so you can't
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
