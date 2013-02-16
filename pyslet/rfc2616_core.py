#! /usr/bin/env python

import string

class HTTPException(Exception):
	"""Abstract class for all HTTP errors."""
	pass

class HTTPParameterError(Exception):
	"""Raised when an expected parameter is missing."""
	pass


def IsOCTET(c):
	"""Given a character, returns True if it matches the production for OCTET.
	
	The HTTP protocol only deals with octets but as a convenience, and
	due to the blurring of octet and character strings in Python 2.x
	we process characters as if they were octets.""" 
	return ord(c)<256

def IsCHAR(c):
	"""Given a character returns True if it matches the production for CHAR."""
	return ord(c)<128

def IsUPALPHA(c):
	"""Given a character returns True if it matches the production for UPALPHA."""
	return ord('A')<=ord(c) and ord(c)<=ord('Z')
	
def IsLOALPHA(c):
	"""Given a character returns True if it matches the production for LOALPHA."""
	return ord('a')<=ord(c) and ord(c)<=ord('z')

def IsALPHA(c):
	"""Given a character returns True if it matches the production for ALPHA."""
	return IsUPALPHA(c) or IsLOALPHA(c)

def IsDIGIT(c):
	"""Given a character returns True if it matches the production for DIGIT."""
	return ord('0')<=ord(c) and ord(c)<=ord('9')

def IsDIGITS(src):
	"""Given a string, returns True if all characters match the production for DIGIT.
	
	Empty strings return False"""
	if src:
		for c in src:
			if not IsDIGIT(c):
				return False
		return True
	else:	
		return False
			
def IsCTL(c):
	"""Given a character returns True if it matches the production for CTL."""
	return ord(c)<32 or ord(c)==127

CR=chr(13)		#: octet 13 (carriage return)
LF=chr(10)		#: octet 10 (linefeed)
HT=chr(9)		#: octet 9 (horizontal tab)
SP=chr(32)		#: octet 32 (space)
DQUOTE=chr(34)	#: octet 34 (double quote)

CRLF=CR+LF		#: the string consisting of CR followed by LF

HTTP_SEPARATORS='()<>@,;:\\"/[]?={} \t'
"""A string consisting of all the HTTP separator characters.  Can be used like::

	if c in HTTP_SEPARATORS:
		# do something"""


def ParseLWS(source,pos=0):
	"""Parse the *source* string (starting from pos) for LWS
	
	Parses a single instance of the production LWS.  The return value is the
	length of the matching string or 0 if no LWS was found at *pos*."""
	lws=0
	mode=None
	while pos<len(source):
		c=source[pos]
		pos+=1
		if mode is None:
			if c==CR:
				mode=CR
			elif c==SP or c==HT:
				mode=SP
				lws+=1
			else:
				break
		elif mode==CR:
			if c==LF:
				mode=LF
			else:
				break
		elif mode==LF:
			if c==SP or c==HT:
				lws+=3
				mode=SP
			else:
				break
		# mode==SP
		elif c==SP or c==HT: 
			lws+=1
		else:
			break
	return lws
	

def ParseTEXT(source,pos=0):
	"""Parse the source string (starting from pos) for TEXT
	
	Parses a single instance of the production TEXT.  The return value is the
	length of the matching TEXT string (including any LWS) or 0 if no TEXT was
	found at *pos*."""
	text=0
	while pos<len(source):
		lws=ParseLWS(source,pos)
		if lws:
			pos+=lws
			text+=lws
		else:
			c=source[pos]
			pos+=1
			if IsOCTET(c) and not IsCTL(c):
				text+=1
			else:
				break
	return text


def UnfoldTEXT(source):
	"""Returns a new string equivalent to *source* with all folded lines unfolded.
	
	The source string is assumed to be legal TEXT so bare controls or other
	characters that are not allowed in TEXT may still appear in the output.
	
	Line folding sequences are replaced with a single SP.  A line folding
	sequence is a LWS that starts with a CRLF."""
	buffer=[]
	# mode is subtely differently from ParseLWS, we hold SP only when skipping after CRLF
	mode=None
	pos=0
	while pos<len(source):
		c=source[pos]
		pos+=1
		if mode is None:
			# Normal mode, e.g., following a non LWS char
			if c==CR:
				mode=CR
			else: # we assume good TEXT
				buffer.append(c)
		elif mode==CR:
			if c==LF:
				mode=LF
			else: # text with a bare CR, is bad but we pass on the CR and re-parse
				buffer.append(CR)
				mode=None
				pos=pos-1
		elif mode==LF:
			if c==SP or c==HT:
				mode=SP
			else: # a bare CRLF is not unfolded, change mode and re-parse
				buffer.append(CRLF)
				mode=None
				pos=pos-1
		# mode==SP
		elif c==SP or c==HT:
			continue
		else:
			buffer.append(SP)
			mode=None
			pos=pos-1
	# Clean up parser modes
	if mode==CR:
		buffer.append(CR)
	elif mode==LF:
		buffer.append(CRLF)
	elif mode==SP:
		# tricky one, source ends in an empty folded line!
		buffer.append(SP)
	return string.join(buffer,'')


def IsHEX(c):
	"""Given a character returns True if it matches the production for HEX."""
	return IsDIGIT(c) or (ord('A')<=ord(c) and ord(c)<=ord('F')) or (ord('a')<=ord(c) and ord(c)<=ord('f'))


def IsHEXDIGITS(c):
	"""Given a string, returns True if all characters match the production for HEX.
	
	Empty strings return False"""
	if src:
		for c in src:
			if not IsHEX(c):
				return False
		return True
	else:	
		return False


class WordParser(object):
	"""Splits a *source* string into words.
	
	*source* is assumed to be *unfolded* TEXT.
	
	By default the function ignores spaces according to the rules for implied
	*LWS in the specification and neither SP nor HT will be stored in the word
	list.  If you set *ignoreSpace* to False then LWS is not ignored and each
	run of LWS is returned as a single SP in the word list."""
	
	def __init__(self,source,ignoreSpace=True):
		self.words=[]
		"""The words are returned as a list of strings. A word may be a token, a
		single separator character, a comment or a quoted string.  To determine the
		type of word, look at the first character.
		
			*	'(' means the word is a comment, surrounded by '(' and ')'
			
			*	a double quote means the word is an unencoded quoted string (use
				py:func:`DecodeQuotedString` for how to decode it)
		
			*	other separator chars are just themselves and only appear as single
				character strings.  (HT is never returned.)
		
			*	Any other character indicates a token."""
		self.pos=0			#: a pointer to the current word in the list
		self.cWord=None		#: the current word or None
		self.InitParser(source,ignoreSpace)
		
	def InitParser(self,source,ignoreSpace=True):
		self.words=[]
		self.pos=0
		mode=None
		pos=0
		word=[]
		while pos<len(source):
			c=source[pos]
			pos+=1
			if mode is None:
				# Start mode
				if c in HTTP_SEPARATORS:
					if c==DQUOTE or c=='(':
						mode=c
						word.append(c)
					elif c==SP or c==HT:
						mode=SP
						if not ignoreSpace:
							self.words.append(SP)
					else:
						self.words.append(c)	
				else:
					word.append(c)
					mode='T'
			elif mode=='T':
				# Parsing a token
				if c in HTTP_SEPARATORS:
					# end the token and reparse
					self.words.append(string.join(word,''))
					word=[]
					mode=None
					pos=pos-1
				else:
					word.append(c)
			elif mode==SP:
				# Parsing a SP
				if c==SP or c==HT:
					continue
				else:
					# End of space separator, re-parse this char
					mode=None
					pos=pos-1
			elif mode==DQUOTE:
				word.append(c)
				if c==DQUOTE:
					self.words.append(string.join(word,''))
					word=[]
					mode=None
				elif c=='\\':
					mode='Q'
			elif mode=='(':
				word.append(c)
				if c==')':
					self.words.append(string.join(word,''))
					word=[]
					mode=None
				elif c=='\\':
					mode='q'
			elif mode=='Q':
				word.append(c)
				mode=DQUOTE
			elif mode=='q':
				word.append(c)
				mode='('
		# Once the parse is done, clean up the mode:
		if mode==DQUOTE or mode=='Q':
			# Be generous and close the quote for them
			word.append(DQUOTE)
		elif mode=='(' or mode=='q':
			# Likewise with the comment
			word.append(')')
		if word:
			self.words.append(string.join(word,''))
		if self.words:
			self.cWord=self.words[0]
		else:
			self.cWord=None

	def SetPos(self,pos):
		"""Sets the current position of the parser.
		
		Example usage for look-ahead::
		
			# wp is a WordParser instance
			savePos=wp.pos
			try:
				# parse a token/sub-token combination
				token=wp.RequireToken()
				wp.RequireSeparator('/')
				subtoken=wp.RequireToken()
				return token,subtoken
			except HTTPParameterError:
				wp.SetPos(savePos)
				return None,None"""
		self.pos=pos
		if self.pos<len(self.words):
			self.cWord=self.words[self.pos]
		else:
			self.cWord=None
		
	def Error(self,expected):
		if self.cWord:
			raise HTTPParameterError("Expected %s, found %s"%(expected,repr(self.cWord)))
		else:
			raise HTTPParameterError("Expected %s"%expected)
	
	def ParseWord(self):
		"""Parses any word from the list returning the word consumed by the parser"""
		result=self.cWord
		self.pos+=1
		if self.pos<len(self.words):
			self.cWord=self.words[self.pos]
		else:
			self.cWord=None
		return result
		
	def IsToken(self):
		"""Returns True if the current word is a token"""
		return self.cWord and self.cWord[0] not in HTTP_SEPARATORS
	
	def ParseToken(self):
		"""Parses a token from the list of words, returning the token or None."""
		if self.IsToken():
			return self.ParseWord()
		else:
			return None	
	
	def RequireToken(self,expected="token"):
		"""Returns the current token or raises HTTPParameterError.

		*	*expected* can be set to the name of the expected object."""
		token=self.ParseToken()
		if token is None:
			self.Error(expected)
		else:
			return token
	
	def IsInteger(self):
		"""Returns True if the current word is an integer token"""
		return self.cWord and IsDIGITS(self.cWord)
	
	def ParseInteger(self):
		"""Parses an integer from the list of words, returning the integer value or None."""
		if self.IsInteger():
			return int(self.ParseWord())
		else:
			return None	
	
	def RequireInteger(self,expected="integer"):
		"""Parses an integer or raises HTTPParameterError.

		*	*expected* can be set to the name of the expected object."""
		result=self.ParseInteger()
		if result is None:
			self.Error(expected)
		else:
			return result
	
	def ParseQualityValue(self):
		"""Parses a q-value from the list of words returning the float equivalent value or None."""
		if self.IsToken():
			q=None
			qSplit=self.cWord.split('.')
			if len(qSplit)==1:
				if IsDIGITS(qSplit[0]):
					q=float(qSplit[0])
			elif len(qSplit)==2:
				if IsDIGITS(qSplit[0]) and IsDIGITS(qSplit[1]):
					q=float("%.3f"%float(self.cWord))
			if q is None or q>1.0:
				return None
			else:
				self.ParseWord()
				return q
		else:
			return None
	
	def IsSeparator(self,sep):
		"""Returns True if the current word matches *sep*"""
		return self.cWord==sep

	def ParseSeparator(self,sep):
		"""Parses a *sep* from the list of words.
		
		Returns True if the current word matches *sep* and False otherwise."""
		if self.cWord==sep:
			self.ParseWord()
			return True
		else:
			return False
			
	def RequireSeparator(self,sep,expected=None):
		"""Parses *sep* or raises HTTPParameterError.

		*	*expected* can be set to the name of the expected object."""
		if self.cWord==sep:
			self.ParseWord()
		else:
			self.Error(expected)
			
	def IsQuotedString(self):
		"""Returns True if the current word is a quoted string."""
		return self.cWord and self.cWord[0]==DQUOTE

	def ParseQuotedString(self):
		"""Parses a quoted string from the list of words.
		
		Returns the *unencoded* quoted string or None."""
		if self.IsQuotedString():
			return DecodeQuotedString(self.ParseWord())
		else:
			return None
			
	def ParseSP(self):
		"""Parses a SP from the list of words.
		
		Returns True if the current word is a SP and False otherwise."""
		return self.ParseSeparator(SP)

	def ParseParameters(self,parameters,ignoreAllSpace=True,caseSensitive=False,qMode=None):
		"""Parses a set of parameters from a list of words.
		
			*	*parameters* is the dictionary in which to store the parsed parameters
				
			*	*ignoreAllSpace* is a boolean (defaults to True) which causes the
				function to ignore all LWS in the word list.  If set to False then space
				around the '=' separator is treated as an error and raises HTTPParameterError.
			
			*	caseSensitive controls whether parameter names are treated as case
				sensitive, defaults to False.
				
			*	qMode allows you to pass a special parameter name that will
				terminate parameter parsing (without being parsed itself).  This is
				used to support headers such as the "Accept" header in which the
				parameter called "q" marks the boundary between media-type
				parameters and Accept extension parameters.
				 
		Updates the parameters dictionary with the new parameter definitions.
		The key in the dictionary is the parameter name (converted to lower case
		if parameters are being dealt with case insensitively) and the value is
		a 2-item list of [ name, value ] always preserving the original case of
		the parameter name."""
		self.ParseSP()
		while self.cWord:
			savePos=self.pos
			try:
				self.ParseSP()
				self.RequireSeparator(';')
				self.ParseSP()
				paramName=self.RequireToken("parameter")
				if not caseSensitive:
					paramKey=paramName.lower()
				else:
					paramKey=paramName
				if qMode and paramKey==qMode:
					raise HTTPParameterError
				if ignoreAllSpace:
					self.ParseSP()
				self.RequireSeparator('=',"parameter")
				if ignoreAllSpace:
					self.ParseSP()
				if self.IsToken():
					paramValue=self.ParseToken()
				elif self.IsQuotedString():
					paramValue=self.ParseQuotedString()
				else:
					self.Error("parameter value")
				parameters[paramKey]=[paramName,paramValue]
			except HTTPParameterError:
				self.SetPos(savePos)
				break
	
	def ParseRemainder(self,sep=''):
		"""Parses the rest of the words, joining them into a single string with *sep*.
		
		Returns an empty string if the parser is at the end of the word list."""
		if self.cWord:
			result=string.join(self.words[self.pos:],sep)
		else:
			result=''
		self.SetPos(len(self.words))
		return result
				
	def RequireEnd(self,production=None):
		"""Raises HTTPParameterError unless the parser is at the end of the word list.

		*	*production* is an optional name for the production being parsed."""
		if self.cWord:
			if production:
				raise HTTPParameterError("Spurious data after %s: found %s"%(production,repr(self.cWord)))
			else:
				raise HTTPParameterError("Spurious data: %s"%repr(self.cWord))


def SplitWords(source,ignoreSpace=True):
	"""Splits a *source* string into words.
	
	*source* is assumed to be *unfolded* TEXT.
	
	The words are returned as a list of strings. A word may be a token, a single
	separator character, a comment or a quoted string.  To determine the type of
	word, look at the first character.
	
		*	'(' means the word is a comment, surrounded by '(' and ')'
		
		*	a double quote means the word is an unencoded quoted string (use
			py:func:`DecodeQuotedString` for how to decode it)
	
		*	other separator chars are just themselves and only appear as single
			character strings.  (HT is never returned.)
	
		*	Any other character indicates a token.

	By default the function ignores spaces according to the rules for implied
	*LWS in the specification and neither SP nor HT will be returned in the word
	list.  If you set *ignoreSpace* to False then LWS is not ignored and each
	run of LWS is returned as a single SP in the resulting word list."""
	mode=None
	pos=0
	words=[]
	word=[]
	while pos<len(source):
		c=source[pos]
		pos+=1
		if mode is None:
			# Start mode
			if c in HTTP_SEPARATORS:
				if c==DQUOTE or c=='(':
					mode=c
					word.append(c)
				elif c==SP or c==HT:
					mode=SP
					if not ignoreSpace:
						words.append(SP)
				else:
					words.append(c)	
			else:
				word.append(c)
				mode='T'
		elif mode=='T':
			# Parsing a token
			if c in HTTP_SEPARATORS:
				# end the token and reparse
				words.append(string.join(word,''))
				word=[]
				mode=None
				pos=pos-1
			else:
				word.append(c)
		elif mode==SP:
			# Parsing a SP
			if c==SP or c==HT:
				continue
			else:
				# End of space separator, re-parse this char
				mode=None
				pos=pos-1
		elif mode==DQUOTE:
			word.append(c)
			if c==DQUOTE:
				words.append(string.join(word,''))
				word=[]
				mode=None
			elif c=='\\':
				mode='Q'
		elif mode=='(':
			word.append(c)
			if c==')':
				words.append(string.join(word,''))
				word=[]
				mode=None
			elif c=='\\':
				mode='q'
		elif mode=='Q':
			word.append(c)
			mode=DQUOTE
		elif mode=='q':
			word.append(c)
			mode='('
	# Once the parse is done, clean up the mode:
	if mode==DQUOTE or mode=='Q':
		# Be generous and close the quote for them
		word.append(DQUOTE)
	elif mode=='(' or mode=='q':
		# Likewise with the comment
		word.append(')')
	if word:
		words.append(string.join(word,''))
	return words


def SplitItems(words,sep=",",ignoreNulls=True):
	"""Splits a word list into a list of words lists representing separate items.
	
	*	words is a word list such as that returned by :py:func:`SplitWords`
	
	*	sep is the separator to use for splitting the words, it defaults to ","
	
	*	ignoreNulls controls the output of empty items (defaults to True)
	
	If ignoreNulls is False, empty items are added to the result as empty lists.
	For example::
	
		>>> import pyslet.rfc2616 as http
		>>> http.SplitItems(http.SplitWords(", Mr Brown, Mr Pink, Mr Orange,"),',',False)
		[[], ['Mr', 'Brown'], ['Mr', 'Pink'], ['Mr', 'Orange'], []]
		>>> http.SplitItems(http.SplitWords(", Mr Brown, Mr Pink, Mr Orange,"))
		[['Mr', 'Brown'], ['Mr', 'Pink'], ['Mr', 'Orange']]
	
	If words is empty an empty list is always returned."""		
	items=[]
	itemStart=0
	pos=0
	while pos<len(words):
		word=words[pos]
		if word==sep:
			if pos>itemStart or not ignoreNulls:
				items.append(words[itemStart:pos])
			itemStart=pos+1
		pos+=1
	if itemStart:
		# we found at least one sep
		if itemStart<len(words) or not ignoreNulls:
			items.append(words[itemStart:])
	else:
		# No instances of sep found at all
		if words:
			items.append(words)
	return items

	
def DecodeQuotedString(qstring):
	"""Decodes a quoted string, returning the unencoded string.
	
	Surrounding double quotes are removed and quoted characters (characters
	preceded by \\) are unescaped."""
	qstring=qstring[1:-1]
	# string the qpairs
	if qstring.find('\\')>=0:
		qbuff=[]
		mode=None
		for c in qstring:
			if mode==None and c=='\\':
				mode=c
				continue
			qbuff.append(c)
			mode=None
		return string.join(qbuff,'')
	else:
		return qstring


def QuoteString(s):
	"""Places a string in double quotes, returning the quoted string.
	
	This is the reverse of :py:func:`DecodeQuotedString`.  Note that only the
	double quote and \\ characters are quoted in the output."""
	qstring=['"']
	for c in s:
		if c=='\\':
			qstring.append('\\\\')
		elif c=='"':
			qstring.append('\\"')
		else:
			qstring.append(c)
	qstring.append('"')
	return string.join(qstring,'')

	
def ParseToken(words,pos=0):
	"""Parses a token from a list of words (starting at *pos*).
	
	Returns 1 if the word at position *pos* is a token and 0 otherwise."""
	if pos<len(words):
		token=words[pos]
		if token[0] in HTTP_SEPARATORS:
			return 0
		else:
			return 1
	else:
		return 0


def ParseSP(words,pos=0):
	"""Parses a SP from a list of words (starting at *pos*).
	
	Returns 1 if the word at position *pos* is a SP and 0 otherwise."""
	if pos<len(words):
		if words[pos]==SP:
			return 1
		else:
			return 0
	else:
		return 0


def ParseParameters(words,parameters,pos=0,ignoreAllSpace=True,caseSensitive=False,qMode=None):
	"""Parses a set of parameters from a list of words.
	
		*	*parameters* is the dictionary in which to store the parsed parameters
			
		*	*pos* is the position from which to start parsing (defaults to 0)
			
		*	*ignoreAllSpace* is a boolean (defaults to True) which causes the
			function to ignore all LWS in the word list.  If set to False then space
			around the '=' separator is treated as an error and raises HTTPParameterError.
		
		*	caseSensitive controls whether parameter names are treated as case
			sensitive, defaults to False.
			
		*	qMode allows you to pass a special parameter name that will
			terminate parameter parsing (without being parsed itself).  This is
			used to support headers such as the "Accept" header in which the
			parameter called "q" marks the boundary between media-type
			parameters and Accept extension parameters.
			 
	Returns the number of words parsed and updates the parameters dictionary
	with the new parameter definitions.  The key in the dictionary is the
	parameter name (converted to lower case if parameters are being dealt with
	case insensitively) and the value is a 2-item list of [ name, value ]
	preserving the original case of the parameter name."""
	mode=None
	param=[]
	startPos=pos
	nWords=0
	while pos<len(words):
		word=words[pos]
		pos+=1
		if mode is None:
			if word==SP:
				pass
			# Each parameter must be preceded by a ';'
			elif word==';':
				# Start of a parameter perhaps
				mode=word
				badSpace=False
			else:
				break
		elif mode==';':
			if word==SP:
				pass
			elif word[0] in HTTP_SEPARATORS:
				# Not a token!
				break
			else:
				# token
				if qMode is None or word!=qMode:
					param.append(word)
					mode='p'
				else:
					# we've found the q-parameter, we're done
					break
		elif mode=='p':
			if word==SP:
				badSpace=True
			elif word=='=':
				mode=word
			else:
				break
		elif mode=='=':
			if word==SP:
				badSpace=True
				continue
			elif word[0]==DQUOTE:
				# quoted string
				param.append(DecodeQuotedString(word))
			elif word[0] in HTTP_SEPARATORS:
				break
			else:
				# token
				param.append(word)
			if badSpace and not ignoreAllSpace:
				raise HTTPParameterError("LWS not allowed between parameter name and value: %s"%string.join(words,''))
			if caseSensitive:
				parameters[param[0]]=param
			else:
				parameters[param[0].lower()]=param
			param=[]
			nWords=pos-startPos
			mode=None
	return nWords


def FormatParameters(parameters):
	keys=parameters.keys()
	keys.sort()
	format=[]
	for k in keys:
		format.append('; ')
		p,v=parameters[k]
		format.append(p)
		format.append('=')
		words=SplitWords(v)
		if len(words)==1 and ParseToken(words)==1:
			# We have a token, no need to escape
			format.append(v)
		else:
			format.append(QuoteString(v))
	return string.join(format,'')
		
