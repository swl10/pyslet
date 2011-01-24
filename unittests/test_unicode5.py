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
		unittest.makeSuite(CharClassTests,'test')
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

	def testRepresentation(self):
		REPR_TESTS=[
			[[],"CharClass()"],
			[[['a','z']],"CharClass((u'a',u'z'))"],
			[[['a','d'],['f','k']],"CharClass((u'a',u'd'), (u'f',u'k'))"]
			]
		for test in REPR_TESTS:
			c=CharClass(*test[0])
			result=self.ClassTest(c)
			self.failUnless(repr(c)==test[1],"CharClass repr test: expected %s, found %s"%(test[1],repr(c)))
		
	def ClassTest(self,cClass):
		#print cClass.ranges
		result=[]
		for c in range(ord('a'),ord('z')+1):
			if cClass.Test(unichr(c)):
				result.append(unichr(c))
		result=string.join(result,'')
		#print result
		return result
		


class MoreCharClassTestTests(unittest.TestCase):

	def testMakeCharClass(self):
		"""Check the MakeCharClass function"""
		CHAR_CLASS_TESTS=[
			[[],[]],
			[ [['a','b'], ['d','e']], [['a','b'], ['d','e']] ],
			[ [['a','b'], ['c','d']], [['a','d']] ],
			[ [['a','b'], ['b','c']], [['a','c']] ],
			[ [['a','c'], ['b','d']], [['a','d']] ],
			[ [['a','d'], ['b','d']], [['a','d']] ],
			[ [['a','d'], ['b','c']], [['a','d']] ],
			[ [['a','a'], ['b','b']], [['a','b']] ],
			[ [['e','f'], ['c','d'], ['a','b']], [['a','f']] ],
			[ [['a','b'], ['a','b']], [['a','b']] ]
			]
		for test in CHAR_CLASS_TESTS:
			src=repr(test[0])
			result=MakeCharClass(test[0])
			self.failUnless(result==test[1],src+" became "+repr(result))
		
	def testSubtractCharClass(self):
		"""Check the SubtractCharClass function"""
		CHAR_CLASS_TESTS=[
			[ [],[],[] ],
			[ [['a','b']], [['c','d']], [['a','b']] ],
			[ [['a','b']], [['b','c']], [['a','a']] ],
			[ [['a','c']], [['b','d']], [['a','a']] ],
			[ [['a','d']], [['b','d']], [['a','a']] ],
			[ [['a','d']], [['b','c']], [['a','a'],['d','d']] ],
			[ [['a','c']], [['a','d']], [] ],
			[ [['a','c']], [['a','c']], [] ],
			[ [['a','d']], [['a','b']], [['c','d']] ],
			[ [['b','c']], [['a','d']], [] ],
			[ [['b','c']], [['a','c']], [] ],
			[ [['b','d']], [['a','c']], [['d','d']] ],
			[ [['a','z']], [['f','h'],['s','u']], [['a','e'],['i','r'],['v','z']] ],
			[ [['a','e'],['i','r'],['v','z']], [['m','x']], [['a','e'],['i','l'],['y','z']] ]
			]
		for test in CHAR_CLASS_TESTS:
			src=repr(test[0])
			result=SubtractCharClass(test[0],test[1])
			self.failUnless(result==test[2],src+" - "+repr(test[1])+" became "+repr(result))

	def testNegateCharClass(self):
		"""Check the NegateCharClass function"""
		minChar=unichr(0)
		maxChar=unichr(maxunicode)		
		CHAR_CLASS_TESTS=[
			[ [], [[minChar,maxChar]] ],
			[ [['b','c']], [[minChar,'a'],['d',maxChar]] ],
			[ [['b','c'],['e','f']], [[minChar,'a'],['d','d'],['g',maxChar]] ]
			]
		for test in CHAR_CLASS_TESTS:
			src=repr(test[0])
			result=NegateCharClass(test[0])
			self.failUnless(result==test[1],repr(test[0])+" negated to "+repr(result))
			result=NegateCharClass(test[1])
			self.failUnless(result==test[0],repr(test[1])+" negated to "+repr(result))
				

class UCDTests(unittest.TestCase):
	"""Tests of the Unicode Category Table come later"""
	def testUCDParser(self):
		pass
				
				 
if __name__ == "__main__":
	unittest.main()