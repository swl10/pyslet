#! /usr/bin/env python

import base64
import os

from pyslet.py2 import output

if __name__ == '__main__':
    password = base64.encodestring(os.urandom(16)).strip(b"\r\n=")
    python_password = repr(password.decode('ascii'))
    output("DB_PASSWORD = %s\n" % python_password)
