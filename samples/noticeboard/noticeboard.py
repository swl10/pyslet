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


import django
import logging
import os.path
import StringIO
import sys
import threading
import traceback

from optparse import OptionParser
from wsgiref.simple_server import make_server
from django.conf import settings
from django.template.loader import get_template
from django.template import Template, Context

import pyslet.odata2.metadata as edmx


class BadRequest(Exception):
    pass


class NoticeBoard(object):
    """Represents our application
    
    Instances are callable to enable passing to wsgi."""
    
    def __init__(self, private_data_dir, debug=False):
        #: flag indicating that we want to stop the application
        self.stop = True
        #: our private data directory
        self.private_data_dir = private_data_dir
        #: the metadata document for our data layer
        self.doc = self._load_metadata(
            os.path.join(private_data_dir, 'nbschema.xml'))
        #: the entity container for our database
        self.container = self.doc.root.DataServices['NBSchema.NBDatabase']
        #: configure django
        settings.configure(DEBUG=debug, TEMPLATE_DEBUG=debug,
            TEMPLATE_DIRS=(
            os.path.abspath(os.path.join(private_data_dir, 'templates')), )
            )
        self.home_tmpl = None
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

    def __call__(self, environ, start_response):
        try:
            path = environ['PATH_INFO']
            if path == "/":
                return self.home(environ, start_response)
            else:
                return self.error_response(
                    environ, start_response, 404, "Page Not Found")
        except BadRequest:
            return self.error_response(
                environ, start_response, 400, "Bad request")
        except Exception as e:
            einfo = sys.exc_info()
            traceback.print_exception(*einfo)
            return self.internal_error(environ, start_response, e)

    def home(self, environ, start_response):
        if self.home_tmpl is None:
            self.home_tmpl = get_template('home.html')
        c = Context({"my_name": "Steve"})
        data = self.home_tmpl.render(c)
        return self.html_response(start_response, data)
        
    def html_response(self, start_response, data, code=200, message='Success'):
        response_headers = []
        response_headers.append(("Content-Type", "text/html"))
        response_headers.append(("Content-Length", str(len(data))))
        start_response("%i %s" % (code, message), response_headers)
        return [str(data)]

    def internal_error(self, environ, start_response, err):
        data = str(err)
        response_headers = []
        response_headers.append(("Content-Type", "text/plain"))
        response_headers.append(("Content-Length", str(len(data))))
        start_response("%i %s" % (500, "Unhandled Exception"),
                       response_headers)
        return [str(data)]


def run_server(app=None):
    """Starts the web server running"""
    django.setup()
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
    app = NoticeBoard(private_data_dir=private_data_dir, debug=options.debug)
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
