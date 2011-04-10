#! /usr/bin/env python

import unittest

from pyslet.html40_19991224 import *

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(HTML40_19991224Tests,'test')
		))

class HTML40_19991224Tests(unittest.TestCase):		
	def testCaseConstants(self):
		self.failUnless(HTML40_PUBLICID=="-//W3C//DTD HTML 4.01//EN")

class ParserTests(unittest.TestCase):		
	def testCaseConstructor(self):
		e=xml.XMLEntity("Preamble\n<P>Hello&nbsp;<b>World!<P>Pleased to meet you.</P>")
		p=HTMLParser(e)
		fragment=p.ParseHTMLFragment()
		self.failUnless(fragment[0]=='Preamble\n',"Preamble: %s"%repr(fragment[0]))
		tag=fragment[1]
		self.failUnless(isinstance(tag,XHTMLP),"P Tag: %s"%repr(tag))
		children=tag.GetChildren()
		self.failUnless(children[0]==u'Hello\xA0',"nbsp: %s"%repr(children[0]))
		self.failUnless(isinstance(children[1],XHTMLB),"B Tag: %s"%repr(children[1]))
		self.failUnless(children[1].GetValue()=="World!")
		tag=fragment[2]
		self.failUnless(isinstance(tag,XHTMLP),"P Tag: %s"%repr(tag))
		self.failUnless(tag.GetValue()=="Pleased to meet you.")
		
if __name__ == "__main__":
	unittest.main()
