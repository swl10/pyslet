#! /usr/bin/env python

import sys

if __name__ == '__main__':
    password = sys.argv[1]
    python_password = repr(password)
    print "DB_PASSWORD = %s" % python_password
