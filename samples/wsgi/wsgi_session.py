#! /usr/bin/env python
import pyslet.xml.structures as xml

from pyslet.wsgi import SessionApp, session_decorator


class MyApp(SessionApp):

    settings_file = 'samples/wsgi/wsgi_session/settings.json'

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
        with self.container['Sessions'].open() as collection:
            try:
                entity = collection[context.session.sid]
                user_name = entity['UserName'].value
            except KeyError:
                user_name = None
        if user_name:
            noform = """<p>Welcome: %s</p>"""
            page = page % (noform % xml.EscapeCharData(user_name))
        else:
            form = """<form method="POST" action="setname">
                <p>Please enter your name: <input type="text" name="name"/>
                    <input type="hidden" name=%s value=%s />
                    <input type="submit" value="Set"/></p>
                </form>"""
            page = page % (
                form % (xml.EscapeCharData(self.csrf_token, True),
                        xml.EscapeCharData(context.session.sid, True)))
        context.set_status(200)
        return self.html_response(context, page)

    @session_decorator
    def setname(self, context):
        user_name = context.get_form_string('name')
        if user_name:
            with self.container['Sessions'].open() as collection:
                try:
                    entity = collection[context.session.sid]
                    entity['UserName'].set_from_value(user_name)
                    collection.update_entity(entity)
                except KeyError:
                    entity = collection.new_entity()
                    entity['SessionID'].set_from_value(context.session.sid)
                    entity['UserName'].set_from_value(user_name)
                    collection.insert_entity(entity)
        return self.redirect_page(context, context.get_app_root())


if __name__ == "__main__":
    MyApp.main()
