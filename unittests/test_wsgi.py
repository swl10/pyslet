#! /usr/bin/env python

import cgi
import io
import json
import logging
import optparse
import os.path
import random
import shutil
import tempfile
import threading
import time
import unittest

from pyslet import html401 as html
from pyslet import iso8601 as iso
from pyslet import wsgi
from pyslet.http import (
    client as http,
    cookie,
    params)
from pyslet.odata2 import (
    metadata as edmx,
    sqlds as sql)
from pyslet.py2 import (
    dict_items,
    is_ascii,
    is_text,
    long2,
    range3,
    ul,
    urlencode
    )
from pyslet.rfc2396 import URI, FileURL


def suite(prefix='test'):
    loader = unittest.TestLoader()
    loader.testMethodPrefix = prefix
    return unittest.TestSuite((
        loader.loadTestsFromTestCase(FunctionTests),
        loader.loadTestsFromTestCase(ContextTests),
        loader.loadTestsFromTestCase(AppTests),
        loader.loadTestsFromTestCase(WSGIDataAppTests),
        loader.loadTestsFromTestCase(AppCipherTests),
        loader.loadTestsFromTestCase(CookieSessionTests),
        loader.loadTestsFromTestCase(FullAppTests),
    ))


STATIC_FILES = os.path.join(
    os.path.join(os.path.split(__file__)[0], 'data_wsgi'), 'static')

PRIVATE_FILES = os.path.join(
    os.path.join(os.path.split(__file__)[0], 'data_wsgi'), 'data')

SETTINGS_FILE = os.path.join(
    os.path.join(os.path.split(__file__)[0], 'data_wsgi'), 'settings.json')


class MockRequest(object):

    def __init__(self, method='GET', path='/', query='', host='localhost',
                 port=80, secure=False, ip='127.0.0.1', body=b'',
                 body_type=None):
        self.input = io.BytesIO(body)
        self.output = io.BytesIO()
        self.errors = io.BytesIO()
        self.environ = {
            'REQUEST_METHOD': method,
            'SCRIPT_NAME': '',
            'PATH_INFO': path,
            'QUERY_STRING': query,
            'SERVER_NAME': host,
            'SERVER_PORT': str(port),
            'SERVER_PROTCOL': 'HTTP/1.1',
            'REMOTE_ADDR': ip,
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': 'https' if secure else 'http',
            'wsgi.input': self.input,
            'wsgi.errors': self.errors,
            'wsgi.multithread': True,
            'wsgi.multiprocess': False,
            'wsgi.run_once': False}
        if body is not None:
            self.environ['CONTENT_LENGTH'] = str(len(body))
        if body_type is not None:
            self.environ['CONTENT_TYPE'] = body_type
        self.status = None
        self.headers = None

    def add_cookies(self, clist):
        hvalue = b"; ".join([b"%s=%s" % (x.name, x.value) for x in clist])
        self.environ['HTTP_COOKIE'] = hvalue.decode('iso-8859-1')

    def call_app(self, app):
        for data in app(self.environ, self.start_response):
            if isinstance(data, bytes):
                self.output.write(data)
            else:
                raise ValueError("Value output by app: %s", str(data))

    def start_response(self, status, response_headers, exc_info=None):
        if not isinstance(status, str):
            raise ValueError("Value for status line: %s" % repr(status))
        self.status = status
        self.headers = {}
        for h, v in response_headers:
            if not isinstance(v, str):
                raise ValueError("Value for header: %s" % h)
            hv = self.headers.setdefault(h.lower(), [])
            hv.append(v)
        self.cookies = {}
        cookie_headers = self.headers.get('set-cookie', [])
        for chi in cookie_headers:
            c = cookie.Section4Cookie.from_str(chi)
            if c.name in self.cookies:
                raise RuntimeError("Duplicate cookie in response: %s" % c.name)
            self.cookies[c.name] = c
        return self.output.write


class MockApp(wsgi.WSGIApp):

    static_files = STATIC_FILES

    private_files = PRIVATE_FILES


class FunctionTests(unittest.TestCase):

    def test_keygen(self):
        key = wsgi.generate_key()
        # by default the key has 128 bits, which equates to 8 quadruplets
        self.assertTrue(len(key.split('.')) == 8)
        crushed_key = ''.join(key.split('.'))
        self.assertTrue(len(crushed_key) == 32)
        for c in crushed_key:
            self.assertTrue(c in "0123456789ABCDEF")
        # obviously we shouldn't be generating the same key twice
        key2 = wsgi.generate_key()
        self.assertTrue(key2 != key)
        # and we can generate shorter keys
        key = wsgi.generate_key(32)
        self.assertTrue(len(key.split('.')) == 2)
        crushed_key = ''.join(key.split('.'))
        self.assertTrue(len(crushed_key) == 8)
        # but we always round up to quadruplets
        key = wsgi.generate_key(33)
        self.assertTrue(len(key.split('.')) == 3, key)
        crushed_key = ''.join(key.split('.'))
        self.assertTrue(len(crushed_key) == 12)
        # degenerate behaviour
        try:
            wsgi.generate_key(0)
            self.fail("key == 0")
        except ValueError:
            pass
        # degenerate behaviour
        try:
            wsgi.generate_key(-8)
            self.fail("key < 0")
        except ValueError:
            pass

    def test_key60(self):
        # no duplicates, but must be predictable
        results = {}
        for i in range3(1000):
            # re-use the generate_key function to create random keys
            key = wsgi.generate_key().encode('ascii')
            int_key = wsgi.key60(key)
            self.assertFalse(key in results, "generate_key is suspect")
            self.assertTrue(int_key >= 0, "negative key60")
            self.assertTrue(isinstance(int_key, long2))
            results[key] = int_key
        for key, int_key in dict_items(results):
            # must be repeatable!
            self.assertTrue(wsgi.key60(key) == int_key)


class ContextTests(unittest.TestCase):

    def test_class(self):
        # minimum content size for loading should be 64K
        self.assertTrue(wsgi.WSGIContext.MAX_CONTENT > 0xFFFF)

    def test_constructor(self):
        req = MockRequest()
        context = wsgi.WSGIContext(req.environ, req.start_response)
        self.assertTrue(isinstance(context.environ, dict))
        self.assertTrue(context.start_response_method == req.start_response)
        self.assertTrue(context.status is None)
        self.assertTrue(context.status_message is None)
        self.assertTrue(isinstance(context.headers, list))
        self.assertTrue(len(context.headers) == 0)

    def test_status(self):
        req = MockRequest()
        context = wsgi.WSGIContext(req.environ, req.start_response)
        self.assertTrue(context.status is None)
        self.assertTrue(context.status_message is None)
        context.set_status(200)
        self.assertTrue(context.status == 200)
        self.assertTrue(context.status_message == "OK")
        context.set_status(404)
        self.assertTrue(context.status == 404)
        self.assertTrue(context.status_message == "Not Found")

    def test_headers(self):
        req = MockRequest()
        context = wsgi.WSGIContext(req.environ, req.start_response)
        self.assertTrue(len(context.headers) == 0)
        context.add_header('X-Test', 'value String')
        self.assertTrue(len(context.headers) == 1)
        # case preserving header name
        self.assertTrue(context.headers[0][0] == 'X-Test')
        # case preserving header value
        self.assertTrue(context.headers[0][1] == 'value String')

    def test_start_response(self):
        req = MockRequest()
        context = wsgi.WSGIContext(req.environ, req.start_response)
        context.set_status(200)
        context.add_header('X-Test', 'value String')
        write_call = context.start_response()
        self.assertTrue(write_call is not None)
        write_call(b"Hello")
        self.assertTrue(len(req.headers) == 1)
        self.assertTrue(req.headers['x-test'] == ['value String'])
        self.assertTrue(req.output.getvalue() == b"Hello")

    def test_app_root(self):
        req = MockRequest()
        context = wsgi.WSGIContext(req.environ, req.start_response)
        root = context.get_app_root()
        self.assertTrue(isinstance(root, URI))
        # default to SERVER_NAME
        self.assertTrue(str(root) == 'http://localhost/')
        req = MockRequest()
        req.environ['HTTP_HOST'] = "www.evil.com"
        context = wsgi.WSGIContext(req.environ, req.start_response)
        root = context.get_app_root()
        self.assertTrue(isinstance(root, URI))
        # check that we ignore Host header and default to SERVER_NAME
        self.assertTrue(str(root) == 'http://localhost/')
        req = MockRequest()
        req.environ['HTTP_HOST'] = "www.evil.com"
        # canonical_root passed as a parameter always takes precedence
        context = wsgi.WSGIContext(req.environ, req.start_response,
                                   canonical_root="https://www.good.com:8443")
        root = context.get_app_root()
        self.assertTrue(isinstance(root, URI))
        self.assertTrue(str(root) == 'https://www.good.com:8443/')
        # test https
        req = MockRequest(secure=True, port=443)
        context = wsgi.WSGIContext(req.environ, req.start_response)
        root = context.get_app_root()
        self.assertTrue(str(root) == 'https://localhost/', str(root))
        # test non-default port for http
        req = MockRequest(port=81)
        context = wsgi.WSGIContext(req.environ, req.start_response)
        root = context.get_app_root()
        self.assertTrue(str(root) == 'http://localhost:81/')
        # test non-default port for https
        req = MockRequest(secure=True, port=8443)
        context = wsgi.WSGIContext(req.environ, req.start_response)
        root = context.get_app_root()
        self.assertTrue(str(root) == 'https://localhost:8443/')
        # check that the path is ignored (four ways)
        req = MockRequest(path="/script.py/index.html")
        context = wsgi.WSGIContext(req.environ, req.start_response)
        self.assertTrue(str(context.get_app_root()) == 'http://localhost/')
        # odd case, but same result
        req.environ['SCRIPT_NAME'] = "/"
        context = wsgi.WSGIContext(req.environ, req.start_response)
        self.assertTrue(str(context.get_app_root()) == 'http://localhost/')
        req.environ['SCRIPT_NAME'] = "/script.py"
        context = wsgi.WSGIContext(req.environ, req.start_response)
        self.assertTrue(str(context.get_app_root()) ==
                        'http://localhost/script.py/')
        req.environ['SCRIPT_NAME'] = "/script.py/"
        context = wsgi.WSGIContext(req.environ, req.start_response)
        self.assertTrue(str(context.get_app_root()) ==
                        'http://localhost/script.py/')

    def test_url(self):
        req = MockRequest()
        context = wsgi.WSGIContext(req.environ, req.start_response)
        url = context.get_url()
        self.assertTrue(isinstance(url, URI))
        self.assertTrue(str(url) == 'http://localhost/')
        # test https
        req = MockRequest(secure=True, port=443)
        context = wsgi.WSGIContext(req.environ, req.start_response)
        url = context.get_url()
        self.assertTrue(str(url) == 'https://localhost/', str(url))
        # test non-default port for http
        req = MockRequest(port=81)
        context = wsgi.WSGIContext(req.environ, req.start_response)
        url = context.get_url()
        self.assertTrue(str(url) == 'http://localhost:81/')
        # test non-default port for https
        req = MockRequest(secure=True, port=8443)
        context = wsgi.WSGIContext(req.environ, req.start_response)
        url = context.get_url()
        self.assertTrue(str(url) == 'https://localhost:8443/')
        # check that canonical_root trumps the port
        req = MockRequest(port=8080)
        context = wsgi.WSGIContext(req.environ, req.start_response,
                                   canonical_root="http://www.example.com")
        url = context.get_url()
        self.assertTrue(str(url) == 'http://www.example.com/')
        # now check the path, with empty SCRIPT_NAME
        req = MockRequest(path="/script.py/index.html")
        context = wsgi.WSGIContext(req.environ, req.start_response)
        url = context.get_url()
        self.assertTrue(str(url) == 'http://localhost/script.py/index.html')
        # now check the path with a non empty SCRIPT_NAME
        req = MockRequest(path="/index.html")
        context = wsgi.WSGIContext(req.environ, req.start_response)
        req.environ['SCRIPT_NAME'] = "/script.py"
        url = context.get_url()
        self.assertTrue(str(url) == 'http://localhost/script.py/index.html')
        # and now with a transferred slash
        req = MockRequest(path="index.html")
        context = wsgi.WSGIContext(req.environ, req.start_response)
        req.environ['SCRIPT_NAME'] = "/script.py/"
        url = context.get_url()
        self.assertTrue(str(url) == 'http://localhost/script.py/index.html')
        # and finally the query...
        req = MockRequest(path="/index.html", query="e=mc2")
        context = wsgi.WSGIContext(req.environ, req.start_response)
        url = context.get_url()
        self.assertTrue(str(url) == 'http://localhost/index.html?e=mc2')

    def test_query(self):
        req = MockRequest(path="/index.html", query="e=mc2&F=ma")
        context = wsgi.WSGIContext(req.environ, req.start_response)
        query = context.get_query()
        self.assertTrue(isinstance(query, dict))
        self.assertTrue("e" in query)
        self.assertTrue("F" in query)
        self.assertTrue(query['e'] == "mc2")
        self.assertTrue(query['F'] == "ma")
        # check multiple values
        req = MockRequest(path="/index.html", query="e=mc2&e=2.718")
        context = wsgi.WSGIContext(req.environ, req.start_response)
        query = context.get_query()
        self.assertTrue(query['e'] == "mc2,2.718")
        # check multiple calls return the same object
        query2 = context.get_query()
        self.assertTrue(query is query2)
        # that that form parameters and cookies are ignored
        req = MockRequest(method="POST", path="/index.html",
                          query="e=mc2&F=ma", body=b"g=9.8",
                          body_type="application/x-www-form-urlencoded")
        req.environ['HTTP_COOKIE'] = "h=6.626e-34"
        context = wsgi.WSGIContext(req.environ, req.start_response)
        query = context.get_query()
        self.assertTrue(len(query) == 2, str(query))
        self.assertTrue(query == {"e": "mc2", "F": "ma"})

    def test_content(self):
        req = MockRequest(body=None)
        # CONTENT_LENGTH is None in this case
        context = wsgi.WSGIContext(req.environ, req.start_response)
        content = context.get_content()
        # but we still return an empty string for no content
        self.assertTrue(isinstance(content, bytes))
        self.assertTrue(len(content) == 0)
        req = MockRequest(body=b'')
        # CONTENT_LENGTH is 0 in this case
        context = wsgi.WSGIContext(req.environ, req.start_response)
        content = context.get_content()
        self.assertTrue(isinstance(content, bytes))
        self.assertTrue(len(content) == 0)
        req = MockRequest(body=b'0123456789ABCDEF')
        # CONTENT_LENGTH is 16 in this case
        context = wsgi.WSGIContext(req.environ, req.start_response)
        content = context.get_content()
        self.assertTrue(content == b"0123456789ABCDEF")
        # check that multiple calls return the same object
        content2 = context.get_content()
        self.assertTrue(content is content2)
        # check truncated read
        req = MockRequest(body=b'0123456789ABCDEF')
        req.environ['CONTENT_LENGTH'] = "10"
        context = wsgi.WSGIContext(req.environ, req.start_response)
        content = context.get_content()
        self.assertTrue(content == b"0123456789")
        # check bad CONTENT_LENGTH, read's until EOF
        req = MockRequest(body=b'0123456789')
        req.environ['CONTENT_LENGTH'] = "16"
        context = wsgi.WSGIContext(req.environ, req.start_response)
        content = context.get_content()
        self.assertTrue(content == b"0123456789")
        # check MAX_CONTENT, defaults to 64K
        src = io.BytesIO()
        b = b"01"
        while src.tell() < 0x10000:
            src.write(b)
            b = src.getvalue()
        req = MockRequest(body=src.getvalue())
        context = wsgi.WSGIContext(req.environ, req.start_response)
        try:
            content = context.get_content()
            self.assertTrue(content == src.getvalue())
        except wsgi.BadRequest:
            self.fail("64K content always acceptable")
        # just one more 'wafer thin' byte...
        src.write(b'0')
        req = MockRequest(body=src.getvalue())
        context = wsgi.WSGIContext(req.environ, req.start_response)
        try:
            content = context.get_content()
        except wsgi.BadRequest:
            pass
        # check that a preceding get_form call results in None
        req = MockRequest(method="POST", body=b'e=mc2&F=ma',
                          body_type="application/x-www-form-urlencoded")
        context = wsgi.WSGIContext(req.environ, req.start_response)
        context.get_form()
        content = context.get_content()
        self.assertTrue(content is None)

    def test_form(self):
        req = MockRequest(method="POST", body=b"e=mc2&F=ma",
                          body_type="application/x-www-form-urlencoded")
        context = wsgi.WSGIContext(req.environ, req.start_response)
        form = context.get_form()
        self.assertTrue(isinstance(form, cgi.FieldStorage))
        self.assertTrue("e" in form, str(form.keys()))
        self.assertTrue("F" in form, str(form.keys()))
        self.assertTrue(form['e'].value == "mc2")
        self.assertTrue(form['F'].value == "ma")
        # check multiple values
        req = MockRequest(method="POST", body=b"e=mc2&e=2.718",
                          body_type="application/x-www-form-urlencoded")
        context = wsgi.WSGIContext(req.environ, req.start_response)
        form = context.get_form()
        self.assertTrue(isinstance(form['e'], list))
        self.assertTrue(form.getlist('e') == ["mc2", "2.718"])
        # check multiple calls return the same object
        form2 = context.get_form()
        self.assertTrue(form is form2)
        # that that query parameters and cookies are ignored
        req = MockRequest(method="POST", path="/index.html",
                          body=b"e=mc2&F=ma", query="g=9.8",
                          body_type="application/x-www-form-urlencoded")
        req.environ['HTTP_COOKIE'] = "h=6.626e-34"
        context = wsgi.WSGIContext(req.environ, req.start_response)
        form = context.get_form()
        self.assertTrue(len(form) == 2, str(form))
        self.assertFalse("g" in form)
        self.assertFalse("h" in form)
        # check that a preceding get_content call results in None
        req = MockRequest(method="POST", body=b'e=mc2&F=ma',
                          body_type="application/x-www-form-urlencoded")
        context = wsgi.WSGIContext(req.environ, req.start_response)
        context.get_content()
        form = context.get_form()
        self.assertTrue(form is None)

    def test_form_string(self):
        req = MockRequest(method="POST", body=b"e=mc2&F=ma",
                          body_type="application/x-www-form-urlencoded")
        context = wsgi.WSGIContext(req.environ, req.start_response)
        self.assertTrue(context.get_form_string("e") == "mc2")
        self.assertTrue(context.get_form_string("F") == "ma")
        # check multiple values
        req = MockRequest(method="POST", body=b"e=mc2&e=2.718",
                          body_type="application/x-www-form-urlencoded")
        context = wsgi.WSGIContext(req.environ, req.start_response)
        self.assertTrue(context.get_form_string("e") == "mc2,2.718")
        self.assertTrue(context.get_form_string("F") == '')

    def test_form_file(self):
        body = b"""
--AaB03x
Content-Disposition: form-data; name="submit-name"

Larry
--AaB03x
Content-Disposition: form-data; name="files"; filename="file1.txt"
Content-Type: text/plain

... contents of file1.txt ...
--AaB03x--"""
        body_type = "multipart/form-data; boundary=AaB03x"
        req = MockRequest(method="POST", body=body, body_type=body_type)
        context = wsgi.WSGIContext(req.environ, req.start_response)
        self.assertTrue(context.get_form_string("submit-name") == "Larry")
        self.assertTrue(context.get_form_string("files") ==
                        "... contents of file1.txt ...")
        try:
            context.get_form_string("files", max_length=5)
            self.fail("max-length check")
        except wsgi.BadRequest:
            pass
        form = context.get_form()
        self.assertTrue(form['files'].file is not None)
        self.assertTrue(form['files'].file.read() ==
                        b"... contents of file1.txt ...")

    def test_cookies(self):
        req = MockRequest(path="/index.html")
        req.environ['HTTP_COOKIE'] = "e=mc2; F=ma"
        context = wsgi.WSGIContext(req.environ, req.start_response)
        cookies = context.get_cookies()
        self.assertTrue(isinstance(cookies, dict))
        self.assertTrue(len(cookies) == 2)
        self.assertTrue(b"e" in cookies)
        self.assertTrue(b"F" in cookies)
        self.assertTrue(cookies[b'e'] == b"mc2")
        self.assertTrue(cookies[b'F'] == b"ma")
        # check multiple values
        req = MockRequest(path="/index.html")
        req.environ['HTTP_COOKIE'] = "e=mc2; e=2.718"
        context = wsgi.WSGIContext(req.environ, req.start_response)
        cookies = context.get_cookies()
        # multi-valued cookies are sorted and joined with comma
        self.assertTrue(cookies[b'e'] == b"2.718,mc2")
        # check multiple calls return the same object
        cookies2 = context.get_cookies()
        self.assertTrue(cookies is cookies2)
        # that that form parameters and the query are ignored
        req = MockRequest(method="POST", path="/index.html",
                          query="h=6.626e-34", body=b"g=9.8",
                          body_type="application/x-www-form-urlencoded")
        req.environ['HTTP_COOKIE'] = "e=mc2; F=ma"
        context = wsgi.WSGIContext(req.environ, req.start_response)
        cookies = context.get_cookies()
        self.assertTrue(len(cookies) == 2, str(cookies))
        self.assertTrue(cookies == {b"e": b"mc2", b"F": b"ma"})


class MockLogging(object):

    CRITICAL = 50
    ERROR = 40
    WARNING = 30
    INFO = 20
    DEBUG = 10
    NOTSET = 0

    def __init__(self):
        self.level = self.NOTSET

    def basicConfig(self, **kwargs):        # noqa
        if 'level' in kwargs:
            self.level = kwargs['level']

    def info(self, msg, *args, **kwargs):
        # don't need to output mocked logging
        pass

    def debug(self, msg, *args, **kwargs):
        # don't need to output mocked logging
        pass


class AppTests(unittest.TestCase):

    def setUp(self):        # noqa
        # mock the logging module in wsgi to prevent out tests actually
        # overriding the logging level
        self.save_logging = wsgi.logging
        wsgi.logging = MockLogging()

    def tearDown(self):     # noqa
        wsgi.logging = self.save_logging

    def test_constructor(self):
        class BaseApp(wsgi.WSGIApp):
            pass
        self.assertTrue(BaseApp.ContextClass is wsgi.WSGIContext)
        self.assertTrue(BaseApp.static_files is None)
        self.assertTrue(BaseApp.private_files is None)
        # our BaseApp doesn't define a settings file
        self.assertTrue(BaseApp.settings_file is None)
        self.assertTrue(BaseApp.settings is None)
        self.assertFalse(BaseApp.settings)
        app = BaseApp()
        self.assertFalse(app.stop)
        self.assertTrue(app.id > 0)
        app2 = BaseApp()
        self.assertFalse(app == app2)
        self.assertFalse(app.id == app2.id)
        self.assertFalse(hash(app) == hash(app2))

    def test_v_option(self):
        class VApp(wsgi.WSGIApp):
            pass
        p = optparse.OptionParser()
        VApp.add_options(p)
        options, args = p.parse_args([])
        self.assertTrue(options.logging is None)
        VApp.setup(options=options, args=args)
        # check setting value
        self.assertTrue(VApp.settings['WSGIApp']['level'] is None)
        self.assertTrue(wsgi.logging.level == wsgi.logging.NOTSET)

        class VApp(wsgi.WSGIApp):
            pass
        options, args = p.parse_args(['-v'])
        self.assertTrue(options.logging == 1)
        VApp.setup(options=options, args=args)
        self.assertTrue(VApp.settings['WSGIApp']['level'] == logging.WARNING)
        self.assertTrue(wsgi.logging.level == wsgi.logging.WARNING)

        class VApp(wsgi.WSGIApp):
            pass
        options, args = p.parse_args(['-vv'])
        self.assertTrue(options.logging == 2)
        VApp.setup(options=options, args=args)
        self.assertTrue(VApp.settings['WSGIApp']['level'] == logging.INFO)
        self.assertTrue(wsgi.logging.level == wsgi.logging.INFO)

        class VApp(wsgi.WSGIApp):
            pass
        options, args = p.parse_args(['-v', '-vv'])
        self.assertTrue(options.logging == 3)
        VApp.setup(options=options, args=args)
        self.assertTrue(VApp.settings['WSGIApp']['level'] == logging.DEBUG)
        self.assertTrue(wsgi.logging.level == wsgi.logging.DEBUG)

        class VApp(wsgi.WSGIApp):
            pass
        options, args = p.parse_args(['-v', '-v', '-v', '-v'])
        self.assertTrue(options.logging == 4)
        VApp.setup(options=options, args=args)
        self.assertTrue(VApp.settings['WSGIApp']['level'] == logging.DEBUG)
        self.assertTrue(wsgi.logging.level == wsgi.logging.DEBUG)

    def test_p_option(self):
        class PApp(wsgi.WSGIApp):
            pass
        p = optparse.OptionParser()
        PApp.add_options(p)
        options, args = p.parse_args([])
        self.assertTrue(options.port is None)
        PApp.setup(options=options, args=args)
        # check setting value
        self.assertTrue(PApp.settings['WSGIApp']['port'] == 8080)

        class PApp(wsgi.WSGIApp):
            pass
        options, args = p.parse_args(['-p', '81'])
        self.assertTrue(options.port == '81')
        PApp.setup(options=options, args=args)
        self.assertTrue(PApp.settings['WSGIApp']['port'] == 81)

        class PApp(wsgi.WSGIApp):
            pass
        options, args = p.parse_args(['--port=81'])
        self.assertTrue(options.port == '81')
        PApp.setup(options=options, args=args)
        self.assertTrue(PApp.settings['WSGIApp']['port'] == 81)

    def test_i_option(self):
        class IApp(wsgi.WSGIApp):
            pass
        p = optparse.OptionParser()
        IApp.add_options(p)
        options, args = p.parse_args([])
        self.assertTrue(options.interactive is None)
        IApp.setup(options=options, args=args)
        # check setting value
        self.assertTrue(IApp.settings['WSGIApp']['interactive'] is False)

        class IApp(wsgi.WSGIApp):
            pass
        options, args = p.parse_args(['-i'])
        self.assertTrue(options.interactive is True)
        IApp.setup(options=options, args=args)
        self.assertTrue(IApp.settings['WSGIApp']['interactive'] is True)

        class IApp(wsgi.WSGIApp):
            pass
        options, args = p.parse_args(['--interactive'])
        self.assertTrue(options.interactive is True)
        IApp.setup(options=options, args=args)
        self.assertTrue(IApp.settings['WSGIApp']['interactive'] is True)

    def test_static_option(self):
        class StaticApp(wsgi.WSGIApp):
            pass
        p = optparse.OptionParser()
        StaticApp.add_options(p)
        options, args = p.parse_args([])
        self.assertTrue(options.static is None)
        StaticApp.setup(options=options, args=args)
        # check setting value
        self.assertTrue(StaticApp.static_files is None)

        class StaticApp(wsgi.WSGIApp):
            pass
        options, args = p.parse_args(['--static', STATIC_FILES])
        self.assertTrue(options.static == STATIC_FILES)
        StaticApp.setup(options=options, args=args)
        self.assertTrue(StaticApp.static_files ==
                        os.path.abspath(STATIC_FILES))

        class StaticApp(wsgi.WSGIApp):
            settings_file = os.path.abspath(SETTINGS_FILE)
        options, args = p.parse_args([])
        StaticApp.setup(options=options, args=args)
        self.assertTrue(StaticApp.static_files ==
                        os.path.abspath(STATIC_FILES))

    def test_private_option(self):
        class PrivateApp(wsgi.WSGIApp):
            pass
        p = optparse.OptionParser()
        PrivateApp.add_options(p)
        options, args = p.parse_args([])
        self.assertTrue(options.private is None)
        PrivateApp.setup(options=options, args=args)
        # check setting value, no override, base setting
        self.assertTrue(PrivateApp.private_files is None)
        try:
            PrivateApp.resolve_setup_path('folder', private=True)
            self.fail("relative path requires private path")
        except RuntimeError:
            pass
        path = PrivateApp.resolve_setup_path('file:///folder', private=True)

        class PrivateApp(wsgi.WSGIApp):
            pass
        options, args = p.parse_args(['--private', PRIVATE_FILES])
        self.assertTrue(options.private == PRIVATE_FILES)
        PrivateApp.setup(options=options, args=args)
        self.assertTrue(PrivateApp.private_files ==
                        os.path.abspath(PRIVATE_FILES))
        path = PrivateApp.resolve_setup_path('folder', private=True)
        self.assertTrue(
            path == os.path.abspath(os.path.join(PRIVATE_FILES, 'folder')))

        class PrivateApp(wsgi.WSGIApp):
            settings_file = os.path.abspath(SETTINGS_FILE)
        options, args = p.parse_args([])
        PrivateApp.setup(options=options, args=args)
        self.assertTrue(PrivateApp.private_files ==
                        os.path.abspath(PRIVATE_FILES))

    def test_settings_option(self):
        path = SETTINGS_FILE

        class SettingsApp(wsgi.WSGIApp):
            pass
        p = optparse.OptionParser()
        SettingsApp.add_options(p)
        options, args = p.parse_args([])
        self.assertTrue(options.settings is None)
        SettingsApp.setup(options=options, args=args)
        # check setting value, base setting is None
        self.assertTrue(SettingsApp.settings_file is None)
        self.assertTrue(SettingsApp.base is None)

        class SettingsApp(wsgi.WSGIApp):
            pass
        options, args = p.parse_args(['--settings', path])
        self.assertTrue(options.settings == path)
        SettingsApp.setup(options=options, args=args)
        self.assertTrue(SettingsApp.settings_file == os.path.abspath(path))
        self.assertTrue(isinstance(SettingsApp.base, FileURL))
        self.assertTrue(SettingsApp.base.get_pathname() ==
                        SettingsApp.settings_file)

    def test_settings_file(self):
        path = SETTINGS_FILE

        class SettingsApp(wsgi.WSGIApp):
            pass
        SettingsApp.setup()
        # in the absence of a settings file, check defaults
        self.assertTrue("WSGIApp" in SettingsApp.settings)
        self.assertTrue("level" in SettingsApp.settings['WSGIApp'])
        self.assertTrue(SettingsApp.settings['WSGIApp']['level'] is None)
        self.assertTrue(SettingsApp.settings['WSGIApp']['canonical_root'] ==
                        "http://localhost:8080")
        self.assertTrue(SettingsApp.settings['WSGIApp']['port'] == 8080)
        self.assertTrue(SettingsApp.settings['WSGIApp']['interactive'] is
                        False)
        self.assertTrue(SettingsApp.settings['WSGIApp']['static'] is None)
        self.assertTrue(SettingsApp.settings['WSGIApp']['private'] is None)

        class SettingsApp(wsgi.WSGIApp):
            pass
        # check that we can read different values from a settings file
        SettingsApp.settings_file = path
        SettingsApp.setup()
        self.assertTrue(SettingsApp.settings['WSGIApp']['level'] == 20)
        self.assertTrue(SettingsApp.settings['WSGIApp']['canonical_root'] ==
                        "https://www.example.com:8443")
        self.assertTrue(SettingsApp.settings['WSGIApp']['port'] == 8081)
        self.assertTrue(SettingsApp.settings['WSGIApp']['interactive'] is True)
        self.assertTrue(SettingsApp.settings['WSGIApp']['static'] == "static")
        self.assertTrue(SettingsApp.settings['WSGIApp']['private'] ==
                        "data")
        self.assertTrue(SettingsApp.static_files ==
                        os.path.abspath(STATIC_FILES))
        self.assertTrue(SettingsApp.private_files ==
                        os.path.abspath(PRIVATE_FILES))
        # now check that the command line overrides them
        path2 = os.path.join(os.path.split(__file__)[0],
                             'data_wsgi', 'settings2.json')

        class SettingsApp(wsgi.WSGIApp):
            pass
        SettingsApp.settings_file = path2
        p = optparse.OptionParser()
        SettingsApp.add_options(p)
        options, args = p.parse_args(
            ['-v', '--port=8082', '--interactive',
             '--static=%s' % STATIC_FILES, '--private=%s' % PRIVATE_FILES])
        SettingsApp.setup(options=options, args=args)
        self.assertTrue(SettingsApp.settings['WSGIApp']['level'] == 30)
        self.assertTrue(SettingsApp.settings['WSGIApp']['port'] == 8082)
        self.assertTrue(SettingsApp.settings['WSGIApp']['interactive'] is True)
        # settings file values are not modified to reflect overrides as
        # they are only used during startup
        self.assertTrue(SettingsApp.settings['WSGIApp']['static'] is None)
        self.assertTrue(SettingsApp.settings['WSGIApp']['private'] is None)
        self.assertTrue(SettingsApp.static_files ==
                        os.path.abspath(STATIC_FILES))
        self.assertTrue(SettingsApp.private_files ==
                        os.path.abspath(PRIVATE_FILES))

    def test_set_method(self):
        class App(wsgi.WSGIApp):

            def method1(self, context):
                context.set_status(200)
                return [b'test1']

            def method2(self, context):
                context.set_status(200)
                return [b'test2']

            def method3(self, context):
                context.set_status(200)
                return [b'test3']

            def method4(self, context):
                context.set_status(200)
                return [b'test4']
        App.setup()
        app = App()
        app.set_method('/test/test', app.method1)
        app.set_method('/test/*', app.method2)
        app.set_method('/*/test', app.method3)
        app.set_method('/tset/tset', app.method4)
        # root is not mapped
        req = MockRequest(path="/")
        req.call_app(app)
        self.assertTrue(req.status.startswith('404 '))
        # matches /test/*, even though there is no trailing slash!
        req = MockRequest(path="/test")
        req.call_app(app)
        self.assertTrue(req.output.getvalue() == b"test2")
        # matches /test/*, fallback wildcard
        req = MockRequest(path="/test/tset")
        req.call_app(app)
        self.assertTrue(req.output.getvalue() == b"test2")
        # matches /test/*, fallback wildcard
        req = MockRequest(path="/test/testA")
        req.call_app(app)
        self.assertTrue(req.output.getvalue() == b"test2")
        # matches /test/*, any path after wildcard
        req = MockRequest(path="/test/test/test")
        req.call_app(app)
        self.assertTrue(req.output.getvalue() == b"test2")
        # not mapped
        req = MockRequest(path="/testA")
        req.call_app(app)
        self.assertTrue(req.status.startswith('404 '))
        # matches /test/test, not the wildcard
        req = MockRequest(path="/test/test")
        req.call_app(app)
        self.assertTrue(req.output.getvalue() == b"test1")
        # matches /*/test
        req = MockRequest(path="/tset/test")
        req.call_app(app)
        self.assertTrue(req.output.getvalue() == b"test3")

    def test_wrapper(self):
        class App(wsgi.WSGIApp):

            def page(self, context):
                context.set_status(200)
                context.add_header('Content-Length', 10)
                context.add_header('Content-Type', ul('text/plain'))
                context.start_response()
                return [ul("0123456789")]
        # check that common errors are caught and absorbed
        App.setup()
        app = App()
        app.set_method('/*', app.page)
        req = MockRequest(path="/index.htm")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.headers['content-length'] == ['10'])
        self.assertTrue(req.output.getvalue() == b"0123456789")

    def test_static(self):
        MockApp.setup()
        app = MockApp()
        app.set_method('/*', app.static_page)
        req = MockRequest(path="/res/public.txt")
        req.call_app(app)
        # we expect success
        self.assertTrue(req.status.startswith('200 '))
        ctype = req.headers['content-type']
        self.assertTrue(len(ctype) == 1)
        self.assertTrue(ctype[0] == "text/plain",
                        str(req.headers['content-type']))
        self.assertTrue(req.output.getvalue().startswith(b"Hello mum!"))
        req = MockRequest(path="/res/private_file.txt")
        req.call_app(app)
        # we expect 404
        self.assertTrue(req.status.startswith('404 '))
        req = MockRequest(path="/res/private.d/noaccess.txt")
        req.call_app(app)
        # we expect 404
        self.assertTrue(req.status.startswith('404 '))
        req = MockRequest(path="/res/")
        req.call_app(app)
        self.assertTrue(req.status.startswith('404 '))
        req = MockRequest(path="/res")
        req.call_app(app)
        self.assertTrue(req.status.startswith('404 '))

    def test_file_response(self):
        # calculate length of public.txt dynamically
        # allows us to check out with CRLF
        pub_path = os.path.join(STATIC_FILES, 'res', 'public.txt')
        pub_len = os.stat(pub_path).st_size

        class App(wsgi.WSGIApp):

            def file_page(self, context):
                context.set_status(200)
                context.add_header('Content-Type', 'text/plain')
                return self.file_response(context, pub_path)

            def missing_page(self, context):
                context.set_status(404)
                context.add_header('Content-Type', 'text/plain')
                return self.file_response(context, pub_path)

        App.setup()
        app = App()
        app.set_method('/*', app.file_page)
        app.set_method('/missing', app.missing_page)
        req = MockRequest(path="/index.htm")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('200 '), req.status)
        self.assertTrue(req.headers['content-length'] == [str(pub_len)])
        self.assertTrue('last-modified' in req.headers)
        self.assertTrue(req.output.getvalue().strip() == b'Hello mum!')
        # check that we can still control the status
        req = MockRequest(path="/missing")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('404 '))

    def test_html_response(self):
        class App(wsgi.WSGIApp):

            def str_page(self, context):
                context.set_status(200)
                return self.html_response(context, b"<title>Caf\xe9</title>")

            def unicode_page(self, context):
                context.set_status(404)
                return self.html_response(context,
                                          ul(b"<title>Caf\xe9</title>"))
        App.setup()
        app = App()
        app.set_method('/str.htm', app.str_page)
        app.set_method('/unicode.htm', app.unicode_page)
        req = MockRequest(path="/str.htm")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('200 '))
        self.assertTrue(req.headers['content-type'] == ['text/html'])
        self.assertTrue(req.headers['content-length'] == ['19'])
        self.assertFalse('last-modified' in req.headers)
        self.assertTrue(req.output.getvalue() == b"<title>Caf\xe9</title>")
        # unicode and status override check combined
        req = MockRequest(path="/unicode.htm")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('404 '))
        logging.debug(repr(req.output.getvalue()))
        self.assertTrue(req.headers['content-type'] ==
                        ['text/html; charset=utf-8'])
        # check it really is UTF-8
        self.assertTrue(req.output.getvalue() ==
                        b'<title>Caf\xc3\xa9</title>')

    def test_json_response(self):
        class App(wsgi.WSGIApp):

            def good_page(self, context):
                context.set_status(200)
                return self.json_response(
                    context, json.dumps(ul(b"Caf\xe9"), ensure_ascii=False))

            def bad_page(self, context):
                context.set_status(404)
                return self.json_response(
                    context, json.dumps(ul(b"Caf\xe9"), ensure_ascii=True))

            def ugly_page(self, context):
                context.set_status(500)
                return self.json_response(
                    context, json.dumps(ul(b"Caf\xe9"),
                                        ensure_ascii=False).encode('utf-8'))
        App.setup()
        app = App()
        app.set_method('/good.json', app.good_page)
        app.set_method('/bad.json', app.bad_page)
        app.set_method('/ugly.json', app.ugly_page)
        req = MockRequest(path="/good.json")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('200 '))
        self.assertTrue(req.headers['content-type'] == ['application/json'])
        self.assertTrue(req.headers['content-length'] == ['7'])
        self.assertFalse('last-modified' in req.headers)
        output = req.output.getvalue().decode('utf-8')
        # unicode characters encoded by UTF-8 only
        self.assertTrue(output == ul(b'"Caf\xe9"'))
        req = MockRequest(path="/bad.json")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('404 '))
        self.assertTrue(req.headers['content-type'] == ['application/json'])
        self.assertTrue(req.headers['content-length'] == ['11'])
        output = req.output.getvalue().decode('utf-8')
        # unicode characters encoded in the JSON itself
        self.assertTrue(output == ul(b'"Caf\\u00e9"'))
        req = MockRequest(path="/ugly.json")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('500 '))
        self.assertTrue(req.headers['content-type'] == ['application/json'])
        self.assertTrue(req.headers['content-length'] == ['7'])
        output = req.output.getvalue().decode('utf-8')
        # unicode characters encoded before being passed
        self.assertTrue(output == ul(b'"Caf\xe9"'))

    def test_text_response(self):
        class App(wsgi.WSGIApp):

            def str_page(self, context):
                context.set_status(200)
                return self.text_response(context, b"Cafe")

            def unicode_page(self, context):
                context.set_status(404)
                return self.text_response(context, ul(b"Caf\xe9"))

            def bad_page(self, context):
                context.set_status(500)
                return self.text_response(context,
                                          ul(b"Caf\xe9").encode('utf-8'))
        App.setup()
        app = App()
        app.set_method('/str.txt', app.str_page)
        app.set_method('/unicode.txt', app.unicode_page)
        app.set_method('/bad.txt', app.bad_page)
        req = MockRequest(path="/str.txt")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('200 '))
        self.assertTrue(req.headers['content-type'] == ['text/plain'])
        self.assertTrue(req.headers['content-length'] == ['4'])
        self.assertFalse('last-modified' in req.headers)
        self.assertTrue(req.output.getvalue() == b"Cafe")
        # unicode and status override check combined
        req = MockRequest(path="/unicode.txt")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('404 '))
        logging.debug(repr(req.output.getvalue()))
        self.assertTrue(req.headers['content-type'] ==
                        ['text/plain; charset=utf-8'])
        # check it really is UTF-8
        self.assertTrue(req.output.getvalue() == b'Caf\xc3\xa9')
        # non-ASCII data in output is not checked (for speed)
        req = MockRequest(path="/bad.txt")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('500 '))
        logging.debug(repr(req.output.getvalue()))
        self.assertTrue(req.headers['content-type'] == ['text/plain'])
        # check it was output as unchecked UTF-8
        self.assertTrue(req.output.getvalue() == b'Caf\xc3\xa9')

    def test_redirect_page(self):
        class App(wsgi.WSGIApp):

            def moved_permanently(self, context):
                return self.redirect_page(
                    context, "http://www.pyslet.org/", 301)

            def found(self, context):
                return self.redirect_page(
                    context, URI.from_octets("http://www.pyslet.org/"), 302)

            def see_other(self, context):
                return self.redirect_page(
                    context, "http://www.pyslet.org/")
        App.setup()
        app = App()
        app.set_method('/moved_permanently', app.moved_permanently)
        app.set_method('/found', app.found)
        app.set_method('/see_other', app.see_other)
        req = MockRequest(path="/moved_permanently")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('301 '))
        self.assertTrue(req.headers['content-type'] == ['text/html'])
        self.assertTrue(req.headers['location'] == ['http://www.pyslet.org/'])
        self.assertFalse('last-modified' in req.headers)
        doc = html.XHTMLDocument()
        req.output.seek(0)
        doc.read(req.output)
        links = list(doc.root.find_children_depth_first(html.A))
        self.assertTrue(len(links) == 1)
        link = links[0]
        self.assertTrue(link.href == 'http://www.pyslet.org/')
        # URI parameter check
        req = MockRequest(path="/found")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('302 '))
        self.assertTrue(req.headers['content-type'] == ['text/html'])
        self.assertTrue(req.headers['location'] == ['http://www.pyslet.org/'])
        # Default code check
        req = MockRequest(path="/see_other", method="POST")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('303 '))
        self.assertTrue(req.headers['content-type'] == ['text/html'])
        self.assertTrue(req.headers['location'] == ['http://www.pyslet.org/'])

    def test_error_page(self):
        class App(wsgi.WSGIApp):

            def missing(self, context):
                return self.error_page(
                    context, 404, "Gone for good")

            def error(self, context):
                return self.error_page(context, msg=ul(b"Gone to the Caf\xe9"))

            def whoops(self, context):
                return self.error_page(context)
        App.setup()
        app = App()
        app.set_method('/missing', app.missing)
        app.set_method('/error', app.error)
        app.set_method('/whoops', app.whoops)
        req = MockRequest(path="/missing")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('404 '))
        self.assertTrue(req.headers['content-type'] == ['text/plain'],
                        req.headers)
        self.assertTrue(req.output.getvalue() == b"Gone for good")
        # URI parameter check
        req = MockRequest(path="/error")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('500 '))
        self.assertTrue(req.headers['content-type'] ==
                        ['text/plain; charset=utf-8'])
        self.assertTrue(req.output.getvalue() == b'Gone to the Caf\xc3\xa9')
        # Check error raising
        req = MockRequest(path="/whoops")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('500 '))
        self.assertTrue(req.headers['content-type'] == ['text/plain'])
        logging.debug(repr(req.output.getvalue()))
        self.assertTrue(req.output.getvalue() == b'500 Internal Server Error')

    def test_catch(self):
        class App(wsgi.WSGIApp):

            def whoops(self, context):
                raise RuntimeError("Whoops!")

        App.setup()
        app = App()
        app.set_method('/whoops', app.whoops)
        # Check error raising
        req = MockRequest(path="/whoops")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('500 '))
        self.assertTrue(req.headers['content-type'] == ['text/plain'])
        logging.debug(repr(req.output.getvalue()))
        self.assertTrue(req.output.getvalue() ==
                        b'500 Internal Server Error\r\nWhoops!')

    def test_run_server(self):
        class App(wsgi.WSGIApp):

            def start_page(self, context):
                context.set_status(200)
                return self.text_response(context, "Start")

            def stop_page(self, context):
                context.set_status(200)
                self.stop = True
                return self.text_response(context, "Stop!")
        App.setup()
        app = App()
        app.set_method('/start', app.start_page)
        app.set_method('/stop', app.stop_page)
        port = random.randint(1111, 9999)
        app.settings['WSGIApp']['port'] = port
        t = threading.Thread(target=app.run_server)
        try:
            t.start()
            client = http.Client()
            request = http.ClientRequest("http://localhost:%i/start" % port)
            client.process_request(request)
            self.assertTrue(request.response.status == 200)
            self.assertTrue(request.res_body == b"Start")
        finally:
            # stop the server
            request = http.ClientRequest("http://localhost:%i/stop" % port)
            client.process_request(request)
            # joint the run_server thread, should terminate
            t.join()


class WSGIDataAppTests(unittest.TestCase):

    DUMMY_SCHEMA = b"""<?xml version="1.0" encoding="utf-8" standalone="yes" ?>
<edmx:Edmx Version="1.0"
    xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx"
    xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
    <edmx:DataServices m:DataServiceVersion="2.0">
        <Schema Namespace="DummySchema"
            xmlns="http://schemas.microsoft.com/ado/2006/04/edm">
            <EntityContainer Name="Dummy" m:IsDefaultEntityContainer="true">
                <EntitySet Name="Dummies" EntityType="DummySchema.DummyType"/>
            </EntityContainer>
            <EntityType Name="DummyType">
                <Key>
                    <PropertyRef Name="ID"/>
                </Key>
                <Property Name="ID" Type="Edm.Int32" Nullable="false"/>
            </EntityType>
        </Schema>
    </edmx:DataServices>
</edmx:Edmx>"""

    def setUp(self):        # noqa
        self.d = tempfile.mkdtemp('.d', 'pyslet-test_wsgi-')
        self.data_dir = os.path.join(self.d, 'data')
        os.mkdir(self.data_dir)
        # write out the settings
        settings = {'WSGIDataApp': {'metadata': 'data/metadata.xml'}}
        settings = json.dumps(settings).encode('utf-8')
        self.settings_path = os.path.join(self.d, 'settings.json')
        with open(self.settings_path, 'wb') as f:
            f.write(settings)
        # put the metadata file in the default place
        self.default_path = os.path.join(self.data_dir, 'metadata.xml')
        with open(self.default_path, 'wb') as f:
            f.write(self.DUMMY_SCHEMA)
        self.db_path = os.path.join(self.data_dir, 'database.sqlite3')

    def tearDown(self):     # noqa
        shutil.rmtree(self.d)

    def test_metadata_option(self):
        """
        cases:
        rel class attribute, private_files, option: OK, override
        """
        # put the metadata file in a custom place
        custom_path = os.path.join(self.data_dir, 'myschema.xml')
        with open(custom_path, 'wb') as f:
            f.write(self.DUMMY_SCHEMA)

        class MetadataApp(wsgi.WSGIDataApp):
            pass
        p = optparse.OptionParser()
        MetadataApp.add_options(p)
        options, args = p.parse_args([])
        # setup should fail
        try:
            MetadataApp.setup(options=options, args=args)
            self.fail("settings_file + metadata path required")
        except RuntimeError:
            pass
        self.assertFalse(os.path.exists(self.db_path))

        class MetadataApp(wsgi.WSGIDataApp):
            settings_file = self.settings_path
            private_files = self.data_dir
        p = optparse.OptionParser()
        MetadataApp.add_options(p)
        options, args = p.parse_args([])
        MetadataApp.setup(options=options, args=args)
        # don't create tables by default
        self.assertFalse(os.path.exists(self.db_path))

    def test_s_option(self):
        class SApp(wsgi.WSGIDataApp):
            settings_file = self.settings_path
            private_files = self.data_dir
        p = optparse.OptionParser()
        SApp.add_options(p)
        options, args = p.parse_args([])
        self.assertTrue(options.sqlout is False)
        self.assertTrue(options.create_tables is False)
        p = optparse.OptionParser()
        SApp.add_options(p)
        options, args = p.parse_args(['-s'])
        self.assertTrue(options.sqlout is True)
        p = optparse.OptionParser()
        SApp.add_options(p)
        options, args = p.parse_args(['--sqlout'])
        self.assertTrue(options.sqlout is True)
        self.assertTrue(options.create_tables is False)
        try:
            SApp.setup(options=options, args=args)
            # log the suggested SQL database schema and then exit.
            self.fail("Expected system exit")
        except SystemExit:
            pass
        self.assertFalse(os.path.exists(self.db_path))

        class SApp(wsgi.WSGIDataApp):
            settings_file = self.settings_path
            private_files = self.data_dir
        p = optparse.OptionParser()
        SApp.add_options(p)
        options, args = p.parse_args(['--sqlout', '--create_tables'])
        self.assertTrue(options.sqlout is True)
        self.assertTrue(options.create_tables is True)
        try:
            SApp.setup(options=options, args=args)
            # logthe suggested SQL database schema and then exit.
            # The setting of --create_tables is ignored.
            self.fail("Expected system exit")
        except SystemExit:
            pass
        self.assertFalse(os.path.exists(self.db_path))

    def test_create_option(self):
        class CreateApp(wsgi.WSGIDataApp):
            settings_file = self.settings_path
            private_files = self.data_dir
        p = optparse.OptionParser()
        CreateApp.add_options(p)
        options, args = p.parse_args([])
        self.assertTrue(options.create_tables is False)
        CreateApp.setup(options=options, args=args)
        # should not have created the database...
        self.assertFalse(os.path.exists(self.db_path))
        # or the tables!
        with CreateApp.container['Dummies'].open() as collection:
            try:
                # table should not exist, this should fail
                len(collection)
                self.fail("No tables expected")
            except sql.SQLError:
                pass
        CreateApp.data_source.close()
        os.remove(self.db_path)

        class CreateApp(wsgi.WSGIDataApp):
            settings_file = self.settings_path
            private_files = self.data_dir
        p = optparse.OptionParser()
        CreateApp.add_options(p)
        options, args = p.parse_args(['--create_tables'])
        self.assertTrue(options.create_tables is True)
        CreateApp.setup(options=options, args=args)
        # should have created the database...
        self.assertTrue(os.path.exists(self.db_path))
        # and the tables!
        with CreateApp.container['Dummies'].open() as collection:
            try:
                # table should now exit
                len(collection)
            except sql.SQLError:
                self.fail("Tables expected")
        # remove database for the next test...
        # close the data source, can't just remove the database file
        CreateApp.data_source.close()
        os.remove(self.db_path)

        class CreateApp(wsgi.WSGIDataApp):
            settings_file = self.settings_path
            private_files = self.data_dir
        p = optparse.OptionParser()
        CreateApp.add_options(p)
        options, args = p.parse_args(['--memory'])
        self.assertTrue(options.create_tables is False)
        CreateApp.setup(options=options, args=args)
        # should not have created the database no disck...
        self.assertFalse(os.path.exists(self.db_path))
        # but the tables should exist in memory!
        with CreateApp.container['Dummies'].open() as collection:
            try:
                len(collection)
            except sql.SQLError:
                self.fail("Tables expected")


class AppCipherTests(unittest.TestCase):

    def setUp(self):    # noqa
        key_schema = """<edmx:Edmx Version="1.0"
    xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx"
    xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
    <edmx:DataServices m:DataServiceVersion="2.0">
        <Schema Namespace="KeySchema"
            xmlns="http://schemas.microsoft.com/ado/2006/04/edm">
            <EntityContainer Name="KeyDatabase"
                    m:IsDefaultEntityContainer="true">
                <EntitySet Name="AppKeys" EntityType="KeySchema.AppKey"/>
            </EntityContainer>
            <EntityType Name="AppKey">
                <Key>
                    <PropertyRef Name="KeyNum"/>
                </Key>
                <Property Name="KeyNum" Nullable="false" Type="Edm.Int32"/>
                <Property Name="KeyString" Nullable="false"
                    Type="Edm.String" MaxLength="256" Unicode="false"/>
                <Property Name="Expires" Nullable="false"
                    Type="Edm.DateTime" Precision="0"/>
            </EntityType>
        </Schema>
    </edmx:DataServices>
</edmx:Edmx>"""
        self.doc = edmx.Document()
        self.doc.read(src=key_schema)
        self.container = self.doc.root.DataServices["KeySchema.KeyDatabase"]
        # self.memcontainer = InMemoryEntityContainer(self.container)
        self.dbcontainer = sql.SQLiteEntityContainer(
            file_path=":memory:", container=self.container)
        self.dbcontainer.create_all_tables()
        self.key_set = self.container['AppKeys']

    def test_plaintext(self):
        ac = wsgi.AppCipher(0, b'password', self.key_set)
        # we don't create an records initially
        with self.key_set.open() as collection:
            self.assertTrue(len(collection) == 0)
        data0 = ac.encrypt(b"Hello")
        self.assertTrue(is_ascii(data0))
        self.assertFalse(data0 == "Hello")
        self.assertTrue(ac.decrypt(data0) == b"Hello")
        # check signing
        msg = b"Hello Caf\xc3\xa9"
        sdata0 = ac.sign(msg)
        self.assertTrue(is_ascii(sdata0))
        try:
            self.assertTrue(ac.check_signature(sdata0, msg) == msg)
        except ValueError:
            self.fail("Failed to validate signed message")
        sdata0 = ac.ascii_sign(msg)
        pos = sdata0.find("Hello%20Caf%C3%A9")
        self.assertTrue(pos >= 0, "signed msg not visible")
        try:
            self.assertTrue(ac.check_signature(sdata0) == msg)
        except ValueError:
            self.fail("Failed to validate ascii signed message")
        # now try with the message
        try:
            self.assertTrue(ac.check_signature(sdata0, msg) == msg)
        except ValueError:
            self.fail("Failed to validate ascii signed message")
        # and now try with mismatched message
        try:
            ac.check_signature(sdata0, b"Hello")
            self.fail("Validated mismatched messages")
        except ValueError:
            pass
        # now corrupt the message by lower-casing the 'H'
        tampered = sdata0[:pos] + "h" + sdata0[pos + 1:]
        try:
            ac.check_signature(tampered)
            self.fail("Validated tampered message")
        except ValueError:
            pass
        try:
            ac.check_signature(tampered, msg)
            self.fail("Validated tampered message")
        except ValueError:
            pass
        # now change the key
        ac.change_key(1, b"pa$$word",
                      iso.TimePoint.from_unix_time(time.time() - 1))
        with self.key_set.open() as collection:
            self.assertTrue(len(collection) == 1)
        data1 = ac.encrypt(b"Hello")
        self.assertFalse(data0 == data1)
        self.assertTrue(ac.decrypt(data1) == b"Hello")
        self.assertTrue(ac.decrypt(data0) == b"Hello")
        ac.change_key(2, b"unguessable",
                      iso.TimePoint.from_unix_time(time.time() - 1))
        with self.key_set.open() as collection:
            self.assertTrue(len(collection) == 2)
        self.assertTrue(ac.decrypt(data0) == b"Hello")
        ac.change_key(10, b"anotherkey",
                      iso.TimePoint.from_unix_time(time.time() - 1))
        with self.key_set.open() as collection:
            self.assertTrue(len(collection) == 3)
        self.assertTrue(ac.decrypt(data0) == b"Hello")
        ac2 = wsgi.AppCipher(10, b"anotherkey", self.key_set)
        self.assertTrue(ac2.decrypt(data0) == b"Hello")
        # check we can still validate older hashes
        try:
            self.assertTrue(ac.check_signature(sdata0) == msg)
        except ValueError:
            self.fail("Failed to validate ascii signed message")

    def test_aes(self):
        if not wsgi.got_crypto:
            logging.warn("Skipping AESAppCipher tests, PyCrypto not installed")
            return
        ac = wsgi.AESAppCipher(0, 'password', self.key_set)
        # we don't create an records initially
        with self.key_set.open() as collection:
            self.assertTrue(len(collection) == 0)
        data0 = ac.encrypt(b"Hello")
        self.assertFalse(data0 == "Hello")
        self.assertTrue(ac.decrypt(data0) == "Hello")
        ac.change_key(1, "pa$$word",
                      iso.TimePoint.from_unix_time(time.time() - 1))
        with self.key_set.open() as collection:
            self.assertTrue(len(collection) == 1)
        data1 = ac.encrypt(b"Hello")
        self.assertFalse(data0 == data1)
        self.assertTrue(ac.decrypt(data1) == "Hello")
        self.assertTrue(ac.decrypt(data0) == "Hello")
        ac.change_key(2, "unguessable",
                      iso.TimePoint.from_unix_time(time.time() - 1))
        with self.key_set.open() as collection:
            self.assertTrue(len(collection) == 2)
        self.assertTrue(ac.decrypt(data0) == "Hello")
        ac.change_key(10, "anotherkey",
                      iso.TimePoint.from_unix_time(time.time() - 1))
        with self.key_set.open() as collection:
            self.assertTrue(len(collection) == 3)
        self.assertTrue(ac.decrypt(data0) == "Hello")
        ac2 = wsgi.AESAppCipher(10, "anotherkey", self.key_set)
        self.assertTrue(ac2.decrypt(data0) == "Hello")


class CookieSessionTests(unittest.TestCase):

    def setUp(self):        # noqa

        class TestSessionApp(wsgi.SessionApp):
            settings_file = os.path.abspath(SETTINGS_FILE)
        p = optparse.OptionParser()
        TestSessionApp.add_options(p)
        options, args = p.parse_args(['--memory'])
        TestSessionApp.setup(options=options, args=args)
        self.app = TestSessionApp()

    def test_constructor(self):
        s = wsgi.CookieSession()
        # check basic fields
        self.assertTrue(is_text(s.sid))
        self.assertTrue(len(s.sid) >= 32, "expect 128 bits in hex")
        self.assertFalse(s.established, "not established")
        self.assertTrue(isinstance(s.last_seen, iso.TimePoint))
        s2 = wsgi.CookieSession()
        self.assertFalse(s.sid == s2.sid, "unique sid")

    def test_establish(self):
        s = wsgi.CookieSession()
        self.assertFalse(s.established)
        old_id = s.sid
        new_id = s.establish()
        self.assertTrue(s.established)
        self.assertFalse(s.sid == old_id)
        self.assertTrue(s.sid == new_id)
        try:
            s.establish()
            self.fail("establish for established session")
        except ValueError:
            pass

    def test_seen_now(self):
        s = wsgi.CookieSession()
        s.established = True
        s.last_seen = iso.TimePoint.from_str("1986-11-22T08:45:00Z")
        last_seen = s.last_seen
        s.seen_now()
        self.assertFalse(s.last_seen == last_seen)

    def test_age(self):
        now = iso.TimePoint.from_now_utc().get_unixtime()
        s = wsgi.CookieSession()
        # Unless our script is very slow, this should be recent
        self.assertTrue(s.age() < 10)
        # now make it older
        s.last_seen = iso.TimePoint.from_unix_time(now - 20)
        self.assertTrue(s.age() > 10)

    def test_str(self):
        s = wsgi.CookieSession()
        s.established = True
        s.last_seen = iso.TimePoint.from_str("1986-11-22T08:45:00Z")
        sdata = str(s)
        s2 = wsgi.CookieSession(sdata)
        self.assertTrue(s.sid == s2.sid)
        self.assertTrue(s2.established)
        self.assertTrue(s.last_seen == s2.last_seen)


class TestSessionApp(wsgi.SessionApp):

    settings_file = os.path.abspath(SETTINGS_FILE)

    def init_dispatcher(self):
        wsgi.SessionApp.init_dispatcher(self)
        self.set_method('/', self.home)

    @wsgi.session_decorator
    def home(self, context):
        data = """<html><head><title>FullApp</title></head>
<body><p>Path: / on FullApp</p></body></html>"""
        context.set_status(200)
        return self.html_response(context, data)


class FullAppTests(unittest.TestCase):

    def setUp(self):    # noqa

        class FullApp(TestSessionApp):
            pass
        p = optparse.OptionParser()
        FullApp.add_options(p)
        options, args = p.parse_args(['--memory'])
        FullApp.setup(options, args)
        self.app = FullApp()

    def test_framed_cookies(self):
        req = MockRequest()
        req.call_app(self.app)
        # we expect a redirect
        self.assertTrue(req.status.startswith('303 '))
        self.assertTrue('location' in req.headers)
        target = req.headers['location']
        self.assertTrue(len(target) == 1)
        target = URI.from_octets(target[0])
        self.assertTrue(target.get_addr() == ('www.example.com', 8443))
        self.assertTrue(isinstance(target, params.HTTPSURL))
        # and we expect a warning cookie
        self.assertTrue(self.app._test_cookie in req.cookies)
        # and we expect a session cookie
        self.assertTrue(self.app._session_cookie in req.cookies)
        cflag = req.cookies[self.app._test_cookie]
        sid = req.cookies[self.app._session_cookie]
        # follow the redirect, passing the cookies
        req = MockRequest(path=target.abs_path, query=target.query)
        req.add_cookies([cflag, sid])
        req.call_app(self.app)
        # we expect a redirect back to our original path
        self.assertTrue(req.status.startswith('303 '), req.status)
        self.assertTrue('location' in req.headers)
        target = req.headers['location']
        self.assertTrue(len(target) == 1)
        target = URI.from_octets(target[0])
        self.assertTrue(target.get_addr() == ('www.example.com', 8443))
        self.assertTrue(isinstance(target, params.HTTPSURL))
        self.assertTrue(target.abs_path == '/')
        # and an updated sid!
        self.assertTrue(self.app._session_cookie in req.cookies)
        new_sid = req.cookies[self.app._session_cookie]
        self.assertFalse(sid.value == new_sid.value)
        sid = new_sid
        # now we repeat the first request with the cookies,
        # should not get a redirect anymore
        req = MockRequest()
        req.add_cookies([cflag, sid])
        req.call_app(self.app)
        self.assertTrue(req.status.startswith('200 '))
        self.assertFalse('location' in req.headers)

    def test_unframed_cookies(self):
        req = MockRequest()
        req.call_app(self.app)
        # follow the redirect, tested in the framed test
        target = URI.from_octets(req.headers['location'][0])
        # ...but ignore the cookies
        req = MockRequest(path=target.abs_path, query=target.query)
        req.call_app(self.app)
        # this should display the frame detection page, no cookies
        self.assertTrue(req.status.startswith('200 '))
        self.assertFalse('location' in req.headers)
        self.assertTrue(len(req.cookies) == 0)
        # can we check the content?
        doc = html.XHTMLDocument()
        req.output.seek(0)
        doc.read(req.output)
        # there should be a form called 'wlaunch'
        form = doc.get_element_by_id('wlaunch')
        if isinstance(form, html.Form):
            self.assertTrue(form.action is not None)
            target = form.action
            self.assertTrue(target.get_addr() == ('www.example.com', 8443))
            self.assertTrue(isinstance(target, params.HTTPSURL))
            # get the input fields
            query = {}
            for input in form.find_children_depth_first(html.Input):
                if input.name in ("return", "s", "sig", "submit"):
                    query[input.name] = str(input.value)
            query = urlencode(query)
        elif isinstance(form, html.A):
            # just a link
            target = form.href
            query = target.query
        else:
            self.fail("Expected <form> or <a>")
        # autosubmit the form, no cookies to send
        req = MockRequest(path=target.abs_path, query=query)
        req.call_app(self.app)
        # should now get a very similar response to our first ever call,
        # redirect to the test page with cookies and complete as per the
        # first scenario
        self.assertTrue(req.status.startswith('303 '))
        self.assertTrue('location' in req.headers)
        target = req.headers['location']
        self.assertTrue(len(target) == 1)
        target = URI.from_octets(target[0])
        self.assertTrue(target.get_addr() == ('www.example.com', 8443))
        self.assertTrue(isinstance(target, params.HTTPSURL))
        # and we expect a warning cookie
        self.assertTrue(self.app._test_cookie in req.cookies)
        # and we expect a session cookie
        self.assertTrue(self.app._session_cookie in req.cookies)
        cflag = req.cookies[self.app._test_cookie]
        sid = req.cookies[self.app._session_cookie]
        # follow the redirect, passing the cookies
        req = MockRequest(path=target.abs_path, query=target.query)
        req.add_cookies([cflag, sid])
        req.call_app(self.app)
        # we expect a redirect back to our original path
        self.assertTrue(req.status.startswith('303 '), req.status)
        self.assertTrue('location' in req.headers)
        target = req.headers['location']
        self.assertTrue(len(target) == 1)
        target = URI.from_octets(target[0])
        self.assertTrue(target.get_addr() == ('www.example.com', 8443))
        self.assertTrue(isinstance(target, params.HTTPSURL))
        self.assertTrue(target.abs_path == '/')
        # and an updated sid!
        self.assertTrue(self.app._session_cookie in req.cookies)
        new_sid = req.cookies[self.app._session_cookie]
        self.assertFalse(sid.value == new_sid.value)
        sid = new_sid
        # now we repeat the first request with the cookies,
        # should not get a redirect anymore
        req = MockRequest()
        req.add_cookies([cflag, sid])
        req.call_app(self.app)
        self.assertTrue(req.status.startswith('200 '))
        self.assertFalse('location' in req.headers)
        # now we have an established session, what happens if we launch
        # again in a third-party blocked cookie situation?
        req = MockRequest()
        req.call_app(self.app)
        # follow the redirect, tested in the framed test
        target = URI.from_octets(req.headers['location'][0])
        # ...but ignore the cookies again!
        req = MockRequest(path=target.abs_path, query=target.query)
        req.call_app(self.app)
        # this should display the frame detection page, no cookies
        self.assertTrue(req.status.startswith('200 '))
        doc = html.XHTMLDocument()
        req.output.seek(0)
        doc.read(req.output)
        form = doc.get_element_by_id('wlaunch')
        if isinstance(form, html.Form):
            target = form.action
            # get the input fields
            query = {}
            for input in form.find_children_depth_first(html.Input):
                if input.name in ("return", "sid", "submit"):
                    query[input.name] = str(input.value)
            query = urlencode(query)
        elif isinstance(form, html.A):
            # just a link
            target = form.href
            query = target.query
        else:
            self.fail("Expected <form> or <a>")
        # autosubmit the form, but we're in a new window now so we can
        # send the cookies from the established session
        req = MockRequest(path=target.abs_path, query=query)
        req.add_cookies([cflag, sid])
        req.call_app(self.app)
        # this should redirect straight to the original home
        self.assertTrue(req.status.startswith('303 '), req.status)
        self.assertTrue('location' in req.headers)
        target = req.headers['location']
        self.assertTrue(len(target) == 1)
        target = URI.from_octets(target[0])
        self.assertTrue(target.get_addr() == ('www.example.com', 8443))
        self.assertTrue(isinstance(target, params.HTTPSURL))
        self.assertTrue(target.abs_path == '/')
        # now we repeat the first request with the cookies again, should
        # not get a redirect anymore
        req = MockRequest()
        req.add_cookies([cflag, sid])
        req.call_app(self.app)
        self.assertTrue(req.status.startswith('200 '))
        self.assertFalse('location' in req.headers)

    def test_no_cookies(self):
        req = MockRequest()
        req.call_app(self.app)
        # follow the redirect, tested in the framed test
        target = URI.from_octets(req.headers['location'][0])
        # ...but ignore the cookies
        req = MockRequest(path=target.abs_path, query=target.query)
        req.call_app(self.app)
        # this should display the frame detection page, no cookies
        self.assertTrue(req.status.startswith('200 '))
        self.assertFalse('location' in req.headers)
        self.assertTrue(len(req.cookies) == 0)
        # can we check the content?
        doc = html.XHTMLDocument()
        req.output.seek(0)
        doc.read(req.output)
        # there might be a form called 'wlaunch'
        form = doc.get_element_by_id('wlaunch')
        if isinstance(form, html.Form):
            target = form.action
            # get the input fields
            query = {}
            for input in form.find_children_depth_first(html.Input):
                if input.name in ("return", "sid", "submit"):
                    query[input.name] = str(input.value)
            query = urlencode(query)
        elif isinstance(form, html.A):
            # just a link
            target = form.href
            query = target.query
        else:
            self.fail("Expected <form> or <a>")
        # autosubmit the form, no cookies to send
        req = MockRequest(path=target.abs_path, query=query)
        req.call_app(self.app)
        # should now get a very similar response to our first ever call,
        # redirect to the test page with no cookies
        target = URI.from_octets(req.headers['location'][0])
        req = MockRequest(path=target.abs_path, query=target.query)
        req.call_app(self.app)
        # we expect content - explaining that we've failed
        self.assertTrue(req.status.startswith('200 '))
        self.assertFalse('location' in req.headers)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
