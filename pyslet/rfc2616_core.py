#! /usr/bin/env python

import string

def IsOCTET(c):
	return ord(c)<256

def IsCHAR(c):
	return ord(c)<128

def IsUPALPHA(c):
	return 'A'<=c and c<='Z'
	
def IsLOALPHA(c):
	return 'a'<=c and c<='z'

def IsALPHA(c):
	return IsUPALPHA(c) or IsLOALPHA(c)

def IsDIGIT(c):
	return '0'<=c and c<='9'

def IsCTL(c):
	return ord(c)<32 or ord(c)==127

CR=chr(13)
LF=chr(10)
HT=chr(9)
SP=chr(32)
DQUOTE=chr(34)

CRLF=CR+LF

HTTP_SEPARATORS='()<>@,;:\\"/[]?={} \t'


def ParseLWS(source,pos=0):
	"""Parse the source string (starting from pos) and return the amount of
	LWS parsed - returns 0 if no LWS is present"""
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
	"""Parse the source string (starting from pos) and return the number of
	TEXT characters parsed, including folded lines and LWS."""
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
	"""The source string is assumed to be legal TEXT, though it may in fact be spread
	across multiple lines separated by CRLF).  This function parses it and replaces any
	line folding sequences with a single SP.  A line folding sequence is a LWS that
	starts with a CRLF."""
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
	return IsDIGIT(c) or ('A'<=c and c<='F') or ('a'<=c and c<='f')

def SplitWords(source):
	"""Reading through source (which is assumed to be *unfolded* TEXT), this function
	splits it up into words.  The words are returned as a list of strings.
	A word may be a token, a single non-LWS separator, a comment or a quoted string.
	To determine the type of word, look at the first character.  A '(' means
	the word is a comment, a double quote means the word is an unencoded quoted
	string, other separator chars are just themselves (and only appear as
	single character strings).  Any other string is a token."""
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

def SplitItems(words,sep=","):
	# Splits the list of words by sep, leading and trailing empty items are preserved
	items=[]
	itemStart=0
	pos=0
	while pos<len(words):
		word=words[pos]
		if word==sep:
			items.append(words[itemStart:pos])
			itemStart=pos+1
		pos+=1
	if itemStart:
		# we found at least one sep
		items.append(words[itemStart:])
	else:
		# No instances of sep found at all
		items.append(words)
	return items
	
def DecodeQuotedString(qstring):
	# strip the quotes
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
	# We need to quote the quote character, and "
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
	"""Takes a tokenized string as a list or words and the position to start
	parsing from.  Returns the number of words parsed: i.e., 1 if a token is
	found at pos and 0 otherwise."""
	if pos<len(words):
		token=words[pos]
		if token[0] in HTTP_SEPARATORS:
			return 0
		else:
			return 1
	else:
		return 0

def ParseParameters(words,parameters,pos=0):
	"""Takes a tokenized string as a list of words, a dictionary in which to
	store the parsed parameters and the position from which to start parsing
	(defaulting to the first word).  Returns the number of words parsed."""
	mode=None
	nWords=0
	param=[]
	while pos<len(words):
		word=words[pos]
		pos+=1
		if mode is None:
			# Each parameter must be preceeded by a ';'
			if word==';':
				# Start of a parameter
				mode=word
			else:
				break
		elif mode==';':
			if word[0] in HTTP_SEPARATORS:
				# Not a token!
				break
			else:
				param.append(word)
				mode='p'
		elif mode=='p':
			if word=='=':
				mode=word
			else:
				break
		elif mode=='=':
			if word[0]==DQUOTE:
				# quoted string
				param.append(DecodeQuotedString(word))
			elif word[0] in HTTP_SEPARATORS:
				break
			else:
				param.append(word)
			parameters[param[0].lower()]=param
			param=[]
			nWords+=4
			mode=None
	return nWords
