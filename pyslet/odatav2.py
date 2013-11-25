#! /usr/bin/env python
"""This module implements the Open Data Protocol specification defined by Microsoft."""

from types import *
import sys, cgi, urllib, string, itertools, traceback, StringIO, json, base64, decimal, uuid, math, warnings

import pyslet.info as info
import pyslet.iso8601 as iso
import pyslet.rfc4287 as atom
import pyslet.rfc5023 as app
import pyslet.rfc2616 as http
import pyslet.rfc2396 as uri
import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsi
import pyslet.html40_19991224 as html
import pyslet.mc_csdl as edm
from pyslet.unicode5 import CharClass, DetectEncoding

from odatav2_core import *
import odatav2_metadata as edmx

	
NUMERIC_TYPES=(
	edm.SimpleType.Double,
	edm.SimpleType.Single,
	edm.SimpleType.Decimal,
	edm.SimpleType.Int64,
	edm.SimpleType.Int32,
	edm.SimpleType.Int16,
	edm.SimpleType.Byte)
	
def PromoteTypes(typeA,typeB):
	"""Given two values from :py:class:`pyslet.mc_csdl.SimpleType` returns the common promoted type.
	
	If typeA and typeB are the same this is always returns that type code.
	
	Otherwise it follows numeric type promotion rules laid down in the
	specification. If the types are incompatible then an EvaluationError is raised."""
	if typeA==typeB:
		return typeA
	elif typeA is None:
		return typeB
	elif typeB is None:
		return typeA
	elif typeA not in NUMERIC_TYPES or typeB not in NUMERIC_TYPES:
		raise EvaluationError("Incompatible types: %s and %s"%(edm.SimpleType.EncodeValue(typeA),
			edm.SimpleType.EncodeValue(typeB)))
	elif edm.SimpleType.Double in (typeA,typeB):
		return edm.SimpleType.Double
	elif edm.SimpleType.Single in (typeA,typeB):
		return edm.SimpleType.Single
	elif edm.SimpleType.Decimal in (typeA,typeB):
		return edm.SimpleType.Decimal
	elif edm.SimpleType.Int64 in (typeA,typeB):
		return edm.SimpleType.Int64
	elif edm.SimpleType.Int32 in (typeA,typeB):
		return edm.SimpleType.Int32
	elif edm.SimpleType.Int16 in (typeA,typeB):
		return edm.SimpleType.Int16
	# else must be both Byte - already got this case above	


def CanCastMethodArgument(typeA,typeB):
	"""Given two values from :py:class:`pyslet.mc_csdl.SimpleType` returns True if *typeA* can be cast to *typeB*.
	
	If typeA and typeB are the same this is always True.
	
	If typeA is NULL then we return True"""
	if typeA==typeB:
		return True
	elif typeA is None:
		return True
	elif typeB==edm.SimpleType.Double:
		return typeA in NUMERIC_TYPES
	elif typeB==edm.SimpleType.Single:
		return typeA in NUMERIC_TYPES
	elif typeB==edm.SimpleType.Decimal:
		return typeA in (edm.SimpleType.Decimal,edm.SimpleType.Int64,edm.SimpleType.Int32,edm.SimpleType.Int16)
	elif typeB==edm.SimpleType.Int64:
		return typeA in NUMERIC_TYPES
	elif typeB==edm.SimpleType.Int32:
		return typeA in NUMERIC_TYPES
	elif typeB==edm.SimpleType.Int16:
		return typeA in NUMERIC_TYPES
	elif typeB==edm.SimpleType.Byte:
		return typeA in NUMERIC_TYPES
	else:
		return False

			
class OperatorCategory(xsi.Enumeration):
	"""An enumeration used to represent operator categories (for precedence).
	::
		
		OperatorCategory.Unary	
		SimpleType.DEFAULT == None

	Note that OperatorCategory.X > OperatorCategory.Y if and only if operator X
	has higher precedence that operator Y.
	
	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
	
	decode={
		"Grouping":10,
		"Primary":9,
		"Unary":8,
		"Multiplicative":7,
		"Additive":6,
		"Relational":5,
		"Equality":4,
		"ConditionalAnd":3,
		"ConditionalOr":2
		}
xsi.MakeEnumeration(OperatorCategory)

		
class Operator(xsi.Enumeration):
	"""An enumeration used to represent operators.
	
	Note that the expressions not, and and or have aliases "boolNot",
	"boolAnd" and "boolOr" to make it easier to use Python attribute
	notation::
	
		Operator.mul
		Operator.DEFAULT == None
		Operator.boolNot == getattr(Operator,"not")
	
	"""
	
	decode={
		'paren':20,
		'member':19,
		'methodCall':18,
		'negate':17,
		'not':16,
		'cast':15,
		'mul':14,
		'div':13,
		'mod':12,
		'add':11,
		'sub':10,
		'lt':9,
		'gt':8,
		'le':7,
		'ge':6,
		'isof':5,
		'eq':4,
		'ne':3,
		'and':2,
		'or':1,
		}

	Category={
		}
	"""A mapping from an operator to an operator category identifier
	which can be compared for precedence testing::
	
		Operator.Category.[opA] > Operator.Category.[opB]
	
	if and only if opA has higher precedence than opB."""

xsi.MakeEnumeration(Operator)
xsi.MakeEnumerationAliases(Operator,{
	'boolParen':'paren',
	'boolMethodCall':'methodCall',
	'boolNot':'not',
	'boolAnd':'and',
	'boolOr':'or'})

Operator.Category={
	Operator.paren:OperatorCategory.Grouping,
	Operator.member:OperatorCategory.Primary,
	Operator.methodCall:OperatorCategory.Primary,
	Operator.negate:OperatorCategory.Unary,
	Operator.boolNot:OperatorCategory.Unary,
	Operator.cast:OperatorCategory.Unary,
	Operator.mul:OperatorCategory.Multiplicative,
	Operator.div:OperatorCategory.Multiplicative,
	Operator.mod:OperatorCategory.Multiplicative,
	Operator.add:OperatorCategory.Additive,
	Operator.sub:OperatorCategory.Additive,
	Operator.lt:OperatorCategory.Relational,
	Operator.gt:OperatorCategory.Relational,
	Operator.le:OperatorCategory.Relational,
	Operator.ge:OperatorCategory.Relational,
	Operator.isof:OperatorCategory.Relational,
	Operator.eq:OperatorCategory.Equality,
	Operator.ne:OperatorCategory.Equality,
	Operator.boolAnd:OperatorCategory.ConditionalAnd,
	Operator.boolOr:OperatorCategory.ConditionalOr }


	
class Method(xsi.Enumeration):
	"""An enumeration used to represent method calls.
	::
	
		Method.endswith
		Method.DEFAULT == None
	"""
	
	decode={
		'endswith':1,
		'indexof':2,
		'replace':3,
		'startswith':4,
		'tolower':5,
		'toupper':6,
		'trim':7,
		'substring':8,
		'substringof':9,
		'concat':10,
		'length':11,
		'year':12,
		'month':13,
		'day':14,
		'hour':15,
		'minute':16,
		'second':17,
		'round':18,
		'floor':19,
		'ceiling':20
		}
xsi.MakeEnumeration(Method)

	
class CommonExpression(object):
	"""Represents a common expression, used by $filter and $orderby system query options."""
	
	def __init__(self,operator=None):
		self.parent=None
		self.operator=operator
		self.operands=[]

	def AddOperand(self,operand):
		self.operands.append(operand)
	
	def Evaluate(self,contextEntity):
		raise NotImplementedError

	def __cmp__(self,other):
		"""We implement __cmp__ based on operator precedence."""
		if other.operator is None or self.operator is None:
			raise ValueError("Expression without operator cannot be compared")
		return cmp(Operator.Category[self.operator],Operator.Category[other.operator])


class UnaryExpression(CommonExpression):
	
	EvalMethod={
		}
	"""A mapping from unary operators to unbound methods that evaluate
	the operator."""

	def __init__(self,operator):
		super(UnaryExpression,self).__init__(operator)

	def Evaluate(self,contextEntity):
		rValue=self.operands[0].Evaluate(contextEntity)
		return self.EvalMethod[self.operator](self,rValue)

	def EvaluateNegate(self,rValue):
		typeCode=rValue.typeCode
		if typeCode in (edm.SimpleType.Byte, edm.SimpleType.Int16):
			rValue=rValue.Cast(edm.SimpleType.Int32)
		elif typeCode == edm.SimpleType.Single:
			rValue=rValue.Cast(edm.SimpleType.Double)
		typeCode=rValue.typeCode
		if typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64, edm.SimpleType.Double, edm.SimpleType.Decimal):
			result=edm.SimpleValue.NewValue(typeCode)
			if rValue:
				result.SetFromPyValue(0-rValue.pyValue)
			return result
		elif typeCode is None:	# -null
			return edm.SimpleValue.NewValue(edm.SimpleType.Int32)
		else:
			raise EvaluationError("Illegal operand for negate")

	def EvaluateNot(self,rValue):
		if isinstance(rValue,edm.SimpleValue):
			if rValue:
				typeCode=rValue.typeCode
				if typeCode==edm.SimpleType.Boolean:
					result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
					result.SetFromPyValue(not rValue.pyValue)
					return result
				else:
					raise EvaluationError("Illegal operand for not")
			else:
				result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
				return result
		else:
			raise EvaluationError("Illegal operand for not")


UnaryExpression.EvalMethod={
	Operator.negate:UnaryExpression.EvaluateNegate,
	Operator.boolNot:UnaryExpression.EvaluateNot }


class BinaryExpression(CommonExpression):
	
	EvalMethod={
		}
	"""A mapping from binary operators to unbound methods that evaluate
	the operator."""
 
	def __init__(self,operator):
		super(BinaryExpression,self).__init__(operator)
		
	def Evaluate(self,contextEntity):
		lValue=self.operands[0].Evaluate(contextEntity)
		if self.operator==Operator.member:
			# Special handling for the member operator, as the left-hand
			# side of the expression returns the context for evaluating
			# the right-hand side
			return self.operands[1].Evaluate(lValue)
		elif self.operator in (Operator.isof, Operator.cast):
			# Special handling due to optional first parameter to
			# signify the context entity 
			if len(self.operands)==1:
				rValue=lValue
				lValue=contextEntity
			else:
				rValue=self.operands[1].Evaluate(contextEntity)	
			return self.EvalMethod[self.operator](self,lValue,rValue)
		else:
			rValue=self.operands[1].Evaluate(contextEntity)	
			return self.EvalMethod[self.operator](self,lValue,rValue)
		
	def PromoteOperands(self,lValue,rValue):
		if isinstance(lValue,edm.SimpleValue) and isinstance(rValue,edm.SimpleValue):
			return PromoteTypes(lValue.typeCode,rValue.typeCode)
		else:
			raise EvaluationError("Expected primitive value for %s"%Operator.EncodeValue(self.operator)) 

	def EvaluateCast(self,lValue,rValue):
		# rValue is always a string literal name of the type to look up
		if not lValue:
			# cast(NULL, <any type>) results in NULL
			try:
				typeCode=edm.SimpleType.DecodeValue(rValue.pyValue)
				result=edm.SimpleValue.NewValue(typeCode)
			except ValueError:
				result=edm.SimpleValue.NewValue(None)
			return result		
		elif isinstance(lValue,edm.Entity):
			# in the future we should deal with entity type inheritance
			# right now, the only thing we can cast an entity instance
			# to is itself
			name=lValue.typeDef.GetFQName()
			if name==rValue.pyValue:
				return lValue
			else:
				raise EvaluationError("Can't cast %s to %s"%(name,str(rValue.pyValue)))
		elif isinstance(lValue,edm.SimpleValue):
			# look up the name of the primitive type
			try:
				typeCode=edm.SimpleType.DecodeValue(rValue.pyValue)
			except ValueError:
				raise EvaluationError("Unrecognized type: %s"%str(rValue.pyValue))
			newCode=PromoteTypes(typeCode,lValue.typeCode)
			if typeCode!=newCode:
				raise EvaluationError("Can't cast %s to %s"%(edm.SimpleType.EncodeValue(lValue.typeCode),
					edm.SimpleType.EncodeValue(typeCode)))
			result=edm.SimpleValue.NewValue(typeCode)
			result.SetFromPyValue(lValue.pyValue)
			return result
		else:
			raise EvaluationError("Illegal operands for isof")		
	
	def EvaluateMul(self,lValue,rValue):
		typeCode=self.PromoteOperands(lValue,rValue)
		if typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64, edm.SimpleType.Single,
			edm.SimpleType.Double, edm.SimpleType.Decimal):
			lValue=lValue.Cast(typeCode)
			rValue=rValue.Cast(typeCode)
			result=edm.SimpleValue.NewValue(typeCode)
			if lValue and rValue:
				result.SetFromPyValue(lValue.pyValue*rValue.pyValue)
			return result
		elif typeCode is None:	# null mul null
			return edm.SimpleValue.NewValue(edm.SimpleType.Int32)
		else:
			raise EvaluationError("Illegal operands for mul")
	
	def EvaluateDiv(self,lValue,rValue):
		try:
			typeCode=self.PromoteOperands(lValue,rValue)
			if typeCode in (edm.SimpleType.Single, edm.SimpleType.Double, edm.SimpleType.Decimal):
				lValue=lValue.Cast(typeCode)
				rValue=rValue.Cast(typeCode)
				result=edm.SimpleValue.NewValue(typeCode)
				if lValue and rValue:
					result.SetFromPyValue(lValue.pyValue/rValue.pyValue)
				return result
			elif typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64):
				lValue=lValue.Cast(typeCode)
				rValue=rValue.Cast(typeCode)
				result=edm.SimpleValue.NewValue(typeCode)
				if lValue and rValue:
					# OData doesn't really specify integer division rules so
					# we use floating point division and truncate towards zero
					result.SetFromPyValue(int(float(lValue.pyValue)/float(rValue.pyValue)))
				return result
			elif typeCode is None:	# null div null
				return edm.SimpleValue.NewValue(edm.SimpleType.Int32)
			else:
				raise EvaluationError("Illegal operands for div")
		except ZeroDivisionError as e:
			raise EvaluationError(str(e))
	
	def EvaluateMod(self,lValue,rValue):
		try:
			typeCode=self.PromoteOperands(lValue,rValue)
			if typeCode in (edm.SimpleType.Single, edm.SimpleType.Double, edm.SimpleType.Decimal):
				lValue=lValue.Cast(typeCode)
				rValue=rValue.Cast(typeCode)
				result=edm.SimpleValue.NewValue(typeCode)
				if lValue and rValue:
					result.SetFromPyValue(math.fmod(lValue.pyValue,rValue.pyValue))
				return result
			elif typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64):
				lValue=lValue.Cast(typeCode)
				rValue=rValue.Cast(typeCode)
				result=edm.SimpleValue.NewValue(typeCode)
				if lValue and rValue:
					# OData doesn't really specify integer division rules so
					# we use floating point division and truncate towards zero
					result.SetFromPyValue(int(math.fmod(float(lValue.pyValue),float(rValue.pyValue))))
				return result
			elif typeCode is None:	# null div null
				return edm.SimpleValue.NewValue(edm.SimpleType.Int32)
			else:
				raise EvaluationError("Illegal operands for div")
		except (ZeroDivisionError,ValueError) as e:
			raise EvaluationError(str(e))
				
	def EvaluateAdd(self,lValue,rValue):
		typeCode=self.PromoteOperands(lValue,rValue)
		if typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64, edm.SimpleType.Single,
			edm.SimpleType.Double, edm.SimpleType.Decimal):
			lValue=lValue.Cast(typeCode)
			rValue=rValue.Cast(typeCode)
			result=edm.SimpleValue.NewValue(typeCode)
			if lValue and rValue:
				result.SetFromPyValue(lValue.pyValue+rValue.pyValue)
			return result
		elif typeCode is None:	# null add null
			return edm.SimpleValue.NewValue(edm.SimpleType.Int32)
		else:
			raise EvaluationError("Illegal operands for add")
	
	def EvaluateSub(self,lValue,rValue):
		typeCode=self.PromoteOperands(lValue,rValue)
		if typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64, edm.SimpleType.Single,
			edm.SimpleType.Double, edm.SimpleType.Decimal):
			lValue=lValue.Cast(typeCode)
			rValue=rValue.Cast(typeCode)
			result=edm.SimpleValue.NewValue(typeCode)
			if lValue and rValue:
				result.SetFromPyValue(lValue.pyValue-rValue.pyValue)
			return result
		elif typeCode is None:	# null sub null
			return edm.SimpleValue.NewValue(edm.SimpleType.Int32)
		else:
			raise EvaluationError("Illegal operands for sub")
	
	def EvaluateLt(self,lValue,rValue):
		return self.EvaluateRelation(lValue,rValue,lambda x,y:x<y)
	
	def EvaluateGt(self,lValue,rValue):
		return self.EvaluateRelation(lValue,rValue,lambda x,y:x>y)
	
	def EvaluateLe(self,lValue,rValue):
		return self.EvaluateRelation(lValue,rValue,lambda x,y:x<=y)
	
	def EvaluateGe(self,lValue,rValue):
		return self.EvaluateRelation(lValue,rValue,lambda x,y:x>=y)
	
	def EvaluateRelation(self,lValue,rValue,relation):
		typeCode=self.PromoteOperands(lValue,rValue)
		if typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64, edm.SimpleType.Single,
			edm.SimpleType.Double, edm.SimpleType.Decimal):
			lValue=lValue.Cast(typeCode)
			rValue=rValue.Cast(typeCode)
			result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
			if lValue and rValue:
				result.SetFromPyValue(relation(lValue.pyValue,rValue.pyValue))
			else:
				# one of the operands is null => False
				result.SetFromPyValue(False)
			return result
		elif typeCode in (edm.SimpleType.String, edm.SimpleType.DateTime, edm.SimpleType.Guid):
			result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
			result.SetFromPyValue(relation(lValue.pyValue,rValue.pyValue))
			return result
		elif typeCode is None:	# e.g., null lt null
			result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
			result.SetFromPyValue(False)
			return result
		else:
			raise EvaluationError("Illegal operands for %s"%Operator.EncodeValue(self.operator))
		
	def EvaluateIsOf(self,lValue,rValue):
		# rValue is always a string literal name of the type to look up
		if not lValue:
			# isof(NULL, <any type> ) is False
			result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
			result.SetFromPyValue(False)
			return result
		elif isinstance(lValue,edm.Entity):
			# in the future we should test the entity for inheritance
			name=lValue.typeDef.GetFQName()
			result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
			result.SetFromPyValue(name==rValue.pyValue)
			return result
		elif isinstance(lValue,edm.SimpleValue):
			# look up the name of the primitive type
			try:
				typeCode=edm.SimpleType.DecodeValue(rValue.pyValue)
			except ValueError:
				raise EvaluationError("Unrecognized type: %s"%str(rValue.pyValue))
			result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
			# we return True if the type of the target, when promoted with type
			# being tested results in the type being tested
			try:
				rValue=(typeCode==PromoteTypes(typeCode,lValue.typeCode))
			except EvaluationError:
				# incompatible types means False
				rValue=False
			result.SetFromPyValue(rValue)
			return result
		else:
			raise EvaluationError("Illegal operands for isof")		
	
	def EvaluateEq(self,lValue,rValue):
		if isinstance(lValue,edm.Entity) and isinstance(rValue,edm.Entity):
			# we can do comparison of entities, but must be the same entity!
			result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
			if lValue.entitySet is rValue.entitySet:
				# now test that the keys are the same
				result.pyValue=(lValue.Key()==rValue.Key())
			else:
				result.pyValue=False
			return result
		else:
			typeCode=self.PromoteOperands(lValue,rValue)
			if typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64, edm.SimpleType.Single,
				edm.SimpleType.Double, edm.SimpleType.Decimal):
				lValue=lValue.Cast(typeCode)
				rValue=rValue.Cast(typeCode)
				result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
				result.SetFromPyValue(lValue.pyValue==rValue.pyValue)
				return result
			elif typeCode in (edm.SimpleType.String, edm.SimpleType.DateTime, edm.SimpleType.Guid, edm.SimpleType.Binary):
				result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
				result.SetFromPyValue(lValue.pyValue==rValue.pyValue)
				return result
			elif typeCode is None:	# null eq null
				result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
				result.SetFromPyValue(True)
				return result
			else:
				raise EvaluationError("Illegal operands for add")
	
	def EvaluateNe(self,lValue,rValue):
		result=self.EvaluateEq(lValue,rValue)
		result.pyValue=not result.pyValue
		return result
	
	def EvaluateAnd(self,lValue,rValue):
		"""Watch out for the differences between OData 2-value logic and
		the usual SQL 3-value approach."""
		typeCode=self.PromoteOperands(lValue,rValue)
		if typeCode==edm.SimpleType.Boolean:
			result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
			if lValue and rValue:
				result.pyValue=lValue.pyValue and rValue.pyValue
			else:
				result.pyValue=False
			return result
		elif typeCode is None:
			# null or null
			result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
			result.pyValue=False
			return result
		else:			
			raise EvaluationError("Illegal operands for boolean and")
				
	def EvaluateOr(self,lValue,rValue):
		"""Watch out for the differences between OData 2-value logic and
		the usual SQL 3-value approach."""
		typeCode=self.PromoteOperands(lValue,rValue)
		if typeCode==edm.SimpleType.Boolean:
			result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
			if lValue and rValue:
				result.pyValue=lValue.pyValue or rValue.pyValue
			else:
				result.pyValue=False
			return result
		elif typeCode is None:
			# null or null
			result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
			result.pyValue=False
			return result
		else:			
			raise EvaluationError("Illegal operands for boolean and")
						
BinaryExpression.EvalMethod={
	Operator.cast:BinaryExpression.EvaluateCast,
	Operator.mul:BinaryExpression.EvaluateMul,
	Operator.div:BinaryExpression.EvaluateDiv,
	Operator.mod:BinaryExpression.EvaluateMod,
	Operator.add:BinaryExpression.EvaluateAdd,
	Operator.sub:BinaryExpression.EvaluateSub,
	Operator.lt:BinaryExpression.EvaluateLt,
	Operator.gt:BinaryExpression.EvaluateGt,
	Operator.le:BinaryExpression.EvaluateLe,
	Operator.ge:BinaryExpression.EvaluateGe,
	Operator.isof:BinaryExpression.EvaluateIsOf,
	Operator.eq:BinaryExpression.EvaluateEq,
	Operator.ne:BinaryExpression.EvaluateNe,
	Operator.boolAnd:BinaryExpression.EvaluateAnd,
	Operator.boolOr:BinaryExpression.EvaluateOr }
	
			
class LiteralExpression(CommonExpression):
	
	def __init__(self,value):
		super(LiteralExpression,self).__init__()
		self.value=value

	def Evaluate(self,contextEntity):
		"""A literal evaluates to itself."""
		return self.value


class PropertyExpression(CommonExpression):
	
	def __init__(self,name):
		super(PropertyExpression,self).__init__()
		self.name=name
		
	def Evaluate(self,contextEntity):
		if contextEntity:
			if isinstance(contextEntity,edm.Entity):
				if contextEntity.IsEntityCollection(self.name):
					raise EvaluationError("%s navigation property must have cardinality of 1 or 0..1"%self.name)
				else:
					result=contextEntity[self.name]
					if isinstance(result,edm.DeferredValue):
						result=result.GetEntity()
					if result is None:
						# The navigation property does not point to anything, return a generic null
						result=edm.SimpleValue(None,self.name)
					return result
			elif self.name in contextEntity:
				# contextEntity must be a complex value
				return contextEntity[self.name]
			else:
				raise EvaluationError("Undefined property: %s"%self.name)
		else:
			raise EvaluationError("Evaluation of %s member: no entity in context"%self.name)	


class CallExpression(CommonExpression):
	
	EvalMethod={
		}
	"""A mapping from method calls to unbound methods that evaluate
	the method."""

	def __init__(self,methodCall):
		super(CallExpression,self).__init__(Operator.methodCall)
		self.method=methodCall

	def Evaluate(self,contextEntity):
		return self.EvalMethod[self.method](self,
			map(lambda x:x.Evaluate(contextEntity),self.operands))

	def PromoteParameter(self,arg,typeCode):
		if isinstance(arg,edm.SimpleValue):
			if CanCastMethodArgument(arg.typeCode,typeCode):
				return arg.Cast(typeCode)
		raise EvaluationError("Expected %s value in %s()"%(
			edm.SimpleType.EncodeValue(typeCode),Method.EncodeValue(self.method))) 

	def CheckStrictParameter(self,arg,typeCode):
		if isinstance(arg,edm.SimpleValue):
			if arg.typeCode==typeCode:
				return arg
		raise EvaluationError("Expected %s value in %s()"%(
			edm.SimpleType.EncodeValue(typeCode),Method.EncodeValue(self.method))) 
		
	def EvaluateEndswith(self,args):
		if (len(args)==2):
			target=self.PromoteParameter(args[0],edm.SimpleType.String)
			prefix=self.PromoteParameter(args[1],edm.SimpleType.String)
			result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
			if target and prefix:
				result.SetFromPyValue(target.pyValue.endswith(prefix.pyValue))
			return result
		else:
			raise EvaluationError("endswith() takes 2 arguments, %i given"%len(args))

	def EvaluateIndexof(self,args):
		if (len(args)==2):
			target=self.PromoteParameter(args[0],edm.SimpleType.String)
			searchString=self.PromoteParameter(args[1],edm.SimpleType.String)
			result=edm.SimpleValue.NewValue(edm.SimpleType.Int32)
			if target and searchString:
				result.SetFromPyValue(target.pyValue.find(searchString.pyValue))
			return result
		else:
			raise EvaluationError("indexof() takes 2 arguments, %i given"%len(args))

	def EvaluateReplace(self,args):
		if (len(args)==3):
			target=self.PromoteParameter(args[0],edm.SimpleType.String)
			searchString=self.PromoteParameter(args[1],edm.SimpleType.String)
			replaceString=self.PromoteParameter(args[2],edm.SimpleType.String)
			result=edm.SimpleValue.NewValue(edm.SimpleType.String)
			if target and searchString and replaceString:
				result.SetFromPyValue(target.pyValue.replace(searchString.pyValue,replaceString.pyValue))
			return result
		else:
			raise EvaluationError("replace() takes 3 arguments, %i given"%len(args))

	def EvaluateStartswith(self,args):
		if (len(args)==2):
			target=self.PromoteParameter(args[0],edm.SimpleType.String)
			prefix=self.PromoteParameter(args[1],edm.SimpleType.String)
			result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
			if target and prefix:
				result.SetFromPyValue(target.pyValue.startswith(prefix.pyValue))
			return result
		else:
			raise EvaluationError("startswith() takes 2 arguments, %i given"%len(args))

	def EvaluateTolower(self,args):
		if (len(args)==1):
			target=self.PromoteParameter(args[0],edm.SimpleType.String)
			result=edm.SimpleValue.NewValue(edm.SimpleType.String)
			if target:
				result.SetFromPyValue(target.pyValue.lower())
			return result
		else:
			raise EvaluationError("tolower() takes 1 argument, %i given"%len(args))

	def EvaluateToupper(self,args):
		if (len(args)==1):
			target=self.PromoteParameter(args[0],edm.SimpleType.String)
			result=edm.SimpleValue.NewValue(edm.SimpleType.String)
			if target:
				result.SetFromPyValue(target.pyValue.upper())
			return result
		else:
			raise EvaluationError("toupper() takes 1 argument, %i given"%len(args))

	def EvaluateTrim(self,args):
		if (len(args)==1):
			target=self.PromoteParameter(args[0],edm.SimpleType.String)
			result=edm.SimpleValue.NewValue(edm.SimpleType.String)
			if target:
				result.SetFromPyValue(target.pyValue.strip())
			return result
		else:
			raise EvaluationError("trim() takes 1 argument, %i given"%len(args))

	def EvaluateSubstring(self,args):
		if (len(args)==2 or len(args)==3):
			target=self.CheckStrictParameter(args[0],edm.SimpleType.String)
			start=self.CheckStrictParameter(args[1],edm.SimpleType.Int32)
			result=edm.SimpleValue.NewValue(edm.SimpleType.String)
			if len(args)==3:
				length=self.CheckStrictParameter(args[2],edm.SimpleType.Int32)
			else:
				length=None
			if target and start:
				if length:
					result.SetFromPyValue(target.pyValue[start.pyValue:start.pyValue+length.pyValue])
				else:
					result.SetFromPyValue(target.pyValue[start.pyValue:])
			return result
		else:
			raise EvaluationError("substring() takes 2 or 3 arguments, %i given"%len(args))

	def EvaluateSubstringof(self,args):
		if (len(args)==2):
			target=self.PromoteParameter(args[0],edm.SimpleType.String)
			searchString=self.PromoteParameter(args[1],edm.SimpleType.String)
			result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
			if target and searchString:
				result.SetFromPyValue(target.pyValue.find(searchString.pyValue)>=0)
			return result
		else:
			raise EvaluationError("substringof() takes 2 arguments, %i given"%len(args))

	def EvaluateConcat(self,args):
		if (len(args)==2):
			leftString=self.CheckStrictParameter(args[0],edm.SimpleType.String)
			rightString=self.CheckStrictParameter(args[1],edm.SimpleType.String)
			result=edm.SimpleValue.NewValue(edm.SimpleType.String)
			if leftString and rightString:
				result.SetFromPyValue(leftString.pyValue+rightString.pyValue)
			return result
		else:
			raise EvaluationError("concat() takes 2 arguments, %i given"%len(args))

	def EvaluateLength(self,args):
		if (len(args)==1):
			target=self.CheckStrictParameter(args[0],edm.SimpleType.String)
			result=edm.SimpleValue.NewValue(edm.SimpleType.Int32)
			if target:
				result.SetFromPyValue(len(target.pyValue))
			return result
		else:
			raise EvaluationError("length() takes 1 argument, %i given"%len(args))

	def EvaluateYear(self,args):
		if (len(args)==1):
			target=self.CheckStrictParameter(args[0],edm.SimpleType.DateTime)
			result=edm.SimpleValue.NewValue(edm.SimpleType.Int32)
			if target:
				result.SetFromPyValue(target.pyValue.date.century*100+target.pyValue.date.year)
			return result
		else:
			raise EvaluationError("year() takes 1 argument, %i given"%len(args))

	def EvaluateMonth(self,args):
		if (len(args)==1):
			target=self.CheckStrictParameter(args[0],edm.SimpleType.DateTime)
			result=edm.SimpleValue.NewValue(edm.SimpleType.Int32)
			if target:
				result.SetFromPyValue(target.pyValue.date.month)
			return result
		else:
			raise EvaluationError("month() takes 1 argument, %i given"%len(args))

	def EvaluateDay(self,args):
		if (len(args)==1):
			target=self.CheckStrictParameter(args[0],edm.SimpleType.DateTime)
			result=edm.SimpleValue.NewValue(edm.SimpleType.Int32)
			if target:
				result.SetFromPyValue(target.pyValue.date.day)
			return result
		else:
			raise EvaluationError("day() takes 1 argument, %i given"%len(args))

	def EvaluateHour(self,args):
		if (len(args)==1):
			target=self.CheckStrictParameter(args[0],edm.SimpleType.DateTime)
			result=edm.SimpleValue.NewValue(edm.SimpleType.Int32)
			if target:
				result.SetFromPyValue(target.pyValue.time.hour)
			return result
		else:
			raise EvaluationError("hour() takes 1 argument, %i given"%len(args))

	def EvaluateMinute(self,args):
		if (len(args)==1):
			target=self.CheckStrictParameter(args[0],edm.SimpleType.DateTime)
			result=edm.SimpleValue.NewValue(edm.SimpleType.Int32)
			if target:
				result.SetFromPyValue(target.pyValue.time.minute)
			return result
		else:
			raise EvaluationError("minute() takes 1 argument, %i given"%len(args))

	def EvaluateSecond(self,args):
		if (len(args)==1):
			target=self.CheckStrictParameter(args[0],edm.SimpleType.DateTime)
			result=edm.SimpleValue.NewValue(edm.SimpleType.Int32)
			if target:
				result.SetFromPyValue(target.pyValue.time.second)
			return result
		else:
			raise EvaluationError("second() takes 1 argument, %i given"%len(args))

	def EvaluateRound(self,args):
		"""This is a bit inefficient, but we convert to and from Decimal
		if necessary to ensure we stick to the rounding rules (even for
		binary, up for decimals)."""
		if (len(args)==1):
			try:
				target=self.PromoteParameter(args[0],edm.SimpleType.Decimal)
				result=edm.SimpleValue.NewValue(edm.SimpleType.Decimal)
				if target:
					result.SetFromPyValue(target.pyValue.to_integral(decimal.ROUND_HALF_UP))
			except EvaluationError:
				target=self.PromoteParameter(args[0],edm.SimpleType.Double)				
				result=edm.SimpleValue.NewValue(edm.SimpleType.Double)
				if target:
					v=decimal.Decimal(target.pyValue)
					result.SetFromPyValue(float(v.to_integral(decimal.ROUND_HALF_EVEN)))
			return result
		else:
			raise EvaluationError("round() takes 1 argument, %i given"%len(args))

	def EvaluateFloor(self,args):
		if (len(args)==1):
			try:
				target=self.PromoteParameter(args[0],edm.SimpleType.Decimal)
				result=edm.SimpleValue.NewValue(edm.SimpleType.Decimal)
				if target:
					result.SetFromPyValue(target.pyValue.to_integral(decimal.ROUND_FLOOR))
			except EvaluationError:
				target=self.PromoteParameter(args[0],edm.SimpleType.Double)				
				result=edm.SimpleValue.NewValue(edm.SimpleType.Double)
				if target:
					result.SetFromPyValue(math.floor(target.pyValue))
			return result
		else:
			raise EvaluationError("floor() takes 1 argument, %i given"%len(args))

	def EvaluateCeiling(self,args):
		if (len(args)==1):
			try:
				target=self.PromoteParameter(args[0],edm.SimpleType.Decimal)
				result=edm.SimpleValue.NewValue(edm.SimpleType.Decimal)
				if target:
					result.SetFromPyValue(target.pyValue.to_integral(decimal.ROUND_CEILING))
			except EvaluationError:
				target=self.PromoteParameter(args[0],edm.SimpleType.Double)				
				result=edm.SimpleValue.NewValue(edm.SimpleType.Double)
				if target:
					result.SetFromPyValue(math.ceil(target.pyValue))
			return result
		else:
			raise EvaluationError("ceiling() takes 1 argument, %i given"%len(args))


CallExpression.EvalMethod={
	Method.endswith:CallExpression.EvaluateEndswith,
	Method.indexof:CallExpression.EvaluateIndexof,
	Method.replace:CallExpression.EvaluateReplace,
	Method.startswith:CallExpression.EvaluateStartswith,
	Method.tolower:CallExpression.EvaluateTolower,
	Method.toupper:CallExpression.EvaluateToupper,
	Method.trim:CallExpression.EvaluateTrim,
	Method.substring:CallExpression.EvaluateSubstring,
	Method.substringof:CallExpression.EvaluateSubstringof,
	Method.concat:CallExpression.EvaluateConcat,
	Method.length:CallExpression.EvaluateLength,
	Method.year:CallExpression.EvaluateYear,
	Method.month:CallExpression.EvaluateMonth,
	Method.day:CallExpression.EvaluateDay,
	Method.hour:CallExpression.EvaluateHour,
	Method.minute:CallExpression.EvaluateMinute,
	Method.second:CallExpression.EvaluateSecond,
	Method.round:CallExpression.EvaluateRound,
	Method.floor:CallExpression.EvaluateFloor,
	Method.ceiling:CallExpression.EvaluateCeiling
	}

	
class Parser(edm.Parser):
	
	def ParseCommonExpression(self):
		"""Returns a :py:class:`CommonExpression` instance."""
		leftOp=None
		rightOp=None
		opStack=[]
		while True:
			self.ParseWSP()
			value=self.ParseURILiteral()
			if value is not None:
				rightOp=LiteralExpression(value)
			else:
				name=self.ParseSimpleIdentifier()
				if name=="not":
					self.RequireProduction(self.ParseWSP(),"WSP after not")
					rightOp=UnaryExpression(Operator.boolNot)
				elif name=="isof":
					self.ParseWSP()
					rightOp=self.RequireProduction(self.ParseCastLike(Operator.isof,"isof"),"isofExpression")
				elif name=="cast":
					self.ParseWSP()
					rightOp=self.RequireProduction(self.ParseCastLike(Operator.cast,"cast"),"caseExpression")
				elif name is not None:
					self.ParseWSP()
					if self.Match("("):
						methodCall=Method.DecodeValue(name)
						rightOp=self.ParseMethodCallExpression(methodCall)
					else:
						rightOp=PropertyExpression(name)
			if rightOp is None:
				if self.Parse("("):
					rightOp=self.RequireProduction(self.ParseCommonExpression(),"commonExpression inside parenExpression")
					self.RequireProduction(self.Parse(")"),"closing bracket in parenExpression")
				elif self.Parse("-"):
					rightOp=UnaryExpression(Operator.negate)
				elif leftOp:
					# an operator waiting for an operand is an error
					raise ValueError("Expected expression after %s in ...%s"%(Operator.EncodeValue(leftOp.operator),self.Peek(10)))
				else:
					# no common expression found at all
					return None
			# if we already have a (unary) operator, skip the search for a binary operator
			if not isinstance(rightOp,UnaryExpression):
				operand=rightOp
				self.ParseWSP()
				if self.Parse("/"):
					# Member operator is a special case as it isn't a name
					rightOp=BinaryExpression(Operator.member)
				else:
					savePos=self.pos
					name=self.ParseSimpleIdentifier()
					if name is not None:
						try:
							rightOp=BinaryExpression(Operator.DecodeValue(name))
						except ValueError:
							# this is not an operator we recognise
							name=None
							self.SetPos(savePos)
							pass
					# if name is None and (self.MatchOne(",)") or self.MatchEnd()):
					# indicates the end of this common expression
					if name is None:
						while leftOp is not None:
							leftOp.AddOperand(operand)
							operand=leftOp
							if opStack:
								leftOp=opStack.pop()
							else:
								leftOp=None
						return operand
			else:
				operand=None
			# we now have:
			# leftOp (may be None)
			# operand (None only if rightOp is unary)
			# rightOp (an operator expression, never None)
			# next job, determine who binds more tightly, left or right?
			while True:
				if leftOp is None or leftOp<rightOp:
					# bind the operand to the right, in cases of equal precedence we left associate 1+2-3 = (1+2)-3
					if operand is not None:
						rightOp.AddOperand(operand)
					if leftOp is not None:
						opStack.append(leftOp)
					leftOp=rightOp
					rightOp=None
					operand=None
					break
				else:
					# bind the operand to the left
					leftOp.AddOperand(operand)
					operand=leftOp
					if opStack:
						leftOp=opStack.pop()
					else:
						leftOp=None
			
	def ParseMethodCallExpression(self,methodCall):
		method=CallExpression(methodCall)
		self.RequireProduction(self.Parse("("),"opening bracket in methodCallExpression")
		while True:
			self.ParseWSP()
			param=self.RequireProduction(self.ParseCommonExpression(),"methodCall argument")
			method.AddOperand(param)
			self.ParseWSP()
			if self.Parse(","):
				continue
			elif self.Parse(")"):
				break
			else:
				raise ValueError("closing bracket in methodCallExpression")
		return method
		
	def ParseCastLike(self,op,name):
		"""Parses a cast-like expression, including 'isof'."""
		self.ParseWSP()
		if self.Parse("("):
			e=BinaryExpression(op)
			firstParam=self.RequireProduction(self.ParseCommonExpression(),"%s argument"%name)
			e.AddOperand(firstParam)
			self.ParseWSP()
			if self.ParseOne(")"):
				# first parameter omitted
				stringParam=firstParam
			else:
				self.RequireProduction(self.Parse(","),"',' in %s"%name)
				self.ParseWSP()
				stringParam=self.RequireProduction(self.ParseCommonExpression(),"%s argument"%name)
				e.AddOperand(stringParam)
				self.ParseWSP()
				self.RequireProduction(self.Parse(")"),"')' after %s"%name)
			# Final check, the string parameter must be a string literal!
			if not isinstance(stringParam,LiteralExpression) or stringParam.value.typeCode!=edm.SimpleType.String:
				raise ValueError("%s requires string literal")
			return e
		else:
			return None
			
	def ParseWSP(self):
		"""Parses WSP characters, returning the string of WSP parsed or None."""
		result=[]
		while True:
			c=self.ParseOne(" \t")
			if c:
				result.append(c)
			else:
				break
		if result:
			return string.join(result,'')
		else:
			return None
	
	def ParseExpandOption(self):
		"""Parses an expand system query option, returning a list of tuples.
		
		E.g., "A/B,C" returns {'A': {'B'}, 'C': None }"""
		result={}
		while True:
			parent=result
			navPath=self.RequireProduction(self.ParseSimpleIdentifier(),"entityNavProperty")
			if navPath not in parent:
				parent[navPath]=None
			while self.Parse("/"):
				if parent[navPath] is None:
					parent[navPath]={}
				parent=parent[navPath]
				navPath=self.RequireProduction(self.ParseSimpleIdentifier(),"entityNavProperty")
				if navPath not in parent:
					parent[navPath]=None			
			if not self.Parse(","):
				break
		self.RequireEnd("expandQueryOp")
		return result
				
	def ParseOrderbyOption(self):
		"""Parses an orderby system query option, returning a list of 2-tuples.
		
		Each tuple is ( <py:class:`CommonExpression` instance>, 1 | -1 )
		
		The value 1 represents the default ascending order, -1 indicated descending."""
		result=[]
		while True:
			self.ParseWSP()
			e=self.RequireProduction(self.ParseCommonExpression(),"commonExpression")
			self.ParseWSP()
			if self.ParseInsensitive("asc"):
				dir=1
			elif self.ParseInsensitive("desc"):
				dir=-1
			else:
				dir=1
			result.append((e,dir))
			self.ParseWSP()
			if not self.Parse(","):
				break
		self.RequireEnd("orderbyQueryOp")
		return result
				
	def ParseSelectOption(self):
		"""Parses a select system query option, returning a list of tuples.
		
		E.g., "A/*,C" returns [("A","*"),("C")]
		
		This is almost identical to the expand option except that '*"
		and WSP is allowed.
		
		selectQueryOp = "$select=" selectClause
		selectClause = [WSP] selectItem [[WSP] "," selectClause] [WSP]
		selectItem = star / selectedProperty / (selectedNavProperty ["/" selectItem])
		selectedProperty = entityProperty / entityComplexProperty
		selectedNavProperty = entityNavProperty-es / entityNavProperty-et
		star = "*"	"""
		result={}
		while True:
			parent=result
			self.ParseWSP()
			navPath=self.RequireProduction(self.ParseStarOrIdentifier(),"selectItem")
			if navPath not in parent:
				parent[navPath]=None
			while navPath!="*" and self.Parse("/"):
				if parent[navPath] is None:
					parent[navPath]={}
				parent=parent[navPath]
				navPath=self.RequireProduction(self.ParseStarOrIdentifier(),"selectItem")
				if navPath not in parent:
					parent[navPath]=None			
			self.ParseWSP()
			if not self.Parse(","):
				break
		self.RequireEnd("selectQueryOp")
		return result
	
	def ParseStarOrIdentifier(self):
		self.ParseWSP()
		if self.Parse("*"):
			return '*'
		else:
			return self.RequireProduction(self.ParseSimpleIdentifier(),"selectItem")

	SimpleIdentifierStartClass=None
	SimpleIdentifierClass=None
	
	def ParseSimpleIdentifier(self):
		"""Parses a SimpleIdentifier
		
		Although the OData specification simply says that these
		identifiers are *pchar the ABNF is confusing because it relies
		on WSP which can only exist after percent encoding has been
		removed.  There is also the implicit assumption that characters
		that might be confused with operators will be percent-encoded if
		they appear in identifiers, again problematic if percent
		encoding has already been removed.

		Later versions of the specification have clarified this and it
		is clear that identifiers must be parsable after
		percent-decoding.  It's a bit of a moot point though because, in
		reality, the identifiers refer to named objects in the entity
		model and this defines the uncode pattern for identifiers as
		follows::
		
			[\p{L}\p{Nl}][\p{L}\p{Nl}\p{Nd}\p{Mn}\p{Mc}\p{Pc}\p{Cf}]{0,}(\.[\p{L}\p{Nl}][\p{L}\p{Nl}\p{Nd}\p{Mn}\p{Mc}\p{Pc}\p{Cf}]{0,}){0,}

		Although this expression appears complex this is basically a '.'
		separated list of name components, each of which must start with
		a letter and continue with a letter, number or underscore."""
		if self.SimpleIdentifierStartClass is None:
			self.SimpleIdentifierStartClass=CharClass(CharClass.UCDCategory(u"L"))
			self.SimpleIdentifierStartClass.AddClass(CharClass.UCDCategory(u"Nl"))
		if self.SimpleIdentifierClass is None:
			self.SimpleIdentifierClass=CharClass(self.SimpleIdentifierStartClass)
			for c in ['Nd','Mn','Mc','Pc','Cf']:
				self.SimpleIdentifierClass.AddClass(CharClass.UCDCategory(c))
		savePos=self.pos
		result=[]
		while True:
			# each segment must start with a start character
			if self.theChar is None or not self.SimpleIdentifierStartClass.Test(self.theChar):
				self.SetPos(savePos)
				return None
			result.append(self.theChar)
			self.NextChar()
			while self.theChar is not None and self.SimpleIdentifierClass.Test(self.theChar):
				result.append(self.theChar)
				self.NextChar()
			if not self.Parse('.'):
				break
			result.append('.')
		return string.join(result,'')
	
	def ParseStringURILiteral(self):
		if self.Parse("'"):
			# string of utf-8 characters
			result=edm.SimpleValue.NewValue(edm.SimpleType.String)
			value=[]
			while True:
				startPos=self.pos
				while not self.Parse("'"):
					if self.MatchEnd():
						raise ValueError("Unterminated quote in literal string")
					self.NextChar()					
				value.append(self.src[startPos:self.pos-1])
				if self.Parse("'"):
					# a repeated SQUOTE, go around again
					continue
				break
			value=string.join(value,"'")
			if self.raw:
				value=value.decode('utf-8')
			result.pyValue=value
			return result
		else:
			return None
							
	def ParseURILiteral(self):
		"""Returns a :py:class:`pyslet.mc_csdl.SimpleType` instance of None if no value can parsed.
		
		Important: do not confuse a return value of (the Python object)
		None with a
		:py:class:`pyslet.mc_csdl.SimpleValue` instance that tests
		:False.  The latter is
		returned when the URI-literal string 'null' is parsed.
		
		If a URI literal value is partially parsed but is badly formed,
		a ValueError is raised."""
		savePos=self.pos
		if self.ParseInsensitive("null"):
			return edm.SimpleValue.NewValue(None)
		elif self.Match("'"):
			return self.ParseStringURILiteral()
		elif self.MatchOne('-.0123456789'):
			# one of the number forms (perhaps)
			num=self.ParseNumericLiteral()
			if num is None:
				# must be something like "." or "-" on its own, not a literal
				return None
			if self.ParseOne("Dd"):
				result=edm.SimpleValue.NewValue(edm.SimpleType.Double)
				result.SetFromNumericLiteral(num)
				return result
			elif self.ParseOne("Ff"):
				result=edm.SimpleValue.NewValue(edm.SimpleType.Single)
				result.SetFromNumericLiteral(num)
				return result
			elif self.ParseOne("Mm"):
				result=edm.SimpleValue.NewValue(edm.SimpleType.Decimal)
				result.SetFromNumericLiteral(num)
				return result
			elif self.ParseOne("Ll"):
				result=edm.SimpleValue.NewValue(edm.SimpleType.Int64)
				result.SetFromNumericLiteral(num)
				return result
			else:
				result=edm.SimpleValue.NewValue(edm.SimpleType.Int32)
				result.SetFromNumericLiteral(num)
				return result
		elif self.ParseInsensitive("true"):
			result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
			result.pyValue=True
			return result
		elif self.ParseInsensitive("false"):
			result=edm.SimpleValue.NewValue(edm.SimpleType.Boolean)
			result.pyValue=False
			return result
		elif self.ParseInsensitive("datetimeoffset"):
			result=edm.SimpleValue.NewValue(edm.SimpleType.DateTimeOffset)
			production="datetimeoffset literal"
			self.Require("'",production)
			dtoString=self.ParseUntil("'")
			self.Require("'",production)
			result.SetFromLiteral(dtoString)
			return result
		elif self.ParseInsensitive("datetime"):
			production="datetime literal"
			self.Require("'",production)
			result=edm.SimpleValue.NewValue(edm.SimpleType.DateTime)
			value=self.RequireProduction(self.ParseDateTimeLiteral(),production)
			self.Require("'",production)
			result.pyValue=value
			return result
		elif self.ParseInsensitive("time"):
			result=edm.SimpleValue.NewValue(edm.SimpleType.Time)
			self.Require("'","time")
			startPos=self.pos
			while not self.Parse("'"):
				if self.MatchEnd():
					raise ValueError("Unterminated quote in time string")
				self.NextChar()					
			try:
				value=xsi.Duration(self.src[startPos:self.pos-1])
			except iso.DateTimeError,e:
				raise ValueError(str(e))			
			result.pyValue=value
			return result
		elif self.Parse("X") or self.ParseInsensitive("binary"):
			self.Require("'","binary")
			result=edm.SimpleValue.NewValue(edm.SimpleType.Binary)
			value=self.ParseBinaryLiteral()
			self.Require("'","binary literal")
			result.pyValue=value
			return result
		elif self.ParseInsensitive("nan"):
			if self.ParseOne("Dd"):
				result=edm.SimpleValue.NewValue(edm.SimpleType.Double)
				result.SetFromNumericLiteral(edm.Numeric('',"nan",None,'',None))
				return result
			elif self.ParseOne("Ff"):
				result=edm.SimpleValue.NewValue(edm.SimpleType.Single)
				result.SetFromNumericLiteral(edm.Numeric('',"nan",None,'',None))
				return result
			else:
				raise ValueError("Expected double or single Nan: Nan%s"%repr(self.Peek(1)))			
		elif self.ParseInsensitive("inf"):
			if self.ParseOne("Dd"):
				result=edm.SimpleValue.NewValue(edm.SimpleType.Double)
				result.pyValue=float("INF")
				return result
			elif self.ParseOne("Ff"):
				result=edm.SimpleValue.NewValue(edm.SimpleType.Single)
				result.pyValue=float("INF")
				return result
			else:
				raise ValueError("Expected double or single inf: INF%s"%repr(self.Peek(1)))
		elif self.ParseInsensitive("guid"):
			result=edm.SimpleValue.NewValue(edm.SimpleType.Guid)
			self.Require("'","guid")
			hex=[]
			hex.append(self.RequireProduction(self.ParseHexDigits(8,8),"guid"))
			self.Require("-","guid")			
			hex.append(self.RequireProduction(self.ParseHexDigits(4,4),"guid"))
			self.Require("-","guid")			
			hex.append(self.RequireProduction(self.ParseHexDigits(4,4),"guid"))
			self.Require("-","guid")			
			hex.append(self.RequireProduction(self.ParseHexDigits(4,4),"guid"))
			if self.Parse('-'):
				# this is a proper guid
				hex.append(self.RequireProduction(self.ParseHexDigits(12,12),"guid"))
			else:
				# this a broken guid, add some magic to make it right
				hex[3:3]=['FFFF']
				hex.append(self.RequireProduction(self.ParseHexDigits(8,8),"guid"))
			self.Require("'","guid")
			result.pyValue=uuid.UUID(hex=string.join(hex,''))
			return result
		else:
			return None			
			# raise ValueError("Expected literal: %s"%repr(self.Peek(10)))

	
def ParseURILiteral(source):
	"""Parses a literal value from a source string.
	
	Returns a tuple of a:
	
		*	a constant from :py:class:`pyslet.mc_csdl.SimpleType`
		
		*	the value, represented with the closest python built-in type
	
	The special string "null" returns None,None"""
	p=Parser(source)
	return p.RequireProductionEnd(p.ParseURILiteral(),"uri literal")

	
def ParseDataServiceVersion(src):
	"""Parses DataServiceVersion from a header field value.
	
	Returns a triple of (integer) major version, (integer) minor version and a
	user agent string.  See section 2.2.5.3 of the specification."""
	mode="#"
	versionStr=None
	uaStr=[]
	for w in http.SplitWords(src):
		if mode=="#":
			if w[0] in http.HTTP_SEPARATORS:
				break
			else:
				# looking for the digit.digit
				versionStr=w
				mode=';'
		elif mode==';':
			if w[0]==mode:
				mode='u'
			else:
				break
		elif mode=='u':
			if w[0] in http.HTTP_SEPARATORS:
				uaStr=None
				break
			else:
				uaStr.append(w)	
	if versionStr is not None:
		v=versionStr.split('.')
		if len(v)==2 and http.IsDIGITS(v[0]) and http.IsDIGITS(v[1]):
			major=int(v[0])
			minor=int(v[1])
		else:
			versionStr=None
	if versionStr is None:
		raise ValueError("Can't read version number from DataServiceVersion: %s"%src)		
	if uaStr is None:
		raise ValueError("Can't read user agent string from DataServiceVersion: %s"%src)
	return major,minor,string.join(uaStr,' ')	


def ParseMaxDataServiceVersion(src):
	"""Parses MaxDataServiceVersion from a header field value.
	
	Returns a triple of (integer) major version, (integer) minor version and a
	user agent string.  See section 2.2.5.7 of the specification."""
	src2=src.split(';')
	versionStr=None
	uaStr=None
	if len(src2)>0:	
		words=http.SplitWords(src2[0])
		if len(words)==1:
			versionStr=words[0]
	if len(src2)>1:
		uaStr=string.join(src2[1:],';')
	if versionStr is not None:
		v=versionStr.split('.')
		if len(v)==2 and http.IsDIGITS(v[0]) and http.IsDIGITS(v[1]):
			major=int(v[0])
			minor=int(v[1])
		else:
			versionStr=None
	if versionStr is None:
		raise ValueError("Can't read version number from MaxDataServiceVersion: %s"%src)		
	if uaStr is None:
		raise ValueError("Can't read user agent string from MaxDataServiceVersion: %s"%src)
	return major,minor,uaStr	


class SystemQueryOption(xsi.Enumeration):
	"""SystemQueryOption defines constants for the OData-defined system query options
	
	Note that these options are enumerated without their '$' prefix::
		
		SystemQueryOption.filter	
		SystemQueryOption.DEFAULT == None

	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
	decode={
		'expand':1,
		'filter':2,
		'orderby':3,
		'format':4,
		'skip':5,
		'top':6,
		'skiptoken':7,
		'inlinecount':8,
		'select':9
		}

xsi.MakeEnumeration(SystemQueryOption)


class InlineCount(xsi.Enumeration):
	"""inlineCount defines constants for the $inlinecount system query option::
	
		InlineCount.allpages
		InlineCount.none
		InlineCount.DEFAULT == None

	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
	decode={
		'allpages':1,
		'none':2
		}
xsi.MakeEnumeration(InlineCount)


class PathOption(xsi.Enumeration):
	"""PathOption defines constants for the $-special values that might
	be found in the resource path, for example::
	
		PathOption.links
		PathOption.DEFAULT == None

	Note that these options are mutually exclusive!
	
	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
	decode={
		'metadata':1,
		'batch':2,
		'count':3,
		'value':4,
		'links':5
		}
xsi.MakeEnumeration(PathOption)

#	URI1: http://host/service.svc/Customers	:	Entity Set
#	URI2: http://host/service.svc/Customers('ALFKI')	:	Entity
#	URI3: http://host/service.svc/Customers('ALFKI')/Address	:	Complex Property
#	URI4: http://host/service.svc/Customers('ALFKI')/Address/Name	:	Complex+Simple Property
#			http://host/service.svc/Customers('ALFKI')/Address/Name/$value
#	URI5: http://host/service.svc/Customers('ALFKI')/CompanyName	:	Simple Property
#			http://host/service.svc/Customers('ALFKI')/CompanyName/$value
#	URI6: http://host/service.svc/Customers('ALFKI')/Orders	:	Navigation property
#	URI7: http://host/service.svc/Customers('ALFKI')/$links/Orders	: links
#	URI8: http://host/service.svc/$metadata	:	metadata
#	URI9: http://host/service.svc/$batch	:	batch
#	URI10: http://host/service.svc/EtFunction	: function returning entity
#	URI11: http://host/service.svc/CollCtFunction	: function returning collection of complex
#	URI12: http://host/service.svc/CtFunction	: function returning complex
#	URI13: http://host/service.svc/CollPrimFunction	: function returning collection of simple values
#	URI14: http://host/service.svc/PrimFunction	: function returning simple value
#	URI15: http://host/service.svc/Customers/$count	: count
#	URI16: http://host/service.svc/Customers('ALFKI')/$count	: count=1
#	URI17: http://host/service.svc/Documents(1)/$value	: media resource

SupportedSystemQueryOptions={
	1:set((
		SystemQueryOption.expand,
		SystemQueryOption.filter,
		SystemQueryOption.format,
		SystemQueryOption.orderby,
		SystemQueryOption.skip,
		SystemQueryOption.top,
		SystemQueryOption.skiptoken,
		SystemQueryOption.inlinecount,
		SystemQueryOption.select)),
	2:set((
		SystemQueryOption.expand,
		SystemQueryOption.filter,
		SystemQueryOption.format,
		SystemQueryOption.select)),
	3:set((
		SystemQueryOption.filter,
		SystemQueryOption.format)),
	4:set((
		SystemQueryOption.format,)),
	5:set((
		SystemQueryOption.format,)),
	61:set((
		SystemQueryOption.expand,
		SystemQueryOption.filter,
		SystemQueryOption.format,
		SystemQueryOption.select)),
	62:set((
		SystemQueryOption.expand,
		SystemQueryOption.filter,
		SystemQueryOption.format,
		SystemQueryOption.orderby,
		SystemQueryOption.skip,
		SystemQueryOption.top,
		SystemQueryOption.skiptoken,
		SystemQueryOption.inlinecount,
		SystemQueryOption.select)),
	7:set((
		SystemQueryOption.format,
		SystemQueryOption.skip,
		SystemQueryOption.top,
		SystemQueryOption.skiptoken,
		SystemQueryOption.inlinecount)),
	8:set(),
	9:set(),
	10:set((
		SystemQueryOption.format,)),
	11:set((
		SystemQueryOption.format,)),
	12:set((
		SystemQueryOption.format,)),
	13:set((
		SystemQueryOption.format,)),
	14:set((
		SystemQueryOption.format,)),
	15:set((
		SystemQueryOption.expand,
		SystemQueryOption.filter,	
		SystemQueryOption.orderby,
		SystemQueryOption.skip,
		SystemQueryOption.top)),
	16:set((
		SystemQueryOption.expand,
		SystemQueryOption.filter)),
	17:set((
		SystemQueryOption.format,))
	}
"""A mapping from URI format number to a set of supported system query options.

Note that URI6 is split into 61 and 62 based on the notes in the specification"""


class ODataURI:
	"""Breaks down an OData URI into its component parts.
	
	If the URI passed in is not a valid ODataURI then a
	:py:class:`ServerError` (or a derived exception class) is raised.
	
	You pass the URI (or a string) to construct the object.  You may also pass
	an optional *pathPrefix* which is a string that represents the part of the
	path that will be ignored.  In other words, *pathPrefix* is the path
	component of the service root.

	There's a little bit of confusion as to whether the service root can be
	empty or not.  An empty service root will be automatically converted to '/'
	by the HTTP protocol.  As a result, the service root often appears to
	contain a trailing slash even when it is not empty.  The sample OData server
	from Microsoft issues a temporary redirect from /OData/OData.svc to add the
	trailing slash before returning the service document."""
	
	def __init__(self,dsURI,pathPrefix='',version=2):
		if not isinstance(dsURI,uri.URI):
			dsURI=uri.URIFactory.URI(dsURI)
		self.uri=dsURI					#: a :py:class:`pyslet.rfc2396.URI` instance representing the whole URI
		self.version=version			#: the OData version of this request
		# self.schema=dsURI.scheme
		self.pathPrefix=pathPrefix		#: a string containing the path prefix without a trailing slash
		self.resourcePath=None			#: a string containing the resource path (or None if this is not a resource path)
		self.navPath=[]					#: a list of navigation path segment strings
		self.pathOption=None			#: the path option in effect or None if no path option was given
		self.linksProperty=None			#: the name of the navigation property following $links (no None)
		self.queryOptions=[]			#: a list of raw strings containing custom query options and service op params
		self.sysQueryOptions={}			#: a dictionary mapping :py:class:`SystemQueryOption` constants to their values
		self.paramTable={}
		if dsURI.absPath is None:
			#	relative paths are resolved relative to the pathPrefix with an added slash!
			#	so ODataURI('Products','/OData/OData.svc') is treated as '/OData/OData.svc/Products'
			dsURI=uri.URIFactory.Resolve(pathPrefix+'/',dsURI)
		if dsURI.absPath is None:
			#	both dsURI and pathPrefix are relative, this is an error
			raise ValueError("pathPrefix cannot be relative: %s"%pathPrefix)
		if pathPrefix and not dsURI.absPath.startswith(pathPrefix):
			# this is not a URI we own
			return
		#
		#	Unpack the query
		if dsURI.query is not None:
			rawOptions=dsURI.query.split('&')
			for paramDef in rawOptions:
				if paramDef.startswith('$'):
					paramName=uri.UnescapeData(paramDef[1:paramDef.index('=')]).decode('utf-8')
					param,paramValue=self.ParseSystemQueryOption(paramName,
						uri.UnescapeData(paramDef[paramDef.index('=')+1:]).decode('utf-8'))
					self.sysQueryOptions[param]=paramValue
				else:
					if '=' in paramDef:
						paramName=uri.UnescapeData(paramDef[:paramDef.index('=')]).decode('utf-8')
						self.paramTable[paramName]=len(self.queryOptions)
					self.queryOptions.append(paramDef)
		#
		#	Unpack the resource path
		self.resourcePath=dsURI.absPath[len(pathPrefix):]
		if self.resourcePath=='/':
			self.navPath=[]
		else:
			segments=self.resourcePath.split('/')
			self.navPath=[]
			for segment in segments[1:]:
				if self.pathOption==PathOption.links:
					if self.linksProperty is not None:
						raise InvalidPathOption("A navigation property preceded by $links must be the last path segment, found %s"%segment)
					self.linksProperty=segment					
				elif segment.startswith("$"):
					try:
						pathOption=PathOption.DecodeLowerValue(segment[1:])
					except KeyError:
						raise InvalidPathOption(segment)
					if self.pathOption is not None:
						raise InvalidPathOption("%s must not be used with $%s"%(segment,PathOption.EncodeValue(self.pathOption)))
					if self.navPath and self.pathOption in (PathOption.batch,PathOption.metadata):
						raise InvalidPathOption("$%s must be the only path segment"%PathOption.EncodeValue(self.pathOption))						
					elif self.pathOption==PathOption.links:
						if not self.navPath:
							raise InvalidPathOption("resource path must not start with $links")
					self.pathOption=pathOption
				else:
					# count, value, batch and metadata must be the last segment
					if self.pathOption in (PathOption.count,PathOption.value,PathOption.batch,PathOption.metadata):
						raise InvalidPathOption("$%s must be the last path segment"%PathOption.EncodeValue(self.pathOption))
					self.navPath.append(self.SplitSegment(segment))
			if self.pathOption==PathOption.links and self.linksProperty is None:
				raise InvalidPathOption("$links must not be the last path segment")
		if self.pathOption:
			if self.pathOption==PathOption.links:
				self.ValidateSystemQueryOptions(7)
			elif self.pathOption==PathOption.metadata:
				self.ValidateSystemQueryOptions(8)
			elif self.pathOption==PathOption.batch:
				self.ValidateSystemQueryOptions(9)
			elif self.pathOption==PathOption.count:
				if self.navPath and self.navPath[-1][1]:
					self.ValidateSystemQueryOptions(16)
				else:	
					self.ValidateSystemQueryOptions(15)

	def ParseSystemQueryOption(self,paramName,paramValue):
		"""Returns a tuple of :py:class:`SystemQueryOption` constant and
		an appropriate representation of the value:
		
		*	filter: an instance of :py:class:`CommonExpression`
		
		*	expand: a list of expand options, see py:meth:`pyslet.mc_csdl.Entity.Expand`
		
		*	format: a list of :py:meth:`pyslet:rfc2616.MediaType` instances (of length 1)
		
		*	other options return a the paramValue unchanged at the moment"""
		try:
			param=SystemQueryOption.DecodeValue(paramName)
			# Now parse the parameter value
			paramParser=Parser(paramValue)
			if param==SystemQueryOption.filter:
				value=paramParser.RequireProductionEnd(paramParser.ParseCommonExpression(),"boolCommonExpression")
			elif param==SystemQueryOption.expand:
				value=paramParser.RequireProductionEnd(paramParser.ParseExpandOption(),"expand query option")
			elif param==SystemQueryOption.format:
				# ("json" / "atom" / "xml" / 
				# <a data service specific value indicating a format specific to the specific data service> / 
				# <An IANA-defined [IANA-MMT] content type>)
				# first up, let's see if this is a valid MediaType
				try:
					value=http.AcceptList(paramValue)
				except http.HTTPParameterError:
					pLower=paramValue.lower()
					if pLower=="atom":
						value=http.AcceptList('application/atom+xml')
					elif pLower=="json":
						value=http.AcceptList('application/json')
					elif pLower=="xml":
						value=http.AcceptList('application/xml')
					else:
						raise InvalidSystemQueryOption("Unsupported $format : %s"%paramValue)
			elif param==SystemQueryOption.orderby:
				value=paramParser.RequireProductionEnd(paramParser.ParseOrderbyOption(),"orderby query option")
			elif param==SystemQueryOption.skip:
				value=paramParser.RequireProductionEnd(paramParser.ParseInteger(),"skip query option")
			elif param==SystemQueryOption.top:
				value=paramParser.RequireProductionEnd(paramParser.ParseInteger(),"top query option")
			elif param==SystemQueryOption.inlinecount:
				value=InlineCount.DecodeLowerValue(paramValue)
			elif param==SystemQueryOption.select:
				value=paramParser.RequireProductionEnd(paramParser.ParseSelectOption(),"selection query option")
			else:
				value=paramValue
		except ValueError, e:
			raise InvalidSystemQueryOption("$%s : %s"%(paramName,str(e)))
		return param,value	
	
	def ValidateSystemQueryOptions(self,uriNum):
		rules=SupportedSystemQueryOptions[uriNum]
		for p in self.sysQueryOptions:
			if p not in rules:
				raise InvalidSystemQueryOption('$%s cannot be used with this form of URI'%SystemQueryOption.EncodeValue(p))
		
	def SplitSegment(self,segment):
		"""Splits a string segment into a unicode name and a keyPredicate dictionary."""
		if segment.startswith('$'):
			# some type of control word
			return segment,None
		elif '(' in segment and segment[-1]==')':
			name=uri.UnescapeData(segment[:segment.index('(')]).decode('utf-8')
			keys=segment[segment.index('(')+1:-1]
			if keys=='':
				keys=[]
			else:
				keys=keys.split(',')
			if len(keys)==0:
				return name,{}
			elif len(keys)==1 and '=' not in keys[0]:
				return name,{u'':ParseURILiteral(keys[0])}
			else:
				keyPredicate={}
				for k in keys:
					nv=k.split('=')
					if len(nv)!=2:
						raise ValueError("unrecognized key predicate: %s"%repr(keys))
					kname,value=nv
					kname=uri.UnescapeData(kname).decode('utf-8')
					kvalue=ParseURILiteral(value)
					keyPredicate[kname]=kvalue
				return name,keyPredicate
		else:
			return uri.UnescapeData(segment).decode('utf-8'),None
	
	def GetParamValue(self,paramName):
		if paramName in self.paramTable:
			paramDef=self.queryOptions[self.paramTable[paramName]]
			# must be a primitive type
			return ParseURILiteral(paramDef[paramDef.index('=')+1:])
		else:
			raise KeyError("Missing service operation, or custom parameter: %s"%paramName)

	def GetResource(self,ds=None):
		noNavPath=False
		resource=ds
		for segment in self.navPath:
			name,keyPredicate=segment
			if noNavPath:
				raise BadURISegment(name)
			if isinstance(resource,edmx.DataServices):
				try:
					resource=resource.SearchContainers(name)
				except KeyError,e:
					raise MissingURISegment(str(e))						
				if isinstance(resource,edm.FunctionImport):
					# TODO: grab the params from the query string
					resource=resource.Execute({})
					#	If this does not identify a collection of entities it must be the last path segment
					if not isinstance(resource,edm.EntityCollection):
						noNavPath=True
						# 10-14 have identical constraints, treat them the same
						self.ValidateSystemQueryOptions(10)
				elif isinstance(resource,edm.EntitySet):
					resource=resource.OpenCollection()		
				else:
					# not the right sort of thing
					raise MissingURISegment(name)					
				if isinstance(resource,edm.EntityCollection):						
					if keyPredicate:
						# the keyPredicate can be passed directly as the key
						try:
							es=resource
							resource=es[es.entitySet.GetKey(keyPredicate)]
						except KeyError,e:
							raise MissingURISegment("%s%s"%(name,ODataURI.FormatKeyDict(keyPredicate)))					
				elif resource is None:
					raise MissingURISegment(name)
			elif isinstance(resource,(edm.EntityCollection,edm.FunctionCollection)):
				# bad request, because the collection must be the last thing in the path
				raise BadURISegment("%s since the object's parent is a collection"%name)
			elif isinstance(resource,edm.Entity):
				if name not in resource:
					raise MissingURISegment(name)
				resource=resource[name]
				if isinstance(resource,edm.DeferredValue):
					if keyPredicate:
						try:
							with resource.OpenCollection() as collection:
								resource=collection[resource.entitySet.GetKey(keyPredicate)]
						except KeyError,e:
							raise MissingURISegment(name)
					elif resource.isCollection:
						resource=resource.OpenCollection()
					else:
						resource=resource.GetEntity()
						if resource is None:
							# See the resolution: https://tools.oasis-open.org/issues/browse/ODATA-412
							raise MissingURISegment("%s, no entity is related"%name)					
				elif isinstance(resource,EntityCollection):
					if keyPredicate:
						try:
							resource=resource[resource.entitySet.GetKey(keyPredicate)]
						except KeyError,e:
							raise MissingURISegment(name)
				elif isinstance(resource,Entity):
					if keyPredicate:
						# the key must match that of the entity
						if resource.Key()!=keyPredicate:
							raise MissingURISegment("%s%s"%(name,ODataURI.FormatKeyDict(keyPredicate)))					
			elif isinstance(resource,edm.Complex):
				if name in resource:
					# This is a regular property of the ComplexType
					resource=resource[name]
				else:
					raise MissingURISegment(name)
			else:
				# Any other type is just a property or simple-type
				raise BadURISegment(name)
		if isinstance(resource,edm.EntityCollection):
			self.ValidateSystemQueryOptions(1)	# includes 6 Note 2
		elif isinstance(resource,edm.Entity):
			if self.pathOption==PathOption.value:
				self.ValidateSystemQueryOptions(17)	# media resource value
			elif self.pathOption!=PathOption.links:	
				self.ValidateSystemQueryOptions(2)	# includes 6 Note 1
		elif isinstance(resource,edm.Complex):
			self.ValidateSystemQueryOptions(3)
		elif isinstance(resource,edm.SimpleValue):
			# 4 & 5 are identical
			self.ValidateSystemQueryOptions(4)		
		return resource
	
	@classmethod
	def FormatKeyDict(cls,d):
		"""Returns a URI formatted, but *not* URI escaped, entity key.

		For example, (42L), or ('Salt & Pepper')."""
		if len(d)==1:
			keyStr="(%s)"%cls.FormatLiteral(d.values()[0])
		else:
			keyStr=[]
			for k,v in d:
				keyStr.append("%s=%s"%(k,cls.FormatLiteral(v)))
			keyStr="(%s)"%string.join(keyStr,",")
		return keyStr
	
	@classmethod
	def FormatEntityKey(cls,entity):
		return cls.FormatKeyDict(entity.KeyDict())
			
	@classmethod
	def FormatLiteral(cls,value):
		"""Returns a URI-formatted value.  For example, 42L or 'Paddy%20O''brian'	"""
		if not value:
			return "null"
		else:
			result=unicode(value)
			if value.typeCode==edm.SimpleType.Binary:
				result="X'%s'"%result
			elif value.typeCode==edm.SimpleType.DateTime:
				result="datetime'%s'"%result
			elif value.typeCode==edm.SimpleType.Decimal:
				restul=result+"M"
			elif value.typeCode==edm.SimpleType.Double:
				restul=result+"D"
			elif value.typeCode==edm.SimpleType.Single:
				restul=result+"SF"
			elif value.typeCode==edm.SimpleType.Guid:
				result="guid'%s'"%result
			elif value.typeCode==edm.SimpleType.Int64:
				restul=result+"L"
			elif value.typeCode==edm.SimpleType.Time:
				result="time'%s'"%result
			elif value.typeCode==edm.SimpleType.DateTimeOffset:
				result="datetimeoffset'%s'"%result
			elif value.typeCode==edm.SimpleType.String:
				# double up on single quotes
				result="'%s'"%string.join(result.split("'"),"''")
			return uri.EscapeData(result.encode('utf-8'))
			
			
class ODataElement(xmlns.XMLNSElement):
	"""Base class for all OData specific elements."""
	pass


class Property(ODataElement):
	"""Represents each property value.
	
	The OData namesapce does not define elements in the dataservices space as
	the elements take their names from the properties themselves.  Therefore,
	the xmlname of each Property instance is the property name."""
	
	def __init__(self,parent):
		ODataElement.__init__(self,parent)
		self.edmValue=None		# an :py:class:`pyslet.mc_csdl.EDMValue` instance

	def GetSimpleType(self):
		type=self.GetNSAttribute((ODATA_METADATA_NAMESPACE,'type'))
		if type:			
			try:
				type=edm.SimpleType.DecodeLowerValue(type.lower())
			except ValueError:
				# assume unknown, probably complex		
				type=None
			return type
		else:
			return None
						
	def GetValue(self,value=None):
		"""Gets an appropriately typed value for the property.
		
		Overloads the basic
		:py:meth:`~pyslet.xml20081126.structures.Element.GetValue`
		implementation to transform the value into an
		:py:class:`pyslet.mc_csdl.EDMValue` instance.
		
		An optional :py:class:`pyslet.mc_csdl.EDMValue` can be passed,
		if present the instance's value is updated with the value of
		this Property element."""
		null=self.GetNSAttribute((ODATA_METADATA_NAMESPACE,'null'))
		null=(null and null.lower()=="true")
		if value is None:
			entry=self.FindParent(Entry)
			if entry and entry.entityType:
				propertyDef=entry.entityType.get(self.xmlname,None)
			else:
				propertyDef=None
			if propertyDef:
				value=propertyDef()
			else:
				# picks up top-level properties only! 
				pList=list(self.FindChildrenBreadthFirst(Property,False))
				if pList:
					# we have a complex type with no definition
					value=edm.Complex()
				else:
					type=self.GetSimpleType()
					if type is None:
						# unknown simple types treated as string
						type=edm.SimpleType.String
					value=edm.SimpleValue.NewValue(type,self.xmlname)
		if isinstance(value,edm.SimpleValue):
			if null:
				value.pyValue=None
			else:
				value.SetFromLiteral(ODataElement.GetValue(self))
		else:
			# you can't have a null complex value BTW
			for child in self.GetChildren():
				if isinstance(child,Property):
					if child.xmlname in value:
						child.GetValue(value[child.xmlname])
					else:
						value.AddProperty(child.xmlname,child.GetValue())
		return value

	def SetValue(self,value):
		"""Sets the value of the property
		
		The null property is updated as appropriate.
		
		When changing the value of an existing property we must match
		the existing type.  For new property values we use the value
		type to set the type property."""
		# start with a clean slate, remove attributes too
		self.Reset(True)
		if isinstance(value,edm.SimpleValue):
			if self.parent is None:
				# If we have no parent then we set the type attribute
				self.SetAttribute((ODATA_METADATA_NAMESPACE,'type'),edm.SimpleType.EncodeValue(value.typeCode))				
			if value:
				ODataElement.SetValue(self,unicode(value))
			else:
				self.SetAttribute((ODATA_METADATA_NAMESPACE,'null'),"true")
		elif isinstance(value,edm.Complex):
			type=self.GetNSAttribute((ODATA_METADATA_NAMESPACE,'type'))
			if value.typeDef:
				self.SetAttribute((ODATA_METADATA_NAMESPACE,'type'),value.typeDef.name)
			else:
				raise ValueError("Complex-valued properties must have a defined type") 
			# loop through our children and set them from this value
			for key,v in value.iteritems():
				child=self.ChildElement(self.__class__,(ODATA_DATASERVICES_NAMESPACE,key))
				child.SetValue(v)
		elif value is None:
			# this is a special case, meaning Null
			self.SetAttribute((ODATA_METADATA_NAMESPACE,'null'),"true")
		else:
			raise TypeError("Expected EDMValue instance")

			
class Properties(ODataElement):
	"""Represents the properties element."""
	XMLNAME=(ODATA_METADATA_NAMESPACE,'properties')
	XMLCONTENT=xml.ElementType.ElementContent
	
	PropertyClass=Property
	
	def __init__(self,parent):
		ODataElement.__init__(self,parent)
		self.Property=[]

	def GetChildren(self):
		return itertools.chain(
			self.Property,
			ODataElement.GetChildren(self))


class Collection(ODataElement):
	"""Represents the result of a service operation that returns a collection of values."""
	XMLNAME=(ODATA_METADATA_NAMESPACE,'collection')
			
	def __init__(self,parent):
		ODataElement.__init__(self,parent)
		self.Property=[]

	def GetChildren(self):
		return itertools.chain(
			self.Property,
			ODataElement.GetChildren(self))

		
class Content(atom.Content):
	"""Overrides the default :py:class:`pyslet.rfc4287.Content` class to add OData handling."""
		
	def __init__(self,parent):
		atom.Content.__init__(self,parent)
		self.type='application/xml'
		self.Properties=None		#: the optional properties element containing the entry's property values

	def GetChildren(self):
		for child in atom.Content.GetChildren(self): yield child
		if self.Properties: yield self.Properties


class Feed(atom.Feed):
	"""Overrides the default :py:class:`pyslet.rfc4287.Feed` class to add OData handling."""
		
	def __init__(self,parent,collection=None):
		super(Feed,self).__init__(parent)
		self.collection=collection			#: the collection this feed represents
		if self.collection is not None:
			location=str(self.collection.GetLocation())
			self.AtomId.SetValue(location)
			self.Title.SetValue(self.collection.GetTitle())
			link=self.ChildElement(self.LinkClass)
			link.href=location
			link.rel="self"			
		self.Count=None
	
	def GetChildren(self):
		"""Overridden to add generation of entries dynamically from :py:attr:`collection`.
		
		The collection's
		:py:meth:`pyslet.mc_csdl.EntityCollection.iterpage` method is
		used to iterate over the entities."""
		for child in super(Feed,self).GetChildren(): yield child
		if self.Count:
			yield self.Count
		if self.collection is not None:
			if self.collection.inlineCount:
				count=Count(self)
				count.SetValue(len(self.collection))
				yield count
			for entity in self.collection.iterpage():
				yield Entry(self,entity)
			# add a next link if necessary
			skiptoken=self.collection.NextSkipToken()
			if skiptoken is not None:
				link=Link(self)
				link.rel="next"
				link.href=str(self.collection.GetLocation())+"?$skiptoken=%s"%uri.EscapeData(skiptoken,uri.IsQueryReserved)
				yield link
				

class Inline(ODataElement):
	"""Implements inline handling of expanded links."""
	XMLNAME=(ODATA_METADATA_NAMESPACE,'inline')
	XMLCONTENT=xml.ElementType.ElementContent

	def __init__(self,parent):
		super(Inline,self).__init__(parent)
		self.Feed=None
		self.Entry=None
	
	def GetChildren(self):
		if self.Feed: yield self.Feed
		if self.Entry: yield self.Entry
		for child in super(Inline,self).GetChildren():
			yield child


class Count(ODataElement):
	"""Implements inlinecount handling."""
	XMLNAME=(ODATA_METADATA_NAMESPACE,'count')

	def SetValue(self,newValue):
		super(Count,self).SetValue(str(newValue))
	
	def GetValue(self):
		return int(super(Count,self).GetValue())

				
class Link(atom.Link):
	"""Overrides the default :py:class:`pyslet.rfc4287.Link` class to add OData handling."""	
	XMLCONTENT=xml.ElementType.ElementContent

	def __init__(self,parent):
		super(Link,self).__init__(parent)
		self.Inline=None
		
	def GetChildren(self):
		if self.Inline: yield self.Inline
		for child in super(Link,self).GetChildren(): yield child
	
	def Expand(self,expansion):
		"""Expands this element based on expansion."""
		inline=self.ChildElement(Inline)
		if isinstance(expansion,Entity):
			# it is hard to calculate the id
			entry=inline.ChildElement(Entry)
			entry.SetValue(expansion)
		elif expansion:
			# we only add the feed if it is non-empty
			feed=inline.ChildElement(Feed)
			feed.collection=expansion
			feed.ChildElement(atom.AtomId).SetValue(self.href)


		
class Entry(atom.Entry):
	"""Overrides the default :py:class:`pyslet.rfc4287.Entry` class to add OData handling.
	
	In addition to the default *parent* element an Entry can be passed
	an optional `pyslet.mc_csdl.Entity` instance.  If present, it is
	used to construct the content of the entity.
	
	Finally, if *id* is also passed it is treated as the base URI of the entry and
	used to create the <id> and associated links."""	
	ContentClass=Content
	LinkClass=Link
	
	def __init__(self,parent,entity=None):
		atom.Entry.__init__(self,parent)
		self.entityType=None		#: :py:class:`pyslet.mc_csdl.EntityType` instance describing the entry
		self.Properties=None		#: properties element will be a direct child for media link entries
		self.etag=None				#: the etag associated with this entry or None if optimistic concurrency is not supported
		self._properties={}
		if entity is not None:
			self.SetValue(entity)
	
	def Reset(self):
		if self.Properties:
			self.Properties.DetachFromParent()
			self.Properties=None
		self.etag=None
		self._properties={}
		super(Entry,self).Reset()
		
	def GetChildren(self):
		"""Replaces the implementation in atom.Entry completed so that
		we can put the content last.  You never know, it is possible
		that someone will parse the metadata and properties and decide
		they don't want the content element and close the connection.
		The other way around might be annoying for large media
		resources."""
		for child in atom.Entity.GetChildren(self): yield child
		if self.Published: yield self.Published
		if self.Source: yield self.Source
		if self.Summary: yield self.Summary
		if self.Properties: yield self.Properties
		if self.Content: yield self.Content
		
	def ContentChanged(self):
		atom.Entry.ContentChanged(self)
		self._properties={}
		if self.Content and self.Content.Properties:
			pList=self.Content.Properties
		else:
			pList=self.Properties
		if pList:
			for p in pList.Property:
				self._properties[p.xmlname]=p
			
			
	def __getitem__(self,key):
		"""Enables :py:class:`Entry` to be suffixed with, e.g., ['PropertyName'] to read property values.
		
		Returns the value of the property with *key* as a
		`pyslet.mc_csdl.EDMValue` instance."""
		return self._properties[key].GetValue()

	def __setitem__(self,key,value):
		"""Enables :py:class:`Entry` to be suffixed with, e.g., ['PropertyName'] to set property values.
		
		Sets the property *key* to *value*.  See
		:py:meth:`Property.SetValue` for more information."""
		if key in self._properties:
			p=self._properties[key].SetValue(value)
		else:
			if self.Properties is None:
				ps=self.ChildElement(self.ContentClass).ChildElement(Properties)
			else:
				ps=self.Properties
			p=ps.ChildElement(ps.PropertyClass,(ODATA_DATASERVICES_NAMESPACE,key))
			p.SetValue(value)
			self._properties[key]=p

#	def GetLink(self,linkTitle):
#		"""Returns a tuple of (linkURI,inline)
#		
#		*	linkURI is the URI of the link
#		
#		*	inline is the inline representation of the link (or None)
#		
#		*inline* is either a Feed or Entry instance."""
#		warnings.warn("Entry.GetLink is deprecated due to lack of uniqueness", DeprecationWarning, stacklevel=3)
#		for l in self.Link:
#			if l.title==linkTitle:
#				# This is the link we are interested in
#				if l.Inline:
#					# we have an inline representation
#					if l.Inline.Feed:
#						return l.href,l.Inline.Feed
#					elif l.Inline.Entry:
#						return l.href,l.Inline.Entry
#					else:				
#						return l.href,None
#				else:
#					raise KeyError("Unexpanded link: %s"%linkTitle)	
#		raise KeyError("Missing link: %s"%linkTitle)
	
	def ResolveTargetPath(self,targetPath,prefix,ns):
		doc=self.GetDocument()
		targetElement=self
		for eName in targetPath:
			newTargetElement=None
			for eTest in targetElement.GetChildren():
				if eTest.GetXMLName()==eName:
					newTargetElement=eTest
					break
			if newTargetElement is None:
				# we need to create a new element
				eClass=targetElement.GetElementClass(eName)
				if eClass is None and doc:
					eClass=doc.GetElementClass(eName)
				if eClass is None:
					eClass=Document.GetElementClass(eName)
				newTargetElement=targetElement.ChildElement(eClass,eName)
				if eName[0]==ns and newTargetElement.GetPrefix(eName[0]) is None:
					# No prefix exists for this namespace, make one
					newTargetElement.MakePrefix(ns,prefix)
			targetElement=newTargetElement
		return targetElement
	
	def GetValue(self,entity,entityResolver=None):
		"""Update *entity* to reflect the value of this Entry.
		
		*entity* must be an existing :py:class:`pyslet.mc_csdl.Entity`
		instance.  It is required but is also returned for consistency
		with the behaviour of the overridden method.
		
		The optional entityResolver is a callable that accepts a single
		parameter of type :py:class:`pyslet.rfc2396.URI` and returns a
		an object representing the resource it points to."""
		for k,v in entity.DataItems():
			# catch property-level feed customisation here
			propertyDef=entity.typeDef[k]
			targetPath=propertyDef.GetTargetPath()
			if targetPath and not propertyDef.KeepInContent():
				# This value needs to be read from somewhere special
				prefix,ns=propertyDef.GetFCNsPrefix()
				targetElement=self.ResolveTargetPath(targetPath,prefix,ns)
				# now we need to grab the actual value, only interested in data
				data=[]
				for child in targetElement.GetChildren():
					if type(child) in StringTypes:
						data.append(child)
				v.SetFromLiteral(string.join(data,''))
			else:
				# and watch out for unselected properties
				if k in self._properties:
					self._properties[k].GetValue(v)
				else:
					v.SetFromPyValue(None)
		if entity.exists==False:
			# we need to look for any link bindings
			for link in self.Link:
				if not link.rel.startswith(ODATA_RELATED):
					continue
				navProperty=link.rel[len(ODATA_RELATED):]
				if not entity.IsNavigationProperty(navProperty):
					continue
				targetSet=entity.entitySet.NavigationTarget(navProperty)
				# we have a navigation property we understand
				if link.Inline is not None:
					with targetSet.OpenCollection() as collection:
						if entity.IsEntityCollection(navProperty):
							for entry in link.Inline.Feed.FindChildrenDepthFirst(Entry,subMatch=False):
								# create a new entity from the target entity set
								targetEntity=collection.NewEntity()
								entry.GetValue(targetEntity,entityResolver)
								entity.BindEntity(navProperty,targetEntity)
						elif link.Inline.Entry is not None:
							targetEntity=collection.NewEntity()
							link.Inline.Entry.GetValue(targetEntity,entityResolver)								
							entity.BindEntity(navProperty,targetEntity)
				elif entityResolver is not None:
					#	this is the tricky bit, we need to resolve
					#	the URI to an entity key
					href=link.ResolveURI(link.href)
					if not href.IsAbsolute():
						#	we'll assume that the base URI is the
						#	location of this entity once it is
						#	created.  Witness this thread:
						#	http://lists.w3.org/Archives/Public/ietf-http-wg/2012OctDec/0122.html
						href=uri.URIFactory.Resolve(entity.GetLocation(),href)
					targetEntity=entityResolver(href)
					if isinstance(targetEntity,Entity) and targetEntity.entitySet is targetSet:
						entity.BindEntity(navProperty,targetEntity)
					else:
						raise InvalidData("Resource is not a valid target for %s: %s"%(navProperty,str(href))) 
				else:
					raise InvalidData("No context to resolve entity URI: %s"%str(link.href)) 
		return entity
				
	def SetValue(self,entity):
		"""Sets the value of this Entry to represent *entity*, a :py:class:`pyslet.mc_csdl.Entity` instance."""
		# start with a reset
		self.Reset()
		mediaLinkResource=entity.typeDef.HasStream()
		self.etag=entity.ETag()
		# Now set the new property values, starting with entity-type level feed customisation
		# seems odd that there can only be one of these but, hey...
		cat=self.ChildElement(atom.Category)
		cat.term=entity.typeDef.GetFQName()
		cat.scheme=ODATA_SCHEME
		targetPath=entity.typeDef.GetTargetPath()
		if targetPath:
			prefix,ns=entity.typeDef.GetFCNsPrefix()
			targetElement=self.ResolveTargetPath(targetPath,prefix,ns)
			sourcePath=entity.typeDef.GetSourcePath()
			if sourcePath:
				v=entity
				for p in sourcePath:
					if isinstance(v,(edm.Entity,edm.Complex)):
						v=v[p]
					else:
						v=None
						break
				if isinstance(v,edm.SimpleValue) and v:
					targetElement.AddData(unicode(v))
		# now do the links
		location=str(entity.GetLocation())
		self.ChildElement(atom.AtomId).SetValue(location)
		if entity.exists:
			# we have no way of knowing if we are read or read/write at this stage
			link=self.ChildElement(self.LinkClass)
			link.href=location
			link.rel="edit"
			if mediaLinkResource:
				link=self.ChildElement(self.LinkClass)
				link.href=location+"/$value"
				link.rel="edit-media"
				if self.etag:
					s="" if entity.ETagIsStrong() else "W/"
					link.SetAttribute((ODATA_METADATA_NAMESPACE,'etag'),s+http.QuoteString(ODataURI.FormatLiteral(self.etag)))
			for navProperty in entity.NavigationKeys():
				link=self.ChildElement(self.LinkClass)
				link.href=location+'/'+navProperty
				link.rel=ODATA_RELATED+navProperty
				link.title=navProperty
				if entity.IsEntityCollection(navProperty):
					link.type=ODATA_RELATED_FEED_TYPE
				else:
					link.type=ODATA_RELATED_ENTRY_TYPE
				if entity.Expanded(navProperty):
					# This property has been expanded
					if entity.IsEntityCollection(navProperty):
						link.Expand(entity[navProperty].OpenCollection())
					else:
						link.Expand(entity[navProperty].GetEntity())
		else:
			for navProperty,bindings in entity.bindings.items():
				# we need to know the location of the target entity set
				targetSet=entity.entitySet.NavigationTarget(navProperty)
				feed=[]
				for binding in bindings:
					if isinstance(binding,Entity):
						if binding.exists:
							href=str(targetSet.GetLocation())+uri.EscapeData(ODataURI.FormatEntityKey(binding))
						else:
							# add to the feed
							feed.append(binding)
							continue
					else:
						href=str(targetSet.GetLocation())+uri.EscapeData(ODataURI.FormatKeyDict(targetSet.GetKeyDict(binding)))
					link=self.ChildElement(self.LinkClass)
					link.rel=ODATA_RELATED+navProperty
					link.title=navProperty
					link.href=href
				if feed:
					feed=DeepInsertCollection(navProperty,entity.entitySet,targetSet,feed)
					link=self.ChildElement(self.LinkClass)
					link.rel=ODATA_RELATED+navProperty
					link.title=navProperty
					link.href=location+'/'+navProperty
					link.Expand(feed)
		# Now set the new property values in the properties element
		if mediaLinkResource:
			self.ChildElement(Properties)
		else:
			self.ChildElement(Content).ChildElement(Properties)
		for k,v in entity.DataItems():
			# catch property-level feed customisation here
			propertyDef=entity.typeDef[k]
			targetPath=propertyDef.GetTargetPath()
			if targetPath:
				# This value needs to go somewhere special
				prefix,ns=propertyDef.GetFCNsPrefix()
				targetElement=self.ResolveTargetPath(targetPath,prefix,ns)
				if v:
					targetElement.AddData(unicode(v))
				if not propertyDef.KeepInContent():
					continue
			# and watch out for unselected properties
			if entity.Selected(k):
				self[k]=v
		self.ContentChanged()


class URI(ODataElement):
	"""Represents a single URI in the XML-response to $links requests"""
	XMLNAME=(ODATA_DATASERVICES_NAMESPACE,'uri')
	

class Links(ODataElement):
	"""Represents a list of links in the XML-response to $links requests"""
	XMLNAME=(ODATA_DATASERVICES_NAMESPACE,'links')
	
	def __init__(self,parent):
		ODataElement.__init__(self,parent)
		self.URI=[]

	def GetChildren(self):
		return itertools.chain(
			self.URI,
			ODataElement.GetChildren(self))


class Entity(edm.Entity):
	"""We override Entity in order to provide some documented signatures
	for sets of media-stream entities."""
	
#	def CreateProperty(self,p):
#		"""Overridden to add handling of media type annotations on simple values"""
#		value=p()
#		try:
#			if isinstance(value,edm.SimpleValue):
#				value.mType=http.MediaType(p.GetAttribute(MimeType))
#		except KeyError:
#			pass
#		self.data[p.name]=value

	def GetLocation(self):
		return str(self.entitySet.GetLocation())+uri.EscapeData(ODataURI.FormatEntityKey(self))
		
	def GetStreamType(self):
		"""Returns the content type of the entity's media stream.
		
		Must return a :py:class:`pyslet.rfc2616.MediaType` instance."""
		raise NotImplementedError
			
	def GetStreamSize(self):
		"""Returns the size of the entity's media stream in bytes."""
		raise NotImplementedError
		
	def GetStreamGenerator(self):
		"""A generator function that yields blocks (strings) of data from the entity's media stream."""
		raise NotImplementedError

	def SetStreamFromGenerator(self,streamType,src):
		"""Replaces the contents of this stream with the strings output
		by iterating over src.

		*streamType* must be a :py:class:`pyslet.rfc2616.MediaType`
		instance."""
		raise NotImplementedError
				
	def SetFromJSONObject(self,obj,entityResolver=None):
		"""Sets the value of this entity from a dictionary parsed from a
		JSON representation."""
		for k,v in self.DataItems():
			if k in obj:
				if isinstance(v,edm.SimpleValue):
					JSONToSimpleValue(v,obj.get(k,None))
				else:
					# assume a complex value then
					JSONToComplex(v,obj.get(k,None))
			else:
				v.SetFromPyValue(None)
		if self.exists==False:
			# we need to look for any link bindings
			for navProperty in self.NavigationKeys():
				if navProperty not in obj:
					continue
				links=obj[navProperty]
				if not self.IsEntityCollection(navProperty):
					# wrap singletons for convenience
					links=(links,)
				targetSet=self.entitySet.NavigationTarget(navProperty)
				with targetSet.OpenCollection() as collection:
					for link in links:
						if len(link)==1 and '__metadata' in link:
							# bind to an existing entity
							href=uri.URIFactory.URI(link['__metadata']['uri'])
							if entityResolver is not None:
								if not href.IsAbsolute():
									#	we'll assume that the base URI is the
									#	location of this entity once it is
									#	created.  Witness this thread:
									#	http://lists.w3.org/Archives/Public/ietf-http-wg/2012OctDec/0122.html
									href=uri.URIFactory.Resolve(self.GetLocation(),href)
								targetEntity=entityResolver(href)
								if isinstance(targetEntity,Entity) and targetEntity.entitySet is targetSet:
									self.BindEntity(navProperty,targetEntity)
								else:
									raise InvalidData("Resource is not a valid target for %s: %s"%(navProperty,str(href))) 
							else:
								raise InvalidData("No context to resolve entity URI: %s"%str(link))						
						else:
							# full inline representation is expected for deep insert
							targetEntity=collection.NewEntity()
							targetEntity.SetFromJSONObject(link,entityResolver)
							self.BindEntity(navProperty,targetEntity)
		
	def GenerateEntityTypeInJSON(self,version=2):
		location=self.GetLocation()
		mediaLinkResource=self.typeDef.HasStream()
		yield '{"__metadata":{'
		yield '"uri":%s'%json.dumps(location)
		yield ',"type":%s'%json.dumps(self.entitySet.entityType.GetFQName())
		etag=self.ETag()
		if etag:
			s="" if self.ETagIsStrong() else "W/"
			yield ',"etag":%s'%json.dumps(s+http.QuoteString(ODataURI.FormatLiteral(etag)))
		if mediaLinkResource:
			yield ',"media_src":%s'%json.dumps(location+"/$value")
			yield ',"content_type":%s'%json.dumps(str(self.GetStreamType()))
			yield ',"edit_media":%s'%json.dumps(location+"/$value")
			if etag:
				s="" if self.ETagIsStrong() else "W/"
				yield ',"media_etag":%s'%json.dumps(s+http.QuoteString(ODataURI.FormatLiteral(etag)))			
		yield '}'
		for k,v in self.DataItems():
			# watch out for unselected properties
			if self.Selected(k):
				yield ','
				if isinstance(v,edm.SimpleValue):
					yield EntityPropertyInJSON(v)
				else:
					yield EntityCTBody(v)
		if self.exists:
			for navProperty in self.NavigationKeys():
				if self.Selected(navProperty):
					yield ', %s'%json.dumps(navProperty)
					if self.Expanded(navProperty):
						yield ':'
						if self.IsEntityCollection(navProperty):
							with self[navProperty].OpenCollection() as collection:
								for y in collection.GenerateEntitySetInJSON(version):
									yield y
						else:
							entity=self[navProperty].GetEntity()
							if entity:
								for y in entity.GenerateEntityTypeInJSON(version):
									yield y
							else:
								yield json.dumps(None)
					else:
						yield ':{"__deferred":{"uri":%s}}'%json.dumps(location+'/'+navProperty)
		else:
			for navProperty,bindings in self.bindings.items():
				# we need to know the location of the target entity set
				targetSet=self.entitySet.NavigationTarget(navProperty)
				yield ', %s :['%json.dumps(navProperty)
				sep=False
				for binding in bindings:
					if sep:
						yield ', '
					else:
						sep=True
					if isinstance(binding,Entity):
						href=str(targetSet.GetLocation())+uri.EscapeData(ODataURI.FormatEntityKey(binding))
					else:
						href=str(targetSet.GetLocation())+uri.EscapeData(ODataURI.FormatKeyDict(targetSet.GetKeyDict(binding)))
					yield '{ "__metadata":{"uri":%s}}'%json.dumps(href)
				yield ']'
		yield '}'
					

def EntityCTInJSON2(complexValue):
	"""Return a version 2 JSON complex entity."""
	return '{"results":%s}'%EntityCTInJSON(complexValue)
	
def EntityCTInJSON(complexValue):
	"""Return a version 1 JSON complex entity - specification seems to be incorrect here."""
	return '{%s}'%EntityCTBody(complexValue)

def EntityCTBody(complexValue):
	return "%s:%s"%(json.dumps(complexValue.name),EntityCTValueToJSON(complexValue))


def EntityCTValueToJSON(complexValue):
	result=[]
	for k,v in complexValue.iteritems():
		if isinstance(v,edm.SimpleValue):
			value=EntityPropertyInJSON(v)
		else:
			value=EntityCTBody(v)
		result.append(value)
	return "{%s}"%string.join(result,',')
	

def JSONToComplex(complexValue,obj):
	if obj is None:
		# do nothing - essentially means a merge
		return
	if "results" in obj and type(obj["results"])==DictType:
		obj=obj["results"]
	for k,v in complexValue.iteritems():
		if k in obj:
			if isinstance(v,edm.SimpleValue):
				JSONToSimpleValue(v,obj.get(k,None))
			else:
				# assume a complex value then
				JSONToComplex(v,obj.get(k,None))
		else:
			v.SetFromPyValue(None)
	

TICKS_PER_DAY=86400000
BASE_DAY=iso.Date('1970-01-01').GetAbsoluteDay()

def EntityPropertyInJSON2(simpleValue):			
	"""Return a version 2 JSON simple value."""
	return '{"results":{%s}}'%EntityPropertyInJSON(simpleValue)

def EntityPropertyInJSON(simpleValue):
	return "%s:%s"%(json.dumps(simpleValue.name),EntityPropertyValueInJSON(simpleValue))

def EntityPropertyValueInJSON(v):
	if not v:
		return 'null'
	elif isinstance(v,edm.BinaryValue):
		# unusual representation as we use base64 encoding
		return json.dumps(base64.b64encode(v.pyValue))
	elif isinstance(v,(edm.BooleanValue,edm.ByteValue,edm.Int16Value,edm.Int32Value,edm.SByteValue)):
		# naked representation
		return unicode(v)
	elif isinstance(v,edm.DateTimeValue):
		# a strange format based on ticks, by definition, DateTime has no offset
		ticks=(v.pyValue.date.GetAbsoluteDay()-BASE_DAY)*TICKS_PER_DAY+int(v.pyValue.time.GetSeconds()*1000)
		return json.dumps("/Date(%i)/"%ticks)
	elif isinstance(v,(edm.DecimalValue,edm.DoubleValue,edm.GuidValue,edm.Int64Value,edm.SingleValue,edm.StringValue,edm.TimeValue)):
		# just use the literal form as a json string
		return json.dumps(unicode(v))
	elif isinstance(v,(edm.DateTimeOffsetValue)):
		# a strange format based on ticks, by definition, DateTime has no offset
		ticks=(v.pyValue.date.GetAbsoluteDay()-BASE_DAY)*TICKS_PER_DAY+int(v.pyValue.time.GetSeconds()*1000)
		dir,offset=v.GetZone()
		if dir>0:
			s=u"+"
		else:
			s=u"-"
		return json.dumps("/Date(%i%s%04i)/"%(ticks,s,offset))
	else:
		raise ValueError("SimpleValue: %s"%repr(v))
	
def JSONToSimpleValue(v,jsonValue):
	"""Given a simple property value parsed from a json representation,
	*jsonValue* and a :py:class:`SimpleValue` instance, *v*, update *v*
	to reflect the parsed value."""
	if jsonValue is None:
		v.SetFromPyValue(None)
	elif isinstance(v,edm.BinaryValue):
		v.SetFromPyValue(base64.b64decode(jsonValue))
	elif isinstance(v,(edm.BooleanValue,edm.ByteValue,edm.Int16Value,edm.Int32Value,edm.SByteValue)):
		v.SetFromPyValue(jsonValue)
	elif isinstance(v,edm.DateTimeValue):
		tp=iso.TimePoint()
		if jsonValue.startswith("/Date(") and jsonValue.endswith(")/"):
			ticks=int(jsonValue[6:-2])
			absoluteDay=BASE_DAY+tp.time.SetSeconds(ticks/1000.0)
			tp.date.SetAbsoluteDay(absoluteDay)
			v.SetFromPyValue(tp)
		else:
			raise ValueError("Illegal value for DateTime: %s"%jsonValue)		
	elif isinstance(v,(edm.DecimalValue,edm.DoubleValue,edm.GuidValue,edm.Int64Value,edm.SingleValue,edm.StringValue,edm.TimeValue)):
		# just use the literal form as a json string
		v.SetFromLiteral(jsonValue)
	elif isinstance(v,(edm.DateTimeOffsetValue)):
		tp=iso.TimePoint()
		if jsonValue.startswith("/Date(") and jsonValue.endswith(")/"):
			ticks=int(jsonValue[6:-2])
			if '+' in ticks:
				# split by +
				ticks=ticks.split('+')
				zDir=1
			elif '-' in ticks:
				# split by -
				ticks=ticks.split('-')
				zDir=-1
			else:
				zDir=0
			if zDir:
				if len(ticks)!=2:
					raise ValueError("Illegal value for DateTimeOffset: %s"%jsonValue)
				zOffset=int(ticks[1])
			else:
				zOffset=0	
			absoluteDay=BASE_DAY+tp.time.SetSeconds(int(ticks[0])/1000.0)
			tp.date.SetAbsoluteDay(absoluteDay)
			tp.SetZone(zDir,zOffset//60,zOffset%60)
			v.SetFromPyValue(tp)			
		else:
			raise ValueError("Illegal value for DateTimeOffset: %s"%jsonValue)			
	else:
		raise ValueError("Expected SimpleValue: %s"%repr(v))
			
		
class EntityCollectionMixin(object):
	"""A mix-in for EntityCollections to provide OData-specific options."""

	def NewEntity(self,autoKey=False):
		"""Returns an OData aware instance"""
		return Entity(self.entitySet)	
	
	def IsMediaLinkEntryCollection(self):
		"""Returns True if this is a collection of Media-Link Entries"""
		return self.entitySet.entityType.HasStream()
		
	def CheckFilter(self,entity):
		"""Checks *entity* against any filter and returns True if it passes.
		
		The *filter* object must be an instance of
		py:class:`CommonExpression` that returns a Boolean value.

		*boolExpression* is a :py:class:`CommonExpression`.  """
		if self.filter is None:
			return True
		else:
			result=self.filter.Evaluate(entity)
			if isinstance(result,edm.BooleanValue):
				return result.pyValue==True			#: NULL treated as False
			else:
				raise ValueError("Boolean required for filter expression") 
	
	def CalculateOrderKey(self,entity,orderObject):
		"""Evaluates orderObject as an instance of py:class:`CommonExpression`."""
		return orderObject.Evaluate(entity).pyValue		

	def GenerateEntitySetInJSON(self,version=2):
		"""Generates JSON serialised form of this collection."""
		if version<2:
			yield "["
		else:
			yield "{"
			if self.inlineCount:
				yield '"__count":%s,'%json.dumps(len(self))
			yield '"results":['
		sep=False
		for entity in self.iterpage():
			if not sep:
				sep=True
			else:
				yield ','
			for s in entity.GenerateEntityTypeInJSON(version):
				yield s
		if version<2:
			yield "]"
		else:
			# add a next link if necessary
			skiptoken=self.NextSkipToken()
			if skiptoken is not None:
				yield '],"__next":{"uri":%s}}'%json.dumps(str(self.GetLocation())+
					"?$skiptoken=%s"%uri.EscapeData(skiptoken,uri.IsQueryReserved))
			else:
				yield ']}'		

	def GenerateLinkCollJSON(self,version=2):
		"""Generates JSON serialised collection of links"""
		if version<2:
			yield "["
		else:
			yield "{"
			if self.inlineCount:
				yield '"__count":%s,'%json.dumps(len(self))
			yield '"results":['
		sep=False
		for entity in self.iterpage():
			if not sep:
				sep=True
			else:
				yield ','
			yield '{"uri":%s}'%json.dumps(entity.GetLocation())
		if version<2:
			yield "]"
		else:
			# add a next link if necessary
			skiptoken=self.NextSkipToken()
			if skiptoken is not None:
				yield '],"__next":{"uri":%s}}'%json.dumps(str(self.GetLocation())+
					"?$skiptoken=%s"%uri.EscapeData(skiptoken,uri.IsQueryReserved))
			else:
				yield ']}'		
			
class EntityCollection(EntityCollectionMixin,edm.EntityCollection):
	"""We override EntityCollection in order to provide OData-specific options."""

	def __init__(self,entitySet):
		edm.EntityCollection.__init__(self,entitySet)
		EntityCollectionMixin.__init__(self)


class NavigationEntityCollection(EntityCollectionMixin,edm.NavigationEntityCollection):
	"""We override NavigationEntityCollection in order to provide OData-specific options."""

	def __init__(self,name,fromEntity,toEnd):
		edm.NavigationEntityCollection.__init__(self,name,fromEntity,toEnd)
		EntityCollectionMixin.__init__(self)
		
	def GetLocation(self):
		"""Returns the location of this collection as a
		:py:class:`rfc2396.URI` instance.
		
		We override the location based on the source entity set + the fromKey."""
		return uri.URIFactory.URI(string.join([
			str(self.fromEntity.GetLocation()),
			'/',
			uri.EscapeData(self.name)],''))

	def GetTitle(self):
		return self.name


class DeepInsertCollection(NavigationEntityCollection):
	
	def __init__(self,name,fromEntity,toEnd,insertList):
		super(DeepInsertCollection,self).__init__(name,fromEntity,toEnd)
		self.insertList=insertList
	
	def itervalues(self):
		for entity in self.insertList:
			yield entity
	
		
class FunctionEntityCollection(EntityCollectionMixin,edm.FunctionEntityCollection):
	"""We override FunctionEntityCollection in order to provide OData-specific options."""

	def __init__(self,function,params):
		edm.FunctionEntityCollection.__init__(self,function,params)
		EntityCollectionMixin.__init__(self)


class FunctionCollection(edm.FunctionCollection):
	"""We override FunctionCollection in order to provide OData-specific options."""

	def GenerateCollectionInJSON(self,version=2):
		"""Generates JSON serialised form of this collection."""
		if version<2:
			yield "["
		else:
			yield "{"
			yield '"results":['
		sep=False
		for value in self:
			if not sep:
				sep=True
			else:
				yield ','
			if isinstance(value,edm.SimpleValue):
				yield EntityPropertyValueInJSON(value)
			else:
				yield EntityCTValueToJSON(value)
		if version<2:
			yield "]"
		else:
			yield ']}'		
	
					
class Client(app.Client):
	"""An OData client.
	
	Can be constructed with an optional URL specifying the service root of an
	OData service."""
	
	def __init__(self,serviceRoot=None):
		app.Client.__init__(self)
		self.SetLog(http.HTTP_LOG_ERROR,sys.stdout)
		self.feeds=[]		#: a list of feeds associated with this client
		self.feedTitles={}	#: a dictionary of feed titles, mapped to collection URLs
		self.schemas={}		#: a dictionary of namespaces mapped to Schema instances
		self.pageSize=None
		"""the default number of entries to retrieve with each request
		
		None indicates no restriction, request all entries."""		
		if serviceRoot:
			self.SetService(serviceRoot)
		else:
			self.serviceRoot=None	#: the URI of the service root
		# Initialise a simple cache of type name -> EntityType definition
		self._cacheTerm=None
		self._cacheType=None
		
	def SetService(self,serviceRoot):
		"""Adds the feeds defined by the URL *serviceRoot* to this client."""
		self.feeds=[]
		self.feedTitles={}
		self.schems={}
		doc=Document(baseURI=serviceRoot,reqManager=self)
		doc.Read()
		if isinstance(doc.root,app.Service):
			for w in doc.root.Workspace:
				for f in w.Collection:
					url=f.GetFeedURL()
					if f.Title:
						self.feedTitles[f.Title.GetValue()]=url
					self.feeds.append(url)
		else:
			raise InvalidServiceDocument(str(serviceRoot))
		metadata=uri.URIFactory.Resolve(serviceRoot,'$metadata')
		doc=edmx.Document(baseURI=metadata,reqManager=self)
		try:
			doc.Read()
			if isinstance(doc.root,edmx.Edmx):
				for s in doc.root.DataServices.Schema:
					self.schemas[s.name]=s
		except xml.XMLError:
			# Failed to read the metadata document, there may not be one of course
			pass
		# reset the cache
		self._cacheTerm=None
		self._cacheType=None
		self.serviceRoot=uri.URIFactory.URI(serviceRoot)

	def LookupEntityType(self,entityTypeName):
		"""Returns the :py:class:`EntityType` instance associated with the fully qualified *entityTypeName*"""
		entityType=None
		if entityTypeName==self._cacheTerm:
			# time saver as most feeds are just lists of the same type
			entityType=self._cacheType
		else:
			name=entityTypeName.split('.')
			if name[0] in self.schemas:
				try:
					entityType=self.schemas[name[0]][string.join(name[1:],'.')]
				except KeyError:
					pass
			# we cache both positive and negative results
			self._cacheTerm=entityTypeName
			self._cacheType=entityType
		return entityType

	def AssociateEntityType(self,entry):
		for c in entry.Category:
			entry.entityType=None
			if c.scheme==ODATA_SCHEME and c.term:
				entry.entityType=self.LookupEntityType(c.term)
			
	def RetrieveFeed(self,feedURL,odataQuery=None):
		"""Given a feed URL, returns a :py:class:`pyslet.rfc4287.Feed` object representing it."""
		doc=Document(baseURI=self._AddParams(feedURL,odataQuery),reqManager=self)
		doc.Read()
		if isinstance(doc.root,atom.Feed):
			for e in doc.root.Entry:
				self.AssociateEntityType(e)
			return doc.root
		else:
			raise InvalidFeedDocument(str(feedURL))
	
	def RetrieveEntries(self,feedURL,odataQuery=None):
		"""Given a feed URL, returns an iterable yielding :py:class:`Entry` instances.
		
		This method uses the :py:attr:`pageSize` attribute to set the paging of
		the data.  (The source may restrict the number of return values too). 
		It hides the details required to iterate through the entire list of
		entries with the caveat that there is no guarantee that the results will
		be consistent.  If the data source is being updated or reconfigured it
		is possible that the some entries may be skipped or duplicated as a result
		of being returned by different HTTP requests."""
		if self.pageSize:
			skip=0
			page=self.pageSize
		else:
			skip=page=None
		if odataQuery is None:
			odataQuery={}
		while True:
			if page:
				if skip:
					odataQuery['$skip']=str(skip)				
			doc=Document(baseURI=self._AddParams(feedURL,odataQuery),reqManager=self)
			doc.Read()
			if isinstance(doc.root,atom.Feed):
				if len(doc.root.Entry):
					for e in doc.root.Entry:
						self.AssociateEntityType(e)
						yield e
				else:
					break
			else:
				raise InvalidFeedDocument(str(feedURL))
			if page:
				skip=skip+page
			else:
				# check for 'next' link
				feedURL=None
				for link in doc.root.Link:
					if link.rel=="next":
						feedURL=link.ResolveURI(link.href)
						break
				if feedURL is None:
					break
						
	def Entry(self,entityTypeName=None):
		"""Returns a new :py:class:`Entry` suitable for passing to :py:meth:`AddEntry`.
		
		The optional *entityTypeName* is the name of an EntityType to bind this
		entry to.  The name must be the fully qualified name of a type in one of
		the namespaces.  A Category instance is added to the Entry to represent this
		binding."""
		if entityTypeName:
			entityType=self.LookupEntityType(entityTypeName)
			if entityType is None:
				raise KeyError("Undeclared Type: %s"%entityTypeName)
		else:
			entityType=None
		e=Entry(None)
		e.entityType=entityType
		if entityType:
			c=e.ChildElement(atom.Category)
			c.scheme=ODATA_SCHEME
			c.term=entityTypeName				
		return e		
				
	def AddEntry(self,feedURL,entry):
		"""Given a feed URL, adds an :py:class:`Entry` to it
		
		Returns the new entry as returned by the OData service.  *entry* must be
		an orphan element."""
		doc=Document(root=entry,reqManager=self)
		req=http.HTTPRequest(str(feedURL),"POST",unicode(doc).encode('utf-8'))
		mtype=http.HTTPMediaType()
		mtype.SetMimeType(atom.ATOM_MIMETYPE)
		mtype.parameters['charset']=('Charset','utf-8')
		req.SetHeader("Content-Type",mtype)
		self.ProcessRequest(req)
		if req.status==201:
			newDoc=Document()
			e=xml.XMLEntity(req.response)
			newDoc.ReadFromEntity(e)
			if isinstance(newDoc.root,atom.Entry):
				return newDoc.root
			else:
				raise InvalidEntryDocument(str(entryURL))
		else:
			raise UnexpectedHTTPResponse("%i %s"%(req.status,req.response.reason))	
			
	def RetrieveEntry(self,entryURL):
		"""Given an entryURL URL, returns the :py:class:`Entry` instance"""
		doc=Document(baseURI=entryURL,reqManager=self)
		doc.Read()
		if isinstance(doc.root,atom.Entry):
			self.AssociateEntityType(doc.root)
			return doc.root
		else:
			raise InvalidEntryDocument(str(entryURL))
			
	def _AddParams(self,baseURL,odataQuery=None):
		if baseURL.query is None:
			query={}
		else:
			query=cgi.parse_qs(baseURL.query)
		if self.pageSize:
			query["$top"]=str(self.pageSize)
		if odataQuery:
			for k in odataQuery.keys():
				query[k]=odataQuery[k]
		if query:
			if baseURL.absPath is None:
				raise InvalidFeedURL(str(baseURL))
			return uri.URIFactory.Resolve(baseURL,baseURL.absPath+"?"+urllib.urlencode(query))
		else:
			return baseURL

	def QueueRequest(self,request):
		request.SetHeader('Accept','application/xml')
		request.SetHeader('DataServiceVersion','2.0; pyslet %s'%info.version)
		request.SetHeader('MaxDataServiceVersion','2.0; pyslet %s'%info.version)
		app.Client.QueueRequest(self,request)


class Error(ODataElement):
	XMLNAME=(ODATA_METADATA_NAMESPACE,'error')
	XMLCONTENT=xmlns.ElementContent
	
	def __init__(self,parent):
		ODataElement.__init__(self,parent)
		self.Code=Code(self)
		self.Message=Message(self)
		self.InnerError=None
	
	def GetChildren(self):
		yield self.Code
		yield self.Message
		if self.InnerError: yield self.InnerError

	def GenerateStdErrorJSON(self):
		yield '{"error":{"code":%s,"message":%s'%(
			json.dumps(self.Code.GetValue()),
			json.dumps(self.Message.GetValue()))
		if self.InnerError:
			yield ',"innererror":%s'%json.dumps(self.InnerError.GetValue())
		yield '}}'
		

class Code(ODataElement):
	XMLNAME=(ODATA_METADATA_NAMESPACE,'code')
	
class Message(ODataElement):
	XMLNAME=(ODATA_METADATA_NAMESPACE,'message')
	
class InnerError(ODataElement):
	XMLNAME=(ODATA_METADATA_NAMESPACE,'innererror')


class WSGIWrapper(object):
	def __init__(self,environ,start_response,responseHeaders):
		"""A simple wrapper class for a wsgi application.
		
		Allows additional responseHeaders to be added to the wsgi response."""
		self.environ=environ
		self.start_response=start_response
		self.responseHeaders=responseHeaders
	
	def call(self,application):
		"""Calls wsgi *application*"""
		return application(self.environ,self.start_response_wrapper)

	def start_response_wrapper(self,status,response_headers,exc_info=None):
		"""Traps the start_response callback and adds the additional headers."""
		response_headers=response_headers+self.responseHeaders
		return self.start_response(status,response_headers,exc_info)

		
class Server(app.Server):
	"""Extends py:class:`pyselt.rfc5023.Server` to provide an OData server.
	
	We do some special processing of the serviceRoot before passing it to the
	parent construtor as in OData it cannot end in a trailing slash.  If it
	does, we strip the slash from the root and use that as our OData service
	root.
	
	But... we always pass a URI with a trailing slash to the parent constructor
	following the example set by http://services.odata.org/OData/OData.svc and
	issue a temporary redirect when we receive requests for the OData service
	root to the OData URI consisting of the service root + a resource path
	consisting of a single '/'.
	
	This makes the links in the service document much clearer and easier to
	generate but more importantly, it deals with the awkward case of a service
	root consisting of just scheme and authority (e.g., http://odata.example.com
	).  This type of servie root cannot be obtained with a simple HTTP request
	as the trailing '/' is implied (and no redirection is necessary)."""

	AtomRanges=[
		http.MediaRange('application/atom+xml'),
		http.MediaRange('application/xml'),
		http.MediaRange('text/xml') ]

	JSONRanges=[
		http.MediaRange('application/json')
		]
							
	DefaultAcceptList=http.AcceptList("application/atom+xml, application/xml; q=0.9, text/xml; q=0.8, text/plain; q=0.7, */*; q=0.6")
	ErrorTypes=[
		http.MediaType('application/atom+xml'),
		http.MediaType('application/xml'),
		http.MediaType('application/json')]
	
	RedirectTypes=[
		http.MediaType('text/html'),
		http.MediaType('text/plain')]
			
	FeedTypes=[		# in order of preference if there is a tie
		http.MediaType('application/atom+xml'),
		http.MediaType('application/atom+xml;type=feed'),
		http.MediaType('application/xml'),
		http.MediaType('text/xml'),
		http.MediaType('application/json'),
		http.MediaType('text/plain')]
	
	EntryTypes=[	# in order of preference if there is a tie
		http.MediaType('application/atom+xml'),
		http.MediaType('application/atom+xml;type=entry'),
		http.MediaType('application/xml'),
		http.MediaType('text/xml'),
		http.MediaType('application/json'),
		http.MediaType('text/plain')]
	
	ValueTypes=[	# in order of preference if there is a tie
		http.MediaType('application/xml'),
		http.MediaType('text/xml'),
		http.MediaType('application/json'),
		http.MediaType('text/plain')]
	
	ServiceRootTypes=[	# in order of preference if there is a tie
		http.MediaType('application/atomsvc+xml'),
		http.MediaType('application/json'),
		http.MediaType('text/plain')]
	
	MetadataTypes=[	# in order of preference if there is a tie
		http.MediaType('application/xml'),
		http.MediaType('text/xml'),
		http.MediaType('text/plain')]
	
	DereferenceTypes=[	# in order of preference
		http.MediaType('text/plain;charset=utf-8'),
		http.MediaType('application/octet-stream'),
		http.MediaType('octet/stream')]		# we allow this one in case someone read the spec literally!
		
	StreamTypes=[
		http.MediaType('application/octet-stream'),
		http.MediaType('octet/stream')]		# we allow this one in case someone read the spec literally!

	def __init__(self,serviceRoot="http://localhost"):
		if serviceRoot[-1]!='/':
			serviceRoot=serviceRoot+'/'
		app.Server.__init__(self,serviceRoot)
		if self.serviceRoot.relPath is not None:
			# The service root must be absolute (or missing completely)!
			raise ValueError("serviceRoot must not be relative")
		if self.serviceRoot.absPath is None:
			self.pathPrefix=''
		else:
			self.pathPrefix=self.serviceRoot.absPath
		# pathPrefix must not have a tailing slash, even if this makes it an empty string
		if self.pathPrefix[-1]=='/':
			self.pathPrefix=self.pathPrefix[:-1]		
		self.ws=self.service.ChildElement(app.Workspace)	#: a single workspace that contains all collections
		self.ws.ChildElement(atom.Title).SetValue("Default")
		self.model=None					#: a :py:class:`pyslet.odatav2_metadata.Edmx` instance containing the model for the service
		
	def SetModel(self,model):
		"""Sets the model for the server from a parentless
		:py:class:`pyslet.odatav2_metadata.Edmx` instance or an Edmx
		:py:class:`pyslet.odatav2_metadata.Document` instance."""
		if isinstance(model,edmx.Document):
			doc=model
			model=model.root
		elif isinstance(model,edmx.Edmx):
			# create a document to hold the model
			doc=edmx.Document(root=model)
		else:
			raise TypeError("Edmx document or instance required for model")
		# update the base URI of the metadata document to identify this service
		doc.SetBase(self.serviceRoot)
		if self.model:
			# get rid of the old model
			for c in self.ws.Collection:
				c.DetachFromDocument()
				c.parent=None
			self.ws.Collection=[]
		for s in model.DataServices.Schema:
			for container in s.EntityContainer:
				if container.IsDefaultEntityContainer():
					prefix=""
				else:
					prefix=container.name+"."
				# define one feed for each entity set, prefixed with the name of the entity set
				for es in container.EntitySet:
					feed=self.ws.ChildElement(app.Collection)
					feed.href=prefix+es.name
					feed.ChildElement(atom.Title).SetValue(prefix+es.name)
					#	update the locations following SetBase above
					es.SetLocation()
		self.model=model
		
	def __call__(self,environ, start_response):
		"""wsgi interface for the server."""
		responseHeaders=[]
		try:
			version=self.CheckCapabilityNegotiation(environ,start_response,responseHeaders)
			if version is None:
				return self.ODataError(ODataURI('error'),environ,start_response,"DataServiceVersionMismatch","Maximum supported protocol version: 2.0")
			request=ODataURI(environ['PATH_INFO'],self.pathPrefix,version)
			if request.resourcePath is None:
				# this is not a URI for us, pass to our superclass
				wrapper=WSGIWrapper(environ,start_response,responseHeaders)
				# super essentially allows us to pass a bound method of our parent
				# that we ourselves are hiding.
				return wrapper.call(super(Server,self).__call__)
			elif request.resourcePath=='':
				# An empty resource path means they hit the service root, redirect
				location=str(self.serviceRoot)
				r=html.HTML(None)
				r.Head.Title.SetValue('Redirect')
				div=r.Body.ChildElement(html.Div)
				div.AddData(u"Moved to: ")
				anchor=div.ChildElement(html.A)
				anchor.href=self.serviceRoot
				anchor.SetValue(location)
				responseType=self.ContentNegotiation(request,environ,self.RedirectTypes)
				if responseType is None:
					# this is a redirect response, default to text/plain anyway
					responseType=http.MediaType('text/plain')
				if responseType=="text/plain":
					data=r.RenderText()
				else:
					data=str(r)
				responseHeaders.append(("Content-Type",str(responseType)))
				responseHeaders.append(("Content-Length",str(len(data))))
				responseHeaders.append(("Location",location))
				start_response("%i %s"%(307,"Temporary Redirect"),responseHeaders)
				return [data]
			else:
				return self.HandleRequest(request,environ,start_response,responseHeaders)
		except InvalidSystemQueryOption,e:
			return self.ODataError(ODataURI('error'),environ,start_response,"InvalidSystemQueryOption","Invalid System Query Option: %s"%str(e))
		except InvalidPathOption,e:
			return self.ODataError(ODataURI('error'),environ,start_response,"Bad Request","Path option is invalid or incompatible with this form of URI: %s"%str(e),400)			
		except ValueError,e:
			traceback.print_exception(*sys.exc_info())
			# This is a bad request
			return self.ODataError(ODataURI('error'),environ,start_response,"ValueError",str(e))
		except:
			eInfo=sys.exc_info()
			traceback.print_exception(*eInfo)
			# return self.HandleError(ODataURI('error'),environ,start_response)
			return self.ODataError(ODataURI('error'),environ,start_response,"UnexpectedError","%s: %s"%(eInfo[0],eInfo[1]),500)

	def ODataError(self,request,environ,start_response,subCode,message='',code=400):
		"""Generates and ODataError, typically as the result of a bad request."""
		responseHeaders=[]
		e=Error(None)
		e.ChildElement(Code).SetValue(subCode)
		e.ChildElement(Message).SetValue(message)
		responseType=self.ContentNegotiation(request,environ,self.ErrorTypes)
		if responseType is None:
			# this is an error response, default to text/plain anyway
			responseType=http.MediaType('text/plain')
		elif responseType=="application/atom+xml":
			# even if you didn't ask for it, you get application/xml in this case
			responseType="application/xml"
		if responseType=="application/json":
			data=string.join(e.GenerateStdErrorJSON(),'')
		else:
			data=str(e)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(code,subCode),responseHeaders)
		return [data]
	
	def GetResourceFromURI(self,href):
		"""Returns the resource object represented by the :py:class:`pyslet.rfc2396.URI`
		
		The URI must not use path, or system query options but must
		identify an enity set, entity, complex or simple value."""
		if not href.IsAbsolute():
			# resolve relative to the service root
			href=URIFactory.Resolve(self.serviceRoot,href)
		# check the canonical roots
		if not self.serviceRoot.GetCanonicalRoot().Match(href.GetCanonicalRoot()):
			# This isn't even for us
			return None
		request=ODataURI(href,self.pathPrefix)
		return self.GetResource(request)
	
	def GetResource(self,odataURI,responseHeaders=None):
		resource=self.model
		noNavPath=(resource is None)
		entity=None
		for segment in odataURI.navPath:
			name,keyPredicate=segment
			if noNavPath:
				raise BadURISegment(name)
			if isinstance(resource,edmx.Edmx):
				try:
					resource=resource.DataServices.SearchContainers(name)
				except KeyError,e:
					raise MissingURISegment(str(e))						
				if isinstance(resource,edm.FunctionImport):
					# TODO: grab the params from the query string
					resource=resource.Execute({})
					#	If this does not identify a collection of entities it must be the last path segment
					if not isinstance(resource,edm.EntityCollection):
						noNavPath=True
						# 10-14 have identical constraints, treat them the same
						odataURI.ValidateSystemQueryOptions(10)
				elif isinstance(resource,edm.EntitySet):
					resource=resource.OpenCollection()
				else:
					# not the right sort of thing
					raise MissingURISegment(name)					
				if isinstance(resource,edm.EntityCollection):						
					if keyPredicate:
						# the keyPredicate can be passed directly as the key
						try:
							collection=resource
							resource=collection[collection.entitySet.GetKey(keyPredicate)]
							entity=resource
							collection.close()
						except KeyError,e:
							raise MissingURISegment("%s%s"%(name,ODataURI.FormatKeyDict(keyPredicate)))					
				elif resource is None:
					raise MissingURISegment(name)
			elif isinstance(resource,(edm.EntityCollection,edm.FunctionCollection)):
				# bad request, because the collection must be the last thing in the path
				raise BadURISegment("%s since the object's parent is a collection"%name)
			elif isinstance(resource,edm.Entity):
				if name not in resource:
					raise MissingURISegment(name)
				resource=resource[name]
				if isinstance(resource,edm.DeferredValue):
					entity=None
					if keyPredicate:
						try:
							with resource.OpenCollection() as collection:
								resource=collection[resource.entitySet.GetKey(keyPredicate)]
								entity=resource
						except KeyError,e:
							raise MissingURISegment(name)
					elif resource.isCollection:
						resource=resource.OpenCollection()
					else:
						resource=resource.GetEntity()
						if resource is None:
							# See the resolution: https://tools.oasis-open.org/issues/browse/ODATA-412
							raise MissingURISegment("%s, no entity is related"%name)
						entity=resource
			elif isinstance(resource,edm.Complex):
				if name in resource:
					# This is a regular property of the ComplexType
					resource=resource[name]
				else:
					raise MissingURISegment(name)
			else:
				# Any other type is just a property or simple-type
				raise BadURISegment(name)
		if isinstance(resource,edm.EntityCollection):
			odataURI.ValidateSystemQueryOptions(1)	# includes 6 Note 2
		elif isinstance(resource,edm.Entity):
			if odataURI.pathOption==PathOption.value:
				odataURI.ValidateSystemQueryOptions(17)	# media resource value
			elif odataURI.pathOption!=PathOption.links:	
				odataURI.ValidateSystemQueryOptions(2)	# includes 6 Note 1
		elif isinstance(resource,edm.Complex):
			odataURI.ValidateSystemQueryOptions(3)
		elif isinstance(resource,edm.SimpleValue):
			# 4 & 5 are identical
			odataURI.ValidateSystemQueryOptions(4)
		if responseHeaders is not None and entity is not None:
			# add an etag to the responseHeaders for the corresponding
			# entity we catch this here because we may be returning just
			# a property of the entity and you can't trace back to the
			# parent entity later
			etag=entity.ETag()
			if etag is not None:
				s="%s" if entity.ETagIsStrong() else "W/%s"
				etag=s%http.QuoteString(ODataURI.FormatLiteral(etag))
				responseHeaders.append(("ETag",etag))			
		return resource

	def HandleRequest(self,request,environ,start_response,responseHeaders):
		"""Handles a request that has been identified as being an OData request.
		
		*	*request* is an :py:class:`ODataURI` instance with a non-empty resourcePath."""
		method=environ["REQUEST_METHOD"].upper()
		try:
			resource=self.GetResource(request,responseHeaders if method=="GET" else None)
			if request.pathOption==PathOption.metadata:
				return self.ReturnMetadata(request,environ,start_response,responseHeaders)
			elif request.pathOption==PathOption.batch:
				return self.ODataError(request,environ,start_response,"Bad Request","Batch requests not supported",404)
			elif request.pathOption==PathOption.count:
				if isinstance(resource,edm.Entity):
					return self.ReturnCount(1,request,environ,start_response,responseHeaders)
				elif isinstance(resource,edm.EntityCollection):
					return self.ReturnCount(len(resource),request,environ,start_response,responseHeaders)
				else:
					raise BadURISegment("$count must be applied to an EntitySet or single EntityType instance")
			elif request.pathOption==PathOption.links:
				# resource will be the source entity, request.linksProperty is the navigation property
				if not isinstance(resource,Entity):
					raise BadURISegment("$links must be preceded by a single EntityType instance")
				if method=="GET":
					# open the collection and select the key properties only
					with resource[request.linksProperty].OpenCollection() as collection:
						collection.SelectKeys()
						if resource.IsEntityCollection(request.linksProperty):
							collection.Skip(request.sysQueryOptions.get(SystemQueryOption.skip,None))
							collection.Top(request.sysQueryOptions.get(SystemQueryOption.top,None))
							collection.SkipToken(request.sysQueryOptions.get(SystemQueryOption.skiptoken,None))
							inlineCount=request.sysQueryOptions.get(SystemQueryOption.inlinecount,None)
							collection.SetInlineCount(inlineCount==InlineCount.allpages)
							return self.ReturnLinks(collection,request,environ,start_response,responseHeaders)
						else:
							# should have just a single link
							entities=collection.values()
							if len(entities)==0:
								raise MissingURISegment("%s, no entity is related"%request.linksProperty)
							elif len(entities)==1:
								return self.ReturnLink(entities[0],request,environ,start_response,responseHeaders)						
							else:
								raise NavigationError("Navigation property %s of %s is not a collection but it yielded multiple entities"%(name,self.fromEntity.entitySet.GetLocation()))
				elif method=="POST":
					targetEntity=self.ReadEntityFromLink(environ)
					with resource[request.linksProperty].OpenCollection() as collection:
						collection[targetEntity.Key()]=targetEntity
					return self.ReturnEmpty(start_response,responseHeaders)
				else:
					raise InvalidMethod("%s not supported here"%method)
			elif isinstance(resource,edm.Entity):
				if request.pathOption==PathOption.value:
					if resource.typeDef.HasStream():
						return self.ReturnStream(resource,request,environ,start_response,responseHeaders)								
					else:
						raise BadURISegment("$value cannot be used since the entity is not a media stream")				
				else:
					self.ExpandResource(resource,request.sysQueryOptions)
					return self.ReturnEntity(resource,request,environ,start_response,responseHeaders)
			elif isinstance(resource,edm.EntityCollection):
				if method=="GET":
					self.ExpandResource(resource,request.sysQueryOptions)
					resource.Filter(request.sysQueryOptions.get(SystemQueryOption.filter,None))
					resource.OrderBy(request.sysQueryOptions.get(SystemQueryOption.orderby,[]))
					resource.Skip(request.sysQueryOptions.get(SystemQueryOption.skip,None))
					resource.Top(request.sysQueryOptions.get(SystemQueryOption.top,None))
					resource.SkipToken(request.sysQueryOptions.get(SystemQueryOption.skiptoken,None))
					inlineCount=request.sysQueryOptions.get(SystemQueryOption.inlinecount,None)
					resource.SetInlineCount(inlineCount==InlineCount.allpages)
					return self.ReturnEntityCollection(resource,request,environ,start_response,responseHeaders)
				elif method=="POST" and resource.IsMediaLinkEntryCollection():
					# POST of a media resource
					entity=resource.NewEntity()
					if "HTTP_SLUG" in environ:
						slug=environ["HTTP_SLUG"]
						for k,v in entity.DataItems():
							# catch property-level feed customisation here
							propertyDef=entity.typeDef[k]
							if propertyDef.GetTargetPath()==[(atom.ATOM_NAMESPACE,"title")]:
								entity[k].SetFromPyValue(slug)
								break					
					resource.InsertEntity(entity)
					if "CONTENT_TYPE" in environ:
						resourceType=http.MediaType(environ["CONTENT_TYPE"])
					else:
						resourceType=http.MediaType('application/octet-stream')
					input=app.InputWrapper(environ)
					entity.SetStreamFromGenerator(resourceType,input.iterblocks())
					responseHeaders.append(('Location',str(entity.GetLocation())))
					return self.ReturnEntity(entity,request,environ,start_response,responseHeaders,201,"Created")
				elif method=="POST":
					# POST to an ordinary entity collection
					entity=resource.NewEntity()
					# read the entity from the request
					self.ReadEntity(entity,environ)
					resource.InsertEntity(entity)
					responseHeaders.append(('Location',str(entity.GetLocation())))
					return self.ReturnEntity(entity,request,environ,start_response,responseHeaders,201,"Created")
				else:
					raise InvalidMethod("%s not supported here"%method)					
			elif isinstance(resource,edm.EDMValue):
				if request.pathOption==PathOption.value:
					return self.ReturnDereferencedValue(resource,request,environ,start_response,responseHeaders)
				else:
					return self.ReturnValue(resource,request,environ,start_response,responseHeaders)
			elif isinstance(resource,edm.FunctionCollection):
				return self.ReturnCollection(resource,request,environ,start_response,responseHeaders)
			else:	
				# None or the DataService object: means we are trying to get the service root
				responseType=self.ContentNegotiation(request,environ,self.ServiceRootTypes)
				if responseType is None:
					return self.ODataError(request,environ,start_response,"Not Acceptable",'atomsvc+xml or json formats supported',406)
				elif responseType=="application/json":
					return self.ReturnJSONRoot(request,environ,start_response,responseHeaders)
				else:
					wrapper=WSGIWrapper(environ,start_response,responseHeaders)
					# super essentially allows us to pass a bound method of our parent
					# that we ourselves are hiding.
					return wrapper.call(super(Server,self).__call__)
		except MissingURISegment,e:
			return self.ODataError(request,environ,start_response,"Resource not found","Resource not found for segment %s"%str(e),404)
		except BadURISegment,e:
			return self.ODataError(request,environ,start_response,"Bad Request","Resource not found for segment %s"%str(e),400)
	
	def ExpandResource(self,resource,sysQueryOptions):
		try:
			expand=sysQueryOptions.get(SystemQueryOption.expand,None)
			select=sysQueryOptions.get(SystemQueryOption.select,None)
			if expand is None and select is None:
				return
			if not isinstance(resource,(EntityCollection,Entity)):
				raise InvalidSystemQueryOption("$select/$expand not allowed")					
			resource.entitySet.entityType.ValidateExpansion(expand,select)
			resource.Expand(expand,select)
		except ValueError as e:
			raise InvalidSystemQueryOption("$select/$expand error: %s"%str(e))					
		
	def ReturnJSONRoot(self,request,environ,start_response,responseHeaders):
		data='{"d":%s}'%json.dumps({'EntitySets':map(lambda x:x.href,self.ws.Collection)})
		responseHeaders.append(("Content-Type","application/json"))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
		
	def ReturnMetadata(self,request,environ,start_response,responseHeaders):
		doc=self.model.GetDocument()
		responseType=self.ContentNegotiation(request,environ,self.MetadataTypes)
		if responseType is None:
			return self.ODataError(request,environ,start_response,"Not Acceptable",'xml or plain text formats supported',406)
		data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
			
	def ReturnLinks(self,entities,request,environ,start_response,responseHeaders):
		responseType=self.ContentNegotiation(request,environ,self.ValueTypes)
		if responseType is None:
			return self.ODataError(request,environ,start_response,"Not Acceptable",'xml, json or plain text formats supported',406)
		if responseType=="application/json":
			data='{"d":%s}'%string.join(entities.GenerateLinkCollJSON(request.version),'')
		else:
			doc=Document(root=Links)
			for e in entities.itervalues():
				child=doc.root.ChildElement(URI)
				child.SetValue(str(self.serviceRoot)+"%s(%s)"%(e.entitySet.name,repr(e.Key())))
			data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
		
	def ReadEntityFromLink(self,environ):
		input=self.ReadXMLOrJSON(environ)
		if isinstance(input,Document):
			if isinstance(input.root,URI):
				return self.GetResourceFromURI(uri.URIFactory.URI(input.root.GetValue()))
			else:
				raise InvalidData("Unable to parse link from request body (found <%s>)"%doc.root.xmlname)
		else:
			# must be a json object
			try:
				return self.GetResourceFromURI(uri.URIFactory.URI(input['uri']))
			except KeyError:
				raise InvalidData("Unable to parse link from JSON request body (found %s )"%str(input)[:256])
		
	def ReturnLink(self,entity,request,environ,start_response,responseHeaders):
		doc=Document(root=URI)
		# doc.root.SetValue(str(self.serviceRoot)+"%s(%s)"%(entity.entitySet.name,repr(entity.Key())))
		doc.root.SetValue(str(entity.GetLocation()))
		responseType=self.ContentNegotiation(request,environ,self.ValueTypes)
		if responseType is None:
			return self.ODataError(request,environ,start_response,"Not Acceptable",'xml, json or plain text formats supported',406)
		if responseType=="application/json":
			data='{"d":%s}'%json.dumps(doc.root,cls=ODataJSONEncoder)
		else:
			data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
			
	def ReturnEntityCollection(self,entities,request,environ,start_response,responseHeaders):
		"""Returns an iterable of Entities."""
		responseType=self.ContentNegotiation(request,environ,self.FeedTypes)
		if responseType is None:
			return self.ODataError(request,environ,start_response,"Not Acceptable",'xml, json or plain text formats supported',406)
		if responseType=="application/json":
			data='{"d":%s}'%string.join(entities.GenerateEntitySetInJSON(request.version),'')
		else:
			# Here's a challenge, we want to pull data through the feed by yielding strings
			# just load in to memory at the moment
			f=Feed(None,entities)
			doc=Document(root=f)
			f.collection=entities
			f.SetBase(str(self.serviceRoot))
			data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
				
	def ReadXMLOrJSON(self,environ):
		"""Reads either an XML document or a JSON object from environ."""
		atomFlag=None
		encoding=None
		if "CONTENT_TYPE" in environ:
			requestType=http.MediaType(environ["CONTENT_TYPE"])
			for r in self.AtomRanges:
				if r.MatchMediaType(requestType):
					atomFlag=True
					break
			if atomFlag is None:
				for r in self.JSONRanges:
					if r.MatchMediaType(requestType):
						atomFlag=False
						break
			encoding=requestType.parameters.get('charset',(None,None))[0]
		input=app.InputWrapper(environ)
		unicodeInput=None
		if encoding is None:
			# read a line, at most 4 bytes
			encoding=DetectEncoding(input.readline(4))
			if encoding is None:
				encoding='utf_8'
			input.seek(0)
		if atomFlag is None:
			# we still need to figure out what we have here
			if encoding.lower() in ("utf_8","utf-8"):
				unicodeInput=input
			else:
				unicodeInput=codecs.getreader(encoding)(input)
			b='\x00'
			while ord(b)<0x20:
				b=unicodeInput.read(1)
				if len(b)==0:
					# empty file
					break
			if b==u'<':
				atomFlag=True
			elif b in u'{[':
				atomFlag=False
			else:
				raise InvalidData("Unable to parse request body")
			unicodeInput.seek(0)			
		if atomFlag==True:
			# read atom file
			doc=Document()
			doc.Read(src=xml.XMLEntity(src=input,encoding=encoding))
			return doc
		else:
			if unicodeInput is None:
				if encoding.lower() in ("utf_8","utf-8"):
					unicodeInput=input
				else:
					unicodeInput=codecs.getreader(encoding)(input)
			return json.load(unicodeInput)
			
	def ReadEntity(self,entity,environ):
		input=self.ReadXMLOrJSON(environ)
		if isinstance(input,Document):
			if isinstance(input.root,Entry):
				# we have an entry, which is a relief!
				input.root.GetValue(entity,self.GetResourceFromURI)
			else:
				raise InvalidData("Unable to parse atom Entry from request body (found <%s>)"%doc.root.xmlname)
		else:
			# must be a json object
			entity.SetFromJSONObject(input,self.GetResourceFromURI)
		
	def ReturnEntity(self,entity,request,environ,start_response,responseHeaders,status=200,statusMsg="Success"):
		"""Returns a single Entity."""
		responseType=self.ContentNegotiation(request,environ,self.EntryTypes)
		if responseType is None:
			return self.ODataError(request,environ,start_response,"Not Acceptable",'xml, json or plain text formats supported',406)
		# Here's a challenge, we want to pull data through the feed by yielding strings
		# just load in to memory at the moment
		if responseType=="application/json":
			data='{"d":%s}'%string.join(entity.GenerateEntityTypeInJSON(),'')
		else:
			doc=Document(root=Entry)
			e=doc.root
			e.SetBase(str(self.serviceRoot))
			e.SetValue(entity)
			data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		etag=entity.ETag()
		if etag is not None:
			s="%s" if entity.ETagIsStrong() else "W/%s"
			etag=s%http.QuoteString(ODataURI.FormatLiteral(etag))
			responseHeaders.append(("ETag",etag))
		start_response("%i %s"%(status,statusMsg),responseHeaders)
		return [data]

	def ReturnStream(self,entity,request,environ,start_response,responseHeaders):
		"""Returns a media stream."""
		types=[entity.GetStreamType()]+self.StreamTypes
		responseType=self.ContentNegotiation(request,environ,types)
		if responseType is None:
			return self.ODataError(request,environ,start_response,"Not Acceptable",'media stream type refused, try application/octet-stream',406)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",entity.GetStreamSize()))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return entity.GetStreamGenerator()

	def ReturnValue(self,value,request,environ,start_response,responseHeaders):
		"""Returns a single property value."""
		responseType=self.ContentNegotiation(request,environ,self.ValueTypes)
		if responseType is None:
			return self.ODataError(request,environ,start_response,"Not Acceptable",'xml, json or plain text formats supported',406)
		if responseType=="application/json":
			if isinstance(value,edm.Complex):
				if request.version==2:
					data='{"d":%s}'%EntityCTInJSON2(value)
				else:
					data='{"d":%s}'%EntityCTInJSON(value)
			else:
				if request.version==2:
					# the spec goes a bit weird here, tripping up over brackets!
					data='{"d":%s}'%EntityPropertyInJSON2(value)
				else:
					data='{"d":{%s}}'%EntityPropertyInJSON(value)					
		else:
			e=Property(None)
			e.SetXMLName((ODATA_DATASERVICES_NAMESPACE,value.name))
			doc=Document(root=e)
			e.SetValue(value)
			data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
				
	def ReturnDereferencedValue(self,value,request,environ,start_response,responseHeaders):
		"""Returns a dereferenced property value."""
		mTypes=self.DereferenceTypes if value.mType is None else [value.mType]
		responseType=self.ContentNegotiation(request,environ,mTypes)
		if responseType is None:
			return self.ODataError(request,environ,start_response,"Not Acceptable",'$value requires plain text or octet-stream formats',406)
		data=unicode(value).encode('utf-8')
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
				
	def ReturnCollection(self,collection,request,environ,start_response,responseHeaders):
		"""Returns a collection of values."""
		responseType=self.ContentNegotiation(request,environ,self.ValueTypes)
		if responseType is None:
			return self.ODataError(request,environ,start_response,"Not Acceptable",'xml, json or plain text formats supported',406)
		if responseType=="application/json":
			data='{"d":%s}'%string.join(collection.GenerateCollectionInJSON(request.version))
		else:
			e=Collection(None)
			e.SetXMLName((ODATA_METADATA_NAMESPACE,collection.name))
			doc=Document(root=e)
			for value in collection:
				p=e.ChildElement(Property)
				p.SetXMLName((ODATA_DATASERVICES_NAMESPACE,value.name))
				p.SetValue(value)
			data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]

	def ReturnCount(self,number,request,environ,start_response,responseHeaders):
		"""Returns the single value number."""
		responseType=self.ContentNegotiation(request,environ,self.DereferenceTypes)
		if responseType is None:
			return self.ODataError(request,environ,start_response,"Not Acceptable",'$count requires plain text or octet-stream formats',406)
		data=str(number)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
				
	def ReturnEmpty(self,start_response,responseHeaders,status=204,statusMsg="No content"):
		"""Returns no content."""
		responseHeaders.append(("Content-Length","0"))
		start_response("%i %s"%(status,statusMsg),responseHeaders)
		return []
				
	def ContentNegotiation(self,request,environ,mTypeList):
		"""Given a list of media types, examines the Accept header and returns the best match.
		
		If there is no match then None is returned.  We also handle an
		accept list override in the form of acceptList, e.g., parsed
		from the $format parameter."""
		aList=request.sysQueryOptions.get(SystemQueryOption.format,None)
		if aList is None:
			if "HTTP_ACCEPT" in environ:
				try:
					aList=http.AcceptList(environ["HTTP_ACCEPT"])
				except http.HTTPParameterError:
					# we'll treat this as a missing Accept header
					aList=self.DefaultAcceptList
			else:
				aList=self.DefaultAcceptList
		return aList.SelectType(mTypeList)
			
	def CheckCapabilityNegotiation(self,environ,start_response,responseHeaders):
		"""Sets the protocol version in *responseHeaders* if we can handle this request.
		
		Returns None if the application should continue to handle the request, otherwise
		it returns an iterable object suitable for the wsgi return value.
		
		*	responseHeaders is a list which contains the proposed response headers.

		In the event of a protocol version mismatch a "400 DataServiceVersion
		mismatch" error response is generated."""
		ua=sa=None
		if "HTTP_DATASERVICEVERSION" in environ:
			major,minor,ua=ParseDataServiceVersion(environ["HTTP_DATASERVICEVERSION"])
		else:
			major=2
			minor=0
		if "HTTP_MAXDATASERVICEVERSION" in environ:
			maxMajor,maxMinor,sa=ParseMaxDataServiceVersion(environ["HTTP_MAXDATASERVICEVERSION"])
		else:
			maxMajor=major
			maxMinor=minor
		if major>2 or (major==2 and minor>0):
			# we can't cope with this request
			return None
		elif maxMajor>=2:
			responseHeaders.append(('DataServiceVersion','2.0; pyslet %s'%info.version))
			return 2
		else:
			responseHeaders.append(('DataServiceVersion','1.0; pyslet %s'%info.version))
			return 1
			
	
class Document(app.Document):
	"""Class for working with OData documents."""
	classMap={}
	
	def __init__(self,**args):
		app.Document.__init__(self,**args)
		self.MakePrefix(ODATA_METADATA_NAMESPACE,'m')
		self.MakePrefix(ODATA_DATASERVICES_NAMESPACE,'d')
	
	@classmethod
	def GetElementClass(cls,name):
		"""Returns the OData, APP or Atom class used to represent name.
		
		Overrides :py:meth:`~pyslet.rfc5023.Document.GetElementClass` to allow
		custom implementations of the Atom or APP classes to be created and
		to cater for OData-specific elements."""
		result=Document.classMap.get(name,None)
		if result is None:
			if name[0]==ODATA_DATASERVICES_NAMESPACE:
				result=Property
			else:
				result=app.Document.GetElementClass(name)
		return result

xmlns.MapClassElements(Document.classMap,globals())


class ODataStoreClient(edm.ERStore):
	"""Provides an implementation of ERStore based on OData."""

	def __init__(self,serviceRoot=None):
		edm.ERStore.__init__(self)
		self.client=Client(serviceRoot)
		self.defaultContainer=None		#: the default entity container
		for s in self.client.schemas:
			# if the client has a $metadata document we'll use it
			schema=self.client.schemas[s]
			self.AddSchema(schema)
			# search for the default entity container
			for container in schema.EntityContainer:
				try:
					if container.IsDefaultEntityContainer():
						if self.defaultContainer is None:
							self.defaultContainer=container
						else:
							raise InvalidMetadataDocument("Multiple default entity containers defined")
				except KeyError:
					pass									
				
	def EntityReader(self,entitySetName):
		"""Iterates over the entities in the given entity set (feed)."""
		feedURL=None
		if self.defaultContainer:
			if entitySetName in self.defaultContainer:
				# use this as the name of the feed directly
				# get the entity type from the entitySet definition
				entitySet=self.defaultContainer[entitySetName]
				entityType=self[entitySet.entityTypeName]
				feedURL=uri.URIFactory.Resolve(self.client.serviceRoot,entitySetName)
		if feedURL is None:
			raise NotImplementedError("Entity containers other than the default") 
		for entry in self.client.RetrieveEntries(feedURL):
			values={}
			for p in entityType.Property:
				v=entry[p.name]
				values[p.name]=v
			yield values

			
