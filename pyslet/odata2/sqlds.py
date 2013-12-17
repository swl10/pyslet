#! /usr/bin/env python
"""This module implements the Open Data Protocol specification defined by Microsoft."""


import sqlite3, hashlib, StringIO, time, string, sys, threading
from types import *

from pyslet.vfs import OSFilePath
import pyslet.iso8601 as iso
import csdl as edm
import core, metadata


SQL_TIMEOUT=90	#: the standard timeout, in seconds

class SQLError(Exception):
	"""Base class for all module exceptions."""
	pass


class DatabaseBusy(SQLError):
	"""Raised when a database connection times out."""
	pass

SQLOperatorPrecedence={
	"""Look-up table for SQL operator precedence calculations."""
	'OR':1,
	'AND':2,
	'NOT':3,
	'=':4,
	'<>':4,
	'<=':4,
	'>=':4,
	'LIKE':4,
	'+':5,
	'-':5,
	'*':6,
	'/':6
	}


class UnparameterizedLiteral(core.LiteralExpression):
	"""Class used as a flag that this literal is safe and does not be parameterized.
	
	This prevents things like::
	
		"name" LIKE ?+?+? ; params=[u'%',u"Smith",u'%']"""
	pass


class SQLCollectionMixin(object):
	
	def __init__(self,container):
		self.container=container		#: the parent container (database) for this collection
		self.tableName=self.container.tableNames[self.entitySet.name]	#: the quoted table name containing this collection
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
			keys=entity.KeyDict()
		for k,v in entity.DataItems():
			if entity.Selected(k) and (not forUpdate or k not in keys):
				if isinstance(v,edm.SimpleValue):
					yield self.container.fieldNames[(self.tableName,(k,))],v
				else:
					for sourcePath,fv in self.ComplexFieldGenerator(v):
						yield self.container.fieldNames[(self.tableName,tuple([k]+sourcePath))],fv
	
	def ComplexFieldGenerator(self,ct):
		"""Generates tuples of source path (as list) and simple value instances."""
		for k,v in ct.iteritems():
			if isinstance(v,edm.SimpleValue):
				yield [k],v
			else:
				for sourcePath,fv in self.ComplexFieldGenerator(v):
					yield [k]+sourcePath,fv
	
	SQLBinaryExpressionMethod={}
	SQLCallExpressionMethod={}
	
	def SQLExpression(self,expression,params,context="AND"):
		"""Returns a SQL-formatted filter string adding paramaters to params.
		
		Expression is a :py:class:`edm.CommonExpression` instance.  This
		method is basically a grand dispatcher that sends calls to other
		methods in the collection."""
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
						fieldName=self.container.fieldNames[(self.tableName,(expression.name,))]
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
		if SQLOperatorPrecedence[context]>SQLOperatorPrecedence[operator]:
			return "(%s)"%query
		else:
			return query
		
	def SQLExpressionMember(self,expression,params,context):
		"""We need to deep dive when evaluating this type of expression."""
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
			raise core.EvaluationError("Property %s does not reference a primite type"%string.join(nameList,'/'))
		fieldName=self.container.fieldNames[(self.tableName,tuple(nameList))]
		if self.qualifyNames:
			return "%s.%s"%(self.tableName,fieldName)
		else:
			return fieldName

	def CalculateMemberFieldName(self,expression):
		"""Returns a list of names represented by this expression"""
		if isinstance(expression,core.PropertyExpression):
			return [expression.name]
		elif isinstance(expression,core.BinaryExpression) and expression.operator==core.Operator.member:
			return self.CalculateMemberFieldName(expression.operands[0])+self.CalculateMemberFieldName(expression.operands[1])
		else:
			raise core.EvaluationError("Unexpected use of member expression")
			
	def SQLExpressionCast(self,expression,params,context):
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
		return self.SQLExpressionGenericBinary(expression,params,context,'*')

	def SQLExpressionDiv(self,expression,params,context):
		return self.SQLExpressionGenericBinary(expression,params,context,'/')

	def SQLExpressionMod(self,expression,params,context):
		raise NotImplementedError

	def SQLExpressionAdd(self,expression,params,context):
		return self.SQLExpressionGenericBinary(expression,params,context,'+')

	def SQLExpressionSub(self,expression,params,context):
		return self.SQLExpressionGenericBinary(expression,params,context,'-')
		
	def SQLExpressionLt(self,expression,params,context):
		return self.SQLExpressionGenericBinary(expression,params,context,'<')

	def SQLExpressionGt(self,expression,params,context):
		return self.SQLExpressionGenericBinary(expression,params,context,'>')

	def SQLExpressionLe(self,expression,params,context):
		return self.SQLExpressionGenericBinary(expression,params,context,'<=')

	def SQLExpressionGe(self,expression,params,context):
		return self.SQLExpressionGenericBinary(expression,params,context,'>=')

	def SQLExpressionIsOf(self,expression,params,context):
		raise NotImplementedError

	def SQLExpressionEq(self,expression,params,context):
		return self.SQLExpressionGenericBinary(expression,params,context,'=')

	def SQLExpressionNe(self,expression,params,context):
		return self.SQLExpressionGenericBinary(expression,params,context,'<>')

	def SQLExpressionAnd(self,expression,params,context):
		return self.SQLExpressionGenericBinary(expression,params,context,'AND')

	def SQLExpressionOr(self,expression,params,context):
		return self.SQLExpressionGenericBinary(expression,params,context,'OR')

	def SQLExpressionEndswith(self,expression,params,context):
		"""The basic idea is to do op[0] LIKE '%'+op[1]
		
		To do this we need to invoke the concatenation operator as per
		Concat"""
		percent=edm.SimpleValue.NewSimpleValue(edm.SimpleType.String)
		percent.SetFromPyValue(u"'%'")
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
		raise NotImplementedError
		
	def SQLExpressionReplace(self,expression,params,context):
		raise NotImplementedError
		
	def SQLExpressionStartswith(self,expression,params,context):
		"""The basic idea is to do op[0] LIKE '%'+op[1]
		
		To do this we need to invoke the concatenation operator as per
		Concat"""
		percent=edm.SimpleValue.NewSimpleValue(edm.SimpleType.String)
		percent.SetFromPyValue(u"'%'")
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
		raise NotImplementedError
		
	def SQLExpressionToupper(self,expression,params,context):
		raise NotImplementedError
		
	def SQLExpressionTrim(self,expression,params,context):
		raise NotImplementedError
		
	def SQLExpressionSubstring(self,expression,params,context):
		raise NotImplementedError
		
	def SQLExpressionSubstringof(self,expression,params,context):
		"""The basic idea is to do op[0] LIKE '%'+op[1]+'%'
		
		To do this we need to invoke the concatenation operator,
		which is a bit clumsy but more robust than just assuming
		that + or ||, or perhaps CONCAT( ).... will actually work."""
		percent=edm.SimpleValue.NewSimpleValue(edm.SimpleType.String)
		percent.SetFromPyValue(u"'%'")
		percent=UnparameterizedLiteral(percent)
		rconcat=core.CallExpression(core.Method.concat)
		rconcat.operands.append(expression.operands[1])
		rconcat.operands.append(percent)
		lconcat=core.CallExpression(core.Method.concat)
		lconcat.operands.append(percent)
		lconcat.operands.append(rconcat)
		query=[]
		query.append(self.SQLExpression(expression.operands[0],params,'LIKE'))
		query.append(" LIKE ")
		query.append(self.SQLExpression(lconcat,params,'LIKE'))
		return self.SQLBracket(string.join(query,''),context,'LIKE')
				
	def SQLExpressionConcat(self,expression,params,context):
		raise NotImplementedError
		
	def SQLExpressionLength(self,expression,params,context):
		raise NotImplementedError
		
	def SQLExpressionYear(self,expression,params,context):
		raise NotImplementedError
		
	def SQLExpressionMonth(self,expression,params,context):
		raise NotImplementedError
		
	def SQLExpressionDay(self,expression,params,context):
		raise NotImplementedError
		
	def SQLExpressionHour(self,expression,params,context):
		raise NotImplementedError
		
	def SQLExpressionMinute(self,expression,params,context):
		raise NotImplementedError
		
	def SQLExpressionSecond(self,expression,params,context):
		raise NotImplementedError
		
	def SQLExpressionRound(self,expression,params,context):
		raise NotImplementedError
		
	def SQLExpressionFloor(self,expression,params,context):
		raise NotImplementedError
		
	def SQLExpressionCeiling(self,expression,params,context):
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
	
	def __init__(self,entitySet,container):
		core.EntityCollection.__init__(self,entitySet)
		SQLCollectionMixin.__init__(self,container)

	def InsertEntity(self,entity):
		if entity.exists:
			raise edm.EntityExists(str(entity.GetLocation()))
		entity.SetConcurrencyTokens()
		query=['INSERT INTO ',self.tableName,' (']
		columnNames,values=zip(*list(self.FieldGenerator(entity)))
		query.append(string.join(columnNames,", "))
		query.append(') VALUES (')
		params=self.container.ParamsClass()
		query.append(string.join(map(lambda x:params.AddParam(self.container.PrepareSQLValue(x)),values),", "))
		query.append(');')
		query=string.join(query,'')
		try:
			#	print query, params.params
			self.cursor.execute(query,params.params)
			self.dbc.commit()
			entity.exists=True
		except self.container.dbapi.IntegrityError:
			raise KeyError(str(entity.GetLocation()))
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
	
	def entityGenerator(self):
		entity=self.NewEntity()
		query=["SELECT "]
		params=self.container.ParamsClass()
		columnNames,values=zip(*list(self.FieldGenerator(entity)))
		query.append(string.join(columnNames,", "))
		query.append(' FROM ')
		query.append(self.tableName)
		if self.filter is not None:
			query.append(' WHERE ')
			query.append(self.SQLExpression(self.filter,params))
		if self.orderby is not None:
			query.append(" ORDER BY ")
			orderby=[]
			for expression,direction in self.orderby:
				orderby.append("%s %s"%(self.SQLExpression(expression,params),"DESC" if direction <0 else "ASC"))
			query.append(string.join(orderby,u", "))
		query=string.join(query,'')
		try:
			#	print query, params.params
			self.cursor.execute(query,params.params)
			while True:
				row=self.cursor.fetchone()
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
		
	def itervalues(self):
		return self.ExpandEntities(
			self.entityGenerator())
		
	def WhereClause(self,entity,params,useFilter=True):
		where=[]
		kd=entity.KeyDict()
		for k,v in kd.items():
			where.append('%s=%s'%(self.container.fieldNames[(self.tableName,(k,))],params.AddParam(self.container.PrepareSQLValue(v))))
		if self.filter is not None and useFilter:
			where.append('('+self.SQLExpression(self.filter,params)+')')		
		return ' WHERE '+string.join(where,' AND ')
		
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
			#	print query, params.params
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
			return entity
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))

	def UpdateEntity(self,entity):
		if not entity.exists:
			raise edm.NonExistentEntity("Attempt to update non existent entity: "+str(entity.GetLocation()))
		# grab a list of sql-name,sql-value pairs representing the key constraint
		concurrencyCheck=False
		constraints=[]
		for k,v in entity.KeyDict().items():
			constraints.append((self.container.fieldNames[(self.tableName,(k,))],
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
		for cName,v in cvList:
			updates.append('%s=%s'%(cName,params.AddParam(self.container.PrepareSQLValue(v))))
		query.append(string.join(updates,', '))
		query.append(' WHERE ')
		where=[]
		for cName,cValue in constraints:
			where.append('%s=%s'%(cName,params.AddParam(cValue)))
		query.append(string.join(where,' AND '))
		query=string.join(query,'')
		try:
			#	print query, params.params
			self.cursor.execute(query,params.params)
			if self.cursor.rowcount==0:
				# no rows matched this constraint, probably a concurrency failure
				if concurrencyCheck:
					raise edm.ConcurrencyError
				else:
					raise KeyError("Entity %s does not exist"%str(entity.GetLocation()))					
			self.dbc.commit()
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
	
	def UpdateLink(self,entity,associationName,targetEntity):
		if not entity.exists:
			raise edm.NonExistentEntity("Attempt to update non-existent entity: "+str(entity.GetLocation()))
		query=['UPDATE ',self.tableName,' SET ']
		params=self.container.ParamsClass()
		updates=[]
		targetSet,nullable,unique=self.container.fkTable[self.entitySet.name][associationName]
		fkNames=[]
		for keyName in targetSet.KeyKeys():
			v=targetEntity[keyName]
			cName=self.container.fieldNames[(self.tableName,(associationName,keyName))]
			updates.append('%s=%s'%(cName,params.AddParam(self.container.PrepareSQLValue(v))))
		query.append(string.join(updates,', '))
		# we don't do concurrency checks on links, and we suppress the filter check too
		query.append(self.WhereClause(entity,params,False))
		query=string.join(query,'')
		try:
			#	print query, params.params
			self.cursor.execute(query,params.params)
			if self.cursor.rowcount==0:
				# no rows matched this constraint must be a key failure
				raise KeyError("Entity %s does not exist"%str(entity.GetLocation()))					
			self.dbc.commit()			
		except self.container.dbapi.IntegrityError:
			raise KeyError("Linked entity %s does not exist"%str(targetEntity.GetLocation()))
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
		
	def __delitem__(self,key):
		entity=self.NewEntity()
		entity.SetKey(key)
		params=self.container.ParamsClass()
		query=["DELETE FROM "]
		params=self.container.ParamsClass()
		query.append(self.tableName)
		# WHERE - ignore the filter
		query.append(self.WhereClause(entity,params,False))
		query=string.join(query,'')
		try:
			#	print query, params.params
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

	def __len__(self):
		query=["SELECT COUNT(*) FROM %s"%self.tableName]
		params=self.container.ParamsClass()
		if self.filter is not None:
			query.append(' WHERE ')
			query.append(self.SQLExpression(self.filter,params))
		query=string.join(query,'')
		try:
			#	print query, params.params
			self.cursor.execute(query,params.params)
			# get the result
			return self.cursor.fetchone()[0]
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
							
	def CreateTableQuery(self,keyDefs=True):
		"""Returns a SQL statement and params object suitable for creating the table."""
		entity=self.NewEntity()
		query=['CREATE TABLE ',self.tableName,' (']
		params=self.container.ParamsClass()
		cols=[]
		for c,v in self.FieldGenerator(entity):
			cols.append("%s %s"%(c,self.container.PrepareSQLType(v,params)))
		if keyDefs:
			keys=entity.KeyDict()
			constraints=[]
			constraints.append(u'PRIMARY KEY (%s)'%string.join(map(lambda x:self.container.fieldNames[(self.tableName,(x,))],keys.keys()),u', '))
			# Now generate the foreign keys
			fkMapping=self.container.fkTable[self.entitySet.name]
			for associationName in fkMapping:
				targetSet,nullable,unique=fkMapping[associationName]
				targetTable=self.container.tableNames[targetSet.name]
				fkNames=[]
				kNames=[]
				for keyName in targetSet.KeyKeys():
					# create a dummy value to catch the unusual case where there is a default
					v=targetSet.entityType[keyName]()
					cName=self.container.fieldNames[(self.tableName,(associationName,keyName))]
					fkNames.append(cName)
					kNames.append(self.container.fieldNames[(targetTable,(keyName,))])
					cols.append("%s %s"%(cName,self.container.PrepareSQLType(v,params,nullable)))
				constraints.append("CONSTRAINT %s FOREIGN KEY (%s) REFERENCES %s(%s)"%(
					self.container.QuoteIdentifier(associationName),
					string.join(fkNames,', '),
					self.container.tableNames[targetSet.name],
					string.join(kNames,', ')))
			cols=cols+constraints
		query.append(string.join(cols,u", "))
		query.append(u')')
		return string.join(query,''),params

	def CreateTable(self,keyDefs=True):
		query,params=self.CreateTableQuery(keyDefs)
		try:
			#	print query, params.params
			self.cursor.execute(query,params.params)
			self.dbc.commit()
		except self.container.dbapi.Error,e:
			raise SQLError(u"%s: %s"%(unicode(sys.exc_info()[0]),unicode(sys.exc_info()[1])))
				

class SQLForeignKeyCollection(SQLCollectionMixin,core.NavigationEntityCollection):
	
	def __init__(self,name,fromEntity,toEntitySet,container,associationName):
		core.NavigationEntityCollection.__init__(self,name,fromEntity,toEntitySet)
		SQLCollectionMixin.__init__(self,container)
		self.qualifyNames=True
		# The relation is actually stored in the source entity set
		# which is the entity set of the *fromEntity*, not the base entity set
		self.keyCollection=self.fromEntity.entitySet.OpenCollection()
		self.associationName=associationName
	
	def JoinClause(self):
		join=[]
		# we don't need to look up the details of the join again, as self.entitySet must be the target
		for keyName in self.entitySet.KeyKeys():
			join.append('%s.%s=%s.%s'%(
				self.tableName,
				self.container.fieldNames[(self.tableName,(keyName,))],
				self.keyCollection.tableName,
				self.container.fieldNames[(self.keyCollection.tableName,(self.associationName,keyName))]))
		return ' INNER JOIN %s ON '%self.keyCollection.tableName+string.join(join,', ')
	
	def WhereClause(self,params):
		where=[]
		for k,v in self.fromEntity.KeyDict().items():
			where.append(u"%s.%s=%s"%(self.keyCollection.tableName,
				self.container.fieldNames[(self.keyCollection.tableName,(k,))],
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
			#	print query, params.params
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
		try:
			#	print query, params.params
			self.cursor.execute(query,params.params)
			while True:
				row=self.cursor.fetchone()
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
		self.keyCollection.UpdateLink(self.fromEntity,self.associationName,entity)
		
	def close(self):
		self.keyCollection.close()
		super(SQLForeignKeyCollection,self).close()


class SQLReverseKeyCollection(SQLCollectionMixin,core.NavigationEntityCollection):
	
	def __init__(self,name,fromEntity,toEntitySet,container,associationName):
		core.NavigationEntityCollection.__init__(self,name,fromEntity,toEntitySet)
		SQLCollectionMixin.__init__(self,container)
		# The relation is actually stored in the *toEntitySet*
		# which is the same entity set that our results will be drawn
		# from, which makes it easier as we don't need a join
		self.associationName=associationName

	def WhereClause(self,params):
		where=[]
		for k,v in self.fromEntity.KeyDict().items():
			where.append(u"%s=%s"%(
				self.container.fieldNames[(self.tableName,(self.associationName,k))],
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
		query.append(self.WhereClause(params))
		query=string.join(query,'')
		try:
			#	print query, params.params
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
		try:
			#	print query, params.params
			self.cursor.execute(query,params.params)
			while True:
				row=self.cursor.fetchone()
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

	def itervalues(self):
		return self.ExpandEntities(
			self.entityGenerator())

	def close(self):
		super(SQLReverseKeyCollection,self).close()


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
		elif self.dbapi.threadsafety==1:
			# we can share the module but not the connections
			self.moduleLock=DummyLock()
			self.connectionLocker=threading.RLock
			self.cPoolMax=maxConnections
		else:
			# thread safety above level 1 means we can share everything we need
			self.moduleLock=DummyLock()
			self.connectionLocker=DummyLock
			self.cPoolMax=1
		self.cPoolLock=threading.Condition()
		self.cPoolClosing=False
		self.cPoolHints={}
		self.cMaxHints=maxConnections
		self.cPoolPos=0
		self.cPool=[(None,None)]*self.cPoolMax
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
		"""A mapping from an entity set name to a foreign key mapping of the form::
		
			{<association set name>: (<target entity set>, <nullable flag>, <unique keys flag>),...}
		
		The outer mapping has one entry for each entity set (even if the
		foreign key mapping is empty.
		
		Each foreign key mapping has one entry for each foreign key
		reference that must appear in that entity set's
		table."""
		self.tableNames={}		#: A mapping from entity/association set names to quoted table identifiers
		self.fieldNames={}
		"""A mapping from tuples of (table name,(source path tuple)) to
		the quoted field name to use in SQL queries.  For example::
		
			(u'"Customer"',(u'Address',u'City')) : u"Address_City"
		
		Note that the key consists of the quoted table name, which can
		be looked up from the entity set name using
		:py:attr:`tableNames`"""
		self.fieldNameJoiner=fieldNameJoiner
		"""Default string used to join complex field names in SQL
		queries, e.g. Address_City"""
		# for each entity set in this container, bind a SQLEntityCollection object
		for es in self.containerDef.EntitySet:
			self.fkTable[es.name]={}
			tableName=self.TableName(es)
			self.tableNames[es.name]=tableName
			for sourcePath in self.FieldNameGenerator(es):
				self.fieldNames[(tableName,sourcePath)]=self.FieldName(es.name,sourcePath)
			self.BindEntitySet(es)
		for es in self.containerDef.EntitySet:
			for np in es.entityType.NavigationProperty:
				self.BindNavigationProperty(es,np.name)
		# once the navigation properties have been bound, fkTable will
		# have been populated with any foreign keys we need to add field
		# name mappings for
		for esName,fkMapping in self.fkTable.iteritems():
			for associationName,details in fkMapping.iteritems():
				targetSet,nullable,unique=details
				tableName=self.tableNames[esName]
				for keyName in targetSet.KeyKeys():
					"""Foreign keys are given fake source paths starting with the association set name::
					
						( u"Orders_Customers", u"CustomerID" )"""
					sourcePath=(associationName,keyName)
					self.fieldNames[(tableName,sourcePath)]=self.FieldName(esName,sourcePath)

	def TableName(self,entitySet):
		"""Returns the quoted identifier to use as the table name for
		*entitySet* in SQL queries."""
		return self.QuoteIdentifier(entitySet.name)
	
	def FieldName(self,entitySetName,sourcePath):
		"""Returns the quoted identifier to use as the name for the
		field with *sourcePath* in the entity set with *entitySetName* .
		
		By default we join the sourcePath using :py:attr:`fieldNameJoiner`."""
		return self.QuoteIdentifier(string.join(sourcePath,self.fieldNameJoiner))

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
		fromASEnd=entitySet.GetLinkEnd(name)
		toASEnd=fromASEnd.otherEnd
		# extract the name of the association set
		associationName=fromASEnd.parent.name
		targetSet=toASEnd.entitySet
		multiplicity=(fromASEnd.associationEnd.multiplicity,toASEnd.associationEnd.multiplicity)
		# now we can work on a case-by-case basis, not that fkTable may be
		# filled in twice for the same association (if navigation properties are
		# defined in both directions) but this is benign because the definition
		# should be identical.
		if multiplicity in (
			(edm.Multiplicity.One,edm.Multiplicity.One),
			(edm.Multiplicity.ZeroToOne,edm.Multiplicity.ZeroToOne)):
			entitySet.BindNavigation(name,self.GetSymmetricNavigationCollectionClass(),container=self,associationName=associationName)
		elif multiplicity==(edm.Multiplicity.Many,edm.Multiplicity.Many):
			entitySet.BindNavigation(name,self.GetSymmetricNavigationCollectionClass(),container=self,associationName=associationName)
		elif multiplicity==(edm.Multiplicity.One,edm.Multiplicity.ZeroToOne):
			entitySet.BindNavigation(name,self.GetReverseKeyCollectionClass(),container=self,associationName=associationName)
			self.fkTable[targetSet.name][associationName]=(entitySet,False,True)
		elif multiplicity==(edm.Multiplicity.One,edm.Multiplicity.Many):
			entitySet.BindNavigation(name,self.GetReverseKeyCollectionClass(),container=self,associationName=associationName)
			self.fkTable[targetSet.name][associationName]=(entitySet,False,False)
		elif multiplicity==(edm.Multiplicity.ZeroToOne,edm.Multiplicity.Many):
			entitySet.BindNavigation(name,self.GetReverseKeyCollectionClass(),container=self,associationName=associationName)
			self.fkTable[targetSet.name][associationName]=(entitySet,True,False)
		elif multiplicity==(edm.Multiplicity.ZeroToOne,edm.Multiplicity.One):
			entitySet.BindNavigation(name,self.GetForeignKeyCollectionClass(),container=self,associationName=associationName)
			self.fkTable[entitySet.name][associationName]=(targetSet,False,True)
		elif multiplicity==(edm.Multiplicity.Many,edm.Multiplicity.One):
			entitySet.BindNavigation(name,self.GetForeignKeyCollectionClass(),container=self,associationName=associationName)
			self.fkTable[entitySet.name][associationName]=(targetSet,False,False)
		else:
# 			(edm.Multiplicity.Many,edm.Multiplicity.ZeroToOne)
			entitySet.BindNavigation(name,self.GetForeignKeyCollectionClass(),container=self,associationName=associationName)
			self.fkTable[entitySet.name][associationName]=(targetSet,True,False)

	def GetCollectionClass(self):
		"""Called during construction, returns the collection class used
		to represent a generic entity set."""
		return SQLEntityCollection

	def GetSymmetricNavigationCollectionClass(self):
		"""Called during construction, returns the collection class used
		to represent a symmetric relation stored in a separate table."""
		return SQLRelationCollection
			
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
				
	def CreateTable(self,es,visited):
		# before we create this table, we need to check to see if it references another table
		visited.add(es.name)
		fkMapping=self.fkTable[es.name]
		for associationName,details in fkMapping.iteritems():
			targetSet,nullable,unique=details
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
					return None
			# we have the module lock
			if threadId in self.cPoolHints:
				tryPos,tLast=self.cPoolHints[threadId]
			else:
				if len(self.cPoolHints)>self.cMaxHints:
					# clean up the pool hint table, anything older than 1 min goes
					old=now-60
					for it in self.cPoolHints.keys():
						iPos,iLast=self.cPoolHints[it]
						if iLast<old:
							del self.cPoolHints[it]
					# adaptively grow the max size of the hint table
					if len(self.cPoolHints)>self.cMaxHints:
						self.cMaxHints=len(self.cPoolHints)+self.cMaxHints
						#	print "Growing the hint table to size: %i"%self.cMaxHints
				# start looking from the next position on the list
				tryPos=self.cPoolPos%self.cPoolMax
			i=0
			while i<2*self.cPoolMax:
				c,lock=self.cPool[tryPos]
				if lock is None:
					# create this connection
					lock=self.connectionLocker()
					c=self.OpenConnection()
					self.cPool[tryPos]=(c,lock)
					lock.acquire()
					self.cPoolHints[threadId]=(tryPos,now)
					self.cPoolPos=tryPos+1
					return c
				elif lock.acquire(False):
					self.cPoolHints[threadId]=(tryPos,now)
					self.cPoolPos=tryPos+1
					return c
				else:
					# couldn't get this connection, move on
					tryPos=(tryPos+1)%self.cPoolMax
					i=i+1
					if i==self.cPoolMax:
						# we've tried every connection, wait
						#	print "Thread [%i] has been forced to wait"%threadId
						self.cPoolLock.wait(timeout)
						#	print "Thread [%i] is waking up"%threadId
						# someone released a lock, go round the loop again
		# we are defeated, no database connection for the caller
		# release lock on the module as there is no connection to release
		self.moduleLock.release()
		return None
						
	def ReleaseConnection(self,c):
		threadId=threading.current_thread().ident
		with self.cPoolLock:
			# we have exclusive use of the cPool members
			if threadId in self.cPoolHints:
				tryPos,tLast=self.cPoolHints[threadId]
			else:
				tryPos=0
			i=0
			released=False
			while i<self.cPoolMax:
				cTry,lock=self.cPool[tryPos]
				if c is cTry:
					# This is our connection, release it
					lock.release()
					self.moduleLock.release()
					self.cPoolLock.notify()
					break
				else:
					# this wasn't our connection, move on
					tryPos=(tryPos+1)%self.cPoolMax
					i=i+1

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
		
	def close(self):
		"""Closes this database.
		
		This method goes through each open connection and attempts to
		acquire it before closing it.  If connections are locked by
		other threads we wait for those threads to release them, calling
		:py:meth:`BreakConnection` to speed up termination if
		:possible."""
		with self.cPoolLock:
			self.cPoolClosing=True
			for i in xrange(len(self.cPool)):
				c,lock=self.cPool[i]
				if lock is None:
					continue
				while True:
					if lock.acquire(False):
						c.close()
						self.cPool[i]=(None,None)
						break
					else:
						# we failed to get this lock, break the connection
						self.BreakConnection(c)
						# now wait forever for someone to release a connection
						self.cPoolLock.wait()		

	def __del__(self):
		self.close()
		
	def QuoteIdentifier(self,identifier):
		"""Given an *identifier* returns a safely quoted form of it.
		
		By default we strip double quote and then use them to enclose
		it.  E.g., if the string u'Employee_Name' is passed then the
		string u'"Employee_Name"' is returned."""
		return u'"%s"'%identifier.replace('"','')

	def PrepareSQLValue(self,simpleValue):
		"""Given a simple value, returns a value suitable for passing as a parameter."""
		if not simpleValue:
			return None
		elif isinstance(simpleValue,(edm.StringValue,
			edm.BinaryValue,
			edm.Int16Value,
			edm.Int32Value,
			edm.Int64Value)):
			# critical for security, do proper SQL escaping of quote
			return simpleValue.pyValue
		elif isinstance(simpleValue,edm.DateTimeValue):
			return self.dbapi.Timestamp(
				simpleValue.pyValue.date.century*100+simpleValue.pyValue.date.year,
				simpleValue.pyValue.date.month,
				simpleValue.pyValue.date.day,
				simpleValue.pyValue.time.hour,
				simpleValue.pyValue.time.minute,
				simpleValue.pyValue.time.second)
		else:
			raise NotImplementedError("SQL type for "+simpleValue.__class__.__name__)

	def ReadSQLValue(self,simpleValue,newValue):
		"""Given a simple value and a newValue returned by the database, updates *simpleValue*."""
		simpleValue.SetFromPyValue(newValue)
		
	def PrepareSQLType(self,simpleValue,params,nullable=None):
		"""Given a simple value, returns a SQL-formatted name of its type.

		For example, if the value is Int32 then this might return the
		string u'INTEGER'"""
		p=simpleValue.pDef
		columnDef=[]
		if isinstance(simpleValue,edm.Int32Value):
			columnDef.append(u"INTEGER")
		elif isinstance(simpleValue,edm.DateTimeValue):
			columnDef.append("TIMESTAMP")
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
		elif isinstance(simpleValue,edm.StringValue):
			if p.fixedLength:
				if p.maxLength:
					columnDef.append(u"CHARACTER(%i)"%p.maxLength)
				else:
					raise SQLModelError("Edm.String of fixed length missing max: %s"%p.name)
			elif p.maxLength:
				columnDef.append(u"VARCHAR(%i)"%p.maxLength)
			else:
				raise NotImplementedError("SQL binding for Edm.String of unbounded length: %s"%p.name)
		else:
			raise NotImplementedError("SQL type for %s"%p.type)
		if (nullable is not None and not nullable) or (nullable is None and not p.nullable):
			columnDef.append(u' NOT NULL')
		if simpleValue:
			# Format the default
			columnDef.append(u' DEFAULT ')
			columnDef.append(params.AddParam(self.PrepareSQLValue(simpleValue)))
		return string.join(columnDef,'')		
# 		'Edm.Binary':	BINARY(n) or VARBINARY(n) 
# 		'Edm.Boolean':	BOOLEAN
# 		'Edm.Byte':		SMALLINT
# 		'Edm.DateTimeOffset':	CHARACTER(20), e.g. 20131209T100159+0100
# 		'Edm.Time':		TIME
# 		'Edm.Double':	FLOAT
# 		'Edm.Single':	REAL
# 		'Edm.Guid':		BINARY(16)
# 		'Edm.Int16':	SMALLINT
# 		'Edm.Int64':	BIGINT
# 		'Edm.String':	VARCHAR(n) or CHARACTER(n) assuming bounded
# 		'Edm.SByte':	SMALLINT
			
class SQLiteEntityContainer(SQLEntityContainer):
	
	def __init__(self,filePath,containerDef):
		super(SQLiteEntityContainer,self).__init__(containerDef,sqlite3)
		if not isinstance(filePath,OSFilePath):
			raise TypeError("SQLiteDB requires an OS file path")
		self.filePath=filePath

	def GetCollectionClass(self):
		return SQLiteEntityCollection
		
	def OpenConnection(self):
		return self.dbapi.connect(str(self.filePath))
		
	def BreakConnection(self,connection):
		connection.interrupt()

	def PrepareSQLValue(self,simpleValue):
		"""Given a simple value, returns a value suitable for passing as a parameter."""
		if not simpleValue:
			return None
		elif isinstance(simpleValue,edm.BinaryValue):
			return buffer(simpleValue.pyValue)
		else:
			return super(SQLiteEntityContainer,self).PrepareSQLValue(simpleValue)

	def ReadSQLValue(self,simpleValue,newValue):
		"""Handle buffer types specially."""
		if type(newValue)==BufferType:
			newValue=str(newValue)
			simpleValue.SetFromPyValue(newValue)
		elif isinstance(simpleValue,edm.DateTimeValue):
			# SQLite stores these as strings!
			simpleValue.SetFromPyValue(iso.TimePoint(newValue))
		else:
			simpleValue.SetFromPyValue(newValue)

	def PrepareSQLType(self,simpleValue,params,nullable=None):
		"""SQLite custom mappings"""
		p=simpleValue.pDef
		columnDef=[]
		if isinstance(simpleValue,edm.StringValue):
			columnDef.append(u"TEXT")
		elif isinstance(simpleValue,edm.BinaryValue):
			columnDef.append(u"BLOB")
		else:
			return super(SQLiteEntityContainer,self).PrepareSQLType(simpleValue,params,nullable)
		if (nullable is not None and not nullable) or (nullable is None and not p.nullable):
			columnDef.append(u' NOT NULL')
		if simpleValue:
			# Format the default
			columnDef.append(u' DEFAULT ')
			columnDef.append(params.AddParam(self.PrepareSQLValue(simpleValue)))
		return string.join(columnDef,'')
		

class SQLiteEntityCollection(SQLEntityCollection):
	
	def SQLExpressionConcat(self,expression,params,context):
		"""We support concatenation using ||"""
		query=[]
		query.append(self.SQLExpression(expression.operands[0],params,'*'))
		query.append(u' || ')
		query.append(self.SQLExpression(expression.operands[1],params,'*'))
		return self.SQLBracket(string.join(query,''),context,'*')

