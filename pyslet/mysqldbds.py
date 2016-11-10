#! /usr/bin/env python
"""DAL implementation for MySQLdb"""

import logging
import os
import math
import datetime

import pyslet.odata2.csdl as edm
import pyslet.odata2.metadata as edmx
import pyslet.odata2.sqlds as sqlds
import pyslet.blockstore as blockstore

try:
    import MySQLdb as dbapi
except ImportError:
    dbapi = None
    logging.warning("MySQLdb not found, will try PyMySQL instead")
    import pymysql as dbapi


class MySQLEntityContainer(sqlds.SQLEntityContainer):

    """Creates a container that represents a MySQL database.

    Additional keyword arguments:

    db
        name of database to connect to (required)

    host
        optional name of host to connect to (defaults to localhost)

    user
        optional name of user to connect as (default to effective user)

    passwd
        optional password of user to connect with (defaults to none)

    mysql_options
        A dictionary of additional options to pass as named arguments to
        the connect method.  It defaults to an empty dictionary.

        For more information see MySQLdb_

    ..  _MySQLdb:   http://mysql-python.sourceforge.net/MySQLdb.html

    All other keyword arguments required to initialise the base class
    must be passed on construction except *dbapi* which is automatically
    set to the MySQLdb module.

    Please note that the MySQL options use_unicode and charset are
    always set to True and 'utf8' respectively and must not be passed in
    mysql_options.
    """

    def __init__(self, db, host=None, user=None, passwd=None,
                 prefix=None, mysql_options={}, **kwargs):
        self.prefix = prefix
        super(MySQLEntityContainer, self).__init__(dbapi=dbapi, **kwargs)
        self.dbname = db
        self.host = host
        self.user = user
        self.passwd = passwd
        self.mysql_options = mysql_options

#     def get_collection_class(self):
#         """Overridden to return :py:class:`MySQLEntityCollection`"""
#         return MySQLEntityCollection
#
#     def get_symmetric_navigation_class(self):
#         """Overridden to return :py:class:`MySQLAssociationCollection`"""
#         return MySQLAssociationCollection
#
#     def get_fk_class(self):
#         """Overridden to return :py:class:`MySQLForeignKeyCollection`"""
#         return MySQLForeignKeyCollection
#
#     def get_rk_class(self):
#         """Overridden to return :py:class:`MySQLReverseKeyCollection`"""
#         return MySQLReverseKeyCollection

    def open(self):
        """Calls the underlying connect method."""
        dbc = self.dbapi.connect(
            db=self.dbname, host=self.host, user=self.user,
            passwd=self.passwd, use_unicode=True, charset='utf8',
            **self.mysql_options)
        return dbc

    def mangle_name(self, source_path):
        """Incorporates the table name prefix"""
        if len(source_path) == 1 and self.prefix:
            source_path = self.prefix + source_path[0]
            return self.quote_identifier(source_path)
        else:
            return super(MySQLEntityContainer, self).mangle_name(source_path)

    def quote_identifier(self, identifier):
        """Given an *identifier* returns a safely quoted form of it.

        By default we replace backtick with a single quote and then use
        backticks to quote the identifier. E.g., if the string
        'Employee_Name' is passed then the string '`Employee_Name`' is
        returned."""
        return '`%s`' % identifier.replace('`', '')

    def prepare_sql_type(self, simple_value, params, nullable=None):
        """Performs MySQL custom mappings

        ==================  ===================================
           EDM Type         MySQL Equivalent
        ------------------  -----------------------------------
        Edm.DateTime        DATETIME(n) with precision
        Edm.Binary          BLOB (when large or unbounded)
        Edm.String          TEXT (when unbounded)
        Edm.Time            TIME(n) with precision
        ==================  ===================================

        All other types use the default mapping."""
        p = simple_value.p_def
        column_def = []
        explicit_null = False
        explicit_default = None
        if isinstance(simple_value, edm.BinaryValue):
            if p is None or (p.fixedLength is None and p.maxLength is None):
                column_def.append("BLOB")
            else:
                max = 0
                if p.fixedLength:
                    max = p.fixedLength
                if p.maxLength:
                    max = p.maxLength
                if max > 1024:
                    column_def.append("BLOB")
        elif isinstance(simple_value, edm.StringValue):
            if p is None or (p.fixedLength is None and p.maxLength is None):
                column_def.append("TEXT")
        elif isinstance(simple_value, edm.DateTimeValue):
            if p is None or p.precision is None:
                precision = 0
            else:
                precision = p.precision
            if p.precision > 6:
                # maximum precision
                precision = 6
            if precision:
                column_def.append("DATETIME(%i)" % precision)
            else:
                column_def.append("DATETIME")
            explicit_null = True
            explicit_default = '0'
        elif isinstance(simple_value, edm.TimeValue):
            if p is None or p.precision is None:
                precision = 0
            else:
                precision = p.precision
            if p.precision > 6:
                # maximum precision
                precision = 6
            if precision:
                column_def.append("TIME(%i)" % precision)
            else:
                column_def.append("TIME")
        if column_def:
            if ((nullable is not None and not nullable) or
                    (nullable is None and p is not None and not p.nullable)):
                column_def.append(' NOT NULL')
                # use the explicit default
                if explicit_default and not simple_value:
                    column_def.append(' DEFAULT ')
                    column_def.append(explicit_default)
            elif explicit_null:
                column_def.append(' NULL')
            if simple_value:
                # Format the default
                column_def.append(' DEFAULT ')
                column_def.append(
                    params.add_param(self.prepare_sql_value(simple_value)))
            return ''.join(column_def)
        else:
            return super(
                MySQLEntityContainer,
                self).prepare_sql_type(
                simple_value,
                params,
                nullable)

    def prepare_sql_value(self, simple_value):
        """Returns a python value suitable for passing as a parameter.

        We inherit most of the value mappings but the following types
        have custom mappings.

        ==================  ==============================================
           EDM Type         Python value added as parameter
        ------------------  ----------------------------------------------
        Edm.Time            datetime.time to handle micro seconds
        ==================  ==============================================
        """
        if not simple_value:
            return None
        elif isinstance(simple_value, edm.TimeValue):
            # we know this is datetime.time so use microseconds
            if isinstance(simple_value.value.second, float):
                # calculate microseconds
                micros, seconds = math.modf(simple_value.value.second)
                micros = int(micros * 1000000)
                seconds = int(seconds)
            else:
                seconds = simple_value.value.second
                micros = 0
            return datetime.time(
                simple_value.value.hour,
                simple_value.value.minute,
                seconds, micros)
        else:
            return super(
                MySQLEntityContainer,
                self).prepare_sql_value(simple_value)

    def limit_clause(self, skip, top):
        clause = []
        if top:
            clause.append('LIMIT %i ' % top)
        if skip:
            clause.append('OFFSET %i ' % skip)
            skip = 0
        return skip, ''.join(clause)


class MySQLStreamStore(blockstore.StreamStore):

    """A stream store backed by a MySQL database.

    db
        The name of the database (required)

    dpath
        The optional directory path to the file system to use for
        storing the blocks of data. If dpath is None then the blocks are
        stored in the MySQL database itself.

    The MySQL connection options, including host, user, passwd, etc. are
    the same as those passed to the constructor of
    :py:class:`MySQLEntityContainer`.  The prefix option may also be
    used."""

    def load_container(self):
        """Loads and returns a default entity container

        The return value is an
        :py:class:`pyslet.odata2.csdl.EntityContainer` instance with
        an EntitySets called 'Blocks', 'Locks' and 'Streams' that are
        suitable for passing to the constructors of
        :py:class:`pyslet.blockstore.BlockStore`,
        :py:class:`pyslet.blockstore.LockStore` and
        :py:class:`pyslet.blockstore.StreamStore`
        respectively."""
        doc = edmx.Document()
        with open(os.path.join(os.path.dirname(__file__),
                               'odata2', 'streamstore.xml'), 'r') as f:
            doc.read(f)
        return doc.root.DataServices['StreamStoreSchema.Container']

    def __init__(self, db, dpath=None, **kwargs):
        self.container_def = self.load_container()
        #: the :py:class:`MySQLEntityContainer` used for the blockstore
        self.container = MySQLEntityContainer(db=db,
                                              container=self.container_def,
                                              **kwargs)
        if dpath is None:
            bs = blockstore.FileBlockStore(dpath)
        else:
            bs = blockstore.EDMBlockStore(
                entity_set=self.container_def['Blocks'])
        ls = blockstore.LockStore(entity_set=self.container_def['Locks'])
        blockstore.StreamStore.__init__(
            self, bs, ls, self.container_def['Streams'])
