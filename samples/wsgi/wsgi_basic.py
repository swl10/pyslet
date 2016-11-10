#! /usr/bin/env python
from pyslet.wsgi import WSGIApp


class MyApp(WSGIApp):

    def init_dispatcher(self):
        super(MyApp, self).init_dispatcher()
        self.set_method("/*", self.home)

    def home(self, context):
        data = "<html><head><title>Hello</title></head>" \
            "<body><p>Hello world!</p></body></html>"
        context.set_status(200)
        return self.html_response(context, data)

if __name__ == "__main__":
    MyApp.main()
