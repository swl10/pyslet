#! /usr/bin/env python
"""This module implements the Open Data Protocol specification defined by Microsoft."""

import sys, cgi, urllib, string, itertools, traceback, StringIO, json, decimal, uuid, math

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
import pyslet.mc_edmx as edmx
import pyslet.mc_csdl as edm
from pyslet.unicode5 import CharClass

class InvalidLiteral(Exception): pass
class InvalidServiceDocument(Exception): pass
class InvalidMetadataDocument(Exception): pass
class InvalidFeedDocument(Exception): pass
class InvalidEntryDocument(Exception): pass
class InvalidFeedURL(Exception): pass
class UnexpectedHTTPResponse(Exception): pass

class ServerError(Exception): pass
class BadURISegment(ServerError): pass
class MissingURISegment(ServerError): pass
class InvalidSystemQueryOption(ServerError): pass
class EvaluationError(Exception): pass


ODATA_METADATA_NAMESPACE="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"	#: namespace for metadata, e.g., the property type attribute
IsDefaultEntityContainer=(ODATA_METADATA_NAMESPACE,u"IsDefaultEntityContainer")

ODATA_DATASERVICES_NAMESPACE="http://schemas.microsoft.com/ado/2007/08/dataservices"		#: namespace for auto-generated elements, e.g., :py:class:`Property`
ODATA_SCHEME="http://schemas.microsoft.com/ado/2007/08/dataservices/scheme"					#: category scheme for type definition terms
ODATA_RELATED="http://schemas.microsoft.com/ado/2007/08/dataservices/related/"				#: link type for related entries

ODATA_RELATED_TYPE="application/atom+xml;type=entry"

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
		'celing':20
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
	"""A mapping from unary operators to bound class methods that
	evaluate the operator."""

	def __init__(self,operator):
		super(UnaryExpression,self).__init__(operator)

	def Evaluate(self,contextEntity):
		rValue=self.operands[0].Evaluate(contextEntity)
		return self.EvalMethod[self.operator](rValue)

	@classmethod
	def EvaluateNegate(cls,rValue):
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

	@classmethod
	def EvaluateNot(cls,rValue):
		raise NotImplementedError


UnaryExpression.EvalMethod={
	Operator.negate:UnaryExpression.EvaluateNegate,
	Operator.boolNot:UnaryExpression.EvaluateNot }


class BinaryExpression(CommonExpression):
	
	EvalMethod={
		}
	"""A mapping from binary operators to bound class methods that
	evaluate the operator."""
	  
	def __init__(self,operator):
		super(BinaryExpression,self).__init__(operator)
		
	def Evaluate(self,contextEntity):
		lValue=self.operands[0].Evaluate(contextEntity)
		if self.operator==Operator.member:
			# Special handling for the member operator, as the left-hand
			# side of the expression returns the context for evaluating
			# the right-hand side
			return self.operands[1].Evaluate(lValue)
		else:
			rValue=self.operands[1].Evaluate(contextEntity)	
			return self.EvalMethod[self.operator](lValue,rValue)
		
	@classmethod
	def EvaluateCast(cls,lValue,rValue):
		raise NotImplementedError
	
	@classmethod
	def EvaluateMul(cls,lValue,rValue):
		typeCode=PromoteTypes(lValue.typeCode,rValue.typeCode)
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
	
	@classmethod
	def EvaluateDiv(cls,lValue,rValue):
		try:
			typeCode=PromoteTypes(lValue.typeCode,rValue.typeCode)
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
	
	@classmethod
	def EvaluateMod(cls,lValue,rValue):
		try:
			typeCode=PromoteTypes(lValue.typeCode,rValue.typeCode)
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
				
	@classmethod
	def EvaluateAdd(cls,lValue,rValue):
		typeCode=PromoteTypes(lValue.typeCode,rValue.typeCode)
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
	
	@classmethod
	def EvaluateSub(cls,lValue,rValue):
		typeCode=PromoteTypes(lValue.typeCode,rValue.typeCode)
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
	
	@classmethod
	def EvaluateLt(cls,lValue,rValue):
		raise NotImplementedError
	
	@classmethod
	def EvaluateGt(cls,lValue,rValue):
		raise NotImplementedError
	
	@classmethod
	def EvaluateLe(cls,lValue,rValue):
		raise NotImplementedError
	
	@classmethod
	def EvaluateGe(cls,lValue,rValue):
		raise NotImplementedError
	
	@classmethod
	def EvaluateIsOf(cls,lValue,rValue):
		raise NotImplementedError
	
	@classmethod
	def EvaluateEq(cls,lValue,rValue):
		typeCode=PromoteTypes(lValue.typeCode,rValue.typeCode)
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
	
	@classmethod
	def EvaluateNe(cls,lValue,rValue):
		result=cls.EvaluateEq(lValue,rValue)
		result.pyValue=not result.pyValue
		return result
	
	@classmethod
	def EvaluateAnd(cls,lValue,rValue):
		"""Watch out for the differences between OData 2-value logic and
		the usual SQL 3-value approach."""
		typeCode=PromoteTypes(lValue.typeCode,rValue.typeCode)
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
				
	@classmethod
	def EvaluateOr(cls,lValue,rValue):
		"""Watch out for the differences between OData 2-value logic and
		the usual SQL 3-value approach."""
		typeCode=PromoteTypes(lValue.typeCode,rValue.typeCode)
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
			if self.name in contextEntity:
				# This is a simple or complex property
				return contextEntity[self.name]
			elif isinstance(contextEntity,edm.Entity):
				if contextEntity.IsEntityCollection(self.name):
					raise EvaluationError("%s navigation property must have cardinality of 1 or 0..1"%self.name)
				else:
					result=contextEntity.Navigate(self.name)
					if result is None:
						# The navigation property does not point to anything, return a generic null
						result=edm.SimpleValue(None,self.name)
					return result
			else:
				raise EvaluationError("Undefined property: %s"%self.name)
		else:
			raise EvaluationError("Evaluation of %s member: no entity in context"%self.name) 		


class CallExpression(CommonExpression):
	
	def __init__(self,methodCall):
		super(CallExpression,self).__init__(Operator.methodCall)
		self.method=methodCall

	
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
				self.ParseWSP()
				if name=="not":
					self.RequireProduction(self.ParseWSP(),"WSP after not")
					rightOp=UnaryExpression(Operator.notBool)
				elif name=="isof":
					rightOp=self.RequireProduction(self.ParseCastLike(Operator.isof,"isof"),"isofExpression")
				elif name=="cast":
					rightOp=self.RequireProduction(self.ParseCastLike(Operator.cast,"cast"),"caseExpression")
				elif name is not None:
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
					name=self.ParseSimpleIdentifier()
					if name is not None:
						rightOp=BinaryExpression(Operator.DecodeValue(name))
					elif self.MatchOne(",)") or self.MatchEnd():
						# indicates the end of this common expression
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
		"""Parses a cast-like expression, including 'isof'.
		
		Note that the OData 2 ABNF is in error here, it makes reference
		to a stringLiteral but clearly a simple identifier is implied!"""
		self.ParseWSP()
		if self.Parse("("):
			e=BinaryExpression(op)
			e.left=self.ParseCommonExpression(None)
			self.ParseWSP()
			self.RequireProduction(self.Parse(","),"',' in %s"%name)
			self.ParseWSP()
			e.right=self.RequireProduction(self.ParseSimpleIdentifier(),"simpleIdentifier in %s"%name)
			self.ParseWSP()
			self.RequireProduction(self.Parse(")"),"')' after %s"%name)
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
		elif self.MatchDigit():
			return self.ParseNumericLiteral()
		elif self.Parse('-'):
			# one of the number forms
			if self.ParseInsensitive("inf"):
				if self.ParseOne("Dd"):
					result=edm.SimpleValue.NewValue(edm.SimpleType.Double)
					result.pyValue=float("-INF")
					return result
				elif self.ParseOne("Ff"):
					result=edm.SimpleValue.NewValue(edm.SimpleType.Single)
					result.pyValue=float("-INF")
					return result
				else:
					raise ValueError("Expected double or single -inf: -INF%s"%repr(self.Peek(1)))							
			else:
				result=self.ParseNumericLiteral('-')
				if result is None:
					# return the minus sign to the parser as this isn't a number
					self.SetPos(savePos)
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
			startPos=self.pos
			while not self.Parse("'"):
				if self.MatchEnd():
					raise ValueError("Unterminated quote in datetimeoffset string")
				self.NextChar()					
			try:
				value=iso.TimePoint(self.src[startPos:self.pos-1])
			except iso.DateTimeError,e:
				raise ValueError(str(e))
			zOffset,zDir=value.GetZone()
			if zOffset is None:
				raise ValueError("datetimeoffset requires zone specifier: %s"%str(value))
			if not value.Complete():
				raise ValueError("datetimeoffset requires a complete specification: %s"%str(value))
			result.pyValue=value
			return result
		elif self.ParseInsensitive("datetime"):
			result=edm.SimpleValue.NewValue(edm.SimpleType.DateTime)
			production="datetime literal"
			self.Require("'",production)
			year=int(self.RequireProduction(self.ParseDigits(4,4),production))
			self.Require("-",)
			month=self.RequireProduction(self.ParseInteger(1,12),"month")
			self.Require("-",production)
			day=self.RequireProduction(self.ParseInteger(1,31,2),"day")
			self.Require("T",production)
			hour=self.RequireProduction(self.ParseInteger(0,24),"hour")
			self.Require(":",production)
			minute=self.RequireProduction(self.ParseInteger(0,60,2),"minute")
			if self.Parse(":"):
				second=self.RequireProduction(self.ParseInteger(0,60,2),"second")
				if self.Parse("."):
					nano=self.ParseDigits(1,7)
					second+=float("0."+nano)					
			else:
				second=0
			self.Require("'",production)
			value=iso.TimePoint()
			try:
				value.SetCalendarTimePoint(year/100,year%100,month,day,hour,minute,second)
			except iso.DateTimeError,e:
				raise ValueError(str(e))
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
		elif self.Match("."):
			# One of the elided numeric forms, don't parse the point!
			return self.ParseNumericLiteral()
		elif self.ParseInsensitive("nan"):
			if self.ParseOne("Dd"):
				result=edm.SimpleValue.NewValue(edm.SimpleType.Double)
				result.pyValue=float("Nan")
				return result
			elif self.ParseOne("Ff"):
				result=edm.SimpleValue.NewValue(edm.SimpleType.Single)
				result.pyValue=float("Nan")
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

	def ParseNumericLiteral(self,sign=''):
		"""Parses one of the number forms, returns a :py:class:`pyslet.mc_csdl.SimpleValue` instance.
		
		This method can return a value of type Decimal, Double, Single, Int64 or Int32.
		
		If no number if found then None is returned, if a number is partially parsed but is
		badly formed a ValueError exception is raised.
		
		*sign* is one of '+', '', or '-' indicating the sign parsed prior to the number."""
		digits=self.ParseDigits(1)
		if self.Parse("."):
			# could be a decimal
			decDigits=self.ParseDigits(1)
			if self.ParseOne("Mm"):
				result=edm.SimpleValue.NewValue(edm.SimpleType.Decimal)
				# it was a decimal
				if decDigits is None:
					raise ValueError("Missing digis after '.' for decimal: %s.d"%(digits))		
				if len(digits)>29 or len(decDigits)>29:
					raise ValueError("Too many digits for decimal literal: %s.%s"%(digits,decDigits))
				result.pyValue=decimal.Decimal("%s%s.%s"%(sign,digits,decDigits))
				return result
			elif self.ParseOne("Dd"):
				result=edm.SimpleValue.NewValue(edm.SimpleType.Double)
				if digits is None:
					digits='0'
				if decDigits is None:
					decDigits='0'
				# it was a double, no length restrictions
				result.pyValue=float("%s%s.%s"%(sign,digits,decDigits))
				return result
			elif self.ParseOne("Ee"):
				eSign=self.Parse("-")
				eDigits=self.RequireProduction(self.ParseDigits(1,3),"exponent")
				if self.ParseOne("Dd"):
					result=edm.SimpleValue.NewValue(edm.SimpleType.Double)
					if digits is None:
						raise ValueError("Missing digis before '.' for expDecimal")
					if decDigits is None:
						decDigits='0'
					elif len(decDigits)>16:
						raise ValueError("Too many digits for double: %s.%s"%(digits,decDigits))
					result.pyValue=float("%s%s.%se%s%s"%(sign,digits,decDigits,eSign,eDigits))
					return result
				elif self.ParseOne("Ff"):
					result=edm.SimpleValue.NewValue(edm.SimpleType.Single)
					if digits is None:
						raise ValueError("Missing digis before '.' for expDecimal")
					if decDigits is None:
						decDigits='0'
					elif len(decDigits)>8:
						raise ValueError("Too many digits for single: %s.%s"%(digits,decDigits))					
					elif len(eDigits)>2:
						raise ValueError("Too many digits for single exponet: %s.%sE%s%s"%(digits,decDigits,eSign,eDigits))					
					result.pyValue=float("%s%s.%se%s%s"%(sign,digits,decDigits,eSign,eDigits))
					return result
				else:
					raise ValueError("NotImplementedError")
			elif self.ParseOne("Ff"):
				result=edm.SimpleValue.NewValue(edm.SimpleType.Single)
				if digits is None:
					digits='0'
				if decDigits is None:
					decDigits='0'
				# it was a single, no length restrictions
				result.pyValue=float("%s%s.%s"%(sign,digits,decDigits))
				return result
			else:
				raise ValueError("NotImplementedError")
		elif digits is None:
			# no digits and no decimal point => this isn't a number
			return None
		elif self.ParseOne("Mm"):
			result=edm.SimpleValue.NewValue(edm.SimpleType.Decimal)
			if len(digits)>29:
				raise ValueError("Too many digits for decimal literal: %s"%digits)
			result.pyValue=decimal.Decimal("%s%s"%(sign,digits))
			return result
		elif self.ParseOne("Ll"):
			result=edm.SimpleValue.NewValue(edm.SimpleType.Int64)
			if len(digits)>19:
				raise ValueError("Too many digits for int64 literal: %s"%digits)
			result.pyValue=long("%s%s"%(sign,digits))
			return result
		elif self.ParseOne("Dd"):
			result=edm.SimpleValue.NewValue(edm.SimpleType.Double)
			if len(digits)>17:
				raise ValueError("Too many digits for double literal: %s"%digits)
			result.pyValue=float(sign+digits)
			return result
		elif self.ParseOne("Ff"):
			result=edm.SimpleValue.NewValue(edm.SimpleType.Single)
			if len(digits)>8:
				raise ValueError("Too many digits for single literal: %s"%digits)
			result.pyValue=float(sign+digits)
			return result
		else:
			result=edm.SimpleValue.NewValue(edm.SimpleType.Int32)
			# just a bunch of digits followed by something else so return int32
			if digits is None:
				raise ValueError("Digits required for integer literal: %s"%digits)				
			if len(digits)>10:
				raise ValueError("Too many digits for integer literal: %s"%digits)
			# watch out, largest negative number is larger than largest positive number!
			value=int(sign+digits)
			if value>2147483647 or value<-2147483648:
				raise ValueError("Range of int32 exceeded: %s"%(sign+digits))
			result.pyValue=value
			return result

	
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
	
	def __init__(self,dsURI,pathPrefix=''):
		if not isinstance(dsURI,uri.URI):
			dsURI=uri.URIFactory.URI(dsURI)
		self.schema=dsURI.scheme
		self.pathPrefix=pathPrefix		#: a string containing the path prefix without a trailing slash
		self.resourcePath=None			#: a string containing the resource path (or None if this is not a resource path)
		self.navPath=[]					#: a list of navigation path component strings
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
		if dsURI.query is not None:
			rawOptions=dsURI.query.split('&')
			for paramDef in rawOptions:
				if paramDef.startswith('$'):
					paramName=uri.UnescapeData(paramDef[1:paramDef.index('=')]).decode('utf-8')
					try:
						param=SystemQueryOption.DecodeValue(paramName)
						# Now parse the parameter value
						paramParser=Parser(uri.UnescapeData(paramDef[paramDef.index('=')+1:]).decode('utf-8'))
						if param==SystemQueryOption.filter:
							paramValue=paramParser.RequireProduction(paramParser.ParseCommonExpression(),"boolCommonExpression")
						else:
							paramValue=paramDef[paramDef.index('=')+1:]
					except ValueError, e:
						raise InvalidSystemQueryOption("$%s : %s"%(paramName,str(e)))
					self.sysQueryOptions[param]=paramValue
				else:
					if '=' in paramDef:
						paramName=uri.UnescapeData(paramDef[:paramDef.index('=')]).decode('utf-8')
						self.paramTable[paramName]=len(self.queryOptions)
					self.queryOptions.append(paramDef)
		self.resourcePath=dsURI.absPath[len(pathPrefix):]
		# grab the first component of the resourcePath
		if self.resourcePath=='/':
			self.navPath=[]
		else:
			components=self.resourcePath.split('/')
			self.navPath=map(self.SplitComponent,components[1:])
	
	def SplitComponent(self,component):
		"""Splits a string component into a unicode name and a keyPredicate dictionary."""
		if component.startswith('$'):
			# some type of control word
			return component,{}
		elif '(' in component and component[-1]==')':
			name=uri.UnescapeData(component[:component.index('(')]).decode('utf-8')
			keys=component[component.index('(')+1:-1]
			if keys=='':
				keys=[]
			else:
				keys=keys.split(',')
			if len(keys)==0:
				return name,{}
			elif len(keys)==1 and '=' not in keys[0]:
				return name,{u'':ParseURILiteral(keys[0]).pyValue}
			else:
				keyPredicate={}
				for k in keys:
					nv=k.split('=')
					if len(nv)!=2:
						raise ValueError("unrecognized key predicate: %s"%repr(keys))
					kname,value=nv
					kname=uri.UnescapeData(kname).decode('utf-8')
					kvalue=ParseURILiteral(value).pyValue
					keyPredicate[kname]=kvalue
				return name,keyPredicate
		else:
			return uri.UnescapeData(component).decode('utf-8'),{}
	
	def GetParamValue(self,paramName):
		if paramName in self.paramTable:
			paramDef=self.queryOptions[self.paramTable[paramName]]
			# must be a primitive type
			return ParseURILiteral(paramDef[paramDef.index('=')+1:])
		else:
			raise KeyError("Missing service operation, or custom parameter: %s"%paramName)
		
			
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
				pList=[]
				# picks up top-level properties only! 
				self.FindChildren(Property,pList)
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
		declaredType=self.GetSimpleType()
		if isinstance(value,edm.SimpleValue):
			type=self.GetNSAttribute((ODATA_METADATA_NAMESPACE,'type'))
			if declaredType is None:
				if type is None:
					self.SetAttribute((ODATA_METADATA_NAMESPACE,'type'),edm.SimpleType.EncodeValue(value.typeCode))
				else:
					# an unknown type can only be set from string, to match GetValue
					if value.tyepCode!=edm.SimpleType.String:
						raise TypeError("Incompatible property types: %s and %s"%(type,edm.SimpleType.EncodeValue(value.typeCode)))
			else:
				if declaredType!=value.typeCode:
					raise TypeError("Incompatible property types: %s and %s"%(type,edm.SimpleType.EncodeValue(value.typeCode)))
			if value:
				self.SetAttribute((ODATA_METADATA_NAMESPACE,'null'),None)
				ODataElement.SetValue(self,unicode(value))
			else:
				self.SetAttribute((ODATA_METADATA_NAMESPACE,'null'),"true")
				ODataElement.SetValue(self,"")
		elif isinstance(value,edm.Complex):
			type=self.GetNSAttribute((ODATA_METADATA_NAMESPACE,'type'))
			if type:
				if value.typeDef and value.typeDef.name!=type:
					raise TypeError("Incompatible complex types: %s and %s"%(type,value.typeDef.name))
			elif value.typeDef:
				self.SetAttribute((ODATA_METADATA_NAMESPACE,'type'),value.typeDef.name)
			self.SetAttribute((ODATA_METADATA_NAMESPACE,'null'),None)
			# loop through our children and set them from this value
			keys={}
			for key in value:
				keys[key]=value[key]				
			for child in self.GetChildren():
				if isinstance(child,Property):
					if child.xmlname in keys:
						child.SetValue(keys[child.xmlname])
						del keys[child.xmlname]
					# otherwise leave the value alone
			for key in keys:
				# add any missing children
				p=self.ChildElement(self.__class__,(ODATA_DATASERVICES_NAMESPACE,key))
				p.SetValue(keys[key])
		elif value is None:
			self.SetAttribute((ODATA_METADATA_NAMESPACE,'null'),"true")
			ODataElement.SetValue(self,"")
		else:
			edmValue=edm.SimpleValue.NewValue(edm.SimpleType.FromPythonType(type(value)))
			if declaredType is None:
				type=self.GetNSAttribute((ODATA_METADATA_NAMESPACE,'type'))
				# can only set from a string (literal form)
				if edmValue.typeCode!=edm.SimpleType.String:
					raise TypeError("Incompatible property types: %s and %s"%(type,edm.SimpleType.EncodeValue(edmValue.typeCode)))
			elif edmValue.typeCode!=declaredType:
				newValue=edm.SimpleValue.NewValue(declaredType)
				newValue.pyValue=edm.SimpleType.CoerceValue(declaredType,edmValue.pyValue)
				edmValue=newValue
			self.SetAttribute((ODATA_METADATA_NAMESPACE,'null'),None)
			ODataElement.SetValue(self,unicode(edmValue))

			
class Properties(ODataElement):
	"""Represents the properties element."""
	XMLNAME=(ODATA_METADATA_NAMESPACE,'properties')
	
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

	
class Entry(atom.Entry):
	"""Overrides the default :py:class:`pyslet.rfc4287.Entry` class to add OData handling.
	
	In addition to the default *parent* element an Entry can be passed
	an optional `pyslet.mc_csdl.Entity` instance.  If present, it is
	used to construct the Entry representation of the entity."""
	
	ContentClass=Content
	
	def __init__(self,parent,entity=None):
		atom.Entry.__init__(self,parent)
		self.entityType=None		#: :py:class:`pyslet.mc_csdl.EntityType` instance describing the entry
		self._properties={}
		if entity is not None:
			self.entityType=entity.typeDef
			for k in entity:
				self[k]=entity[k]
	
	def ContentChanged(self):
		atom.Entry.ContentChanged(self)
		self._properties={}
		if self.Content and self.Content.Properties:
			for p in self.Content.Properties.Property:
				self._properties[p.xmlname]=p
			
	def __getitem__(self,key):
		"""Enables :py:class:`Entry` to be suffixed with, e.g., ['PropertyName'] to read property values.
		
		Returns the value of the property with *key* as a
		`pyslet.mc_csdl.EDMValue` instance."""
		return self._properties[key].GetValue()

	def __setitem__(self,key,value):
		"""Enables :py:class:`Entry` to be suffixed with, e.g., ['PropertyName'] to set property values.
		
		Sets the property *key* to *value*.  If *value* is not an
		:py:class:`pyslet.mc_csdl.EDMValue` instance it will be coerced
		to an appropriate value on a best-effort basis.
		
		For existing properties, the *value* must be a compatible type
		and will be coerced to match the property's defined type if
		necessary.  See
		:py:meth:`Property.SetValue` for more information."""
		if key in self._properties:
			p=self._properties[key].SetValue(value)
		else:
			ps=self.ChildElement(self.ContentClass).ChildElement(Properties)
			p=ps.ChildElement(ps.PropertyClass,(ODATA_DATASERVICES_NAMESPACE,key))
			p.SetValue(value)
			self._properties[key]=p

	def AddLink(self,linkTitle,linkURI):
		"""Adds a link with name *linkTitle* to the entry with *linkURI*."""
		l=self.ChildElement(self.LinkClass)
		l.href=linkURI
		l.rel=ODATA_RELATED+linkTitle
		l.title=linkTitle
		l.type=ODATA_RELATED_TYPE

	def SetValue(self,entity):
		"""Sets the value of this Entry to represent *entity*, a :py:class:`pyslet.mc_csdl.TypeInstance` instance."""
		# start by removing the existing properties
		if self.Content and self.Content.Properties:
			self.Content.DeleteChild(self.Content.Properties)
		self.entityType=entity.typeDef
		for key in entity:
			self[key]=entity[key]
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


class EntitySet(edm.EntitySet):
	"""We override EntitySet inorder to provide some documented signatures for
	sets of media-stream entities."""
	
	def GetStreamType(self,entity):
		"""Returns the content type of the entity's media stream.
		
		Must return a :py:class:`pyslet.rfc2616.MediaType` instance."""
		raise NotImplementedError
	
	def GetStreamSize(self,entity):
		"""Returns the size of the entity's media stream in bytes."""
		raise NotImplementedError
		
	def GetStreamGenerator(self,entity):
		"""A generator function that yields blocks (strings) of data from the entity's media stream."""
		raise NotImplementedError

		
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

	def JSONDict(self):
		"""Returns a dictionary representation of this object."""
		d={}
		d['code']=self.Code.GetValue()
		d['message']=self.Message.GetValue()
		if self.InnerError:
			d['innererror']=self.InnerError.GetValue()
		return {'error':d}


class Code(ODataElement):
	XMLNAME=(ODATA_METADATA_NAMESPACE,'code')
	
class Message(ODataElement):
	XMLNAME=(ODATA_METADATA_NAMESPACE,'message')
	
class InnerError(ODataElement):
	XMLNAME=(ODATA_METADATA_NAMESPACE,'innererror')


class ODataJSONEncoder(json.JSONEncoder):
	def default(self, obj):
		if hasattr(obj,'JSONDict'):
			return obj.JSONDict()
		else:
			return json.JSONEncoder.default(self, obj)	


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
	
	DefaultAcceptList=http.AcceptList("application/atom+xml, application/xml; q=0.9, text/xml; q=0.8, text/plain; q=0.7, application/octet-stream; q=0.6")
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
		self.model=None					#: a :py:class:`pyslet.mc_edmx.Edmx` instance containing the model for the service
		self.defaultContainer=None		#: the default entity container
		
	def SetModel(self,model):
		"""Sets the model for the server from a parentless
		:py:class:`pyslet.mc_edmx.Edmx` instance or an Edmx
		:py:class:`pyslet.mc_edmx.Document` instance."""
		if isinstance(model,edmx.Document):
			model=model.root
		elif isinstance(model,edmx.Edmx):
			# create a document to hold the model
			doc=edmx.Document(root=model)
		else:
			raise TypeError("Edmx document or instance required for model")
		if self.model:
			# get rid of the old model
			for c in self.ws.Collection:
				c.DetachFromDocument()
				c.parent=None
			self.ws.Collection=[]
			self.defaultContainer=None
		for s in model.DataServices.Schema:
			for container in s.EntityContainer:
				# is this the default entity container?
				prefix=container.name+"."
				try:
					if container.GetAttribute(IsDefaultEntityContainer)=="true":
						prefix=""
						self.defaultContainer=container
				except KeyError:
					pass
				# define one feed for each entity set, prefixed with the name of the entity set
				for es in container.EntitySet:
					feed=self.ws.ChildElement(app.Collection)
					feed.href=prefix+es.name
					feed.ChildElement(atom.Title).SetValue(prefix+es.name)
		self.model=model
		
	def __call__(self,environ, start_response):
		"""wsgi interface for the server."""
		responseHeaders=[]
		try:
			result=self.CheckCapabilityNegotiation(environ,start_response,responseHeaders)
			if result is None:
				request=ODataURI(environ['PATH_INFO'],self.pathPrefix)
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
					responseType=self.ContentNegotiation(environ,self.RedirectTypes)
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
			else:
				return result
		except InvalidSystemQueryOption,e:
			return self.ODataError(environ,start_response,"InvalidSystemQueryOption","Invalid System Query Option: %s"%str(e))
		except ValueError,e:
			traceback.print_exception(*sys.exc_info())
			# This is a bad request
			return self.ODataError(environ,start_response,"ValueError",str(e))
		except:
			traceback.print_exception(*sys.exc_info())
			return self.HandleError(environ,start_response)

	def ODataError(self,environ,start_response,subCode,message='',code=400):
		"""Generates and ODataError, typically as the result of a bad request."""
		responseHeaders=[]
		e=Error(None)
		e.ChildElement(Code).SetValue(subCode)
		e.ChildElement(Message).SetValue(message)
		responseType=self.ContentNegotiation(environ,self.ErrorTypes)
		if responseType is None:
			# this is an error response, default to text/plain anyway
			responseType=http.MediaType('text/plain')
		elif responseType=="application/atom+xml":
			# even if you didn't ask for it, you get application/xml in this case
			responseType="application/xml"
		if responseType=="application/json":
			data=json.dumps(e,cls=ODataJSONEncoder)
		else:
			data=str(e)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(code,subCode),responseHeaders)
		return [data]
		
	def HandleRequest(self,requestURI,environ,start_response,responseHeaders):
		"""Handles a request that has been identified as being an OData request.
		
		*	*requestURI* is an :py:class:`ODataURI` instance with a non-empty resourcePath."""
		focus=None
		METADATA=1
		LINKS=2
		VALUE=3
		BATCH=4
		COUNT=5
		control=None
		path=[]
		try:
			for component in requestURI.navPath:
				name,keyPredicate=component
				if control==VALUE:
					# bad request, because $value must be the last thing in the path
					raise BadURISegment("%s since the object's parent is a dereferenced value"%name)							
				elif control==METADATA:
					# bad request, because $metadata must be the only thing in the path
					raise BadURISegment("%s since $metadata must be the only path component"%name)													
				elif control==BATCH:
					# bad request, because $batch must be the only thing in the path
					raise BadURISegment("%s since $batch must be the only path component"%name)
				elif control==COUNT:
					# bad request, because $count must be the only thing in the path
					raise BadURISegment("%s since $count must be the last path component"%name)																		
				if focus is None:
					if name=='$metadata':
						control=METADATA
						continue
					elif name=='$batch':
						control=BATCH
						continue
					elif name in self.defaultContainer:
						focus=self.defaultContainer[name]
					else:
						for s in self.model.DataServices.Schema:
							if name in s:
								focus=s[name]
								container=focus.FindParent(edm.EntityContainer)
								if container is self.defaultContainer:
									focus=None
								break
					if isinstance(focus,edm.FunctionImport):
						# TODO: grab the params from the query string
						params={}
						focus=focus.Execute(params)
						if not isinstance(focus,edm.FunctionEntitySet):
							# a function that returns anything other than an entity set
							for option in requestURI.sysQueryOptions:
								if option!=SystemQueryOption.format:
									raise InvalidSystemQueryOption('$'+SystemQueryOption.EncodeValue(option))
					if isinstance(focus,edm.EntitySet) or isinstance(focus,edm.FunctionEntitySet):
						if keyPredicate:
							# the keyPredicate can be passed directly as the key
							try:
								es=focus
								focus=es[keyPredicate]
								path=["%s(%s)"%(es.name,repr(focus.Key()))]
							except KeyError,e:
								raise MissingURISegment(name)
						else:
							# return this entity set
							path.append(focus.name)
# 					else:
# 						# Attempt to use the name of some other object type, bad request
# 						raise MissingURISegment(name)
				elif isinstance(focus,(edm.EntitySet,edm.DynamicEntitySet)):
					if name=="$count":
						control=COUNT
						for option in [
							SystemQueryOption.format,
							SystemQueryOption.skiptoken,
							SystemQueryOption.inlinecount,
							SystemQueryOption.select ]:
							if option in requestURI.sysQueryOptions:
								raise InvalidSystemQueryOption('$%s cannot be used with $count'%SystemQueryOption.EncodeValue(option))
						continue
					else:
						# bad request, because the collection must be the last thing in the path
						raise BadURISegment("%s since the object's parent is a collection"%name)
				elif isinstance(focus,edm.FunctionCollection):
					raise BadURISegment("%s since the object's parent is a collection"%name)					
				elif isinstance(focus,edm.Entity):
					if name in focus:
						if control:
							raise BadURISegment(name)
						# This is just a regular or dynamic property name
						focus=focus[name]
						path.append(name)
					elif name.startswith("$"):
						if control:
							raise BadURISegment(name)
						if name=="$links":
							control=LINKS
						elif name=="$count":
							control=COUNT
							for option in requestURI.sysQueryOptions:
								if option not in [SystemQueryOption.expand, SystemQueryOption.filter]:
									raise InvalidSystemQueryOption('$%s cannot be used with $count'%SystemQueryOption.EncodeValue(option))							
						elif name=="$value":
							hasStream=focus.typeDef.GetNSAttribute((ODATA_METADATA_NAMESPACE,'HasStream'))
							hasStream=(hasStream and hasStream.lower()=="true")
							if hasStream:
								control=VALUE
								for option in requestURI.sysQueryOptions:
									if option!=SystemQueryOption.format:
										raise InvalidSystemQueryOption('$%s cannot be used with media resource links'%SystemQueryOption.EncodeValue(option))							
							else:
								raise BadURISegment("%s since the entity is not a media stream"%name)
						else:
							raise BadURISegment(name)
					else:
						if control and control!=LINKS:
							raise BadURISegment("unexpected segment %s after system path component"%name)							
						try:
							# should be a navigation property
							if focus.IsEntityCollection(name):
								es=focus.Navigate(name)
								if keyPredicate:
									if control==LINKS:
										raise BadURISegment(name)
									try:
										focus=es[keyPredicate]
										path=["%s(%s)"%(es.name,repr(focus.Key()))]
									except KeyError,e:
										raise MissingURISegment(name)
								else:
									# return this entity set
									focus=es
									path.append(es.name)
							else:
								focus=focus.Navigate(name)
								# should be None or a specific entity this time
								if focus is None:
									raise MissingURISegment(name)
								elif keyPredicate:
									if control==LINKS:
										raise BadURISegment(name)
									# the key must match that of the entity
									if focus.Key()!=keyPredicate:
										raise MissingURISegment(name)
								path=["%s(%s)"%(focus.entitySet.name,repr(focus.Key()))]
						except KeyError:
							raise MissingURISegment(name)
				elif isinstance(focus,edm.Complex):
					if name in focus:
						# This is a regular property of the ComplexType
						focus=focus[name]
						path.append(name)
					elif name=="$value":
						raise NotImplementedError("$value")
					else:
						raise MissingURISegment(name)
				else:
					# Any other type is just a property or simple-type
					if name=="$value":
						control=VALUE
					else:
						raise BadURISegment(name)
			path=string.join(path,'/')
			if control==METADATA:
				if requestURI.sysQueryOptions:
					raise InvalidSystemQueryOption('$metadata document must not have sytem query options')				
				return self.ReturnMetadata(environ,start_response,responseHeaders)
			elif control==BATCH:
				if requestURI.sysQueryOptions:
					raise InvalidSystemQueryOption('$batch must not have sytem query options')				
				return self.ODataError(environ,start_response,"Bad Request","Batch requests not supported",404)
			elif isinstance(focus,edm.Entity):
				if control==COUNT:
					return self.ReturnCount(1,environ,start_response,responseHeaders)
				elif control==LINKS:
					for option in [
						SystemQueryOption.expand,
						SystemQueryOption.filter,
						SystemQueryOption.orderby,
						SystemQueryOption.select ]:
						if option in requestURI.sysQueryOptions:
							raise InvalidSystemQueryOption('$'+SystemQueryOption.EncodeValue(option))
					return self.ReturnLink(focus,environ,start_response,responseHeaders)				
				elif control==VALUE:
					return self.ReturnStream(focus,environ,start_response,responseHeaders)								
				else:
					for option in [
						SystemQueryOption.orderby,
						SystemQueryOption.skip,
						SystemQueryOption.top,
						SystemQueryOption.skiptoken,
						SystemQueryOption.inlinecount ]:
						if option in requestURI.sysQueryOptions:
							raise InvalidSystemQueryOption('$'+SystemQueryOption.EncodeValue(option))
					return self.ReturnEntity(path,focus,environ,start_response,responseHeaders)
			elif isinstance(focus,edm.EDMValue):
				for option in [
					SystemQueryOption.expand,
					SystemQueryOption.orderby,
					SystemQueryOption.skip,
					SystemQueryOption.top,
					SystemQueryOption.skiptoken,
					SystemQueryOption.inlinecount,
					SystemQueryOption.select ]:
					if option in requestURI.sysQueryOptions:
						raise InvalidSystemQueryOption('$'+SystemQueryOption.EncodeValue(option))
				if isinstance(focus,edm.SimpleValue) and SystemQueryOption.filter in requestURI.sysQueryOptions:
					raise InvalidSystemQueryOption("$filter")					
				if control==VALUE:
					return self.ReturnDereferencedValue(focus,environ,start_response,responseHeaders)
				else:
					return self.ReturnValue(focus,environ,start_response,responseHeaders)
			elif isinstance(focus,edm.EntitySet) or isinstance(focus,edm.DynamicEntitySet):
				if control==COUNT:
					return self.ReturnCount(len(focus),environ,start_response,responseHeaders)
				elif control==LINKS:
					for option in [
						SystemQueryOption.expand,
						SystemQueryOption.filter,
						SystemQueryOption.orderby,
						SystemQueryOption.select ]:
						if option in requestURI.sysQueryOptions:
							raise InvalidSystemQueryOption('$'+SystemQueryOption.EncodeValue(option))
					return self.ReturnLinks(focus,environ,start_response,responseHeaders)				
				else:
					return self.ReturnEntityCollection(path,focus,environ,start_response,responseHeaders)
			elif isinstance(focus,edm.FunctionCollection):
				return self.ReturnCollection(focus,environ,start_response,responseHeaders)
			else:	
				# an empty navPath means we are trying to get the service root
				wrapper=WSGIWrapper(environ,start_response,responseHeaders)
				# super essentially allows us to pass a bound method of our parent
				# that we ourselves are hiding.
				return wrapper.call(super(Server,self).__call__)
		except InvalidSystemQueryOption,e:
			return self.ODataError(environ,start_response,"Bad Request","System query option is cannot be used with this form of URI: %s"%str(e),400)
		except MissingURISegment,e:
			return self.ODataError(environ,start_response,"Bad Request","Resource not found for component %s"%str(e),404)
		except BadURISegment,e:
			return self.ODataError(environ,start_response,"Bad Request","Resource not found for component %s"%str(e),400)
	
	def ReturnMetadata(self,environ,start_response,responseHeaders):
		doc=self.model.GetDocument()
		responseType=self.ContentNegotiation(environ,self.MetadataTypes)
		if responseType is None:
			return self.ODataError(environ,start_response,"Not Acceptable",'xml or plain text formats supported',406)
		data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
			
	def ReturnLinks(self,entities,environ,start_response,responseHeaders):
		doc=Document(root=Links)
		for e in entities.itervalues():
			child=doc.root.ChildElement(URI)
			child.SetValue(str(self.serviceRoot)+"%s(%s)"%(e.entitySet.name,repr(e.Key())))
		responseType=self.ContentNegotiation(environ,self.ValueTypes)
		if responseType is None:
			return self.ODataError(environ,start_response,"Not Acceptable",'xml, json or plain text formats supported',406)
		if responseType=="application/json":
			data=json.dumps(links,cls=ODataJSONEncoder)
		else:
			data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
		
	def ReturnLink(self,entity,environ,start_response,responseHeaders):
		doc=Document(root=URI)
		doc.root.SetValue(str(self.serviceRoot)+"%s(%s)"%(entity.entitySet.name,repr(entity.Key())))
		responseType=self.ContentNegotiation(environ,self.ValueTypes)
		if responseType is None:
			return self.ODataError(environ,start_response,"Not Acceptable",'xml, json or plain text formats supported',406)
		if responseType=="application/json":
			data=json.dumps(doc.root,cls=ODataJSONEncoder)
		else:
			data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
			
	def ReturnEntityCollection(self,path,entities,environ,start_response,responseHeaders):
		"""Returns an iterable of Entities."""
		doc=Document(root=atom.Feed)
		f=doc.root
		#f.MakePrefix(ODATA_DATASERVICES_NAMESPACE,u'd')
		#f.MakePrefix(ODATA_METADATA_NAMESPACE,u'm')
		f.SetBase(str(self.serviceRoot))
		# f.ChildElement(atom.Title).SetValue(entities.GetTitle())
		f.ChildElement(atom.AtomId).SetValue(str(self.serviceRoot)+path)
		# f.ChildElement(atom.Updated).SetValue(entities.GetUpdated())
		for e in entities.itervalues():
			entry=f.ChildElement(atom.Entry)
			entry.ChildElement(atom.AtomId).SetValue(str(self.serviceRoot)+"%s(%s)"%(e.entitySet.name,repr(e.Key())))		
		# do stuff with the entries themselves, add link elements etc
		responseType=self.ContentNegotiation(environ,self.FeedTypes)
		if responseType is None:
			return self.ODataError(environ,start_response,"Not Acceptable",'xml, json or plain text formats supported',406)
		if responseType=="application/json":
			data=json.dumps(f,cls=ODataJSONEncoder)
		else:
			# Here's a challenge, we want to pull data through the feed by yielding strings
			# just load in to memory at the moment
			data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
				
	def ReturnEntity(self,path,entity,environ,start_response,responseHeaders):
		"""Returns a single Entity."""
		doc=Document(root=Entry)
		e=doc.root
		e.SetBase(str(self.serviceRoot))
		e.ChildElement(atom.AtomId).SetValue(str(self.serviceRoot)+path)
		e.SetValue(entity)
		# TODO: do stuff with the entries themselves, add link elements etc
		responseType=self.ContentNegotiation(environ,self.EntryTypes)
		if responseType is None:
			return self.ODataError(environ,start_response,"Not Acceptable",'xml, json or plain text formats supported',406)
		if responseType=="application/json":
			data=json.dumps(e,cls=ODataJSONEncoder)
		else:
			# Here's a challenge, we want to pull data through the feed by yielding strings
			# just load in to memory at the moment
			data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]

	def ReturnStream(self,entity,environ,start_response,responseHeaders):
		"""Returns a media stream."""
		types=[entity.entitySet.GetStreamType(entity)]+self.StreamTypes
		responseType=self.ContentNegotiation(environ,types)
		if responseType is None:
			return self.ODataError(environ,start_response,"Not Acceptable",'media stream type refused, try application/octet-stream',406)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",entity.entitySet.GetStreamSize(entity)))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return entity.entitySet.GetStreamGenerator(entity)

	def ReturnValue(self,value,environ,start_response,responseHeaders):
		"""Returns a single property value."""
		e=Property(None)
		e.SetXMLName((ODATA_DATASERVICES_NAMESPACE,value.name))
		doc=Document(root=e)
		e.SetValue(value)
		responseType=self.ContentNegotiation(environ,self.ValueTypes)
		if responseType is None:
			return self.ODataError(environ,start_response,"Not Acceptable",'xml, json or plain text formats supported',406)
		if responseType=="application/json":
			data=json.dumps(e,cls=ODataJSONEncoder)
		else:
			data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
				
	def ReturnDereferencedValue(self,value,environ,start_response,responseHeaders):
		"""Returns a dereferenced property value."""
		responseType=self.ContentNegotiation(environ,self.DereferenceTypes)
		if responseType is None:
			return self.ODataError(environ,start_response,"Not Acceptable",'$value requires plain text or octet-stream formats',406)
		data=unicode(value).encode('utf-8')
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
				
	def ReturnCollection(self,collection,environ,start_response,responseHeaders):
		"""Returns a collection of values."""
		e=Collection(None)
		e.SetXMLName((ODATA_METADATA_NAMESPACE,collection.name))
		doc=Document(root=e)
		for value in collection:
			p=e.ChildElement(Property)
			p.SetXMLName((ODATA_DATASERVICES_NAMESPACE,value.name))
			p.SetValue(value)
		responseType=self.ContentNegotiation(environ,self.ValueTypes)
		if responseType is None:
			return self.ODataError(environ,start_response,"Not Acceptable",'xml, json or plain text formats supported',406)
		if responseType=="application/json":
			data=json.dumps(e,cls=ODataJSONEncoder)
		else:
			data=str(doc)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]

	def ReturnCount(self,number,environ,start_response,responseHeaders):
		"""Returns the single value number."""
		responseType=self.ContentNegotiation(environ,self.DereferenceTypes)
		if responseType is None:
			return self.ODataError(environ,start_response,"Not Acceptable",'$count requires plain text or octet-stream formats',406)
		data=str(number)
		responseHeaders.append(("Content-Type",str(responseType)))
		responseHeaders.append(("Content-Length",str(len(data))))
		start_response("%i %s"%(200,"Success"),responseHeaders)
		return [data]
				
	def ContentNegotiation(self,environ,mTypeList):
		"""Given a list of media types, examines the Accept header and returns the best match.
		
		If there is no match then None is returned."""
		if "HTTP_Accept" in environ:
			try:
				aList=http.AcceptList(environ["HTTP_Accept"])
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
		if "HTTP_DataServiceVersion" in environ:
			major,minor,ua=ParseDataServiceVersion(environ["HTTP_DataServiceVersion"])
		else:
			major=2
			minor=0
		if "HTTP_MaxDataServiceVersion" in environ:
			maxMajor,maxMinor,sa=ParseMaxDataServiceVersion(environ["HTTP_MaxDataServiceVersion"])
		else:
			maxMajor=major
			maxMinor=minor
		if major>2 or (major==2 and minor>0):
			# we can't cope with this request
			return self.ODataError(environ,start_response,"DataServiceVersionMismatch","Maximum supported protocol version: 2.0")
		if maxMajor>=2:
			responseHeaders.append(('DataServiceVersion','2.0; pyslet %s'%info.version))
		else:
			responseHeaders.append(('DataServiceVersion','1.0; pyslet %s'%info.version))
		return None
			
	
class Document(app.Document):
	"""Class for working with OData documents."""
	classMap={}
	
	def __init__(self,**args):
		app.Document.__init__(self,**args)
		self.MakePrefix(ODATA_METADATA_NAMESPACE,'m')
		self.MakePrefix(ODATA_DATASERVICES_NAMESPACE,'d')
	
	def GetElementClass(self,name):
		"""Returns the OData, APP or Atom class used to represent name.
		
		Overrides :py:meth:`~pyslet.rfc5023.Document.GetElementClass` to allow
		custom implementations of the Atom or APP classes to be created and
		to cater for OData-specific elements."""
		result=Document.classMap.get(name,None)
		if result is None:
			if name[0]==ODATA_DATASERVICES_NAMESPACE:
				result=Property
			else:
				result=app.Document.GetElementClass(self,name)
		return result


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
					if container.GetAttribute(IsDefaultEntityContainer)=="true":
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

			
xmlns.MapClassElements(Document.classMap,globals())