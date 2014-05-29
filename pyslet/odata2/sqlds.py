#! /usr/bin/env python
"""This module implements the Open Data Protocol specification defined by Microsoft."""


import sqlite3
import hashlib
import StringIO
import time
import string
import sys
import traceback
import threading
import decimal
import uuid
import math
import logging
from types import *

from pyslet.vfs import OSFilePath
import pyslet.iso8601 as iso
import csdl as edm
import core
import metadata


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

            "name" LIKE ?+?+? ; params=[u'%',u"Smith",u'%']"""
    pass


class SQLParams(object):

    """An abstract class used to build parameterized queries.

    Python's DB API support three different conventions for specifying
    parameters and each module indicates the convention in use.  The SQL
    construction methods in this module abstract away this variability
    for maximum portability using different implementations of the basic
    SQLParams class."""

    def __init__(self):
        # : an object suitable for passing to DB API's execute method
        self.params = None

    def AddParam(self, value):
        """Adds a value to this set of parameters returning the string to include in the query

        value:
                The native representation of the value in a format suitable
                for passing to the underlying DB API."""
        raise NotImplementedError


class QMarkParams(SQLParams):

    """A class for building parameter lists using '?' syntax."""

    def __init__(self):
        super(QMarkParams, self).__init__()
        self.params = []

    def AddParam(self, value):
        self.params.append(value)
        return "?"


class NumericParams(SQLParams):

    """A class for building parameter lists using ':1', ':2',... syntax"""

    def __init__(self):
        super(QMarkParams, self).__init__()
        self.params = []

    def AddParam(self, value):
        self.params.append(value)
        return ":%i" % len(self.params)


class NamedParams(SQLParams):

    """A class for building parameter lists using ':A', ':B",... syntax

    Although there is more freedom with named parameters, in order to
    support the ordered lists of the other formats we just invent
    parameter names using ':p1', ':p2', etc."""

    def __init__(self):
        super(QMarkParams, self).__init__()
        self.params = {}

    def AddParam(self, value):
        name = "p%i" % len(self.params)
        self.params[name] = value
        return ":" + name


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

            t=SQLTransaction(db_module,db_connection)
            try:
                    t.Begin()
                    t.Execute("UPDATE SOME_TABLE SET SOME_COL='2'")
                    t.Commit()
            except Exception as e:
                    t.Rollback(e)
            finally:
                    t.Close(e)

    The transaction object can be passed to a sub-method between the
    Begin and Commit calls provided that method follows the same pattern
    as the above for the try, except and finally blocks.  The object
    keeps track of these 'nested' transactions and delays the commit or
    rollback until the outermost method invokes them."""

    def __init__(self, api, dbc):
        self.api = api			#: the database module
        self.dbc = dbc			#: the database connection
        #: the database cursor to use for executing commands
        self.cursor = None
        self.noCommit = 0			#: used to manage nested transactions
        self.queryCount = 0		#: records the number of successful commands

    def Begin(self):
        """Begins a transaction

        If a transaction is already in progress a nested transaction is
        started which has no affect on the database connection itself."""
        if self.cursor is None:
            self.cursor = self.dbc.cursor()
        else:
            self.noCommit += 1

    def Execute(self, sqlCmd, params):
        """Executes *sqlCmd* as part of this transaction.

        sqlCmd
                A string containing the query

        params
                A :py:class:`SQLParams` object containing any
                parameterized values."""
        self.cursor.execute(sqlCmd, params.params)
        self.queryCount += 1

    def Commit(self):
        """Ends this transaction with a commit

        Nested transactions do nothing."""
        if self.noCommit:
            return
        self.dbc.commit()

    def Rollback(self, err=None, swallowErr=False):
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

        swallowErr
                A flag (defaults to False) indicating that *err* should be
                swallowed, rather than re-raised."""
        if not self.noCommit:
            try:
                self.dbc.rollback()
                if err is not None:
                    logging.info(
                        "Rollback invoked for transaction following error %s", str(err))
            except self.api.NotSupportedError:
                if err is not None:
                    if transaction.queryCount:
                        logging.error(
                            "Data Integrity Error on TABLE %s: Rollback invoked on a connection that does not support transactions after error %s", self.tableName, str(err))
                    else:
                        logging.info(
                            "Query failed following error %s", str(err))
                pass
        if err is not None and not swallowErr:
            logging.debug(
                string.join(traceback.format_exception(*sys.exc_info(), limit=3)))
            if isinstance(err, self.api.Error):
                raise SQLError(str(err))
            else:
                raise err

    def Close(self):
        """Closes this transaction after a rollback or commit.

        Each call to :py:meth:`Begin` MUST be balanced with one call to
        Close."""
        if self.noCommit:
            self.noCommit = self.noCommit - 1
        elif self.cursor is not None:
            self.cursor.close()
            self.cursor = None
            self.queryCount = 0


class SQLCollectionBase(core.EntityCollection):

    """A base class to provide core SQL functionality.

    Additional keyword arguments:

    container
            A :py:class:`SQLEntityContainer` instance.

    qualifyNames
            An optional boolean (defaults to False) indicating whether or not
            the column names must be qualified in all queries.

    On construction a data connection is acquired from *container*, this
    may prevent other threads from using the database until the lock is
    released by the :py:meth:`close` method."""

    def __init__(self, container, qualifyNames=False, **kwArgs):
        super(SQLCollectionBase, self).__init__(**kwArgs)
        #: the parent container (database) for this collection
        self.container = container
        # : the quoted table name containing this collection
        self.tableName = self.container.mangledNames[(self.entitySet.name,)]
        # : if True, field names in expressions are qualified with :py:attr:`tableName`
        self.qualifyNames = qualifyNames
        self.OrderBy(None)				# force orderNames to be initialised
        self.dbc = None					#: a connection to the database
        self._sqlLen = None
        self._sqlGen = None
        try:
            self.dbc = self.container.AcquireConnection(SQL_TIMEOUT)
            if self.dbc is None:
                raise DatabaseBusy(
                    "Failed to acquire connection after %is" % SQL_TIMEOUT)
        except:
            self.close()
            raise

    def close(self):
        """Closes the cursor and database connection if they are open."""
        if self.dbc is not None:
            self.container.ReleaseConnection(self.dbc)
            self.dbc = None

    def __len__(self):
        if self._sqlLen is None:
            query = ["SELECT COUNT(*) FROM %s" % self.tableName]
            params = self.container.ParamsClass()
            query.append(self.JoinClause())
            query.append(self.WhereClause(None, params))
            query = string.join(query, '')
            self._sqlLen = (query, params)
        else:
            query, params = self._sqlLen
        transaction = SQLTransaction(self.container.dbapi, self.dbc)
        try:
            transaction.Begin()
            logging.info("%s; %s", query, unicode(params.params))
            transaction.Execute(query, params)
            # get the result
            result = transaction.cursor.fetchone()[0]
            # we haven't changed the database, but we don't want to
            # leave the connection idle in transaction
            transaction.Commit()
            return result
        except Exception as e:
            # we catch (almost) all exceptions and re-raise after rollback
            transaction.Rollback(e)
        finally:
            transaction.Close()

    def entityGenerator(self):
        entity, values = None, None
        if self._sqlGen is None:
            entity = self.NewEntity()
            query = ["SELECT "]
            params = self.container.ParamsClass()
            columnNames, values = zip(*list(self.FieldGenerator(entity)))
            # values is used later for the first result
            columnNames = list(columnNames)
            self.OrderByCols(columnNames, params)
            query.append(string.join(columnNames, ", "))
            query.append(' FROM ')
            query.append(self.tableName)
            query.append(self.JoinClause())
            query.append(
                self.WhereClause(None, params, useFilter=True, useSkip=False))
            query.append(self.OrderByClause())
            query = string.join(query, '')
            self._sqlGen = query, params
        else:
            query, params = self._sqlGen
        transaction = SQLTransaction(self.container.dbapi, self.dbc)
        try:
            transaction.Begin()
            logging.info("%s; %s", query, unicode(params.params))
            transaction.Execute(query, params)
            while True:
                row = transaction.cursor.fetchone()
                if row is None:
                    break
                if entity is None:
                    entity = self.NewEntity()
                    values = zip(*list(self.FieldGenerator(entity)))[1]
                for value, newValue in zip(values, row):
                    self.container.ReadSQLValue(value, newValue)
                entity.exists = True
                yield entity
                entity, values = None, None
            # we haven't changed the database, but we don't want to
            # leave the connection idle in transaction
            transaction.Commit()
        except Exception as e:
            transaction.Rollback(e)
        finally:
            transaction.Close()

    def itervalues(self):
        return self.ExpandEntities(
            self.entityGenerator())

    def SetPage(self, top, skip=0, skiptoken=None):
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
                p.ParseWSP()
                self.skiptoken.append(p.RequireProduction(p.ParseURILiteral()))
                p.ParseWSP()
                if not p.Parse(','):
                    if p.MatchEnd():
                        break
                    else:
                        raise core.InvalidSystemQueryOption(
                            "Unrecognized $skiptoken: %s" % skiptoken)
            if self.orderby is None:
                orderLen = 0
            else:
                orderLen = len(self.orderby)
            if len(self.skiptoken) == orderLen + len(self.entitySet.keys) + 1:
                # the last value must be an integer we add to skip
                if isinstance(self.skiptoken[-1], edm.Int32Value):
                    self.skip += self.skiptoken[-1].value
                    self.skiptoken = self.skiptoken[:-1]
                else:
                    raise core.InvalidSystemQueryOption(
                        "skiptoken incompatible with ordering: %s" % skiptoken)
            elif len(self.skiptoken) != orderLen + len(self.entitySet.keys):
                raise core.InvalidSystemQueryOption(
                    "skiptoken incompatible with ordering: %s" % skiptoken)
        self.nextSkiptoken = None

    def NextSkipToken(self):
        if self.nextSkiptoken:
            token = []
            for t in self.nextSkiptoken:
                token.append(core.ODataURI.FormatLiteral(t))
            return string.join(token, u",")
        else:
            return None

    def pageGenerator(self, setNextPage=False):
        if self.top == 0:
            # end of paging
            return
        entity = self.NewEntity()
        query = ["SELECT "]
        params = self.container.ParamsClass()
        columnNames, values = zip(*list(self.FieldGenerator(entity)))
        columnNames = list(columnNames)
        self.OrderByCols(columnNames, params, True)
        query.append(string.join(columnNames, ", "))
        query.append(' FROM ')
        query.append(self.tableName)
        query.append(self.JoinClause())
        query.append(
            self.WhereClause(None, params, useFilter=True, useSkip=True))
        query.append(self.OrderByClause())
        query = string.join(query, '')
        transaction = SQLTransaction(self.container.dbapi, self.dbc)
        try:
            skip = self.skip
            top = self.top
            topmax = self.topmax
            transaction.Begin()
            logging.info("%s; %s", query, unicode(params.params))
            transaction.Execute(query, params)
            while True:
                row = transaction.cursor.fetchone()
                if row is None:
                    # no more pages
                    if setNextPage:
                        self.top = self.skip = 0
                        self.skipToken = None
                    break
                if skip:
                    skip = skip - 1
                    continue
                if entity is None:
                    entity = self.NewEntity()
                    values = zip(*list(self.FieldGenerator(entity)))[1]
                rowValues = list(row)
                for value, newValue in zip(values, rowValues):
                    self.container.ReadSQLValue(value, newValue)
                entity.exists = True
                yield entity
                if topmax is not None:
                    topmax = topmax - 1
                    if topmax < 1:
                        # this is the last entity, set the nextSkiptoken
                        orderValues = rowValues[-len(self.orderNames):]
                        self.nextSkiptoken = []
                        for v in orderValues:
                            self.nextSkiptoken.append(
                                self.container.NewFromSQLValue(v))
                        tokenLen = 0
                        for v in self.nextSkiptoken:
                            if v and isinstance(v, (edm.StringValue, edm.BinaryValue)):
                                tokenLen += len(v.value)
                        # a really large skiptoken is no use to anyone
                        if tokenLen > 512:
                            # ditch this one, copy the previous one and add a
                            # skip
                            self.nextSkiptoken = list(self.skiptoken)
                            v = edm.Int32Value()
                            v.SetFromValue(self.topmax)
                            self.nextSkiptoken.append(v)
                        if setNextPage:
                            self.skiptoken = self.nextSkiptoken
                            self.skip = 0
                        break
                if top is not None:
                    top = top - 1
                    if top < 1:
                        if setNextPage:
                            if self.skip is not None:
                                self.skip = self.skip + self.top
                            else:
                                self.skip = self.top
                        break
                entity = None
            # we haven't changed the database, but we don't want to
            # leave the connection idle in transaction
            transaction.Commit()
        except Exception as e:
            transaction.Rollback(e)
        finally:
            transaction.Close()

    def iterpage(self, setNextPage=False):
        return self.ExpandEntities(
            self.pageGenerator(setNextPage))

    def __getitem__(self, key):
        entity = self.NewEntity()
        entity.SetKey(key)
        params = self.container.ParamsClass()
        query = ["SELECT "]
        columnNames, values = zip(*list(self.FieldGenerator(entity)))
        query.append(string.join(columnNames, ", "))
        query.append(' FROM ')
        query.append(self.tableName)
        query.append(self.JoinClause())
        query.append(self.WhereClause(entity, params))
        query = string.join(query, '')
        transaction = SQLTransaction(self.container.dbapi, self.dbc)
        try:
            transaction.Begin()
            logging.info("%s; %s", query, unicode(params.params))
            transaction.Execute(query, params)
            rowcount = transaction.cursor.rowcount
            row = transaction.cursor.fetchone()
            if rowcount == 0 or row is None:
                raise KeyError
            elif rowcount > 1 or (rowcount == -1 and transaction.cursor.fetchone() is not None):
                # whoops, that was unexpected
                raise SQLError(
                    "Integrity check failure, non-unique key: %s" % repr(key))
            for value, newValue in zip(values, row):
                self.container.ReadSQLValue(value, newValue)
            entity.exists = True
            entity.Expand(self.expand, self.select)
            transaction.Commit()
            return entity
        except Exception as e:
            transaction.Rollback(e)
        finally:
            transaction.Close()

    def JoinClause(self):
        """A utility method to return the JOIN clause.

        Defaults to an empty expression."""
        return ""

    def Filter(self, filter):
        self.filter = filter
        self.SetPage(None)
        self._sqlLen = None
        self._sqlGen = None

    def WhereClause(self, entity, params, useFilter=True, useSkip=False, nullCols=()):
        """A utility method that generates the WHERE clause for a query

        entity
                An optional entity within this collection that is the focus
                of this query.  If not None the resulting WHERE clause will
                restrict the query to this entity only.

        params
                The :py:class:`SQLParams` object to add parameters to.

        useFilter
                Defaults to True, indicates if this collection's filter should
                be added to the WHERE clause.

        useSkip
                Defaults to False, indicates if the skiptoken should be used
                in the where clause.  If True then the query is limited to
                entities appearing after the skiptoken's value (see below).

        nullColls
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
            self.WhereEntityClause(where, entity, params)
        if self.filter is not None and useFilter:
            # useFilter option adds the current filter too
            where.append('(' + self.SQLExpression(self.filter, params) + ')')
        if self.skiptoken is not None and useSkip:
            self.WhereSkiptokenClause(where, params)
        for nullCol in nullCols:
            where.append('%s IS NULL' % nullCol)
        if where:
            return ' WHERE ' + string.join(where, ' AND ')
        else:
            return ''

    def WhereEntityClause(self, where, entity, params):
        """Adds the entity constraint expression to a list of SQL expressions.

        where
                The list to append the entity expression to.

        entity
                An expression is added to restrict the query to this entity"""
        for k, v in entity.KeyDict().items():
            where.append('%s=%s' % (self.container.mangledNames[
                         (self.entitySet.name, k)], params.AddParam(self.container.PrepareSQLValue(v))))

    def WhereSkiptokenClause(self, where, params):
        """Adds the entity constraint expression to a list of SQL expressions.

        where
                The list to append the skiptoken expression to."""
        skipExpression = []
        i = ket = 0
        while True:
            oName, dir = self.orderNames[i]
            v = self.skiptoken[i]
            op = ">" if dir > 0 else "<"
            skipExpression.append(
                "(%s %s %s" % (oName, op, params.AddParam(self.container.PrepareSQLValue(v))))
            ket += 1
            i += 1
            if i < len(self.orderNames):
                # more to come
                skipExpression.append(
                    " OR (%s = %s AND " % (oName, params.AddParam(self.container.PrepareSQLValue(v))))
                ket += 1
                continue
            else:
                skipExpression.append(u")" * ket)
                break
        where.append(string.join(skipExpression, ''))

    def OrderBy(self, orderby):
        """Sets the orderby rules for this collection.

        We override the default implementation to calculate a list
        of field name aliases to use in ordered queries.  For example,
        if the orderby expression is "tolower(Name) desc" then each SELECT
        query will be generated with an additional expression, e.g.::

                SELECT ID, Name, DOB, LOWER(Name) AS o_1 ... ORDER BY o_1 DESC, ID ASC

        The name "o_1" is obtained from the name mangler using the tuple::

                (entitySet.name,'o_1')

        Subsequent order expressions have names 'o_2', 'o_3', etc.		

        Notice that regardless of the ordering expression supplied the
        keys are always added to ensure that, when an ordering is
        required, a defined order results even at the expense of some
        redundancy."""
        self.orderby = orderby
        self.SetPage(None)
        self.orderNames = []
        if self.orderby is not None:
            oi = 0
            for expression, direction in self.orderby:
                oi = oi + 1
                oName = "o_%i" % oi
                oName = self.container.mangledNames.get(
                    (self.entitySet.name, oName), oName)
                self.orderNames.append((oName, direction))
        for key in self.entitySet.keys:
            mangledName = self.container.mangledNames[
                (self.entitySet.name, key)]
            if self.qualifyNames:
                mangledName = "%s.%s" % (self.tableName, mangledName)
            self.orderNames.append((mangledName, 1))
        self._sqlGen = None

    def OrderByClause(self):
        """A utility method to return the orderby clause.

        params
                The :py:class:`SQLParams` object to add parameters to."""
        if self.orderNames:
            orderby = []
            for expression, direction in self.orderNames:
                orderby.append(
                    "%s %s" % (expression, "DESC" if direction < 0 else "ASC"))
            return ' ORDER BY ' + string.join(orderby, u", ")
        else:
            return ''

    def OrderByCols(self, columnNames, params, forceOrder=False):
        """A utility to add the column names and aliases for the ordering.

        columnNames
                A list of SQL column name/alias expressions

        params
                The :py:class:`SQLParams` object to add parameters to."""
        oNameIndex = 0
        if self.orderby is not None:
            for expression, direction in self.orderby:
                oName, oDir = self.orderNames[oNameIndex]
                oNameIndex += 1
                sqlExpression = self.SQLExpression(expression, params)
                columnNames.append("%s AS %s" % (sqlExpression, oName))
        if self.orderby is not None or forceOrder:
            # add the remaining names (which are just the keys)
            while oNameIndex < len(self.orderNames):
                oName, oDir = self.orderNames[oNameIndex]
                oNameIndex += 1
                columnNames.append(oName)

    def FieldGenerator(self, entity, forUpdate=False):
        """A utility generator method for mangled property names and values.

        entity
                Any instance of :py:class:`~pyslet.odata2.csdl.Entity`

        forUpdate
                True if the result should exclude the entity's keys

        The yielded values are tuples of (mangled field name,
        :py:class:`~pyslet.odata2.csdl.SimpleValue` instance).		
        Only selected fields are yielded."""
        if forUpdate:
            keys = entity.entitySet.keys
        for k, v in entity.DataItems():
            if entity.Selected(k) and (not forUpdate or k not in keys):
                if isinstance(v, edm.SimpleValue):
                    mangledName = self.container.mangledNames[
                        (self.entitySet.name, k)]
                    if self.qualifyNames:
                        mangledName = "%s.%s" % (self.tableName, mangledName)
                    yield mangledName, v
                else:
                    for sourcePath, fv in self._ComplexFieldGenerator(v):
                        mangledName = self.container.mangledNames[
                            tuple([self.entitySet.name, k] + sourcePath)]
                        if self.qualifyNames:
                            mangledName = "%s.%s" % (
                                self.tableName, mangledName)
                        yield mangledName, fv

    def _ComplexFieldGenerator(self, ct):
        for k, v in ct.iteritems():
            if isinstance(v, edm.SimpleValue):
                yield [k], v
            else:
                for sourcePath, fv in self._ComplexFieldGenerator(v):
                    yield [k] + sourcePath, fv

    SQLBinaryExpressionMethod = {}
    SQLCallExpressionMethod = {}

    def SQLExpression(self, expression, params, context="AND"):
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
                :py:meth:`SQLBracket` for a useful utility function to
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
            return getattr(self, self.SQLBinaryExpressionMethod[expression.operator])(expression, params, context)
        elif isinstance(expression, UnparameterizedLiteral):
            return unicode(expression.value)
        elif isinstance(expression, core.LiteralExpression):
            return params.AddParam(self.container.PrepareSQLValue(expression.value))
        elif isinstance(expression, core.PropertyExpression):
            try:
                p = self.entitySet.entityType[expression.name]
                if isinstance(p, edm.Property):
                    if p.complexType is None:
                        fieldName = self.container.mangledNames[
                            (self.entitySet.name, expression.name)]
                        if self.qualifyNames:
                            return "%s.%s" % (self.tableName, fieldName)
                        else:
                            return fieldName
                    else:
                        raise core.EvaluationError(
                            "Unqualified property %s must refer to a simple type" % expresison.name)
            except KeyError:
                raise core.EvaluationError(
                    "Property %s is not declared" % expression.name)
        elif isinstance(expression, core.CallExpression):
            return getattr(self, self.SQLCallExpressionMethod[expression.method])(expression, params, context)

    def SQLBracket(self, query, context, operator):
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

                collection.SQLBracket("Age+3","*","+")=="(Age+3)"
                collection.SQLBracket("Age*3","+","*")=="Age*3"	"""
        if SQLOperatorPrecedence[context] > SQLOperatorPrecedence[operator]:
            return "(%s)" % query
        else:
            return query

    def SQLExpressionMember(self, expression, params, context):
        """Converts a member expression, e.g., Address/City

        This implementation does not support the use of navigation
        properties but does support references to complex properties.

        It outputs the mangled name of the property, qualified by the
        table name if :py:attr:`qualifyNames` is True."""
        nameList = self._CalculateMemberFieldName(expression)
        contextDef = self.entitySet.entityType
        for name in nameList:
            if contextDef is None:
                raise core.EvaluationError(
                    "Property %s is not declared" % string.join(nameList, '/'))
            p = contextDef[name]
            if isinstance(p, edm.Property):
                if p.complexType is not None:
                    contextDef = p.complexType
                else:
                    contextDef = None
            elif isinstance(p, edm.NavigationProperty):
                raise NotImplementedError(
                    "Use of navigation properties in expressions not supported")
        # the result must be a simple property, so contextDef must not be None
        if contextDef is not None:
            raise core.EvaluationError(
                "Property %s does not reference a primitive type" % string.join(nameList, '/'))
        fieldName = self.container.mangledNames[
            tuple([self.entitySet.name] + nameList)]
        if self.qualifyNames:
            return "%s.%s" % (self.tableName, fieldName)
        else:
            return fieldName

    def _CalculateMemberFieldName(self, expression):
        if isinstance(expression, core.PropertyExpression):
            return [expression.name]
        elif isinstance(expression, core.BinaryExpression) and expression.operator == core.Operator.member:
            return self._CalculateMemberFieldName(expression.operands[0]) + self._CalculateMemberFieldName(expression.operands[1])
        else:
            raise core.EvaluationError("Unexpected use of member expression")

    def SQLExpressionCast(self, expression, params, context):
        """Converts the cast expression: no default implementation"""
        raise NotImplementedError

    def SQLExpressionGenericBinary(self, expression, params, context, operator):
        """A utility method for implementing binary operator conversion.

        The signature of the basic :py:meth:`SQLExpression` is extended
        to include an *operator* argument, a string representing the
        (binary) SQL operator corresponding to the expression object."""
        query = []
        query.append(
            self.SQLExpression(expression.operands[0], params, operator))
        query.append(u' ')
        query.append(operator)
        query.append(u' ')
        query.append(
            self.SQLExpression(expression.operands[1], params, operator))
        return self.SQLBracket(string.join(query, ''), context, operator)

    def SQLExpressionMul(self, expression, params, context):
        """Converts the mul expression: maps to SQL "*" """
        return self.SQLExpressionGenericBinary(expression, params, context, '*')

    def SQLExpressionDiv(self, expression, params, context):
        """Converts the div expression: maps to SQL "/" """
        return self.SQLExpressionGenericBinary(expression, params, context, '/')

    def SQLExpressionMod(self, expression, params, context):
        """Converts the mod expression: no default implementation"""
        raise NotImplementedError

    def SQLExpressionAdd(self, expression, params, context):
        """Converts the add expression: maps to SQL "+" """
        return self.SQLExpressionGenericBinary(expression, params, context, '+')

    def SQLExpressionSub(self, expression, params, context):
        """Converts the sub expression: maps to SQL "-" """
        return self.SQLExpressionGenericBinary(expression, params, context, '-')

    def SQLExpressionLt(self, expression, params, context):
        """Converts the lt expression: maps to SQL "<" """
        return self.SQLExpressionGenericBinary(expression, params, context, '<')

    def SQLExpressionGt(self, expression, params, context):
        """Converts the gt expression: maps to SQL ">" """
        return self.SQLExpressionGenericBinary(expression, params, context, '>')

    def SQLExpressionLe(self, expression, params, context):
        """Converts the le expression: maps to SQL "<=" """
        return self.SQLExpressionGenericBinary(expression, params, context, '<=')

    def SQLExpressionGe(self, expression, params, context):
        """Converts the ge expression: maps to SQL ">=" """
        return self.SQLExpressionGenericBinary(expression, params, context, '>=')

    def SQLExpressionIsOf(self, expression, params, context):
        """Converts the isof expression: no default implementation"""
        raise NotImplementedError

    def SQLExpressionEq(self, expression, params, context):
        """Converts the eq expression: maps to SQL "=" """
        return self.SQLExpressionGenericBinary(expression, params, context, '=')

    def SQLExpressionNe(self, expression, params, context):
        """Converts the ne expression: maps to SQL "<>" """
        return self.SQLExpressionGenericBinary(expression, params, context, '<>')

    def SQLExpressionAnd(self, expression, params, context):
        """Converts the and expression: maps to SQL "AND" """
        return self.SQLExpressionGenericBinary(expression, params, context, 'AND')

    def SQLExpressionOr(self, expression, params, context):
        """Converts the or expression: maps to SQL "OR" """
        return self.SQLExpressionGenericBinary(expression, params, context, 'OR')

    def SQLExpressionEndswith(self, expression, params, context):
        """Converts the endswith function: maps to "op[0] LIKE '%'+op[1]"

        This is implemented using the concatenation operator"""
        percent = edm.SimpleValue.NewSimpleValue(edm.SimpleType.String)
        percent.SetFromValue(u"'%'")
        percent = UnparameterizedLiteral(percent)
        concat = core.CallExpression(core.Method.concat)
        concat.operands.append(percent)
        concat.operands.append(expression.operands[1])
        query = []
        query.append(
            self.SQLExpression(expression.operands[0], params, 'LIKE'))
        query.append(" LIKE ")
        query.append(self.SQLExpression(concat, params, 'LIKE'))
        return self.SQLBracket(string.join(query, ''), context, 'LIKE')

    def SQLExpressionIndexof(self, expression, params, context):
        """Converts the indexof method: maps to POSITION( op[0] IN op[1] )"""
        query = [u"POSITION("]
        query.append(self.SQLExpression(expression.operands[0], params, ','))
        query.append(u" IN ")
        query.append(self.SQLExpression(expression.operands[1], params, ','))
        query.append(u")")
        return string.join(query, '')

    def SQLExpressionReplace(self, expression, params, context):
        """Converts the replace method: no default implementation"""
        raise NotImplementedError

    def SQLExpressionStartswith(self, expression, params, context):
        """Converts the startswith function: maps to "op[0] LIKE op[1]+'%'"

        This is implemented using the concatenation operator"""
        percent = edm.SimpleValue.NewSimpleValue(edm.SimpleType.String)
        percent.SetFromValue(u"'%'")
        percent = UnparameterizedLiteral(percent)
        concat = core.CallExpression(core.Method.concat)
        concat.operands.append(expression.operands[1])
        concat.operands.append(percent)
        query = []
        query.append(
            self.SQLExpression(expression.operands[0], params, 'LIKE'))
        query.append(" LIKE ")
        query.append(self.SQLExpression(concat, params, 'LIKE'))
        return self.SQLBracket(string.join(query, ''), context, 'LIKE')

    def SQLExpressionTolower(self, expression, params, context):
        """Converts the tolower method: maps to LOWER function"""
        return u"LOWER(%s)" % self.SQLExpression(expression.operands[0], params, ',')

    def SQLExpressionToupper(self, expression, params, context):
        """Converts the toupper method: maps to UCASE function"""
        return u"UPPER(%s)" % self.SQLExpression(expression.operands[0], params, ',')

    def SQLExpressionTrim(self, expression, params, context):
        """Converts the trim method: maps to TRIM function"""
        return u"TRIM(%s)" % self.SQLExpression(expression.operands[0], params, ',')

    def SQLExpressionSubstring(self, expression, params, context):
        """Converts the substring method: maps to SUBSTRING( op[0] FROM op[1] [ FOR op[2] ]"""
        query = [u"SUBSTRING("]
        query.append(self.SQLExpression(expression.operands[0], params, ','))
        query.append(u" FROM ")
        query.append(self.SQLExpression(expression.operands[1], params, ','))
        if len(expression.operands > 2):
            query.append(u" FOR ")
            query.append(
                self.SQLExpression(expression.operands[2], params, ','))
        query.append(u")")
        return string.join(query, '')

    def SQLExpressionSubstringof(self, expression, params, context):
        """Converts the substringof function: maps to "op[1] LIKE '%'+op[0]+'%'"

        To do this we need to invoke the concatenation operator.

        This method has been poorly defined in OData with the parameters
        being switched between versions 2 and 3.  It is being withdrawn
        as a result and replaced with contains in OData version 4.  We
        follow the version 3 convention here of "first parameter in the
        second parameter" which fits better with the examples and with
        the intuitive meaning::

                substringof(A,B) == A in B"""
        percent = edm.SimpleValue.NewSimpleValue(edm.SimpleType.String)
        percent.SetFromValue(u"'%'")
        percent = UnparameterizedLiteral(percent)
        rconcat = core.CallExpression(core.Method.concat)
        rconcat.operands.append(expression.operands[0])
        rconcat.operands.append(percent)
        lconcat = core.CallExpression(core.Method.concat)
        lconcat.operands.append(percent)
        lconcat.operands.append(rconcat)
        query = []
        query.append(
            self.SQLExpression(expression.operands[1], params, 'LIKE'))
        query.append(" LIKE ")
        query.append(self.SQLExpression(lconcat, params, 'LIKE'))
        return self.SQLBracket(string.join(query, ''), context, 'LIKE')

    def SQLExpressionConcat(self, expression, params, context):
        """Converts the concat method: maps to ||"""
        query = []
        query.append(self.SQLExpression(expression.operands[0], params, '*'))
        query.append(u' || ')
        query.append(self.SQLExpression(expression.operands[1], params, '*'))
        return self.SQLBracket(string.join(query, ''), context, '*')

    def SQLExpressionLength(self, expression, params, context):
        """Converts the length method: maps to CHAR_LENGTH( op[0] )"""
        return u"CHAR_LENGTH(%s)" % self.SQLExpression(expression.operands[0], params, ',')

    def SQLExpressionYear(self, expression, params, context):
        """Converts the year method: maps to EXTRACT(YEAR FROM op[0])"""
        return u"EXTRACT(YEAR FROM %s)" % self.SQLExpression(expression.operands[0], params, ',')

    def SQLExpressionMonth(self, expression, params, context):
        """Converts the month method: maps to EXTRACT(MONTH FROM op[0])"""
        return u"EXTRACT(MONTH FROM %s)" % self.SQLExpression(expression.operands[0], params, ',')

    def SQLExpressionDay(self, expression, params, context):
        """Converts the day method: maps to EXTRACT(DAY FROM op[0])"""
        return u"EXTRACT(DAY FROM %s)" % self.SQLExpression(expression.operands[0], params, ',')

    def SQLExpressionHour(self, expression, params, context):
        """Converts the hour method: maps to EXTRACT(HOUR FROM op[0])"""
        return u"EXTRACT(HOUR FROM %s)" % self.SQLExpression(expression.operands[0], params, ',')

    def SQLExpressionMinute(self, expression, params, context):
        """Converts the minute method: maps to EXTRACT(MINUTE FROM op[0])"""
        return u"EXTRACT(MINUTE FROM %s)" % self.SQLExpression(expression.operands[0], params, ',')

    def SQLExpressionSecond(self, expression, params, context):
        """Converts the second method: maps to EXTRACT(SECOND FROM op[0])"""
        return u"EXTRACT(SECOND FROM %s)" % self.SQLExpression(expression.operands[0], params, ',')

    def SQLExpressionRound(self, expression, params, context):
        """Converts the round method: no default implementation"""
        raise NotImplementedError

    def SQLExpressionFloor(self, expression, params, context):
        """Converts the floor method: no default implementation"""
        raise NotImplementedError

    def SQLExpressionCeiling(self, expression, params, context):
        """Converts the ceiling method: no default implementation"""
        raise NotImplementedError


SQLCollectionBase.SQLCallExpressionMethod = {
    core.Method.endswith: 'SQLExpressionEndswith',
    core.Method.indexof: 'SQLExpressionIndexof',
    core.Method.replace: 'SQLExpressionReplace',
    core.Method.startswith: 'SQLExpressionStartswith',
    core.Method.tolower: 'SQLExpressionTolower',
    core.Method.toupper: 'SQLExpressionToupper',
    core.Method.trim: 'SQLExpressionTrim',
    core.Method.substring: 'SQLExpressionSubstring',
    core.Method.substringof: 'SQLExpressionSubstringof',
    core.Method.concat: 'SQLExpressionConcat',
    core.Method.length: 'SQLExpressionLength',
    core.Method.year: 'SQLExpressionYear',
    core.Method.month: 'SQLExpressionMonth',
    core.Method.day: 'SQLExpressionDay',
    core.Method.hour: 'SQLExpressionHour',
    core.Method.minute: 'SQLExpressionMinute',
    core.Method.second: 'SQLExpressionSecond',
    core.Method.round: 'SQLExpressionRound',
    core.Method.floor: 'SQLExpressionFloor',
    core.Method.ceiling: 'SQLExpressionCeiling'
}

SQLCollectionBase.SQLBinaryExpressionMethod = {
    core.Operator.member: 'SQLExpressionMember',
    core.Operator.cast: 'SQLExpressionCast',
    core.Operator.mul: 'SQLExpressionMul',
    core.Operator.div: 'SQLExpressionDiv',
    core.Operator.mod: 'SQLExpressionMod',
    core.Operator.add: 'SQLExpressionAdd',
    core.Operator.sub: 'SQLExpressionSub',
    core.Operator.lt: 'SQLExpressionLt',
    core.Operator.gt: 'SQLExpressionGt',
    core.Operator.le: 'SQLExpressionLe',
    core.Operator.ge: 'SQLExpressionGe',
    core.Operator.isof: 'SQLExpressionIsOf',
    core.Operator.eq: 'SQLExpressionEq',
    core.Operator.ne: 'SQLExpressionNe',
    core.Operator.boolAnd: 'SQLExpressionAnd',
    core.Operator.boolOr: 'SQLExpressionOr'
}


class SQLEntityCollection(SQLCollectionBase):

    """Represents a collection of entities from an :py:class:`EntitySet`.

    This class is the heart of the SQL implementation of the API,
    constructing and executing queries to implement the core methods
    from :py:class:`pyslet.odata2.csdl.EntityCollection`."""

    def InsertEntity(self, entity):
        """Inserts *entity* into the collection.

        We override this method, rerouting it to a SQL-specific
        implementation that takes additional arguments."""
        self.InsertEntitySQL(entity)

    def InsertEntitySQL(self, entity, fromEnd=None, fkValues=None, transaction=None):
        """Inserts *entity* into the collection.

        This method is not designed to be overridden by other
        implementations but it does extend the default functionality for
        a more efficient implementation and to enable better
        transactional processing. The additional parameters are
        documented here.

        fromEnd
                An optional :py:class:`pyslet.odata2.csdl.AssociationSetEnd`
                bound to this entity set.  If present, indicates that this
                entity is being inserted as part of a single transaction
                involving an insert or update to the other end of the
                association.

                This suppresses any check for a required link via this
                association (as it is assumed that the link is present, or
                will be, in the same transaction).

        fkValues
                If the association referred to by *fromEnd* is represented
                by a set of foreign keys stored in this entity set's table
                (see :py:class:`SQLReverseKeyCollection`) then fkValues is
                the list of (mangled column name, value) tuples that must be
                inserted in order to create the link.

        transaction
                An optional transaction.  If present, the connection is left
                uncommitted.

        The method functions in three phases.

        1.	Process all bindings for which we hold the foreign key. 
                This includes inserting new entities where deep inserts are
                being used or calculating foreign key values where links to
                existing entities have been specified on creation.

                In addition, all required links are checked and raise errors
                if no binding is present.

        2.	A simple SQL INSERT statement is executed to add the record
                to the database along with any foreign keys generated in (1)
                or passed in *fkValues*.

        3.	Process all remaining bindings.  Although we could do this
                using the
                :py:meth:`~pyslet.odata2.csdl.DeferredValue.UpdateBindings`
                method of DeferredValue we handle this directly to retain
                transactional integrity (where supported).

                Links to existing entities are created using the InsertLink
                method available on the SQL-specific
                :py:class:`SQLNavigationCollection`.

                Deep inserts are handled by a recursive call to this method.
                After step 1, the only bindings that remain are (a) those
                that are stored at the other end of the link and so can be
                created by passing values for *fromEnd* and *fkValues* in a
                recursive call or (b) those that are stored in a separate
                table which are created by combining a recursive call and a
                call to InsertLink.

        Required links are always created in step 1 because the
        overarching mapping to SQL forces such links to be represented
        as foreign keys in the source table (i.e., this table) unless
        the relationship is 1-1, in which case the link is created in
        step 3 and our database is briefly in violation of the model. If
        the underlying database API does not support transactions then
        it is possible for this state to persist resulting in an orphan
        entity or entities, i.e., entities with missing required links. 
        A failed :py:meth:`Rollback` call will log this condition along
        with the error that caused it."""
        if transaction is None:
            transaction = SQLTransaction(self.container.dbapi, self.dbc)
        if entity.exists:
            raise edm.EntityExists(str(entity.GetLocation()))
        # We must also go through each bound navigation property of our
        # own and add in the foreign keys for forward links.
        if fkValues is None:
            fkValues = []
        fkMapping = self.container.fkTable[self.entitySet.name]
        try:
            transaction.Begin()
            navigationDone = set()
            for linkEnd, navName in self.entitySet.linkEnds.iteritems():
                if navName:
                    dv = entity[navName]
                if linkEnd.otherEnd.associationEnd.multiplicity == edm.Multiplicity.One:
                    # a required association
                    if linkEnd == fromEnd:
                        continue
                    if navName is None:
                        # unbound principal; can only be created from this
                        # association
                        raise edm.NavigationError(
                            "Entities in %s can only be created from their principal" % self.entitySet.name)
                    if not dv.bindings:
                        raise edm.NavigationError("Required navigation property %s of %s is not bound" % (
                            navName, self.entitySet.name))
                associationSetName = linkEnd.parent.name
                # if linkEnd is in fkMapping it means we are keeping a
                # foreign key for this property, it may even be required but
                # either way, let's deal with it now.  We're only interested
                # in associations that are bound to navigation properties.
                if linkEnd not in fkMapping or navName is None:
                    continue
                nullable, unique = fkMapping[linkEnd]
                targetSet = linkEnd.otherEnd.entitySet
                if len(dv.bindings) == 0:
                    # we've already checked the case where nullable is False
                    # above
                    continue
                elif len(dv.bindings) > 1:
                    raise edm.NavigationError(
                        "Unexpected error: found multiple bindings for foreign key constraint %s" % navName)
                binding = dv.bindings[0]
                if not isinstance(binding, edm.Entity):
                    # just a key, grab the entity
                    with targetSet.OpenCollection() as targetCollection:
                        targetCollection.SelectKeys()
                        targetEntity = targetCollection[binding]
                    dv.bindings[0] = targetEntity
                else:
                    targetEntity = binding
                    if not targetEntity.exists:
                        # add this entity to it's base collection
                        with targetSet.OpenCollection() as targetCollection:
                            targetCollection.InsertEntitySQL(
                                targetEntity, linkEnd.otherEnd, transaction=transaction)
                # Finally, we have a target entity, add the foreign key to
                # fkValues
                for keyName in targetSet.keys:
                    fkValues.append((self.container.mangledNames[
                                    (self.entitySet.name, associationSetName, keyName)], targetEntity[keyName]))
                navigationDone.add(navName)
            # Step 2
            entity.SetConcurrencyTokens()
            query = ['INSERT INTO ', self.tableName, ' (']
            columnNames, values = zip(
                *(list(self.FieldGenerator(entity)) + fkValues))
            query.append(string.join(columnNames, ", "))
            query.append(') VALUES (')
            params = self.container.ParamsClass()
            query.append(string.join(
                map(lambda x: params.AddParam(self.container.PrepareSQLValue(x)), values), ", "))
            query.append(');')
            query = string.join(query, '')
            logging.info("%s; %s", query, unicode(params.params))
            transaction.Execute(query, params)
            entity.exists = True
            # Step 3
            for k, dv in entity.NavigationItems():
                linkEnd = self.entitySet.navigation[k]
                if not dv.bindings:
                    continue
                elif k in navigationDone:
                    dv.bindings = []
                    continue
                associationSetName = linkEnd.parent.name
                targetSet = dv.Target()
                targetFKMapping = self.container.fkTable[targetSet.name]
                with dv.OpenCollection() as navCollection, targetSet.OpenCollection() as targetCollection:
                    while dv.bindings:
                        binding = dv.bindings[0]
                        if not isinstance(binding, edm.Entity):
                            targetCollection.SelectKeys()
                            binding = targetCollection[binding]
                        if binding.exists:
                            navCollection.InsertLink(binding, transaction)
                        else:
                            if linkEnd.otherEnd in targetFKMapping:
                                # target table has a foreign key
                                targetFKValues = []
                                for keyName in self.entitySet.keys:
                                    targetFKValues.append((self.container.mangledNames[
                                                          (targetSet.name, associationSetName, keyName)], entity[keyName]))
                                targetCollection.InsertEntitySQL(
                                    binding, linkEnd.otherEnd, targetFKValues, transaction=transaction)
                            else:
                                # foreign keys are in an auxiliary table
                                targetCollection.InsertEntitySQL(
                                    binding, linkEnd.otherEnd, transaction=transaction)
                                navCollection.InsertLink(binding, transaction)
                        dv.bindings = dv.bindings[1:]
            transaction.Commit()
        except self.container.dbapi.IntegrityError as e:
            # we might need to distinguish between a failure due to fkValues or
            # a missing key
            transaction.Rollback(e, swallowErr=True)
            # swallow the error as this should indicate a failure at the
            # point of INSERT, fkValues may have violated a unique
            # constraint but we can't make that distinction at the
            # moment.
            raise edm.ConstraintError(
                "InsertEntity failed for %s : %s" % (str(entity.GetLocation()), str(e)))
        except Exception as e:
            transaction.Rollback(e)
        finally:
            transaction.Close()

    def UpdateEntity(self, entity):
        """Updates *entity*

        This method follows a very similar pattern to :py:meth:`InsertMethod`,
        using a three-phase process.

        1.	Process all bindings for which we hold the foreign key. 
                This includes inserting new entities where deep inserts are
                being used or calculating foreign key values where links to
                existing entities have been specified on update.

        2.	A simple SQL UPDATE statement is executed to update the
                record in the database along with any updated foreign keys
                generated in (1).

        3.	Process all remaining bindings while retaining transactional
                integrity (where supported).

                Links to existing entities are created using the InsertLink
                or Replace methods available on the SQL-specific
                :py:class:`SQLNavigationCollection`.  The Replace method is
                used when a navigation property that links to a single
                entity has been bound.  Deep inserts are handled by calling
                InsertEntitySQL before the link is created.

        The same transactional behaviour as :py:meth:`InsertEntitySQL` is
        exhibited."""
        if not entity.exists:
            raise edm.NonExistentEntity(
                "Attempt to update non existent entity: " + str(entity.GetLocation()))
            fkValues = []
        fkValues = []
        fkMapping = self.container.fkTable[self.entitySet.name]
        transaction = SQLTransaction(self.container.dbapi, self.dbc)
        try:
            transaction.Begin()
            navigationDone = set()
            for k, dv in entity.NavigationItems():
                linkEnd = self.entitySet.navigation[k]
                if not dv.bindings:
                    continue
                associationSetName = linkEnd.parent.name
                # if linkEnd is in fkMapping it means we are keeping a
                # foreign key for this property, it may even be required but
                # either way, let's deal with it now.  This will insert or
                # update the link automatically, this navigation property
                # can never be a collection
                if linkEnd not in fkMapping:
                    continue
                targetSet = linkEnd.otherEnd.entitySet
                nullable, unique = fkMapping[linkEnd]
                if len(dv.bindings) > 1:
                    raise NavigationError(
                        "Unexpected error: found multiple bindings for foreign key constraint %s" % k)
                binding = dv.bindings[0]
                if not isinstance(binding, edm.Entity):
                    # just a key, grab the entity
                    with targetSet.OpenCollection() as targetCollection:
                        targetCollection.SelectKeys()
                        targetEntity = targetCollection[binding]
                    dv.bindings[0] = targetEntity
                else:
                    targetEntity = binding
                    if not targetEntity.exists:
                        # add this entity to it's base collection
                        with targetSet.OpenCollection() as targetCollection:
                            targetCollection.InsertEntitySQL(
                                targetEntity, linkEnd.otherEnd, transaction)
                # Finally, we have a target entity, add the foreign key to
                # fkValues
                for keyName in targetSet.keys:
                    fkValues.append((self.container.mangledNames[
                                    (self.entitySet.name, associationSetName, keyName)], targetEntity[keyName]))
                navigationDone.add(k)
            # grab a list of sql-name,sql-value pairs representing the key
            # constraint
            concurrencyCheck = False
            constraints = []
            for k, v in entity.KeyDict().items():
                constraints.append((self.container.mangledNames[(self.entitySet.name, k)],
                                    self.container.PrepareSQLValue(v)))
            cvList = list(self.FieldGenerator(entity, True))
            for cName, v in cvList:
                # concurrency tokens get added as if they were part of the key
                if v.pDef.concurrencyMode == edm.ConcurrencyMode.Fixed:
                    concurrencyCheck = True
                    constraints.append(
                        (cName, self.container.PrepareSQLValue(v)))
            # now update the entity to have the latest concurrency token
            entity.SetConcurrencyTokens()
            query = ['UPDATE ', self.tableName, ' SET ']
            params = self.container.ParamsClass()
            updates = []
            for cName, v in cvList + fkValues:
                updates.append(
                    '%s=%s' % (cName, params.AddParam(self.container.PrepareSQLValue(v))))
            query.append(string.join(updates, ', '))
            query.append(' WHERE ')
            where = []
            for cName, cValue in constraints:
                where.append('%s=%s' % (cName, params.AddParam(cValue)))
            query.append(string.join(where, ' AND '))
            query = string.join(query, '')
            logging.info("%s; %s", query, unicode(params.params))
            transaction.Execute(query, params)
            if transaction.cursor.rowcount == 0:
                # no rows matched this constraint, probably a concurrency
                # failure
                if concurrencyCheck:
                    raise edm.ConcurrencyError
                else:
                    raise KeyError("Entity %s does not exist" %
                                   str(entity.GetLocation()))
            #	We finish off the bindings in a similar way to InsertEntitySQL
            #	but this time we need to handle the case where there is an
            #	existing link and the navigation property is not a
            #	collection.
            for k, dv in entity.NavigationItems():
                linkEnd = self.entitySet.navigation[k]
                if not dv.bindings:
                    continue
                elif k in navigationDone:
                    dv.bindings = []
                    continue
                associationSetName = linkEnd.parent.name
                targetSet = dv.Target()
                targetFKMapping = self.container.fkTable[targetSet.name]
                with dv.OpenCollection() as navCollection, targetSet.OpenCollection() as targetCollection:
                    while dv.bindings:
                        binding = dv.bindings[0]
                        if not isinstance(binding, edm.Entity):
                            targetCollection.SelectKeys()
                            binding = targetCollection[binding]
                        if binding.exists:
                            if dv.isCollection:
                                navCollection.InsertLink(binding, transaction)
                            else:
                                navCollection.ReplaceLink(binding, transaction)
                        else:
                            if linkEnd.otherEnd in targetFKMapping:
                                # target table has a foreign key
                                targetFKValues = []
                                for keyName in self.entitySet.keys:
                                    targetFKValues.append((self.container.mangledNames[
                                                          (targetSet.name, associationSetName, keyName)], entity[keyName]))
                                if not dv.isCollection:
                                    navCollection.ClearLinks(transaction)
                                targetCollection.InsertEntitySQL(
                                    binding, linkEnd.otherEnd, targetFKValues, transaction)
                            else:
                                # foreign keys are in an auxiliary table
                                targetCollection.InsertEntitySQL(
                                    binding, linkEnd.otherEnd)
                                if dv.isCollection:
                                    navCollection.InsertLink(
                                        binding, transaction)
                                else:
                                    navCollection.ReplaceLink(
                                        binding, transaction)
                        dv.bindings = dv.bindings[1:]
            transaction.Commit()
        except self.container.dbapi.IntegrityError as e:
            # we might need to distinguish between a failure due to fkValues or
            # a missing key
            transaction.Rollback(e, swallowErr=True)
            raise edm.ConstraintError(
                "Update failed for %s : %s" % (str(entity.GetLocation()), str(e)))
        except Exception as e:
            transaction.Rollback(e)
        finally:
            transaction.Close()

    def UpdateLink(self, entity, linkEnd, targetEntity, noReplace=False, transaction=None):
        """Updates a link when this table contains the foreign key

        entity
                The entity being linked from (must already exist)

        linkEnd
                The :py:class:`~pyslet.odata2.csdl.AssociationSetEnd` bound
                to this entity set that represents this entity set's end of
                the assocation being modified.

        targetEntity
                The entity to link to or None if the link is to be removed.

        noReplace
                If True, existing links will not be replaced.  The affect is
                to force the underlying SQL query to include a constraint
                that the foreign key is currently NULL.  By default this
                argument is False and any existing link will be replaced.

        transaction
                An optional transaction.  If present, the connection is left
                uncommitted."""
        if not entity.exists:
            raise edm.NonExistentEntity(
                "Attempt to update non-existent entity: " + str(entity.GetLocation()))
        if transaction is None:
            transaction = SQLTransaction(self.container.dbapi, self.dbc)
        query = ['UPDATE ', self.tableName, ' SET ']
        params = self.container.ParamsClass()
        updates = []
        nullCols = []
        targetSet = linkEnd.otherEnd.entitySet
        associationSetName = linkEnd.parent.name
        nullable, unique = self.container.fkTable[self.entitySet.name][linkEnd]
        if not nullable and targetEntity is None:
            raise edm.NavigationError("Can't remove a required link")
        if targetEntity:
            for keyName in targetSet.keys:
                v = targetEntity[keyName]
                cName = self.container.mangledNames[
                    (self.entitySet.name, associationSetName, keyName)]
                updates.append(
                    '%s=%s' % (cName, params.AddParam(self.container.PrepareSQLValue(v))))
                if noReplace:
                    nullCols.append(cName)
        else:
            for keyName in targetSet.keys:
                cName = self.container.mangledNames[
                    (self.entitySet.name, associationSetName, keyName)]
                updates.append('%s=NULL' % cName)
        query.append(string.join(updates, ', '))
        # we don't do concurrency checks on links, and we suppress the filter
        # check too
        query.append(
            self.WhereClause(entity, params, False, nullCols=nullCols))
        query = string.join(query, '')
        try:
            transaction.Begin()
            logging.info("%s; %s", query, unicode(params.params))
            transaction.Execute(query, params)
            if transaction.cursor.rowcount == 0:
                if nullCols:
                    # raise a constraint failure, rather than a key failure -
                    # assume entity is good
                    raise edm.NavigationError("Entity %s is already linked through association %s" % (
                        entity.GetLocation(), associationSetName))
                else:
                    # key failure - unexpected case as entity should be good
                    raise KeyError("Entity %s does not exist" %
                                   str(entity.GetLocation()))
            transaction.Commit()
        except self.container.dbapi.IntegrityError as e:
            transaction.Rollback(e, swallowErr=True)
            raise KeyError("Linked entity %s does not exist" %
                           str(targetEntity.GetLocation()))
        except Exception as e:
            transaction.Rollback(e)
        finally:
            transaction.Close()

    def __delitem__(self, key):
        with self.entitySet.OpenCollection() as base:
            base.SelectKeys()
            entity = base[key]
        self.DeleteEntity(entity)

    def DeleteEntity(self, entity, fromEnd=None, transaction=None):
        """Deletes an entity

        Called by the dictionary-like del operator, provided as a
        separate method to enable it to be called recursively when
        doing cascade deletes and to support transactions.

        fromEnd
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
            transaction = SQLTransaction(self.container.dbapi, self.dbc)
        try:
            transaction.Begin()
            fkMapping = self.container.fkTable[self.entitySet.name]
            for linkEnd, navName in self.entitySet.linkEnds.iteritems():
                if linkEnd == fromEnd:
                    continue
                associationSetName = linkEnd.parent.name
                if linkEnd in fkMapping:
                    # if we are holding a foreign key then deleting us will delete
                    # the link too, so nothing to do here.
                    continue
                else:
                    if linkEnd.associationEnd.multiplicity == edm.Multiplicity.One:
                        # we are required, so it must be a 1-? relationship
                        if navName is not None:
                            # and it is bound to a navigation property so we
                            # can cascade delete
                            targetEntitySet = linkEnd.otherEnd.entitySet
                            with entity[navName].OpenCollection() as links, targetEntitySet.OpenCollection() as cascade:
                                links.SelectKeys()
                                for targetEntity in links.values():
                                    links.DeleteLink(targetEntity, transaction)
                                    cascade.DeleteEntity(
                                        targetEntity, linkEnd.otherEnd, transaction)
                        else:
                            raise edm.NavigationError("Can't cascade delete from an entity in %s as the association set %s is not bound to a navigation property" % (
                                self.entitySet.name, associationSetName))
                    else:
                        # we are not required, so just drop the links
                        if navName is not None:
                            with entity[navName].OpenCollection() as links:
                                links.ClearLinks(transaction)
                        # otherwise annoying, we need to do something special
                        elif associationSetName in self.container.auxTable:
                            # foreign keys are in an association table,
                            # hardest case as navigation may be unbound so
                            # we have to call a class method and pass the
                            # container and connection
                            SQLAssociationCollection.ClearLinksUnbound(
                                self.container, linkEnd, entity, transaction)
                        else:
                            # foreign keys are at the other end of the link, we
                            # have a method for that...
                            targetEntitySet = linkEnd.otherEnd.entitySet
                            with targetEntitySet.OpenCollection() as keyCollection:
                                keyCollection.ClearLinks(
                                    linkEnd.otherEnd, entity, transaction)
            params = self.container.ParamsClass()
            query = ["DELETE FROM "]
            params = self.container.ParamsClass()
            query.append(self.tableName)
            # WHERE - ignore the filter
            query.append(self.WhereClause(entity, params, useFilter=False))
            query = string.join(query, '')
            logging.info("%s; %s", query, unicode(params.params))
            transaction.Execute(query, params)
            rowcount = transaction.cursor.rowcount
            if rowcount == 0:
                raise KeyError
            elif rowcount > 1:
                # whoops, that was unexpected
                raise SQLError(
                    "Integrity check failure, non-unique key: %s" % repr(key))
            transaction.Commit()
        except Exception as e:
            transaction.Rollback(e)
        finally:
            transaction.Close()

    def DeleteLink(self, entity, linkEnd, targetEntity, transaction=None):
        """Deletes the link between *entity* and *targetEntity*

        The foreign key for this link must be held in this entity set's
        table.

        entity
                The entity in this entity set that the link is from.

        linkEnd
                The :py:class:`~pyslet.odata2.csdl.AssociationSetEnd` bound
                to this entity set that represents this entity set's end of
                the assocation being modified.

        targetEntity
                The target entity that defines the link to be removed.

        transaction
                An optional transaction.  If present, the connection is left
                uncommitted."""
        if not entity.exists:
            raise edm.NonExistentEntity(
                "Attempt to update non-existent entity: " + str(entity.GetLocation()))
        if transaction is None:
            transaction = SQLTransaction(self.container.dbapi, self.dbc)
        query = ['UPDATE ', self.tableName, ' SET ']
        params = self.container.ParamsClass()
        updates = []
        associationSetName = linkEnd.parent.name
        targetSet = linkEnd.otherEnd.entitySet
        nullable, unique = self.container.fkTable[self.entitySet.name][linkEnd]
        if not nullable:
            raise edm.NavigationError(
                "Can't remove a required link from association set %s" % associationSetName)
        for keyName in targetSet.keys:
            cName = self.container.mangledNames[
                (self.entitySet.name, associationSetName, keyName)]
            updates.append('%s=NULL' % cName)
        query.append(string.join(updates, ', '))
        # custom where clause to ensure that the link really existed before we
        # delete it
        query.append(' WHERE ')
        where = []
        kd = entity.KeyDict()
        for k, v in kd.items():
            where.append('%s=%s' % (self.container.mangledNames[
                         (self.entitySet.name, k)], params.AddParam(self.container.PrepareSQLValue(v))))
        for keyName in targetSet.keys:
            v = targetEntity[keyName]
            cName = self.container.mangledNames[
                (self.entitySet.name, associationSetName, keyName)]
            where.append(
                '%s=%s' % (cName, params.AddParam(self.container.PrepareSQLValue(v))))
        query.append(string.join(where, ' AND '))
        query = string.join(query, '')
        try:
            transaction.Begin()
            logging.info("%s; %s", query, unicode(params.params))
            transaction.Execute(query, params)
            if transaction.cursor.rowcount == 0:
                # no rows matched this constraint, entity either doesn't exist
                # or wasn't linked to the target
                raise KeyError("Entity %s does not exist or is not linked to %s" % str(
                    entity.GetLocation(), targetEntity.GetLocation))
            transaction.Commit()
        except Exception as e:
            transaction.Rollback(e)
        finally:
            transaction.Close()

    def ClearLinks(self, linkEnd, targetEntity, transaction=None):
        """Deletes all links to *targetEntity*

        The foreign key for this link must be held in this entity set's
        table.

        linkEnd
                The :py:class:`~pyslet.odata2.csdl.AssociationSetEnd` bound
                to this entity set that represents this entity set's end of
                the assocation being modified.

        targetEntity
                The target entity that defines the link(s) to be removed.

        transaction
                An optional transaction.  If present, the connection is left
                uncommitted."""
        if transaction is None:
            transaction = SQLTransaction(self.container.dbapi, self.dbc)
        query = ['UPDATE ', self.tableName, ' SET ']
        params = self.container.ParamsClass()
        updates = []
        associationSetName = linkEnd.parent.name
        targetSet = linkEnd.otherEnd.entitySet
        nullable, unique = self.container.fkTable[self.entitySet.name][linkEnd]
        for keyName in targetSet.keys:
            cName = self.container.mangledNames[
                (self.entitySet.name, associationSetName, keyName)]
            updates.append('%s=NULL' % cName)
        # custom where clause
        query.append(string.join(updates, ', '))
        query.append(' WHERE ')
        where = []
        for keyName in targetSet.keys:
            v = targetEntity[keyName]
            cName = self.container.mangledNames[
                (self.entitySet.name, associationSetName, keyName)]
            where.append(
                '%s=%s' % (cName, params.AddParam(self.container.PrepareSQLValue(v))))
        query.append(string.join(where, ' AND '))
        query = string.join(query, '')
        try:
            transaction.Begin()
            logging.info("%s; %s", query, unicode(params.params))
            transaction.Execute(query, params)
            transaction.Commit()
        except self.container.dbapi.IntegrityError as e:
            # catch the nullable violation here, makes it benign to clear links
            # to an unlinked target
            transaction.Rollback(e, swallowErr=True)
            raise edm.NavigationError(
                "Can't remove required link from assocation set %s" % associationSetName)
        except Exception as e:
            transaction.Rollback(e)
        finally:
            transaction.Close()

    def CreateTableQuery(self):
        """Returns a SQL statement and params object suitable for creating the table."""
        entity = self.NewEntity()
        query = ['CREATE TABLE ', self.tableName, ' (']
        params = self.container.ParamsClass()
        cols = []
        for c, v in self.FieldGenerator(entity):
            cols.append("%s %s" %
                        (c, self.container.PrepareSQLType(v, params)))
        keys = entity.KeyDict()
        constraints = []
        constraints.append(u'PRIMARY KEY (%s)' % string.join(
            map(lambda x: self.container.mangledNames[(self.entitySet.name, x)], keys.keys()), u', '))
        # Now generate the foreign keys
        fkMapping = self.container.fkTable[self.entitySet.name]
        for linkEnd in fkMapping:
            associationSetName = linkEnd.parent.name
            targetSet = linkEnd.otherEnd.entitySet
            nullable, unique = fkMapping[linkEnd]
            targetTable = self.container.mangledNames[(targetSet.name,)]
            fkNames = []
            kNames = []
            for keyName in targetSet.keys:
                # create a dummy value to catch the unusual case where there is
                # a default
                v = targetSet.entityType[keyName]()
                cName = self.container.mangledNames[
                    (self.entitySet.name, associationSetName, keyName)]
                fkNames.append(cName)
                kNames.append(
                    self.container.mangledNames[(targetSet.name, keyName)])
                cols.append(
                    "%s %s" % (cName, self.container.PrepareSQLType(v, params, nullable)))
            constraints.append("CONSTRAINT %s FOREIGN KEY (%s) REFERENCES %s(%s)" % (
                self.container.QuoteIdentifier(associationSetName),
                string.join(fkNames, ', '),
                self.container.mangledNames[(targetSet.name,)],
                string.join(kNames, ', ')))
        cols = cols + constraints
        query.append(string.join(cols, u", "))
        query.append(u')')
        return string.join(query, ''), params

    def CreateTable(self):
        """Executes the SQL statement returned by :py:meth:`CreateTableQuery`"""
        query, params = self.CreateTableQuery()
        transaction = SQLTransaction(self.container.dbapi, self.dbc)
        try:
            transaction.Begin()
            logging.info("%s; %s", query, unicode(params.params))
            transaction.Execute(query, params)
            transaction.Commit()
        except Exception as e:
            transaction.Rollback(e)
        finally:
            transaction.Close()


class SQLNavigationCollection(SQLCollectionBase, core.NavigationCollection):

    """Abstract class representing all navigation collections.

    Additional keyword arguments:

    associationSetName
            The name of the association set that defines this relationship.
            This additional parameter is used by the name mangler to obtain
            the field name (or table name) used for the foreign keys."""

    def __init__(self, associationSetName, **kwArgs):
        super(SQLNavigationCollection, self).__init__(**kwArgs)
        self.associationSetName = associationSetName

    def __setitem__(self, key, entity):
        # sanity check entity to check it can be inserted here
        if not isinstance(entity, edm.Entity) or entity.entitySet is not self.entitySet:
            raise TypeError
        if key != entity.Key():
            raise ValueError
        if not entity.exists:
            raise edm.NonExistentEntity(
                "Attempt to link to a non-existent entity: " + str(entity.GetLocation()))
        self.InsertLink(entity)

    def InsertLink(self, entity, transaction=None):
        """A utility method that inserts a link to *entity* into this collection.

        transaction
                An optional transaction.  If present, the connection is left
                uncommitted."""
        raise NotImplementedError

    def Replace(self, entity):
        if not isinstance(entity, edm.Entity) or entity.entitySet is not self.entitySet:
            raise TypeError
        if not entity.exists:
            raise edm.NonExistentEntity(
                "Attempt to link to a non-existent entity: " + str(entity.GetLocation()))
        self.ReplaceLink(entity)

    def ReplaceLink(self, entity, transaction=None):
        """A utility method that replaces all links in the collection with a single linke to *entity*.

        transaction
                An optional transaction.  If present, the connection is left
                uncommitted."""
        raise NotImplementedError

    def DeleteLink(self, entity, transaction=None):
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
    as *fromEntity*.  This occurs when the relationship is one of::

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
    :py:meth:`SQLEntityContainer.MangleName` method in the container."""

    def __init__(self, **kwArgs):
        # absorb qualifyNames just in case
        if not kwArgs.pop('qualifyNames', True):
            logging.warn("SQLForeignKeyCollection ignored qualifyNames=False")
        super(SQLForeignKeyCollection, self).__init__(
            qualifyNames=True, **kwArgs)
        self.keyCollection = self.fromEntity.entitySet.OpenCollection()
        navName = self.entitySet.linkEnds[self.fromEnd.otherEnd]
        if not navName:
            self.sourceName = self.container.mangledNames[
                (self.entitySet.name, self.fromEnd.name)]
        else:
            self.sourceName = self.container.mangledNames[
                (self.entitySet.name, navName)]

    def JoinClause(self):
        """Overridden to provide a join to the entity set containing the *fromEntity*.

        The join clause introduces an additional name that is looked up
        by the name mangler.  To avoid name clashes when the
        relationship is recursive the join clause introduces an alias
        for the table containing *fromEntity*.  To continue the example
        above, if the link from Orders to Customers is bound to a
        navigation property in the reverse direction called, say,
        'AllOrders' *in the target entity set* then this alias is
        looked up using::

                ('Customers','AllOrders')

        By default this would just be the string 'AllOrders' (the
        name of the navigation property). The resulting join looks
        something like this::

                SELECT ... FROM Customers
                INNER JOIN Orders AS AllOrders ON Customers.CustomerID=AllOrders.OrdersToCustomers_CustomerID
                ...
                WHERE AllOrders.OrderID = ?;

        The value of the OrderID key property in fromEntity is passed as
        a parameter when executing the expression.

        There is an awkward case when the reverse navigation property
        has not been bound, in this case the link's role name is used
        instead, this provides a best guess as to what the navigation
        property name would have been had it been bound; it must be
        unique within the context of *target* entitySet's type - a
        benign constraint on the model's metadata description."""
        join = []
        # we don't need to look up the details of the join again, as
        # self.entitySet must be the target
        for keyName in self.entitySet.keys:
            join.append('%s.%s=%s.%s' % (
                self.tableName,
                self.container.mangledNames[(self.entitySet.name, keyName)],
                self.sourceName,
                self.container.mangledNames[(self.fromEntity.entitySet.name, self.associationSetName, keyName)]))
        return ' INNER JOIN %s AS %s ON ' % (
            self.container.mangledNames[(self.fromEntity.entitySet.name,)], self.sourceName) + string.join(join, ', ')

    def WhereClause(self, entity, params, useFilter=True, useSkip=False):
        """Overridden to add the constraint for entities linked from *fromEntity* only.

        We continue to use the alias set in the :py:meth:`JoinClause`
        where an example WHERE clause is illustrated."""
        where = []
        for k, v in self.fromEntity.KeyDict().items():
            where.append(u"%s.%s=%s" % (self.sourceName,
                                        self.container.mangledNames[
                                            (self.fromEntity.entitySet.name, k)],
                                        params.AddParam(self.container.PrepareSQLValue(v))))
        if entity is not None:
            self.WhereEntityClause(where, entity, params)
        if self.filter is not None and useFilter:
            # useFilter option adds the current filter too
            where.append('(' + self.SQLExpression(self.filter, params) + ')')
        if self.skiptoken is not None and useSkip:
            self.WhereSkiptokenClause(where, params)
        if where:
            return ' WHERE ' + string.join(where, ' AND ')
        else:
            return ''

    def InsertEntity(self, entity):
        transaction = SQLTransaction(self.container.dbapi, self.dbc)
        try:
            # Because of the nature of the relationships we are used
            # for, *entity* can be inserted into the base collection
            # without a link back to us (the link is optional from
            # entity's point of view). We we still force the insert to
            # take place without a commit as the insertion of the link
            # afterwards may still fail.
            transaction.Begin()
            with self.entitySet.OpenCollection() as baseCollection:
                baseCollection.InsertEntitySQL(
                    entity, self.fromEnd.otherEnd, transaction=transaction)
            self.keyCollection.UpdateLink(
                self.fromEntity, self.fromEnd, entity, noReplace=True, transaction=transaction)
            transaction.Commit()
        except self.container.dbapi.IntegrityError as e:
            # we can't tell why the operation failed, could be a
            # KeyError, if we are trying to insert an existing entity or
            # could be a ConstraintError if we are already linked to a
            # different entity
            transaction.Rollback(e, swallowErr=True)
            raise NavigationError(str(e))
        except Exception as e:
            transaction.Rollback(e)
        finally:
            transaction.Close()

    def InsertLink(self, entity, transaction=None):
        return self.keyCollection.UpdateLink(self.fromEntity, self.fromEnd, entity, noReplace=True, transaction=transaction)

    def ReplaceLink(self, entity, transaction=None):
        # Target multiplicity must be 0..1 or 1; treat it the same as setitem
        return self.keyCollection.UpdateLink(self.fromEntity, self.fromEnd, entity, transaction=transaction)

    def DeleteLink(self, entity, transaction=None):
        return self.keyCollection.DeleteLink(self.fromEntity, self.fromEnd, entity, transaction=transaction)

    def __delitem__(self, key):
        #	Before we remove a link we need to know if this is ?-1
        #	relationship, if so, this deletion will result in a
        #	constraint violation.
        if self.toMultiplicity == edm.Multiplicity.One:
            raise edm.NavigationError("Can't remove a required link")
        #	Turn the key into an entity object as required by DeleteLink
        with self.entitySet.OpenCollection() as targetCollection:
            targetEntity = targetCollection.NewEntity()
            targetEntity.SetKey(key)
            # we open the base collection and call the update link method
            self.keyCollection.DeleteLink(
                self.fromEntity, self.fromEnd, targetEntity)

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

    def __init__(self, **kwArgs):
        super(SQLReverseKeyCollection, self).__init__(**kwArgs)
        self.keyCollection = self.entitySet.OpenCollection()

    def WhereClause(self, entity, params, useFilter=True, useSkip=False):
        """Overridden to add the constraint to entities linked from *fromEntity* only."""
        where = []
        for k, v in self.fromEntity.KeyDict().items():
            where.append(u"%s=%s" % (
                self.container.mangledNames[
                    (self.entitySet.name, self.associationSetName, k)],
                params.AddParam(self.container.PrepareSQLValue(v))))
        if entity is not None:
            self.WhereEntityClause(where, entity, params)
        if self.filter is not None and useFilter:
            # useFilter option adds the current filter too
            where.append('(' + self.SQLExpression(self.filter, params) + ')')
        if self.skiptoken is not None and useSkip:
            self.WhereSkiptokenClause(where, params)
        if where:
            return ' WHERE ' + string.join(where, ' AND ')
        else:
            return ''

    def InsertEntity(self, entity):
        transaction = SQLTransaction(self.container.dbapi, self.dbc)
        fkValues = []
        for k, v in self.fromEntity.KeyDict().items():
            fkValues.append(
                (self.container.mangledNames[(self.entitySet.name, self.associationSetName, k)], v))
        try:
            transaction.Begin()
            self.keyCollection.InsertEntitySQL(
                entity, self.fromEnd.otherEnd, fkValues, transaction)
            transaction.Commit()
        except self.container.dbapi.IntegrityError, e:
            transaction.Rollback(e, swallowErr=True)
            raise KeyError(str(entity.GetLocation()))
        except Exception as e:
            transaction.Rollback(e)
        finally:
            transaction.Close()

    def InsertLink(self, entity, transaction=None):
        return self.keyCollection.UpdateLink(entity, self.fromEnd.otherEnd, self.fromEntity, noReplace=True, transaction=transaction)
        # we use noReplace mode as the source multiplicity must be 1 or
        # 0..1 for this type of collection and if *entity* is already
        # linked it would be an error

    def ReplaceLink(self, entity, transaction=None):
        if self.fromMultiplicity == edm.Multiplicity.One:
            # we are required, this must be an error
            raise edm.NavigationError(
                "Can't delete required link from association set %s" % self.associationSetName)
        if transaction is None:
            transaction = SQLTransaction(self.container.dbapi, self.dbc)
        try:
            transaction.Begin()
            self.keyCollection.ClearLinks(
                self.fromEnd.otherEnd, self.fromEntity, transaction)
            self.InsertLink(entity, transaction)
            transaction.Commit()
        except self.container.dbapi.IntegrityError as e:
            transaction.Rollback(e, swallowErr=True)
            raise edm.NavigationError("Model integrity error when linking %s and %s" % (
                str(self.fromEntity.GetLocation()), str(entity.GetLocation())))
        except Exception as e:
            transaction.Rollback(e)
        finally:
            transaction.Close()

    def __delitem__(self, key):
        entity = self.keyCollection[key]
        if self.fromMultiplicity == edm.Multiplicity.One:
            # we are required, this must be an error
            raise edm.NavigationError(
                "Can't delete required link from association set %s" % self.associationSetName)
        # fromMultiplicity is 0..1
        self.keyCollection.DeleteLink(
            entity, self.fromEnd.otherEnd, self.fromEntity)

    def DeleteLink(self, entity, transaction=None):
        """Called during cascaded deletes.

        This is actually a no-operation as the foreign key for this
        association is in the entity's record itself and will be removed
        automatically when entity is deleted."""
        return 0

    def clear(self):
        self.keyCollection.ClearLinks(self.fromEnd.otherEnd, self.fromEntity)

    def ClearLinks(self, transaction=None):
        """Deletes all links from this collection's *fromEntity*

        transaction
                An optional transaction.  If present, the connection is left
                uncommitted."""
        self.keyCollection.ClearLinks(
            self.fromEnd.otherEnd, self.fromEntity, transaction)

    def close(self):
        self.keyCollection.close()
        super(SQLReverseKeyCollection, self).close()


class SQLAssociationCollection(SQLNavigationCollection):

    """The collection of entities obtained by navigation using an auxiliary table

    This object is used when the relationship is described by two sets
    of foreign keys stored in an auxiliary table.  This occurs mainly
    when the link is Many to Many but it is also used for 1 to 1
    relationships.  This last use may seem odd but it is used to
    represent the symmetry of the relationship. In practice, a single
    set of foreign keys is likely to exist in one table or the other and
    so the relationship is best modelled by a 0..1 to 1 relationship
    even if the intention is that the records will always exist in pairs.

    The name of the auxiliary table is obtained from the name mangler using
    the association set's name.  The keys use a more complex mangled form
    to cover cases where there is a recursive Many to Many relation (such
    as a social network of friends between User entities).  The names of
    the keys are obtained by mangling::

            ( association set name, target entity set name, navigation property name, key name )

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
    :py:meth:`SQLEntityContainer.MangleName` method in the container to
    catch these cases and return the shorter column names."""

    def __init__(self, **kwArgs):
        if not kwArgs.pop('qualifyNames', True):
            logging.warn('SQLAssociationCollection ignored qualifyNames=False')
        super(SQLAssociationCollection, self).__init__(
            qualifyNames=True, **kwArgs)
        # The relation is actually stored in an extra table so we will
        # need a join for all operations.
        self.associationSetName = self.fromEnd.parent.name
        self.associationTableName = self.container.mangledNames[
            (self.associationSetName,)]
        entitySetA, nameA, entitySetB, nameB, self.uniqueKeys = self.container.auxTable[
            self.associationSetName]
        if self.fromEntity.entitySet is entitySetA and self.name == nameA:
            self.fromNavName = nameA
            self.toNavName = nameB
        else:
            self.fromNavName = nameB
            self.toNavName = nameA

    def JoinClause(self):
        """Overridden to provide the JOIN to the auxiliary table.

        Unlike the foreign key JOIN clause there is no need to use an
        alias in this case as the auxiliary table is assumed to be
        distinct from the the table it is being joined to."""
        join = []
        # we don't need to look up the details of the join again, as
        # self.entitySet must be the target
        for keyName in self.entitySet.keys:
            join.append('%s.%s=%s.%s' % (
                self.tableName,
                self.container.mangledNames[(self.entitySet.name, keyName)],
                self.associationTableName,
                self.container.mangledNames[(self.associationSetName, self.entitySet.name, self.toNavName, keyName)]))
        return ' INNER JOIN %s ON ' % self.associationTableName + string.join(join, ', ')

    def WhereClause(self, entity, params, useFilter=True, useSkip=False):
        """Overridden to provide the *fromEntity* constraint in the auxiliary table."""
        where = []
        for k, v in self.fromEntity.KeyDict().items():
            where.append(u"%s.%s=%s" % (self.associationTableName,
                                        self.container.mangledNames[
                                            (self.associationSetName, self.fromEntity.entitySet.name, self.fromNavName, k)],
                                        params.AddParam(self.container.PrepareSQLValue(v))))
        if entity is not None:
            for k, v in entity.KeyDict().items():
                where.append(u"%s.%s=%s" % (self.associationTableName,
                                            self.container.mangledNames[
                                                (self.associationSetName, entity.entitySet.name, self.toNavName, k)],
                                            params.AddParam(self.container.PrepareSQLValue(v))))
        if useFilter and self.filter is not None:
            where.append("(%s)" % self.SQLExpression(self.filter, params))
        if self.skiptoken is not None and useSkip:
            self.WhereSkiptokenClause(where, params)
        return ' WHERE ' + string.join(where, ' AND ')

    def InsertEntity(self, entity):
        """Rerouted to a SQL-specific implementation with additional arguments."""
        self.InsertEntitySQL(entity, transaction=None)

    def InsertEntitySQL(self, entity, transaction=None):
        """Inserts *entity* into the base collection and creates the link.

        This is always done in two steps, bound together in a single
        transaction (where supported).  If this object represents a 1 to
        1 relationship then, briefly, we'll be in violation of the
        model. This will only be an issue in non-transactional
        systems."""
        if transaction is None:
            transaction = SQLTransaction(self.container.dbapi, self.dbc)
        try:
            transaction.Begin()
            with self.entitySet.OpenCollection() as baseCollection:
                # if this is a 1-1 relationship InsertEntitySQL will fail (with
                # an unbound navigation property) so we need to suppress the
                # back-link.
                baseCollection.InsertEntitySQL(
                    entity, linkEnd.otherEnd, transaction=transaction)
            self.InsertLink(entity, transaction)
            transaction.Commit()
        except self.container.dbapi.IntegrityError as e:
            transaction.Rollback(e, swallowErr=True)
            raise NavigationError(str(entity.GetLocation()))
        except Exception as e:
            transaction.Rollback(e)
        finally:
            transaction.Close()

    def InsertLink(self, entity, transaction=None):
        if transaction is None:
            transaction = SQLTransaction(self.container.dbapi, self.dbc)
        query = ['INSERT INTO ', self.associationTableName, ' (']
        params = self.container.ParamsClass()
        valueNames = []
        values = []
        for k, v in self.fromEntity.KeyDict().items():
            valueNames.append(self.container.mangledNames[
                              (self.associationSetName, self.fromEntity.entitySet.name, self.fromNavName, k)])
            values.append(params.AddParam(self.container.PrepareSQLValue(v)))
        for k, v in entity.KeyDict().items():
            valueNames.append(self.container.mangledNames[
                              (self.associationSetName, self.entitySet.name, self.toNavName, k)])
            values.append(params.AddParam(self.container.PrepareSQLValue(v)))
        query.append(string.join(valueNames, ', '))
        query.append(') VALUES (')
        query.append(string.join(values, ', '))
        query.append(')')
        query = string.join(query, '')
        query = string.join(query, '')
        try:
            transaction.Begin()
            logging.info("%s; %s", query, unicode(params.params))
            transaction.Execute(query, params)
            transaction.Commit()
        except self.container.dbapi.IntegrityError as e:
            transaction.Rollback(e, swallowErr=True)
            raise edm.NavigationError("Model integrity error when linking %s and %s" % (
                str(self.fromEntity.GetLocation()), str(entity.GetLocation())))
        except Exception as e:
            transaction.Rollback(e)
        finally:
            transaction.Close()

    def ReplaceLink(self, entity, transaction=None):
        if self.fromEntity[self.fromNavName].isCollection:
            if transaction is None:
                transaction = SQLTransaction(self.container.dbapi, self.dbc)
            try:
                transaction.Begin()
                self.ClearLinks(transaction)
                self.InsertLink(entity, transaction)
                transaction.Commit()
            except self.container.dbapi.IntegrityError as e:
                transaction.Rollback(e, swallowErr=True)
                raise edm.NavigationError("Model integrity error when linking %s and %s" % (
                    str(self.fromEntity.GetLocation()), str(entity.GetLocation())))
            except Exception as e:
                transaction.Rollback(e)
            finally:
                transaction.Close()
        else:
            # We don't support symmetric associations of the 0..1 - 0..1
            # variety so this must be a 1..1 relationship.
            raise edm.NavigationError(
                "Replace not allowed for 1-1 relationship (implicit delete not supported)")

    def __delitem__(self, key):
        #	Before we remove a link we need to know if this is 1-1
        #	relationship, if so, this deletion will result in a
        #	constraint violation.
        if self.uniqueKeys:
            raise edm.NavigationError("Can't remove a required link")
        with self.entitySet.OpenCollection() as targetCollection:
            entity = targetCollection.NewEntity()
            entity.SetKey(key)
            self.DeleteLink(entity)

    def DeleteLink(self, entity, transaction=None):
        """Called during cascaded deletes to force-remove a link prior
        to the deletion of the entity itself.

        This method is also re-used for simple deletion of the link in
        this case as the link is in the auxiliary table itself."""
        if transaction is None:
            transaction = SQLTransaction(self.container.dbapi, self.dbc)
        query = ['DELETE FROM ', self.associationTableName]
        params = self.container.ParamsClass()
        # we suppress the filter check on the where clause
        query.append(self.WhereClause(entity, params, False))
        query = string.join(query, '')
        try:
            transaction.Begin()
            logging.info("%s; %s", query, unicode(params.params))
            transaction.Execute(query, params)
            if transaction.cursor.rowcount == 0:
                # no rows matched this constraint must be a key failure at one
                # of the two ends
                raise KeyError("One of the entities %s or %s no longer exists" % (
                    str(self.fromEntity.GetLocation()), str(entity.GetLocation())))
            transaction.Commit()
        except Exception as e:
            transaction.Rollback(e)
        finally:
            transaction.Close()

    def ClearLinks(self, transaction=None):
        """Deletes all links from this collection's *fromEntity*

        transaction
                An optional transaction.  If present, the connection is left
                uncommitted."""
        if transaction is None:
            transaction = SQLTransaction(self.container.dbapi, self.dbc)
        query = ['DELETE FROM ', self.associationTableName]
        params = self.container.ParamsClass()
        # we suppress the filter check on the where clause
        query.append(self.WhereClause(None, params, False))
        query = string.join(query, '')
        try:
            transaction.Begin()
            logging.info("%s; %s", query, unicode(params.params))
            transaction.Execute(query, params)
            transaction.Commit()
        except Exception as e:
            transaction.Rollback(e)
        finally:
            transaction.Close()

    @classmethod
    def ClearLinksUnbound(cls, container, fromEnd, fromEntity, transaction):
        """Special class method for deleting all the links from *fromEntity*

        This is a class method because it has to work even if there is
        no navigation property bound to this end of the association.

        container
                The :py:class:`SQLEntityContainer` containing this association
                set.

        fromEnd
                The :py:class:`~pyslet.odata2.csdl.AssociationSetEnd` that represents
                the end of the association that *fromEntity* is bound to.

        fromEntity
                The entity to delete links from

        transaction
                The current transaction (required)

        This is a class method because it has to work even if there is
        no navigation property bound to this end of the association.  If
        there was a navigation property then an instance could be
        created and the simpler :py:meth:`ClearLinks` method used."""
        associationSetName = fromEnd.parent.name
        associationTableName = container.mangledNames[(associationSetName,)]
        navName = fromEntity.entitySet.linkEnds[fromEnd]
        if navName is None:
            # this is most likely the case, we're being called this way
            # because we can't instantiate a collection on an unbound
            # navigation property
            navName = u""
        entitySetA, nameA, entitySetB, nameB, uniqueKeys = container.auxTable[
            associationSetName]
        if fromEntity.entitySet is entitySetA and navName == nameA:
            fromNavName = nameA
        else:
            fromNavName = nameB
        query = ['DELETE FROM ', associationTableName]
        params = container.ParamsClass()
        query.append(' WHERE ')
        where = []
        for k, v in fromEntity.KeyDict().items():
            where.append(u"%s.%s=%s" % (associationTableName,
                                        container.mangledNames[
                                            (associationSetName, fromEntity.entitySet.name, fromNavName, k)],
                                        params.AddParam(container.PrepareSQLValue(v))))
        query.append(string.join(where, ' AND '))
        query = string.join(query, '')
        logging.info("%s; %s", query, unicode(params.params))
        transaction.Execute(query, params)

    @classmethod
    def CreateTableQuery(cls, container, associationSetName):
        """Returns a SQL statement and params object suitable for creating the auxiliary table.

        This is a class method to enable the table to be created before
        any entities are created."""
        tableName = container.mangledNames[(associationSetName,)]
        entitySetA, nameA, entitySetB, nameB, uniqueKeys = container.auxTable[
            associationSetName]
        query = ['CREATE TABLE ', container.mangledNames[
            (associationSetName,)], ' (']
        params = container.ParamsClass()
        cols = []
        constraints = []
        pkNames = []
        for es, prefix, ab in ((entitySetA, nameA, 'A'), (entitySetB, nameB, 'B')):
            targetTable = container.mangledNames[(es.name,)]
            fkNames = []
            kNames = []
            for keyName in es.keys:
                # create a dummy value to catch the unusual case where there is
                # a default
                v = es.entityType[keyName]()
                cName = container.mangledNames[
                    (associationSetName, es.name, prefix, keyName)]
                fkNames.append(cName)
                pkNames.append(cName)
                kNames.append(container.mangledNames[(es.name, keyName)])
                cols.append("%s %s" %
                            (cName, container.PrepareSQLType(v, params)))
            constraints.append("CONSTRAINT %s FOREIGN KEY (%s) REFERENCES %s(%s)" % (
                container.QuoteIdentifier(u"fk" + ab),
                string.join(fkNames, ', '),
                targetTable,
                string.join(kNames, ', ')))
            if uniqueKeys:
                constraints.append("CONSTRAINT %s UNIQUE (%s)" % (
                    container.QuoteIdentifier(u"u" + ab),
                    string.join(fkNames, ', ')))
        # Finally, add a unique constraint spanning all columns as we don't
        # want duplicate relations
        constraints.append("CONSTRAINT %s UNIQUE (%s)" % (
            container.QuoteIdentifier(u"pk"),
            string.join(pkNames, ', ')))
        cols = cols + constraints
        query.append(string.join(cols, u", "))
        query.append(u')')
        return string.join(query, ''), params

    @classmethod
    def CreateTable(cls, container, associationSetName):
        """Executes the SQL statement returned by :py:meth:`CreateTableQuery`"""
        dbc = container.AcquireConnection(
            SQL_TIMEOUT)		#: a connection to the database
        if dbc is None:
            raise DatabaseBusy(
                "Failed to acquire connection after %is" % SQL_TIMEOUT)
        transaction = SQLTransaction(container.dbapi, dbc)
        try:
            transaction.Begin()
            query, params = cls.CreateTableQuery(container, associationSetName)
            logging.info("%s; %s", query, unicode(params.params))
            transaction.Execute(query, params)
            transaction.Commit()
        except Exception as e:
            transaction.Rollback(e)
        finally:
            transaction.Close()
            if dbc is not None:
                container.ReleaseConnection(dbc)


class DummyLock(object):

    """An object to use in place of a real Lock, can always be acquired"""

    def acquire(self, blocking=None):
        return True

    def release(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self):
        pass


class SQLConnectionLock(object):

    """An object used to wrap a lock object.

    lockClass
            An object to use as the lock."""

    def __init__(self, lockClass):
        self.thread = None
        self.threadId = None
        self.lock = lockClass()
        self.locked = 0
        self.dbc = None


class SQLEntityContainer(object):

    """Object used to represent an Entity Container (aka Database).

    Keyword arguments on construction:

    containerDef
            The :py:class:`~pyslet.odata2.csdl.EntityContainer` that defines
            this database.

    dbapi
            The DB API v2 compatible module to use to connect to the database.

            This implementation is compatible with modules regardless of their
            thread-safety level (provided they declare it correctly!).		

    maxConnections (optional)
            The maximum number of connections to open to the database.  If your
            program attempts to open more than this number (defaults to 10) then
            it will block until a connection becomes free.  Connections are always
            shared within the same thread so this argument should be set to the
            expected maximum number of threads that will access the database.

            If using a module with thread-safety level 0 maxConnections is
            ignored and is effectively 1, so use of the API is then best
            confined to single-threaded programs. Multi-threaded programs
            can still use the API but it will block when there is contention
            for access to the module and context switches will force the
            database connection to be closed and reopened.

    fieldNameJoiner (optional)
            The character used by the name mangler to join compound names,
            for example, to obtain the column name of a complex property
            like "Address/City".  The default is "_", resulting in names
            like "Address_City" but it can be changed here.  Note: all names
            are quoted using :py:meth:`QuoteIdentifier` before appearing in
            SQL statements.

    This class is designed to work with diamond inheritance and super.
    All derived classes must call __init__ through super and pass all
    unused keyword arguments.  For example::

            class MyDBContainer:
                    def __init__(self,myDBConfig,**kwArgs):
                            super(MyDBContainer,self).__init__(**kwArgs)
                            # do something with myDBConfig...."""

    def __init__(self, containerDef, dbapi, maxConnections=10, fieldNameJoiner=u"_", **kwArgs):
        if kwArgs:
            logging.debug(
                "Unabsorbed kwArgs in SQLEntityContainer constructor")
        self.containerDef = containerDef
        self.dbapi = dbapi				#: the DB API compatible module
        self.moduleLock = None
        if self.dbapi.threadsafety == 0:
            # we can't even share the module, so just use one connection will
            # do
            self.moduleLock = threading.RLock()
            self.connectionLocker = DummyLock
            self.cPoolMax = 1
        else:
            # Level 1 and above we can share the module
            self.moduleLock = DummyLock()
            self.connectionLocker = threading.RLock
            self.cPoolMax = maxConnections
        self.cPoolLock = threading.Condition()
        self.cPoolClosing = False
        self.cPoolLocked = {}
        self.cPoolUnlocked = {}
        self.cPoolDead = []
        # set up the parameter style
        if self.dbapi.paramstyle == "qmark":
            self.ParamsClass = QMarkParams
        elif self.dbapi.paramstyle == "numeric":
            self.ParamsClass = NumericParams
        elif self.dbapi.paramstyle == "named":
            self.ParamsClass = NamedParams
        else:
            # will fail later when we try and add parameters
            self.ParamsClass = SQLParams
        self.fkTable = {}
        """A mapping from an entity set name to a foreign key mapping of
		the form::
		
			{<association set end>: (<nullable flag>, <unique keys flag>),...}
		
		The outer mapping has one entry for each entity set (even if the
		corresponding foreign key mapping is empty).

		Each foreign key mapping has one entry for each foreign key
		reference that must appear in that entity set's table.  The key
		is an :py:class:`AssociationSetEnd` that is bound to the entity
		set (the other end will be bound to the target entity set). 
		This allows us to distinguish between the two ends of a
		recursive association."""
        self.auxTable = {}
        """A mapping from the names of symmetric association sets to a tuple of::
		
			( <entity set A>, <name prefix A>, <entity set B>, <name prefix B>, <unique keys> )"""
        self.mangledNames = {}
        """A mapping from source path tuples to mangled and quoted names
		to use in SQL queries.  For example::
		
			(u'Customer'):u'"Customer"'
			(u'Customer', u'Address', u'City') : u"Address_City"
			(u'Customer', u'Orders') : u"Customer_Orders"
		
		Note that the first element of the tuple is the entity set name
		but the default implementation does not use this in the mangled
		name for primitive fields as they are qualified in contexts
		where a name clash is possible.  However, mangled navigation
		property names do include the table name prefix as they used as
		pseudo-table names."""
        self.fieldNameJoiner = fieldNameJoiner
        """Default string used to join complex field names in SQL
		queries, e.g. Address_City"""
        # for each entity set in this container, bind a SQLEntityCollection
        # object
        for es in self.containerDef.EntitySet:
            self.fkTable[es.name] = {}
            for sourcePath in self.SourcePathGenerator(es):
                self.mangledNames[sourcePath] = self.MangleName(sourcePath)
            self.BindEntitySet(es)
        for es in self.containerDef.EntitySet:
            for np in es.entityType.NavigationProperty:
                self.BindNavigationProperty(es, np.name)
        # once the navigation properties have been bound, fkTable will
        # have been populated with any foreign keys we need to add field
        # name mappings for
        for esName, fkMapping in self.fkTable.iteritems():
            for linkEnd, details in fkMapping.iteritems():
                associationSetName = linkEnd.parent.name
                targetSet = linkEnd.otherEnd.entitySet
                for keyName in targetSet.keys:
                    """Foreign keys are given fake source paths starting with the association set name::

                            ( u"Orders_Customers", u"CustomerID" )"""
                    sourcePath = (esName, associationSetName, keyName)
                    self.mangledNames[sourcePath] = self.MangleName(sourcePath)
        # and auxTable will have been populated with additional tables to
        # hold symmetric associations...
        for aSet in self.containerDef.AssociationSet:
            if aSet.name not in self.auxTable:
                continue
            self.mangledNames[(aSet.name,)] = self.MangleName((aSet.name,))
            """Foreign keys in Tables that model association sets are
			given fake source paths that combine the entity set name and
			the name of the navigation property endpoint.

			This ensures the special case where the two entity sets are
			the same is taken care of (as the navigation property
			endpoints must still be unique). For one-way associations,
			prefixB will be an empty string."""
            esA, prefixA, esB, prefixB, unique = self.auxTable[aSet.name]
            for keyName in esA.keys:
                sourcePath = (aSet.name, esA.name, prefixA, keyName)
                self.mangledNames[sourcePath] = self.MangleName(sourcePath)
            for keyName in esB.keys:
                sourcePath = (aSet.name, esB.name, prefixB, keyName)
                self.mangledNames[sourcePath] = self.MangleName(sourcePath)

    def MangleName(self, sourcePath):
        """Mangles a source path into a quoted SQL name

        This is a key extension point to use when you are wrapping an existing
        database with the API.  It allows you to control the names used for
        entity sets (tables) and properties (columns) in SQL queries.

        sourcePath
                A tuple or list of strings describing the path to a property in
                the metadata model.

                For entity sets, this is a tuple with a single entry in it, the
                entity set name.

                For data properties this is a tuple containing the path, including
                the entity set name
                e.g., ("Customers","Address","City") for the City property
                in a complex property 'Address' in entity set "Customers".

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

        The default implementation strips the entity set name away and uses
        the default joining character to create a compound name before calling
        :py:meth:`QuoteIdentifier` to obtain the SQL string.

        All names are mangled once, on construction, and from then on
        looked up in the dictionary of mangled names.

        If you need to override this method to modify the names used in
        your database you should ensure all other names (including any
        unrecognized by your program) are passed to the default
        implementation for mangling."""
        if len(sourcePath) > 1:
            sourcePath = list(sourcePath)[1:]
        return self.QuoteIdentifier(string.join(sourcePath, self.fieldNameJoiner))

    def SourcePathGenerator(self, entitySet):
        """Utility generator for source path *tuples* for *entitySet*"""
        yield (entitySet.name,)
        for sourcePath in self.TypeNameGenerator(entitySet.entityType):
            yield tuple([entitySet.name] + sourcePath)
        for linkEnd, navName in entitySet.linkEnds.iteritems():
            if not navName:
                # use the role name of the other end of the link instead
                # this makes sense because if entitySet is 'Orders' and
                # is linked to 'Customers' but lacks a navigation
                # property then the role name for linkEnd is likely to
                # be something like 'Order' and the other end is likely
                # to be something like 'Customer' - which provides a
                # reasonable guess at what the navigation property might
                # have been called and, furthermore, is under the
                # control of the model designer without directly
                # affecting the entities themselves.
                yield (entitySet.name, linkEnd.otherEnd.name)
            else:
                yield (entitySet.name, navName)

    def FieldNameGenerator(self, entitySet):
        """Utility generator for source path *tuples* of the fields in *entitySet*"""
        for sourcePath in self.TypeNameGenerator(entitySet.entityType):
            yield tuple(sourcePath)

    def TypeNameGenerator(self, typeDef):
        for p in typeDef.Property:
            if p.complexType is not None:
                for subPath in self.TypeNameGenerator(p.complexType):
                    yield [p.name] + subPath
            else:
                yield [p.name]

    def BindEntitySet(self, entitySet):
        entitySet.Bind(self.GetCollectionClass(), container=self)

    def BindNavigationProperty(self, entitySet, name):
        # Start by making a tuple of the end multiplicities.
        fromASEnd = entitySet.navigation[name]
        toASEnd = fromASEnd.otherEnd
        # extract the name of the association set
        associationSetName = fromASEnd.parent.name
        targetSet = toASEnd.entitySet
        multiplicity = (
            fromASEnd.associationEnd.multiplicity, toASEnd.associationEnd.multiplicity)
        # now we can work on a case-by-case basis, note that fkTable may be
        # filled in twice for the same association (if navigation properties are
        # defined in both directions) but this is benign because the definition
        # should be identical.
        if multiplicity in (
                (edm.Multiplicity.One, edm.Multiplicity.One),
                (edm.Multiplicity.ZeroToOne, edm.Multiplicity.ZeroToOne)):
            entitySet.BindNavigation(name, self.GetSymmetricNavigationCollectionClass(
            ), container=self, associationSetName=associationSetName)
            if associationSetName in self.auxTable:
                # This is the navigation property going back the other way, set
                # the navigation name only
                self.auxTable[associationSetName][3] = name
            else:
                self.auxTable[associationSetName] = [
                    entitySet, name, targetSet, "", True]
        elif multiplicity == (edm.Multiplicity.Many, edm.Multiplicity.Many):
            entitySet.BindNavigation(name, self.GetSymmetricNavigationCollectionClass(
            ), container=self, associationSetName=associationSetName)
            if associationSetName in self.auxTable:
                self.auxTable[associationSetName][3] = name
            else:
                self.auxTable[associationSetName] = [
                    entitySet, name, targetSet, "", False]
        elif multiplicity == (edm.Multiplicity.One, edm.Multiplicity.ZeroToOne):
            entitySet.BindNavigation(name, self.GetReverseKeyCollectionClass(
            ), container=self, associationSetName=associationSetName)
            self.fkTable[targetSet.name][toASEnd] = (False, True)
        elif multiplicity == (edm.Multiplicity.One, edm.Multiplicity.Many):
            entitySet.BindNavigation(name, self.GetReverseKeyCollectionClass(
            ), container=self, associationSetName=associationSetName)
            self.fkTable[targetSet.name][toASEnd] = (False, False)
        elif multiplicity == (edm.Multiplicity.ZeroToOne, edm.Multiplicity.Many):
            entitySet.BindNavigation(name, self.GetReverseKeyCollectionClass(
            ), container=self, associationSetName=associationSetName)
            self.fkTable[targetSet.name][toASEnd] = (True, False)
        elif multiplicity == (edm.Multiplicity.ZeroToOne, edm.Multiplicity.One):
            entitySet.BindNavigation(name, self.GetForeignKeyCollectionClass(
            ), container=self, associationSetName=associationSetName)
            self.fkTable[entitySet.name][fromASEnd] = (False, True)
        elif multiplicity == (edm.Multiplicity.Many, edm.Multiplicity.One):
            entitySet.BindNavigation(name, self.GetForeignKeyCollectionClass(
            ), container=self, associationSetName=associationSetName)
            self.fkTable[entitySet.name][fromASEnd] = (False, False)
        else:
            # 			(edm.Multiplicity.Many,edm.Multiplicity.ZeroToOne)
            entitySet.BindNavigation(name, self.GetForeignKeyCollectionClass(
            ), container=self, associationSetName=associationSetName)
            self.fkTable[entitySet.name][fromASEnd] = (True, False)

    def GetCollectionClass(self):
        """Returns the collection class used to represent a generic entity set.

        Override this method to provide a class derived from
        :py:class:`SQLEntityCollection` when you are customising this
        implementation for a specific database engine."""
        return SQLEntityCollection

    def GetSymmetricNavigationCollectionClass(self):
        """Returns the collection class used to represent a symmetric relation.

        Override this method to provide a class derived from
        :py:class:`SQLAssociationCollection` when you are customising this
        implementation for a specific database engine."""
        return SQLAssociationCollection

    def GetForeignKeyCollectionClass(self):
        """Returns the collection class used when the foreign key is in the source table.

        Override this method to provide a class derived from
        :py:class:`SQLForeignKeyCollection` when you are customising this
        implementation for a specific database engine."""
        return SQLForeignKeyCollection

    def GetReverseKeyCollectionClass(self):
        """Returns the collection class used when the foreign key is in the target table.

        Override this method to provide a class derived from
        :py:class:`SQLReverseKeyCollection` when you are customising this
        implementation for a specific database engine."""
        return SQLReverseKeyCollection

    def CreateAllTables(self):
        """Creates all tables in this container.

        Tables are created in a sensible order to ensure that foreign
        key constraints do not fail but this method is not compatible
        with databases that contain circular references though, e.g.,
        Table A -> Table B with a foreign key and Table B -> Table A
        with a foreign key.  Such databases will have to be created by
        hand. You can use the CreateTableQuery methods to act as a
        starting point for your script."""
        visited = set()
        for es in self.containerDef.EntitySet:
            if es.name not in visited:
                self.CreateTable(es, visited)
        # we now need to go through the auxTable and create them
        for associationSetName in self.auxTable:
            self.GetSymmetricNavigationCollectionClass().CreateTable(
                self, associationSetName)

    def CreateTable(self, es, visited):
        # before we create this table, we need to check to see if it references
        # another table
        visited.add(es.name)
        fkMapping = self.fkTable[es.name]
        for linkEnd, details in fkMapping.iteritems():
            targetSet = linkEnd.otherEnd.entitySet
            if targetSet.name in visited:
                # prevent recursion
                continue
            self.CreateTable(targetSet, visited)
        # now we are free to create the table
        with es.OpenCollection() as collection:
            collection.CreateTable()

    def AcquireConnection(self, timeout=None):
        # block on the module for threadsafety==0 case
        threadId = threading.current_thread().ident
        now = start = time.time()
        with self.cPoolLock:
            if self.cPoolClosing:
                # don't open connections when we are trying to close them
                return None
            while not self.moduleLock.acquire(False):
                self.cPoolLock.wait(timeout)
                now = time.time()
                if timeout is not None and now > start + timeout:
                    logging.warn(
                        "Thread[%i] timed out waiting for the the database module lock", threadId)
                    return None
            # we have the module lock
            if threadId in self.cPoolLocked:
                # our threadId is in the locked table
                cLock = self.cPoolLocked[threadId]
                if cLock.lock.acquire(False):
                    cLock.locked += 1
                    return cLock.dbc
                else:
                    logging.warn(
                        "Thread[%i] moved a database connection to the dead pool", threadId)
                    self.cPoolDead.append(cLock)
                    del self.cPoolLocked[threadId]
            while True:
                if threadId in self.cPoolUnlocked:
                    # take the connection that last belonged to us
                    cLock = self.cPoolUnlocked[threadId]
                    del self.cPoolUnlocked[threadId]
                elif len(self.cPoolUnlocked) + len(self.cPoolLocked) < self.cPoolMax:
                    # Add a new connection
                    cLock = SQLConnectionLock(self.connectionLocker)
                    cLock.dbc = self.OpenConnection()
                elif self.cPoolUnlocked:
                    # take a connection that doesn't belong to us, popped at
                    # random
                    oldThreadId, cLock = self.cPoolUnlocked.popitem()
                    if self.dbapi.threadsafety > 1:
                        logging.debug(
                            "Thread[%i] recycled database connection from Thread[%i]", threadId, oldThreadId)
                    else:
                        logging.debug(
                            "Thread[%i] closed an unused database connection (max connections reached)", oldThreadId)
                        # is it ok to close a connection from a different
                        # thread?
                        cLock.dbc.close()
                        cLock.dbc = self.OpenConnection()
                else:
                    now = time.time()
                    if timeout is not None and now > start + timeout:
                        logging.warn(
                            "Thread[%i] timed out waiting for a database connection", threadId)
                        break
                    logging.debug(
                        "Thread[%i] forced to wait for a database connection", threadId)
                    self.cPoolLock.wait(timeout)
                    logging.debug(
                        "Thread[%i] resuming search for database connection", threadId)
                    continue
                cLock.lock.acquire()
                cLock.locked += 1
                cLock.thread = threading.current_thread()
                cLock.threadId = threadId
                self.cPoolLocked[threadId] = cLock
                return cLock.dbc
        # we are defeated, no database connection for the caller
        # release lock on the module as there is no connection to release
        self.moduleLock.release()
        return None

    def ReleaseConnection(self, c):
        threadId = threading.current_thread().ident
        with self.cPoolLock:
            # we have exclusive use of the cPool members
            if threadId in self.cPoolLocked:
                cLock = self.cPoolLocked[threadId]
                if cLock.dbc is c:
                    cLock.lock.release()
                    self.moduleLock.release()
                    cLock.locked -= 1
                    if not cLock.locked:
                        del self.cPoolLocked[threadId]
                        self.cPoolUnlocked[threadId] = cLock
                        self.cPoolLock.notify()
                    return
            logging.error(
                "Thread[%i] attempting to release a database connection it didn't acquire", threadId)
            # it seems likely that some other thread is going to leave a locked
            # connection now, let's try and find it to correct the situation
            badThread, badLock = None, None
            for tid, cLock in self.cPoolLocked.iteritems():
                if cLock.dbc is c:
                    badThread = tid
                    badLock = cLock
                    break
            if badLock is not None:
                badLock.lock.release()
                self.moduleLock.release()
                badLock.locked -= 1
                if not badLock.locked:
                    del self.cPoolLocked[badThread]
                    self.cPoolUnlocked[badLock.threadId] = badLock
                    self.cPoolLock.notify()
                    logging.warn(
                        "Thread[%i] released database connection acquired by Thread[%i]", threadId, badThread)
                return
            # this is getting frustrating, exactly which connection does
            # this thread think it is trying to release?
            # Check the dead pool just in case
            iDead = None
            for i in xrange(len(self.cPoolDead)):
                cLock = self.cPoolDead[i]
                if cLock.dbc is c:
                    iDead = i
                    break
            if iDead is not None:
                badLock = self.cPoolDead[iDead]
                badLock.lock.release()
                self.moduleLock.release()
                badLock.locked -= 1
                logging.warn(
                    "Thread[%i] successfully released a database connection from the dead pool", threadId)
                if not badLock.locked:
                    # no need to notify other threads as we close this
                    # connection for safety
                    badLock.dbc.close()
                    del self.cPoolDead[iDead]
                    logging.warn(
                        "Thread[%i] removed a database connection from the dead pool", threadId)
                return
            # ok, this really is an error!
            logging.error(
                "Thread[%i] attempted to unlock un unknown database connection: %s", threadId, repr(c))

    def OpenConnection(self):
        """Creates and returns a new connection object.

        Must be overridden by database specific implementations because
        the underlying DB ABI does not provide a standard method of
        connecting."""
        raise NotImplementedError

    def BreakConnection(self, connection):
        """Called when closing or cleaning up locked connections.

        This method is called when the connection is locked (by a
        different thread) and the caller wants to force that thread to
        relinquish control.

        The assumption is that the database is stuck in some lengthy
        transaction and that BreakConnection can be used to terminate
        the transaction and force an exception in the thread that
        initiated it - resulting in a subsequent call to
        :py:meth:`ReleaseConnection` and a state which enables this
        thread to acquire the connection's lock so that it can close it.

        The default implementation does nothing, which might cause the
        close method to stall until the other thread relinquishes
        control normally."""
        pass

    def close(self, timeout=5):
        """Closes this database.

        This method goes through each open connection and attempts to
        acquire it and then close it.  The object is put into a mode
        that disables :py:meth:`AcquireConnection` (it returns None
        from now on).

        timeout
                Defaults to 5 seconds.  If connections are locked by other
                *running* threads we wait for those threads to release them,
                calling :py:meth:`BreakConnection` to speed up termination
                if possible.

                If None (not recommended!) this method will block indefinitely
                until all threads properly call :py:meth:`ReleaseConnection`.

        Any locks we fail to acquire in the timeout are ignored and
        the connections are left open for the python garbage
        collector to dispose of."""
        with self.cPoolLock:
            self.cPoolClosing = True
            while self.cPoolUnlocked:
                threadId, cLock = self.cPoolUnlocked.popitem()
                # we don't bother to acquire the lock
                cLock.dbc.close()
            while self.cPoolLocked:
                # trickier, these are in use
                threadId, cLock = self.cPoolLocked.popitem()
                noWait = False
                while True:
                    if cLock.lock.acquire(False):
                        cLock.dbc.close()
                        break
                    elif cLock.thread.isAlive():
                        if noWait:
                            break
                        else:
                            self.BreakConnection(cLock.dbc)
                            logging.warn(
                                "Waiting to break database connection acquired by Thread[%i]", threadId)
                            self.cPoolLock.wait(timeout)
                            noWait = True
                    else:
                        # This connection will never be released properly
                        cLock.dbc.close()
            while self.cPoolDead:
                cLock = self.cPoolDead.pop()
                noWait = False
                while True:
                    if cLock.lock.acquire(False):
                        cLock.dbc.close()
                        break
                    elif cLock.thread.isAlive():
                        if noWait:
                            break
                        else:
                            self.BreakConnection(cLock.dbc)
                            logging.warn(
                                "Waiting to break a database connection from the dead pool")
                            self.cPoolLock.wait(timeout)
                            noWait = True
                    else:
                        # This connection will never be released properly
                        cLock.dbc.close()

    def __del__(self):
        self.close()

    def QuoteIdentifier(self, identifier):
        """Given an *identifier* returns a safely quoted form of it.

        By default we strip double quote and then use them to enclose
        it.  E.g., if the string u'Employee_Name' is passed then the
        string u'"Employee_Name"' is returned."""
        return u'"%s"' % identifier.replace('"', '')

    def PrepareSQLType(self, simpleValue, params, nullable=None):
        """Given a simple value, returns a SQL-formatted name of its type.

        Used to construct CREATE TABLE queries.

        simpleValue
                A :py:class:`pyslet.odata2.csdl.SimpleValue` instance which
                must have been created from a suitable
                :py:class:`pyslet.odata2.csdl.Property` definition.

        params
                A :py:class:`SQLParams` object.  If simpleValue is non-NULL, a
                DEFAULT value is added as part of the type definition.

        nullable
                Optional Boolean that can be used to override the nullable status
                of the associated property definition.

        For example, if the value was created from an Int32 non-nullable
        property and has value 0 then this might return the string
        u'INTEGER NOT NULL DEFAULT ?' with 0 being added to *params*

        You should override this implementation if your database
        platform requires special handling of certain datatypes.  The
        default mappings are given below.

        ==================  =========================================================
           EDM Type			SQL Equivalent
        ------------------  ---------------------------------------------------------
        Edm.Binary          BINARY(MaxLength) if FixedLength specified
        Edm.Binary          VARBINARY(MaxLength) if no FixedLength
        Edm.Boolean         BOOLEAN
        Edm.Byte            SMALLINT
        Edm.DateTime        TIMESTAMP
        Edm.DateTimeOffset  CHARACTER(20), ISO 8601 string representation is used
        Edm.Decimal         DECIMAL(Precision,Scale), defaults 10,0
        Edm.Double          FLOAT
        Edm.Guid            BINARY(16)
        Edm.Int16           SMALLINT
        Edm.Int32           INTEGER
        Edm.Int64           BIGINT
        Edm.SByte           SMALLINT
        Edm.Single          REAL
        Edm.String          CHAR(MaxLength) or VARCHAR(MaxLength)
        Edm.String          NCHAR(MaxLength) or NVARCHAR(MaxLength) if Unicode="true"
        Edm.Time            TIME
        ==================  =========================================================  

        Parameterized CREATE TABLE queries are unreliable in my
        experience so the current implementation of the native
        CreateTable methods ignore default values when calling this
        method."""
        p = simpleValue.pDef
        columnDef = []
        if isinstance(simpleValue, edm.BinaryValue):
            if p.fixedLength:
                if p.maxLength:
                    columnDef.append(u"BINARY(%i)" % p.maxLength)
                else:
                    raise SQLModelError(
                        "Edm.Binary of fixed length missing max: %s" % p.name)
            elif p.maxLength:
                columnDef.append(u"VARBINARY(%i)" % p.maxLength)
            else:
                raise NotImplementedError(
                    "SQL binding for Edm.Binary of unbounded length: %s" % p.name)
        elif isinstance(simpleValue, edm.BooleanValue):
            columnDef.append(u"BOOLEAN")
        elif isinstance(simpleValue, edm.ByteValue):
            columnDef.append(u"SMALLINT")
        elif isinstance(simpleValue, edm.DateTimeValue):
            columnDef.append("TIMESTAMP")
        elif isinstance(simpleValue, edm.DateTimeOffsetValue):
            # stored as string and parsed e.g. 20131209T100159+0100
            columnDef.append("CHARACTER(20)")
        elif isinstance(simpleValue, edm.DecimalValue):
            if p.precision is None:
                precision = 10  # chosen to allow 32-bit integer precision
            else:
                precision = p.precision
            if p.scale is None:
                scale = 0		# from the CSDL model specification
            else:
                scale = p.scale
            columnDef.append(u"DECIMAL(%i,%i)" % (precision, scale))
        elif isinstance(simpleValue, edm.DoubleValue):
            columnDef.append("FLOAT")
        elif isinstance(simpleValue, edm.GuidValue):
            columnDef.append("BINARY(16)")
        elif isinstance(simpleValue, edm.Int16Value):
            columnDef.append(u"SMALLINT")
        elif isinstance(simpleValue, edm.Int32Value):
            columnDef.append(u"INTEGER")
        elif isinstance(simpleValue, edm.Int64Value):
            columnDef.append(u"BIGINT")
        elif isinstance(simpleValue, edm.SByteValue):
            columnDef.append(u"SMALLINT")
        elif isinstance(simpleValue, edm.SingleValue):
            columnDef.append(u"REAL")
        elif isinstance(simpleValue, edm.StringValue):
            if p.unicode is None or p.unicode:
                n = "N"
            else:
                n = ""
            if p.fixedLength:
                if p.maxLength:
                    columnDef.append(u"%sCHAR(%i)" % (n, p.maxLength))
                else:
                    raise SQLModelError(
                        "Edm.String of fixed length missing max: %s" % p.name)
            elif p.maxLength:
                columnDef.append(u"%sVARCHAR(%i)" % (n, p.maxLength))
            else:
                raise NotImplementedError(
                    "SQL binding for Edm.String of unbounded length: %s" % p.name)
        elif isinstance(simpleValue, edm.TimeValue):
            columnDef.append(u"TIME")
        else:
            raise NotImplementedError("SQL type for %s" % p.type)
        if (nullable is not None and not nullable) or (nullable is None and not p.nullable):
            columnDef.append(u' NOT NULL')
        if simpleValue:
            # Format the default
            columnDef.append(u' DEFAULT ')
            columnDef.append(
                params.AddParam(self.PrepareSQLValue(simpleValue)))
        return string.join(columnDef, '')

    def PrepareSQLValue(self, simpleValue):
        """Given a simple value, returns a value suitable for passing as a parameter

        simpleValue
                A :py:class:`pyslet.odata2.csdl.SimpleValue` instance.

        You should override this method if your database requires
        special handling of parameter values.  The default
        implementation performs the following conversions

        ==================  =========================================================
           EDM Type			Python value added as parameter
        ------------------  ---------------------------------------------------------
        NULL				None
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
        ==================  =========================================================
        """
        if not simpleValue:
            return None
        elif isinstance(simpleValue, (
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
            return simpleValue.value
        elif isinstance(simpleValue, edm.DateTimeValue):
            microseconds, seconds = math.modf(simpleValue.value.time.second)
            return self.dbapi.Timestamp(
                simpleValue.value.date.century *
                100 + simpleValue.value.date.year,
                simpleValue.value.date.month,
                simpleValue.value.date.day,
                simpleValue.value.time.hour,
                simpleValue.value.time.minute,
                int(seconds), int(1000000.0 * microseconds + 0.5))
        elif isinstance(simpleValue, edm.DateTimeOffsetValue):
            return simpleValue.value.GetCalendarString(basic=True, ndp=6, dp=".").ljust(27, ' ')
        elif isinstance(simpleValue, edm.GuidValue):
            return simpleValue.value.bytes
        elif isinstance(simpleValue, edm.TimeValue):
            return self.dbapi.Time(
                simpleValue.value.hour,
                simpleValue.value.minute,
                simpleValue.value.second)
        else:
            raise NotImplementedError(
                "SQL type for " + simpleValue.__class__.__name__)

    def ReadSQLValue(self, simpleValue, newValue):
        """Updates *simpleValue* from *newValue*.

        simpleValue
                A :py:class:`pyslet.odata2.csdl.SimpleValue` instance.

        newValue
                A value returned by the underlying DB API, e.g., from a cursor
                fetch  operation

        This method performs the reverse transformation to
        :py:meth:`PrepareSQLValue` and may need to be overridden to
        convert *newValue* into a form suitable for passing to the
        underlying
        :py:meth:`~pyslet.odata2.csdl.SimpleValue.SetFromValue`
        method."""
        simpleValue.SetFromValue(newValue)

    def NewFromSQLValue(self, sqlValue):
        """Returns a new :py:class:`pyslet.odata2.csdl.SimpleValue` instance with value *sqlValue*

        sqlValue
                A value returned by the underlying DB API, e.g., from a cursor
                fetch  operation

        This method creates a new instance, selecting the most
        appropriate type to represent sqlValue.  By default
        :py:meth:`pyslet.odata2.csdl.EDMValue.NewSimpleValueFromValue`
        is used.

        You may need to override this method to identify the appropriate
        value type."""
        return edm.EDMValue.NewSimpleValueFromValue(sqlValue)


class SQLiteEntityContainer(SQLEntityContainer):

    """Creates a :py:class:`SQLEntityContainer` that represents a SQLite database.

    Additional keyword arguments:

    filePath
            The path to the SQLite database file.

    sqlite_options
            A dictionary of additional options to pass as named arguments to
            the connect method.  It defaults to an empty dictionary, you
            won't normally need to pass additional options and you shouldn't
            change the isolation_level as the collection classes have been
            designed to work in the default mode.

            For more information see sqlite3_

    ..	_sqlite3:	https://docs.python.org/2/library/sqlite3.html

    All other keyword arguments required to initialise the base class
    must be passed on construction except *dbapi* which is automatically
    set to the Python sqlite3 module."""

    def __init__(self, filePath, sqlite_options={}, **kwArgs):
        super(SQLiteEntityContainer, self).__init__(dbapi=sqlite3, **kwArgs)
        if not isinstance(filePath, OSFilePath) and not type(filePath) in StringTypes:
            raise TypeError("SQLiteDB requires an OS file path")
        self.filePath = filePath
        self.sqlite_options = sqlite_options

    def GetCollectionClass(self):
        """Overridden to return :py:class:`SQLiteEntityCollection`"""
        return SQLiteEntityCollection

    def GetSymmetricNavigationCollectionClass(self):
        """Overridden to return :py:class:`SQLiteAssociationCollection`"""
        return SQLiteAssociationCollection

    def GetForeignKeyCollectionClass(self):
        """Overridden to return :py:class:`SQLiteForeignKeyCollection`"""
        return SQLiteForeignKeyCollection

    def GetReverseKeyCollectionClass(self):
        """Overridden to return :py:class:`SQLiteReverseKeyCollection`"""
        return SQLiteReverseKeyCollection

    def OpenConnection(self):
        """Calls the underlying connect method.

        Passes the filePath used to construct the container as the only
        parameter.  You can pass the string ':memory:' to create an
        in-memory database.

        Other connection arguments are not currently supported, you can
        derive a more complex implementation by overriding this method
        and (optionally) the __init__ method to pass in values for ."""
        return self.dbapi.connect(str(self.filePath), **self.sqlite_options)

    def BreakConnection(self, connection):
        """Calls the underlying interrupt method."""
        connection.interrupt()

    def PrepareSQLType(self, simpleValue, params, nullable=None):
        """Performs SQLite custom mappings

        We inherit most of the type mappings but the following three
        types use custom mappings:

        ==================  =========================================================
           EDM Type			SQLite Equivalent
        ------------------  ---------------------------------------------------------
        Edm.Decimal         TEXT
        Edm.Guid            BLOB
        Edm.Time            REAL
        ==================  =========================================================  
        """
        p = simpleValue.pDef
        columnDef = []
        if isinstance(simpleValue, (edm.StringValue, edm.DecimalValue)):
            columnDef.append(u"TEXT")
        elif isinstance(simpleValue, (edm.BinaryValue, edm.GuidValue)):
            columnDef.append(u"BLOB")
        elif isinstance(simpleValue, edm.TimeValue):
            columnDef.append(u"REAL")
        else:
            return super(SQLiteEntityContainer, self).PrepareSQLType(simpleValue, params, nullable)
        if (nullable is not None and not nullable) or (nullable is None and not p.nullable):
            columnDef.append(u' NOT NULL')
        if simpleValue:
            # Format the default
            columnDef.append(u' DEFAULT ')
            columnDef.append(
                params.AddParam(self.PrepareSQLValue(simpleValue)))
        return string.join(columnDef, '')

    def PrepareSQLValue(self, simpleValue):
        """Given a simple value, returns a value suitable for passing as a parameter.

        We inherit most of the value mappings but the following types
        have custom mappings.

        ==================  =========================================================
           EDM Type			Python value added as parameter
        ------------------  ---------------------------------------------------------
        Edm.Binary          buffer object
        Edm.Decimal         string representation obtained with str()
        Edm.Guid            buffer object containing bytes representation
        Edm.Time            value of :py:meth:`pyslet.iso8601.Time.GetTotalSeconds`
        ==================  =========================================================

        Our use of buffer type is not ideal as it generates warning when
        Python is run with the -3 flag (to check for Python 3
        compatibility) but it seems unavoidable at the current time."""
        if not simpleValue:
            return None
        elif isinstance(simpleValue, edm.BinaryValue):
            return buffer(simpleValue.value)
        elif isinstance(simpleValue, edm.DecimalValue):
            return str(simpleValue.value)
        elif isinstance(simpleValue, edm.GuidValue):
            return buffer(simpleValue.value.bytes)
        elif isinstance(simpleValue, edm.TimeValue):
            return simpleValue.value.GetTotalSeconds()
        else:
            return super(SQLiteEntityContainer, self).PrepareSQLValue(simpleValue)

    def ReadSQLValue(self, simpleValue, newValue):
        """Reverses the transformation performed by :py:meth:`PrepareSQLValue`"""
        if newValue is None:
            simpleValue.SetNull()
        elif type(newValue) == BufferType:
            newValue = str(newValue)
            simpleValue.SetFromValue(newValue)
        elif isinstance(simpleValue, (edm.DateTimeValue, edm.DateTimeOffsetValue)):
            # SQLite stores these as strings
            simpleValue.SetFromValue(
                iso.TimePoint.FromString(newValue, tDesignators="T "))
        elif isinstance(simpleValue, edm.TimeValue):
            simpleValue.value = iso.Time(totalSeconds=newValue)
        elif isinstance(simpleValue, edm.DecimalValue):
            simpleValue.value = decimal.Decimal(newValue)
        else:
            simpleValue.SetFromValue(newValue)

    def NewFromSQLValue(self, sqlValue):
        """Returns a new :py:class:`pyslet.odata2.csdl.SimpleValue` instance with value *sqlValue*

        Overridden to ensure that buffer objects returned by the
        underlying DB API are converted to strings.  Otherwise
        *sqlValue* is passed directly to the parent."""
        if type(sqlValue) == BufferType:
            result = edm.BinaryValue()
            result.SetFromValue(str(sqlValue))
            return result
        else:
            return super(SQLiteEntityContainer, self).NewFromSQLValue(sqlValue)


class SQLiteEntityCollectionBase(SQLCollectionBase):

    """Base class for SQLite SQL custom mappings.

    This class provides some SQLite specific mappings for certain
    functions to improve compatibility with the OData expression
    language."""

    def SQLExpressionLength(self, expression, params, context):
        """Converts the length method: maps to length( op[0] )"""
        query = ["length("]
        query.append(self.SQLExpression(expression.operands[0], params, ','))
        query.append(")")
        return string.join(query, '')  # don't bother with brackets!

    def SQLExpressionYear(self, expression, params, context):
        """Converts the year method: maps to CAST(strftime('%Y',op[0]) AS INTEGER)"""
        query = ["CAST(strftime('%Y',"]
        query.append(self.SQLExpression(expression.operands[0], params, ','))
        query.append(") AS INTEGER)")
        return string.join(query, '')  # don't bother with brackets!

    def SQLExpressionMonth(self, expression, params, context):
        """Converts the month method: maps to  CAST(strftime('%m',op[0]) AS INTEGER)"""
        query = ["CAST(strftime('%m',"]
        query.append(self.SQLExpression(expression.operands[0], params, ','))
        query.append(") AS INTEGER)")
        return string.join(query, '')  # don't bother with brackets!

    def SQLExpressionDay(self, expression, params, context):
        """Converts the day method: maps to  CAST(strftime('%d',op[0]) AS INTEGER)"""
        query = ["CAST(strftime('%d',"]
        query.append(self.SQLExpression(expression.operands[0], params, ','))
        query.append(") AS INTEGER)")
        return string.join(query, '')  # don't bother with brackets!

    def SQLExpressionHour(self, expression, params, context):
        """Converts the hour method: maps to  CAST(strftime('%H',op[0]) AS INTEGER)"""
        query = ["CAST(strftime('%H',"]
        query.append(self.SQLExpression(expression.operands[0], params, ','))
        query.append(") AS INTEGER)")
        return string.join(query, '')  # don't bother with brackets!

    def SQLExpressionMinute(self, expression, params, context):
        """Converts the minute method: maps to  CAST(strftime('%M',op[0]) AS INTEGER)"""
        query = ["CAST(strftime('%M',"]
        query.append(self.SQLExpression(expression.operands[0], params, ','))
        query.append(") AS INTEGER)")
        return string.join(query, '')  # don't bother with brackets!

    def SQLExpressionSecond(self, expression, params, context):
        """Converts the second method: maps to  CAST(strftime('%S',op[0]) AS INTEGER)"""
        query = ["CAST(strftime('%S',"]
        query.append(self.SQLExpression(expression.operands[0], params, ','))
        query.append(") AS INTEGER)")
        return string.join(query, '')  # don't bother with brackets!

    def SQLExpressionTolower(self, expression, params, context):
        """Converts the tolower method: maps to lower(op[0])"""
        query = ["lower("]
        query.append(self.SQLExpression(expression.operands[0], params, ','))
        query.append(")")
        return string.join(query, '')  # don't bother with brackets!

    def SQLExpressionToupper(self, expression, params, context):
        """Converts the toupper method: maps to upper(op[0])"""
        query = ["upper("]
        query.append(self.SQLExpression(expression.operands[0], params, ','))
        query.append(")")
        return string.join(query, '')  # don't bother with brackets!


class SQLiteEntityCollection(SQLiteEntityCollectionBase, SQLEntityCollection):

    """SQLite-specific collection for entity sets"""
    pass


class SQLiteAssociationCollection(SQLiteEntityCollectionBase, SQLAssociationCollection):

    """SQLite-specific collection for symmetric association sets"""
    pass


class SQLiteForeignKeyCollection(SQLiteEntityCollectionBase, SQLForeignKeyCollection):

    """SQLite-specific collection for navigation from a foreign key"""
    pass


class SQLiteReverseKeyCollection(SQLiteEntityCollectionBase, SQLReverseKeyCollection):

    """SQLite-specific collection for navigation to a foreign key"""
    pass
