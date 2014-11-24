#! /usr/bin/env python
"""Sample LTI Application"""

# ---------------------
# Configuration Section
# ---------------------


#: the port on which we'll listen for requests
SERVICE_PORT = 8081

#: the directory containing the private data files defaults to the
#: script's directory
PRIVATE_DATA = None


#: the database module to use, defaults to sqlite. Alternatives are:
#: 'mysql'
DBAPI = None


# --------------------
# End of Configuration
# --------------------

import cgi
import django
import logging
import os
import os.path
import random
import string
import StringIO
import sys
import threading
import time
import traceback
import urllib
import urlparse

from oauth import oauth

from optparse import OptionParser
from wsgiref.simple_server import make_server
from django.conf import settings
from django.template.loader import get_template
from django.template import Template, Context

import pyslet.iso8601 as iso
import pyslet.xml20081126.structures as xml
import pyslet.odata2.csdl as edm
import pyslet.odata2.core as core
import pyslet.odata2.metadata as edmx
import pyslet.http.cookie as cookie
import pyslet.http.messages as messages
import pyslet.imsbltiv1p0 as lti

from pyslet.rfc2396 import URI

#: The name of our CSRF token
CSRF_TOKEN = "csrftoken"

#: The name of the cookie warning cookie
COOKIE_WARNING = "cookiesok"
COOKIE_SESSION = "sid"
COOKIE_WARNING_AGE = 8640000    # 100 days


class BadRequest(Exception):
    pass

class ServerError(Exception):
    pass

class SessionError(ServerError):
    pass


def generate_key(key_length=128):
    """Generates a new key

    key_length
        The minimum key length in bits.  Defaults to 128.

    The key is returned as a sequence of 16 bit hexadecimal
    strings separated by '.' to make them easier to read and
    transcribe into other systems."""
    key = []
    nfours = (key_length + 1) // 16
    try:
        rbytes = os.urandom(nfours * 2)
        for i in xrange(nfours):
            four = "%02X%02X" % (
                ord(rbytes[2 * i]), ord(rbytes[2 * i + 1]))
            key.append(four)
    except NotImplementedError:
        logging.warn("urandom required for secure key generation")
        for i in xrange(nfours):
            four = []
            for j in xrange(4):
                four.append(random.choice('0123456789ABCDEFG'))
            key.append(string.join(four, ''))
    return string.join(key, '.')


class Session(object):

    #: session expire after...
    SESSION_EXPIRY = 600
    
    def __init__(self, entity_set, environ, user_key=None):
        self.entity_set = entity_set
        self.sentity = None
        now = iso.TimePoint.FromNowUTC().WithZone(None)
        self.expires = iso.TimePoint.FromUnixTime(time.time() +
                                                  self.SESSION_EXPIRY)
        with self.entity_set.OpenCollection() as collection:
            if user_key:
                # load the session
                param = edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
                param.set_from_value(user_key)
                params = {'user_key': param}
                filter = core.CommonExpression.from_str(
                    "UserKey eq :user_key", params)
                collection.set_filter(filter)
                slist = collection.values()
                collection.set_filter(None)
                if len(slist) > 1:
                    # that's an internal error
                    raise SessionError(
                        "Duplicate user_key in Sessions: %s" % user_key)
                elif len(slist) == 1:
                    self.sentity = slist[0]
                    if (not self.sentity['Expires'] or
                            self.sentity['Expires'].value < now):
                        # session has expired, remove it
                        del collection[self.sentity.key()]
                        self.sentity = None
                    else:
                        # update the session expiry time
                        self.sentity['Expires'].set_from_value(
                            self.expires.WithZone(None))
                        collection.update_entity(self.sentity)
            if self.sentity is None:
                # generate a new user_key
                user_key = generate_key()
                server_key = generate_key()
                self.sentity = collection.new_entity()
                self.sentity['UserKey'].set_from_value(user_key)
                self.sentity['ServerKey'].set_from_value(server_key)
                self.sentity['Expires'].set_from_value(
                    self.expires.WithZone(None))
                self.sentity['Established'].set_from_value(False)
                if 'HTTP_USERAGENT' in environ:
                    user_agent = environ['HTTP_USERAGENT']
                    if len(user_agent) > 255:
                        user_agent = user_agent[0:255]
                    self.sentity['UserAgent'].set_from_value(user_agent)
                collection.insert_entity(self.sentity)
    
    def absorb(self, new_session):
        """Merge a session into this one.
        
        new_session
            A session which was started by the same browser as us (in
            a mode where cookies were clocked) but now needs to be
            merged in."""
        # just delete new_session
        new_session.delete()
                            
    def get_cookie(self):
        c = cookie.Section4Cookie(
            COOKIE_SESSION, self.sentity['UserKey'].value, http_only=True)
        return c
    
    def get_user_key(self):
        return self.sentity['UserKey'].value

    def update_user_key(self):
        with self.entity_set.OpenCollection() as collection:
            self.sentity['UserKey'].set_from_value(generate_key())
            collection.update_entity(self.sentity)

    def establish(self):
        # if this session is not yet established then establish it
        if not self.sentity['Established'].value:
            with self.entity_set.OpenCollection() as collection:
                self.sentity['Established'].set_from_value(True)
                collection.update_entity(self.sentity)

    def is_established(self):
        return self.sentity['Established'].value

    def match_environ(self, environ):
        user_agent = environ.get('HTTP_USERAGENT', None)
        if user_agent and len(user_agent) > 255:
            user_agent = user_agent[0:255]
        if self.sentity['UserAgent'].value != user_agent:
            return False
        return True

    def delete(self):
        if self.sentity.exists:
            with self.entity_set.OpenCollection() as collection:
                del collection[self.sentity.key()]

    @classmethod
    def delete_session(cls, entity_set, user_key):
        with entity_set.OpenCollection() as collection:
            param = edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
            param.set_from_value(user_key)
            params = {'user_key': param}
            filter = core.CommonExpression.from_str("UserKey eq :user_key",
                                                    params)
            collection.set_filter(filter)
            slist = collection.values()
            collection.set_filter(None)
            if len(slist):
                for sentity in slist:
                    del collection[sentity.key()]


class WSGIContext(object):
    """A class used for managing WSGI calls
    
    environ
        The WSGI environment
    
    start_response
        The WSGI call-back"""
    
    #: The maximum amount of content we'll read into memory (64K)
    MAX_CONTENT = 64*1024
    
    def __init__(self, environ, start_response):
        self.environ = environ
        self.query = None
        self.content = None
        self.form = None
        self.cookies = None
        self.session = None
        self.start_response_method = start_response
        self.status = None
        self.status_message = None
        self.headers = []
    
    def set_status(self, code):
        self.status = code
        self.status_message = messages.Response.REASON.get(code, "Unknown")    
    
    def add_header(self, name, value):
        self.headers.append((name, value))

    def start_response(self):
        if self.status is None:
            self.status = 500
            self.status_message = messages.Response.REASON.get(500,
                                                               "No status")
        return self.start_response_method(
            "%i %s" % (self.status, self.status_message), self.headers)

    def get_app_root(self):
        url = [self.environ['wsgi.url_scheme'], '://']
        if self.environ.get('HTTP_HOST'):
            url.append(self.environ['HTTP_HOST'])
        else:
            url.append(self.environ['SERVER_NAME'])
            port = self.environ['SERVER_PORT']
            if url[0] == 'https':
                if port != '443':
                    url += [':', port]
            elif port != '80':
                url += [':', port]
        url.append(urllib.quote(self.environ.get('SCRIPT_NAME', '')))
        # we always add the slash, that's our root URL
        url.append('/')
        return URI.from_octets(string.join(url, ''))
        
    def get_url(self):
        url = [self.environ['wsgi.url_scheme'], '://']
        if self.environ.get('HTTP_HOST'):
            url.append(self.environ['HTTP_HOST'])
        else:
            url.append(self.environ['SERVER_NAME'])
            port = self.environ['SERVER_PORT']
            if url[0] == 'https':
                if port != '443':
                    url += [':', port]
            elif port != '80':
                url += [':', port]
        url.append(urllib.quote(self.environ.get('SCRIPT_NAME', '')))
        url.append(urllib.quote(self.environ.get('PATH_INFO', '')))
        query = self.environ.get('QUERY_STRING', '')
        if query:
            url += ['?', query]
        return URI.from_octets(string.join(url, ''))

    def get_query(self):
        if self.query is None:
            self.query = urlparse.parse_qs(self.environ.get('QUERY_STRING', ''))
            for n, v in self.query.items():
                self.query[n] = string.join(v, ',')
        return self.query

    def get_content(self):
        if self.form is None and self.content is None:
            length = self.environ.get('CONTENT_LENGTH', '')
            if length.isdigit():
                length = int(length)
            else:
                length = 0
            if length < self.MAX_CONTENT:
                input = self.environ['wsgi.input']
                f = StringIO.StringIO()
                while length:
                    part = input.read(length)
                    if not part:
                        break
                    f.write(part)
                    length -= len(part)
                self.content = f.getvalue()
            else:
                raise BadRequest("Too much data")
        return self.content
    
    def get_form(self):
        if self.form is None and self.content is None:
            post_environ = self.environ.copy()
            post_environ['QUERY_STRING'] = ''
            self.form = cgi.FieldStorage(
                fp=post_env['wsgi.input'], environ=post_environ,
                keep_blank_values=True)
        return self.form

    def get_form_string(self, name):
        form = self.get_form()
        if name in form:
            result = form[name]
            if not name.file:
                return result.value
        return ''
            
    def get_cookies(self):
        if self.cookies is None:
            cookie_values = self.environ.get('HTTP_COOKIE', None)
            if cookie_values is not None:
                p = cookie.CookieParser(cookie_values)
                self.cookies = p.require_cookie_string()
            else:
                self.cookies = {}
        return self.cookies
    
    
def session_decorator(method):
    """Decorates a web method with session handling
    
    method is called with an active session as the first argument unless
    the session has been forced by the caller."""

    def method_call(self, context):
        return self.session_wrapper(method, context)
        
    return method_call
    

class DispatchNode(object):
    
    def __init__(self):
        self.method = None
        self.wildcard = None
        self.nodes = {}

class NoticeBoard(DispatchNode):
    """Represents our application
    
    Instances are callable to enable passing to wsgi."""
    
    #: our private data directory (applies to all instances)
    private_data_dir = None
    
    @classmethod
    def django_setup(cls, private_data_dir, debug=False):
        cls.private_data_dir = private_data_dir
        #: configure django
        settings.configure(DEBUG=debug, TEMPLATE_DEBUG=debug,
            TEMPLATE_DIRS=(
            os.path.abspath(os.path.join(private_data_dir, 'templates')), )
            )
        django.setup()
        
    def __init__(self):
        #: flag indicating that we want to stop the application
        self.stop = True
        #: the metadata document for our data layer
        self.doc = self._load_metadata(
            os.path.join(self.private_data_dir, 'nbschema.xml'))
        #: the entity container for our database
        self.container = self.doc.root.DataServices['NBSchema.NBDatabase']
        self.home_tmpl = None
        self.error_tmpl = None
        self.provider = lti.BLTIToolProvider()
        self.provider.new_consumer('12345','secret')
        DispatchNode.__init__(self)
        self.init_dispatcher()
        self.stop = False
        
    def _load_metadata(self, path):
        """Loads the metadata file from path."""
        doc = edmx.Document()
        with open(path, 'rb') as f:
            doc.Read(f)
        return doc

    def dbinit_sqlite(self, in_memory=False, sql_out=None):
        from pyslet.odata2.sqlds import SQLiteEntityContainer
        if in_memory:
            path = ":memory:"
            initdb = True
        else:
            path = os.path.join(self.private_data_dir, 'nbdatabase.db')
            initdb = not os.path.isfile(path)
        self.dbcontainer = SQLiteEntityContainer(
            file_path=path, container=self.container)
        if sql_out is not None:
            # write the sql create script to sql_out
            self.dbcontainer.create_all_tables(out=sql_out)
        elif initdb:
            self.dbcontainer.create_all_tables()

    def set_method(self, path, method):
        path = path.split('/')
        if not path:
            path = ['']
        node = self
        for p in path:
            old_node = node
            if p == '*':
                old_node.wildcard = method
                # wildcard must be the last component
                return
            else:
                node = old_node.nodes.get(p, None)
                if not node:
                    # we need a new node
                    node = DispatchNode()
                    old_node.nodes[p] = node
        node.handler = method        
                
    def init_dispatcher(self):
        self.set_method('/', self.home)
        self.set_method('/cookie_test', self.cookie_test)
        self.set_method('/wlaunch', self.wlaunch)
        self.set_method('/launch', self.lti_launch)
        
    def __call__(self, environ, start_response):
        context = WSGIContext(environ, start_response)
        try:
            path = context.environ['PATH_INFO'].split('/')
            if not path:
                # empty path
                path = ['']
            node = self
            wildcard = None
            for p in path:
                old_node = node
                node = old_node.nodes.get(p, None)
                if node:
                    if node.wildcard is not None:
                        wildcard = node.wildcard
                else:
                    break
            if node and node.handler is not None:
                return node.handler(context)
            if wildcard:
                return wildcard(context)
            # we didn't find a handler
            return self.error_response(context, 404)
        except BadRequest:
            return self.error_response(context, 400)
        except Exception as e:
            logging.exception(context.environ['PATH_INFO'])
            return self.internal_error(context, e)

    def session_wrapper(self, method, context):
        cookies = context.get_cookies()
        # load or create a session object
        sid = cookies.get(COOKIE_SESSION, '')
        context.session = Session(
            self.container['Sessions'], context.environ, sid)
        # check the CSRF token
        if context.environ['REQUEST_METHOD'].upper() == 'POST':
            token = context.get_form_string(CSRF_TOKEN)
            # we accept a token even if the session expired but this
            # form is unlikely to do much with a new session.  The point
            # is we compare to the cookie received and not the actual
            # session key as this may have changed
            if not token or token != sid:
                logging.warn("%s\nSecurity threat intercepted; "
                             "POST token mismatch, possible CSRF attack\n"
                             "session=%s; token=%s",
                             context.environ.get('PATH_INFO', ''),
                             contest.session.get_user_key(), token)
                return self.error_response(context, 403)
        # has the user been here before?
        if COOKIE_WARNING not in cookies:
            # no they haven't, set a cookie and go
            c = cookie.Section4Cookie(COOKIE_WARNING, "0", path="/",
                                      max_age=COOKIE_WARNING_AGE)
            context.add_header('Set-Cookie', str(c))
            context.add_header('Set-Cookie', str(context.session.get_cookie()))
            query = urllib.urlencode(
                {'return': str(context.get_url()),
                 'sid': context.session.get_user_key()})
            cookie_test = URI.from_octets('cookie_test?' + query).resolve(
                context.get_app_root())
            return self.redirect_response(context, cookie_test)
        context.session.establish()
        if sid != context.session.get_user_key():
            context.add_header('Set-Cookie', str(context.session.get_cookie()))
        return method(self, context)

    def cookie_test(self, context):
        app_root = context.get_app_root()
        cookies = context.get_cookies()
        logging.debug("cookies: %s", repr(cookies))
        query = context.get_query()
        logging.debug("query: %s", repr(query))
        if 'return' not in query or 'sid' not in query:
            # missing required parameters
            return self.error_response(context, 400)
        if COOKIE_WARNING not in cookies:
            # cookies are blocked
            if query.get('framed', '0') == '1':
                # we've been through the wlaunch sequence already
                # just fail
                c = Context({})
                data = get_template('nocookies.html').render(c)
                context.set_status(200)
                return self.html_response(context, data)                
            wlaunch = URI.from_octets('wlaunch').resolve(app_root)
            c = Context(
                {
                'ctest_attr': xml.EscapeCharData7(str(wlaunch), True),
                'return_attr': xml.EscapeCharData7(query['return'], True),
                'sid_attr': xml.EscapeCharData7(query['sid'], True)
                })
            data = get_template('cookie_test.html').render(c)
            context.set_status(200)
            return self.html_response(context, data)
        user_key = cookies.get(COOKIE_SESSION, 'MISSING')
        sid = query['sid']
        return_path = query['return']
        user_key = cookies.get(COOKIE_SESSION, '')
        if user_key != sid:
            # we got a cookie, but not the one we expected.  Possible
            # foul play so remove both sessions and die
            if user_key:
                Session.delete_session(self.container['Sessions'], user_key)
            if sid:
                Session.delete_session(self.container['Sessions'], sid)
            # go to an error page
            logging.warn("%s\nSecurity threat intercepted; "
                          "session mismatch, possible fixation attack\n"
                          "cookie=%s; qparam=%s",
                          context.environ.get('PATH_INFO', ''),
                          user_key, sid)
            return self.error_response(context, 400)
        if not self._check_redirect(return_path, app_root):
            return self.error_response(context, 400)
        # we have matching session ids and the redirect checks out
        context.session = Session(
            self.container['Sessions'], context.environ, user_key)
        if context.session.get_user_key() == sid:
            # but we've exposed the user_key in the URL which is bad.
            # Let's rewrite that now for safety (without changing
            # session).
            user_key = context.session.update_user_key()
            context.add_header('Set-Cookie', str(context.session.get_cookie()))
        return self.redirect_response(context, return_path)

    def wlaunch(self, context):
        app_root = context.get_app_root()
        cookies = context.get_cookies()
        logging.debug("cookies: %s", repr(cookies))
        query = context.get_query()
        if 'return' not in query or 'sid' not in query:
            # missing required parameters
            return self.error_response(context, 400)
        logging.debug("query: %s", repr(query))
        # load the session from the query initially
        sid = query['sid']
        context.session = Session(
            self.container['Sessions'], context.environ, sid)
        if (context.session.is_established() or
                not context.session.match_environ(context.environ)):
            # we're still trying to establish a session here so this
            # is a surprising result.  Perhaps an attacker has
            # injected their own established session ID here?
            Session.delete_session(self.container['Sessions'], sid)
            logging.warn("Security threat intercepted in wlaunch; "
                         "unexpected session injected in query, "
                         "possible fixation attack\n"
                         "session=%s", sid)
            return self.error_response(context, 400)
        return_path = query['return']
        if not self._check_redirect(return_path, app_root):
            return self.error_response(context, 400)
        if COOKIE_WARNING not in cookies:
            # no cookies, either the user has never been here before or
            # cookies are blocked completely, test again
            c = cookie.Section4Cookie(COOKIE_WARNING, "0", path="/",
                                      max_age=COOKIE_WARNING_AGE)
            context.add_header('Set-Cookie', str(c))
            context.add_header('Set-Cookie', str(context.session.get_cookie()))
            query = urllib.urlencode(
                {'return': return_path,
                 'sid': context.session.get_user_key(),
                 'framed': '1'})
            cookie_test = URI.from_octets('cookie_test?' + query).resolve(
                context.get_app_root())
            return self.redirect_response(context, cookie_test)
        # so cookies were blocked in the frame but now we're in a new
        # window, suddenly, they appear.  Revive any existing session in
        # favour of the session started in the fram
        user_key = cookies.get(COOKIE_SESSION, '')
        if user_key:
            csession = Session(
                self.container['Sessions'], context.environ, user_key)
            if (csession.is_established() and
                    csession.match_environ(context.environ)):
                # established, matching session.  Merge!
                csession.absorb(context.session)
                context.session = csession
        # now we have finally have a session
        if context.session.get_user_key() == sid:
            # this session id was exposed in the query, change it
            user_key = context.session.update_user_key()
            context.add_header('Set-Cookie', str(context.session.get_cookie()))
        return self.redirect_response(context, return_path)                    
            
    @session_decorator
    def home(self, context):
        if self.home_tmpl is None:
            self.home_tmpl = get_template('home.html')
        c = Context({"my_name": "Steve"})
        data = self.home_tmpl.render(c)
        context.set_status(200)
        return self.html_response(context, data)
    
    def lookup_consumer(self, key):
        return self.consumers.get(key, None)

    def lookup_nonce(self, oauth_consumer, oauth_token, nonce):
        if oauth_consumer.CheckNonce(nonce):
            return nonce
        else:
            return None

    def lti_launch(self, context):
        # we are only interested in the authorisation header
        h = context.environ.get('HTTP_AUTHORIZATION', None)
        if h:
            headers = {'Authorization': h}
        else:
            headers = None
        consumer, parameters = self.provider.launch(
            context.environ['REQUEST_METHOD'].upper(),
            str(context.get_url()), headers, context.get_content())
        logging.debug("%s\n%s", repr(consumer), repr(parameters))
        # now deal with the session creation
        cookies = context.get_cookies()
        sid = cookies.get(COOKIE_SESSION, '')
        context.session = Session(
            self.container['Sessions'], context.environ, sid)
        # has the user been here before?
        if COOKIE_WARNING not in cookies:
            # no they haven't, set a cookie and redirect
            c = cookie.Section4Cookie(COOKIE_WARNING, "0", path="/",
                                      max_age=COOKIE_WARNING_AGE)
            context.add_header('Set-Cookie', str(c))
            context.add_header('Set-Cookie', str(context.session.get_cookie()))
            query = urllib.urlencode(
                {'return': str(context.get_app_root()),
                 'sid': context.session.get_user_key()})
            cookie_test = URI.from_octets('cookie_test?' + query).resolve(
                context.get_app_root())
            return self.redirect_response(context, cookie_test)
        context.session.establish()
        if sid != context.session.get_user_key():
            context.add_header('Set-Cookie', str(context.session.get_cookie()))
        context.set_status(200)
        return self.html_response(context, 'Result')
        
    def redirect_response(self, context, location, code=303):
        c = Context({'location': xml.EscapeCharData7(str(location), True)})
        redirect_tmpl = get_template('redirect.html')
        data = redirect_tmpl.render(c)
        context.add_header("Location", str(location))
        context.add_header("Content-Type", "text/html")
        context.add_header("Content-Length", str(len(data)))
        context.set_status(code)
        context.start_response()
        return [str(data)]

    def error_response(self, context, code=500):
        """Generates an Error response"""
        if self.error_tmpl is None:
            self.error_tmpl = get_template('error.html')
        context.set_status(code)
        c = Context({"code": str(code),
                     "msg": xml.EscapeCharData7(context.status_message)})
        data = self.error_tmpl.render(c)
        return self.html_response(context, data)

    def html_response(self, context, data):
        context.add_header("Content-Type", "text/html")
        context.add_header("Content-Length", str(len(data)))
        context.start_response()
        return [str(data)]

    def internal_error(self, context, err):
        data = str(err)
        context.add_header("Content-Type", "text/plain")
        context.add_header("Content-Length", str(len(data)))
        context.set_status(500)
        context.start_response()
        return [str(data)]

    def _check_redirect(self, target_path, app_root=None):
        if target_path:
            target_path = URI.from_octets(target_path)
            if (target_path.get_canonical_root() !=
                    app_root.get_canonical_root()):
                # catch the open redirect here, nice try!
                logging.warn("%s\nSecurity threat intercepted; "
                             "external redirect, possible phishing attack\n"
                             "return=%s",
                             target_path)
                return False
            else:
                return True
        else:
            return False

def run_server(app=None):
    """Starts the web server running"""
    server = make_server('', SERVICE_PORT, app)
    logging.info("HTTP server on port %i running" % SERVICE_PORT)
    # Respond to requests until process is killed
    while not app.stop:
        server.handle_request()


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-s", "--sqlout", dest="sqlout",
                      default=None, help="Write out SQL script and quit")
    parser.add_option("-m", "--memory", dest="in_memory", action="store_true",
                      default=False, help="Use in-memory sqlite database")
    parser.add_option("-i", "--interactive", dest="interactive",
                      action="store_true", default=False,
                      help="Enable interactive prompt after starting server")
    parser.add_option("-d", "--debug", action="store_true", dest="debug",
                      default=False, help="enable django template debugging")
    parser.add_option("-v", action="count", dest="logging",
                      default=0, help="increase verbosity of output up to 3x")
    (options, args) = parser.parse_args()
    if options.logging > 3:
        level = 3
    else:
        level = options.logging
    logging.basicConfig(level=[logging.ERROR, logging.WARN, logging.INFO,
                               logging.DEBUG][level])
    if PRIVATE_DATA is None:
        private_data_dir = os.path.split(__file__)[0]
    else:
        private_data_dir = PRIVATE_DATA
    NoticeBoard.django_setup(private_data_dir=private_data_dir,
                             debug=options.debug)
    app = NoticeBoard()
    if options.in_memory:
        # override DB to select SQLite
        DBAPI = None
    if DBAPI is None:
        if options.sqlout is not None:
            # implies in_memory
            if options.sqlout == '-':
                out = StringIO.StringIO()
                app.dbinit_sqlite(in_memory=True, sql_out=out)
                print out.getvalue()
            else:
                with open(options.sqlout, 'wb') as f:
                    app.dbinit_sqlite(in_memory=True, sql_out=f)
            sys.exit(0)
        elif options.in_memory:
            app.dbinit_sqlite(in_memory=True)
        else:
            app.dbinit_sqlite(in_memory=False)
    else:
        raise ValueError("Unrecognized value for DBAPI: %s" % DBAPI)
    t = threading.Thread(
        target=run_server, kwargs={'app': app})
    t.setDaemon(True)
    t.start()
    logging.info("Starting NoticeBoard server on port %s", SERVICE_PORT)
    if options.interactive:
        # loop around getting commands
        while not app.stop:
            cmd = raw_input('cmd: ').lower()
            if cmd == 'stop':
                app.stop = True
            else:
                print "Unrecognized command: %s" % cmd
        sys.exit()
    else:
        t.join()
