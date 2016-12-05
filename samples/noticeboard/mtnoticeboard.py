#! /usr/bin/env python

import json
import logging
import os.path
import string
import sys
import urllib

from oauthlib import oauth2

from optparse import OptionParser

from pyslet import imsbltiv1p0 as lti
from pyslet import wsgi
from pyslet.http import client as http
from pyslet.odata2 import core as odata
from pyslet.odata2 import csdl as edm
from pyslet.py2 import long2
from pyslet.rfc2396 import URI
from pyslet.xml import structures as xml


from noticeboard import NoticeBoard


class MultiTenantSession(wsgi.CookieSession):

    def __init__(self, src=None):
        super(MultiTenantSession, self).__init__(src)
        if src:
            fields = src.split('-')
            if len(fields) >= 4:
                if fields[3]:
                    self.owner = long2(fields[3])
                else:
                    self.owner = None
            else:
                raise ValueError("Bad Session: %s" % src)
        else:
            self.owner = None

    def __unicode__(self):
        return "%s-%s" % (
            super(MultiTenantSession, self).__unicode__(),
            "" if self.owner is None else str(self.owner))

    def get_owner_id(self):
        """Returns the ID of the owner of the session

        The owner is the person logged in to the root of the
        application.  It may be None.  This should not be confused with
        a user associated with the session via an LTI launch.

        If there is no owner, None is returned."""
        return self.owner

    def set_owner_id(self, owner_id):
        """Sets the ID of the owner of the session"""
        self.owner = owner_id

    def del_owner_id(self):
        """Removes the link between the session and the current owner

        Called when the person logged in to the root of the application
        logs outs.  Future calls to :meth:`get_owner_id` will return
        None.

        You MUST call
        :meth:`~pyslet.wsgi.WSGISessionApp.set_session_cookie` after
        modifying the session to ensure the owner is removed from the
        browser cookie."""
        self.owner = None


class MultiTenantTPApp(lti.ToolProviderApp):

    #: We have our own NoticeBoard-specific Session class
    SessionClass = MultiTenantSession

    #: The path to the certificate files
    cert_file = None

    @classmethod
    def add_options(cls, parser):
        """Adds the following options:

        --google_certs       refresh the google certificates"""
        super(MultiTenantTPApp, cls).add_options(parser)
        parser.add_option(
            "--google_certs", dest="google_certs", action="store_true",
            default=False, help="Download Google API certificates and exit")

    @classmethod
    def setup(cls, options=None, args=None, **kwargs):
        """Adds multi-tenant initialisation"""
        super(MultiTenantTPApp, cls).setup(options, args, **kwargs)
        mt_settings = cls.settings.setdefault('MultiTenantTPApp', {})
        mt_settings.setdefault('google_client_id', '')
        mt_settings.setdefault('google_client_secret', '')
        cert_url = mt_settings.setdefault('google_certs', 'google_certs.pem')
        cls.cert_file = cls.resolve_setup_path(cert_url)
        if options and options.google_certs:
            # update the certs_file and exit
            c = http.Client()
            certs = []
            for s in ('https://accounts.google.com',
                      'https://www.googleapis.com', ):
                url = URI.from_octets(s)
                certs.append(c.get_server_certificate_chain(url))
            with open(cls.cert_file, 'wb') as f:
                f.write(string.join(certs, ''))
            sys.exit(0)

    def __init__(self):
        super(MultiTenantTPApp, self).__init__()
        mt_settings = self.settings['MultiTenantTPApp']
        self.google_id = mt_settings['google_client_id']
        self.google_secret = mt_settings['google_client_secret']
        # TODO: add configuration of certificates!
        self.http = http.Client(ca_certs=self.cert_file)

    def init_dispatcher(self):
        super(MultiTenantTPApp, self).init_dispatcher()
        self.set_method('/gclient_action', self.gclient_action)
        self.set_method('/logout', self.logout)
        self.set_method('/consumers/', self.consumers_page)
        self.set_method('/consumers/add_action', self.consumer_add_action)
        self.set_method('/consumers/edit', self.consumer_edit_page)
        self.set_method('/consumers/edit_action', self.consumer_edit_action)
        self.set_method('/consumers/del', self.consumer_del_page)
        self.set_method('/consumers/del_action', self.consumer_del_action)

    def get_owner(self, context):
        current_owner = context.session.get_owner_id()
        if current_owner is not None:
            with self.container['Owners'].open() as collection:
                try:
                    current_owner = collection[current_owner]
                except KeyError:
                    context.session.del_owner_id()
                    self.set_session_cookie(context)
                    current_owner = None
        return current_owner

    def set_owner(self, context, owner):
        context.session.set_owner_id(owner['Key'].value)
        self.set_session_cookie(context)

    def del_owner(self, context):
        context.session.del_owner_id()
        self.set_session_cookie(context)

    @wsgi.session_decorator
    def home(self, context):
        page_context = self.new_context_dictionary(context)
        current_owner = self.get_owner(context)
        page_context['logout'] = False
        if current_owner:
            page_context['got_user'] = True
            page_context['user_name'] = current_owner['FullName'].value
        else:
            page_context['got_user'] = False
            if self.google_id:
                page_context['google_sso'] = True
                page_context['gclient_id_attr'] = xml.escape_char_data7(
                    self.google_id, True)
                page_context[self.csrf_token] = context.session.sid
            else:
                page_context['google_sso'] = False
        data = self.render_template(context, 'mthome.html', page_context)
        context.set_status(200)
        return self.html_response(context, data)

    @wsgi.session_decorator
    def gclient_action(self, context):
        """Handles Google+ sign-in postmessage callback

        Exchange the one-time authorization code for a token and store
        the token in the session."""
        if context.environ['REQUEST_METHOD'].upper() != 'POST':
            raise wsgi.MethodNotAllowed
        if not self.google_id:
            raise wsgi.BadRequest
        # the wsgi.session_decorator took care of checking the CSRF
        # token already
        code = context.get_form_string('code')
        if code == 'logout':
            # this is the logout action
            context.session.del_owner(context)
            context.set_status(200)
            return self.json_response(
                context, json.dumps("session owner logged out"))
        # swap this code for an OAuth 2 access token
        gclient = oauth2.WebApplicationClient(client_id=self.google_id)
        body = gclient.prepare_request_body(
            code=code, client_secret=self.google_secret,
            redirect_uri='postmessage')
        req = http.ClientRequest("https://accounts.google.com/o/oauth2/token",
                                 method="POST", entity_body=str(body))
        req.set_accept("application/json")
        req.set_content_type('application/x-www-form-urlencoded;charset=UTF-8')
        self.http.process_request(req)
        if req.status != 200:
            logging.warn("OAuth request returned status: %i", req.status)
            raise wsgi.BadRequest
        gclient.parse_request_body_response(req.res_body)
        url, headers, data = gclient.add_token(
            'https://www.googleapis.com/oauth2/v1/userinfo', http_method="GET")
        req = http.ClientRequest(url)
        req.set_accept("application/json")
        req.set_content_type('application/x-www-form-urlencoded;charset=UTF-8')
        for h, v in headers.items():
            req.set_header(h, v)
        self.http.process_request(req)
        if req.status != 200:
            logging.warn("OAuth request returned status: %i", req.status)
            raise wsgi.BadRequest
        userinfo = json.loads(req.res_body.decode('utf-8'))
        current_owner = self.get_owner(context)
        if current_owner:
            if (current_owner['IDType'].value == 'google' and
                    current_owner['ID'].value == userinfo['id']):
                # we're already logged in to this session
                logging.warn("google user already logged in")
                context.set_status(200)
                return self.json_response(
                    context, json.dumps("Already logged in"))
            # clear this link
            self.del_owner(context)
        logging.debug("Google user logged in: %s <%s>", userinfo['name'],
                      userinfo['email'])
        with self.container['Owners'].open() as collection:
            # let's find this user in our database
            id = edm.EDMValue.from_type(edm.SimpleType.String)
            id.set_from_value(userinfo['id'])
            filter = odata.CommonExpression.from_str(
                "IDType eq 'google' and ID eq :id", {'id': id})
            collection.set_filter(filter)
            owners = collection.values()
            if len(owners) == 0:
                # first time we ever saw this person, create an entry
                owner = collection.new_entity()
                owner['Key'].set_from_value(
                    wsgi.key60('gmail:' + userinfo['id']))
                owner['IDType'].set_from_value('google')
                owner['ID'].set_from_value(userinfo['id'])
                owner['GivenName'].set_from_value(userinfo['given_name'])
                owner['FamilyName'].set_from_value(userinfo['family_name'])
                owner['FullName'].set_from_value(userinfo['name'])
                owner['Email'].set_from_value(userinfo['email'])
                # and create them a silo for their data
                with owner['Silo'].target().open() as silos:
                    silo = silos.new_entity()
                    silo['ID'].set_from_value(owner['Key'].value)
                    silo['Slug'].set_from_value(userinfo['email'])
                    silos.insert_entity(silo)
                owner['Silo'].bind_entity(silo)
                collection.insert_entity(owner)
                # and finally create a default consumer for them
                with silo['Consumers'].open() as collection:
                    consumer = lti.ToolConsumer.new_from_values(
                        collection.new_entity(), self.app_cipher, "default")
                    collection.insert_entity(consumer.entity)
                self.set_owner(context, owner)
            elif len(owners) == 1:
                # we already saw this user
                owner = owners[0]
                # update the record from the latest userinfo
                owner['GivenName'].set_from_value(userinfo['given_name'])
                owner['FamilyName'].set_from_value(userinfo['family_name'])
                owner['FullName'].set_from_value(userinfo['name'])
                owner['Email'].set_from_value(userinfo['email'])
                collection.update_entity(owner)
                self.set_owner(context, owner)
            else:
                logging.error("Duplicate google owner: %s <%s>",
                              id.value, userinfo['email'])
                self.del_owner(context)
                raise RuntimeError("Unexpected duplicate in Owners")
        context.set_status(200)
        return self.json_response(
            context, json.dumps("%s now logged in" % userinfo['name']))

    @wsgi.session_decorator
    def logout(self, context):
        page_context = self.new_context_dictionary(context)
        page_context['logout'] = True
        page_context['got_user'] = False
        if self.google_id:
            page_context['google_sso'] = True
            page_context['gclient_id_attr'] = xml.escape_char_data7(
                self.google_id, True)
        else:
            page_context['google_sso'] = False
        page_context[self.csrf_token] = context.session.sid
        data = self.render_template(context, 'mthome.html', page_context)
        context.set_status(200)
        return self.html_response(context, data)

    @wsgi.session_decorator
    def consumers_page(self, context):
        page_context = self.new_context_dictionary(context)
        # add errors
        errors = set(('duplicate_key', ))
        query = context.get_query()
        error = query.get('error', '')
        for e in errors:
            page_context[e] = (e == error)
        owner = self.get_owner(context)
        if owner is None:
            # we require an owner to be logged in
            raise wsgi.PageNotAuthorized
        page_context['user_name'] = owner['FullName'].value
        silo = owner['Silo'].get_entity()
        page_context['silo'] = silo
        consumer_list = []
        with silo['Consumers'].open() as collection:
            collection.set_orderby(
                odata.Parser('Handle asc').parse_orderby_option())
            for consumer in collection.itervalues():
                citem = {}
                consumer = lti.ToolConsumer(consumer, self.app_cipher)
                query = urllib.urlencode(
                    {'cid':
                     odata.ODataURI.format_literal(consumer.entity['ID'])})
                citem['consumer'] = consumer
                citem['cedit_link'] = xml.escape_char_data7(
                    'edit?' + query, True)
                citem['cdel_link'] = xml.escape_char_data7(
                    'del?' + query, True)
                consumer_list.append(citem)
            query = urllib.urlencode(
                {'silo': odata.ODataURI.format_literal(silo['ID'])})
            page_context['cadd_link'] = xml.escape_char_data7(
                'add?' + query, True)
        page_context['consumers'] = consumer_list
        page_context[self.csrf_token] = context.session.sid
        data = self.render_template(context, 'consumers/index.html',
                                    page_context)
        context.set_status(200)
        return self.html_response(context, data)

    @wsgi.session_decorator
    def consumer_add_action(self, context):
        if context.environ['REQUEST_METHOD'].upper() != 'POST':
            raise wsgi.MethodNotAllowed
        owner = self.get_owner(context)
        if owner is None:
            # we require an owner to be logged in
            raise wsgi.PageNotAuthorized
        silo = owner['Silo'].get_entity()
        try:
            handle = context.get_form_string('handle', 80)
            key = context.get_form_string('key', 80)
            secret = context.get_form_string('secret', 80)
            with silo['Consumers'].open() as collection:
                consumer = lti.ToolConsumer.new_from_values(
                    collection.new_entity(), self.app_cipher, handle, key=key,
                    secret=secret)
                collection.insert_entity(consumer.entity)
        except edm.ConstraintError:
            # ID/Key clash most likely, offer a message and a back page
            link = URI.from_octets(
                "./?error=duplicate_key").resolve(context.get_url())
            return self.redirect_page(context, link, 303)
        except ValueError:
            raise wsgi.BadRequest
        except KeyError:
            raise wsgi.PageNotAuthorized
        link = URI.from_octets("./").resolve(context.get_url())
        return self.redirect_page(context, link, 303)

    @wsgi.session_decorator
    def consumer_edit_page(self, context):
        page_context = self.new_context_dictionary(context)
        owner = self.get_owner(context)
        if owner is None:
            # we require an owner to be logged in
            raise wsgi.PageNotAuthorized
        page_context['owner'] = owner
        silo = owner['Silo'].get_entity()
        page_context['silo'] = silo
        query = context.get_query()
        cid = odata.uri_literal_from_str(query.get('cid', '')).value
        with silo['Consumers'].open() as collection:
            try:
                consumer = lti.ToolConsumer(collection[cid], self.app_cipher)
            except KeyError:
                raise wsgi.PageNotAuthorized
        page_context['consumer'] = consumer
        page_context['cid_attr'] = xml.escape_char_data7(str(cid), True)
        page_context[self.csrf_token] = context.session.sid
        data = self.render_template(context, 'consumers/edit_form.html',
                                    page_context)
        context.set_status(200)
        return self.html_response(context, data)

    @wsgi.session_decorator
    def consumer_edit_action(self, context):
        if context.environ['REQUEST_METHOD'].upper() != 'POST':
            raise wsgi.MethodNotAllowed
        owner = self.get_owner(context)
        if owner is None:
            # we require an owner to be logged in
            raise wsgi.PageNotAuthorized
        silo = owner['Silo'].get_entity()
        try:
            cid = context.get_form_long('cid')
            key = context.get_form_string('key', 80)
            secret = context.get_form_string('secret', 80)
            with silo['Consumers'].open() as collection:
                consumer = lti.ToolConsumer(collection[cid], self.app_cipher)
                # we never change the handle
                consumer.update_from_values(key, secret)
        except ValueError:
            raise wsgi.BadRequest
        except KeyError:
            raise wsgi.PageNotAuthorized
        link = URI.from_octets("./").resolve(context.get_url())
        return self.redirect_page(context, link, 303)

    @wsgi.session_decorator
    def consumer_del_page(self, context):
        page_context = self.new_context_dictionary(context)
        owner = self.get_owner(context)
        if owner is None:
            # we require an owner to be logged in
            raise wsgi.PageNotAuthorized
        page_context['owner'] = owner
        silo = owner['Silo'].get_entity()
        page_context['silo'] = silo
        query = context.get_query()
        cid = odata.uri_literal_from_str(query.get('cid', '')).value
        with silo['Consumers'].open() as collection:
            try:
                consumer = collection[cid]
            except KeyError:
                raise wsgi.PageNotAuthorized
        page_context['consumer'] = consumer
        page_context[self.csrf_token] = context.session.sid
        data = self.render_template(context, 'consumers/del_form.html',
                                    page_context)
        context.set_status(200)
        return self.html_response(context, data)

    @wsgi.session_decorator
    def consumer_del_action(self, context):
        if context.environ['REQUEST_METHOD'].upper() != 'POST':
            raise wsgi.MethodNotAllowed
        owner = self.get_owner(context)
        if owner is None:
            # we require an owner to be logged in
            raise wsgi.PageNotAuthorized
        silo = owner['Silo'].get_entity()
        try:
            cid = context.get_form_long('cid')
            with silo['Consumers'].open() as collection:
                consumer = collection[cid]
                # now to delete we must delete from the parent collection
                consumer.delete()
        except ValueError:
            raise wsgi.BadRequest
        except KeyError:
            raise wsgi.PageNotAuthorized
        link = URI.from_octets("./").resolve(context.get_url())
        return self.redirect_page(context, link, 303)


class MTNoticeBoard(MultiTenantTPApp, NoticeBoard):
    pass


if __name__ == '__main__':
    parser = OptionParser()
    MTNoticeBoard.add_options(parser)
    (options, args) = parser.parse_args()
    MTNoticeBoard.settings_file = os.path.join(os.path.split(__file__)[0],
                                               'data', 'settings.json')
    MTNoticeBoard.setup(options, args)
    app = MTNoticeBoard()
    app.run_server()
