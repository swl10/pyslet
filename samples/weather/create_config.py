#! /usr/bin/env python

import base64
import os
import sys

if __name__ == '__main__':
    password = base64.encodestring(os.urandom(16)).strip("\r\n=")
    python_password = repr(password)
    print "DB_PASSWORD = %s" % python_password
