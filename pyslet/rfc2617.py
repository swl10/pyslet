#! /usr/bin/env python


import string, base64
import pyslet.rfc2396 as uri
from pyslet.rfc2616_core import *


class HTTPUnknownAuthParam(Exception): pass

class Challenge(object):
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


class Credentials(object):
	def __init__(self):
		self.scheme=None
		self.protectionSpace=None
		self.realm=None
	
	def Match(self,challenge=None,url=None):
		if challenge is None:
			raise ValueError("Generic credentials cannot be matched against a URL")
		if self.scheme!=challenge.scheme:
			return False
		if self.protectionSpace!=challenge.protectionSpace:
			return False
		if self.realm:
			if self.realm!=challenge.realm:
				return False
		return True

	@classmethod
	def FromHeader(cls,wp):
		scheme=wp.RequireToken("Authentication Scheme").lower()
		if scheme=="basic":
			# the rest of the words represent the credentials as a base64 string
			credentials=BasicCredentials()
			credentials.SetBasicCredentials(wp.ParseRemainder())
		else:
			raise NotImplementedError
		return credentials

	@classmethod
	def FromHTTPString(cls,source):
		"""Constructs a :py:class:`Credentials` instance from an HTTP
		formatted string."""
		wp=WordParser(source)
		credentials=cls.FromWords(wp)
		wp.RequireEnd("authorization header")
		return credentials
				

class BasicCredentials(Credentials):
	def __init__(self):
		Credentials.__init__(self)
		self.scheme="Basic"
		self.userid=None
		self.password=None
		self.pathPrefixes=[]	#: a list of path-prefixes for which these credentials are known to be good 
		
	def SetBasicCredentials(self,basicCredentials):
		credentials=base64.b64decode(basicCredentials).split(':')
		if len(credentials)==2:
			self.userid,self.password=credentials
		else:
			raise HTTPInvalidBasicCredentials(basicCredentials)

	def Match(self,challenge=None,url=None):
		if challenge is not None:
			# must match the challenge
			if not super(BasicCredentials,self).Match(challenge):
				return False
		if url is not None:
			# must match the url
			if not self.TestURL(url):
				return False
		elif challenge is None:
			raise ValueError("BasicCredentials must be matched to a challenge or a URL")
		return True

	def TestURL(self,url):
		"""Given a :py:class:`~pyslet.rfc2396.URI` instance representing
		an absolute URI, checks if these credentials contain a matching
		protection space and path prefix."""
		if not url.IsAbsolute():
			raise ValueError("TestURL requires an absolute URL")
		if self.protectionSpace==url.GetCanonicalRoot() and self.TestPath(url.absPath):
			return True
		else:
			return False
		
	def TestPath(self,path):
		"""Returns True if there is a path prefix that matches *path*"""
		path=uri.SplitPath(path)
		uri.NormalizeSegments(path)
		for p in self.pathPrefixes:
			if self.IsPrefix(p,path):
				return True
		return False

	def AddSuccessPath(self,path):
		"""Adds *pathPrefix* to the list of path prefixes that these
		credentials apply to.

		If pathPrefix is a more general prefix than an existing prefix
		in the list then it replaces that prefix."""
		newPrefix=uri.SplitPath(path)
		uri.NormalizeSegments(newPrefix)
		keep=True
		i=0
		while i<len(self.pathPrefixes):
			p=self.pathPrefixes[i]
			# p could be a prefix of newPrefix
			if self.IsPrefix(p,newPrefix):
				keep=False
				break
			elif self.IsPrefix(newPrefix,p):
				# newPrefix could be a prefix of p
				del self.pathPrefixes[i]
				continue
			i=i+1
		if keep:
			self.pathPrefixes.append(newPrefix)
	
	def IsPrefix(self,prefix,path):
		if len(prefix)>len(path):
			return False
		i=0
		while i<len(prefix):
			# note that an empty segment matches anything (except nothing)
			if prefix[i] and prefix[i]!=path[i]:
				return False
			i=i+1
		return True
					
	def __str__(self):
		format=[self.scheme,' ']
		if self.userid is not None and self.password is not None:
			format.append(base64.b64encode(self.userid+":"+self.password))
		return string.join(format,'')

		
