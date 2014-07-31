#! /usr/bin/env python
"""Creates an OData service from the file system"""

import os
import os.path
import threading
import logging
from wsgiref.simple_server import make_server

import pyslet.odata2.metadata as edmx
import pyslet.odata2.core as odata
from pyslet.odata2.server import ReadOnlyServer

#: the port on which we'll listen for requests
SERVICE_PORT = 8081

#: the service root of our OData service
SERVICE_ROOT = "http://localhost:%i/" % SERVICE_PORT

#: the base path of our exposed file system
BASE_PATH = os.path.abspath(os.path.normpath("local/fsodata"))


class FSCollection(odata.EntityCollection):

    def itervalues(self):
        return self.order_entities(
            self.expand_entities(self.filter_entities(
                self.generate_entities())))

    def generate_entities(self):
        """List all the files in our file system"""
        for dirpath, dirnames, filenames in os.walk(BASE_PATH):
            for d in dirnames:
                path = os.path.join(dirpath, d)
                if path.startswith(BASE_PATH):
                    e = self.new_entity()
                    e['path'].set_from_value(path[len(BASE_PATH):])
                    e['name'].set_from_value(d)
                    e.exists = True
                    yield e
            for f in filenames:
                path = os.path.join(dirpath, f)
                if path.startswith(BASE_PATH):
                    e = self.new_entity()
                    e['path'].set_from_value(path[len(BASE_PATH):])
                    e['name'].set_from_value(f)
                    try:
                        info = os.lstat(path)
                        e['size'].set_from_value(info.st_size)
                        e['lastAccess'].set_from_value(info.st_atime)
                        e['lastModified'].set_from_value(info.st_mtime)
                    except IOError:
                        # just leave the information as NULLs
                        pass
                    yield e

    def __getitem__(self, path):
        """Get just a single file, by path"""
        if path and path[0] == os.sep:
            fspath = os.path.join(BASE_PATH, path[1:])
            base, name = os.path.split(fspath)
            if name and not os.path.islink(fspath):
                if os.path.isdir(fspath):
                    e = self.new_entity()
                    e['path'].set_from_value(path)
                    e['name'].set_from_value(name)
                    e.exists = True
                    return e
                elif os.path.isfile(fspath):
                    e = self.new_entity()
                    e['path'].set_from_value(path)
                    e['name'].set_from_value(name)
                    try:
                        info = os.lstat(fspath)
                        e['size'].set_from_value(info.st_size)
                        e['lastAccess'].set_from_value(info.st_atime)
                        e['lastModified'].set_from_value(info.st_mtime)
                    except IOError:
                        # just leave the information as NULLs
                        pass
                    e.exists = True
                    return e
        raise KeyError("No such path: %s" % path)


def load_metadata(
        path=os.path.join(os.path.split(__file__)[0], 'fsschema.xml')):
    """Loads the metadata file from the script directory."""
    doc = edmx.Document()
    with open(path, 'rb') as f:
        doc.Read(f)
    # next step is to bind our model to it
    container = doc.root.DataServices['FSSchema.FS']
    container['Files'].bind(FSCollection)
    return doc


def run_server(app=None):
    """Starts the web server running"""
    server = make_server('', SERVICE_PORT, app)
    logging.info("HTTP server on port %i running" % SERVICE_PORT)
    # Respond to requests until process is killed
    server.serve_forever()


def main():
    """Executed when we are launched"""
    doc = load_metadata()
    server = ReadOnlyServer(serviceRoot=SERVICE_ROOT)
    server.SetModel(doc)
    t = threading.Thread(
        target=run_server, kwargs={'app': server})
    t.setDaemon(True)
    t.start()
    logging.info("Starting OData server on %s" % SERVICE_ROOT)
    t.join()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
