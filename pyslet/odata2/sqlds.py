#! /usr/bin/env python
"""Binds the OData API to the Python DB API."""


import binascii
import decimal
import hashlib
import io
import itertools
import logging
import math
import os.path
import sqlite3
import sys
import threading
import time
import traceback
import warnings

from .. import blockstore
from .. import iso8601 as iso
from ..http import params
from ..py2 import (
    buffer2,
    dict_items,
    dict_values,
    is_text,
    range3,
    to_text,
    ul)
from ..vfs import OSFilePath

from . import core
from . import csdl as edm
from . import metadata as edmx


logging = logging.getLogger('pyslet.odata2.sqlds')

# : the standard timeout while waiting for a database connection, in seconds
SQL_TIMEOUT = 90


class SQLError(Exception):

    """Base class for all module exceptions."""
    pass


class DatabaseBusy(SQLError):

    """Raised when a database connection times out."""
    pass

SQLOperatorPrecedence = {
    ',': 0,
    'OR': 1,
    'AND': 2,
    'NOT': 3,
    '=': 4,
    '<>': 4,
    '<': 4,
    '>': 4,
    '<=': 4,
    '>=': 4,
    'LIKE': 4,
    '+': 5,
    '-': 5,
    '*': 6,
    '/': 6
}
"""Look-up table for SQL operator precedence calculations.

The keys are strings representing the operator, the values are
integers that allow comparisons for operator precedence. For
example::

    SQLOperatorPrecedence['+']<SQLOperatorPrecedence['*']
    SQLOperatorPrecedence['<']==SQLOperatorPrecedence['>']"""


class UnparameterizedLiteral(core.LiteralExpression):

    """Class used as a flag that this literal is safe and does not need
    to be parameterized.

    This is used in the query converter to prevent things like this
    happening when the converter itself constructs a LIKE expression::

            "name" LIKE ?+?+? ; params=['%', "Smith", '%']"""
    pass


class SQLParams(object):

    """An abstract class used to build parameterized queries.

    Python's DB API supports three different conventions for specifying
    parameters and each module indicates the convention in use.  The SQL
    construction methods in this module abstract away this variability
    for maximum portability using different implementations of the basic
    SQLParams class."""

    def __init__(self):
        # : an object suitable for passing to DB API's execute method
        self.params = None

    def add_param(self, value):
        """Adds a value to this set of parameters

        Returns the string to include in the query in place of this
        value.

        value:
                The native representation of the value in a format
                suitable for passing to the underlying DB API."""
        raise NotImplementedError

    @classmethod
    def escape_literal(cls, literal):
        """Escapes a literal string, returning the escaped version

        This method is only used to escape characters that are
        interpreted specially by the parameter substitution system. For
        example, if the parameters are being substituted using python's
        % operator then the '%' sign needs to be escaped (by doubling)
        in the output.

        This method has nothing to do with turning python values into
        SQL escaped literals, that task is always deferred to the
        underlying DB module to prevent SQL injection attacks.

        The default implementation does nothing, in most cases that is
        the correct thing to do."""
        return literal


class QMarkParams(SQLParams):

    """A class for building parameter lists using '?' syntax."""

    def __init__(self):
        super(QMarkParams, self).__init__()
        self.params = []

    def add_param(self, value):
        self.params.append(value)
        return "?"


class FormatParams(SQLParams):

    """A class for building parameter lists using '%s' syntax."""

    def __init__(self):
        super(FormatParams, self).__init__()
        self.params = []

    def add_param(self, value):
        self.params.append(value)
        return "%s"

    @classmethod
    def escape_literal(cls, literal):
        """Doubles any % characters to prevent formatting errors"""
        return literal.replace("%", "%%")


class NumericParams(SQLParams):

    """A class for building parameter lists using ':1', ':2',... syntax"""

    def __init__(self):
        super(NumericParams, self).__init__()
        self.params = []

    def add_param(self, value):
        self.params.append(value)
        return ":%i" % len(self.params)


class NamedParams(SQLParams):

    """A class for building parameter lists using ':A', ':B",... syntax

    Although there is more freedom with named parameters, in order to
    support the ordered lists of the other formats we just invent
    parameter names using ':p0', ':p1', etc."""

    def __init__(self):
        super(NamedParams, self).__init__()
        self.params = {}

    def add_param(self, value):
        name = "p%i" % len(self.params)
        self.params[name] = value
        return ":" + name


class PyFormatParams(SQLParams):

    """A class for building parameter lists using '%(name)s' syntax."""

    def __init__(self):
        super(PyFormatParams, self).__init__()
        self.params = {}

    def add_param(self, value):
        name = "p%i" % len(self.params)
        self.params[name] = value
        return "%%(%s)s" % name

    @classmethod
    def escape_literal(cls, literal):
        """Doubles any % characters to prevent formatting errors"""
        return literal.replace("%", "%%")


def retry_decorator(tmethod):
    """Decorates a transaction method with retry handling"""

    def retry(self, *args, **kwargs):
        if self.query_count:
            return tmethod(self, *args, **kwargs)
        else:
            strike = 0
            while True:
                try:
                    result = tmethod(self, *args, **kwargs)
                    break
                except self.api.OperationalError as err:
                    strike += 1
                    if strike < 3:
                        logging.error(
                            "Thread[%i] retrying database connection "
                            "after error: %s", self.connection.thread_id,
                            str(err))
                        self.container.close_connection(self.connection.dbc)
                        self.connection.dbc = self.container.open()
                        if self.cursor is not None:
                            # create a new cursor
                            self.cursor = self.connection.dbc.cursor()
                    else:
                        raise
        return result

    return retry


class SQLTransaction(object):

    """Class used to model a transaction.

    Python's DB API uses transactions by default, hiding the details from
    the caller.  Essentially, the first execute call on a connection issues
    a BEGIN statement and the transaction ends with either a commit or a
    rollback.  It is generally considered a bad idea to issue a SQL command
    and then leave the connection with an open transaction.

    The purpose of this class is to help us write methods that can
    operate either as a single transaction or as part of sequence of
    methods that form a single transaction.  It also manages cursor
    creation and closing and logging.

    Essentially, the class is used as follows::

            t = SQLTransaction(db_container, db_connection)
            try:
                    t.begin()
                    t.execute("UPDATE SOME_TABLE SET SOME_COL='2'")
                    t.commit()
            except Exception as e:
                    t.rollback(e)
            finally:
                    t.close(e)

    The transaction object can be passed to a sub-method between the
    begin and commit calls provided that method follows the same pattern
    as the above for the try, except and finally blocks.  The object
    keeps track of these 'nested' transactions and delays the commit or
    rollback until the outermost method invokes them."""

    def __init__(self, container, connection):
        self.container = container
        self.api = container.dbapi      #: the database module
        self.connection = connection    #: the database connection
        #: the database cursor to use for executing commands
        self.cursor = None
        self.no_commit = 0      #: used to manage nested transactions
        self.query_count = 0    #: records the number of successful commands

    @retry_decorator
    def begin(self):
        """Begins a transaction

        If a transaction is already in progress a nested transaction is
        started which has no affect on the database connection itself."""
        if self.cursor is None:
            self.cursor = self.connection.dbc.cursor()
        else:
            self.no_commit += 1

    @retry_decorator
    def execute(self, sqlcmd, params=None):
        """Executes *sqlcmd* as part of this transaction.

        sqlcmd
                A string containing the query

        params
                A :py:class:`SQLParams` object containing any
                parameterized values."""
        self.cursor.execute(sqlcmd,
                            params.params if params is not None else None)
        self.query_count += 1

    def commit(self):
        """Ends this transaction with a commit

        Nested transactions do nothing."""
        if self.no_commit:
            return
        self.connection.dbc.commit()

    def rollback(self, err=None, swallow=False):
        """Calls the underlying database connection rollback method.

        Nested transactions do not rollback the connection, they do
        nothing except re-raise *err* (if required).

        If rollback is not supported the resulting error is absorbed.

        err
            The exception that triggered the rollback.  If not None then
            this is logged at INFO level when the rollback succeeds.

            If the transaction contains at least one successfully
            executed query and the rollback fails then *err* is logged
            at ERROR rather than INFO level indicating that the data may
            now be in violation of the model.

        swallow
            A flag (defaults to False) indicating that *err* should be
            swallowed, rather than re-raised."""
        if not self.no_commit:
            try:
                self.connection.dbc.rollback()
                if err is not None:
                    logging.info(
                        "rollback invoked for transaction following error %s",
                        str(err))
            except self.api.NotSupportedError:
                if err is not None:
                    if self.query_count:
                        logging.error(
                            "Data Integrity Error on TABLE %s: rollback "
                            "invoked on a connection that does not "
                            "support transactions after error %s",
                            self.table_name,
                            str(err))
                    else:
                        logging.info(
                            "Query failed following error %s", str(err))
                pass
        if err is not None and not swallow:
            logging.debug(
                ' '.join(
                    traceback.format_exception(*sys.exc_info(), limit=6)))
            if isinstance(err, self.api.Error):
                raise SQLError(str(err))
            else:
                raise err

    def close(self):
        """Closes this transaction after a rollback or commit.

        Each call to :py:meth:`begin` MUST be balanced with one call to
        close."""
        if self.no_commit:
            self.no_commit = self.no_commit - 1
        elif self.cursor is not None:
            self.cursor.close()
            self.cursor = None
            self.query_count = 0


class SQLCollectionBase(core.EntityCollection):

    """A base class to provide core SQL functionality.

    Additional keyword arguments:

    container
            A :py:class:`SQLEntityContainer` instance.

    On construction a data connection is acquired from *container*, this
    may prevent other threads from using the database until the lock is
    released by the :py:meth:`close` method."""

    DEFAULT_VALUE = True
    """A boolean indicating whether or not the collection supports the
    syntax::

        UPDATE "MyTable" SET "MyField"=DEFAULT

    Most databases do support this syntax but SQLite does not.  In cases
    where this is False, default values are set explicitly as they are
    defined in the metadata model instead.  If True then the default
    values defined in the metadata model are ignored by the
    collection object."""

    def __init__(self, container, **kwargs):
        super(SQLCollectionBase, self).__init__(**kwargs)
        #: the parent container (database) for this collection
        self.container = container
        # the quoted table name containing this collection
        self.table_name = self.container.mangled_names[(self.entity_set.name,)]
        self.auto_keys = False
        for k in self.entity_set.keys:
            source_path = (self.entity_set.name, k)
            if source_path in self.container.ro_names:
                self.auto_keys = True
        self._joins = None
        # force orderNames to be initialised
        self.set_orderby(None)
        #: a connection to the database acquired with
        #: :meth:`SQLEntityContainer.acquire_connection`
        self.connection = None
        self._sqlLen = None
        self._sqlGen = None
        try:
            self.connection = self.container.acquire_connection(SQL_TIMEOUT)
            if self.connection is None:
                raise DatabaseBusy(
                    "Failed to acquire connection after %is" % SQL_TIMEOUT)
        except:
            self.close()
            raise

    def close(self):
        """Closes the cursor and database connection if they are open."""
        if self.connection is not None:
            self.container.release_connection(self.connection)
            self.connection = None

    def __len__(self):
        if self._sqlLen is None:
            query = ["SELECT COUNT(*) FROM %s" % self.table_name]
            params = self.container.ParamsClass()
            where = self.where_clause(None, params)
            query.append(self.join_clause())
            query.append(where)
            query = ''.join(query)
            self._sqlLen = (query, params)
        else:
            query, params = self._sqlLen
        transaction = SQLTransaction(self.container, self.connection)
        try:
            transaction.begin()
            logging.info("%s; %s", query, to_text(params.params))
            transaction.execute(query, params)
            # get the result
            result = transaction.cursor.fetchone()[0]
            # we haven't changed the database, but we don't want to
            # leave the connection idle in transaction
            transaction.commit()
            return result
        except Exception as e:
            # we catch (almost) all exceptions and re-raise after rollback
            transaction.rollback(e)
        finally:
            transaction.close()

    def entity_generator(self):
        entity, values = None, None
        if self._sqlGen is None:
            entity = self.new_entity()
            query = ["SELECT "]
            params = self.container.ParamsClass()
            column_names, values = zip(*list(self.select_fields(entity)))
            # values is used later for the first result
            column_names = list(column_names)
            self.orderby_cols(column_names, params)
            query.append(", ".join(column_names))
            query.append(' FROM ')
            query.append(self.table_name)
            # we force where and orderby to be calculated before the
            # join clause is added as they may add to the joins
            where = self.where_clause(
                None, params, use_filter=True, use_skip=False)
            orderby = self.orderby_clause()
            query.append(self.join_clause())
            query.append(where)
            query.append(orderby)
            query = ''.join(query)
            self._sqlGen = query, params
        else:
            query, params = self._sqlGen
        transaction = SQLTransaction(self.container, self.connection)
        try:
            transaction.begin()
            logging.info("%s; %s", query, to_text(params.params))
            transaction.execute(query, params)
            while True:
                row = transaction.cursor.fetchone()
                if row is None:
                    break
                if entity is None:
                    entity = self.new_entity()
                    values = next(
                        itertools.islice(
                            zip(*list(self.select_fields(entity))), 1, None))
                for value, new_value in zip(values, row):
                    self.container.read_sql_value(value, new_value)
                entity.exists = True
                yield entity
                entity, values = None, None
            # we haven't changed the database, but we don't want to
            # leave the connection idle in transaction
            transaction.commit()
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()

    def itervalues(self):
        return self.expand_entities(
            self.entity_generator())

    def set_page(self, top, skip=0, skiptoken=None):
        """Sets the values for paging.

        Our implementation uses a special format for *skiptoken*.  It is
        a comma-separated list of simple literal values corresponding to
        the values required by the ordering augmented with the key
        values to ensure uniqueness.

        For example, if $orderby=A,B on an entity set with key K then
        the skiptoken will typically have three values comprising the
        last values returned for A,B and K in that order.  In cases
        where the resulting skiptoken would be unreasonably large an
        additional integer (representing a further skip) may be appended
        and the whole token expressed relative to an earlier skip
        point."""
        self.top = top
        self.skip = skip
        if skiptoken is None:
            self.skiptoken = None
        else:
            # parse a sequence of literal values
            p = core.Parser(skiptoken)
            self.skiptoken = []
            while True:
                p.parse_wsp()
                self.skiptoken.append(
                    p.require_production(p.parse_uri_literal()))
                p.parse_wsp()
                if not p.parse(','):
                    if p.match_end():
                        break
                    else:
                        raise core.InvalidSystemQueryOption(
                            "Unrecognized $skiptoken: %s" % skiptoken)
            if self.orderby is None:
                order_len = 0
            else:
                order_len = len(self.orderby)
            if (len(self.skiptoken) ==
                    order_len + len(self.entity_set.keys) + 1):
                # the last value must be an integer we add to skip
                if isinstance(self.skiptoken[-1], edm.Int32Value):
                    self.skip += self.skiptoken[-1].value
                    self.skiptoken = self.skiptoken[:-1]
                else:
                    raise core.InvalidSystemQueryOption(
                        "skiptoken incompatible with ordering: %s" % skiptoken)
            elif len(self.skiptoken) != order_len + len(self.entity_set.keys):
                raise core.InvalidSystemQueryOption(
                    "skiptoken incompatible with ordering: %s" % skiptoken)
        self.nextSkiptoken = None

    def next_skiptoken(self):
        if self.nextSkiptoken:
            token = []
            for t in self.nextSkiptoken:
                token.append(core.ODataURI.format_literal(t))
            return ",".join(token)
        else:
            return None

    def page_generator(self, set_next=False):
        if self.top == 0:
            # end of paging
            return
        skip = self.skip
        top = self.top
        topmax = self.topmax
        if topmax is not None:
            if top is not None:
                limit = min(top, topmax)
            else:
                limit = topmax
        else:
            limit = top
        entity = self.new_entity()
        query = ["SELECT "]
        skip, limit_clause = self.container.select_limit_clause(skip, limit)
        if limit_clause:
            query.append(limit_clause)
        params = self.container.ParamsClass()
        column_names, values = zip(*list(self.select_fields(entity)))
        column_names = list(column_names)
        self.orderby_cols(column_names, params, True)
        query.append(", ".join(column_names))
        query.append(' FROM ')
        query.append(self.table_name)
        where = self.where_clause(None, params, use_filter=True, use_skip=True)
        orderby = self.orderby_clause()
        query.append(self.join_clause())
        query.append(where)
        query.append(orderby)
        skip, limit_clause = self.container.limit_clause(skip, limit)
        if limit_clause:
            query.append(limit_clause)
        query = ''.join(query)
        transaction = SQLTransaction(self.container, self.connection)
        try:
            transaction.begin()
            logging.info("%s; %s", query, to_text(params.params))
            transaction.execute(query, params)
            while True:
                row = transaction.cursor.fetchone()
                if row is None:
                    # no more pages
                    if set_next:
                        self.top = self.skip = 0
                        self.skipToken = None
                    break
                if skip:
                    skip = skip - 1
                    continue
                if entity is None:
                    entity = self.new_entity()
                    values = next(
                        itertools.islice(
                            zip(*list(self.select_fields(entity))), 1, None))
                row_values = list(row)
                for value, new_value in zip(values, row_values):
                    self.container.read_sql_value(value, new_value)
                entity.exists = True
                yield entity
                if topmax is not None:
                    topmax = topmax - 1
                    if topmax < 1:
                        # this is the last entity, set the nextSkiptoken
                        order_values = row_values[-len(self.orderNames):]
                        self.nextSkiptoken = []
                        for v in order_values:
                            self.nextSkiptoken.append(
                                self.container.new_from_sql_value(v))
                        tokenlen = 0
                        for v in self.nextSkiptoken:
                            if v and isinstance(v, (edm.StringValue,
                                                    edm.BinaryValue)):
                                tokenlen += len(v.value)
                        # a really large skiptoken is no use to anyone
                        if tokenlen > 512:
                            # ditch this one, copy the previous one and add a
                            # skip
                            self.nextSkiptoken = list(self.skiptoken)
                            v = edm.Int32Value()
                            v.set_from_value(self.topmax)
                            self.nextSkiptoken.append(v)
                        if set_next:
                            self.skiptoken = self.nextSkiptoken
                            self.skip = 0
                        break
                if top is not None:
                    top = top - 1
                    if top < 1:
                        if set_next:
                            if self.skip is not None:
                                self.skip = self.skip + self.top
                            else:
                                self.skip = self.top
                        break
                entity = None
            # we haven't changed the database, but we don't want to
            # leave the connection idle in transaction
            transaction.commit()
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()

    def iterpage(self, set_next=False):
        return self.expand_entities(
            self.page_generator(set_next))

    def __getitem__(self, key):
        entity = self.new_entity()
        entity.set_key(key)
        params = self.container.ParamsClass()
        query = ["SELECT "]
        column_names, values = zip(*list(self.select_fields(entity)))
        query.append(", ".join(column_names))
        query.append(' FROM ')
        query.append(self.table_name)
        where = self.where_clause(entity, params)
        query.append(self.join_clause())
        query.append(where)
        query = ''.join(query)
        transaction = SQLTransaction(self.container, self.connection)
        try:
            transaction.begin()
            logging.info("%s; %s", query, to_text(params.params))
            transaction.execute(query, params)
            rowcount = transaction.cursor.rowcount
            row = transaction.cursor.fetchone()
            if rowcount == 0 or row is None:
                raise KeyError
            elif rowcount > 1 or (rowcount == -1 and
                                  transaction.cursor.fetchone() is not None):
                # whoops, that was unexpected
                raise SQLError(
                    "Integrity check failure, non-unique key: %s" % repr(key))
            for value, new_value in zip(values, row):
                self.container.read_sql_value(value, new_value)
            entity.exists = True
            entity.expand(self.expand, self.select)
            transaction.commit()
            return entity
        except KeyError:
            # no need to do a rollback for a KeyError, will still
            # close the transaction of course
            raise
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()

    def read_stream(self, key, out=None):
        entity = self.new_entity()
        entity.set_key(key)
        svalue = self._get_streamid(key)
        sinfo = core.StreamInfo()
        if svalue:
            estream = self.container.streamstore.get_stream(svalue.value)
            sinfo.type = params.MediaType.from_str(estream['mimetype'].value)
            sinfo.created = estream['created'].value.with_zone(0)
            sinfo.modified = estream['modified'].value.with_zone(0)
            sinfo.size = estream['size'].value
            sinfo.md5 = estream['md5'].value
        else:
            estream = None
            sinfo.size = 0
            sinfo.md5 = hashlib.md5(b'').digest()
        if out is not None and svalue:
            with self.container.streamstore.open_stream(estream, 'r') as src:
                actual_size, actual_md5 = self._copy_src(src, out)
            if sinfo.size is not None and sinfo.size != actual_size:
                # unexpected size mismatch
                raise SQLError("stream size mismatch on read %s" %
                               entity.get_location())
            if sinfo.md5 is not None and sinfo.md5 != actual_md5:
                # md5 mismatch
                raise SQLError("stream checksum mismatch on read %s" %
                               entity.get_location())
        return sinfo

    def read_stream_close(self, key):
        entity = self.new_entity()
        entity.set_key(key)
        svalue = self._get_streamid(key)
        sinfo = core.StreamInfo()
        if svalue:
            estream = self.container.streamstore.get_stream(svalue.value)
            sinfo.type = params.MediaType.from_str(estream['mimetype'].value)
            sinfo.created = estream['created'].value.with_zone(0)
            sinfo.modified = estream['modified'].value.with_zone(0)
            sinfo.size = estream['size'].value
            sinfo.md5 = estream['md5'].value
            return sinfo, self._read_stream_gen(estream, sinfo)
        else:
            estream = None
            sinfo.size = 0
            sinfo.md5 = hashlib.md5('').digest()
            self.close()
            return sinfo, []

    def _read_stream_gen(self, estream, sinfo):
        try:
            with self.container.streamstore.open_stream(estream, 'r') as src:
                h = hashlib.md5()
                count = 0
                while True:
                    data = src.read(io.DEFAULT_BUFFER_SIZE)
                    if len(data):
                        count += len(data)
                        h.update(data)
                        yield data
                    else:
                        break
            if sinfo.size is not None and sinfo.size != count:
                # unexpected size mismatch
                raise SQLError("stream size mismatch on read [%i]" %
                               estream.key())
            if sinfo.md5 is not None and sinfo.md5 != h.digest():
                # md5 mismatch
                raise SQLError("stream checksum mismatch on read [%i]" %
                               estream.key())
        finally:
            self.close()

    def update_stream(self, src, key, sinfo=None):
        e = self.new_entity()
        e.set_key(key)
        if sinfo is None:
            sinfo = core.StreamInfo()
        etag = e.etag_values()
        if len(etag) == 1 and isinstance(etag[0], edm.BinaryValue):
            h = hashlib.sha256()
            etag = etag[0]
        else:
            h = None
        c, v = self.stream_field(e, prefix=False)
        if self.container.streamstore:
            # spool the data into the store and store the stream key
            estream = self.container.streamstore.new_stream(sinfo.type,
                                                            sinfo.created)
            with self.container.streamstore.open_stream(estream, 'w') as dst:
                sinfo.size, sinfo.md5 = self._copy_src(src, dst, sinfo.size, h)
            if sinfo.modified is not None:
                # force modified date based on input
                estream['modified'].set_from_value(
                    sinfo.modified.shift_zone(0))
                estream.commit()
            v.set_from_value(estream.key())
        else:
            raise NotImplementedError
        if h is not None:
            etag.set_from_value(h.digest())
        oldvalue = self._get_streamid(key)
        transaction = SQLTransaction(self.container, self.connection)
        try:
            transaction.begin()
            # store the new stream value for the entity
            query = ['UPDATE ', self.table_name, ' SET ']
            params = self.container.ParamsClass()
            query.append(
                "%s=%s" %
                (c, params.add_param(self.container.prepare_sql_value(v))))
            query.append(' WHERE ')
            where = []
            for k, kv in dict_items(e.key_dict()):
                where.append(
                    '%s=%s' %
                    (self.container.mangled_names[(self.entity_set.name, k)],
                     params.add_param(self.container.prepare_sql_value(kv))))
            query.append(' AND '.join(where))
            query = ''.join(query)
            logging.info("%s; %s", query, to_text(params.params))
            transaction.execute(query, params)
        except Exception as e:
            # we allow the stream store to re-use the same database but
            # this means we can't transact on both at once (from the
            # same thread) - settle for logging at the moment
            # self.container.streamstore.delete_stream(estream)
            logging.error("Orphan stream created %s[%i]",
                          estream.entity_set.name, estream.key())
            transaction.rollback(e)
        finally:
            transaction.close()
        # now remove the old stream
        if oldvalue:
            oldstream = self.container.streamstore.get_stream(oldvalue.value)
            self.container.streamstore.delete_stream(oldstream)

    def _get_streamid(self, key, transaction=None):
        entity = self.new_entity()
        entity.set_key(key)
        params = self.container.ParamsClass()
        query = ["SELECT "]
        sname, svalue = self.stream_field(entity)
        query.append(sname)
        query.append(' FROM ')
        query.append(self.table_name)
        query.append(self.where_clause(entity, params, use_filter=False))
        query = ''.join(query)
        if transaction is None:
            transaction = SQLTransaction(self.container, self.connection)
        try:
            transaction.begin()
            logging.info("%s; %s", query, to_text(params.params))
            transaction.execute(query, params)
            rowcount = transaction.cursor.rowcount
            row = transaction.cursor.fetchone()
            if rowcount == 0 or row is None:
                raise KeyError
            elif rowcount > 1 or (rowcount == -1 and
                                  transaction.cursor.fetchone() is not None):
                # whoops, that was unexpected
                raise SQLError(
                    "Integrity check failure, non-unique key: %s" % repr(key))
            self.container.read_sql_value(svalue, row[0])
            entity.exists = True
            transaction.commit()
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()
        return svalue

    def _copy_src(self, src, dst, max_bytes=None, xhash=None):
        md5 = hashlib.md5()
        rbytes = max_bytes
        count = 0
        while rbytes is None or rbytes > 0:
            if rbytes is None:
                data = src.read(io.DEFAULT_BUFFER_SIZE)
            else:
                data = src.read(min(rbytes, io.DEFAULT_BUFFER_SIZE))
                rbytes -= len(data)
            if not data:
                # we're done
                break
            # add the data to the hash
            md5.update(data)
            if xhash is not None:
                xhash.update(data)
            while data:
                wbytes = dst.write(data)
                if wbytes is None:
                    if not isinstance(dst, io.RawIOBase):
                        wbytes = len(data)
                    else:
                        wbytes = 0
                        time.sleep(0)   # yield to prevent hard loop
                if wbytes < len(data):
                    data = data[wbytes:]
                else:
                    data = None
                count += wbytes
        return count, md5.digest()

    def reset_joins(self):
        """Sets the base join information for this collection"""
        self._joins = {}
        self._aliases = set()
        self._aliases.add(self.table_name)

    def next_alias(self):
        i = len(self._aliases)
        while True:
            alias = "nav%i" % i
            if alias in self._aliases:
                i += 1
            else:
                break
        return alias

    def add_join(self, name):
        """Adds a join to this collection

        name
            The name of the navigation property to traverse.

        The return result is the alias name to use for the target table.

        As per the specification, the target must have multiplicity 1 or
        0..1."""
        if self._joins is None:
            self.reset_joins()
        elif name in self._joins:
            return self._joins[name][0]
        alias = self.next_alias()
        src_multiplicity, dst_multiplicity = \
            self.entity_set.get_multiplicity(name)
        if dst_multiplicity not in (edm.Multiplicity.ZeroToOne,
                                    edm.Multiplicity.One):
            # we can't join on this navigation property
            raise NotImplementedError(
                "NavigationProperty %s.%s cannot be used in an expression" %
                (self.entity_set.name, name))
        fk_mapping = self.container.fk_table[self.entity_set.name]
        link_end = self.entity_set.navigation[name]
        target_set = self.entity_set.get_target(name)
        target_table_name = self.container.mangled_names[(target_set.name, )]
        join = []
        if link_end in fk_mapping:
            # we own the foreign key
            for key_name in target_set.keys:
                join.append(
                    '%s.%s=%s.%s' %
                    (self.table_name, self.container.mangled_names[
                        (self.entity_set.name, link_end.parent.name,
                         key_name)],
                     alias,
                     self.container.mangled_names[
                        (target_set.name, key_name)]))
            join = ' LEFT JOIN %s AS %s ON %s' % (
                target_table_name, alias, ' AND '.join(join))
            self._joins[name] = (alias, join)
            self._aliases.add(alias)
        else:
            target_fk_mapping = self.container.fk_table[target_set.name]
            if link_end.otherEnd in target_fk_mapping:
                # target table has the foreign key
                for key_name in self.entity_set.keys:
                    join.append(
                        '%s.%s=%s.%s' %
                        (self.table_name, self.container.mangled_names[
                            (self.entity_set.name, key_name)],
                         alias,
                         self.container.mangled_names[
                            (target_set.name,
                             link_end.parent.name, key_name)]))
                join = ' LEFT JOIN %s AS %s ON %s' % (
                    target_table_name, alias, ' AND '.join(join))
                self._joins[name] = (alias, join)
                self._aliases.add(alias)
            else:
                # relation is in an auxiliary table
                src_set, src_name, dst_set, dst_name, ukeys = \
                    self.container.aux_table[link_end.parent.name]
                if self.entity_set is src_set:
                    name2 = dst_name
                else:
                    name2 = src_name
                aux_table_name = self.container.mangled_names[(
                    link_end.parent.name, )]
                for key_name in self.entity_set.keys:
                    join.append(
                        '%s.%s=%s.%s' %
                        (self.table_name, self.container.mangled_names[
                            (self.entity_set.name, key_name)],
                         alias, self.container.mangled_names[
                            (link_end.parent.name, self.entity_set.name,
                             name, key_name)]))
                join = ' LEFT JOIN %s AS %s ON %s' % (
                    aux_table_name, alias, ' AND '.join(join))
                self._aliases.add(alias)
                join2 = []
                alias2 = self.next_alias()
                for key_name in target_set.keys:
                    join2.append(
                        '%s.%s=%s.%s' %
                        (alias, self.container.mangled_names[
                            (link_end.parent.name, target_set.name,
                             name2, key_name)],
                         alias2, self.container.mangled_names[
                            (target_set.name, key_name)]))
                join2 = ' LEFT JOIN %s AS %s ON %s' % (
                    target_table_name, alias2, ' AND '.join(join2))
                self._aliases.add(alias2)
                alias = alias2
                self._joins[name] = (alias, join + join2)
        return alias

    def join_clause(self):
        """A utility method to return the JOIN clause.

        Defaults to an empty expression."""
        if self._joins is None:
            self.reset_joins()
        return ''.join(x[1] for x in dict_values(self._joins))

    def set_filter(self, filter):
        self._joins = None
        self.filter = filter
        self.set_page(None)
        self._sqlLen = None
        self._sqlGen = None

    def where_clause(
            self,
            entity,
            params,
            use_filter=True,
            use_skip=False,
            null_cols=()):
        """A utility method that generates the WHERE clause for a query

        entity
                An optional entity within this collection that is the focus
                of this query.  If not None the resulting WHERE clause will
                restrict the query to this entity only.

        params
                The :py:class:`SQLParams` object to add parameters to.

        use_filter
                Defaults to True, indicates if this collection's filter should
                be added to the WHERE clause.

        use_skip
                Defaults to False, indicates if the skiptoken should be used
                in the where clause.  If True then the query is limited to
                entities appearing after the skiptoken's value (see below).

        null_cols
                An iterable of mangled column names that must be NULL (defaults
                to an empty tuple).  This argument is used during updates to
                prevent the replacement of non-NULL foreign keys.

        The operation of the skiptoken deserves some explanation.  When in
        play the skiptoken contains the last value of the order expression
        returned.  The order expression always uses the keys to ensure
        unambiguous ordering.  The clause added is best served with an
        example.  If an entity has key K and an order expression such
        as "tolower(Name) desc" then the query will contain
        something like::

                SELECT K, Nname, DOB, LOWER(Name) AS o_1, K ....
                        WHERE (o_1 < ? OR (o_1 = ? AND K > ?))

        The values from the skiptoken will be passed as parameters."""
        where = []
        if entity is not None:
            self.where_entity_clause(where, entity, params)
        if self.filter is not None and use_filter:
            # use_filter option adds the current filter too
            where.append('(' + self.sql_expression(self.filter, params) + ')')
        if self.skiptoken is not None and use_skip:
            self.where_skiptoken_clause(where, params)
        for nullCol in null_cols:
            where.append('%s IS NULL' % nullCol)
        if where:
            return ' WHERE ' + ' AND '.join(where)
        else:
            return ''

    def where_entity_clause(self, where, entity, params):
        """Adds the entity constraint expression to a list of SQL expressions.

        where
                The list to append the entity expression to.

        entity
                An expression is added to restrict the query to this entity"""
        for k, v in dict_items(entity.key_dict()):
            where.append(
                '%s.%s=%s' %
                (self.table_name,
                 self.container.mangled_names[(self.entity_set.name, k)],
                 params.add_param(self.container.prepare_sql_value(v))))

    def where_skiptoken_clause(self, where, params):
        """Adds the entity constraint expression to a list of SQL expressions.

        where
                The list to append the skiptoken expression to."""
        skip_expression = []
        i = ket = 0
        while True:
            if self.orderby and i < len(self.orderby):
                oname = None
                expression, dir = self.orderby[i]
            else:
                oname, dir = self.orderNames[i]
            v = self.skiptoken[i]
            op = ">" if dir > 0 else "<"
            if oname is None:
                o_expression = self.sql_expression(expression, params, op)
            else:
                o_expression = oname
            skip_expression.append(
                "(%s %s %s" %
                (o_expression,
                 op,
                 params.add_param(
                     self.container.prepare_sql_value(v))))
            ket += 1
            i += 1
            if i < len(self.orderNames):
                # more to come
                if oname is None:
                    # remake the expression
                    o_expression = self.sql_expression(expression, params, '=')
                skip_expression.append(
                    " OR (%s = %s AND " %
                    (o_expression, params.add_param(
                        self.container.prepare_sql_value(v))))
                ket += 1
                continue
            else:
                skip_expression.append(")" * ket)
                break
        where.append(''.join(skip_expression))

    def set_orderby(self, orderby):
        """Sets the orderby rules for this collection.

        We override the default implementation to calculate a list
        of field name aliases to use in ordered queries.  For example,
        if the orderby expression is "tolower(Name) desc" then each SELECT
        query will be generated with an additional expression, e.g.::

                SELECT ID, Name, DOB, LOWER(Name) AS o_1 ...
                    ORDER BY o_1 DESC, ID ASC

        The name "o_1" is obtained from the name mangler using the tuple::

                (entity_set.name,'o_1')

        Subsequent order expressions have names 'o_2', 'o_3', etc.

        Notice that regardless of the ordering expression supplied the
        keys are always added to ensure that, when an ordering is
        required, a defined order results even at the expense of some
        redundancy."""
        self.orderby = orderby
        self.set_page(None)
        self.orderNames = []
        if self.orderby is not None:
            oi = 0
            for expression, direction in self.orderby:
                oi = oi + 1
                oname = "o_%i" % oi
                oname = self.container.mangled_names.get(
                    (self.entity_set.name, oname), oname)
                self.orderNames.append((oname, direction))
        for key in self.entity_set.keys:
            mangled_name = self.container.mangled_names[
                (self.entity_set.name, key)]
            mangled_name = "%s.%s" % (self.table_name, mangled_name)
            self.orderNames.append((mangled_name, 1))
        self._sqlGen = None

    def orderby_clause(self):
        """A utility method to return the orderby clause.

        params
                The :py:class:`SQLParams` object to add parameters to."""
        if self.orderNames:
            orderby = []
            for expression, direction in self.orderNames:
                orderby.append(
                    "%s %s" % (expression, "DESC" if direction < 0 else "ASC"))
            return ' ORDER BY ' + ", ".join(orderby) + ' '
        else:
            return ''

    def orderby_cols(self, column_names, params, force_order=False):
        """A utility to add the column names and aliases for the ordering.

        column_names
            A list of SQL column name/alias expressions

        params
            The :py:class:`SQLParams` object to add parameters to.

        force_order
            Forces the addition of an ordering by key if an orderby
            expression has not been set."""
        oname_index = 0
        if self.orderby is not None:
            for expression, direction in self.orderby:
                oname, odir = self.orderNames[oname_index]
                oname_index += 1
                sql_expression = self.sql_expression(expression, params)
                column_names.append("%s AS %s" % (sql_expression, oname))
        if self.orderby is not None or force_order:
            # add the remaining names (which are just the keys)
            while oname_index < len(self.orderNames):
                oname, odir = self.orderNames[oname_index]
                oname_index += 1
                column_names.append(oname)

    def _mangle_name(self, source_path, prefix=True):
        mangled_name = self.container.mangled_names[source_path]
        if prefix:
            mangled_name = "%s.%s" % (self.table_name, mangled_name)
        return mangled_name

    def insert_fields(self, entity):
        """A generator for inserting mangled property names and values.

        entity
            Any instance of :py:class:`~pyslet.odata2.csdl.Entity`

        The yielded values are tuples of (mangled field name,
        :py:class:`~pyslet.odata2.csdl.SimpleValue` instance).

        Read only fields are never generated, even if they are keys.
        This allows automatically generated keys to be used and also
        covers the more esoteric use case where a foreign key constraint
        exists on the primary key (or part thereof) - in the latter case
        the relationship should be marked as required to prevent
        unexpected constraint violations.

        Otherwise, only selected fields are yielded so if you attempt to
        insert a value without selecting the key fields you can expect a
        constraint violation unless the key is read only."""
        for k, v in entity.data_items():
            source_path = (self.entity_set.name, k)
            if (source_path not in self.container.ro_names and
                    entity.is_selected(k)):
                if isinstance(v, edm.SimpleValue):
                    yield self._mangle_name(source_path, prefix=False), v
                else:
                    for sub_path, fv in self._complex_field_generator(v):
                        source_path = tuple([self.entity_set.name, k] +
                                            sub_path)
                        yield self._mangle_name(source_path, prefix=False), fv

    def auto_fields(self, entity):
        """A generator for selecting auto mangled property names and values.

        entity
            Any instance of :py:class:`~pyslet.odata2.csdl.Entity`

        The yielded values are tuples of (mangled field name,
        :py:class:`~pyslet.odata2.csdl.SimpleValue` instance).

        Only fields that are read only are yielded with the caveat that
        they must also be either selected or keys.  The purpose of this
        method is to assist with reading back automatically generated
        field values after an insert or update."""
        keys = entity.entity_set.keys
        for k, v in entity.data_items():
            source_path = (self.entity_set.name, k)
            if (source_path in self.container.ro_names and (
                    entity.is_selected(k) or k in keys)):
                if isinstance(v, edm.SimpleValue):
                    yield self._mangle_name(source_path), v
                else:
                    for sub_path, fv in self._complex_field_generator(v):
                        source_path = tuple([self.entity_set.name, k] +
                                            sub_path)
                        yield self._mangle_name(source_path), fv

    def key_fields(self, entity):
        """A generator for selecting mangled key names and values.

        entity
            Any instance of :py:class:`~pyslet.odata2.csdl.Entity`

        The yielded values are tuples of (mangled field name,
        :py:class:`~pyslet.odata2.csdl.SimpleValue` instance).
        Only the keys fields are yielded."""
        for k in entity.entity_set.keys:
            v = entity[k]
            source_path = (self.entity_set.name, k)
            yield self._mangle_name(source_path), v

    def select_fields(self, entity, prefix=True):
        """A generator for selecting mangled property names and values.

        entity
            Any instance of :py:class:`~pyslet.odata2.csdl.Entity`

        The yielded values are tuples of (mangled field name,
        :py:class:`~pyslet.odata2.csdl.SimpleValue` instance).
        Only selected fields are yielded with the caveat that the keys
        are always selected."""
        keys = entity.entity_set.keys
        for k, v in entity.data_items():
            source_path = (self.entity_set.name, k)
            if (k in keys or entity.is_selected(k)):
                if isinstance(v, edm.SimpleValue):
                    yield self._mangle_name(source_path, prefix), v
                else:
                    for sub_path, fv in self._complex_field_generator(v):
                        source_path = tuple([self.entity_set.name, k] +
                                            sub_path)
                        yield self._mangle_name(source_path, prefix), fv

    def update_fields(self, entity):
        """A generator for updating mangled property names and values.

        entity
            Any instance of :py:class:`~pyslet.odata2.csdl.Entity`

        The yielded values are tuples of (mangled field name,
        :py:class:`~pyslet.odata2.csdl.SimpleValue` instance).

        Neither read only fields nor key fields are generated.

        For SQL variants that support default values on columns natively
        unselected items are suppressed and are returned instead in
        name-only form by :meth:`default_fields`.

        For SQL variants that don't support defaut values, unselected
        items are yielded here but with either the default value
        specified in the metadata schema definition of the corresponding
        property or as NULL.

        This method is used to implement OData's PUT semantics.  See
        :py:meth:`merge_fields` for an alternative."""
        keys = entity.entity_set.keys
        for k, v in entity.data_items():
            source_path = (self.entity_set.name, k)
            if k in keys or source_path in self.container.ro_names:
                continue
            if not entity.is_selected(k):
                if self.DEFAULT_VALUE:
                    continue
                else:
                    v.set_default_value()
            if isinstance(v, edm.SimpleValue):
                yield self._mangle_name(source_path, prefix=False), v
            else:
                for sub_path, fv in self._complex_field_generator(v):
                    source_path = tuple([self.entity_set.name, k] +
                                        sub_path)
                    yield self._mangle_name(source_path, prefix=False), fv

    def merge_fields(self, entity):
        """A generator for merging mangled property names and values.

        entity
            Any instance of :py:class:`~pyslet.odata2.csdl.Entity`

        The yielded values are tuples of (mangled field name,
        :py:class:`~pyslet.odata2.csdl.SimpleValue` instance).

        Neither read only fields, keys nor unselected fields are
        generated. All other fields are yielded implementing OData's
        MERGE semantics.  See
        :py:meth:`update_fields` for an alternative."""
        keys = entity.entity_set.keys
        for k, v in entity.data_items():
            source_path = (self.entity_set.name, k)
            if (k in keys or
                    source_path in self.container.ro_names or
                    not entity.is_selected(k)):
                continue
            if isinstance(v, edm.SimpleValue):
                yield self._mangle_name(source_path, prefix=False), v
            else:
                for sub_path, fv in self._complex_field_generator(v):
                    source_path = tuple([self.entity_set.name, k] +
                                        sub_path)
                    yield self._mangle_name(source_path, prefix=False), fv

    def default_fields(self, entity):
        """A generator for mangled property names.

        entity
            Any instance of :py:class:`~pyslet.odata2.csdl.Entity`

        The yielded values are the mangled field names that should be
        set to default values.  Neither read only fields, keys nor
        selected fields are generated."""
        if not self.DEFAULT_VALUE:
            # don't yield anything
            return
        keys = entity.entity_set.keys
        for k, v in entity.data_items():
            source_path = (self.entity_set.name, k)
            if (k in keys or
                    source_path in self.container.ro_names or
                    entity.is_selected(k)):
                continue
            if isinstance(v, edm.SimpleValue):
                yield self._mangle_name(source_path, prefix=False)
            else:
                for sub_path, fv in self._complex_field_generator(v):
                    source_path = tuple([self.entity_set.name, k] +
                                        sub_path)
                    yield self._mangle_name(source_path, prefix=False)

    def _complex_field_generator(self, ct):
        for k, v in ct.iteritems():
            if isinstance(v, edm.SimpleValue):
                yield [k], v
            else:
                for source_path, fv in self._complex_field_generator(v):
                    yield [k] + source_path, fv

    def stream_field(self, entity, prefix=True):
        """Returns information for selecting the stream ID.

        entity
            Any instance of :py:class:`~pyslet.odata2.csdl.Entity`

        Returns a tuples of (mangled field name,
        :py:class:`~pyslet.odata2.csdl.SimpleValue` instance)."""
        source_path = (self.entity_set.name, '_value')
        return self._mangle_name(source_path, prefix), \
            edm.EDMValue.from_type(edm.SimpleType.Int64)

    SQLBinaryExpressionMethod = {}
    SQLCallExpressionMethod = {}

    def sql_expression(self, expression, params, context="AND"):
        """Converts an expression into a SQL expression string.

        expression
                A :py:class:`pyslet.odata2.core.CommonExpression` instance.

        params
                A :py:class:`SQLParams` object of the appropriate type for
                this database connection.

        context
                A string containing the SQL operator that provides the
                context in which the expression is being converted, defaults
                to 'AND'. This is used to determine if the resulting
                expression must be bracketed or not.  See
                :py:meth:`sql_bracket` for a useful utility function to
                illustrate this.

        This method is basically a grand dispatcher that sends calls to
        other node-specific methods with similar signatures.  The effect
        is to traverse the entire tree rooted at *expression*.

        The result is a string containing the parameterized expression
        with appropriate values added to the *params* object *in the same
        sequence* that they appear in the returned SQL expression.

        When creating derived classes to implement database-specific
        behaviour you should override the individual evaluation methods
        rather than this method.  All related methods have the same
        signature.

        Where methods are documented as having no default implementation,
        NotImplementedError is raised."""
        if isinstance(expression, core.UnaryExpression):
            raise NotImplementedError
        elif isinstance(expression, core.BinaryExpression):
            return getattr(
                self,
                self.SQLBinaryExpressionMethod[
                    expression.operator])(
                expression,
                params,
                context)
        elif isinstance(expression, UnparameterizedLiteral):
            return self.container.ParamsClass.escape_literal(
                to_text(expression.value))
        elif isinstance(expression, core.LiteralExpression):
            return params.add_param(
                self.container.prepare_sql_value(
                    expression.value))
        elif isinstance(expression, core.PropertyExpression):
            try:
                p = self.entity_set.entityType[expression.name]
                if isinstance(p, edm.Property):
                    if p.complexType is None:
                        field_name = self.container.mangled_names[
                            (self.entity_set.name, expression.name)]
                        return "%s.%s" % (self.table_name, field_name)
                    else:
                        raise core.EvaluationError(
                            "Unqualified property %s "
                            "must refer to a simple type" %
                            expression.name)
            except KeyError:
                raise core.EvaluationError(
                    "Property %s is not declared" % expression.name)
        elif isinstance(expression, core.CallExpression):
            return getattr(
                self,
                self.SQLCallExpressionMethod[
                    expression.method])(
                expression,
                params,
                context)

    def sql_bracket(self, query, context, operator):
        """A utility method for bracketing a SQL query.

        query
                The query string

        context
                A string representing the SQL operator that defines the
                context in which the query is to placed.  E.g., 'AND'

        operator
                The dominant operator in the query.

        This method is used by operator-specific conversion methods.
        The query is not parsed, it is merely passed in as a string to be
        bracketed (or not) depending on the values of *context* and
        *operator*.

        The implementation is very simple, it checks the precedence of
        *operator* in *context* and returns *query* bracketed if
        necessary::

                collection.sql_bracket("Age+3","*","+")=="(Age+3)"
                collection.sql_bracket("Age*3","+","*")=="Age*3" """
        if SQLOperatorPrecedence[context] > SQLOperatorPrecedence[operator]:
            return "(%s)" % query
        else:
            return query

    def sql_expression_member(self, expression, params, context):
        """Converts a member expression, e.g., Address/City

        This implementation does not support the use of navigation
        properties but does support references to complex properties.

        It outputs the mangled name of the property, qualified by the
        table name."""
        name_list = self._calculate_member_field_name(expression)
        context_def = self.entity_set.entityType
        depth = 0
        table_name = self.table_name
        entity_set = self.entity_set
        path = []
        for name in name_list:
            if context_def is None:
                raise core.EvaluationError("Property %s is not declared" %
                                           '/'.join(name_list))
            p = context_def[name]
            if isinstance(p, edm.Property):
                path.append(name)
                if p.complexType is not None:
                    context_def = p.complexType
                else:
                    context_def = None
            elif isinstance(p, edm.NavigationProperty):
                if depth > 0:
                    raise NotImplementedError(
                        "Member expression exceeds maximum navigation depth")
                else:
                    table_name = self.add_join(name)
                    context_def = p.to_end.entityType
                    depth += 1
                    path = []
                    entity_set = entity_set.get_target(name)
        # the result must be a simple property, so context_def must not be None
        if context_def is not None:
            raise core.EvaluationError(
                "Property %s does not reference a primitive type" %
                '/'.join(name_list))
        field_name = self.container.mangled_names[
            tuple([entity_set.name] + path)]
        return "%s.%s" % (table_name, field_name)

    def _calculate_member_field_name(self, expression):
        if isinstance(expression, core.PropertyExpression):
            return [expression.name]
        elif (isinstance(expression, core.BinaryExpression) and
                expression.operator == core.Operator.member):
            return (
                self._calculate_member_field_name(expression.operands[0]) +
                self._calculate_member_field_name(expression.operands[1]))
        else:
            raise core.EvaluationError("Unexpected use of member expression")

    def sql_expression_cast(self, expression, params, context):
        """Converts the cast expression: no default implementation"""
        raise NotImplementedError

    def sql_expression_generic_binary(
            self,
            expression,
            params,
            context,
            operator):
        """A utility method for implementing binary operator conversion.

        The signature of the basic :py:meth:`sql_expression` is extended
        to include an *operator* argument, a string representing the
        (binary) SQL operator corresponding to the expression object."""
        query = []
        query.append(
            self.sql_expression(expression.operands[0], params, operator))
        query.append(' ')
        query.append(operator)
        query.append(' ')
        query.append(
            self.sql_expression(expression.operands[1], params, operator))
        return self.sql_bracket(''.join(query), context, operator)

    def sql_expression_mul(self, expression, params, context):
        """Converts the mul expression: maps to SQL "*" """
        return self.sql_expression_generic_binary(
            expression,
            params,
            context,
            '*')

    def sql_expression_div(self, expression, params, context):
        """Converts the div expression: maps to SQL "/" """
        return self.sql_expression_generic_binary(
            expression,
            params,
            context,
            '/')

    def sql_expression_mod(self, expression, params, context):
        """Converts the mod expression: no default implementation"""
        raise NotImplementedError

    def sql_expression_add(self, expression, params, context):
        """Converts the add expression: maps to SQL "+" """
        return self.sql_expression_generic_binary(
            expression,
            params,
            context,
            '+')

    def sql_expression_sub(self, expression, params, context):
        """Converts the sub expression: maps to SQL "-" """
        return self.sql_expression_generic_binary(
            expression,
            params,
            context,
            '-')

    def sql_expression_lt(self, expression, params, context):
        """Converts the lt expression: maps to SQL "<" """
        return self.sql_expression_generic_binary(
            expression,
            params,
            context,
            '<')

    def sql_expression_gt(self, expression, params, context):
        """Converts the gt expression: maps to SQL ">" """
        return self.sql_expression_generic_binary(
            expression,
            params,
            context,
            '>')

    def sql_expression_le(self, expression, params, context):
        """Converts the le expression: maps to SQL "<=" """
        return self.sql_expression_generic_binary(
            expression,
            params,
            context,
            '<=')

    def sql_expression_ge(self, expression, params, context):
        """Converts the ge expression: maps to SQL ">=" """
        return self.sql_expression_generic_binary(
            expression,
            params,
            context,
            '>=')

    def sql_expression_isof(self, expression, params, context):
        """Converts the isof expression: no default implementation"""
        raise NotImplementedError

    def sql_expression_eq(self, expression, params, context):
        """Converts the eq expression: maps to SQL "=" """
        return self.sql_expression_generic_binary(
            expression,
            params,
            context,
            '=')

    def sql_expression_ne(self, expression, params, context):
        """Converts the ne expression: maps to SQL "<>" """
        return self.sql_expression_generic_binary(
            expression,
            params,
            context,
            '<>')

    def sql_expression_and(self, expression, params, context):
        """Converts the and expression: maps to SQL "AND" """
        return self.sql_expression_generic_binary(
            expression,
            params,
            context,
            'AND')

    def sql_expression_or(self, expression, params, context):
        """Converts the or expression: maps to SQL "OR" """
        return self.sql_expression_generic_binary(
            expression,
            params,
            context,
            'OR')

    def sql_expression_endswith(self, expression, params, context):
        """Converts the endswith function: maps to "op[0] LIKE '%'+op[1]"

        This is implemented using the concatenation operator"""
        percent = edm.SimpleValue.from_type(edm.SimpleType.String)
        percent.set_from_value("'%'")
        percent = UnparameterizedLiteral(percent)
        concat = core.CallExpression(core.Method.concat)
        concat.operands.append(percent)
        concat.operands.append(expression.operands[1])
        query = []
        query.append(
            self.sql_expression(expression.operands[0], params, 'LIKE'))
        query.append(" LIKE ")
        query.append(self.sql_expression(concat, params, 'LIKE'))
        return self.sql_bracket(''.join(query), context, 'LIKE')

    def sql_expression_indexof(self, expression, params, context):
        """Converts the indexof method: maps to POSITION( op[0] IN op[1] )"""
        query = ["POSITION("]
        query.append(self.sql_expression(expression.operands[0], params, ','))
        query.append(" IN ")
        query.append(self.sql_expression(expression.operands[1], params, ','))
        query.append(")")
        return ''.join(query)

    def sql_expression_replace(self, expression, params, context):
        """Converts the replace method: no default implementation"""
        raise NotImplementedError

    def sql_expression_startswith(self, expression, params, context):
        """Converts the startswith function: maps to "op[0] LIKE op[1]+'%'"

        This is implemented using the concatenation operator"""
        percent = edm.SimpleValue.from_type(edm.SimpleType.String)
        percent.set_from_value("'%'")
        percent = UnparameterizedLiteral(percent)
        concat = core.CallExpression(core.Method.concat)
        concat.operands.append(expression.operands[1])
        concat.operands.append(percent)
        query = []
        query.append(
            self.sql_expression(expression.operands[0], params, 'LIKE'))
        query.append(" LIKE ")
        query.append(self.sql_expression(concat, params, 'LIKE'))
        return self.sql_bracket(''.join(query), context, 'LIKE')

    def sql_expression_tolower(self, expression, params, context):
        """Converts the tolower method: maps to LOWER function"""
        return "LOWER(%s)" % self.sql_expression(
            expression.operands[0],
            params,
            ',')

    def sql_expression_toupper(self, expression, params, context):
        """Converts the toupper method: maps to UCASE function"""
        return "UPPER(%s)" % self.sql_expression(
            expression.operands[0],
            params,
            ',')

    def sql_expression_trim(self, expression, params, context):
        """Converts the trim method: maps to TRIM function"""
        return "TRIM(%s)" % self.sql_expression(
            expression.operands[0],
            params,
            ',')

    def sql_expression_substring(self, expression, params, context):
        """Converts the substring method

        maps to SUBSTRING( op[0] FROM op[1] [ FOR op[2] ] )"""
        query = ["SUBSTRING("]
        query.append(self.sql_expression(expression.operands[0], params, ','))
        query.append(" FROM ")
        query.append(self.sql_expression(expression.operands[1], params, ','))
        if len(expression.operands) > 2:
            query.append(" FOR ")
            query.append(
                self.sql_expression(expression.operands[2], params, ','))
        query.append(")")
        return ''.join(query)

    def sql_expression_substringof(self, expression, params, context):
        """Converts the substringof function

        maps to "op[1] LIKE '%'+op[0]+'%'"

        To do this we need to invoke the concatenation operator.

        This method has been poorly defined in OData with the parameters
        being switched between versions 2 and 3.  It is being withdrawn
        as a result and replaced with contains in OData version 4.  We
        follow the version 3 convention here of "first parameter in the
        second parameter" which fits better with the examples and with
        the intuitive meaning::

                substringof(A,B) == A in B"""
        percent = edm.SimpleValue.from_type(edm.SimpleType.String)
        percent.set_from_value("'%'")
        percent = UnparameterizedLiteral(percent)
        rconcat = core.CallExpression(core.Method.concat)
        rconcat.operands.append(expression.operands[0])
        rconcat.operands.append(percent)
        lconcat = core.CallExpression(core.Method.concat)
        lconcat.operands.append(percent)
        lconcat.operands.append(rconcat)
        query = []
        query.append(
            self.sql_expression(expression.operands[1], params, 'LIKE'))
        query.append(" LIKE ")
        query.append(self.sql_expression(lconcat, params, 'LIKE'))
        return self.sql_bracket(''.join(query), context, 'LIKE')

    def sql_expression_concat(self, expression, params, context):
        """Converts the concat method: maps to ||"""
        query = []
        query.append(self.sql_expression(expression.operands[0], params, '*'))
        query.append(' || ')
        query.append(self.sql_expression(expression.operands[1], params, '*'))
        return self.sql_bracket(''.join(query), context, '*')

    def sql_expression_length(self, expression, params, context):
        """Converts the length method: maps to CHAR_LENGTH( op[0] )"""
        return "CHAR_LENGTH(%s)" % self.sql_expression(
            expression.operands[0],
            params,
            ',')

    def sql_expression_year(self, expression, params, context):
        """Converts the year method: maps to EXTRACT(YEAR FROM op[0])"""
        return "EXTRACT(YEAR FROM %s)" % self.sql_expression(
            expression.operands[0],
            params,
            ',')

    def sql_expression_month(self, expression, params, context):
        """Converts the month method: maps to EXTRACT(MONTH FROM op[0])"""
        return "EXTRACT(MONTH FROM %s)" % self.sql_expression(
            expression.operands[0],
            params,
            ',')

    def sql_expression_day(self, expression, params, context):
        """Converts the day method: maps to EXTRACT(DAY FROM op[0])"""
        return "EXTRACT(DAY FROM %s)" % self.sql_expression(
            expression.operands[0],
            params,
            ',')

    def sql_expression_hour(self, expression, params, context):
        """Converts the hour method: maps to EXTRACT(HOUR FROM op[0])"""
        return "EXTRACT(HOUR FROM %s)" % self.sql_expression(
            expression.operands[0],
            params,
            ',')

    def sql_expression_minute(self, expression, params, context):
        """Converts the minute method: maps to EXTRACT(MINUTE FROM op[0])"""
        return "EXTRACT(MINUTE FROM %s)" % self.sql_expression(
            expression.operands[0],
            params,
            ',')

    def sql_expression_second(self, expression, params, context):
        """Converts the second method: maps to EXTRACT(SECOND FROM op[0])"""
        return "EXTRACT(SECOND FROM %s)" % self.sql_expression(
            expression.operands[0],
            params,
            ',')

    def sql_expression_round(self, expression, params, context):
        """Converts the round method: no default implementation"""
        raise NotImplementedError

    def sql_expression_floor(self, expression, params, context):
        """Converts the floor method: no default implementation"""
        raise NotImplementedError

    def sql_expression_ceiling(self, expression, params, context):
        """Converts the ceiling method: no default implementation"""
        raise NotImplementedError


SQLCollectionBase.SQLCallExpressionMethod = {
    core.Method.endswith: 'sql_expression_endswith',
    core.Method.indexof: 'sql_expression_indexof',
    core.Method.replace: 'sql_expression_replace',
    core.Method.startswith: 'sql_expression_startswith',
    core.Method.tolower: 'sql_expression_tolower',
    core.Method.toupper: 'sql_expression_toupper',
    core.Method.trim: 'sql_expression_trim',
    core.Method.substring: 'sql_expression_substring',
    core.Method.substringof: 'sql_expression_substringof',
    core.Method.concat: 'sql_expression_concat',
    core.Method.length: 'sql_expression_length',
    core.Method.year: 'sql_expression_year',
    core.Method.month: 'sql_expression_month',
    core.Method.day: 'sql_expression_day',
    core.Method.hour: 'sql_expression_hour',
    core.Method.minute: 'sql_expression_minute',
    core.Method.second: 'sql_expression_second',
    core.Method.round: 'sql_expression_round',
    core.Method.floor: 'sql_expression_floor',
    core.Method.ceiling: 'sql_expression_ceiling'
}

SQLCollectionBase.SQLBinaryExpressionMethod = {
    core.Operator.member: 'sql_expression_member',
    core.Operator.cast: 'sql_expression_cast',
    core.Operator.mul: 'sql_expression_mul',
    core.Operator.div: 'sql_expression_div',
    core.Operator.mod: 'sql_expression_mod',
    core.Operator.add: 'sql_expression_add',
    core.Operator.sub: 'sql_expression_sub',
    core.Operator.lt: 'sql_expression_lt',
    core.Operator.gt: 'sql_expression_gt',
    core.Operator.le: 'sql_expression_le',
    core.Operator.ge: 'sql_expression_ge',
    core.Operator.isof: 'sql_expression_isof',
    core.Operator.eq: 'sql_expression_eq',
    core.Operator.ne: 'sql_expression_ne',
    core.Operator.boolAnd: 'sql_expression_and',
    core.Operator.boolOr: 'sql_expression_or'
}


class SQLEntityCollection(SQLCollectionBase):

    """Represents a collection of entities from an :py:class:`EntitySet`.

    This class is the heart of the SQL implementation of the API,
    constructing and executing queries to implement the core methods
    from :py:class:`pyslet.odata2.csdl.EntityCollection`."""

    def insert_entity(self, entity):
        """Inserts *entity* into the collection.

        We override this method, rerouting it to a SQL-specific
        implementation that takes additional arguments."""
        self.insert_entity_sql(entity)

    def new_stream(self, src, sinfo=None, key=None):
        e = self.new_entity()
        if key is None:
            e.auto_key()
        else:
            e.set_key(key)
        if sinfo is None:
            sinfo = core.StreamInfo()
        etag = e.etag_values()
        if len(etag) == 1 and isinstance(etag[0], edm.BinaryValue):
            h = hashlib.sha256()
            etag = etag[0]
        else:
            h = None
        c, v = self.stream_field(e, prefix=False)
        if self.container.streamstore:
            # spool the data into the store and store the stream key
            estream = self.container.streamstore.new_stream(sinfo.type,
                                                            sinfo.created)
            with self.container.streamstore.open_stream(estream, 'w') as dst:
                sinfo.size, sinfo.md5 = self._copy_src(src, dst, sinfo.size, h)
            if sinfo.modified is not None:
                # force modified date based on input
                estream['modified'].set_from_value(
                    sinfo.modified.shift_zone(0))
                estream.commit()
            v.set_from_value(estream.key())
        else:
            raise NotImplementedError
        if h is not None:
            etag.set_from_value(h.digest())
        transaction = SQLTransaction(self.container, self.connection)
        try:
            transaction.begin()
            # now try the insert and loop with random keys if required
            for i in range3(100):
                try:
                    self.insert_entity_sql(e, transaction=transaction)
                    break
                except edm.ConstraintError:
                    # try a different key
                    e.auto_key()
            if not e.exists:
                # give up - we can't insert anything
                logging.error("Failed to find an unused key in %s "
                              "after 100 attempts", e.entity_set.name)
                raise edm.SQLError("Auto-key failure")
            # finally, store the stream value for the entity
            query = ['UPDATE ', self.table_name, ' SET ']
            params = self.container.ParamsClass()
            query.append(
                "%s=%s" %
                (c, params.add_param(self.container.prepare_sql_value(v))))
            query.append(' WHERE ')
            where = []
            for k, kv in dict_items(e.key_dict()):
                where.append(
                    '%s=%s' %
                    (self.container.mangled_names[(self.entity_set.name, k)],
                     params.add_param(self.container.prepare_sql_value(kv))))
            query.append(' AND '.join(where))
            query = ''.join(query)
            logging.info("%s; %s", query, to_text(params.params))
            transaction.execute(query, params)
        except Exception as e:
            # we allow the stream store to re-use the same database but
            # this means we can't transact on both at once (from the
            # same thread) - settle for logging at the moment
            # self.container.streamstore.delete_stream(estream)
            logging.error("Orphan stream created %s[%i]",
                          estream.entity_set.name, estream.key())
            transaction.rollback(e)
        finally:
            transaction.close()
        return e

    def insert_entity_sql(
            self,
            entity,
            from_end=None,
            fk_values=None,
            transaction=None):
        """Inserts *entity* into the collection.

        This method is not designed to be overridden by other
        implementations but it does extend the default functionality for
        a more efficient implementation and to enable better
        transactional processing. The additional parameters are
        documented here.

        from_end
                An optional :py:class:`pyslet.odata2.csdl.AssociationSetEnd`
                bound to this entity set.  If present, indicates that this
                entity is being inserted as part of a single transaction
                involving an insert or update to the other end of the
                association.

                This suppresses any check for a required link via this
                association (as it is assumed that the link is present, or
                will be, in the same transaction).

        fk_values
                If the association referred to by *from_end* is represented
                by a set of foreign keys stored in this entity set's table
                (see :py:class:`SQLReverseKeyCollection`) then fk_values is
                the list of (mangled column name, value) tuples that must be
                inserted in order to create the link.

        transaction
                An optional transaction.  If present, the connection is left
                uncommitted.

        The method functions in three phases.

        1.  Process all bindings for which we hold the foreign key.
            This includes inserting new entities where deep inserts are
            being used or calculating foreign key values where links to
            existing entities have been specified on creation.

            In addition, all required links are checked and raise errors
            if no binding is present.

        2.  A simple SQL INSERT statement is executed to add the record
            to the database along with any foreign keys generated in (1)
            or passed in *fk_values*.

        3.  Process all remaining bindings.  Although we could do this
            using the
            :py:meth:`~pyslet.odata2.csdl.DeferredValue.update_bindings`
            method of DeferredValue we handle this directly to retain
            transactional integrity (where supported).

            Links to existing entities are created using the insert_link
            method available on the SQL-specific
            :py:class:`SQLNavigationCollection`.

            Deep inserts are handled by a recursive call to this method.
            After step 1, the only bindings that remain are (a) those
            that are stored at the other end of the link and so can be
            created by passing values for *from_end* and *fk_values* in a
            recursive call or (b) those that are stored in a separate
            table which are created by combining a recursive call and a
            call to insert_link.

        Required links are always created in step 1 because the
        overarching mapping to SQL forces such links to be represented
        as foreign keys in the source table (i.e., this table) unless
        the relationship is 1-1, in which case the link is created in
        step 3 and our database is briefly in violation of the model. If
        the underlying database API does not support transactions then
        it is possible for this state to persist resulting in an orphan
        entity or entities, i.e., entities with missing required links.
        A failed :py:meth:`rollback` call will log this condition along
        with the error that caused it."""
        if transaction is None:
            transaction = SQLTransaction(self.container, self.connection)
        if entity.exists:
            raise edm.EntityExists(str(entity.get_location()))
        # We must also go through each bound navigation property of our
        # own and add in the foreign keys for forward links.
        if fk_values is None:
            fk_values = []
        fk_mapping = self.container.fk_table[self.entity_set.name]
        try:
            transaction.begin()
            nav_done = set()
            for link_end, nav_name in dict_items(self.entity_set.linkEnds):
                if nav_name:
                    dv = entity[nav_name]
                if (link_end.otherEnd.associationEnd.multiplicity ==
                        edm.Multiplicity.One):
                    # a required association
                    if link_end == from_end:
                        continue
                    if nav_name is None:
                        # unbound principal; can only be created from this
                        # association
                        raise edm.NavigationError(
                            "Entities in %s can only be created "
                            "from their principal" % self.entity_set.name)
                    if not dv.bindings:
                        raise edm.NavigationError(
                            "Required navigation property %s of %s "
                            "is not bound" % (nav_name, self.entity_set.name))
                aset_name = link_end.parent.name
                # if link_end is in fk_mapping it means we are keeping a
                # foreign key for this property, it may even be required but
                # either way, let's deal with it now.  We're only interested
                # in associations that are bound to navigation properties.
                if link_end not in fk_mapping or nav_name is None:
                    continue
                nullable, unique = fk_mapping[link_end]
                target_set = link_end.otherEnd.entity_set
                if len(dv.bindings) == 0:
                    # we've already checked the case where nullable is False
                    # above
                    continue
                elif len(dv.bindings) > 1:
                    raise edm.NavigationError(
                        "Unexpected error: found multiple bindings "
                        "for foreign key constraint %s" % nav_name)
                binding = dv.bindings[0]
                if not isinstance(binding, edm.Entity):
                    # just a key, grab the entity
                    with target_set.open() as targetCollection:
                        targetCollection.select_keys()
                        target_entity = targetCollection[binding]
                    dv.bindings[0] = target_entity
                else:
                    target_entity = binding
                    if not target_entity.exists:
                        # add this entity to it's base collection
                        with target_set.open() as targetCollection:
                            targetCollection.insert_entity_sql(
                                target_entity,
                                link_end.otherEnd,
                                transaction=transaction)
                # Finally, we have a target entity, add the foreign key to
                # fk_values
                for key_name in target_set.keys:
                    fk_values.append(
                        (self.container.mangled_names[
                            (self.entity_set.name,
                             aset_name,
                             key_name)],
                            target_entity[key_name]))
                nav_done.add(nav_name)
            # Step 2
            try:
                entity.key()
            except KeyError:
                # missing key on insert, auto-generate if we can
                for i in range3(100):
                    entity.auto_key()
                    if not self.test_key(entity, transaction):
                        break
            entity.set_concurrency_tokens()
            query = ['INSERT INTO ', self.table_name, ' (']
            insert_values = list(self.insert_fields(entity))
            # watch out for exposed FK fields!
            for fkname, fkv in fk_values:
                i = 0
                while i < len(insert_values):
                    iname, iv = insert_values[i]
                    if fkname == iname:
                        # fk overrides - update the entity's value
                        iv.set_from_value(fkv.value)
                        # now drop it from the list to prevent
                        # double column names
                        del insert_values[i]
                    else:
                        i += 1
            column_names, values = zip(*(insert_values + fk_values))
            query.append(", ".join(column_names))
            query.append(') VALUES (')
            params = self.container.ParamsClass()
            query.append(
                ", ".join(params.add_param(
                    self.container.prepare_sql_value(x)) for x in values))
            query.append(')')
            query = ''.join(query)
            logging.info("%s; %s", query, to_text(params.params))
            transaction.execute(query, params)
            # before we can say the entity exists we need to ensure
            # we have the key
            auto_fields = list(self.auto_fields(entity))
            if auto_fields:
                # refresh these fields in the entity
                self.get_auto(entity, auto_fields, transaction)
            entity.exists = True
            # Step 3
            for k, dv in entity.navigation_items():
                link_end = self.entity_set.navigation[k]
                if not dv.bindings:
                    continue
                elif k in nav_done:
                    dv.bindings = []
                    continue
                aset_name = link_end.parent.name
                target_set = dv.target()
                target_fk_mapping = self.container.fk_table[target_set.name]
                with dv.open() as navCollection:
                    with target_set.open() as targetCollection:
                        while dv.bindings:
                            binding = dv.bindings[0]
                            if not isinstance(binding, edm.Entity):
                                targetCollection.select_keys()
                                binding = targetCollection[binding]
                            if binding.exists:
                                navCollection.insert_link(binding, transaction)
                            else:
                                if link_end.otherEnd in target_fk_mapping:
                                    # target table has a foreign key
                                    target_fk_values = []
                                    for key_name in self.entity_set.keys:
                                        target_fk_values.append(
                                            (self.container.mangled_names[
                                                (target_set.name,
                                                 aset_name,
                                                 key_name)],
                                                entity[key_name]))
                                    targetCollection.insert_entity_sql(
                                        binding,
                                        link_end.otherEnd,
                                        target_fk_values,
                                        transaction=transaction)
                                else:
                                    # foreign keys are in an auxiliary table
                                    targetCollection.insert_entity_sql(
                                        binding,
                                        link_end.otherEnd,
                                        transaction=transaction)
                                    navCollection.insert_link(
                                        binding, transaction)
                            dv.bindings = dv.bindings[1:]
            transaction.commit()
        except (self.container.dbapi.IntegrityError,
                self.container.dbapi.InternalError) as e:
            # we might need to distinguish between a failure due to
            # fk_values or a missing key
            transaction.rollback(e, swallow=True)
            # swallow the error as this should indicate a failure at the
            # point of INSERT, fk_values may have violated a unique
            # constraint but we can't make that distinction at the
            # moment.
            raise edm.ConstraintError(
                "insert_entity failed for %s : %s" %
                (str(entity.get_location()), str(e)))
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()

    def get_auto(self, entity, auto_fields, transaction):
        params = self.container.ParamsClass()
        query = ["SELECT "]
        column_names, values = zip(*auto_fields)
        query.append(", ".join(column_names))
        query.append(' FROM ')
        query.append(self.table_name)
        # no join clause required
        if self.auto_keys:
            query.append(self.where_last(entity, params))
        else:
            query.append(self.where_clause(entity, params, use_filter=False))
        query = ''.join(query)
        try:
            transaction.begin()
            logging.info("%s; %s", query, to_text(params.params))
            transaction.execute(query, params)
            rowcount = transaction.cursor.rowcount
            row = transaction.cursor.fetchone()
            if rowcount == 0 or row is None:
                raise KeyError
            elif rowcount > 1 or (rowcount == -1 and
                                  transaction.cursor.fetchone() is not None):
                # whoops, that was unexpected
                raise SQLError(
                    "Integrity check failure, non-unique key after insert")
            for value, new_value in zip(values, row):
                self.container.read_sql_value(value, new_value)
            entity.expand(self.expand, self.select)
            transaction.commit()
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()

    def test_key(self, entity, transaction):
        params = self.container.ParamsClass()
        query = ["SELECT "]
        column_names, values = zip(*list(self.key_fields(entity)))
        query.append(", ".join(column_names))
        query.append(' FROM ')
        query.append(self.table_name)
        query.append(self.where_clause(entity, params, use_filter=False))
        query = ''.join(query)
        try:
            transaction.begin()
            logging.info("%s; %s", query, to_text(params.params))
            transaction.execute(query, params)
            rowcount = transaction.cursor.rowcount
            row = transaction.cursor.fetchone()
            if rowcount == 0 or row is None:
                result = False
            elif rowcount > 1 or (rowcount == -1 and
                                  transaction.cursor.fetchone() is not None):
                # whoops, that was unexpected
                raise SQLError(
                    "Integrity check failure, non-unique key: %s" %
                    repr(entity.key()))
            else:
                result = True
            transaction.commit()
            return result
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()

    def where_last(self, entity, params):
        raise NotImplementedError("Automatic keys not supported")

    def update_entity(self, entity, merge=True):
        """Updates *entity*

        This method follows a very similar pattern to :py:meth:`InsertMethod`,
        using a three-phase process.

        1.  Process all bindings for which we hold the foreign key.
                This includes inserting new entities where deep inserts are
                being used or calculating foreign key values where links to
                existing entities have been specified on update.

        2.  A simple SQL UPDATE statement is executed to update the
                record in the database along with any updated foreign keys
                generated in (1).

        3.  Process all remaining bindings while retaining transactional
                integrity (where supported).

                Links to existing entities are created using the insert_link
                or replace methods available on the SQL-specific
                :py:class:`SQLNavigationCollection`.  The replace method is
                used when a navigation property that links to a single
                entity has been bound.  Deep inserts are handled by calling
                insert_entity_sql before the link is created.

        The same transactional behaviour as :py:meth:`insert_entity_sql` is
        exhibited."""
        if not entity.exists:
            raise edm.NonExistentEntity(
                "Attempt to update non existent entity: " +
                str(entity.get_location()))
            fk_values = []
        fk_values = []
        fk_mapping = self.container.fk_table[self.entity_set.name]
        transaction = SQLTransaction(self.container, self.connection)
        try:
            transaction.begin()
            nav_done = set()
            for k, dv in entity.navigation_items():
                link_end = self.entity_set.navigation[k]
                if not dv.bindings:
                    continue
                aset_name = link_end.parent.name
                # if link_end is in fk_mapping it means we are keeping a
                # foreign key for this property, it may even be required but
                # either way, let's deal with it now.  This will insert or
                # update the link automatically, this navigation property
                # can never be a collection
                if link_end not in fk_mapping:
                    continue
                target_set = link_end.otherEnd.entity_set
                nullable, unique = fk_mapping[link_end]
                if len(dv.bindings) > 1:
                    raise edm.NavigationError(
                        "Unexpected error: found multiple bindings for "
                        "foreign key constraint %s" % k)
                binding = dv.bindings[0]
                if not isinstance(binding, edm.Entity):
                    # just a key, grab the entity
                    with target_set.open() as targetCollection:
                        targetCollection.select_keys()
                        target_entity = targetCollection[binding]
                    dv.bindings[0] = target_entity
                else:
                    target_entity = binding
                    if not target_entity.exists:
                        # add this entity to it's base collection
                        with target_set.open() as targetCollection:
                            targetCollection.insert_entity_sql(
                                target_entity, link_end.otherEnd, transaction)
                # Finally, we have a target entity, add the foreign key to
                # fk_values
                for key_name in target_set.keys:
                    fk_values.append(
                        (self.container.mangled_names[
                            (self.entity_set.name,
                             aset_name,
                             key_name)],
                            target_entity[key_name]))
                nav_done.add(k)
            # grab a list of sql-name,sql-value pairs representing the key
            # constraint
            concurrency_check = False
            constraints = []
            for k, v in dict_items(entity.key_dict()):
                constraints.append(
                    (self.container.mangled_names[
                        (self.entity_set.name, k)],
                        self.container.prepare_sql_value(v)))
            key_len = len(constraints)
            def_list = []
            if merge:
                cv_list = list(self.merge_fields(entity))
            else:
                cv_list = list(self.update_fields(entity))
                def_list = list(self.default_fields(entity))
            for cname, v in cv_list:
                # concurrency tokens get added as if they were part of the key
                if v.p_def.concurrencyMode == edm.ConcurrencyMode.Fixed:
                    concurrency_check = True
                    constraints.append(
                        (cname, self.container.prepare_sql_value(v)))
            # now update the entity to have the latest concurrency token
            entity.set_concurrency_tokens()
            query = ['UPDATE ', self.table_name, ' SET ']
            params = self.container.ParamsClass()
            updates = []
            for cname, v in cv_list + fk_values:
                updates.append(
                    '%s=%s' %
                    (cname,
                     params.add_param(self.container.prepare_sql_value(v))))
            for cname in def_list:
                updates.append('%s=DEFAULT' % cname)
            if updates:
                query.append(', '.join(updates))
                query.append(' WHERE ')
                where = []
                for cname, cvalue in constraints:
                    where.append('%s=%s' % (cname, params.add_param(cvalue)))
                query.append(' AND '.join(where))
                query = ''.join(query)
                logging.info("%s; %s", query, to_text(params.params))
                transaction.execute(query, params)
            if updates and transaction.cursor.rowcount == 0:
                # we need to check if this entity really exists
                query = ['SELECT COUNT(*) FROM ', self.table_name, ' WHERE ']
                params = self.container.ParamsClass()
                where = []
                for cname, cvalue in constraints:
                    where.append('%s=%s' % (cname, params.add_param(cvalue)))
                query.append(' AND '.join(where))
                query = ''.join(query)
                logging.info("%s; %s", query, to_text(params.params))
                transaction.execute(query, params)
                result = transaction.cursor.fetchone()[0]
                if result == 0 and concurrency_check:
                    # could be a concurrency error, repeat with just keys
                    query = [
                        'SELECT COUNT(*) FROM ', self.table_name, ' WHERE ']
                    params = self.container.ParamsClass()
                    where = []
                    for cname, cvalue in constraints[:key_len]:
                        where.append(
                            '%s=%s' % (cname, params.add_param(cvalue)))
                    query.append(' AND '.join(where))
                    query = ''.join(query)
                    logging.info("%s; %s", query, to_text(params.params))
                    transaction.execute(query, params)
                    result = transaction.cursor.fetchone()[0]
                    if result == 1:
                        raise edm.ConcurrencyError
                if result == 0:
                    raise KeyError("Entity %s does not exist" %
                                   str(entity.get_location()))
                # otherwise, no rows affected, but ignore!
            # We finish off the bindings in a similar way to
            # insert_entity_sql but this time we need to handle the case
            # where there is an existing link and the navigation
            # property is not a collection.
            for k, dv in entity.navigation_items():
                link_end = self.entity_set.navigation[k]
                if not dv.bindings:
                    continue
                elif k in nav_done:
                    dv.bindings = []
                    continue
                aset_name = link_end.parent.name
                target_set = dv.target()
                target_fk_mapping = self.container.fk_table[target_set.name]
                with dv.open() as navCollection:
                    with target_set.open() as targetCollection:
                        while dv.bindings:
                            binding = dv.bindings[0]
                            if not isinstance(binding, edm.Entity):
                                targetCollection.select_keys()
                                binding = targetCollection[binding]
                            if binding.exists:
                                if dv.isCollection:
                                    navCollection.insert_link(
                                        binding, transaction)
                                else:
                                    navCollection.replace_link(binding,
                                                               transaction)
                            else:
                                if link_end.otherEnd in target_fk_mapping:
                                    # target table has a foreign key
                                    target_fk_values = []
                                    for key_name in self.entity_set.keys:
                                        target_fk_values.append(
                                            (self.container.mangled_names[
                                                (target_set.name,
                                                 aset_name,
                                                 key_name)],
                                                entity[key_name]))
                                    if not dv.isCollection:
                                        navCollection.clear_links(transaction)
                                    targetCollection.insert_entity_sql(
                                        binding,
                                        link_end.otherEnd,
                                        target_fk_values,
                                        transaction)
                                else:
                                    # foreign keys are in an auxiliary table
                                    targetCollection.insert_entity_sql(
                                        binding, link_end.otherEnd)
                                    if dv.isCollection:
                                        navCollection.insert_link(
                                            binding, transaction)
                                    else:
                                        navCollection.replace_link(
                                            binding, transaction)
                            dv.bindings = dv.bindings[1:]
            transaction.commit()
        except (self.container.dbapi.IntegrityError,
                self.container.dbapi.InternalError) as e:
            # we might need to distinguish between a failure due to
            # fk_values or a missing key
            transaction.rollback(e, swallow=True)
            raise edm.ConstraintError(
                "Update failed for %s : %s" %
                (str(entity.get_location()), str(e)))
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()

    def update_link(
            self,
            entity,
            link_end,
            target_entity,
            no_replace=False,
            transaction=None):
        """Updates a link when this table contains the foreign key

        entity
                The entity being linked from (must already exist)

        link_end
                The :py:class:`~pyslet.odata2.csdl.AssociationSetEnd` bound
                to this entity set that represents this entity set's end of
                the assocation being modified.

        target_entity
                The entity to link to or None if the link is to be removed.

        no_replace
                If True, existing links will not be replaced.  The affect is
                to force the underlying SQL query to include a constraint
                that the foreign key is currently NULL.  By default this
                argument is False and any existing link will be replaced.

        transaction
                An optional transaction.  If present, the connection is left
                uncommitted."""
        if not entity.exists:
            raise edm.NonExistentEntity(
                "Attempt to update non-existent entity: " +
                str(entity.get_location()))
        if transaction is None:
            transaction = SQLTransaction(self.container, self.connection)
        query = ['UPDATE ', self.table_name, ' SET ']
        params = self.container.ParamsClass()
        updates = []
        null_cols = []
        target_set = link_end.otherEnd.entity_set
        aset_name = link_end.parent.name
        nullable, unique = \
            self.container.fk_table[self.entity_set.name][link_end]
        if not nullable and target_entity is None:
            raise edm.NavigationError("Can't remove a required link")
        if target_entity:
            for key_name in target_set.keys:
                v = target_entity[key_name]
                cname = self.container.mangled_names[
                    (self.entity_set.name, aset_name, key_name)]
                updates.append(
                    '%s=%s' %
                    (cname,
                     params.add_param(
                         self.container.prepare_sql_value(v))))
                if no_replace:
                    null_cols.append(cname)
        else:
            for key_name in target_set.keys:
                cname = self.container.mangled_names[
                    (self.entity_set.name, aset_name, key_name)]
                updates.append('%s=NULL' % cname)
        query.append(', '.join(updates))
        # we don't do concurrency checks on links, and we suppress the filter
        # check too
        query.append(
            self.where_clause(entity, params, False, null_cols=null_cols))
        query = ''.join(query)
        try:
            transaction.begin()
            logging.info("%s; %s", query, to_text(params.params))
            transaction.execute(query, params)
            if transaction.cursor.rowcount == 0:
                if null_cols:
                    # raise a constraint failure, rather than a key failure -
                    # assume entity is good
                    raise edm.NavigationError(
                        "Entity %s is already linked through association %s" %
                        (entity.get_location(), aset_name))
                else:
                    # key failure - unexpected case as entity should be good
                    raise KeyError("Entity %s does not exist" %
                                   str(entity.get_location()))
            transaction.commit()
        except self.container.dbapi.IntegrityError as e:
            transaction.rollback(e, swallow=True)
            raise KeyError("Linked entity %s does not exist" %
                           str(target_entity.get_location()))
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()

    def __delitem__(self, key):
        with self.entity_set.open() as base:
            entity = base.new_entity()
            entity.set_key(key)
            entity.exists = True    # an assumption!
            # base.select_keys()
            # entity = base[key]
        self.delete_entity(entity)

    def delete_entity(self, entity, from_end=None, transaction=None):
        """Deletes an entity

        Called by the dictionary-like del operator, provided as a
        separate method to enable it to be called recursively when
        doing cascade deletes and to support transactions.

        from_end
                An optional
                :py:class:`~pyslet.odata2.csdl.AssociationSetEnd` bound to
                this entity set that represents the link from which we are
                being deleted during a cascade delete.

                The purpose of this parameter is prevent cascade deletes
                from doubling back on themselves and causing an infinite
                loop.

        transaction
                An optional transaction.  If present, the connection is left
                uncommitted."""
        if transaction is None:
            transaction = SQLTransaction(self.container, self.connection)
        try:
            transaction.begin()
            fk_mapping = self.container.fk_table[self.entity_set.name]
            for link_end, nav_name in dict_items(self.entity_set.linkEnds):
                if link_end == from_end:
                    continue
                aset_name = link_end.parent.name
                if link_end in fk_mapping:
                    # if we are holding a foreign key then deleting us
                    # will delete the link too, so nothing to do here.
                    continue
                else:
                    if (link_end.associationEnd.multiplicity ==
                            edm.Multiplicity.One):
                        # we are required, so it must be a 1-? relationship
                        if nav_name is not None:
                            # and it is bound to a navigation property so we
                            # can cascade delete
                            target_entity_set = link_end.otherEnd.entity_set
                            with entity[nav_name].open() as links:
                                with target_entity_set.open() as \
                                        cascade:
                                    links.select_keys()
                                    for target_entity in links.values():
                                        links.delete_link(target_entity,
                                                          transaction)
                                        cascade.delete_entity(
                                            target_entity,
                                            link_end.otherEnd,
                                            transaction)
                        else:
                            raise edm.NavigationError(
                                "Can't cascade delete from an entity in %s as "
                                "the association set %s is not bound to a "
                                "navigation property" %
                                (self.entity_set.name, aset_name))
                    else:
                        # we are not required, so just drop the links
                        if nav_name is not None:
                            with entity[nav_name].open() as links:
                                links.clear_links(transaction)
                        # otherwise annoying, we need to do something special
                        elif aset_name in self.container.aux_table:
                            # foreign keys are in an association table,
                            # hardest case as navigation may be unbound so
                            # we have to call a class method and pass the
                            # container and connection
                            SQLAssociationCollection.clear_links_unbound(
                                self.container, link_end, entity, transaction)
                        else:
                            # foreign keys are at the other end of the
                            # link, we have a method for that...
                            target_entity_set = link_end.otherEnd.entity_set
                            with target_entity_set.open() as \
                                    keyCollection:
                                keyCollection.clear_links(
                                    link_end.otherEnd, entity, transaction)
            params = self.container.ParamsClass()
            query = ["DELETE FROM "]
            params = self.container.ParamsClass()
            query.append(self.table_name)
            # WHERE - ignore the filter
            query.append(self.where_clause(entity, params, use_filter=False))
            query = ''.join(query)
            logging.info("%s; %s", query, to_text(params.params))
            transaction.execute(query, params)
            rowcount = transaction.cursor.rowcount
            if rowcount == 0:
                raise KeyError
            elif rowcount > 1:
                # whoops, that was unexpected
                raise SQLError(
                    "Integrity check failure, non-unique key: %s" %
                    repr(entity.key()))
            transaction.commit()
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()

    def delete_link(self, entity, link_end, target_entity, transaction=None):
        """Deletes the link between *entity* and *target_entity*

        The foreign key for this link must be held in this entity set's
        table.

        entity
                The entity in this entity set that the link is from.

        link_end
                The :py:class:`~pyslet.odata2.csdl.AssociationSetEnd` bound
                to this entity set that represents this entity set's end of
                the assocation being modified.

        target_entity
                The target entity that defines the link to be removed.

        transaction
                An optional transaction.  If present, the connection is left
                uncommitted."""
        if not entity.exists:
            raise edm.NonExistentEntity(
                "Attempt to update non-existent entity: " +
                str(entity.get_location()))
        if transaction is None:
            transaction = SQLTransaction(self.container, self.connection)
        query = ['UPDATE ', self.table_name, ' SET ']
        params = self.container.ParamsClass()
        updates = []
        aset_name = link_end.parent.name
        target_set = link_end.otherEnd.entity_set
        nullable, unique = \
            self.container.fk_table[self.entity_set.name][link_end]
        if not nullable:
            raise edm.NavigationError(
                "Can't remove a required link from association set %s" %
                aset_name)
        for key_name in target_set.keys:
            cname = self.container.mangled_names[
                (self.entity_set.name, aset_name, key_name)]
            updates.append('%s=NULL' % cname)
        query.append(', '.join(updates))
        # custom where clause to ensure that the link really existed before we
        # delete it
        query.append(' WHERE ')
        where = []
        kd = entity.key_dict()
        for k, v in dict_items(kd):
            where.append(
                '%s=%s' %
                (self.container.mangled_names[
                    (self.entity_set.name, k)], params.add_param(
                    self.container.prepare_sql_value(v))))
        for key_name in target_set.keys:
            v = target_entity[key_name]
            cname = self.container.mangled_names[
                (self.entity_set.name, aset_name, key_name)]
            where.append(
                '%s=%s' %
                (cname,
                 params.add_param(
                     self.container.prepare_sql_value(v))))
        query.append(' AND '.join(where))
        query = ''.join(query)
        try:
            transaction.begin()
            logging.info("%s; %s", query, to_text(params.params))
            transaction.execute(query, params)
            if transaction.cursor.rowcount == 0:
                # no rows matched this constraint, entity either doesn't exist
                # or wasn't linked to the target
                raise KeyError(
                    "Entity %s does not exist or is not linked to %s" % str(
                        entity.get_location(),
                        target_entity.get_location))
            transaction.commit()
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()

    def clear_links(self, link_end, target_entity, transaction=None):
        """Deletes all links to *target_entity*

        The foreign key for this link must be held in this entity set's
        table.

        link_end
                The :py:class:`~pyslet.odata2.csdl.AssociationSetEnd` bound
                to this entity set that represents this entity set's end of
                the assocation being modified.

        target_entity
                The target entity that defines the link(s) to be removed.

        transaction
                An optional transaction.  If present, the connection is left
                uncommitted."""
        if transaction is None:
            transaction = SQLTransaction(self.container, self.connection)
        query = ['UPDATE ', self.table_name, ' SET ']
        params = self.container.ParamsClass()
        updates = []
        aset_name = link_end.parent.name
        target_set = link_end.otherEnd.entity_set
        nullable, unique = \
            self.container.fk_table[self.entity_set.name][link_end]
        for key_name in target_set.keys:
            cname = self.container.mangled_names[
                (self.entity_set.name, aset_name, key_name)]
            updates.append('%s=NULL' % cname)
        # custom where clause
        query.append(', '.join(updates))
        query.append(' WHERE ')
        where = []
        for key_name in target_set.keys:
            v = target_entity[key_name]
            cname = self.container.mangled_names[
                (self.entity_set.name, aset_name, key_name)]
            where.append(
                '%s=%s' %
                (cname,
                 params.add_param(
                     self.container.prepare_sql_value(v))))
        query.append(' AND '.join(where))
        query = ''.join(query)
        try:
            transaction.begin()
            logging.info("%s; %s", query, to_text(params.params))
            transaction.execute(query, params)
            transaction.commit()
        except self.container.dbapi.IntegrityError as e:
            # catch the nullable violation here, makes it benign to
            # clear links to an unlinked target
            transaction.rollback(e, swallow=True)
            raise edm.NavigationError(
                "Can't remove required link from assocation set %s" %
                aset_name)
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()

    def create_table_query(self):
        """Returns a SQL statement and params for creating the table."""
        entity = self.new_entity()
        query = ['CREATE TABLE ', self.table_name, ' (']
        params = self.container.ParamsClass()
        cols = []
        cnames = {}
        for c, v in self.select_fields(entity, prefix=False):
            try:
                v.set_default_value()
            except edm.ConstraintError:
                # non-nullable, no default
                pass
            if c in cnames:
                continue
            else:
                cnames[c] = True
                cols.append("%s %s" %
                            (c, self.container.prepare_sql_type(v, params)))
        # do we have a media stream?
        if self.entity_set.entityType.has_stream():
            v = edm.EDMValue.from_type(edm.SimpleType.Int64)
            c = self.container.mangled_names[(self.entity_set.name, '_value')]
            cnames[c] = True
            cols.append("%s %s" %
                        (c, self.container.prepare_sql_type(v, params)))
        constraints = []
        constraints.append(
            'PRIMARY KEY (%s)' %
            ', '.join(self.container.mangled_names[(self.entity_set.name, x)]
                      for x in self.entity_set.keys))
        # Now generate the foreign keys
        fk_mapping = self.container.fk_table[self.entity_set.name]
        for link_end in fk_mapping:
            aset_name = link_end.parent.name
            target_set = link_end.otherEnd.entity_set
            nullable, unique = fk_mapping[link_end]
            fk_names = []
            k_names = []
            for key_name in target_set.keys:
                # create a dummy value to catch the unusual case where
                # there is a default
                v = target_set.entityType[key_name]()
                try:
                    v.set_default_value()
                except edm.ConstraintError:
                    # non-nullable, no default
                    pass
                cname = self.container.mangled_names[
                    (self.entity_set.name, aset_name, key_name)]
                fk_names.append(cname)
                k_names.append(
                    self.container.mangled_names[(target_set.name, key_name)])
                if cname in cnames:
                    # if a fk is already declared, skip it
                    continue
                else:
                    cols.append("%s %s" % (
                                cname,
                                self.container.prepare_sql_type(
                                    v, params, nullable)))
            constraints.append(
                "CONSTRAINT %s FOREIGN KEY (%s) REFERENCES %s(%s)" %
                (self.container.quote_identifier(aset_name), ', '.join(
                    fk_names), self.container.mangled_names[
                    (target_set.name,)], ', '.join(
                    k_names)))
        cols = cols + constraints
        query.append(", ".join(cols))
        query.append(')')
        return ''.join(query), params

    def create_table(self):
        """Executes the SQL statement :py:meth:`create_table_query`"""
        query, params = self.create_table_query()
        transaction = SQLTransaction(self.container, self.connection)
        try:
            transaction.begin()
            logging.info("%s; %s", query, to_text(params.params))
            transaction.execute(query, params)
            transaction.commit()
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()

    def drop_table_query(self):
        """Returns a SQL statement for dropping the table."""
        query = ['DROP TABLE ', self.table_name]
        return ''.join(query)

    def drop_table(self):
        """Executes the SQL statement :py:meth:`drop_table_query`"""
        query = self.drop_table_query()
        transaction = SQLTransaction(self.container, self.connection)
        try:
            transaction.begin()
            logging.info("%s;", query)
            transaction.execute(query)
            transaction.commit()
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()


class SQLNavigationCollection(SQLCollectionBase, core.NavigationCollection):

    """Abstract class representing all navigation collections.

    Additional keyword arguments:

    aset_name
            The name of the association set that defines this relationship.
            This additional parameter is used by the name mangler to obtain
            the field name (or table name) used for the foreign keys."""

    def __init__(self, aset_name, **kwargs):
        self.aset_name = aset_name
        super(SQLNavigationCollection, self).__init__(**kwargs)

    def __setitem__(self, key, entity):
        # sanity check entity to check it can be inserted here
        if (not isinstance(entity, edm.Entity) or
                entity.entity_set is not self.entity_set):
            raise TypeError
        if key != entity.key():
            raise ValueError
        if not entity.exists:
            raise edm.NonExistentEntity(
                "Attempt to link to a non-existent entity: " +
                str(entity.get_location()))
        self.insert_link(entity)

    def insert_link(self, entity, transaction=None):
        """Inserts a link to *entity* into this collection.

        transaction
                An optional transaction.  If present, the connection is left
                uncommitted."""
        raise NotImplementedError

    def replace(self, entity):
        if (not isinstance(entity, edm.Entity) or
                entity.entity_set is not self.entity_set):
            raise TypeError
        if not entity.exists:
            raise edm.NonExistentEntity(
                "Attempt to link to a non-existent entity: " +
                str(entity.get_location()))
        self.replace_link(entity)

    def replace_link(self, entity, transaction=None):
        """Replaces all links with a single link to *entity*.

        transaction
                An optional transaction.  If present, the connection is left
                uncommitted."""
        raise NotImplementedError

    def delete_link(self, entity, transaction=None):
        """A utility method that deletes the link to *entity* in this collection.

        This method is called during cascaded deletes to force-remove a
        link prior to the deletion of the entity itself.

        transaction
                An optional transaction.  If present, the connection is left
                uncommitted."""
        raise NotImplementedError


class SQLForeignKeyCollection(SQLNavigationCollection):

    """The collection of entities obtained by navigation via a foreign key

    This object is used when the foreign key is stored in the same table
    as *from_entity*.  This occurs when the relationship is one of::

            0..1 to 1
            Many to 1
            Many to 0..1

    The name mangler looks for the foreign key in the field obtained by
    mangling::

            (entity set name, association set name, key name)

    For example, suppose that a link exists from entity set Orders[*] to
    entity set Customers[0..1] and that the key field of Customer is
    "CustomerID".  If the association set that binds Orders to Customers
    with this link is called OrdersToCustomers then the foreign key would
    be obtained by looking up::

            ('Orders','OrdersToCustomers','CustomerID')

    By default this would result in the field name::

            'OrdersToCustomers_CustomerID'

    This field would be looked up in the 'Orders' table.  The operation
    of the name mangler can be customised by overriding the
    :py:meth:`SQLEntityContainer.mangle_name` method in the container."""

    def __init__(self, **kwargs):
        super(SQLForeignKeyCollection, self).__init__(**kwargs)
        self.keyCollection = self.from_entity.entity_set.open()

    def reset_joins(self):
        """Overridden to provide an inner join to *from_entity*'s table.

        The join clause introduces an alias for the table containing
        *from_entity*.  The resulting join looks something like this::

            SELECT ... FROM Customers
            INNER JOIN Orders AS nav1 ON
                Customers.CustomerID=nav1.OrdersToCustomers_CustomerID
            ...
            WHERE nav1.OrderID = ?;

        The value of the OrderID key property in from_entity is passed as
        a parameter when executing the expression.

        In most cases, there will be a navigation properly bound to this
        association in the reverse direction.  For example, to continue
        the above example, Orders to Customers might be bound to a
        navigation property in the reverse direction called, say,
        'AllOrders' *in the target entity set*.

        If this navigation property is used in an expression then the
        existing INNER JOIN defined here is used instead of a new LEFT
        JOIN as would normally be the case."""
        super(SQLForeignKeyCollection, self).reset_joins()
        # nav_name is the navigation property from this entity set that
        # takes you back to the from_entity.  It may by an empty string
        # if there is no back link.  We need to know this in case
        # someone adds this navigation property to an expression, they
        # need to use our inner join in preference to the usual left
        # join.
        nav_name = self.entity_set.linkEnds[self.from_end.otherEnd]
        alias = self.next_alias()
        join = []
        # we don't need to look up the details of the join again, as
        # self.entity_set must be the target
        for key_name in self.entity_set.keys:
            join.append(
                '%s.%s=%s.%s' %
                (self.table_name, self.container.mangled_names[
                    (self.entity_set.name, key_name)],
                    alias, self.container.mangled_names[
                        (self.from_entity.entity_set.name,
                         self.aset_name, key_name)]))
        join = ' INNER JOIN %s AS %s ON ' % (
            self.container.mangled_names[(self.from_entity.entity_set.name,)],
            alias) + ' AND '.join(join)
        self._aliases.add(alias)
        self._joins[nav_name] = (alias, join)
        self._source_alias = alias

    def where_clause(self, entity, params, use_filter=True, use_skip=False):
        """Adds the constraint for entities linked from *from_entity* only.

        We continue to use the alias set in the :py:meth:`join_clause`
        where an example WHERE clause is illustrated."""
        if self._joins is None:
            self.reset_joins()
        where = []
        for k, v in dict_items(self.from_entity.key_dict()):
            where.append(
                "%s.%s=%s" %
                (self._source_alias, self.container.mangled_names[
                    (self.from_entity.entity_set.name, k)], params.add_param(
                    self.container.prepare_sql_value(v))))
        if entity is not None:
            self.where_entity_clause(where, entity, params)
        if self.filter is not None and use_filter:
            # use_filter option adds the current filter too
            where.append('(' + self.sql_expression(self.filter, params) + ')')
        if self.skiptoken is not None and use_skip:
            self.where_skiptoken_clause(where, params)
        if where:
            return ' WHERE ' + ' AND '.join(where)
        else:
            return ''

    def insert_entity(self, entity):
        transaction = SQLTransaction(self.container, self.connection)
        try:
            # Because of the nature of the relationships we are used
            # for, *entity* can be inserted into the base collection
            # without a link back to us (the link is optional from
            # entity's point of view). We still force the insert to
            # take place without a commit as the insertion of the link
            # afterwards might still fail.
            transaction.begin()
            with self.entity_set.open() as baseCollection:
                baseCollection.insert_entity_sql(
                    entity, self.from_end.otherEnd, transaction=transaction)
            self.keyCollection.update_link(
                self.from_entity,
                self.from_end,
                entity,
                no_replace=True,
                transaction=transaction)
            transaction.commit()
        except self.container.dbapi.IntegrityError as e:
            # we can't tell why the operation failed, could be a
            # KeyError, if we are trying to insert an existing entity or
            # could be a ConstraintError if we are already linked to a
            # different entity
            transaction.rollback(e, swallow=True)
            raise edm.NavigationError(str(e))
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()

    def insert_link(self, entity, transaction=None):
        return self.keyCollection.update_link(
            self.from_entity,
            self.from_end,
            entity,
            no_replace=True,
            transaction=transaction)

    def replace_link(self, entity, transaction=None):
        # Target multiplicity must be 0..1 or 1; treat it the same as setitem
        return self.keyCollection.update_link(
            self.from_entity,
            self.from_end,
            entity,
            transaction=transaction)

    def delete_link(self, entity, transaction=None):
        return self.keyCollection.delete_link(
            self.from_entity,
            self.from_end,
            entity,
            transaction=transaction)

    def __delitem__(self, key):
        #   Before we remove a link we need to know if this is ?-1
        #   relationship, if so, this deletion will result in a
        #   constraint violation.
        if self.toMultiplicity == edm.Multiplicity.One:
            raise edm.NavigationError("Can't remove a required link")
        #   Turn the key into an entity object as required by delete_link
        with self.entity_set.open() as targetCollection:
            target_entity = targetCollection.new_entity()
            target_entity.set_key(key)
            # we open the base collection and call the update link method
            self.keyCollection.delete_link(
                self.from_entity, self.from_end, target_entity)

    def close(self):
        if self.keyCollection is not None:
            self.keyCollection.close()
        super(SQLForeignKeyCollection, self).close()


class SQLReverseKeyCollection(SQLNavigationCollection):

    """The collection of entities obtained by navigation to a foreign key

    This object is used when the foreign key is stored in the target
    table.  This occurs in the reverse of the cases where
    :py:class:`SQLReverseKeyCollection` is used, i.e:

            1 to 0..1
            1 to Many
            0..1 to Many

    The implementation is actually simpler in this direction as no JOIN
    clause is required."""

    def __init__(self, **kwargs):
        super(SQLReverseKeyCollection, self).__init__(**kwargs)
        self.keyCollection = self.entity_set.open()

    def where_clause(self, entity, params, use_filter=True, use_skip=False):
        """Adds the constraint to entities linked from *from_entity* only."""
        where = []
        for k, v in dict_items(self.from_entity.key_dict()):
            where.append("%s=%s" % (
                self.container.mangled_names[
                    (self.entity_set.name, self.aset_name, k)],
                params.add_param(self.container.prepare_sql_value(v))))
        if entity is not None:
            self.where_entity_clause(where, entity, params)
        if self.filter is not None and use_filter:
            # use_filter option adds the current filter too
            where.append('(' + self.sql_expression(self.filter, params) + ')')
        if self.skiptoken is not None and use_skip:
            self.where_skiptoken_clause(where, params)
        if where:
            return ' WHERE ' + ' AND '.join(where)
        else:
            return ''

    def insert_entity(self, entity):
        transaction = SQLTransaction(self.container, self.connection)
        fk_values = []
        for k, v in dict_items(self.from_entity.key_dict()):
            fk_values.append(
                (self.container.mangled_names[
                    (self.entity_set.name, self.aset_name, k)], v))
        try:
            transaction.begin()
            self.keyCollection.insert_entity_sql(
                entity, self.from_end.otherEnd, fk_values, transaction)
            transaction.commit()
        except self.container.dbapi.IntegrityError as e:
            transaction.rollback(e, swallow=True)
            raise KeyError(str(entity.get_location()))
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()

    def insert_link(self, entity, transaction=None):
        return self.keyCollection.update_link(
            entity,
            self.from_end.otherEnd,
            self.from_entity,
            no_replace=True,
            transaction=transaction)
        # we use no_replace mode as the source multiplicity must be 1 or
        # 0..1 for this type of collection and if *entity* is already
        # linked it would be an error

    def replace_link(self, entity, transaction=None):
        if self.fromMultiplicity == edm.Multiplicity.One:
            # we are required, this must be an error
            raise edm.NavigationError(
                "Can't delete required link from association set %s" %
                self.aset_name)
        if transaction is None:
            transaction = SQLTransaction(self.container, self.connection)
        try:
            transaction.begin()
            self.keyCollection.clear_links(
                self.from_end.otherEnd, self.from_entity, transaction)
            self.insert_link(entity, transaction)
            transaction.commit()
        except self.container.dbapi.IntegrityError as e:
            transaction.rollback(e, swallow=True)
            raise edm.NavigationError(
                "Model integrity error when linking %s and %s" %
                (str(
                    self.from_entity.get_location()), str(
                    entity.get_location())))
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()

    def __delitem__(self, key):
        entity = self.keyCollection[key]
        if self.fromMultiplicity == edm.Multiplicity.One:
            # we are required, this must be an error
            raise edm.NavigationError(
                "Can't delete required link from association set %s" %
                self.aset_name)
        # fromMultiplicity is 0..1
        self.keyCollection.delete_link(
            entity, self.from_end.otherEnd, self.from_entity)

    def delete_link(self, entity, transaction=None):
        """Called during cascaded deletes.

        This is actually a no-operation as the foreign key for this
        association is in the entity's record itself and will be removed
        automatically when entity is deleted."""
        return 0

    def clear(self):
        self.keyCollection.clear_links(
            self.from_end.otherEnd,
            self.from_entity)

    def clear_links(self, transaction=None):
        """Deletes all links from this collection's *from_entity*

        transaction
                An optional transaction.  If present, the connection is left
                uncommitted."""
        self.keyCollection.clear_links(
            self.from_end.otherEnd, self.from_entity, transaction)

    def close(self):
        self.keyCollection.close()
        super(SQLReverseKeyCollection, self).close()


class SQLAssociationCollection(SQLNavigationCollection):

    """The collection obtained by navigation using an auxiliary table

    This object is used when the relationship is described by two sets
    of foreign keys stored in an auxiliary table.  This occurs mainly
    when the link is Many to Many but it is also used for 1 to 1
    relationships.  This last use may seem odd but it is used to
    represent the symmetry of the relationship. In practice, a single
    set of foreign keys is likely to exist in one table or the other and
    so the relationship is best modelled by a 0..1 to 1 relationship
    even if the intention is that the records will always exist in
    pairs.

    The name of the auxiliary table is obtained from the name mangler
    using the association set's name.  The keys use a more complex
    mangled form to cover cases where there is a recursive Many to Many
    relation (such as a social network of friends between User
    entities).  The names of the keys are obtained by mangling::

            ( association set name, target entity set name,
                navigation property name, key name )

    An example should help.  Suppose we have entities representing
    sports Teams(TeamID) and sports Players(PlayerID) and that you can
    navigate from Player to Team using the "PlayedFor" navigation
    property and from Team to Player using the "Players" navigation
    property.  Both navigation properties are collections so the
    relationship is Many to Many.  If the association set that binds the
    two entity sets is called PlayersAndTeams then the the auxiliary
    table name will be mangled from::

            ('PlayersAndTeams')

    and the fields will be mangled from::

            ('PlayersAndTeams','Teams','PlayedFor','TeamID')
            ('PlayersAndTeams','Players','Players','PlayerID')

    By default this results in column names 'Teams_PlayedFor_TeamID' and
    'Players_Players_PlayerID'.  If you are modelling an existing
    database then 'TeamID' and 'PlayerID' on their own are more likely
    choices. You would need to override the
    :py:meth:`SQLEntityContainer.mangle_name` method in the container to
    catch these cases and return the shorter column names.

    Finally, to ensure the uniqueness of foreign key constraints, the
    following names are mangled::

        ( association set name, association set name, 'fkA')
        ( association set name, association set name, 'fkB')

    Notice that the association set name is used twice as it is not only
    defines the scope of the name but must also be incorporated into the
    constraint name to ensure uniqueness across the entire databas."""

    def __init__(self, **kwargs):
        super(SQLAssociationCollection, self).__init__(**kwargs)
        # The relation is actually stored in an extra table so we will
        # need a join for all operations.
        self.aset_name = self.from_end.parent.name
        self.atable_name = self.container.mangled_names[
            (self.aset_name,)]
        entitySetA, nameA, entitySetB, nameB, self.uniqueKeys = \
            self.container.aux_table[self.aset_name]
        if self.from_entity.entity_set is entitySetA and self.name == nameA:
            self.from_nav_name = nameA
            self.toNavName = nameB
        else:
            self.from_nav_name = nameB
            self.toNavName = nameA

    def reset_joins(self):
        """Overridden to provide an inner join to the aux table.

        If the Customer and Group entities are related with a Many-Many
        relationship called Customers_Groups, the resulting join looks
        something like this (when the from_entity is a Customer)::

            SELECT ... FROM Groups
            INNER JOIN Customers_Groups ON
                Groups.GroupID = Customers_Groups.Groups_MemberOf_GroupID
            ...
            WHERE Customers_Groups.Customers_Members_CustomerID = ?;

        The value of the CustomerID key property in from_entity is
        passed as a parameter when executing the expression."""
        super(SQLAssociationCollection, self).reset_joins()
        join = []
        for key_name in self.entity_set.keys:
            join.append(
                '%s.%s=%s.%s' %
                (self.table_name,
                 self.container.mangled_names[(self.entity_set.name,
                                               key_name)],
                 self.atable_name,
                 self.container.mangled_names[(self.aset_name,
                                               self.entity_set.name,
                                               self.toNavName, key_name)]))
        join = ' INNER JOIN %s ON ' % self.atable_name + ' AND '.join(join)
        self._aliases.add(self.atable_name)
        self._joins[''] = ('', join)

    def add_join(self, name):
        """Overridden to provide special handling of navigation

        In most cases, there will be a navigation property bound to this
        association in the reverse direction.  For Many-Many relations
        this can't be used in an expression but if the relationship
        is actually 1-1 then we would augment the default INNER JOIN
        with an additional INNER JOIN to include the whole of the
        from_entity. (Normally we'd think of these expressions as LEFT
        joins but we're navigating back across a link that points to a
        single entity so there is no difference.)

        To illustrate, if Customers have a 1-1 relationship with
        PrimaryContacts through a Customers_PrimaryContacts association
        set then the expression grows an additional join::

            SELECT ... FROM PrimaryContacts
            INNER JOIN Customers_PrimaryContacts ON
                PrimaryContacts.ContactID =
                    Customers_PrimaryContacts.PrimaryContacts_Contact_ContactID
            INNER JOIN Customers AS nav1 ON
                Customers_PrimaryContacts.Customers_Customer_CustmerID =
                    Customers.CustomerID
            ...
            WHERE Customers_PrimaryContacts.Customers_Customer_CustomerID = ?;

        This is a cumbersome query to join two entities that are
        supposed to have a 1-1 relationship, which is one of the reasons
        why it is generally better to pick on side of the relationship
        or other and make it 0..1 to 1 as this would obviate the
        auxiliary table completely and just put a non-NULL, unique
        foreign key in the table that represents the 0..1 side of the
        relationship."""
        if not self._joins:
            self.reset_joins()
        if name != self.entity_set.linkEnds[self.from_end.otherEnd]:
            return super(SQLAssociationCollection, self).add_join(name)
        # special handling here
        if name in self._joins:
            return self._joins[name][0]
        # this collection is either 1-1 or Many-Many
        src_multiplicity, dst_multiplicity = \
            self.entity_set.get_multiplicity(name)
        if dst_multiplicity != edm.Multiplicity.One:
            # we can't join on this navigation property
            raise NotImplementedError(
                "NavigationProperty %s.%s cannot be used in an expression" %
                (self.entity_set.name, name))
        alias = self.next_alias()
        target_set = self.from_entity.entity_set
        target_table_name = self.container.mangled_names[(target_set.name, )]
        join = []
        for key_name in target_set.keys:
            join.append(
                '%s.%s=%s.%s' %
                (self.atable_name,
                 self.container.mangled_names[(self.aset_name, target_set.name,
                                               self.from_nav_name, key_name)],
                 alias,
                 self.container.mangled_names[(target_set.name, key_name)]))
        join = ' INNER JOIN %s AS %s ON %s' % (
            target_table_name, alias, ' AND '.join(join))
        self._joins[name] = (alias, join)
        self._aliases.add(alias)
        return alias

    def where_clause(self, entity, params, use_filter=True, use_skip=False):
        """Provides the *from_entity* constraint in the auxiliary table."""
        where = []
        for k, v in dict_items(self.from_entity.key_dict()):
            where.append(
                "%s.%s=%s" %
                (self.atable_name,
                 self.container.mangled_names[
                     (self.aset_name,
                      self.from_entity.entity_set.name,
                      self.from_nav_name,
                      k)],
                    params.add_param(
                     self.container.prepare_sql_value(v))))
        if entity is not None:
            for k, v in dict_items(entity.key_dict()):
                where.append(
                    "%s.%s=%s" %
                    (self.atable_name,
                     self.container.mangled_names[
                         (self.aset_name,
                          entity.entity_set.name,
                          self.toNavName,
                          k)],
                        params.add_param(
                         self.container.prepare_sql_value(v))))
        if use_filter and self.filter is not None:
            where.append("(%s)" % self.sql_expression(self.filter, params))
        if self.skiptoken is not None and use_skip:
            self.where_skiptoken_clause(where, params)
        return ' WHERE ' + ' AND '.join(where)

    def insert_entity(self, entity):
        """Rerouted to a SQL-specific implementation"""
        self.insert_entity_sql(entity, transaction=None)

    def insert_entity_sql(self, entity, transaction=None):
        """Inserts *entity* into the base collection and creates the link.

        This is always done in two steps, bound together in a single
        transaction (where supported).  If this object represents a 1 to
        1 relationship then, briefly, we'll be in violation of the
        model. This will only be an issue in non-transactional
        systems."""
        if transaction is None:
            transaction = SQLTransaction(self.container, self.connection)
        try:
            transaction.begin()
            with self.entity_set.open() as baseCollection:
                # if this is a 1-1 relationship insert_entity_sql will
                # fail (with an unbound navigation property) so we need
                # to suppress the back-link.
                baseCollection.insert_entity_sql(
                    entity, self.from_end.otherEnd, transaction=transaction)
            self.insert_link(entity, transaction)
            transaction.commit()
        except self.container.dbapi.IntegrityError as e:
            transaction.rollback(e, swallow=True)
            raise edm.NavigationError(str(entity.get_location()))
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()

    def insert_link(self, entity, transaction=None):
        if transaction is None:
            transaction = SQLTransaction(self.container, self.connection)
        query = ['INSERT INTO ', self.atable_name, ' (']
        params = self.container.ParamsClass()
        value_names = []
        values = []
        for k, v in dict_items(self.from_entity.key_dict()):
            value_names.append(
                self.container.mangled_names[
                    (self.aset_name,
                     self.from_entity.entity_set.name,
                     self.from_nav_name,
                     k)])
            values.append(
                params.add_param(
                    self.container.prepare_sql_value(v)))
        for k, v in dict_items(entity.key_dict()):
            value_names.append(
                self.container.mangled_names[
                    (self.aset_name,
                     self.entity_set.name,
                     self.toNavName,
                     k)])
            values.append(
                params.add_param(
                    self.container.prepare_sql_value(v)))
        query.append(', '.join(value_names))
        query.append(') VALUES (')
        query.append(', '.join(values))
        query.append(')')
        query = ''.join(query)
        try:
            transaction.begin()
            logging.info("%s; %s", query, to_text(params.params))
            transaction.execute(query, params)
            transaction.commit()
        except self.container.dbapi.IntegrityError as e:
            transaction.rollback(e, swallow=True)
            raise edm.NavigationError(
                "Model integrity error when linking %s and %s" %
                (str(
                    self.from_entity.get_location()), str(
                    entity.get_location())))
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()

    def replace_link(self, entity, transaction=None):
        if self.from_entity[self.from_nav_name].isCollection:
            if transaction is None:
                transaction = SQLTransaction(self.container, self.connection)
            try:
                transaction.begin()
                self.clear_links(transaction)
                self.insert_link(entity, transaction)
                transaction.commit()
            except self.container.dbapi.IntegrityError as e:
                transaction.rollback(e, swallow=True)
                raise edm.NavigationError(
                    "Model integrity error when linking %s and %s" %
                    (str(
                        self.from_entity.get_location()), str(
                        entity.get_location())))
            except Exception as e:
                transaction.rollback(e)
            finally:
                transaction.close()
        else:
            # We don't support symmetric associations of the 0..1 - 0..1
            # variety so this must be a 1..1 relationship.
            raise edm.NavigationError(
                "replace not allowed for 1-1 relationship "
                "(implicit delete not supported)")

    def __delitem__(self, key):
        #   Before we remove a link we need to know if this is 1-1
        #   relationship, if so, this deletion will result in a
        #   constraint violation.
        if self.uniqueKeys:
            raise edm.NavigationError("Can't remove a required link")
        with self.entity_set.open() as targetCollection:
            entity = targetCollection.new_entity()
            entity.set_key(key)
            self.delete_link(entity)

    def delete_link(self, entity, transaction=None):
        """Called during cascaded deletes to force-remove a link prior
        to the deletion of the entity itself.

        This method is also re-used for simple deletion of the link in
        this case as the link is in the auxiliary table itself."""
        if transaction is None:
            transaction = SQLTransaction(self.container, self.connection)
        query = ['DELETE FROM ', self.atable_name]
        params = self.container.ParamsClass()
        # we suppress the filter check on the where clause
        query.append(self.where_clause(entity, params, False))
        query = ''.join(query)
        try:
            transaction.begin()
            logging.info("%s; %s", query, to_text(params.params))
            transaction.execute(query, params)
            if transaction.cursor.rowcount == 0:
                # no rows matched this constraint must be a key failure at one
                # of the two ends
                raise KeyError(
                    "One of the entities %s or %s no longer exists" %
                    (str(
                        self.from_entity.get_location()), str(
                        entity.get_location())))
            transaction.commit()
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()

    def clear_links(self, transaction=None):
        """Deletes all links from this collection's *from_entity*

        transaction
                An optional transaction.  If present, the connection is left
                uncommitted."""
        if transaction is None:
            transaction = SQLTransaction(self.container, self.connection)
        query = ['DELETE FROM ', self.atable_name]
        params = self.container.ParamsClass()
        # we suppress the filter check on the where clause
        query.append(self.where_clause(None, params, False))
        query = ''.join(query)
        try:
            transaction.begin()
            logging.info("%s; %s", query, to_text(params.params))
            transaction.execute(query, params)
            transaction.commit()
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()

    @classmethod
    def clear_links_unbound(
            cls,
            container,
            from_end,
            from_entity,
            transaction):
        """Special class method for deleting all the links from *from_entity*

        This is a class method because it has to work even if there is
        no navigation property bound to this end of the association.

        container
                The :py:class:`SQLEntityContainer` containing this
                association set.

        from_end
                The :py:class:`~pyslet.odata2.csdl.AssociationSetEnd`
                that represents the end of the association that
                *from_entity* is bound to.

        from_entity
                The entity to delete links from

        transaction
                The current transaction (required)

        This is a class method because it has to work even if there is
        no navigation property bound to this end of the association.  If
        there was a navigation property then an instance could be
        created and the simpler :py:meth:`clear_links` method used."""
        aset_name = from_end.parent.name
        atable_name = container.mangled_names[(aset_name,)]
        nav_name = from_entity.entity_set.linkEnds[from_end]
        if nav_name is None:
            # this is most likely the case, we're being called this way
            # because we can't instantiate a collection on an unbound
            # navigation property
            nav_name = ""
        entitySetA, nameA, entitySetB, nameB, uniqueKeys = container.aux_table[
            aset_name]
        if from_entity.entity_set is entitySetA and nav_name == nameA:
            from_nav_name = nameA
        else:
            from_nav_name = nameB
        query = ['DELETE FROM ', atable_name]
        params = container.ParamsClass()
        query.append(' WHERE ')
        where = []
        for k, v in dict_items(from_entity.key_dict()):
            where.append(
                "%s.%s=%s" %
                (atable_name,
                 container.mangled_names[
                     (aset_name,
                      from_entity.entity_set.name,
                      from_nav_name,
                      k)],
                    params.add_param(
                     container.prepare_sql_value(v))))
        query.append(' AND '.join(where))
        query = ''.join(query)
        logging.info("%s; %s", query, to_text(params.params))
        transaction.execute(query, params)

    @classmethod
    def create_table_query(cls, container, aset_name):
        """Returns a SQL statement and params to create the auxiliary table.

        This is a class method to enable the table to be created before
        any entities are created."""
        entitySetA, nameA, entitySetB, nameB, uniqueKeys = container.aux_table[
            aset_name]
        query = ['CREATE TABLE ', container.mangled_names[(aset_name,)], ' (']
        params = container.ParamsClass()
        cols = []
        constraints = []
        pk_names = []
        for es, prefix, ab in ((entitySetA, nameA, 'A'),
                               (entitySetB, nameB, 'B')):
            target_table = container.mangled_names[(es.name,)]
            fk_names = []
            k_names = []
            for key_name in es.keys:
                # create a dummy value to catch the unusual case where
                # there is a default
                v = es.entityType[key_name]()
                try:
                    v.set_default_value()
                except edm.ConstraintError:
                    # non-nullable, no default
                    pass
                cname = container.mangled_names[
                    (aset_name, es.name, prefix, key_name)]
                fk_names.append(cname)
                pk_names.append(cname)
                k_names.append(container.mangled_names[(es.name, key_name)])
                cols.append("%s %s" %
                            (cname, container.prepare_sql_type(v, params)))
            constraints.append(
                "CONSTRAINT %s FOREIGN KEY (%s) REFERENCES %s(%s)" %
                (container.mangled_names[(aset_name, aset_name, "fk" + ab)],
                 ', '.join(fk_names),
                 target_table, ', '.join(k_names)))
            if uniqueKeys:
                constraints.append("CONSTRAINT %s UNIQUE (%s)" % (
                    container.quote_identifier("u" + ab),
                    ', '.join(fk_names)))
        # Finally, add a unique constraint spanning all columns as we don't
        # want duplicate relations
        constraints.append("CONSTRAINT %s UNIQUE (%s)" % (
            container.mangled_names[(aset_name, aset_name, "pk")],
            ', '.join(pk_names)))
        cols = cols + constraints
        query.append(", ".join(cols))
        query.append(')')
        return ''.join(query), params

    @classmethod
    def create_table(cls, container, aset_name):
        """Executes the SQL statement :py:meth:`create_table_query`"""
        connection = container.acquire_connection(
            SQL_TIMEOUT)        #: a connection to the database
        if connection is None:
            raise DatabaseBusy(
                "Failed to acquire connection after %is" % SQL_TIMEOUT)
        transaction = SQLTransaction(container, connection)
        try:
            transaction.begin()
            query, params = cls.create_table_query(container, aset_name)
            logging.info("%s; %s", query, to_text(params.params))
            transaction.execute(query, params)
            transaction.commit()
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()
            if connection is not None:
                container.release_connection(connection)

    @classmethod
    def drop_table_query(cls, container, aset_name):
        """Returns a SQL statement to drop the auxiliary table."""
        entitySetA, nameA, entitySetB, nameB, uniqueKeys = container.aux_table[
            aset_name]
        query = ['DROP TABLE ', container.mangled_names[(aset_name,)]]
        return ''.join(query)

    @classmethod
    def drop_table(cls, container, aset_name):
        """Executes the SQL statement :py:meth:`drop_table_query`"""
        connection = container.acquire_connection(
            SQL_TIMEOUT)        #: a connection to the database
        if connection is None:
            raise DatabaseBusy(
                "Failed to acquire connection after %is" % SQL_TIMEOUT)
        transaction = SQLTransaction(container, connection)
        try:
            transaction.begin()
            query = cls.drop_table_query(container, aset_name)
            logging.info("%s;", query)
            transaction.execute(query)
            transaction.commit()
        except Exception as e:
            transaction.rollback(e)
        finally:
            transaction.close()
            if connection is not None:
                container.release_connection(connection)


class DummyLock(object):

    """An object to use in place of a real Lock, can always be acquired"""

    def acquire(self, blocking=None):
        return True

    def release(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass


class SQLConnection(object):

    """An object used to wrap the connection.

    Used in the connection pools to keep track of which thread owns the
    connections, the depth of the lock and when the connection was last
    modified (acquired or released)."""

    def __init__(self):
        self.thread = None
        self.thread_id = None
        self.locked = 0
        self.last_seen = 0
        self.dbc = None


class SQLEntityContainer(object):

    """Object used to represent an Entity Container (aka Database).

    Keyword arguments on construction:

    container
        The :py:class:`~pyslet.odata2.csdl.EntityContainer` that defines
        this database.

    streamstore
        An optional :py:class:`~pyslet.blockstore.StreamStore` that will
        be used to store media resources in the container.  If absent,
        media resources actions will generate NotImplementedError.

    dbapi
        The DB API v2 compatible module to use to connect to the
        database.

        This implementation is compatible with modules regardless of
        their thread-safety level (provided they declare it
        correctly!).

    max_connections (optional)
        The maximum number of connections to open to the database.
        If your program attempts to open more than this number
        (defaults to 10) then it will block until a connection
        becomes free.  Connections are always shared within the same
        thread so this argument should be set to the expected
        maximum number of threads that will access the database.

        If using a module with thread-safety level 0 max_connections
        is ignored and is effectively 1, so use of the API is then
        best confined to single-threaded programs. Multi-threaded
        programs can still use the API but it will block when there
        is contention for access to the module and context switches
        will force the database connection to be closed and reopened.

    field_name_joiner (optional)
        The character used by the name mangler to join compound
        names, for example, to obtain the column name of a complex
        property like "Address/City".  The default is "_", resulting
        in names like "Address_City" but it can be changed here.
        Note: all names are quoted using :py:meth:`quote_identifier`
        before appearing in SQL statements.

    max_idle (optional)
        The maximum number of seconds idle database connections should
        be kept open before they are cleaned by the
        :meth:`pool_cleaner`. The default is None which means that the
        pool_cleaner never runs. Any other value causes a separate
        thread to be created to run the pool cleaner passing the value
        of the parameter each time. The frequency of calling the
        pool_cleaner method is calculated by dividing max_idle by 5, but
        it never runs more than once per minute.  For example, a setting
        of 3600 (1 hour) will result in a pool cleaner call every 12
        minutes.

    This class is designed to work with diamond inheritance and super.
    All derived classes must call __init__ through super and pass all
    unused keyword arguments.  For example::

        class MyDBContainer:
                def __init__(self,myDBConfig,**kwargs):
                        super(MyDBContainer,self).__init__(**kwargs)
                        # do something with myDBConfig...."""

    def __init__(self, container, dbapi, streamstore=None, max_connections=10,
                 field_name_joiner="_", max_idle=None, **kwargs):
        if kwargs:
            logging.debug(
                "Unabsorbed kwargs in SQLEntityContainer constructor")
        self.container = container
        #: the :py:class:`~pyslet.odata2.csdl.EntityContainer`
        self.streamstore = streamstore
        #: the optional :py:class:`~pyslet.blockstore.StreamStore`
        self.dbapi = dbapi
        #: the DB API compatible module
        self.module_lock = None
        if self.dbapi.threadsafety == 0:
            # we can't even share the module, so just use one connection will
            # do
            self.module_lock = threading.RLock()
            self.clocker = DummyLock
            self.cpool_max = 1
        else:
            # Level 1 and above we can share the module
            self.module_lock = DummyLock()
            self.clocker = threading.RLock
            self.cpool_max = max_connections
        self.cpool_lock = threading.Condition()
        self.cpool_locked = {}
        self.cpool_unlocked = {}
        self.cpool_idle = []
        self.cpool_size = 0
        self.closing = threading.Event()
        # set up the parameter style
        if self.dbapi.paramstyle == "qmark":
            self.ParamsClass = QMarkParams
        elif self.dbapi.paramstyle == "numeric":
            self.ParamsClass = NumericParams
        elif self.dbapi.paramstyle == "named":
            self.ParamsClass = NamedParams
        elif self.dbapi.paramstyle == "format":
            self.ParamsClass = FormatParams
        elif self.dbapi.paramstyle == "pyformat":
            self.ParamsClass = PyFormatParams
        else:
            # will fail later when we try and add parameters
            logging.warning("Unsupported DBAPI params style: %s\n"
                            "setting to qmark",
                            self.dbapi.paramstyle)
            self.ParamsClass = SQLParams
        self.fk_table = {}
        """A mapping from an entity set name to a FK mapping of the form::

            {<association set end>: (<nullable flag>, <unique keys flag>),...}

        The outer mapping has one entry for each entity set (even if the
        corresponding foreign key mapping is empty).

        Each foreign key mapping has one entry for each foreign key
        reference that must appear in that entity set's table.  The key
        is an :py:class:`AssociationSetEnd` that is bound to the entity
        set (the other end will be bound to the target entity set).
        This allows us to distinguish between the two ends of a
        recursive association."""
        self.aux_table = {}
        """A mapping from the names of symmetric association sets to a
        tuple of::

            (<entity set A>, <name prefix A>, <entity set B>,
            <name prefix B>, <unique keys>)"""
        self.mangled_names = {}
        """A mapping from source path tuples to mangled and quoted names
        to use in SQL queries.  For example::

            ('Customer'):'"Customer"'
            ('Customer', 'Address', 'City') : "Address_City"
            ('Customer', 'Orders') : "Customer_Orders"

        Note that the first element of the tuple is the entity set name
        but the default implementation does not use this in the mangled
        name for primitive fields as they are qualified in contexts
        where a name clash is possible.  However, mangled navigation
        property names do include the table name prefix as they used as
        pseudo-table names."""
        self.field_name_joiner = field_name_joiner
        """Default string used to join complex field names in SQL
        queries, e.g. Address_City"""
        self.ro_names = set()
        """The set of names that should be considered read only by the
        SQL insert and update generation code.  The items in the set are
        source paths, as per :py:attr:`mangled_names`.  The set is
        populated on construction using the :py:meth:`ro_name` method."""
        # for each entity set in this container, bind a SQLEntityCollection
        # object
        for es in self.container.EntitySet:
            self.fk_table[es.name] = {}
            for source_path in self.source_path_generator(es):
                self.mangled_names[source_path] = self.mangle_name(source_path)
                if self.ro_name(source_path):
                    self.ro_names.add(source_path)
            self.bind_entity_set(es)
        for es in self.container.EntitySet:
            for np in es.entityType.NavigationProperty:
                self.bind_navigation_property(es, np.name)
        # once the navigation properties have been bound, fk_table will
        # have been populated with any foreign keys we need to add field
        # name mappings for
        for esName, fk_mapping in dict_items(self.fk_table):
            for link_end, details in dict_items(fk_mapping):
                aset_name = link_end.parent.name
                target_set = link_end.otherEnd.entity_set
                for key_name in target_set.keys:
                    """Foreign keys are given fake source paths starting
                    with the association set name::

                            ( "Orders_Customers", "CustomerID" )"""
                    source_path = (esName, aset_name, key_name)
                    self.mangled_names[source_path] = \
                        self.mangle_name(source_path)
        # and aux_table will have been populated with additional tables to
        # hold symmetric associations...
        for aSet in self.container.AssociationSet:
            if aSet.name not in self.aux_table:
                continue
            self.mangled_names[(aSet.name,)] = self.mangle_name((aSet.name,))
            """Foreign keys in Tables that model association sets are
            given fake source paths that combine the entity set name and
            the name of the navigation property endpoint.

            This ensures the special case where the two entity sets are
            the same is taken care of (as the navigation property
            endpoints must still be unique). For one-way associations,
            prefixB will be an empty string."""
            esA, prefixA, esB, prefixB, unique = self.aux_table[aSet.name]
            for key_name in esA.keys:
                source_path = (aSet.name, esA.name, prefixA, key_name)
                self.mangled_names[source_path] = self.mangle_name(source_path)
            for key_name in esB.keys:
                source_path = (aSet.name, esB.name, prefixB, key_name)
                self.mangled_names[source_path] = self.mangle_name(source_path)
            """And mangle the foreign key constraint names..."""
            for kc in ('fkA', 'fkB', "pk"):
                source_path = (aSet.name, aSet.name, kc)
                self.mangled_names[source_path] = self.mangle_name(source_path)
        # start the pool cleaner thread if required
        if max_idle is not None:
            t = threading.Thread(
                target=self._run_pool_cleaner, kwargs={'max_idle': max_idle})
            t.setDaemon(True)
            t.start()
            logging.info("Starting pool_cleaner with max_idle=%f" %
                         float(max_idle))

    def mangle_name(self, source_path):
        """Mangles a source path into a quoted SQL name

        This is a key extension point to use when you are wrapping an existing
        database with the API.  It allows you to control the names used for
        entity sets (tables) and properties (columns) in SQL queries.

        source_path
            A tuple or list of strings describing the path to a property
            in the metadata model.

            For entity sets, this is a tuple with a single entry in it,
            the entity set name.

            For data properties this is a tuple containing the path,
            including the entity set name e.g.,
            ("Customers","Address","City") for the City property in a
            complex property 'Address' in entity set "Customers".

            For navigation properties the tuple is the navigation
            property name prefixed with the entity set name, e.g.,
            ("Customers","Orders"). This name is only used as a SQL
            alias for the target table, to remove ambiguity from certain
            queries that include a join across the navigation property.
            The mangled name must be distinct from the entity set name
            itself. from other such aliases and from other column names
            in this table.

            Foreign key properties contain paths starting with both the
            entity set and the association set names (see
            :py:class:`SQLForeignKeyCollection` for details) unless the
            association is symmetric, in which case they also contain
            the navigation property name (see
            :py:class:`SQLAssociationCollection` for details of these
            more complex cases).

        The default implementation strips the entity set name away and
        uses the default joining character to create a compound name
        before calling
        :py:meth:`quote_identifier` to obtain the SQL string. All names
        are mangled once, on construction, and from then on looked up in
        the dictionary of mangled names.

        If you need to override this method to modify the names used in
        your database you should ensure all other names (including any
        unrecognized by your program) are passed to the default
        implementation for mangling."""
        if len(source_path) > 1:
            source_path = list(source_path)[1:]
        return self.quote_identifier(
            self.field_name_joiner.join(source_path))

    def ro_name(self, source_path):
        """Test if a source_path identifies a read-only property

        This is a an additional extension point to use when you are
        wrapping an existing database with the API.  It allows you to
        manage situations where an entity property has an implied
        value and should be treated read only.

        There are two key use cases, auto-generated primary keys (such
        as auto-increment integer keys) and foreign keys which are
        exposed explicitly as foreign keys and should only be updated
        through an associated navigation property.

        source_path
            A tuple or list of strings describing the path to a property
            in the metadata model.  See :py:meth:`mangle_name` for more
            information.

        The default implementation returns False.

        If you override this method you must ensure all other names
        (including any unrecognized by your program) are passed to the
        default implementation using super."""
        return False

    def source_path_generator(self, entity_set):
        """Utility generator for source path *tuples* for *entity_set*"""
        yield (entity_set.name,)
        for source_path in self.type_name_generator(entity_set.entityType):
            yield tuple([entity_set.name] + source_path)
        if entity_set.entityType.has_stream():
            yield (entity_set.name, '_value')
        for link_end, nav_name in dict_items(entity_set.linkEnds):
            if not nav_name:
                # use the role name of the other end of the link instead
                # this makes sense because if entity_set is 'Orders' and
                # is linked to 'Customers' but lacks a navigation
                # property then the role name for link_end is likely to
                # be something like 'Order' and the other end is likely
                # to be something like 'Customer' - which provides a
                # reasonable guess at what the navigation property might
                # have been called and, furthermore, is under the
                # control of the model designer without directly
                # affecting the entities themselves.
                yield (entity_set.name, link_end.otherEnd.name)
            else:
                yield (entity_set.name, nav_name)

    def type_name_generator(self, type_def):
        for p in type_def.Property:
            if p.complexType is not None:
                for subPath in self.type_name_generator(p.complexType):
                    yield [p.name] + subPath
            else:
                yield [p.name]

    def bind_entity_set(self, entity_set):
        entity_set.bind(self.get_collection_class(), container=self)

    def bind_navigation_property(self, entity_set, name):
        # Start by making a tuple of the end multiplicities.
        from_as_end = entity_set.navigation[name]
        to_as_end = from_as_end.otherEnd
        # extract the name of the association set
        aset_name = from_as_end.parent.name
        target_set = to_as_end.entity_set
        multiplicity = (
            from_as_end.associationEnd.multiplicity,
            to_as_end.associationEnd.multiplicity)
        # now we can work on a case-by-case basis, note that fk_table may
        # be filled in twice for the same association (if navigation
        # properties are defined in both directions) but this is benign
        # because the definition should be identical.
        if multiplicity in (
                (edm.Multiplicity.One, edm.Multiplicity.One),
                (edm.Multiplicity.ZeroToOne, edm.Multiplicity.ZeroToOne)):
            entity_set.bind_navigation(
                name,
                self.get_symmetric_navigation_class(),
                container=self,
                aset_name=aset_name)
            if aset_name in self.aux_table:
                # This is the navigation property going back the other
                # way, set the navigation name only
                self.aux_table[aset_name][3] = name
            else:
                self.aux_table[aset_name] = [
                    entity_set, name, target_set, "", True]
        elif multiplicity == (edm.Multiplicity.Many, edm.Multiplicity.Many):
            entity_set.bind_navigation(
                name,
                self.get_symmetric_navigation_class(),
                container=self,
                aset_name=aset_name)
            if aset_name in self.aux_table:
                self.aux_table[aset_name][3] = name
            else:
                self.aux_table[aset_name] = [
                    entity_set, name, target_set, "", False]
        elif (multiplicity ==
                (edm.Multiplicity.One, edm.Multiplicity.ZeroToOne)):
            entity_set.bind_navigation(name,
                                       self.get_rk_class(),
                                       container=self, aset_name=aset_name)
            self.fk_table[target_set.name][to_as_end] = (False, True)
        elif multiplicity == (edm.Multiplicity.One, edm.Multiplicity.Many):
            entity_set.bind_navigation(name,
                                       self.get_rk_class(),
                                       container=self, aset_name=aset_name)
            self.fk_table[target_set.name][to_as_end] = (False, False)
        elif (multiplicity ==
                (edm.Multiplicity.ZeroToOne, edm.Multiplicity.Many)):
            entity_set.bind_navigation(
                name,
                self.get_rk_class(),
                container=self,
                aset_name=aset_name)
            self.fk_table[target_set.name][to_as_end] = (True, False)
        elif (multiplicity ==
                (edm.Multiplicity.ZeroToOne, edm.Multiplicity.One)):
            entity_set.bind_navigation(
                name,
                self.get_fk_class(),
                container=self,
                aset_name=aset_name)
            self.fk_table[entity_set.name][from_as_end] = (False, True)
        elif multiplicity == (edm.Multiplicity.Many, edm.Multiplicity.One):
            entity_set.bind_navigation(
                name,
                self.get_fk_class(),
                container=self,
                aset_name=aset_name)
            self.fk_table[entity_set.name][from_as_end] = (False, False)
        else:
            #           (edm.Multiplicity.Many,edm.Multiplicity.ZeroToOne)
            entity_set.bind_navigation(name, self.get_fk_class(
            ), container=self, aset_name=aset_name)
            self.fk_table[entity_set.name][from_as_end] = (True, False)

    def get_collection_class(self):
        """Returns the collection class used to represent a generic entity set.

        Override this method to provide a class derived from
        :py:class:`SQLEntityCollection` when you are customising this
        implementation for a specific database engine."""
        return SQLEntityCollection

    def get_symmetric_navigation_class(self):
        """Returns the collection class used to represent a symmetric relation.

        Override this method to provide a class derived from
        :py:class:`SQLAssociationCollection` when you are customising this
        implementation for a specific database engine."""
        return SQLAssociationCollection

    def get_fk_class(self):
        """Returns the class used when the FK is in the source table.

        Override this method to provide a class derived from
        :py:class:`SQLForeignKeyCollection` when you are customising this
        implementation for a specific database engine."""
        return SQLForeignKeyCollection

    def get_rk_class(self):
        """Returns the class used when the FK is in the target table.

        Override this method to provide a class derived from
        :py:class:`SQLReverseKeyCollection` when you are customising this
        implementation for a specific database engine."""
        return SQLReverseKeyCollection

    def create_all_tables(self, out=None):
        """Creates all tables in this container.

        out
            An optional file-like object.  If given, the tables are not
            actually created, the SQL statements are written to this
            file instead.

        Tables are created in a sensible order to ensure that foreign
        key constraints do not fail but this method is not compatible
        with databases that contain circular references though, e.g.,
        Table A -> Table B with a foreign key and Table B -> Table A
        with a foreign key.  Such databases will have to be created by
        hand. You can use the create_table_query methods to act as a
        starting point for your script."""
        visited = set()
        create_list = []
        for es in self.container.EntitySet:
            if es.name not in visited:
                self.create_table_list(es, visited, create_list)
        for es in create_list:
            with es.open() as collection:
                if out is None:
                    collection.create_table()
                else:
                    query, params = collection.create_table_query()
                    out.write(query)
                    out.write(ul(";\n\n"))
                    if params.params:
                        logging.warning("Ignoring params to CREATE TABLE: %s",
                                        to_text(params.params))
        # we now need to go through the aux_table and create them
        for aset_name in self.aux_table:
            nav_class = self.get_symmetric_navigation_class()
            if out is None:
                nav_class.create_table(self, aset_name)
            else:
                query, params = nav_class.create_table_query(self, aset_name)
                out.write(query)
                out.write(ul(";\n\n"))
                if params.params:
                    logging.warning("Ignoring params to CREATE TABLE: %s",
                                    to_text(params.params))

    def CreateAllTables(self):      # noqa
        warnings.warn("SQLEntityContainer.CreateAllTables is deprecated, "
                      "use create_all_tables",
                      DeprecationWarning,
                      stacklevel=3)
        return self.create_all_tables()

    def create_table(self, es, visited):
        # before we create this table, we need to check to see if it
        # references another table
        visited.add(es.name)
        fk_mapping = self.fk_table[es.name]
        for link_end, details in dict_items(fk_mapping):
            target_set = link_end.otherEnd.entity_set
            if target_set.name in visited:
                # prevent recursion
                continue
            self.create_table(target_set, visited)
        # now we are free to create the table
        with es.open() as collection:
            collection.create_table()

    def create_table_list(self, es, visited, create_list):
        # before we create this table, we need to check to see if it
        # references another table
        visited.add(es.name)
        fk_mapping = self.fk_table[es.name]
        for link_end, details in dict_items(fk_mapping):
            target_set = link_end.otherEnd.entity_set
            if target_set.name in visited:
                # prevent infinite recursion
                continue
            self.create_table_list(target_set, visited, create_list)
        # now we are free to create the table
        create_list.append(es)

    def drop_all_tables(self, out=None):
        """Drops all tables in this container.

        Tables are dropped in a sensible order to ensure that foreign
        key constraints do not fail, the order is essentially the
        reverse of the order used by :py:meth:`create_all_tables`."""
        # first we need to go through the aux_table and drop them
        for aset_name in self.aux_table:
            nav_class = self.get_symmetric_navigation_class()
            if out is None:
                try:
                    nav_class.drop_table(self, aset_name)
                except SQLError as e:
                    logging.warning("Ignoring : %s", str(e))
            else:
                query = nav_class.drop_table_query(self, aset_name)
                out.write(query)
                out.write(ul(";\n\n"))
        visited = set()
        drop_list = []
        for es in self.container.EntitySet:
            if es.name not in visited:
                self.create_table_list(es, visited, drop_list)
        drop_list.reverse()
        for es in drop_list:
            with es.open() as collection:
                if out is None:
                    try:
                        collection.drop_table()
                    except SQLError as e:
                        logging.warning("Ignoring : %s", str(e))
                else:
                    query = collection.drop_table_query()
                    out.write(query)
                    out.write(ul(";\n\n"))

    def acquire_connection(self, timeout=None):
        # block on the module for threadsafety==0 case
        thread = threading.current_thread()
        thread_id = thread.ident
        now = start = time.time()
        cpool_item = None
        close_flag = False
        with self.cpool_lock:
            if self.closing.is_set():
                # don't open connections when we are trying to close them
                return None
            while not self.module_lock.acquire(False):
                self.cpool_lock.wait(timeout)
                now = time.time()
                if timeout is not None and now > start + timeout:
                    logging.warning(
                        "Thread[%i] timed out waiting for the the database "
                        "module lock", thread_id)
                    return None
            # we have the module lock
            cpool_item = self.cpool_locked.get(thread_id, None)
            if cpool_item:
                # our thread_id is in the locked table
                cpool_item.locked += 1
                cpool_item.last_seen = now
            while cpool_item is None:
                if thread_id in self.cpool_unlocked:
                    # take the connection that last belonged to us
                    cpool_item = self.cpool_unlocked[thread_id]
                    del self.cpool_unlocked[thread_id]
                    logging.debug("Thread[%i] re-acquiring connection",
                                  thread_id)
                elif (self.cpool_idle):
                    # take a connection from an expired thread
                    cpool_item = self.cpool_idle.pop()
                elif self.cpool_size < self.cpool_max:
                    # Add a new connection
                    cpool_item = SQLConnection()
                    # do the actual open outside of the cpool lock
                    self.cpool_size += 1
                elif self.cpool_unlocked:
                    # take a connection that doesn't belong to us, popped at
                    # random
                    old_thread_id, cpool_item = self.cpool_unlocked.popitem()
                    if self.dbapi.threadsafety > 1:
                        logging.debug(
                            "Thread[%i] recycled database connection from "
                            "Thread[%i]", thread_id, old_thread_id)
                    else:
                        logging.debug(
                            "Thread[%i] closed an unused database connection "
                            "(max connections reached)", old_thread_id)
                        # is it ok to close a connection from a different
                        # thread?  Yes: we require it!
                        close_flag = True
                else:
                    now = time.time()
                    if timeout is not None and now > start + timeout:
                        logging.warning(
                            "Thread[%i] timed out waiting for a database "
                            "connection", thread_id)
                        break
                    logging.debug(
                        "Thread[%i] forced to wait for a database connection",
                        thread_id)
                    self.cpool_lock.wait(timeout)
                    logging.debug(
                        "Thread[%i] resuming search for database connection",
                        thread_id)
                    continue
                cpool_item.locked += 1
                cpool_item.thread = thread
                cpool_item.thread_id = thread_id
                cpool_item.last_seen = time.time()
                self.cpool_locked[thread_id] = cpool_item
        if cpool_item:
            if close_flag:
                self.close_connection(cpool_item.dbc)
                cpool_item.dbc = None
            if cpool_item.dbc is None:
                cpool_item.dbc = self.open()
            return cpool_item
        # we are defeated, no database connection for the caller
        # release lock on the module as there is no connection to release
        self.module_lock.release()
        return None

    def release_connection(self, release_item):
        thread_id = threading.current_thread().ident
        close_flag = False
        with self.cpool_lock:
            # we have exclusive use of the cpool members
            cpool_item = self.cpool_locked.get(thread_id, None)
            if cpool_item:
                if cpool_item is release_item:
                    self.module_lock.release()
                    cpool_item.locked -= 1
                    cpool_item.last_seen = time.time()
                    if not cpool_item.locked:
                        del self.cpool_locked[thread_id]
                        self.cpool_unlocked[thread_id] = cpool_item
                        self.cpool_lock.notify()
                    return
            # it seems likely that some other thread is going to leave a
            # locked connection now, let's try and find it to correct
            # the situation
            bad_thread, bad_item = None, None
            for tid, cpool_item in dict_items(self.cpool_locked):
                if cpool_item is release_item:
                    bad_thread = tid
                    bad_item = cpool_item
                    break
            if bad_item is not None:
                self.module_lock.release()
                bad_item.locked -= 1
                bad_item.last_seen = time.time()
                if not bad_item.locked:
                    del self.cpool_locked[bad_thread]
                    self.cpool_unlocked[bad_item.thread_id] = bad_item
                    self.cpool_lock.notify()
                    logging.error(
                        "Thread[%i] released database connection originally "
                        "acquired by Thread[%i]", thread_id, bad_thread)
                return
            # this is getting frustrating, exactly which connection does
            # this thread think it is trying to release?
            # Check the idle pool just in case
            bad_item = None
            for i in range3(len(self.cpool_idle)):
                cpool_item = self.cpool_idle[i]
                if cpool_item is release_item:
                    bad_item = cpool_item
                    del self.cpool_idle[i]
                    self.cpool_size -= 1
                    break
            if bad_item is not None:
                # items in the idle pool are already unlocked
                logging.error(
                    "Thread[%i] released a database connection from the "
                    "idle pool: closing for safety", thread_id)
                close_flag = True
            # ok, this really is an error!
            logging.error(
                "Thread[%i] attempted to unlock un unknown database "
                "connection: %s", thread_id, repr(release_item))
        if close_flag:
            self.close_connection(release_item.dbc)

    def connection_stats(self):
        """Return information about the connection pool

        Returns a triple of:

        nlocked
            the number of connections in use by all threads.

        nunlocked
            the number of connections waiting

        nidle
            the number of dead connections

        Connections are placed in the 'dead pool' when unexpected lock
        failures occur or if they are locked and the owning thread is
        detected to have terminated without releasing them."""
        with self.cpool_lock:
            # we have exclusive use of the cpool members
            return (len(self.cpool_locked), len(self.cpool_unlocked),
                    len(self.cpool_idle))

    def _run_pool_cleaner(self, max_idle=SQL_TIMEOUT * 10.0):
        run_time = max_idle / 5.0
        if run_time < 60.0:
            run_time = 60.0
        while not self.closing.is_set():
            self.closing.wait(run_time)
            self.pool_cleaner(max_idle)

    def pool_cleaner(self, max_idle=SQL_TIMEOUT * 10.0):
        """Cleans up the connection pool

        max_idle (float)
            Optional number of seconds beyond which an idle connection
            is closed.  Defaults to 10 times the
            :data:`SQL_TIMEOUT`."""
        now = time.time()
        old_time = now - max_idle
        to_close = []
        with self.cpool_lock:
            locked_list = list(dict_values(self.cpool_locked))
            for cpool_item in locked_list:
                if not cpool_item.thread.isAlive():
                    logging.error(
                        "Thread[%i] failed to release database connection "
                        "before terminating", cpool_item.thread_id)
                    del self.cpool_locked[cpool_item.thread_id]
                    to_close.append(cpool_item.dbc)
            unlocked_list = list(dict_values(self.cpool_unlocked))
            for cpool_item in unlocked_list:
                if not cpool_item.thread.isAlive():
                    logging.debug(
                        "pool_cleaner moving database connection to idle "
                        "after Thread[%i] terminated",
                        cpool_item.thread_id)
                    del self.cpool_unlocked[cpool_item.thread_id]
                    cpool_item.thread_id = None
                    cpool_item.thread = None
                    self.cpool_idle.append(cpool_item)
                elif (cpool_item.last_seen <= old_time and
                        self.dbapi.threadsafety <= 1):
                    logging.debug(
                        "pool_cleaner removing database connection "
                        "after Thread[%i] timed out",
                        cpool_item.thread_id)
                    del self.cpool_unlocked[cpool_item.thread_id]
                    self.cpool_size -= 1
                    to_close.append(cpool_item.dbc)
            i = len(self.cpool_idle)
            while i:
                i = i - 1
                cpool_item = self.cpool_idle[i]
                if cpool_item.last_seen <= old_time:
                    logging.info("pool_cleaner removed idle connection")
                    to_close.append(cpool_item.dbc)
                    del self.cpool_idle[i]
                    self.cpool_size -= 1
        for dbc in to_close:
            if dbc is not None:
                self.close_connection(dbc)

    def open(self):
        """Creates and returns a new connection object.

        Must be overridden by database specific implementations because
        the underlying DB ABI does not provide a standard method of
        connecting."""
        raise NotImplementedError

    def close_connection(self, connection):
        """Calls the underlying close method."""
        connection.close()

    def break_connection(self, connection):
        """Called when closing or cleaning up locked connections.

        This method is called when the connection is locked (by a
        different thread) and the caller wants to force that thread to
        relinquish control.

        The assumption is that the database is stuck in some lengthy
        transaction and that break_connection can be used to terminate
        the transaction and force an exception in the thread that
        initiated it - resulting in a subsequent call to
        :py:meth:`release_connection` and a state which enables this
        thread to acquire the connection's lock so that it can close it.

        The default implementation does nothing, which might cause the
        close method to stall until the other thread relinquishes
        control normally."""
        pass

    def close(self, timeout=5):
        """Closes this database.

        This method goes through each open connection and attempts to
        acquire it and then close it.  The object is put into a mode
        that disables :py:meth:`acquire_connection` (it returns None
        from now on).

        timeout
            Defaults to 5 seconds.  If connections are locked by other
            *running* threads we wait for those threads to release them,
            calling :py:meth:`break_connection` to speed up termination
            if possible.

            If None (not recommended!) this method will block
            indefinitely until all threads properly call
            :py:meth:`release_connection`.

        Any locks we fail to acquire in the timeout are ignored and
        the connections are left open for the python garbage
        collector to dispose of."""
        thread_id = threading.current_thread().ident
        to_close = []
        self.closing.set()
        with self.cpool_lock:
            nlocked = None
            while True:
                while self.cpool_idle:
                    cpool_item = self.cpool_idle.pop()
                    logging.error(
                        "Thread[%i] failed to release database connection "
                        "before terminating", cpool_item.thread_id)
                    to_close.append(cpool_item.dbc)
                while self.cpool_unlocked:
                    unlocked_id, cpool_item = self.cpool_unlocked.popitem()
                    to_close.append(cpool_item.dbc)
                locked_list = list(dict_values(self.cpool_locked))
                for cpool_item in locked_list:
                    if cpool_item.thread_id == thread_id:
                        logging.error(
                            "Thread[%i] failed to release database connection "
                            "before closing container", cpool_item.thread_id)
                        del self.cpool_locked[cpool_item.thread_id]
                        to_close.append(cpool_item.dbc)
                    elif not cpool_item.thread.isAlive():
                        logging.error(
                            "Thread[%i] failed to release database connection "
                            "before terminating", cpool_item.thread_id)
                        del self.cpool_locked[cpool_item.thread_id]
                        to_close.append(cpool_item.dbc)
                    else:
                        # thread is alive, try and interrupt it if it is
                        # stuck in a slow query
                        self.break_connection(cpool_item.dbc)
                if self.cpool_locked and (nlocked is None or
                                          nlocked > len(self.cpool_locked)):
                    # if this is the first time around the loop, or...
                    # if the size of the locked pool is actually
                    # shrinking, wait for locked connections to be
                    # released
                    nlocked = len(self.cpool_locked)
                    logging.warning(
                        "Waiting to break unreleased database connections")
                    self.cpool_lock.wait(timeout)
                    continue
                # we're not getting anywhere, force-close these
                # connections
                locked_list = list(dict_values(self.cpool_locked))
                for cpool_item in locked_list:
                    logging.error(
                        "Thread[%i] failed to release database connection: "
                        "forcing it to close", cpool_item.thread_id)
                    del self.cpool_locked[cpool_item.thread_id]
                    to_close.append(cpool_item.dbc)
                break
        for dbc in to_close:
            if dbc is not None:
                self.close_connection(dbc)

    def quote_identifier(self, identifier):
        """Given an *identifier* returns a safely quoted form of it.

        By default we strip double quote and then use them to enclose
        it.  E.g., if the string 'Employee_Name' is passed then the
        string '"Employee_Name"' is returned."""
        return '"%s"' % identifier.replace('"', '')

    def prepare_sql_type(self, simple_value, params, nullable=None):
        """Given a simple value, returns a SQL-formatted name of its type.

        Used to construct CREATE TABLE queries.

        simple_value
            A :py:class:`pyslet.odata2.csdl.SimpleValue` instance which
            should have been created from a suitable
            :py:class:`pyslet.odata2.csdl.Property` definition.

        params
            A :py:class:`SQLParams` object.  Not used, see
            :meth:`prepare_sql_literal`

        nullable
            Optional Boolean that can be used to override the nullable status
            of the associated property definition.

        For example, if the value was created from an Int32 non-nullable
        property and has default value 0 then this might return the
        string 'INTEGER NOT NULL DEFAULT 0'.

        You should override this implementation if your database
        platform requires special handling of certain datatypes.  The
        default mappings are given below.

        ==================  =============================================
           EDM Type         SQL Equivalent
        ------------------  ---------------------------------------------
        Edm.Binary          BINARY(MaxLength) if FixedLength specified
        Edm.Binary          VARBINARY(MaxLength) if no FixedLength
        Edm.Boolean         BOOLEAN
        Edm.Byte            SMALLINT
        Edm.DateTime        TIMESTAMP
        Edm.DateTimeOffset  CHARACTER(27), ISO 8601 string
                            representation is used with micro second
                            precision
        Edm.Decimal         DECIMAL(Precision,Scale), defaults 10,0
        Edm.Double          FLOAT
        Edm.Guid            BINARY(16)
        Edm.Int16           SMALLINT
        Edm.Int32           INTEGER
        Edm.Int64           BIGINT
        Edm.SByte           SMALLINT
        Edm.Single          REAL
        Edm.String          CHAR(MaxLength) or VARCHAR(MaxLength)
        Edm.String          NCHAR(MaxLength) or NVARCHAR(MaxLength) if
                            Unicode="true"
        Edm.Time            TIME
        ==================  =============================================

        Parameterized CREATE TABLE queries are unreliable in my
        experience so the current implementation of the native
        create_table methods ignore default values when calling this
        method."""
        p = simple_value.p_def
        column_def = []
        if isinstance(simple_value, edm.BinaryValue):
            if p is None:
                raise NotImplementedError(
                    "SQL binding for Edm.Binary of unbounded length: %s" %
                    p.name)
            elif p.fixedLength:
                if p.maxLength:
                    column_def.append("BINARY(%i)" % p.maxLength)
                else:
                    raise edm.ModelConstraintError(
                        "Edm.Binary of fixed length missing max: %s" % p.name)
            elif p.maxLength:
                column_def.append("VARBINARY(%i)" % p.maxLength)
            else:
                raise NotImplementedError(
                    "SQL binding for Edm.Binary of unbounded length: %s" %
                    p.name)
        elif isinstance(simple_value, edm.BooleanValue):
            column_def.append("BOOLEAN")
        elif isinstance(simple_value, edm.ByteValue):
            column_def.append("SMALLINT")
        elif isinstance(simple_value, edm.DateTimeValue):
            column_def.append("TIMESTAMP")
        elif isinstance(simple_value, edm.DateTimeOffsetValue):
            # stored as string and parsed e.g. 20131209T100159.000000+0100
            # need to check the precision and that in to the mix
            column_def.append("CHARACTER(27)")
        elif isinstance(simple_value, edm.DecimalValue):
            if p.precision is None:
                precision = 10  # chosen to allow 32-bit integer precision
            else:
                precision = p.precision
            if p.scale is None:
                scale = 0       # from the CSDL model specification
            else:
                scale = p.scale
            column_def.append("DECIMAL(%i,%i)" % (precision, scale))
        elif isinstance(simple_value, edm.DoubleValue):
            column_def.append("FLOAT")
        elif isinstance(simple_value, edm.GuidValue):
            column_def.append("BINARY(16)")
        elif isinstance(simple_value, edm.Int16Value):
            column_def.append("SMALLINT")
        elif isinstance(simple_value, edm.Int32Value):
            column_def.append("INTEGER")
        elif isinstance(simple_value, edm.Int64Value):
            column_def.append("BIGINT")
        elif isinstance(simple_value, edm.SByteValue):
            column_def.append("SMALLINT")
        elif isinstance(simple_value, edm.SingleValue):
            column_def.append("REAL")
        elif isinstance(simple_value, edm.StringValue):
            if p.unicode is None or p.unicode:
                n = "N"
            else:
                n = ""
            if p.fixedLength:
                if p.maxLength:
                    column_def.append("%sCHAR(%i)" % (n, p.maxLength))
                else:
                    raise edm.ModelConstraintError(
                        "Edm.String of fixed length missing max: %s" % p.name)
            elif p.maxLength:
                column_def.append("%sVARCHAR(%i)" % (n, p.maxLength))
            else:
                raise NotImplementedError(
                    "SQL binding for Edm.String of unbounded length: %s" %
                    p.name)
        elif isinstance(simple_value, edm.TimeValue):
            column_def.append("TIME")
        else:
            raise NotImplementedError("SQL type for %s" % p.type)
        if ((nullable is not None and not nullable) or
                (nullable is None and p is not None and not p.nullable)):
            column_def.append(' NOT NULL')
        if simple_value:
            # Format the default
            column_def.append(' DEFAULT %s' %
                              self.prepare_sql_literal(simple_value))
        return ''.join(column_def)

    def prepare_sql_value(self, simple_value):
        """Returns a python object suitable for passing as a parameter

        simple_value
                A :py:class:`pyslet.odata2.csdl.SimpleValue` instance.

        You should override this method if your database requires
        special handling of parameter values.  The default
        implementation performs the following conversions

        ==================  =======================================
           EDM Type         Python value added as parameter
        ------------------  ---------------------------------------
        NULL                None
        Edm.Binary          (byte) string
        Edm.Boolean         True or False
        Edm.Byte            int
        Edm.DateTime        Timestamp instance from DB API module
        Edm.DateTimeOffset  string (ISO 8601 basic format)
        Edm.Decimal         Decimal instance
        Edm.Double          float
        Edm.Guid            (byte) string
        Edm.Int16           int
        Edm.Int32           int
        Edm.Int64           long
        Edm.SByte           int
        Edm.Single          float
        Edm.String          (unicode) string
        Edm.Time            Time instance from DB API module
        ==================  =======================================
        """
        if not simple_value:
            return None
        elif isinstance(simple_value, (
                edm.BooleanValue,
                edm.BinaryValue,
                edm.ByteValue,
                edm.DecimalValue,
                edm.DoubleValue,
                edm.Int16Value,
                edm.Int32Value,
                edm.Int64Value,
                edm.SByteValue,
                edm.SingleValue,
                edm.StringValue
        )):
            return simple_value.value
        elif isinstance(simple_value, edm.DateTimeValue):
            microseconds, seconds = math.modf(simple_value.value.time.second)
            return self.dbapi.Timestamp(
                simple_value.value.date.century *
                100 + simple_value.value.date.year,
                simple_value.value.date.month,
                simple_value.value.date.day,
                simple_value.value.time.hour,
                simple_value.value.time.minute,
                int(seconds), int(1000000.0 * microseconds + 0.5))
        elif isinstance(simple_value, edm.DateTimeOffsetValue):
            return simple_value.value.get_calendar_string(
                basic=True, ndp=6, dp=".").ljust(27, ' ')
        elif isinstance(simple_value, edm.GuidValue):
            return simple_value.value.bytes
        elif isinstance(simple_value, edm.TimeValue):
            return self.dbapi.Time(
                simple_value.value.hour,
                simple_value.value.minute,
                simple_value.value.second)
        else:
            raise NotImplementedError(
                "SQL type for " + simple_value.__class__.__name__)

    def read_sql_value(self, simple_value, new_value):
        """Updates *simple_value* from *new_value*.

        simple_value
                A :py:class:`pyslet.odata2.csdl.SimpleValue` instance.

        new_value
                A value returned by the underlying DB API, e.g., from a cursor
                fetch  operation

        This method performs the reverse transformation to
        :py:meth:`prepare_sql_value` and may need to be overridden to
        convert *new_value* into a form suitable for passing to the
        underlying
        :py:meth:`~pyslet.odata2.csdl.SimpleValue.set_from_value`
        method."""
        if new_value is None:
            simple_value.set_null()
        elif isinstance(simple_value, (edm.DateTimeOffsetValue)):
            # we stored these as strings
            simple_value.set_from_value(
                iso.TimePoint.from_str(new_value, tdesignators="T "))
        else:
            simple_value.set_from_value(new_value)

    def new_from_sql_value(self, sql_value):
        """Returns a new simple value with value *sql_value*

        The return value is a :py:class:`pyslet.odata2.csdl.SimpleValue`
        instance.

        sql_value
            A value returned by the underlying DB API, e.g., from a
            cursor fetch  operation

        This method creates a new instance, selecting the most
        appropriate type to represent sql_value.  By default
        :py:meth:`pyslet.odata2.csdl.EDMValue.from_value`
        is used.

        You may need to override this method to identify the appropriate
        value type."""
        return edm.EDMValue.from_value(sql_value)

    def prepare_sql_literal(self, value):
        """Formats a simple value as a SQL literal

        Although SQL containers use parameterised queries for all
        INSERT, SELECT, UPDATE and DELETE queries, CREATE TABLE queries
        are generally only created when the data model has been designed
        using the OData data model and are intended to be exported as
        SQL scripts for review (and perhaps modification) by a DBA prior
        to being run on a real database server as part of initially
        provisioning a running system.  In this case, default values in
        the data model must be inserted into the CREATE TABLE query
        itself and so a method is provided for transforming values
        accordingly."""
        if not value:
            return "NULL"
        elif isinstance(value, edm.BinaryValue):
            return "X'%s'" % str(value)
        elif isinstance(value, edm.BooleanValue):
            return "TRUE" if value.value else "FALSE"
        elif isinstance(value, (edm.ByteValue, edm.DecimalValue,
                                edm.DoubleValue, edm.Int16Value,
                                edm.Int32Value, edm.Int64Value,
                                edm.SingleValue, edm.SByteValue, )):
            return str(value.value)
        elif isinstance(value, (edm.DateTimeValue, edm.DateTimeOffsetValue,
                                edm.TimeValue)):
            return "'%s'" % str(value.value)
        elif isinstance(value, edm.GuidValue):
            return "X'%s'" % binascii.hexlify(
                value.value.bytes).decode('ascii')
        elif isinstance(value, edm.StringValue):
            return "'%s'" % value.value.replace("'", "''")
        else:
            raise NotImplementedError

    def select_limit_clause(self, skip, top):
        """Returns a SELECT modifier to limit a query

        See :meth:`limit_clause` for details of the parameters.

        Returns a tuple of:

        skip
            0 if the modifier implements this functionality.  If it does
            not implement this function then the value passed in for
            skip *must* be returned.

        modifier
            A string modifier to insert immediately after the SELECT
            statement (must be empty or end with a space).

        For example, if your database supports the TOP keyword you might
        return::

            (skip, 'TOP %i' % top)

        This will result in queries such as::

            SELECT TOP 10 FROM ....

        More modern syntax tends to use a special limit clause at the
        end of the query, rather than a SELECT modifier.  The default
        implementation returns::

            (skip, '')

        ...essentially doing nothing."""
        return (skip, '')

    def limit_clause(self, skip, top):
        """Returns a limit clause to limit a query

        skip
            An integer number of entities to skip

        top
            An integer number of entities to limit the result set of a
            query or None is no limit is desired.

        Returns a tuple of:

        skip
            0 if the limit clause implements this functionality.  If it
            does not implement this function then the value passed in
            for skip *must* be returned.

        clause
            A limit clause to append to the query.  Must be empty or end
            with a space.

        For example, if your database supports the MySQL-style LIMIT and
        OFFSET keywords you would return (for non-None values of top)::

            (0, 'LIMIT %i OFFSET %i' % (top, skip))

        This will result in queries such as::

            SELECT * FROM Customers LIMIT 10 OFFSET 20

        More modern syntax tends to use a special limit clause at the
        end of the query, rather than a SELECT modifier.  Such as::

            (skip, 'FETCH FIRST %i ROWS ONLY ' % top)

        This syntax is part of SQL 2008 standard but is not widely
        adopted and, for compatibility with existing external database
        implementation, the default implementation remains blank."""
        return (skip, '')


class SQLiteEntityContainer(SQLEntityContainer):

    """Creates a container that represents a SQLite database.

    Additional keyword arguments:

    file_path
            The path to the SQLite database file.

    sqlite_options
        A dictionary of additional options to pass as named arguments to
        the connect method.  It defaults to an empty dictionary, you
        won't normally need to pass additional options and you shouldn't
        change the isolation_level as the collection classes have been
        designed to work in the default mode.  Also, check_same_thread
        is forced to False, this is poorly documented but we only do it
        so that we can close a connection in a different thread from the
        one that opened it when cleaning up.

        For more information see sqlite3_

    ..  _sqlite3:   https://docs.python.org/2/library/sqlite3.html

    All other keyword arguments required to initialise the base class
    must be passed on construction except *dbapi* which is automatically
    set to the Python sqlite3 module."""

    def __init__(self, file_path, sqlite_options={}, **kwargs):
        if is_text(file_path) and file_path == ":memory:":
            if (('max_connections' in kwargs and
                    kwargs['max_connections'] != 1) or
                    'max_connections' not in kwargs):
                logging.warning("Forcing max_connections=1 for in-memory "
                                "SQLite database")
            kwargs['max_connections'] = 1
            self.sqlite_memdbc = sqlite3.connect(
                ":memory:", check_same_thread=False, **sqlite_options)
        else:
            self.sqlite_memdbc = None
        super(SQLiteEntityContainer, self).__init__(dbapi=sqlite3, **kwargs)
        if (not isinstance(file_path, OSFilePath) and not is_text(file_path)):
            raise TypeError("SQLiteDB requires an OS file path")
        self.file_path = file_path
        self.sqlite_options = sqlite_options

    def get_collection_class(self):
        """Overridden to return :py:class:`SQLiteEntityCollection`"""
        return SQLiteEntityCollection

    def get_symmetric_navigation_class(self):
        """Overridden to return :py:class:`SQLiteAssociationCollection`"""
        return SQLiteAssociationCollection

    def get_fk_class(self):
        """Overridden to return :py:class:`SQLiteForeignKeyCollection`"""
        return SQLiteForeignKeyCollection

    def get_rk_class(self):
        """Overridden to return :py:class:`SQLiteReverseKeyCollection`"""
        return SQLiteReverseKeyCollection

    def open(self):
        """Calls the underlying connect method.

        Passes the file_path used to construct the container as the only
        parameter.  You can pass the string ':memory:' to create an
        in-memory database.

        Other connection arguments are not currently supported, you can
        derive a more complex implementation by overriding this method
        and (optionally) the __init__ method to pass in values for ."""
        if self.sqlite_memdbc is not None:
            return self.sqlite_memdbc
        dbc = self.dbapi.connect(str(self.file_path), check_same_thread=False,
                                 **self.sqlite_options)
        c = dbc.cursor()
        c.execute("PRAGMA foreign_keys = ON")
        c.close()
        return dbc

    def break_connection(self, connection):
        """Calls the underlying interrupt method."""
        connection.interrupt()

    def close_connection(self, connection):
        """Calls the underlying close method."""
        if self.sqlite_memdbc is None:
            connection.close()

    def close(self):
        super(SQLiteEntityContainer, self).close()
        # close any in-memory database
        if self.sqlite_memdbc is not None:
            self.sqlite_memdbc.close()

    def prepare_sql_type(self, simple_value, params, nullable=None):
        """Performs SQLite custom mappings

        ==================  ===================================
           EDM Type         SQLite Equivalent
        ------------------  -----------------------------------
        Edm.Binary          BLOB
        Edm.Decimal         TEXT
        Edm.Guid            BLOB
        Edm.String          TEXT
        Edm.Time            REAL
        Edm.Int64           INTEGER
        ==================  ===================================

        The remainder of the type mappings use the defaults from the
        parent class."""
        p = simple_value.p_def
        column_def = []
        if isinstance(simple_value, (edm.StringValue, edm.DecimalValue)):
            column_def.append("TEXT")
        elif isinstance(simple_value, (edm.BinaryValue, edm.GuidValue)):
            column_def.append("BLOB")
        elif isinstance(simple_value, edm.TimeValue):
            column_def.append("REAL")
        elif isinstance(simple_value, edm.Int64Value):
            column_def.append("INTEGER")
        else:
            return super(
                SQLiteEntityContainer,
                self).prepare_sql_type(
                simple_value,
                params,
                nullable)
        if ((nullable is not None and not nullable) or
                (nullable is None and p is not None and not p.nullable)):
            column_def.append(' NOT NULL')
        if simple_value:
            # Format the default
            column_def.append(' DEFAULT %s' %
                              self.prepare_sql_literal(simple_value))
        return ''.join(column_def)

    def prepare_sql_value(self, simple_value):
        """Returns a python value suitable for passing as a parameter.

        We inherit most of the value mappings but the following types
        have custom mappings.

        ==================  ==============================================
           EDM Type         Python value added as parameter
        ------------------  ----------------------------------------------
        Edm.Binary          buffer object
        Edm.Decimal         string representation obtained with str()
        Edm.Guid            buffer object containing bytes representation
        Edm.Time            value of
                            :py:meth:`pyslet.iso8601.Time.get_total_seconds`
        ==================  ==============================================

        Our use of buffer type is not ideal as it generates warning when
        Python is run with the -3 flag (to check for Python 3
        compatibility) but it seems unavoidable at the current time."""
        if not simple_value:
            return None
        elif isinstance(simple_value, edm.BinaryValue):
            return buffer2(simple_value.value)
        elif isinstance(simple_value, edm.DecimalValue):
            return str(simple_value.value)
        elif isinstance(simple_value, edm.GuidValue):
            return buffer2(simple_value.value.bytes)
        elif isinstance(simple_value, edm.TimeValue):
            return simple_value.value.get_total_seconds()
        else:
            return super(
                SQLiteEntityContainer,
                self).prepare_sql_value(simple_value)

    def read_sql_value(self, simple_value, new_value):
        """Reverses the transformation performed by prepare_sql_value"""
        if new_value is None:
            simple_value.set_null()
        elif isinstance(new_value, buffer2):
            new_value = bytes(new_value)
            simple_value.set_from_value(new_value)
        elif isinstance(simple_value,
                        (edm.DateTimeValue, edm.DateTimeOffsetValue)):
            # SQLite stores these as strings
            simple_value.set_from_value(
                iso.TimePoint.from_str(new_value, tdesignators="T "))
        elif isinstance(simple_value, edm.TimeValue):
            simple_value.value = iso.Time(total_seconds=new_value)
        elif isinstance(simple_value, edm.DecimalValue):
            simple_value.value = decimal.Decimal(new_value)
        else:
            simple_value.set_from_value(new_value)

    def new_from_sql_value(self, sql_value):
        """Returns a new simple value instance initialised from *sql_value*

        Overridden to ensure that buffer objects returned by the
        underlying DB API are converted to strings.  Otherwise
        *sql_value* is passed directly to the parent."""
        if isinstance(sql_value, buffer2):
            result = edm.BinaryValue()
            result.set_from_value(bytes(sql_value))
            return result
        else:
            return super(SQLiteEntityContainer, self).new_from_sql_value(
                sql_value)

    def prepare_sql_literal(self, value):
        """Formats a simple value as a SQL literal

        Overridden for custom SQLite mappings."""
        if not value:
            return "NULL"
        elif isinstance(value, edm.BooleanValue):
            return "1" if value.value else "0"
        elif isinstance(value, edm.TimeValue):
            return str(value.value.get_total_seconds())
        else:
            return super(SQLiteEntityContainer, self).prepare_sql_literal(
                value)

    def limit_clause(self, skip, top):
        clause = []
        if top:
            clause.append('LIMIT %i ' % top)
        if skip:
            clause.append('OFFSET %i ' % skip)
            skip = 0
        return skip, ''.join(clause)


class SQLiteEntityCollectionBase(SQLCollectionBase):

    """Base class for SQLite SQL custom mappings.

    This class provides some SQLite specific mappings for certain
    functions to improve compatibility with the OData expression
    language."""

    DEFAULT_VALUE = False
    """SQLite does not support setting a value =DEFAULT"""

    def sql_expression_substring(self, expression, params, context):
        """Converts the substring method

        maps to substr( op[0], op[1] [, op[2] ] )

        Few databases seem to actually support the standard syntax using
        FROM ... [FOR ...].  SQLite is no exception."""
        query = ["substr("]
        query.append(self.sql_expression(expression.operands[0], params, ','))
        query.append(", ")
        query.append(self.sql_expression(expression.operands[1], params, ','))
        if len(expression.operands) > 2:
            query.append(", ")
            query.append(
                self.sql_expression(expression.operands[2], params, ','))
        query.append(")")
        return ''.join(query)

    def sql_expression_length(self, expression, params, context):
        """Converts the length method: maps to length( op[0] )"""
        query = ["length("]
        query.append(self.sql_expression(expression.operands[0], params, ','))
        query.append(")")
        return ''.join(query)  # don't bother with brackets!

    def sql_expression_year(self, expression, params, context):
        """Converts the year method

        maps to CAST(strftime('%Y',op[0]) AS INTEGER)"""
        query = ["CAST(strftime('%Y',"]
        query.append(self.sql_expression(expression.operands[0], params, ','))
        query.append(") AS INTEGER)")
        return ''.join(query)  # don't bother with brackets!

    def sql_expression_month(self, expression, params, context):
        """Converts the month method

        maps to  CAST(strftime('%m',op[0]) AS INTEGER)"""
        query = ["CAST(strftime('%m',"]
        query.append(self.sql_expression(expression.operands[0], params, ','))
        query.append(") AS INTEGER)")
        return ''.join(query)  # don't bother with brackets!

    def sql_expression_day(self, expression, params, context):
        """Converts the day method

        maps to  CAST(strftime('%d',op[0]) AS INTEGER)"""
        query = ["CAST(strftime('%d',"]
        query.append(self.sql_expression(expression.operands[0], params, ','))
        query.append(") AS INTEGER)")
        return ''.join(query)  # don't bother with brackets!

    def sql_expression_hour(self, expression, params, context):
        """Converts the hour method

        maps to  CAST(strftime('%H',op[0]) AS INTEGER)"""
        query = ["CAST(strftime('%H',"]
        query.append(self.sql_expression(expression.operands[0], params, ','))
        query.append(") AS INTEGER)")
        return ''.join(query)  # don't bother with brackets!

    def sql_expression_minute(self, expression, params, context):
        """Converts the minute method

        maps to  CAST(strftime('%M',op[0]) AS INTEGER)"""
        query = ["CAST(strftime('%M',"]
        query.append(self.sql_expression(expression.operands[0], params, ','))
        query.append(") AS INTEGER)")
        return ''.join(query)  # don't bother with brackets!

    def sql_expression_second(self, expression, params, context):
        """Converts the second method

        maps to  CAST(strftime('%S',op[0]) AS INTEGER)"""
        query = ["CAST(strftime('%S',"]
        query.append(self.sql_expression(expression.operands[0], params, ','))
        query.append(") AS INTEGER)")
        return ''.join(query)  # don't bother with brackets!

    def sql_expression_tolower(self, expression, params, context):
        """Converts the tolower method

        maps to lower(op[0])"""
        query = ["lower("]
        query.append(self.sql_expression(expression.operands[0], params, ','))
        query.append(")")
        return ''.join(query)  # don't bother with brackets!

    def sql_expression_toupper(self, expression, params, context):
        """Converts the toupper method

        maps to upper(op[0])"""
        query = ["upper("]
        query.append(self.sql_expression(expression.operands[0], params, ','))
        query.append(")")
        return ''.join(query)  # don't bother with brackets!


class SQLiteEntityCollection(SQLiteEntityCollectionBase, SQLEntityCollection):

    """SQLite-specific collection for entity sets"""

    def where_last(self, entity, params):
        """In SQLite all tables have a ROWID concept"""
        return ' WHERE ROWID = last_insert_rowid()'


class SQLiteAssociationCollection(
        SQLiteEntityCollectionBase,
        SQLAssociationCollection):

    """SQLite-specific collection for symmetric association sets"""
    pass


class SQLiteForeignKeyCollection(
        SQLiteEntityCollectionBase,
        SQLForeignKeyCollection):

    """SQLite-specific collection for navigation from a foreign key"""
    pass


class SQLiteReverseKeyCollection(
        SQLiteEntityCollectionBase,
        SQLReverseKeyCollection):

    """SQLite-specific collection for navigation to a foreign key"""
    pass


class SQLiteStreamStore(blockstore.StreamStore):

    """A stream store backed by a SQLite database.

    file_path
        The path to the SQLite database file.

    dpath
        The optional directory path to the file system to use for
        storing the blocks of data. If dpath is None then the blocks are
        stored in the SQLite database itself."""

    def load_container(self):
        """Loads and returns a default entity container

        The return value is a
        :py:class:`pyslet.odata2.csdl.EntityContainer` instance with
        an EntitySets called 'Blocks', 'Locks' and 'Streams' that are
        suitable for passing to the constructors of
        :py:class:`pyslet.blockstore.BlockStore`,
        :py:class:`pyslet.blockstore.LockStore` and
        :py:class:`pyslet.blockstore.StreamStore`
        respectively."""
        doc = edmx.Document()
        with io.open(os.path.join(os.path.dirname(__file__),
                                  'streamstore.xml'), 'rb') as f:
            doc.read(f)
        return doc.root.DataServices['StreamStoreSchema.Container']

    def __init__(self, file_path, dpath=None):
        self.container_def = self.load_container()
        if isinstance(file_path, OSFilePath):
            file_path = str(file_path)
        create = not os.path.exists(file_path)
        self.container = SQLiteEntityContainer(file_path=file_path,
                                               container=self.container_def)
        if create:
            self.container.create_all_tables()
        if dpath is None:
            bs = blockstore.FileBlockStore(dpath)
        else:
            bs = blockstore.EDMBlockStore(
                entity_set=self.container_def['Blocks'])
        ls = blockstore.LockStore(entity_set=self.container_def['Locks'])
        blockstore.StreamStore.__init__(
            self, bs, ls, self.container_def['Streams'])
