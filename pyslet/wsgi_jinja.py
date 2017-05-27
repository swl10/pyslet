#! /usr/bin/env python

from jinja2 import Environment, FileSystemLoader

from pyslet import wsgi
from pyslet.vfs import OSFilePath
from pyslet.xml import structures as xml


class JinjaApp(wsgi.WSGIApp):

    """Extends WSGIApp to include Jinja_ template support.

    ..  _Jinja:    http://jinja.pocoo.org/

    This class is designed to enable you to write WSGI applications
    using Pyslet's framework but using Jinja's powerful `templating
    language`__.  Pyslet does not contain its own templating language!

    __  http://jinja.pocoo.org/docs/dev/

    This class is intended to be mixed into the class hierarchy using
    Python's support for multiple inheritance.  It inherits from the
    most basic WSGI class enabling you to write even the simplest
    applications using Jinja templates.  It does not require a data
    storage backend or support for sessions though you can mix this
    class with :class:`~pyslet.wsgi.WSGIDataApp` or
    :class:`~pyslet.wsgi.SessionApp` when building your own application
    if you wish.  In the latter case, you should put JinjaApp before
    SessionApp in the method resolution order if you want to enable the
    template-based versions of the :meth:`ctest_page` and
    :meth:`cfail_page` methods.

    This class has been tested with Jinja 2.8.  You can install Jinja
    just like any other python library from `PyPi`__.

    __  https://pypi.python.org/pypi/Jinja2

    The key 'JinjaApp' is reserved for settings defined by this
    class in the settings file. The defined settings are:

    template_dirs (['templates'])
        A list of URLs that point to the template directories used to
        initialise Jinja.  Relative paths are relative to the settings
        file in which the setting is defined.  For more information see
        :attr:`pyslet.wsgi.WSGIApp.settings_file`.

    One of the template directories must contain a sub-directory called
    jinjaapp containing templates for:

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
    present in the Jinja context with key 'context'.  See
    :meth:`new_context` below for details."""

    #: template_dirs paths
    template_dirs = []

    @classmethod
    def setup(cls, options=None, args=None, **kwargs):
        """Adds Jinja initialisation"""
        super(JinjaApp, cls).setup(options, args, **kwargs)
        jsettings = cls.settings.setdefault('JinjaApp', {})
        template_urls = jsettings.setdefault('template_dirs', ['templates'])
        template_paths = []
        for t in template_urls:
            template_paths.append(cls.resolve_setup_path(t))
        cls.template_dirs = [t.path for t in template_paths]

    def __init__(self, **kwargs):
        super(JinjaApp, self).__init__(**kwargs)
        #: the Jinja environment
        self.loader = FileSystemLoader(self.template_dirs)
        self.env = Environment(loader=self.loader)

    def redirect_page(self, context, location, code=303):
        """Provides a template driven redirection page

        These are rarely shown to users in modern browsers but if
        automated redirection fails for some reason then this page may
        be visible.  It is based on the template::

            jinjaapp/redirect.html

        The Jinja context contains an additional variable called
        'location_attr' which contains a *quoted and HTML-escaped*
        string suitable for replacing an attribute value, e.g.::

            <a href={{ location|safe }}>click here</a>"""
        c = self.new_context_dictionary(context)
        c['location_attr'] = xml.escape_char_data7(str(location), True)
        data = self.render_template(context, 'jinjaapp/redirect.html', c)
        context.add_header("Location", str(location))
        context.add_header("Content-Type", "text/html")
        context.add_header("Content-Length", str(len(data)))
        context.set_status(code)
        context.start_response()
        return [str(data)]

    def error_page(self, context, code=500):
        """Provides a template driven error response

        It is based on the template::

            jinjaapp/error.html

        The Django context contains two additional variables with values
        suitably escaped for placing into the *content* of an HTML
        element.  They are 'code' and 'msg' representing the HTTP error
        code and message string respectively."""
        context.set_status(code)
        c = self.new_context_dictionary(context)
        c["code"] = str(code)
        c["msg"] = xml.escape_char_data7(context.status_message)
        data = self.render_template(context, 'jinjaapp/error.html', c)
        return self.html_response(context, data)

    def ctest_page(self, context, target_url, return_url, sid):
        """Provides a template driven cookie test page

        It is based on the template::

            jinjaapp/ctest.html

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
        c = self.new_context_dictionary(context)
        c['ctest_attr'] = xml.escape_char_data7(target_url, True)
        c['return_attr'] = xml.escape_char_data7(return_url, True)
        c['sid_attr'] = xml.escape_char_data7(sid, True)
        data = self.render_template(context, 'jinjaapp/ctest.html', c)
        context.set_status(200)
        return self.html_response(context, data)

    def cfail_page(self, context):
        """Provides a template driven cookie fail page

        See :meth:`pyslet.wsgi.SessionApp.cfail_page` for details.
        There are no additional variables in the Django context."""
        c = self.new_context_dictionary(context)
        data = self.render_template(context, 'cfail.html', c)
        context.set_status(200)
        return self.html_response(context, data)

    def new_context_dictionary(self, context):
        """Creates a new Jinja context dictionary

        context:
            The :class:`~pyslet.wsgi.WSGIContext` of the request.

        The default implementation creates a new dictionary containing
        Pyslet's context object keyed on the word 'context'.

        You should override this method to provide any additional values
        required in all pages, such as a link to a CSS file or
        application 'favicon'."""
        return {'context': context}

    def render_template(self, context, path, page_context):
        """Renders a Jinja template

        context
            The :class:`~pyslet.wsgi.WSGIContext` of the request.

        path
            The relative path to the template (i.e., always forward
            slashes and relative to one of the template directories)

        context_dictionary
            The context dictionary object, e.g., returned by
            :meth:`new_context_dictionary`.

        Returns the page's data rendered with the given context
        dictionary. May return a string of bytes or a Unicode string."""
        return self.env.get_template(
            str(OSFilePath(*path.split("/")))).render(page_context)
