#! /usr/bin/env python

import logging
import sys
import types
import unittest

import pyslet.py2 as py2


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(Python2Tests, 'test'),
    ))


class Python2Tests(unittest.TestCase):

    def test_py2(self):
        if sys.version_info[0] < 3:
            self.assertTrue(py2.py2)
        else:
            self.assertFalse(py2.py2)

    def test_suffix(self):
        if sys.version_info[0] < 3:
            self.assertTrue(py2.suffix == '')
        else:
            self.assertTrue(py2.suffix == '3')

    def test_text(self):
        data = "hello"
        udata = u"hello"
        bdata = b"hello"
        xdata = ['hello']
        self.assertTrue(py2.is_text(data))
        self.assertTrue(py2.is_text(udata))
        if sys.version_info[0] < 3:
            self.assertTrue(py2.is_text(bdata))
        else:
            self.assertFalse(py2.is_text(bdata))
        self.assertFalse(py2.is_text(xdata))
        if sys.version_info[0] < 3:
            self.assertFalse(py2.is_unicode(data))
        else:
            self.assertTrue(py2.is_unicode(data))
        self.assertTrue(py2.is_unicode(udata))
        self.assertFalse(py2.is_unicode(bdata))
        self.assertFalse(py2.is_unicode(xdata))
        # force text forces strings to be text
        self.assertTrue(data == py2.force_text(data))
        self.assertTrue(isinstance(py2.force_text(data), type(u"")))
        if sys.version_info[0] < 3:
            self.assertFalse(isinstance(py2.force_text(data), type("")))
        else:
            self.assertTrue(isinstance(py2.force_text(data), type("")))
        self.assertTrue(isinstance(py2.force_text(data), type(u"")))
        self.assertTrue(data == py2.force_text(udata))
        self.assertTrue(isinstance(py2.force_text(udata), type(u"")))
        if sys.version_info[0] < 3:
            # force_text will not throw an error in python 2
            pass
        else:
            try:
                py2.force_text(bdata)
                self.fail("force_text(bytes)")
            except TypeError:
                pass
        # this must work in both python 2 and 3 to prevent accidental
        # conversion to string.
        try:
            py2.force_text(xdata)
            self.fail("force_text(object)")
        except TypeError:
            pass
        # conversion to text
        self.assertTrue(data == py2.to_text(data))
        self.assertTrue(isinstance(py2.to_text(data), type(u"")))
        self.assertTrue(data == py2.to_text(udata))
        self.assertTrue(isinstance(py2.to_text(udata), type(u"")))
        self.assertTrue(data == py2.to_text(bdata))
        self.assertTrue(isinstance(py2.to_text(bdata), type(u"")))
        if sys.version_info[0] < 3:
            self.assertTrue(u"['hello']" == py2.to_text(xdata))
        else:
            self.assertTrue("['hello']" == py2.to_text(xdata))

    def test_character(self):
        self.assertTrue(py2.character(0x2A) == "\x2A")
        self.assertTrue(py2.character(0x2A) == u"\x2A")
        self.assertTrue(isinstance(py2.character(0x2A), type(u"")))
        if sys.version_info[0] < 3:
            self.assertFalse(isinstance(py2.character(0x2A), type("")))
        else:
            self.assertTrue(isinstance(py2.character(0x2A), type("")))

    def test_byte(self):
        # bytes are different in the two versions
        if sys.version_info[0] < 3:
            self.assertTrue(py2.byte(0x2A) == '\x2A')
            self.assertTrue(isinstance(py2.byte(0x2A), type('*')))
            self.assertFalse(isinstance(py2.byte(0x2A), type(u'*')))
        else:
            self.assertTrue(py2.byte(0x2A) == 0x2A)
            self.assertTrue(isinstance(py2.byte(0x2A), int))
        if sys.version_info[0] < 3:
            self.assertTrue(py2.byte('*') == '\x2A')
            self.assertTrue(py2.byte('\xe9') == '\xe9')
            self.assertTrue(py2.byte(b'\xe9') == '\xe9')
            try:
                py2.byte(u'\xe9')
                self.fail("py2.byte(unicode)")
            except TypeError:
                pass
            self.assertTrue(py2.byte(bytearray(b'\xe9')) == '\xe9')
            self.assertTrue(isinstance(py2.byte('*'), type('*')))
            self.assertFalse(isinstance(py2.byte('*'), type(u'*')))
        else:
            self.assertTrue(py2.byte('*') == 0x2A)
            self.assertTrue(py2.byte('\xe9') == 0xE9)
            self.assertTrue(py2.byte(b'\xe9') == 0xE9)
            self.assertTrue(py2.byte(u'\xe9') == 0xE9)
            self.assertTrue(py2.byte(bytearray(b'\xe9')) == 0xE9)
            try:
                py2.byte('\u82f1')
                self.fail("py2.byte(wide char)")
            except ValueError:
                pass
            self.assertTrue(isinstance(py2.byte('*'), int))
        data = b"hello"
        self.assertTrue(py2.join_bytes(list(data)) == data)
        try:
            py2.byte(256)
            self.fail("py2.byte(large)")
        except ValueError:
            pass
        try:
            py2.byte(-1)
            self.fail("py2.byte(negative)")
        except ValueError:
            pass

    def test_str(self):
        class X(py2.UnicodeMixin):
            def __init__(self, data):
                self.data = data

            def __unicode__(self):
                return py2.to_text(self.data)

        self.assertTrue(str(X('hello')) == 'hello')
        self.assertTrue(str(X(u'hello')) == 'hello')
        self.assertTrue(str(X(b'hello')) == 'hello')
        try:
            result = str(X(u'Caf\xe9'))
            if sys.version_info[0] < 3:
                self.assertTrue(result.decode(sys.getdefaultencoding()) ==
                                u'Caf\xe9')
            else:
                self.assertTrue(result == 'Caf\xe9')
            self.assertTrue(isinstance(result, type('')))
        except UnicodeEncodeError:
            # This is acceptable if the string can't be converted
            pass

    def test_literals(self):
        data1 = "hello"
        if sys.version_info[0] < 3:
            target_type = types.UnicodeType
        else:
            target_type = str
        self.assertTrue(py2.u8(b"hello") == data1)
        self.assertTrue(isinstance(py2.u8(b"hello"), target_type))
        self.assertTrue(py2.ul(b"hello") == data1)
        self.assertTrue(isinstance(py2.ul(b"hello"), target_type))
        data2 = b'Caf\xc3\xa9'.decode('utf-8')
        self.assertTrue(py2.u8(b'Caf\xc3\xa9') == data2)
        self.assertTrue(py2.ul(b'Caf\xe9') == data2)
        data3 = b'\xe8\x8b\xb1\xe5\x9b\xbd'.decode('utf-8')
        self.assertTrue(py2.u8(b'\xe8\x8b\xb1\xe5\x9b\xbd') == data3)
        # Catch common errors
        # 1: missing b in literal, OK for ASCII text
        self.assertTrue(py2.u8("hello") == data1)
        self.assertTrue(py2.ul("hello") == data1)
        # 2: missing b, u8 fails for 8-bit character
        try:
            py2.u8('Caf\xe9')
            self.fail('8-bit unqualified literal (bad UTF-8)')
        except UnicodeDecodeError:
            self.fail('8-bit unqualified literal decoded as utf-8')
        except ValueError:
            pass
        # ... but in Python 2 we can't catch valid utf-8 sequences
        # pretending to be unicode strings
        try:
            py2.u8('Caf\xc3\xa9')
            self.assertTrue(sys.version_info[0] < 3,
                            '8-bit unqualified literal (good UTF-8)')
        except ValueError:
            pass
        # 3: missing b, ul accepted with 8-bit character
        self.assertTrue(py2.ul('Caf\xe9')) == data2
        # 4: missing b, u8 fails for 16-bit character
        try:
            # in python 2 we can't catch this but it was probably a bug
            # before anyway due to the missing 'u'
            result = py2.u8('\u82f1\u56fd')
            self.assertTrue(sys.version_info[0] < 3,
                            '16-bit unqualified literal')
            self.assertTrue(result == '\\u82f1\\u56fd')
        except ValueError:
            self.assertFalse(sys.version_info[0] < 3,
                             '16-bit unqualified literal')
        # 5: missing b, ul fails for 16-bit character
        try:
            result = py2.ul('\u82f1\u56fd')
            self.assertTrue(sys.version_info[0] < 3,
                            '16-bit unqualified literal')
            self.assertTrue(result == '\\u82f1\\u56fd')
        except ValueError:
            self.assertFalse(sys.version_info[0] < 3,
                             '16-bit unqualified literal')
        # 6: input already qualified with 'u', benign for ASCII
        self.assertTrue(py2.u8(u"hello") == data1)
        self.assertTrue(py2.ul(u"hello") == data1)
        # ...u8 fails for 8-bit character
        try:
            py2.u8(u'Caf\xe9')
            self.fail('8-bit qualified literal')
        except UnicodeEncodeError:
            self.fail('8-bit qualified literal uncaught encode error')
        except ValueError:
            pass
        # ...ul accepted with 8-bit character
        self.assertTrue(py2.ul(u'Caf\xe9')) == data2
        # ...u8 fails for 16-bit character
        try:
            py2.u8(u'\u82f1\u56fd')
            self.fail('16-bit qualified literal')
        except UnicodeEncodeError:
            self.fail('16-bit qualified literal uncaught encode error')
        except ValueError:
            pass
        # ...ul fails for 16-bit character
        try:
            py2.ul(u'\u82f1\u56fd')
            self.fail('16-bit qualified literal')
        except UnicodeEncodeError:
            self.fail('16-bit qualified literal uncaught encode error')
        except ValueError:
            pass

    def test_range(self):
        if sys.version_info[0] < 3:
            self.assertTrue(isinstance(py2.range3, type(xrange)))
        else:
            self.assertTrue(isinstance(py2.range3, type(range)))

    def test_dict(self):
        d = {"one": 1, "two": 2, "three": 3}
        for i in (1, 2, 3):
            self.assertTrue(i in py2.dict_values(d))
            self.assertFalse(i in py2.dict_keys(d))
        self.assertFalse("one" in py2.dict_values(d))
        self.assertTrue("one" in py2.dict_keys(d))

    def test_builtins(self):
        self.assertTrue(isinstance(py2.builtins, types.ModuleType))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
