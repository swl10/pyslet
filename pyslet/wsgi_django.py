#! /usr/bin/env python

import django
import logging

from django.conf import settings
from django.template.loader import get_template
from django.template import Context

import pyslet.xml.structures as xml
import pyslet.wsgi as wsgi


class DjangoApp(wsgi.WSGIApp):

    """Extends WSGIApp to include Django_ template support.

    ..  _Django:    https://www.djangoproject.com/

    This class is designed to enable you to write WSGI applications
    using Pyslet's framework but using Django's powerful `templating
    language`__.  Pyslet does not contain its own templating language!

    __  https://docs.djangoproject.com/en/1.7/topics/templates/

    This class is intended to be mixed into the class hierarchy using
    Python's support for multiple inheritance.  It inherits from the
    most basic WSGI class enabling you to write even the simplest
    applications using Django templates.  It does not require a data
    storage backend or support for sessions though you can mix this
    class with :class:`~pyslet.wsgi.WSGIDataApp` or
    :class:`~pyslet.wsgi.SessionApp` when building your own application
    if you wish.  In the latter case, you should put DjangoApp before
    SessionApp in the method resolution order if you want to enable the
    template-based versions of the :meth:`ctest_page` and
    :meth:`cfail_page` methods.

    This class does not make your application a Django application, it
    simply requires the django module to be installed so that the
    templating language can be used by Pyslet's framework.

    You can understand more about using Django's template language
    from the `The Django template language: For Python programmers`__.

    __  https://docs.djangoproject.com/en/1.7/ref/templates/api/

    This class has been tested with Django 1.7.  You can install Django
    just like any other python library from `PyPi`__.

    __  https://pypi.python.org/pypi/Django

    The key 'DjangoApp' is reserved for settings defined by this
    class in the settings file. The defined settings are:

    template_dirs (['templates'])
        A list of URLs that point to the template directories used to
        initialise Django.  Relative paths are relative to the settings
        file in which the setting is defined.  For more information see
        :attr:`pyslet.wsgi.WSGIApp.settings_file`.

    One of the template directories must contain a sub-directory called
    djangoapp containing templates for:

    redirect.html
        See :meth:`redirect_page`

    error.html
        See :meth:`error_page`

    If you are also overriding SessionApp you may, in addition, provide
    templates in the same directory for:

    ctest.html
        See :meth:`ctest_page`

    cfail.html
        See :meth:`cfail_page`

    In all of the above cases, the :class:`pyslet.wsgi.WSGIContext` is
    present in the Django context with key 'context'.  See
    :meth:`new_context` below for details."""

    #: the debug option value
    debug = False

    #: flag to indicate that the Django settings have been configured
    configured = False

    #: template_dirs paths
    template_dirs = []

    @classmethod
    def add_options(cls, parser):
        """Defines command line options.

        parser
            An OptionParser instance, as defined by Python's built-in
            optparse module.

        The following options are added to *parser* by this
        implementation:

        -d, --debug     Enables template debugging.  It defaults to False
                        and should not be used in production.  See also
                        :attr:`debug`."""
        super(DjangoApp, cls).add_options(parser)
        parser.add_option(
            "-d", "--debug", action="store_true", dest="debug",
            default=False, help="enable django template debugging")

    @classmethod
    def setup(cls, options=None, args=None, **kwargs):
        """Adds Django initialisation

        .. warning::

            The Django system can only be initialised once, so you can
            only ever setup one class that uses DjangoApp as a base.  In
            practice, subsequent calls to setup will simply ignore the
            Django configuration step, ignoring any debug setting and
            template directory locations.

            This restriction may be removed in future versions as this
            area of Django appears to be evolving."""
        super(DjangoApp, cls).setup(options, args, **kwargs)
        if options:
            cls.debug = options.debug
        dsettings = cls.settings.setdefault('DjangoApp', {})
        template_urls = dsettings.setdefault('template_dirs', ['templates'])
        template_paths = []
        for t in template_urls:
            template_paths.append(cls.resolve_setup_path(t))
        if not DjangoApp.configured:
            settings.configure(
                DEBUG=cls.debug, TEMPLATE_DEBUG=cls.debug,
                TEMPLATE_DIRS=template_paths)
            django.setup()
            DjangoApp.configured = True
        else:
            logging.warning("DjangoApp: setup ignored for %s" % cls.__name__)
            cls.template_dirs = [t.path for t in template_paths]

    def redirect_page(self, context, location, code=303):
        """Provides a template driven redirection page

        These are rarely shown to users in modern browsers but if
        automated redirection fails for some reason then this page may
        be visible.  It is based on the template::

            djangoapp/redirect.html

        The Django context contains an additional variable called
        'location_attr' which contains a *quoted and HTML-escaped*
        string suitable for replacing an attribute value, e.g.::

            <a href={{ location|safe }}>click here</a>"""
        c = self.new_page_context(context)
        c['location_attr'] = xml.escape_char_data7(str(location), True)
        data = self.render_template(context, 'djangoapp/redirect.html', c)
        context.add_header("Location", str(location))
        context.add_header("Content-Type", "text/html")
        context.add_header("Content-Length", str(len(data)))
        context.set_status(code)
        context.start_response()
        return [str(data)]

    def error_page(self, context, code=500):
        """Provides a template driven error response

        It is based on the template::

            djangoapp/error.html

        The Django context contains two additional variables with values
        suitably escaped for placing into the *content* of an HTML
        element.  They are 'code' and 'msg' representing the HTTP error
        code and message string respectively."""
        context.set_status(code)
        c = self.new_page_context(context)
        c["code"] = str(code)
        c["msg"] = xml.escape_char_data7(context.status_message)
        data = self.render_template(context, 'djangoapp/error.html', c)
        return self.html_response(context, data)

    def ctest_page(self, context, target_url, return_url, sid):
        """Provides a template driven cookie test page

        It is based on the template::

            djangoapp/ctest.html

        Shown after blocked cookies are detected.  See
        :meth:`pyslet.wsgi.SessionApp.ctest_page` for details.  The
        Django context contains three additional variables with values
        'ctest_attr', 'return_attr' and 'sid_attr', all *quoted and
        HTML-escaped* ready to be used as attribute values.

        The ctest_attr variable contains the URL that can be used as a
        form target suitable for opening in a new browser window.  The
        other two values are the originally requested URL and the
        session id respectively and must be submitted as hidden values
        on the form."""
        c = self.new_page_context(context)
        c['ctest_attr'] = xml.escape_char_data7(target_url, True)
        c['return_attr'] = xml.escape_char_data7(return_url, True)
        c['sid_attr'] = xml.escape_char_data7(sid, True)
        data = self.render_template(context, 'djangoapp/ctest.html', c)
        context.set_status(200)
        return self.html_response(context, data)

    def cfail_page(self, context):
        """Provides a template driven cookie fail page

        See :meth:`pyslet.wsgi.SessionApp.cfail_page` for details.
        There are no additional variables in the Django context."""
        c = self.new_page_context(context)
        data = self.render_template(context, 'cfail.html', c)
        context.set_status(200)
        return self.html_response(context, data)

    def new_page_context(self, context):
        """Creates a new Django page context

        context:
            The :class:`~pyslet.wsgi.WSGIContext` of the request.

        The default implementation adds Pyslet's context object to the
        Django page context with key 'context'.

        You should override this method to provide any additional values
        required in all pages, such as a link to a CSS file or
        application 'favicon'."""
        return Context({'context': context})

    def render_template(self, context, path, page_context):
        """Renders a Django template

        context
            The :class:`~pyslet.wsgi.WSGIContext` of the request.

        path
            The Django-style path to the template (i.e., always
            forward slashes and relative to one of the template
            directories)

        page_context
            The Django context object, e.g., returned by
            :meth:`new_page_context`.

        Returns the page data rendered in the given Django page context.
         May be a string of bytes or a Unicode string."""
        return get_template(path).render(page_context)
