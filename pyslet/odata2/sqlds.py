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
	released by :py:class:`close`."""
	
	def __init__(self,container):
		self.container=container		#: the parent container (database) for this collection
		self.tableName=self.container.mangledNames[(self.entitySet.name,)]	#: the quoted table name containing this collection
		self.qualifyNames=False			#: if True, field names in expressions are qualified with :py:attr:`tableName`
		self.dbc=self.container.AcquireConnection(SQL_TIMEOUT)		#: a connection to the database
		if self.dbc is None:
			raise DatabaseBusy("Failed to acquire connection after %is"%SQL_TIMEOUT)
		self.cursor=self.dbc.cursor()	#: a database cursor for executing queries

	def close(self):
		if self.dbc is not None:
			if self.cursor is not None:
				self.cursor.close()
			self.container.ReleaseConnection(self.dbc)
			self.dbc=None

	def FieldGenerator(self,entity,forUpdate=False):
		"""Generates tuples of (escaped) field names and simple value instances from *entity*
		
		Only selected fields are yielded.  If forUpdate is True then key
		fields are excluded."""
		if forUpdate:
			keys=entity.entitySet.keys
		for k,v in entity.DataItems():
			if entity.Selected(k) and (not forUpdate or k not in keys):
				if isinstance(v,edm.SimpleValue):
					yield self.container.mangledNames[(self.entitySet.name,k)],v
				else:
					for sourcePath,fv in self.ComplexFieldGenerator(v):
						yield self.container.mangledNames[tuple([self.entitySet.name,k]+sourcePath)],fv
	
	def ComplexFieldGenerator(self,ct):
		for k,v in ct.iteritems():
			if isinstance(v,edm.SimpleValue):
				yield [k],v
			else:
				for sourcePath,fv in self.ComplexFieldGenerator(v):
					yield [k]+sourcePath,fv
	
	SQLBinaryExpressionMethod={}
	SQLCallExpressionMethod={}
	
	def SQLExpression(self,expression,params,context="AND"):
		"""Returns expression converted into a SQL expression string.
		
		*expression* is a :py:class:`core.CommonExpression` instance.
		
		This method is basically a grand dispatcher that sends calls to
		other node-specific methods with similar signatures.  The effect
		is to traverse the entire rooted at *expression*.
		
		*params* is a :py:class:`SQLParams` object of the appropriate
		type for this database connection.
		
		*context* is a string containing the SQL operator that provides
		the context in which the expression is being converted.  This
		should be used to determine if the resulting expression must be
		bracketed or not.  See :py:meth:`SQLBracket` for a useful
		utility function to illustrate this.
		
		The result must be a string containing the parameterized
		expression with appropriate values added to the *param* object
		*in the same sequence* that they appear in the returned SQL
		expression.
		
		When creating derived classes to implement database-specific
		behaviour you should override the individual evaluation methods
		rather than this method.  All methods follow the same basic
		pattern, taking these three parameters."""
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
		"""A utility method that checks the precedence of *operator* in
		*context* and returns *query* bracketed if necessary.  An
		example is the easiest way to understand its purpose::
		
			collection.SQLBracket("Age+3","*","+")=="(Age+3)"
			collection.SQLBracket("Age*3","+","*")=="Age*3"	"""		
		if SQLOperatorPrecedence[context]>SQLOperatorPrecedence[operator]:
			return "(%s)"%query
		else:
			return query
		
	def SQLExpressionMember(self,expression,params,context):
		"""Converts the member expression, e.g., Address/City

		This implementation does not support the use of navigation
		properties but does support references to complex properties.

		It outputs the mangled name of the property, qualified by the
		table name if :py:attr:`qualifyNames` is True."""
		nameList=self.CalculateMemberFieldName(expression)
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

	def CalculateMemberFieldName(self,expression):
		"""Utility method for implementing member expressions.

		Given a member expression it returns a list of names, calling
		itself recursively to cater for deep references."""
		if isinstance(expression,core.PropertyExpression):
			return [expression.name]
		elif isinstance(expression,core.BinaryExpression) and expression.operator==core.Operator.member:
			return self.CalculateMemberFieldName(expression.operands[0])+self.CalculateMemberFieldName(expression.operands[1])
		else:
			raise core.EvaluationError("Unexpected use of member expression")
			
	def SQLExpressionCast(self,expression,params,context):
		"""Converts the cast expression: no default implementation"""
		raise NotImplementedError

	def SQLExpressionGenericBinary(self,expression,params,context,operator):
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
	passed."""	
	def __init__(self,entitySet,container):
		core.EntityCollection.__init__(self,entitySet)
		SQLCollectionMixin.__init__(self,container)

	def WhereClause(self,entity,params,useFilter=True,nullCols=()):
		"""A convenience method for creating a WHERE clause, returning a
		parameterized SQL expression.
		
		*entity*
			The entity we want to constrain by so its keys are added to
			the where clause.
		
		*params*
			The :py:class:`SQLParams` object that the values are added
			to *in the sequence* they appear in the parameterized result.
		
		*useFilter*
			If True will cause the current filter expression to be added
			as a constraint.
		
		*nullCols*
			An iterable list of mangled column names that must be NULL"""		
		where=[]
		kd=entity.KeyDict()
		for k,v in kd.items():
			where.append('%s=%s'%(self.container.mangledNames[(self.entitySet.name,k)],params.AddParam(self.container.PrepareSQLValue(v))))
		if self.filter is not None and useFilter:
			where.append('('+self.SQLExpression(self.filter,params)+')')
		for nullCol in nullCols:
			where.append('%s IS NULL'%nullCol)
		return ' WHERE '+string.join(where,' AND ')
		
	def InsertEntity(self,entity,fromEnd=None,fkValues=None):
		if entity.exists:
			raise edm.EntityExists(str(entity.GetLocation()))
		# This is harder than it looks, fkValues is a list of column
		# name and value tuples to match those returned by the
		# FieldGenerator we use for the regular properties.  This value
		# augments *fromEnd* when we are being inserted into a reverse
		# key collection (i.e., we're the target and we store the
		# foreign key).
		#
		# We must also go through each bound navigation property of our
		# own and add in the foreign keys for forward links.
		if fkValues is None:
			fkValues=[]
		fkMapping=self.container.fkTable[self.entitySet.name]
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
			# Finally, we have a target entity, add the foreign key to fkValues
			for keyName in targetSet.keys:
				fkValues.append((self.container.mangledNames[(self.entitySet.name,associationSetName,keyName)],targetEntity[keyName]))
			navigationDone.add(navName)
		entity.SetConcurrencyTokens()
		query=['INSERT INTO ',self.tableName,' (']
		columnNames,values=zip(*(list(self.FieldGenerator(entity))+fkValues))
		query.append(string.join(columnNames,", "))
		query.append(') VALUES (')
		params=self.container.ParamsClass()
		query.append(string.join(map(lambda x:params.AddParam(self.container.PrepareSQLValue(x)),values),", "))
		query.append(');')
		query=string.join(query,'')
		try:
			logging.info(query+unicode(params.params))
			self.cursor.execute(query,params.params)
			self.dbc.commit()
			entity.exists=True
		except self.container.dbapi.IntegrityError:
			# we might need to distinguish between a failure due to fkValues or a missing key
			raise KeyError(str(entity.GetLocation()))
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
		# Rather than calling the deferred value's UpdateBindings method
		# we take some short cuts to improve efficiency and to take care
		# of the awkward cases. If the target entity already exists we
		# can just insert a link but if we are doing a deep insert we
		# need to work harder.  We've already taken care of cases where
		# we own the foreign key so now we only have two cases left, (i)
		# the target table has the key or (ii) it is in an auxiliary
		# table.  Case (i) is the tricky one as it involves passing the
		# foreign keys to be inserted as the new entity is created (they
		# may be required) with a call to this method on the target
		# entity set.  Case (ii) is simpler, though if the relationship
		# is 1-1 we'll briefly be in violation of the model (but not the
		# database schema) and should really insert the entity and the
		# link in a single transaction (TODO)
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
					else:
						if linkEnd.otherEnd in targetFKMapping:
							# target table has a foreign key
							targetFKValues=[]
							for keyName in self.entitySet.keys:
								targetFKValues.append((self.container.mangledNames[(targetSet.name,associationSetName,keyName)],entity[keyName]))
							targetCollection.InsertEntity(binding,linkEnd.otherEnd,targetFKValues)
						else:
							# foreign keys are in an auxiliary table
							targetCollection.InsertEntity(binding,linkEnd.otherEnd)
							navCollection.InsertLink(binding)
					dv.bindings=dv.bindings[1:]
		
	def __len__(self):
		query=["SELECT COUNT(*) FROM %s"%self.tableName]
		params=self.container.ParamsClass()
		if self.filter is not None:
			query.append(' WHERE ')
			query.append(self.SQLExpression(self.filter,params))
		query=string.join(query,'')
		try:
			logging.info(query+unicode(params.params))
			self.cursor.execute(query,params.params)
			# get the result
			return self.cursor.fetchone()[0]
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
							
	def entityGenerator(self):
		entity=self.NewEntity()
		query=["SELECT "]
		params=self.container.ParamsClass()
		columnNames,values=zip(*list(self.FieldGenerator(entity)))
		# now add the order by clauses
		orderNames=[]
		oi=0
		match=set()
		for name in columnNames:
			match.add(name)
		if self.orderby is not None:
			columnNames=list(columnNames)
			for expression,direction in self.orderby:
				while True:
					oi=oi+1
					oName="o%i"%oi
					if oName in match:
						continue
					else:
						orderNames.append((oName,direction))
						break
				sqlExpression=self.SQLExpression(expression,params)
				columnNames.append("%s AS %s"%(sqlExpression,oName))
		query.append(string.join(columnNames,", "))
		query.append(' FROM ')
		query.append(self.tableName)
		if self.filter is not None:
			query.append(' WHERE ')
			query.append(self.SQLExpression(self.filter,params))
		if self.orderby is not None:
			query.append(" ORDER BY ")
			orderby=[]
			for expression,direction in orderNames:
				orderby.append("%s %s"%(expression,"DESC" if direction <0 else "ASC"))
			query.append(string.join(orderby,u", "))
		query=string.join(query,'')
		cursor=None
		try:
			cursor=self.dbc.cursor()
			logging.info(query+unicode(params.params))
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
		
	def SetPage(self,top,skip=0,skiptoken=None):
		"""Sets the page parameters.
		
		The skip and top query options are integers which determine the
		number of entities returned (top) and the number of entities
		skipped (skip and skiptoken) by iterpage.
		
		The default implementation treats the skip token exactly the
		same as the skip value itself except that we obscure it slightly
		by treating it as a hex value."""
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
		orderNames=[]
		self.nextSkiptoken=None
		oi=0
		match=set()
		for name in columnNames:
			match.add(name)
		if self.orderby is not None:
			for expression,direction in self.orderby:
				while True:
					oi=oi+1
					oName="o%i"%oi
					if oName in match:
						continue
					else:
						orderNames.append((oName,direction))
						break
				sqlExpression=self.SQLExpression(expression,params)
				columnNames.append("%s AS %s"%(sqlExpression,oName))
		# add the keys too
		for key in self.entitySet.keys:
			while True:
				oi=oi+1
				oName="o%i"%oi
				if oName in match:
					continue
				else:
					orderNames.append((oName,1))
					break
			columnNames.append("%s AS %s"%(self.container.mangledNames[(self.entitySet.name,key)],oName))			
		query.append(string.join(columnNames,", "))
		query.append(' FROM ')
		query.append(self.tableName)
		filter=[]
		if self.filter:
			filter.append(self.SQLExpression(self.filter,params))
		if self.skiptoken:
			# work backwards through the expression
			expression=[]
			i=0
			ket=0
			while True:
				oName,dir=orderNames[i]
				v=self.skiptoken[i]
				op=">" if dir>0 else "<"
				expression.append("(%s %s %s"%(oName,op,params.AddParam(self.container.PrepareSQLValue(v))))
				ket+=1
				i=i+1
				if i<len(orderNames):
					# more to come
					expression.append(" OR (%s = %s AND "%(oName,params.AddParam(self.container.PrepareSQLValue(v))))
					ket+=1
					continue
				else:
					expression.append(u")"*ket)
					break
			filter.append(string.join(expression,''))
		if filter:
			query.append(' WHERE ')
			query.append(string.join(filter,' AND '))
		if orderNames:
			query.append(" ORDER BY ")
			orderby=[]
			for expression,direction in orderNames:
				orderby.append("%s %s"%(expression,"DESC" if direction <0 else "ASC"))
			query.append(string.join(orderby,u", "))
		query=string.join(query,'')
		cursor=None
		try:
			skip=self.skip
			top=self.top
			topmax=self.topmax
			cursor=self.dbc.cursor()
			logging.info(query+unicode(params.params))
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
						orderValues=rowValues[-len(orderNames):]
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
		
	def __getitem__(self,key):
		entity=self.NewEntity()
		entity.SetKey(key)
		params=self.container.ParamsClass()
		query=["SELECT "]
		columnNames,values=zip(*list(self.FieldGenerator(entity)))
		query.append(string.join(columnNames,", "))
		query.append(' FROM ')
		query.append(self.tableName)
		# WHERE
		query.append(self.WhereClause(entity,params))
		query=string.join(query,'')
		try:
			logging.info(query+unicode(params.params))
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

	def UpdateEntity(self,entity):
		if not entity.exists:
			raise edm.NonExistentEntity("Attempt to update non existent entity: "+str(entity.GetLocation()))
			fkValues=[]
		fkValues=[]
		fkMapping=self.container.fkTable[self.entitySet.name]
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
		try:
			logging.info(query+unicode(params.params))
			self.cursor.execute(query,params.params)
			if self.cursor.rowcount==0:
				# no rows matched this constraint, probably a concurrency failure
				if concurrencyCheck:
					raise edm.ConcurrencyError
				else:
					raise KeyError("Entity %s does not exist"%str(entity.GetLocation()))					
			self.dbc.commit()
		except self.container.dbapi.IntegrityError:
			# we might need to distinguish between a failure due to fkValues or a missing key
			raise KeyError(str(entity.GetLocation()))
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
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
						else:
							navCollection.Replace(binding)
					else:
						if linkEnd.otherEnd in targetFKMapping:
							# target table has a foreign key
							targetFKValues=[]
							for keyName in self.entitySet.keys:
								targetFKValues.append((self.container.mangledNames[(targetSet.name,associationSetName,keyName)],entity[keyName]))
							if not dv.isCollection:
								navCollection.clear()
							targetCollection.InsertEntity(binding,linkEnd.otherEnd,targetFKValues)
						else:
							# foreign keys are in an auxiliary table
							targetCollection.InsertEntity(binding,linkEnd.otherEnd)
							if dv.isCollection:
								navCollection.InsertLink(binding)
							else:
								navCollection.Replace(binding)
					dv.bindings=dv.bindings[1:]
	
	def UpdateLink(self,entity,linkEnd,targetEntity,noReplace=False):
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
		query.append(self.WhereClause(entity,params,False,nullCols))
		query=string.join(query,'')
		try:
			logging.info(query+unicode(params.params))
			self.cursor.execute(query,params.params)
			if self.cursor.rowcount==0:
				if nullCols:
					# this could be a constraint failure, rather than a key failure
					if entity.Key() in self:
						raise edm.NavigationConstraintError("Entity %s is already linked through association %s"%(entity.GetLocation(),associationSetName))
					else:
						# no rows matched this constraint must be a key failure
						raise KeyError("Entity %s does not exist"%str(entity.GetLocation()))
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
	
	def DeleteEntity(self,entity,fromEnd=None):	
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
								links.DeleteLink(targetEntity)
								cascade.DeleteEntity(targetEntity,linkEnd.otherEnd)
					else:
						raise edm.NavigationConstraintError("Can't cascade delete from an entity in %s as the association set %s is not bound to a navigation property"%(self.entitySet.name,associationSetName))
				else:
					# we are not required, so just drop the links
					if navName is not None:
						with entity[navName].OpenCollection() as links:
							links.clear()
					# otherwise annoying, we need to do something special
					elif associationSetName in self.container.auxTable:
						# foreign keys are in an association table, hardest case as navigation may be unbound
						SQLAssociationCollection.ClearLinks(self.container,linkEnd,entity,self.cursor)
					else:
						# foreign keys are at the other end of the link, we have a method for that...
						targetEntitySet=linkEnd.otherEnd.entitySet
						with targetEntitySet.OpenCollection() as keyCollection:
							keyCollection.ClearLinks(linkEnd.otherEnd,entity)
		params=self.container.ParamsClass()
		query=["DELETE FROM "]
		params=self.container.ParamsClass()
		query.append(self.tableName)
		# WHERE - ignore the filter
		query.append(self.WhereClause(entity,params,False))
		query=string.join(query,'')
		try:
			logging.info(query+unicode(params.params))
			self.cursor.execute(query,params.params)
			rowcount=self.cursor.rowcount
			if rowcount==0:
				raise KeyError
			elif rowcount>1:
				# whoops, that was unexpected
				raise SQLError("Integrity check failure, non-unique key: %s"%repr(key))
			self.dbc.commit()
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))

	def DeleteLink(self,entity,linkEnd,targetEntity):
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
			logging.info(query+unicode(params.params))
			self.cursor.execute(query,params.params)
			if self.cursor.rowcount==0:
				# no rows matched this constraint, entity either doesn't exist or wasn't linked to the target
				raise KeyError("Entity %s does not exist or is not linked to %s"%str(entity.GetLocation(),targetEntity.GetLocation))					
			self.dbc.commit()
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
		
	def ClearLinks(self,linkEnd,targetEntity):
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
			logging.info(query+unicode(params.params))
			self.cursor.execute(query,params.params)
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
		query,params=self.CreateTableQuery()
		try:
			logging.info(query+unicode(params.params))
			self.cursor.execute(query,params.params)
			self.dbc.commit()
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
				

class SQLForeignKeyCollection(SQLCollectionMixin,core.NavigationEntityCollection):
	
	def __init__(self,name,fromEntity,toEntitySet,container,associationSetName):
		core.NavigationEntityCollection.__init__(self,name,fromEntity,toEntitySet)
		SQLCollectionMixin.__init__(self,container)
		self.qualifyNames=True
		# The relation is actually stored in the source entity set
		# which is the entity set of the *fromEntity*, not the base entity set
		self.keyCollection=self.fromEntity.entitySet.OpenCollection()
		self.sourceName=self.container.mangledNames[(self.fromEntity.entitySet.name,self.name)]
		self.associationSetName=associationSetName
	
	def JoinClause(self):
		join=[]
		# we don't need to look up the details of the join again, as self.entitySet must be the target
		for keyName in self.entitySet.keys:
			join.append('%s.%s=%s.%s'%(
				self.tableName,
				self.container.mangledNames[(self.entitySet.name,keyName)],
				self.sourceName,
				self.container.mangledNames[(self.fromEntity.entitySet.name,self.associationSetName,keyName)]))
		return ' INNER JOIN %s AS %s ON '%(self.fromEntity.entitySet.name,self.sourceName)+string.join(join,', ')
	
	def WhereClause(self,params):
		where=[]
		for k,v in self.fromEntity.KeyDict().items():
			where.append(u"%s.%s=%s"%(self.sourceName,
				self.container.mangledNames[(self.fromEntity.entitySet.name,k)],
				params.AddParam(self.container.PrepareSQLValue(v))))
		if self.filter is not None:
			where.append("(%s)"%self.SQLExpression(self.filter,params))		
		return ' WHERE '+string.join(where,' AND ')
	
	def OrderByClause(self,params):
		orderby=[]
		for expression,direction in self.orderby:
			orderby.append("%s %s"%(self.SQLExpression(expression,params),"DESC" if direction <0 else "ASC"))
		return ' ORDER BY '+string.join(orderby,u", ")
			
	def __len__(self):
		query=["SELECT COUNT(*) FROM %s"%self.tableName]
		params=self.container.ParamsClass()
		query.append(self.JoinClause())
		query.append(self.WhereClause(params))
		query=string.join(query,'')
		try:
			logging.info(query+unicode(params.params))
			self.cursor.execute(query,params.params)
			# get the result
			return self.cursor.fetchone()[0]
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
		
	def entityGenerator(self):
		entity=self.NewEntity()
		query=["SELECT "]
		params=self.container.ParamsClass()
		columnNames,values=zip(*list(self.FieldGenerator(entity)))
		# qualify with the table name
		query.append(string.join(map(lambda x:self.tableName+"."+x,columnNames),", "))
		query.append(' FROM ')
		query.append(self.tableName)
		query.append(self.JoinClause())
		query.append(self.WhereClause(params))
		if self.orderby is not None:
			query.append(self.OrderByClause(params))
		query=string.join(query,'')
		cursor=None
		try:
			cursor=self.dbc.cursor()
			logging.info(query+unicode(params.params))
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


class SQLReverseKeyCollection(SQLCollectionMixin,core.NavigationEntityCollection):
	
	def __init__(self,name,fromEntity,toEntitySet,container,associationSetName):
		core.NavigationEntityCollection.__init__(self,name,fromEntity,toEntitySet)
		SQLCollectionMixin.__init__(self,container)
		# The relation is actually stored in the *toEntitySet*
		# which is the same entity set that our results will be drawn
		# from, which makes it easier as we don't need a join
		self.keyCollection=self.entitySet.OpenCollection()
		self.associationSetName=associationSetName

	def WhereClause(self,params):
		where=[]
		for k,v in self.fromEntity.KeyDict().items():
			where.append(u"%s=%s"%(
				self.container.mangledNames[(self.entitySet.name,self.associationSetName,k)],
				params.AddParam(self.container.PrepareSQLValue(v))))
		if self.filter is not None:
			where.append("(%s)"%self.SQLExpression(self.filter,params))		
		return ' WHERE '+string.join(where,' AND ')
	
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
		
	def __len__(self):
		query=["SELECT COUNT(*) FROM %s"%self.tableName]
		params=self.container.ParamsClass()
		query.append(self.WhereClause(params))
		query=string.join(query,'')
		try:
			logging.info(query+unicode(params.params))
			self.cursor.execute(query,params.params)
			# get the result
			return self.cursor.fetchone()[0]
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
		
	def entityGenerator(self):
		entity=self.NewEntity()
		query=["SELECT "]
		params=self.container.ParamsClass()
		columnNames,values=zip(*list(self.FieldGenerator(entity)))
		# qualify with the table name
		query.append(string.join(columnNames,", "))
		query.append(' FROM ')
		query.append(self.tableName)
		query.append(self.WhereClause(params))
		if self.orderby is not None:
			query.append(self.OrderByClause(params))
		query=string.join(query,'')
		cursor=None
		try:
			cursor=self.dbc.cursor()
			logging.info(query+unicode(params.params))
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
		
	def DeleteLink(self,entity):
		"""Called during cascaded deletes to force-remove a link prior
		to the deletion of the entity itself.  As the foreign key for
		this association is in the entity's record itself we don't have
		to do anything."""
		pass
		
	def clear(self):
		self.keyCollection.ClearLinks(self.fromEnd.otherEnd,self.fromEntity)
		
	def close(self):
		self.keyCollection.close()
		super(SQLReverseKeyCollection,self).close()


class SQLAssociationCollection(SQLCollectionMixin,core.NavigationEntityCollection):
	"""The implementation is similar to SQLForeignKeyCollection except
	that we use the association set's name as the table name that
	contains the keys and combine the name of the entity set with the
	navigation property to use as a prefix for the field path.
	
	The code to update links is different because we need to distinguish
	an insert from an update."""
	
	def __init__(self,name,fromEntity,toEntitySet,container,associationSetName):
		core.NavigationEntityCollection.__init__(self,name,fromEntity,toEntitySet)
		SQLCollectionMixin.__init__(self,container)
		# The relation is actually stored in an extra table so we will
		# need a join for all operations.
		self.qualifyNames=True
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
	
	def WhereClause(self,params,useFilter=True,targetEntity=None):
		where=[]
		for k,v in self.fromEntity.KeyDict().items():
			where.append(u"%s.%s=%s"%(self.associationTableName,
				self.container.mangledNames[(self.associationSetName,self.fromEntity.entitySet.name,self.fromNavName,k)],
				params.AddParam(self.container.PrepareSQLValue(v))))
		if targetEntity is not None:
			for k,v in targetEntity.KeyDict().items():
				where.append(u"%s.%s=%s"%(self.associationTableName,
					self.container.mangledNames[(self.associationSetName,targetEntity.entitySet.name,self.toNavName,k)],
					params.AddParam(self.container.PrepareSQLValue(v))))
		if useFilter and self.filter is not None:
			where.append("(%s)"%self.SQLExpression(self.filter,params))		
		return ' WHERE '+string.join(where,' AND ')
	
	def OrderByClause(self,params):
		orderby=[]
		for expression,direction in self.orderby:
			orderby.append("%s %s"%(self.SQLExpression(expression,params),"DESC" if direction <0 else "ASC"))
		return ' ORDER BY '+string.join(orderby,u", ")
			
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
			logging.info(query+unicode(params.params))
			self.cursor.execute(query,params.params)
			self.dbc.commit()
		except self.container.dbapi.IntegrityError:
			raise edm.NavigationConstraintError("Model integrity error when linking %s and %s"%(str(self.fromEntity.GetLocation()),str(entity.GetLocation())))
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
	
	def __len__(self):
		query=["SELECT COUNT(*) FROM %s"%self.tableName]
		params=self.container.ParamsClass()
		query.append(self.JoinClause())
		query.append(self.WhereClause(params))
		query=string.join(query,'')
		try:
			logging.info(query+unicode(params.params))
			self.cursor.execute(query,params.params)
			# get the result
			return self.cursor.fetchone()[0]
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
		
	def entityGenerator(self):
		entity=self.NewEntity()
		query=["SELECT "]
		params=self.container.ParamsClass()
		columnNames,values=zip(*list(self.FieldGenerator(entity)))
		# qualify with the table name
		query.append(string.join(map(lambda x:self.tableName+"."+x,columnNames),", "))
		query.append(' FROM ')
		query.append(self.tableName)
		query.append(self.JoinClause())
		query.append(self.WhereClause(params))
		if self.orderby is not None:
			query.append(self.OrderByClause(params))
		query=string.join(query,'')
		cursor=None
		try:
			cursor=self.dbc.cursor()
			logging.info(query+unicode(params.params))
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

	def DeleteLink(self,entity):
		"""Called during cascaded deletes to force-remove a link prior
		to the deletion of the entity itself"""
		query=['DELETE FROM ',self.associationTableName]
		params=self.container.ParamsClass()
		# we suppress the filter check on the where clause
		query.append(self.WhereClause(params,False,entity))
		query=string.join(query,'')
		try:
			logging.info(query+unicode(params.params))
			self.cursor.execute(query,params.params)
			if self.cursor.rowcount==0:
				# no rows matched this constraint must be a key failure at one of the two ends
				raise KeyError("One of the entities %s or %s no longer exists"%(str(self.fromEntity.GetLocation()),str(entity.GetLocation())))
			self.dbc.commit()
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))

	@classmethod
	def ClearLinks(cls,container,fromEnd,fromEntity,cursor):
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
			logging.info(query+unicode(params.params))
			cursor.execute(query,params.params)
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
			logging.info(query+unicode(params.params))
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
		if type(newValue)==BufferType:
			newValue=str(newValue)
			simpleValue.SetFromValue(newValue)
		elif isinstance(simpleValue,(edm.DateTimeValue,edm.DateTimeOffsetValue)):
			# SQLite stores these as strings!
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
		
