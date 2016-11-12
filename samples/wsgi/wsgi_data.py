#! /usr/bin/env python
import time

from pyslet.odata2 import csdl as edm
from pyslet.wsgi import WSGIDataApp


class MyApp(WSGIDataApp):

    settings_file = 'samples/wsgi_data/settings.json'

    def init_dispatcher(self):
        super(MyApp, self).init_dispatcher()
        self.set_method("/*", self.home)

    def home(self, context):
        path = context.environ.get('PATH_INFO', '')
        with self.container['Hits'].open() as collection:
            ntries = 0
            while ntries < 5:
                try:
                    hit = collection[path]
                    collection.update_entity(hit)
                    break
                except KeyError:
                    try:
                        hit = collection.new_entity()
                        hit.set_key(path)
                        collection.insert_entity(hit)
                        break
                    except edm.ConstraintError:
                        # possible race condition, concurrency failure
                        time.sleep(1)
                        ntries += 1
        data = ("<html><head><title>Hit Count</title></head>"
                "<body><p>Your are hit number: %i</p></body></html>" %
                hit['Count'].value)
        context.set_status(200)
        context.add_header("Cache-Control", "no-cache")
        return self.html_response(context, data)

if __name__ == "__main__":
    MyApp.main()
