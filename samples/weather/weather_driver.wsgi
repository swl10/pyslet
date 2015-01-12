#! /usr/bin/env python

import logging

from pyslet.odata2.server import ReadOnlyServer

import weather
import config

logging.basicConfig(filename=config.LOG_FILE, level=config.LOG_LEVEL)
doc = weather.load_metadata()
weather.make_mysql_container(doc, host=config.DB_HOST, database=config.DB_USER,
                             user=config.DB_USER, password=config.DB_PASSWORD)
server = ReadOnlyServer(serviceRoot=config.SERVICE_ROOT)
server.SetModel(doc)
logging.debug("Path prefix: %s", server.pathPrefix)


def application(environ, start_response):
    logging.debug("*** START REQUEST ***")
    for key in environ:
        logging.debug("%s: %s", key, str(environ[key]))
    for data in server(environ, start_response):
        if not isinstance(data, str):
            logging.debug("Bad response data: %s", data)
        else:
            logging.debug(data)
        yield data
    return
