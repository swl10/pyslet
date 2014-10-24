--
-- Execute with, for example:
-- mysql -v -u root -p < unittests/test_mysqldbds.sql
--

CREATE DATABASE pyslet;

GRANT SELECT,INSERT,UPDATE,DELETE,CREATE,CREATE TEMPORARY TABLES,
    DROP,INDEX,ALTER ON pyslet.* TO pyslet@localhost IDENTIFIED BY 'pyslet';
