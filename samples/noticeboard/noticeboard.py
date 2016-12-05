#! /usr/bin/env python

import logging
import os.path
import time

from optparse import OptionParser

from pyslet import imsbltiv1p0 as lti
from pyslet import wsgi
from pyslet.odata2 import core as odata
from pyslet.rfc2396 import URI
from pyslet.wsgi_jinja import JinjaApp
from pyslet.xml import structures as xml


class NoticeBoard(JinjaApp, lti.ToolProviderApp):

    def init_dispatcher(self):
        super(NoticeBoard, self).init_dispatcher()
        self.set_method('/css/*', self.static_page)
        self.set_method('/images/*', self.static_page)
        self.set_method('/resource/*/add', self.add_page)
        self.set_method('/resource/*/add_action', self.add_action)
        self.set_method('/resource/*/edit', self.edit_page)
        self.set_method('/resource/*/edit_action', self.edit_action)
        self.set_method('/resource/*/delete', self.delete_page)
        self.set_method('/resource/*/delete_action', self.delete_action)
        self.set_method('/', self.home)

    def new_context_dictionary(self, context):
        context_dict = super(NoticeBoard, self).new_context_dictionary(context)
        app_root = str(context.get_app_root())
        context_dict['css_attr'] = xml.escape_char_data7(
            app_root + 'css/base.css', True)
        context_dict['favicon_attr'] = xml.escape_char_data7(
            app_root + 'images/favicon.ico', True)
        return context_dict

    def home(self, context):
        context_dict = self.new_context_dictionary(context)
        data = self.render_template(context, 'home.html', context_dict)
        context.set_status(200)
        return self.html_response(context, data)

    @wsgi.session_decorator
    def resource_page(self, context):
        self.load_visit(context)
        context_dict = self.new_context_dictionary(context)
        if context.group is None:
            # we require a group
            data = self.render_template(context, 'notices/no_context.html',
                                        context_dict)
            context.set_status(200)
            return self.html_response(context, data)
        notices = []
        with context.group['Notices'].open() \
                as collection:
            collection.set_orderby(
                odata.Parser('Updated desc').parse_orderby_option())
            collection.set_expand({'User': None})
            for entity in collection.itervalues():
                notice = {}
                user = entity['User'].get_entity()
                can_edit = False
                can_delete = False
                logging.debug("OwnerID: %s", user['UserID'].value)
                logging.debug("UserID: %s", context.user['UserID'].value
                              if context.user else "None")
                logging.debug("Permissions: %i", context.permissions)
                if (context.user and context.user == user):
                    can_edit = True
                    can_delete = True
                elif (context.permissions & self.WRITE_PERMISSION):
                    can_delete = True
                notice['title'] = entity['Title'].value
                notice['description'] = entity['Description'].value
                notice['owner'] = self.get_user_display_name(context, user)
                notice['updated'] = int(
                    entity['Updated'].value.with_zone(0).get_unixtime() *
                    1000) - self.js_origin
                notice['can_edit'] = can_edit
                logging.debug('ID = %s', odata.FormatURILiteral(entity['ID']))
                notice['edit_link_attr'] = (
                    'edit?id=%s' % odata.FormatURILiteral(entity['ID']))
                notice['can_delete'] = can_delete
                notice['delete_link_attr'] = (
                    'delete?id=%s' % odata.FormatURILiteral(entity['ID']))
                notices.append(notice)
        context_dict['notices'] = notices
        title = "this page"
        if context.group is not None:
            title = context.group['Title'].value
        context_dict['course_name'] = title
        data = self.render_template(context, 'notices/index.html',
                                    context_dict)
        context.set_status(200)
        return self.html_response(context, data)

    @wsgi.session_decorator
    def add_page(self, context):
        self.load_visit(context)
        context_dict = self.new_context_dictionary(context)
        context_dict['title_attr'] = xml.escape_char_data7('', True)
        context_dict['description'] = ''
        context_dict[self.csrf_token] = context.session.sid
        data = self.render_template(context, 'notices/add_form.html',
                                    context_dict)
        context.set_status(200)
        return self.html_response(context, data)

    @wsgi.session_decorator
    def add_action(self, context):
        if context.environ['REQUEST_METHOD'].upper() != 'POST':
            raise wsgi.MethodNotAllowed
        self.load_visit(context)
        # we must have both a user and a group
        if context.user is None:
            raise wsgi.PageNotAuthorized
        if context.group is None:
            raise wsgi.PageNotAuthorized
        # create a new Notice entity
        with self.container['Notices'].open() \
                as collection:
            now = time.time()
            new_notice = collection.new_entity()
            new_notice['Title'].set_from_value(
                context.get_form_string('title'))
            new_notice['Description'].set_from_value(
                context.get_form_string('description'))
            new_notice['Created'].set_from_value(now)
            new_notice['Updated'].set_from_value(now)
            new_notice['User'].bind_entity(context.user)
            new_notice['Context'].bind_entity(context.group)
            collection.insert_entity(new_notice)
        link = URI.from_octets("view").resolve(context.get_url())
        return self.redirect_page(context, link, 303)

    @wsgi.session_decorator
    def edit_page(self, context):
        self.load_visit(context)
        context_dict = self.new_context_dictionary(context)
        if context.group is None:
            raise wsgi.PageNotAuthorized
        try:
            query = context.get_query()
            logging.debug("edit key=%s", query['id'])
            key = odata.uri_literal_from_str(query.get('id', '')).value
            with context.group['Notices'].open() \
                    as collection:
                collection.set_expand({'User': None})
                entity = collection[key]
                user = entity['User'].get_entity()
                if not (context.user and context.user == user):
                    # only the owner can edit their post
                    raise wsgi.PageNotAuthorized
                context_dict['id_attr'] = xml.escape_char_data7(
                    odata.FormatURILiteral(entity['ID']), True)
                context_dict['title_attr'] = xml.escape_char_data7(
                    entity['Title'].value, True)
                context_dict['description'] = entity['Description'].value
                context_dict[self.csrf_token] = context.session.sid
        except ValueError:
            raise wsgi.BadRequest
        except KeyError:
            raise wsgi.PageNotFound
        data = self.render_template(context, 'notices/edit_form.html',
                                    context_dict)
        context.set_status(200)
        return self.html_response(context, data)

    @wsgi.session_decorator
    def edit_action(self, context):
        if context.environ['REQUEST_METHOD'].upper() != 'POST':
            raise wsgi.MethodNotAllowed
        self.load_visit(context)
        # we must have both a user and a group
        if context.group is None:
            raise wsgi.PageNotAuthorized
        try:
            key = odata.uri_literal_from_str(
                context.get_form_string('id')).value
            with context.group['Notices'].open() \
                    as collection:
                collection.set_expand({'User': None})
                entity = collection[key]
                user = entity['User'].get_entity()
                if not (context.user and context.user == user):
                    # only the owner can edit their post
                    raise wsgi.PageNotAuthorized
                now = time.time()
                entity['Title'].set_from_value(
                    context.get_form_string('title'))
                entity['Description'].set_from_value(
                    context.get_form_string('description'))
                entity['Updated'].set_from_value(now)
                collection.update_entity(entity)
        except ValueError:
            raise wsgi.BadRequest
        except KeyError:
            raise wsgi.PageNotFound
        link = URI.from_octets("view").resolve(context.get_url())
        return self.redirect_page(context, link, 303)

    @wsgi.session_decorator
    def delete_page(self, context):
        self.load_visit(context)
        context_dict = self.new_context_dictionary(context)
        if context.group is None:
            raise wsgi.PageNotAuthorized
        try:
            query = context.get_query()
            key = odata.uri_literal_from_str(query.get('id', '')).value
            with context.group['Notices'].open() \
                    as collection:
                collection.set_expand({'User': None})
                entity = collection[key]
                user = entity['User'].get_entity()
                if (not (context.user and context.user == user) and
                        not (context.permissions & self.WRITE_PERMISSION)):
                    # only the owner or user with write permissions can delete
                    raise wsgi.PageNotAuthorized
                context_dict['id_attr'] = xml.escape_char_data7(
                    odata.FormatURILiteral(entity['ID']), True)
                context_dict['title'] = entity['Title'].value
                context_dict['description'] = entity['Description'].value
                context_dict[self.csrf_token] = context.session.sid
        except ValueError:
            raise wsgi.BadRequest
        except KeyError:
            raise wsgi.PageNotFound
        data = self.render_template(context, 'notices/del_form.html',
                                    context_dict)
        context.set_status(200)
        return self.html_response(context, data)

    @wsgi.session_decorator
    def delete_action(self, context):
        if context.environ['REQUEST_METHOD'].upper() != 'POST':
            raise wsgi.MethodNotAllowed
        self.load_visit(context)
        # we must have both a user and a group
        if context.group is None:
            raise wsgi.PageNotAuthorized
        try:
            key = odata.uri_literal_from_str(
                context.get_form_string('id')).value
            with context.group['Notices'].open() \
                    as collection:
                collection.set_expand({'User': None})
                entity = collection[key]
                user = entity['User'].get_entity()
                if (not (context.user and context.user == user) and
                        not (context.permissions & self.WRITE_PERMISSION)):
                    # only the owner or user with write permissions can delete
                    raise wsgi.PageNotAuthorized
                entity.delete()
        except ValueError:
            raise wsgi.BadRequest
        except KeyError:
            raise wsgi.PageNotFound
        link = URI.from_octets("view").resolve(context.get_url())
        return self.redirect_page(context, link, 303)


if __name__ == '__main__':
    parser = OptionParser()
    NoticeBoard.add_options(parser)
    (options, args) = parser.parse_args()
    NoticeBoard.settings_file = os.path.join(os.path.split(__file__)[0],
                                             'data', 'settings.json')
    NoticeBoard.setup(options, args)
    app = NoticeBoard()
    app.run_server()
