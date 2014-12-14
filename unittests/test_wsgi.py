#! /usr/bin/env python

import cgi
import json
import logging
import optparse
import os.path
import random
import string
import StringIO
import threading
import unittest
import urllib

import pyslet.http.client as http
import pyslet.http.cookie as cookie
import pyslet.http.params as params
import pyslet.html40_19991224 as html
import pyslet.wsgi as wsgi

from pyslet.rfc2396 import URI


def suite(prefix='test'):
    loader = unittest.TestLoader()
    loader.testMethodPrefix = prefix
    return unittest.TestSuite((
        loader.loadTestsFromTestCase(FunctionTests),
        loader.loadTestsFromTestCase(ContextTests),
        loader.loadTestsFromTestCase(FullAppTests),
    ))


STATIC_FILES = os.path.join(
    os.path.join(os.path.split(__file__)[0], 'data_wsgi'), 'static')

PRIVATE_FILES = os.path.join(
    os.path.join(os.path.split(__file__)[0], 'data_wsgi'), 'data')


class MockRequest(object):

    def __init__(self, method='GET', path='/', query='', host='localhost',
                 port=80, secure=False, ip='127.0.0.1', body='',
                 body_type=None):
        self.input = StringIO.StringIO(body)
        self.output = StringIO.StringIO()
        self.errors = StringIO.StringIO()
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
        self.environ['HTTP_COOKIE'] = string.join(
            map(lambda x: "%s=%s" % (x.name, x.value), clist), "; ")

    def call_app(self, app):
        for data in app(self.environ, self.start_response):
            if isinstance(data, str):
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
        crushed_key = string.join(key.split('.'), '')
        self.assertTrue(len(crushed_key) == 32)
        for c in crushed_key:
            self.assertTrue(c in "0123456789ABCDEF")
        # obviously we shouldn't be generating the same key twice
        key2 = wsgi.generate_key()
        self.assertTrue(key2 != key)
        # and we can generate shorter keys
        key = wsgi.generate_key(32)
        self.assertTrue(len(key.split('.')) == 2)
        crushed_key = string.join(key.split('.'), '')
        self.assertTrue(len(crushed_key) == 8)
        # but we always round up to quadruplets
        key = wsgi.generate_key(33)
        self.assertTrue(len(key.split('.')) == 3, key)
        crushed_key = string.join(key.split('.'), '')
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
        for i in xrange(1000):
            # re-use the generate_key function to create random keys
            key = wsgi.generate_key()
            int_key = wsgi.key60(key)
            self.assertFalse(key in results, "generate_key is suspect")
            self.assertTrue(int_key >= 0, "negative key60")
            self.assertTrue(isinstance(int_key, long))
            results[key] = int_key
        for key, int_key in results.items():
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
        write_call("Hello")
        self.assertTrue(len(req.headers) == 1)
        self.assertTrue(req.headers['x-test'] == ['value String'])
        self.assertTrue(req.output.getvalue() == "Hello")

    def test_app_root(self):
        req = MockRequest()
        context = wsgi.WSGIContext(req.environ, req.start_response)
        root = context.get_app_root()
        self.assertTrue(isinstance(root, URI))
        self.assertTrue(str(root) == 'http://localhost/')
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
        # check that host header trumps everything
        req = MockRequest(port=8080)
        req.environ['HTTP_HOST'] = "www.example.com"
        context = wsgi.WSGIContext(req.environ, req.start_response)
        root = context.get_app_root()
        self.assertTrue(str(root) == 'http://www.example.com/')
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
        # check that host header trumps everything
        req = MockRequest(port=8080)
        req.environ['HTTP_HOST'] = "www.example.com"
        context = wsgi.WSGIContext(req.environ, req.start_response)
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
                          query="e=mc2&F=ma", body="g=9.8",
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
        self.assertTrue(isinstance(content, str))
        self.assertTrue(len(content) == 0)
        req = MockRequest(body='')
        # CONTENT_LENGTH is 0 in this case
        context = wsgi.WSGIContext(req.environ, req.start_response)
        content = context.get_content()
        self.assertTrue(isinstance(content, str))
        self.assertTrue(len(content) == 0)
        req = MockRequest(body='0123456789ABCDEF')
        # CONTENT_LENGTH is 16 in this case
        context = wsgi.WSGIContext(req.environ, req.start_response)
        content = context.get_content()
        self.assertTrue(content == "0123456789ABCDEF")
        # check that multiple calls return the same object
        content2 = context.get_content()
        self.assertTrue(content is content2)
        # check truncated read
        req = MockRequest(body='0123456789ABCDEF')
        req.environ['CONTENT_LENGTH'] = "10"
        context = wsgi.WSGIContext(req.environ, req.start_response)
        content = context.get_content()
        self.assertTrue(content == "0123456789")
        # check bad CONTENT_LENGTH, read's until EOF
        req = MockRequest(body='0123456789')
        req.environ['CONTENT_LENGTH'] = "16"
        context = wsgi.WSGIContext(req.environ, req.start_response)
        content = context.get_content()
        self.assertTrue(content == "0123456789")
        # check MAX_CONTENT, defaults to 64K
        src = StringIO.StringIO()
        b = "01"
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
        src.write('0')
        req = MockRequest(body=src.getvalue())
        context = wsgi.WSGIContext(req.environ, req.start_response)
        try:
            content = context.get_content()
        except wsgi.BadRequest:
            pass
        # check that a preceding get_form call results in None
        req = MockRequest(method="POST", body='e=mc2&F=ma',
                          body_type="application/x-www-form-urlencoded")
        context = wsgi.WSGIContext(req.environ, req.start_response)
        context.get_form()
        content = context.get_content()
        self.assertTrue(content is None)

    def test_form(self):
        req = MockRequest(method="POST", body="e=mc2&F=ma",
                          body_type="application/x-www-form-urlencoded")
        context = wsgi.WSGIContext(req.environ, req.start_response)
        form = context.get_form()
        self.assertTrue(isinstance(form, cgi.FieldStorage))
        self.assertTrue("e" in form, str(form.keys()))
        self.assertTrue("F" in form, str(form.keys()))
        self.assertTrue(form['e'].value == "mc2")
        self.assertTrue(form['F'].value == "ma")
        # check multiple values
        req = MockRequest(method="POST", body="e=mc2&e=2.718",
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
                          body="e=mc2&F=ma", query="g=9.8",
                          body_type="application/x-www-form-urlencoded")
        req.environ['HTTP_COOKIE'] = "h=6.626e-34"
        context = wsgi.WSGIContext(req.environ, req.start_response)
        form = context.get_form()
        self.assertTrue(len(form) == 2, str(form))
        self.assertFalse("g" in form)
        self.assertFalse("h" in form)
        # check that a preceding get_content call results in None
        req = MockRequest(method="POST", body='e=mc2&F=ma',
                          body_type="application/x-www-form-urlencoded")
        context = wsgi.WSGIContext(req.environ, req.start_response)
        context.get_content()
        form = context.get_form()
        self.assertTrue(form is None)

    def test_form_string(self):
        req = MockRequest(method="POST", body="e=mc2&F=ma",
                          body_type="application/x-www-form-urlencoded")
        context = wsgi.WSGIContext(req.environ, req.start_response)
        self.assertTrue(context.get_form_string("e") == "mc2")
        self.assertTrue(context.get_form_string("F") == "ma")
        # check multiple values
        req = MockRequest(method="POST", body="e=mc2&e=2.718",
                          body_type="application/x-www-form-urlencoded")
        context = wsgi.WSGIContext(req.environ, req.start_response)
        self.assertTrue(context.get_form_string("e") == "mc2,2.718")
        self.assertTrue(context.get_form_string("F") == '')

    def test_form_file(self):
        body = """
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
                        "... contents of file1.txt ...")

    def test_cookies(self):
        req = MockRequest(path="/index.html")
        req.environ['HTTP_COOKIE'] = "e=mc2; F=ma"
        context = wsgi.WSGIContext(req.environ, req.start_response)
        cookies = context.get_cookies()
        self.assertTrue(isinstance(cookies, dict))
        self.assertTrue(len(cookies) == 2)
        self.assertTrue("e" in cookies)
        self.assertTrue("F" in cookies)
        self.assertTrue(cookies['e'] == "mc2")
        self.assertTrue(cookies['F'] == "ma")
        # check multiple values
        req = MockRequest(path="/index.html")
        req.environ['HTTP_COOKIE'] = "e=mc2; e=2.718"
        context = wsgi.WSGIContext(req.environ, req.start_response)
        cookies = context.get_cookies()
        # multi-valued cookies are sorted and joined with comma
        self.assertTrue(cookies['e'] == "2.718,mc2")
        # check multiple calls return the same object
        cookies2 = context.get_cookies()
        self.assertTrue(cookies is cookies2)
        # that that form parameters and the query are ignored
        req = MockRequest(method="POST", path="/index.html",
                          query="h=6.626e-34", body="g=9.8",
                          body_type="application/x-www-form-urlencoded")
        req.environ['HTTP_COOKIE'] = "e=mc2; F=ma"
        context = wsgi.WSGIContext(req.environ, req.start_response)
        cookies = context.get_cookies()
        self.assertTrue(len(cookies) == 2, str(cookies))
        self.assertTrue(cookies == {"e": "mc2", "F": "ma"})


class AppTests(unittest.TestCase):

    def test_constructor(self):
        class BaseApp(wsgi.WSGIApp):
            pass
        self.assertTrue(BaseApp.ContextClass is wsgi.WSGIContext)
        self.assertTrue(BaseApp.static_files is not None)
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
        self.assertTrue(options.logging == 0)
        VApp.setup(options=options, args=args)
        # check setting value
        self.assertTrue(VApp.settings['WSGIApp']['level'] == logging.ERROR)

        class VApp(wsgi.WSGIApp):
            pass
        options, args = p.parse_args(['-v'])
        self.assertTrue(options.logging == 1)
        VApp.setup(options=options, args=args)
        self.assertTrue(VApp.settings['WSGIApp']['level'] == logging.WARN)

        class VApp(wsgi.WSGIApp):
            pass
        options, args = p.parse_args(['-vv'])
        self.assertTrue(options.logging == 2)
        VApp.setup(options=options, args=args)
        self.assertTrue(VApp.settings['WSGIApp']['level'] == logging.INFO)

        class VApp(wsgi.WSGIApp):
            pass
        options, args = p.parse_args(['-v', '-vv'])
        self.assertTrue(options.logging == 3)
        VApp.setup(options=options, args=args)
        self.assertTrue(VApp.settings['WSGIApp']['level'] == logging.DEBUG)

        class VApp(wsgi.WSGIApp):
            pass
        options, args = p.parse_args(['-v', '-v', '-v', '-v'])
        self.assertTrue(options.logging == 4)
        VApp.setup(options=options, args=args)
        self.assertTrue(VApp.settings['WSGIApp']['level'] == logging.DEBUG)

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
        self.assertTrue(StaticApp.static_files is not None)
        self.assertTrue(StaticApp.static_files != STATIC_FILES)
        self.assertTrue(StaticApp.static_files !=
                        os.path.abspath(STATIC_FILES))

        class StaticApp(wsgi.WSGIApp):
            pass
        options, args = p.parse_args(['--static', STATIC_FILES])
        self.assertTrue(options.static == STATIC_FILES)
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

        class PrivateApp(wsgi.WSGIApp):
            pass
        options, args = p.parse_args(['--private', PRIVATE_FILES])
        self.assertTrue(options.private == PRIVATE_FILES)
        PrivateApp.setup(options=options, args=args)
        self.assertTrue(PrivateApp.private_files ==
                        os.path.abspath(PRIVATE_FILES))

    def test_settings_option(self):
        path = os.path.join(os.path.split(__file__)[0],
                            'data_wsgi', 'settings.json')

        class SettingsApp(wsgi.WSGIApp):
            pass
        p = optparse.OptionParser()
        SettingsApp.add_options(p)
        options, args = p.parse_args([])
        self.assertTrue(options.settings is None)
        SettingsApp.setup(options=options, args=args)
        # check setting value, base setting is current directory
        self.assertTrue(SettingsApp.settings_file is not None)
        self.assertTrue(SettingsApp.settings_file != path)
        self.assertTrue(SettingsApp.settings_file != os.path.abspath(path))

        class SettingsApp(wsgi.WSGIApp):
            pass
        options, args = p.parse_args(['--settings', path])
        self.assertTrue(options.settings == path)
        SettingsApp.setup(options=options, args=args)
        self.assertTrue(SettingsApp.settings_file == os.path.abspath(path))

    def test_settings_file(self):
        path = os.path.join(os.path.split(__file__)[0],
                            'data_wsgi', 'settings.json')

        class SettingsApp(wsgi.WSGIApp):
            pass
        SettingsApp.setup()
        # in the absence of a settings file, check defaults
        self.assertTrue("WSGIApp" in SettingsApp.settings)
        self.assertTrue("level" in SettingsApp.settings['WSGIApp'])
        self.assertTrue(SettingsApp.settings['WSGIApp']['level'] is None)
        self.assertTrue(SettingsApp.settings['WSGIApp']['port'] == 8080)
        self.assertTrue(SettingsApp.settings['WSGIApp']['interactive'] is
                        False)

        class SettingsApp(wsgi.WSGIApp):
            pass
        # check that we can read different values from a settings file
        SettingsApp.settings_file = path
        SettingsApp.setup()
        self.assertTrue(SettingsApp.settings['WSGIApp']['level'] == 20)
        self.assertTrue(SettingsApp.settings['WSGIApp']['port'] == 8081)
        self.assertTrue(SettingsApp.settings['WSGIApp']['interactive'] is True)
        # now check that the command line overrides them
        path2 = os.path.join(os.path.split(__file__)[0],
                             'data_wsgi', 'settings2.json')

        class SettingsApp(wsgi.WSGIApp):
            pass
        SettingsApp.settings_file = path2
        p = optparse.OptionParser()
        SettingsApp.add_options(p)
        options, args = p.parse_args(['-v', '--port=8082', '--interactive'])
        SettingsApp.setup(options=options, args=args)
        self.assertTrue(SettingsApp.settings['WSGIApp']['level'] == 30)
        self.assertTrue(SettingsApp.settings['WSGIApp']['port'] == 8082)
        self.assertTrue(SettingsApp.settings['WSGIApp']['interactive'] is True)

    def test_set_method(self):
        class App(wsgi.WSGIApp):

            def method1(self, context):
                context.set_status(200)
                return ['test1']

            def method2(self, context):
                context.set_status(200)
                return ['test2']

            def method3(self, context):
                context.set_status(200)
                return ['test3']

            def method4(self, context):
                context.set_status(200)
                return ['test4']
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
        self.assertTrue(req.output.getvalue() == "test2")
        # matches /test/*, fallback wildcard
        req = MockRequest(path="/test/tset")
        req.call_app(app)
        self.assertTrue(req.output.getvalue() == "test2")
        # matches /test/*, fallback wildcard
        req = MockRequest(path="/test/testA")
        req.call_app(app)
        self.assertTrue(req.output.getvalue() == "test2")
        # matches /test/*, any path after wildcard
        req = MockRequest(path="/test/test/test")
        req.call_app(app)
        self.assertTrue(req.output.getvalue() == "test2")
        # not mapped
        req = MockRequest(path="/testA")
        req.call_app(app)
        self.assertTrue(req.status.startswith('404 '))
        # matches /test/test, not the wildcard
        req = MockRequest(path="/test/test")
        req.call_app(app)
        self.assertTrue(req.output.getvalue() == "test1")
        # matches /*/test
        req = MockRequest(path="/tset/test")
        req.call_app(app)
        self.assertTrue(req.output.getvalue() == "test3")

    def test_wrapper(self):
        class App(wsgi.WSGIApp):

            def page(self, context):
                context.set_status(200)
                context.add_header('Content-Length', 10)
                context.add_header('Content-Type', 'text/plain')
                context.start_response()
                return [u"0123456789"]
        # check that common errors are caught and absorbed
        App.setup()
        app = App()
        app.set_method('/*', app.page)
        req = MockRequest(path="/index.htm")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.headers['content-length'] == ['10'])
        self.assertTrue(req.output.getvalue() == "0123456789")

    def test_static(self):
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
        self.assertTrue(req.output.getvalue().startswith("Hello mum!"))
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
        class App(wsgi.WSGIApp):

            def file_page(self, context):
                context.set_status(200)
                context.add_header('Content-Type', 'text/plain')
                return self.file_response(
                    context, os.path.join(STATIC_FILES, 'res', 'public.txt'))

            def missing_page(self, context):
                context.set_status(404)
                context.add_header('Content-Type', 'text/plain')
                return self.file_response(
                    context, os.path.join(STATIC_FILES, 'res', 'public.txt'))
        App.setup()
        app = App()
        app.set_method('/*', app.file_page)
        app.set_method('/missing', app.missing_page)
        req = MockRequest(path="/index.htm")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('200 '))
        self.assertTrue(req.headers['content-length'] == ['11'])
        self.assertTrue('last-modified' in req.headers)
        self.assertTrue(req.output.getvalue() == 'Hello mum!\n')
        # check that we can still control the status
        req = MockRequest(path="/missing")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('404 '))

    def test_html_response(self):
        class App(wsgi.WSGIApp):

            def str_page(self, context):
                context.set_status(200)
                return self.html_response(context, "<title>Caf\xe9</title>")

            def unicode_page(self, context):
                context.set_status(404)
                return self.html_response(context, u"<title>Caf\xe9</title>")
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
        self.assertTrue(req.output.getvalue() == "<title>Caf\xe9</title>")
        # unicode and status override check combined
        req = MockRequest(path="/unicode.htm")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('404 '))
        print repr(req.output.getvalue())
        self.assertTrue(req.headers['content-type'] ==
                        ['text/html; charset=utf-8'])
        # check it really is UTF-8
        self.assertTrue(req.output.getvalue() ==
                        '<title>Caf\xc3\xa9</title>')

    def test_json_response(self):
        class App(wsgi.WSGIApp):

            def good_page(self, context):
                context.set_status(200)
                return self.json_response(
                    context, json.dumps(u"Caf\xe9", ensure_ascii=False))

            def bad_page(self, context):
                context.set_status(404)
                return self.json_response(
                    context, json.dumps(u"Caf\xe9", ensure_ascii=True))

            def ugly_page(self, context):
                context.set_status(500)
                return self.json_response(
                    context, json.dumps(u"Caf\xe9",
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
        self.assertTrue(output == u'"Caf\xe9"')
        req = MockRequest(path="/bad.json")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('404 '))
        self.assertTrue(req.headers['content-type'] == ['application/json'])
        self.assertTrue(req.headers['content-length'] == ['11'])
        output = req.output.getvalue().decode('utf-8')
        # unicode characters encoded in the JSON itself
        self.assertTrue(output == u'"Caf\\u00e9"')
        req = MockRequest(path="/ugly.json")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('500 '))
        self.assertTrue(req.headers['content-type'] == ['application/json'])
        self.assertTrue(req.headers['content-length'] == ['7'])
        output = req.output.getvalue().decode('utf-8')
        # unicode characters encoded before being passed
        self.assertTrue(output == u'"Caf\xe9"')

    def test_text_response(self):
        class App(wsgi.WSGIApp):

            def str_page(self, context):
                context.set_status(200)
                return self.text_response(context, "Cafe")

            def unicode_page(self, context):
                context.set_status(404)
                return self.text_response(context, u"Caf\xe9")

            def bad_page(self, context):
                context.set_status(500)
                return self.text_response(context, u"Caf\xe9".encode('utf-8'))
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
        self.assertTrue(req.output.getvalue() == "Cafe")
        # unicode and status override check combined
        req = MockRequest(path="/unicode.txt")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('404 '))
        print repr(req.output.getvalue())
        self.assertTrue(req.headers['content-type'] ==
                        ['text/plain; charset=utf-8'])
        # check it really is UTF-8
        self.assertTrue(req.output.getvalue() == 'Caf\xc3\xa9')
        # non-ASCII data in output is not checked (for speed)
        req = MockRequest(path="/bad.txt")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('500 '))
        print repr(req.output.getvalue())
        self.assertTrue(req.headers['content-type'] == ['text/plain'])
        # check it was output as unchecked UTF-8
        self.assertTrue(req.output.getvalue() == 'Caf\xc3\xa9')

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
        doc.Read(req.output)
        links = list(doc.root.FindChildrenDepthFirst(html.A))
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
                return self.error_page(context, msg=u"Gone to the Caf\xe9")

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
        self.assertTrue(req.headers['content-type'] == ['text/plain'])
        self.assertTrue(req.output.getvalue() == "Gone for good")
        # URI parameter check
        req = MockRequest(path="/error")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('500 '))
        self.assertTrue(req.headers['content-type'] ==
                        ['text/plain; charset=utf-8'])
        self.assertTrue(req.output.getvalue() == 'Gone to the Caf\xc3\xa9')
        # Check error raising
        req = MockRequest(path="/whoops")
        req.call_app(app.call_wrapper)
        self.assertTrue(req.status.startswith('500 '))
        self.assertTrue(req.headers['content-type'] == ['text/plain'])
        print repr(req.output.getvalue())
        self.assertTrue(req.output.getvalue() == '500 Internal Server Error')

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
        print repr(req.output.getvalue())
        self.assertTrue(req.output.getvalue() ==
                        '500 Internal Server Error\r\nWhoops!')

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
        t.start()
        client = http.Client()
        request = http.ClientRequest("http://localhost:%i/start" % port)
        client.process_request(request)
        self.assertTrue(request.response.status == 200)
        self.assertTrue(request.res_body == "Start")
        # stop the server
        request = http.ClientRequest("http://localhost:%i/stop" % port)
        client.process_request(request)
        # joint the run_server thread, should terminate
        t.join()


class FullApp(wsgi.DBAppMixin, wsgi.SessionApp):

    private_files = os.path.abspath(
        os.path.join(
            os.path.join(os.path.split(__file__)[0], 'data_wsgi'),
            'data'))

    def __init__(self):
        data_path = os.path.join(self.private_files, 'metadata.xml')
        wsgi.DBAppMixin.__init__(self, data_path, 'WSGISchema.WSGIDatabase')
        wsgi.SessionApp.__init__(self, self.container['Sessions'])

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
        self.app = FullApp()
        self.app.dbinit_sqlite(in_memory=True)

    def test_framed_cookies(self):
        req = MockRequest()
        req.call_app(self.app)
        # we expect a redirect
        self.assertTrue(req.status.startswith('303 '))
        self.assertTrue('location' in req.headers)
        target = req.headers['location']
        self.assertTrue(len(target) == 1)
        target = URI.from_octets(target[0])
        self.assertTrue(target.get_addr() == ('localhost', 80))
        self.assertTrue(isinstance(target, params.HTTPURL))
        # and we expect a warning cookie
        self.assertTrue(wsgi.Session.COOKIE_TEST in req.cookies)
        # and we expect a session cookie
        self.assertTrue(wsgi.Session.COOKIE_SESSION in req.cookies)
        cflag = req.cookies[wsgi.Session.COOKIE_TEST]
        sid = req.cookies[wsgi.Session.COOKIE_SESSION]
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
        self.assertTrue(target.get_addr() == ('localhost', 80))
        self.assertTrue(isinstance(target, params.HTTPURL))
        self.assertTrue(target.abs_path == '/')
        # and an updated sid!
        self.assertTrue(wsgi.Session.COOKIE_SESSION in req.cookies)
        new_sid = req.cookies[wsgi.Session.COOKIE_SESSION]
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
        doc.Read(req.output)
        # there should be a form called 'wlaunch'
        form = doc.GetElementByID('wlaunch')
        if isinstance(form, html.Form):
            self.assertTrue(form.action is not None)
            target = form.action
            self.assertTrue(target.get_addr() == ('localhost', 80))
            self.assertTrue(isinstance(target, params.HTTPURL))
            # get the input fields
            query = {}
            for input in form.FindChildrenDepthFirst(html.Input):
                if input.name in ("return", "sid", "submit"):
                    query[input.name] = str(input.value)
            query = urllib.urlencode(query)
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
        self.assertTrue(target.get_addr() == ('localhost', 80))
        self.assertTrue(isinstance(target, params.HTTPURL))
        # and we expect a warning cookie
        self.assertTrue(wsgi.Session.COOKIE_TEST in req.cookies)
        # and we expect a session cookie
        self.assertTrue(wsgi.Session.COOKIE_SESSION in req.cookies)
        cflag = req.cookies[wsgi.Session.COOKIE_TEST]
        sid = req.cookies[wsgi.Session.COOKIE_SESSION]
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
        self.assertTrue(target.get_addr() == ('localhost', 80))
        self.assertTrue(isinstance(target, params.HTTPURL))
        self.assertTrue(target.abs_path == '/')
        # and an updated sid!
        self.assertTrue(wsgi.Session.COOKIE_SESSION in req.cookies)
        new_sid = req.cookies[wsgi.Session.COOKIE_SESSION]
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
        doc.Read(req.output)
        form = doc.GetElementByID('wlaunch')
        if isinstance(form, html.Form):
            target = form.action
            # get the input fields
            query = {}
            for input in form.FindChildrenDepthFirst(html.Input):
                if input.name in ("return", "sid", "submit"):
                    query[input.name] = str(input.value)
            query = urllib.urlencode(query)
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
        self.assertTrue(target.get_addr() == ('localhost', 80))
        self.assertTrue(isinstance(target, params.HTTPURL))
        self.assertTrue(target.abs_path == '/')
        # our session should be merged in, so we have the existing sid
        # and therefore no cookie need be set
        self.assertFalse(wsgi.Session.COOKIE_SESSION in req.cookies)
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
        doc.Read(req.output)
        # there might be a form called 'wlaunch'
        form = doc.GetElementByID('wlaunch')
        if isinstance(form, html.Form):
            target = form.action
            # get the input fields
            query = {}
            for input in form.FindChildrenDepthFirst(html.Input):
                if input.name in ("return", "sid", "submit"):
                    query[input.name] = str(input.value)
            query = urllib.urlencode(query)
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
