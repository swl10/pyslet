#! /usr/bin/env python


import string, base64
from pyslet.rfc2616_core import *


class HTTPUnknownAuthParam(Exception): pass

class Challenge:
	def __init__(self):
		self.scheme=None
		self.protectionSpace=None
		self.realm=None
	
	def SetAuthParam(self,name,value):
		if name.lower()=='realm':
			self.realm=value
		else:
			raise HTTPUnknownAuthParam(name)

class BasicChallenge(Challenge):
	def __init__(self):
		Challenge.__init__(self)
		self.scheme="Basic"

	def __str__(self):
		format=[self.scheme,' ']
		if self.realm is not None:
			format.append('realm')
			format.append('=')
			format.append(QuoteString(self.realm))
		return string.join(format,'')

		
def ParseAuthParams(words,challenge,pos=0):
	mode=None
	nWords=0
	name=None
	value=None
	while pos<len(words):
		word=words[pos]
		pos+=1
		if mode is None:
			if word[0] in HTTP_SEPARATORS:
				# Not a realm!
				break
			else:
				name=word
				mode='n'
		elif mode=='n':
			if word=='=':
				mode=word
			elif word[0] in HTTP_SEPARATORS:
				# strange, that was the last param
				break
			else:
				# another token means this is the start of the next challenge
				break	
		elif mode=='=':
			if word[0]==DQUOTE:
				value=DecodeQuotedString(word)
			elif word[0] in HTTP_SEPARATORS:
				break
			else:
				value=word
			challenge.SetAuthParam(name,value)
			nWords+=3
			mode=','
		elif mode==',':
			if word[0]==',':
				mode=None
				nWords+=1
			else:
				break
	return nWords


class Credentials:
	def __init__(self):
		self.scheme=None
		self.protectionSpace=None
		self.realm=None
	
	def Match(self,challenge):
		if self.scheme!=challenge.scheme:
			return False
		if self.protectionSpace!=challenge.protectionSpace:
			return False
		if self.realm:
			if self.realm!=challenge.realm:
				return False
		return True

		
class BasicCredentials(Credentials):
	def __init__(self):
		Credentials.__init__(self)
		self.scheme="Basic"
		self.userid=None
		self.password=None
	
	def SetBasicCredentials(self,basicCredentials):
		credentials=base64.b64decode(basicCredentials).split(':')
		if len(credentials)==2:
			self.userid,self.password=credentials
		else:
			raise HTTPInvalidBasicCredentials(basicCredentials)
			
	def __str__(self):
		format=[self.scheme,' ']
		if self.userid is not None and self.password is not None:
			format.append(base64.b64encode(self.userid+":"+self.password))
		return string.join(format,'')

		
