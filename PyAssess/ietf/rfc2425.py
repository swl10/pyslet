from rfc2234 import *

import rfc3066

class RFC2425Directory:
	pass

class RFC2425Error(Exception): pass


"""
The definition of NON_ASCII in RFC2425 is consistent with the decision to base ABNF
grammars on streams of octets rather than characters.  The encoding is dealt with
rather quickly in 5.5.  Although one could use codings such as UTF-8 the assumption
is that the stream will be decoded into a stream of octets, rather than characters
and that the rules in the grammar will be applied to those octets.

Problems start when we interpret field values.  Clearly we can use the charset of
the stream to interpret the octets, but if we wish to include characters that don't
appear in the charset they will need to be further encoded.  The encoding parameter
on directory fields supports this interpretation so we'll assuming that values
requiring more interesting values will themselves define a method of encoding their
values into an 8-bit stream (e.g. UTF-7).
"""
def IsNON_ASCII(c):
	return c and (ord(c)>=0x80 and ord(c)<=0xFF)

def IsQSAFE_CHAR(c):
	return c and (IsWSP(c) or
		ord(c)==0x21 or
		(ord(c)>=0x23 and ord(c)<=0x7E) or
		IsNON_ASCII(c))

def IsSAFE_CHAR(c):
	return c and (IsWSP(c) or
		ord(c)==0x21 or
		(ord(c)>=0x23 and ord(c)<=0x2B) or
		(ord(c)>=0x2D and ord(c)<=0x39) or
		(ord(c)>=0x3C and ord(c)<=0x7E) or
		IsNON_ASCII(c))

def IsVALUE_CHAR(c):
	return IsWSP(c) or IsVCHAR(c) or IsNON_ASCII(c)

		
class RFC2425Parser(RFC2234CoreParser):
	def NextChar (self):
		"""
		This parser extends the basic NextChar method to ensure that lines are
		unfolded as the folds are not represented in the higher-level parsing
		rules defined in the RFC.  This does mean that directory based information
		must be parsed from data streams that are not subject to folding in their
		entirety and then fed back into a new parser to access the directory
		information.
		"""
		RFC2234CoreParser.NextChar(self)
		if IsCR(self.theChar):
			folded=0
			self.PushParser()
			RFC2234CoreParser.NextChar(self)
			if IsLF(self.theChar):
				RFC2234CoreParser.NextChar(self)
				self.NextLine()
				if IsWSP(self.theChar):
					RFC2234CoreParser.NextChar(self)
					folded=1
			self.PopParser(not folded)
	
	def ParseContentLine(self):
		group=None
		name=self.ParseNameChars()
		params=[]
		if not name:
			self.SyntaxError("expected name")
		if self.theChar==".":
			self.NextChar()
			group=name
			name=self.ParseNameChars()
			if not name:
				self.SyntaxError("expected name")
		while self.theChar==";":
			self.NextChar()
			params.append(self.ParseParam())
		self.ParseTerminal(":")
		value=self.ParseValue()
		self.ParseCRLF()
		return (group,name,params,value)
		
	def GetEncodingParam(self,plist):
		return self.GetTokenParam(plist,"encoding")

	def GetValuetypeParam(self,plist):
		return self.GetTokenParam(plist,"valuetype")
	
	def GetLanguageParam(self,plist):
		for i in range(len(plist)):
			p=plist[i]
			if p[0].lower()=="language":
				value=p[1]
				del plist[i]
				if len(value)!=1:
					raise RFC2425Error('bad language: "'+string.join(p[1],'","')+'"')
				else:					
					value=rfc3066.LanguageTag(value[0])
					if not value:
						raise RFC2425Error("empty language")
					return value
		return None
		
	def GetContextParam(self,plist):
		return self.GetTokenParam(plist,"context")
	
	def GetTokenParam(self,plist,name):
		for i in range(len(plist)):
			p=plist[i]
			if p[0].lower()==name:
				token=p[1]
				del plist[i]
				if len(token)!=1:
					raise RFC2425Error('bad '+name+': "'+string.join(p[1],'","')+'"')
				else:
					token=token[0]
					if token:			
						for c in token:
							if not (IsALPHA(c) or IsDIGIT(c) or c=="-"):
								raise RFC2425Error('bad '+name+': '+p[1][0])
						return token
					else:
						raise RFC2425Error("empty "+name)
		return None
						
	def ParseGroup(self):
		group=self.ParseNameChars()
		if group:
			return group
		else:
			self.SyntaxError("expected group")
	
	def ParseName(self):
		name=self.ParseNameChars()
		if name:
			return name
		else:
			self.SyntaxError("expected name")
	
	def ParseIANAToken(self):
		"""The ABNF seems deficient here because this production includes
		tokens starting with the extension string "x-", even though there
		is clearly never any intention of registering these with the IANA.
		RFC2425 doesn't seem to discuss this point outside the ABNF either."""
		name=self.ParseNameChars()
		if name:
			return name
		else:
			self.SyntaxError("expected iana-token")

	def ParseXName(self):
		xname=self.ParseLiteral("x-")
		xname=xname+self.ParseNameChars()
		if len(xname)>2:
			return xname
		else:
			self.SyntaxError("expected x-name")

	def ParseParam(self):
		pname=self.ParseParamName()
		self.ParseTerminal("=")
		pvalue=[self.ParseParamValue()]
		while self.theChar==',':
			try:
				self.PushParser()
				self.NextChar()
				pvalue.append(self.ParseParamValue())
				self.PopParser(0)
			except RFCSyntaxError:
				self.PopParser(1)
				break
		return (pname,pvalue)
			
	def ParseParamName(self):
		name=self.ParseNameChars()
		if name:
			return name
		else:
			self.SyntaxError("expected param-name")
					
	def ParseParamValue(self):
		if IsDQUOTE(self.theChar):
			return self.ParseQuotedString()
		else:
			return self.ParsePText()

	def ParseQuotedString(self):
		self.ParseDQUOTE()
		value=""
		while IsQSAFE_CHAR(self.theChar):
			value=value+self.theChar
			self.NextChar()
		self.ParseDQUOTE()
		return value
				
	def ParsePText(self):
		ptext=""
		while IsSAFE_CHAR(self.theChar):
			ptext=ptext+self.theChar
			self.NextChar()
		return ptext
		
	def ParseValue(self):
		value=""
		while IsVALUE_CHAR(self.theChar):
			value=value+self.theChar
			self.NextChar()
		return value
	
	def ParseNameChars(self):
		result=""
		while IsDIGIT(self.theChar) or IsALPHA(self.theChar) or self.theChar=='-':
			result=result+self.theChar
			self.NextChar()
		return result
	
