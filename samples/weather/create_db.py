#! /usr/bin/env python

from pyslet.py2 import output

import weather_config as config

if __name__ == '__main__':
    password = config.DB_PASSWORD
    sql_password = password.replace("'", "''")
    output("DROP DATABASE weather;\n")
    output("CREATE DATABASE weather;\n")
    output("GRANT SELECT,INSERT,UPDATE,DELETE,CREATE,CREATE TEMPORARY TABLES,")
    output("DROP,INDEX,ALTER ON weather.* TO weather@localhost ")
    output("IDENTIFIED BY '%s';\n" % sql_password)
