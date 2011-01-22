"""Copyright (c) 2005, University of Cambridge.

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

from types import *
from PyAssess.iso.iso639 import *
from rfc2234 import *
import string

# Subclassed the RFC3066Parser from RFC2234Parser
# Replaced parseHYPHEN_MINUS by RFC2234Parser.ParseTerminal

#-- Syntax Constants --#
RFC3066_PRIMARY_SUBTAG_CC_MIN = 1
RFC3066_PRIMARY_SUBTAG_CC_MAX = 8

RFC3066_SUBTAG_CC_MIN = 1
RFC3066_SUBTAG_CC_MAX = 8

class RFC3066Error(Exception): pass

#-- RFC3066 language_tag object --#
class LanguageTag:
	def __init__(self,lang=None):
		if isinstance(lang,LanguageTag):
			self.primarySubtag=lang.primarySubtag
			self.subtags=lang.subtags[:]
		else:
			self.primarySubtag=None
			self.subtags=[]
			if lang:				
				if not (type(lang) in StringTypes):
					raise TypeError
				parser=RFC3066Parser()
				parser.ResetParser(lang)
				self.primarySubtag=parser.ParsePrimarySubtag()
				while parser.theChar is not None:
					self.subtags.append(parser.ParseSubtag())
				if (len(self.primarySubtag)==1 and not self.primarySubtag in 'iIxX') or \
					len(self.primarySubtag)>3:
					raise RFC3066Error("invalid primary tag: "+self.primarySubtag)
				ccode=GetISO639CanonicalCode(self.primarySubtag)
				if ccode and ccode!=self.primarySubtag.lower():
					raise RFC3066Error("2-character or terminologic code required for: "+self.primarySubtag)
				if self.subtags and len(self.subtags[0])==1:
					raise RFC3066Error("invalid second subtag: "+self.subtags[0])			
	
	def __repr__(self):
		s=str(self)
		if s:
			s=repr(s)
		return "LanguageTag("+s+")"
	
	def __str__(self):
		if self.primarySubtag:
			if self.subtags:
				return self.primarySubtag+"-"+string.join(self.subtags,'-')
			else:
				return self.primarySubtag
		else:
			return ""

	def __cmp__(self,other):
		return cmp(str(self).lower(),str(other).lower())
	
	def __nonzero__(self):
		if self.primarySubtag:
			return 1
		else:
			return 0
	
	def Canonicalize(self):
		if self.primarySubtag:
			if len(self.primarySubtag)==2 or len(self.primarySubtag)==3:
				self.primarySubtag=GetISO639CanonicalCode(self.primarySubtag)
			if self.subtags:
				if len(self.subtags[0])==2:
					self.subtags[0]=self.subtags[0].upper()
				else:
					self.subtags[0]=self.subtags[0].lower()
			for i in range(1,len(self.subtags)):
				self.subtags[i]=self.subtags[i].lower()

class LanguageRange:
	def __init__(self,tag=None):
		self.wildcard=(tag=="*")
		if not self.wildcard:
			self.language=LanguageTag(tag)
			self.language.Canonicalize()
		else:
			self.language=None
	
	def __repr__(self):
		if self.wildcard:
			return "LanguageRange('*')"
		else:
			return "LanguageRange("+repr(str(self.language))+")"
	
	def __str__(self):
		if self.wildcard:
			return "*"
		elif self.language:
			return str(self.language)
		else:
			return ""
				
	def __nonzero__(self):
		if self.wildcard or self.language:
			return 1
		else:
			return 0
	
	def MatchLanguage(self,lang):
		if not isinstance(lang,LanguageTag):
			lang=LanguageTag(lang)
		if not (lang and self):
			# empty language isn't in any range, empty range contains no language
			return 0
		elif self.wildcard:
			return 1
		elif self.language.primarySubtag!=lang.primarySubtag.lower() or \
			len(self.language.subtags)>len(lang.subtags):
			return 0
		else:
			for i in range(len(self.language.subtags)):
				if self.language.subtags[i].lower()!=lang.subtags[i].lower():
					return 0
		return 1
			
class RFC3066Parser(RFC2234CoreParser):
	def __init__(self,):
		RFC2234CoreParser.__init__(self)
		#-- initialise a stack for found/parse language tag objects --#
		self.rfc3066object_stack = []
		self.current_rfc3066object = None
		
		self.tags = self.rfc3066object_stack
	
	def ParsePrimarySubtag(self):
		tag=""
		while IsALPHA(self.theChar) and len(tag)<8:
			tag=tag+self.theChar
			self.NextChar()
		if tag:
			return tag
		else:
			self.SyntaxError("exected primary subtag")
	
	def ParseSubtag(self):
		tag=""
		self.ParseTerminal('-')
		while (IsALPHA(self.theChar) or IsDIGIT(self.theChar)) and len(tag)<8:
			tag=tag+self.theChar
			self.NextChar()
		if tag:
			return tag
		else:
			self.SyntaxError("expected subtag")
