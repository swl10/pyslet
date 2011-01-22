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

from rfc2234 import *
from PyAssess.iso.iso8601 import *

import string
import pdb

# insert following line to set a manual breakpoint
# pdb.set_trace()

RFC2445_MEDIA_TYPE="text"
RFC2445_SUBTYPE="calendar"


class iCalendarObject:
	def __init__(self):
		self.prodid=None
		self.scale=None
		self.method=None
		self.events=[]
		
	def SetProdID (self,prodid):
		self.prodid=prodid
		
	def SetCalendarScale (self,scale):
		self.scale=scale

	def SetMethod (self,method):
		self.method=method
	
	def AddEvent (self,event):
		self.events.append(event)


class iCalendarEvent:
	def __init__(self):
		self.UID=None
		self.timestamp=None
		self.start=None
		self.end=None
		self.summary=None
		self.location=None
		self.organizer=None
		self.attendees=[]
		
	def SetUID (self,uid):
		self.uid=uid
		
	def SetStartDate(self,start):
		self.start=start

	def SetEndDate(self,end):
		self.end=end

	def SetSummary(self,summary):
		self.summary=summary
	
	def SetTimeStamp (self,timestamp):
		self.timestamp=timestamp
	
	def SetLocation (self,location):
		self.location=location

	def SetOrganizer (self,organizer):
		self.organizer=organizer
		
	def AddAttendee (self,attendee):
		self.attendees.append(attendee)
		
class iCalendarPerson:
	def __init__(self):
		self.address=None
		self.commonName=None
		self.language=None
	
	def SetAddress (self,address):
		self.address=address
	
	def SetCommonName (self,commonName):
		self.commonName=commonName
		
	def SetLanguage (self,language):
		self.language=language
						
class iCalendarAttendee(iCalendarPerson): pass
						
class iCalendarOrganizer(iCalendarPerson): pass
						
class iCalendarDateTime:
	def __init__(self):
		self.value=None
		self.tzid=None
	
	def SetValue (self,value):
		self.value=value
	
	def SetTimeZoneID (self,tzid):
		self.tzid=tzid	
		
class iCalendarText:
	def __init__(self):
		self.text=None
		self.language=None
		self.alt=None
	
	def SetText (self,text):
		self.text=text
	
	def SetLanguage (self,language):
		self.language=language
	
	def SetAltRepresentation (self,alt):
		self.alt=alt
		
def IsQSAFECHAR (c):
	return IsWSP(c) or ord(c)==0x21 or (ord(c)>=0x23 and ord(c)<=0x7E) or IsNONUSASCII(c)

def IsSAFECHAR (c):
	return IsWSP(c) or ord(c)==0x21 or (ord(c)>=0x23 and ord(c)<=0x2B) or (ord(c)>=0x2D and ord(c)<=0x39) or \
		(ord(c)>=0x3C and ord(c)<=0x7E) or IsNONUSASCII(c)

def IsVALUECHAR (c):
	return IsWSP(c) or (ord(c)>=0x21 and ord(c)<=0x7E) or IsNONUSASCII(c)
	
def IsNONUSASCII (c):
	return ord(c)>=0x80 and ord(c)<=0xF8

def IsTSAFECHAR (c):
	return ord(c)==0x20 or ord(c)==0x21 or (ord(c)>=0x23 and ord(c)<=0x2B) or \
		(ord(c)>=0x2D and ord(c)<=0x39) or (ord(c)>=0x3C and ord(c)<=0x5B) or \
		(ord(c)>=0x5D and ord(c)<=0x7E) or IsNONUSASCII(c)

		
class RFC2445Parser (RFC2234CoreParser):
	"""A parser for objects described by RFC 2245."""
	
	def __init__(self):
		RFC2234CoreParser.__init__(self)

	def NextChar (self):
		"""
		This parser extends the basic NextChar method to ensure that lines are
		unfolded as the folds are not represented in the higher-level parsing
		rules defined in the RFC.
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
	
	def ParseCalendarObject (self):
		"""
		icalobject = 1*("BEGIN" ":" "VCALENDAR" CRLF
					  icalbody
					  "END" ":" "VCALENDAR" CRLF)

	    icalbody   = calprops component

		calprops   = 2*(
	
					; 'prodid' and 'version' are both REQUIRED,
					; but MUST NOT occur more than once
	
					prodid /version /
	
					; 'calscale' and 'method' are optional,
					; but MUST NOT occur more than once
	
					calscale        /
					method          /
	
					x-prop
					)
	
		component  = 1*(eventc / todoc / journalc / freebusyc /
					/ timezonec / iana-comp / x-comp)
		"""
		self.ParseLiteral('BEGIN:VCALENDAR')
		self.ParseCRLF()
		# First loop parses properties
		properties={}
		ico=iCalendarObject()
		while 1:
			name=self.ParseName().upper()
			if name=="BEGIN":
				# The beginning of some type of component ends the properties
				break
			elif name=="END":
				self.SyntaxError("Empty iCalendar object")
			else:
				# A property
				if properties.has_key(name):
					self.SyntaxError("duplicate "+name+" property")
				if name[:2]=="X-":
					# we ignore X- properties, even duplicates
					self.ParseXProp(name)
				else:
					properties[name]=1
					if name=="VERSION":
						self.ParseVersion()
					elif name=="PRODID":
						ico.SetProdID(self.ParseProdID())
					elif name=="CALSCALE":
						ico.SetCalendarScale(self.ParseScale())
					elif name=="METHOD":
						ico.SetMethod(self.ParseMethod())
					else:
						self.SyntaxError("unknown iCalendar object property: "+name)
		if not properties.get("VERSION"):
			self.SyntaxError("missing VERSION property on iCalendar object")
		if not properties.get("PRODID"):
			self.SyntaxError("missing PRODID property on iCalendar object")
		while 1:
			if self.theChar==":":
				self.NextChar()
			else:
				self.SyntaxError("expected ':'")
			componentName=self.ParseName().upper()
			self.ParseCRLF()
			if componentName=="VEVENT":
				ico.AddEvent(self.ParseEvent())
			elif componentName=="VTODO":
				ico.AddToDo(self.ParseToDo())
			elif componentName=="VJOURNAL":
				ico.AddJournal(self.ParseJournal())
			elif componentName=="VFREEBUSY":
				ico.AddFreeBusy(self.ParseFreeBusy())
			elif componentName=="VTIMEZONE":
				ico.AddTimeZone(self.ParseTimeZone())
			else:
				ico.AddXComponent(self.ParseXComponent(componentName))
			name=self.ParseName().upper()
			if name=="END":
				break
			elif name!="BEGIN":
				self.SyntaxError("Expected BEGIN or END, found "+name)
		self.ParseLiteral(':VCALENDAR')
		self.ParseCRLF()
		return ico
	
	# Methods for Parsing Components follow...

	def ParseEvent (self):
		"""
		eventc     = "BEGIN" ":" "VEVENT" CRLF
					  eventprop *alarmc
					  "END" ":" "VEVENT" CRLF
	
		eventprop  = *(
	
					; the following are optional,
					; but MUST NOT occur more than once
	
					class / created / description / dtstart / geo /
					last-mod / location / organizer / priority /
					dtstamp / seq / status / summary / transp /
					uid / url / recurid /
	
					; either 'dtend' or 'duration' may appear in
					; a 'eventprop', but 'dtend' and 'duration'
					; MUST NOT occur in the same 'eventprop'
	
					dtend / duration /
	
					; the following are optional,
					; and MAY occur more than once
	
					attach / attendee / categories / comment /
					contact / exdate / exrule / rstatus / related /
					resources / rdate / rrule / x-prop
	
					)
		"""		
		event=iCalendarEvent()
		properties={}
		while 1:
			name=self.ParseName().upper()
			if name=="BEGIN" or name=="END":
				# The beginning of an alarm or the end of the event
				break
			else:
				# A property
				if properties.has_key(name):
					self.SyntaxError("duplicate "+name+" property")
				if name=="ATTENDEE":
					event.AddAttendee(self.ParseAttendee())
				elif name=="CLASS":
					properties[name]=1
					event.SetClass(self.ParseClass())
				elif name=="DTEND":
					if properties.has_key('DURATION'):
						self.SyntaxError("DTEND not allowed with DURATION")
					properties[name]=1
					event.SetEndDate(self.ParseDateTimeProperty())
				elif name=="DTSTAMP":
					properties[name]=1
					event.SetTimeStamp(self.ParseDTStamp())
				elif name=="DTSTART":
					properties[name]=1
					event.SetStartDate(self.ParseDateTimeProperty())
				elif name=="DURATION":
					if properties.has_key('DTEND'):
						self.SyntaxError("DURATION not allowed with DTEND")
					properties[name]=1
					event.SetDuration(self.ParseDuration())
				elif name=="LOCATION":
					properties[name]=1
					event.SetLocation(self.ParseTextProperty())
				elif name=="ORGANIZER":
					properties[name]=1
					event.SetOrganizer(self.ParseOrganizer())
				elif name=="SUMMARY":
					properties[name]=1
					event.SetSummary(self.ParseTextProperty())
				elif name=="UID":
					properties[name]=1
					event.SetUID(self.ParseUID())
				elif name[:2]=="X-":
					self.ParseXProp(name)
				else:
					self.SyntaxError("unknown event component property: "+name)
		while name=="BEGIN":
			if self.theChar==":":
				self.NextChar()
			else:
				self.SyntaxError("expected ':'")
			alarmName=self.ParseName().upper()
			self.ParseCRLF()
			if alarmName=="VALARM":
				event.AddAlarm(self.ParseAlarm())
			else:
				self.SyntaxError("unknown event sub-component: "+name)
			name=self.ParseName().upper()
		if name!="END":
			self.SyntaxError("Expected END, found "+name)
		self.ParseLiteral(':VEVENT')
		self.ParseCRLF()
		return event
			
	# Methods for Parsing Properties follow...
	
	def ParseAttendee (self):
		"""
		 attendee   = "ATTENDEE" attparam ":" cal-address CRLF
	
		 attparam   = *(
	
					; the following are optional,
					; but MUST NOT occur more than once
	
					(";" cutypeparam) / (";"memberparam) /
					(";" roleparam) / (";" partstatparam) /
					(";" rsvpparam) / (";" deltoparam) /
					(";" delfromparam) / (";" sentbyparam) /
					(";"cnparam) / (";" dirparam) /
					(";" languageparam) /
	
					; the following is optional,
					; and MAY occur more than once
	
					(";" xparam)
	
					)
		"""
		attendee=iCalendarAttendee()
		parameters={}
		while self.theChar==";":
			self.NextChar()
			name=self.ParseName().upper()
			if self.theChar=="=":
				self.NextChar()
			else:
				self.SyntaxError("expected '='")
			if parameters.has_key(name):
				self.SyntaxError("duplicate "+name+" parameter")
			if name=="CN":
				parameters[name]=1
				attendee.SetCommonName(self.ParseParamValue())
			elif name=="LANGUAGE":
				parameters[name]=1
				attendee.SetLanguage(self.ParseLanguageParam())
			else:
				self.ParseXParam(name)
		if self.theChar==":":
			self.NextChar()
		else:
			self.SyntaxError("expected ':'")
		attendee.SetAddress(self.ParseValue())
		self.ParseCRLF()
		return attendee
	
	def ParseDateTimeProperty (self):
		"""
		dtstart    = "DTSTART" dtstparam ":" dtstval CRLF
	
		dtstparam  = *(
	
					; the following are optional,
					; but MUST NOT occur more than once
	
					(";" "VALUE" "=" ("DATE-TIME" / "DATE")) /
					(";" tzidparam) /
	
					; the following is optional,
					; and MAY occur more than once
	
					  *(";" xparam)
	
					)
	
		dtstval    = date-time / date
		;Value MUST match value type

		dtend      = "DTEND" dtendparam":" dtendval CRLF
	
		dtendparam = *(
	
					; the following are optional,
					; but MUST NOT occur more than once
	
					(";" "VALUE" "=" ("DATE-TIME" / "DATE")) /
					(";" tzidparam) /
	
					; the following is optional,
					; and MAY occur more than once
	
					(";" xparam)
	
					)
	
		dtendval   = date-time / date
		;Value MUST match value type
		"""
		dt=iCalendarDateTime()
		parameters={}
		valueType='DATE-TIME'
		while self.theChar==";":
			self.NextChar()
			name=self.ParseName().upper()
			if self.theChar=="=":
				self.NextChar()
			else:
				self.SyntaxError("expected '='")
			if parameters.has_key(name):
				self.SyntaxError("duplicate "+name+" parameter")
			if name=="VALUE":
				parameters[name]=1
				valueType=self.ParseName().upper()
			elif name=="TZID":
				parameters[name]=1
				dt.SetTimeZoneID(self.ParseTimeZoneID())
			else:
				self.ParseXParam(name)
		if self.theChar==":":
			self.NextChar()
		else:
			self.SyntaxError("expected ':'")
		if valueType=="DATE":
			dt.SetValue(self.ParseDate())
		elif valueType=="DATE-TIME":
			dt.SetValue(self.ParseDateTime())
		else:
			self.SyntaxError("bad value type: "+valueType+" (expected DATE or DATE-TIME)")
		self.ParseCRLF()
		return dt
	
	def ParseDTStamp (self):
		"""
		dtstamp    = "DTSTAMP" stmparam ":" date-time CRLF
	
		stmparam   = *(";" xparam)
		"""
		self.ParseXParams()
		if self.theChar==":":
			self.NextChar()
		else:
			self.SyntaxError("expected ':'")
		stamp=self.ParseDateTime()
		self.ParseCRLF()
		return stamp
	
	def ParseDuration (self):
		"""
		duration   = "DURATION" durparam ":" dur-value CRLF
					  ;consisting of a positive duration of time.
	
		durparam   = *(";" xparam)
		"""
		self.ParseXParams()
		if self.theChar==":":
			self.NextChar()
		else:
			self.SyntaxError("expected ':'")
		duration=self.ParseDurationValue()
		self.ParseCRLF()
						
	def ParseOrganizer (self):
		"""
		organizer  = "ORGANIZER" orgparam ":"
					  cal-address CRLF
	
		orgparam   = *(
	
					; the following are optional,
					; but MUST NOT occur more than once
	
					(";" cnparam) / (";" dirparam) / (";" sentbyparam) /
					(";" languageparam) /
	
					; the following is optional,
					; and MAY occur more than once
	
					(";" xparam)
	
					)
		"""
		organizer=iCalendarOrganizer()
		parameters={}
		while self.theChar==";":
			self.NextChar()
			name=self.ParseName().upper()
			if self.theChar=="=":
				self.NextChar()
			else:
				self.SyntaxError("expected '='")
			if parameters.has_key(name):
				self.SyntaxError("duplicate "+name+" parameter")
			if name=="CN":
				parameters[name]=1
				organizer.SetCommonName(self.ParseParamValue())
			elif name=="LANGUAGE":
				parameters[name]=1
				organizer.SetLanguage(self.ParseLanguageParam())
			else:
				self.ParseXParam(name)
		if self.theChar==":":
			self.NextChar()
		else:
			self.SyntaxError("expected ':'")
		organizer.SetAddress(self.ParseValue())
		self.ParseCRLF()
		return organizer
			
	def ParseProdID (self):
		"""
	    prodid     = "PRODID" pidparam ":" pidvalue CRLF
	
		pidparam   = *(";" xparam)
	
		pidvalue   = text
		"""		
		self.ParseXParams()
		if self.theChar==":":
			self.NextChar()
		else:
			self.SyntaxError("expected ':'")
		id=self.ParseText()
		self.ParseCRLF()
		return id
		
	def ParseScale (self):
		"""
		calscale   = "CALSCALE" calparam ":" calvalue CRLF
	
		calparam   = *(";" xparam)
	
		calvalue   = "GREGORIAN" / iana-token
		"""
		self.ParseXParams()
		if self.theChar==":":
			self.NextChar()
		else:
			self.SyntaxError("expected ':'")
		scale=self.ParseName()
		self.ParseCRLF()
		return scale
	
	def ParseTextProperty (self):
		"""
		location   = "LOCATION locparam ":" text CRLF
	
		locparam   = *(
	
					; the following are optional,
					; but MUST NOT occur more than once
	
					(";" altrepparam) / (";" languageparam) /
	
					; the following is optional,
					; and MAY occur more than once
	
					(";" xparam)
	
					)

		summary    = "SUMMARY" summparam ":" text CRLF
	
		summparam  = *(
	
					; the following are optional,
					; but MUST NOT occur more than once
	
					(";" altrepparam) / (";" languageparam) /
	
					; the following is optional,
					; and MAY occur more than once
	
					(";" xparam)
	
					)
		"""
		t=iCalendarText()
		parameters={}
		while self.theChar==";":
			self.NextChar()
			name=self.ParseName().upper()
			if self.theChar=="=":
				self.NextChar()
			else:
				self.SyntaxError("expected '='")
			if parameters.has_key(name):
				self.SyntaxError("duplicate "+name+" parameter")
			if name=="LANGUAGE":
				parameters[name]=1
				t.SetLanguage(self.ParseLanguageParam())
			elif name=="ALTREP":
				parameters[name]=1
				t.SetAltRepresentation(self.ParseURIParam())
			else:
				self.ParseXParam(name)
		if self.theChar==":":
			self.NextChar()
		else:
			self.SyntaxError("expected ':'")
		t.SetText(self.ParseText())
		self.ParseCRLF()
		return t
	
	def ParseUID (self):
		"""
		uid        = "UID" uidparam ":" text CRLF

		uidparam   = *(";" xparam)
		"""
		self.ParseXParams()
		uid=self.ParseText()
		self.ParseCRLF()
		return uid
		
	def ParseVersion (self):
		self.ParseXParams()
		if self.theChar==":":
			self.NextChar()
		else:
			self.SyntaxError("expected ':'")
		# Deviations from iCalendar version 2.0 must be registered with IANA
		# and their syntax is not given in RFC2445 so we insist upon the literal
		# string "2.0"
		self.ParseLiteral("2.0")
		self.ParseCRLF()
	
	def ParseXProp (self,xname):
		self.CheckXName(xname)
		while self.theChar==";":
			self.NextChar()
			name=self.ParseName().upper()
			if self.theChar=="=":
				self.NextChar()
			else:
				self.SyntaxError("expected '='")
			if name=="LANGUAGE":
				self.ParseLanguageParam()
				break
			else:
				self.ParseXParam(name)
		if self.theChar==":":
			self.NextChar()
		else:
			self.SyntaxError("expected ':'")
		self.ParseText()
		self.ParseCRLF()
	
	# Methods for Parsing Parameters follow...
	
	def ParseLanguageParam (self):
		"""
		languageparam =    "LANGUAGE" "=" language
	
		language = <Text identifying a language, as defined in [RFC 1766]>
		"""		
		tag=""
		while IsALPHA(self.theChar) or self.theChar=="-":
			tag=tag+self.theChar
			self.NextChar()
		return tag

	def ParseTimeZoneID (self):
		"""
		tzidparam  = "TZID" "=" [tzidprefix] paramtext CRLF
	
		tzidprefix = "/"
		
		; We assume that the CRLF is a misprint here as its existence
		; contradicts earlier syntax definitions for content lines
		"""
		if self.theChar=="/":
			self.NextChar()
			prefix="/"
		else:
			prefix=""
		return prefix+self.ParseParamText()
		
	def ParseURIParam (self):
		"""
		altrepparam        = "ALTREP" "=" DQUOTE uri DQUOTE

		uri        = <As defined by any IETF RFC>
		"""
		return self.ParseQuotedString()
				
	def ParseXParams (self):
		while self.theChar==";":
			self.NextChar()
			name=self.ParseName()
			if self.theChar=="=":
				self.NextChar()
			else:
				self.SyntaxError("expected '='")
			self.ParseXParam(name)
			
	def ParseXParam (self,xname):
		"""
		xparam     =x-name "=" param-value *("," param-value)
		"""
		self.CheckXName(xname)
		self.ParseParamValue()
		while self.theChar==",":
			self.NextChar()
			self.ParseParamValue()
	
	# Methods for parsing basic syntax follow...
			
	def ParseName (self):
		# We don't distinguish between iana-token's and x-tokens because the
		# latter match the production for the former anyway.
		name=""
		while IsALPHA(self.theChar) or IsDIGIT(self.theChar) or self.theChar=='-':
			name=name+self.theChar
			self.NextChar()
		if not name:
			self.SyntaxError("expected name")
		return name

	def CheckXName (self,xname):
		xname_parts=string.split(xname,'-')
		if len(xname_parts)<3 or xname_parts[0].upper()!="X":
			self.SyntaxError("bad name for x-prop: "+xname)
		else:
			if len(xname_parts[1])<3:
				# Strictly speaking, this is a syntax error but the crime
				# is committed by Apple's iCal, which we like, so we let
				# them off with a warning.
				self.Warning("bad vendor id in x-prop: "+xname)
				return 0
			else:
				return 1
			
	def ParseParamValue (self):
		"""
		param-value        = paramtext / quoted-string
		"""
		if IsDQUOTE(self.theChar):
			return self.ParseQuotedString()
		else:
			return self.ParamText()
	
	def ParseQuotedString (self):
		"""
		quoted-string      = DQUOTE *QSAFE-CHAR DQUOTE
		"""
		qStr=""
		if IsDQUOTE(self.theChar):
			self.NextChar()
			while not IsDQUOTE(self.theChar):
				if IsQSAFECHAR(self.theChar):
					qStr=qStr+self.theChar
					self.NextChar()
				else:
					self.SyntaxError("expected DQUOTE")
			self.NextChar()
		else:
			self.SyntaxError("expected DQUOTE")
		return qStr
	
	def ParseParamText (self):
		"""
		paramtext  = *SAFE-CHAR
		"""
		pTxt=""
		while IsSAFECHAR(self.theChar):
			pTxt=pTxt+self.theChar
			self.NextChar()
		return pTxt
	
	def ParseText (self):
		"""
		text       = *(TSAFE-CHAR / ":" / DQUOTE / ESCAPED-CHAR)
		; Folded according to description above
	
		ESCAPED-CHAR = "\\" / "\;" / "\," / "\N" / "\n")
			; \\ encodes \, \N or \n encodes newline
			; \; encodes ;, \, encodes ,
		"""
		text=""
		while 1:
			if self.theChar=="\\":
				self.NextChar()
				if self.theChar=="\\":
					text=text+"\\"
				elif self.theChar==";":
					text=text+";"
				elif self.theChar==",":
					text=text+","
				elif self.theChar.lower()=="n":
					text=text+LF
				elif IsDQUOTE(self.theChar):
					# Although it appears to make sense to escape this in text
					# it is not allowed by the syntax.  A bug in iCal?  We
					# surpress the backslash in this case only!
					self.Warning("DQUOTE escaped, working around iCal bug")
					text=text+DQUOTE
				else:
					# Like the previous case, we're in the syntax sin-bin
					# here so we can do what we like.  We choose to treat
					# the intention as a simple backslash.
					self.Warning("unescaped \\ in text")
					text=text+"\\"
			elif IsTSAFECHAR(self.theChar) or self.theChar==":" or IsDQUOTE(self.theChar):
				text=text+self.theChar
			else:
				break
			self.NextChar()
		return text
	
	def ParseDate (self):
		"""
		date               = date-value
	
		date-value         = date-fullyear date-month date-mday
		date-fullyear      = 4DIGIT
		date-month         = 2DIGIT        ;01-12
		date-mday          = 2DIGIT        ;01-28, 01-29, 01-30, 01-31
										   ;based on month/year
		"""
		dateStr=""
		while IsDIGIT(self.theChar):
			dateStr=dateStr+self.theChar
			self.NextChar()
		date=ISODate()
		try:
			syntax=date.ReadISODate(dateStr)
		except ISODateTimeError, err:
			self.SyntaxError(str(err))
		if syntax!='YYYYMMDD':
			self.SyntaxError("date value error")
		return date
	
	def ParseDateTime (self):
		"""
		date-time  = date "T" time ;As specified in the date and time
                                ;value definitions
        time               = time-hour time-minute time-second [time-utc]

		time-hour          = 2DIGIT        ;00-23
		time-minute        = 2DIGIT        ;00-59
		time-second        = 2DIGIT        ;00-60
		;The "60" value is used to account for "leap" seconds.
	
		time-utc   = "Z"
		"""
		dtStr=""
		while IsDIGIT(self.theChar):
			dtStr=dtStr+self.theChar
			self.NextChar()
		# Strictly speaking, literals are case-insensitive in the ABNF
		# but I'm not convinced that "t" is encouraged by ISO8601
		if len(dtStr)!=8 or self.theChar.upper()!="T":
			self.SyntaxError("invalid date-time")
		self.NextChar()
		dtStr=dtStr+"T"
		while IsDIGIT(self.theChar):
			dtStr=dtStr+self.theChar
			self.NextChar()
		if len(dtStr)!=15:
			self.SyntaxError("invalid date-time")
		if self.theChar.upper()=="Z":
			dtStr=dtStr+"Z"
			self.NextChar()
		try:
			timepoint=ISOTimePoint(dtStr)
		except ISODateTimeError, err:
			self.SyntaxError(str(err))
		return timepoint
	
	def ParseDurationValue (self):
		"""
		dur-value  = (["+"] / "-") "P" (dur-date / dur-time / dur-week)
	
		dur-date   = dur-day [dur-time]
		dur-time   = "T" (dur-hour / dur-minute / dur-second)
		dur-week   = 1*DIGIT "W"
		dur-hour   = 1*DIGIT "H" [dur-minute]
		dur-minute = 1*DIGIT "M" [dur-second]
		dur-second = 1*DIGIT "S"
		dur-day    = 1*DIGIT "D"
		"""
		
	def ParseUserTypeParamValue (self):
		return RFC2245UserTypeParameter(self.ParseName().upper())
	
	def ParseDelegatorParamValue (self):
		p=RFC2245DelegatorParameter(self.ParseURIListParamValue())
		
	def ParseDelegateeParamValue (self):
		p=RFC2245DelegateeParameter(self.ParseURIListParamValue())
	
	def ParseDirectoryEntryParamValue (self):
		return RFC2245DirectoryEntryParameter(self.ParseQuotedString())
	
	def ParseEncodingParamValue (self):
		return RFC2245EncodingParameter(self.ParseName().upper())
	
	def ParseFormatTypeParamValue (self):
		# The specification appears to be incorrect here, as FormatType is
		# supposed to be a MIME type, but name is inadequate for this.
		type=self.ParseName()
		return RFC2245FormatTypeParameter(type)

	def ParseFreeBusyTypeParamValue (self):
		return RFC2245FreeBusyParameter(self.ParseName().upper())
	
	def ParseMemberParamValue (self):
		return RFC2245MemberParameter(self.ParseURIListParamValue())
	
	def ParsePartStatusParamValue (self):
		return RFC2245PartStatusParameter(self.ParseName().upper())
	
	def ParseRangeParamValue (self):
		value=self.ParseName().upper()
		if not value in ['THISANDPRIOR','THISANDFUTURE']:
			self.SyntaxError("illegal RANGE parameter value: "+value)
		return RFC2245RangeParameter(value)
				
	def ParseRelatedParamValue (self):
		value=self.ParseName().upper()
		if not value in ['START','END']:
			self.SyntaxError("illegal RELATED parameter value: "+value)
		return RFC2245RelatedParameter(value)
	
	def ParseRelationParamValue (self):
		return RFC2245RelationParameter(self.ParseName().upper())
	
	def ParseRoleParamValue (self):
		return RFC2245RoleParameter(self.ParseName().upper())
	
	def ParseRSPVPParamValue (self):
		value=self.ParseName().upper()
		if not value in ['TRUE','FALSE']:
			self.SyntaxError("illegal RSVP parameter value: "+value)
		return RFC2245RSVPParameter(value=="TRUE")
	
	def ParseSentByParamValue (self):
		return RFC2245SentByParameter(self.ParseQuotedString())
	
	def ParseUnknownParamValue (self,name):
		p=RFC2245UnknownParameter(name)
		while 1:
			if IsDQUOTE(self.theChar):
				value=self.ParseQuotedString()
			else:
				value=self.ParseParamText()
			p.AppendValue(value)
			if self.theChar==",":
				self.NextChar()
			else:
				break
		return p
	
	def ParseURIListParamValue (self):
		values=[]
		while 1:
			if IsDQUOTE(self.theChar):
				value=self.ParseQuotedString()
			else:
				value=self.ParseParamText()
			values.append(p)
			if self.theChar==",":
				self.NextChar()
			else:
				break
		return values
				
	def ParseValue (self):
		value=""
		while IsVALUECHAR(self.theChar):
			value=value+self.theChar
			self.NextChar()
		return value
		
	def ParseContentLine (self):
		line=RFC2245ContentLine()
		line.name=self.ParseName()
		while self.theChar==';':
			self.NextChar()
			self.ParseParam(line)
		if self.theChar==':':
			self.NextChar()
			line.value=self.ParseValue()
			self.ParseCRLF()
		else:
			self.SyntaxError("expected ':' value")
		return line
		

if __name__=='__main__':
	import sys
	p=RFC2445Parser()
	for fName in sys.argv[1:]:
		f=open(fName,'r')
		p.InitParser(f)
		while p.theChar:
			try:
				print str(p.ParseCalendarObject())
			except RFC2234Error, err:
				print err
				break
		f.close()


