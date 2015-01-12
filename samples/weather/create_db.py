#! /usr/bin/env python

import sys

if __name__ == '__main__':
    password = sys.argv[1]
    sql_password = password.replace("'", "''")
    print "DROP DATABASE weather;"
    print "CREATE DATABASE weather;"
    print "GRANT SELECT,INSERT,UPDATE,DELETE,CREATE,CREATE TEMPORARY TABLES,"
    print "DROP,INDEX,ALTER ON weather.* TO weather@localhost "
    print "IDENTIFIED BY '%s';" % sql_password
