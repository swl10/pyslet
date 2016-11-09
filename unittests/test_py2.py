#! /usr/bin/env python

import io
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
        self.assertTrue(py2.is_string(data))
        self.assertTrue(py2.is_string(udata))
        self.assertTrue(py2.is_string(bdata))
        self.assertFalse(py2.is_string(xdata))
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
        self.assertTrue(data == py2.force_text(udata))
        self.assertTrue(isinstance(py2.force_text(udata), type(u"")))
        if sys.version_info[0] < 3:
            self.assertFalse(isinstance(py2.force_text(udata), type("")))
        else:
            self.assertTrue(isinstance(py2.force_text(udata), type("")))
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
        # force ascii forces strings to be ascii text
        self.assertTrue(data == py2.force_ascii(data))
        if sys.version_info[0] < 3:
            self.assertFalse(isinstance(py2.force_ascii(data), type(u"")))
        else:
            self.assertTrue(isinstance(py2.force_ascii(data), type(u"")))
        self.assertTrue(isinstance(py2.force_ascii(data), type("")))
        self.assertTrue(data == py2.force_ascii(udata))
        if sys.version_info[0] < 3:
            self.assertFalse(isinstance(py2.force_ascii(udata), type(u"")))
        else:
            self.assertTrue(isinstance(py2.force_ascii(udata), type(u"")))
        self.assertTrue(isinstance(py2.force_ascii(udata), type("")))
        if sys.version_info[0] < 3:
            self.assertTrue(bdata == py2.force_ascii(bdata))
            self.assertFalse(isinstance(py2.force_ascii(bdata), type(u"")))
        else:
            # can't compare different types in Python 3
            self.assertFalse(bdata == py2.force_ascii(bdata))
            self.assertTrue(isinstance(py2.force_ascii(bdata), type(u"")))
        self.assertTrue(isinstance(py2.force_ascii(bdata), type("")))
        # this must work in both python 2 and 3 to prevent accidental
        # conversion to string.
        try:
            py2.force_ascii(xdata)
            self.fail("force_ascii(object)")
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
        # check the empty text constant:
        self.assertTrue(isinstance(py2.uempty, type(u"")))
        self.assertFalse(py2.uempty)
        self.assertTrue(len(py2.uempty) == 0)

    def test_character(self):
        self.assertTrue(py2.character(0x2A) == "\x2A")
        self.assertTrue(py2.character(0x2A) == u"\x2A")
        self.assertTrue(isinstance(py2.character(0x2A), type(u"")))
        if sys.version_info[0] < 3:
            self.assertFalse(isinstance(py2.character(0x2A), type("")))
        else:
            self.assertTrue(isinstance(py2.character(0x2A), type("")))
        # character must also be able to convert bytes, even if they
        # have values outside the ASCII range
        self.assertTrue(py2.character(py2.byte(0x2A)) == "\x2A")
        self.assertTrue(py2.character(py2.byte(0xe9)) == py2.ul("\xE9"))
        self.assertTrue(py2.join_characters(list(u"Caf\xe9")) ==
                        u"Caf\xe9")
        self.assertTrue(py2.join_characters([u"Caf\xe9"]) == u"Caf\xe9")

    def test_byte(self):
        # bytes are different in the two versions
        if sys.version_info[0] < 3:
            self.assertTrue(py2.byte(0x2A) == '\x2A')
            self.assertTrue(isinstance(py2.byte(0x2A), type('*')))
            self.assertFalse(isinstance(py2.byte(0x2A), type(u'*')))
            self.assertFalse(py2.is_byte(0x82F1))
            self.assertFalse(py2.is_byte(256))
            self.assertTrue(py2.is_byte('\x2A'))
            self.assertTrue(py2.is_byte(b'\x2A'))
            self.assertFalse(py2.is_byte(u'\x2A'))
            self.assertFalse(py2.is_byte(u'**'))
            self.assertTrue(py2.is_byte('**'[0]))
            self.assertFalse(py2.is_byte(u'**'[0]))
        else:
            self.assertTrue(py2.byte(0x2A) == 0x2A)
            self.assertTrue(isinstance(py2.byte(0x2A), int))
            self.assertTrue(py2.is_byte(0x2A))
            self.assertFalse(py2.is_byte(0x82F1))
            self.assertFalse(py2.is_byte('\x2A'))
            self.assertFalse(py2.is_byte(b'\x2A'))
            self.assertFalse(py2.is_byte('**'[0]))
        self.assertFalse(py2.is_byte('**'))
        self.assertFalse(py2.is_byte(b'**'))
        self.assertTrue(py2.is_byte(b'**'[0]))
        if sys.version_info[0] < 3:
            self.assertTrue(py2.byte('*') == '\x2A')
            self.assertTrue(py2.byte('\xe9') == '\xe9')
            self.assertTrue(py2.byte(b'\xe9') == '\xe9')
            self.assertTrue(py2.byte(u'\xe9') == '\xe9')
            self.assertTrue(py2.byte(bytearray(b'\xe9')) == '\xe9')
            try:
                py2.byte(u'\u82f1')
                self.fail("py2.byte(wide char)")
            except ValueError:
                pass
            try:
                py2.byte('\u82f1')
                self.fail("py2.byte(wide char, missing u)")
            except ValueError:
                pass
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
        # test joining iterables of byte
        data = b"hello"
        self.assertTrue(py2.join_bytes(list(data)) == data)
        # test byte_to_bstr
        data = py2.byte(0x40)
        self.assertTrue(py2.byte_to_bstr(data) == b'@')
        self.assertTrue(isinstance(py2.byte_to_bstr(data), bytes))
        for i in py2.range3(256):
            b = py2.byte(i)
            self.assertTrue(py2.byte_to_bstr(b)[0] == b)
        # Now move on to exception handling
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
        # now test byte value...
        self.assertTrue(py2.byte_value(py2.byte(0)) == 0)
        self.assertTrue(py2.byte_value(py2.byte(0x30)) == 0x30)
        self.assertTrue(py2.byte_value(py2.byte(0xFF)) == 0xFF)
        # force bytes
        self.assertTrue(py2.force_bytes("Hello") == b"Hello")
        self.assertTrue(isinstance(py2.force_bytes("Hello"), bytes))
        self.assertTrue(py2.force_bytes(b"Hello") == b"Hello")
        self.assertTrue(isinstance(py2.force_bytes(b"Hello"), bytes))
        self.assertTrue(py2.force_bytes(u"Hello") == b"Hello")
        self.assertTrue(isinstance(py2.force_bytes(u"Hello"), bytes))
        try:
            py2.force_bytes(py2.ul('Caf\xe9'))
            self.fail("force_bytes with high-bit character")
        except UnicodeEncodeError:
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

    def test_cmp(self):
        class X(py2.CmpMixin):
            def __init__(self, data):
                self.data = data

            def __cmp__(self, other):
                if self.data < other.data:
                    return -1
                elif self.data == other.data:
                    return 0
                else:
                    return 1

        # call __eq__
        self.assertTrue(X(1) == X(1))
        self.assertFalse(X(1) == X(2))
        # call __ne__
        self.assertFalse(X(1) != X(1))
        self.assertTrue(X(1) != X(2))
        # call __lt__
        self.assertFalse(X(1) < X(1))
        self.assertTrue(X(1) < X(2))
        # call __le__
        self.assertTrue(X(1) <= X(1))
        self.assertTrue(X(1) <= X(2))
        self.assertFalse(X(2) <= X(1))
        # call __gt__
        self.assertFalse(X(1) > X(1))
        self.assertTrue(X(2) > X(1))
        # call __ge__
        self.assertTrue(X(1) >= X(1))
        self.assertTrue(X(2) >= X(1))
        self.assertFalse(X(1) >= X(2))

    def test_key_simple(self):
        class X(py2.SortableMixin):
            def __init__(self, data):
                self.data = data

            def sortkey(self):
                return self.data

        # call __eq__
        self.assertTrue(X(1) == X(1))
        self.assertFalse(X(1) == X(2))
        # call __ne__
        self.assertFalse(X(1) != X(1))
        self.assertTrue(X(1) != X(2))
        # call __lt__
        self.assertFalse(X(1) < X(1))
        self.assertTrue(X(1) < X(2))
        # call __le__
        self.assertTrue(X(1) <= X(1))
        self.assertTrue(X(1) <= X(2))
        self.assertFalse(X(2) <= X(1))
        # call __gt__
        self.assertFalse(X(1) > X(1))
        self.assertTrue(X(2) > X(1))
        # call __ge__
        self.assertTrue(X(1) >= X(1))
        self.assertTrue(X(2) >= X(1))
        self.assertFalse(X(1) >= X(2))
        # can't compare different types
        # Python 2 and 3 return False if __eq__ returns NotImplemented
        self.assertFalse(X(1) == 1)
        # and hence True...
        self.assertTrue(X(1) != 1)
        try:
            # falls back to object ids in Python 2
            X(1) < 2 or X(1) > 2
            self.fail("unorderable types: TypeError")
        except TypeError:
            pass
        try:
            # falls back to object ids in Python 2
            X(1) <= 2 or X(1) >= 2
            self.fail("unorderable types: TypeError")
        except TypeError:
            pass

    def test_key_other(self):
        class X(py2.SortableMixin):
            def __init__(self, data):
                self.data = data

            def otherkey(self, other):
                if isinstance(other, X):
                    return other.data
                elif isinstance(other, int):
                    return other
                else:
                    return NotImplemented

            def sortkey(self):
                return self.data

        # call __eq__
        self.assertTrue(X(1) == X(1))
        self.assertTrue(X(1) == 1)
        self.assertFalse(X(1) == X(2))
        self.assertFalse(X(1) == 2)
        # call __ne__
        self.assertFalse(X(1) != X(1))
        self.assertFalse(X(1) != 1)
        self.assertTrue(X(1) != X(2))
        self.assertTrue(X(1) != 2)
        # call __lt__
        self.assertFalse(X(1) < X(1))
        self.assertFalse(X(1) < 1)
        self.assertTrue(X(1) < X(2))
        self.assertTrue(X(1) < 2)
        # call __le__
        self.assertTrue(X(1) <= X(1))
        self.assertTrue(X(1) <= 1)
        self.assertTrue(X(1) <= X(2))
        self.assertTrue(X(1) <= 2)
        self.assertFalse(X(2) <= X(1))
        self.assertFalse(X(2) <= 1)
        # call __gt__
        self.assertFalse(X(1) > X(1))
        self.assertFalse(X(1) > 1)
        self.assertTrue(X(2) > X(1))
        self.assertTrue(X(2) > 1)
        # call __ge__
        self.assertTrue(X(1) >= X(1))
        self.assertTrue(X(1) >= 1)
        self.assertTrue(X(2) >= X(1))
        self.assertTrue(X(2) >= 1)
        self.assertFalse(X(1) >= X(2))
        self.assertFalse(X(1) >= 2)

    def test_bool(self):
        class X(py2.BoolMixin):
            def __init__(self, value):
                self.value = value

            def __bool__(self):
                return self.value

        x = X(True)
        self.assertTrue(x)
        x = X(False)
        self.assertFalse(x)

        class X(py2.BoolMixin):
            def __init__(self, value):
                self.value = value

            def __len__(self):
                return 0

            def __bool__(self):
                return self.value

        # now test that __bool__ takes precedence over __len__
        x = X(True)
        self.assertTrue(x)
        x = X(False)
        self.assertFalse(x)

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

    def test_long(self):
        if sys.version_info[0] < 3:
            self.assertTrue(py2.long2 is long)
        else:
            self.assertTrue(py2.long2 is int)

    def test_buffer(self):
        if sys.version_info[0] < 3:
            self.assertTrue(py2.buffer2 is buffer)
        else:
            self.assertTrue(py2.buffer2 is bytes)

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
        self.assertTrue(("one", 1) in py2.dict_items(d))
        self.assertFalse((1, "one") in py2.dict_items(d))
        # finally, these functions return iterable objects, not lists
        try:
            py2.dict_keys(d)[0]
            self.fail("dict_keys can be indexed")
        except TypeError:
            pass
        try:
            py2.dict_values(d)[0]
            self.fail("dict_values can be indexed")
        except TypeError:
            pass
        try:
            py2.dict_items(d)[0]
            self.fail("dict_items can be indexed")
        except TypeError:
            pass

    def test_builtins(self):
        self.assertTrue(isinstance(py2.builtins, types.ModuleType))

    def test_output(self):
        txt_out = io.StringIO()
        save_stdout = sys.stdout
        try:
            sys.stdout = txt_out
            py2.output(py2.ul("Going to the\nCaf\xe9"))
        finally:
            sys.stdout = save_stdout
        self.assertTrue(txt_out.getvalue() == py2.ul("Going to the\nCaf\xe9"))
        bin_out = io.BytesIO()
        try:
            sys.stdout = bin_out
            py2.output(py2.ul("Going to the\nCaf\xe9"))
        finally:
            sys.stdout = save_stdout
        self.assertTrue(bin_out.getvalue() == b"Going to the\nCaf\xc3\xa9")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
