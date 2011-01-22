import unittest
from types import FloatType

from xmlschema import *

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(DatatypeTests,'test'),
		unittest.makeSuite(RegularExpressionTests,'test')
		))

class DatatypeTests(unittest.TestCase):
	def testParseBoolean(self):
		"""Check a ParseBoolean"""
		self.failUnless(ParseBoolean("true")==1,"true test")
		self.failUnless(ParseBoolean("false")==0,"false test")
		self.failUnless(ParseBoolean("1")==1,"1 test")
		self.failUnless(ParseBoolean("0")==0,"0 test")
		for bad in ['True','TRUE','T','FALSE','False','Yes','No','yes','no','YES','NO']:
			try:
				ParseBoolean(bad)
				self.fail("ValueError test: %s"%bad)
			except ValueError:
				pass		
	
	def testFormatBoolean(self):
		"""Check FormatBoolean"""
		self.failUnless(FormatBoolean(1)=="true","true test")
		self.failUnless(FormatBoolean(0)=="false","false test")
		self.failUnless(FormatBoolean(100)=="true","non-zero test")
		self.failUnless(FormatBoolean(None)=="false","None test")
	
	def testParseInteger(self):
		"""Check ParseInteger"""
		self.failUnless(ParseInteger("1")==1,"simple test")
		self.failUnless(ParseInteger("+1")==1,"plus test")
		self.failUnless(ParseInteger("-1")==-1,"minus test")
		self.failUnless(ParseInteger("0")==0,"zero test")
		self.failUnless(ParseInteger("+0")==0,"plus zero")
		self.failUnless(ParseInteger("-0")==-0,"minus zero")
		self.failUnless(ParseInteger("-36893488147419103232")==-36893488147419103232L,"large neg test")
		self.failUnless(ParseInteger("36893488147419103232")==36893488147419103232L,"large pos test")
		for bad in [' 1','1.','1.0','1e+10','one']:
			try:
				ParseInteger(bad)
				self.fail("ValueError test: %s"%bad)
			except ValueError:
				pass

	def testFormatInteger(self):
		"""Check FormatInteger"""
		self.failUnless(FormatInteger(1)=="1","simple test")
		self.failUnless(FormatInteger(0)=="0","zero test")
		self.failUnless(FormatInteger(-1)=="-1","minus test")
		self.failUnless(FormatInteger(-36893488147419103232L)=="-36893488147419103232","large neg test")
		self.failUnless(FormatInteger(36893488147419103232L)=="36893488147419103232","large pos test")

	def testParseDecimal(self):
		"""Check ParseDecimal"""
		d=ParseDecimal("1")
		self.failUnless(d==1.0 and type(d) is FloatType,"simple type test")
		self.failUnless(ParseDecimal("+1")==1.0,"plus test")
		self.failUnless(ParseDecimal("-1")==-1.0,"minus test")
		d=ParseDecimal("0")
		self.failUnless(d==0.0 and type(d) is FloatType,"zero test")
		self.failUnless(ParseDecimal("+0")==0.0,"plus zero")
		self.failUnless(ParseDecimal("-0")==-0.0,"minus zero")
		self.failUnless(ParseDecimal("0.")==0.0,"zero point")
		self.failUnless(ParseDecimal(".0")==0.0,"point zero")
		self.failUnless(ParseDecimal(".")==0.0,"point only zero")
		# now the totalDigits test
		self.failUnless(ParseDecimal("1.1",3)==1.1,"less than total digits")
		self.failUnless(ParseDecimal("1.1",2)==1.1,"exactly total digits")
		try:
			ParseDecimal("1.1",1)
			self.fail("more than total digits")
		except ValueError:
			pass
		# now the fractionDigits test
		self.failUnless(ParseDecimal("1.1",None,2)==1.1,"less than fraction digits")
		self.failUnless(ParseDecimal("1.1",None,1)==1.1,"exactly fraction digits")
		try:
			ParseDecimal("1.1",None,0)
			self.fail("more than fraction digits")
		except ValueError:
			pass
		# conflicting fractionDigits and totalDigits
		try:
			ParseDecimal("1.1",1,2)
			self.fail("more than total digits, less than fraction digits")
		except ValueError:
			pass
		d=ParseDecimal("36893488147419103232")
		self.failUnless(3.68934e19<d and 3.68935e19>d,"large pos integer")
		d=ParseDecimal("-36893488147419103232")
		self.failUnless(-3.68934e19>d and -3.68935e19<d,"large neg integer")
		d=ParseDecimal("0.000000000000000000314")
		self.failUnless(3.139e-19<d and 3.141e-19>d,"small pos test")

	def testFormatDecimal(self):
		"""Check FormatDecimal"""
		self.failUnless(FormatDecimal(1.0)=="1.0","simple test")
		self.failUnless(FormatDecimal(0)=="0.0","zero test")
		self.failUnless(FormatDecimal(-1)=="-1.0","minus test")
		self.failUnless(FormatDecimal(3.14e-19)=="0.000000000000000000314","small pos test")
		d=FormatDecimal(3.6893488147419103232e19)
		self.failUnless(d[:14]=="36893488147419" and d[-2:]==".0","large pos test")
		d=FormatDecimal(-3.6893488147419103232e19)
		self.failUnless(d[:15]=="-36893488147419" and d[-2:]==".0","large neg test")
		self.failUnless(FormatDecimal(3.1415926535897931,3)=="3.14","totalDigits OK")
		self.failUnless(FormatDecimal(3141.5926535897931,4,3)=="3142.","totalDigit/canonical form conflict")
		try:
			FormatDecimal(3141.5926535897931,3)
			self.fail("totalDigits exceeded")
		except ValueError:
			pass
		self.failUnless(FormatDecimal(3.1415926535897931,None,3)=="3.142","fractionDigits rounding")
		try:
			FormatDecimal(99.5,2)
			self.fail("totalDigits exceeded, pathalogical case")
		except ValueError:
			pass
	
	def testParseFloat(self):
		"""Check ParseFloat"""
		f=ParseFloat("1")
		self.failUnless(f==1.0 and type(f) is FloatType,"simple type test")
		self.failUnless(ParseFloat("1.0e+1")==10.0,"plus exp test")
		self.failUnless(ParseFloat("100e-1")==10.0,"minus exp test")
		self.failUnless(ParseFloat("1.0e1")==10.0,"no sign exp test")
		f=ParseFloat("0")
		self.failUnless(ParseFloat("1.0E+1")==10.0,"upper-case test")
		self.failUnless(ParseFloat("100e-1")==10.0,"minus exp test")
		self.failUnless(f==0.0 and type(f) is FloatType,"zero test")

	def testFormatFloat(self):
		"""Check FormatFloat"""
		self.failUnless(FormatFloat(1.0)=="1.0E0","simple test")
		self.failUnless(FormatFloat(0)=="0.0E0","zero test")
		self.failUnless(FormatFloat(-1)=="-1.0E0","minus test")
		self.failUnless(FormatFloat(3.14e-19)=="3.14E-19","small pos test")
		d=FormatFloat(3.6893488147419103232e19)
		self.failUnless(d[:15]=="3.6893488147419" and d[-3:]=="E19","large pos test")
		d=FormatFloat(-3.6893488147419103232e19)
		self.failUnless(d[:16]=="-3.6893488147419" and d[-3:]=="E19","large neg test")

class RegularExpressionTests(unittest.TestCase):
	def testExpression(self):
		e=RegularExpression("")
		self.failUnless(e.Match("") and not e.Match("a"),"empty string")
		e=RegularExpression("a|b")
		self.failUnless(e.Match("a") and e.Match("b") and not e.Match("a|b") and not e.Match("c"),"branch separator")
		e=RegularExpression("a|")
		self.failUnless(e.Match("a") and not e.Match("b") and not e.Match("a|") and e.Match(""),"empty branch separator")
		e=RegularExpression("ab")
		self.failUnless(e.Match("ab") and not e.Match("abc"),"concatenation")
		e=RegularExpression("a?")
		self.failUnless(e.Match("a") and e.Match("") and not e.Match("b"),"quantifier: ?")
		e=RegularExpression("a*")
		self.failUnless(e.Match("a") and e.Match("") and e.Match("aaaaaa") and not e.Match("b"),"quantifier: *")
		e=RegularExpression("a+")
		self.failUnless(e.Match("a") and not e.Match("") and e.Match("aaaaaa") and not e.Match("b"),"quantifier: +")
		e=RegularExpression("a{2,3}")
		self.failUnless(not e.Match("") and not e.Match("a") and e.Match("aa") and e.Match("aaa") and not e.Match("aaaa"),"quantifier: {n,m}")
		e=RegularExpression("a{2}")
		self.failUnless(not e.Match("") and not e.Match("a") and e.Match("aa") and not e.Match("aaa"),"quantifier: {n}")
		e=RegularExpression("a{2,}")
		self.failUnless(not e.Match("") and not e.Match("a") and e.Match("aa") and e.Match("aaaaaa"),"quantifier: {n,}")
		e=RegularExpression("a{0,2}")
		self.failUnless(e.Match("") and e.Match("a") and e.Match("aa") and not e.Match("aaa"),"quantifier: {0,n}")
		e=RegularExpression("a{0,0}")
		self.failUnless(e.Match("") and not e.Match("a") and not e.Match("aaa"),"quantifier: {0,n}")
		e=RegularExpression("^$")
		self.failUnless(e.Match("^$"),"false start/end of string markers")
		e=RegularExpression("a(b)")
		self.failUnless(e.Match("ab") and not e.Match("a"),"bracketed expression")
		e=RegularExpression("[d]")
		self.failUnless(e.Match("d"),"simple set")
		e=RegularExpression("[-a]")
		self.failUnless(e.Match("-") and e.Match("a") and not e.Match("-a"),"hyphen character leading range")
		e=RegularExpression("[a-]")
		self.failUnless(e.Match("-") and e.Match("a") and not e.Match("a-"),"hyphen character trailing range")
		e=RegularExpression("[a-c]")
		self.failUnless(not e.Match("-") and e.Match("a") and e.Match("b") and e.Match("c"),"full range")
		e=RegularExpression("[a^-`]")
		self.failUnless(e.Match("a") and e.Match("^") and e.Match("_") and not e.Match("-"),"caret range")
		e=RegularExpression("[^-a]")
		self.failUnless(not e.Match("-") and not e.Match("a") and e.Match("b"),"hyphen character leading negative range")
		e=RegularExpression("[^a-c]")
		self.failUnless(e.Match("-") and not e.Match("a") and not e.Match("b") and not e.Match("c"),"negative full range")
		e=RegularExpression("[a-d-[b-c]]")
		self.failUnless(not e.Match("-") and e.Match("a") and not e.Match("b") and e.Match("d"),"subtracted range case I")
		e=RegularExpression("[a-d-[d]]")
		self.failUnless(not e.Match("-") and e.Match("a") and e.Match("b") and not e.Match("d"),"subtracted range case II")
		e=RegularExpression("[a-z-[fghm-p]]")
		self.failUnless(not e.Match("-") and e.Match("a") and not e.Match("g") and not e.Match("o"),"subtracted complex range case")
		e=RegularExpression("[a-z-[fghm-p-[g-h]]]")
		self.failUnless(not e.Match("-") and e.Match("a") and e.Match("g") and not e.Match("o"),"double subtracted complex range case")
		e=RegularExpression(r"\n\r\t\\\|\.\-\^\?\*\+\{\}\(\)\[\]")
		self.failUnless(e.Match("\n\r\t\\|.-^?*+{}()[]"),"single char escapes")
		e=RegularExpression(r"\p{Lu}")
		self.failUnless(e.Match("D") and not e.Match("d"),"char category escapes")
		e=RegularExpression(r"\p{IsBasicLatin}")
		self.failUnless(e.Match("D") and e.Match("\x7F") and not e.Match(u'\xE9'),"IsBlock category escapes")
		e=RegularExpression(r".")
		self.failUnless(e.Match(".") and e.Match("a") and not e.Match("\n") and not e.Match("\r"),"dot escape")
		e=RegularExpression(r"\s")
		self.failUnless(e.Match(" ") and e.Match("\t") and e.Match("\n") and e.Match("\r") and not e.Match(u"\xA0"),"white space escape")
		e=RegularExpression(r"\S")
		self.failIf(e.Match(" ") or e.Match("\t") or e.Match("\n") or e.Match("\r") or not e.Match(u"\xA0"),"white space complement escape")
		e=RegularExpression(r"\i")
		self.failUnless(e.Match(":") and e.Match("_") and e.Match("D") and not e.Match("-"),"Initial namechar escape")
		e=RegularExpression(r"\I")
		self.failUnless(not e.Match(":") and not e.Match("_") and not e.Match("D") and e.Match("-"),"Initial namechar complement escape")
		e=RegularExpression(r"\c")
		self.failUnless(e.Match(":") and e.Match("-") and e.Match("D") and e.Match("0") and not e.Match("&"),"namechar escape")
		e=RegularExpression(r"\C")
		self.failUnless(not e.Match(":") and not e.Match("-") and not e.Match("D") and not e.Match("0") and e.Match("&"),"namechar complement escape")
		e=RegularExpression(r"\d")
		self.failUnless(e.Match("0") and e.Match("9") and e.Match(u"\u0660") and e.Match(u"\u0669") and not e.Match("."),"digit escape")
		e=RegularExpression(r"\D")
		self.failIf(e.Match("0") or e.Match("9") or e.Match(u"\u0660") or e.Match(u"\u0669") or not e.Match("."),"digit complement escape")
		e=RegularExpression(r"\w")
		self.failUnless(e.Match("a") and e.Match("0") and e.Match("+") and e.Match("$") and not e.Match("."),"word char escape")
		e=RegularExpression(r"\W")
		self.failIf(e.Match("a") or e.Match("0") or e.Match("+") or e.Match("$") or not e.Match("."),"word char complement escape")
		 
	def testBadExpressions(self):
		BAD_RE=["a{-1,2}","a{3,2}","a{}","a{a}","a{1,2,3}","a{,2}","?a","*a","+a","{a","}a",")a","]a","[c-a]",r"\a",
			r"\p{Cx}",r"\p{IsBadBlock}"]
		for eStr in BAD_RE:
			try:
				e=RegularExpression(eStr)
				self.fail("Regular expression %s compiled OK"%eStr)
			except RegularExpressionError:
				pass
							
if __name__ == "__main__":
	unittest.main()