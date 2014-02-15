#! /usr/bin/env python
"""OData core elements"""

from pyslet.unicode5 import CharClass, DetectEncoding
import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsi
import pyslet.rfc2396 as uri
import pyslet.rfc2616 as http
import pyslet.rfc4287 as atom
import pyslet.rfc5023 as app
import pyslet.iso8601 as iso
import csdl as edm

import string, itertools, json, base64, decimal, uuid, math
from types import *

ODATA_METADATA_NAMESPACE="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"	#: namespace for metadata, e.g., the property type attribute
IsDefaultEntityContainer=(ODATA_METADATA_NAMESPACE,u"IsDefaultEntityContainer")
MimeType=(ODATA_METADATA_NAMESPACE,u"MimeType")
HttpMethod=(ODATA_METADATA_NAMESPACE,u"HttpMethod")
HasStream=(ODATA_METADATA_NAMESPACE,u"HasStream")
DataServiceVersion=(ODATA_METADATA_NAMESPACE,"DataServiceVersion")
FC_KeepInContent=(ODATA_METADATA_NAMESPACE,"FC_KeepInContent")
FC_TargetPath=(ODATA_METADATA_NAMESPACE,"FC_TargetPath")
FC_NsPrefix=(ODATA_METADATA_NAMESPACE,"FC_NsPrefix")
FC_NsUri=(ODATA_METADATA_NAMESPACE,"FC_NsUri")
FC_SourcePath=(ODATA_METADATA_NAMESPACE,"FC_SourcePath")

ODATA_DATASERVICES_NAMESPACE="http://schemas.microsoft.com/ado/2007/08/dataservices"		#: namespace for auto-generated elements, e.g., :py:class:`Property`
ODATA_SCHEME="http://schemas.microsoft.com/ado/2007/08/dataservices/scheme"					#: category scheme for type definition terms
ODATA_RELATED="http://schemas.microsoft.com/ado/2007/08/dataservices/related/"				#: link type for related entries

ODATA_RELATED_ENTRY_TYPE="application/atom+xml;type=entry"
ODATA_RELATED_FEED_TYPE="application/atom+xml;type=feed"

class InvalidLiteral(Exception): pass
class InvalidServiceDocument(Exception): pass
class InvalidMetadataDocument(Exception): pass
class InvalidFeedDocument(Exception): pass
class InvalidEntryDocument(Exception): pass
class InvalidFeedURL(Exception): pass

class ServerError(Exception): pass
class BadURISegment(ServerError): pass
class MissingURISegment(ServerError): pass
class InvalidSystemQueryOption(ServerError): pass
class InvalidPathOption(ServerError): pass
class InvalidMethod(ServerError): pass
class InvalidData(ServerError): pass
class EvaluationError(Exception): pass


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

	IsSpecial=None
	"""A set of Operator values that are special, in that they do no
	describe the simple pattern::
	
		[lvalue] opname right-value  
	
	For example, isof, negate, method, etc..."""
	
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

Operator.IsSpecial=set(
	(Operator.paren,Operator.member,Operator.methodCall,Operator.negate,Operator.cast,Operator.isof))
	

	
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

	@staticmethod
	def FromString(src):
		p=Parser(src)
		return p.RequireProductionEnd(p.ParseCommonExpression(),"commonExpression")
	
	@staticmethod
	def OrderByFromString(src):
		p=Parser(src)
		return p.RequireProductionEnd(p.ParseOrderbyOption(),"orderbyOption")

	@staticmethod
	def OrderByToString(orderBy):
		return string.join(map(lambda x:"%s %s"%(unicode(x[0]),"asc" if x[1]>0 else "desc"),orderBy),', ')
		
	def __unicode__(self):
		raise NotImplementedError
	
	
class UnaryExpression(CommonExpression):
	
	EvalMethod={
		}
	"""A mapping from unary operator constants to unbound methods that
	evaluate the operator."""

	def __init__(self,operator):
		super(UnaryExpression,self).__init__(operator)

	def __unicode__(self):
		if self.operator==Operator.negate:
			op=u"-"
		else:
			op=u"%s "%Operator.EncodeValue(self.operator)
		rValue=self.operands[0]
		if rValue.operator is not None and rValue<self:
			# right expression is weaker than us, use brackets
			result="%s(%s)"%(op,unicode(rValue))
		else:
			result="%s%s"%(op,unicode(rValue))
		return result

	def Evaluate(self,contextEntity):
		rValue=self.operands[0].Evaluate(contextEntity)
		return self.EvalMethod[self.operator](self,rValue)

	def EvaluateNegate(self,rValue):
		typeCode=rValue.typeCode
		if typeCode in (edm.SimpleType.Byte, edm.SimpleType.Int16):
			rValue=rValue.SimpleCast(edm.SimpleType.Int32)
		elif typeCode == edm.SimpleType.Single:
			rValue=rValue.SimpleCast(edm.SimpleType.Double)
		typeCode=rValue.typeCode
		if typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64, edm.SimpleType.Double, edm.SimpleType.Decimal):
			result=edm.EDMValue.NewSimpleValue(typeCode)
			if rValue:
				result.SetFromValue(0-rValue.value)
			return result
		elif typeCode is None:	# -null
			return edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
		else:
			raise EvaluationError("Illegal operand for negate")

	def EvaluateNot(self,rValue):
		if isinstance(rValue,edm.SimpleValue):
			if rValue:
				typeCode=rValue.typeCode
				if typeCode==edm.SimpleType.Boolean:
					result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
					result.SetFromValue(not rValue.value)
					return result
				else:
					raise EvaluationError("Illegal operand for not")
			else:
				result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
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
	
	def __unicode__(self):
		opPrefix=opSuffix=''
		if self.operator in Operator.IsSpecial:
			if self.operator==Operator.member:
				op=u"/"
			elif self.operator in (Operator.cast,Operator.isof):
				opPrefix=u"%s("%Operator.EncodeValue(self.operator)
				op=","
				opSuffix=")"
			else:
				raise ValueError("Can't format %s as a binary operator"&Operator.EncodeValue(self.operator))
		else:
			op=u" %s "%Operator.EncodeValue(self.operator)
		lValue=self.operands[0]
		rValue=self.operands[1]
		if lValue.operator is not None and lValue<self:
			# left expression is weaker than us, use brackets
			lValue="(%s)"%unicode(lValue)
		else:
			lValue=unicode(lValue)
		if rValue.operator is not None and rValue<self:
			# right expression is weaker than us, use brackets
			rValue="(%s)"%unicode(rValue)
		else:
			rValue=unicode(rValue)
		return string.join((opPrefix,lValue,op,rValue,opSuffix),'')
			
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
				typeCode=edm.SimpleType.DecodeValue(rValue.value)
				result=edm.EDMValue.NewSimpleValue(typeCode)
			except ValueError:
				result=edm.SimpleValue.NewValue(None)
			return result		
		elif isinstance(lValue,edm.Entity):
			# in the future we should deal with entity type inheritance
			# right now, the only thing we can cast an entity instance
			# to is itself
			name=lValue.typeDef.GetFQName()
			if name==rValue.value:
				return lValue
			else:
				raise EvaluationError("Can't cast %s to %s"%(name,str(rValue.value)))
		elif isinstance(lValue,edm.SimpleValue):
			# look up the name of the primitive type
			try:
				typeCode=edm.SimpleType.DecodeValue(rValue.value)
			except ValueError:
				raise EvaluationError("Unrecognized type: %s"%str(rValue.value))
			newCode=PromoteTypes(typeCode,lValue.typeCode)
			if typeCode!=newCode:
				raise EvaluationError("Can't cast %s to %s"%(edm.SimpleType.EncodeValue(lValue.typeCode),
					edm.SimpleType.EncodeValue(typeCode)))
			result=edm.EDMValue.NewSimpleValue(typeCode)
			result.SetFromValue(lValue.value)
			return result
		else:
			raise EvaluationError("Illegal operands for isof")		
	
	def EvaluateMul(self,lValue,rValue):
		typeCode=self.PromoteOperands(lValue,rValue)
		if typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64, edm.SimpleType.Single,
			edm.SimpleType.Double, edm.SimpleType.Decimal):
			lValue=lValue.SimpleCast(typeCode)
			rValue=rValue.SimpleCast(typeCode)
			result=edm.EDMValue.NewSimpleValue(typeCode)
			if lValue and rValue:
				result.SetFromValue(lValue.value*rValue.value)
			return result
		elif typeCode is None:	# null mul null
			return edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
		else:
			raise EvaluationError("Illegal operands for mul")
	
	def EvaluateDiv(self,lValue,rValue):
		try:
			typeCode=self.PromoteOperands(lValue,rValue)
			if typeCode in (edm.SimpleType.Single, edm.SimpleType.Double, edm.SimpleType.Decimal):
				lValue=lValue.SimpleCast(typeCode)
				rValue=rValue.SimpleCast(typeCode)
				result=edm.EDMValue.NewSimpleValue(typeCode)
				if lValue and rValue:
					result.SetFromValue(lValue.value/rValue.value)
				return result
			elif typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64):
				lValue=lValue.SimpleCast(typeCode)
				rValue=rValue.SimpleCast(typeCode)
				result=edm.EDMValue.NewSimpleValue(typeCode)
				if lValue and rValue:
					# OData doesn't really specify integer division rules so
					# we use floating point division and truncate towards zero
					result.SetFromValue(int(float(lValue.value)/float(rValue.value)))
				return result
			elif typeCode is None:	# null div null
				return edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
			else:
				raise EvaluationError("Illegal operands for div")
		except ZeroDivisionError as e:
			raise EvaluationError(str(e))
	
	def EvaluateMod(self,lValue,rValue):
		try:
			typeCode=self.PromoteOperands(lValue,rValue)
			if typeCode in (edm.SimpleType.Single, edm.SimpleType.Double, edm.SimpleType.Decimal):
				lValue=lValue.SimpleCast(typeCode)
				rValue=rValue.SimpleCast(typeCode)
				result=edm.EDMValue.NewSimpleValue(typeCode)
				if lValue and rValue:
					result.SetFromValue(math.fmod(lValue.value,rValue.value))
				return result
			elif typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64):
				lValue=lValue.SimpleCast(typeCode)
				rValue=rValue.SimpleCast(typeCode)
				result=edm.EDMValue.NewSimpleValue(typeCode)
				if lValue and rValue:
					# OData doesn't really specify integer division rules so
					# we use floating point division and truncate towards zero
					result.SetFromValue(int(math.fmod(float(lValue.value),float(rValue.value))))
				return result
			elif typeCode is None:	# null div null
				return edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
			else:
				raise EvaluationError("Illegal operands for div")
		except (ZeroDivisionError,ValueError) as e:
			raise EvaluationError(str(e))
				
	def EvaluateAdd(self,lValue,rValue):
		typeCode=self.PromoteOperands(lValue,rValue)
		if typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64, edm.SimpleType.Single,
			edm.SimpleType.Double, edm.SimpleType.Decimal):
			lValue=lValue.SimpleCast(typeCode)
			rValue=rValue.SimpleCast(typeCode)
			result=edm.EDMValue.NewSimpleValue(typeCode)
			if lValue and rValue:
				result.SetFromValue(lValue.value+rValue.value)
			return result
		elif typeCode is None:	# null add null
			return edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
		else:
			raise EvaluationError("Illegal operands for add")
	
	def EvaluateSub(self,lValue,rValue):
		typeCode=self.PromoteOperands(lValue,rValue)
		if typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64, edm.SimpleType.Single,
			edm.SimpleType.Double, edm.SimpleType.Decimal):
			lValue=lValue.SimpleCast(typeCode)
			rValue=rValue.SimpleCast(typeCode)
			result=edm.EDMValue.NewSimpleValue(typeCode)
			if lValue and rValue:
				result.SetFromValue(lValue.value-rValue.value)
			return result
		elif typeCode is None:	# null sub null
			return edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
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
			lValue=lValue.SimpleCast(typeCode)
			rValue=rValue.SimpleCast(typeCode)
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
			if lValue and rValue:
				result.SetFromValue(relation(lValue.value,rValue.value))
			else:
				# one of the operands is null => False
				result.SetFromValue(False)
			return result
		elif typeCode in (edm.SimpleType.String, edm.SimpleType.DateTime, edm.SimpleType.Guid):
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
			result.SetFromValue(relation(lValue.value,rValue.value))
			return result
		elif typeCode is None:	# e.g., null lt null
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
			result.SetFromValue(False)
			return result
		else:
			raise EvaluationError("Illegal operands for %s"%Operator.EncodeValue(self.operator))
		
	def EvaluateIsOf(self,lValue,rValue):
		# rValue is always a string literal name of the type to look up
		if not lValue:
			# isof(NULL, <any type> ) is False
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
			result.SetFromValue(False)
			return result
		elif isinstance(lValue,edm.Entity):
			# in the future we should test the entity for inheritance
			name=lValue.typeDef.GetFQName()
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
			result.SetFromValue(name==rValue.value)
			return result
		elif isinstance(lValue,edm.SimpleValue):
			# look up the name of the primitive type
			try:
				typeCode=edm.SimpleType.DecodeValue(rValue.value)
			except ValueError:
				raise EvaluationError("Unrecognized type: %s"%str(rValue.value))
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
			# we return True if the type of the target, when promoted with type
			# being tested results in the type being tested
			try:
				rValue=(typeCode==PromoteTypes(typeCode,lValue.typeCode))
			except EvaluationError:
				# incompatible types means False
				rValue=False
			result.SetFromValue(rValue)
			return result
		else:
			raise EvaluationError("Illegal operands for isof")		
	
	def EvaluateEq(self,lValue,rValue):
		if isinstance(lValue,edm.Entity) and isinstance(rValue,edm.Entity):
			# we can do comparison of entities, but must be the same entity!
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
			if lValue.entitySet is rValue.entitySet:
				# now test that the keys are the same
				result.value=(lValue.Key()==rValue.Key())
			else:
				result.value=False
			return result
		else:
			typeCode=self.PromoteOperands(lValue,rValue)
			if typeCode in (edm.SimpleType.Int32, edm.SimpleType.Int64, edm.SimpleType.Single,
				edm.SimpleType.Double, edm.SimpleType.Decimal):
				lValue=lValue.SimpleCast(typeCode)
				rValue=rValue.SimpleCast(typeCode)
				result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
				result.SetFromValue(lValue.value==rValue.value)
				return result
			elif typeCode in (edm.SimpleType.String, edm.SimpleType.DateTime, edm.SimpleType.Guid, edm.SimpleType.Binary):
				result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
				result.SetFromValue(lValue.value==rValue.value)
				return result
			elif typeCode is None:	# null eq null
				result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
				result.SetFromValue(True)
				return result
			else:
				raise EvaluationError("Illegal operands for add")
	
	def EvaluateNe(self,lValue,rValue):
		result=self.EvaluateEq(lValue,rValue)
		result.value=not result.value
		return result
	
	def EvaluateAnd(self,lValue,rValue):
		"""Watch out for the differences between OData 2-value logic and
		the usual SQL 3-value approach."""
		typeCode=self.PromoteOperands(lValue,rValue)
		if typeCode==edm.SimpleType.Boolean:
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
			if lValue and rValue:
				result.value=lValue.value and rValue.value
			else:
				result.value=False
			return result
		elif typeCode is None:
			# null or null
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
			result.value=False
			return result
		else:			
			raise EvaluationError("Illegal operands for boolean and")
				
	def EvaluateOr(self,lValue,rValue):
		"""Watch out for the differences between OData 2-value logic and
		the usual SQL 3-value approach."""
		typeCode=self.PromoteOperands(lValue,rValue)
		if typeCode==edm.SimpleType.Boolean:
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
			if lValue and rValue:
				result.value=lValue.value or rValue.value
			else:
				result.value=False
			return result
		elif typeCode is None:
			# null or null
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
			result.value=False
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

	def __unicode__(self):
		"""Return, for example, 42L or 'Paddy O''brian'	- note that %-encoding is not applied"""
		if not self.value:
			return "null"
		else:
			result=unicode(self.value)
			if self.value.typeCode==edm.SimpleType.Binary:
				result="X'%s'"%result
			elif self.value.typeCode==edm.SimpleType.DateTime:
				result="datetime'%s'"%result
			elif self.value.typeCode==edm.SimpleType.Decimal:
				result=result+"M"
			elif self.value.typeCode==edm.SimpleType.Double:
				result=result+"D"
			elif self.value.typeCode==edm.SimpleType.Single:
				result=result+"F"
			elif self.value.typeCode==edm.SimpleType.Guid:
				result="guid'%s'"%result
			elif self.value.typeCode==edm.SimpleType.Int64:
				result=result+"L"
			elif self.value.typeCode==edm.SimpleType.Time:
				result="time'%s'"%result
			elif self.value.typeCode==edm.SimpleType.DateTimeOffset:
				result="datetimeoffset'%s'"%result
			elif self.value.typeCode==edm.SimpleType.String:
				# double up on single quotes
				result="'%s'"%string.join(result.split("'"),"''")
			return result
	
	def Evaluate(self,contextEntity):
		"""A literal evaluates to itself."""
		return self.value


class PropertyExpression(CommonExpression):
	
	def __init__(self,name):
		super(PropertyExpression,self).__init__()
		self.name=name
	
	def __unicode__(self):
		return unicode(self.name)
			
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
						result=edm.EDMValue.NewValue(None)
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

	def __unicode__(self):
		return "%s(%s)"%(Method.EncodeValue(self.method),string.join(map(lambda x:unicode(x),self.operands),','))

	def Evaluate(self,contextEntity):
		return self.EvalMethod[self.method](self,
			map(lambda x:x.Evaluate(contextEntity),self.operands))

	def PromoteParameter(self,arg,typeCode):
		if isinstance(arg,edm.SimpleValue):
			if CanCastMethodArgument(arg.typeCode,typeCode):
				return arg.SimpleCast(typeCode)
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
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
			if target and prefix:
				result.SetFromValue(target.value.endswith(prefix.value))
			return result
		else:
			raise EvaluationError("endswith() takes 2 arguments, %i given"%len(args))

	def EvaluateIndexof(self,args):
		if (len(args)==2):
			target=self.PromoteParameter(args[0],edm.SimpleType.String)
			searchString=self.PromoteParameter(args[1],edm.SimpleType.String)
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
			if target and searchString:
				result.SetFromValue(target.value.find(searchString.value))
			return result
		else:
			raise EvaluationError("indexof() takes 2 arguments, %i given"%len(args))

	def EvaluateReplace(self,args):
		if (len(args)==3):
			target=self.PromoteParameter(args[0],edm.SimpleType.String)
			searchString=self.PromoteParameter(args[1],edm.SimpleType.String)
			replaceString=self.PromoteParameter(args[2],edm.SimpleType.String)
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
			if target and searchString and replaceString:
				result.SetFromValue(target.value.replace(searchString.value,replaceString.value))
			return result
		else:
			raise EvaluationError("replace() takes 3 arguments, %i given"%len(args))

	def EvaluateStartswith(self,args):
		if (len(args)==2):
			target=self.PromoteParameter(args[0],edm.SimpleType.String)
			prefix=self.PromoteParameter(args[1],edm.SimpleType.String)
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
			if target and prefix:
				result.SetFromValue(target.value.startswith(prefix.value))
			return result
		else:
			raise EvaluationError("startswith() takes 2 arguments, %i given"%len(args))

	def EvaluateTolower(self,args):
		if (len(args)==1):
			target=self.PromoteParameter(args[0],edm.SimpleType.String)
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
			if target:
				result.SetFromValue(target.value.lower())
			return result
		else:
			raise EvaluationError("tolower() takes 1 argument, %i given"%len(args))

	def EvaluateToupper(self,args):
		if (len(args)==1):
			target=self.PromoteParameter(args[0],edm.SimpleType.String)
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
			if target:
				result.SetFromValue(target.value.upper())
			return result
		else:
			raise EvaluationError("toupper() takes 1 argument, %i given"%len(args))

	def EvaluateTrim(self,args):
		if (len(args)==1):
			target=self.PromoteParameter(args[0],edm.SimpleType.String)
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
			if target:
				result.SetFromValue(target.value.strip())
			return result
		else:
			raise EvaluationError("trim() takes 1 argument, %i given"%len(args))

	def EvaluateSubstring(self,args):
		if (len(args)==2 or len(args)==3):
			target=self.CheckStrictParameter(args[0],edm.SimpleType.String)
			start=self.CheckStrictParameter(args[1],edm.SimpleType.Int32)
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
			if len(args)==3:
				length=self.CheckStrictParameter(args[2],edm.SimpleType.Int32)
			else:
				length=None
			if target and start:
				if length:
					result.SetFromValue(target.value[start.value:start.value+length.value])
				else:
					result.SetFromValue(target.value[start.value:])
			return result
		else:
			raise EvaluationError("substring() takes 2 or 3 arguments, %i given"%len(args))

	def EvaluateSubstringof(self,args):
		if (len(args)==2):
			searchString=self.PromoteParameter(args[0],edm.SimpleType.String)
			target=self.PromoteParameter(args[1],edm.SimpleType.String)
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
			if target and searchString:
				result.SetFromValue(target.value.find(searchString.value)>=0)
			return result
		else:
			raise EvaluationError("substringof() takes 2 arguments, %i given"%len(args))

	def EvaluateConcat(self,args):
		if (len(args)==2):
			leftString=self.CheckStrictParameter(args[0],edm.SimpleType.String)
			rightString=self.CheckStrictParameter(args[1],edm.SimpleType.String)
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
			if leftString and rightString:
				result.SetFromValue(leftString.value+rightString.value)
			return result
		else:
			raise EvaluationError("concat() takes 2 arguments, %i given"%len(args))

	def EvaluateLength(self,args):
		if (len(args)==1):
			target=self.CheckStrictParameter(args[0],edm.SimpleType.String)
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
			if target:
				result.SetFromValue(len(target.value))
			return result
		else:
			raise EvaluationError("length() takes 1 argument, %i given"%len(args))

	def EvaluateYear(self,args):
		if (len(args)==1):
			target=self.CheckStrictParameter(args[0],edm.SimpleType.DateTime)
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
			if target:
				result.SetFromValue(target.value.date.century*100+target.value.date.year)
			return result
		else:
			raise EvaluationError("year() takes 1 argument, %i given"%len(args))

	def EvaluateMonth(self,args):
		if (len(args)==1):
			target=self.CheckStrictParameter(args[0],edm.SimpleType.DateTime)
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
			if target:
				result.SetFromValue(target.value.date.month)
			return result
		else:
			raise EvaluationError("month() takes 1 argument, %i given"%len(args))

	def EvaluateDay(self,args):
		if (len(args)==1):
			target=self.CheckStrictParameter(args[0],edm.SimpleType.DateTime)
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
			if target:
				result.SetFromValue(target.value.date.day)
			return result
		else:
			raise EvaluationError("day() takes 1 argument, %i given"%len(args))

	def EvaluateHour(self,args):
		if (len(args)==1):
			target=self.CheckStrictParameter(args[0],edm.SimpleType.DateTime)
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
			if target:
				result.SetFromValue(target.value.time.hour)
			return result
		else:
			raise EvaluationError("hour() takes 1 argument, %i given"%len(args))

	def EvaluateMinute(self,args):
		if (len(args)==1):
			target=self.CheckStrictParameter(args[0],edm.SimpleType.DateTime)
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
			if target:
				result.SetFromValue(target.value.time.minute)
			return result
		else:
			raise EvaluationError("minute() takes 1 argument, %i given"%len(args))

	def EvaluateSecond(self,args):
		if (len(args)==1):
			target=self.CheckStrictParameter(args[0],edm.SimpleType.DateTime)
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
			if target:
				result.SetFromValue(target.value.time.second)
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
				result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Decimal)
				if target:
					result.SetFromValue(target.value.to_integral(decimal.ROUND_HALF_UP))
			except EvaluationError:
				target=self.PromoteParameter(args[0],edm.SimpleType.Double)				
				result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Double)
				if target:
					v=decimal.Decimal(target.value)
					result.SetFromValue(float(v.to_integral(decimal.ROUND_HALF_EVEN)))
			return result
		else:
			raise EvaluationError("round() takes 1 argument, %i given"%len(args))

	def EvaluateFloor(self,args):
		if (len(args)==1):
			try:
				target=self.PromoteParameter(args[0],edm.SimpleType.Decimal)
				result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Decimal)
				if target:
					result.SetFromValue(target.value.to_integral(decimal.ROUND_FLOOR))
			except EvaluationError:
				target=self.PromoteParameter(args[0],edm.SimpleType.Double)				
				result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Double)
				if target:
					result.SetFromValue(math.floor(target.value))
			return result
		else:
			raise EvaluationError("floor() takes 1 argument, %i given"%len(args))

	def EvaluateCeiling(self,args):
		if (len(args)==1):
			try:
				target=self.PromoteParameter(args[0],edm.SimpleType.Decimal)
				result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Decimal)
				if target:
					result.SetFromValue(target.value.to_integral(decimal.ROUND_CEILING))
			except EvaluationError:
				target=self.PromoteParameter(args[0],edm.SimpleType.Double)				
				result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Double)
				if target:
					result.SetFromValue(math.ceil(target.value))
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
							opCode=Operator.DecodeValue(name)
							if opCode in Operator.IsSpecial:
								raise ValueError
							rightOp=BinaryExpression(opCode)
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
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
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
			result.value=value
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
			return edm.EDMValue.NewSimpleValue(None)
		elif self.Match("'"):
			return self.ParseStringURILiteral()
		elif self.MatchOne('-.0123456789'):
			# one of the number forms (perhaps)
			num=self.ParseNumericLiteral()
			if num is None:
				# must be something like "." or "-" on its own, not a literal
				return None
			if self.ParseOne("Dd"):
				result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Double)
				result.SetFromNumericLiteral(num)
				return result
			elif self.ParseOne("Ff"):
				result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Single)
				result.SetFromNumericLiteral(num)
				return result
			elif self.ParseOne("Mm"):
				result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Decimal)
				result.SetFromNumericLiteral(num)
				return result
			elif self.ParseOne("Ll"):
				result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Int64)
				result.SetFromNumericLiteral(num)
				return result
			else:
				result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Int32)
				result.SetFromNumericLiteral(num)
				return result
		elif self.ParseInsensitive("true"):
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
			result.value=True
			return result
		elif self.ParseInsensitive("false"):
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Boolean)
			result.value=False
			return result
		elif self.ParseInsensitive("datetimeoffset"):
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.DateTimeOffset)
			production="datetimeoffset literal"
			self.Require("'",production)
			dtoString=self.ParseUntil("'")
			self.Require("'",production)
			result.SetFromLiteral(dtoString)
			return result
		elif self.ParseInsensitive("datetime"):
			production="datetime literal"
			self.Require("'",production)
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.DateTime)
			value=self.RequireProduction(self.ParseDateTimeLiteral(),production)
			self.Require("'",production)
			result.value=value
			return result
		elif self.ParseInsensitive("time"):
			production="time literal"
			self.Require("'",production)
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Time)
			value=self.RequireProduction(self.ParseTimeLiteral(),production)
			self.Require("'",production)
			result.value=value
			return result
		elif self.Parse("X") or self.ParseInsensitive("binary"):
			self.Require("'","binary")
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Binary)
			value=self.ParseBinaryLiteral()
			self.Require("'","binary literal")
			result.value=value
			return result
		elif self.ParseInsensitive("nan"):
			if self.ParseOne("Dd"):
				result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Double)
				result.SetFromNumericLiteral(edm.Numeric('',"nan",None,'',None))
				return result
			elif self.ParseOne("Ff"):
				result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Single)
				result.SetFromNumericLiteral(edm.Numeric('',"nan",None,'',None))
				return result
			else:
				raise ValueError("Expected double or single Nan: Nan%s"%repr(self.Peek(1)))			
		elif self.ParseInsensitive("inf"):
			if self.ParseOne("Dd"):
				result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Double)
				result.value=float("INF")
				return result
			elif self.ParseOne("Ff"):
				result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Single)
				result.value=float("INF")
				return result
			else:
				raise ValueError("Expected double or single inf: INF%s"%repr(self.Peek(1)))
		elif self.ParseInsensitive("guid"):
			result=edm.EDMValue.NewSimpleValue(edm.SimpleType.Guid)
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
			result.value=uuid.UUID(hex=string.join(hex,''))
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


def FormatExpand(expand):
	"""Returns a unicode string representation of the *expand* rules."""
	result=_FormatExpandList(expand)
	result.sort()
	return string.join(result,',')

def _FormatExpandList(expand):
	"""Returns a list of unicode strings representing the *expand* rules."""
	result=[]
	for k,v in expand.iteritems():
		if not v:
			result.append(k)
		else:
			result=result+map(lambda x:"%s/%s"%(k,x),_FormatExpandList(v))
	return result

def FormatSelect(select):
	"""Returns a unicode string representation of the *select* rules."""
	return FormatExpand(select)		# same implementation as expand
	

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
					elif segment.startswith("$"):
						raise InvalidPathOption("A navigation property is required after $links, found %s"%segment)
					npSegment=self.SplitSegment(segment)
					self.navPath.append(npSegment)
					self.linksProperty=npSegment[0]
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
	
	@classmethod
	def FormatKeyDict(cls,d):
		"""Returns a URI formatted and URI escaped, entity key.

		For example, (42L), or ('Salt%20%26%20Pepper')."""
		if len(d)==1:
			keyStr="(%s)"%cls.FormatLiteral(d.values()[0])
		else:
			keyStr=[]
			for k,v in d.iteritems():
				keyStr.append("%s=%s"%(k,cls.FormatLiteral(v)))
			keyStr="(%s)"%string.join(keyStr,",")
		return uri.EscapeData(keyStr.encode('utf-8'))
	
	@classmethod
	def FormatEntityKey(cls,entity):
		return cls.FormatKeyDict(entity.KeyDict())
			
	@staticmethod
	def FormatLiteral(value):
		"""Returns a URI-literal-formatted value as a *unicode* string.  For example, u"42L" or u"'Paddy O''brian'"	"""
		return unicode(LiteralExpression(value))
	
	@staticmethod
	def FormatSysQueryOptions(sysQueryOptions):
		return string.join(
			map(lambda x:"$%s=%s"%(
					str(SystemQueryOption.EncodeValue(x[0])),
					uri.EscapeData(x[1].encode('utf-8'))),
				sysQueryOptions.items()),
			'&')
			
class Entity(edm.Entity):
	"""We override Entity in order to provide some documented signatures
	for sets of media-stream entities."""
	
	def GetLocation(self):
		return uri.URIFactory.URI(str(self.entitySet.GetLocation())+ODataURI.FormatEntityKey(self))
		
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
				
	def SetFromJSONObject(self,obj,entityResolver=None,forUpdate=False):
		"""Sets the value of this entity from a dictionary parsed from a
		JSON representation."""
		for k,v in self.DataItems():
			if k in obj:
				if isinstance(v,edm.SimpleValue):
					ReadEntityPropertyValueInJSON(v,obj[k])
				else:
					# assume a complex value then
					ReadEntityCTValue(v,obj[k])
			else:
				v.SetFromValue(None)
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
									self[navProperty].BindEntity(targetEntity)
								else:
									raise InvalidData("Resource is not a valid target for %s: %s"%(navProperty,str(href))) 
							else:
								raise InvalidData("No context to resolve entity URI: %s"%str(link))						
						else:
							# full inline representation is expected for deep insert
							targetEntity=collection.NewEntity()
							targetEntity.SetFromJSONObject(link,entityResolver)
							self[navProperty].BindEntity(targetEntity)
		elif forUpdate:
			# we need to look for any updated link bindings
			for navProperty in self.NavigationKeys():
				if navProperty not in obj or self.IsEntityCollection(navProperty):
					# missing or can't be updated these this way
					continue
				link=obj[navProperty]
				if '__metadata' in link:
					targetSet=self.entitySet.NavigationTarget(navProperty)
					# bind to an existing entity
					href=uri.URIFactory.URI(link['__metadata']['uri'])
					if entityResolver is not None:
						if not href.IsAbsolute():
							#	we'll assume that the base URI is the
							#	location of this entity.  Witness this thread:
							#	http://lists.w3.org/Archives/Public/ietf-http-wg/2012OctDec/0122.html
							href=uri.URIFactory.Resolve(self.GetLocation(),href)
						targetEntity=entityResolver(href)
						if isinstance(targetEntity,Entity) and targetEntity.entitySet is targetSet:
							self[navProperty].BindEntity(targetEntity)
						else:
							raise InvalidData("Resource is not a valid target for %s: %s"%(navProperty,str(href))) 
					else:
						raise InvalidData("No context to resolve entity URI: %s"%str(link))						

			
	def GenerateEntityTypeInJSON(self,forUpdate=False,version=2):
		location=str(self.GetLocation())
		mediaLinkResource=self.typeDef.HasStream()
		yield '{"__metadata":{'
		yield '"uri":%s'%json.dumps(location)
		yield ',"type":%s'%json.dumps(self.entitySet.entityType.GetFQName())
		etag=self.ETag()
		if etag:
			s="" if self.ETagIsStrong() else "W/"
			yield ',"etag":%s'%json.dumps(s+http.QuoteString(string.join(map(ODataURI.FormatLiteral,etag),',')))
		if mediaLinkResource:
			yield ',"media_src":%s'%json.dumps(location+"/$value")
			yield ',"content_type":%s'%json.dumps(str(self.GetStreamType()))
			yield ',"edit_media":%s'%json.dumps(location+"/$value")
			if etag:
				s="" if self.ETagIsStrong() else "W/"
				yield ',"media_etag":%s'%json.dumps(s+http.QuoteString(string.join(map(ODataURI.FormatLiteral,etag),',')))			
		yield '}'
		for k,v in self.DataItems():
			# watch out for unselected properties
			if self.Selected(k):
				yield ','
				if isinstance(v,edm.SimpleValue):
					yield EntityPropertyInJSON(v)
				else:
					yield EntityCTBody(v)
		if self.exists and not forUpdate:
			for navProperty,navValue in self.NavigationItems():
				if self.Selected(navProperty):
					yield ', %s'%json.dumps(navProperty)
					if navValue.isExpanded:
						yield ':'
						if navValue.isCollection:
							with navValue.OpenCollection() as collection:
								for y in collection.GenerateEntitySetInJSON(version):
									yield y
						else:
							entity=navValue.GetEntity()
							if entity:
								for y in entity.GenerateEntityTypeInJSON(False,version):
									yield y
							else:
								yield json.dumps(None)
					else:
						yield ':{"__deferred":{"uri":%s}}'%json.dumps(location+'/'+navProperty)
		elif forUpdate:
			for k,dv in self.NavigationItems():
				if not dv.bindings or dv.isCollection:
					# nothing to do here, we can't update this type of navigation property
					continue
				# we need to know the location of the target entity set
				targetSet=dv.Target()
				binding=dv.bindings[-1]
				if isinstance(binding,Entity):
					if binding.exists:
						href=str(targetSet.GetLocation())+ODataURI.FormatEntityKey(binding)
					else:
						# we can't create new entities on update
						continue
				else:
					href=str(targetSet.GetLocation())+ODataURI.FormatKeyDict(targetSet.GetKeyDict(binding))
				yield ', %s:{"__metadata":{"uri":%s}}'%(json.dumps(k),json.dumps(href))				
# 			for navProperty,bindings in self.bindings.items():
# 				if not bindings or self[navProperty].isCollection:
# 					# nothing to do here, we can't update this type of navigation property
# 					continue
# 				# we need to know the location of the target entity set
# 				targetSet=self.entitySet.NavigationTarget(navProperty)
# 				binding=bindings[-1]
# 				if isinstance(binding,Entity):
# 					if binding.exists:
# 						href=str(targetSet.GetLocation())+ODataURI.FormatEntityKey(binding)
# 					else:
# 						# we can't create new entities on update
# 						continue
# 				else:
# 					href=str(targetSet.GetLocation())+ODataURI.FormatKeyDict(targetSet.GetKeyDict(binding))
# 				yield ', %s:{"__metadata":{"uri":%s}}'%(json.dumps(navProperty),json.dumps(href))
		else:
			for k,dv in self.NavigationItems():
				if not dv.bindings:
					continue
				targetSet=dv.Target()
				yield ', %s :['%json.dumps(k)
				sep=False
				for binding in dv.bindings:
					if sep:
						yield ', '
					else:
						sep=True
					if isinstance(binding,Entity):
						if binding.exists:
							href=str(targetSet.GetLocation())+ODataURI.FormatEntityKey(binding)
						else:
							# we need to yield the entire entity instead
							for s in binding.GenerateEntityTypeInJSON():
								yield s
							href=None
					else:
						href=str(targetSet.GetLocation())+ODataURI.FormatKeyDict(targetSet.GetKeyDict(binding))
					if href:
						yield '{ "__metadata":{"uri":%s}}'%json.dumps(href)
				yield ']'				
# 			for navProperty,bindings in self.bindings.items():
# 				# we need to know the location of the target entity set
# 				targetSet=self.entitySet.NavigationTarget(navProperty)
# 				yield ', %s :['%json.dumps(navProperty)
# 				sep=False
# 				for binding in bindings:
# 					if sep:
# 						yield ', '
# 					else:
# 						sep=True
# 					if isinstance(binding,Entity):
# 						href=str(targetSet.GetLocation())+ODataURI.FormatEntityKey(binding)
# 					else:
# 						href=str(targetSet.GetLocation())+ODataURI.FormatKeyDict(targetSet.GetKeyDict(binding))
# 					yield '{ "__metadata":{"uri":%s}}'%json.dumps(href)
# 				yield ']'
		yield '}'
					
	def LinkJSON(self):
		"""Returns JSON serialised link"""
		return '{"uri":%s}'%json.dumps(str(self.GetLocation()))


def EntityCTInJSON2(complexValue):
	"""Return a version 2 JSON complex entity."""
	return '{"results":%s}'%EntityCTInJSON(complexValue)

def ReadEntityCTInJSON2(complexValue,obj):
	if "results" in obj and type(obj["results"])==DictType:
		obj=obj["results"]
		ReadEntityCTInJSON(complexValue,obj)
	
def EntityCTInJSON(complexValue):
	"""Return a version 1 JSON complex entity - specification seems to be incorrect here."""
	return '{%s}'%EntityCTBody(complexValue)

def ReadEntityCTInJSON(complexValue,obj):
	if complexValue.pDef.name in obj:
		ReadEntityCTValue(complexValue,obj[complexValue.pDef.name])
	
def EntityCTBody(complexValue):
	return "%s:%s"%(json.dumps(complexValue.pDef.name),EntityCTValueToJSON(complexValue))

def EntityCTValueToJSON(complexValue):
	result=[]
	for k,v in complexValue.iteritems():
		if isinstance(v,edm.SimpleValue):
			value=EntityPropertyInJSON(v)
		else:
			value=EntityCTBody(v)
		result.append(value)
	return "{%s}"%string.join(result,',')

def ReadEntityCTValue(complexValue,obj):
	for k,v in complexValue.iteritems():
		if k in obj:
			if isinstance(v,edm.SimpleValue):
				ReadEntityPropertyValueInJSON(v,obj[k])
			else:
				ReadEntityCTValue(v,obj[k])
		else:
			v.SetFromValue(None)
	

TICKS_PER_DAY=86400000
BASE_DAY=iso.Date.FromString('1970-01-01').GetAbsoluteDay()

def EntityPropertyInJSON2(simpleValue):			
	"""Return a version 2 JSON simple value."""
	return '{"results":{%s}}'%EntityPropertyInJSON(simpleValue)

def EntityPropertyInJSON1(simpleValue):
	"""Returns a version 1 JSON simple value.
	
	Not defined by the specification but useful for generating request/response bodies."""
	return '{%s}'%EntityPropertyInJSON(simpleValue)

def ReadEntityPropertyInJSON1(simpleValue,obj):
	if simpleValue.pDef.name in obj:
		ReadEntityPropertyValueInJSON(simpleValue,obj[simpleValue.pDef.name])
		
def EntityPropertyInJSON(simpleValue):
	return "%s:%s"%(json.dumps(simpleValue.pDef.name),EntityPropertyValueInJSON(simpleValue))

def EntityPropertyValueInJSON(v):
	if not v:
		return 'null'
	elif isinstance(v,edm.BinaryValue):
		# unusual representation as we use base64 encoding
		return json.dumps(base64.b64encode(v.value))
	elif isinstance(v,(edm.BooleanValue,edm.ByteValue,edm.Int16Value,edm.Int32Value,edm.SByteValue)):
		# naked representation
		return unicode(v)
	elif isinstance(v,edm.DateTimeValue):
		# a strange format based on ticks, by definition, DateTime has no offset
		ticks=(v.value.date.GetAbsoluteDay()-BASE_DAY)*TICKS_PER_DAY+int(v.value.time.GetTotalSeconds()*1000)
		return json.dumps("/Date(%i)/"%ticks)
	elif isinstance(v,(edm.DecimalValue,edm.DoubleValue,edm.GuidValue,edm.Int64Value,edm.SingleValue,edm.StringValue,edm.TimeValue)):
		# just use the literal form as a json string
		return json.dumps(unicode(v))
	elif isinstance(v,(edm.DateTimeOffsetValue)):
		# a strange format based on ticks, by definition, DateTime has no offset
		ticks=(v.value.date.GetAbsoluteDay()-BASE_DAY)*TICKS_PER_DAY+int(v.value.time.GetTotalSeconds()*1000)
		dir,offset=v.GetZone()
		if dir>0:
			s=u"+"
		else:
			s=u"-"
		return json.dumps("/Date(%i%s%04i)/"%(ticks,s,offset))
	else:
		raise ValueError("SimpleValue: %s"%repr(v))
		
def ReadEntityPropertyValueInJSON(v,jsonValue):
	"""Given a simple property value parsed from a json representation,
	*jsonValue* and a :py:class:`SimpleValue` instance, *v*, update *v*
	to reflect the parsed value."""
	if jsonValue is None:
		v.SetFromValue(None)
	elif isinstance(v,edm.BinaryValue):
		v.SetFromValue(base64.b64decode(jsonValue))
	elif isinstance(v,(edm.BooleanValue,edm.ByteValue,edm.Int16Value,edm.Int32Value,edm.SByteValue)):
		v.SetFromValue(jsonValue)
	elif isinstance(v,edm.DateTimeValue):
		if jsonValue.startswith("/Date(") and jsonValue.endswith(")/"):
			ticks=int(jsonValue[6:-2])
			t,overflow=iso.Time().Offset(seconds=ticks/1000.0)
			d=iso.Date(absoluteDay=BASE_DAY+overflow)
			v.SetFromValue(iso.TimePoint(date=d,time=t))
		else:
			raise ValueError("Illegal value for DateTime: %s"%jsonValue)		
	elif isinstance(v,(edm.DecimalValue,edm.DoubleValue,edm.GuidValue,edm.Int64Value,edm.SingleValue,edm.StringValue,edm.TimeValue)):
		# just use the literal form as a json string
		v.SetFromLiteral(jsonValue)
	elif isinstance(v,(edm.DateTimeOffsetValue)):
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
			t,overflow=Time().Offset(seconds=int(ticks[0])/1000.0).WithZone(zDir,zOffset//60,zOffset%60)
			d=Date(absoluteDay=BASE_DAY+overflow)
			v.SetFromValue(iso.TimePoint(date=d,time=t))
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
				return result.value==True			#: NULL treated as False
			else:
				raise ValueError("Boolean required for filter expression") 
	
	def CalculateOrderKey(self,entity,orderObject):
		"""Evaluates orderObject as an instance of py:class:`CommonExpression`."""
		return orderObject.Evaluate(entity).value		

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
			for s in entity.GenerateEntityTypeInJSON(False,version):
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
			yield '{"uri":%s}'%json.dumps(str(entity.GetLocation()))
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
	
	def __init__(self,name,fromEntity,toEntitySet):
		edm.NavigationEntityCollection.__init__(self,name,fromEntity,toEntitySet)
		EntityCollectionMixin.__init__(self)
		
	def ExpandCollection(self):
		"""Return an expanded version of this collection with OData specific class"""
		return ExpandedEntityCollection(self.name,self.fromEntity,self.entitySet,self.values())						

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


class ExpandedEntityCollection(EntityCollectionMixin,edm.ExpandedEntityCollection):

	def __init__(self,name,fromEntity,toEntitySet,entityList):
		edm.ExpandedEntityCollection.__init__(self,name,fromEntity,toEntitySet,entityList)
		EntityCollectionMixin.__init__(self)


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
					p=edm.Property(None)
					p.name=self.xmlname
					p.simpleTypeCode=type
					value=edm.EDMValue.NewValue(p)
		if isinstance(value,edm.SimpleValue):
			if null:
				value.value=None
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

	def AttachToDocument(self,doc=None):
		"""Overridden to prevent unnecessary iterations through the set of children.
		
		Our children do not have XML IDs"""
		return
		
	def DetachFromDocument(self,doc=None):
		"""Overridden to prevent unnecessary iterations through the set of children.

		Our children do not have XML IDs"""
		return
		

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

	def LoadExpansion(self,deferred,exists=True):
		"""Given a :py:class:`csdl.DeferredProperty` instance, adds an expansion if one is present in the link"""
		if self.Inline is not None:
			targetEntitySet=deferred.Target()
			with targetEntitySet.OpenCollection() as collection:
				if self.Inline.Entry is not None:
					entity=collection.NewEntity()
					entity.exists=exists
					self.Inline.Entry.GetValue(entity)
					entries=[entity]
				elif self.Inline.Feed is not None:
					entries=[]
					for entry in self.Inline.Feed.FindChildrenDepthFirst(Entry,subMatch=False):
						entity=collection.NewEntity()
						entity.exists=exists
						entry.GetValue(entity)
						entries.append(entity)
				deferred.SetExpansion(ExpandedEntityCollection(deferred.name,deferred.fromEntity,targetEntitySet,entries))

		
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
	
	def GetValue(self,entity,entityResolver=None,forUpdate=False):
		"""Update *entity* to reflect the value of this Entry.
		
		*entity* must be an :py:class:`pyslet.mc_csdl.Entity`
		instance.  It is required but is also returned for consistency
		with the behaviour of the overridden method.
		
		When reading entities that don't yet exist, or values
		*forUpdate* an entityResolver may be required.  It is a callable
		that accepts a single parameter of type
		:py:class:`pyslet.rfc2396.URI` and returns a an object
		representing the resource it points to."""
		selected=set()
		unselected=set()
		for k,v in entity.DataItems():
			# catch property-level feed customisation here
			propertyDef=entity.typeDef[k]
			targetPath=propertyDef.GetTargetPath()
			if targetPath and not propertyDef.KeepInContent():
				# This value needs to be read from somewhere special
				prefix,ns=propertyDef.GetFCNsPrefix()
				targetElement=self.ResolveTargetPath(targetPath,prefix,ns)
				if isinstance(targetElement,atom.Date):
					dtOffset=targetElement.GetValue()
					if isinstance(v,edm.DateTimeOffsetValue):
						v.SetFromValue(dtOffset)
					elif isinstance(v,edm.DateTimeValue):
						# strip the zone and use that
						v.SetFromValue(dtOffset.WithZone(zDirection=None))
					elif isinstance(v,edm.StringValue):
						v.SetFromLiteral(str(dtOffset))
					else:
						# give up, treat this value as NULL
						v.SetFromValue(None)
				else:	
					# now we need to grab the actual value, only interested in data
					data=[]
					for child in targetElement.GetChildren():
						if type(child) in StringTypes:
							data.append(child)
					v.SetFromLiteral(string.join(data,''))
					selected.add(k)
			else:
				# and watch out for unselected properties
				if k in self._properties:
					self._properties[k].GetValue(v)
					selected.add(k)
				else:
					# Property is not selected!
					v.SetFromValue(None)
					unselected.add(k)
		# Now set this entity's select property...
		if not unselected:
			entity.selected=None
		else:
			entity.selected=selected
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
								entity[navProperty].BindEntity(targetEntity)
						elif link.Inline.Entry is not None:
							targetEntity=collection.NewEntity()
							link.Inline.Entry.GetValue(targetEntity,entityResolver)								
							entity[navProperty].BindEntity(targetEntity)
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
						entity[navProperty].BindEntity(targetEntity)
					else:
						raise InvalidData("Resource is not a valid target for %s: %s"%(navProperty,str(href))) 
				else:
					raise InvalidData("No context to resolve entity URI: %s"%str(link.href))
		elif forUpdate:
			# we need to look for any updated link bindings
			for link in self.Link:
				if not link.rel.startswith(ODATA_RELATED):
					continue
				navProperty=link.rel[len(ODATA_RELATED):]
				if not entity.IsNavigationProperty(navProperty) or entity[navProperty].isCollection:
					continue
				targetSet=entity.entitySet.NavigationTarget(navProperty)
				# we have a navigation property we can update
				if entityResolver is not None:
					#	this is the tricky bit, we need to resolve
					#	the URI to an entity key
					href=link.ResolveURI(link.href)
					if not href.IsAbsolute():
						#	we'll assume that the base URI is the location of this entity
						#	Witness this thread:
						#	http://lists.w3.org/Archives/Public/ietf-http-wg/2012OctDec/0122.html
						href=uri.URIFactory.Resolve(entity.GetLocation(),href)
					targetEntity=entityResolver(href)
					if isinstance(targetEntity,Entity) and targetEntity.entitySet is targetSet:
						entity[navProperty].BindEntity(targetEntity)
					else:
						raise InvalidData("Resource is not a valid target for %s: %s"%(navProperty,str(href))) 
				else:
					raise InvalidData("No context to resolve entity URI: %s"%str(link.href))
		else:
			# entity exists, look to see if it has been expanded
			for link in self.Link:
				if not link.rel.startswith(ODATA_RELATED):
					continue
				navProperty=link.rel[len(ODATA_RELATED):]
				if not entity.IsNavigationProperty(navProperty):
					continue
				targetSet=entity.entitySet.NavigationTarget(navProperty)
				link.LoadExpansion(entity[navProperty])
		return entity
				
	def SetValue(self,entity,forUpdate=False):
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
				if isinstance(targetElement,atom.Date) and v:
					if isinstance(v,edm.DateTimeOffsetValue):
						targetElement.SetValue(unicode(v))
					elif isinstance(v,edm.DateTimeValue):
						# assume UTC
						dtOffset=v.value.WithZone(zDirection=0)
						targetElement.SetValue(unicode(dtOffset))						
					elif isinstance(v,edm.StringValue):
						try:
							dtOffset=iso8601.TimePoint.FromString(v.value)
							if dtOffset.GetZone()[0] is None:
								dtOffset=dtOffset.WithZone(zDirection=0)
							targetElement.SetValue(unicode(dtOffset))
						except iso8601.DateTimeError:
							# do nothing
							pass
				elif isinstance(v,edm.SimpleValue) and v:
					targetElement.AddData(unicode(v))
		# now do the links
		location=str(entity.GetLocation())
		self.ChildElement(atom.AtomId).SetValue(location)
		if entity.exists and not forUpdate:
			link=self.ChildElement(self.LinkClass)
			link.href=location
			link.rel="edit"
			if mediaLinkResource:
				link=self.ChildElement(self.LinkClass)
				link.href=location+"/$value"
				link.rel="edit-media"
				if self.etag:
					s="" if entity.ETagIsStrong() else "W/"
					link.SetAttribute((ODATA_METADATA_NAMESPACE,'etag'),s+http.QuoteString(string.join(map(ODataURI.FormatLiteral,self.etag),',')))
			for navProperty,navValue in entity.NavigationItems():
				link=self.ChildElement(self.LinkClass)
				link.href=location+'/'+navProperty
				link.rel=ODATA_RELATED+navProperty
				link.title=navProperty
				if navValue.isCollection:
					link.type=ODATA_RELATED_FEED_TYPE
				else:
					link.type=ODATA_RELATED_ENTRY_TYPE
				if navValue.isExpanded:
					# This property has been expanded
					if navValue.isCollection:
						link.Expand(navValue.OpenCollection())
					else:
						link.Expand(navValue.GetEntity())
		elif forUpdate:
			# This is a special form of representation which only represents the
			# navigation properties with single cardinality
			for k,dv in entity.NavigationItems():
				if not dv.bindings or dv.isCollection:
					# nothing to do here, we can't update this type of navigation property
					continue
				# we need to know the location of the target entity set
				targetSet=dv.Target()
				binding=dv.bindings[-1]
				if isinstance(binding,Entity):
					if binding.exists:
						href=str(targetSet.GetLocation())+ODataURI.FormatEntityKey(binding)
					else:
						# we can't create new entities on update
						continue
				else:
					href=str(targetSet.GetLocation())+ODataURI.FormatKeyDict(targetSet.GetKeyDict(binding))
				link=self.ChildElement(self.LinkClass)
				link.rel=ODATA_RELATED+k
				link.title=k
				link.href=href
		else:
			# entity does not exist...
			for k,dv in entity.NavigationItems():
				if not dv.bindings:
					continue
				targetSet=dv.Target()
				feed=[]
				for binding in dv.bindings:
					if isinstance(binding,Entity):
						if binding.exists:
							href=str(targetSet.GetLocation())+ODataURI.FormatEntityKey(binding)
						else:
							feed.append(binding)
							href=None
					else:
						href=str(targetSet.GetLocation())+ODataURI.FormatKeyDict(targetSet.GetKeyDict(binding))
					if href:
						link=self.ChildElement(self.LinkClass)
						link.rel=ODATA_RELATED+k
						link.title=k
						link.href=href
				if feed:
					link=self.ChildElement(self.LinkClass)
					link.rel=ODATA_RELATED+k
					link.title=k
					link.href=location+'/'+k
					if dv.isCollection:
						feed=edm.ExpandedEntityCollection(k,entity,targetSet,feed)
						link.Expand(feed)
					elif len(feed)>1:
						raise NavigationError("Multiple bindings found for navigation property %s.%s"%(entitySet.name,k))
					else:
						link.Expand(feed[0])
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
				self.SetFCValue(targetElement,v)
				if not propertyDef.KeepInContent():
					continue
			# and watch out for unselected properties
			if entity.Selected(k):
				self[k]=v
		self.ContentChanged()

	def SetFCValue(self,targetElement,v):
		if isinstance(targetElement,atom.Date) and v:
			if isinstance(v,edm.DateTimeOffsetValue):
				targetElement.AddData(unicode(v))
			elif isinstance(v,edm.DateTimeValue):
				# assume UTC
				dtOffset=v.value.WithZone(zDirection=0)
				targetElement.AddData(unicode(dtOffset))						
			elif isinstance(v,edm.StringValue):
				try:
					dtOffset=iso8601.TimePoint.FromString(v.value)
					if dtOffset.GetZone()[0] is None:
						dtOffset=dtOffset.WithZone(zDirection=0)
					targetElement.AddData(unicode(dtOffset))
				except iso8601.DateTimeError:
					# do nothing
					pass
		elif isinstance(v,edm.SimpleValue) and v:
			targetElement.AddData(unicode(v))


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
