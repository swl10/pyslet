#! /usr/bin/env python

import logging
import os.path
import time


from optparse import OptionParser

import pyslet.imsbltiv1p0 as lti
import pyslet.xml20081126.structures as xml
import pyslet.odata2.core as odata
import pyslet.wsgi as wsgi

from pyslet.rfc2396 import URI
from pyslet.wsgi_django import DjangoApp


class NoticeBoard(DjangoApp, lti.ToolProviderApp):

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

    def new_page_context(self, context):
        page_context = super(NoticeBoard, self).new_page_context(context)
        app_root = str(context.get_app_root())
        page_context['css_attr'] = xml.EscapeCharData7(
            app_root + 'css/base.css', True)
        page_context['favicon_attr'] = xml.EscapeCharData7(
            app_root + 'images/favicon.ico', True)
        return page_context

    def home(self, context):
        page_context = self.new_page_context(context)
        data = self.render_template(context, 'home.html', page_context)
        context.set_status(200)
        return self.html_response(context, data)

    @wsgi.session_decorator
    def resource_page(self, context):
        self.load_visit(context)
        page_context = self.new_page_context(context)
        if context.group is None:
            # we require a group
            data = self.render_template(context, 'notices/no_context.html',
                                        page_context)
            context.set_status(200)
            return self.html_response(context, data)
        notices = []
        with context.group['Notices'].OpenCollection() \
                as collection:
            collection.set_orderby(
                odata.Parser('Updated desc').parse_orderby_option())
            collection.set_expand({'User': None})
            for entity in collection.itervalues():
                notice = {}
                user = entity['User'].GetEntity()
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
        page_context['notices'] = notices
        title = "this page"
        if context.group is not None:
            title = context.group['Title'].value
        page_context['course_name'] = title
        data = self.render_template(context, 'notices/index.html',
                                    page_context)
        context.set_status(200)
        return self.html_response(context, data)

    @wsgi.session_decorator
    def add_page(self, context):
        self.load_visit(context)
        page_context = self.new_page_context(context)
        page_context['title_attr'] = xml.EscapeCharData7('', True)
        page_context['description'] = ''
        page_context[self.csrf_token] = context.session.sid()
        data = self.render_template(context, 'notices/add_form.html',
                                    page_context)
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
        with self.container['Notices'].OpenCollection() \
                as collection:
            now = time.time()
            new_notice = collection.new_entity()
            new_notice['Title'].set_from_value(
                context.get_form_string('title'))
            new_notice['Description'].set_from_value(
                context.get_form_string('description'))
            new_notice['Created'].set_from_value(now)
            new_notice['Updated'].set_from_value(now)
            new_notice['User'].BindEntity(context.user)
            new_notice['Context'].BindEntity(context.group)
            collection.insert_entity(new_notice)
        link = URI.from_octets("view").resolve(context.get_url())
        return self.redirect_page(context, link, 303)

    @wsgi.session_decorator
    def edit_page(self, context):
        self.load_visit(context)
        page_context = self.new_page_context(context)
        if context.group is None:
            raise wsgi.PageNotAuthorized
        try:
            query = context.get_query()
            logging.debug("edit key=%s", query['id'])
            key = odata.ParseURILiteral(query.get('id', '')).value
            with context.group['Notices'].OpenCollection() \
                    as collection:
                collection.set_expand({'User': None})
                entity = collection[key]
                user = entity['User'].GetEntity()
                if not (context.user and context.user == user):
                    # only the owner can edit their post
                    raise wsgi.PageNotAuthorized
                page_context['id_attr'] = xml.EscapeCharData7(
                    odata.FormatURILiteral(entity['ID']), True)
                page_context['title_attr'] = xml.EscapeCharData7(
                    entity['Title'].value, True)
                page_context['description'] = entity['Description'].value
                page_context[self.csrf_token] = context.session.sid()
        except ValueError:
            raise wsgi.BadRequest
        except KeyError:
            raise wsgi.PageNotFound
        data = self.render_template(context, 'notices/edit_form.html',
                                    page_context)
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
            key = odata.ParseURILiteral(context.get_form_string('id')).value
            with context.group['Notices'].OpenCollection() \
                    as collection:
                collection.set_expand({'User': None})
                entity = collection[key]
                user = entity['User'].GetEntity()
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
        page_context = self.new_page_context(context)
        if context.group is None:
            raise wsgi.PageNotAuthorized
        try:
            query = context.get_query()
            key = odata.ParseURILiteral(query.get('id', '')).value
            with context.group['Notices'].OpenCollection() \
                    as collection:
                collection.set_expand({'User': None})
                entity = collection[key]
                user = entity['User'].GetEntity()
                if (not (context.user and context.user == user) and
                        not (context.permissions & self.WRITE_PERMISSION)):
                    # only the owner or user with write permissions can delete
                    raise wsgi.PageNotAuthorized
                page_context['id_attr'] = xml.EscapeCharData7(
                    odata.FormatURILiteral(entity['ID']), True)
                page_context['title'] = entity['Title'].value
                page_context['description'] = entity['Description'].value
                page_context[self.csrf_token] = context.session.sid()
        except ValueError:
            raise wsgi.BadRequest
        except KeyError:
            raise wsgi.PageNotFound
        data = self.render_template(context, 'notices/del_form.html',
                                    page_context)
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
            key = odata.ParseURILiteral(context.get_form_string('id')).value
            with context.group['Notices'].OpenCollection() \
                    as collection:
                collection.set_expand({'User': None})
                entity = collection[key]
                user = entity['User'].GetEntity()
                if (not (context.user and context.user == user) and
                        not (context.permissions & self.WRITE_PERMISSION)):
                    # only the owner or user with write permissions can delete
                    raise wsgi.PageNotAuthorized
                entity.Delete()
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
