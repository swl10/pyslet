#! /usr/bin/env python
"""This module implements the Open Data Protocol specification defined by Microsoft."""


import sqlite3, hashlib, StringIO, time, string, sys, threading, decimal, uuid, math, logging
from types import *

from pyslet.vfs import OSFilePath
import pyslet.iso8601 as iso
import csdl as edm
import core, metadata


SQL_TIMEOUT=90	#: the standard timeout while waiting for a database connection, in seconds

class SQLError(Exception):
	"""Base class for all module exceptions."""
	pass


class DatabaseBusy(SQLError):
	"""Raised when a database connection times out."""
	pass

SQLOperatorPrecedence={
	',':0,
	'OR':1,
	'AND':2,
	'NOT':3,
	'=':4,
	'<>':4,
	'<':4,
	'>':4,
	'<=':4,
	'>=':4,
	'LIKE':4,
	'+':5,
	'-':5,
	'*':6,
	'/':6
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


class SQLCollectionMixin(object):
	"""A base class that is mixed in to other SQL collection classes to
	provide core functionality.
	
	*container* must be a :py:class:`SQLEntityContainer` instance.
	
	On construction a data connection is acquired from *container*, this
	may prevent other threads from using the database until the lock is
	released by the :py:meth:`close` method."""	
	def __init__(self,container):
		self.container=container		#: the parent container (database) for this collection
		self.tableName=self.container.mangledNames[(self.entitySet.name,)]	#: the quoted table name containing this collection
		self.qualifyNames=False			#: if True, field names in expressions are qualified with :py:attr:`tableName`
		self.OrderBy(None)				# force orderNames to be initialised
		self.dbc=None					#: a connection to the database
		self.cursor=None				#: a database cursor for executing queries
		self._sqlLen=None
		self._sqlGen=None
		try:
			self.dbc=self.container.AcquireConnection(SQL_TIMEOUT)		
			if self.dbc is None:
				raise DatabaseBusy("Failed to acquire connection after %is"%SQL_TIMEOUT)
			self.cursor=self.dbc.cursor()
		except:
			self.close()
			raise
			
	def close(self):
		"""Closes the cursor and database connection if they are open."""
		if self.dbc is not None:
			if self.cursor is not None:
				self.cursor.close()
			self.container.ReleaseConnection(self.dbc)
			self.dbc=None

	def __len__(self):
		if self._sqlLen is None:
			query=["SELECT COUNT(*) FROM %s"%self.tableName]
			params=self.container.ParamsClass()
			query.append(self.JoinClause())
			query.append(self.WhereClause(None,params))
			query=string.join(query,'')
			self._sqlLen=(query,params)
		else:
			query,params=self._sqlLen
		cursor=None
		try:
			cursor=self.dbc.cursor()
			logging.info("%s; %s",query,unicode(params.params))
			cursor.execute(query,params.params)
			# get the result
			return cursor.fetchone()[0]
		except self.container.dbapi.Error as e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
		finally:
			if cursor is not None:
				cursor.close()

	def entityGenerator(self):
		entity,values=None,None
		if self._sqlGen is None:
			entity=self.NewEntity()
			query=["SELECT "]
			params=self.container.ParamsClass()
			columnNames,values=zip(*list(self.FieldGenerator(entity)))
			# values is used later for the first result
			columnNames=list(columnNames)
			self.OrderByCols(columnNames,params)
			query.append(string.join(columnNames,", "))
			query.append(' FROM ')
			query.append(self.tableName)
			query.append(self.JoinClause())
			query.append(self.WhereClause(None,params,useFilter=True,useSkip=False))
			query.append(self.OrderByClause())
			query=string.join(query,'')
			self._sqlGen=query,params
		else:
			query,params=self._sqlGen
		cursor=None
		try:
			cursor=self.dbc.cursor()
			logging.info("%s; %s",query,unicode(params.params))
			cursor.execute(query,params.params)
			while True:
				row=cursor.fetchone()
				if row is None:
					break
				if entity is None:
					entity=self.NewEntity()
					values=zip(*list(self.FieldGenerator(entity)))[1]
				for value,newValue in zip(values,row):
					self.container.ReadSQLValue(value,newValue)
				entity.exists=True
				yield entity
				entity,values=None,None
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
		finally:
			if cursor is not None:
				cursor.close()
		
	def itervalues(self):
		return self.ExpandEntities(
			self.entityGenerator())

	def __getitem__(self,key):
		entity=self.NewEntity()
		entity.SetKey(key)
		params=self.container.ParamsClass()
		query=["SELECT "]
		columnNames,values=zip(*list(self.FieldGenerator(entity)))
		query.append(string.join(columnNames,", "))
		query.append(' FROM ')
		query.append(self.tableName)
		query.append(self.JoinClause())
		query.append(self.WhereClause(entity,params))
		query=string.join(query,'')
		try:
			logging.info("%s; %s",query,unicode(params.params))
			self.cursor.execute(query,params.params)
			rowcount=self.cursor.rowcount
			row=self.cursor.fetchone()
			if rowcount==0 or row is None:
				raise KeyError
			elif rowcount>1 or (rowcount==-1 and self.cursor.fetchone() is not None):
				# whoops, that was unexpected
				raise SQLError("Integrity check failure, non-unique key: %s"%repr(key))
			for value,newValue in zip(values,row):
				self.container.ReadSQLValue(value,newValue)
			entity.exists=True
			entity.Expand(self.expand,self.select)
			return entity
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))

	def Rollback(self,err=None):
		"""Calls the underlying database connection rollback method.

		If rollback is not supported the resulting error is absorbed.
		
		err
			The exception that has triggered the rollback.  If not None
			then this is logged at INFO level when the rollback succeeds
			or ERROR level if rollback is not supported."""
		try:
			self.dbc.rollback()
			if err is not None:
				logging.info("Rollback invoked for transaction on TABLE %s following error %s",self.tableName,str(err))
		except self.container.dbapi.NotSupportedError:
			if err is not None:
				logging.error("Data Integrity Error on TABLE %s: Rollback invoked on a connection that does not support transactions after error %s",self.tableName,str(err))
			pass
	
	def JoinClause(self):
		"""A utility method to return the JOIN clause.
		
		Defaults to an empty expression."""
		return ""

	def Filter(self,filter):
		"""Sets the filter for this collection.
		
		We override this method to clear cached queries that must be
		recalculated."""
		self.filter=filter
		self.SetPage(None)
		self._sqlLen=None
		self._sqlGen=None

	def WhereClause(self,entity,params,useFilter=True,useSkip=False,nullCols=()):
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
		
			SELECT K, Nname, DOB, LCASE(Name) AS O1, K ....
				WHERE (O1 < ? OR (O1 = ? AND K > ?))
		
		The values from the skiptoken will be passed as parameters."""
		where=[]
		if entity is not None:
			self.WhereEntityClause(where,entity,params)
		if self.filter is not None and useFilter:
			# useFilter option adds the current filter too
			where.append('('+self.SQLExpression(self.filter,params)+')')
		if self.skiptoken is not None and useSkip:
			self.WhereSkiptokenClause(where,params)
		for nullCol in nullCols:
			where.append('%s IS NULL'%nullCol)
		if where:
			return ' WHERE '+string.join(where,' AND ')
		else:
			return ''

	def WhereEntityClause(self,where,entity,params):
		"""Adds the entity constraint expression to a list of SQL expressions.
		
		where
			The list to append the entity expression to.
		
		entity
			An expression is added to restrict the query to this entity"""
		for k,v in entity.KeyDict().items():
			where.append('%s=%s'%(self.container.mangledNames[(self.entitySet.name,k)],params.AddParam(self.container.PrepareSQLValue(v))))
	
	def WhereSkiptokenClause(self,where,params):
		"""Adds the entity constraint expression to a list of SQL expressions.
		
		where
			The list to append the skiptoken expression to."""
		skipExpression=[]
		i=ket=0
		while True:
			oName,dir=self.orderNames[i]
			v=self.skiptoken[i]
			op=">" if dir>0 else "<"
			skipExpression.append("(%s %s %s"%(oName,op,params.AddParam(self.container.PrepareSQLValue(v))))
			ket+=1
			i+=1
			if i<len(self.orderNames):
				# more to come
				skipExpression.append(" OR (%s = %s AND "%(oName,params.AddParam(self.container.PrepareSQLValue(v))))
				ket+=1
				continue
			else:
				skipExpression.append(u")"*ket)
				break
		where.append(string.join(skipExpression,''))
		
	def OrderBy(self,orderby):
		"""Sets the orderby rules for this collection.
		
		We override the default implementation to calculate a list
		of field name aliases to use in ordered queries.  For example,
		if the orderby expression is "tolower(Name) desc" then each SELECT
		query will be generated with an additional expression, e.g.::
		
			SELECT ID, Name, DOB, LCASE(Name) AS O1 ... ORDER BY O1 DESC, ID ASC
			
		The name "O1" is obtained from the name mangler using the tuple::
		
			(entitySet.name,'O1')

		Subsequent order expressions have names 'O2', 'O3', etc.		

		Notice that regardless of the ordering expression supplied the
		keys are are always added to ensure that, when an ordering is
		required, a defined order results even at the expense of some
		redundancy."""
		self.orderby=orderby
		self.SetPage(None)
		self.orderNames=[]
		if self.orderby is not None:
			oi=0
			for expression,direction in self.orderby:
				oi=oi+1
				oName="o_%i"%oi
				oName=self.container.mangledNames.get((self.entitySet.name,oName),oName)
				self.orderNames.append((oName,direction))
		for key in self.entitySet.keys:
			mangledName=self.container.mangledNames[(self.entitySet.name,key)]
			if self.qualifyNames:
				mangledName="%s.%s"%(self.tableName,mangledName)
			self.orderNames.append((mangledName,1))
		self._sqlGen=None
		
	def OrderByClause(self):
		"""A utility method to return the orderby clause.
		
		params
			The :py:class:`SQLParams` object to add parameters to."""
		if self.orderNames:
			orderby=[]
			for expression,direction in self.orderNames:
				orderby.append("%s %s"%(expression,"DESC" if direction <0 else "ASC"))
			return ' ORDER BY '+string.join(orderby,u", ")
		else:
			return ''
	
	def OrderByCols(self,columnNames,params):
		"""A utility to add the column names and aliases for the ordering.
		
		columnNames
			A list of SQL column name/alias expressions
		
		params
			The :py:class:`SQLParams` object to add parameters to."""
		if self.orderby is not None:
			oNameIndex=0
			for expression,direction in self.orderby:
				oName,oDir=self.orderNames[oNameIndex]
				oNameIndex+=1
				sqlExpression=self.SQLExpression(expression,params)
				columnNames.append("%s AS %s"%(sqlExpression,oName))
			# add the remaining names (which are just the keys)
			while oNameIndex<len(self.orderNames):
				oName,oDir=self.orderNames[oNameIndex]
				oNameIndex+=1
				columnNames.append(oName)

	def FieldGenerator(self,entity,forUpdate=False):
		"""A utility generator method for mangled property names and values.
		
		entity
			Any instance of :py:class:`~pyslet.odata2.csdl.Entity`
		
		forUpdate
			True if the result should exclude the entity's keys
		
		The yielded values are tuples of (mangled field name,
		:py:class:`~pyslet.odata2.csdl.SimpleValue` instance).		
		Only selected fields are yielded."""
		if forUpdate:
			keys=entity.entitySet.keys
		for k,v in entity.DataItems():
			if entity.Selected(k) and (not forUpdate or k not in keys):
				if isinstance(v,edm.SimpleValue):
					mangledName=self.container.mangledNames[(self.entitySet.name,k)]
					if self.qualifyNames:
						mangledName="%s.%s"%(self.tableName,mangledName)
					yield mangledName,v
				else:
					for sourcePath,fv in self._ComplexFieldGenerator(v):
						mangledName=self.container.mangledNames[tuple([self.entitySet.name,k]+sourcePath)]
						if self.qualifyNames:
							mangledName="%s.%s"%(self.tableName,mangledName)
						yield mangledName,fv
	
	def _ComplexFieldGenerator(self,ct):
		for k,v in ct.iteritems():
			if isinstance(v,edm.SimpleValue):
				yield [k],v
			else:
				for sourcePath,fv in self._ComplexFieldGenerator(v):
					yield [k]+sourcePath,fv
	
	SQLBinaryExpressionMethod={}
	SQLCallExpressionMethod={}
	
	def SQLExpression(self,expression,params,context="AND"):
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
		
		Where method are documented as having no default implementation,
		NotImplementedError is raised."""
		if isinstance(expression,core.UnaryExpression):
			raise NotImplementedError
		elif isinstance(expression,core.BinaryExpression):
			return getattr(self,self.SQLBinaryExpressionMethod[expression.operator])(expression,params,context)
		elif isinstance(expression,UnparameterizedLiteral):	
			return unicode(expression.value)
		elif isinstance(expression,core.LiteralExpression):
			return params.AddParam(self.container.PrepareSQLValue(expression.value))
		elif isinstance(expression,core.PropertyExpression):
			try:
				p=self.entitySet.entityType[expression.name]
				if isinstance(p,edm.Property):
					if p.complexType is None:
						fieldName=self.container.mangledNames[(self.entitySet.name,expression.name)]
						if self.qualifyNames:
							return "%s.%s"%(self.tableName,fieldName)
						else:
							return fieldName
					else:
						raise core.EvaluationError("Unqualified property %s must refer to a simple type"%expresison.name)
			except KeyError:
				raise core.EvaluationError("Property %s is not declared"%expression.name)
		elif isinstance(expression,core.CallExpression):
			return getattr(self,self.SQLCallExpressionMethod[expression.method])(expression,params,context)
	
	def SQLBracket(self,query,context,operator):
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
		if SQLOperatorPrecedence[context]>SQLOperatorPrecedence[operator]:
			return "(%s)"%query
		else:
			return query
		
	def SQLExpressionMember(self,expression,params,context):
		"""Converts a member expression, e.g., Address/City

		This implementation does not support the use of navigation
		properties but does support references to complex properties.

		It outputs the mangled name of the property, qualified by the
		table name if :py:attr:`qualifyNames` is True."""
		nameList=self._CalculateMemberFieldName(expression)
		contextDef=self.entitySet.entityType
		for name in nameList:
			if contextDef is None:
				raise core.EvaluationError("Property %s is not declared"%string.join(nameList,'/'))
			p=contextDef[name]
			if isinstance(p,edm.Property):
				if p.complexType is not None:
					contextDef=p.complexType
				else:
					contextDef=None
			elif isinstance(p,edm.NavigationProperty):
				raise NotImplementedError("Use of navigation properties in expressions not supported")
		# the result must be a simple property, so contextDef must not be None
		if contextDef is not None:
			raise core.EvaluationError("Property %s does not reference a primitive type"%string.join(nameList,'/'))
		fieldName=self.container.mangledNames[tuple([self.entitySet.name]+nameList)]
		if self.qualifyNames:
			return "%s.%s"%(self.tableName,fieldName)
		else:
			return fieldName

	def _CalculateMemberFieldName(self,expression):
		if isinstance(expression,core.PropertyExpression):
			return [expression.name]
		elif isinstance(expression,core.BinaryExpression) and expression.operator==core.Operator.member:
			return self._CalculateMemberFieldName(expression.operands[0])+self._CalculateMemberFieldName(expression.operands[1])
		else:
			raise core.EvaluationError("Unexpected use of member expression")
			
	def SQLExpressionCast(self,expression,params,context):
		"""Converts the cast expression: no default implementation"""
		raise NotImplementedError

	def SQLExpressionGenericBinary(self,expression,params,context,operator):
		"""A utility method for implementing binary operator conversion.
		
		The signature of the basic :py:meth:`SQLExpression` is extended
		to include an *operator* argument, a string representing the
		(binary) SQL operator corresponding to the expression object.""" 
		query=[]
		query.append(self.SQLExpression(expression.operands[0],params,operator))
		query.append(u' ')
		query.append(operator)
		query.append(u' ')
		query.append(self.SQLExpression(expression.operands[1],params,operator))
		return self.SQLBracket(string.join(query,''),context,operator)
	
	def SQLExpressionMul(self,expression,params,context):
		"""Converts the mul expression: maps to SQL "*" """
		return self.SQLExpressionGenericBinary(expression,params,context,'*')

	def SQLExpressionDiv(self,expression,params,context):
		"""Converts the div expression: maps to SQL "/" """
		return self.SQLExpressionGenericBinary(expression,params,context,'/')

	def SQLExpressionMod(self,expression,params,context):
		"""Converts the mod expression: no default implementation"""
		raise NotImplementedError

	def SQLExpressionAdd(self,expression,params,context):
		"""Converts the add expression: maps to SQL "+" """
		return self.SQLExpressionGenericBinary(expression,params,context,'+')

	def SQLExpressionSub(self,expression,params,context):
		"""Converts the sub expression: maps to SQL "-" """
		return self.SQLExpressionGenericBinary(expression,params,context,'-')
		
	def SQLExpressionLt(self,expression,params,context):
		"""Converts the lt expression: maps to SQL "<" """
		return self.SQLExpressionGenericBinary(expression,params,context,'<')

	def SQLExpressionGt(self,expression,params,context):
		"""Converts the gt expression: maps to SQL ">" """
		return self.SQLExpressionGenericBinary(expression,params,context,'>')

	def SQLExpressionLe(self,expression,params,context):
		"""Converts the le expression: maps to SQL "<=" """
		return self.SQLExpressionGenericBinary(expression,params,context,'<=')

	def SQLExpressionGe(self,expression,params,context):
		"""Converts the ge expression: maps to SQL ">=" """
		return self.SQLExpressionGenericBinary(expression,params,context,'>=')

	def SQLExpressionIsOf(self,expression,params,context):
		"""Converts the isof expression: no default implementation"""
		raise NotImplementedError

	def SQLExpressionEq(self,expression,params,context):
		"""Converts the eq expression: maps to SQL "=" """
		return self.SQLExpressionGenericBinary(expression,params,context,'=')

	def SQLExpressionNe(self,expression,params,context):
		"""Converts the ne expression: maps to SQL "<>" """
		return self.SQLExpressionGenericBinary(expression,params,context,'<>')

	def SQLExpressionAnd(self,expression,params,context):
		"""Converts the and expression: maps to SQL "AND" """
		return self.SQLExpressionGenericBinary(expression,params,context,'AND')

	def SQLExpressionOr(self,expression,params,context):
		"""Converts the or expression: maps to SQL "OR" """
		return self.SQLExpressionGenericBinary(expression,params,context,'OR')

	def SQLExpressionEndswith(self,expression,params,context):
		"""Converts the endswith function: maps to "op[0] LIKE '%'+op[1]"
		
		This is implemented using the concatenation operator"""
		percent=edm.SimpleValue.NewSimpleValue(edm.SimpleType.String)
		percent.SetFromValue(u"'%'")
		percent=UnparameterizedLiteral(percent)
		concat=core.CallExpression(core.Method.concat)
		concat.operands.append(percent)
		concat.operands.append(expression.operands[1])
		query=[]
		query.append(self.SQLExpression(expression.operands[0],params,'LIKE'))
		query.append(" LIKE ")
		query.append(self.SQLExpression(concat,params,'LIKE'))
		return self.SQLBracket(string.join(query,''),context,'LIKE')
		
	def SQLExpressionIndexof(self,expression,params,context):
		"""Converts the indexof method: no default implementation"""
		raise NotImplementedError
		
	def SQLExpressionReplace(self,expression,params,context):
		"""Converts the replace method: no default implementation"""
		raise NotImplementedError
		
	def SQLExpressionStartswith(self,expression,params,context):
		"""Converts the startswith function: maps to "op[0] LIKE op[1]+'%'"
		
		This is implemented using the concatenation operator"""
		percent=edm.SimpleValue.NewSimpleValue(edm.SimpleType.String)
		percent.SetFromValue(u"'%'")
		percent=UnparameterizedLiteral(percent)
		concat=core.CallExpression(core.Method.concat)
		concat.operands.append(expression.operands[1])
		concat.operands.append(percent)
		query=[]
		query.append(self.SQLExpression(expression.operands[0],params,'LIKE'))
		query.append(" LIKE ")
		query.append(self.SQLExpression(concat,params,'LIKE'))
		return self.SQLBracket(string.join(query,''),context,'LIKE')
		
	def SQLExpressionTolower(self,expression,params,context):
		"""Converts the tolower method: no default implementation"""
		raise NotImplementedError
		
	def SQLExpressionToupper(self,expression,params,context):
		"""Converts the toupper method: no default implementation"""
		raise NotImplementedError
		
	def SQLExpressionTrim(self,expression,params,context):
		"""Converts the trim method: no default implementation"""
		raise NotImplementedError
		
	def SQLExpressionSubstring(self,expression,params,context):
		"""Converts the substring method: no default implementation"""
		raise NotImplementedError
		
	def SQLExpressionSubstringof(self,expression,params,context):
		"""Converts the substringof function: maps to "op[1] LIKE '%'+op[0]+'%'"

		To do this we need to invoke the concatenation operator.
		
		This method has been poorly defined in OData with the parameters
		being switched between versions 2 and 3.  It is being withdrawn
		as a result and replaced with contains in OData version 4.  We
		follow the version 3 convention here of "first parameter in the
		second parameter" which fits better with the examples and with
		the intuitive meaning::
		
			substringof(A,B) == A in B"""
		percent=edm.SimpleValue.NewSimpleValue(edm.SimpleType.String)
		percent.SetFromValue(u"'%'")
		percent=UnparameterizedLiteral(percent)
		rconcat=core.CallExpression(core.Method.concat)
		rconcat.operands.append(expression.operands[0])
		rconcat.operands.append(percent)
		lconcat=core.CallExpression(core.Method.concat)
		lconcat.operands.append(percent)
		lconcat.operands.append(rconcat)
		query=[]
		query.append(self.SQLExpression(expression.operands[1],params,'LIKE'))
		query.append(" LIKE ")
		query.append(self.SQLExpression(lconcat,params,'LIKE'))
		return self.SQLBracket(string.join(query,''),context,'LIKE')
				
	def SQLExpressionConcat(self,expression,params,context):
		"""Converts the concat method: no default implementation"""
		raise NotImplementedError
		
	def SQLExpressionLength(self,expression,params,context):
		"""Converts the length method: no default implementation"""
		raise NotImplementedError
		
	def SQLExpressionYear(self,expression,params,context):
		"""Converts the year method: no default implementation"""
		raise NotImplementedError
		
	def SQLExpressionMonth(self,expression,params,context):
		"""Converts the month method: no default implementation"""
		raise NotImplementedError
		
	def SQLExpressionDay(self,expression,params,context):
		"""Converts the day method: no default implementation"""
		raise NotImplementedError
		
	def SQLExpressionHour(self,expression,params,context):
		"""Converts the hour method: no default implementation"""
		raise NotImplementedError
		
	def SQLExpressionMinute(self,expression,params,context):
		"""Converts the minute method: no default implementation"""
		raise NotImplementedError
		
	def SQLExpressionSecond(self,expression,params,context):
		"""Converts the second method: no default implementation"""
		raise NotImplementedError
		
	def SQLExpressionRound(self,expression,params,context):
		"""Converts the round method: no default implementation"""
		raise NotImplementedError
		
	def SQLExpressionFloor(self,expression,params,context):
		"""Converts the floor method: no default implementation"""
		raise NotImplementedError
		
	def SQLExpressionCeiling(self,expression,params,context):
		"""Converts the ceiling method: no default implementation"""
		raise NotImplementedError
		
	
SQLCollectionMixin.SQLCallExpressionMethod={
	core.Method.endswith:'SQLExpressionEndswith',
	core.Method.indexof:'SQLExpressionIndexof',
	core.Method.replace:'SQLExpressionReplace',
	core.Method.startswith:'SQLExpressionStartswith',
	core.Method.tolower:'SQLExpressionTolower',
	core.Method.toupper:'SQLExpressionToupper',
	core.Method.trim:'SQLExpressionTrim',
	core.Method.substring:'SQLExpressionSubstring',
	core.Method.substringof:'SQLExpressionSubstringof',
	core.Method.concat:'SQLExpressionConcat',
	core.Method.length:'SQLExpressionLength',
	core.Method.year:'SQLExpressionYear',
	core.Method.month:'SQLExpressionMonth',
	core.Method.day:'SQLExpressionDay',
	core.Method.hour:'SQLExpressionHour',
	core.Method.minute:'SQLExpressionMinute',
	core.Method.second:'SQLExpressionSecond',
	core.Method.round:'SQLExpressionRound',
	core.Method.floor:'SQLExpressionFloor',
	core.Method.ceiling:'SQLExpressionCeiling'
	}

SQLCollectionMixin.SQLBinaryExpressionMethod={
	core.Operator.member:'SQLExpressionMember',
	core.Operator.cast:'SQLExpressionCast',
	core.Operator.mul:'SQLExpressionMul',
	core.Operator.div:'SQLExpressionDiv',
	core.Operator.mod:'SQLExpressionMod',
	core.Operator.add:'SQLExpressionAdd',
	core.Operator.sub:'SQLExpressionSub',
	core.Operator.lt:'SQLExpressionLt',
	core.Operator.gt:'SQLExpressionGt',
	core.Operator.le:'SQLExpressionLe',
	core.Operator.ge:'SQLExpressionGe',
	core.Operator.isof:'SQLExpressionIsOf',
	core.Operator.eq:'SQLExpressionEq',
	core.Operator.ne:'SQLExpressionNe',
	core.Operator.boolAnd:'SQLExpressionAnd',
	core.Operator.boolOr:'SQLExpressionOr'
	}

			
class SQLEntityCollection(SQLCollectionMixin,core.EntityCollection):
	"""Represents a collection of entities from an :py:class:`EntitySet`
	stored in a :py:class:`SQLEntityContainer`.
	
	The base constructor is extended to allow the *container* to be
	passed.
	
	This class is the heart of the SQL implementation of the API,
	constructing and executing queries to implement the core methods
	from :py:class:`pyslet.odata2.csdl.EntityCollection`."""	
	def __init__(self,entitySet,container):
		core.EntityCollection.__init__(self,entitySet)
		SQLCollectionMixin.__init__(self,container)

	def InsertEntity(self,entity,fromEnd=None,fkValues=None):
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

			This has two effects on the operation of the method. 
			Firstly it suppresses any check for a required link via this
			association (as it is assumed that the link is, or will be,
			present). Secondly, it suppresses the commit on the database
			connection on the assumption that the caller will commit an
			associated insert or update enabling the two operations to
			succeed or fail together as a single transaction.

		fkValues
			If the association referred to by *fromEnd* is represented
			by a set of foreign keys stored in this entity set's table
			(see :py:class:`SQLReverseKeyCollection`) then fkValues is
			the list of (mangled column name, value) tuples that must be
			inserted in order to create the link.
		
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
		commit=fromEnd is None
		rollback=False
		if entity.exists:
			raise edm.EntityExists(str(entity.GetLocation()))
		# We must also go through each bound navigation property of our
		# own and add in the foreign keys for forward links.
		if fkValues is None:
			fkValues=[]
		fkMapping=self.container.fkTable[self.entitySet.name]
		try:
			navigationDone=set()
			for linkEnd,navName in self.entitySet.linkEnds.iteritems():
				if navName:
					dv=entity[navName]			
				if linkEnd.otherEnd.associationEnd.multiplicity==edm.Multiplicity.One:
					# a required association
					if linkEnd==fromEnd:
						continue
					if navName is None:
						# unbound principal; can only be created from this association
						raise edm.NavigationConstraintError("Entities in %s can only be created from their principal"%self.entitySet.name)
					if not dv.bindings:
						raise edm.NavigationConstraintError("Required navigation property %s of %s is not bound"%(navName,self.entitySet.name))
				associationSetName=linkEnd.parent.name
				# if linkEnd is in fkMapping it means we are keeping a
				# foreign key for this property, it may even be required but
				# either way, let's deal with it now.  We're only interested
				# in associations that are bound to navigation properties.
				if linkEnd not in fkMapping or navName is None:
					continue
				nullable,unique=fkMapping[linkEnd]
				targetSet=linkEnd.otherEnd.entitySet
				if len(dv.bindings)==0:
					#	we've already checked the case where nullable is False above
					continue
				elif len(dv.bindings)>1:
					raise edm.NavigationConstraintError("Unexpected error: found multiple bindings for foreign key constraint %s"%navName)
				binding=dv.bindings[0]
				if not isinstance(binding,edm.Entity):
					# just a key, grab the entity
					with targetSet.OpenCollection() as targetCollection:
						targetCollection.SelectKeys()
						targetEntity=targetCollection[binding]
					dv.bindings[0]=targetEntity
				else:
					targetEntity=binding
					if not targetEntity.exists:
						# add this entity to it's base collection
						with targetSet.OpenCollection() as targetCollection:
							targetCollection.InsertEntity(targetEntity,linkEnd.otherEnd)
							rollback=True
				# Finally, we have a target entity, add the foreign key to fkValues
				for keyName in targetSet.keys:
					fkValues.append((self.container.mangledNames[(self.entitySet.name,associationSetName,keyName)],targetEntity[keyName]))
				navigationDone.add(navName)
			# Step 2
			entity.SetConcurrencyTokens()
			query=['INSERT INTO ',self.tableName,' (']
			columnNames,values=zip(*(list(self.FieldGenerator(entity))+fkValues))
			query.append(string.join(columnNames,", "))
			query.append(') VALUES (')
			params=self.container.ParamsClass()
			query.append(string.join(map(lambda x:params.AddParam(self.container.PrepareSQLValue(x)),values),", "))
			query.append(');')
			query=string.join(query,'')
			logging.info("%s; %s",query,unicode(params.params))
			self.cursor.execute(query,params.params)
			entity.exists=True
			# Step 3
			for k,dv in entity.NavigationItems():
				linkEnd=self.entitySet.navigation[k]
				if not dv.bindings:
					continue
				elif k in navigationDone:
					dv.bindings=[]
					continue
				associationSetName=linkEnd.parent.name
				targetSet=dv.Target()
				targetFKMapping=self.container.fkTable[targetSet.name]
				with dv.OpenCollection() as navCollection, targetSet.OpenCollection() as targetCollection:
					while dv.bindings:
						binding=dv.bindings[0]
						if not isinstance(binding,edm.Entity):
							targetCollection.SelectKeys()
							binding=targetCollection[binding]
						if binding.exists:
							navCollection.InsertLink(binding)
							rollback=True
						else:
							if linkEnd.otherEnd in targetFKMapping:
								# target table has a foreign key
								targetFKValues=[]
								for keyName in self.entitySet.keys:
									targetFKValues.append((self.container.mangledNames[(targetSet.name,associationSetName,keyName)],entity[keyName]))
								targetCollection.InsertEntity(binding,linkEnd.otherEnd,targetFKValues)
								rollback=True
							else:
								# foreign keys are in an auxiliary table
								targetCollection.InsertEntity(binding,linkEnd.otherEnd)
								rollback=True
								navCollection.InsertLink(binding)
						dv.bindings=dv.bindings[1:]
			if commit:
				self.dbc.commit()			
		except self.container.dbapi.IntegrityError,e:
			# we might need to distinguish between a failure due to fkValues or a missing key
			if commit and rollback:
				self.Rollback(e)
			raise KeyError(str(entity.GetLocation()))
		except self.container.dbapi.Error as e:
			if commit and rollback:
				self.Rollback(e)
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
		except:
			if commit and rollback:
				self.Rollback(sys.exc_info()[0])
			raise
												
	def SetPage(self,top,skip=0,skiptoken=None):
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
		self.top=top
		self.skip=skip
		if skiptoken is None:
			self.skiptoken=None
		else:
			# parse a sequence of literal values
			p=core.Parser(skiptoken)
			self.skiptoken=[]
			while True:
				p.ParseWSP()
				self.skiptoken.append(p.RequireProduction(p.ParseURILiteral()))
				p.ParseWSP()
				if not p.Parse(','):
					if p.MatchEnd():
						break
					else:
						raise core.InvalidSystemQueryOption("Unrecognized $skiptoken: %s"%skiptoken)
			if self.orderby is None:
				orderLen=0
			else:
				orderLen=len(self.orderby)
			if len(self.skiptoken)==orderLen+len(self.entitySet.keys)+1:
				# the last value must be an integer we add to skip
				if isinstance(self.skiptoken[-1],edm.Int32Value):
					self.skip+=self.skiptoken[-1].value
					self.skiptoken=self.skiptoken[:-1]
				else:
					raise core.InvalidSystemQueryOption("skiptoken incompatible with ordering: %s"%skiptoken)
			elif len(self.skiptoken)!=orderLen+len(self.entitySet.keys):
				raise core.InvalidSystemQueryOption("skiptoken incompatible with ordering: %s"%skiptoken)									
		self.nextSkiptoken=None
			
	def NextSkipToken(self):
		if self.nextSkiptoken:
			token=[]
			for t in self.nextSkiptoken:
				token.append(core.ODataURI.FormatLiteral(t))
			return string.join(token,u",")
		else:
			return None
			
	def pageGenerator(self,setNextPage=False):
		if self.top==0:
			# end of paging
			return
		entity=self.NewEntity()
		query=["SELECT "]
		params=self.container.ParamsClass()
		columnNames,values=zip(*list(self.FieldGenerator(entity)))
		columnNames=list(columnNames)
		# now add the order by clauses
		self.nextSkiptoken=None
		oNameIndex=0
		if self.orderby is not None:
			for expression,direction in self.orderby:
				oName,oDir=self.orderNames[oNameIndex]
				oNameIndex+=1
				sqlExpression=self.SQLExpression(expression,params)
				columnNames.append("%s AS %s"%(sqlExpression,oName))
		# default ordering is by key, so always add the remaining order names (which are just the keys)
		while oNameIndex<len(self.orderNames):
			oName,oDir=self.orderNames[oNameIndex]
			oNameIndex+=1
			columnNames.append(oName)
		query.append(string.join(columnNames,", "))
		query.append(' FROM ')
		query.append(self.tableName)
		query.append(self.WhereClause(None,params,useFilter=True,useSkip=True))
		query.append(self.OrderByClause())
		query=string.join(query,'')
		cursor=None
		try:
			skip=self.skip
			top=self.top
			topmax=self.topmax
			cursor=self.dbc.cursor()
			logging.info("%s; %s",query,unicode(params.params))
			cursor.execute(query,params.params)
			while True:
				row=cursor.fetchone()
				if row is None:
					# no more pages
					if setNextPage:
						self.top=self.skip=0
						self.skipToken=None
					break
				if skip:
					skip=skip-1
					continue
				if entity is None:
					entity=self.NewEntity()
					values=zip(*list(self.FieldGenerator(entity)))[1]
				rowValues=list(row)
				for value,newValue in zip(values,rowValues):
					self.container.ReadSQLValue(value,newValue)
				entity.exists=True
				yield entity
				if topmax is not None:
					topmax=topmax-1
					if topmax<1:
						# this is the last entity, set the nextSkiptoken
						orderValues=rowValues[-len(self.orderNames):]
						self.nextSkiptoken=[]
						for v in orderValues:
							self.nextSkiptoken.append(self.container.NewFromSQLValue(v))
						tokenLen=0
						for v in self.nextSkiptoken:
							if v and isinstance(v,(edm.StringValue,edm.BinaryValue)):
								tokenLen+=len(v.value)
						# a really large skiptoken is no use to anyone
						if tokenLen>512:
							# ditch this one, copy the previous one and add a skip
							self.nextSkiptoken=list(self.skiptoken)
							v=edm.Int32Value()
							v.SetFromValue(self.topmax)
							self.nextSkiptoken.append(v)
						if setNextPage:
							self.skiptoken=self.nextSkiptoken
							self.skip=0
						break
				if top is not None:
					top=top-1
					if top<1:
						if setNextPage:
							if self.skip is not None:
								self.skip=self.skip+self.top
							else:
								self.skip=self.top
						break
				entity=None
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
		finally:
			if cursor is not None:
				cursor.close()

	def iterpage(self,setNextPage=False):
		return self.ExpandEntities(
			self.pageGenerator(setNextPage))
		
# 	def __getitem__(self,key):
# 		entity=self.NewEntity()
# 		entity.SetKey(key)
# 		params=self.container.ParamsClass()
# 		query=["SELECT "]
# 		columnNames,values=zip(*list(self.FieldGenerator(entity)))
# 		query.append(string.join(columnNames,", "))
# 		query.append(' FROM ')
# 		query.append(self.tableName)
# 		query.append(self.WhereClause(entity,params))
# 		query=string.join(query,'')
# 		try:
# 			logging.info("%s; %s",query,unicode(params.params))
# 			self.cursor.execute(query,params.params)
# 			rowcount=self.cursor.rowcount
# 			row=self.cursor.fetchone()
# 			if rowcount==0 or row is None:
# 				raise KeyError
# 			elif rowcount>1 or (rowcount==-1 and self.cursor.fetchone() is not None):
# 				# whoops, that was unexpected
# 				raise SQLError("Integrity check failure, non-unique key: %s"%repr(key))
# 			for value,newValue in zip(values,row):
# 				self.container.ReadSQLValue(value,newValue)
# 			entity.exists=True
# 			entity.Expand(self.expand,self.select)
# 			return entity
# 		except self.container.dbapi.Error,e:
# 			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))

	def UpdateEntity(self,entity):
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
			InsertEntity before the link is created.
		
		The same transactional behaviour as :py:meth:`InsertEntity` is
		exhibited."""
		if not entity.exists:
			raise edm.NonExistentEntity("Attempt to update non existent entity: "+str(entity.GetLocation()))
			fkValues=[]
		fkValues=[]
		fkMapping=self.container.fkTable[self.entitySet.name]
		rollback=False
		try:
			navigationDone=set()
			for k,dv in entity.NavigationItems():
				linkEnd=self.entitySet.navigation[k]
				if not dv.bindings:
					continue
				associationSetName=linkEnd.parent.name
				# if linkEnd is in fkMapping it means we are keeping a
				# foreign key for this property, it may even be required but
				# either way, let's deal with it now.  This will insert or
				# update the link automatically, this navigation property
				# can never be a collection
				if linkEnd not in fkMapping:
					continue
				targetSet=linkEnd.otherEnd.entitySet
				nullable,unique=fkMapping[linkEnd]
				if len(dv.bindings)>1:
					raise NavigationConstraintError("Unexpected error: found multiple bindings for foreign key constraint %s"%k)
				binding=dv.bindings[0]
				if not isinstance(binding,edm.Entity):
					# just a key, grab the entity
					with targetSet.OpenCollection() as targetCollection:
						targetCollection.SelectKeys()
						targetEntity=targetCollection[binding]
					dv.bindings[0]=targetEntity
				else:
					targetEntity=binding
					if not targetEntity.exists:
						# add this entity to it's base collection
						with targetSet.OpenCollection() as targetCollection:
							targetCollection.InsertEntity(targetEntity,linkEnd.otherEnd)
							rollback=True
				# Finally, we have a target entity, add the foreign key to fkValues
				for keyName in targetSet.keys:
					fkValues.append((self.container.mangledNames[(self.entitySet.name,associationSetName,keyName)],targetEntity[keyName]))
				navigationDone.add(k)
			# grab a list of sql-name,sql-value pairs representing the key constraint
			concurrencyCheck=False
			constraints=[]
			for k,v in entity.KeyDict().items():
				constraints.append((self.container.mangledNames[(self.entitySet.name,k)],
					self.container.PrepareSQLValue(v)))
			cvList=list(self.FieldGenerator(entity,True))
			for cName,v in cvList:
				# concurrency tokens get added as if they were part of the key
				if v.pDef.concurrencyMode==edm.ConcurrencyMode.Fixed:
					concurrencyCheck=True
					constraints.append((cName,self.container.PrepareSQLValue(v)))
			# now update the entity to have the latest concurrency token
			entity.SetConcurrencyTokens()
			query=['UPDATE ',self.tableName,' SET ']
			params=self.container.ParamsClass()
			updates=[]
			for cName,v in cvList+fkValues:
				updates.append('%s=%s'%(cName,params.AddParam(self.container.PrepareSQLValue(v))))
			query.append(string.join(updates,', '))
			query.append(' WHERE ')
			where=[]
			for cName,cValue in constraints:
				where.append('%s=%s'%(cName,params.AddParam(cValue)))
			query.append(string.join(where,' AND '))
			query=string.join(query,'')
			logging.info("%s; %s",query,unicode(params.params))
			self.cursor.execute(query,params.params)
			if self.cursor.rowcount==0:
				# no rows matched this constraint, probably a concurrency failure
				if concurrencyCheck:
					raise edm.ConcurrencyError
				else:
					raise KeyError("Entity %s does not exist"%str(entity.GetLocation()))					
			#	We finish off the bindings in a similar way to InsertEntity
			#	but this time we need to handle the case where there is an
			#	existing link and the navigation property is not a
			#	collection. 
			for k,dv in entity.NavigationItems():
				linkEnd=self.entitySet.navigation[k]
				if not dv.bindings:
					continue
				elif k in navigationDone:
					dv.bindings=[]
					continue
				associationSetName=linkEnd.parent.name
				targetSet=dv.Target()
				targetFKMapping=self.container.fkTable[targetSet.name]
				with dv.OpenCollection() as navCollection, targetSet.OpenCollection() as targetCollection:
					while dv.bindings:
						binding=dv.bindings[0]
						if not isinstance(binding,edm.Entity):
							targetCollection.SelectKeys()
							binding=targetCollection[binding]
						if binding.exists:
							if dv.isCollection:
								navCollection.InsertLink(binding)
								rollback=True
							else:
								navCollection.Replace(binding)
								rollback=True
						else:
							if linkEnd.otherEnd in targetFKMapping:
								# target table has a foreign key
								targetFKValues=[]
								for keyName in self.entitySet.keys:
									targetFKValues.append((self.container.mangledNames[(targetSet.name,associationSetName,keyName)],entity[keyName]))
								if not dv.isCollection:
									navCollection.clear()
								targetCollection.InsertEntity(binding,linkEnd.otherEnd,targetFKValues)
								rollback=True
							else:
								# foreign keys are in an auxiliary table
								targetCollection.InsertEntity(binding,linkEnd.otherEnd)
								if dv.isCollection:
									navCollection.InsertLink(binding)
								else:
									navCollection.Replace(binding)
								rollback=True
						dv.bindings=dv.bindings[1:]
			self.dbc.commit()
		except self.container.dbapi.IntegrityError as e:
			# we might need to distinguish between a failure due to fkValues or a missing key
			self.Rollback(e)
			raise KeyError(str(entity.GetLocation()))
		except self.container.dbapi.Error as e:
			self.Rollback(e)
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
		except:
			self.Rollback(sys.exc_info()[0])
			raise
	
	def UpdateLink(self,entity,linkEnd,targetEntity,noReplace=False,commit=True):
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

		commit
			If True (the default) then the link is added in a single
			transaction, otherwise the connection is left uncommitted."""
		if not entity.exists:
			raise edm.NonExistentEntity("Attempt to update non-existent entity: "+str(entity.GetLocation()))
		query=['UPDATE ',self.tableName,' SET ']
		params=self.container.ParamsClass()
		updates=[]
		nullCols=[]
		targetSet=linkEnd.otherEnd.entitySet
		associationSetName=linkEnd.parent.name
		nullable,unique=self.container.fkTable[self.entitySet.name][linkEnd]
		if not nullable and targetEntity is None:
			raise edm.NavigationConstraintError("Can't remove a required link")			
		if targetEntity:
			for keyName in targetSet.keys:
				v=targetEntity[keyName]
				cName=self.container.mangledNames[(self.entitySet.name,associationSetName,keyName)]
				updates.append('%s=%s'%(cName,params.AddParam(self.container.PrepareSQLValue(v))))
				if noReplace:
					nullCols.append(cName)
		else:
			for keyName in targetSet.keys:
				cName=self.container.mangledNames[(self.entitySet.name,associationSetName,keyName)]
				updates.append('%s=NULL'%cName)
		query.append(string.join(updates,', '))
		# we don't do concurrency checks on links, and we suppress the filter check too
		query.append(self.WhereClause(entity,params,False,nullCols=nullCols))
		query=string.join(query,'')
		try:
			logging.info("%s; %s",query,unicode(params.params))
			self.cursor.execute(query,params.params)
			if self.cursor.rowcount==0:
				if nullCols:
					# this could be a constraint failure, rather than a key failure
					if entity.Key() in self:
						raise edm.NavigationConstraintError("Entity %s is already linked through association %s"%(entity.GetLocation(),associationSetName))
					else:
						# no rows matched this constraint must be a key failure
						raise KeyError("Entity %s does not exist"%str(entity.GetLocation()))
			if commit:
				self.dbc.commit()			
		except self.container.dbapi.IntegrityError:
			raise KeyError("Linked entity %s does not exist"%str(targetEntity.GetLocation()))
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
		
	def __delitem__(self,key):
		with self.entitySet.OpenCollection() as base:
			base.SelectKeys()
			entity=base[key]
		self.DeleteEntity(entity)
	
	def DeleteEntity(self,entity,fromEnd=None,commit=True):
		"""Deletes an entity
		
		Called by the dictionary-like del operator, provided as a
		separate method to enable it to be called recursively when
		doing cascade deletes and to support transactions.

		fromEnd
			An optional
			:py:class:`~pyslet.odata2.csdl.AssociationSetEnd` bound to
			this entity set that represents the link from which we are
			being deleted during a cascade delete.
		
		commit
			If True (the default) then the entity is deleted in a single
			transaction, otherwise the connection is left uncommitted."""
		rollback=False
		try:
			fkMapping=self.container.fkTable[self.entitySet.name]
			for linkEnd,navName in self.entitySet.linkEnds.iteritems():
				if linkEnd==fromEnd:
					continue
				associationSetName=linkEnd.parent.name
				if linkEnd in fkMapping:
					# if we are holding a foreign key then deleting us will delete
					# the link too, so nothing to do here.
					continue
				else:
					if linkEnd.associationEnd.multiplicity==edm.Multiplicity.One:
						# we are required, so it must be a 1-? relationship
						if navName is not None:
							# and it is bound to a navigation property so we can cascade delete
							targetEntitySet=linkEnd.otherEnd.entitySet
							with entity[navName].OpenCollection() as links, targetEntitySet.OpenCollection() as cascade:
								links.SelectKeys()
								for targetEntity in links.values():
									links.DeleteLink(targetEntity,commit=False)
									rollback=True
									cascade.DeleteEntity(targetEntity,linkEnd.otherEnd,commit=False)
						else:
							raise edm.NavigationConstraintError("Can't cascade delete from an entity in %s as the association set %s is not bound to a navigation property"%(self.entitySet.name,associationSetName))
					else:
						# we are not required, so just drop the links
						if navName is not None:
							with entity[navName].OpenCollection() as links:
								links.ClearLinks(commit=False)
						# otherwise annoying, we need to do something special
						elif associationSetName in self.container.auxTable:
							# foreign keys are in an association table,
							# hardest case as navigation may be unbound so
							# we have to call a class method and pass the
							# container and connection
							SQLAssociationCollection.ClearLinksUnbound(self.container,linkEnd,entity,self.dbc)
							rollback=True
						else:
							# foreign keys are at the other end of the link, we have a method for that...
							targetEntitySet=linkEnd.otherEnd.entitySet
							with targetEntitySet.OpenCollection() as keyCollection:
								keyCollection.ClearLinks(linkEnd.otherEnd,entity,commit=False)
								rollback=True
			params=self.container.ParamsClass()
			query=["DELETE FROM "]
			params=self.container.ParamsClass()
			query.append(self.tableName)
			# WHERE - ignore the filter
			query.append(self.WhereClause(entity,params,useFilter=False))
			query=string.join(query,'')
			logging.info("%s; %s",query,unicode(params.params))
			self.cursor.execute(query,params.params)
			rowcount=self.cursor.rowcount
			if rowcount==0:
				raise KeyError
			elif rowcount>1:
				# whoops, that was unexpected
				raise SQLError("Integrity check failure, non-unique key: %s"%repr(key))
			if commit:
				self.dbc.commit()
		except self.container.dbapi.Error,e:
			if commit and rollback:
				self.Rollback(e)
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
		except:
			if commit and rollback:
				self.Rollback(sys.exc_info()[0])
			raise

	def DeleteLink(self,entity,linkEnd,targetEntity,commit=True):
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

		commit
			If True (the default) then the link is deleted in a single
			transaction, otherwise the connection is left
			uncommitted."""						
		if not entity.exists:
			raise edm.NonExistentEntity("Attempt to update non-existent entity: "+str(entity.GetLocation()))
		query=['UPDATE ',self.tableName,' SET ']
		params=self.container.ParamsClass()
		updates=[]
		associationSetName=linkEnd.parent.name
		targetSet=linkEnd.otherEnd.entitySet
		nullable,unique=self.container.fkTable[self.entitySet.name][linkEnd]
		if not nullable:
			raise edm.NavigationConstraintError("Can't remove a required link from association set %s"%associationSetName)			
		for keyName in targetSet.keys:
			cName=self.container.mangledNames[(self.entitySet.name,associationSetName,keyName)]
			updates.append('%s=NULL'%cName)	
		query.append(string.join(updates,', '))
		# custom where clause to ensure that the link really existed before we delete it
		query.append(' WHERE ')
		where=[]
		kd=entity.KeyDict()
		for k,v in kd.items():
			where.append('%s=%s'%(self.container.mangledNames[(self.entitySet.name,k)],params.AddParam(self.container.PrepareSQLValue(v))))
		for keyName in targetSet.keys:
			v=targetEntity[keyName]
			cName=self.container.mangledNames[(self.entitySet.name,associationSetName,keyName)]
			where.append('%s=%s'%(cName,params.AddParam(self.container.PrepareSQLValue(v))))
		query.append(string.join(where,' AND '))
		query=string.join(query,'')
		try:
			logging.info("%s; %s",query,unicode(params.params))
			self.cursor.execute(query,params.params)
			if self.cursor.rowcount==0:
				# no rows matched this constraint, entity either doesn't exist or wasn't linked to the target
				raise KeyError("Entity %s does not exist or is not linked to %s"%str(entity.GetLocation(),targetEntity.GetLocation))					
			if commit:
				self.dbc.commit()
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
		
	def ClearLinks(self,linkEnd,targetEntity,commit=True):
		"""Deletes all links to *targetEntity*
		
		The foreign key for this link must be held in this entity set's
		table.
		
		linkEnd
			The :py:class:`~pyslet.odata2.csdl.AssociationSetEnd` bound
			to this entity set that represents this entity set's end of
			the assocation being modified.

		targetEntity
			The target entity that defines the link(s) to be removed.

		commit
			If True (the default) then the link is deleted in a single
			transaction, otherwise the connection is left
			uncommitted."""		
		query=['UPDATE ',self.tableName,' SET ']
		params=self.container.ParamsClass()
		updates=[]
		associationSetName=linkEnd.parent.name
		targetSet=linkEnd.otherEnd.entitySet
		nullable,unique=self.container.fkTable[self.entitySet.name][linkEnd]
		for keyName in targetSet.keys:
			cName=self.container.mangledNames[(self.entitySet.name,associationSetName,keyName)]
			updates.append('%s=NULL'%cName)	
		# custom where clause
		query.append(string.join(updates,', '))
		query.append(' WHERE ')
		where=[]
		for keyName in targetSet.keys:
			v=targetEntity[keyName]
			cName=self.container.mangledNames[(self.entitySet.name,associationSetName,keyName)]
			where.append('%s=%s'%(cName,params.AddParam(self.container.PrepareSQLValue(v))))
		query.append(string.join(where,' AND '))
		query=string.join(query,'')
		try:
			logging.info("%s; %s",query,unicode(params.params))
			self.cursor.execute(query,params.params)
			if commit:
				self.dbc.commit()			
		except self.container.dbapi.IntegrityError:
			# catch the nullable violation here, makes it benign to clear links to an unlinked target
			raise edm.NavigationConstraintError("Can't remove required link from assocation set %s"%associationSetName)
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
		
	def CreateTableQuery(self):
		"""Returns a SQL statement and params object suitable for creating the table."""
		entity=self.NewEntity()
		query=['CREATE TABLE ',self.tableName,' (']
		params=self.container.ParamsClass()
		cols=[]
		for c,v in self.FieldGenerator(entity):
			cols.append("%s %s"%(c,self.container.PrepareSQLType(v,params)))
		keys=entity.KeyDict()
		constraints=[]
		constraints.append(u'PRIMARY KEY (%s)'%string.join(map(lambda x:self.container.mangledNames[(self.entitySet.name,x)],keys.keys()),u', '))
		# Now generate the foreign keys
		fkMapping=self.container.fkTable[self.entitySet.name]
		for linkEnd in fkMapping:
			associationSetName=linkEnd.parent.name
			targetSet=linkEnd.otherEnd.entitySet
			nullable,unique=fkMapping[linkEnd]
			targetTable=self.container.mangledNames[(targetSet.name,)]
			fkNames=[]
			kNames=[]
			for keyName in targetSet.keys:
				# create a dummy value to catch the unusual case where there is a default
				v=targetSet.entityType[keyName]()
				cName=self.container.mangledNames[(self.entitySet.name,associationSetName,keyName)]
				fkNames.append(cName)
				kNames.append(self.container.mangledNames[(targetSet.name,keyName)])
				cols.append("%s %s"%(cName,self.container.PrepareSQLType(v,params,nullable)))
			constraints.append("CONSTRAINT %s FOREIGN KEY (%s) REFERENCES %s(%s)"%(
				self.container.QuoteIdentifier(associationSetName),
				string.join(fkNames,', '),
				self.container.mangledNames[(targetSet.name,)],
				string.join(kNames,', ')))
		cols=cols+constraints
		query.append(string.join(cols,u", "))
		query.append(u')')
		return string.join(query,''),params

	def CreateTable(self):
		"""Executes the SQL statement returned by :py:meth:`CreateTableQuery`"""
		query,params=self.CreateTableQuery()
		try:
			logging.info("%s; %s",query,unicode(params.params))
			self.cursor.execute(query,params.params)
			self.dbc.commit()
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
				

class SQLNavigationCollection(SQLCollectionMixin,core.NavigationEntityCollection):
	"""Abstract class representing all navigation collections.
	
	name
		The name of the navigation property represented by this
		collection.

	fromEntity
		The entity being navigated from
	
	toEntitySet
		The target entity set.  This is the entity set bound to the other
		end of the association referenced by the navigation property.
		The collection behaves like a subset of this entity set.
	
	associationSetName
		The name of the association set that defines this relationship.
		This additional parameter is used by the name mangler to obtain
		the field name (or table name) used for the foreign keys."""	
	def __init__(self,name,fromEntity,toEntitySet,container,associationSetName):
		core.NavigationEntityCollection.__init__(self,name,fromEntity,toEntitySet)
		SQLCollectionMixin.__init__(self,container)
		self.associationSetName=associationSetName

	
class SQLForeignKeyCollection(SQLNavigationCollection):
	"""The collection of entities obtained by navigation via a foreign key
	
	This object is used when the foreign key is stored in the same
	table as *fromEntity*.  The name mangler looks for the foreign key
	in the field obtained by mangling::
	
		(entity set name, association set name, key name)
	
	For example, suppose that a link exists from entity type Order[*] to
	entity type Customer[0..1] and that these types are used by entity
	sets Orders and Customers respectively.  Assume that the key field
	of Customer is "CustomerID".  If the association set that binds
	Orders to Customers with this link is called Orders_Customers then
	the foreign key would obtained by looking up::
	
		('Orders','Orders_Customers','CustomerID')
	
	By default this would result in the field name::
	
		'Orders_Customers_CustomerID'
	
	This field would be looked up in the 'Orders' table.  The operation
	of the name mangler can be customised by overriding the
	:py:meth:`SQLEntityContainer.MangleName` method in the container."""	 
	def __init__(self,name,fromEntity,toEntitySet,container,associationSetName):
		super(SQLForeignKeyCollection,self).__init__(name,fromEntity,toEntitySet,container,associationSetName)
		self.qualifyNames=True
		# clumsy, reset the ordernames; need a method to set qualifyNames now
		self.OrderBy(None)
		self.keyCollection=self.fromEntity.entitySet.OpenCollection()
		self.sourceName=self.container.mangledNames[(self.fromEntity.entitySet.name,self.name)]
	
	def JoinClause(self):
		"""Overridden to provide a join to the entity set containing the *fromEntity*.""" 
		join=[]
		# we don't need to look up the details of the join again, as self.entitySet must be the target
		for keyName in self.entitySet.keys:
			join.append('%s.%s=%s.%s'%(
				self.tableName,
				self.container.mangledNames[(self.entitySet.name,keyName)],
				self.sourceName,
				self.container.mangledNames[(self.fromEntity.entitySet.name,self.associationSetName,keyName)]))
		return ' INNER JOIN %s AS %s ON '%(self.fromEntity.entitySet.name,self.sourceName)+string.join(join,', ')

	def WhereClause(self,entity,params,useFilter=True,useSkip=False,nullCols=()):
		"""Overridden to add the constraint to entities linked from *fromEntity* only."""
		where=[]
		for k,v in self.fromEntity.KeyDict().items():
			where.append(u"%s.%s=%s"%(self.sourceName,
				self.container.mangledNames[(self.fromEntity.entitySet.name,k)],
				params.AddParam(self.container.PrepareSQLValue(v))))
		if entity is not None:
			self.WhereEntityClause(where,entity,params)
		if self.filter is not None and useFilter:
			# useFilter option adds the current filter too
			where.append('('+self.SQLExpression(self.filter,params)+')')
		if self.skiptoken is not None and useSkip:
			self.WhereSkiptokenClause(where,params)
		for nullCol in nullCols:
			where.append('%s IS NULL'%nullCol)
		if where:
			return ' WHERE '+string.join(where,' AND ')
		else:
			return ''
			
# 	def entityGenerator(self):
# 		entity=self.NewEntity()
# 		query=["SELECT "]
# 		params=self.container.ParamsClass()
# 		columnNames,values=zip(*list(self.FieldGenerator(entity)))
# 		# qualify with the table name
# 		query.append(string.join(map(lambda x:self.tableName+"."+x,columnNames),", "))
# 		query.append(' FROM ')
# 		query.append(self.tableName)
# 		query.append(self.JoinClause())
# 		query.append(self.WhereClause(None,params))
# 		if self.orderby is not None:
# 			query.append(self.OrderByClause(params))
# 		query=string.join(query,'')
# 		cursor=None
# 		try:
# 			cursor=self.dbc.cursor()
# 			logging.info("%s; %s",query,unicode(params.params))
# 			cursor.execute(query,params.params)
# 			while True:
# 				row=cursor.fetchone()
# 				if row is None:
# 					break
# 				if entity is None:
# 					entity=self.NewEntity()
# 					values=zip(*list(self.FieldGenerator(entity)))[1]
# 				for value,newValue in zip(values,row):
# 					self.container.ReadSQLValue(value,newValue)
# 				entity.exists=True
# 				yield entity
# 				entity=None
# 		except self.container.dbapi.Error,e:
# 			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
# 		finally:
# 			if cursor is not None:
# 				cursor.close()
# 				
# 	def itervalues(self):
# 		return self.ExpandEntities(
# 			self.entityGenerator())
		
	def __setitem__(self,key,entity):
		# sanity check entity to check it can be inserted here
		if not isinstance(entity,edm.Entity) or entity.entitySet is not self.entitySet:
			raise TypeError
		if key!=entity.Key():
			raise ValueError
		# we open the base collection and call the update link method
		self.keyCollection.UpdateLink(self.fromEntity,self.fromEnd,entity)
		
	def Replace(self,entity):
		# Target multiplicity must be 0..1 or 1; treat it the same as setitem
		if not isinstance(entity,edm.Entity) or entity.entitySet is not self.entitySet:
			raise TypeError
		self.keyCollection.UpdateLink(self.fromEntity,self.fromEnd,entity)
	
	def __delitem__(self,key):
		#	Before we remove a link we need to know if this is ?-1
		#	relationship, if so, this deletion will result in a
		#	constraint violation.
		if self.toMultiplicity==edm.Multiplicity.One:
			raise edm.NavigationConstraintError("Can't remove a required link")
		# we open the base collection and call the update link method
		self.keyCollection.UpdateLink(self.fromEntity,self.fromEnd,None)

	def close(self):
		self.keyCollection.close()
		super(SQLForeignKeyCollection,self).close()


class SQLReverseKeyCollection(SQLNavigationCollection):
	
	def __init__(self,name,fromEntity,toEntitySet,container,associationSetName):
		super(SQLReverseKeyCollection,self).__init__(name,fromEntity,toEntitySet,container,associationSetName)
		# The relation is actually stored in the *toEntitySet*
		# which is the same entity set that our results will be drawn
		# from, which makes it easier as we don't need a join
		self.keyCollection=self.entitySet.OpenCollection()

	def WhereClause(self,entity,params,useFilter=True,useSkip=False,nullCols=()):
		"""Overridden to add the constraint to entities linked from *fromEntity* only."""
		where=[]
		for k,v in self.fromEntity.KeyDict().items():
			where.append(u"%s=%s"%(
				self.container.mangledNames[(self.entitySet.name,self.associationSetName,k)],
				params.AddParam(self.container.PrepareSQLValue(v))))
		if entity is not None:
			self.WhereEntityClause(where,entity,params)
		if self.filter is not None and useFilter:
			# useFilter option adds the current filter too
			where.append('('+self.SQLExpression(self.filter,params)+')')
		if self.skiptoken is not None and useSkip:
			self.WhereSkiptokenClause(where,params)
		for nullCol in nullCols:
			where.append('%s IS NULL'%nullCol)
		if where:
			return ' WHERE '+string.join(where,' AND ')
		else:
			return ''

	def OrderByClause(self,params):
		orderby=[]
		for expression,direction in self.orderby:
			orderby.append("%s %s"%(self.SQLExpression(expression,params),"DESC" if direction <0 else "ASC"))
		return ' ORDER BY '+string.join(orderby,u", ")
			
	def InsertEntity(self,entity):
		"""Inserts *entity* into this collection.
		
		We need to calculate the values for the foreign keys fields
		and pass them to the baseCollection."""
		fkValues=[]
		for k,v in self.fromEntity.KeyDict().items():
			fkValues.append((self.container.mangledNames[(self.entitySet.name,self.associationSetName,k)],v))
		self.keyCollection.InsertEntity(entity,self.fromEnd.otherEnd,fkValues)

	def __setitem__(self,key,entity):
		# sanity check entity to check it can be inserted here
		if not isinstance(entity,edm.Entity) or entity.entitySet is not self.entitySet:
			raise TypeError
		if key!=entity.Key():
			raise ValueError
		self.InsertLink(entity)
		
	def InsertLink(self,entity):
		# the fromMultiplicity must be 1 or 0..1 for this type of
		# collection.  If *entity* is already linked to a different
		# fromEntity it's an error, we don't just blithely update the
		# foreign key as that would implicitly break that link
		self.keyCollection.UpdateLink(entity,self.fromEnd.otherEnd,self.fromEntity,noReplace=True)
				
	def entityGenerator(self):
		entity=self.NewEntity()
		query=["SELECT "]
		params=self.container.ParamsClass()
		columnNames,values=zip(*list(self.FieldGenerator(entity)))
		# qualify with the table name
		query.append(string.join(columnNames,", "))
		query.append(' FROM ')
		query.append(self.tableName)
		query.append(self.WhereClause(None,params))
		if self.orderby is not None:
			query.append(self.OrderByClause(params))
		query=string.join(query,'')
		cursor=None
		try:
			cursor=self.dbc.cursor()
			logging.info("%s; %s",query,unicode(params.params))
			cursor.execute(query,params.params)
			while True:
				row=cursor.fetchone()
				if row is None:
					break
				if entity is None:
					entity=self.NewEntity()
					values=zip(*list(self.FieldGenerator(entity)))[1]
				for value,newValue in zip(values,row):
					self.container.ReadSQLValue(value,newValue)
				entity.exists=True
				yield entity
				entity=None
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
		finally:
			if cursor is not None:
				cursor.close()
				
	def itervalues(self):
		return self.ExpandEntities(
			self.entityGenerator())

	def __delitem__(self,key):
		entity=self.keyCollection[key]
		if self.fromMultiplicity==edm.Multiplicity.One:
			# we are required, this must be an error
			raise edm.NavigationConstraintError("Can't delete required link from association set %s"%self.associationSetName)
		# fromMultiplicity is 0..1
		self.keyCollection.DeleteLink(entity,self.fromEnd.otherEnd,self.fromEntity)
		
	def DeleteLink(self,entity,commit=True):
		"""Called during cascaded deletes to force-remove a link prior
		to the deletion of the entity itself.  As the foreign key for
		this association is in the entity's record itself we don't have
		to do anything."""
		pass
		
	def clear(self):
		self.keyCollection.ClearLinks(self.fromEnd.otherEnd,self.fromEntity)
	
	def ClearLinks(self,commit=True):
		self.keyCollection.ClearLinks(self.fromEnd.otherEnd,self.fromEntity,commit=commit)
			
	def close(self):
		self.keyCollection.close()
		super(SQLReverseKeyCollection,self).close()


class SQLAssociationCollection(SQLNavigationCollection):
	"""The implementation is similar to SQLForeignKeyCollection except
	that we use the association set's name as the table name that
	contains the keys and combine the name of the entity set with the
	navigation property to use as a prefix for the field path.
	
	The code to update links is different because we need to distinguish
	an insert from an update."""	
	def __init__(self,name,fromEntity,toEntitySet,container,associationSetName):
		super(SQLAssociationCollection,self).__init__(name,fromEntity,toEntitySet,container,associationSetName)
		# The relation is actually stored in an extra table so we will
		# need a join for all operations.
		self.qualifyNames=True
		# clumsy, reset the ordernames; need a method to set qualifyNames now
		self.OrderBy(None)
		#	self.associationSetName=associationSetName
		self.associationSetName=self.fromEnd.parent.name
		self.associationTableName=self.container.mangledNames[(self.associationSetName,)]
		entitySetA,nameA,entitySetB,nameB,self.uniqueKeys=container.auxTable[self.associationSetName]
		if fromEntity.entitySet is entitySetA and name==nameA:
			self.fromNavName=nameA
			self.toNavName=nameB
		else:
			self.fromNavName=nameB
			self.toNavName=nameA
	
	def JoinClause(self):
		join=[]
		# we don't need to look up the details of the join again, as self.entitySet must be the target
		for keyName in self.entitySet.keys:
			join.append('%s.%s=%s.%s'%(
				self.tableName,
				self.container.mangledNames[(self.entitySet.name,keyName)],
				self.associationTableName,
				self.container.mangledNames[(self.associationSetName,self.entitySet.name,self.toNavName,keyName)]))
		return ' INNER JOIN %s ON '%self.associationTableName+string.join(join,', ')
	
	def WhereClause(self,entity,params,useFilter=True):
		where=[]
		for k,v in self.fromEntity.KeyDict().items():
			where.append(u"%s.%s=%s"%(self.associationTableName,
				self.container.mangledNames[(self.associationSetName,self.fromEntity.entitySet.name,self.fromNavName,k)],
				params.AddParam(self.container.PrepareSQLValue(v))))
		if entity is not None:
			for k,v in entity.KeyDict().items():
				where.append(u"%s.%s=%s"%(self.associationTableName,
					self.container.mangledNames[(self.associationSetName,entity.entitySet.name,self.toNavName,k)],
					params.AddParam(self.container.PrepareSQLValue(v))))
		if useFilter and self.filter is not None:
			where.append("(%s)"%self.SQLExpression(self.filter,params))		
		return ' WHERE '+string.join(where,' AND ')
	
# 	def OrderByClause(self,params):
# 		orderby=[]
# 		for expression,direction in self.orderby:
# 			orderby.append("%s %s"%(self.SQLExpression(expression,params),"DESC" if direction <0 else "ASC"))
# 		return ' ORDER BY '+string.join(orderby,u", ")
			
	def InsertEntity(self,entity):
		"""Inserts *entity* into the base collection and then adds a
		link to this auxiliary table."""
		with self.entitySet.OpenCollection() as baseCollection:
			# if this is a 1-1 relationship InsertEntity will fail (with
			# an unbound navigation property) so we need to suppress the
			# back-link.
			baseCollection.InsertEntity(entity,linkEnd.otherEnd)
			self.InsertLink(entity)

	def __setitem__(self,key,entity):
		# sanity check entity to check it can be inserted here
		if not isinstance(entity,edm.Entity) or entity.entitySet is not self.entitySet:
			raise TypeError
		if key!=entity.Key():
			raise ValueError
		if not entity.exists:
			raise edm.NonExistentEntity("Attempt to update non-existent entity: "+str(entity.GetLocation()))
		self.InsertLink(entity)
	
	def InsertLink(self,entity):
		query=['INSERT INTO ',self.associationTableName,' (']
		params=self.container.ParamsClass()
		valueNames=[]
		values=[]
		for k,v in self.fromEntity.KeyDict().items():
			valueNames.append(self.container.mangledNames[(self.associationSetName,self.fromEntity.entitySet.name,self.fromNavName,k)])
			values.append(params.AddParam(self.container.PrepareSQLValue(v)))
		for k,v in entity.KeyDict().items():
			valueNames.append(self.container.mangledNames[(self.associationSetName,self.entitySet.name,self.toNavName,k)])
			values.append(params.AddParam(self.container.PrepareSQLValue(v)))
		query.append(string.join(valueNames,', '))
		query.append(') VALUES (')
		query.append(string.join(values,', '))
		query.append(')')
		query=string.join(query,'')
		query=string.join(query,'')
		try:
			logging.info("%s; %s",query,unicode(params.params))
			self.cursor.execute(query,params.params)
			self.dbc.commit()
		except self.container.dbapi.IntegrityError:
			raise edm.NavigationConstraintError("Model integrity error when linking %s and %s"%(str(self.fromEntity.GetLocation()),str(entity.GetLocation())))
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
			
	def entityGenerator(self):
		entity=self.NewEntity()
		query=["SELECT "]
		params=self.container.ParamsClass()
		columnNames,values=zip(*list(self.FieldGenerator(entity)))
		# qualify with the table name
		# query.append(string.join(map(lambda x:self.tableName+"."+x,columnNames),", "))
		query.append(string.join(columnNames,", "))
		query.append(' FROM ')
		query.append(self.tableName)
		query.append(self.JoinClause())
		query.append(self.WhereClause(None,params))
		if self.orderby is not None:
			query.append(self.OrderByClause(params))
		query=string.join(query,'')
		cursor=None
		try:
			cursor=self.dbc.cursor()
			logging.info("%s; %s",query,unicode(params.params))
			cursor.execute(query,params.params)
			while True:
				row=cursor.fetchone()
				if row is None:
					break
				if entity is None:
					entity=self.NewEntity()
					values=zip(*list(self.FieldGenerator(entity)))[1]
				for value,newValue in zip(values,row):
					self.container.ReadSQLValue(value,newValue)
				entity.exists=True
				yield entity
				entity=None
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
		finally:
			if cursor is not None:
				cursor.close()
				
	def itervalues(self):
		return self.ExpandEntities(
			self.entityGenerator())
		
	def Replace(self,entity):
		if self.fromEntity[self.fromNavName].isCollection:
			# No special handling
			super(SQLAssociationCollection,self).Replace(entity)
		else:
			# We don't support symmetric associations of the 0..1 - 0..1
			# variety so this must be a 1..1 relationship.
			raise edm.NavigationConstraintError("Replace not allowed for 1-1 relationship (implicit delete not supported)")
	
	def __delitem__(self,key):
		#	Before we remove a link we need to know if this is 1-1
		#	relationship, if so, this deletion will result in a
		#	constraint violation.
		if self.uniqueKeys:
			raise edm.NavigationConstraintError("Can't remove a required link")
		with self.entitySet.OpenCollection() as targetCollection:
			targetCollection.SelectKeys()
			entity=targetCollection[key]
		self.DeleteLink(entity)

	def DeleteLink(self,entity,commit=True):
		"""Called during cascaded deletes to force-remove a link prior
		to the deletion of the entity itself"""
		query=['DELETE FROM ',self.associationTableName]
		params=self.container.ParamsClass()
		# we suppress the filter check on the where clause
		query.append(self.WhereClause(entity,params,False))
		query=string.join(query,'')
		try:
			logging.info("%s; %s",query,unicode(params.params))
			self.cursor.execute(query,params.params)
			if self.cursor.rowcount==0:
				# no rows matched this constraint must be a key failure at one of the two ends
				raise KeyError("One of the entities %s or %s no longer exists"%(str(self.fromEntity.GetLocation()),str(entity.GetLocation())))
			if commit:
				self.dbc.commit()
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))

	def ClearLinks(self,commit=True):
		query=['DELETE FROM ',self.associationTableName]
		params=self.container.ParamsClass()
		# we suppress the filter check on the where clause
		query.append(self.WhereClause(None,params,False))
		query=string.join(query,'')
		try:
			logging.info("%s; %s",query,unicode(params.params))
			self.cursor.execute(query,params.params)
			if commit:
				self.dbc.commit()
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
		
	@classmethod
	def ClearLinksUnbound(cls,container,fromEnd,fromEntity,dbc):
		"""Special class method for deleting all the links from the
		entity *fromEntity* where it represents *fromEnd* in a symmetric
		association.
		
		This is a class method because it has to work even if there is
		no navigation property bound to this end of the association."""
		associationSetName=fromEnd.parent.name
		associationTableName=container.mangledNames[(associationSetName,)]
		navName=fromEntity.entitySet.linkEnds[fromEnd]
		if navName is None:
			# this is most likely the case, we're being called this way
			# because we can't instantiate a collection on an unbound
			# navigation property
			navName=u""
		entitySetA,nameA,entitySetB,nameB,uniqueKeys=container.auxTable[associationSetName]
		if fromEntity.entitySet is entitySetA and navName==nameA:
			fromNavName=nameA
		else:
			fromNavName=nameB
		query=['DELETE FROM ',associationTableName]
		params=container.ParamsClass()
		query.append(' WHERE ')
		where=[]
		for k,v in fromEntity.KeyDict().items():
			where.append(u"%s.%s=%s"%(associationTableName,
				container.mangledNames[(associationSetName,fromEntity.entitySet.name,fromNavName,k)],
				params.AddParam(container.PrepareSQLValue(v))))
		query.append(string.join(where,' AND '))
		query=string.join(query,'')
		try:
			logging.info("%s; %s",query,unicode(params.params))
			cursor=dbc.cursor()
			cursor.execute(query,params.params)
			cursor.close()
		except container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))		
	
	@classmethod
	def CreateTable(cls,container,associationSetName):
		dbc=container.AcquireConnection(SQL_TIMEOUT)		#: a connection to the database
		if dbc is None:
			raise DatabaseBusy("Failed to acquire connection after %is"%SQL_TIMEOUT)
		try:
			cursor=dbc.cursor()
			query,params=cls.CreateTableQuery(container,associationSetName)
			logging.info("%s; %s",query,unicode(params.params))
			cursor.execute(query,params.params)
			dbc.commit()
		except container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
		finally:
			if dbc is not None:
				if cursor is not None:
					cursor.close()
				container.ReleaseConnection(dbc)
	
	@classmethod
	def CreateTableQuery(cls,container,associationSetName):
		tableName=container.mangledNames[(associationSetName,)]
		entitySetA,nameA,entitySetB,nameB,uniqueKeys=container.auxTable[associationSetName]
		query=['CREATE TABLE ',container.mangledNames[(associationSetName,)],' (']
		params=container.ParamsClass()
		cols=[]
		constraints=[]
		pkNames=[]
		for es,prefix,ab in ((entitySetA,nameA,'A'),(entitySetB,nameB,'B')):
			targetTable=container.mangledNames[(es.name,)]
			fkNames=[]
			kNames=[]
			for keyName in es.keys:
				# create a dummy value to catch the unusual case where there is a default
				v=es.entityType[keyName]()
				cName=container.mangledNames[(associationSetName,es.name,prefix,keyName)]
				fkNames.append(cName)
				pkNames.append(cName)
				kNames.append(container.mangledNames[(es.name,keyName)])
				cols.append("%s %s"%(cName,container.PrepareSQLType(v,params)))
			constraints.append("CONSTRAINT %s FOREIGN KEY (%s) REFERENCES %s(%s)"%(
				container.QuoteIdentifier(u"fk"+ab),
				string.join(fkNames,', '),
				targetTable,
				string.join(kNames,', ')))
			if uniqueKeys:
				constraints.append("CONSTRAINT %s UNIQUE (%s)"%(
					container.QuoteIdentifier(u"u"+ab),
					string.join(fkNames,', ')))
		# Finally, add a unique constraint spanning all columns as we don't want duplicate relations
		constraints.append("CONSTRAINT %s UNIQUE (%s)"%(
			container.QuoteIdentifier(u"pk"),
			string.join(pkNames,', ')))
		cols=cols+constraints
		query.append(string.join(cols,u", "))
		query.append(u')')
		return string.join(query,''),params


class DummyLock(object):
	"""An object to use in place of a real Lock, can always be acquired"""
	
	def acquire(self,blocking=None):
		return True
	
	def release(self):
		pass

	def __enter__(self):
		return self
	
	def __exit__(self):
		pass


# class SQLCursor(object):
# 
# 	def __init__(self,container):
# 		self.container=container
# 		
# 	def __enter__(self):
# 		"""On entry we secure the module lock and then get a connection object"""
# 		self.connection=self.container.GetConnection()
# 		return self
# 		
# 	def __exit__(self):
# 		self.container.ReleaseConnection()
# 
# 
class SQLParams(object):
	
	def __init__(self):
		self.params=None	#: an object suitable for passing to execute
		
	def AddParam(self,value):
		"""Adds a value to this set of parameters returning the string to include in the query."""
		raise NotImplementedError

class QMarkParams(SQLParams):
	
	def __init__(self):
		super(QMarkParams,self).__init__()
		self.params=[]
	
	def AddParam(self,value):
		self.params.append(value)
		return "?"	

class NumericParams(SQLParams):
	
	def __init__(self):
		super(QMarkParams,self).__init__()
		self.params=[]
	
	def AddParam(self,value):
		self.params.append(value)
		return ":%i"%len(self.params)

class NamedParams(SQLParams):
	
	def __init__(self):
		super(QMarkParams,self).__init__()
		self.params={}
	
	def AddParam(self,value):
		name="p%i"%len(self.params)
		self.params[name]=value
		return ":"+name


class SQLConnectionLock(object):
	
	def __init__(self,lockClass):
		self.threadId=None
		self.lock=lockClass()
		self.locked=0
		self.dbc=None
		

class SQLEntityContainer(object):
	
	def __init__(self,containerDef,dbapi,maxConnections=10,fieldNameJoiner=u"_"):
		self.containerDef=containerDef
		self.dbapi=dbapi				#: a DB API compatible module
		self.moduleLock=None
		if self.dbapi.threadsafety==0:
			# we can't even share the module, so just use one connection will do
			self.moduleLock=threading.RLock()
			self.connectionLocker=DummyLock
			self.cPoolMax=1
		else:
			# Level 1 and above we can share the module
			self.moduleLock=DummyLock()
			self.connectionLocker=threading.RLock
			self.cPoolMax=maxConnections
		self.cPoolLock=threading.Condition()
		self.cPoolClosing=False
		self.cPoolLocked={}
		self.cPoolUnlocked={}
		self.cPoolDead=[]
		# set up the parameter style
		if self.dbapi.paramstyle=="qmark":
			self.ParamsClass=QMarkParams
		elif self.dbapi.paramstyle=="numeric":
			self.ParamsClass=NumericParams
		elif self.dbapi.paramstyle=="named":
			self.ParamsClass=NamedParams
		else:
			# will fail later when we try and add parameters
			self.ParamsClass=SQLParams
		self.fkTable={}
		"""A mapping from an entity set end to a foreign key mapping of the form::
		
			{<association set end>: (<nullable flag>, <unique keys flag>),...}
		
		The outer mapping has one entry for each entity set (even if the
		corresponding foreign key mapping is empty).

		Each foreign key mapping has one entry for each foreign key
		reference that must appear in that entity set's table.  The key
		is an :py:class:`AssociationSetEnd` that is bound to the entity
		set (the other end will be bound to the target entity set). 
		This allows us to distinguish between the two ends of a
		recursive association."""
		self.auxTable={}
		"""A mapping from the names of symmetric association sets to a tuple of::
		
			( <entity set A>, <name prefix A>, <entity set B>, <name prefix B>, <unique keys> )"""
		self.mangledNames={}
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
		self.fieldNameJoiner=fieldNameJoiner
		"""Default string used to join complex field names in SQL
		queries, e.g. Address_City"""
		# for each entity set in this container, bind a SQLEntityCollection object
		for es in self.containerDef.EntitySet:
			self.fkTable[es.name]={}
			tableName=self.TableName(es.name)
			for sourcePath in self.SourcePathGenerator(es):
				self.mangledNames[sourcePath]=self.MangleName(sourcePath,False)
			self.BindEntitySet(es)
		for es in self.containerDef.EntitySet:
			for np in es.entityType.NavigationProperty:
				self.BindNavigationProperty(es,np.name)
		# once the navigation properties have been bound, fkTable will
		# have been populated with any foreign keys we need to add field
		# name mappings for
		for esName,fkMapping in self.fkTable.iteritems():
			for linkEnd,details in fkMapping.iteritems():
				associationSetName=linkEnd.parent.name
				targetSet=linkEnd.otherEnd.entitySet
				tableName=self.mangledNames[(esName,)]
				for keyName in targetSet.keys:
					"""Foreign keys are given fake source paths starting with the association set name::
					
						( u"Orders_Customers", u"CustomerID" )"""
					sourcePath=(esName,associationSetName,keyName)
					self.mangledNames[sourcePath]=self.MangleName(sourcePath)
		# and auxTable will have been populated with additional tables to
		# hold symmetric associations...
		for aSet in self.containerDef.AssociationSet:
			if aSet.name not in self.auxTable:
				continue
			tableName=self.mangledNames[(aSet.name,)]=self.MangleName((aSet.name,),False)
			"""Foreign keys in Tables that model association sets are
			given fake source paths that combine the entity set name and
			the name of the navigation property endpoint.

			This ensures the special case where the two entity sets are
			the same is taken care of (as the navigation property
			endpoints must still be unique). For one-way associations,
			prefixB will be an empty string."""
			esA,prefixA,esB,prefixB,unique=self.auxTable[aSet.name]
			for keyName in esA.keys:
				sourcePath=(aSet.name,esA.name,prefixA,keyName)
				self.mangledNames[sourcePath]=self.MangleName(sourcePath)
			for keyName in esB.keys:
				sourcePath=(aSet.name,esB.name,prefixB,keyName)
				self.mangledNames[sourcePath]=self.MangleName(sourcePath)

	def TableName(self,setName,navName=None):
		"""Returns the quoted identifier to use as the table name for
		entity or association set named *setName* in SQL queries.
		
		If navName is not None then the name returned should be an alias
		for the table to use in JOINed statements.  A combination of the
		two is usually sufficient."""
		if navName:
			return self.QuoteIdentifier(string.join((setName,navName),self.fieldNameJoiner))
		else:
			return self.QuoteIdentifier(setName)
	
	def FieldName(self,entitySetName,sourcePath):
		"""Returns the quoted identifier to use as the name for the
		field with *sourcePath* in the entity set with *entitySetName* .
		
		By default we join the sourcePath using :py:attr:`fieldNameJoiner`."""
		return self.QuoteIdentifier(string.join(sourcePath,self.fieldNameJoiner))

	def MangleName(self,sourcePath,navHint=False):
		if not navHint and len(sourcePath)>1:
			sourcePath=list(sourcePath)[1:]
		return self.QuoteIdentifier(string.join(sourcePath,self.fieldNameJoiner))
			
	def SourcePathGenerator(self,entitySet):
		"""Generates source path *tuples* for *entitySet*"""
		yield (entitySet.name,)
		for sourcePath in self.TypeNameGenerator(entitySet.entityType):
			yield tuple([entitySet.name]+sourcePath)
		for np in entitySet.entityType.NavigationProperty:
			yield (entitySet.name,np.name)
			
	def FieldNameGenerator(self,entitySet):
		"""Generates source path *tuples* for the fields in *entitySet*"""
		for sourcePath in self.TypeNameGenerator(entitySet.entityType):
			yield tuple(sourcePath)
			
	def TypeNameGenerator(self,typeDef):
		"""Generates source path *lists* from a complex or entity type"""
		for p in typeDef.Property:
			if p.complexType is not None:
				for subPath in self.TypeNameGenerator(p.complexType):
					yield [p.name]+subPath
			else:
				yield [p.name]
	
	def BindEntitySet(self,entitySet):		
		entitySet.Bind(self.GetCollectionClass(),container=self)

	def BindNavigationProperty(self,entitySet,name):
		# Start by making a tuple of the end multiplicities.
		fromASEnd=entitySet.navigation[name]
		toASEnd=fromASEnd.otherEnd
		# extract the name of the association set
		associationSetName=fromASEnd.parent.name
		targetSet=toASEnd.entitySet
		multiplicity=(fromASEnd.associationEnd.multiplicity,toASEnd.associationEnd.multiplicity)
		# now we can work on a case-by-case basis, note that fkTable may be
		# filled in twice for the same association (if navigation properties are
		# defined in both directions) but this is benign because the definition
		# should be identical.
		if multiplicity in (
			(edm.Multiplicity.One,edm.Multiplicity.One),
			(edm.Multiplicity.ZeroToOne,edm.Multiplicity.ZeroToOne)):
			entitySet.BindNavigation(name,self.GetSymmetricNavigationCollectionClass(),container=self,associationSetName=associationSetName)
			if associationSetName in self.auxTable:
				# This is the navigation property going back the other way, set the navigation name only
				self.auxTable[associationSetName][3]=name
			else:
				self.auxTable[associationSetName]=[entitySet,name,targetSet,"",True]
		elif multiplicity==(edm.Multiplicity.Many,edm.Multiplicity.Many):
			entitySet.BindNavigation(name,self.GetSymmetricNavigationCollectionClass(),container=self,associationSetName=associationSetName)
			if associationSetName in self.auxTable:
				self.auxTable[associationSetName][3]=name
			else:
				self.auxTable[associationSetName]=[entitySet,name,targetSet,"",False]
		elif multiplicity==(edm.Multiplicity.One,edm.Multiplicity.ZeroToOne):
			entitySet.BindNavigation(name,self.GetReverseKeyCollectionClass(),container=self,associationSetName=associationSetName)
			self.fkTable[targetSet.name][toASEnd]=(False,True)
		elif multiplicity==(edm.Multiplicity.One,edm.Multiplicity.Many):
			entitySet.BindNavigation(name,self.GetReverseKeyCollectionClass(),container=self,associationSetName=associationSetName)
			self.fkTable[targetSet.name][toASEnd]=(False,False)
		elif multiplicity==(edm.Multiplicity.ZeroToOne,edm.Multiplicity.Many):
			entitySet.BindNavigation(name,self.GetReverseKeyCollectionClass(),container=self,associationSetName=associationSetName)
			self.fkTable[targetSet.name][toASEnd]=(True,False)
		elif multiplicity==(edm.Multiplicity.ZeroToOne,edm.Multiplicity.One):
			entitySet.BindNavigation(name,self.GetForeignKeyCollectionClass(),container=self,associationSetName=associationSetName)
			self.fkTable[entitySet.name][fromASEnd]=(False,True)
		elif multiplicity==(edm.Multiplicity.Many,edm.Multiplicity.One):
			entitySet.BindNavigation(name,self.GetForeignKeyCollectionClass(),container=self,associationSetName=associationSetName)
			self.fkTable[entitySet.name][fromASEnd]=(False,False)
		else:
# 			(edm.Multiplicity.Many,edm.Multiplicity.ZeroToOne)
			entitySet.BindNavigation(name,self.GetForeignKeyCollectionClass(),container=self,associationSetName=associationSetName)
			self.fkTable[entitySet.name][fromASEnd]=(True,False)

	def GetCollectionClass(self):
		"""Called during construction, returns the collection class used
		to represent a generic entity set."""
		return SQLEntityCollection

	def GetSymmetricNavigationCollectionClass(self):
		"""Called during construction, returns the collection class used
		to represent a symmetric relation stored in a separate table."""
		return SQLAssociationCollection
			
	def GetForeignKeyCollectionClass(self):
		"""Called during construction, returns the collection class used
		to implement a relation consisting of a foreign key in the
		source table."""
		return SQLForeignKeyCollection
			
	def GetReverseKeyCollectionClass(self):
		"""Called during construction, returns the collection class used
		to implement a relation consisting of a foreign key in the
		target table."""
		return SQLReverseKeyCollection

	def CreateAllTables(self):
		visited=set()
		for es in self.containerDef.EntitySet:
			if es.name not in visited:
				self.CreateTable(es,visited)
		# we now need to go through the auxTable and create them
		for associationSetName in self.auxTable:
			self.GetSymmetricNavigationCollectionClass().CreateTable(self,associationSetName)
		
	def CreateTable(self,es,visited):
		# before we create this table, we need to check to see if it references another table
		visited.add(es.name)
		fkMapping=self.fkTable[es.name]
		for linkEnd,details in fkMapping.iteritems():
			targetSet=linkEnd.otherEnd.entitySet
			if targetSet.name in visited:
				# prevent recursion
				continue
			self.CreateTable(targetSet,visited)
		# now we are free to create the table
		with es.OpenCollection() as collection:
			collection.CreateTable()	
			
	def AcquireConnection(self,timeout=None):
		# block on the module for threadsafety==0 case
		threadId=threading.current_thread().ident
		now=start=time.time()
		with self.cPoolLock:
			if self.cPoolClosing:
				# don't open connections when we are trying to close them
				return None
			while not self.moduleLock.acquire(False):
				self.cPoolLock.wait(timeout)
				now=time.time()
				if timeout is not None and now>start+timeout:
					logging.warn("Thread[%i] timed out waiting for the the database module lock",threadId)
					return None
			# we have the module lock
			if threadId in self.cPoolLocked:
				# our threadId is in the locked table
				cLock=self.cPoolLocked[threadId]
				if cLock.lock.acquire(False):
					cLock.locked+=1
					return cLock.dbc
				else:
					logging.warn("Thread[%i] moved a database connection to the dead pool",threadId)
					self.cPoolDead.append(cLock)
					del self.cPoolLocked[threadId]
			while True:
				if threadId in self.cPoolUnlocked:
					# take the connection that belongs to us
					cLock=self.cPoolUnlocked[threadId]
					del self.cPoolUnlocked[threadId]
				elif len(self.cPoolUnlocked)+len(self.cPoolLocked)<self.cPoolMax:
					# Add a new connection
					cLock=SQLConnectionLock(self.connectionLocker)
					cLock.threadId=threadId
					cLock.dbc=self.OpenConnection()
				elif self.cPoolUnlocked:
					# take a connection that doesn't belong to us, popped at random
					oldThreadId,cLock=self.cPoolUnlocked.popitem()
					if self.dbapi.threadsafety>1:
						logging.debug("Thread[%i] recycled database connection from Thread[%i]",threadId,oldThreadId)
					else:
						logging.debug("Thread[%i] closed an unused database connection (max connections reached)",oldThreadId)
						cLock.dbc.close()	# is it ok to close a connection from a different thread?
						cLock.threadId=threadId
						cLock.dbc=self.OpenConnection()
				else:
					now=time.time()
					if timeout is not None and now>start+timeout:
						logging.warn("Thread[%i] timed out waiting for a database connection",threadId)
						break
					logging.debug("Thread[%i] forced to wait for a database connection",threadId)
					self.cPoolLock.wait(timeout)
					logging.debug("Thread[%i] resuming search for database connection",threadId)
					continue
				cLock.lock.acquire()
				cLock.locked+=1
				self.cPoolLocked[threadId]=cLock
				return cLock.dbc
		# we are defeated, no database connection for the caller
		# release lock on the module as there is no connection to release
		self.moduleLock.release()
		return None
						
	def ReleaseConnection(self,c):
		threadId=threading.current_thread().ident
		with self.cPoolLock:
			# we have exclusive use of the cPool members
			if threadId in self.cPoolLocked:
				cLock=self.cPoolLocked[threadId]
				if cLock.dbc is c:
					cLock.lock.release()
					self.moduleLock.release()
					cLock.locked-=1
					if not cLock.locked:
						del self.cPoolLocked[threadId]
						self.cPoolUnlocked[threadId]=cLock
						self.cPoolLock.notify()
					return
			logging.error("Thread[%i] attempting to release a database connection it didn't acquire",threadId) 
			# it seems likely that some other thread is going to leave a locked
			# connection now, let's try and find it to correct the situation
			badThread,badLock=None,None
			for tid,cLock in self.cPoolLocked.iteritems():
				if cLock.dbc is c:
					badThread=tid
					badLock=cLock
					break
			if badLock is not None:
				badLock.lock.release()
				self.moduleLock.release()
				badLock.locked-=1
				if not badLock.locked:
					del self.cPoolLocked[badThread]
					self.cPoolUnlocked[badLock.threadId]=badLock
					self.cPoolLock.notify()
					logging.warn("Thread[%i] released database connection acquired by Thread[%i]",threadId,badThread)
				return
			# this is getting frustrating, exactly which connection does
			# this thread think it is trying to release?
			# Check the dead pool just in case
			iDead=None
			for i in xrange(len(self.cPoolDead)):
				cLock=self.cPoolDead[i]
				if cLock.dbc is c:
					iDead=i
					break
			if iDead is not None:
				badLock=self.cPoolDead[iDead]
				badLock.lock.release()
				self.moduleLock.release()
				badLock.locked-=1
				logging.warn("Thread[%i] successfully released a database connection from the dead pool",threadId)
				if not badLock.locked:
					# no need to notify other threads as we close this connection for safety
					badLock.dbc.close()
					del self.cPoolDead[iDead]
					logging.warn("Thread[%i] removed a database connection from the dead pool",threadId)
				return
			# ok, this really is an error!
			logging.error("Thread[%i] attempted to unlock un unknown database connection: %s",threadId,repr(c))									

	def OpenConnection(self):
		"""Creates and returns a new connection object.
		
		Must be overridden by specific database implementations"""
		raise NotImplementedError

	def BreakConnection(self,connection):
		"""Called when closing or cleaning up locked connections.
		
		This method is called when the connection is locked (by a
		different thread) and the caller wants to force that thread to
		relinquish control.

		The default implementation does nothing, which might cause the
		close method to stall until the other thread relinquishes
		control normally.""" 
		pass
		
	def close(self,waitForLocks=True):
		"""Closes this database.
		
		This method goes through each open connection and attempts to
		acquire it before closing it.  If connections are locked by
		other threads we wait for those threads to release them, calling
		:py:meth:`BreakConnection` to speed up termination if
		:possible."""
		with self.cPoolLock:
			self.cPoolClosing=True
			while self.cPoolUnlocked:
				threadId,cLock=self.cPoolUnlocked.popitem()
				# we don't bother to acquire the lock
				cLock.dbc.close()
			while self.cPoolLocked:
				# trickier, these are in use
				threadId,cLock=self.cPoolLocked.popitem()
				while True:
					if cLock.lock.acquire(False):
						cLock.dbc.close()
						break
					elif waitForLocks:
						self.BreakConnection(cLock.dbc)
						logging.warn("Waiting to break database connection acquired by Thread[%i]",threadId)
						self.cPoolLock.wait()
					else:
						break
			while self.cPoolDead:
				cLock=self.cPoolDead.pop()
				while True:
					if cLock.lock.acquire(False):
						cLock.dbc.close()
						break
					elif waitForLocks:
						self.BreakConnection(cLock.dbc)
						logging.warn("Waiting to break a database connection from the dead pool")
						self.cPoolLock.wait()				
					else:
						break				

	def __del__(self):
		self.close(waitForLocks=False)
		
	def QuoteIdentifier(self,identifier):
		"""Given an *identifier* returns a safely quoted form of it.
		
		By default we strip double quote and then use them to enclose
		it.  E.g., if the string u'Employee_Name' is passed then the
		string u'"Employee_Name"' is returned."""
		return u'"%s"'%identifier.replace('"','')

	def PrepareSQLType(self,simpleValue,params,nullable=None):
		"""Given a simple value, returns a SQL-formatted name of its type.

		For example, if the value is Int32 then this might return the
		string u'INTEGER'"""
		p=simpleValue.pDef
		columnDef=[]
		if isinstance(simpleValue,edm.BinaryValue):
			if p.fixedLength:
				if p.maxLength:
					columnDef.append(u"BINARY(%i)"%p.maxLength)
				else:
					raise SQLModelError("Edm.Binary of fixed length missing max: %s"%p.name)
			elif p.maxLength:
				columnDef.append(u"VARBINARY(%i)"%p.maxLength)
			else:
				raise NotImplementedError("SQL binding for Edm.Binary of unbounded length: %s"%p.name)
		elif isinstance(simpleValue,edm.BooleanValue):
			columnDef.append(u"BOOLEAN")		
		elif isinstance(simpleValue,edm.ByteValue):
			columnDef.append(u"SMALLINT")
		elif isinstance(simpleValue,edm.DateTimeValue):
			columnDef.append("TIMESTAMP")
		elif isinstance(simpleValue,edm.DateTimeOffsetValue):
			# stored as string and parsed e.g. 20131209T100159+0100
			columnDef.append("CHARACTER(20)")
		elif isinstance(simpleValue,edm.DecimalValue):
			if p.precision is None:
				precision=10	# chosen to allow 32-bit integer precision
			else:
				precision=p.precision
			if p.scale is None:
				scale=0		# from the CSDL model specification
			else:
				scale=p.scale
			columnDef.append(u"DECIMAL(%i,%i)"%(precision,scale))
		elif isinstance(simpleValue,edm.DoubleValue):
			columnDef.append("FLOAT")
		elif isinstance(simpleValue,edm.GuidValue):
			columnDef.append("BINARY(16)")
		elif isinstance(simpleValue,edm.Int16Value):
			columnDef.append(u"SMALLINT")
		elif isinstance(simpleValue,edm.Int32Value):
			columnDef.append(u"INTEGER")
		elif isinstance(simpleValue,edm.Int64Value):
			columnDef.append(u"BIGINT")
		elif isinstance(simpleValue,edm.SByteValue):
			columnDef.append(u"SMALLINT")
		elif isinstance(simpleValue,edm.SingleValue):
			columnDef.append(u"REAL")
		elif isinstance(simpleValue,edm.StringValue):
			if p.unicode is None or p.unicode:
				n="N"
			else:
				n=""
			if p.fixedLength:
				if p.maxLength:
					columnDef.append(u"%sCHAR(%i)"%(n,p.maxLength))
				else:
					raise SQLModelError("Edm.String of fixed length missing max: %s"%p.name)
			elif p.maxLength:
				columnDef.append(u"%sVARCHAR(%i)"%(n,p.maxLength))
			else:
				raise NotImplementedError("SQL binding for Edm.String of unbounded length: %s"%p.name)
		elif isinstance(simpleValue,edm.TimeValue):
			columnDef.append(u"TIME")
		else:
			raise NotImplementedError("SQL type for %s"%p.type)
		if (nullable is not None and not nullable) or (nullable is None and not p.nullable):
			columnDef.append(u' NOT NULL')
		if simpleValue:
			# Format the default
			columnDef.append(u' DEFAULT ')
			columnDef.append(params.AddParam(self.PrepareSQLValue(simpleValue)))
		return string.join(columnDef,'')		

	def PrepareSQLValue(self,simpleValue):
		"""Given a simple value, returns a value suitable for passing as a parameter."""
		if not simpleValue:
			return None
		elif isinstance(simpleValue,(
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
			# critical for security, do proper SQL escaping of quote
			return simpleValue.value
		elif isinstance(simpleValue,edm.DateTimeValue):
			microseconds,seconds=math.modf(simpleValue.value.time.second)
			return self.dbapi.Timestamp(
				simpleValue.value.date.century*100+simpleValue.value.date.year,
				simpleValue.value.date.month,
				simpleValue.value.date.day,
				simpleValue.value.time.hour,
				simpleValue.value.time.minute,
				int(seconds),int(1000000.0*microseconds+0.5))
		elif isinstance(simpleValue,edm.DateTimeOffsetValue):
			return simpleValue.value.GetCalendarString(basic=True,ndp=6,dp=".").ljust(27,' ')			
		elif isinstance(simpleValue,edm.GuidValue):
			return simpleValue.value.bytes
		elif isinstance(simpleValue,edm.TimeValue):
			return self.dbapi.Time(
				simpleValue.value.hour,
				simpleValue.value.minute,
				simpleValue.value.second)
		else:
			raise NotImplementedError("SQL type for "+simpleValue.__class__.__name__)

	def ReadSQLValue(self,simpleValue,newValue):
		"""Given a simple value and a newValue returned by the database, updates *simpleValue*."""
		simpleValue.SetFromValue(newValue)

	def NewFromSQLValue(self,sqlValue):
		"""Given a sqlValue returned by the database, returns a new
		SimpleValue instance."""
		return edm.EDMValue.NewSimpleValueFromValue(sqlValue)

			
class SQLiteEntityContainer(SQLEntityContainer):
	
	def __init__(self,filePath,containerDef):
		super(SQLiteEntityContainer,self).__init__(containerDef,sqlite3)
		if not isinstance(filePath,OSFilePath) and not type(filePath) in StringTypes:
			raise TypeError("SQLiteDB requires an OS file path")
		self.filePath=filePath

	def GetCollectionClass(self):
		return SQLiteEntityCollection
		
	def OpenConnection(self):
		return self.dbapi.connect(str(self.filePath))
		
	def BreakConnection(self,connection):
		connection.interrupt()

	def PrepareSQLType(self,simpleValue,params,nullable=None):
		"""SQLite custom mappings"""
		p=simpleValue.pDef
		columnDef=[]
		if isinstance(simpleValue,(edm.StringValue,edm.DecimalValue)):
			columnDef.append(u"TEXT")
		elif isinstance(simpleValue,(edm.BinaryValue,edm.GuidValue)):
			columnDef.append(u"BLOB")
		elif isinstance(simpleValue,edm.TimeValue):
			columnDef.append(u"REAL")
		else:
			return super(SQLiteEntityContainer,self).PrepareSQLType(simpleValue,params,nullable)
		if (nullable is not None and not nullable) or (nullable is None and not p.nullable):
			columnDef.append(u' NOT NULL')
		if simpleValue:
			# Format the default
			columnDef.append(u' DEFAULT ')
			columnDef.append(params.AddParam(self.PrepareSQLValue(simpleValue)))
		return string.join(columnDef,'')

	def PrepareSQLValue(self,simpleValue):
		"""Given a simple value, returns a value suitable for passing as a parameter."""
		if not simpleValue:
			return None
		elif isinstance(simpleValue,edm.BinaryValue):
			return buffer(simpleValue.value)
		elif isinstance(simpleValue,edm.DecimalValue):
			return str(simpleValue.value)
		elif isinstance(simpleValue,edm.GuidValue):
			return buffer(simpleValue.value.bytes)
		elif isinstance(simpleValue,edm.TimeValue):
			return simpleValue.value.GetTotalSeconds()
		else:
			return super(SQLiteEntityContainer,self).PrepareSQLValue(simpleValue)

	def ReadSQLValue(self,simpleValue,newValue):
		"""Handle buffer types specially."""
		if newValue is None:
			simpleValue.SetNull()
		elif type(newValue)==BufferType:
			newValue=str(newValue)
			simpleValue.SetFromValue(newValue)
		elif isinstance(simpleValue,(edm.DateTimeValue,edm.DateTimeOffsetValue)):
			# SQLite stores these as strings
			simpleValue.SetFromValue(iso.TimePoint.FromString(newValue,tDesignators="T "))
		elif isinstance(simpleValue,edm.TimeValue):
			simpleValue.value=iso.Time(totalSeconds=newValue)
		elif isinstance(simpleValue,edm.DecimalValue):
			simpleValue.value=decimal.Decimal(newValue)
		else:
			simpleValue.SetFromValue(newValue)
		
	def NewFromSQLValue(self,sqlValue):
		"""Given a sqlValue returned by the database, returns a new
		SimpleValue instance."""
		if type(sqlValue)==BufferType:
			result=edm.BinaryValue()
			result.SetFromValue(str(sqlValue))
			return result
		else:
			return super(SQLiteEntityContainer,self).NewFromSQLValue(sqlValue)


class SQLiteEntityCollection(SQLEntityCollection):
	
	def SQLExpressionConcat(self,expression,params,context):
		"""We support concatenation using ||"""
		query=[]
		query.append(self.SQLExpression(expression.operands[0],params,'*'))
		query.append(u' || ')
		query.append(self.SQLExpression(expression.operands[1],params,'*'))
		return self.SQLBracket(string.join(query,''),context,'*')

	def SQLExpressionLength(self,expression,params,context):
		query=["length("]
		query.append(self.SQLExpression(expression.operands[0],params,','))
		query.append(")")
		return string.join(query,'')	# don't bother with brackets!
		
	def SQLExpressionYear(self,expression,params,context):
		"""We support month using strftime('%Y',op[0])"""
		query=["CAST(strftime('%Y',"]
		query.append(self.SQLExpression(expression.operands[0],params,','))
		query.append(") AS INTEGER)")
		return string.join(query,'')	# don't bother with brackets!

	def SQLExpressionMonth(self,expression,params,context):
		"""We support month using strftime('%m',op[0])"""
		query=["CAST(strftime('%m',"]
		query.append(self.SQLExpression(expression.operands[0],params,','))
		query.append(") AS INTEGER)")
		return string.join(query,'')	# don't bother with brackets!
		
	def SQLExpressionDay(self,expression,params,context):
		"""We support month using strftime('%d',op[0])"""
		query=["CAST(strftime('%d',"]
		query.append(self.SQLExpression(expression.operands[0],params,','))
		query.append(") AS INTEGER)")
		return string.join(query,'')	# don't bother with brackets!

	def SQLExpressionHour(self,expression,params,context):
		"""We support month using strftime('%H',op[0])"""
		query=["CAST(strftime('%H',"]
		query.append(self.SQLExpression(expression.operands[0],params,','))
		query.append(") AS INTEGER)")
		return string.join(query,'')	# don't bother with brackets!

	def SQLExpressionMinute(self,expression,params,context):
		"""We support month using strftime('%M',op[0])"""
		query=["CAST(strftime('%M',"]
		query.append(self.SQLExpression(expression.operands[0],params,','))
		query.append(") AS INTEGER)")
		return string.join(query,'')	# don't bother with brackets!

	def SQLExpressionSecond(self,expression,params,context):
		"""We support month using strftime('%S',op[0])"""
		query=["CAST(strftime('%S',"]
		query.append(self.SQLExpression(expression.operands[0],params,','))
		query.append(") AS INTEGER)")
		return string.join(query,'')	# don't bother with brackets!

	def SQLExpressionTolower(self,expression,params,context):
		query=["lower("]
		query.append(self.SQLExpression(expression.operands[0],params,','))
		query.append(")")
		return string.join(query,'')	# don't bother with brackets!
		
	def SQLExpressionToupper(self,expression,params,context):
		query=["upper("]
		query.append(self.SQLExpression(expression.operands[0],params,','))
		query.append(")")
		return string.join(query,'')	# don't bother with brackets!
		
