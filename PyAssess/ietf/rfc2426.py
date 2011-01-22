from types import *

from rfc2425 import RFC2425Parser

class VCard:
	def __init__(self,arg=None):
		if type(arg) in StringTypes:
			p=RFC2425Parser(arg)
			while p.theChar is not None:
				p.ParseContentLine()
			self.data=arg			
		elif isinstance(arg,VCard):
			# copy constructor
			self.data=arg.data
		else:
			self.data=''
	
	def __str__(self):
		return self.data
		
	
			