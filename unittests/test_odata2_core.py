#! /usr/bin/env python

import unittest, logging

from pyslet.vfs import OSFilePath as FilePath
import pyslet.odata2.metadata as edmx
from pyslet.odata2.core import *

def suite(prefix='test'):
	loader=unittest.TestLoader()
	loader.testMethodPrefix=prefix
	return unittest.TestSuite((
		loader.loadTestsFromTestCase(ODataTests),
 		loader.loadTestsFromTestCase(CommonExpressionTests),
 		loader.loadTestsFromTestCase(ODataURITests)
# 		loader.loadTestsFromTestCase(ClientTests),
# 		loader.loadTestsFromTestCase(ServerTests),
# 		loader.loadTestsFromTestCase(SampleServerTests)
		))
		

class ODataTests(unittest.TestCase):
	def testCaseConstants(self):
		# self.assertTrue(IMSCP_NAMESPACE=="http://www.imsglobal.org/xsd/imscp_v1p1","Wrong CP namespace: %s"%IMSCP_NAMESPACE)
		# self.assertTrue(IMSCPX_NAMESPACE=="http://www.imsglobal.org/xsd/imscp_extensionv1p2","Wrong extension namespace: %s"%IMSCPX_NAMESPACE)
		pass

class CommonExpressionTests(unittest.TestCase):
	
	def EvaluateCommon(self,expressionString):
		p=Parser(expressionString)
		e=p.ParseCommonExpression()
		return e.Evaluate(None)
		
	def testCaseEvaluateCommonExpression(self):
		# cursory check:
		# a commonExpression must represent any and all supported common expression types
		p=Parser("true and false")
		e=p.ParseCommonExpression()
		self.assertTrue(isinstance(e,CommonExpression),"Expected common expression")
		value=e.Evaluate(None)
		self.assertTrue(isinstance(value,edm.SimpleValue),"Expected EDM value; found %s"%repr(value))
		self.assertTrue(value.value is False,"Expected false")
				
	def testCaseEvaluateBooleanExpression(self):
		# cursory check:
		# a boolCommonExpression MUST be a common expression that evaluates to the EDM Primitive type Edm.Boolean
		value=self.EvaluateCommon("true and false")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is False,"Expected false")
				
	def testCaseEvaluateParenExpression(self):
		"""a parenExpression MUST be evaluated by evaluating the
		expression with the parentheses, starting with the innermost
		parenthesized expressions and proceeding outwards...

		...the result of the parenExpression MUST be the result of the
		evaluation of the contained expression."""
		p=Parser("(false and false or true)")		# note that or is the weakest operator
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.assertTrue(value.value is True,"Expected True")
		p=Parser("(false and (false or true))")		# should change the result
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("(((((((false) and (((false)) or true)))))))")
		self.assertTrue(value.value is False,"Expected False - multibrackets")
				
	def testCaseEvaluateBooleanParenExpression(self):
		"""Cursory check: a boolParenExpression MUST be evaluated by
		evaluating the expression with the parentheses. The result of
		the boolParenExpression MUST ... be of the EDM Primitive type
		Edm.Boolean"""
		value=self.EvaluateCommon("(false and (false or true))")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is False,"Expected false")
	
	def testCaseEvaluateAddExpression(self):
		"""...operand expressions MUST evaluate to a value of one of the
		following EDM Primitive types:
			Edm.Decimal
			Edm.Double
			Edm.Single
			Edm.Int32
			Edm.Int64

		The addExpression SHOULD NOT be supported for any other EDM
		Primitive types.
		
		..data service SHOULD follow the binary numeric promotion
		rules... The EDM Primitive type of the result of evaluating the
		addExpression MUST be the same type as the operands after binary
		numeric promotion.
		
		data service can support evaluating operands with null values
		following the rules defined in Lifted operators"""
		value=self.EvaluateCommon("2M add 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.assertTrue(value.value == 4,"Expected 4")
		value=self.EvaluateCommon("2D add 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.value == 4.0,"Expected 4")
		value=self.EvaluateCommon("2F add 2D")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.value == 4.0,"Expected 4")
		value=self.EvaluateCommon("2 add 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.value == 4L,"Expected 4")
		try:
			value=self.EvaluateCommon("2 add '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("2 add null")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.value is None,"Expected None")

	def testCaseEvaluateSubExpression(self):
		"""See testCaseEvaluateAddExpression"""
		value=self.EvaluateCommon("4M sub 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.assertTrue(value.value == 2,"Expected 2.0")
		value=self.EvaluateCommon("4D sub 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.value == 2.0,"Expected 2.0")
		value=self.EvaluateCommon("4F sub 2D")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.value == 2.0,"Expected 2.0")
		value=self.EvaluateCommon("4 sub 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.value == 2L,"Expected 2L")
		try:
			value=self.EvaluateCommon("4 sub '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("4 sub null")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.value is None,"Expected None")

	def testCaseEvaluateMulExpression(self):
		"""See testCaseEvaluateAddExpression"""
		value=self.EvaluateCommon("4M mul 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.assertTrue(value.value == 8,"Expected 8.0")
		value=self.EvaluateCommon("4D mul 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.value == 8.0,"Expected 8.0")
		value=self.EvaluateCommon("4F mul 2D")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.value == 8.0,"Expected 8.0")
		value=self.EvaluateCommon("4 mul 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.value == 8L,"Expected 8L")
		try:
			value=self.EvaluateCommon("4 mul '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("4 mul null")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.value is None,"Expected None")

	def testCaseEvaluateDivExpression(self):
		"""See testCaseEvaluateAddExpression
		
		OData is ambiguous in the way it defines division as it makes reference only
		to the IEEE floating point operations.  For compatibility with SQL though we
		assume that integer division simple truncates fractional parts."""
		value=self.EvaluateCommon("4M div 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.assertTrue(value.value == 2,"Expected 2")
		value=self.EvaluateCommon("4D div 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.value == 2.0,"Expected 2.0")
		try:
			value=self.EvaluateCommon("4D div 0")
			self.fail("Division by zero")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("4F div 2D")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.value == 2.0,"Expected 2.0")
		value=self.EvaluateCommon("5 div 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.value == 2L,"Expected 2L")
		value=self.EvaluateCommon("-5 div 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.value == -2L,"Expected -2L")
		try:
			value=self.EvaluateCommon("4 div '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("4 div null")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.value is None,"Expected None")

	def testCaseEvaluateModExpression(self):
		"""See testCaseEvaluateAddExpression
		
		The data service SHOULD evaluate the operation represented by
		the modExpression, according to the rules of [IEEE754-2008]

		For integer division we just truncate fractional parts towards zero."""
		value=self.EvaluateCommon("5.5M mod 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.assertTrue(value.value == 1.5,"Expected 1.5")
		value=self.EvaluateCommon("5.5D mod 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.value == 1.5,"Expected 1.5")
		try:
			value=self.EvaluateCommon("5.5D mod 0")
			self.fail("Division by zero")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("5.5F mod 2D")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.value == 1.5,"Expected 1.5")
		value=self.EvaluateCommon("5 mod 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.value == 1L,"Expected 1L")
		value=self.EvaluateCommon("-5 mod 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.value == -1L,"Expected -1L")
		try:
			value=self.EvaluateCommon("5 mod '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("5 mod null")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.value is None,"Expected None")


	def testCaseEvaluateNegateExpression(self):
		"""See testCaseEvaluateAddExpression for list of simple types.
		
		..data service SHOULD follow the unary numeric promotion rules
		... to implicitly convert the operand to a supported EDM
		Primitive type

		the result of evaluating the negateExpression SHOULD always be
		equal to the result of evaluating the subExpression where one
		operand is the value zero and the other is the value of the
		operand.  [comment applies to null processing too]"""
		value=self.EvaluateCommon("-(2M)")
		self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.assertTrue(value.value == -2,"Expected -2.0")
		value=self.EvaluateCommon("-(2D)")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.value == -2.0,"Expected -2.0")
		p=Parser("-(-2F)")	# unary numeric promotion to Double - a bit weird 
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.value == 2.0,"Expected 2.0")
		value=self.EvaluateCommon("-(2L)")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.value == -2L,"Expected -2L")
		try:
			value=self.EvaluateCommon("-'2'")
			self.fail("String promotion to numeric")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("-null")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.value is None,"Expected None")


	def testCaseEvaluateAndExpression(self):
		"""...operand expressions MUST evaluate to the EDM Primitive
		types of Edm.Boolean. The andExpression SHOULD NOT be supported
		for operands of any other EDM Primitive types.

		The EDM Primitive type of the result of evaluating the andExpression MUST be Edm.Boolean.

		...service MUST evaluate the expression to the value of true if
		the values of the operands are both true after being evaluated.
		If either operand is false after being evaluated, the expression
		MUST evaluate to the value of false.
		
		The data service can support evaluating operands with null
		values following the rules defined in Binary Numeric
		Promotions.... [for Boolean expressions evaluated to the value
		of null, a data service MUST return the value of false]"""
		value=self.EvaluateCommon("false and false")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is False,"Expected False")
		try:
			value=self.EvaluateCommon("false and 0")
			self.fail("Integer promotion to Boolean")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("false and true")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("true and false")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("true and true")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("true and null")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("false and null")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("false and false")
		self.assertTrue(value.value is False,"Expected False")


	def testCaseEvaluateOrExpression(self):
		"""See testCaseEvaluateAndExpression for more details.
		
		...data service MUST evaluate the expression to the value of
		true if at least one of the operands is true after being
		evaluated. If both operands are false after being evaluated, the
		expression MUST evaluate to the value of false"""
		value=self.EvaluateCommon("false or false")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is False,"Expected False")
		try:
			value=self.EvaluateCommon("false or 0")
			self.fail("Integer promotion to Boolean")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("false or true")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("true or false")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("true or true")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("true or null")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("false or null")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("null or null")
		self.assertTrue(value.value is False,"Expected False")

	def testCaseEvaluateEqExpression(self):
		"""...operand expressions MUST evaluate to a value of a known
		EntityType or one of the following EDM Primitive types:
			Edm.Decimal
			Edm.Double
			Edm.Single
			Edm.Int32
			Edm.Int64
			Edm.String
			Edm.DateTime
			Edm.Guid
			Edm.Binary
		
		(For tests on EntityType instances see the same method in the
		sample data set later)
			
		The eqExpression SHOULD NOT be supported for any other EDM
		Primitive types.

		...a data service SHOULD follow the binary numeric promotion
		rules defined in Unary [sic] Numeric Promotions...
		
		...The EDM Primitive type of the result of evaluating the
		eqExpression MUST be Edm.Boolean.

		...a data service MUST return a value of true if the values of
		the operands are equal and false if they are not equal. If the
		type of the operands is a known EntityType, then a value of true
		MUST be returned if the operand expressions, once evaluated,
		represent the same entity instance.
		
		...for equality operators, a data service MUST consider two null
		values equal and a null value unequal to any non-null value."""
		value=self.EvaluateCommon("2M eq 3M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("2D eq 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("2F eq 2D")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("2 eq 2L")
		self.assertTrue(value.value is True,"Expected True")
		try:
			value=self.EvaluateCommon("2 eq '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("'2' eq '2'")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' eq datetime'2013-08-30T18:49'")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' eq datetime'2013-08-30T18:49:01'")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' eq guid'b3afeebc-9658-4699-9d9c-1df551fd6814'")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' eq guid'3fa6109e-f09c-4c5e-a5f3-6cf38d35c9b5'")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("X'DEADBEEF' eq binary'deadbeef'")
		self.assertTrue(value.value is True,"Expected True")			
		value=self.EvaluateCommon("X'DEAD' eq binary'BEEF'")
		self.assertTrue(value.value is False,"Expected False")			
		value=self.EvaluateCommon("2 eq null")
		self.assertTrue(value.value is False,"Expected False")			
		value=self.EvaluateCommon("null eq null")
		self.assertTrue(value.value is True,"Expected True")			

	def testCaseEvaluateNeExpression(self):
		"""See testCaseEvaluateEqExpression for details."""
		value=self.EvaluateCommon("2M ne 3M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("2D ne 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("2F ne 2D")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("2 ne 2L")
		self.assertTrue(value.value is False,"Expected False")
		try:
			value=self.EvaluateCommon("2 ne '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("'2' ne '2'")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' ne datetime'2013-08-30T18:49'")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' ne datetime'2013-08-30T18:49:01'")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' ne guid'b3afeebc-9658-4699-9d9c-1df551fd6814'")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' ne guid'3fa6109e-f09c-4c5e-a5f3-6cf38d35c9b5'")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("X'DEADBEEF' ne binary'deadbeef'")
		self.assertTrue(value.value is False,"Expected False")			
		value=self.EvaluateCommon("X'DEAD' ne binary'BEEF'")
		self.assertTrue(value.value is True,"Expected True")			
		value=self.EvaluateCommon("2 ne null")
		self.assertTrue(value.value is True,"Expected True")			
		value=self.EvaluateCommon("null ne null")
		self.assertTrue(value.value is False,"Expected False")			


	def testCaseEvaluateLtExpression(self):
		"""...operand expressions MUST evaluate to a value of one of the
		following EDM Primitive types:
			Edm.Decimal
			Edm.Double
			Edm.Single
			Edm.Int32
			Edm.Int64
			Edm.String
			Edm.DateTime
			Edm.Guid

		...data service SHOULD follow the binary numeric promotion
		
		...The EDM Primitive type of the result of evaluating the
		ltExpression MUST be Edm.Boolean.

		...a data service MUST return a value of true if the value of
		the first operand is less than the value of the second operand,
		false if not.
		
		...for relational operators, a data service MUST return the
		value false if one or both of the operands is null."""
		value=self.EvaluateCommon("2M lt 3M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("2D lt 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("2.1F lt 2D")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("2 lt 3L")
		self.assertTrue(value.value is True,"Expected True")
		try:
			value=self.EvaluateCommon("2 lt '3'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("'20' lt '3'")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' lt datetime'2013-08-30T18:49'")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' lt datetime'2013-08-30T18:49:01'")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' lt guid'b3afeebc-9658-4699-9d9c-1df551fd6814'")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' lt guid'3fa6109e-f09c-4c5e-a5f3-6cf38d35c9b5'")
		self.assertTrue(value.value is False,"Expected False")
		try:
			p=Parser("X'DEADBEEF' lt binary'deadbeef'")
			e=p.ParseCommonExpression()
			value=e.Evaluate(None)
			self.fail("Relational operation on binary data")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("2 lt null")
		self.assertTrue(value.value is False,"Expected False")			
		value=self.EvaluateCommon("null lt null")
		self.assertTrue(value.value is False,"Expected False")			

	def testCaseEvaluateLeExpression(self):
		"""See testCaseEvaluateLtExpression for more information - abbreviated tests"""
		value=self.EvaluateCommon("2D le 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' le datetime'2013-08-30T18:49:00'")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("2 le null")
		self.assertTrue(value.value is False,"Expected False")			
		value=self.EvaluateCommon("null le null")
		self.assertTrue(value.value is False,"Expected False")			
		
	def testCaseEvaluateGtExpression(self):
		"""See testCaseEvaluateLtExpression for more information - abbreviated tests"""
		value=self.EvaluateCommon("2D gt 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' gt datetime'2013-08-30T18:49:00'")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("2 gt null")
		self.assertTrue(value.value is False,"Expected False")			
		value=self.EvaluateCommon("null gt null")
		self.assertTrue(value.value is False,"Expected False")			
		
	def testCaseEvaluateGeExpression(self):
		"""See testCaseEvaluateLtExpression for more information - abbreviated tests"""
		value=self.EvaluateCommon("2D ge 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' ge datetime'2013-08-30T18:49:00'")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("2 ge null")
		self.assertTrue(value.value is False,"Expected False")			
		value=self.EvaluateCommon("null ge null")
		self.assertTrue(value.value is False,"Expected False")			

	def testCaseEvaluateNotExpression(self):
		"""...operation is supported ... as long as the operand
		expression evaluates to a value of the EDM Primitive type
		Edm.Boolean. The data service SHOULD NOT support operand
		expressions of any other EDM Primitive type

		The EDM Primitive type of the result of evaluating the
		notExpression MUST be Edm.Boolean.

		the data service MUST evaluate the logical negation operation by
		returning false if the operand value is true and returning true
		if the operand value is false.
		
		...for unary operators, a data service MUST return the value
		null if the operand value is null."""
		value=self.EvaluateCommon("not false")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("not true")
		self.assertTrue(value.value is False,"Expected False")
		try:
			value=self.EvaluateCommon("not 1")
			self.fail("Integer promotion to Boolean")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("not null")
		self.assertTrue(value.value is None,"Expected NULL")
	
	def testCaseEvaluateIsOfExpression(self):
		"""...the data service MAY<24> support some or all of the common
		expressions as the first operand value... the data service can
		support the first operand as being optional... interpreted to
		apply to the entity instance specified by the navigation portion
		of the request URI.
		
		The second operand MUST be a stringLiteral that represents the
		name of a known entity or EDM Primitive type.

		The EDM Primitive type of the result of evaluating the
		isofExpression MUST be Edm.Boolean.

		...the data service MUST evaluate the isofExpression to return a
		value of true if the targeted instance can be converted to the
		specified type. If the conversion is not allowed, then the
		expression MUST be evaluated to false.
		
		data service can support evaluating an operand with a null value
		following the rules defined in Binary Numeric Promotions. [It
		isn't clear what this means at all, clearly there is a typo.  We
		add our own rule... isof(NULL,'type') always returns False, in
		keeping with other boolean operators]
		
		It is also not clear which 'explicit conversions' are allowed in
		the Edm model and which aren't.  The approach taken is to allow
		only the numeric promotions supported for binary operations,
		which is a bit tight but perhaps safer than allowing forms which
		may not be portable."""
		value=self.EvaluateCommon("isof(2D,'Edm.Double')")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("isof(2M,'Edm.Double')")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("isof(2,'Edm.Double')")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("isof(2.0D,'Edm.Single')")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("isof('x','Edm.String')")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("isof(X'DEAD','Edm.String')")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("isof(false or true,'Edm.Boolean')")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("isof(null,'Edm.String')")
		self.assertTrue(value.value is False,"Expected False")
		value=self.EvaluateCommon("isof('Edm.String')")
		self.assertTrue(value.value is False,"Expected False")
	
	def testCaseEvaluateCastExpression(self):
		"""...see testCaseEvaluateIsOfExpression for more information.
		
		The type of the result of evaluating the castExpression MUST be
		the same type as represented by the string literal value from
		the second operand.
		
		A data service MAY support any cast operations where there
		exists an explicit conversion from the targeted instance (first
		operand) to the type represented by second operand. In all other
		cases, the data service SHOULD NOT support the specified cast
		operation.

		The data service MAY support evaluating an operand with a null
		value following the rules defined in Lifted Operators. [again,
		not 100% clear what these are.]"""
		value=self.EvaluateCommon("cast(2D,'Edm.Double')")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.value==2.0,"Expected 2.0")
		value=self.EvaluateCommon("cast(2L,'Edm.Single')")
		self.assertTrue(value.typeCode==edm.SimpleType.Single,"Expected Single")
		self.assertTrue(value.value==2.0,"Expected 2.0")
		value=self.EvaluateCommon("cast(2,'Edm.Int64')")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.value==2L,"Expected 2")
		try:
			value=self.EvaluateCommon("cast(2.0D,'Edm.Single')")
			self.fail("Double cast to Single")
		except:
			pass
		value=self.EvaluateCommon("cast('x','Edm.String')")
		self.assertTrue(value.value=='x',"Expected 'x'")
		try:
			value=self.EvaluateCommon("cast(X'DEAD','Edm.String')")
			self.fail("Binary cast to String")
		except:
			pass
		try:
			value=self.EvaluateCommon("cast(1,'Edm.Boolean')")
			self.fail("1 cast to Boolean")
		except:
			pass
		value=self.EvaluateCommon("cast(null,'Edm.String')")
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected String")
		self.assertTrue(value.value is None,"Expected None")
		value=self.EvaluateCommon("cast('Edm.Int16')")
		self.assertTrue(value.typeCode==edm.SimpleType.Int16,"Expected Int16")
		self.assertTrue(value.value is None,"Expected None")		
	
	def testCaseEvaluateBooleanCastExpression(self):
		# cursory check:
		value=self.EvaluateCommon("cast(true,'Edm.Boolean')")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is True,"Expected True")

	def testCaseEvaluateBooleanLiteralExpression(self):
		"""the type of the boolLiteralExpression MUST always be the EDM
		primitive type Edm.Boolean."""
		value=self.EvaluateCommon("true")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is True,"Expected True")
		value=self.EvaluateCommon("false")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value is False,"Expected False")

	def testCaseEvaluateLiteralExpression(self):
		"""the type of the literalExpression MUST be the EDM Primitive
		type for the lexical representation of the literal:
		
			null
			Edm.Binary
			Edm.Boolean
			Edm.Byte		
			Edm.DateTime
			Edm.Decimal
			Edm.Double
			Edm.Single
			Edm.Guid
			Edm.Int16
			Edm.Int32
			Edm.Int64
			Edm.SByte,
			Edm.String,
			Edm.Time,
			Edm.DateTimeOffset"""
		value=self.EvaluateCommon("null")
		self.assertTrue(value.typeCode==None,"Expected None")
		self.assertTrue(value.value==None,"Expected None")
		value=self.EvaluateCommon("X'DEAD'")
		self.assertTrue(value.typeCode==edm.SimpleType.Binary,"Expected Binary")
		self.assertTrue(value.value=='\xde\xad')
		value=self.EvaluateCommon("true")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Booelan")
		self.assertTrue(value.value==True)
		value=self.EvaluateCommon("123")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.value==123)
		value=self.EvaluateCommon("datetime'2013-08-31T15:28'")
		self.assertTrue(value.typeCode==edm.SimpleType.DateTime,"Expected DateTime")
		self.assertTrue(value.value.date.year==13)
		value=self.EvaluateCommon("123.5M")
		self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.assertTrue(value.value==123.5)
		value=self.EvaluateCommon("123.5D")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.value==123.5)
		value=self.EvaluateCommon("123.5F")
		self.assertTrue(value.typeCode==edm.SimpleType.Single,"Expected Single")
		self.assertTrue(value.value==123.5)
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814'")
		self.assertTrue(value.typeCode==edm.SimpleType.Guid,"Expected Guid")
		self.assertTrue(value.value==uuid.UUID('b3afeebc-9658-4699-9d9c-1df551fd6814'))
		value=self.EvaluateCommon("123456")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.value==123456)
		value=self.EvaluateCommon("123456L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.value==123456L)
		value=self.EvaluateCommon("-123")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.value==-123)
		value=self.EvaluateCommon("'123'")
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected String")
		self.assertTrue(value.value=='123')
		value=self.EvaluateCommon("time'15:28'")
		self.assertTrue(value.typeCode==edm.SimpleType.Time,"Expected Time")
		self.assertTrue(value.value.hour==15)
		self.assertTrue(value.value.minute==28)
		self.assertTrue(value.value.second==0)
		value=self.EvaluateCommon("datetimeoffset'2002-10-10T12:00:00-05:00'")
		self.assertTrue(value.typeCode==edm.SimpleType.DateTimeOffset,"Expected DateTimeOffset")
		self.assertTrue(value.value==iso.TimePoint.FromString('2002-10-10T12:00:00-05:00'))

	def testCaseEvaluateMethodCallExpression(self):
		"""Cursory check only."""
		value=self.EvaluateCommon("length('x')")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.value==1)

	def testCaseEvaluateBooleanMethodCallExpress(self):
		"""Cursory check only."""
		value=self.EvaluateCommon("startswith('xyz','x')")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value==True)

	def testCaseEvaluateEndsWithExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The endsWithMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		...the result of evaluating the endsWithMethodCallExpression
		SHOULD be a value of the EDM Primitive type Edm.Boolean.

		...the data service SHOULD evaluate ... by returning a Boolean
		value indicating whether the end of the first parameter
		values matches the second parameter value."""
		value=self.EvaluateCommon("endswith('startswith','with')")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value==True)
		value=self.EvaluateCommon("endswith('startswith','start')")
		self.assertTrue(value.value==False)
		value=self.EvaluateCommon("endswith('startswith','WITH')")
		# not case insensitive
		self.assertTrue(value.value==False)
		try:
			value=self.EvaluateCommon("endswith('3.14',4)")
			self.fail("integer as suffix")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("endswith('3.14')")
			self.fail("1 parameter")
		except EvaluationError:
			pass

	def testCaseEvaluateIndexOfExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The indexOfMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		...the EDM Primitive type of the result of evaluating the
		indexOfMethodCallExpression SHOULD be a value of the EDM
		Primitive type Edm.Int32.
		
		the data service SHOULD evaluate ... by returning an integer
		value indicating the index of the first occurrence of the second
		parameter value in the first parameter value. If no index is
		found, a value of -1 SHOULD be returned."""
		value=self.EvaluateCommon("indexof('startswith','tart')")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.value==1)
		value=self.EvaluateCommon("indexof('startswith','start')")
		self.assertTrue(value.value==0)
		value=self.EvaluateCommon("indexof('startswith','t')")
		self.assertTrue(value.value==1)
		# not case insensitive
		value=self.EvaluateCommon("indexof('startswith','W')")
		self.assertTrue(value.value==-1)
		try:
			value=self.EvaluateCommon("indexof('3.14',1)")
			self.fail("integer as parameter")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("indexof('3.14')")
			self.fail("1 parameter")
		except EvaluationError:
			pass

	def testCaseEvaluateReplaceExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The replaceMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		the EDM Primitive type of the result of evaluating the
		replaceMethodCallExpression SHOULD be a value of the EDM
		Primitive type Edm.String.

		the data service SHOULD evaluate ... by returning a string value
		with all occurrences of the second parameter value replaced by
		the third parameter value in the first parameter value."""
		value=self.EvaluateCommon("replace('startswith','tart','cake')")
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected String")
		self.assertTrue(value.value==u"scakeswith")
		value=self.EvaluateCommon("replace('startswith','t','x')")
		self.assertTrue(value.value==u"sxarxswixh")
		# not case insensitive
		value=self.EvaluateCommon("replace('sTartswith','t','x')")
		self.assertTrue(value.value==u"sTarxswixh")
		value=self.EvaluateCommon("replace('startswith','t','tx')")
		self.assertTrue(value.value==u"stxartxswitxh")
		try:
			value=self.EvaluateCommon("replace('3.14','1',2)")
			self.fail("integer as parameter")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("replace('3.14','1')")
			self.fail("2 parameter")
		except EvaluationError:
			pass

	def testCaseEvaluateStartsWithExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The startsWithMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		...the result of evaluating the startsWithMethodCallExpression
		SHOULD be a value of the EDM Primitive type Edm.Boolean.

		...the data service SHOULD evaluate ... by returning a Boolean
		value indicating whether the beginning of the first parameter
		values matches the second parameter value."""
		value=self.EvaluateCommon("startswith('startswith','start')")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value==True)
		value=self.EvaluateCommon("startswith('startswith','end')")
		self.assertTrue(value.value==False)
		value=self.EvaluateCommon("startswith('startswith','Start')")
		# not case insensitive
		self.assertTrue(value.value==False)
		try:
			value=self.EvaluateCommon("startswith('3.14',3)")
			self.fail("integer as prefix")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("startswith('3.14')")
			self.fail("1 parameter")
		except EvaluationError:
			pass

	def testCaseEvaluateToLowerExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The toLowerMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		...the EDM Primitive type of the result ... SHOULD be a value of
		the EDM Primitive type Edm.String.

		...the data service SHOULD evaluate ... by returning a string
		value with the contents of the parameter value converted to
		lower case."""
		value=self.EvaluateCommon("tolower('Steve')")
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected String")
		self.assertTrue(value.value==u"steve")
		value=self.EvaluateCommon(u"tolower('CAF\xc9')")
		self.assertTrue(value.value==u'caf\xe9')
		value=self.EvaluateCommon(u"tolower('caf\xe9')")
		self.assertTrue(value.value==u'caf\xe9')
		try:
			value=self.EvaluateCommon("tolower(3.14F)")
			self.fail("floating lower")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("tolower('Steve','John')")
			self.fail("2 parameters")
		except EvaluationError:
			pass

	def testCaseEvaluateToUpperExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The toUpperMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		...the EDM Primitive type of the result ... SHOULD be a value of
		the EDM Primitive type Edm.String.

		...the data service SHOULD evaluate ... by returning a string
		value with the contents of the parameter value converted to
		upper case."""
		value=self.EvaluateCommon("toupper('Steve')")
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected String")
		self.assertTrue(value.value==u"STEVE")
		value=self.EvaluateCommon(u"toupper('CAF\xc9')")
		self.assertTrue(value.value==u'CAF\xc9')
		value=self.EvaluateCommon(u"toupper('caf\xe9')")
		self.assertTrue(value.value==u'CAF\xc9')
		try:
			value=self.EvaluateCommon("toupper(3.14F)")
			self.fail("floating upper")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("toupper('Steve','John')")
			self.fail("2 parameters")
		except EvaluationError:
			pass

	def testCaseEvaluateTrimExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The trimMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		the EDM Primitive type of the result of evaluating the
		trimMethodCallExpression SHOULD be a value of the EDM Primitive
		type Edm.String.

		the data service SHOULD evaluate ... by returning a string value
		with the contents of the parameter value with all leading and
		trailing white-space characters removed."""
		value=self.EvaluateCommon("trim('  Steve\t\n\r \r\n')")
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected String")
		self.assertTrue(value.value==u"Steve")
		value=self.EvaluateCommon(u"trim(' C  a  f \xe9 ')")
		self.assertTrue(value.value==u'C  a  f \xe9')
		try:
			value=self.EvaluateCommon("trim(3.14F)")
			self.fail("floating trim")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("trim('Steve','John')")
			self.fail("2 parameters")
		except EvaluationError:
			pass

	def testCaseEvaluateSubstringExpression(self):
		"""The first parameter expression MUST evaluate to a value of
		the EDM Primitive type Edm.String. The second and third
		parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.Int32.

		The substringMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		the EDM Primitive type of the result of evaluating the
		substringMethodCallExpression SHOULD be a value of the EDM
		Primitive type Edm.String.

		the data service SHOULD evaluate ... by returning the string
		value starting at the character index specified by the second
		parameter value in the first parameter string value. If the
		optional third parameter is specified, the resulting string
		SHOULD be the length (in characters) of the third parameter
		value. Otherwise, the entire string from the specified starting
		index is returned."""
		value=self.EvaluateCommon("substring('startswith',1,4)")
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected String")
		self.assertTrue(value.value==u"tart")
		value=self.EvaluateCommon("substring('startswith',1)")
		self.assertTrue(value.value==u"tartswith")
		try:
			value=self.EvaluateCommon("substring('startswith',1.0D,4)")
			self.fail("double as parameter")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("substring('3.14')")
			self.fail("1 parameter")
		except EvaluationError:
			pass
	
	def testCaseEvaluateSubstringOfExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The substringOfMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		the EDM Primitive type of the result of evaluating the
		substringOfMethodCallExpression SHOULD be a value of the EDM
		Primitive type Edm.Boolean.

		...the data service SHOULD evaluate ... by returning a Boolean
		value indicating whether the second parameter string value
		occurs in the first parameter string value.
		
		TODO: There appears to be an error in the specification here and
		this should have been the other way around!  Correct in v3"""
		value=self.EvaluateCommon("substringof('startswith','tart')")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.value==True)
		value=self.EvaluateCommon("substringof('startswith','start')")
		self.assertTrue(value.value==True)
		value=self.EvaluateCommon("substringof('startswith','t')")
		self.assertTrue(value.value==True)
		# not case insensitive
		value=self.EvaluateCommon("substringof('startswith','W')")
		self.assertTrue(value.value==False)
		try:
			value=self.EvaluateCommon("substringof('3.14',1)")
			self.fail("integer as parameter")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("substringof('3.14')")
			self.fail("1 parameter")
		except EvaluationError:
			pass
		
	def testCaseEvaluateConcatExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The concatMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		the EDM Primitive type of the result of evaluating the
		concatMethodCallExpression SHOULD be a value of the EDM
		Primitive type Edm.String.

		the data service SHOULD evaluate ... by returning a string value
		which is the first and second parameter values merged together
		with the first parameter value coming first in the result."""
		value=self.EvaluateCommon("concat('starts','with')")
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected String")
		self.assertTrue(value.value==u"startswith")
		value=self.EvaluateCommon("concat('3.1',concat('4','159'))")
		self.assertTrue(value.value==u"3.14159")
		try:
			value=self.EvaluateCommon("concat('3.14',1)")
			self.fail("integer as parameter")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("concat('3.14')")
			self.fail("1 parameter")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("concat('3.1','4','159')")
			self.fail("3 parameters")
		except EvaluationError:
			pass
	
	def testCaseEvaluateLengthExpression(self):
		"""The parameter expressions MUST evaluate to a value of the EDM
		Primitive type Edm.String.

		The lengthMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.
		
		the EDM Primitive type of the result of evaluating the
		lengthMethodCallExpression SHOULD be a value of the EDM
		Primitive type Edm.Int32.

		the data service SHOULD evaluate ... by returning the number of
		characters in the specified parameter value."""
		value=self.EvaluateCommon("length('Steve')")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.value==5)
		value=self.EvaluateCommon(u"length('CAF\xc9')")
		self.assertTrue(value.value==4)
		value=self.EvaluateCommon(u"length('')")
		self.assertTrue(value.value==0)
		try:
			value=self.EvaluateCommon("length(3.14F)")
			self.fail("floating length")
		except EvaluationError:
			pass
		try:
			value=self.EvaluateCommon("length('Steve','John')")
			self.fail("2 parameters")
		except EvaluationError:
			pass		

	def testCaseEvaluateYearExpression(self):
		"""The parameter expression MUST evaluate to a value of the EDM
		Primitive type Edm.DateTime.

		The yearMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.

		the EDM Primitive type of the result of evaluating the
		yearMethodCallExpression SHOULD be the EDM Primitive type
		Edm.Int32.

		the data service SHOULD evaluate ... by returning the year
		component value of the parameter value.
		
		We implement very similar tests for month, day, hour, minute and second"""
		for f,r in (
			("year",2013),
			("month",9),
			("day",1),
			("hour",10),
			("minute",56),
			("second",0)):
			value=self.EvaluateCommon("%s(datetime'2013-09-01T10:56')"%f)
			self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
			self.assertTrue(value.value==r)
			try:
				value=self.EvaluateCommon("%s(datetimeoffset'2013-09-01T10:56:12-05:00')"%f)
				self.fail("datetimeoffset %s"%f)
			except EvaluationError:
				pass
			try:
				value=self.EvaluateCommon("%s(datetime'2013-09-01T10:56',datetime'2013-09-01T10:57')"%f)
				self.fail("2 parameters")
			except EvaluationError:
				pass

	def testCaseEvaluateRoundExpression(self):
		"""The parameter expression MUST evaluate to a value of one of
		the following EDM Primitive types:
			Edm.Decimal
			Edm.Double

		The roundMethodCallExpression SHOULD NOT be supported for
		parameters of any other EDM Primitive types.

		data service SHOULD follow the numeric promotion rules for
		method call parameters defined in Binary numeric promotions to
		implicitly convert the parameters to a supported EDM Primitive
		type.
		
		The EDM Primitive type of the result of evaluating the
		roundMethodCallExpression MUST be the same type as the parameter.
		
		the data service SHOULD evaluate ... by returning the nearest
		integral value to the parameter value, following the rules
		defined in [IEEE754-2008] for the rounding operation.
		
		We cover floor and ceil using similar routines..."""
		for f,r in (
			("round",(2,2,-2,2,3,-3,2,3)),
			("floor",(1,2,-3,1,2,-3,2,3)),
			("ceiling",(2,3,-2,2,3,-2,3,3))):
			value=self.EvaluateCommon("%s(1.5D)"%f)
			self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
			self.assertTrue(value.value==r[0])
			# check rounding to even for binary floating point
			value=self.EvaluateCommon("%s(2.5D)"%f)
			self.assertTrue(value.value==r[1])
			value=self.EvaluateCommon("%s(-2.5D)"%f)
			self.assertTrue(value.value==r[2])
			value=self.EvaluateCommon("%s(1.5M)"%f)
			self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
			self.assertTrue(value.value==r[3])
			# check rounding away from zero for decimals
			value=self.EvaluateCommon("%s(2.5M)"%f)
			self.assertTrue(value.value==r[4])
			value=self.EvaluateCommon("%s(-2.5M)"%f)
			self.assertTrue(value.value==r[5])
			# single promotes to double
			value=self.EvaluateCommon("%s(2.5F)"%f)
			self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
			self.assertTrue(value.value==r[6])
			# integers promote to decimal - seems a bit strange but there you go
			value=self.EvaluateCommon("%s(3)"%f)
			self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
			self.assertTrue(value.value==r[7])
			try:
				value=self.EvaluateCommon("%s('3')"%f)
				self.fail("round string parameter")
			except EvaluationError:
				pass
			try:
				value=self.EvaluateCommon("%s(3.1D,3.2D)"%f)
				self.fail("two parameters")
			except EvaluationError:
				pass		

	def testCaseOperatorPrecedence(self):
		value=self.EvaluateCommon("--2 mul 3 div 1 mul 2 mod 2 add 2 div 2 sub 1 eq 2 and false or true")
		self.assertTrue(value.value is True)
	
	def testCaseStringConversionExpression(self):
		for example in [
			u"true and false",
			u"(((((((false) and (((false)) or true)))))))",
			"(false and (false or true))",
			"2M add 2M",
			"2D add 2M",
			"2F add 2D",
			"2 add 2L",
			"2 add null",
			"4D sub 2M",
			"4 sub null",
			"4F mul 2D",
			"-5 div 2L",
			"5.5M mod 2M",
			"-(2M)",
			"-(-2F)",
			"-null",
			"2F eq 2D",
			"datetime'2013-08-30T18:49' eq datetime'2013-08-30T18:49'",
			"guid'b3afeebc-9658-4699-9d9c-1df551fd6814' eq guid'b3afeebc-9658-4699-9d9c-1df551fd6814'",
			"X'DEADBEEF' eq binary'deadbeef'",
			"2 eq null",
			"X'DEAD' ne binary'BEEF'",
			"2.1F lt 2D",
			"'20' lt '3'",
			"2D gt 2M",
			"datetime'2013-08-30T18:49' ge datetime'2013-08-30T18:49:00'",
			"not false",
			"not false and not true",
			"isof(2.0D,'Edm.Single')",
			"cast(2L,'Edm.Single')",
			"true",
			"guid'b3afeebc-9658-4699-9d9c-1df551fd6814'",
			"123456L",
			"time'10:56'",
			"length('x')",
			"startswith('xyz','x')",
			"endswith('startswith','with')",
			"indexof('startswith','tart')",
			"replace('startswith','tart','cake')",
			"tolower('Steve')",
			"toupper('Steve')",
			"trim('  Steve\t\n\r \r\n')",
			"substring('startswith',1,4)",
			"substringof('startswith','tart')",
			"concat('starts','with')",
			"length('Steve')",
			"year(datetime'2013-09-01T10:56')",
			"month(datetime'2013-09-01T10:56')",
			"day(datetime'2013-09-01T10:56')",
			"hour(datetime'2013-09-01T10:56')",
			"minute(datetime'2013-09-01T10:56')",
			"second(datetime'2013-09-01T10:56')",
			"round(1.5D)",
			"floor(1.5D)",
			"ceiling(1.5D)",
			"--2 mul 3 div 1 mul 2 mod 2 add 2 div 2 sub 1 eq 2 and false or true",
			]:
			e1=CommonExpression.FromString(example)
			e2=CommonExpression.FromString(unicode(e1))
			self.assertTrue(e1.Evaluate(None)==e2.Evaluate(None),"Mismatch evaluating: %s"%example)
			self.assertTrue(unicode(e1)==unicode(e2),"Unstable expression: %s, %s!=%s"%(example,unicode(e1),unicode(e2)))
			

class ODataURITests(unittest.TestCase):

	def testCaseConstructor(self):
		dsURI=ODataURI('/')
		self.assertTrue(dsURI.pathPrefix=='',"empty path prefix")
		self.assertTrue(dsURI.resourcePath=='/',"resource path")
		self.assertTrue(dsURI.queryOptions==[],'query options')
		self.assertTrue(dsURI.navPath==[],"navPath: %s"%repr(dsURI.navPath))
		dsURI=ODataURI('/','/x')
		self.assertTrue(dsURI.pathPrefix=='/x',"non-empty path prefix")
		self.assertTrue(dsURI.resourcePath==None,"resource path")
		dsURI=ODataURI('/x','/x')
		self.assertTrue(dsURI.pathPrefix=='/x',"non-empty path prefix")
		self.assertTrue(dsURI.resourcePath=='',"empty resource path, special case")
		self.assertTrue(dsURI.navPath==[],"empty navPath, special case: %s"%repr(dsURI.navPath))		
		dsURI=ODataURI('/x.svc/Products','/x.svc')
		self.assertTrue(dsURI.pathPrefix=='/x.svc',"svc path prefix")
		self.assertTrue(dsURI.resourcePath=='/Products',"resource path")
		self.assertTrue(len(dsURI.navPath)==1,"navPath: %s"%repr(dsURI.navPath))
		self.assertTrue(type(dsURI.navPath[0][0]) is UnicodeType,"entitySet name type")
		self.assertTrue(dsURI.navPath[0][0]=='Products',"entitySet name: Products")
		self.assertTrue(dsURI.navPath[0][1]==None,"entitySet no key-predicate")		
		dsURI=ODataURI('Products','/x.svc')
		self.assertTrue(dsURI.pathPrefix=='/x.svc',"svc path prefix")
		self.assertTrue(dsURI.resourcePath=='/Products',"resource path")
		try:
			dsURI=ODataURI('Products','x.svc')
			self.fail("x.svc/Products  - illegal path")
		except ValueError:
			pass
	
	def testCaseQueryOptions(self):
		"""QueryOptions:
		
		Any number of the query options MAY<5> be specified in a data service URI.
		The order of Query Options within a URI MUST be insignificant.
		Query option names and values MUST be treated as case sensitive.
		System Query Option names MUST begin with a "$", as seen in System Query Option (section 2.2.3.6.1).
		Custom Query Options (section 2.2.3.6.2) MUST NOT begin with a "$".
		"""
		dsURI=ODataURI("Products()?$format=json&$top=20&$skip=10&space='%20'",'/x.svc')
		self.assertTrue(set(dsURI.sysQueryOptions.keys())==set([SystemQueryOption.format,
			SystemQueryOption.top,SystemQueryOption.skip]),repr(dsURI.sysQueryOptions))
		self.assertTrue(dsURI.queryOptions==["space='%20'"],'query options')
		dsURI=ODataURI("Products()?$top=20&space='%20'&$format=json&$skip=10",'/x.svc')
		self.assertTrue(set(dsURI.sysQueryOptions.keys())==set([SystemQueryOption.format,
			SystemQueryOption.top,SystemQueryOption.skip]),repr(dsURI.sysQueryOptions))
		self.assertTrue(dsURI.queryOptions==["space='%20'"],'query options')		
		try:
			dsURI=ODataURI("Products()?$unsupported=10",'/x.svc')
			self.fail("$unsupported system query option")
		except InvalidSystemQueryOption:
			pass

	def testCaseCommonExpressions(self):
		dsURI=ODataURI("Products()?$filter=substringof(CompanyName,%20'bikes')",'/x.svc')
		self.assertTrue(isinstance(dsURI.sysQueryOptions[SystemQueryOption.filter],CommonExpression),"Expected common expression")
		dsURI=ODataURI("Products()?$filter=true%20and%20false",'/x.svc')
		f=dsURI.sysQueryOptions[SystemQueryOption.filter]
		self.assertTrue(isinstance(f,CommonExpression),"Expected common expression")
		self.assertTrue(isinstance(f,BinaryExpression),"Expected binary expression, %s"%repr(f))
		self.assertTrue(f.operator==Operator.boolAnd,"Expected and: %s"%repr(f.operator))		
		try:
			dsURI=ODataURI("Products()?$filter=true%20nand%20false",'/x.svc')
			self.fail("Expected exception for nand")
		except InvalidSystemQueryOption:
			pass
				
	def testCaseEntitySet(self):
		dsURI=ODataURI("Products()?$format=json&$top=20&$skip=10&space='%20'",'/x.svc')
		self.assertTrue(dsURI.resourcePath=='/Products()',"resource path")
		self.assertTrue(set(dsURI.sysQueryOptions.keys())==set([SystemQueryOption.format,
			SystemQueryOption.top,SystemQueryOption.skip]),repr(dsURI.sysQueryOptions))
		self.assertTrue(dsURI.queryOptions==["space='%20'"],'query options')
		self.assertTrue(dsURI.navPath==[(u'Products',{})],"entitySet: Products, found %s"%repr(dsURI.navPath))
		dsURI=ODataURI('Products()/$count','/x.svc')
		self.assertTrue(dsURI.resourcePath=='/Products()/$count',"resource path")
		self.assertTrue(dsURI.sysQueryOptions=={},'sysQueryOptions')
		self.assertTrue(dsURI.queryOptions==[],'query options')
		self.assertTrue(dsURI.navPath==[(u'Products',{})],"path: %s"%repr(dsURI.navPath))
		self.assertTrue(dsURI.pathOption==PathOption.count,"$count recognised")
		dsURI=ODataURI('Products(1)/$value','/x.svc')
		self.assertTrue(len(dsURI.navPath)==1)
		self.assertTrue(dsURI.navPath[0][0]==u'Products')
		self.assertTrue(len(dsURI.navPath[0][1]))
		self.assertTrue(isinstance(dsURI.navPath[0][1][u''],edm.Int32Value),"Key value type")
		self.assertTrue(dsURI.navPath[0][1][u''].value==1,"Key value")
		# self.assertTrue(dsURI.navPath==[(u'Products',{'':1})],"path: %s"%repr(dsURI.navPath))
		self.assertTrue(dsURI.pathOption==PathOption.value,"$value recognised")
		dsURI=ODataURI('Products(x=1,y=2)','/x.svc')
		self.assertTrue(len(dsURI.navPath)==1)
		self.assertTrue(dsURI.navPath[0][0]==u'Products')
		self.assertTrue(isinstance(dsURI.navPath[0][1][u'x'],edm.Int32Value),"Key value type")
		self.assertTrue(dsURI.navPath[0][1][u'x'].value==1,"x Key value")
		self.assertTrue(isinstance(dsURI.navPath[0][1][u'y'],edm.Int32Value),"Key value type")
		self.assertTrue(dsURI.navPath[0][1][u'y'].value==2,"y Key value")		
		# self.assertTrue(dsURI.navPath==[(u'Products',{u'x':1,u'y':2})],"path: %s"%repr(dsURI.navPath))
		
	def testCaseExpand(self):
		"""Redundant expandClause rules on the same data service URI can
		be considered valid, but MUST NOT alter the meaning of the
		URI."""
		dsURI=ODataURI("Customers?$expand=Orders",'/x.svc')
		expand=dsURI.sysQueryOptions[SystemQueryOption.expand]
		self.assertTrue(len(expand)==1,"One path")
		self.assertTrue(expand['Orders'] is None,"Orders nav path")
		self.assertTrue(FormatExpand(expand)=="Orders",FormatExpand(expand))
		dsURI=ODataURI("Customers?$expand=Orders,Orders",'/x.svc')
		expand=dsURI.sysQueryOptions[SystemQueryOption.expand]
		self.assertTrue(len(expand)==1,"One path")
		self.assertTrue(expand['Orders'] is None,"redundant Orders nav path")
		self.assertTrue(FormatExpand(expand)=="Orders",FormatExpand(expand))
		dsURI=ODataURI("Orders?$expand=OrderLines/Product,Customer",'/x.svc')
		expand=dsURI.sysQueryOptions[SystemQueryOption.expand]
		self.assertTrue(expand['OrderLines']=={'Product':None},"OrderLines expansion: %s"%str(expand))
		self.assertTrue(expand['Customer'] is None,"Customer expansion")
		self.assertTrue(FormatExpand(expand)=="Customer,OrderLines/Product")
	
	def testCaseFilter(self):
		dsURI=ODataURI("Orders?$filter=ShipCountry%20eq%20'France'",'/x.svc')
		filter=dsURI.sysQueryOptions[SystemQueryOption.filter]
		self.assertTrue(isinstance(filter,BinaryExpression),"Binary expression component")
		self.assertTrue(isinstance(filter.operands[0],PropertyExpression))
		self.assertTrue(filter.operands[0].name=="ShipCountry")
		dsURI=ODataURI("Orders?$filter%20=%20Customers/ContactName%20ne%20'Fred'",'/x.svc')
		filter=dsURI.sysQueryOptions[SystemQueryOption.filter]
		self.assertTrue(filter.operands[0].operands[1].name=="ContactName")
	
	def testCaseFormat(self):
		dsURI=ODataURI("Orders?$format=json",'/x.svc')
		format=dsURI.sysQueryOptions[SystemQueryOption.format]
		self.assertTrue(isinstance(format,http.AcceptList),"Format is an HTTP AcceptList instance")
		self.assertTrue(str(format)=='application/json',str(format[0]))

	def testCaseOrderby(self):
		dsURI=ODataURI("Orders?$orderby=ShipCountry",'/x.svc')
		orderBy=dsURI.sysQueryOptions[SystemQueryOption.orderby]
		self.assertTrue(len(orderBy)==1,"Single orderBy clause")
		orderBy=orderBy[0]
		self.assertTrue(orderBy[1]==1,"default is asc")
		self.assertTrue(isinstance(orderBy[0],PropertyExpression),"OrderBy is a property expression")
		self.assertTrue(orderBy[0].name=='ShipCountry',str(orderBy[0]))
		dsURI=ODataURI("Orders?$orderby%20=%20ShipCountry%20ne%20'France'%20desc",'/x.svc')
		orderBy=dsURI.sysQueryOptions[SystemQueryOption.orderby]
		orderBy=orderBy[0]
		self.assertTrue(orderBy[1]==-1,"desc")
		self.assertTrue(isinstance(orderBy[0],BinaryExpression),"OrderBy is a binary expression")
		self.assertTrue(orderBy[0].operands[0].name=='ShipCountry',str(orderBy[0].operands[0]))
		self.assertTrue(orderBy[0].operands[0].name=='ShipCountry',str(orderBy[0].operands[0]))
		dsURI=ODataURI("Orders?$orderby%20=%20ShipCountry%20ne%20'France'%20desc,OrderID%20asc",'/x.svc')
		orderBy=dsURI.sysQueryOptions[SystemQueryOption.orderby]
		self.assertTrue(len(orderBy)==2,"Two orderBy clauses")
					
	def testCaseSkip(self):
		"""The value of this query option ... MUST be an integer greater
		than or equal to zero. If a value less than 0 is specified, the
		URI should be considered malformed."""
		dsURI=ODataURI("Orders?$orderby=OrderDate%20desc&$skip=10",'/x.svc')
		skip=dsURI.sysQueryOptions[SystemQueryOption.skip]
		self.assertTrue(type(skip) is IntType,"skip type")
		self.assertTrue(skip==10,"skip 10")
		dsURI=ODataURI("Customers('ALFKI')/Orders?$skip=10",'/x.svc')
		skip=dsURI.sysQueryOptions[SystemQueryOption.skip]
		self.assertTrue(skip==10,"skip 10")
		dsURI=ODataURI("Orders?$orderby=OrderDate%20desc&$skip=0",'/x.svc')
		skip=dsURI.sysQueryOptions[SystemQueryOption.skip]
		self.assertTrue(skip==0,"skip 0")
		try:
			dsURI=ODataURI("Orders?$orderby=OrderDate%20desc&$skip=-1",'/x.svc')
			self.fail("skip=-1")
		except InvalidSystemQueryOption:
			pass

	def testCaseTop(self):
		"""The value of this query option ... MUST be an integer greater
		than or equal to zero. If a value less than 0 is specified, the
		URI should be considered malformed."""
		dsURI=ODataURI("Orders?$orderby=OrderDate%20desc&$top=10",'/x.svc')
		top=dsURI.sysQueryOptions[SystemQueryOption.top]
		self.assertTrue(type(top) is IntType,"top type")
		self.assertTrue(top==10,"top 10")
		dsURI=ODataURI("Customers('ALFKI')/Orders?$top=10",'/x.svc')
		top=dsURI.sysQueryOptions[SystemQueryOption.top]
		self.assertTrue(top==10,"top 10")
		dsURI=ODataURI("Orders?$orderby=OrderDate%20desc&$top=0",'/x.svc')
		top=dsURI.sysQueryOptions[SystemQueryOption.top]
		self.assertTrue(top==0,"top 0")
		try:
			dsURI=ODataURI("Orders?$orderby=OrderDate%20desc&$top=-1",'/x.svc')
			self.fail("top=-1")
		except InvalidSystemQueryOption:
			pass

	def testCaseSkipToken(self):
		"""The value of this query option ... MUST be an integer greater
		than or equal to zero. If a value less than 0 is specified, the
		URI should be considered malformed."""
		dsURI=ODataURI("Orders?$orderby=OrderDate%20desc&$skiptoken=AEF134ad",'/x.svc')
		skiptoken=dsURI.sysQueryOptions[SystemQueryOption.skiptoken]
		self.assertTrue(type(skiptoken) is UnicodeType,"skiptoken type")
		self.assertTrue(skiptoken==u"AEF134ad","skiptoken opqque string")
		dsURI=ODataURI("Customers('ALFKI')/Orders?$skiptoken=0%2010",'/x.svc')
		skiptoken=dsURI.sysQueryOptions[SystemQueryOption.skiptoken]
		self.assertTrue(skiptoken==u"0 10","skiptoken 010")

	def testCaseInlineCount(self):
		"""inlinecountQueryOp = "$inlinecount=" ("allpages" / "none") """
		dsURI=ODataURI("Orders?$inlinecount=allpages",'/x.svc')
		inlineCount=dsURI.sysQueryOptions[SystemQueryOption.inlinecount]
		self.assertTrue(inlineCount==InlineCount.allpages,"allpages constant")
		dsURI=ODataURI("Orders?$inlinecount=allpages&$top=10",'/x.svc')
		inlineCount=dsURI.sysQueryOptions[SystemQueryOption.inlinecount]
		self.assertTrue(inlineCount==InlineCount.allpages,"allpages constant")
		dsURI=ODataURI("Orders?$inlinecount=none&$top=10",'/x.svc')
		inlineCount=dsURI.sysQueryOptions[SystemQueryOption.inlinecount]
		self.assertTrue(inlineCount==InlineCount.none,"none constant")
		dsURI=ODataURI("Orders?$inlinecount=allpages&$filter=ShipCountry%20eq%20'France'",'/x.svc')
		inlineCount=dsURI.sysQueryOptions[SystemQueryOption.inlinecount]
		self.assertTrue(inlineCount==InlineCount.allpages,"allpages constant")
	
	def testCaseSelect(self):
		"""Syntax::
		
		selectQueryOp = "$select=" selectClause
		selectClause = [WSP] selectItem [[WSP] "," selectClause] [WSP]
		selectItem = star / selectedProperty / (selectedNavProperty ["/" selectItem])
		selectedProperty = entityProperty / entityComplexProperty
		selectedNavProperty = entityNavProperty-es / entityNavProperty-et
		star = "*"	"""
		dsURI=ODataURI("Customers?$select=CustomerID,CompanyName,Address",'/x.svc')
		select=dsURI.sysQueryOptions[SystemQueryOption.select]
		self.assertTrue(len(select)==3,"Three paths")
		self.assertTrue(select=={'CompanyName':None,'CustomerID':None,'Address':None})		
		dsURI=ODataURI("Customers?$select=CustomerID,Orders",'/x.svc')
		select=dsURI.sysQueryOptions[SystemQueryOption.select]
		self.assertTrue(select=={'CustomerID':None,'Orders':None})		
		dsURI=ODataURI("Customers?$select=CustomerID,Orders&$expand=Orders/OrderDetails",'/x.svc')
		select=dsURI.sysQueryOptions[SystemQueryOption.select]
		self.assertTrue(select=={'CustomerID':None,'Orders':None})		
		dsURI=ODataURI("Customers?$select=*",'/x.svc')
		select=dsURI.sysQueryOptions[SystemQueryOption.select]
		self.assertTrue(select=={'*':None})		
		dsURI=ODataURI("Customers?$select=CustomerID,Orders/*&$expand=Orders/OrderDetails",'/x.svc')
		select=dsURI.sysQueryOptions[SystemQueryOption.select]
		self.assertTrue(select=={'CustomerID':None,'Orders':{'*':None}})		
		dsURI=ODataURI("/service.svc/Customers?$expand=Orders&$filter=substringof(CompanyName,%20'bikes')&$orderby=CompanyName%20asc&$top=2&$skip=3&$skiptoken='Contoso','AKFNU'&$inlinecount=allpages&$select=CustomerID,CompanyName,Orders&$format=xml")
		select=dsURI.sysQueryOptions[SystemQueryOption.select]
		self.assertTrue(len(select)==3,"Three paths")
		try:
			dsURI=ODataURI("Customers?$select=CustomerID,*/Orders")
			self.fail("* must be last item in a select clause")
		except InvalidSystemQueryOption:
			pass


class DataServiceRegressionTests(unittest.TestCase):
	"""Abstract class used to test individual data services."""
	
	def setUp(self):
		self.regressionData=FilePath(FilePath(__file__).abspath().split()[0],'data_odatav2','sample_server')
		doc=edmx.Document()
		mdPath=self.regressionData.join('regression.xml')
		with mdPath.open('rb') as f:
			doc.Read(f)
		self.ds=doc.root.DataServices

	def tearDown(self):
		pass
	
	def RunTestCaseAllTypes(self):
		allTypes=self.ds['RegressionModel.RegressionContainer.AllTypes']
		with allTypes.OpenCollection() as collection:
			entity=collection.NewEntity()
			# <Property Name="ID" Type="Edm.Int32" Nullable="false"/>
			entity['ID'].SetFromValue(1)
			# <Property Name="BinaryFixed" Type="Edm.Binary" MaxLength="10" FixedLength="true"/>
			entity['BinaryFixed'].SetFromValue('1234567890')
			# <Property Name="BinaryVariable" Type="Edm.Binary" MaxLength="10" FixedLength="false"/>
			entity['BinaryVariable'].SetFromValue('1234567')
			# <Property Name="BooleanProperty" Type="Edm.Boolean"/>
			entity['BooleanProperty'].SetFromValue(True)
			# <Property Name="DateTimeProperty" Type="Edm.DateTime" Precision="3"/>
			entity['DateTimeProperty'].SetFromValue(iso.TimePoint.FromString('1972-03-03T09:45:00'))
			# <Property Name="TimeProperty" Type="Edm.Time" Precision="3"/>
			entity['TimeProperty'].SetFromValue(iso.Time.FromString('09:45:00'))
			# <Property Name="DateTimeOffsetProperty" Type="Edm.DateTimeOffset" Precision="3"/>
			entity['DateTimeOffsetProperty'].SetFromValue(iso.TimePoint.FromString('1972-07-03T09:45:00+01:00'))
			# <Property Name="DecimalProperty" Type="Edm.Decimal" Precision="10" Scale="2"/>
			entity['DecimalProperty'].SetFromValue(decimal.Decimal('3.14'))
			# <Property Name="SingleValue" Type="Edm.Single"/>
			entity['SingleValue'].SetFromValue(3.14)
			# <Property Name="DoubleValue" Type="Edm.Double"/>
			entity['DoubleValue'].SetFromValue(3.14)
			# <Property Name="GuidValue" Type="Edm.Guid"/>
			entity['GuidValue'].SetFromValue(uuid.UUID(int=3))
			# <Property Name="SByteValue" Type="Edm.SByte"/>
			entity['SByteValue'].SetFromValue(3)			
			# <Property Name="Int16Value" Type="Edm.Int16"/>
			entity['Int16Value'].SetFromValue(3)
			# <Property Name="Int64Value" Type="Edm.Int64"/>
			entity['Int64Value'].SetFromValue(3)
			# <Property Name="ByteValue" Type="Edm.Byte"/>
			entity['ByteValue'].SetFromValue(3)
			# <Property Name="UnicodeString" Type="Edm.String" Unicode="true" FixedLength="false" MaxLength="10"/>
			entity['UnicodeString'].SetFromValue(u"Caf\xe9")
			# <Property Name="ASCIIString" Type="Edm.String" Unicode="false" FixedLength="false" MaxLength="10"/>
			entity['ASCIIString'].SetFromValue(u"Cafe")
			# <Property Name="FixedString" Type="Edm.String" FixedLength="true" MaxLength="5"/>
			entity['FixedString'].SetFromValue(u"ALFKI")
			#	CREATE
			collection.InsertEntity(entity)
			#	READ (collection)
			self.assertTrue(len(collection)==1,"AllTypes length after insert")
			gotEntity=collection.values()[0]
			self.assertTrue(gotEntity['ID'].value==1)
			#	READ (by key)
			gotEntity=collection[1]
			self.assertTrue(gotEntity['ID'].value==1,"ID on read")
			self.assertTrue(gotEntity['BinaryFixed'].value=='1234567890',"BinaryFixed on read")
			self.assertTrue(gotEntity['BinaryVariable'].value=='1234567',"BinaryVariable on read")
			self.assertTrue(gotEntity['BooleanProperty'].value==True,"BooleanProperty on read")
			self.assertTrue(isinstance(gotEntity['DateTimeProperty'].value,iso.TimePoint),"DateTimeProperty type on read")
			self.assertTrue(gotEntity['DateTimeProperty'].value==iso.TimePoint.FromString('1972-03-03T09:45:00'),"DateTimeProperty value on read")
			self.assertTrue(isinstance(gotEntity['TimeProperty'].value,iso.Time),"TimeProperty type on read")
			self.assertTrue(gotEntity['TimeProperty'].value==iso.Time.FromString('09:45:00'),"TimeProperty value on read")
			self.assertTrue(isinstance(gotEntity['DateTimeOffsetProperty'].value,iso.TimePoint),"DateTimeOffsetProperty type on read")
			self.assertTrue(gotEntity['DateTimeOffsetProperty'].value==iso.TimePoint.FromString('1972-07-03T09:45:00+01:00'),"DateTimeOffsetProperty value on read")
			self.assertTrue(isinstance(gotEntity['DecimalProperty'].value,decimal.Decimal),"DecimalProperty type on read")
			self.assertTrue(gotEntity['DecimalProperty'].value==decimal.Decimal('3.14'),"DecimalProperty value on read")
			self.assertTrue(gotEntity['SingleValue'].value==3.14,"SingleValue on read")
			self.assertTrue(gotEntity['DoubleValue'].value==3.14,"DoubleValue on read")
			self.assertTrue(isinstance(gotEntity['GuidValue'].value,uuid.UUID),"GuidValue type on read")
			self.assertTrue(gotEntity['GuidValue'].value==uuid.UUID(int=3),"GuidValue value on read")
			self.assertTrue(gotEntity['SByteValue'].value==3,"SByteValue on read")
			self.assertTrue(gotEntity['Int16Value'].value==3,"Int16Value on read")
			self.assertTrue(gotEntity['Int64Value'].value==3,"Int64Value on read")
			self.assertTrue(gotEntity['ByteValue'].value==3,"ByteValue on read")
			self.assertTrue(gotEntity['UnicodeString'].value==u"Caf\xe9","UnicodeString on read")
			self.assertTrue(gotEntity['ASCIIString'].value==u"Cafe","ASCIIString on read")
			self.assertTrue(gotEntity['FixedString'].value==u"ALFKI","FixedString on read")
			#	UPDATE			
			gotEntity['BinaryFixed'].SetFromValue('\x00\x01\x02\x03\x04~\xDE\xAD\xBE\xEF')
			gotEntity['BinaryVariable'].SetFromValue('\x00~\xDE\xAD\xBE\xEF')
			gotEntity['BooleanProperty'].SetFromValue(False)
			gotEntity['DateTimeProperty'].SetFromValue(iso.TimePoint.FromString('2013-12-25T15:59:03.142'))
			gotEntity['TimeProperty'].SetFromValue(iso.Time.FromString('17:32:03.142'))
			gotEntity['DateTimeOffsetProperty'].SetFromValue(iso.TimePoint.FromString('2013-12-25T15:59:03.142-05:00'))
			gotEntity['DecimalProperty'].SetFromValue(decimal.Decimal('-100.50'))
			gotEntity['SingleValue'].SetFromValue(-100.5)
			gotEntity['DoubleValue'].SetFromValue(-100.5)
			gotEntity['GuidValue'].SetFromValue(uuid.UUID(int=20131225155903142))
			gotEntity['SByteValue'].SetFromValue(-101)			
			gotEntity['Int16Value'].SetFromValue(-101)
			gotEntity['Int64Value'].SetFromValue(-101)
			gotEntity['ByteValue'].SetFromValue(255)
			gotEntity['UnicodeString'].SetFromValue(u"I\u2764Unicode")
			gotEntity['ASCIIString'].SetFromValue(u"Bistro")
			gotEntity['FixedString'].SetFromValue(u"\u2780\u2781\u2782\u2783\u2784")
			collection.UpdateEntity(gotEntity)
			checkEntity=collection[1]
			self.assertTrue(checkEntity['BinaryFixed'].value=='\x00\x01\x02\x03\x04~\xDE\xAD\xBE\xEF',"BinaryFixed on read")
			self.assertTrue(checkEntity['BinaryVariable'].value=='\x00~\xDE\xAD\xBE\xEF',"BinaryVariable on read")
			self.assertTrue(checkEntity['BooleanProperty'].value==False,"BooleanProperty on read")
			self.assertTrue(isinstance(checkEntity['DateTimeProperty'].value,iso.TimePoint),"DateTimeProperty type on read")
			self.assertTrue(checkEntity['DateTimeProperty'].value==iso.TimePoint.FromString('2013-12-25T15:59:03.142'),"DateTimeProperty value on read")
			self.assertTrue(isinstance(checkEntity['TimeProperty'].value,iso.Time),"TimeProperty type on read")
			self.assertTrue(checkEntity['TimeProperty'].value.GetString(ndp=3,dp=".")=='17:32:03.142',"TimeProperty value on read")
			self.assertTrue(isinstance(checkEntity['DateTimeOffsetProperty'].value,iso.TimePoint),"DateTimeOffsetProperty type on read")
			self.assertTrue(checkEntity['DateTimeOffsetProperty'].value.GetCalendarString(ndp=3,dp=".")=='2013-12-25T15:59:03.142-05:00',"DateTimeOffsetProperty value on read")
			self.assertTrue(isinstance(checkEntity['DecimalProperty'].value,decimal.Decimal),"DecimalProperty type on read")
			self.assertTrue(checkEntity['DecimalProperty'].value==decimal.Decimal('-100.50'),"DecimalProperty value on read")
			self.assertTrue(checkEntity['SingleValue'].value==-100.5,"SingleValue on read")
			self.assertTrue(checkEntity['DoubleValue'].value==-100.5,"DoubleValue on read")
			self.assertTrue(isinstance(checkEntity['GuidValue'].value,uuid.UUID),"GuidValue type on read")
			self.assertTrue(checkEntity['GuidValue'].value==uuid.UUID(int=20131225155903142),"GuidValue value on read")
			self.assertTrue(checkEntity['SByteValue'].value==-101,"SByteValue on read")
			self.assertTrue(checkEntity['Int16Value'].value==-101,"Int16Value on read")
			self.assertTrue(checkEntity['Int64Value'].value==-101,"Int64Value on read")
			self.assertTrue(checkEntity['ByteValue'].value==255,"ByteValue on read")
			self.assertTrue(checkEntity['UnicodeString'].value==u"I\u2764Unicode","UnicodeString on read")
			self.assertTrue(checkEntity['ASCIIString'].value==u"Bistro","ASCIIString on read")
			self.assertTrue(checkEntity['FixedString'].value==u"\u2780\u2781\u2782\u2783\u2784","FixedString on read")
			#	DELETE			
			del collection[1]
			self.assertTrue(len(collection)==0,"AllTypes length after DELETE")
			try:
				gotEntity=collection[1]
				self.fail("Index into collection after AllTypes DELETE")
			except KeyError:
				pass
	
	def RunTestCaseComplexTypes(self):
		complexTypes=self.ds['RegressionModel.RegressionContainer.ComplexTypes']
		with complexTypes.OpenCollection() as collection:
			entity=collection.NewEntity()
			entity['ID'].SetFromValue(100)
			entity['Complex']['Data'].SetFromValue("Level1")
			entity['Complex']['Complex']['Data'].SetFromValue("Level2")
			entity['Complex']['Complex']['Index'].SetFromValue(255)
			#	CREATE
			collection.InsertEntity(entity)
			#	READ (collection)
			self.assertTrue(len(collection)==1,"ComplexTypes length after insert")
			gotEntity=collection.values()[0]
			self.assertTrue(gotEntity['ID'].value==100)
			#	READ (by key)
			gotEntity=collection[100]
			self.assertTrue(gotEntity['ID'].value==100,"ID on read")
			self.assertTrue(gotEntity['Complex']['Data'].value=='Level1',"Level 1 on read")
			self.assertTrue(gotEntity['Complex']['Complex']['Data'].value=='Level2',"Level 2 on read")
			self.assertTrue(gotEntity['Complex']['Complex']['Index'].value==255,"Level 2 index on read")
			#	UPDATE			
			gotEntity['Complex']['Data'].SetFromValue("Level1Update")
			gotEntity['Complex']['Complex']['Data'].SetFromValue("Level2Update")
			gotEntity['Complex']['Complex']['Index'].SetFromValue(-255)
			collection.UpdateEntity(gotEntity)
			checkEntity=collection[100]
			self.assertTrue(gotEntity['Complex']['Data'].value=='Level1Update',"Level 1 on read")
			self.assertTrue(gotEntity['Complex']['Complex']['Data'].value=='Level2Update',"Level 2 on read")
			self.assertTrue(gotEntity['Complex']['Complex']['Index'].value==-255,"Level 2 index on read")
			#	DELETE			
			del collection[100]
			self.assertTrue(len(collection)==0,"ComplexTypes length after DELETE")
			try:
				gotEntity=collection[100]
				self.fail("Index into collection after ComplexTypes DELETE")
			except KeyError:
				pass
						
	def RunTestCaseCompoundKey(self):
		compoundKeys=self.ds['RegressionModel.RegressionContainer.CompoundKeys']
		with compoundKeys.OpenCollection() as collection:
			entity=collection.NewEntity()
			entity['K1'].SetFromValue(1)
			entity['K2'].SetFromValue('00001')
			entity['K3'].SetFromValue(iso.TimePoint.FromString('2013-12-25T15:59:03.142'))
			entity['K4'].SetFromValue('\xde\xad\xbe\xef')
			entity['Data'].SetFromValue("Compound Key")
			#	CREATE
			collection.InsertEntity(entity)
			#	READ (collection)
			self.assertTrue(len(collection)==1,"CompoundKey length after insert")
			gotEntity=collection.values()[0]
			self.assertTrue(gotEntity['K1'].value==1)
			self.assertTrue(gotEntity['K2'].value=='00001')
			self.assertTrue(gotEntity['K3'].value.GetCalendarString(ndp=3,dp=".")=='2013-12-25T15:59:03.142')
			self.assertTrue(gotEntity['K4'].value=='\xde\xad\xbe\xef')
			self.assertTrue(gotEntity['Data'].value=='Compound Key')
			#	READ (by key)
			gotEntity=collection[(1,'00001',iso.TimePoint.FromString('2013-12-25T15:59:03.142'),'\xde\xad\xbe\xef')]
			self.assertTrue(gotEntity['Data'].value=="Compound Key")
			#	UPDATE			
			gotEntity['Data'].SetFromValue("Updated Compound Key")
			collection.UpdateEntity(gotEntity)
			checkEntity=collection[(1,'00001',iso.TimePoint.FromString('2013-12-25T15:59:03.142'),'\xde\xad\xbe\xef')]
			self.assertTrue(checkEntity['Data'].value=='Updated Compound Key')
			#	DELETE	
			del collection[(1,'00001',iso.TimePoint.FromString('2013-12-25T15:59:03.142'),'\xde\xad\xbe\xef')]
			self.assertTrue(len(collection)==0,"CompoundKey length after DELETE")
			try:
				gotEntity=collection[(1,'00001',iso.TimePoint.FromString('2013-12-25T15:59:03.142'),'\xde\xad\xbe\xef')]
				self.fail("Index into collection after CompoundKey DELETE")
			except KeyError:
				pass

	def RunTestCaseNavigationOne2One(self):
		ones=self.ds['RegressionModel.RegressionContainer.O2Os']
		onexs=self.ds['RegressionModel.RegressionContainer.O2OXs']
		with ones.OpenCollection() as collection,onexs.OpenCollection() as collectionX:
			entity=collection.NewEntity()
			entity['K'].SetFromValue(1)
			entity['Data'].SetFromValue('NavigationOne')
			#	CREATE
			try:
				collection.InsertEntity(entity)
				self.fail("Entity inserted without 1-1 relationship")
			except edm.ConstraintError:
				pass
			entityX=collectionX.NewEntity()
			entityX['K'].SetFromValue(100)
			entityX['Data'].SetFromValue('NavigationOneX')
			entity['OX'].BindEntity(entityX)
			try:
				collection.InsertEntity(entity)
			except edm.ConstraintError:							
				self.fail("Entity insert failed with 1-1 binding")
			# Repeat but in reverse to check symmetry				
			e2=collection.NewEntity()
			e2['K'].SetFromValue(2)
			e2['Data'].SetFromValue('NavigationTwo')
			e2X=collectionX.NewEntity()
			e2X['K'].SetFromValue(200)
			e2X['Data'].SetFromValue('NavigationTwoX')
			e2X['O'].BindEntity(e2)
			collectionX.InsertEntity(e2X)
			#	READ both ways
			entity=collection[1]
			navX=entity['OX'].GetEntity()
			self.assertTrue(navX is not None,"Failed to read back navigation link")
			self.assertTrue(navX['K']==100)
			nav=navX['O'].GetEntity()
			self.assertFalse(nav is None,"Failed to read back reverse navigation link")
			self.assertTrue(nav['K']==1)
			#	UPDATE - by adding a link, should fail.  Requires a deep delete.
			try:
				with entity['OX'].OpenCollection() as navCollection:
					navCollection[200]=e2X
				self.fail("Nav collection __setitem__ should have failed for 1-1 relationship")
			except edm.ConstraintError:
				pass
			#	UPDATE - using bind and update - also should fail for 1-1 link
			entity['OX'].BindEntity(e2X)
			try:
				entity.Update()
				self.fail("BindEntity/Update should have failed for 1-1 relationship")
			except edm.ConstraintError:
				pass
			#	DELETE - link
			with entity['OX'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[100]
					self.fail("Delete of link in a 1-1 relationship")
				except edm.ConstraintError:
					pass
			#	DELETE - entity; for a 1-1 link it should fail or cascade the delete
			try:
				del collection[1]				
				self.assertFalse(1 in collection,"Delete with a 1-1 relationship")
				self.assertFalse(100 in collectionX,"Cascade delete for 1-1 relationship")			
			except edm.ConstraintError:
				# an error is acceptable here, though we generate a warning
				logging.warning("entities with a 1-1 relationship cannot be deleted")
				self.assertTrue(1 in collection,"Delete with a 1-1 relationship")
				self.assertTrue(100 in collectionX,"Cascade delete for 1-1 relationship")			
							
	def RunTestCaseNavigationOne2One1(self):
		ones=self.ds['RegressionModel.RegressionContainer.O2O1s']
		onexs=self.ds['RegressionModel.RegressionContainer.O2OX1s']
		with ones.OpenCollection() as collection,onexs.OpenCollection() as collectionX:
			entity=collection.NewEntity()
			entity['K'].SetFromValue(1)
			entity['Data'].SetFromValue('NavigationOne')
			#	CREATE
			try:
				collection.InsertEntity(entity)
				self.fail("Entity inserted without 1-1 relationship")
			except edm.ConstraintError:
				pass
			entityX=collectionX.NewEntity()
			entityX['K'].SetFromValue(100)
			entityX['Data'].SetFromValue('NavigationOneX')
			entity['OX'].BindEntity(entityX)
			try:
				collection.InsertEntity(entity)
			except edm.ConstraintError:							
				self.fail("Entity insert failed with 1-1 binding")
			# Repeat but in reverse to check that we can't insert into a
			# dependent entity set without the principal leading
			e2=collection.NewEntity()
			e2['K'].SetFromValue(2)
			e2['Data'].SetFromValue('NavigationTwo')
			e2X=collectionX.NewEntity()
			e2X['K'].SetFromValue(200)
			e2X['Data'].SetFromValue('NavigationTwoX')
			try:
				collectionX.InsertEntity(e2X)
				self.fail("Entity insert should fail with unbound 1-1 relationship")
			except edm.ConstraintError:
				pass
			e2['OX'].BindEntity(e2X)
			collection.InsertEntity(e2)
			#	READ the link
			entity=collection[1]
			navX=entity['OX'].GetEntity()
			self.assertTrue(navX is not None,"Failed to read back navigation link")
			self.assertTrue(navX['K']==100)
			#	UPDATE - by adding a link, should fail.  Requires a deep delete.
			e2X=collectionX[200]
			try:
				with entity['OX'].OpenCollection() as navCollection:
					navCollection[200]=e2X
				self.fail("Nav collection __setitem__ should have failed for 1-1 relationship")
			except edm.ConstraintError:
				pass
			#	UPDATE - using bind and update - also should fail for 1-1 link
			entity['OX'].BindEntity(e2X)
			try:
				entity.Update()
				self.fail("BindEntity/Update should have failed for 1-1 relationship")
			except edm.ConstraintError:
				pass
			#	DELETE - link
			with entity['OX'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[100]
					self.fail("Delete of link in a 1-1 relationship")
				except edm.ConstraintError:
					pass
			#	DELETE - entity; for a 1-1 link it should fail or cascade the delete
			try:
				#	with no navigation property we mustn't cascade the delete
				#	(I'm making up my own rules here)
				del collectionX[100]
				self.fail("Deletion should fail for unbound 1-1 relationship")
			except edm.ConstraintError:
				pass
			try:
				del collection[1]				
				self.assertFalse(1 in collection,"Delete with a 1-1 relationship")
				self.assertFalse(100 in collectionX,"Cascade delete for 1-1 relationship")			
			except edm.ConstraintError:
				# an error is acceptable here, though we generate a warning
				logging.warning("entities with a 1-1 relationship cannot be deleted.")
				self.assertTrue(1 in collection,"Delete with a 1-1 relationship")
				self.assertTrue(100 in collectionX,"Cascade delete for 1-1 relationship")			

	def RunTestCaseNavigationZeroOne2One(self):
		zeroones=self.ds['RegressionModel.RegressionContainer.ZO2Os']
		ones=self.ds['RegressionModel.RegressionContainer.ZO2OXs']
		with zeroones.OpenCollection() as collectionZO,ones.OpenCollection() as collectionO:
			entityZO=collectionZO.NewEntity()
			entityZO['K'].SetFromValue(1)
			entityZO['Data'].SetFromValue('NavigationZeroOne')
			#	CREATE
			try:
				collectionZO.InsertEntity(entityZO)
				self.fail("Entity inserted without 0..1-1 relationship")
			except edm.ConstraintError:
				pass
			entityO=collectionO.NewEntity()
			entityO['K'].SetFromValue(100)
			entityO['Data'].SetFromValue('NavigationOne')
			entityZO['O'].BindEntity(entityO)
			try:
				collectionZO.InsertEntity(entityZO)
			except edm.ConstraintError:							
				self.fail("Entity insert failed with 0..1-1 binding")
			entityO=collectionO[100]
			## entityZO <-> entityO
			# Repeat but in reverse to check symmetry				
			entityZO2=collectionZO.NewEntity()
			entityZO2['K'].SetFromValue(2)
			entityZO2['Data'].SetFromValue('NavigationZeroOne_2')
			entityO2=collectionO.NewEntity()
			entityO2['K'].SetFromValue(200)
			entityO2['Data'].SetFromValue('NavigationOne_2')
			entityO2['ZO'].BindEntity(entityZO2)
			collectionO.InsertEntity(entityO2)
			## entityZO2 <-> entityO2
			#	Now try inserting at the 1 end without a binding
			entityO3=collectionO.NewEntity()
			entityO3['K'].SetFromValue(300)
			entityO3['Data'].SetFromValue('NavigationOne_3')
			try:
				collectionO.InsertEntity(entityO3)
			except edm.ConstraintError:							
				self.fail("Unbound entity insert failed at the 1 end of 0..1-1 link")			
			## None <-> entityO3
			#	READ both ways
			entityZO=collectionZO[1]
			navO=entityZO['O'].GetEntity()
			self.assertTrue(navO is not None,"Failed to read back navigation link")
			self.assertTrue(navO['K']==100)
			navZO=navO['ZO'].GetEntity()
			self.assertFalse(navZO is None,"Failed to read back reverse navigation link")
			self.assertTrue(navZO['K']==1)
			#	UPDATE - by replacing the required target of a link, should work
			try:
				with entityZO['O'].OpenCollection() as navCollection:
					navCollection.Replace(entityO3)
			except edm.ConstraintError:
				self.fail("Replace on 0..1-1 navigation property")
			## entityZO <-> entityO3
			## None <-> entityO
			navZO=entityO3['ZO'].GetEntity()
			self.assertTrue(navZO['K']==1)
			navZO=entityO['ZO'].GetEntity()
			self.assertTrue(navZO is None)
			#	now the other way around, should fail as entityZO is
			#	already bound to a different entity (and even if we
			#	allowed it, we'd have to break the link to entityZO2
			#	which is illegal without deletion).
			## entityZO2 <-> entityO2				
			## entityZO <-> entityO3
			try:
				with entityO2['ZO'].OpenCollection() as navCollection:
					navCollection[entityZO.Key()]=entityZO
				self.fail("__setitem__ on 1-0..1 navigation property should fail")
			except edm.ConstraintError:
				pass				
			#	UPDATE - using bind and update
			entityZO['O'].BindEntity(entityO)
			try:
				entityZO.Update()
			except edm.ConstraintError:
				self.fail("BindEntity/Update on 0..1-1 navigation property")
			## entityZO <-> entityO
			## entityZO2 <-> entityO2				
			## None <-> entityO3
			entityO2['ZO'].BindEntity(entityZO)
			try:
				entityO2.Update()
				self.fail("BindEntity/Update on 1-0..1 navigation property should fail")
			except edm.ConstraintError:
				pass
			#	DELETE - link
			## entityZO <-> entityO
			with entityO['ZO'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[1]
					self.fail("Delete of link in a 0..1-1 relationship from 1 end")
				except edm.ConstraintError:
					pass
			with entityZO['O'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[100]
					self.fail("Delete of link in a 0..1-1 relationship from the 0..1 end")
				except edm.ConstraintError:
					pass
			#	DELETE - entity; for a 0..1-1 link should succeed on the 0..1 end			
			## entityZO <-> entityO
			try:
				del collectionZO[1]				
				self.assertFalse(1 in collectionZO,"Delete entity at 0..1 end of relationship")
				self.assertTrue(100 in collectionO,"No cascade delete expected for 0..1-1 relationship")			
			except edm.ConstraintError:
				self.fail("Delete entity failed at 0..1 end of relationship")
			#	DELETE - entity; for a 0..1-1 link should fail or cascade the delete on the 1 end			
			## entityZO2 <-> entityO2
			try:
				del collectionO[200]
				self.assertFalse(200 in collectionO,"Delete entity at 1 end of relationship")
				self.assertFalse(2 in collectionZO,"Cascade delete required for 0..1 end of relationship")
			except edm.ConstraintError:
				# an error is acceptable here, though we generate a warning
				logging.warning("no cascade delete across 0..1-1 relationship")
				self.assertTrue(200 in collectionO)
				self.assertTrue(2 in collectionZO)

	def RunTestCaseNavigationZeroOne2OneForward(self):
		zeroones=self.ds['RegressionModel.RegressionContainer.ZO2OFs']
		ones=self.ds['RegressionModel.RegressionContainer.ZO2OXFs']
		with zeroones.OpenCollection() as collectionZO,ones.OpenCollection() as collectionO:
			#	CREATE
			entityZO=collectionZO.NewEntity()
			entityZO['K'].SetFromValue(1)
			entityZO['Data'].SetFromValue('NavigationZeroOne')
			entityO=collectionO.NewEntity()
			entityO['K'].SetFromValue(100)
			entityO['Data'].SetFromValue('NavigationOne')
			entityZO['O'].BindEntity(entityO)
			try:
				collectionZO.InsertEntity(entityZO)
			except edm.ConstraintError:							
				self.fail("Entity insert failed with 0..1-1 binding")
			## entityZO <-> entityO
			entityO2=collectionO.NewEntity()
			entityO2['K'].SetFromValue(200)
			entityO2['Data'].SetFromValue('NavigationOne_2')
			collectionO.InsertEntity(entityO2)
			## None <-> entityO2
			#	READ (forward only)
			entityZO=collectionZO[1]
			entityO=collectionO[100]
			navO=entityZO['O'].GetEntity()
			self.assertTrue(navO is not None,"Failed to read back navigation link")
			self.assertTrue(navO['K']==100)
			#	UPDATE - by replacing the required target of a link, should work
			try:
				with entityZO['O'].OpenCollection() as navCollection:
					navCollection.Replace(entityO2)
			except edm.ConstraintError:
				self.fail("Replace on 0..1-1 navigation property")
			## entityZO <-> entityO2
			## None <-> entityO
			#	UPDATE - using bind and update
			entityZO['O'].BindEntity(entityO)
			try:
				entityZO.Update()
			except edm.ConstraintError:
				self.fail("BindEntity/Update on 0..1-1 navigation property")
			## entityZO <-> entityO
			## None <-> entityO2
			#	DELETE - link
			with entityZO['O'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[100]
					self.fail("Delete of link in a 0..1-1 relationship from the 0..1 end")
				except edm.ConstraintError:
					pass
			#	DELETE - entity; for a 0..1-1 link should succeed on the 0..1 end			
			## entityZO <-> entityO
			try:
				del collectionZO[1]				
				self.assertFalse(1 in collectionZO,"Delete entity at 0..1 end of relationship")
				self.assertTrue(100 in collectionO,"No cascade delete expected for 0..1-1 relationship")			
			except edm.ConstraintError:
				self.fail("Delete entity failed at 0..1 end of relationship")
			#	DELETE - entity; for a 0..1-1 link should fail on the 1 end when there is no navigation to cascade over
			## None <-> entityO			
			## None <-> entityO2
			entityZO2=collectionZO.NewEntity()
			entityZO2['K'].SetFromValue(2)
			entityZO2['Data'].SetFromValue('NavigationZeroOne_2')
			entityZO2['O'].BindEntity(entityO2)
			collectionZO.InsertEntity(entityZO2)
			## entityZO2 <-> entityO2
			try:
				del collectionO[200]
				self.fail("(Cascade) delete not allowed over unbound navigation property")
			except edm.ConstraintError:
				self.assertTrue(200 in collectionO)
				self.assertTrue(2 in collectionZO)

	def RunTestCaseNavigationZeroOne2OneReverse(self):
		zeroones=self.ds['RegressionModel.RegressionContainer.ZO2ORs']
		ones=self.ds['RegressionModel.RegressionContainer.ZO2OXRs']
		with zeroones.OpenCollection() as collectionZO,ones.OpenCollection() as collectionO:
			entityZO=collectionZO.NewEntity()
			entityZO['K'].SetFromValue(1)
			entityZO['Data'].SetFromValue('NavigationZeroOne')
			#	CREATE
			try:
				collectionZO.InsertEntity(entityZO)
				self.fail("Entity inserted without 0..1-1 relationship (unbound navigation property)")
			except edm.ConstraintError:
				pass
			entityO=collectionO.NewEntity()
			entityO['K'].SetFromValue(100)
			entityO['Data'].SetFromValue('NavigationOne')
			entityO['ZO'].BindEntity(entityZO)
			try:
				collectionO.InsertEntity(entityO)
			except edm.ConstraintError:							
				self.fail("Entity insert failed with 0..1-1 binding")
			## entityZO <-> entityO
			#	Now try inserting at the 1 end without a binding
			entityO2=collectionO.NewEntity()
			entityO2['K'].SetFromValue(200)
			entityO2['Data'].SetFromValue('NavigationOne_2')
			try:
				collectionO.InsertEntity(entityO2)
			except edm.ConstraintError:							
				self.fail("Unbound entity insert failed at the 1 end of 0..1-1 link")			
			## None <-> entityO2
			#	READ (reverse only)
			entityO=collectionO[100]
			entityZO=collectionZO[1]
			navZO=entityO['ZO'].GetEntity()
			self.assertTrue(navZO is not None,"Failed to read back navigation link")
			self.assertTrue(navZO['K']==1)
			#	UPDATE - by inserting a new value into the navigation collection  should work
			entityZO2=collectionZO.NewEntity()
			entityZO2['K'].SetFromValue(2)
			entityZO2['Data'].SetFromValue('NavigationZeroOne')
			with entityO2['ZO'].OpenCollection() as navCollection:
				try:
					navCollection.InsertEntity(entityZO2)
				except NotImplementedError:
					# acceptable to reject this as there is no back link
					logging.warning("Insertion into O[2].ZO not supported due to absence of back-link")															
				except edm.ConstraintError:
					self.fail("Failed to insert a new entity at the 0..1 end of an empty link")
			navZO=entityO2['ZO'].GetEntity()
			if navZO is None:
				# Fix up the unimplemented insertion...
				entityO2=collectionO.CopyEntity(entityO2)
				del collectionO[200]
				entityO2.SetKey(200)
				entityO2['ZO'].BindEntity(entityZO2)
				collectionO.InsertEntity(entityO2)		
				navZO=entityO2['ZO'].GetEntity()
			self.assertTrue(navZO['K']==2)
			entityZO2=collectionZO[2]
			## entityZO <-> entityO
			## entityZO2 <-> entityO2				
			#	now try and update the link, should fail as entityZO
			#	is already bound and even if we allowed ourselves to
			#	implicitly break that link it would leave entityZO2
			#	unbound which would require an implicit delete
			try:
				with entityO2['ZO'].OpenCollection() as navCollection:
					navCollection[entityZO.Key()]=entityZO
				self.fail("__setitem__ on 1-0..1 navigation property should fail")
			except edm.ConstraintError:
				pass				
			entityO2['ZO'].BindEntity(entityZO)
			try:
				entityO2.Update()
				self.fail("BindEntity/Update on 1-0..1 navigation property should fail")
			except edm.ConstraintError:
				pass
			#	DELETE - link
			## entityZO <-> entityO
			## entityZO2 <-> entityO2			
			with entityO['ZO'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[1]
					self.fail("Delete of link in a 0..1-1 relationship from 1 end")
				except edm.ConstraintError:
					pass
			#	DELETE - entity; for a 0..1-1 link should succeed on
			#	the 0..1 end even though there is no navigation
			#	property, the link must be broken of course!		
			## entityZO <-> entityO
			try:
				del collectionZO[1]				
				self.assertFalse(1 in collectionZO,"Delete entity at 0..1 end of relationship")
				self.assertTrue(100 in collectionO,"No cascade delete expected for 0..1-1 relationship")
				self.assertTrue(entityO['ZO'].GetEntity() is None,"Link should have been broken by deletion at 0..1 end")
			except edm.ConstraintError:
				self.fail("Delete entity failed at 0..1 end of relationship")
			#	DELETE - entity; for a 0..1-1 link should fail or cascade the delete on the 1 end			
			## entityZO2 <-> entityO2
			try:
				del collectionO[200]
				self.assertFalse(200 in collectionO,"Delete entity at 1 end of relationship")
				self.assertFalse(2 in collectionZO,"Cascade delete required for 0..1 end of relationship")
			except edm.ConstraintError:
				# an error is acceptable here, though we generate a warning
				logging.warning("no cascade delete across 0..1-1 relationship")
				self.assertTrue(200 in collectionO)
				self.assertTrue(2 in collectionZO)

	def RunTestCaseNavigationMany2One(self):
		manys=self.ds['RegressionModel.RegressionContainer.Many2Os']
		ones=self.ds['RegressionModel.RegressionContainer.Many2OXs']
		with manys.OpenCollection() as collectionMany,ones.OpenCollection() as collectionO:
			entityMany=collectionMany.NewEntity()
			entityMany['K'].SetFromValue(1)
			entityMany['Data'].SetFromValue('NavigationMany')
			#	CREATE
			try:
				collectionMany.InsertEntity(entityMany)
				self.fail("Entity inserted without *-1 relationship")
			except edm.ConstraintError:
				pass
			entityO=collectionO.NewEntity()
			entityO['K'].SetFromValue(100)
			entityO['Data'].SetFromValue('NavigationOne')
			entityMany['O'].BindEntity(entityO)
			try:
				collectionMany.InsertEntity(entityMany)
			except edm.ConstraintError:							
				self.fail("Entity insert failed with *-1 binding")
			## entityMany <-> entityO
			# Repeat but in reverse to check symmetry				
			entityMany2=collectionMany.NewEntity()
			entityMany2['K'].SetFromValue(2)
			entityMany2['Data'].SetFromValue('NavigationMany_2')
			entityMany3=collectionMany.NewEntity()
			entityMany3['K'].SetFromValue(3)
			entityMany3['Data'].SetFromValue('NavigationMany_3')
			entityO2=collectionO.NewEntity()
			entityO2['K'].SetFromValue(200)
			entityO2['Data'].SetFromValue('NavigationOne_2')
			# we can create more than one link now
			entityO2['Many'].BindEntity(entityMany2)
			entityO2['Many'].BindEntity(entityMany3)
			collectionO.InsertEntity(entityO2)
			## entityMany2, entityMany3 <-> entityO2
			#	Now try inserting at the 1 end without a binding
			entityO3=collectionO.NewEntity()
			entityO3['K'].SetFromValue(300)
			entityO3['Data'].SetFromValue('NavigationOne_3')
			try:
				collectionO.InsertEntity(entityO3)
			except edm.ConstraintError:							
				self.fail("Unbound entity insert failed at the 1 end of *-1 link")			
			## [] <-> entityO3
			#	READ both ways
			entityMany=collectionMany[1]
			navO=entityMany['O'].GetEntity()
			self.assertTrue(navO is not None,"Failed to read back navigation link")
			self.assertTrue(navO['K']==100)
			try:
				navMany=navO['Many'].GetEntity()
				self.fail("GetEntity should fail on a deferred value with multiplicity *")
			except edm.NavigationError:
				pass
			with navO['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==1)
				navMany=navCollection[1]
				self.assertTrue(navMany['K']==1)
			#	READ multiple...
			entityMany2=collectionMany[2]
			navO=entityMany2['O'].GetEntity()
			self.assertTrue(navO is not None,"Failed to read back Many2")
			self.assertTrue(navO['K']==200)
			entityMany3=collectionMany[3]
			navO=entityMany3['O'].GetEntity()
			self.assertTrue(navO is not None,"Failed to read back Many3")
			self.assertTrue(navO['K']==200)
			entityO2=collectionO[200]
			with entityO2['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==2)
				self.assertFalse(1 in navCollection)
				self.assertTrue(2 in navCollection)
				self.assertTrue(3 in navCollection)
			#	READ empty link...
			with entityO3['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==0)
			#	UPDATE - by replacing the required target of a link, should work
			try:
				with entityMany['O'].OpenCollection() as navCollection:
					navCollection.Replace(entityO3)
			except edm.ConstraintError:
				self.fail("Replace on *-1 navigation property")
			## entityMany <-> entityO3
			## [] <-> entityO
			with entityO3['Many'].OpenCollection() as navCollection:
				self.assertTrue(1 in navCollection)
			entityO=collectionO[100]
			with entityO['Many'].OpenCollection() as navCollection:
				self.assertTrue(1 not in navCollection)
				self.assertTrue(len(navCollection)==0)
			#	now the other way around, should fail as entityMany is
			#	already bound to a different entity and we don't allow
			#	that link to be broken implicitly
			## [] <-> entityO
			## entityMany2, entityMany3 <-> entityO2				
			## entityMany <-> entityO3
			try:
				with entityO2['Many'].OpenCollection() as navCollection:
					navCollection[entityMany.Key()]=entityMany
				self.fail("__setitem__ on 1-* navigation property should fail")
			except edm.ConstraintError:
				pass				
			#	UPDATE - using bind and update
			entityMany['O'].BindEntity(entityO)
			try:
				entityMany.Update()
			except edm.ConstraintError:
				self.fail("BindEntity/Update on *-1 navigation property")
			## entityMany <-> entityO
			## entityMany2, entityMany3 <-> entityO2				
			## [] <-> entityO3
			entityO2['Many'].BindEntity(entityMany)
			try:
				entityO2.Update()
				self.fail("BindEntity/Update on 1-* navigation property should fail")
			except edm.ConstraintError:
				pass
			#	DELETE - link
			## entityMany <-> entityO
			with entityO['Many'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[1]
					self.fail("Delete of link in a *-1 relationship from 1 end")
				except edm.ConstraintError:
					pass
			with entityMany['O'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[100]
					self.fail("Delete of link in a *-1 relationship from the * end")
				except edm.ConstraintError:
					pass
			#	DELETE - entity; for a *-1 link should succeed on the * end			
			## entityMany <-> entityO
			try:
				del collectionMany[1]				
				self.assertFalse(1 in collectionMany,"Delete entity at * end of relationship")
				self.assertTrue(100 in collectionO,"No cascade delete expected for *-1 relationship")			
			except edm.ConstraintError:
				self.fail("Delete entity failed at * end of relationship")
			#	DELETE - entity; for a *-1 link should fail or cascade the delete on the 1 end			
			## entityMany2, entityMany3 <-> entityO2				
			try:
				del collectionO[200]
				self.assertFalse(200 in collectionO,"Delete entity at 1 end of relationship")
				self.assertFalse(2 in collectionMany,"Cascade delete required for * end of relationship")
				self.assertFalse(3 in collectionMany,"Cascade delete required for * end of relationship")
			except edm.ConstraintError:
				# an error is acceptable here, though we generate a warning
				logging.warning("no cascade delete across *-1 relationship")
				self.assertTrue(200 in collectionO)
				self.assertTrue(2 in collectionMany)
				self.assertTrue(3 in collectionMany)

	def RunTestCaseNavigationMany2OneForward(self):
		manys=self.ds['RegressionModel.RegressionContainer.Many2OFs']
		ones=self.ds['RegressionModel.RegressionContainer.Many2OXFs']
		with manys.OpenCollection() as collectionMany,ones.OpenCollection() as collectionO:
			entityMany=collectionMany.NewEntity()
			entityMany['K'].SetFromValue(1)
			entityMany['Data'].SetFromValue('NavigationMany')
			#	CREATE
			entityO=collectionO.NewEntity()
			entityO['K'].SetFromValue(100)
			entityO['Data'].SetFromValue('NavigationOne')
			entityMany['O'].BindEntity(entityO)
			try:
				collectionMany.InsertEntity(entityMany)
			except edm.ConstraintError:							
				self.fail("Entity insert failed with *-1 binding")
			## entityMany <-> entityO
			# we can create more than one link now, but must go forward
			entityO2=collectionO.NewEntity()
			entityO2['K'].SetFromValue(200)
			entityO2['Data'].SetFromValue('NavigationOne_2')
			collectionO.InsertEntity(entityO2)
			entityMany2=collectionMany.NewEntity()
			entityMany2['K'].SetFromValue(2)
			entityMany2['Data'].SetFromValue('NavigationMany_2')
			entityMany2['O'].BindEntity(entityO2)
			collectionMany.InsertEntity(entityMany2)
			entityMany3=collectionMany.NewEntity()
			entityMany3['K'].SetFromValue(3)
			entityMany3['Data'].SetFromValue('NavigationMany_3')
			entityMany3['O'].BindEntity(entityO2)
			collectionMany.InsertEntity(entityMany3)
			## entityMany2, entityMany3 <-> entityO2
			#	Now try inserting at the 1 end without a binding
			entityO3=collectionO.NewEntity()
			entityO3['K'].SetFromValue(300)
			entityO3['Data'].SetFromValue('NavigationOne_3')
			collectionO.InsertEntity(entityO3)
			## [] <-> entityO3
			#	READ (forward only)
			entityMany=collectionMany[1]
			entityO=collectionO[100]
			navO=entityMany['O'].GetEntity()
			self.assertTrue(navO is not None,"Failed to read back navigation link")
			self.assertTrue(navO['K']==100)
			#	READ multiple...
			entityMany2=collectionMany[2]
			navO=entityMany2['O'].GetEntity()
			self.assertTrue(navO is not None,"Failed to read back Many2")
			self.assertTrue(navO['K']==200)
			entityMany3=collectionMany[3]
			navO=entityMany3['O'].GetEntity()
			self.assertTrue(navO is not None,"Failed to read back Many3")
			self.assertTrue(navO['K']==200)
			#	UPDATE - by replacing the required target of a link, should work
			try:
				with entityMany2['O'].OpenCollection() as navCollection:
					navCollection.Replace(entityO3)
			except edm.ConstraintError:
				self.fail("Replace on *-1 navigation property")
			## entityMany <-> entityO
			## entityMany3 <-> entityO2
			## entityMany2 <-> entityO3
			self.assertTrue(collectionMany[2]['O'].GetEntity().Key()==300)
			#	now the other way around, should fail as entityMany is
			#	already bound to a different entity and we don't allow
			#	that link to be broken implicitly
			#	UPDATE - using bind and update
			entityMany2['O'].BindEntity(entityO)
			try:
				entityMany2.Update()
			except edm.ConstraintError:
				self.fail("BindEntity/Update on *-1 navigation property")
			## entityMany, entityMany2 <-> entityO
			## entityMany3 <-> entityO2				
			## [] <-> entityO3
			self.assertTrue(collectionMany[2]['O'].GetEntity().Key()==100)
			#	DELETE - link
			with entityMany3['O'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[200]
					self.fail("Delete of link in a *-1 relationship from the * end")
				except edm.ConstraintError:
					pass
			#	DELETE - entity; for a *-1 link should succeed on the * end			
			## entityMany, entityMany2 <-> entityO
			## entityMany3 <-> entityO2				
			## [] <-> entityO3
			try:
				del collectionMany[3]				
				self.assertFalse(3 in collectionMany,"Delete entity at * end of relationship")
				self.assertTrue(200 in collectionO,"No cascade delete expected for *-1 relationship")			
			except edm.ConstraintError:
				self.fail("Delete entity failed at * end of relationship")
			#	DELETE - entity; for a *-1 link should fail or cascade the delete on the 1 end			
			## entityMany, entityMany2 <-> entityO
			## [] <-> entityO2				
			## [] <-> entityO3
			try:
				del collectionO[100]
				# with no back link we don't allow cascade deletion
				self.fail("Cascale delete across *-1 relationship (unbound back link)")
			except edm.ConstraintError:
				self.assertTrue(100 in collectionO)
				self.assertTrue(1 in collectionMany)
				self.assertTrue(2 in collectionMany)

	def RunTestCaseNavigationMany2OneReverse(self):
		manys=self.ds['RegressionModel.RegressionContainer.Many2ORs']
		ones=self.ds['RegressionModel.RegressionContainer.Many2OXRs']
		with manys.OpenCollection() as collectionMany,ones.OpenCollection() as collectionO:
			entityMany=collectionMany.NewEntity()
			entityMany['K'].SetFromValue(1)
			entityMany['Data'].SetFromValue('NavigationMany')
			#	CREATE
			try:
				collectionMany.InsertEntity(entityMany)
				self.fail("Entity inserted without *-1 relationship (no forward link)")
			except edm.ConstraintError:
				pass
			entityO=collectionO.NewEntity()
			entityO['K'].SetFromValue(100)
			entityO['Data'].SetFromValue('NavigationOne')
			entityO['Many'].BindEntity(entityMany)
			try:
				collectionO.InsertEntity(entityO)
			except edm.ConstraintError:							
				self.fail("Entity insert failed with *-1 binding")
			## entityMany <-> entityO
			entityMany2=collectionMany.NewEntity()
			entityMany2['K'].SetFromValue(2)
			entityMany2['Data'].SetFromValue('NavigationMany_2')
			entityMany3=collectionMany.NewEntity()
			entityMany3['K'].SetFromValue(3)
			entityMany3['Data'].SetFromValue('NavigationMany_3')
			entityO2=collectionO.NewEntity()
			entityO2['K'].SetFromValue(200)
			entityO2['Data'].SetFromValue('NavigationOne_2')
			# we can create more than one link now
			entityO2['Many'].BindEntity(entityMany2)
			entityO2['Many'].BindEntity(entityMany3)
			collectionO.InsertEntity(entityO2)
			## entityMany2, entityMany3 <-> entityO2
			#	Now try inserting at the 1 end without a binding
			entityO3=collectionO.NewEntity()
			entityO3['K'].SetFromValue(300)
			entityO3['Data'].SetFromValue('NavigationOne_3')
			try:
				collectionO.InsertEntity(entityO3)
			except edm.ConstraintError:							
				self.fail("Unbound entity insert failed at the 1 end of *-1 link")			
			## [] <-> entityO3
			#	READ (reverse link only)
			entityMany=collectionMany[1]
			try:
				navMany=entityO['Many'].GetEntity()
				self.fail("GetEntity should fail on a deferred value with multiplicity *")
			except edm.NavigationError:
				pass
			with entityO['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==1)
				navMany=navCollection[1]
				self.assertTrue(navMany['K']==1)
			#	READ multiple...
			entityO2=collectionO[200]
			with entityO2['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==2)
				self.assertFalse(1 in navCollection)
				self.assertTrue(2 in navCollection)
				self.assertTrue(3 in navCollection)
			#	READ empty link...
			with entityO3['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==0)
			#	UPDATE - with entity creation
			entityMany4=collectionMany.NewEntity()
			entityMany4['K'].SetFromValue(4)
			entityMany4['Data'].SetFromValue('NavigationMany_4')
			entityO2['Many'].BindEntity(entityMany4)
			collectionO.UpdateEntity(entityO2)
			self.assertTrue(entityMany4.exists)
			with entityO2['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==3)
				self.assertTrue(4 in navCollection)
			#	UPDATE - should fail as entityMany is already bound to
			#	a different entity and we don't allow that link to be
			#	broken implicitly
			## entityMany <-> entityO
			## entityMany2, entityMany3, entityMany4 <-> entityO2
			## [] <-> entityO3
			try:
				with entityO3['Many'].OpenCollection() as navCollection:
					navCollection[entityMany.Key()]=entityMany
				self.fail("__setitem__ on 1-* navigation property should fail")
			except edm.ConstraintError:
				pass				
			#	UPDATE - using bind and update
			entityO3['Many'].BindEntity(entityMany)
			try:
				entityO3.Update()
				self.fail("BindEntity/Update on 1-* navigation property should fail")
			except edm.ConstraintError:
				pass
			#	DELETE - link; fails when link is required
			## entityMany <-> entityO
			## entityMany2, entityMany3, entityMany4 <-> entityO2
			## [] <-> entityO3
			with entityO['Many'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[1]
					self.fail("Delete of link in a *-1 relationship from 1 end")
				except edm.ConstraintError:
					pass
			#	DELETE - entity; for a *-1 link should succeed on the * end			
			## entityMany <-> entityO
			## entityMany2, entityMany3, entityMany4 <-> entityO2
			## [] <-> entityO3
			try:
				del collectionMany[1]				
				self.assertFalse(1 in collectionMany,"Delete entity at * end of relationship")
				self.assertTrue(100 in collectionO,"No cascade delete expected for *-1 relationship")			
			except edm.ConstraintError:
				self.fail("Delete entity failed at * end of relationship")
			#	DELETE - entity; for a *-1 link should fail or cascade the delete on the 1 end			
			## [] <-> entityO
			## entityMany2, entityMany3, entityMany4 <-> entityO2
			## [] <-> entityO3
			try:
				del collectionO[200]
				self.assertFalse(200 in collectionO,"Delete entity at 1 end of relationship")
				self.assertFalse(2 in collectionMany,"Cascade delete required for * end of relationship")
				self.assertFalse(3 in collectionMany,"Cascade delete required for * end of relationship")
				self.assertFalse(4 in collectionMany,"Cascade delete required for * end of relationship")
			except edm.ConstraintError:
				# an error is acceptable here, though we generate a warning
				logging.warning("no cascade delete across *-1 relationship")
				self.assertTrue(200 in collectionO)
				self.assertTrue(2 in collectionMany)
				self.assertTrue(3 in collectionMany)
				self.assertTrue(4 in collectionMany)

	def RunTestCaseNavigationMany2ZeroOne(self):
		manys=self.ds['RegressionModel.RegressionContainer.Many2ZOs']
		zeroones=self.ds['RegressionModel.RegressionContainer.Many2ZOXs']
		with manys.OpenCollection() as collectionMany,zeroones.OpenCollection() as collectionZO:
			entityMany=collectionMany.NewEntity()
			entityMany['K'].SetFromValue(1)
			entityMany['Data'].SetFromValue('NavigationMany')
			collectionMany.InsertEntity(entityMany)
			self.assertTrue(1 in collectionMany)
			## entityMany <-> None
			entityMany2=collectionMany.NewEntity()
			entityMany2['K'].SetFromValue(2)
			entityMany2['Data'].SetFromValue('NavigationMany_2')
			entityZO=collectionZO.NewEntity()
			entityZO['K'].SetFromValue(100)
			entityZO['Data'].SetFromValue('NavigationOne')
			entityMany2['ZO'].BindEntity(entityZO)
			try:
				collectionMany.InsertEntity(entityMany2)
			except edm.ConstraintError:							
				self.fail("Entity insert failed with *-1 binding")
			## entityMany <-> None
			## entityMany2 <-> entityZO
			entityMany3=collectionMany.NewEntity()
			entityMany3['K'].SetFromValue(3)
			entityMany3['Data'].SetFromValue('NavigationMany_3')
			entityMany4=collectionMany.NewEntity()
			entityMany4['K'].SetFromValue(4)
			entityMany4['Data'].SetFromValue('NavigationMany_4')
			entityZO2=collectionZO.NewEntity()
			entityZO2['K'].SetFromValue(200)
			entityZO2['Data'].SetFromValue('NavigationOne_2')
			# we can create more than one link now
			entityZO2['Many'].BindEntity(entityMany3)
			entityZO2['Many'].BindEntity(entityMany4)
			collectionZO.InsertEntity(entityZO2)
			## entityMany <-> None
			## entityMany2 <-> entityZO
			## entityMany3, entityMany4 <-> entityZO2
			#	Now try inserting at the 1 end without a binding
			entityZO3=collectionZO.NewEntity()
			entityZO3['K'].SetFromValue(300)
			entityZO3['Data'].SetFromValue('NavigationOne_3')
			try:
				collectionZO.InsertEntity(entityZO3)
			except edm.ConstraintError:							
				self.fail("Unbound entity insert failed at the 1 end of *-1 link")			
			#	READ both ways
			## entityMany <-> None
			## entityMany2 <-> entityZO
			## entityMany3, entityMany4 <-> entityZO2
			## [] <-> entityZO3
			self.assertTrue(entityMany['ZO'].GetEntity() is None)
			entityMany2=collectionMany[2]
			navZO=entityMany2['ZO'].GetEntity()
			self.assertTrue(navZO is not None,"Failed to read back navigation link")
			self.assertTrue(navZO['K']==100)
			try:
				navMany=navZO['Many'].GetEntity()
				self.fail("GetEntity should fail on a deferred value with multiplicity *")
			except edm.NavigationError:
				pass
			with navZO['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==1)
				self.assertTrue(2 in navCollection)
			#	READ multiple...
			## entityMany <-> None
			## entityMany2 <-> entityZO
			## entityMany3, entityMany4 <-> entityZO2
			## [] <-> entityZO3
			entityMany3=collectionMany[3]
			entityZO=collectionZO[100]
			navZO=entityMany3['ZO'].GetEntity()
			self.assertTrue(navZO is not None,"Failed to read back Many3")
			self.assertTrue(navZO['K']==200)
			entityMany4=collectionMany[4]
			navO=entityMany4['ZO'].GetEntity()
			self.assertTrue(navZO is not None,"Failed to read back Many4")
			self.assertTrue(navZO['K']==200)
			entityZO2=collectionZO[200]
			with entityZO2['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==2)
				self.assertFalse(1 in navCollection)
				self.assertFalse(2 in navCollection)
				self.assertTrue(3 in navCollection)
				self.assertTrue(4 in navCollection)
			#	READ empty link...
			with entityZO3['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==0)
			#	UPDATE - by replacing the target of a 0..1 link, should work
			## entityMany <-> None
			## entityMany2 <-> entityZO
			## entityMany3, entityMany4 <-> entityZO2
			## [] <-> entityZO3
			try:
				with entityMany2['ZO'].OpenCollection() as navCollection:
					navCollection.Replace(entityZO3)
			except edm.ConstraintError:
				self.fail("Replace on *-0..1 navigation property")
			## entityMany <-> None
			## [] <-> entityZO
			## entityMany3, entityMany4 <-> entityZO2
			## entityMany2 <-> entityZO3
			with entityZO3['Many'].OpenCollection() as navCollection:
				self.assertTrue(2 in navCollection)
			with entityZO['Many'].OpenCollection() as navCollection:
				self.assertTrue(2 not in navCollection)
				self.assertTrue(len(navCollection)==0)
			#	now the other way around, should fail as entityMany is
			#	already bound to a different entity and we don't allow
			#	that link to be broken implicitly
			## entityMany <-> None
			## [] <-> entityZO
			## entityMany3, entityMany4 <-> entityZO2
			## entityMany2 <-> entityZO3
			try:
				with entityZO2['Many'].OpenCollection() as navCollection:
					navCollection[entityMany2.Key()]=entityMany2
				self.fail("__setitem__ on 0..1-* navigation property should fail")
			except edm.ConstraintError:
				pass				
			#	UPDATE - using bind and update
			entityMany2['ZO'].BindEntity(entityZO)
			try:
				entityMany2.Update()
			except edm.ConstraintError:
				self.fail("BindEntity/Update on *-0..1 navigation property")
			## entityMany <-> None
			## entityMany2 <-> entityZO
			## entityMany3, entityMany4 <-> entityZO2
			## [] <-> entityZO3
			entityZO2['Many'].BindEntity(entityMany2)
			try:
				entityZO2.Update()
				self.fail("BindEntity/Update on 0..1-* navigation property should fail")
			except edm.ConstraintError:
				pass
			#	DELETE - link
			## entityMany <-> None
			## entityMany2 <-> entityZO
			## entityMany3, entityMany4 <-> entityZO2
			## [] <-> entityZO3
			with entityZO['Many'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[2]
					self.assertTrue(2 in collectionMany)
					self.assertTrue(collectionMany[2]['ZO'].GetEntity()==None)
				except edm.ConstraintError:
					self.fail("Delete of link in a *-0..1 relationship from 1 end")
			## entityMany <-> None
			## entityMany2 <-> None
			## [] <-> entityZO
			## entityMany3, entityMany4 <-> entityZO2
			## [] <-> entityZO3
			with entityMany3['ZO'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[200]
					self.assertTrue(200 in collectionZO)
				except edm.ConstraintError:
					self.fail("Delete of link in a *-0..1 relationship from the * end")
			#	DELETE - entity; for a *-0..1 link should succeed on the * end			
			## entityMany <-> None
			## entityMany2 <-> None
			## [] <-> entityZO
			## entityMany3 <-> None
			## entityMany4 <-> entityZO2
			## [] <-> entityZO3
			entityMany['ZO'].BindEntity(entityZO)
			collectionMany.UpdateEntity(entityMany)
			entityMany2['ZO'].BindEntity(entityZO)
			collectionMany.UpdateEntity(entityMany2)
			## entityMany, entityMany2 <-> entityZO
			## entityMany3 <-> None
			## entityMany4 <-> entityZO2
			## [] <-> entityZO3
			try:
				del collectionMany[4]			
				self.assertFalse(4 in collectionMany,"Delete entity at * end of relationship")
				self.assertTrue(200 in collectionZO,"No cascade delete expected for *-0..1 relationship")			
			except edm.ConstraintError:
				self.fail("Delete entity failed at * end of relationship")			
			#	DELETE - entity; for a *-0..1 link should succeed on the 0..1 end
			## entityMany, entityMany2 <-> entityZO
			## entityMany3 <-> None
			## [] <-> entityZO2
			## [] <-> entityZO3
			try:
				del collectionZO[100]
				self.assertFalse(100 in collectionZO,"Delete entity at 0..1 end of relationship")
				self.assertTrue(1 in collectionMany,"Cascade delete not allowed for * end of relationship")
				self.assertTrue(2 in collectionMany,"Cascade delete not allwoed for * end of relationship")
			except edm.ConstraintError:
				self.fail("Delete entity at the 0..1 end of the relationship")
			## entityMany <-> None
			## entityMany2 <-> None
			## entityMany3 <-> None
			## [] <-> entityZO2
			## [] <-> entityZO3			

	def RunTestCaseNavigationMany2ZeroOneForward(self):
		manys=self.ds['RegressionModel.RegressionContainer.Many2ZOFs']
		zeroones=self.ds['RegressionModel.RegressionContainer.Many2ZOXFs']
		with manys.OpenCollection() as collectionMany,zeroones.OpenCollection() as collectionZO:
			entityMany=collectionMany.NewEntity()
			entityMany['K'].SetFromValue(1)
			entityMany['Data'].SetFromValue('NavigationMany')
			collectionMany.InsertEntity(entityMany)
			self.assertTrue(1 in collectionMany)
			## entityMany <-> None
			entityMany2=collectionMany.NewEntity()
			entityMany2['K'].SetFromValue(2)
			entityMany2['Data'].SetFromValue('NavigationMany_2')
			entityZO=collectionZO.NewEntity()
			entityZO['K'].SetFromValue(100)
			entityZO['Data'].SetFromValue('NavigationOne')
			entityMany2['ZO'].BindEntity(entityZO)
			try:
				collectionMany.InsertEntity(entityMany2)
			except edm.ConstraintError:							
				self.fail("Entity insert failed with *-1 binding")
			entityZO=collectionZO[100]
			## entityMany <-> None
			## entityMany2 <-> entityZO
			#	Now try inserting at the 1 end without a binding
			entityZO2=collectionZO.NewEntity()
			entityZO2['K'].SetFromValue(200)
			entityZO2['Data'].SetFromValue('NavigationOne_2')
			try:
				collectionZO.InsertEntity(entityZO2)
			except edm.ConstraintError:							
				self.fail("Unbound entity insert failed at the 1 end of *-1 link")
			#	insert multiple...
			entityMany3=collectionMany.NewEntity()
			entityMany3['K'].SetFromValue(3)
			entityMany3['Data'].SetFromValue('NavigationMany_3')
			entityMany3['ZO'].BindEntity(entityZO)
			try:
				collectionMany.InsertEntity(entityMany3)
			except edm.ConstraintError:							
				self.fail("Entity insert failed to update * link")	
			#	READ (forward only)
			## entityMany <-> None
			## entityMany2, entityMany3 <-> entityZO
			## [] <-> entityZO2
			self.assertTrue(entityMany['ZO'].GetEntity() is None)
			entityMany2=collectionMany[2]
			navZO=entityMany2['ZO'].GetEntity()
			self.assertTrue(navZO is not None,"Failed to read back navigation link")
			self.assertTrue(navZO['K']==100)
			entityMany3=collectionMany[3]
			navZO=entityMany3['ZO'].GetEntity()
			self.assertTrue(navZO is not None,"Failed to read back Many3")
			self.assertTrue(navZO['K']==100)
			#	UPDATE - by replacing the target of a 0..1 link, should work
			## entityMany <-> None
			## entityMany2, entityMany3 <-> entityZO
			## [] <-> entityZO2
			try:
				with entityMany2['ZO'].OpenCollection() as navCollection:
					navCollection.Replace(entityZO2)
			except edm.ConstraintError:
				self.fail("Replace on *-0..1 navigation property")
			## entityMany <-> None
			## entityMany3 <-> entityZO
			## entityMany2 <-> entityZO2
			#	UPDATE - using bind and update
			entityMany2['ZO'].BindEntity(entityZO)
			try:
				entityMany2.Update()
			except edm.ConstraintError:
				self.fail("BindEntity/Update on *-0..1 navigation property")
			#	DELETE - link
			## entityMany <-> None
			## entityMany2, entityMany3 <-> entityZO
			## [] <-> entityZO2
			with entityMany3['ZO'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[100]
					self.assertTrue(100 in collectionZO)
				except edm.ConstraintError:
					self.fail("Delete of link in a *-0..1 relationship from the * end")
			#	DELETE - entity; for a *-1 link should succeed on the * end			
			## entityMany <-> None
			## entityMany2 <-> entityZO
			## [] <-> entityZO2
			## entityMany3 <-> None
			entityMany['ZO'].BindEntity(entityZO)
			collectionMany.UpdateEntity(entityMany)
			entityMany3['ZO'].BindEntity(entityZO2)
			collectionMany.UpdateEntity(entityMany3)
			## entityMany, entityMany2 <-> entityZO
			## entityMany3 <-> entityZO2
			try:
				del collectionMany[3]			
				self.assertFalse(3 in collectionMany,"Delete entity at * end of relationship")
				self.assertTrue(200 in collectionZO,"No cascade delete expected for *-0..1 relationship")			
			except edm.ConstraintError:
				self.fail("Delete entity failed at * end of relationship")			
			#	DELETE - entity; for a *-0..1 link should not cascade			
			## entityMany, entityMany2 <-> entityZO
			## None <-> entityZO2
			try:
				del collectionZO[100]
				self.assertFalse(100 in collectionZO,"Delete entity at 0..1 end of relationship")
				self.assertTrue(1 in collectionMany,"Cascade delete not allowed for * end of relationship")
				self.assertTrue(2 in collectionMany,"Cascade delete not allwoed for * end of relationship")
			except edm.ConstraintError:
				self.fail("Delete entity at the 0..1 end of the relationship")
			## entityMany <-> None
			## entityMany2 <-> None
			## None <-> entityZO2

	def RunTestCaseNavigationMany2ZeroOneReverse(self):
		manys=self.ds['RegressionModel.RegressionContainer.Many2ZORs']
		zeroones=self.ds['RegressionModel.RegressionContainer.Many2ZOXRs']
		with manys.OpenCollection() as collectionMany,zeroones.OpenCollection() as collectionZO:
			entityMany=collectionMany.NewEntity()
			entityMany['K'].SetFromValue(1)
			entityMany['Data'].SetFromValue('NavigationMany')
			collectionMany.InsertEntity(entityMany)
			self.assertTrue(1 in collectionMany)
			## entityMany <-> None
			entityZO=collectionZO.NewEntity()
			entityZO['K'].SetFromValue(100)
			entityZO['Data'].SetFromValue('NavigationOne')
			collectionZO.InsertEntity(entityZO)
			## entityMany <-> None
			## [] <-> entityZO
			entityMany2=collectionMany.NewEntity()
			entityMany2['K'].SetFromValue(2)
			entityMany2['Data'].SetFromValue('NavigationMany_2')
			entityMany3=collectionMany.NewEntity()
			entityMany3['K'].SetFromValue(3)
			entityMany3['Data'].SetFromValue('NavigationMany_3')
			entityZO2=collectionZO.NewEntity()
			entityZO2['K'].SetFromValue(200)
			entityZO2['Data'].SetFromValue('NavigationOne_2')
			# we can create more than one link now
			entityZO2['Many'].BindEntity(entityMany2)
			entityZO2['Many'].BindEntity(entityMany3)
			collectionZO.InsertEntity(entityZO2)
			entityMany2=collectionMany[2]
			entityMany3=collectionMany[3]
			## entityMany <-> None
			## [] <-> entityZO
			## entityMany2, entityMany3 <-> entityZO2
			#	READ (reverse only)
			with entityZO['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==0)
			with entityZO2['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==2)
				self.assertTrue(2 in navCollection)
				self.assertTrue(3 in navCollection)
			#	UPDATE - entityMany should work, but entityMany2 should
			#	fail as it is already bound to a different entity and
			#	we don't allow that link to be broken implicitly
			## entityMany <-> None
			## [] <-> entityZO
			## entityMany2, entityMany3 <-> entityZO2
			with entityZO['Many'].OpenCollection() as navCollection:
				try:
					navCollection[entityMany.Key()]=entityMany
					self.assertTrue(1 in navCollection)
				except edm.ConstraintError:
					self.fail("__setitem__ on 0..1-* navigation property should succeed")
				try:					
					navCollection[entityMany2.Key()]=entityMany2
					self.fail("__setitem__ on 0..1-* navigation property should fail (target already linked)")
				except edm.ConstraintError:
					pass
			#	UPDATE - using bind and update
			## entityMany <-> entityZO
			## entityMany2, entityMany3 <-> entityZO2
			entityZO['Many'].BindEntity(entityMany2)
			try:
				entityZO.Update()
				self.fail("BindEntity/Update on 0..1-* navigation property should fail")
			except edm.ConstraintError:
				pass
			#	DELETE - link
			## entityMany <-> entityZO
			## entityMany2, entityMany3 <-> entityZO2
			with entityZO['Many'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[1]
					self.assertTrue(1 in collectionMany)
				except edm.ConstraintError:
					self.fail("Delete of link in a *-0..1 relationship from 1 end")
			## entityMany <-> None
			## [] <-> entityZO
			## entityMany2, entityMany3 <-> entityZO2
			entityZO=collectionZO[100]
			entityZO['Many'].BindEntity(entityMany)
			entityZO.Update()
			#	DELETE - entity; for a *-0..1 link should succeed on the * end			
			## entityMany <-> entityZO
			## entityMany2, entityMany3 <-> entityZO2
			try:
				del collectionMany[1]			
				self.assertFalse(1 in collectionMany,"Delete entity at * end of relationship")
				self.assertTrue(100 in collectionZO,"No cascade delete expected for *-0..1 relationship")			
			except edm.ConstraintError:
				self.fail("Delete entity failed at * end of relationship")			
			#	DELETE - entity; for a *-0..1 link should succeed on the 0..1 end
			## None <-> entityZO
			## entityMany2, entityMany3 <-> entityZO2
			try:
				del collectionZO[200]
				self.assertFalse(200 in collectionZO,"Delete entity at 0..1 end of relationship")
				self.assertTrue(2 in collectionMany,"Cascade delete not allowed for * end of relationship")
				self.assertTrue(3 in collectionMany,"Cascade delete not allwoed for * end of relationship")
			except edm.ConstraintError:
				self.fail("Delete entity at the 0..1 end of the relationship")
			## None <-> entityZO
			## entityMany2 <-> None
			## entityMany3 <-> None

	def RunTestCaseNavigationMany2ZeroOneRecursive(self):
		manys2zeroones=self.ds['RegressionModel.RegressionContainer.Many2ZORvs']
		with manys2zeroones.OpenCollection() as collection:
			entity1=collection.NewEntity()
			entity1['K'].SetFromValue(1)
			entity1['Data'].SetFromValue('Navigation_1')
			collection.InsertEntity(entity1)
			self.assertTrue(1 in collection)
			## [] <-> entity1 <-> None
			entity2=collection.NewEntity()
			entity2['K'].SetFromValue(2)
			entity2['Data'].SetFromValue('Navigation_2')
			entity3=collection.NewEntity()
			entity3['K'].SetFromValue(3)
			entity3['Data'].SetFromValue('Navigation_3')
			entity2['ZO'].BindEntity(entity3)
			try:
				collection.InsertEntity(entity2)
				entity3=collection[3]
			except edm.ConstraintError:							
				self.fail("Entity insert failed with *-1 binding")
			## [] <-> entity1 <-> None
			## [] <-> entity2 <-> entity3
			entity4=collection.NewEntity()
			entity4['K'].SetFromValue(4)
			entity4['Data'].SetFromValue('Navigation_4')
			entity5=collection.NewEntity()
			entity5['K'].SetFromValue(5)
			entity5['Data'].SetFromValue('Navigation_5')
			# we can create more than one link now
			entity4['Many'].BindEntity(entity5)
			entity4['Many'].BindEntity(entity3)
			collection.InsertEntity(entity4)
			entity5=collection[5]
			## [] <-> entity1 <-> None
			## [] <-> entity2 <-> entity3 <-> entity4 <-> None
			##             [] <-> entity5 ...
			#	READ both ways
			self.assertTrue(entity1['ZO'].GetEntity() is None)
			entity2=collection[2]
			navZO=entity2['ZO'].GetEntity()
			self.assertTrue(navZO is not None,"Failed to read back navigation link")
			self.assertTrue(navZO['K']==3)
			try:
				navMany=navZO['Many'].GetEntity()
				self.fail("GetEntity should fail on a deferred value with multiplicity *")
			except edm.NavigationError:
				pass
			with navZO['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==1)
				self.assertTrue(2 in navCollection)
			#	READ multiple...
			entity3=collection[3]
			navZO=entity3['ZO'].GetEntity()
			self.assertTrue(navZO is not None,"Failed to read back Many3")
			self.assertTrue(navZO['K']==4)
			entityMany5=collection[5]
			navO=entityMany5['ZO'].GetEntity()
			self.assertTrue(navZO is not None,"Failed to read back Many5")
			self.assertTrue(navZO['K']==4)
			entity4=collection[4]
			with entity4['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==2)
				self.assertFalse(1 in navCollection)
				self.assertFalse(2 in navCollection)
				self.assertTrue(3 in navCollection)
				self.assertTrue(5 in navCollection)
			#	READ empty link...
			with entity2['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==0)
			#	UPDATE - by replacing the target of a 0..1 link, should work
			## [] <-> entity1 <-> None
			## [] <-> entity2 <-> entity3 <-> entity4 <-> None
			##             [] <-> entity5 ...
			try:
				with entity3['ZO'].OpenCollection() as navCollection:
					navCollection.Replace(entity1)
			except edm.ConstraintError:
				self.fail("Replace on *-0..1 navigation property")
			## [] <-> entity2 <-> entity3 <-> entity1 <-> None
			##             [] <-> entity5 <-> entity4 <-> None
			with entity1['Many'].OpenCollection() as navCollection:
				self.assertTrue(3 in navCollection)
			with entity4['Many'].OpenCollection() as navCollection:
				self.assertTrue(3 not in navCollection)
				self.assertTrue(len(navCollection)==1)
			#	now the other way around, should fail when entity2 is
			#	already bound to a different entity and we don't allow
			#	that link to be broken implicitly
			try:
				with entity5['Many'].OpenCollection() as navCollection:
					navCollection[entity2.Key()]=entity2
				self.fail("__setitem__ on 0..1-* navigation property should fail")
			except edm.ConstraintError:
				pass				
			#	UPDATE - using bind and update
			entity2['ZO'].BindEntity(entity4)
			try:
				entity2.Update()
			except edm.ConstraintError:
				self.fail("BindEntity/Update on *-0..1 navigation property")
			## [] <-> entity3 <-> entity1 <-> None
			## [] <-> entity5 <-> entity4 <-> None
			## [] <-> entity2 ...
			entity5['Many'].BindEntity(entity2)
			try:
				entity5.Update()
				self.fail("BindEntity/Update on 0..1-* navigation property should fail")
			except edm.ConstraintError:
				pass
			#	DELETE - link
			## [] <-> entity3 <-> entity1 <-> None
			## [] <-> entity5 <-> entity4 <-> None
			## [] <-> entity2 ...
			with entity1['Many'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[3]
					self.assertTrue(3 in collection)
					self.assertTrue(collection[3]['ZO'].GetEntity()==None)
				except edm.ConstraintError:
					self.fail("Delete of link in a *-0..1 relationship from 1 end")
			## [] <-> entity3 <-> None
			## [] <-> entity1 <-> None
			## [] <-> entity5 <-> entity4 <-> None
			## [] <-> entity2 ...
			with entity2['ZO'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[4]
					self.assertTrue(4 in collection)
				except edm.ConstraintError:
					self.fail("Delete of link in a *-0..1 relationship from the * end")
			#	DELETE - entity; for a *-0..1 link should succeed on the * end			
			## [] <-> entity3 <-> None
			## [] <-> entity1 <-> None
			## [] <-> entity5 <-> entity4 <-> None
			## [] <-> entity2 <-> None
			entity2['ZO'].BindEntity(entity4)
			entity2.Update()
			entity3['ZO'].BindEntity(entity4)
			entity3.Update()
			## [] <-> entity1 <-> None
			## [] <-> entity5 <-> entity4 <-> None
			## [] <-> entity2 ...
			## [] <-> entity3 ...
			try:
				del collection[3]			
				self.assertFalse(3 in collection,"Delete entity at * end of relationship")
				self.assertTrue(4 in collection,"No cascade delete expected for *-0..1 relationship")			
			except edm.ConstraintError:
				self.fail("Delete entity failed at * end of relationship")			
			#	DELETE - entity; for a *-0..1 link should succeed on the 0..1 end
			## [] <-> entity1 <-> None
			## [] <-> entity5 <-> entity4 <-> None
			## [] <-> entity2 ...
			try:
				del collection[4]
				self.assertFalse(4 in collection,"Delete entity at 0..1 end of relationship")
				self.assertTrue(5 in collection,"Cascade delete not allowed for * end of relationship")
				self.assertTrue(2 in collection,"Cascade delete not allwoed for * end of relationship")
			except edm.ConstraintError:
				self.fail("Delete entity at the 0..1 end of the relationship")
			## [] <-> entity1 <-> None
			## [] <-> entity5 <-> None
			## [] <-> entity2 <-> None

	def RunTestCaseNavigationMany2ZeroOneRecursiveForward(self):
		manys2zeroones=self.ds['RegressionModel.RegressionContainer.Many2ZORvFs']
		with manys2zeroones.OpenCollection() as collection:
			entity1=collection.NewEntity()
			entity1['K'].SetFromValue(1)
			entity1['Data'].SetFromValue('Navigation_1')
			collection.InsertEntity(entity1)
			self.assertTrue(1 in collection)
			## [] -> entity1 -> None
			entity2=collection.NewEntity()
			entity2['K'].SetFromValue(2)
			entity2['Data'].SetFromValue('Navigation_2')
			entity3=collection.NewEntity()
			entity3['K'].SetFromValue(3)
			entity3['Data'].SetFromValue('Navigation_3')
			entity4=collection.NewEntity()
			entity4['K'].SetFromValue(4)
			entity4['Data'].SetFromValue('Navigation_4')
			entity2['ZO'].BindEntity(entity3)
			entity3['ZO'].BindEntity(entity4)
			try:
				collection.InsertEntity(entity2)
				entity3=collection[3]
				entity4=collection[4]
			except edm.ConstraintError:							
				self.fail("Entity insert failed with deep *-1 binding")
			## [] -> entity1 -> None
			## [] -> entity2 -> entity3 -> entity4 -> None
			entity5=collection.NewEntity()
			entity5['K'].SetFromValue(5)
			entity5['Data'].SetFromValue('Navigation_5')
			entity5['ZO'].BindEntity(entity4)
			collection.InsertEntity(entity5)
			## [] -> entity1 -> None
			## [] -> entity2 -> entity3 -> entity4 -> None
			##             [] -> entity5 ...
			#	READ (forward only)
			self.assertTrue(entity1['ZO'].GetEntity() is None)
			entity2=collection[2]
			navZO=entity2['ZO'].GetEntity()
			self.assertTrue(navZO is not None,"Failed to read back navigation link")
			self.assertTrue(navZO['K']==3)
			#	READ multiple...
			entity3=collection[3]
			navZO=entity3['ZO'].GetEntity()
			self.assertTrue(navZO is not None,"Failed to read back Many3")
			self.assertTrue(navZO['K']==4)
			entityMany5=collection[5]
			navO=entityMany5['ZO'].GetEntity()
			self.assertTrue(navZO is not None,"Failed to read back Many5")
			self.assertTrue(navZO['K']==4)
			#	UPDATE - by replacing the target of a 0..1 link, should work
			## [] -> entity1 -> None
			## [] -> entity2 -> entity3 -> entity4 -> None
			##             [] -> entity5 ...
			try:
				with entity3['ZO'].OpenCollection() as navCollection:
					navCollection.Replace(entity1)
			except edm.ConstraintError:
				self.fail("Replace on *-0..1 navigation property")
			self.assertTrue(entity3['ZO'].GetEntity().Key()==1)
			## [] -> entity2 -> entity3 -> entity1 -> None
			##             [] -> entity5 -> entity4 -> None
			#	UPDATE - using bind and update
			entity2['ZO'].BindEntity(entity4)
			try:
				entity2.Update()
			except edm.ConstraintError:
				self.fail("BindEntity/Update on *-0..1 navigation property")
			## [] -> entity3 -> entity1 -> None
			## [] -> entity5 -> entity4 -> None
			## [] -> entity2 ...
			#	DELETE - link
			with entity3['ZO'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[1]
					self.assertTrue(1 in collection)
					self.assertTrue(collection[3]['ZO'].GetEntity()==None)
				except edm.ConstraintError:
					self.fail("Delete of link in a *-0..1 relationship from * end")
			## [] -> entity3 -> None
			## [] -> entity1 -> None
			## [] -> entity5 -> entity4 -> None
			## [] -> entity2 ...
			#	DELETE - entity; for a *-0..1 link should succeed on the * end			
			entity3['ZO'].BindEntity(entity4)
			entity3.Update()
			## [] -> entity1 -> None
			## [] -> entity5 -> entity4 -> None
			## [] -> entity2 ...
			## [] -> entity3 ...
			try:
				del collection[3]		
				self.assertFalse(3 in collection,"Delete entity at * end of relationship")
				self.assertTrue(4 in collection,"No cascade delete expected for *-0..1 relationship")			
			except edm.ConstraintError:
				self.fail("Delete entity failed at * end of relationship")			
			#	DELETE - entity; for a *-0..1 link should succeed on the 0..1 end
			## [] -> entity1 -> None
			## [] -> entity5 -> entity4 -> None
			## [] -> entity2 ...
			try:
				del collection[4]
				self.assertFalse(4 in collection,"Delete entity at 0..1 end of relationship")
				self.assertTrue(5 in collection,"Cascade delete not allowed for * end of relationship")
				self.assertTrue(2 in collection,"Cascade delete not allwoed for * end of relationship")
			except edm.ConstraintError:
				self.fail("Delete entity at the 0..1 end of the relationship")
			## [] -> entity1 -> None
			## [] -> entity5 -> None
			## [] -> entity2 -> None

	def RunTestCaseNavigationMany2ZeroOneRecursiveReverse(self):
		manys2zeroones=self.ds['RegressionModel.RegressionContainer.Many2ZORvRs']
		with manys2zeroones.OpenCollection() as collection:
			entity1=collection.NewEntity()
			entity1['K'].SetFromValue(1)
			entity1['Data'].SetFromValue('Navigation_1')
			collection.InsertEntity(entity1)
			self.assertTrue(1 in collection)
			## [] <- entity1 <- None
			entity2=collection.NewEntity()
			entity2['K'].SetFromValue(2)
			entity2['Data'].SetFromValue('Navigation_2')
			entity3=collection.NewEntity()
			entity3['K'].SetFromValue(3)
			entity3['Data'].SetFromValue('Navigation_3')
			entity3['Many'].BindEntity(entity2)
			try:
				collection.InsertEntity(entity3)
				entity2=collection[2]
			except edm.ConstraintError:							
				self.fail("Entity insert failed with *-1 binding")
			## [] <- entity1 <- None
			## [] <- entity2 <- entity3
			entity4=collection.NewEntity()
			entity4['K'].SetFromValue(4)
			entity4['Data'].SetFromValue('Navigation_4')
			entity5=collection.NewEntity()
			entity5['K'].SetFromValue(5)
			entity5['Data'].SetFromValue('Navigation_5')
			# we can create more than one link now
			entity4['Many'].BindEntity(entity5)
			entity4['Many'].BindEntity(entity3)
			collection.InsertEntity(entity4)
			entity5=collection[5]
			## [] <- entity1 <- None
			## [] <- entity2 <- entity3 <- entity4 <- None
			##             [] <- entity5 ...
			#	READ (reverse only)
			entity3=collection[3]
			try:
				navMany=entity3['Many'].GetEntity()
				self.fail("GetEntity should fail on a deferred value with multiplicity *")
			except edm.NavigationError:
				pass
			with entity3['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==1)
				self.assertTrue(2 in navCollection)
			#	READ multiple...
			entity4=collection[4]
			with entity4['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==2)
				self.assertFalse(1 in navCollection)
				self.assertFalse(2 in navCollection)
				self.assertTrue(3 in navCollection)
				self.assertFalse(4 in navCollection)
				self.assertTrue(5 in navCollection)
			#	READ empty link...
			with entity2['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==0)
			#	UPDATE - by replacing all the targets of a * link, should work
			## [] <- entity1 <- None
			## [] <- entity2 <- entity3 <- entity4 <- None
			##             [] <- entity5 ...
			try:
				with entity4['Many'].OpenCollection() as navCollection:
					navCollection.Replace(entity1)
			except edm.ConstraintError:
				self.fail("Replace on *-0..1 navigation property")
			## [] <- entity1 <- entity4 <- None
			## [] <- entity2 <- entity3 <- None
			##             [] <- entity5 <- None
			entity3=collection[3]
			with entity1['Many'].OpenCollection() as navCollection:
				navCollection[3]=entity3
				self.assertTrue(3 in navCollection)
			## [] <- entity2 <- entity3 <- entity1 <- entity4 <- None
			##             [] <- entity5 <- None
			with entity4['Many'].OpenCollection() as navCollection:
				self.assertTrue(3 not in navCollection)
				self.assertTrue(len(navCollection)==1)
			#	should fail when entity2 is already bound to a
			#	different entity and we don't allow that link to be
			#	broken implicitly
			try:
				with entity5['Many'].OpenCollection() as navCollection:
					navCollection[2]=entity2
				self.fail("__setitem__ on 0..1-* navigation property should fail")
			except edm.ConstraintError:
				pass				
			#	UPDATE - using bind and update
			## [] <- entity2 <- entity3 <- entity1 <- entity4 <- None
			##            [] <- entity5 <- None
			with entity3['Many'].OpenCollection() as navCollection:
				navCollection.clear()
			## [] <- entity3 <- entity1 <- entity4 <- None
			## [] <- entity5 <- None
			## [] <- entity2 <- None
			with entity4['Many'].OpenCollection() as navCollection:
				navCollection.Replace(entity5)
			entity4['Many'].BindEntity(entity2)
			try:
				entity4.Update()
			except edm.ConstraintError:
				self.fail("BindEntity/Update on *-0..1 navigation property")
			## [] <- entity3 <- entity1 <- None
			## [] <- entity5 <- entity4 <- None
			## [] <- entity2 <- ...
			entity5['Many'].BindEntity(entity2)
			try:
				entity5.Update()
				self.fail("BindEntity/Update on 0..1-* navigation property should fail")
			except edm.ConstraintError:
				pass
			#	DELETE - link
			## [] <- entity3 <- entity1 <- None
			## [] <- entity5 <- entity4 <- None
			## [] <- entity2 ...
			with entity1['Many'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[3]
					self.assertTrue(3 in collection)
				except edm.ConstraintError:
					self.fail("Delete of link in a *-0..1 relationship from 1 end")
			## [] <- entity3 <- None
			## [] <- entity1 <- None
			## [] <- entity5 <- entity4 <- None
			## [] <- entity2 ...
			entity4['Many'].BindEntity(entity3)
			entity4.Update()
			## [] <- entity1 <- None
			## [] <- entity5 <- entity4 <- None
			## [] <- entity2 ...
			## [] <- entity3 ...
			try:
				del collection[3]			
				self.assertFalse(3 in collection,"Delete entity at * end of relationship")
				self.assertTrue(4 in collection,"No cascade delete expected for *-0..1 relationship")			
			except edm.ConstraintError:
				self.fail("Delete entity failed at * end of relationship")			
			#	DELETE - entity; for a *-0..1 link should succeed on the 0..1 end
			## [] <- entity1 <- None
			## [] <- entity5 <- entity4 <- None
			## [] <- entity2 ...
			try:
				del collection[4]
				self.assertFalse(4 in collection,"Delete entity at 0..1 end of relationship")
				self.assertTrue(5 in collection,"Cascade delete not allowed for * end of relationship")
				self.assertTrue(2 in collection,"Cascade delete not allwoed for * end of relationship")
			except edm.ConstraintError:
				self.fail("Delete entity at the 0..1 end of the relationship")
			## [] <- entity1 <- None
			## [] <- entity5 <- None
			## [] <- entity2 <- None

	def RunTestCaseNavigationMany2Many(self):
		manys=self.ds['RegressionModel.RegressionContainer.Many2Manys']
		manyXs=self.ds['RegressionModel.RegressionContainer.Many2ManyXs']
		with manys.OpenCollection() as collectionMany,manyXs.OpenCollection() as collectionManyX:
			entityMany=collectionMany.NewEntity()
			entityMany['K'].SetFromValue(1)
			entityMany['Data'].SetFromValue('NavigationMany_1')
			collectionMany.InsertEntity(entityMany)
			self.assertTrue(1 in collectionMany)
			## entityMany <-> []
			entityMany2=collectionMany.NewEntity()
			entityMany2['K'].SetFromValue(2)
			entityMany2['Data'].SetFromValue('NavigationMany_2')
			entityManyX=collectionManyX.NewEntity()
			entityManyX['K'].SetFromValue(100)
			entityManyX['Data'].SetFromValue('NavigationOne')
			entityMany2['ManyX'].BindEntity(entityManyX)
			try:
				collectionMany.InsertEntity(entityMany2)
				entityManyX=collectionManyX[100]
			except edm.ConstraintError:							
				self.fail("Entity insert failed with *-1 binding")
			## entityMany <-> []
			## entityMany2 <-> entityManyX
			entityMany3=collectionMany.NewEntity()
			entityMany3['K'].SetFromValue(3)
			entityMany3['Data'].SetFromValue('NavigationMany_3')
			entityMany4=collectionMany.NewEntity()
			entityMany4['K'].SetFromValue(4)
			entityMany4['Data'].SetFromValue('NavigationMany_4')
			entityManyX2=collectionManyX.NewEntity()
			entityManyX2['K'].SetFromValue(200)
			entityManyX2['Data'].SetFromValue('NavigationOne_2')
			# we can create more than one link now
			entityManyX2['Many'].BindEntity(entityMany3)
			entityManyX2['Many'].BindEntity(entityMany4)
			collectionManyX.InsertEntity(entityManyX2)
			entityMany3=collectionMany[3]
			## entityMany <-> []
			## entityMany2 <-> entityManyX
			## entityMany3, entityMany4 <-> entityManyX2
			#	Now try inserting with a binding to an existing entity
			entityManyX3=collectionManyX.NewEntity()
			entityManyX3['K'].SetFromValue(300)
			entityManyX3['Data'].SetFromValue('NavigationOne_3')
			entityManyX3['Many'].BindEntity(entityMany2)
			try:
				collectionManyX.InsertEntity(entityManyX3)
			except edm.ConstraintError:							
				self.fail("Unbound entity insert failed with existing entity")			
			## entityMany <-> []
			## entityMany2 <-> entityManyX, entityManyX3
			## entityMany3, entityMany4 <-> entityManyX2
			#	READ both ways
			try:
				entityMany['ManyX'].GetEntity()
				self.fail("GetEntity should fail on a deferred value with multiplicity *")
			except edm.NavigationError:
				pass
			entityMany2=collectionMany[2]
			with entityMany2['ManyX'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==2)
				self.assertTrue(100 in navCollection)
				self.assertFalse(200 in navCollection)
				self.assertTrue(300 in navCollection)
			with entityManyX['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==1)
				self.assertFalse(1 in navCollection)
				self.assertTrue(2 in navCollection)
				self.assertFalse(3 in navCollection)
				self.assertFalse(4 in navCollection)
			#	READ empty link...
			with entityMany['ManyX'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==0)
			#	UPDATE - by replace
			## entityMany <-> []
			## entityMany2 <-> entityManyX, entityManyX3
			## entityMany3, entityMany4 <-> entityManyX2
			try:
				with entityMany2['ManyX'].OpenCollection() as navCollection:
					navCollection.Replace(entityManyX2)
			except edm.ConstraintError:
				self.fail("Replace on *-* navigation property")
			## entityMany <-> []
			## [] <-> entityManyX
			## entityMany2, entityMany3, entityMany4 <-> entityManyX2
			## [] <-> entityManyX3
			with entityManyX['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==0)
			with entityManyX2['Many'].OpenCollection() as navCollection:
				self.assertTrue(1 not in navCollection)
				self.assertTrue(2 in navCollection)
				self.assertTrue(3 in navCollection)
				self.assertTrue(4 in navCollection)
				self.assertTrue(len(navCollection)==3)
			with entityManyX3['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==0)
			#	UPDATE - __setitem__
			## entityMany <-> []
			## [] <-> entityManyX
			## entityMany2, entityMany3, entityMany4 <-> entityManyX2
			## [] <-> entityManyX3
			try:
				with entityMany['ManyX'].OpenCollection() as navCollection:
					navCollection[entityManyX2.Key()]=entityManyX2
					navCollection[entityManyX.Key()]=entityManyX
					self.assertTrue(len(navCollection)==2)
			except edm.ConstraintError:
				self.fail("__setitem__ on *-* navigation property")
			with entityManyX2['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==4)
				self.assertTrue(1 in navCollection)
			## entityMany <-> entityManyX,...
			## entityMany, entityMany2, entityMany3, entityMany4 <-> entityManyX2
			## [] <-> entityManyX3
			#	UPDATE - using bind and update
			entityMany['ManyX'].BindEntity(entityManyX3)
			try:
				entityMany.Update()
			except edm.ConstraintError:
				self.fail("BindEntity/Update on *-* navigation property")
			## entityMany <-> entityManyX, entityManyX2, entityManyX3
			## entityMany, entityMany2, entityMany3, entityMany4 <-> entityManyX2
			entityManyX3['Many'].BindEntity(entityMany3)
			try:
				entityManyX3.Update()
			except edm.ConstraintError:
				self.fail("BindEntity/Update on *-* navigation property")
			## entityMany  -> entityManyX, entityManyX2, entityManyX3
			## entityMany, entityMany2, entityMany3, entityMany4 <-  entityManyX2
			## entityMany, entityMany3 <-  entityManyX3
			with entityManyX3['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==2)
			#	DELETE - link
			with entityManyX['Many'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[1]
					self.assertTrue(len(navCollection)==0)
					self.assertTrue(1 in collectionMany)
				except edm.ConstraintError:
					self.fail("Delete of link in a *-* relationship")
			## [] <- entityManyX
			## entityMany  -> entityManyX2, entityManyX3
			## entityMany, entityMany2, entityMany3, entityMany4 <-  entityManyX2
			## entityMany, entityMany3 <-  entityManyX3
			with entityMany['ManyX'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==2)
					del navCollection[300]
					self.assertTrue(len(navCollection)==1)
					self.assertTrue(300 in collectionManyX)
				except edm.ConstraintError:
					self.fail("Delete of link in a *-* relationship")
			## [] <- entityManyX
			## entityMany, entityMany2, entityMany3, entityMany4 <-  entityManyX2
			## entityMany3 <-  entityManyX3
			#	DELETE - entity
			try:
				del collectionMany[4]			
				self.assertFalse(4 in collectionMany,"Delete entity in *-* relationship")
				self.assertTrue(200 in collectionManyX,"No cascade delete expected for *-* relationship")			
			except edm.ConstraintError:
				self.fail("Delete entity failed for *-* relationship")			
			#	DELETE - entity with multiple links
			## [] <- entityManyX
			## entityMany, entityMany2, entityMany3 <-  entityManyX2
			## entityMany3 <-  entityManyX3
			try:
				del collectionManyX[200]
				self.assertFalse(200 in collectionManyX,"Delete entity in *-* relationship")
				self.assertTrue(1 in collectionMany,"Cascade delete not allowed for * end of relationship")
				self.assertTrue(2 in collectionMany,"Cascade delete not allwoed for * end of relationship")
				self.assertTrue(3 in collectionMany,"Cascade delete not allwoed for * end of relationship")
			except edm.ConstraintError:
				self.fail("Delete entity for *-* relationship")
			## [] <- entityManyX
			## entityMany -> []
			## entityMany2 -> []
			## entityMany3 <-> entityManyX3

	def RunTestCaseNavigationMany2Many1(self):
		manys=self.ds['RegressionModel.RegressionContainer.Many2Many1s']
		manyXs=self.ds['RegressionModel.RegressionContainer.Many2ManyX1s']
		with manys.OpenCollection() as collectionMany,manyXs.OpenCollection() as collectionManyX:
			entityMany=collectionMany.NewEntity()
			entityMany['K'].SetFromValue(1)
			entityMany['Data'].SetFromValue('NavigationMany_1')
			collectionMany.InsertEntity(entityMany)
			self.assertTrue(1 in collectionMany)
			## entityMany <-> []
			entityMany2=collectionMany.NewEntity()
			entityMany2['K'].SetFromValue(2)
			entityMany2['Data'].SetFromValue('NavigationMany_2')
			entityManyX=collectionManyX.NewEntity()
			entityManyX['K'].SetFromValue(100)
			entityManyX['Data'].SetFromValue('NavigationOne')
			entityMany2['ManyX'].BindEntity(entityManyX)
			try:
				collectionMany.InsertEntity(entityMany2)
				entityManyX=collectionManyX[100]
			except edm.ConstraintError:							
				self.fail("Entity insert failed with *-1 binding")
			## entityMany <-> []
			## entityMany2 <-> entityManyX
			entityMany3=collectionMany.NewEntity()
			entityMany3['K'].SetFromValue(3)
			entityMany3['Data'].SetFromValue('NavigationMany_3')
			entityManyX2=collectionManyX.NewEntity()
			entityManyX2['K'].SetFromValue(200)
			entityManyX2['Data'].SetFromValue('NavigationOne_2')
			entityManyX3=collectionManyX.NewEntity()
			entityManyX3['K'].SetFromValue(300)
			entityManyX3['Data'].SetFromValue('NavigationOne_3')
			# we can create more than one link now
			entityMany3['ManyX'].BindEntity(entityManyX2)
			entityMany3['ManyX'].BindEntity(entityManyX3)
			collectionMany.InsertEntity(entityMany3)
			entityManyX2=collectionManyX[200]
			entityManyX3=collectionManyX[300]
			## entityMany  -> []
			## entityMany2  -> entityManyX
			## entityMany3  -> entityManyX2, entityManyX3
			#	Now try inserting with a binding to an existing entity
			entityMany4=collectionMany.NewEntity()
			entityMany4['K'].SetFromValue(4)
			entityMany4['Data'].SetFromValue('NavigationMany_4')
			entityMany4['ManyX'].BindEntity(entityManyX2)
			try:
				collectionMany.InsertEntity(entityMany4)
			except edm.ConstraintError:							
				self.fail("Unbound entity insert failed with existing entity")			
			## entityMany  -> []
			## entityMany2  -> entityManyX
			## entityMany3  -> entityManyX2, entityManyX3
			## entityMany4  -> entityManyX2
			#	READ (one way only)
			try:
				entityMany['ManyX'].GetEntity()
				self.fail("GetEntity should fail on a deferred value with multiplicity *")
			except edm.NavigationError:
				pass
			entityMany3=collectionMany[3]
			with entityMany3['ManyX'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==2)
				self.assertTrue(100 not in navCollection)
				self.assertTrue(200 in navCollection)
				self.assertTrue(300 in navCollection)
			#	READ empty link...
			with entityMany['ManyX'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==0)
			#	UPDATE - by replace
			## entityMany  -> []
			## entityMany2  -> entityManyX
			## entityMany3  -> entityManyX2, entityManyX3
			## entityMany4  -> entityManyX2
			try:
				with entityMany2['ManyX'].OpenCollection() as navCollection:
					navCollection.Replace(entityManyX2)
			except edm.ConstraintError:
				self.fail("Replace on *-* navigation property")
			## entityMany  -> []
			## entityMany2  -> entityManyX2
			## entityMany3  -> entityManyX2, entityManyX3
			## entityMany4  -> entityManyX2
			for e in (entityMany2,entityMany3,entityMany4):
				with e['ManyX'].OpenCollection() as navCollection:
					self.assertTrue(200 in navCollection)
					self.assertFalse(100 in navCollection)
			#	UPDATE - __setitem__
			try:
				with entityMany['ManyX'].OpenCollection() as navCollection:
					navCollection[entityManyX2.Key()]=entityManyX2
					navCollection[entityManyX.Key()]=entityManyX
					self.assertTrue(len(navCollection)==2)
			except edm.ConstraintError:
				self.fail("__setitem__ on *-* navigation property")
			## entityMany  -> entityManyX, entityManyX2
			## entityMany2  -> entityManyX2
			## entityMany3  -> entityManyX2, entityManyX3
			## entityMany4  -> entityManyX2
			#	UPDATE - using bind and update
			entityMany['ManyX'].BindEntity(entityManyX3)
			try:
				entityMany.Update()
			except edm.ConstraintError:
				self.fail("BindEntity/Update on *-* navigation property")
			## entityMany  -> entityManyX, entityManyX2, entityManyX3
			## entityMany2  -> entityManyX2
			## entityMany3  -> entityManyX2, entityManyX3
			## entityMany4  -> entityManyX2
			with entityMany['ManyX'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==3)
			#	DELETE - link
			with entityMany['ManyX'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==3)
				try:
					del navCollection[100]
					self.assertTrue(len(navCollection)==2)
					self.assertTrue(100 in collectionManyX)
				except edm.ConstraintError:
					self.fail("Delete of link in a *-* relationship")
			## entityMany  -> entityManyX2, entityManyX3
			## entityMany2  -> entityManyX2
			## entityMany3  -> entityManyX2, entityManyX3
			## entityMany4  -> entityManyX2
			#	DELETE - entity
			try:
				del collectionMany[4]			
				self.assertFalse(4 in collectionMany,"Delete entity in *-* relationship")
				self.assertTrue(200 in collectionManyX,"No cascade delete expected for *-* relationship")			
			except edm.ConstraintError:
				self.fail("Delete entity failed for *-* relationship")
			#	DELETE - entity from unbound end (links just get dropped)
			try:
				del collectionManyX[200]
				self.assertFalse(200 in collectionManyX,"Delete entity in *-* relationship")
				self.assertTrue(1 in collectionMany,"No cascade delete expected for *-* relationship")			
				self.assertTrue(2 in collectionMany,"No cascade delete expected for *-* relationship")			
				self.assertTrue(3 in collectionMany,"No cascade delete expected for *-* relationship")
			except edm.ConstraintError:
				self.fail("Delete entity failed for unbound *-* relationship")
			## entityMany  -> entityManyX3
			## entityMany2  -> []
			## entityMany3  -> entityManyX3
			with entityMany['ManyX'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==1)
				navCollection[100]=entityManyX
			#	DELETE - entity with multiple links
			## entityMany  -> entityManyX, entityManyX3
			## entityMany2  -> []
			## entityMany3  -> entityManyX3
			try:
				del collectionMany[1]
				self.assertFalse(1 in collectionMany,"Delete entity in *-* relationship")
				self.assertTrue(100 in collectionManyX,"Cascade delete not allowed for * end of relationship")
				self.assertTrue(300 in collectionManyX,"Cascade delete not allwoed for * end of relationship")
			except edm.ConstraintError:
				self.fail("Delete entity for *-* relationship")
			## entityMany2  -> []
			## entityMany3  -> entityManyX3

	def RunTestCaseNavigationMany2ManyRecursive(self):
		manys2manys=self.ds['RegressionModel.RegressionContainer.Many2ManyRvs']
		with manys2manys.OpenCollection() as collection:
			entity1=collection.NewEntity()
			entity1['K'].SetFromValue(1)
			entity1['Data'].SetFromValue('Navigation_1')
			collection.InsertEntity(entity1)
			self.assertTrue(1 in collection)
			## [] <- entity1 -> []
			entity2=collection.NewEntity()
			entity2['K'].SetFromValue(2)
			entity2['Data'].SetFromValue('Navigation_2')
			entity3=collection.NewEntity()
			entity3['K'].SetFromValue(3)
			entity3['Data'].SetFromValue('Navigation_3')
			entity2['ManyX'].BindEntity(entity3)
			try:
				collection.InsertEntity(entity2)
				entity3=collection[3]
			except edm.ConstraintError:							
				self.fail("Entity insert failed with *-* binding")
			## [] <- entity1 -> []
			## [] <- entity2 -> entity3
			## entity2 <- entity3 -> []			
			entity4=collection.NewEntity()
			entity4['K'].SetFromValue(4)
			entity4['Data'].SetFromValue('Navigation_4')
			entity5=collection.NewEntity()
			entity5['K'].SetFromValue(5)
			entity5['Data'].SetFromValue('Navigation_5')
			# we can create more than one link now
			entity4['Many'].BindEntity(entity5)
			entity4['Many'].BindEntity(entity3)
			collection.InsertEntity(entity4)
			## [] <- entity1 -> []
			## [] <- entity2 -> entity3
			## entity2 <- entity3 -> entity4			
			## entity3, entity5 <- entity4 -> []			
			## [] <- entity5 -> entity4
			entity6=collection.NewEntity()
			entity6['K'].SetFromValue(6)
			entity6['Data'].SetFromValue('Navigation_6')
			entity6['Many'].BindEntity(entity3)
			collection.InsertEntity(entity6)			
			## [] <- entity1 -> []
			## [] <- entity2 -> entity3
			## entity2 <- entity3 -> entity4, entity6			
			## entity3, entity5 <- entity4 -> []			
			## [] <- entity5 -> entity4
			## entity3 <- entity6 -> []
			#	READ both ways
			try:
				navManyX=entity1['ManyX'].GetEntity()
				self.fail("GetEntity should fail on a deferred value with multiplicity *")
			except edm.NavigationError:
				pass
			with entity1['ManyX'].OpenCollection() as navManyX:
				self.assertTrue(len(navManyX)==0)
			entity2=collection[2]
			with entity2['ManyX'].OpenCollection() as navManyX:
				self.assertTrue(len(navManyX)==1)
				self.assertTrue(3 in navManyX)
			entity3=collection[3]
			try:
				navMany=entity3['Many'].GetEntity()
				self.fail("GetEntity should fail on a deferred value with multiplicity *")
			except edm.NavigationError:
				pass
			with entity3['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==1)
				self.assertTrue(2 in navCollection)
			#	READ multiple...
			with entity3['ManyX'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==2)
				self.assertTrue(4 in navCollection)
				self.assertTrue(6 in navCollection)
			entity5=collection[5]
			with entity5['ManyX'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==1)
				self.assertTrue(4 in navCollection)
			entity4=collection[4]
			with entity4['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==2)
				self.assertFalse(1 in navCollection)
				self.assertFalse(2 in navCollection)
				self.assertTrue(3 in navCollection)
				self.assertTrue(5 in navCollection)
			#	READ empty return link...
			with entity2['Many'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==0)
			#	UPDATE - by replacing the target of a * link, should work
			## [] <- entity1 -> []
			## [] <- entity2 -> entity3
			## entity2 <- entity3 -> entity4, entity6			
			## entity3, entity5 <- entity4 -> []			
			## [] <- entity5 -> entity4
			## entity3 <- entity6 -> []
			try:
				with entity3['ManyX'].OpenCollection() as navCollection:
					navCollection.Replace(entity1)
			except edm.ConstraintError:
				self.fail("Replace on *-* navigation property")
			## entity3 <- entity1 -> []
			## [] <- entity2 -> entity3
			## entity2 <- entity3 -> entity1			
			## entity5 <- entity4 -> []			
			## [] <- entity5 -> entity4
			## [] <- entity6 -> []
			with entity1['Many'].OpenCollection() as navCollection:
				self.assertTrue(3 in navCollection)
			with entity4['Many'].OpenCollection() as navCollection:
				self.assertTrue(3 not in navCollection)
				self.assertTrue(len(navCollection)==1)
			#	now the other way around...
			try:
				with entity5['Many'].OpenCollection() as navCollection:
					navCollection[entity2.Key()]=entity2
			except edm.ConstraintError:
				self.fail("__setitem__ on *-* navigation property should pass")
			## entity3 <- entity1 -> []
			## [] <- entity2 -> entity3, entity5
			## entity2 <- entity3 -> entity1			
			## entity5 <- entity4 -> []			
			## entity2 <- entity5 -> entity4
			## [] <- entity6 -> []
			#	UPDATE - using bind and update
			entity2['ManyX'].BindEntity(entity4)
			try:
				entity2.Update()
			except edm.ConstraintError:
				self.fail("BindEntity/Update on *-* navigation property")
			## entity3 <- entity1 -> []
			## [] <- entity2 -> entity3, entity4, entity5
			## entity2 <- entity3 -> entity1			
			## entity2, entity5 <- entity4 -> []			
			## entity2 <- entity5 -> entity4
			## [] <- entity6 -> []
			entity5['Many'].BindEntity(entity1)
			try:
				entity5.Update()
			except edm.ConstraintError:
				self.fail("BindEntity/Update on *-* navigation property should pass")
			## entity3 <- entity1 -> entity5
			## [] <- entity2 -> entity3, entity4, entity5
			## entity2 <- entity3 -> entity1			
			## entity2, entity5 <- entity4 -> []			
			## entity1, entity2 <- entity5 -> entity4
			## [] <- entity6 -> []
			#	DELETE - link
			with entity1['Many'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[3]
					self.assertTrue(3 in collection)
				except edm.ConstraintError:
					self.fail("Delete of link in a *-* relationship")
			## [] <- entity1 -> entity5
			## [] <- entity2 -> entity3, entity4, entity5
			## entity2 <- entity3 -> []			
			## entity2, entity5 <- entity4 -> []			
			## entity1, entity2 <- entity5 -> entity4
			## [] <- entity6 -> []
			with entity3['ManyX'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==0)
			with entity2['ManyX'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==3)
					del navCollection[4]
					self.assertTrue(4 in collection)
				except edm.ConstraintError:
					self.fail("Delete of link in a *-* relationship")
			#	DELETE - entity; for a *-* link should succeed		
			## [] <- entity1 -> entity5
			## [] <- entity2 -> entity3, entity5
			## entity2 <- entity3 -> []			
			## entity5 <- entity4 -> []			
			## entity1, entity2 <- entity5 -> entity4
			## [] <- entity6 -> []
			try:
				del collection[3]			
				self.assertFalse(3 in collection,"Delete entity in * relationship")
				self.assertTrue(4 in collection,"No cascade delete expected for *-* relationship")			
			except edm.ConstraintError:
				self.fail("Delete entity failed in * relationship")
			## [] <- entity1 -> entity5
			## [] <- entity2 -> entity5
			## entity5 <- entity4 -> []			
			## entity1, entity2 <- entity5 -> entity4
			## [] <- entity6 -> []
			#	DELETE - entity; for a *-* link should succeed
			try:
				del collection[5]
				self.assertFalse(5 in collection,"Delete entity in * relationship")
				self.assertTrue(4 in collection,"Cascade delete not allowed in * end of relationship")
				self.assertTrue(2 in collection,"Cascade delete not allowed in * end of relationship")
				self.assertTrue(1 in collection,"Cascade delete not allwoed in * end of relationship")
			except edm.ConstraintError:
				self.fail("Delete entity in * relationship")
			## [] <- entity1 -> []
			## [] <- entity2 -> []
			## [] <- entity4 -> []			
			## [] <- entity6 -> []

	def RunTestCaseNavigationMany2ManyRecursive1(self):
		manys2manys=self.ds['RegressionModel.RegressionContainer.Many2ManyRv1s']
		with manys2manys.OpenCollection() as collection:
			entity1=collection.NewEntity()
			entity1['K'].SetFromValue(1)
			entity1['Data'].SetFromValue('Navigation_1')
			collection.InsertEntity(entity1)
			self.assertTrue(1 in collection)
			## [] <- entity1 -> []
			entity2=collection.NewEntity()
			entity2['K'].SetFromValue(2)
			entity2['Data'].SetFromValue('Navigation_2')
			entity3=collection.NewEntity()
			entity3['K'].SetFromValue(3)
			entity3['Data'].SetFromValue('Navigation_3')
			entity2['ManyX'].BindEntity(entity3)
			try:
				collection.InsertEntity(entity2)
			except edm.ConstraintError:							
				self.fail("Entity insert failed with *-* binding")
			## [] <- entity1 -> []
			## [] <- entity2 -> entity3
			## entity2 <- entity3 -> []			
			entity4=collection.NewEntity()
			entity4['K'].SetFromValue(4)
			entity4['Data'].SetFromValue('Navigation_4')
			entity5=collection.NewEntity()
			entity5['K'].SetFromValue(5)
			entity5['Data'].SetFromValue('Navigation_5')
			# we can create more than one link now
			entity4['ManyX'].BindEntity(entity5)
			entity4['ManyX'].BindEntity(entity3)
			collection.InsertEntity(entity4)
			## [] <- entity1 -> []
			## [] <- entity2 -> entity3
			## entity2, entity4 <- entity3 -> []			
			## [] <- entity4 -> entity3, entity5			
			## entity4 <- entity5 -> []			
			#	READ (one way only)
			try:
				navManyX=entity1['ManyX'].GetEntity()
				self.fail("GetEntity should fail on a deferred value with multiplicity *")
			except edm.NavigationError:
				pass
			with entity1['ManyX'].OpenCollection() as navManyX:
				self.assertTrue(len(navManyX)==0)
			entity2=collection[2]
			with entity2['ManyX'].OpenCollection() as navManyX:
				self.assertTrue(len(navManyX)==1)
				self.assertTrue(3 in navManyX)
			#	READ multiple...
			with entity4['ManyX'].OpenCollection() as navCollection:
				self.assertTrue(len(navCollection)==2)
				self.assertFalse(1 in navCollection)
				self.assertFalse(2 in navCollection)
				self.assertTrue(3 in navCollection)
				self.assertTrue(5 in navCollection)
			#	UPDATE - by replacing the target of a * link, should work
			## [] <- entity1 -> []
			## [] <- entity2 -> entity3
			## entity2, entity4 <- entity3 -> []			
			## [] <- entity4 -> entity3, entity5			
			## entity4 <- entity5 -> []			
			try:
				with entity4['ManyX'].OpenCollection() as navCollection:
					navCollection.Replace(entity1)
			except edm.ConstraintError:
				self.fail("Replace on *-* navigation property")
			try:
				with entity5['ManyX'].OpenCollection() as navCollection:
					navCollection[entity2.Key()]=entity2
			except edm.ConstraintError:
				self.fail("__setitem__ on *-* navigation property should pass")
			## entity4 <- entity1 -> []
			## entity5 <- entity2 -> entity3
			## entity2 <- entity3 -> []			
			## [] <- entity4 -> entity1			
			## [] <- entity5 -> entity2
			#	UPDATE - using bind and update
			entity4['ManyX'].BindEntity(entity2)
			try:
				entity4.Update()
			except edm.ConstraintError:
				self.fail("BindEntity/Update on *-* navigation property")
			## entity4 <- entity1 -> []
			## entity4, entity5 <- entity2 -> entity3
			## entity2 <- entity3 -> []			
			## [] <- entity4 -> entity1, entity2
			## [] <- entity5 -> entity2
			#	DELETE - link
			with entity5['ManyX'].OpenCollection() as navCollection:
				try:
					self.assertTrue(len(navCollection)==1)
					del navCollection[2]
					self.assertTrue(2 in collection)
				except edm.ConstraintError:
					self.fail("Delete of link in a *-* relationship")
			## entity4 <- entity1 -> []
			## entity4 <- entity2 -> entity3
			## entity2 <- entity3 -> []			
			## [] <- entity4 -> entity1, entity2
			## [] <- entity5 -> []
			#	DELETE - entity; for a *-* link should succeed 
			try:
				del collection[3]			
				self.assertFalse(3 in collection,"Delete entity in * relationship")
				self.assertTrue(2 in collection,"No cascade delete expected for *-* relationship")			
			except edm.ConstraintError:
				self.fail("Delete entity failed in * relationship")
			## entity4 <- entity1 -> []
			## entity4 <- entity2 -> []
			## [] <- entity4 -> entity1, entity2
			## [] <- entity5 -> []
			#	DELETE - entity; for a *-* link should succeed
			try:
				del collection[4]
				self.assertFalse(4 in collection,"Delete entity in * relationship")
				self.assertTrue(2 in collection,"Cascade delete not allowed in * end of relationship")
				self.assertTrue(1 in collection,"Cascade delete not allwoed in * end of relationship")
			except edm.ConstraintError:
				self.fail("Delete entity in * relationship")
			## [] <- entity1 -> []
			## [] <- entity2 -> []
			## [] <- entity5 -> []

	def RunAllCombined(self):
		"""Runs all the individual tests combined into one (useful for expensive setUp/tearDown"""
		self.RunTestCaseAllTypes()
		self.RunTestCaseComplexTypes()
		self.RunTestCaseCompoundKey()
		self.RunTestCaseNavigationOne2One()
		self.RunTestCaseNavigationOne2One1()
		self.RunTestCaseNavigationZeroOne2One()
		self.RunTestCaseNavigationZeroOne2OneForward()
		self.RunTestCaseNavigationZeroOne2OneReverse()
		self.RunTestCaseNavigationMany2One()
		self.RunTestCaseNavigationMany2OneForward()
		self.RunTestCaseNavigationMany2OneReverse()
		self.RunTestCaseNavigationMany2ZeroOne()
		self.RunTestCaseNavigationMany2ZeroOneForward()
		self.RunTestCaseNavigationMany2ZeroOneReverse()
		self.RunTestCaseNavigationMany2ZeroOneRecursive()
		self.RunTestCaseNavigationMany2ZeroOneRecursiveForward()
		self.RunTestCaseNavigationMany2ZeroOneRecursiveReverse()
		self.RunTestCaseNavigationMany2Many()
		self.RunTestCaseNavigationMany2Many1()
		self.RunTestCaseNavigationMany2ManyRecursive()
		
if __name__ == "__main__":
	logging.basicConfig(level=logging.INFO)
	unittest.main()
