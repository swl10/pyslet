"""Copyright (c) 2004, University of Cambridge.

All rights reserved.

Redistribution and use of this software in source and binary forms
(where applicable), with or without modification, are permitted
provided that the following conditions are met:

 *  Redistributions of source code must retain the above copyright
    notice, this list of conditions, and the following disclaimer.

 *  Redistributions in binary form must reproduce the above
    copyright notice, this list of conditions, and the following
    disclaimer in the documentation and/or other materials provided with
    the distribution.
    
 *  Neither the name of the University of Cambridge, nor the names of
    any other contributors to the software, may be used to endorse or
    promote products derived from this software without specific prior
    written permission.

THIS SOFTWARE IS PROVIDED ``AS IS'', WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."""


import types, random

# We read 64K 
READ_BUFFER_SIZE=65536

#	Exceptions
class RFC2234Error(Exception):pass
class RFC2234RuleError (RFC2234Error):pass

class RFCParserError(Exception):	
	def __init__(self,str,lineNum=None,linePos=None):
		Exception.__init__(self,str)
		self.lineNum=lineNum
		self.linePos=linePos
				
	def __str__(self):
		return self.AppendLineInfo(self.GetStem()+": "+Exception.__str__(self))

	def GetStem(self):
		return "Error"
		
	def AppendLineInfo(self,msg):
		if self.lineNum is not None:
			msg=msg+"; Line "+str(self.lineNum)
			if self.linePos is not None:
				msg=msg+"."+str(self.linePos)
		return msg

class RFCSyntaxError(RFCParserError):
	def GetStem(self):
		return "Syntax Error"

class RFCValidityError(RFCParserError):
	def GetStem(self):
		return "Validity Error"
	
	def AppendLineInfo(self,msg):
		"""We override this method for validity errors because they generally
		relate to what we have just parsed, rather than what we are about to
		parse.  As such, we make the output more approximate (reporting only
		the line number) and if we are at the beginning of a line we report
		the previous line instead to prevent misleading the user."""
		if self.lineNum is not None:
			lineNum=self.lineNum
			if self.linePos is not None:
				if self.linePos==0 and self.lineNum:
					lineNum=self.lineNum-1
			msg=msg+"; Line "+str(lineNum)
		return msg
										
class RFCParserWarning (RFCParserError):
	def GetStem(self):
		return "Warning"


class RFC2234Parser:
	"""
	A general purpose RFC2234 Parser class, the data source can be a string,
	a file or another RFC2234Parser instance.
	"""

	def __init__(self,source=None):
		self.validationMode=RFC2234Parser.kStopOnFatalErrors
		if source is None:
			self.ResetParser("")
		else:
			self.ResetParser(source)

	def ResetParser(self,src,baseLine=0,basePos=0):
		if isinstance(src,RFC2234Parser):
			self.parent=src
			self.theChar=self.parent.theChar
		else:
			self.parent=None
			if type(src) in  (types.StringType,types.UnicodeType):
				self.data=src
				self.dataSource=None
			elif type(src) is types.FileType:
				self.data=''
				self.dataSource=src
			else:
				raise ValueError
			self.lineNum=baseLine
			self.basePos=basePos
			self.dataPos=0
			self.theChar=None
			self.errors=[]
			self.parserStack=[]
			if len(self.data)==0 and self.dataSource:
				self.data=self.dataSource.read(READ_BUFFER_SIZE)
			if len(self.data):
				self.theChar=self.data[0]
			else:
				self.theChar=None
	
	def NextChar (self):
		if self.theChar is not None:
			if self.parent:
				self.parent.NextChar()
				self.theChar=self.parent.theChar
			else:
				self.dataPos=self.dataPos+1
				if self.dataPos>=len(self.data) and self.dataSource:
					if self.parserStack:
						self.data=self.data+self.dataSource.read(READ_BUFFER_SIZE)
					else:
						self.basePos=self.basePos-len(self.data)
						self.data=self.dataSource.read(READ_BUFFER_SIZE)
						self.dataPos=0
				if self.dataPos<len(self.data):
					self.theChar=self.data[self.dataPos]
				else:
					self.theChar=None
	
	def NextLine (self):
		if self.parent:
			self.parent.NextLine()
		else:
			self.lineNum=self.lineNum+1
			self.basePos=self.dataPos
		
	# Constants used for setting validation mode
	kStopOnFatalErrors=0
	kStopOnAllErrors=1
	kStopOnWarnings=2
	
	def SetValidationMode (self,validationMode):
		self.validationMode=validationMode

	# Constants used for passing to the error methods
	kFatal=1
	kNonFatal=0

	def SyntaxError (self,msgStr=None,fatal=1):
		if self.parent:
			self.parent.SyntaxError(msgStr,fatal)
		else:
			self.errors.append(RFCSyntaxError(msgStr,self.lineNum,self.dataPos-self.basePos))
			if fatal or self.validationMode>=RFC2234Parser.kStopOnAllErrors:
				raise self.errors[-1]

	def ValidityError (self,msgStr=None,fatal=1):
		if self.parent:
			self.parent.ValidityError(msgStr,fatal)
		else:
			self.errors.append(RFCValidityError(msgStr,self.lineNum,self.dataPos-self.basePos))
			if fatal or self.validationMode>=RFC2234Parser.kStopOnAllErrors:
				raise self.errors[-1]

	def Warning (self,msgStr=None):
		if self.parent:
			self.parent.Warning(msgStr)
		else:
			self.errors.append(RFCWarning(msgStr,self.lineNum,self.dataPos-self.basePos))
			if self.validationMode==RFC2234Parser.kStopOnWarnings:
				raise self.errors[-1]
	
	def PushParser (self):
		if self.parent:
			self.parent.PushParser()
		else:
			self.parserStack.append((self.lineNum,self.basePos,self.dataPos,self.theChar,len(self.errors)))
	
	def PopParser (self,rewind):
		if self.parent:
			self.parent.PopParser(rewind)
			self.theChar=self.parent.theChar
		else:
			if rewind:
				self.lineNum,self.basePos,self.dataPos,self.theChar,nErrors=self.parserStack.pop()
				del self.errors[nErrors:]
			else:
				self.parserStack.pop()
					
	def ParseTerminal (self,terminal):
		for c in terminal:
			if self.theChar==c:
				self.NextChar()
			else:
				if not IsVCHAR(c):
					expected="expected chr("+str(ord(c))+")"
				else:
					expected="expected '"+c+"'"
				self.SyntaxError(expected)
		return terminal
	
	def ParseLiteral (self,literal):
		result=""
		for c in literal.lower():
			if self.theChar is not None and self.theChar.lower()==c:
				result=result+self.theChar
				self.NextChar()
			else:
				if not IsVCHAR(c):
					expected="expected chr("+str(ord(c))+")"
				else:
					expected='expected "'+c+'"'
				self.SyntaxError(expected)
		return result
	
	def ParseValueRange (self,lowerBound,upperBound):
		if self.theChar is not None and ord(self.theChar)>=lowerBound and ord(self.theChar)<=upperBound:
			theChar=self.theChar
			self.NextChar()
			return theChar
		else:
			if not IsVCHAR(unichr(lowerBound)) or not IsVCHAR(unichr(upperBound)):
				expected="expected char("+str(lowerBound)+")-chr("+str(upperBound)+")"
			else:
				# VCHAR can only be ASCII so safe to use chr
				expected="expected '"+chr(lowerBound)+"'-'"+chr(upperBound)+"'"
			self.SyntaxError(expected)

	def ParseEndOfData(self):
		if self.theChar is not None:
			self.SyntaxError("expected end-of-data")
		

#	Common Terminals
CR=chr(0x0D)
DQUOTE=chr(0x22)
HTAB=chr(0x09)
LF=chr(0x0A)
SP=chr(0x20)
#	CRLF
CRLF=CR+LF

#	Some utility functions for core syntax productions
def IsALPHA(c):
	return c and ((ord(c)>=0x41 and ord(c)<=0x5A) or (ord(c)>=0x61 and ord(c)<=0x7A))

def IsBIT(c):
	return c=='0' or c=='1'

def IsCHAR(c):
	return c and ord(c)<=0x7F

def IsCR(c):
	return c==CR

def IsCTL(c):
	return c is not None and (ord(c)<=0x1F or ord(c)==0x7F)

def IsDIGIT(c):
	return c and (ord(c)>=0x30 and ord(c)<=0x39)
	
def IsDQUOTE(c):
	return c==DQUOTE

def IsHEXDIG(c):
	return IsDIGIT(c) or (c and ((ord(c)>=0x41 and ord(c)<=0x46) or (ord(c)>=0x61 and ord(c)<=0x66)))

def IsHTAB(c):
	return c==HTAB

def IsLF(c):
	return c==LF

def IsOCTET(c):
	return c is not None and (ord(c)<=0xFF)
	
def IsSP(c):
	return c==SP

def IsVCHAR(c):
	return c and (ord(c)>=0x21 and ord(c)<=0x7E)

def IsWSP(c):
	return c==SP or c==HTAB

class RFC2234CoreParser (RFC2234Parser):
	
	def ParseRepeat (self,testFunction):
		result=""
		while testFunction(self.theChar):
			result=result+self.theChar
			self.NextChar()
		return result
		
	def ParseALPHA (self):
		if IsALPHA(self.theChar):
			theChar=self.theChar
			self.NextChar()
			return theChar
		else:
			self.SyntaxError('expected ALPHA')
	
	def ParseBIT (self):
		if IsBIT(self.theChar):
			bit=self.theChar
			self.NextChar()
			return bit=="1"
		else:
			self.SyntaxError("expected BIT")

	def ParseBITRepeat (self):
		value=-1
		while IsBIT(self.theChar):
			if value<0:
				value=(self.theChar=="1")
			else:
				value=value*2+(self.theChar=="1")
			self.NextChar()
		return value
		
	def ParseCHAR (self):
		if IsCHAR(self.theChar):
			theChar=self.theChar
			self.NextChar()
			return theChar
		else:
			self.SyntaxError("expected CHAR")
	
	def ParseCR (self):
		if IsCR(self.theChar):
			self.NextChar()
			return CR
		else:
			self.SyntaxError("expected CR")
	
	def ParseCRLF (self):
		if IsCR(self.theChar):
			self.NextChar()
			if IsLF(self.theChar):
				self.NextChar()
				self.NextLine()
				return CRLF
		self.SyntaxError("expected CRLF")
	
	def ParseCTL (self):
		if IsCTL(self.theChar):
			theChar=self.theChar
			self.NextChar()
			return theChar
		else:
			self.SyntaxError("expected CTL")
	
	def ParseDIGIT (self):
		if IsDIGIT(self.theChar):
			value=ord(self.theChar)-ord('0')
			self.NextChar()
			return value
		else:
			self.SyntaxError("expected DIGIT")

	def ParseDIGITRepeat (self):
		value=None
		while IsDIGIT(self.theChar):
			if value is None:
				value=ord(self.theChar)-ord('0')
			else:
				value=value*10+(ord(self.theChar)-ord('0'))
			self.NextChar()
		return value
		
	def ParseDQUOTE (self):
		if IsDQUOTE(self.theChar):
			self.NextChar()
			return DQUOTE
		else:
			self.SyntaxError("expected DQUOTE")
	
	def ParseHEXDIG (self):
		value=-1
		if self.theChar:
			theCharCode=ord(self.theChar)
			if IsDIGIT(self.theChar):
				value=theCharCode-ord('0')
			elif (theCharCode>=ord('a') and theCharCode<=ord('f')):
				value=theCharCode-ord('a')+10
			elif (theCharCode>=ord('A') and theCharCode<=ord('F')):
				value=theCharCode-ord('A')+10
		if value>=0:
			self.NextChar()
			return value
		else:
			self.SyntaxError("expected HEXDIG")
			
	def ParseHEXDIGRepeat (self):
		value=None
		while self.theChar:
			theCharCode=ord(self.theChar)
			if IsDIGIT(self.theChar):
				digitValue=theCharCode-ord('0')
			elif (theCharCode>=ord('a') and theCharCode<=ord('f')):
				digitValue=theCharCode-ord('a')+10
			elif (theCharCode>=ord('A') and theCharCode<=ord('F')):
				digitValue=theCharCode-ord('A')+10
			else:
				break
			if value is None:
				value=digitValue
			else:
				value=value*16+digitValue
			self.NextChar()
		return value
			
	def ParseHTAB (self):
		if IsHTAB(self.theChar):
			self.NextChar()
			return HTAB
		else:
			self.SyntaxError("expected HTAB")
	
	def ParseLF (self):
		if IsLF(self.theChar):
			self.NextChar()
			return LF
		else:
			self.SyntaxError("expected LF")

	def ParseLWSP (self):
		lwsp=""
		while 1:
			if IsWSP(self.theChar):
				lwsp=lwsp+self.theChar
				self.NextChar()
			elif IsCR(self.theChar):
				try:
					self.PushParser()
					lwsp=lwsp+(self.ParseCRLF()+self.ParseWSP())
					self.PopParser(0)
				except RFC2234Error:
					self.PopParser(1)
					break
		return lwsp

	def ParseOCTET (self):
		if IsOCTET(self.theChar):
			theChar=self.theChar
			self.NextChar()
			return theChar
		else:
			self.SyntaxError("expected OCTET")
		
	def ParseSP (self):
		if self.theChar==0x20:
			self.NextChar()
			return ' '
		else:
			self.SyntaxError("expected SP")

	def ParseVCHAR (self):
		theCharCode=ord(self.theChar)
		if theCharCode>=0x21 and theCharCode<=0x7E:
			theChar=self.theChar
			self.NextChar()
			return theChar
		else:
			self.SyntaxError("expected VCHAR")
	
	def ParseWSP (self):
		if IsWSP(self.theChar):
			theChar=self.theChar
			self.NextChar()
			return theChar
		else:
			self.SyntaxError("expected WSP")


#	Our parsers can parse several different types of object
kUndefinedRule=0	# A pattern that has not been defined
kTerminalRule=1		# A string of characters to be matched literally
kLiteralRule=2		# A string of characters to be matched literally case-insensitive
kValueRangeRule=3	# A tuple of two values representing lower and upper bounds on a single value
kSequenceRule=4		# A tuple of elements that must appear in sequence
kAlternativeRule=5	# A tuple of elements, one of which must appear
kRepeatRule=6		# A tuple of min and max count followed directly by the next element
kProseRule=7		# A string of character representing a human-readable description of the rule
kAliasRule=8		# A simple pointer to a different rule

#	Our parses recognize two types of rule
kBasicRule=0
kIncrementalRule=1

class RFC2234ABNFRuleBase:
	def __init__(self):
		self.Reset()
	
	def Reset (self):	
		self.rules={}
		self.ruleID={}
		self.nextRuleID=0
	
	def AddRule (self,rule):
		for r in self.rules:
			# This loop slows us down but the trade is a tidying ruleBase with no repeated
			# patterns unless they form identically defined rules with different names
			if rule==self.rules[r][1:]:
				return r
		ruleID=self.nextRuleID
		self.nextRuleID=self.nextRuleID+1
		self.rules[ruleID]=[None]+rule
		return ruleID

	def DeclareRule (self,ruleName):
		# If rule name is already declared, returns the existing ruleID
		lcRuleName=ruleName.lower()
		if self.ruleID.has_key(lcRuleName):
			return self.ruleID[lcRuleName]
		else:
			ruleID=self.nextRuleID
			self.nextRuleID=self.nextRuleID+1
			self.rules[ruleID]=[ruleName,kUndefinedRule]
			self.ruleID[lcRuleName]=ruleID
			return ruleID
	
	def DefineRule (self,ruleName,ruleType,ruleID):
		lcRuleName=ruleName.lower()
		rule=self.rules[ruleID]
		if ruleType==kBasicRule:
			# This is a basic rule definition
			if self.ruleID.has_key(lcRuleName):
				# Already defined
				oldID=self.ruleID[lcRuleName]
				oldRule=self.rules[oldID]
				if oldRule[1]==kUndefinedRule:
					if rule[0]:
						# This rule already has a name, so we use the old ruleID instead
						ruleID=oldID
						self.rules[ruleID]=[ruleName]+rule[1:]
					else:
						# Turn the old rule into an alias, best removed later during compaction
						self.rules[oldID]=[None,kAliasRule,ruleID]
						rule[0]=ruleName
				else:
					raise RFC2234RuleError(ruleName)
			elif  rule[0]:
				# This rule already has a name, duplicate it
				ruleID=self.nextRuleID
				self.nextRuleID=self.nextRuleID+1
				self.rules[ruleID]=[ruleName]+rule[1:]
			else:
				# Simple case, just add the name to the rule
				rule[0]=ruleName
		else:
			# Incremental rule, combine old and new in a new rule
			if not self.ruleID.has_key(lcRuleName):
				raise RFC2234RuleError(ruleName)
			basicID=self.ruleID[ruleName]
			basicRule=self.rules[basicID]
			if basicRule[1]==kUndefinedRule:
				raise RFC2234RuleError(ruleName)
			newRuleID=self.nextRuleID
			self.nextRuleID=self.nextRuleID+1
			self.rules[newRuleID]=[ruleName,kAlternativeRule,basicID,ruleID]
			self.rules[basicID][0]=None
			ruleID=newRuleID
		self.ruleID[lcRuleName]=ruleID

	def GetRuleID (self,ruleName):
		lcRuleName=ruleName.lower()
		if self.ruleID.has_key(lcRuleName):
			return self.ruleID[lcRuleName]
		else:
			raise RFC2234RuleError(ruleName)

	def PrintRuleBase (self):
		result=""
		ruleNames=self.ruleID.keys()
		ruleNames.sort()
		for r in ruleNames:
			result=result+self.PrintRuleDefinition(r)+CRLF
		return result
	
	def PrintRuleDefinition (self,ruleName):
		ruleID=self.GetRuleID(ruleName)
		return self.rules[ruleID][0]+" = "+self.PrintRule(ruleID,0,1)
		
	def PrintRule (self,ruleID,bracket=0,expandRule=0):
		rule=self.rules[ruleID]
		if not expandRule and rule[0]:
			return rule[0]
		ruleType=rule[1]
		if ruleType==kUndefinedRule:
			return "<undefined>"
		elif ruleType==kTerminalRule:
			terminalStr=rule[2]
			result="%d"+str(ord(terminalStr[0]))
			for c in terminalStr[1:]:
				result=result+"."+str(ord(c))
			return result
		elif ruleType==kLiteralRule:
			return '"'+rule[2]+'"'
		elif ruleType==kValueRangeRule:
			return "%d"+str(rule[2])+"-"+str(rule[3])
		elif ruleType==kSequenceRule:
			if bracket:
				result="("
			else:
				result=""
			result=result+self.PrintRule(rule[2],1)
			for r in rule[3:]:
				result=result+" "+self.PrintRule(r,1)
			if bracket:
				result=result+")"
			return result
		elif ruleType==kAlternativeRule:
			if bracket:
				result="("
			else:
				result=""
			result=result+self.PrintRule(rule[2],1)
			for r in rule[3:]:
				result=result+" / "+self.PrintRule(r,1)
			if bracket:
				result=result+")"
			return result
		elif ruleType==kRepeatRule:
			minRepeat=rule[2]
			maxRepeat=rule[3]
			if minRepeat==0 and maxRepeat==1:
				result="["+self.PrintRule(rule[4],0)+"]"
			elif minRepeat==maxRepeat:
				result=str(minRepeat)+self.PrintRule(rule[4],1)
			else:
				if minRepeat>0:
					result=str(minRepeat)
				else:
					result=""
				result=result+"*"
				if maxRepeat is not None:
					result=result+str(maxRepeat)
				result=result+self.PrintRule(rule[4],1)
			return result
		elif ruleType==kProseRule:
			 return "<"+rule[2]+">"
		elif ruleType==kAliasRule:
			return self.PrintRule(rule[2],bracket)
		else:
			raise RFC2234RuleError("internal rule-base error")

	def GenerateData (self,ruleName,maxOptRepeat):
		result=""
		ruleStack=[(self.GetRuleID(ruleName),None)]
		recursionControl=[0]*len(self.rules)
		while ruleStack:
			ruleID,rulePos=ruleStack.pop()
			rule=self.rules[ruleID]
			ruleType=rule[1]
			if ruleType==kTerminalRule:
				result=result+rule[2]
			elif ruleType==kLiteralRule:
				literalStr=rule[2]
				for c in literalStr:
					if IsALPHA(c):
						if random.randrange(2):
							result=result+c.lower()
						else:
							result=result+c.upper()
					else:
						result=result+c
			elif ruleType==kValueRangeRule:
				if rule[3]>0x7F:
					result=result+unichr(random.randrange(rule[2],rule[3]+1))
				else:
					result=result+chr(random.randrange(rule[2],rule[3]+1))
			elif ruleType==kSequenceRule or ruleType==kAliasRule:
				if rulePos is None:
					rulePos=2
					recursionControl[ruleID]=recursionControl[ruleID]+1
				else:
					rulePos=rulePos+1
				if rulePos<len(rule):
					# push ourselves first
					ruleStack.append((ruleID,rulePos))
					ruleStack.append((rule[rulePos],None))
				else:
					recursionControl[ruleID]=recursionControl[ruleID]-1
			elif ruleType==kAlternativeRule:
				# Select one at random
				if rulePos is None:
					recursionControl[ruleID]=recursionControl[ruleID]+1
					choices=[]
					for r in rule[2:]:
						if recursionControl[r]<maxOptRepeat:
							choices.append(r)
					if not choices:
						raise RFC2234RuleError("too much recursion")
					ruleStack.append((ruleID,1))
					ruleStack.append((choices[random.randrange(len(choices))],None))
				else:
					recursionControl[ruleID]=recursionControl[ruleID]-1
			elif ruleType==kRepeatRule:
				minRepeat=rule[2]
				maxRepeat=rule[3]
				if rulePos is None:
					adjustedMaxOpt=maxOptRepeat-recursionControl[ruleID]
					if adjustedMaxOpt<0:
						adjustedMaxOpt=0
					if maxRepeat is None or maxRepeat>minRepeat+adjustedMaxOpt:
						maxRepeat=minRepeat+adjustedMaxOpt
					rulePos=[random.randrange(minRepeat,maxRepeat+1),0]
					rulePos[1]=rulePos[0]-minRepeat
					recursionControl[ruleID]=recursionControl[ruleID]+rulePos[1]
				else:
					rulePos[0]=rulePos[0]-1
				if rulePos[0]:
					ruleStack.append((ruleID,rulePos))
					ruleStack.append((rule[4],None))
				else:
					recursionControl[ruleID]=recursionControl[ruleID]-rulePos[1]
			elif ruleType==kProseRule:
				raise RFC2234RuleError("can't generate from prose description")
			else:
				raise RFC2234RuleError("internal rule-base error")
		return result
					
	def ValidateData (self,ruleName,data):
		ruleStack=[(self.GetRuleID(ruleName),None,None)]
		errorPos=-1
		pos=0
		parserStack=[(pos,ruleStack)]
		while 1:
			parserStack.sort()
			pos,ruleStack=parserStack[0]
			del parserStack[0]
			if not ruleStack:
				break
			ruleID,rulePos,ruleName=ruleStack.pop()
			try:
				rule=self.rules[ruleID]
				if rule[0]:
					ruleName=rule[0]
				ruleType=rule[1]
				if ruleType==kTerminalRule:
					terminalStr=rule[2]
					match=data[pos:pos+len(terminalStr)]
					if match!=terminalStr:
						raise RFCValidyError("in production "+ruleName)
					pos=pos+len(terminalStr)
				elif ruleType==kLiteralRule:
					literalStr=rule[2].lower()
					match=data[pos:pos+len(literalStr)].lower()
					if match!=literalStr:
						raise RFCValidyError("in production "+ruleName)
					pos=pos+len(literalStr)
				elif ruleType==kValueRangeRule:
					c=data[pos:pos+1]
					if not (c and ord(c)>=rule[2] and ord(c)<=rule[3]):
						raise RFCValidyError("in production "+ruleName)
					pos=pos+1
				elif ruleType==kSequenceRule:
					if rulePos is None:
						rulePos=2
					else:
						rulePos=rulePos+1
					if rulePos<len(rule):
						if rulePos<len(rule)-1: # push ourselves first
							ruleStack.append((ruleID,rulePos,ruleName))
						ruleStack.append((rule[rulePos],None,ruleName))
				elif ruleType==kAlternativeRule:
					if rulePos is None: # first time
						rulePos=2
					else: # recover from failure, try next option
						rulePos=rulePos+1
					if rulePos<len(rule):
						if rulePos<len(rule)-1:
							# Save the parser for all but the last item, adding ourselves
							# to the saved ruleStack ready to recover from failure
							parserStack.append((pos,ruleStack+[(ruleID,rulePos,ruleName)]))
						ruleStack.append((rule[rulePos],None,ruleName))
				elif ruleType==kRepeatRule:
					minRepeat=rule[2]
					maxRepeat=rule[3]
					subRuleID=rule[4]
					if rulePos is None: # first time
						rulePos=0
					else:
						rulePos=rulePos+1
					if rulePos<minRepeat: # Next one is required
						ruleStack.append((ruleID,rulePos,ruleName))
						ruleStack.append((subRuleID,None,ruleName))
					elif maxRepeat is None or rulePos<maxRepeat: # This one is optional
						parserStack.append((pos,ruleStack[:]))
						ruleStack.append((ruleID,rulePos,ruleName))
						ruleStack.append((subRuleID,None,ruleName))
					# else: success
				elif ruleType==kProseRule:
					raise RFC2234RuleError("can't validate against prose description")
				elif ruleType==kAliasRule:
					ruleStack.append((rule[2],None,ruleName))
				else:
					raise RFC2234RuleError("internal rule-base error")
				parserStack.append((pos,ruleStack))
			except RFCValidyError, err:
				if pos>errorPos:
					maxError=err
					errorPos=pos
				if not len(parserStack):
					raise maxError

	
class RFC2234ABNFParser (RFC2234CoreParser):
	
	def __init__(self,ruleBase=None):
		if not ruleBase:
			ruleBase=RFC2234ABNFRuleBase()
		RFC2234CoreParser.__init__(self)
		self.SetRuleBase(ruleBase)
		
	def SetRuleBase (self,ruleBase):
		self.ruleBase=ruleBase
	
	def GetRuleBase (self):
		return self.ruleBase
				
	def ParseRulelist (self):
		loopCount=0
		while self.theChar:
			if IsALPHA(self.theChar):
				self.ParseRule()
			else:
				self.ParseCWspRepeat()
				self.ParseCNl()
			loopCount=loopCount+1
		if not loopCount:
			self.SyntaxError("expected rule, comment or newline")
			
	def ParseRule (self):
		ruleName=self.ParseRulename()
		ruleType=self.ParseDefinedAs()
		ruleID=self.ParseElements()
		self.ParseCNl()
		ruleID=self.ruleBase.DefineRule(ruleName,ruleType,ruleID)
		return ruleID
	
	def ParseRulename (self):
		name=self.ParseALPHA()
		while IsALPHA(self.theChar) or IsDIGIT(self.theChar) or self.theChar=="-":
			name=name+self.theChar
			self.NextChar()
		return name

	def ParseDefinedAs (self):
		self.ParseCWspRepeat()
		if self.theChar=="=":
			self.NextChar()
			if self.theChar=="/":
				self.NextChar()
				result=kIncrementalRule
			else:
				result=kBasicRule
		else:
			self.SyntaxError("expected '='")
		self.ParseCWspRepeat()
		return result

	def ParseElements (self):
		result=self.ParseAlternation()
		self.ParseCWspRepeat()
		return result
	
	def ParseCWsp (self):
		if IsWSP(self.theChar):
			self.NextChar()
		else:
			self.ParseCNl()
			self.ParseWSP()

	def ParseCWspRepeat (self):
		while self.theChar:
			if IsWSP(self.theChar):
				self.NextChar()
			elif IsCR(self.theChar) or self.theChar==";":
				try:
					self.PushParser()
					self.ParseCNl()
					self.ParseWSP()
					self.PopParser(0)
				except:
					self.PopParser(1)
					break
			else:
				break

	def ParseCNl (self):
		# Ignore c-nl
		if self.theChar==";":
			self.ParseComment()
		else:
			self.ParseCRLF()
	
	def ParseComment (self):
		comment=''
		if self.theChar==";":
			self.NextChar()
			while IsWSP(self.theChar) or IsVCHAR(self.theChar):
				comment=comment+self.theChar
				self.NextChar()
			self.ParseCRLF()
			return comment
		else:
			self.SyntaxError("expected ';'")

	def ParseAlternation (self):
		alternation=[kAlternativeRule]
		alternation.append(self.ParseConcatenation())
		while self.theChar:
			try:
				self.PushParser()
				self.ParseCWspRepeat()
				self.ParseLiteral("/")
				self.ParseCWspRepeat()
				alternation.append(self.ParseConcatenation())
				self.PopParser(0)
			except RFC2234Error:
				self.PopParser(1)
				break
		if len(alternation)==2:
			return alternation[1]
		else:
			return self.ruleBase.AddRule(alternation)
			
	def ParseConcatenation (self):
		concatenation=[kSequenceRule]
		concatenation.append(self.ParseRepetition())
		while self.theChar:
			try:
				self.PushParser()
				self.ParseCWsp()
				self.ParseCWspRepeat()
				concatenation.append(self.ParseRepetition())
				self.PopParser(0)
			except RFC2234Error:
				self.PopParser(1)
				break
		if len(concatenation)==2:
			return concatenation[1]
		else:
			return self.ruleBase.AddRule(concatenation)
	
	def ParseRepetition (self):
		if IsDIGIT(self.theChar) or self.theChar=="*":
			minRepeat,maxRepeat=self.ParseRepeat()
			return self.ruleBase.AddRule([kRepeatRule,minRepeat,maxRepeat,self.ParseElement()])
		else:
			return self.ParseElement()
	
	def ParseRepeat (self):
		minRepeat=self.ParseDIGITRepeat()
		if self.theChar=="*":
			self.NextChar()
			maxRepeat=self.ParseDIGITRepeat()
			if minRepeat is None:
				minRepeat=0
		elif minRepeat is None:
			self.SyntaxError("expected DIGIT or '*'")
		else:
			maxRepeat=minRepeat
		return (minRepeat,maxRepeat)
	
	def ParseElement (self):
		if IsALPHA(self.theChar):
			return self.ruleBase.DeclareRule(self.ParseRulename())
		elif self.theChar=="(":
			return self.ParseGroup()
		elif self.theChar=="[":
			return self.ParseOption()
		elif IsDQUOTE(self.theChar):
			return self.ParseCharVal()
		elif self.theChar=="%":
			return self.ParseNumVal()
		elif self.theChar=="<":
			return self.ParseProseVal()				
		else:
			self.SyntaxError("expected element")
			
	def ParseGroup (self):
		if self.theChar=="(":
			self.NextChar()
			self.ParseCWspRepeat()
			result=self.ParseAlternation()
			self.ParseCWspRepeat()
			if self.theChar==")":
				self.NextChar()
				return result
		self.Syntaxerror("expected '('")
	
	def ParseOption (self):
		if self.theChar=="[":
			self.NextChar()
			self.ParseCWspRepeat()
			result=self.ParseAlternation()
			self.ParseCWspRepeat()
			if self.theChar=="]":
				self.NextChar()
				return self.ruleBase.AddRule([kRepeatRule,0,1,result])
		self.SyntaxError("expected '['")
				
	def ParseCharVal (self):
		if IsDQUOTE(self.theChar):
			literalStr=""
			self.NextChar()
			while self.theChar:
				if IsDQUOTE(self.theChar):
					self.NextChar()
					return self.ruleBase.AddRule([kLiteralRule,literalStr])
				theCharCode=ord(self.theChar)
				if theCharCode>=0x20 and theCharCode<=0x7E:
					literalStr=literalStr+self.theChar
					self.NextChar()
				else:
					break
		self.SyntaxError("expected DQUOTE")

	def ParseNumVal(self):
		# Parses a TerminalRule, or ValueRangeRule
		if self.theChar=="%":
			self.NextChar()
			if self.theChar=="b" or self.theChar=="B":
				val=self.ParseBinVal()
			elif self.theChar=="d" or self.theChar=="D":
				val=self.ParseDecVal()
			else:
				val=self.ParseHexVal()
			if type(val) is types.TupleType:
				return self.ruleBase.AddRule([kValueRangeRule,val[0],val[1]])
			else:
				return self.ruleBase.AddRule([kTerminalRule,val])
		else:
			self.SyntaxError("expected num-val")
	
	def ParseBinVal (self):
		if self.theChar=="b" or self.theChar=="B":
			self.NextChar()
			return self.ParseVal(self.ParseBITRepeat)
		else:
			self.SyntaxError("expected bin-val")
						
	def ParseDecVal (self):
		if self.theChar=="d" or self.theChar=="D":
			self.NextChar()
			return self.ParseVal(self.ParseDIGITRepeat)
		else:
			self.SyntaxError("expected dec-val")
						
	def ParseHexVal (self):
		if self.theChar=="x" or self.theChar=="X":
			self.NextChar()
			return self.ParseVal(self.ParseHEXDIGRepeat)
		else:
			self.SyntaxError("expected hex-val")
						
	def ParseVal (self,fValueParser):	
		value=fValueParser()
		if value is None:
			self.SyntaxError("expected value")
		if self.theChar=="-":
			self.PushParser()
			# It's a value range, maybe
			self.NextChar()
			value2=fValueParser()
			if value2 is None:
				# It's a one-value terminal
				self.PopParser(1)
			else:
				# Its a value range, definately
				self.PopParser(0)
				return (value,value2)
		# It's a terminal
		if value>0x7F:
			terminalStr=unichr(value)
		else:
			terminalStr=chr(value)
		while self.theChar==".":
			self.PushParser()
			self.NextChar()
			value=fValueParser()
			if value is None:
				self.PopParser(1)
				break
			else:
				self.PopParser(0)
				if value>0x7F:
					terminalStr=terminalStr+unichr(value)
				else:
					terminalStr=terminalStr+chr(value)
		return terminalStr

	def ParseProseVal (self):
		if self.theChar=="<":
			proseStr=""
			self.NextChar()
			while self.theChar:
				theCharCode=ord(self.theChar)
				if theCharCode==0x3E:
					self.NextChar()
					return self.ruleBase.AddRule([kProseRule,proseStr])
				if theCharCode>=0x20 and theCharCode<=0x7E:
					proseStr=proseStr+self.theChar
					self.NextChar()
				else:
					self.SyntaxError("expected '>'")
		self.SyntaxError("expected '<'")
		