#! /usr/bin/env python
import pyslet.xml20081126.structures as xml

from pyslet.wsgi import SessionApp, session_decorator


class MyApp(SessionApp):

    private_files = "samples/wsgi_session"

    def init_dispatcher(self):
        super(MyApp, self).init_dispatcher()
        self.set_method("/", self.home)
        self.set_method("/setname", self.setname)

    @session_decorator
    def home(self, context):
        page = """<html><head><title>Session Page</title></head><body>
            <h1>Session Page</h1>
            %s
            </body></html>"""
        if context.session.entity['UserName']:
            noform = """<p>Welcome: %s</p>"""
            page = page % (
                noform % xml.EscapeCharData(
                    context.session.entity['UserName'].value))
        else:
            form = """<form method="POST" action="setname">
                <p>Please enter your name: <input type="text" name="name"/>
                    <input type="hidden" name=%s value=%s />
                    <input type="submit" value="Set"/></p>
                </form>"""
            page = page % (
                form % (xml.EscapeCharData(self.csrf_token, True),
                        xml.EscapeCharData(context.session.sid(),
                                           True)))
        context.set_status(200)
        return self.html_response(context, page)

    @session_decorator
    def setname(self, context):
        user_name = context.get_form_string('name')
        if user_name:
            context.session.entity['UserName'].set_from_value(user_name)
            context.session.touch()
        return self.redirect_page(context, context.get_app_root())


if __name__ == "__main__":
    MyApp.main()
