#! /usr/bin/env python
import unittest

from sys import maxunicode
import string

MAX_CHAR=0x10FFFF
if maxunicode<MAX_CHAR:
	MAX_CHAR=maxunicode
	print "unicode5 tests truncated to unichr(0x%X) by narrow python build"%MAX_CHAR

from pyslet.unicode5 import *

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(CharClassTests,'test'),
		unittest.makeSuite(UCDTests,'test')
		))

from pyslet.unicode5 import *


class CharClassTests(unittest.TestCase):
	def testConstructor(self):
		c=CharClass()
		for code in xrange(MAX_CHAR+1):
			self.failIf(c.Test(unichr(code)))
		c=CharClass('a')
		self.failUnless(self.ClassTest(c)=='a')
		c=CharClass(('a','z'))
		self.failUnless(self.ClassTest(c)=='abcdefghijklmnopqrstuvwxyz')
		c=CharClass('abcxyz')
		self.failUnless(len(c.ranges)==2,"No range optimization: %s"%repr(c.ranges))
		self.failUnless(self.ClassTest(c)=='abcxyz')
		cc=CharClass(c)
		self.failUnless(self.ClassTest(cc)=='abcxyz')

	def testComplexConstructors(self):
		INIT_TESTS=[
			[[],""],
			[[['a','z']],"abcdefghijklmnopqrstuvwxyz"],
			[[['a','d'],['f','k']],"abcdfghijk"],
			[[['b','b']],"b"],
			[[['a','b'],['c','d'],['e','f'],['g','h'],['i','j'],['k','k']],"abcdefghijk"],
			[[['a','b'],['d','f'],['h','h']],"abdefh"],
			[[['h','h'],['d','f'],['a','b']],"abdefh"],
			]
		for test in INIT_TESTS:
			c=CharClass(*test[0])
			result=self.ClassTest(c)
			self.failUnless(result==test[1],"CharClass test: expected %s, found %s"%(test[1],result))

	def testAdd(self):
		c=CharClass("ac")
		c.AddChar("b")
		self.failUnless(self.ClassTest(c)=="abc","AddChar")
		c.AddRange("b","e")
		self.failUnless(self.ClassTest(c)=="abcde","AddRange")
		c.AddClass(CharClass(["m","s"]))
		self.failUnless(self.ClassTest(c)=="abcdemnopqrs","AddClass")
		
	def testSubtraction(self):
		c=CharClass("abc")
		c.SubtractChar("b")
		result=self.ClassTest(c)
		self.failUnless(result=="ac","SubtractChar: %s"%result)
		c.SubtractRange("b","d")
		self.failUnless(self.ClassTest(c)=="a","SubtractRange")		
		TESTS=[
			[ [],[],"" ],
			[ [['a','b']], [['c','d']], "ab" ],
			[ [['a','b']], [['b','c']], "a" ],
			[ [['a','c']], [['b','d']], "a" ],
			[ [['a','d']], [['b','d']], "a" ],
			[ [['a','d']], [['b','c']], "ad" ],
			[ [['a','c']], [['a','d']], "" ],
			[ [['a','c']], [['a','c']], "" ],
			[ [['a','d']], [['a','b']], "cd" ],
			[ [['b','c']], [['a','d']], "" ],
			[ [['b','c']], [['a','c']], "" ],
			[ [['b','d']], [['a','c']], "d" ],
			[ [['a','z']], [['f','h'],['s','u']], "abcdeijklmnopqrvwxyz" ],
			[ [['a','e'],['i','r'],['v','z']], [['m','x']], "abcdeijklyz" ]
			]
		for test in TESTS:
			c1=CharClass(*test[0])
			c2=CharClass(*test[1])
			c3=CharClass(c1)
			c3.SubtractClass(c2)
			result=self.ClassTest(c3)
			self.failUnless(result==test[2],"Subtract: %s - %s, found %s"%(repr(c1),repr(c2),repr(c3)))
		
	def testNegateCharClass(self):
		"""Check the Negation function"""
		minChar=unichr(0)
		maxChar=unichr(maxunicode)
		CHAR_CLASS_TESTS=[
			[ [], [[minChar,maxChar]] ],
			[ [['b','c']], [[minChar,'a'],['d',maxChar]] ],
			[ [['b','c'],['e','f']], [[minChar,'a'],['d','d'],['g',maxChar]] ]
			]
		for test in CHAR_CLASS_TESTS:
			c1=CharClass(*test[0])
			c2=CharClass(c1)
			c2.Negate()
			c3=CharClass(*test[1])
			self.failUnless(c2==c3,"%s negated to %s, expected %s"%(repr(c1),repr(c2),repr(c3)))
			c2.Negate()
			self.failUnless(c2==c1,"%s double negation got %s"%(repr(c1),repr(c2)))

	def testRepresentation(self):
		REPR_TESTS=[
			[[],"CharClass()",""],
			[[['a','z']],"CharClass((u'a',u'z'))","a-z"],
			[[['a','d'],['f','k']],"CharClass((u'a',u'd'), (u'f',u'k'))","a-df-k"],
			[[['-','-']],"CharClass(u'-')","\\-"],
			[[['[',']']],"CharClass((u'[',u']'))","[-\\]"],
			[[['\\','\\']],"CharClass(u'\\\\')","\\\\"],			
			]
		for test in REPR_TESTS:
			c=CharClass(*test[0])
			self.failUnless(repr(c)==test[1],"CharClass repr test: expected %s, found %s"%(test[1],repr(c)))
			result=c.FormatRe()
			self.failUnless(result==test[2],"CharClass Re test: expected %s, found %s"%(test[2],result))
			
			
	def ClassTest(self,cClass):
		#print cClass.ranges
		result=[]
		for c in range(ord('a'),ord('z')+1):
			if cClass.Test(unichr(c)):
				result.append(unichr(c))
		result=string.join(result,'')
		#print result
		return result
						

class UCDTests(unittest.TestCase):
	"""Tests of the Unicode Category classes"""
	def testUCDClasses(self):
		classCc=CharClass.UCDCategory('Cc')
		classC=CharClass.UCDCategory('C')
		for code in xrange(0x20):
			self.failUnless(classCc.Test(unichr(code)))
			self.failUnless(classC.Test(unichr(code)))			
		for code in xrange(0x7F,0xA0):
			self.failUnless(classCc.Test(unichr(code)))
			self.failUnless(classC.Test(unichr(code)))			
		self.failIf(classCc.Test(unichr(0xAD)))
		self.failUnless(classC.Test(unichr(0xAD)))
		self.failUnless(CharClass.UCDCategory('Cf').Test(unichr(0xAD)))

	def testUCDBlocks(self):
		classBasicLatin=CharClass.UCDBlock('Basic Latin')
		self.failUnless(classBasicLatin is CharClass.UCDBlock('basiclatin'),"block name normalization")
		for code in xrange(0x80):
			self.failUnless(classBasicLatin.Test(unichr(code)))
		self.failIf(classBasicLatin.Test(unichr(0x80)))
		# randomly pick one of the other blocks
		classBasicLatin=CharClass.UCDBlock('Arrows')
		self.failIf(classBasicLatin.Test(unichr(0x2150)))
		self.failUnless(classBasicLatin.Test(unichr(0x2190)))
				
				 
if __name__ == "__main__":
	unittest.main()