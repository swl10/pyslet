#! /usr/bin/env python

import unittest
import logging

import pyslet.rfc2396 as uri
import pyslet.urn as urn

from pyslet.py2 import ul, u8, character, is_unicode, range3, dict_items


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(URNTests, 'test'),
    ))


class URNTests(unittest.TestCase):

    def test_constructor(self):
        try:
            u = urn.URN()
            self.fail("empty constructor")
        except ValueError:
            pass
        try:
            u = urn.URN(nid="foo")
            self.fail("namespace-specific string missing")
        except ValueError:
            pass
        u = urn.URN(nid="foo", nss="a123,456")
        self.assertTrue(isinstance(u, urn.URN))
        self.assertTrue(str(u) == "urn:foo:a123,456")
        self.assertTrue(is_unicode(u.nid))
        self.assertTrue(is_unicode(u.nss))
        u = uri.URI.from_octets('urn:foo:a123,456')
        self.assertTrue(isinstance(u, urn.URN))
        self.assertTrue(str(u) == 'urn:foo:a123,456')

    def test_scheme_case(self):
        """The leading "urn:" sequence is case-insensitive."""
        u0 = urn.URN(nid="foo", nss="bar")
        u1 = uri.URI.from_octets('URN:foo:bar')
        u2 = uri.URI.from_octets('urn:foo:bar')
        self.assertTrue(u0 == u1)
        self.assertTrue(u0 == u2)
        self.assertTrue(u1 == u2)
        self.assertFalse(str(u0) == str(u1))
        self.assertTrue(str(u0) == str(u2))
        self.assertFalse(str(u1) == str(u2))
        # canonical form is lower case scheme
        self.assertFalse(str(u0.canonicalize()) == str(u1))
        self.assertTrue(str(u0.canonicalize()) == str(u2))
        self.assertTrue(str(u1.canonicalize()) == str(u2))
        self.assertTrue(str(u1.canonicalize()) == str(u0))
        self.assertTrue(str(u2.canonicalize()) == str(u0))
        self.assertFalse(str(u2.canonicalize()) == str(u1))

    def test_letnum(self):
        """Basic syntax definitions::
            <let-num> ::= <upper> | <lower> | <number>
            <let-num-hyp> ::= <upper> | <lower> | <number> | "-"
        """
        for i in range3(0x00, 0x2D):
            self.assertFalse(urn.is_upper(character(i)))
            self.assertFalse(urn.is_lower(character(i)))
            self.assertFalse(urn.is_number(character(i)))
            self.assertFalse(urn.is_letnum(character(i)))
            self.assertFalse(urn.is_letnumhyp(character(i)))
        self.assertFalse(urn.is_upper(character(0x2D)))
        self.assertFalse(urn.is_lower(character(0x2D)))
        self.assertFalse(urn.is_number(character(0x2D)))
        self.assertFalse(urn.is_letnum(character(0x2D)))
        self.assertTrue(urn.is_letnumhyp(character(0x2D)))
        for i in range3(0x2E, 0x30):
            self.assertFalse(urn.is_upper(character(i)))
            self.assertFalse(urn.is_lower(character(i)))
            self.assertFalse(urn.is_number(character(i)))
            self.assertFalse(urn.is_letnum(character(i)))
            self.assertFalse(urn.is_letnumhyp(character(i)))
        for i in range3(0x30, 0x3A):
            self.assertFalse(urn.is_upper(character(i)))
            self.assertFalse(urn.is_lower(character(i)))
            self.assertTrue(urn.is_number(character(i)))
            self.assertTrue(urn.is_letnum(character(i)))
            self.assertTrue(urn.is_letnumhyp(character(i)))
        for i in range3(0x3A, 0x41):
            self.assertFalse(urn.is_upper(character(i)))
            self.assertFalse(urn.is_lower(character(i)))
            self.assertFalse(urn.is_number(character(i)))
            self.assertFalse(urn.is_letnum(character(i)))
            self.assertFalse(urn.is_letnumhyp(character(i)))
        for i in range3(0x41, 0x5B):
            self.assertTrue(urn.is_upper(character(i)))
            self.assertFalse(urn.is_lower(character(i)))
            self.assertFalse(urn.is_number(character(i)))
            self.assertTrue(urn.is_letnum(character(i)))
            self.assertTrue(urn.is_letnumhyp(character(i)))
        for i in range3(0x5B, 0x61):
            self.assertFalse(urn.is_upper(character(i)))
            self.assertFalse(urn.is_lower(character(i)))
            self.assertFalse(urn.is_number(character(i)))
            self.assertFalse(urn.is_letnum(character(i)))
            self.assertFalse(urn.is_letnumhyp(character(i)))
        for i in range3(0x61, 0x7B):
            self.assertFalse(urn.is_upper(character(i)))
            self.assertTrue(urn.is_lower(character(i)))
            self.assertFalse(urn.is_number(character(i)))
            self.assertTrue(urn.is_letnum(character(i)))
            self.assertTrue(urn.is_letnumhyp(character(i)))
        for i in range3(0x7B, 0xFF):
            self.assertFalse(urn.is_upper(character(i)))
            self.assertFalse(urn.is_lower(character(i)))
            self.assertFalse(urn.is_number(character(i)))
            self.assertFalse(urn.is_letnum(character(i)))
            self.assertFalse(urn.is_letnumhyp(character(i)))

    def test_nid(self):
        """Syntax for nid::

            <NID> ::= <let-num> [ 1,31<let-num-hyp> ]

        The Namespace Identifier is case insensitive

        To avoid confusion with the "urn:" identifier, the NID "urn" is
        reserved and MUST NOT be used."""
        positive = [
            "a", "A", "0", "z", "Z", "9",
            "abB2-", "aB2-b", "a2-bB", "a-bB2",
            "abcdef1234567890ABCDEF1234567890",
            "0-------------------------------",
            "12345678901234567890123456789012",
            "isbn", "ISBN"]
        for nid in positive:
            try:
                u = urn.URN(nid=nid, nss="bar")
            except uri.URIException:
                self.fail("POSTIVE nid test: %s" % nid)
            self.assertTrue(u.nid == nid, "case preserved")
            uparsed = uri.URI.from_octets('urn:%s:bar' % nid)
            self.assertTrue(uparsed.nid == nid, "parsed case preserved")
            self.assertTrue(uparsed == u)
            self.assertTrue(str(uparsed) == str(u))
            # The Namespace Identifier is case insensitive
            uupper = urn.URN(nid=nid.upper(), nss="bar")
            ulower = urn.URN(nid=nid.lower(), nss="bar")
            self.assertTrue(ulower == uupper)
            self.assertTrue(ulower == u)
            self.assertTrue(uupper == u)
            self.assertTrue(u.nid == nid, "case preserved")
            # canonical form is lower case
            ucanonical = u.canonicalize()
            self.assertTrue(str(ucanonical) == str(ulower))
            if nid != nid.lower():
                self.assertFalse(str(ucanonical) == str(u))
                self.assertFalse(str(ucanonical) == str(uupper))
        negative = [
            "", "-", "-a", "-A", "-0",
            # check '.' and '+' specifically
            ".", "+", "a.", "a+", "a+b", "a.b",
            "abcdef1234567890ABCDEF1234567890a",
            # check urn specifically
            "urn", "URN", "Urn"]
        for nid in negative:
            try:
                u = urn.URN(nid=nid, nss="bar")
                self.fail("NEGATIVE nid test: %s" % nid)
            except uri.URIException:
                pass
            try:
                u = uri.URI.from_octets('urn:%s:bar' % nid)
                self.fail("NEGATIVE nid parse test: %s" % nid)
            except uri.URIException:
                pass

    def test_trans(self):
        # controls
        for i in range3(0x00, 0x21):
            self.assertFalse(urn.is_reserved(character(i)))
            self.assertFalse(urn.is_other(character(i)))
            self.assertFalse(urn.is_hex(character(i)))
            self.assertFalse(urn.is_trans(character(i)))
        # !
        self.assertFalse(urn.is_reserved(character(0x21)))
        self.assertTrue(urn.is_other(character(0x21)))
        self.assertFalse(urn.is_hex(character(0x21)))
        self.assertTrue(urn.is_trans(character(0x21)))
        # "
        self.assertFalse(urn.is_reserved(character(0x22)))
        self.assertFalse(urn.is_other(character(0x22)))
        self.assertFalse(urn.is_hex(character(0x22)))
        self.assertFalse(urn.is_trans(character(0x22)))
        # #
        self.assertTrue(urn.is_reserved(character(0x23)))
        self.assertFalse(urn.is_other(character(0x23)))
        self.assertFalse(urn.is_hex(character(0x23)))
        self.assertTrue(urn.is_trans(character(0x23)))
        # $
        self.assertFalse(urn.is_reserved(character(0x24)))
        self.assertTrue(urn.is_other(character(0x24)))
        self.assertFalse(urn.is_hex(character(0x24)))
        self.assertTrue(urn.is_trans(character(0x24)))
        # %
        self.assertTrue(urn.is_reserved(character(0x25)))
        self.assertFalse(urn.is_other(character(0x25)))
        self.assertFalse(urn.is_hex(character(0x25)))
        self.assertTrue(urn.is_trans(character(0x25)))
        # &
        self.assertFalse(urn.is_reserved(character(0x26)))
        self.assertFalse(urn.is_other(character(0x26)))
        self.assertFalse(urn.is_hex(character(0x26)))
        self.assertFalse(urn.is_trans(character(0x26)))
        # ' ( ) * + , - .
        for i in range3(0x27, 0x2F):
            self.assertFalse(urn.is_reserved(character(i)))
            self.assertTrue(urn.is_other(character(i)))
            self.assertFalse(urn.is_hex(character(i)))
            self.assertTrue(urn.is_trans(character(i)))
        # /
        self.assertTrue(urn.is_reserved(character(0x2F)))
        self.assertFalse(urn.is_other(character(0x2F)))
        self.assertFalse(urn.is_hex(character(0x2F)))
        self.assertTrue(urn.is_trans(character(0x2F)))
        # digits
        for i in range3(0x30, 0x3A):
            self.assertFalse(urn.is_reserved(character(i)))
            self.assertFalse(urn.is_other(character(i)))
            self.assertTrue(urn.is_hex(character(i)))
            self.assertTrue(urn.is_trans(character(i)))
        # : ;
        for i in range3(0x3A, 0x3C):
            self.assertFalse(urn.is_reserved(character(i)))
            self.assertTrue(urn.is_other(character(i)))
            self.assertFalse(urn.is_hex(character(i)))
            self.assertTrue(urn.is_trans(character(i)))
        # <
        self.assertFalse(urn.is_reserved(character(0x3C)))
        self.assertFalse(urn.is_other(character(0x3C)))
        self.assertFalse(urn.is_hex(character(0x3C)))
        self.assertFalse(urn.is_trans(character(0x3C)))
        # =
        self.assertFalse(urn.is_reserved(character(0x3D)))
        self.assertTrue(urn.is_other(character(0x3D)))
        self.assertFalse(urn.is_hex(character(0x3D)))
        self.assertTrue(urn.is_trans(character(0x3D)))
        # >
        self.assertFalse(urn.is_reserved(character(0x3E)))
        self.assertFalse(urn.is_other(character(0x3E)))
        self.assertFalse(urn.is_hex(character(0x3E)))
        self.assertFalse(urn.is_trans(character(0x3E)))
        # ?
        self.assertTrue(urn.is_reserved(character(0x3F)))
        self.assertFalse(urn.is_other(character(0x3F)))
        self.assertFalse(urn.is_hex(character(0x3F)))
        self.assertTrue(urn.is_trans(character(0x3F)))
        # @
        self.assertFalse(urn.is_reserved(character(0x40)))
        self.assertTrue(urn.is_other(character(0x40)))
        self.assertFalse(urn.is_hex(character(0x40)))
        self.assertTrue(urn.is_trans(character(0x40)))
        # A-F
        for i in range3(0x41, 0x47):
            self.assertFalse(urn.is_reserved(character(i)))
            self.assertFalse(urn.is_other(character(i)))
            self.assertTrue(urn.is_hex(character(i)))
            self.assertTrue(urn.is_trans(character(i)))
        # G-Z
        for i in range3(0x47, 0x5B):
            self.assertFalse(urn.is_reserved(character(i)))
            self.assertFalse(urn.is_other(character(i)))
            self.assertFalse(urn.is_hex(character(i)))
            self.assertTrue(urn.is_trans(character(i)))
        # [ \ ] ^
        for i in range3(0x5B, 0x5F):
            self.assertFalse(urn.is_reserved(character(i)))
            self.assertFalse(urn.is_other(character(i)))
            self.assertFalse(urn.is_hex(character(i)))
            self.assertFalse(urn.is_trans(character(i)))
        # _
        self.assertFalse(urn.is_reserved(character(0x5F)))
        self.assertTrue(urn.is_other(character(0x5F)))
        self.assertFalse(urn.is_hex(character(0x5F)))
        self.assertTrue(urn.is_trans(character(0x5F)))
        # `
        self.assertFalse(urn.is_reserved(character(0x60)))
        self.assertFalse(urn.is_other(character(0x60)))
        self.assertFalse(urn.is_hex(character(0x60)))
        self.assertFalse(urn.is_trans(character(0x60)))
        # a-f
        for i in range3(0x61, 0x67):
            self.assertFalse(urn.is_reserved(character(i)))
            self.assertFalse(urn.is_other(character(i)))
            self.assertTrue(urn.is_hex(character(i)))
            self.assertTrue(urn.is_trans(character(i)))
        # g-z
        for i in range3(0x67, 0x7B):
            self.assertFalse(urn.is_reserved(character(i)))
            self.assertFalse(urn.is_other(character(i)))
            self.assertFalse(urn.is_hex(character(i)))
            self.assertTrue(urn.is_trans(character(i)))
        # { | } ~ control and 8-bit characters
        for i in range3(0x7B, 0xFF):
            self.assertFalse(urn.is_reserved(character(i)))
            self.assertFalse(urn.is_other(character(i)))
            self.assertFalse(urn.is_hex(character(i)))
            self.assertFalse(urn.is_trans(character(i)))

    def test_nss(self):
        """Syntax for URN char::

            <trans> | "%" <hex> <hex>

        Translation is done by encoding each character outside the URN
        character set as a sequence of one to six octets using UTF-8
        encoding [5], and the encoding of each of those octets as "%"
        followed by two characters from the <hex> character set above.

        the character [%] used in a literal sense MUST be encoded

        a character MUST NOT be "%"-encoded if the character is not a
        reserved character

        SHOULD NOT use [other reserved characters] characters in
        unencoded form

        each character outside the URN character set [is encoded] as a
        sequence of one to six octets using UTF-8 encoding

        The presence of an "%" character in an URN MUST be followed by
        two characters from the <hex> character set

        In addition, octet 0 (0 hex) should NEVER be used, in either
        unencoded or %-encoded form."""
        trans_tests = {
            ul('\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10'
               '\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f '
               '!"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\'
               ']^_`abcdefghijklmnopqrstuvwxyz{|}~\x7f'):
            '%01%02%03%04%05%06%07%08%09%0A%0B%0C%0D%0E%0F%10'
            '%11%12%13%14%15%16%17%18%19%1A%1B%1C%1D%1E%1F%20'
            '!%22%23$%25%26\'()*+,-.%2F0123456789:;%3C=%3E%3F@ABCDEFGHIJKLMN'
            'OPQRSTUVWXYZ%5B%5C%5D%5E_%60abcdefghijklmnopqrstuvwxyz%7B%7C%7D'
            '%7E%7F',
            u8(b'\xe8\x8b\xb1\xe5\x9b\xbd'): '%E8%8B%B1%E5%9B%BD',
            ul('Caf\xe9'): 'Caf%C3%A9'
            }
        for src, dst in dict_items(trans_tests):
            self.assertTrue(
                urn.translate_to_urnchar(src) == dst,
                "%s -> \n%s, expected \n%s" %
                (repr(src),
                 repr(urn.translate_to_urnchar(src)),
                 repr(dst)))
            self.assertTrue(
                urn.translate_from_urnchar(dst) == src,
                "%s -> \n%s, expected \n%s" %
                (repr(dst),
                 repr(urn.translate_from_urnchar(dst)), repr(src)))
            u = urn.URN(nid='foo', nss=dst)
            self.assertTrue(u.nss == dst)
            u = uri.URI.from_octets('urn:foo:%s' % dst)
            self.assertTrue(u.nss == dst)
        for wrong in ("100% wrong", "Zero%00"):
            try:
                urn.translate_from_urnchar(wrong)
                self.fail("%s test in URN" % repr(wrong))
            except ValueError:
                pass
        try:
            urn.translate_to_urnchar("Zero\x00Byte")
            self.fail("Zero byte test in URN")
        except ValueError:
            pass
        # let's invent a scheme whereby the reserved characters
        # include . which is reserved for special meaning and
        # / is used unencoded as a path separator (even though
        # it is reserved and *SHOULD* be encoded

        def dot(c):
            return c == "."

        src = "urn:path:.steve/file%2Ename/easy_come%2Feasy_go"
        u = uri.URI.from_octets(src)
        path = u.nss.replace('.', 'users/')
        path = [urn.translate_from_urnchar(s) for s in path.split('/')]
        self.assertTrue(path == [
            'users', 'steve', 'file.name', 'easy_come/easy_go'],
            "Parsed: %s" % repr(path))
        path = path[1:]
        # / is always reserved so we don't need to call this out
        path = [urn.translate_to_urnchar(x, dot) for x in path]
        # add the newly reserved characters after translation...
        path = '.' + '/'.join(path)
        u2 = urn.URN(nid='path', nss=path)
        self.assertTrue(u == u2)
        self.assertTrue(str(u) == str(u2))

    def test_parseurn(self):
        """An URN ends when an octet/character from the excluded
        character set (<excluded>) is encountered."""
        tests = [
            'urn:foo:bar\x00wrong',
            'urn:foo:bar wrong',
            'urn:foo:bar\\wrong',
            'urn:foo:bar"wrong',
            'urn:foo:bar&wrong',
            'urn:foo:bar<wrong',
            'urn:foo:bar>wrong',
            'urn:foo:bar[wrong',
            'urn:foo:bar]wrong',
            'urn:foo:bar^wrong',
            'urn:foo:bar`wrong',
            'urn:foo:bar{wrong',
            'urn:foo:bar|wrong',
            'urn:foo:bar}wrong',
            'urn:foo:bar~wrong',
            ul('urn:foo:bar\x7fwrong'),
            ul(b'urn:foo:bar\x9fwrong'),
            ul(b'urn:foo:bar\xff')]
        for src in tests:
            dst = urn.parse_urn(src)
            self.assertTrue(dst == 'urn:foo:bar', "parse_urn(%s) == %s" %
                            (repr(src), repr(dst)))

    def test_lexical_equality(self):
        u1 = uri.URI.from_octets('URN:foo:a123,456')
        u2 = uri.URI.from_octets('urn:foo:a123,456')
        u3 = uri.URI.from_octets('urn:FOO:a123,456')
        u4 = uri.URI.from_octets('urn:foo:A123,456')
        u5 = uri.URI.from_octets('urn:foo:a123%2C456')
        u6 = uri.URI.from_octets('URN:FOO:a123%2c456')
        self.assertTrue(u1 == u2)
        self.assertTrue(u1 == u3)
        self.assertTrue(u2 == u3)
        self.assertFalse(u4 == u1)
        self.assertFalse(u4 == u2)
        self.assertFalse(u4 == u3)
        self.assertFalse(u4 == u5)
        self.assertFalse(u4 == u6)
        self.assertFalse(u5 == u1)
        self.assertFalse(u5 == u2)
        self.assertFalse(u5 == u3)
        self.assertFalse(u5 == u4)
        self.assertTrue(u5 == u6)
        self.assertFalse(u6 == u1)
        self.assertFalse(u6 == u2)
        self.assertFalse(u6 == u3)
        self.assertFalse(u6 == u4)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
