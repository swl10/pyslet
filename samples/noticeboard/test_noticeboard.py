#! /usr/bin/env python

import django
import logging
import os.path
import string
import StringIO
import unittest
import urllib

import pyslet.http.cookie as cookie
import pyslet.http.params as params
import pyslet.html40_19991224 as html

from pyslet.rfc2396 import URI

import noticeboard



def suite(prefix='test'):
    loader = unittest.TestLoader()
    loader.testMethodPrefix = prefix
    return unittest.TestSuite((
        loader.loadTestsFromTestCase(NoticeBoardTests),
    ))


class MockRequest(object):
    
    def __init__(self, method='GET', path='/', query='', host='localhost',
                 port=80, secure=False, ip='1.2.3.4', body=''):
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
        self.status = None
        self.headers = None

    def add_cookies(self, clist):
        self.environ['HTTP_COOKIE'] = string.join(
            map(lambda x: "%s=%s" % (x.name, x.value), clist), "; ")

    def call_app(self, app):
        for data in app(self.environ, self.start_response):
            self.output.write(data)

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

            
class NoticeBoardTests(unittest.TestCase):

    def setUp(self):    # noqa
        self.app = noticeboard.NoticeBoard()
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
        self.assertTrue(noticeboard.COOKIE_WARNING in req.cookies)        
        # and we expect a session cookie
        self.assertTrue(noticeboard.COOKIE_SESSION in req.cookies)
        cflag = req.cookies[noticeboard.COOKIE_WARNING]
        sid = req.cookies[noticeboard.COOKIE_SESSION]
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
        self.assertTrue(noticeboard.COOKIE_SESSION in req.cookies)
        new_sid = req.cookies[noticeboard.COOKIE_SESSION]
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
        self.assertTrue(isinstance(form, html.Form))
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
        self.assertTrue(noticeboard.COOKIE_WARNING in req.cookies)        
        # and we expect a session cookie
        self.assertTrue(noticeboard.COOKIE_SESSION in req.cookies)
        cflag = req.cookies[noticeboard.COOKIE_WARNING]
        sid = req.cookies[noticeboard.COOKIE_SESSION]
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
        self.assertTrue(noticeboard.COOKIE_SESSION in req.cookies)
        new_sid = req.cookies[noticeboard.COOKIE_SESSION]
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
        target = form.action
        query = {}
        for input in form.FindChildrenDepthFirst(html.Input):
            if input.name in ("return", "sid", "submit"):
                query[input.name] = str(input.value)
        query = urllib.urlencode(query)
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
        self.assertFalse(noticeboard.COOKIE_SESSION in req.cookies)
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
        # there should be a form called 'wlaunch'
        form = doc.GetElementByID('wlaunch')
        target = form.action
        # get the input fields
        query = {}
        for input in form.FindChildrenDepthFirst(html.Input):
            if input.name in ("return", "sid", "submit"):
                query[input.name] = str(input.value)
        query = urllib.urlencode(query)
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
    logging.basicConfig(level=logging.INFO)
    if noticeboard.PRIVATE_DATA is None:
        private_data_dir = os.path.split(__file__)[0]
    else:
        private_data_dir = noticeboard.PRIVATE_DATA
    noticeboard.NoticeBoard.django_setup(private_data_dir=private_data_dir,
                                         debug=True)
    unittest.main()
