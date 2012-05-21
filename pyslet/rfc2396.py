#! /usr/bin/env python
"""This module implements the URI specification defined in RFC 2396

References:
"""
import string, os, os.path, sys
from types import UnicodeType, StringType
from pyslet.rfc1738 import *

class URIException(Exception): pass
class URIRelativeError(URIException): pass


def IsUpAlpha(c):
	return c and (ord(c)>=0x41 and ord(c)<=0x5A)
	
def IsLowAlpha(c):
	return c and (ord(c)>=0x61 and ord(c)<=0x7A)

def IsAlpha(c):
	return IsUpAlpha(c) or IsLowAlpha(c)

def IsDigit(c):
	return c and (ord(c)>=0x30 and ord(c)<=0x39)

def IsAlphaNum(c):
	return IsUpAlpha(c) or IsLowAlpha(c) or IsDigit(c)

def IsReserved(c):
	return c and ord(c) in (0x3B,0x2F,0x3F,0x3A,0x40,0x26,0x3D,0x2B,0x24,0x2C) # ;/?:@&=+$,
	
def IsUnreserved(c):
	return IsAlphaNum(c) or IsMark(c)
	
def IsMark(c):
	return c and ord(c) in (0x2D,0x5F,0x2E,0x21,0x7E,0x2A,0x27,0x28,0x29)  # -_.!~*'()

def IsHex(c):
	return c and (IsDigit(c) or (ord(c)>=0x41 and ord(c)<=0x46) or (ord(c)>=0x61 and ord(c)<=0x66))
	
def IsControl(c):
	return c and (ord(c)<0x20 or ord(c)==0x7F)

def IsSpace(c):
	return c and ord(c)==0x20

def IsDelims(c):
	return c and ord(c) in (0x3C,0x3E,0x23,0x25,0x22)

def IsUnwise(c):
	return c and ord(c) in (0x7B,0x7D,0x7C,0x5C,0x5E,0x5B,0x5D,0x60)

def IsSchemeChar(c):
	return IsAlphaNum(c) or (c and ord(c) in (0x2B,0x2D,0x2E))

def IsAuthorityReserved(c):
	return (c and ord(c) in (0x3B,0x3A,0x40,0x3F,0x2F))

def ParseURIC(source,pos=0):
	"""Parse the source string (starting from pos) and return the number
	of URI characters (uric) parsed"""
	uric=0
	mode=None
	while pos<len(source):
		c=source[pos]
		pos+=1
		if mode is None:
			if IsReserved(c) or IsUnreserved(c):
				uric+=1
			elif ord(c)==0x25: # % escape
				mode='%'
			else:
				break
		elif mode=='%':
			if IsHex(c):
				mode=c
			else:
				break
		else:
			if IsHex(c):
				mode=None
				uric+=3
			else:
				break
	return uric


def ParseScheme(octets):
	pos=0
	scheme=None
	while pos<len(octets):
		c=octets[pos]
		if (pos and IsSchemeChar(c)) or IsAlpha(c):
			pos+=1
		else:
			if ord(c)==0x3A:
				# we have the scheme
				scheme=octets[0:pos]
			break
	return scheme


def EscapeData(source,reservedFunction=IsReserved):
	result=[]
	for c in source:
		if reservedFunction(c) or not (IsUnreserved(c) or IsReserved(c)):
			# short-circuit boolean means we don't evaluate IsReserved twice in default case
			result.append("%%%02X"%ord(c))
		else:
			result.append(c)
	return string.join(result,'')


def UnescapeData(source):
	data=[]
	mode=None
	pos=0
	while pos<len(source):
		c=source[pos]
		pos+=1
		if mode is None:
			if ord(c)==0x25:
				mode='%'
			else:
				data.append(c)
		elif mode=='%':
			if IsHex(c):
				mode=c
			else:
				data.append('%')
				data.append(c)
				mode=None
		else:
			if IsHex(c):
				data.append(chr(int(mode+c,16)))
			else:
				data.append('%')
				data.append(mode)
			mode=None
	return string.join(data,'')


def SplitServer(authority):
	userinfo=None
	host=None
	port=None
	if authority is not None:
		if authority:
			mode=None
			pos=0
			while True:
				if pos<len(authority):
					c=authority[pos]
				else:
					c=None
				if mode is None:
					if c is None:
						host=authority
						break
					elif ord(c)==0x40:
						userinfo=authority[:pos]
						mode='h'
						hStart=pos+1
					elif ord(c)==0x3A:
						# could be in userinfo or start of port
						host=authority[:pos]
						mode='p'
						pStart=pos+1
					pos+=1
				elif mode=='h':
					if c is None:
						host=authority[hStart:]
						break
					elif ord(c)==0x3A:
						host=authority[hStart:pos]
						mode='p'
						pStart=pos+1
					pos+=1
				elif mode=='p':
					if c is None:
						port=authority[pStart:]
						break
					elif ord(c)==0x40 and userinfo is None:
						# must have been username:pass@
						userinfo=authority[:pos]
						host=None
						mode='h'
						hStart=pos+1
					elif not IsDigit(c):
						if userinfo is None:
							# probably username:pass...
							host=None
							mode='u'
						else:
							# userinfo@host:123XX - bad port, stop parsing
							port=authority[pStart:pos]
							break
					pos+=1
				elif mode=='u':
					# username:pass...
					if c is None:
						userinfo=authority
						host=''
						break
					elif ord(c)==0x40:
						userinfo=authority[:pos]
						mode='h'
						hStart=pos+1
					pos+=1
		else:
			host=''
	return userinfo,host,port

def IsPathSegmentReserved(c):
	return (c and ord(c) in (0x2F,0x3B,0x3D,0x3F))

def SplitPath(path,absPath=True):
	segments=[]
	if path:
		pos=0
		if absPath:
			segStart=None
		else:
			segStart=0
		while True:
			if pos<len(path):
				c=path[pos]
				if ord(c)==0x2F:
					if segStart is not None:
						segments.append(path[segStart:pos])
					segStart=pos+1
				pos+=1
			else:
				if segStart is not None:
					segments.append(path[segStart:pos])
				break
	elif not absPath:
		# relative paths always have an empty segment
		segments.append('')
	return segments

def SplitAbsPath(absPath):
	return SplitPath(absPath,True)

def SplitRelPath(relPath):
	return SplitPath(relPath,False)

def NormalizeSegments(pathSegments):
	"""Normalizes a list of pathSegments, as returned by Split*Path methods.
	
	Normalizing follows the rules for resolving relative URI paths, './'
	and trailing '.' are removed, 'seg/../' and trailing seg/.. are
	also removed."""
	i=0
	while i<len(pathSegments):
		if pathSegments[i]=='.':
			if i+1>=len(pathSegments):
				pathSegments[i]=''
			else:
				del pathSegments[i]
		elif pathSegments[i]=='..' and (i>0 and pathSegments[i-1]!='..'):
			if i+1>=len(pathSegments):
				pathSegments[i]=''
				del pathSegments[i-1]
			else:
				del pathSegments[i]
				del pathSegments[i-1]
				i-=1
		else:
			i+=1
	if pathSegments and pathSegments[-1]=='..':
		# special case of trailing '..' gets an extra slash for consistency
		pathSegments.append('')
		
def RelativizeSegments(pathSegments,baseSegments):
	result=[]
	pos=0
	while pos<len(baseSegments):
		if result:
			result=['..']+result
		else:
			if pos>=len(pathSegments) or baseSegments[pos]!=pathSegments[pos]:
				result=result+pathSegments[pos:]
		pos=pos+1
	if not result and len(pathSegments)>len(baseSegments):
		# full match but pathSegments is longer
		return pathSegments[len(baseSegments)-1:]
	elif result==['']:
		return ['.']+result
	else:
		return result
	
def MakeRelPathAbs(absPath,basePath):
	"""Return absPath relative to basePath"""
	pathSegments=SplitAbsPath(absPath)
	NormalizeSegments(pathSegments)
	baseSegments=SplitAbsPath(basePath)
	NormalizeSegments(baseSegments)
	result=RelativizeSegments(pathSegments,baseSegments)
	return string.join(result,'/')

def MakeRelPathRel(relPath,baseRelPath):
	"""Return relPath relative to baseRelPath"""
	pathSegments=SplitRelPath(relPath)
	NormalizeSegments(pathSegments)
	baseSegments=SplitRelPath(baseRelPath)
	NormalizeSegments(baseSegments)
	# At this point there are no '.' components, but there may be leading '..'
	i=0
	while i<len(pathSegments):
		if pathSegments[i]=='..':
			i+=1
		else:
			break
	j=0
	while j<len(baseSegments):
		if baseSegments[j]=='..':
			j+=1
		else:
			break
	if j>i:
		i=j
	if i:
		# we have leading '..' components, add a common path prefix and re-normalize
		pathSegments=['x']*i+pathSegments
		NormalizeSegments(pathSegments)
		baseSegments=['x']*i+baseSegments
		NormalizeSegments(baseSegments)
	result=RelativizeSegments(pathSegments,baseSegments)
	return string.join(result,'/')


def SplitPathSegment(segment):
	pchar=''
	params=[]
	pos=0
	mode=None
	while True:
		if pos<len(segment):
			c=segment[pos]
		else:
			c=None
		if mode is None:
			if c is None:
				pchar=segment
				break
			elif ord(c)==0x3B:
				mode=';'
				pchar=segment[:pos]
				pStart=pos+1
			pos+=1
		elif mode==';':
			if c is None:
				params.append(segment[pStart:])
				break
			elif ord(c)==0x3B:
				params.append(segment[pStart:pos])
				pStart=pos+1
			pos+=1
	return pchar,params


def IsQueryReserved(c):
	return (c and ord(c) in (0x3B,0x2F,0x3F,0x3A,0x40,0x26,0x3D,0x2B,0x2C,0x24))
	

def EncodeUnicodeURI(uSrc):
	"""Takes a unicode string that is supposed to be a URI and returns an octent string.
	
	The encoding algorithm used is the same as the one adopted by HTML: utf-8
	and then %-escape. This is not part of the RFC standard which only defines
	the behaviour for streams of octets."""
	octets=[]
	for c in uSrc:
		if ord(c)>0x7F:
			octets=octets+map(lambda x:"%%%2X"%ord(x),c.encode('UTF-8'))
			clean=False
		else:
			octets.append(chr(ord(c)))
	return string.join(octets,'')

	
class URI:
	"""Class to represent URI Reference."""
			
	def __init__(self,octets):
		if type(octets) is UnicodeType:
			octets=EncodeUnicodeURI(octets)
		uriLen=ParseURIC(octets)
		self.octets=octets[0:uriLen]
		"""The octet string representing this URI."""
		self.fragment=None
		"""The fragment string that was appended to the URI or None if no fragment was given."""
		if uriLen<len(octets):
			if ord(octets[uriLen])==0x23:
				self.fragment=octets[uriLen+1:]
		self.scheme=ParseScheme(self.octets)
		"""The URI scheme, if present."""
		self.schemeSpecificPart=None
		"""The scheme specific part of the URI."""
		if self.scheme is not None:
			self.schemeSpecificPart=self.octets[len(self.scheme)+1:]
		if self.IsAbsolute():
			self.relPath=None
			self.ParseSchemeSpecificPart()
		else:
			self.opaquePart=None
			self.ParseRelativeURI()
			
	def ParseSchemeSpecificPart(self):
		pos=0
		mode=':'
		self.opaquePart=self.authority=self.absPath=self.query=None
		while True:
			if pos<len(self.schemeSpecificPart):
				c=self.schemeSpecificPart[pos]
			else:
				c=None
			if mode==':':
				# Is this a hier_part or opaque_part?
				if c is None:
					# Empty scheme-specific part; neither opaque nor hierarchical
					break
				elif ord(c)==0x2F:
					mode='/'
				else:
					self.opaquePart=self.schemeSpecificPart
					break
				pos+=1
			elif mode=='/':
				# Is this a net_path or abs_path
				if c is None:
					# Single '/' is an abs_path
					self.absPath='/'
					break
				elif ord(c)==0x2F:
					mode='a'
					aStart=pos+1
				else:
					mode='p'
					pStart=pos-1
				pos+=1
			elif mode=='a':
				# parse authority
				if c is None:
					self.authority=self.schemeSpecificPart[aStart:pos]					
					break
				elif ord(c)==0x2F:
					self.authority=self.schemeSpecificPart[aStart:pos]					
					mode='p'
					pStart=pos
				elif ord(c)==0x3F:
					self.authority=self.schemeSpecificPart[aStart:pos]
					mode='?'
					qStart=pos+1
				pos+=1
			elif mode=='p':
				# parse absPath
				if c is None:
					self.absPath=self.schemeSpecificPart[pStart:pos]
					break
				elif ord(c)==0x3F:
					self.absPath=self.schemeSpecificPart[pStart:pos]
					mode='?'
					qStart=pos+1
				pos+=1
			elif mode=='?':
				# query string is everything up to the end of the URI
				if c is None:
					self.query=self.schemeSpecificPart[qStart:pos]
					break
				pos+=1
				
	def ParseRelativeURI(self):
		pos=0
		self.authority=self.absPath=self.relPath=self.query=None
		mode=None
		while True:
			if pos<len(self.octets):
				c=self.octets[pos]
			else:
				c=None
			if mode is None:
				# net_path, abs_path or rel_path ?
				if c is None:
					# An empty URI is a same document reference
					self.relPath=''
					break
				elif ord(c)==0x2F:
					mode='/'
				elif ord(c)==0x3F:
					# the RFC is ambiguous here, seems relPath can be empty afterall
					self.relPath=''
					mode='?'
					qStart=pos+1
				else:
					mode='r'
					rStart=pos
				pos+=1
			elif mode=='/':
				# Is this a net_path or abs_path
				if c is None:
					# Single '/' is an abs_path
					self.absPath='/'
					break
				elif ord(c)==0x2F:
					mode='a'
					aStart=pos+1
				else:
					mode='p'
					pStart=pos-1
				pos+=1
			elif mode=='a':
				# parse authority
				if c is None:
					self.authority=self.octets[aStart:pos]					
					break
				elif ord(c)==0x2F:
					self.authority=self.octets[aStart:pos]					
					mode='p'
					pStart=pos
				elif ord(c)==0x3F:
					self.authority=self.octets[aStart:pos]
					mode='?'
					qStart=pos+1
				pos+=1
			elif mode=='p':
				# parse absPath
				if c is None:
					self.absPath=self.octets[pStart:pos]
					break
				elif ord(c)==0x3F:
					self.absPath=self.octets[pStart:pos]
					mode='?'
					qStart=pos+1
				pos+=1
			elif mode=='r':
				# parse relPath
				if c is None:
					self.relPath=self.octets[rStart:pos]
					break
				elif ord(c)==0x3F:
					self.relPath=self.octets[rStart:pos]
					mode='?'
					qStart=pos+1
				pos+=1
			elif mode=='?':
				# query string is everything up to the end of the URI
				if c is None:
					self.query=self.octets[qStart:pos]
					break
				pos+=1

	def GetFileName(self):
		"""Returns the file name associated with this resource or None if the
		URL scheme does not have the concept.  By default the file name is
		extracted from the last component of the path. Note the subtle
		difference between returning None and returning an empty string
		(indicating that the URI represents a directory-like object)."""
		if self.absPath:
			segments=SplitAbsPath(self.absPath)
		elif self.relPath:
			segments=SplitRelPath(self.relPath)
		else:
			segments=[]
		fileName=None
		# we loop around until we have a non-empty fileName
		while fileName is None:
			if segments:
				fileName=segments.pop()
			else:
				break
		if fileName is not None:
			fileName=unicode(UnescapeData(fileName),'utf-8')
			return fileName
		else:
			return None
		
	def Resolve(self,base,current=None):
		"""Resolves the current (relative) URI relative to base
		
		If the current URI is also relative then the result is a relative URI,
		otherwise the result is an absolute URI.  The RFC does not actually go
		into the procedure for combining relative URIs but if B is an absolute
		URI and R1 and R2 are relative URIs then using the resolve operator::
		
			U1 = B [*] R1
			U2 = U1 [*] R2
			U2 = ( B [*] R1 ) [*] R2
		
		The last expression prompts the issue of associativity, in other words,
		is the following expression also valid? ::
		
			U2 = B [*] ( R1 [*] R2 )
		
		For this to work it must be possible to use the resolve operator to
		combine two relative URIs to make a third, which is what we allow
		here."""
		if current is None:
			current=base
		if not(self.absPath or self.relPath) and self.scheme is None and self.authority is None and self.query is None:
			# current document reference, just change the fragment
			if self.fragment is None:
				return URIFactory.URI(current.octets)
			else:
				return URIFactory.URI(current.octets+'#'+self.fragment)
		if self.scheme is not None:
			return URIFactory.URI(str(self))
		scheme=base.scheme
		authority=None
		if self.authority is None:
			authority=base.authority
			if self.absPath is None:
				if base.absPath is not None:
					segments=SplitAbsPath(base.absPath)[:-1]
					segments=segments+SplitRelPath(self.relPath)
					NormalizeSegments(segments)
					absPath='/'+string.join(segments,'/')
					relPath=None
				else:
					segments=SplitRelPath(base.relPath)[:-1]
					segments=segments+SplitRelPath(self.relPath)
					NormalizeSegments(segments)
					absPath=None
					relPath=string.join(segments,'/')
					if relPath=='':
						# degenerate case, as we are relative we won't prefix with /
						relPath='./'
			else:
				absPath=self.absPath
				relPath=None
		else:
			authority=self.authority
			absPath=self.absPath
			relPath=None
		result=[]
		if scheme is not None:
			result.append(scheme)
			result.append(':')
		if authority is not None:
			result.append('//')
			result.append(authority)
		if absPath is not None:
			result.append(absPath)
		elif relPath is not None:
			result.append(relPath)
		if self.query is not None:
			result.append('?')
			result.append(self.query)
		if self.fragment is not None:
			result.append('#')
			result.append(self.fragment)
		return URIFactory.URI(string.join(result,''))
	
	def Relative(self,base):
		"""Evaluates the Relative operator, returning the current URI expressed relative to base
		
		As we also allow the Resolve method for relative paths it makes sense
		for the Relative operator to also be defined::
		
			R3 = R1 [*] R2
			R3 [/] R1 = R2
			
		Note that there are some restrictions.... ::
		
			U = B [*] R
		
		If R is absolute, or simply more specified than B on the following scale:
		
		absolute URI > authority > absolute path > relative path
		
		then U = R regardless of the value of B and therefore::
		
			U [/] B = U if B is less specified than U.
		
		Also note that if U is a relative URI then B cannot be absolute. In fact
		B must always be less than, or equally specified to U because B is the
		base URI from which U has been derived. ::
		
			U [/] B = undefined if B is more specified than U
		
		Therefore the only interesting cases are when B is equally specified to
		U.  To give a concrete example::
				
			U = /HD/User/setting.txt
			B = /HD/folder/file.txt
			
			/HD/User/setting.txt [\] /HD/folder/file.txt = ../User/setting.txt
			/HD/User/setting.txt = /HD/folder/file.txt [*] ../User/setting.txt

		And for relative paths::
		
			U = User/setting.txt
			B = User/folder/file.txt
			
			User/setting.txt [\] User/folder/file.txt = ../setting.txt
			User/setting.txt = User/folder/file.txt [*] ../setting.txt		
		"""
		if self.opaquePart is not None:
			# This is not a hierarchical URI so we can ignore base
			return URIFactory.URI(str(self))
		if self.scheme is None:
			if base.scheme is not None:
				raise URIRelativeError(str(base))
		elif base.scheme is None or self.scheme.lower()!=base.scheme.lower():
			return URIFactory.URI(str(self))
		# continuing with equal schemes; scheme will not be shown in result
		if self.authority is None:
			if base.authority is not None:
				raise URIRelativeError(str(base))
		if self.authority!=base.authority:
			authority=self.authority
			absPath=self.absPath
			relPath=self.relPath
		else:
			# equal or empty authorities
			authority=None
			if self.absPath is None:
				if base.absPath is not None:
					raise URIRelativeError(str(base))
				absPath=None
				if self.relPath is None:
					raise URIRelativeError(str(base))
				if base.relPath is None:
					relPath=self.relPath
				else:
					# two relative paths, calculate self relative to base
					# we add a common leading segment to re-use the absPath routine
					relPath=MakeRelPathRel(self.relPath,base.relPath)
			elif base.absPath is None:
				return URIFactory.URI(str(self))
			else:
				# two absolute paths, calculate self relative to base
				absPath=None
				relPath=MakeRelPathAbs(self.absPath,base.absPath)
				# todo: /a/b relative to /c/d really should be '/a/b' and not ../a/b
				# in particular, drive letters look wrong in relative paths: ../C:/Program%20Files/
		result=[]
		if authority is not None:
			result.append('//')
			result.append(authority)
		if absPath is not None:
			result.append(absPath)
		elif relPath is not None:
			result.append(relPath)
		if self.query is not None:
			result.append('?')
			result.append(self.query)
		if self.fragment is not None:
			result.append('#')
			result.append(self.fragment)
		return URIFactory.URI(string.join(result,''))			
			
	def __str__(self):
		r"""URI are always returned as a string (of bytes), not a unicode string.
		
		The reason for this restriction is best illustrated with an example:

		The URI %E8%8B%B1%E5%9B%BD.xml is a UTF-8 and URL-encoded path segment
		using the Chinese word for United Kingdom.  When we remove the
		URL-encoding we get the string '\\xe8\\x8b\\xb1\\xe5\\x9b\\xbd.xml'
		which must be interpreted with utf-8 to get the intended path segment
		value: u'\\u82f1\\u56fd.xml'.  However, if the URL was marked as being a
		unicode string of characters then this second stage would not be carried
		out and the result would be the unicode string
		u'\\xe8\\x8b\\xb1\\xe5\\x9b\\xbd', which is a meaningless string of 6
		characters taken from the European Latin-1 character set."""
		if self.fragment is not None:
			return self.octets+'#'+self.fragment
		else:
			return self.octets

	def Match(self,otherURI):
		"""Compares this URI against otherURI returning True if they match.
		
		At the moment this is a very simple algorithm: just compare the octet
		strings.  In the future we should canonicalize before comparing."""
		return str(self)==str(otherURI)
		
	def IsAbsolute(self):
		"""Returns True if this URI is absolute, i.e., fully specified with a scheme name."""
		return self.scheme is not None
				

class URIFactoryClass:
	"""A factory class that contains methods for creating :class:`URI` instances."""
	
	def __init__(self):
		self.urlClass={}
	
	def Register(self,scheme,uriClass):
		self.urlClass[scheme.lower()]=uriClass
		
	def URI(self,octets):
		"""Creates an instance of :class:`URI` from a string of octets."""
		scheme=ParseScheme(octets)
		if scheme is not None:
			scheme=scheme.lower()
		return self.urlClass.get(scheme,URI)(octets)

	def URLFromPathname(self,path):
		"""Converts a local file path into a :class:`URI` instance.

		If the path is not absolute it is made absolute by resolving it relative
		to the current working directory before converting it to a URI.

		Under Windows, the URL is constructed according to the recommendations
		on this blog post:
		http://blogs.msdn.com/b/ie/archive/2006/12/06/file-uris-in-windows.aspx
		So UNC paths are mapped to both the network location and path components
		of the resulting URI."""
		host=''
		segments=[]
		if not os.path.isabs(path):
			path=os.path.join(os.getcwd(),path)
		#print path
		drive,head=os.path.splitdrive(path)
		while head:
			newHead,tail=os.path.split(head)
			if newHead==head:
				# We are unable to split any more from head
				break
			else:
				segments[0:0]=[tail]
				if newHead=='\\\\':
					# This is the unusual case of the UNC path, first segment is machine
					host=segments[0]
					del segments[0]
					break
				head=newHead
		if drive:
			segments[0:0]=[drive]
		# At this point we need to convert to octets
		c=sys.getfilesystemencoding()
		if type(host) is UnicodeType:
			host=EscapeData(host.encode(c),IsAuthorityReserved)
		for i in xrange(len(segments)):
                        # we always use utf-8 in URL path segments to make URLs portable
			if type(segments[i]) is UnicodeType:
				segments[i]=EscapeData(segments[i].encode('utf-8'),IsPathSegmentReserved)
			else:
				segments[i]=EscapeData(unicode(segments[i],c).encode('utf-8'),IsPathSegmentReserved)
		return FileURL('file://%s/%s'%(host,string.join(segments,'/')))

	def Resolve(self,b,r):
		"""Evaluates the resolve operator B [*] R, resolving R relative to B
		
		The input parameters are converted to URI objects if necessary."""
		if not isinstance(b,URI):
			b=self.URI(b)
		if not isinstance(r,URI):
			r=self.URI(r)
		return r.Resolve(b)

	def Relative(self,u,b):
		"""Evaluates the relative operator U [/] B, returning U relative to B
		
		The input parameters are converted to URI objects if necessary."""
		if not isinstance(u,URI):
			u=self.URI(u)
		if not isinstance(b,URI):
			b=self.URI(b)
		return u.Relative(b)
		
		
class FileURL(URI):
	"""Represents the FileURL defined by RFC1738"""
	def __init__(self,octets='file:///'):
		URI.__init__(self,octets)
		self.userinfo,self.host,self.port=SplitServer(self.authority)
			
	def GetPathname(self,force8Bit=False):
		"""Returns the system path name corresponding to this file URL
		
		Note that if the system supports unicode file names (as reported by
		os.path.supports_unicode_filenames) then GetPathname also returns a
		unicode string, otherwise it returns an 8-bit string encoded in the
		underlying file system encoding.
		
		There are some libraries (notably sax) that will fail when passed files
		opened using unicode paths.  The force8Bit flag can be used to force
		GetPathname to return a byte string encoded using the native file system
		encoding."""
		c=sys.getfilesystemencoding()
		if os.path.supports_unicode_filenames and not force8Bit:
			decode=lambda s:unicode(UnescapeData(s),'utf-8')
		else:
			decode=lambda s:unicode(UnescapeData(s),'utf-8').encode(c)
		if self.host and hasattr(os.path,'splitunc'):
			uncRoot=decode('\\\\%s'%self.host)
		else:
			uncRoot=decode('')
		segments=SplitAbsPath(self.absPath)
		# ignore parameters in file system
		path=string.join(map(decode,segments),os.sep)
		if uncRoot:
			# If we have a UNC root then we will have an absolute path
			path=string.join((uncRoot,path),os.sep)
		elif not os.path.isabs(path):
			# Otherwise, prepend the sep if we're not absolute (most likely UNIX)
			# Note that drive designations do not need a prefix
			path=string.join(('',path),os.sep)
		return path
		

URIFactory=URIFactoryClass()
URIFactory.Register('file',FileURL)
