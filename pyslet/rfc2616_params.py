#! /usr/bin/env python

import string, warnings
from types import *

from pyslet.rfc2616_core import *
import pyslet.iso8601 as iso
import pyslet.rfc2396 as uri


class HTTPVersion(object):
	"""Represents the HTTP Version.
	
	HTTPVersion objects can be created from their string representation
	passed in *source*.  If *source* is None then the protocol version
	is set to 1.1.
	
	HTTPVersion objects must be treated as immutable, they define
	comparison functions (such that 1.1>1.0 and  1.2<1.25) and can also
	be used as keys in dictionaries if required.
	
	Finally, on conversion to a string the output is of the form::
	
		HTTP/<major>.<minor>"""	
	def __init__(self,major=1,minor=None):
		self.major=major	#: major protocol version (read only)
		self.minor=minor	#: minor protocol version (read only)
		if minor is None:
			self.minor=1 if major==1 else 0
	
	@classmethod
	def FromString(cls,source):
		"""Constructs an :py:class:`HTTPVersion` object from a string."""
		wp=ParameterParser(source)
		result=wp.RequireProduction(wp.ParseHTTPVersion(),"HTTP Version")
		wp.RequireEnd("HTTP version")
		return result
					
	def __str__(self):
		return "HTTP/%i.%i"%(self.major,self.minor)

	def __hash__(self):
		return hash((self.major,self.minor))
		
	def __cmp__(self,other):
		if not isinstance(other,HTTPVersion):
			raise TypeError
		if self.major<other.major:
			return -1
		elif self.major>other.major:
			return 1
		elif self.minor<other.minor:
			return -1
		elif self.minor>other.minor:
			return 1
		else:
			return 0

HTTP_1_1=HTTPVersion(1,1)			

class HTTPURL(uri.ServerBasedURL):
	"""Represents http URLs"""
	
	DEFAULT_PORT=80		#: the default HTTP port
	
	def __init__(self,octets='http://localhost/'):
		super(HTTPURL,self).__init__(octets)

	def Canonicalize(self):
		"""Returns a canonical form of this URI"""
		newURI=[]
		if self.scheme is not None:
			newURI.append(self.scheme.lower())
			newURI.append(':')
		if self.authority is not None:
			newURI.append('//')
			if self.userinfo is not None:
				newURI.append(self.userinfo)
				newURI.append('@')
			newURI.append(self.host.lower())
			if self.port:	# port could be an empty string
				port=int(self.port)
				if port!=self.DEFAULT_PORT:
					newURI.append(':')
					newURI.append("%i"%int(self.port))
		if self.absPath is not None:
			if not self.absPath:
				newURI.append("/")
			else:
				newURI.append(uri.CanonicalizeData(self.absPath))
		elif self.relPath is not None:
			newURI.append(uri.CanonicalizeData(self.relPath))
		if self.query is not None:
			newURI.append('?')
			newURI.append(uri.CanonicalizeData(self.query))
		if self.fragment is not None:
			newURI.append('#')
			newURI.append(self.fragment)
		return uri.URIFactory.URI(string.join(newURI,''))


class HTTPSURL(HTTPURL):
	"""Represents https URLs"""
	
	DEFAULT_PORT=443	#: the default HTTPS port
	
	def __init__(self,octets='https://localhost/'):
		super(HTTPSURL,self).__init__(octets)


uri.URIFactory.Register('http',HTTPURL)
uri.URIFactory.Register('https',HTTPSURL)


class FullDate(iso.TimePoint):
	"""A sub-class of :py:class:`pyslet.iso8601.TimePoint` which adds parsing
	and formatting methods for HTTP-formatted dates."""
	
	@classmethod					
	def FromHTTPString(cls,source):
		"""Parses a :py:class:`pyslet.iso8601.TimePoint` instance from an HTTP
		formatted string."""
		wp=ParameterParser(source)
		tp=wp.RequireFullDate()
		wp.ParseSP()
		wp.RequireEnd("full date")
		return tp
		
	def __str__(self):
		"""Formats a :py:class:`pyslet.iso8601.TimePoint` instance in the
		following format, described as RFC 1123 [8]-date format::
		
			Sun, 06 Nov 1994 08:49:37 GMT
		
		Note that this overrides the default behaviour which would be to use one
		of the iso8601 output formats."""
		century,year,month,day,hour,minute,second=self.GetCalendarTimePoint()
		century,decade,dyear,week,dayOfWeek=self.date.GetWeekDay()
		return "%s, %02i %s %04i %02i:%02i:%02i GMT"%(
			ParameterParser.wkday[dayOfWeek-1],
			day,
			ParameterParser.month[month-1],
			century*100+year,
			hour,minute,second)

	def __unicode(self):
		"""See __str__"""
		return unicode(str(self))


class TransferEncoding(object):
	"""Represents an HTTP transfer-encoding.
	
	The built-in str function can be used to format instances according
	to the grammar defined in the specification.
	
	Instances must be treated as immutable, they define comparison
	methods and a hash implementation to allow them to be used as keys
	in dictionaries."""	
	def __init__(self,token="chunked",parameters={}):
		token=token.lower() 
		if token=="chunked":
			self.token="chunked"		#: the transfer-encoding token (defaults to "chunked")
			self.parameters={}			#: declared extension parameters
		else:
			self.token=token
			self.parameters=parameters
		self._hp=map(lambda x:(x[0],x[1][1]),self.parameters.items())
		self._hp.sort()
	
	@classmethod
	def FromString(cls,source):
		"""Parses the transfer-encoding from a *source* string.
		
		If the protocol version is not parsed correctly SyntaxError is raised."""
		p=ParameterParser(source)
		te=p.RequireTransferEncoding()
		p.RequireEnd("transfer-encoding")
		return te
		
	def __str__(self):
		return self.token+FormatParameters(self.parameters)

	def __eq__(self,other):
		return hash(self)==hash(other)
	
	def __cmp__(self,other):
		if type(other) in StringTypes:
			other=TransferEncoding.FromString(other)
		if not isinstance(TransferEncoding):
			raise TypeError
		return cmp((self.token,self._hp),(other.token,other._hp))
		
	def __hash__(self):
		return hash((self.token,self._hp))

		
class MediaType(object):
	"""Represents an HTTP media-type.
	
	The built-in str function can be used to format instances according
	to the grammar defined in the specification.
	
	Instances must be treated as immutable, they define comparison
	methods and a hash implementation to allow them to be used as keys
	in dictionaries.  Media-types are compared by type, subtype and
	ultimately parameters."""	
	def __init__(self,type="application",subtype="octet-stream",parameters={}):
		self.type=type
		self.subtype=subtype
		self.parameters=parameters
		self._hp=map(lambda x:(x[0],x[1][1]),self.parameters.items())
		self._hp.sort()
	
	@classmethod
	def FromString(cls,source):
		"""Creates a media-type from a *source* string.
		
		Enforces the following rule from the specification:
		
			Linear white space (LWS) MUST NOT be used between the type and
			subtype, nor between an attribute and its value"""
		p=ParameterParser(source,ignoreSpace=False)
		mt=p.RequireMediaType()
		p.ParseSP()
		p.RequireEnd("media-type")
		return mt
					
	def __str__(self):
		return string.join([self.type,'/',self.subtype],'')+FormatParameters(self.parameters)

	def __unicode__(self):
		return unicode(self.__str__())
	
	def __repr__(self):
		return "MediaType(%s,%s,%s)"%(repr(self.type),repr(self.subtype),repr(self.parameters))
			
	def __cmp__(self,other):
		if type(other) in StringTypes:
			other=MediaType.FromString(other)
		if not isinstance(other,MediaType):
			raise TypeError
		result=cmp(self.type.lower(),other.type.lower())
		if result:
			return result
		result=cmp(self.subtype.lower(),other.subtype.lower())
		if result:
			return result
		return cmp(self._hp,other._hp)

	def __hash__(self):
		return hash((self.type.lower(),self.subtype.lower(),self._hp))


class ProductToken(object):
	"""Represents an HTTP product token.
	
	The built-in str function can be used to format instances according
	to the grammar defined in the specification.
	
	Instances must be treated as immutable, they define comparison
	methods and a hash implementation to allow them to be used as keys
	in dictionaries.
	
	The comparison operations use a more interesting sort than plain
	text on version in order to provide a more intuitive ordering.  As
	it is common practice to use dotted decimal notation for versions
	(with some alphanumeric modifiers) the version string is exploded
	(see :py:meth:`Explode`) internally on construction and this
	exploded value is used in comparisons.  The upshot is that version
	1.0.3 sorts before 1.0.10 as you would expect and 1.0a < 1.0 <
	1.0.3a3 < 1.0.3a20 < 1.0.3b1 < 1.0.3; there are limits to this
	algorithm.  1.0dev > 1.0b1 even though it looks like it should be
	the other way around.  Similarly 1.0-live < 1.0-prod etc.

	You shouldn't use this comparison as a definitive way to determine
	that one release is more recent or up-to-date than another unless
	you know that the product in question uses a numbering scheme
	compatible with these rules."""	
	def __init__(self,token=None,version=None):
		self.token=token		#: the product's token
		self.version=version	#: the product's version
		if self.version is not None:
			# explode the version string
			self._version=self.Explode(self.version)
		else:
			self._version=()

	@classmethod
	def Explode(cls,version):
		"""Returns an exploded version string.
		
		Version strings are split by dot and then by runs of non-digit
		characters resulting in a list of tuples.  Examples will help::
		
			Explode("2.15")==((2),(15))
			Explode("2.17b3")==((2),(17,"b",3))
			Explode("2.b3")==((2),(-1,"b",3))

		Note that a missing leading numeric component is treated as -1
		to force "a3" to sort before "0a3"."""
		exploded=[]
		p=BasicParser(version)
		while p.theChar is not None:
			# parse an item
			vitem=[]
			modifier=[]
			while not p.Match(".") and not p.MatchEnd():
				num=p.ParseInteger()
				if num is None:
					if not vitem:
						vitem.append(-1)
					modifier.append(p.theChar)
					p.NextChar()
				else:
					if modifier:
						vitem.append(string.join(modifier,''))
						modifier=[]
					vitem.append(num)
			if modifier:
				vitem.append(string.join(modifier,''))
			exploded.append(tuple(vitem))
			p.Parse(".")		
		return tuple(exploded)
		
	@classmethod	
	def FromString(cls,source):
		"""Creates a product token from a *source* string."""
		p=ParameterParser(source)
		p.ParseSP()
		pt=p.RequireProductToken()
		p.ParseSP()
		p.RequireEnd("product token")
		return pt
	
	@classmethod	
	def ListFromString(cls,source):
		"""Creates a list of product tokens from a *source* string.

		Individual tokens are separated by white space."""
		ptList=[]
		p=ParameterParser(source)
		p.ParseSP()
		while p.cWord is not None:
			ptList.append(p.RequireProductToken())
			p.ParseSP()
		p.RequireEnd("product token")
		return ptList
	
	def __str__(self):
		if self.version is None:
			return self.token
		else:
			return string.join((self.token,'/',self.version),'')

	def __unicode__(self):
		return unicode(self.__str__())
	
	def __repr__(self):
		return "ProductToken(%s,%s)"%(repr(self.token),repr(self.version))
			
	def __cmp__(self,other):
		if type(other) in StringTypes:
			other=ProductToken.FromString(other)
		elif not isinstance(other,ProductToken):
			raise TypeError
		result=cmp(self.token,other.token)
		if result:
			return result
		iVersion=0
		while True:
			if iVersion<len(self._version):
				v=self._version[iVersion]
			else:
				v=None
			if iVersion<len(other._version):
				vOther=other._version[iVersion]
			else:
				vOther=None
			# a missing component sorts before
			if v is None:
				if vOther is None:
					# both missing, must be equal.  Note that this
					# means that "01" is treated equal to "1"
					return 0
				else:					
					return -1
			elif vOther is None:
				return 1
			# now loop through the sub-components and compare them
			jVersion=0
			while True:
				if jVersion<len(v):
					vv=v[jVersion]
				else:
					vv=None
				if jVersion<len(vOther):
					vvOther=vOther[jVersion]
				else:
					vvOther=None
				if vv is None:
					if vvOther is None:
						break
					else:
						# "1.0">"1.0a"
						return 1
				elif vvOther is None:
					# "1.0a"<"1.0"
					return -1
				# 1.0 < 1.1 and 1.0a<1.0b
				result=cmp(vv,vvOther)
				if result:
					return result
				jVersion+=1
			iVersion+=1
		# we can't get here
		return 0	

	def __hash__(self):
		# despite the complex comparison function versions can only be
		# equal if they have exactly the same version
		return hash((self.token,self._version))


class LanguageTag(object):
	"""Represents an HTTP language-tag.
	
	The built-in str function can be used to format instances according
	to the grammar defined in the specification.
	
	Instances must be treated as immutable, they define comparison
	methods and a hash implementation to allow them to be used as keys
	in dictionaries."""	
	def __init__(self,primary,*subtags):
		self.primary=primary
		self.subtags=subtags
		tags=[primary.lower()]
		for sub in subtags:
			tags.append(sub.lower())
		self._tag=tuple(tags)
	
	def PartialMatch(self,range):
		"""Returns True if this tag is a partial match against *range*, False otherwise.
		
		range
			A tuple of lower-cased subtags.  An empty tuple matches
			all instances.
		
		For example::
			
			lang=LanguageTag("en",("US","Texas"))
			lang.PartialMatch(())==True
			lang.PartialMatch(("en",)==True
			lang.PartialMatch(("en","us")==True
			lang.PartialMatch(("en","us","texas")==True
			lang.PartialMatch(("en","gb")==False
			lang.PartialMatch(("en","us","tex")==False"""
		if len(range)>len(self._tag):
			return False
		for i in xrange(len(range)):
			if self._tag[i]!=range[i]:
				return False
		return True
			 
	@classmethod
	def FromString(cls,source):
		"""Creates a language tag from a *source* string.
		
		Enforces the following rules from the specification:
		
			White space is not allowed within the tag"""
		p=ParameterParser(source,ignoreSpace=False)
		p.ParseSP()
		t=p.RequireLanguageTag()
		p.ParseSP()
		p.RequireEnd("language tag")
		return t
					
	@classmethod
	def ListFromString(cls,source):
		"""Creates a list of language tags from a *source* string."""
		p=ParameterParser(source,ignoreSpace=False)
		tags=[]
		while True:
			p.ParseSP()
			t=p.ParseProduction(p.RequireLanguageTag)
			if t is not None:
				tags.append(t)
			p.ParseSP()
			if not p.ParseSeparator(","):
				break
		p.ParseSP()
		p.RequireEnd("language tag")
		return tags
					
	def __str__(self):
		return string.join([self.primary]+list(self.subtags),'-')

	def __unicode__(self):
		return unicode(self.__str__())
	
	def __repr__(self):
		return "LanguageTag(%s)"%string.join(map(repr,[self.primary]+list(self.subtags)),',')
			
	def __cmp__(self,other):
		"""Language tags are compared case insensitive."""
		if type(other) in StringTypes:
			other=LanguageTag.FromString(other)
		if not isinstance(other,LanguageTag):
			raise TypeError
		return cmp(self._tag,other._tag)

	def __hash__(self):
		return hash(self._tag)


class EntityTag:
	"""Represents an HTTP entity-tag.
	
	tag
		The opaque tag
	
	weak
		A boolean indicating if the entity-tag is a weak or strong
		entity tag.
		
	The built-in str function can be used to format instances according
	to the grammar defined in the specification.
	
	Instances must be treated as immutable, they define comparison
	methods and a hash implementation to allow them to be used as keys
	in dictionaries."""	
	def __init__(self,tag,weak=True):
		self.weak=weak		#: True if this is a weak tag
		self.tag=tag		#: the opaque tag

	@classmethod
	def FromString(cls,source):
		"""Creates an entity-tag from a *source* string."""
		p=ParameterParser(source)
		et=p.RequireEntityTag()
		p.RequireEnd("entity-tag")
		return et
		
	def __str__(self):
		if self.weak:
			return "W/"+QuoteString(self.tag)
		else:
			return QuoteString(self.tag)

	def __unicode__(self):
		return unicode(self.__str__())
	
	def __repr__(self):
		return "EntityTag(%s,%s)"%(repr(self.tag),"True" if self.week else "False")
			
	def __cmp__(self,other):
		"""Entity-tags are compared case sensitive."""
		if type(other) in StringTypes:
			other=EntityTag.FromString(other)
		if not isinstance(other,EntityTag):
			raise TypeError
		result=cmp(self.tag,other.tag)
		if not result:
			# sorts strong tags before weak ones
			result=cmp(self.weak,other.weak)
		return result
		
	def __hash__(self):
		return hash((self.tag,self.weak))


class ParameterParser(WordParser):

	def ParseHTTPVersion(self):
		"""Parses an :py:class:`HTTPVersion` instance or None if no
		version was found.""" 
		savePos=self.pos
		try:
			self.ParseSP()
			token=self.RequireToken("HTTP").upper()
			if token!="HTTP":
				raise SyntaxError("Expected 'HTTP', found %s"%repr(token))
			self.ParseSP()
			self.RequireSeparator('/',"HTTP/")
			self.ParseSP()
			token=self.RequireToken("protocol version")
			version=token.split('.')
			if len(version)!=2 or not IsDIGITS(version[0]) or not IsDIGITS(version[1]): 
				raise SyntaxError("Expected version, found %s"%repr(token))
			return HTTPVersion(major=int(version[0]),minor=int(version[1]))
		except SyntaxError:
			self.SetPos(savePost)
			return None

	wkday=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
	#	A list of day-of-week names Mon=0, Sun=6.
	_weekday=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
	#	A list of long-form day-of-week names Monday=0, Sunday=6.
	_wkdayTable={}
	#	A mapping from lower-case day-of-week names to integers (Mon=0, Sun=6)

	month=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
	#	A list of month names Jan=0, Dec=11.
	_monthTable={}
	#	A mapping from lower-case month names to integers (Jan=0, Dec=11)
	
	def RequireFullDate(self):
		"""Parses a :py:class:`FullDate` instance raising
		:py:class:`SyntaxError` if none is found.
		
		There are three supported formats as described in the specification::
	
			"Sun, 06 Nov 1994 08:49:37 GMT"
			"Sunday, 06-Nov-94 08:49:37 GMT"
			"Sun Nov  6 08:49:37 1994"
		
		The first of these is the preferred format."""
		century=None
		year=None	
		month=None
		day=None
		hour=None
		minute=None
		second=None
		dayOfWeek=None
		self.ParseSP()
		token=self.RequireToken("day-of-week").lower()
		dayOfWeek=self._wkdayTable.get(token,None)
		if dayOfWeek is None:
			raise SyntaxError("Unrecognized day of week: %s"%token)
		self.ParseSP()
		if self.ParseSeparator(","):
			self.ParseSP()
			if self.IsToken() and IsDIGITS(self.cWord):
				# Best format 0: "Sun, 06 Nov 1994 08:49:37 GMT" - the preferred format!				
				day=self.RequireInteger("date")
				self.ParseSP()
				token=self.RequireToken("month").lower()
				month=self._monthTable.get(token,None)	
				if month is None:
					raise SyntaxError("Unrecognized month: %s"%repr(token))
				self.ParseSP()
				year=self.RequireInteger("year")
				century=year//100
				year=year%100
			else:
				# Alternative 1: "Sunday, 06-Nov-94 08:49:37 GMT"
				token=self.RequireToken("DD-MMM-YY")
				sToken=token.split('-')
				if len(sToken)!=3 or not IsDIGITS(sToken[0]) or not IsDIGITS(sToken[2]):
					raise SyntaxError("Expected DD-MMM-YY, found %s"%repr(token))
				day=int(sToken[0])
				year=int(sToken[2])
				month=self._monthTable.get(sToken[1].lower(),None)	
				if month is None:
					raise SyntaxError("Unrecognized month: %s"%repr(sToken[1]))				
		else:
			# "Sun Nov  6 08:49:37 1994"
			token=self.RequireToken("month").lower()
			month=self._monthTable.get(token,None)	
			if month is None:
				raise SyntaxError("Unrecognized month: %s"%repr(token))
			self.ParseSP()
			day=self.RequireInteger("date")
		self.ParseSP()
		hour=self.RequireInteger("hour")
		self.RequireSeparator(':')
		minute=self.RequireInteger("minute")
		self.RequireSeparator(':')
		second=self.RequireInteger("second")
		self.ParseSP()
		if year is None:
			year=self.RequireInteger("year")
			century=year//100
			year=year%100
		else:
			token=self.RequireToken("GMT").upper()
			if token!="GMT":
				raise SyntaxError("Unrecognized timezone: %s"%repr(token))
		if century is None:
			if year<90:
				century=20
			else:
				century=19
		tp=FullDate(date=iso.Date(century=century,year=year,month=month+1,day=day),time=iso.Time(hour=hour,minute=minute,second=second,zDirection=0))
		d1,d2,d3,d4,dow=tp.date.GetWeekDay()
		if dow!=dayOfWeek+1:
			raise SyntaxError("Day-of-week mismatch, expected %s but found %s"%(self.wkday[dow-1],self.wkday[dayOfWeek]))
		return tp

	ParseDeltaSeconds=WordParser.ParseInteger		#: Parses a delta-seconds value, see :py:meth:`WordParser.ParseInteger`
	
	ParseCharset=WordParser.ParseTokenLower			#: Parses a charset, see :py:meth:`WordParser.ParseTokenLower`

	ParseContentCoding=WordParser.ParseTokenLower	#: Parses a content-coding, see :py:meth:`WordParser.ParseTokenLower`

	def RequireTransferEncoding(self):
		"""Parses a transfer-encoding returning a
		:py:class:`TransferEncoding` instance or None if no
		transfer-encoding was found."""
		self.ParseSP()
		token=self.RequireToken("transfer-encoding").lower()
		if token!="chunked":
			parameters={}
			self.ParseParameters(parameters)
			return TransferEncoding(token,parameters)
		else:
			return TransferEncoding()

	def RequireMediaType(self):
		"""Parses a media type returning a :py:class:`MediaType`
		instance.  Raises SyntaxError if no media-type was found."""		
		self.ParseSP()
		type=self.RequireToken("media-type").lower()
		self.RequireSeparator('/',"media-type")
		subtype=self.RequireToken("media-subtype").lower()
		self.ParseSP()
		parameters={}
		self.ParseParameters(parameters,ignoreAllSpace=False)
		return MediaType(type,subtype,parameters)
	
	def RequireProductToken(self):
		"""Parses a product token returning a :py:class:`ProductToken`
		instance.  Raises SyntaxError if no product token was found."""
		self.ParseSP()
		token=self.RequireToken("product token")
		self.ParseSP()
		if self.ParseSeparator('/'):
			version=self.RequireToken("product-version")
		else:
			version=None
		return ProductToken(token,version)
		
	def ParseQualityValue(self):
		"""Parses a qvalue from returning the float equivalent value or
		None if no qvalue was found."""
		if self.IsToken():
			q=None
			qSplit=self.cWord.split('.')
			if len(qSplit)==1:
				if IsDIGITS(qSplit[0]):
					q=float(qSplit[0])
			elif len(qSplit)==2:
				if IsDIGITS(qSplit[0]) and IsDIGITS(qSplit[1]):
					q=float("%.3f"%float(self.cWord))
			if q is None:
				return None
			else:
				if q>1.0:
					# be generous if the value has overflowed
					q=1.0
				self.ParseWord()
				return q
		else:
			return None
	
	def RequireLanguageTag(self):
		"""Parses a language tag returning a :py:class:`LanguageTag`
		instance.  Raises SyntaxError if no language tag was
		found."""		
		self.ParseSP()
		tag=self.RequireToken("languaget-tag").split('-')
		self.ParseSP()
		return LanguageTag(tag[0],*tag[1:])
					
	def RequireEntityTag(self):
		"""Parses an entity-tag returning a :py:class:`EntityTag`
		instance.  Raises SyntaxError if no language tag was
		found."""		
		self.ParseSP()
		w=self.ParseToken()
		self.ParseSP()
		if w is not None:
			if w.upper()!="W":
				raise SyntaxError("Expected W/ or quoted string for entity-tag")
			self.RequireSeparator("/","entity-tag")
			self.ParseSP()
			w=True
		else:
			w=False
		tag=self.RequireProduction(self.ParseQuotedString(),"entity-tag")
		self.ParseSP()
		return EntityTag(tag,w)
					

for i in xrange(len(ParameterParser.wkday)):
	ParameterParser._wkdayTable[ParameterParser.wkday[i].lower()]=i
for i in xrange(len(ParameterParser._weekday)):
	ParameterParser._wkdayTable[ParameterParser._weekday[i].lower()]=i
for i in xrange(len(ParameterParser.month)):
	ParameterParser._monthTable[ParameterParser.month[i].lower()]=i
		

# HTTP_DAY_NUM={
# 	"monday":0, "mon":0,
# 	"tuesday":1, "tue":1,
# 	"wednesday":2, "wed":2,
# 	"thursday":3, "thu":3,
# 	"friday":4, "fri":4,
# 	"saturday":5, "sat":5,
# 	"sunday":6, "sun":6 }
# 
# # Note that in Python time/datetime objects Jan has index 1!
# HTTP_MONTH_NUM={
# 	"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12
# 	}
# 	
# def ParseDate(dateStr):
# 	date=string.split(dateStr.strip().lower())
# 	if len(date)==4:
# 		# e.g., "Sunday, 06-Nov-94 08:49:37 GMT"
# 		date=date[0:1]+date[1].split('-')+date[2].split(':')+date[3:]
# 	elif len(date)==5:
# 		# e.g., "Sun Nov  6 08:49:37 1994"
# 		date=[date[0]+',',date[2],date[1],date[4]]+date[3].split(':')+['gmt']
# 	elif len(date)==6:
# 		# e.g., "Sun, 06 Nov 1994 08:49:37 GMT" - the preferred format!
# 		date=date[0:4]+date[4].split(':')+date[5:]
# 	if len(date)!=8:
# 		raise ValueError("Badly formed date: %s"%dateStr)
# 	wday=HTTP_DAY_NUM[date[0][:-1]]
# 	mday=int(date[1])
# 	mon=HTTP_MONTH_NUM[date[2]]
# 	year=int(date[3])
# 	# No obvious guidance on base year for two-digit years by HTTP was
# 	# first used in 1990 so dates before that are unlikely!
# 	if year<90:
# 		year=year+2000
# 	elif year<100:
# 		year=year+1900
# 	hour=int(date[4])
# 	min=int(date[5])
# 	sec=int(date[6])
# 	if date[7]!='gmt':
# 		raise ValueError("HTTP date must have GMT timezone: %s"%dateStr)
# 	result=datetime.datetime(year,mon,mday,hour,min,sec)
# 	if result.weekday()!=wday:
# 		raise ValueError("Weekday mismatch in: %s"%dateStr)
# 	return result
# 
# 
# HTTP_DAYS=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
# HTTP_MONTHS=["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
# 
# def FormatDate(date):
# 	# E.g., "Sun, 06 Nov 1994 08:49:37 GMT"
# 	return "%s, %02i %s %04i %02i:%02i:%02i GMT"%(
# 			HTTP_DAYS[date.weekday()],
# 			date.day,
# 			HTTP_MONTHS[date.month],
# 			date.year,
# 			date.hour,
# 			date.minute,
# 			date.second)
	