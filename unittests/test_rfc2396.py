#! /usr/bin/env python

import unittest
import logging
import os
import os.path
import string
import sys
from types import UnicodeType, StringType

import pyslet.vfs as vfs
import pyslet.rfc2396 as uri


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(RFC2396Tests, 'test'),
        unittest.makeSuite(URITests, 'test'),
        unittest.makeSuite(FileURLTests, 'test'),
        unittest.makeSuite(VirtualFileURLTests, 'test')
    ))


SERVER_EXAMPLES = {
    # if there is no authority then it is safe to parse
    None:
    (None, None, None),
    # empty string is a speical case and is treated as empty host
        '':
    (None, '', None),
    '@host.com':
    ('', 'host.com', None),
    'host.com':
    (None, 'host.com', None),
    'foo:@host.com':
    ('foo:', 'host.com', None),
    'myname@host.dom':
    ('myname', 'host.dom', None),
    'user:pass@host.com:443':
    ('user:pass', 'host.com', '443')
    }


class RFC2396Tests(unittest.TestCase):

    def test_basics(self):
        """Tests for basic character classes.

        alpha = lowalpha | upalpha
        lowalpha = "a" | ... | "z"
        upalpha  = "A" | ... | "Z"
        digit = "0" | ... | "9"
        alphanum = alpha | digit
        reserved = ";" | "/" | "?" | ":" | "@" | "&" | "=" | "+" | "$" | ","
        unreserved  = alphanum | mark
        mark = "-" | "_" | "." | "!" | "~" | "*" | "'" | "(" | ")"
        """
        # UPALPHA = <any US-ASCII uppercase letter "A".."Z">
        upalpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(
                uri.is_up_alpha(c) == (c in upalpha),
                "is_up_alpha(chr(%i))" % i)
        lowalpha = "abcdefghijklmnopqrstuvwxyz"
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(uri.is_low_alpha(c) == (c in lowalpha),
                            "is_low_alpha(chr(%i))" % i)
        alpha = upalpha + lowalpha
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(uri.is_alpha(c) == (c in alpha),
                            "is_alpha(chr(%i))" % i)
        digit = "0123456789"
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(uri.is_digit(c) == (c in digit),
                            "is_digit(chr(%i))" % i)
        alphanum = alpha + digit
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(uri.is_alpha_num(c) == (c in alphanum),
                            "is_alpha_num(chr(%i))" % i)
        reserved = ";/?:@&=+$,"
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(uri.is_reserved(c) == (c in reserved),
                            "is_reserved(chr(%i))" % i)
        mark = "-_.!~*'()"
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(uri.is_mark(c) == (c in mark),
                            "is_mark(chr(%i))" % i)
        unreserved = alphanum + mark
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(uri.is_unreserved(c) == (c in unreserved),
                            "is_unreserved(chr(%i))" % i)
        control = "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C\x0D"\
            "\x0E\x0F\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1A\x1B\x1C"\
            "\x1D\x1E\x1F\x7F"
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(
                uri.is_control(c) == (c in control), "is_control(chr(%i))" % i)
        space = " "
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(uri.is_space(c) == (c in space),
                            "is_space(chr(%i))" % i)
        delims = "<>#%\""
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(
                uri.is_delims(c) == (c in delims), "is_delims(chr(%i))" % i)
        unwise = "{}|\\^[]`"
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(
                uri.is_unwise(c) == (c in unwise), "is_unwise(chr(%i))" % i)
        authority_reserved = ";:@?/"
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(uri.is_authority_reserved(c) == (
                c in authority_reserved), "is_authority_reserved(chr(%i))" % i)
        path_segment_reserved = "/;=?"
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(uri.is_path_segment_reserved(c) ==
                            (c in path_segment_reserved),
                            "is_path_segment_reserved(chr(%i))" % i)
        query_reserved = ";/?:@&=+,$"
        for i in xrange(0, 256):
            c = chr(i)
            self.assertTrue(uri.is_query_reserved(c) == (c in query_reserved),
                            "is_query_reserved(chr(%i))" % i)

    def test_uric(self):
        """uric = reserved | unreserved | escaped"""
        self.assertTrue(uri.parse_uric("w ") == 1, "space in URI")
        self.assertTrue(uri.parse_uric("'w'>") == 3, "single-quote in URI")
        self.assertTrue(uri.parse_uric('"w">') == 0, "double-quote in URI")
        self.assertTrue(uri.parse_uric('Caf%E9 ') == 6, "uc hex")
        self.assertTrue(uri.parse_uric('Caf%e9 ') == 6, "lc hex")
        self.assertTrue(uri.parse_uric('index#frag') == 5, "fragment in URI")

    def test_escape(self):
        data = "\t\n\r !\"#$%&'()*+,-./0123456789:;<=>?@"\
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
        escaped_normal = "%09%0A%0D%20!%22%23%24%25%26'()*%2B%2C-.%2F"\
            "0123456789%3A%3B%3C%3D%3E%3F%40"\
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ%5B%5C%5D%5E_%60"\
            "abcdefghijklmnopqrstuvwxyz%7B%7C%7D~"
        escaped_max = "%09%0A%0D%20%21%22%23%24%25%26%27%28%29%2A%2B%2C%2D"\
            "%2E%2F0123456789%3A%3B%3C%3D%3E%3F%40"\
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ%5B%5C%5D%5E%5F%60"\
            "abcdefghijklmnopqrstuvwxyz%7B%7C%7D%7E"
        escaped_min = "%09%0A%0D%20!%22%23$%25&'()*+,-./0123456789:;%3C=%3E?@"\
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ%5B%5C%5D%5E_%60"\
            "abcdefghijklmnopqrstuvwxyz%7B%7C%7D~"
        self.compare_strings(
            escaped_normal, uri.escape_data(data), "Normal escaping")
        self.compare_strings(escaped_max, uri.escape_data(data,
                             lambda x: not uri.is_alpha_num(x)),
                             "Max escaping")
        self.compare_strings(
            escaped_min, uri.escape_data(data, lambda x: False),
            "Min escaping")
        self.compare_strings(data,
                             uri.unescape_data(uri.escape_data(data)),
                             "Round-trip escaping")

    def compare_strings(self, expected, found, label="Test"):
        for i in xrange(len(expected)):
            if i >= len(found):
                self.fail("%s truncation failure:\n%s... expected %s" %
                          (label, found[0:i], expected[i]))
            if expected[i] == found[i]:
                continue
            self.fail("%s mismatch:\n%s... expected %s ; found %s" %
                      (label, repr(found[0:i + 1]),
                       repr(expected[i]), repr(found[i])))

    def test_path_segments(self):
        # if there is no abs_path in a URI then abs_path will be None,
        # should be safe to split
        segments = uri.split_abs_path(None)
        self.assertTrue(segments == [])
        # an abs_path cannot be an empty string so treat this the same as None
        segments = uri.split_abs_path('')
        self.assertTrue(segments == [])
        # if there is an abs_path there is always at least one segment, so '/'
        # is a single empty segment
        segments = uri.split_abs_path('/')
        self.assertTrue(segments == [''])
        # we don't decode when splitting, segments can contain params
        segments = uri.split_abs_path('/Caf%e9/Nero;LHR.T2/Table4/')
        self.assertTrue(segments == ['Caf%e9', 'Nero;LHR.T2', 'Table4', ''])
        # A segment may be empty
        pchar, params = uri.split_path_segment('')
        self.assertTrue(pchar == '' and params == [])
        # A segment may have no params (and should not remove escaping)
        pchar, params = uri.split_path_segment('Caf%e9')
        self.assertTrue(pchar == 'Caf%e9' and params == [])
        # A segment param may be empty
        pchar, params = uri.split_path_segment('Nero;')
        self.assertTrue(pchar == 'Nero' and params == [''],
                        "Got: %s %s" % (pchar, str(params)))
        # A segment may consist only of params
        pchar, params = uri.split_path_segment(';Nero')
        self.assertTrue(pchar == '' and params == ['Nero'])
        # Degenerate params
        pchar, params = uri.split_path_segment(';')
        self.assertTrue(pchar == '' and params == [''])
        # A segment param does not remove escaping
        pchar, params = uri.split_path_segment('Nero;LHR.T2;curr=%a3')
        self.assertTrue(pchar == 'Nero' and params == ['LHR.T2', 'curr=%a3'])

    def test_server(self):
        keys = SERVER_EXAMPLES.keys()
        for k in keys:
            userinfo, host, port = uri.split_server(k)
            userinfo2, host2, port2 = SERVER_EXAMPLES[k]
            self.assertTrue(
                userinfo == userinfo2, "%s found userinfo %s" % (k, userinfo2))
            self.assertTrue(host == host2, "%s found host %s" % (k, host2))
            self.assertTrue(port == port2, "%s found port %s" % (k, port2))

SIMPLE_EXAMPLE = 'http://www.example.com/'
RELATIVE_EXAMPLE = "index.html"
LIST_EXAMPLE = 'http://www.example.com/ http://www.example.com/index.htm'

ABS_EXAMPLES = {
    'ftp://ftp.is.co.za/rfc/rfc1808.txt':
    ('ftp', None, 'ftp.is.co.za', '/rfc/rfc1808.txt', None, 'rfc1808.txt'),
        'gopher://spinaltap.micro.umn.edu/00/Weather/California/Los%20Angeles':
    ('gopher', None, 'spinaltap.micro.umn.edu',
     '/00/Weather/California/Los%20Angeles', None, 'Los Angeles'),
        'http://www.math.uio.no/faq/compression-faq/part1.html':
    ('http', None, 'www.math.uio.no',
     '/faq/compression-faq/part1.html', None, 'part1.html'),
        'mailto:mduerst@ifi.unizh.ch':
    ('mailto', 'mduerst@ifi.unizh.ch', None, None, None, None),
        'news:comp.infosystems.www.servers.unix':
    ('news', 'comp.infosystems.www.servers.unix',
     None, None, None, None),
        'telnet://melvyl.ucop.edu/':
    ('telnet', None, 'melvyl.ucop.edu', '/', None, ''),
        'http://www.ics.uci.edu/pub/ietf/uri/#Related':
    ('http', None, 'www.ics.uci.edu', '/pub/ietf/uri/', None, ''),
        'http://a/b/c/g?y':
    ('http', None, 'a', '/b/c/g', 'y', 'g'),
        'http://a/b/c/g?':
    ('http', None, 'a', '/b/c/g', '', 'g'),
        'http://a/?':
    ('http', None, 'a', '/', '', ''),
        'noauth:/':
    ('noauth', None, None, '/', None, ''),
        'noauth:/?':
    ('noauth', None, None, '/', '', ''),
    'http://localhost/reserved/%2F%3Fx%3D1':
        ('http', None, 'localhost', '/reserved/%2F%3Fx%3D1', None,
         '/?x=1')
}

REL_BASE = "http://a/b/c/d;p?q"
REL_BASE1 = "http://a/b/"
REL_BASE2 = "c/d;p?q"

REL_CURRENT = "current.doc"
REL_EXAMPLES = {
    # resolved URI, scheme, authority, abs_path, rel_path, query, fragment
    'g:h': ('g:h', 'g', None, None, None, None, None),
    'g': ('http://a/b/c/g', None, None, None, 'g', None, None),
    './g': ('http://a/b/c/g', None, None, None, './g', None, None),
    'g/': ('http://a/b/c/g/', None, None, None, 'g/', None, None),
    '/g': ('http://a/g', None, None, '/g', None, None, None),
    '/g?': ('http://a/g?', None, None, '/g', None, '', None),
    '/': ('http://a/', None, None, '/', None, None, None),
    '/?': ('http://a/?', None, None, '/', None, '', None),
    '//g': ('http://g', None, 'g', None, None, None, None),
    '?y': ('http://a/b/c/?y', None, None, None, '', 'y', None),
    './?y': ('http://a/b/c/?y', None, None, None, './', 'y', None),
    'g?y': ('http://a/b/c/g?y', None, None, None, 'g', 'y', None),
    'g?': ('http://a/b/c/g?', None, None, None, 'g', '', None),
    '#s': ('current.doc#s', None, None, None, '', None, 's'),
    'g#s': ('http://a/b/c/g#s', None, None, None, 'g', None, 's'),
    'g?y#s': ('http://a/b/c/g?y#s', None, None, None, 'g', 'y', 's'),
    ';x': ('http://a/b/c/;x', None, None, None, ';x', None, None),
    'g;x': ('http://a/b/c/g;x', None, None, None, 'g;x', None, None),
    'g;x?y#s': ('http://a/b/c/g;x?y#s', None, None, None, 'g;x', 'y', 's'),
    '.': ('http://a/b/c/', None, None, None, '.', None, None),
    './': ('http://a/b/c/', None, None, None, './', None, None),
    '..': ('http://a/b/', None, None, None, '..', None, None),
    '../': ('http://a/b/', None, None, None, '../', None, None),
    '../g': ('http://a/b/g', None, None, None, '../g', None, None),
    '../..': ('http://a/', None, None, None, '../..', None, None),
    '../../': ('http://a/', None, None, None, '../../', None, None),
    '../../g': ('http://a/g', None, None, None, '../../g', None, None),
    '../../g?': ('http://a/g?', None, None, None, '../../g', '', None),
    '../../?': ('http://a/?', None, None, None, '../../', '', None),
}


class URITests(unittest.TestCase):

    def test_constructor(self):
        u = uri.URI(SIMPLE_EXAMPLE)
        self.assertTrue(isinstance(u, uri.URI))
        self.assertTrue(str(u) == SIMPLE_EXAMPLE)
        try:
            u = uri.URI(LIST_EXAMPLE)
            # we don't support this type of thing any more
            # self.assertTrue(str(u)==SIMPLE_EXAMPLE,"Simple from list")
        except uri.URIException:
            pass
        u = uri.URI.from_octets(u'\u82f1\u56fd.xml')
        self.assertTrue(
            str(u) == '%E8%8B%B1%E5%9B%BD.xml', "Unicode example: %s" % str(u))
        self.assertTrue(type(u.octets) is StringType, "octest must be string")

    def test_compare(self):
        u1 = uri.URI(SIMPLE_EXAMPLE)
        u2 = uri.URI(SIMPLE_EXAMPLE)
        self.assertTrue(
            u1.match(u2) and u2.match(u1), "Equal URIs fail to match")
        u2 = uri.URI('hello.xml')
        self.assertFalse(
            u1.match(u2) or u2.match(u1), "Mismatched URIs do match")
        u1 = uri.URI("HTTP://www.example.com/")
        u2 = uri.URI("http://www.example.com/")
        self.assertTrue(
            u1.match(u2) and u2.match(u1), "Equal URIs fail to match")

    def test_scheme(self):
        u = uri.URI(SIMPLE_EXAMPLE)
        self.assertTrue(u.is_absolute(), "Absolute test")
        self.assertTrue(u.scheme == 'http', "Scheme")
        self.assertTrue(u.scheme_specific_part == '//www.example.com/')
        u = uri.URI(RELATIVE_EXAMPLE)
        self.assertFalse(u.is_absolute(), "Relative test")
        self.assertTrue(u.scheme is None, "relative scheme")
        self.assertTrue(u.scheme_specific_part is None)

    def test_fragment(self):
        u = uri.URI(SIMPLE_EXAMPLE)
        self.assertTrue(u.fragment is None, "no fragment")
        u = uri.URI('http://www.ics.uci.edu/pub/ietf/uri/#Related')
        self.assertTrue(u.scheme_specific_part ==
                        '//www.ics.uci.edu/pub/ietf/uri/', 'URI with fragment')
        self.assertTrue(u.fragment == 'Related', 'fragment')

    def test_absolute_examples(self):
        keys = ABS_EXAMPLES.keys()
        for k in keys:
            logging.info("Testing absolute: %s", k)
            u = uri.URI(k)
            scheme, opaque_part, authority, abs_path, query, fName = \
                ABS_EXAMPLES[k]
            self.assertTrue(scheme == u.scheme,
                            "%s found scheme %s" % (k, u.scheme))
            self.assertTrue(opaque_part == u.opaque_part,
                            "%s found opaque_part %s" % (k, u.opaque_part))
            self.assertTrue(authority == u.authority,
                            "%s found authority %s" % (k, u.authority))
            self.assertTrue(abs_path == u.abs_path,
                            "%s found abs_path %s" % (k, u.abs_path))
            self.assertTrue(query == u.query,
                            "%s found query %s" % (k, u.query))
            self.assertTrue(fName == u.get_file_name(),
                            "%s found file name %s" % (k, u.get_file_name()))

    def test_relative_examples(self):
        keys = REL_EXAMPLES.keys()
        base = uri.URI(REL_BASE)
        current = uri.URI(REL_CURRENT)
        relatives = {}
        for k in keys:
            logging.info("Testing relative: %s", k)
            u = uri.URI(k)
            resolved, scheme, authority, abs_path, rel_path, query, \
                fragment = REL_EXAMPLES[k]
            relatives[resolved] = relatives.get(resolved, []) + [k]
            resolution = str(u.resolve(base, current))
            self.assertTrue(scheme == u.scheme,
                            "%s found scheme %s" % (k, u.scheme))
            self.assertTrue(authority == u.authority,
                            "%s found authority %s" % (k, u.authority))
            self.assertTrue(abs_path == u.abs_path,
                            "%s found abs_path %s" % (k, u.abs_path))
            self.assertTrue(rel_path == u.rel_path,
                            "%s found rel_path %s" % (k, u.rel_path))
            self.assertTrue(query == u.query,
                            "%s found query %s" % (k, u.query))
            self.assertTrue(fragment == u.fragment,
                            "%s found fragment %s" % (k, u.fragment))
            self.assertTrue(resolved == resolution,
                            "%s [*] %s = %s ; found %s" %
                            (str(base), k, resolved, resolution))
        for r in relatives.keys():
            logging.info("Testing %s [/] %s = ( %s )", r, str(base),
                         string.join(relatives[r], ' | '))
            u = uri.URI(r)
            # this check removes the 'current document' case
            if not u.is_absolute():
                continue
            relative = str(u.relative(base))
            # relative should be one of the relatives!
            no_match = True
            for k in relatives[r]:
                if k == relative:
                    no_match = False
                    break
            self.assertFalse(no_match, "%s [/] %s = ( %s ) ; found %s" %
                             (r, str(base), string.join(relatives[r], ' | '),
                              relative))

    def test_relative_join_examples(self):
        keys = REL_EXAMPLES.keys()
        base1 = uri.URI(REL_BASE1)
        base2 = uri.URI(REL_BASE2)
        current = uri.URI(REL_CURRENT)
        relatives = {}
        for k in keys:
            u = uri.URI(k)
            if not u.octets:  # don't test same document cases
                continue
            resolved, scheme, authority, abs_path, rel_path, query, \
                fragment = REL_EXAMPLES[k]
            logging.info("Testing: %s [*] ( %s [*] %s ) = %s",
                         str(base1), str(base2), k, resolved)
            # two-step resolution, first combines relative URLs, second
            # resolves to absolute
            resolution1 = u.resolve(base2, current)
            relatives[str(resolution1)] = relatives.get(
                str(resolution1), []) + [k]
            resolution2 = str(resolution1.resolve(base1, current))
            self.assertTrue(scheme == u.scheme,
                            "%s found scheme %s" % (k, u.scheme))
            self.assertTrue(authority == u.authority,
                            "%s found authority %s" % (k, u.authority))
            self.assertTrue(abs_path == u.abs_path,
                            "%s found abs_path %s" % (k, u.abs_path))
            self.assertTrue(rel_path == u.rel_path,
                            "%s found rel_path %s" % (k, u.rel_path))
            self.assertTrue(query == u.query,
                            "%s found query %s" % (k, u.query))
            self.assertTrue(fragment == u.fragment,
                            "%s found fragment %s" % (k, u.fragment))
            self.assertTrue(resolved == resolution2,
                            "%s [*] ( %s [*] %s ) = %s ; found %s" %
                            (str(base1), str(base2), k, resolved, resolution2))
        for r in relatives.keys():
            logging.info("Testing: %s [/] %s = ( %s )", r,
                         str(base2), string.join(relatives[r], ' | '))
            u = uri.URI(r)
            # this check removes the 'current document' case
            if u.octets == 'current.doc':
                continue
            relative = str(u.relative(base2))
            # now relative should be one of the relatives!
            no_match = True
            for k in relatives[r]:
                if k == relative:
                    no_match = False
                    break
            self.assertFalse(no_match, "%s [/] %s = ( %s ); found %s" %
                             (r, str(base2), repr(relatives[r]), relative))

FILE_EXAMPLE = "file://vms.host.edu/disk$user/my/notes/note12345.txt"


class FileURLTests(unittest.TestCase):

    def setUp(self):    # noqa
        self.cwd = os.getcwd()
        self.data_path = os.path.join(
            os.path.split(__file__)[0], 'data_rfc2396')
        if not os.path.isabs(self.data_path):
            self.data_path = os.path.join(os.getcwd(), self.data_path)

    def test_constructor(self):
        u = uri.URI.from_octets(FILE_EXAMPLE)
        self.assertTrue(isinstance(u, uri.URI), "FileURL is URI")
        self.assertTrue(isinstance(u, uri.FileURL), "FileURI is FileURL")
        self.assertTrue(str(u) == FILE_EXAMPLE)
        u = uri.FileURL()
        self.assertTrue(str(u) == 'file:///', 'Default file')

    def test_pathnames(self):
        force_8bit = type(self.data_path) is StringType
        base = uri.URI.from_path(self.data_path)
        self.assertTrue(base.get_pathname(force_8bit) == self.data_path,
                        "Expected %s found %s" %
                        (self.data_path, base.get_pathname(force_8bit)))
        for dirpath, dirnames, filenames in os.walk(self.data_path):
            self.visit_method(dirpath, filenames)

    def test_unicode_pathnames(self):
        if type(self.data_path) is StringType:
            c = sys.getfilesystemencoding()
            data_path = unicode(self.data_path, c)
        else:
            data_path = self.data_path
        base = uri.URI.from_path(data_path)
        if os.path.supports_unicode_filenames:
            data_path2 = base.get_pathname()
            self.assertTrue(type(data_path2) is UnicodeType,
                            "Expected get_pathname to return unicode")
            self.assertTrue(data_path2 == data_path,
                            u"Expected %s found %s" % (data_path, data_path2))
            # os.path.walk(data_path,self.visit_method,None)
            for dirpath, dirnames, filenames in os.walk(data_path):
                self.visit_method(dirpath, filenames)
        else:
            data_path2 = base.get_pathname()
            self.assertTrue(type(data_path2) is StringType,
                            "Expected get_pathname to return string")
            logging.warn("os.path.supports_unicode_filenames is False "
                         "(skipped unicode path tests)")

    def visit_method(self, dirname, names):
        d = uri.URI.from_path(os.path.join(dirname, os.curdir))
        c = sys.getfilesystemencoding()
        for name in names:
            if name.startswith('??'):
                logging.warn("8-bit path tests limited to ASCII file names "
                             "by %s encoding", c)
                continue
            join_match = os.path.join(dirname, name)
            if type(name) is UnicodeType:
                seg_name = uri.escape_data(
                    name.encode('utf-8'), uri.is_path_segment_reserved)
            else:
                seg_name = uri.escape_data(name, uri.is_path_segment_reserved)
            u = uri.URI(seg_name)
            u = u.resolve(d)
            self.assertTrue(isinstance(u, uri.FileURL))
            joined = u.get_pathname()
            if type(join_match) is StringType and type(joined) is UnicodeType:
                # if we're walking in 8-bit mode we need to downgrade to
                # compare
                joined = joined.encode(c)
            self.assertTrue(joined == join_match,
                            "Joined pathnames mismatch:\n%s\n%s" %
                            (joined, join_match))


class VirtualFileURLTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.vfs = vfs.defaultFS
        self.cwd = self.vfs.getcwd()
        self.data_path = self.vfs(__file__).split()[0].join('data_rfc2396')
        if not self.data_path.isabs():
            self.data_path = self.vfs.getcwd().join(self.data_path)

    def test_constructor(self):
        u = uri.URI.from_octets(FILE_EXAMPLE)
        self.assertTrue(isinstance(u, uri.URI), "FileURL is URI")
        self.assertTrue(isinstance(u, uri.FileURL), "FileURI is FileURL")
        self.assertTrue(str(u) == FILE_EXAMPLE)
        u = uri.FileURL()
        self.assertTrue(str(u) == 'file:///', 'Default file')

    def test_pathnames(self):
        base = uri.URI.from_virtual_path(self.data_path)
        self.assertTrue(base.get_virtual_file_path() == self.data_path,
                        "Expected %s found %s" %
                        (self.data_path, base.get_virtual_file_path()))
        for dirpath, dirnames, filenames in self.data_path.walk():
            self.visit_method(dirpath, filenames)

    def visit_method(self, dirname, names):
        # Make d a directory like path by adding an empty component at the end
        d = uri.URI.from_virtual_path(dirname.join(dirname.curdir))
        for name in names:
            if unicode(name).startswith('??'):
                logging.warn("8-bit path tests limited to ASCII file names")
                continue
            join_match = dirname.join(name)
            seg_name = uri.escape_data(
                unicode(name).encode('utf-8'), uri.is_path_segment_reserved)
            u = uri.URI(seg_name)
            u = u.resolve(d)
            self.assertTrue(isinstance(u, uri.FileURL))
            joined = u.get_virtual_file_path()
            self.assertTrue(joined == join_match,
                            "Joined pathnames mismatch:\n%s\n%s" %
                            (joined, join_match))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
