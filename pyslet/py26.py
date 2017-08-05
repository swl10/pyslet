#! /usr/bin/env python
"""Experimental module for Python 2.6 compatibility."""

import io
import logging
import sys
import zipfile

from wsgiref.simple_server import ServerHandler

from .py2 import is_text, builtins


py26 = sys.hexversion < 0x02070000
"""If you must know whether or not you are running under Python 2.6
then you can check using this flag,which is True in that case."""


def finish_content(self):
    # ugly patch for python 2.6; see the following for details:
    # http://stackoverflow.com/questions/3857029/does-wsgi-override-content-length-header
    if not self.headers_sent:
        if (self.environ.get('REQUEST_METHOD', '') != 'HEAD' or
                'Content-Length' not in self.headers):
            self.headers['Content-Length'] = 0
        self.send_headers()


def is_zipfile(filename):
    # patched to accept a file that is already open we use the
    # _EndRecData method directly, we're all grown-ups here
    try:
        if is_text(filename):
            fpin = open(filename, "rb")
            endrec = zipfile._EndRecData(fpin)
            fpin.close()
        else:
            endrec = zipfile._EndRecData(filename)
        if endrec:
            return True
    except IOError:
        pass
    return False


if py26:
    def get_method_function(methodlike):
        if isinstance(methodlike, classmethod):
            # second arg just needs to be any type
            return methodlike.__get__(None, type).im_func
        elif isinstance(methodlike, staticmethod):
            return methodlike.__get__(None, type)
        else:
            return methodlike
else:
    def get_method_function(methodlike):
        if isinstance(methodlike, (classmethod, staticmethod)):
            return methodlike.__func__
        else:
            return methodlike


if py26:
    logging.info("Adding missing constants to py26.io")
    io.SEEK_SET = 0
    io.SEEK_CUR = 1
    io.SEEK_END = 2

    class memoryview(object):       # noqa

        def __init__(self):
            raise TypeError("memoryview object not available in py26")

    logging.info("Patching wsgiref.simple_server.ServerHandler for HEAD bug")
    ServerHandler.finish_content = finish_content

    logging.info("Patching zipfile.is_zipfile for open files")
    zipfile.is_zipfile = is_zipfile
else:
    memoryview = builtins.memoryview


if py26:
    class RawIOBase(io.RawIOBase):

        def read(self, n=-1):
            """Read and return up to n bytes.

            Returns an empty bytes array on EOF, or None if the object is
            set not to block and has no data to read.

            Adapted from python2.6/io.py to deal with failure to return
            None in non-blocking case."""
            if n is None:
                n = -1
            if n < 0:
                return self.readall()
            b = bytearray(n.__index__())
            n = self.readinto(b)
            if n is None:
                return None
            else:
                del b[n:]
                return bytes(b)
else:
    RawIOBase = io.RawIOBase
