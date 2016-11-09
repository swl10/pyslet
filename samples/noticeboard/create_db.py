#! /usr/bin/env python

import json
import sys

if __name__ == '__main__':
    input = sys.argv[1]
    with open(input, 'rb') as f:
        settings = json.load(f)
    password = settings['WSGIDataApp']['dbpassword']
    sql_password = password.replace("'", "''")
    print "DROP DATABASE noticeboard;"
    print "CREATE DATABASE noticeboard;"
    print "GRANT SELECT,INSERT,UPDATE,DELETE,CREATE,CREATE TEMPORARY TABLES,"
    print "DROP,INDEX,ALTER ON noticeboard.* TO noticeboard@localhost "
    print "IDENTIFIED BY '%s';" % sql_password
