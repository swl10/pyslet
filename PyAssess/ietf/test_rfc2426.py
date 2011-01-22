import unittest
from types import *

from rfc2426 import *
from rfc2234 import RFCSyntaxError

def suite():
	return unittest.makeSuite(VCardTests)

class VCardTests(unittest.TestCase):
	def setUp(self):
		pass
			
	def tearDown(self):
		pass
	
	def testConstructor(self):
		"""Test VCard constructor"""
		vc=VCard()
		vc=VCard("BEGIN:VCARD\r\nEND:VCARD\r\n")
		try:
			VCard("rubbish")
			self.fail("rubbish test")
		except RFCSyntaxError:
			pass