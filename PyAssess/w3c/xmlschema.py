from string import split, join
from math import modf, floor, log10, pow
from re import compile
from sys import maxunicode

from PyAssess.ietf.rfc2234 import RFC2234Parser, RFC2234CoreParser, RFCSyntaxError, IsDIGIT, IsALPHA
from PyAssess.unicode.ucd import MakeCharClass, NegateCharClass, SubtractCharClass, CategoryTable, GetBlockRange
from xml import NameCharClass, LetterClass

# We use the machine Epsilon to put bounds on the number of fractional
# digits we generate in decimal representations.
kEpsilon=1.0
kMaxSigFig=0
while 1.0+kEpsilon>1.0:
	kEpsilon=kEpsilon/10.0
	kMaxSigFig+=1

def ParseBoolean(src):
	if src=="true":
		return 1
	elif src=="false":
		return 0
	elif src=="1":
		return 1
	elif src=="0":
		return 0
	else:
		raise ValueError

def FormatBoolean(src):
	if src:
		return "true"
	else:
		return "false"

def ParseInteger(src):
	if not src:
		raise ValueError
	else:
		sign=1
		off=0
		if src[0]=='-':
			sign=-1
			off=1
		elif src[0]=='+':
			off=1
		src=src[off:]
		if not src.isdigit():
			raise ValueError
		return sign*int(src)

def FormatInteger(src):
	return str(src)

def ParseDecimal(src,totalDigits=None,fractionDigits=None):
	parts=split(src,'.')
	if len(parts)==2:
		integerPart,fractionPart=parts
	elif len(parts)==1:
		integerPart=parts[0]
		fractionPart=''
	else:
		raise ValueError(src)
	sign=1.0
	if integerPart:
		if integerPart[0]=='-':
			sign=-1.0
			integerPart=integerPart[1:]
		elif integerPart[0]=='+':
			integerPart=integerPart[1:]
		if integerPart:
			if not integerPart.isdigit():
				raise ValueError(src)
			mainDigits=len(integerPart)
			value=float(integerPart)*sign
		else:
			value=0.0
	else:
		value=0.0
	if fractionPart:
		if not fractionPart.isdigit():
			raise ValueError(src)
		value=value+float(fractionPart)/float(10**len(fractionPart))
	if not (totalDigits is None) and len(integerPart)+len(fractionPart)>totalDigits:
		raise ValueError("%s exceeds %i total digits"%(src,totalDigits))
	if not (fractionDigits is None) and len(fractionPart)>fractionDigits:
		raise ValueError("%s exceeds %i fractional digits"%(src,fractionDigits))
	return value					

def FormatDecimal(src,totalDigits=None,fractionDigits=None):
	# deal with the minus sign first
	if src<0:
		sign=["-"]
		src=-src
	else:
		sign=[]
	# the canonical representation calls for at least one digit to the right
	# of the decimal point, but later on we'll relax this constraint if totalDigits
	# dictates that we must
	trimFraction=0
	# Now create the string of digits
	if src==0.0:
		digits=[0,0]
		roundPoint=1
		decimalPoint=1
	else:
		exp=int(floor(log10(src)))
		digits=map(lambda x:ord(x)-48,list(str(long(floor(pow(10.0,kMaxSigFig-exp)*src)))))
		if len(digits)>kMaxSigFig+1:
			# we have overflowed
			exp+=1
		elif len(digits)<kMaxSigFig+1:
			# we have underflowed
			exp-=1
			digits.append(0)
		roundPoint=kMaxSigFig
		# Expand digits to ensure that the decimal point falls somewhere in, or just after,
		# the digits it describes
		decimalPoint=exp+1
		if decimalPoint<1:
			# pre-pend zeros
			digits=[0]*(1-decimalPoint)+digits
			roundPoint+=(1-decimalPoint)
			decimalPoint=1
		elif decimalPoint>=len(digits):
			digits=digits+[0]*(decimalPoint-len(digits)+1)
	# Now adjust the rounding position for the requested precision (as necessary)
	if not (totalDigits is None):
		if totalDigits<decimalPoint:
			raise ValueError("%g value exceeds %i total digits"%(src,totalDigits))
		elif totalDigits==decimalPoint:
			# we'll have to trim the fraction
			trimFraction=1
		if totalDigits<roundPoint:
			roundPoint=totalDigits
	if not (fractionDigits is None):
		if decimalPoint+fractionDigits<roundPoint:
			roundPoint=decimalPoint+fractionDigits
	# Now do the rounding, step 1, check for overflow and then zero everything up
	# to and including the round point itself
	overflow=(digits[roundPoint]>4)
	for i in range(len(digits)-1,roundPoint-1,-1):
		digits[i]=0
	# keep rounding until we stop overflowing
	if overflow:
		for i in range(roundPoint-1,-1,-1):
			digits[i]+=1
			if digits[i]>9:
				digits[i]=0
			else:
				overflow=0
				break
		if overflow:
			digits=[1]+digits
			decimalPoint+=1
			roundPoint+=1
			if trimFraction:
				# we were on the limit before, now we've bust it
				raise ValueError("%g value exceeds %i total digits"%(src,totalDigits))
	# Truncate any trailing zeros, except the first zero to the right of the point (maybe)
	trimPoint=len(digits)
	for i in range(len(digits)-1,decimalPoint-trimFraction,-1):
		if digits[i]==0:
			trimPoint=i
		else:
			break
	digits=digits[:trimPoint]
	digits=map(lambda x:chr(48+x),digits)
	return join(sign+digits[:decimalPoint]+['.']+digits[decimalPoint:],'')


def ParseFloat(src):
	parts=split(src,'e')
	if len(parts)==1:
		parts=split(src,'E')
	if len(parts)==2:
		mantissaStr,exponentStr=parts
		mantissa=ParseDecimal(parts[0])
		exponent=ParseInteger(exponentStr)
	elif len(parts)==1:
		mantissa=ParseDecimal(parts[0])
		exponent=0
	else:
		raise ValueError(src)
	return mantissa*pow(10.0,float(exponent))

		
def FormatFloat(src):
	# deal with the minus sign first
	if src<0:
		sign=["-"]
		src=-src
	else:
		sign=[]
	# Now create the string of digits
	if src==0.0:
		digits=[0,0]
		exponent=0
	else:
		exponent=int(floor(log10(src)))
		digits=map(lambda x:ord(x)-48,list(str(long(floor(pow(10.0,kMaxSigFig-exponent)*src)))))
		if len(digits)>kMaxSigFig+1:
			# we have overflowed
			exponent+=1
		elif len(digits)<kMaxSigFig+1:
			# we have underflowed
			exponent-=1
			digits.append(0)
		if digits[kMaxSigFig]>4:
			digits[kMaxSigFig]=0
			for i in range(kMaxSigFig-1,-1,-1):
				digits[i]+=1
				if digits[i]>9:
					digits[i]=0
				else:
					overflow=0
					break
			if overflow:
				digits=[1,0]
				exponent+=1
		# Truncate any trailing zeros, except the first zero to the right of the point
		trimPoint=len(digits)
		for i in range(len(digits)-1,1,-1):
			if digits[i]==0:
				trimPoint=i
			else:
				break
		digits=digits[:trimPoint]
	digits=map(lambda x:chr(48+x),digits)
	return join(sign+digits[:1]+['.']+digits[1:]+['E',FormatInteger(exponent)],'')

class RegularExpressionError(Exception): pass

class RegularExpression:
	def __init__(self,src):
		p=RegularExpressionParser(src)
		try:
			pyre=p.ParseRegularExpression()
			p.ParseEndOfData()
		except RFCSyntaxError,err:
			raise RegularExpressionError(str(err))
		# print "Compiling regular expression %s"%repr(pyre)
		self.p=compile(pyre)
	
	def Match(self,string):
		# print "Matching pattern %s against string %s"%(repr(self.p.pattern),repr(string))
		m=self.p.match(string)
		if m is None or m.end(0)<len(string):
			# print "No Match"
			return 0
		else:
			# print "Match"
			return 1

def IsRENormalChar(c):
	"""The definition of this function is designed to be conservative with
	respect to the specification, which is clearly in error around production
	[10] as the prose and the BNF do not match.  It appears that | was intended
	to be excluded in the prose but has been omitted, the reverse being true
	for the curly-brackets."""
	if c in ".\\?*+{}()[]|":
		return 0
	else:
		return 1

def IsREXmlChar(c):
	return c is not None and c not in "\\-[]"

def IsREXmlCharIncDash(c):
	return c is not None and c not in "\\[]"

SingleCharEscapes={
	'n':chr(0x0A),
	'r':chr(0x0D),
	't':chr(0x09),
	'\\':'\\',
	'|':'|',
	'.':'.',
	'-':'-',
	'^':'^',
	'?':'?',
	'*':'*',
	'+':'+',
	'{':'{',
	'}':'}',
	'(':'(',
	')':')',
	'[':'[',
	']':']'
	}

MultiCharEscapes={
	's':[
		[unichr(9),unichr(10)],
		[unichr(13),unichr(13)],
		[unichr(32),unichr(32)]],
	'S':[
		[unichr(0),unichr(8)],
		[unichr(11),unichr(12)],
		[unichr(14),unichr(31)],
		[unichr(33),unichr(maxunicode)]],
	'i':MakeCharClass(LetterClass+[['_','_'],[':',':']]),
	'I':NegateCharClass(MakeCharClass(LetterClass+[['_','_'],[':',':']])),
	'c':NameCharClass,
	'C':NegateCharClass(NameCharClass),
	'd':CategoryTable['Nd'],
	'D':NegateCharClass(CategoryTable['Nd']),
	'w':NegateCharClass(MakeCharClass(CategoryTable['P']+CategoryTable['Z']+CategoryTable['C'])),
	'W':MakeCharClass(CategoryTable['P']+CategoryTable['Z']+CategoryTable['C'])
	}
	

def FormatPythonCharClass(charClass):
	pyCharSet=[]
	for r in charClass:
		pyCharSet.append(FormatPythonSetChar(r[0]))
		if r[0]==r[1]:
			continue
		if ord(r[1])>ord(r[0])+1:
			pyCharSet.append('-')
		pyCharSet.append(FormatPythonSetChar(r[1]))
	return join(pyCharSet,'')
	
def FormatPythonSetChar(c):
	if c in "-]\\":
		# prepen a backslash
		return "\\"+c
	else:
		return c

class RegularExpressionParser(RFC2234CoreParser):
	def __init__(self,source=None):
		RFC2234Parser.__init__(self,source)
		self.re=[]
		
	def ParseRegularExpression(self,reset=1):
		if reset:
			self.re=[]
		self.ParseBranch()
		if self.theChar=='|':
			self.NextChar()
			self.re.append('|')
			self.ParseBranch()
		return join(self.re,'')
		
	def ParseBranch(self):
		while self.theChar is not None:
			try:
				saveLen=len(self.re)
				self.PushParser()
				self.ParsePiece()
				self.PopParser(0)
			except RFCSyntaxError:
				self.PopParser(1)
				self.re=self.re[:saveLen]
				break
	
	def ParsePiece(self):
		self.ParseAtom()
		if self.theChar is None:
			return
		elif self.theChar in "?*+":
			self.re.append(self.theChar)
			self.NextChar()
		elif self.theChar=='{':	
			try:
				saveLen=len(self.re)
				self.PushParser()
				self.NextChar()
				self.re.append('{')
				self.ParseQuantity()
				if self.theChar=='}':
					self.re.append('}')
					self.NextChar()
				else:
					self.SyntaxError("expected }")
				self.PopParser(0)
			except RFCSyntaxError:
				self.PopParser(1)
				self.re=self.re[:saveLen]
	
	def ParseQuantity(self):
		n=self.ParseDIGITRepeat()
		if n is None:
			self.SyntaxError("expected integer in quantity")
		if self.theChar==',':
			self.NextChar()
			if IsDIGIT(self.theChar):
				m=self.ParseDIGITRepeat()
				if n>m:
					self.SyntaxError("illegal quantity: {%i,%i}"%(n,m))
				self.re.append("%i,%i"%(n,m))
			else:
				self.re.append("%i,"%n)				
		else:
			self.re.append("%i"%n)				

	def ParseAtom(self):
		if IsRENormalChar(self.theChar):
			if self.theChar in ".^$*+?{}\\[]|()":
				self.re.append("\\"+self.theChar)
			else:
				self.re.append(self.theChar)
			self.NextChar()
		elif self.theChar=="\\" or self.theChar==".":
			charClass=self.ParseCharClassEsc()
			if len(charClass)==1 and charClass[0][0]==charClass[0][1]:
				# a single character
				if charClass[0][0] in ".^$*+?{}\\[]|()":
					self.re.append("\\"+charClass[0][0])
				else:
					self.re.append(charClass[0][0])
			else:
				self.re.append("[%s]"%FormatPythonCharClass(charClass))
		elif self.theChar=='[':
			neg,charClass=self.ParseCharClassExpr()
			# now format the charClass into python syntax
			if neg:
				self.re.append("[^%s]"%FormatPythonCharClass(charClass))
			else:
				self.re.append("[%s]"%FormatPythonCharClass(charClass))
		elif self.theChar=='(':
			self.re.append('(')
			self.NextChar()
			self.ParseRegularExpression(0)
			if self.theChar==')':
				self.re.append(')')
				self.NextChar()
			else:
				self.SyntaxError("expected ')'")
		else:
			self.SyntaxError("expected atom")
	
	def ParseCharClassExpr(self):
		if self.theChar!="[":
			self.SyntaxError("expected '['")
		self.NextChar()
		neg,charClass=self.ParseCharGroup()
		if self.theChar!="]":
			self.SyntaxError("expected ']'")
		self.NextChar()
		return neg,charClass
	
	def ParseCharGroup(self):
		charClass=[]		
		if self.theChar=="^":
			neg=1
			self.NextChar()
		else:
			neg=0
		hyphenRange=0
		while self.theChar is not None:
			if self.theChar=="-":
				# a single hyphen is a charRange consisting of one XmlCharIncDash
				# we set this case apart so that we can pick it up later and don't
				# get fooled by things like \--\- which also results in ['-','-']
				self.NextChar()
				hyphenRange=1
				charClass.append(['-','-'])
				continue
			try:
				self.PushParser()
				charClass.append(self.ParseCharRange())
				hyphenRange=0
				self.PopParser(0)
				continue
			except RFCSyntaxError:
				self.PopParser(1)
			try:
				self.PushParser()
				subClass=self.ParseCharClassEsc()
				charClass+=subClass
				hyphenRange=0
				self.PopParser(0)
				continue
			except RFCSyntaxError:
				self.PopParser(1)
			break
		if self.theChar=="[" and hyphenRange:
			# Then we have a subtraction - tricky
			charClass=charClass[:-1]
			subNeg,subClass=self.ParseCharClassExpr()
			# Python doesn't support subtractions, so we have to do the subtraction
			# now, particularly icky if it turns out to be a negative subClass
			subClass=MakeCharClass(subClass)
			if subNeg:
				subClass=NegateCharClass(subClass)
			charClass=SubtractCharClass(MakeCharClass(charClass),subClass)
		return neg,charClass
	
	def ParseCharRange(self):
		self.PushParser()
		try:
			s=self.ParseCharOrEsc()
			if self.theChar=="-":
				self.NextChar()
			else:
				self.SyntaxError("expected '-'")
			e=self.ParseCharOrEsc()
			self.PopParser(0)
		except RFCSyntaxError:
			self.PopParser(1)
			if IsREXmlCharIncDash(self.theChar):
				s=e=self.theChar
				self.NextChar()
			else:
				self.SyntaxError("expected char range")
		if ord(e)<ord(s):
			self.SyntaxError("invalid character range %s-%s"%(s,e))
		return [s,e]

	def ParseCharOrEsc(self):
		if IsREXmlChar(self.theChar):
			c=self.theChar
			self.NextChar()
			return c
		else:
			return self.ParseSingleCharEsc()
	
	def ParseCharClassEsc(self):
		if self.theChar=="\\":
			self.PushParser()
			try:
				c=self.ParseSingleCharEsc()
				self.PopParser(0)
				return [[c,c]]
			except RFCSyntaxError:
				self.PopParser(1)
			self.PushParser()
			try:
				charClass=self.ParseMultiCharEsc()
				self.PopParser(0)
				return charClass
			except RFCSyntaxError:
				self.PopParser(1)
			# we parse Cat and Compl escapes together
			return self.ParseCatEsc()
		elif self.theChar==".":
			return self.ParseMultiCharEsc()
		else:
			self.SyntaxError("expected \\ or .")
						
	def ParseSingleCharEsc(self):
		if self.theChar=="\\":
			self.NextChar()
			c=SingleCharEscapes.get(self.theChar)
			if c is None:
				self.SyntaxError("expected single character escape character")
			self.NextChar()
			return c
		else:
			self.SyntaxError("expected \\")
	
	def ParseCatEsc(self):
		if self.theChar=="\\":
			self.NextChar()
			if self.theChar=="P":
				compl=1
			elif self.theChar=="p":
				compl=0
			else:
				self.SyntaxError("expected category escape")
			self.NextChar()
			if not self.theChar=="{":
				self.SyntaxError("expected {")
			self.NextChar()
			catName=[]
			while IsALPHA(self.theChar) or IsDIGIT(self.theChar) or self.theChar=="-":
				catName.append(self.theChar)
				self.NextChar()
			catName=join(catName,'')
			if len(catName)==2:
				# this one of the general categories
				charClass=CategoryTable.get(catName,None)
				if charClass is None:
					self.SyntaxError("Unknown general category in escape")
			elif len(catName)>2 and catName[:2]=="Is":
				# this is an IsBlock
				r=GetBlockRange(catName[2:])
				if r is None:
					self.SyntaxError("Unrecognized IsBlock in category escape")
				charClass=[r]
			else:
				self.SyntaxError("unrecognized category escape")
			if not self.theChar=="}":
				self.SyntaxError("expected }")
			self.NextChar()
			if compl:
				return NegateCharClass(charClass)
			else:
				return charClass
		else:
			self.SyntaxError("expected \\")

	def ParseMultiCharEsc(self):
		charClass=[]
		if self.theChar=="\\":
			self.NextChar()
			charClass=MultiCharEscapes.get(self.theChar,None)
			if charClass is None:
				self.SyntaxError("unrecognized character escape")
			self.NextChar()
			return charClass
		elif self.theChar==".":
			self.NextChar()
			return [[unichr(0),unichr(9)],[unichr(11),unichr(12)],[unichr(14),unichr(maxunicode)]]
		else:
			self.SyntaxError("expected \\ or .")
	
			