#! /usr/bin/env python
"""Creates an OData in-memory cache of key value pairs"""

import logging
import threading
import time

from wsgiref.simple_server import make_server

from pyslet import iso8601 as iso
from pyslet.odata2 import metadata as edmx
from pyslet.odata2 import core as core
from pyslet.odata2 import csdl as edm
from pyslet.odata2.memds import InMemoryEntityContainer
from pyslet.odata2.server import Server
from pyslet.py2 import character, output, range3


SERVICE_PORT = 8080
SERVICE_ROOT = "http://localhost:%i/" % SERVICE_PORT
CLEANUP_SLEEP = 10


cache_app = None       #: our Server instance


def load_metadata():
    """Loads the metadata file from the current directory."""
    doc = edmx.Document()
    with open('MemCacheSchema.xml', 'rb') as f:
        doc.read(f)
    return doc


def test_data(mem_cache):
    with mem_cache.open() as collection:
        for i in range3(26):
            e = collection.new_entity()
            e.set_key(str(i))
            e['Value'].set_from_value(character(0x41 + i))
            e['Expires'].set_from_value(
                iso.TimePoint.from_unix_time(time.time() + 10 * i))
            collection.insert_entity(e)


def test_model():
    """Read and write some key value pairs"""
    doc = load_metadata()
    InMemoryEntityContainer(doc.root.DataServices['MemCacheSchema.MemCache'])
    mem_cache = doc.root.DataServices['MemCacheSchema.MemCache.KeyValuePairs']
    test_data(mem_cache)
    with mem_cache.open() as collection:
        for e in collection.itervalues():
            output("%s: %s (expires %s)\n" %
                   (e['Key'].value, e['Value'].value, str(e['Expires'].value)))


def run_cache_server():
    """Starts the web server running"""
    server = make_server('', SERVICE_PORT, cache_app)
    logging.info("Starting HTTP server on port %i..." % SERVICE_PORT)
    # Respond to requests until process is killed
    server.serve_forever()


def cleanup_forever(mem_cache):
    """Runs a loop continuously cleaning up expired items"""
    now = edm.DateTimeValue()
    expires = core.PropertyExpression("Expires")
    t = core.LiteralExpression(now)
    filter = core.BinaryExpression(core.Operator.lt)
    filter.operands.append(expires)
    filter.operands.append(t)
    while True:
        now.set_from_value(iso.TimePoint.from_now_utc())
        logging.info("Cleanup thread running at %s", str(now.value))
        with mem_cache.open() as cacheEntries:
            cacheEntries.set_filter(filter)
            expired_list = list(cacheEntries)
            if expired_list:
                logging.info("Cleaning %i cache entries", len(expired_list))
                for expired in expired_list:
                    del cacheEntries[expired]
            cacheEntries.set_filter(None)
            logging.info(
                "Cleanup complete, %i cache entries remain", len(cacheEntries))
        time.sleep(CLEANUP_SLEEP)


def main():
    """Executed when we are launched"""
    doc = load_metadata()
    InMemoryEntityContainer(doc.root.DataServices['MemCacheSchema.MemCache'])
    server = Server(serviceRoot=SERVICE_ROOT)
    server.set_model(doc)
    # The server is now ready to serve forever
    global cache_app
    cache_app = server
    t = threading.Thread(target=run_cache_server)
    t.setDaemon(True)
    t.start()
    logging.info("MemCache starting HTTP server on %s" % SERVICE_ROOT)
    cleanup_forever(
        doc.root.DataServices['MemCacheSchema.MemCache.KeyValuePairs'])


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
