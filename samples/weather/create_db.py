#! /usr/bin/env python

import weather_config as config

if __name__ == '__main__':
    password = config.DB_PASSWORD
    sql_password = password.replace("'", "''")
    print "DROP DATABASE weather;"
    print "CREATE DATABASE weather;"
    print "GRANT SELECT,INSERT,UPDATE,DELETE,CREATE,CREATE TEMPORARY TABLES,"
    print "DROP,INDEX,ALTER ON weather.* TO weather@localhost "
    print "IDENTIFIED BY '%s';" % sql_password
