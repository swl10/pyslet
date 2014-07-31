#! /usr/bin/env python
"""Module for PEP-8 compatibility"""

import warnings
import string


class PEP8Compatibility(object):

    _pep8_dict = {}

    @classmethod
    def make_attr_name(cls, name):
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

        This method is thread safe but relies on the thread-safety of
        Python's builtin dictionary.  Essentially we keep a cache of
        names so we only have to calculate the mapping once per run.
        Hence we do a {}.get followed by a {}[key] = value, but we don't
        bother with locks between the calls as it is benign if two
        threads both calculate and update the dictionary value
        simultaneously."""
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

    def __getattr__(self, name):
        """Retries name in pep8_style

        Converts from WordCaps (or camelCase) as necessary and attempts
        to return an alternative attribute.  If successful it returns
        the computed attribute while raising a deprecation warning.  If
        unsuccessful it raises AttributeError.

        Although this method clearly slows scripts that rely on it
        __getattr__ is only called when the usual methods of attribute
        resolution have failed so it has a minimal impact on scripts
        that use the new PEP-8 compatible names."""
        new_name = self._pep8_dict.get(name, None)
        if new_name is None:
            new_name = self.make_attr_name(name)
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
