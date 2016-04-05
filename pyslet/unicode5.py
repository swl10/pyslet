#! /usr/bin/env python
"""Utilities to aid interaction with the unicode database"""

import logging
import os.path

from sys import maxunicode
from pickle import dump, load

from .py2 import (
    byte,
    byte_value,
    character,
    dict_values,
    force_text,
    is_text,
    is_unicode,
    join_bytes,
    py2,
    range3,
    suffix,
    to_text,
    ul,
    UnicodeMixin,
    urlopen)
from .pep8 import PEP8Compatibility


UCDDatabaseURL = "http://www.unicode.org/Public/UNIDATA/UnicodeData.txt"
UCDBlockDatabaseURL = "http://www.unicode.org/Public/UNIDATA/Blocks.txt"
UCDCategories = {}
UCDBlocks = {}

CATEGORY_FILE = "unicode5_catogories%s.pck" % suffix
BLOCK_FILE = "unicode5_blocks%s.pck" % suffix


MAGIC_TABLE = {
    # UCS-4, big-endian machine (1234 order)
    b'\x00\x00\xfe\xff': 'utf_32_be',
    # UCS-4, little-endian (4321 order)
    b'\xff\xfe\x00\x00': 'utf_32_le',
    # UCS-4, unusual octet order (2143)
    b'\x00\x00\xff\xfe': 'utf_32',
    # UCS-4, unusual octet order (3412)
    b'\xfe\xff\x00\x00': 'utf_32',
    # UTF-16, big-endian
    b'\xfe\xff\x00\x2a': 'utf_16_be',
    # UTF-16, little-endian
    b'\xff\xfe\x2a\x00': 'utf_16_le',
    # UCS-4 or other encoding with a big-endian 32-bit code unit
    b'\x00\x00\x00\x2a': 'utf_32_be',
    # UCS-4 or other encoding with a little-endian 32-bit code unit
    b'\x2a\x00\x00\x00': 'utf_32_le',
    # UCS-4 or other encoding with an unusual 32-bit code unit
    b'\x00\x00\x2a\x00': 'utf_32_le',
    # UCS-4 or other encoding with an unusual 32-bit code unit
    b'\x00\x2a\x00\x00': 'utf_32_le',
    # UTF-16BE or big-endian ISO-10646-UCS-2 or other encoding with a
    # 16-bit code unit
    b'\x00\x2a\x00\x2a': 'utf_16_be',
    # UTF-16LE or little-endian ISO-10646-UCS-2 or other encoding with a
    # 16-bit code unit
    b'\x2a\x00\x2a\x00': 'utf_16_le',
    # UTF-8, ISO 646, ASCII or similar
    b'\x2a\x2a\x2a\x2a': 'utf_8'
}


def detect_encoding(magic):
    """Detects text encoding

    magic
        A string of bytes

    Given a byte string this function looks at (up to) four bytes and
    returns a best guess at the unicode encoding being used for the
    data.

    It returns a string suitable for passing to Python's native decode
    method, e.g., 'utf_8'.  The default is 'utf_8', an encoding which
    will also work if the data is plain ASCII."""
    if magic[0:3] == b'\xef\xbb\xbf':
        # catch this odd one first
        return 'utf_8_sig'
    # now we're only interested in a handful of values
    keepers = b"\x00\xfe\xff"
    key = []
    for i in range3(4):
        # star - as good as any
        if i >= len(magic):
            key.append(byte(0x2A))
        elif magic[i] in keepers:
            key.append(magic[i])
        else:
            key.append(byte(0x2A))
    key = join_bytes(key)
    if key in MAGIC_TABLE:
        return MAGIC_TABLE[key]
    else:
        return None


class CharClass(UnicodeMixin):

    """Represents a class of unicode characters.

    A class of characters is represented internally by a list of
    character ranges that define the class.  This is efficient because
    most character classes are defined in blocks of characters.

    For the constructor, multiple arguments can be provided.

    String arguments add all characters in the string to the class.  For
    example, CharClass('abcxyz') creates a class comprising two ranges:
    a-c and x-z.

    Tuple/List arguments can be used to pass pairs of characters that
    define a range.  For example, CharClass(('a','z')) creates a class
    comprising the letters a-z.

    Instances of CharClass can also be used in the constructor to add an
    existing class.

    Instances support Python's repr function::

        >>> c = CharClass('abcxyz')
        >>> print repr(c)
        CharClass((u'a',u'c'), (u'x',u'z'))

    The string representation of a CharClass is a python regular
    expression suitable for matching a single character from the
    CharClass::

        >>> print str(c)
        [a-cx-z]

    """

    @classmethod
    def ucd_category(cls, category):
        """Returns the character class representing the Unicode category.

        You must *not* modify the returned instance, if you want to
        derive a character class from one of the standard Unicode
        categories then you should create a copy by passing the result
        of this class method to the CharClass constructor, e.g. to
        create a class of all general controls and the space character::

                c=CharClass(CharClass.ucd_category(u"Cc"))
                c.add_char(u" ")"""
        global UCDCategories
        if not UCDCategories:
            # The category table is empty, so we need to load it
            load_category_table()
        return UCDCategories[category]

    @classmethod
    def ucd_block(cls, block_name):
        """Returns the character class representing the Unicode block.

        You must not modify the returned instance, if you want to derive
        a character class from one of the standard Unicode blocks then
        you should create a copy by passing the result of this class
        method to the CharClass constructor, e.g. to create a class
        combining all Basic Latin characters and those in the Latin-1
        Supplement::

            c=CharClass(CharClass.ucd_block(u"Basic Latin"))
            c.add_class(CharClass.ucd_block(u"Latin-1 Supplement")"""
        global UCDBlocks
        if not UCDBlocks:
            # The block table is empty, so we need to load it
            load_block_table()
        return UCDBlocks[_normalize_block_name(block_name)]

    def __init__(self, *args):
        self.ranges = []
        self._clear_cache()
        for arg in args:
            if is_text(arg):
                # Each character in the string is put in the class
                for c in arg:
                    self.add_char(c)
            elif type(arg) in (tuple, list):
                self.add_range(arg[0], arg[1])
            elif isinstance(arg, CharClass):
                self.add_class(arg)
            else:
                raise ValueError

    def __repr__(self):
        result = ['CharClass(']
        first_range = True
        for r in self.ranges:
            if first_range:
                first_range = False
            else:
                result.append(', ')
            if r[0] == r[1]:
                result.append(repr(r[0]))
            else:
                result.append('(')
                result.append(repr(r[0]))
                result.append(',')
                result.append(repr(r[1]))
                result.append(')')
        result.append(')')
        return ''.join(result)

    _set_controls = {
        ul("\x07"): ul("\\a"),
        ul("\x08"): ul("\\b"),
        ul("\x09"): ul("\\t"),
        ul("\x0A"): ul("\\n"),
        ul("\x0B"): ul("\\v"),
        ul("\x0C"): ul("\\f"),
        ul("\x0D"): ul("\\r")}

    _set_escapes = ul("-\\]")
    _backslash = ul("\\")

    def _set_escape(self, c):
        """Escapes characters for inclusion in a set, i.e., -, \,  and ]"""
        if c in self._set_escapes:
            return self._backslash + c
        else:
            return self._set_controls.get(c, c)

    _re_controls = {
        ul("\x07"): ul("\\a"),
        ul("\x09"): ul("\\t"),
        ul("\x0A"): ul("\\n"),
        ul("\x0B"): ul("\\v"),
        ul("\x0C"): ul("\\f"),
        ul("\x0D"): ul("\\r")}

    _re_escapes = ul(".^$*+?{}\\[]|()")

    def _re_escape(self, c):
        """Escapes characters for inclusion in a regular expression
        outside a set"""
        if c in self._re_escapes:
            return self._backslash + c
        else:
            return self._re_controls.get(c, c)

    _empty_range = ul("[^\\x00-%s]") % character(maxunicode)

    def __unicode__(self):
        result = []
        if len(self.ranges) == 0:
            # we generally try and avoid representing maxunicode in a range
            # by using negation.  However, in the case of an empty range
            # we have no choice.
            return self._empty_range
        elif self.ranges[-1][1] == character(maxunicode):
            # to avoid maxunicode we negate this range
            neg = CharClass(self)
            neg.negate()
            result = to_text(neg)
            if result[0] == "[":
                return "[^%s]" % result[1:-1]
            elif result[0] == "\\":
                # we may not need the escape
                if result == "\\]":
                    return "[^\\]]"
                elif result in dict_values(self._re_controls):
                    return "[^%s]" % result
                else:
                    return "[^%s]" % result[1]
            else:
                return "[^%s]" % result
        if len(self.ranges) == 1:
            r = self.ranges[0]
            if r[0] == r[1]:
                # a single character
                return self._re_escape(r[0])
        add_caret = False
        for r in self.ranges:
            if r[0] == "^":
                add_caret = True
                r0 = u"_"
            else:
                r0 = r[0]
            if ord(r0) > ord(r[1]):
                continue
            elif r0 == r[1]:
                # just a singleton
                result.append(self._set_escape(r0))
            elif ord(r0) + 1 == ord(r[1]):
                # a dumb range, remove the hyphen
                result.append(
                    "%s%s" % (self._set_escape(r0), self._set_escape(r[1])))
            else:
                result.append("%s-%s" %
                              (self._set_escape(r0), self._set_escape(r[1])))
        if add_caret:
            result.append(u'^')
        return u"[%s]" % u"".join(result)

    def format_re(self):
        """Create a representation of the class suitable for putting in
        [] in a python regular expression"""
        py_charset = []
        for a, z in self.ranges:
            py_charset.append(self.format_re_char(a))
            if a == z:
                continue
            if ord(z) > ord(a) + 1:
                py_charset.append('-')
            py_charset.append(self.format_re_char(z))
        return ''.join(py_charset)

    def format_re_char(self, c):
        if c in "-]\\":
            # prepen a backslash
            return "\\" + c
        else:
            return c

    def __eq__(self, other):
        """Compares two character classes for equality."""
        return self.ranges == other.ranges

    def add_range(self, a, z):
        """Adds a range of characters from a to z to the class"""
        # our implementation assumes that codepoint is used in
        # comparisons
        a = force_text(a)
        z = force_text(z)
        if z < a:
            x = z
            z = a
            a = x
        if self.ranges:
            match_a, index_a = self._bisection_search(a, 0,
                                                      len(self.ranges) - 1)
            match_z, index_z = self._bisection_search(z, 0,
                                                      len(self.ranges) - 1)
            if match_a:
                if match_z:
                    # Both ends of the new range are already matched
                    if index_a == index_z:
                        # Nothing to do
                        return
                    else:
                        # We need to join the ranges from index_a to and
                        # including index_z
                        self.ranges[index_a:index_z + 1] = [
                            [self.ranges[index_a][0], self.ranges[index_z][1]]]
                else:
                    # Note that at this point, index_z must be > index_a
                    # We need to join the ranges from index_a up to but
                    # *not* including index_z extending the last range to
                    # include z
                    self.ranges[
                        index_a:index_z] = [[self.ranges[index_a][0], z]]
            elif match_z:
                # We need to join the ranges from index_a up to and
                # including index_z extending the first range to include
                # a (works even if index_a==index_z)
                self.ranges[
                    index_a:index_z + 1] = [[a, self.ranges[index_z][1]]]
            else:
                # We need to join the ranges from index_a to index_z-1,
                # extending them to include a and z respectively.  Note
                # that if index_a==index_z then no ranges are joined and
                # the slice assignment simply inserts a new range.
                self.ranges[index_a:index_z] = [[a, z]]
            self._merge(index_a)
        else:
            self.ranges = [[a, z]]
        self._clear_cache()

    def subtract_range(self, a, z):
        """Subtracts a range of characters from the character class"""
        a = force_text(a)
        z = force_text(z)
        if z < a:
            x = z
            z = a
            a = x
        if self.ranges:
            match_a, index_a = self._bisection_search(a, 0,
                                                      len(self.ranges) - 1)
            match_z, index_z = self._bisection_search(z, 0,
                                                      len(self.ranges) - 1)
            if match_a:
                if match_z:
                    # Both ends of the new range are matched
                    if index_a == index_z:
                        # a-z is entirely within a single range
                        rlower, rupper = self.ranges[index_a]
                        if ord(rlower) == ord(rupper) or (
                                ord(rlower) == ord(a) and
                                ord(rupper) == ord(z)):
                            # This is either a singleton range, so a==z
                            # must be true too! or we have an exact
                            # range match
                            del self.ranges[index_a]
                        elif ord(rlower) == ord(a):
                            # Remove the left portion of the range
                            self.ranges[index_a][0] = character(ord(z) + 1)
                        elif ord(rupper) == ord(z):
                            # Remove the right portion of the range
                            self.ranges[index_a][1] = character(ord(a) - 1)
                        else:
                            # We need to split this range
                            self.ranges[index_a][1] = character(ord(a) - 1)
                            self.ranges.insert(
                                index_a + 1,
                                [character(ord(z) + 1), rupper])
                    else:
                        # We need to trim index_a and index_z and remove all
                        # ranges between
                        rlower, rupper = self.ranges[index_a]
                        if ord(rlower) == ord(rupper) or ord(a) == ord(rlower):
                            # remove this entire range
                            snip_a = index_a
                        else:
                            # Remove the right portion of the range
                            self.ranges[index_a][1] = character(ord(a) - 1)
                            snip_a = index_a + 1
                        rlower, rupper = self.ranges[index_z]
                        if ord(rlower) == ord(rupper) or ord(z) == ord(rupper):
                            # remove this entire range
                            snip_z = index_z + 1
                        else:
                            # Remove the left portion of the range
                            self.ranges[index_z][0] = character(ord(z) + 1)
                            snip_z = index_z
                        if snip_z >= snip_a:
                            del self.ranges[snip_a:snip_z]
                else:
                    # We need to trim index_a and delete up to, but not
                    # including, index_z
                    rlower, rupper = self.ranges[index_a]
                    if ord(rlower) == ord(rupper) or ord(a) == ord(rlower):
                        snip = index_a
                    else:
                        self.ranges[index_a][1] = character(ord(a) - 1)
                        snip = index_a + 1
                    del self.ranges[snip:index_z]
            elif match_z:
                # We need to trim index_z and delete to the left up to and
                # including index_a
                rlower, rupper = self.ranges[index_z]
                if ord(rlower) == ord(rupper) or ord(z) == ord(rupper):
                    snip = index_z + 1
                else:
                    self.ranges[index_z][0] = character(ord(z) + 1)
                    snip = index_z
                del self.ranges[index_a:snip]
            else:
                # We need to remove the ranges from index_a to index_z-1.
                # Note that if index_a==index_z then no ranges are removed
                del self.ranges[index_a:index_z]
        self._clear_cache()

    def add_char(self, c):
        """Adds a single character to the character class"""
        c = force_text(c)
        if self.ranges:
            match, index = self._bisection_search(c, 0, len(self.ranges) - 1)
            if not match:
                self.ranges.insert(index, [c, c])
                self._merge(index)
        else:
            self.ranges = [[c, c]]
        self._clear_cache()

    def subtract_char(self, c):
        """Subtracts a single character from the character class"""
        c = force_text(c)
        if self.ranges:
            match, index = self._bisection_search(c, 0, len(self.ranges) - 1)
            if match:
                a, z = self.ranges[index]
                if ord(a) == ord(z):
                    # This is a singleton range
                    del self.ranges[index]
                elif ord(a) == ord(c):
                    self.ranges[index][0] = character(ord(a) + 1)
                elif ord(z) == ord(c):
                    self.ranges[index][1] = character(ord(z) - 1)
                else:
                    # We need to split this range
                    self.ranges[index][1] = character(ord(c) - 1)
                    self.ranges.insert(index + 1,
                                       [character(ord(c) + 1), z])
        self._clear_cache()

    def add_class(self, c):
        """Adds all the characters in c to the character class

        This is effectively a union operation."""
        if self.ranges:
            for r in c.ranges:
                self.add_range(r[0], r[1])
        else:
            # take a short cut here, if we have no ranges yet just copy them
            for r in c.ranges:
                self.ranges.append(r)
        self._clear_cache()

    def subtract_class(self, c):
        """Subtracts all the characters in c from the character class"""
        for r in c.ranges:
            self.subtract_range(r[0], r[1])
        self._clear_cache()

    def negate(self):
        """Negates this character class

        As a convenience returns the object as the result enabling
        this method to be used in construction, e.g.::

            c = CharClass('\x0a\x0d').negate()

        Results in the class of all characters *except* line feed and
        carriage return."""
        max = CharClass([character(0), character(maxunicode)])
        max.subtract_class(self)
        self.ranges = max.ranges
        self._clear_cache()
        return self

    def _merge(self, index):
        """Used internally to merge the range at index with its
        neighbours if possible"""
        a, z = self.ranges[index]
        index_a = index_z = index
        if index_a > 0:
            ap = self.ranges[index_a - 1][1]
            if ord(ap) >= ord(a) - 1:
                # Left merge
                index_a = index_a - 1
        if index_z < len(self.ranges) - 1:
            zn = self.ranges[index_z + 1][0]
            if ord(zn) <= ord(z) + 1:
                # Right merge
                index_z = index_z + 1
        if index_a != index_z:
            # Do the merge
            self.ranges[
                index_a:index_z + 1] = [[self.ranges[index_a][0],
                                         self.ranges[index_z][1]]]

    def _clear_cache(self):
        self._block_cache = [None] * 256

    def test(self, c):
        """Test a unicode character.

        Returns True if the character is in the class.

        If c is None, False is returned.

        This function uses an internal cache to speed up tests of
        complex classes.  Test results are cached in 256 character
        blocks.  The cache does not require a lock to make this method
        thread-safe (a lock would have a significant performance
        penalty) as it uses a simple python list.  The worst case race
        condition would result in two separate threads calculating the
        same block simultaneously and assigning it the same slot in the
        cache but python's list object is thread-safe under assignment
        (and the two calculated blocks will be identical) so this is not
        an issue.

        Why does this matter?  This function is called a lot,
        particularly when parsing XML.  When parsing a tag the parser
        will repeatedly test each character to determine if it is a
        valid name character and the definition of name character is
        complex.  Here are some illustrative figures calculated using
        cProfile for a typical 1MB XML file which calls test 142198
        times: with no cache 0.42s spent in test, with the cache 0.11s
        spent."""
        if c is None:
            return False
        elif self.ranges:
            cv = ord(c)
            block_num = cv >> 8
            try:
                block = self._block_cache[block_num]
                if block is None:
                    block = bytearray(256)
                    ccode = block_num * 256
                    match, index = self._bisection_search(
                        character(ccode), 0, len(self.ranges) - 1)
                    # match == True means we're in the indexed range
                    # match == False means indexed range is after us
                    block[0] = match
                    if index < len(self.ranges):
                        rmatch = self.ranges[index]
                        cmin = ord(rmatch[0])
                        cmax = ord(rmatch[1])
                    else:
                        rmatch = False
                    for i in range3(1, 256):
                        ccode += 1
                        if match:
                            # have we left this range?
                            if ccode > cmax:
                                index += 1
                                if index < len(self.ranges):
                                    rmatch = self.ranges[index]
                                    cmin = ord(rmatch[0])
                                    cmax = ord(rmatch[1])
                                else:
                                    rmatch = None
                                match = False
                            else:
                                block[i] = True
                                continue
                        # have we entered this range
                        if rmatch and ccode >= cmin:
                            block[i] = True
                            match = True
                    self._block_cache[block_num] = block
                block_pos = cv & 0xFF
                if block[block_pos]:
                    return True
                else:
                    return False
            except IndexError:
                # deal with wide Unicode characters using standard search
                match, index = self._bisection_search(
                    c, 0, len(self.ranges) - 1)
                return match
        else:
            return False

    def test_slow(self, c):
        if c is None:
            return False
        elif self.ranges:
            match, index = self._bisection_search(
                c, 0, len(self.ranges) - 1)
            return match
        else:
            return False

    def _bisection_search(self, c, rmin, rmax):
        """Performs a recursive bisection search for c.

        c is the character to search for rmin and rmax define a slice on
        the list of ranges in which to search

        The result is a tuple comprising a flag indicating if c is in
        the part of the class being searched and an integer index of the
        range into which c falls or, if c was not found, then it is the
        index at which a new range (containing only c) should be
        inserted."""
        if rmin == rmax:
            # is c in this range
            if c > self.ranges[rmin][1]:
                return (False, rmin + 1)
            elif c < self.ranges[rmin][0]:
                return (False, rmin)
            else:
                return (True, rmin)
        else:
            rtry = (rmin + rmax) // 2
            if c <= self.ranges[rtry][1]:
                return self._bisection_search(c, rmin, rtry)
            else:
                return self._bisection_search(c, rtry + 1, rmax)


def load_category_table():
    """Loads the category table from a resource file."""
    global UCDCategories
    f = open(os.path.join(os.path.dirname(__file__), CATEGORY_FILE), 'rb')
    UCDCategories = load(f)
    f.close()


def _get_cat_class(cat_name):
    global UCDCategories
    if cat_name in UCDCategories:
        return UCDCategories[cat_name]
    else:
        cat = CharClass()
        UCDCategories[cat_name] = cat
        return cat


def parse_category_table():
    global UCDCategories
    UCDCategories = {}
    next_code = 0
    mark = None
    mark_major_category = None
    mark_minor_category = None
    n_major_cat = _get_cat_class(u'C')
    n_minor_cat = _get_cat_class(u'Cn')
    for line in urlopen(UCDDatabaseURL).readlines():
        # disregard any comments
        line = to_text(line)
        line = line.split('#')[0]
        if not line:
            continue
        fields = line.split(';')
        code_point = int(fields[0], 16)
        assert code_point >= next_code, \
            "Unicode database error: code points went backwards: at %08X" % \
            code_point
        if code_point > maxunicode:
            logging.warning(
                "Warning: category table limited by narrow python build")
            break
        category = fields[2].strip()
        assert len(category) == 2, "Unexpected category field"
        major_category = _get_cat_class(category[0])
        minor_category = _get_cat_class(category)
        char_name = fields[1].strip()
        if mark is None:
            if char_name[0] == '<' and char_name[-6:] == "First>":
                mark = code_point
                mark_major_category = major_category
                mark_minor_category = minor_category
            else:
                major_category.add_char(character(code_point))
                minor_category.add_char(character(code_point))
            if code_point > next_code:
                # we have skipped a load of code-points
                n_major_cat.add_range(character(next_code),
                                      character(code_point - 1))
                n_minor_cat.add_range(character(next_code),
                                      character(code_point - 1))
        else:
            # end a marked range
            assert minor_category == mark_minor_category, \
                "Unicode character range end-points with non-matching "\
                "general categories"
            mark_major_category.add_range(character(mark),
                                          character(code_point))
            mark_minor_category.add_range(character(mark),
                                          character(code_point))
            mark = None
            mark_major_category = None
            mark_minor_category = None
        next_code = code_point + 1
    # when we finally exit from this loop we should not be in a marked range
    assert mark is None, \
        "Unicode database ended during character range definition: %08X-?" % \
        mark
    f = open(os.path.join(os.path.dirname(__file__), CATEGORY_FILE), 'wb')
    dump(UCDCategories, f)
    f.close()


def load_block_table():
    """Loads the block table from a resource file."""
    global UCDBlocks
    f = open(os.path.join(os.path.dirname(__file__), BLOCK_FILE), 'rb')
    UCDBlocks = load(f)
    f.close()


def _normalize_block_name(block_name):
    """Implements Unicode name normalization for block names.

    Removes white space, '-', '_' and forces lower case."""
    block_name = ''.join(block_name.split())
    block_name = block_name.replace('-', '')
    return block_name.replace('_', '').lower()


def parse_block_table():
    global UCDBlocks
    UCDBlocks = {}
    narrow_warning = False
    for line in urlopen(UCDBlockDatabaseURL).readlines():
        line = to_text(line)
        line = line.split('#')[0].strip()
        if not line:
            continue
        fields = line.split(';')
        code_points = fields[0].strip().split('..')
        code_point0 = int(code_points[0], 16)
        code_point1 = int(code_points[1], 16)
        # the Unicode standard tells us to remove -, _ and any whitespace
        # before case-ignore comparison
        block_name = _normalize_block_name(fields[1])
        if code_point0 > maxunicode:
            if not narrow_warning:
                logging.warning(
                    "Warning: block table limited by narrow python build")
            narrow_warning = True
            continue
        elif code_point1 > maxunicode:
            code_point1 = maxunicode
            if not narrow_warning:
                logging.warning(
                    "Warning: block table limited by narrow python build")
            narrow_warning = True
        UCDBlocks[block_name] = CharClass(
            (character(code_point0), character(code_point1)))
    f = open(os.path.join(os.path.dirname(__file__), BLOCK_FILE), 'wb')
    dump(UCDBlocks, f)
    f.close()


class ParserError(ValueError):

    """Exception raised by :class:`BasicParser`

    production
        The name of the production being parsed

    parser
        The :class:`BasicParser` instance raising the error (optional)

    ParserError is a subclass of ValueError."""

    def __init__(self, production, parser=None):
        self.production = production
        if parser:
            #: the position of the parser when the error was raised
            self.pos = parser.pos
            #: up to 40 characters/bytes to the left of pos
            self.left = parser.src[max(0, self.pos - 40):self.pos]
            #: up to 40 characters/bytes to the right of pos
            self.right = parser.src[self.pos:self.pos + 40]
            if production:
                msg = "ParserError: expected %s at [%i]" % (production,
                                                            self.pos)
            else:
                msg = "ParserError: at [%i]" % self.pos
        else:
            self.pos = None
            self.left = None
            self.right = None
            if production:
                msg = "ParserError: expected %s" % production
            else:
                msg = "ParserError"
        ValueError.__init__(self, msg)


class ParserMixin(object):

    """A mix-in class for parsing

    These methods help establish a common pattern across parsers by
    providing a conversion between look-ahead and non-look ahead style
    parsing methods.

    Derived classes must define the following.

        parser_error
            a method for raising an error detected during parsing that
            takes an optional character string describing the production
            being parsed.

        match_end
            a method for determining if the parser has consumed all
            the input.

        pos
            an attribute containing the current position

        setpos
            a method for setting *pos* from a previously saved value."""

    def require_production(self, result, production=None):
        """Returns *result* if not None or raises ParserError.

            result
                The result of a parse_* type method.

            production
                Optional string used to customise the error message.

        This method is intended to be used as a conversion function
        allowing any parse_* method to be converted into a require_*
        method.  E.g.::

            p = BasicParser("hello")
            num = p.require_production(p.parse_integer(), "Number")

            ParserError: Expected Number at [0]"""
        if result is None:
            self.parser_error(production)
        else:
            return result

    def parse_production(self, require_method, *args, **kwargs):
        """Executes the bound method *require_method*.

            require_method
                A bound method that will be called with \*args

            args
                The positional arguments to pass to require_method

            kwargs
                The keyword arguments to pass to require_method

        This method is intended to be used as a conversion function
        allowing any require_* method to be converted into a parse_*
        method for the purposes of look-ahead.

        If successful the result of the method is returned.  If any
        ValueError (including :class:`ParserError`) is raised, the
        exception is caught, the parser rewound and None is returned."""
        savepos = self.pos
        try:
            return require_method(*args, **kwargs)
        except ValueError:
            self.setpos(savepos)
            return None

    def require_end(self, production='end'):
        """Tests that the parser has consumed all the source

        There is no return result."""
        if not self.match_end():
            self.parser_error(production)

    def require_production_end(self, result, production=None):
        """Returns *result* if not None and parsing is complete.

        This method is similar to :meth:`require_production` except that
        it enforces the constraint that the entire source must have been
        parsed.  Essentially, it just calls :meth:`require_end` before
        returning *result*."""
        result = self.require_production(result, production)
        self.require_end(production)
        return result


class BasicParser(ParserMixin, PEP8Compatibility):

    """A base class for parsing character strings or binary data

    source
        Can be either a string of characters or a string of bytes.

    BasicParser instances can parse either characters or bytes but not
    both simultaneously, you must choose on construction by passing an
    appropriate str (Python 2: unicode), bytes or bytearray object.

    Binary mode is suitable for parsing data described in terms of
    OCTETS, such as many IETF and internet standards.  When passing
    string literals to parsing methods in binary mode use the binary
    string literal form::

        parser.match(b':')

    Methods that return the parsed data in its original form will also
    return bytes objects in binary mode.

    Methods are named according to the type of operation they perform.

        match\_*
            Returns a boolean True or False depending on whether or not
            a syntax production is matched at the current location. The
            state of the parser is unchanged.  This type of method is
            only used for very simple productions, e.g.,
            :meth:`match_digit`.

        parse\_*
            Attempts to parse a syntax element returning an appropriate
            object as the result or None if the production is not
            present. The position of the parser is only changed if the
            element was parsed successfully.  This type of method is
            intended for fairly simple productions, e.g.,
            :meth:`parse_integer`. More complex productions are
            implemented using require\_* methods but the general
            :meth:`parse_production` can be used to enable more complex
            look-ahead scenarios.

        require\_*
            Parses a syntax production, returning an appropriate object
            as the result.  If the production is not matched a
            :class:`ParserError` is raised.

            On success, the position of the parser points to the first
            character after the parsed production ready to continue
            parsing.  On failure, the parser is positioned at the
            point at which the exception was raised.

            When deriving your own sub-classes you will normally use the
            require\_* pattern to extend the parser.

    Compatibility note: if you are attempting to use the same source for
    both Python 2 and 3 then you may not be able to rely on the parser
    mode::

        >>> from pyslet.unicode5 import BasicParser
        >>> p = BasicParser("hello")
        >>> p.raw

    The above interpreter session will print True in Python 2 and False
    in Python 3.  This is just another manifestation of the changes to
    string handling between the two releases.  If you are dealing with
    ASCII data you can ignore the issue, otherwise you should consider
    using one of the various techniques for forcing strings to be
    interpreted as unicode when running in Python 2.  The most important
    thing is consistency between the type of object you pass to the
    constructor and those that you pass to the various parsing
    methods.  You may find the :func:`pyslet.py2.ul` and/or
    :func:`pyslet.py2.u8` functions useful for forcing text mode."""

    def __init__(self, source):
        PEP8Compatibility.__init__(self)
        self.raw = not is_unicode(source)
        """True if parser is working in binary mode."""
        self.src = source       #: the string being parsed
        self.pos = -1           #: the position of the current character
        self.the_char = None
        """The current character or None if the parser is positioned
        outside the src string.

        In binary mode this will be a byte, which is an integer in
        Python 3 but a character in Python 2.  In text mode it is
        a (unicode) character."""
        self.last_error = None
        self.next_char()

    def setpos(self, new_pos):
        """Sets the position of the parser to *new_pos*

        Useful for saving the parser state and returning later::

            save_pos = parser.pos
            #
            # do some look-ahead parsing
            #
            parser.setpos(save_pos)
        """
        self.pos = new_pos - 1
        self.next_char()

    def next_char(self):
        """Points the parser at the next character.

        Updates *pos* and *the_char*."""
        self.pos += 1
        if self.pos >= 0 and self.pos < len(self.src):
            self.the_char = self.src[self.pos]
        else:
            self.the_char = None

    def parser_error(self, production=None):
        """Raises an error encountered by the parser

        See :class:`ParserError` for details.

        If production is None then the previous error is re-raised. If
        multiple errors have been raised previously the one with the
        most advanced parser position is used.  This is useful in
        situations where there are multiple alternative productions,
        none of which can be successfully parsed.  It allows parser
        methods to catch the exception from the last possible choice and
        raise an error relating to the closest previous match.  For
        example::

            def require_abc(self):
                result = p.parse_production(p.require_a)
                if result is None:
                    result = p.parse_production(p.require_b)
                if result is None:
                    result = p.parse_production(p.require_c)
                if result is None:
                    # will raise the most advanced error raised during
                    # the three previous methods
                    p.parser_error()
                else:
                    return result

        See :meth:`parse_production` for more details on this pattern.

        The position of the parser is always set to the position of the
        error raised."""
        if production:
            e = ParserError(production, self)
        elif self.last_error is not None and self.pos <= self.last_error.pos:
            e = self.last_error
        else:
            e = ParserError('', self)
        if self.last_error is None or e.pos > self.last_error.pos:
            self.last_error = e
        if e.pos != self.pos:
            self.setpos(e.pos)
        raise e

    def peek(self, nchars):
        """Returns the next *nchars* characters or bytes.

        If there are less than nchars remaining then a shorter string is
        returned."""
        return self.src[self.pos:self.pos + nchars]

    def match_end(self):
        """True if all of :attr:`src` has been parsed"""
        return self.the_char is None

    def match(self, match_string):
        """Returns true if *match_string* is at the current position"""
        if self.the_char is None:
            return False
        else:
            return self.src[self.pos:self.pos +
                            len(match_string)] == match_string

    def parse(self, match_string):
        """Parses *match_string*

        Returns *match_string* or None if it cannot be parsed."""
        if self.match(match_string):
            self.setpos(self.pos + len(match_string))
            return match_string
        else:
            return None

    def require(self, match_string, production=None):
        """Parses and requires *match_string*

        match_string
            The string to be parsed

        production
            Optional name of production, defaults to match_string itself.

        For consistency, returns match_string on success."""
        if not self.parse(match_string):
            if production is None:
                if self.raw:
                    production = repr(match_string)
                    if py2 and production and production[0] in "\"'":
                        production = "b" + production
                else:
                    production = match_string

            self.parser_error(production)
        else:
            return match_string

    def match_insensitive(self, lower_string):
        """Returns true if *lower_string* is matched (ignoring case).

        *lower_string* must already be a lower-cased string."""
        if self.the_char is None:
            return False
        else:
            return self.src[self.pos:self.pos +
                            len(lower_string)].lower() == lower_string

    def parse_insensitive(self, lower_string):
        """Parses *lower_string* ignoring case in the source.

        lower_string
            Must be a lower-cased string

        Advances the parser to the first character after lower_string.
        Returns the matched string which may differ in case from
        lower_string."""
        if self.match_insensitive(lower_string):
            return_string = self.src[self.pos:self.pos + len(lower_string)]
            self.setpos(self.pos + len(lower_string))
            return return_string
        else:
            return None

    def parse_until(self, match_string):
        """Parses up to but not including *match_string*.

        Advances the parser to the first character *of* match_string.
        If match_string is not found (or is None) then all the remaining
        characters in the source are parsed.

        Returns the parsed text, even if empty.  Never returns None."""
        if match_string is None:
            match_pos = -1
        else:
            match_pos = self.src.find(match_string, self.pos)
        if match_pos == -1:
            result = self.src[self.pos:]
            self.setpos(len(self.src))
        else:
            result = self.src[self.pos:match_pos]
            self.setpos(match_pos)
        return result

    def match_one(self, match_chars):
        """Returns true if one of *match_chars* is at the current position.

        The 'in' operator is used to test match_chars so this can be a
        list or tuple of characters (or bytes), it does not have to be
        string."""
        if self.the_char is None:
            return False
        else:
            return self.the_char in match_chars

    def parse_one(self, match_chars):
        """Parses one of *match_chars*.

        match_chars
            A *string* (list or tuple) of characters or bytes

        Returns the character (or byte) or None if no match is found.

        Warning: in binary mode, this method will return a single byte
        value, the type of which will differ in Python 2.  In Python 3,
        bytes are integers, in Python 2 they are binary strings of
        length 1.  You can use the function :func:`py2.byte` to help
        ensure your source works on both platforms, for example::

            from .py2 import byte
            c = parser.parse_one(b"+-")
            if c == byte(b"+"):
                # do plus thing...
            elif c is not None:
                # must be minus...
            else:
                # do something else...
        """
        if self.match_one(match_chars):
            result = self.the_char
            self.next_char()
            return result
        else:
            return None

    u_digits = ul("0123456789")
    b_digits = b"0123456789"

    def match_digit(self):
        """Returns true if the current character is a digit

        Only ASCII digits are considered, in binary mode byte values
        0x30 to 0x39 are matched."""
        if self.raw:
            return self.match_one(self.b_digits)
        else:
            return self.match_one(self.u_digits)

    def parse_digit(self):
        """Parses a digit character.

        Returns the digit character/byte, or None if no digit is found.
        Like :meth:`match_digit` only ASCII digits are parsed."""
        if self.raw:
            return self.parse_one(self.b_digits)
        else:
            return self.parse_one(self.u_digits)

    def parse_digit_value(self):
        """Parses a single digit value.

        Returns the digit value, or None if no digit is found.
        Like :meth:`match_digit` only ASCII digits are parsed."""
        if self.raw:
            result = self.parse_one(self.b_digits)
            if result is not None:
                result = byte_value(result) - 0x30
        else:
            result = self.parse_one(self.u_digits)
            if result is not None:
                result = ord(result) - 0x30
        return result

    def parse_digits(self, min, max=None):
        """Parses a string of digits

        min
            The minimum number of digits to parse.  There is a special
            cases where min=0, in this case an empty string may be
            returned.

        max (default None)
            The maximum number of digits to parse, or None there is no
            maximum.

        Returns the string of digits or None if no digits can be parsed.
        Like :meth:`parse_digit`, only ASCII digits are considered."""
        if min < 0 or (max is not None and min > max):
            raise ValueError("min must be > 0")
        savepos = self.pos
        result = []
        while max is None or len(result) < max:
            d = self.parse_digit()
            if d is None:
                break
            else:
                result.append(d)
        if len(result) < min:
            self.setpos(savepos)
            return None
        if self.raw:
            return join_bytes(result)
        else:
            return ul('').join(result)

    def parse_integer(self, min=None, max=None, max_digits=None):
        """Parses an integer (or long).

        min (optional, defaults to None)
            A lower bound on the acceptable integer value, the
            result will always be >= min on success

        max (optional, defaults to None)
            An upper bound on the acceptable integer value, the
            result will always be <= max on success

        max_digits (optional, defaults to None)
            The limit on the number of digits, i.e., the field width.

        If a suitable integer can't be parsed then None is returned.
        This method only processes ASCII digits.

        Warning: in Python 2 the result may be of type long."""
        if min is None:
            min = 0
        if min < 0 or (max is not None and max < min):
            raise ValueError("0 <= min <= max required")
        savepos = self.pos
        d = self.parse_digits(1, max_digits)
        if d is None:
            return None
        else:
            d = int(d)
            if d < min or (max is not None and d > max):
                self.setpos(savepos)
                return None
            return d

    u_hex_digits = ul("0123456789abcdefABCDEF")
    b_hex_digits = b"0123456789abcdefABCDEF"

    def match_hex_digit(self):
        """Returns true if the current character is a hex-digit

        Only ASCII digits are considered, letters can be either upper or
        lower case.  In binary mode byte values 0x30 to 0x39, 0x41-0x46
        and 0x61-0x66 are matched."""
        if self.raw:
            return self.match_one(self.b_hex_digits)
        else:
            return self.match_one(self.u_hex_digits)

    def parse_hex_digit(self):
        """Parses a hex-digit.

        Returns the digit, or None if no digit is found.  See
        :meth:`match_hex_digit` for which characters/bytes are
        considered hex-digits."""
        if self.raw:
            return self.parse_one(self.b_hex_digits)
        else:
            return self.parse_one(self.u_hex_digits)

    def parse_hex_digits(self, min, max=None):
        """Parses a string of hex-digits

        min
            The minimum number of hex-digits to parse.  There is a
            special cases where min=0, in this case an empty string may
            be returned.

        max (default None)
            The maximum number of hex-digits to parse, or None there is
            no maximum.

        Returns the string of hex-digits or None if no digits can be
        parsed. See :meth:`match_hex_digit` for which characters/bytes
        are considered hex-digits."""
        if min < 0 or (max is not None and min > max):
            raise ValueError("min must be > 0")
        savepos = self.pos
        rlen = 0
        while max is None or rlen < max:
            d = self.parse_hex_digit()
            if d is None:
                break
            else:
                rlen += 1
        if rlen < min:
            self.setpos(savepos)
            return None
        return self.src[savepos:savepos + rlen]
