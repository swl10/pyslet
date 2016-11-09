#! /usr/bin/env python
"""Creates an OData service from the file system"""

import io
import os
import os.path
import threading
import logging
from wsgiref.simple_server import make_server

from pyslet.http import params
from pyslet.odata2 import metadata as edmx
from pyslet.odata2 import core as odata
from pyslet.odata2.server import ReadOnlyServer

#: the port on which we'll listen for requests
SERVICE_PORT = 8081

#: the service root of our OData service
SERVICE_ROOT = "http://localhost:%i/" % SERVICE_PORT

#: the base path of our exposed file system
BASE_PATH = os.path.realpath(os.path.abspath("fsodata_root"))

#: a mapping from .ext to mime type
EXTENSION_MAP = {
    '.txt': 'text/plain',
    '.html': 'text/html',
    '.xml': 'application/xml'}


def map_extension(ext):
    if ext:
        type = EXTENSION_MAP.get(ext, EXTENSION_MAP.get(ext.lower, None))
    else:
        type = None
    if type is None:
        return params.APPLICATION_OCTETSTREAM
    else:
        return params.MediaType.from_str(type)


def path_to_fspath(path):
    """Turns a key path into a file system path"""
    # special case, '/'
    if path == '/':
        return BASE_PATH
    spath = path.split('/')
    # all paths should start with a slash but no paths may end with one
    if not spath[0] and spath[-1]:
        spath = spath[1:]
        # now traverse the path carefully for security; we ban links and
        # anything that starts with a '.' or contains our system
        # specific separator
        fspath = BASE_PATH
        for name in spath:
            fspath = os.path.join(fspath, name)
            if (not name or name[0] == '.' or os.path.sep in name or
                    os.path.islink(fspath)):
                fspath = None
                break
        if fspath and os.path.normpath(fspath) == fspath:
            # os.path agrees with us
            return fspath
    raise KeyError("No such path: %s" % path)


def fspath_to_path(fspath):
    if fspath == BASE_PATH:
        return '/'
    else:
        path = []
        fspath = os.path.normpath(os.path.realpath(os.path.abspath(fspath)))
        while len(fspath) > len(BASE_PATH):
            base, name = os.path.split(fspath)
            if (not name or name[0] == '.' or '/' in name or
                    os.path.islink(fspath)):
                # if the path is a link or a . name or contains / it is
                # no good
                raise ValueError
            fspath = base
            path[0:0] = [name]
        # at this point fspath must match BASE_PATH exactly
        if fspath == BASE_PATH:
            path[0:0] = ['']
            return '/'.join(path)
    raise ValueError


def fspath_to_entity(fspath, e):
    path = fspath_to_path(fspath)
    e['path'].set_from_value(path)
    if path == '/':
        e['name'].set_from_value('/')
    else:
        e['name'].set_from_value(path.split('/')[-1])
    if os.path.isfile(fspath):
        e['isDirectory'].set_from_value(False)
        try:
            info = os.lstat(fspath)
            e['size'].set_from_value(info.st_size)
            e['lastAccess'].set_from_value(info.st_atime)
            e['lastModified'].set_from_value(info.st_mtime)
        except IOError:
            # just leave the information as NULLs
            pass
    elif os.path.isdir(fspath):
        e['isDirectory'].set_from_value(True)
    else:
        raise ValueError
    e.exists = True


class FSCollection(odata.EntityCollection):

    def itervalues(self):
        return self.order_entities(
            self.expand_entities(self.filter_entities(
                self.generate_entities())))

    def generate_entities(self):
        """List all the files in our file system

        The first item yielded is a dummy value with path /"""
        e = self.new_entity()
        e['path'].set_from_value('/')
        e['name'].set_from_value('/')
        e['isDirectory'].set_from_value(True)
        e.exists = True
        yield e
        for dirpath, dirnames, filenames in os.walk(BASE_PATH):
            for d in dirnames:
                fspath = os.path.join(dirpath, d)
                e = self.new_entity()
                try:
                    fspath_to_entity(fspath, e)
                    yield e
                except ValueError:
                    # unexpected but ignore
                    continue
            for f in filenames:
                fspath = os.path.join(dirpath, f)
                e = self.new_entity()
                try:
                    fspath_to_entity(fspath, e)
                    yield e
                except ValueError:
                    # unexpected but ignore
                    continue

    def __getitem__(self, path):
        """Get just a single file, by path"""
        try:
            fspath = path_to_fspath(path)
            e = self.new_entity()
            fspath_to_entity(fspath, e)
            if self.check_filter(e):
                if self.expand or self.select:
                    e.expand(self.expand, self.select)
                return e
            else:
                raise KeyError("Filtered path: %s" % path)
        except ValueError:
            raise KeyError("No such path: %s" % path)

    def _get_path_info(self, path):
        try:
            e = self[path]
            fspath = path_to_fspath(path)
            if os.path.isdir(fspath):
                # directories return zero-length data
                sinfo = odata.StreamInfo(type=params.PLAIN_TEXT, size=0)
            else:
                root, ext = os.path.splitext(fspath)
                type = map_extension(ext)
                modified = e['lastModified'].value
                if modified:
                    modified = modified.with_zone(0)
                sinfo = odata.StreamInfo(
                    type=type,
                    modified=modified,
                    size=e['size'].value)
            return fspath, sinfo
        except ValueError:
            raise KeyError("No such path: %s" % path)

    def _generate_file(self, fspath, close_it=False):
        try:
            with open(fspath, 'rb') as f:
                data = ''
                while True:
                    data = f.read(io.DEFAULT_BUFFER_SIZE)
                    if not data:
                        # EOF
                        break
                    else:
                        yield data
        finally:
            if close_it:
                self.close()

    def read_stream(self, path, out=None):
        fspath, sinfo = self._get_path_info(path)
        if out is not None and sinfo.size:
            for data in self._generate_file(fspath):
                out.write(data)
        return sinfo

    def read_stream_close(self, path):
        fspath, sinfo = self._get_path_info(path)
        if sinfo.size:
            return sinfo, self._generate_file(fspath, True)
        else:
            self.close()
            return sinfo, []


class FSChildren(odata.NavigationCollection):

    def itervalues(self):
        return self.order_entities(
            self.expand_entities(self.filter_entities(
                self.generate_entities())))

    def generate_entities(self):
        """List all the children of an entity"""
        path = self.from_entity['path'].value
        fspath = path_to_fspath(path)
        if os.path.isdir(fspath):
            for filename in os.listdir(fspath):
                child_fspath = os.path.join(fspath, filename)
                try:
                    e = self.new_entity()
                    fspath_to_entity(child_fspath, e)
                    yield e
                except ValueError:
                    # skip this one
                    continue

    def __getitem__(self, child_path):
        """Get just a single file, by path"""
        path = self.from_entity['path'].value
        # child_path must be child of path
        head = child_path[:len(path)]
        tail = child_path[len(path):]
        if path == '/':
            # special handling as tail will not start with /
            if head != path or not tail or '/' in tail:
                raise KeyError("not a child path: %s" % child_path)
        elif (head != path or not tail or
              tail[0] != '/' or '/' in tail[1:]):
            raise KeyError("not a child path: %s" % child_path)
        child_fspath = path_to_fspath(child_path)
        try:
            e = self.new_entity()
            fspath_to_entity(child_fspath, e)
            if self.check_filter(e):
                if self.expand or self.select:
                    e.expand(self.expand, self.select)
                return e
        except ValueError:
            raise KeyError("no such path: %s" % child_path)


class FSParent(odata.NavigationCollection):

    def itervalues(self):
        return self.order_entities(
            self.expand_entities(self.filter_entities(
                self.generate_entities())))

    def generate_entities(self):
        """List the single parent of an entity"""
        path = self.from_entity['path'].value
        if path == '/':
            # special case, no parent
            return
        parent_path = '/'.join(path.split('/')[:-1])
        if not parent_path:
            # special case!
            parent_path = '/'
        parent_fspath = path_to_fspath(parent_path)
        try:
            e = self.new_entity()
            fspath_to_entity(parent_fspath, e)
            yield e
        except ValueError:
            # really unexpected, every path should have a parent
            # except for the root
            raise ValueError("Unexpected path error: %s" % parent_path)

    def __getitem__(self, parent_path):
        """OK only if path *is* the parent of from_entity"""
        path = self.from_entity['path'].value
        if path == '/':
            raise KeyError("'/' has no parent path")
        if parent_path == '/'.join(path.split('/')[:-1]):
            parent_fspath = path_to_fspath(parent_path)
            try:
                e = self.new_entity()
                fspath_to_entity(parent_fspath, e)
                if self.check_filter(e):
                    if self.expand or self.select:
                        e.expand(self.expand, self.select)
                    return e
            except ValueError:
                raise ValueError("Unexpected path error: %s" % parent_path)
        else:
            raise KeyError("bad parent path: %s" % parent_path)


def load_metadata(
        path=os.path.join(os.path.split(__file__)[0], 'fsschema.xml')):
    """Loads the metadata file from the script directory."""
    doc = edmx.Document()
    with open(path, 'rb') as f:
        doc.read(f)
    # next step is to bind our model to it
    container = doc.root.DataServices['FSSchema.FS']
    container['Files'].bind(FSCollection)
    container['Files'].bind_navigation('Files', FSChildren)
    container['Files'].bind_navigation('Parent', FSParent)
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
