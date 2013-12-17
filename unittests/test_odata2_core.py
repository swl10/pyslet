#! /usr/bin/env python

import unittest

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
		self.assertTrue(value.pyValue is False,"Expected false")
				
	def testCaseEvaluateBooleanExpression(self):
		# cursory check:
		# a boolCommonExpression MUST be a common expression that evaluates to the EDM Primitive type Edm.Boolean
		value=self.EvaluateCommon("true and false")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected false")
				
	def testCaseEvaluateParenExpression(self):
		"""a parenExpression MUST be evaluated by evaluating the
		expression with the parentheses, starting with the innermost
		parenthesized expressions and proceeding outwards...

		...the result of the parenExpression MUST be the result of the
		evaluation of the contained expression."""
		p=Parser("(false and false or true)")		# note that or is the weakest operator
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.assertTrue(value.pyValue is True,"Expected True")
		p=Parser("(false and (false or true))")		# should change the result
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("(((((((false) and (((false)) or true)))))))")
		self.assertTrue(value.pyValue is False,"Expected False - multibrackets")
				
	def testCaseEvaluateBooleanParenExpression(self):
		"""Cursory check: a boolParenExpression MUST be evaluated by
		evaluating the expression with the parentheses. The result of
		the boolParenExpression MUST ... be of the EDM Primitive type
		Edm.Boolean"""
		value=self.EvaluateCommon("(false and (false or true))")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected false")
	
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
		self.assertTrue(value.pyValue == 4,"Expected 4")
		value=self.EvaluateCommon("2D add 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 4.0,"Expected 4")
		value=self.EvaluateCommon("2F add 2D")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 4.0,"Expected 4")
		value=self.EvaluateCommon("2 add 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue == 4L,"Expected 4")
		try:
			value=self.EvaluateCommon("2 add '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("2 add null")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue is None,"Expected None")

	def testCaseEvaluateSubExpression(self):
		"""See testCaseEvaluateAddExpression"""
		value=self.EvaluateCommon("4M sub 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.assertTrue(value.pyValue == 2,"Expected 2.0")
		value=self.EvaluateCommon("4D sub 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 2.0,"Expected 2.0")
		value=self.EvaluateCommon("4F sub 2D")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 2.0,"Expected 2.0")
		value=self.EvaluateCommon("4 sub 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue == 2L,"Expected 2L")
		try:
			value=self.EvaluateCommon("4 sub '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("4 sub null")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue is None,"Expected None")

	def testCaseEvaluateMulExpression(self):
		"""See testCaseEvaluateAddExpression"""
		value=self.EvaluateCommon("4M mul 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.assertTrue(value.pyValue == 8,"Expected 8.0")
		value=self.EvaluateCommon("4D mul 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 8.0,"Expected 8.0")
		value=self.EvaluateCommon("4F mul 2D")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 8.0,"Expected 8.0")
		value=self.EvaluateCommon("4 mul 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue == 8L,"Expected 8L")
		try:
			value=self.EvaluateCommon("4 mul '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("4 mul null")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue is None,"Expected None")

	def testCaseEvaluateDivExpression(self):
		"""See testCaseEvaluateAddExpression
		
		OData is ambiguous in the way it defines division as it makes reference only
		to the IEEE floating point operations.  For compatibility with SQL though we
		assume that integer division simple truncates fractional parts."""
		value=self.EvaluateCommon("4M div 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.assertTrue(value.pyValue == 2,"Expected 2")
		value=self.EvaluateCommon("4D div 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 2.0,"Expected 2.0")
		try:
			value=self.EvaluateCommon("4D div 0")
			self.fail("Division by zero")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("4F div 2D")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 2.0,"Expected 2.0")
		value=self.EvaluateCommon("5 div 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue == 2L,"Expected 2L")
		value=self.EvaluateCommon("-5 div 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue == -2L,"Expected -2L")
		try:
			value=self.EvaluateCommon("4 div '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("4 div null")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue is None,"Expected None")

	def testCaseEvaluateModExpression(self):
		"""See testCaseEvaluateAddExpression
		
		The data service SHOULD evaluate the operation represented by
		the modExpression, according to the rules of [IEEE754-2008]

		For integer division we just truncate fractional parts towards zero."""
		value=self.EvaluateCommon("5.5M mod 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.assertTrue(value.pyValue == 1.5,"Expected 1.5")
		value=self.EvaluateCommon("5.5D mod 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 1.5,"Expected 1.5")
		try:
			value=self.EvaluateCommon("5.5D mod 0")
			self.fail("Division by zero")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("5.5F mod 2D")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 1.5,"Expected 1.5")
		value=self.EvaluateCommon("5 mod 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue == 1L,"Expected 1L")
		value=self.EvaluateCommon("-5 mod 2L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue == -1L,"Expected -1L")
		try:
			value=self.EvaluateCommon("5 mod '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("5 mod null")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue is None,"Expected None")


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
		self.assertTrue(value.pyValue == -2,"Expected -2.0")
		value=self.EvaluateCommon("-(2D)")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == -2.0,"Expected -2.0")
		p=Parser("-(-2F)")	# unary numeric promotion to Double - a bit weird 
		e=p.ParseCommonExpression()
		value=e.Evaluate(None)
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue == 2.0,"Expected 2.0")
		value=self.EvaluateCommon("-(2L)")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue == -2L,"Expected -2L")
		try:
			value=self.EvaluateCommon("-'2'")
			self.fail("String promotion to numeric")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("-null")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue is None,"Expected None")


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
		self.assertTrue(value.pyValue is False,"Expected False")
		try:
			value=self.EvaluateCommon("false and 0")
			self.fail("Integer promotion to Boolean")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("false and true")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("true and false")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("true and true")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("true and null")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("false and null")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("false and false")
		self.assertTrue(value.pyValue is False,"Expected False")


	def testCaseEvaluateOrExpression(self):
		"""See testCaseEvaluateAndExpression for more details.
		
		...data service MUST evaluate the expression to the value of
		true if at least one of the operands is true after being
		evaluated. If both operands are false after being evaluated, the
		expression MUST evaluate to the value of false"""
		value=self.EvaluateCommon("false or false")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected False")
		try:
			value=self.EvaluateCommon("false or 0")
			self.fail("Integer promotion to Boolean")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("false or true")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("true or false")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("true or true")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("true or null")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("false or null")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("null or null")
		self.assertTrue(value.pyValue is False,"Expected False")

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
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("2D eq 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("2F eq 2D")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("2 eq 2L")
		self.assertTrue(value.pyValue is True,"Expected True")
		try:
			value=self.EvaluateCommon("2 eq '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("'2' eq '2'")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' eq datetime'2013-08-30T18:49'")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' eq datetime'2013-08-30T18:49:01'")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' eq guid'b3afeebc-9658-4699-9d9c-1df551fd6814'")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' eq guid'3fa6109e-f09c-4c5e-a5f3-6cf38d35c9b5'")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("X'DEADBEEF' eq binary'deadbeef'")
		self.assertTrue(value.pyValue is True,"Expected True")			
		value=self.EvaluateCommon("X'DEAD' eq binary'BEEF'")
		self.assertTrue(value.pyValue is False,"Expected False")			
		value=self.EvaluateCommon("2 eq null")
		self.assertTrue(value.pyValue is False,"Expected False")			
		value=self.EvaluateCommon("null eq null")
		self.assertTrue(value.pyValue is True,"Expected True")			

	def testCaseEvaluateNeExpression(self):
		"""See testCaseEvaluateEqExpression for details."""
		value=self.EvaluateCommon("2M ne 3M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("2D ne 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("2F ne 2D")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("2 ne 2L")
		self.assertTrue(value.pyValue is False,"Expected False")
		try:
			value=self.EvaluateCommon("2 ne '2'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("'2' ne '2'")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' ne datetime'2013-08-30T18:49'")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' ne datetime'2013-08-30T18:49:01'")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' ne guid'b3afeebc-9658-4699-9d9c-1df551fd6814'")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' ne guid'3fa6109e-f09c-4c5e-a5f3-6cf38d35c9b5'")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("X'DEADBEEF' ne binary'deadbeef'")
		self.assertTrue(value.pyValue is False,"Expected False")			
		value=self.EvaluateCommon("X'DEAD' ne binary'BEEF'")
		self.assertTrue(value.pyValue is True,"Expected True")			
		value=self.EvaluateCommon("2 ne null")
		self.assertTrue(value.pyValue is True,"Expected True")			
		value=self.EvaluateCommon("null ne null")
		self.assertTrue(value.pyValue is False,"Expected False")			


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
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("2D lt 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("2.1F lt 2D")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("2 lt 3L")
		self.assertTrue(value.pyValue is True,"Expected True")
		try:
			value=self.EvaluateCommon("2 lt '3'")
			self.fail("String promotion to int")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("'20' lt '3'")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' lt datetime'2013-08-30T18:49'")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' lt datetime'2013-08-30T18:49:01'")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' lt guid'b3afeebc-9658-4699-9d9c-1df551fd6814'")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814' lt guid'3fa6109e-f09c-4c5e-a5f3-6cf38d35c9b5'")
		self.assertTrue(value.pyValue is False,"Expected False")
		try:
			p=Parser("X'DEADBEEF' lt binary'deadbeef'")
			e=p.ParseCommonExpression()
			value=e.Evaluate(None)
			self.fail("Relational operation on binary data")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("2 lt null")
		self.assertTrue(value.pyValue is False,"Expected False")			
		value=self.EvaluateCommon("null lt null")
		self.assertTrue(value.pyValue is False,"Expected False")			

	def testCaseEvaluateLeExpression(self):
		"""See testCaseEvaluateLtExpression for more information - abbreviated tests"""
		value=self.EvaluateCommon("2D le 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' le datetime'2013-08-30T18:49:00'")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("2 le null")
		self.assertTrue(value.pyValue is False,"Expected False")			
		value=self.EvaluateCommon("null le null")
		self.assertTrue(value.pyValue is False,"Expected False")			
		
	def testCaseEvaluateGtExpression(self):
		"""See testCaseEvaluateLtExpression for more information - abbreviated tests"""
		value=self.EvaluateCommon("2D gt 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' gt datetime'2013-08-30T18:49:00'")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("2 gt null")
		self.assertTrue(value.pyValue is False,"Expected False")			
		value=self.EvaluateCommon("null gt null")
		self.assertTrue(value.pyValue is False,"Expected False")			
		
	def testCaseEvaluateGeExpression(self):
		"""See testCaseEvaluateLtExpression for more information - abbreviated tests"""
		value=self.EvaluateCommon("2D ge 2M")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("datetime'2013-08-30T18:49' ge datetime'2013-08-30T18:49:00'")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("2 ge null")
		self.assertTrue(value.pyValue is False,"Expected False")			
		value=self.EvaluateCommon("null ge null")
		self.assertTrue(value.pyValue is False,"Expected False")			

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
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("not true")
		self.assertTrue(value.pyValue is False,"Expected False")
		try:
			value=self.EvaluateCommon("not 1")
			self.fail("Integer promotion to Boolean")
		except EvaluationError:
			pass
		value=self.EvaluateCommon("not null")
		self.assertTrue(value.pyValue is None,"Expected NULL")
	
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
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("isof(2M,'Edm.Double')")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("isof(2,'Edm.Double')")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("isof(2.0D,'Edm.Single')")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("isof('x','Edm.String')")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("isof(X'DEAD','Edm.String')")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("isof(false or true,'Edm.Boolean')")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("isof(null,'Edm.String')")
		self.assertTrue(value.pyValue is False,"Expected False")
		value=self.EvaluateCommon("isof('Edm.String')")
		self.assertTrue(value.pyValue is False,"Expected False")
	
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
		self.assertTrue(value.pyValue==2.0,"Expected 2.0")
		value=self.EvaluateCommon("cast(2L,'Edm.Single')")
		self.assertTrue(value.typeCode==edm.SimpleType.Single,"Expected Single")
		self.assertTrue(value.pyValue==2.0,"Expected 2.0")
		value=self.EvaluateCommon("cast(2,'Edm.Int64')")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue==2L,"Expected 2")
		try:
			value=self.EvaluateCommon("cast(2.0D,'Edm.Single')")
			self.fail("Double cast to Single")
		except:
			pass
		value=self.EvaluateCommon("cast('x','Edm.String')")
		self.assertTrue(value.pyValue=='x',"Expected 'x'")
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
		self.assertTrue(value.pyValue is None,"Expected None")
		value=self.EvaluateCommon("cast('Edm.Int16')")
		self.assertTrue(value.typeCode==edm.SimpleType.Int16,"Expected Int16")
		self.assertTrue(value.pyValue is None,"Expected None")		
	
	def testCaseEvaluateBooleanCastExpression(self):
		# cursory check:
		value=self.EvaluateCommon("cast(true,'Edm.Boolean')")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is True,"Expected True")

	def testCaseEvaluateBooleanLiteralExpression(self):
		"""the type of the boolLiteralExpression MUST always be the EDM
		primitive type Edm.Boolean."""
		value=self.EvaluateCommon("true")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is True,"Expected True")
		value=self.EvaluateCommon("false")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue is False,"Expected False")

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
		self.assertTrue(value.pyValue==None,"Expected None")
		value=self.EvaluateCommon("X'DEAD'")
		self.assertTrue(value.typeCode==edm.SimpleType.Binary,"Expected Binary")
		self.assertTrue(value.pyValue=='\xde\xad')
		value=self.EvaluateCommon("true")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Booelan")
		self.assertTrue(value.pyValue==True)
		value=self.EvaluateCommon("123")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue==123)
		value=self.EvaluateCommon("datetime'2013-08-31T15:28'")
		self.assertTrue(value.typeCode==edm.SimpleType.DateTime,"Expected DateTime")
		self.assertTrue(value.pyValue.date.year==13)
		value=self.EvaluateCommon("123.5M")
		self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
		self.assertTrue(value.pyValue==123.5)
		value=self.EvaluateCommon("123.5D")
		self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
		self.assertTrue(value.pyValue==123.5)
		value=self.EvaluateCommon("123.5F")
		self.assertTrue(value.typeCode==edm.SimpleType.Single,"Expected Single")
		self.assertTrue(value.pyValue==123.5)
		value=self.EvaluateCommon("guid'b3afeebc-9658-4699-9d9c-1df551fd6814'")
		self.assertTrue(value.typeCode==edm.SimpleType.Guid,"Expected Guid")
		self.assertTrue(value.pyValue==uuid.UUID('b3afeebc-9658-4699-9d9c-1df551fd6814'))
		value=self.EvaluateCommon("123456")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue==123456)
		value=self.EvaluateCommon("123456L")
		self.assertTrue(value.typeCode==edm.SimpleType.Int64,"Expected Int64")
		self.assertTrue(value.pyValue==123456L)
		value=self.EvaluateCommon("-123")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue==-123)
		value=self.EvaluateCommon("'123'")
		self.assertTrue(value.typeCode==edm.SimpleType.String,"Expected String")
		self.assertTrue(value.pyValue=='123')
		value=self.EvaluateCommon("time'P123D'")
		self.assertTrue(value.typeCode==edm.SimpleType.Time,"Expected Time")
		self.assertTrue(value.pyValue.days==123)
		value=self.EvaluateCommon("datetimeoffset'2002-10-10T12:00:00-05:00'")
		self.assertTrue(value.typeCode==edm.SimpleType.DateTimeOffset,"Expected DateTimeOffset")
		self.assertTrue(value.pyValue==iso.TimePoint('2002-10-10T12:00:00-05:00'))

	def testCaseEvaluateMethodCallExpression(self):
		"""Cursory check only."""
		value=self.EvaluateCommon("length('x')")
		self.assertTrue(value.typeCode==edm.SimpleType.Int32,"Expected Int32")
		self.assertTrue(value.pyValue==1)

	def testCaseEvaluateBooleanMethodCallExpress(self):
		"""Cursory check only."""
		value=self.EvaluateCommon("startswith('xyz','x')")
		self.assertTrue(value.typeCode==edm.SimpleType.Boolean,"Expected Boolean")
		self.assertTrue(value.pyValue==True)

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
		self.assertTrue(value.pyValue==True)
		value=self.EvaluateCommon("endswith('startswith','start')")
		self.assertTrue(value.pyValue==False)
		value=self.EvaluateCommon("endswith('startswith','WITH')")
		# not case insensitive
		self.assertTrue(value.pyValue==False)
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
		self.assertTrue(value.pyValue==1)
		value=self.EvaluateCommon("indexof('startswith','start')")
		self.assertTrue(value.pyValue==0)
		value=self.EvaluateCommon("indexof('startswith','t')")
		self.assertTrue(value.pyValue==1)
		# not case insensitive
		value=self.EvaluateCommon("indexof('startswith','W')")
		self.assertTrue(value.pyValue==-1)
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
		self.assertTrue(value.pyValue==u"scakeswith")
		value=self.EvaluateCommon("replace('startswith','t','x')")
		self.assertTrue(value.pyValue==u"sxarxswixh")
		# not case insensitive
		value=self.EvaluateCommon("replace('sTartswith','t','x')")
		self.assertTrue(value.pyValue==u"sTarxswixh")
		value=self.EvaluateCommon("replace('startswith','t','tx')")
		self.assertTrue(value.pyValue==u"stxartxswitxh")
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
		self.assertTrue(value.pyValue==True)
		value=self.EvaluateCommon("startswith('startswith','end')")
		self.assertTrue(value.pyValue==False)
		value=self.EvaluateCommon("startswith('startswith','Start')")
		# not case insensitive
		self.assertTrue(value.pyValue==False)
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
		self.assertTrue(value.pyValue==u"steve")
		value=self.EvaluateCommon(u"tolower('CAF\xc9')")
		self.assertTrue(value.pyValue==u'caf\xe9')
		value=self.EvaluateCommon(u"tolower('caf\xe9')")
		self.assertTrue(value.pyValue==u'caf\xe9')
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
		self.assertTrue(value.pyValue==u"STEVE")
		value=self.EvaluateCommon(u"toupper('CAF\xc9')")
		self.assertTrue(value.pyValue==u'CAF\xc9')
		value=self.EvaluateCommon(u"toupper('caf\xe9')")
		self.assertTrue(value.pyValue==u'CAF\xc9')
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
		self.assertTrue(value.pyValue==u"Steve")
		value=self.EvaluateCommon(u"trim(' C  a  f \xe9 ')")
		self.assertTrue(value.pyValue==u'C  a  f \xe9')
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
		self.assertTrue(value.pyValue==u"tart")
		value=self.EvaluateCommon("substring('startswith',1)")
		self.assertTrue(value.pyValue==u"tartswith")
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
		self.assertTrue(value.pyValue==True)
		value=self.EvaluateCommon("substringof('startswith','start')")
		self.assertTrue(value.pyValue==True)
		value=self.EvaluateCommon("substringof('startswith','t')")
		self.assertTrue(value.pyValue==True)
		# not case insensitive
		value=self.EvaluateCommon("substringof('startswith','W')")
		self.assertTrue(value.pyValue==False)
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
		self.assertTrue(value.pyValue==u"startswith")
		value=self.EvaluateCommon("concat('3.1',concat('4','159'))")
		self.assertTrue(value.pyValue==u"3.14159")
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
		self.assertTrue(value.pyValue==5)
		value=self.EvaluateCommon(u"length('CAF\xc9')")
		self.assertTrue(value.pyValue==4)
		value=self.EvaluateCommon(u"length('')")
		self.assertTrue(value.pyValue==0)
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
			self.assertTrue(value.pyValue==r)
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
			self.assertTrue(value.pyValue==r[0])
			# check rounding to even for binary floating point
			value=self.EvaluateCommon("%s(2.5D)"%f)
			self.assertTrue(value.pyValue==r[1])
			value=self.EvaluateCommon("%s(-2.5D)"%f)
			self.assertTrue(value.pyValue==r[2])
			value=self.EvaluateCommon("%s(1.5M)"%f)
			self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
			self.assertTrue(value.pyValue==r[3])
			# check rounding away from zero for decimals
			value=self.EvaluateCommon("%s(2.5M)"%f)
			self.assertTrue(value.pyValue==r[4])
			value=self.EvaluateCommon("%s(-2.5M)"%f)
			self.assertTrue(value.pyValue==r[5])
			# single promotes to double
			value=self.EvaluateCommon("%s(2.5F)"%f)
			self.assertTrue(value.typeCode==edm.SimpleType.Double,"Expected Double")
			self.assertTrue(value.pyValue==r[6])
			# integers promote to decimal - seems a bit strange but there you go
			value=self.EvaluateCommon("%s(3)"%f)
			self.assertTrue(value.typeCode==edm.SimpleType.Decimal,"Expected Decimal")
			self.assertTrue(value.pyValue==r[7])
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
		self.assertTrue(value.pyValue is True)
	
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
			"time'P123D'",
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
		self.assertTrue(dsURI.navPath[0][1][u''].pyValue==1,"Key value")
		# self.assertTrue(dsURI.navPath==[(u'Products',{'':1})],"path: %s"%repr(dsURI.navPath))
		self.assertTrue(dsURI.pathOption==PathOption.value,"$value recognised")
		dsURI=ODataURI('Products(x=1,y=2)','/x.svc')
		self.assertTrue(len(dsURI.navPath)==1)
		self.assertTrue(dsURI.navPath[0][0]==u'Products')
		self.assertTrue(isinstance(dsURI.navPath[0][1][u'x'],edm.Int32Value),"Key value type")
		self.assertTrue(dsURI.navPath[0][1][u'x'].pyValue==1,"x Key value")
		self.assertTrue(isinstance(dsURI.navPath[0][1][u'y'],edm.Int32Value),"Key value type")
		self.assertTrue(dsURI.navPath[0][1][u'y'].pyValue==2,"y Key value")		
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

if __name__ == "__main__":
	unittest.main()
