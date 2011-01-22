from rfc2234 import *
from exceptions import TypeError
from types import *
from string import join

"""
We are going to run roughshod over a subtle and important issue in this module.

The RFC2234 class is designed to parse streams of integers, typically through the
use of the python string or unicode builtin objects.  However, strictly speaking
RFC2234 does not say anything about what characters those strings represent even
though the syntax elements are described in terms of their code points in US-ASCII.

URI are not parsed from strings of integers but from strings of characters.  Of
course, we have standards like US-ASCII and Unicode precisely because it is useful
to treat streams of characters just like streams of integers but they are not the
same thing.  Therefore, we are going to make the big assumption that the URI we
are parsing has been encoded according to the Unicode standard and that we can
interpret each integer we get from the RFC2234 data stream as if it were the
corresponding Unicode character.
"""
IsAlpha=IsALPHA

def IsLowalpha(c):
	return c and (ord(c)>=0x61 and ord(c)<=0x7A)

def IsUpalpha(c):
	return c and (ord(c)>=0x41 and ord(c)<=0x5A)

def IsAlphanum(c):
	return IsDigit(c) or IsAlpha(c)

IsDigit=IsDIGIT

def EncodeEscape(c):
	c=ord(c)
	if c>255:
		raise ValueError
	else:
		return '%'+"%.2X"%c

def ConformEscapes(src):
	result=[]
	upper=0
	for c in src:
		if upper:
			result.append(c.upper())
			upper-=1
		else:
			if c=='%':
				upper=2
			result.append(c)
	return join(result,'')
				
def EncodeURIC(src):
	result=[]
	for c in src:
		if IsUnreserved(c) or IsReserved(c):
			result.append(c)
		else:
			result.append(EncodeEscape(c))
	return join(result,'')
		
class URICString:
	raw=1
	encoded=0
	def __init__(self,arg,raw=0):
		if type(arg) is StringType:
			if raw:
				self.value=arg
				self.string=EncodeURIC(arg)
			else:
				p=RFC2396Parser(arg)
				self.value=p.ParseURICRepeat()
				p.ParseEndOfData()
				self.string=ConformEscapes(arg)
		elif isinstance(arg,URICString):
			self.value=arg.value
			self.string=arg.string
		else:
			raise TypeError
	
	def __repr__(self):
		return "URICString("+repr(self.string)+")"
	
	def __str__(self):
		return self.string	

def IsMark(c):
	return c and c in "-_.!~*'()"

def IsReserved(c):
	return c and c in ";/?:@&=+$,"

def IsUnreserved(c):
	return c and (IsAlphanum(c) or IsMark(c))

	
def EncodePChar(src):
	result=""
	for c in src:
		if IsUnreserved(c) or c in ":@&=+$,":
			result=result+c
		else:
			result=result+Escape(c)
	return result



class URIReference:
	def __init__(self,arg,fragment=None):
		if type(arg) in StringTypes:
			p=RFC2396Parser(arg)
			p.ParseURIReference(self)
		elif isinstance(arg,URIReference):
			self.uri=arg.uri
			self.fragment=arg.fragment
		elif isinstance(arg,(AbsoluteURI,RelativeURI)):
			self.uri=arg
			if isinstance(fragment,URIFragment) or fragment is None:
				self.fragment=fragment
			else:
				self.fragment=URIFragment(fragment)
		else:
			raise TypeError
			
	def __repr__(self):
		return "URIReference("+repr(str(self))+")"

	def __str__(self):
		if self.fragment is None:
			return str(self.uri)
		else:
			return str(self.uri)+"#"+str(self.fragment)
	
	def __cmp__(self,other):
		return cmp(str(self),str(other))

				
class AbsoluteURI:
	def __init__(self,arg,pathPart=None):
		if isinstance(arg,AbsoluteURI):
			self.scheme=arg.scheme
			self.pathPart=arg.pathPart
		elif type(arg) in StringTypes:
			if isinstance(pathPart,(URIHierPart,URIOpaquePart)):
				self.scheme=arg
				self.pathPart=pathPart
			elif pathPart is None:
				p=RFC2396Parser(arg)
				p.ParseAbsoluteURI(self)
				p.ParseEndOfData()
			else:
				raise TypeError
		else:
			raise TypeError
	
	def __repr__(self):
		return "AbsoluteURI("+repr(self.scheme)+", "+repr(self.pathPart)+")"
	
	def __str__(self):
		return self.scheme+":"+str(self.pathPart)
	
	def GetPathType(self):
		if isinstance(self.pathPart,URIHierPart):
			return 0
		else:
			return 1
	
	def __cmp__(self,other):
		if isinstance(other,AbsoluteURI):
			result=cmp(self.scheme,other.scheme)
			if not result:
				result=cmp(self.GetPathType(),other.GetPathType())
			if not result:
				result=cmp(self.pathPart,other.pathPart)
			return result
		else:
			raise TypeError
	
	
class RelativeURI:
	def __init__(self,arg,query=None):
		if isinstance(arg,(URINetPath,URIAbsPath,URIRelPath)):
			self.pathPart=arg
			if isinstance(query,URIQuery) or query is None:
				self.query=query
			else:
				self.query=URIQuery(query)
		elif type(arg) in StringTypes:
			p=RFC2396Parser(arg)
			p.ParseRelativeURI(self)
			p.ParseEndOfData()
		else:
			raise TypeError

	def __repr__(self):
		return "RelativeURI("+repr(self.pathPart)+", "+repr(self.query)+")"
	
	def __str__(self):
		if self.query is None:
			return str(self.pathPart)
		else:
			return str(self.pathPart)+'?'+str(self.query)

	def GetPathType(self):
		if isinstance(self.pathPart,URIRelPath):
			return 0
		elif isinstance(self.pathPart,URIAbsPath):
			return 1
		else:
			return 2
				
	def __cmp__(self,other):
		if isinstance(other,RelativeURI):
			result=cmp(self.GetPathType(),other.GetPathType())
			if not result:
				result=cmp(self.pathPart,other.pathPart)
			if not result:
				result=cmp(self.query,other.query)
			return result
		else:
			raise TypeError

				
class URIHierPart:
	def __init__(self,pathPart,query=None):
		if isinstance(pathPart,(URINetPath,URIAbsPath)):
			self.pathPart=pathPart
		else:
			raise TypeError
		if isinstance(query,URIQuery) or query is None:
			self.query=query
		else:
			raise TypeError

	def __repr__(self):
		return "URIHierPart("+repr(self.pathPart)+", "+repr(self.query)+")"
	
	def __str__(self):
		if self.query is None:
			return str(self.pathPart)
		else:
			return str(self.pathPart)+'?'+str(self.query)
	
	def __cmp__(self,other):
		if isinstance(other,URIHierPart):
			if isinstance(self.pathPart,URIAbsPath):
				if isinstance(other.pathPart,URIAbsPath):
					result=cmp(self.pathPart,other.pathPart)
				else:
					result=-1
			elif isinstance(other.pathPart,URIAbsPath):
				result=1
			else:
				result=cmp(self.pathPart,other.pathPart)
			if not result:
				result=cmp(self.query,other.query)
			return result
		else:
			raise TypeError

			
class URIPath: pass


class URIOpaquePart(URIPath):
	def __init__(self,part=""):
		if type(part) is StringType:
			self.part=part
		else:
			raise TypeError
	
	def __repr__(self):
		return "URIOpaquePart("+repr(self.part)+")"
	
	def __str__(self):
		if self.part and self.part[0]=='/':
			# encode the first slash
			return EncodeEscape('/')+EncodeURIC(self.part[1:])
		else:
			return EncodeURIC(self.part)

	def __cmp__(self,other):
		if isinstance(other,URIOpaquePart):
			return cmp(self.part,other.part)
		elif type(other) in StringTypes:
			return cmp(self.part,other)
		else:
			raise TypeError


class URINetPath:
	def __init__(self,authority,absPath=None):
		if isinstance(authority,URIAuthority):
			self.authority=authority
		else:
			raise TypeError
		if isinstance(absPath,URIAbsPath):
			self.absPath=absPath
		elif absPath is None:
			self.absPath=None
		else:
			self.absPath=URIAbsPath(absPath)
	
	def __repr__(self):
		return "URINetPath("+repr(self.authority)+", "+repr(self.absPath)+")"
	
	def __str__(self):
		if self.absPath:
			return "//"+str(self.authority)+str(self.absPath)
		else:
			return "//"+str(self.authority)
	
	def __cmp__(self,other):
		if isinstance(other,URINetPath):
			result=cmp(self.authority,other.authority)
			if not result:
				result=cmp(self.absPath,other.absPath)
			return result
		else:
			raise TypeError

			
class URIAbsPath(URIPath):
	def __init__(self,segments=None):
		if segments is None:
			self.segments=[URISegment()]
		elif type(segments) is ListType:
			if len(segments):
				self.segments=segments
			else:
				raise ValueError
		else:
			raise TypeError
	
	def __repr__(self):
		return "URIAbsPath("+repr(self.segments)+")"

	def __str__(self):
		result=""
		for segment in self.segments:
			result=result+"/"+str(segment)
		return result
			
	def __cmp__(self,other):
		if isinstance(other,URIAbsPath):
			return cmp(self.segments,other.segments)
		else:
			raise TypeError
				

class URIRelPath:
	def __init__(self,relSegment,absPath=None):
		if isinstance(relSegment,URIRelSegment):
			self.relSegment=relSegment
		else:
			self.relSegment=URIRelSegment(relSegment)
		if isinstance(absPath,URIAbsPath):
			self.absPath=absPath
		elif absPath is None:
			self.absPath=None
		else:
			self.absPath=URIAbsPath(absPath)
	
	def __repr__(self):
		return "URIRelPath("+repr(self.relSegment)+", "+repr(self.absPath)+")"
	
	def __str__(self):
		if self.absPath:
			return str(self.relSegment)+str(self.absPath)
		else:
			return str(self.relSegment)
	
	def __cmp__(self,other):
		if isinstance(other,URIRelPath):
			result=cmp(self.relSegment,other.relSegment)
			if not result:
				result=cmp(self.absPath,other.absPath)
			return result
		else:
			raise TypeError
				

class URIRelSegment:
	def __init__(self,segment=""):
		self.segment=segment
	
	def __repr__(self):
		return "URIRelSegment("+repr(self.segment)+")"
	
	def __str__(self):
		result=[]
		for c in self.segment:
			if IsUnreserved(c) or c in ";@&=+$,":
				result.append(c)
			else:
				result.append(EncodeEscape(c))
		return join(result,'')		

	def __cmp__(self,other):
		if isinstance(other,URIRelSegment):
			return cmp(self.segment,other.segment)
		else:
			raise TypeError


class URIAuthority: pass


class URIRegName(URIAuthority):
	def __init__(self,arg):
		if type(arg) in StringTypes:
			self.regname=arg
		else:
			raise TypeError

	def __repr__(self):
		return "URIRegName("+repr(self.regname)+")"
	
	def __str__(self):
		result=""
		for c in self.regname:
			if IsUnreserved(c) or c in "$,;:@&=+":
				result=result+c
			else:
				result=result+EncodeEscape(c)
	
	def __cmp__(self,other):
		if isinstance(other,URIRegName):
			return cmp(self.regname,other.regname)
		else:
			raise TypeError

	
class URIServer(URIAuthority):
	def __init__(self,host,port=None,userinfo=None):
		if port is None:
			self.port=None
		elif type(port) is IntType:
			self.port=port
		else:
			raise TypeError
		if userinfo is None:
			self.userinfo=None
		elif type(userinfo) is StringType:
			self.userinfo=userinfo
		else:
			raise TypeError
		if not isinstance(host,URIHost):
			raise TypeError
		self.host=host

	def __repr__(self):
		return "URIServer("+repr(self.host)+", "+repr(self.port)+", "+repr(self.userinfo)+")"
	
	def __str__(self):
		result=""
		if self.userinfo is not None:
			for c in self.userInfo:
				if IsUnreserved(c) or c in ";:&=+$,":
					result=result+c
				else:
					result=result+EncodeEscape(c)
			result=result+"@"
		result=result+str(self.host)
		if self.port is not None:
			result=result+":"+str(self.port)
		return result

	def __cmp__(self,other):
		if isinstance(other,URIServer):
			selfType=isinstance(self.host,URIHostname)
			otherType=isinstance(self.host,URIHostname)
			if selfType<otherType:
				return -1
			elif selfType>otherType:
				return 1
			result=cmp(self.host,other.host)
			if not result:
				result=cmp(self.userinfo,other.userinfo)
			if not result:
				result=cmp(self.port,other.port)
			return result
		else:
			raise TypeError
			
class URIHost: pass

class URIHostname(URIHost):
	def __init__(self,hostname):
		if type(hostname) is ListType:
			if len(hostname):
				self.hostname=hostname
			else:
				raise ValueError
		else:
			raise TypeError
	
	def __repr__(self):
		return "URIHostname("+repr(self.hostname)+")"
	
	def __str__(self):
		return join(self.hostname,'.')
	
	def __cmp__(self,other):
		if isinstance(other,URIHostname):
			return cmp(self.hostname,other.hostname)
		else:
			raise TypeError

class URIIPv4Address(URIHost):
	def __init__(self,address=None):
		if address is None:
			self.address=[0,0,0,0]
		elif type(address) is ListType:
			if len(address)==4:
				self.address=address
			else:
				raise ValueError
		else:
			raise TypeError

	def __repr__(self):
		return "URIIPv4Address("+repr(self.address)+")"
	
	def __str__(self):
		return join(map(str,self.address),'.')

	def __cmp__(self,other):
		if isinstance(other,URIIPv4Address):
			return cmp(self.address,other.address)
		else:
			raise TypeError

		

class URISegment:
	def __init__(self,segment="",params=None):
		self.segment=segment
		if params is None:
			self.params=[]
		else:
			self.params=params
	
	def __repr__(self):
		return "URISegment("+repr(self.segment)+", "+repr(self.params)+")"
		
	def __str__(self):
		result=EncodePChar(self.segment)
		for p in self.params:
			result=result+";"+EncodePChar(p)
		return result
												
	def __cmp__(self,other):
		if isinstance(other,URISegment):
			result=cmp(self.segment,other.segment)
			if not result:
				result=cmp(self.params,other.params)
			return result
		else:
			raise TypeError


class URIQuery:
	def __init__(self,queryStr=''):
		if type(queryStr) is StringType:
			self.queryStr=queryStr
		else:
			raise TypeError
	
	def __repr__(self):
		return "URIQuery("+repr(self.queryStr)+")"
	
	def __str__(self):
		return EncodeURIC(self.queryStr)
	
	def __cmp__(self,other):
		if isinstance(other,URIQuery):
			return cmp(self.queryStr,other.queryStr)
		else:
			raise TypeError

class URIFragment:
	raw=0
	encoded=1
	def __init__(self,arg='',encoded=0):
		if type(arg) is StringType:
			if encoded:
				p=RFC2396Parser(arg)
				p.ParseFragment(self)
				p.ParseEndOfData()
			else:
				self.value=arg
		elif isinstance(value,URIFragment):
			self.value=arg.value
		else:
			raise TypeError

	def __str__(self):
		return EncodeURIC(self.value)
		
	
class RFC2396Parser(RFC2234CoreParser):

	def ParseURIReference(self,uriRef=None):
		self.PushParser()
		try:
			uri=self.ParseAbsoluteURI()
			self.PopParser(0)
		except RFCSyntaxError:
			self.PopParser(1)
			uri=self.ParseRelativeURI()
		if self.theChar=="#":
			self.NextChar()
			fragment=self.ParseFragment()
		else:
			fragment=None
		if uriRef is None:
			return URIReference(uri,fragment)
		else:
			uriRef.uri=uri
			uriRef.fragment=fragment
			return uriRef
			
	def ParseAbsoluteURI(self,uri=None):
		scheme=self.ParseScheme()
		self.ParseTerminal(':')
		self.PushParser()
		try:
			pathPart=self.ParseHierPart()
			self.PopParser(0)
		except RFCSyntaxError:
			self.PopParser(1)
			pathPart=self.ParseOpaquePart()
		if uri is None:
			return AbsoluteURI(scheme,pathPart)
		else:
			uri.scheme=scheme
			uri.pathPart=pathPart

	def ParseRelativeURI(self,uri=None):
		self.PushParser()
		try:
			pathPart=self.ParseNetPath()
			self.PopParser(0)
		except RFCSyntaxError:
			self.PopParser(1)
			self.PushParser()
			try:
				pathPart=self.ParseAbsPath()
				self.PopParser(0)
			except RFCSyntaxError:
				self.PopParser(1)
				pathPart=self.ParseRelPath()
		if self.theChar=="?":
			self.NextChar()
			query=self.ParseQuery()
		else:
			query=None
		if uri is None:
			return RelativeURI(pathPart,query)
		else:
			uri.pathPart=pathPart
			uri.query=query
			return uri
		
	def ParseAbsPath(self):
		self.ParseTerminal("/")
		return URIAbsPath(self.ParsePathSegments())
		
	ParseAlpha=RFC2234CoreParser.ParseALPHA

	def ParseAlphanum(self):
		if IsAlphanum(self.theChar):
			c=self.theChar
			self.NextChar()
			return c
		else:
			self.SyntaxError("expected alphanum")
	
	def ParseAuthority(self):
		self.PushParser()
		try:
			authority=self.ParseServer()
			self.PopParser(0)
		except RFCSyntaxError:
			self.PopParser(1)
			authority=self.ParseRegName()
		return authority
		
	def ParseDomainLabel(self):
		label=self.ParseAlphanum()
		while IsAlphanum(self.theChar) or self.theChar=="-":
			label=label+self.theChar
			self.NextChar()
		if label[-1]=="-":
			self.SyntaxError("domain-label can't end in hypen")
		return label
			
	def ParseEscaped(self):
		self.ParseTerminal("%")
		value=self.ParseHEXDIG()
		value=value*16+self.ParseHEXDIG()
		return value

	def ParseFragment(self,fragment=None):
		if fragment is None:
			return URIFragment(self.ParseURICRepeat(),URIFragment.raw)
		else:
			fragment.value=self.ParseURICRepeat()
			
	def ParseHierPart(self):
		self.PushParser()
		try:
			pathPart=self.ParseNetPath()
			self.PopParser(0)
		except:
			self.PopParser(1)
			pathPart=self.ParseAbsPath()
		if self.theChar=="?":
			self.NextChar()
			query=self.ParseQuery()
		else:
			query=None
		return URIHierPart(pathPart,query)	
			
	def ParseHost(self):
		hostname=[]
		topLevel=0
		trailingDot=0
		while IsAlphanum(self.theChar):
			topLevel=IsAlpha(self.theChar)
			hostname.append(self.ParseDomainLabel())
			if self.theChar==".":
				self.NextChar()
				trailingDot=1
			else:
				trailingDot=0
				break
		if trailingDot:
			hostname.append('')
		if len(hostname)==4:
			# Check for an IP address
			ipAddress=1
			for label in hostname:
				if not label.isdigit():
					ipAddress=0
					break
			if ipAddress:
				return URIIPv4Address(map(int,hostname))
		if not topLevel:
			# Last label must be a toplabel
			self.SyntaxError("expected toplabel")
		return URIHostname(hostname)
		
	def ParseHostname(self):
		hostname=[]
		topLevel=0
		trailingDot=0
		while IsAlphanum(self.theChar):
			topLevel=IsAlpha(self.theChar)
			hostname.append(self.ParseDomainLabel())
			if self.theChar==".":
				self.NextChar()
				trailingDot=1
			elif not topLevel:
				# A domainlabel must be followed by a dot
				self.SyntaxError("expected '.'")
			else:
				trailingDot=0
		if not topLevel:
			# Last label must be a toplabel
			self.SyntaxError("expected toplabel")
		if trailingDot:
			hostname.append('')
		return URIHostname(hostname)
	
	def ParseHostPort(self):
		host=self.ParseHost()
		port=None
		if self.theChar==":":
			self.NextChar()
			port=self.ParsePort()
		return (host,port)
	
	def ParseIPv4Address(self):
		address=[]
		for i in range(4):
			if len(address):
				self.ParseTerminal(".")
			value=self.ParseDIGITRepeat()
			if value is None:
				self.SyntaxError("expected digits")
			else:
				address.append(value)
		return URIIPv4Address(address)
	
	def ParseNetPath(self):
		self.ParseLiteral("//")
		authority=self.ParseAuthority()
		if self.theChar=="/":
			absPath=self.ParseAbsPath()
		else:
			absPath=None
		return URINetPath(authority,absPath)
	
	def ParseOpaquePart(self):
		if self.theChar!='/':
			result=self.ParseURICRepeat()
			if not result:
				self.SyntaxError("expected non-empty opaque part")
			return URIOpaquePart(result)
		else:
			self.SyntaxError("opaque part cannot start with '/'")
				
	def ParseParam(self):
		return self.ParsePCharRepeat()
	
	def ParsePath(self):
		if self.theChar=="/":
			return self.ParseAbsPath()
		else:
			return self.ParseOpaquePart()

	def ParsePathSegments(self):
		segments=[self.ParseSegment()]
		while self.theChar=="/":
			self.NextChar()
			segments.append(self.ParseSegment())
		return segments
			
	def ParsePCharRepeat(self):
		pCharStr=""
		while self.theChar is not None:
			if self.theChar=="%":
				pCharStr=pCharStr+chr(self.ParseEscaped())
			elif IsUnreserved(self.theChar) or self.theChar in ":@&=+$,":
				pCharStr=pCharStr+self.theChar
				self.NextChar()
			else:
				break
		return pCharStr
	
	ParsePort=RFC2234CoreParser.ParseDIGITRepeat
	
	def ParseQuery(self):
		return URIQuery(self.ParseURICRepeat())
	
	def ParseRegName(self):
		regname=""
		while IsUnreserved(self.theChar) or (self.theChar and self.theChar in "$,;:@&=+%"):
			if self.theChar=="%":
				regname=regname+chr(self.ParseEscaped())
			else:
				regname=regname+self.theChar
				self.NextChar()
		if regname:
			return URIRegName(regname)
		else:
			self.SyntaxError("expected reg_name")
	
	def ParseRelPath(self):
		relSegment=self.ParseRelSegment()
		if self.theChar=="/":
			absPath=self.ParseAbsPath()
		else:
			absPath=None
		return URIRelPath(relSegment,absPath)
		
	def ParseRelSegment(self):
		result=[]
		while IsUnreserved(self.theChar) or (self.theChar and self.theChar in ";@&=+$,%"):
			if self.theChar=="%":
				result.append(chr(self.ParseEscaped()))
			else:
				result.append(self.theChar)
				self.NextChar()
		if result:
			return URIRelSegment(join(result,''))
		else:
			self.SyntaxError("expected relative segment")
			
	def ParseScheme(self):
		scheme=self.ParseAlpha()
		while self.theChar and (
			IsAlpha(self.theChar) or IsDigit(self.theChar) or self.theChar in "+-."):
			scheme=scheme+self.theChar
			self.NextChar()
		return scheme
	
	def ParseSegment(self):
		segment=URISegment(self.ParsePCharRepeat())
		while self.theChar==";":
			self.NextChar()
			segment.params.append(self.ParsePCharRepeat())
		return segment
	
	def ParseServer(self):
		self.PushParser()
		userinfo=self.ParseUserInfo()
		if self.theChar=="@":
			self.PopParser(0)
			self.NextChar()
		else:
			self.PopParser(1)
			userinfo=None
		host,port=self.ParseHostPort()
		return URIServer(host,port,userinfo)
		
	def ParseTopLabel(self):
		label=self.ParseAlpha()
		while IsAlphanum(self.theChar) or self.theChar=="-":
			label=label+self.theChar
			self.NextChar()
		if label[-1]=="-":
			self.SyntaxError("top-label can't end in hypen")
		return label
			
	def ParseURICRepeat(self):
		# We don't do look ahead for escapes because uric is nowhere used where
		# % may follow
		uricStr=""
		while self.theChar is not None:
			if self.theChar=="%":
				uricStr=uricStr+chr(self.ParseEscaped())
			elif IsReserved(self.theChar) or IsUnreserved(self.theChar):
				uricStr=uricStr+self.theChar
				self.NextChar()
			else:
				break
		return uricStr
	
	def ParseUserInfo(self):
		info=""
		while IsUnreserved(self.theChar) or (self.theChar and self.theChar in ";:&=+$,"):
			if self.theChar=="%":
				info=info+chr(self.ParseEscaped())
			else:
				info=info+self.theChar
				self.NextChar()
		return info
		

