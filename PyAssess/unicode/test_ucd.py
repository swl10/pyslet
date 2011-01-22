import unittest
from sys import maxunicode

from ucd import *

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(CharClassTestTests,'test'),
		unittest.makeSuite(UCDTests,'test')
		))

class CharClassTestTests(unittest.TestCase):
	def testCharInClass(self):
		"""Check a group of ranges"""
		CHAR_CLASS_TESTS=[
			[[],""],
			[[['a','z']],"abcdefghijklmnopqrstuvwxyz"],
			[[['a','d'],['f','k']],"abcdfghijk"],
			[[['b','b']],"b"],
			[[['a','b'],['c','d'],['e','f'],['g','h'],['i','j'],['k','k']],"abcdefghijk"],
			[[['a','b'],['d','f'],['h','h']],"abdefh"]
			]
		for test in CHAR_CLASS_TESTS:
			result=[]
			for c in "abcdefghijklmnopqrstuvwxyz":
				if CharInClass(c,test[0]):
					result.append(c)
			result=join(result,'')
			self.failUnless(result==test[1],repr(test[0])+" matched "+repr(result))

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