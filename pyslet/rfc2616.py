#! /usr/bin/env python

HTTP_PORT=80
HTTPS_PORT=443
HTTP_VERSION="HTTP/1.1"

SOCKET_TIMEOUT=120
SOCKET_CHUNK=8192

import string
import time
import datetime
import socket
import urlparse
import select
import types
import base64
from pyslet.rfc2616_core import *
from pyslet.rfc2616_params import *
from pyslet.rfc2616_headers import *
from pyslet.rfc2617 import *
import pyslet.rfc2396 as uri

HTTP_LOG_NONE=0
HTTP_LOG_ERROR=1
HTTP_LOG_INFO=2
HTTP_LOG_DETAIL=3
HTTP_LOG_DEBUG=4
HTTP_LOG_ALL=5

class HTTP2616ConnectionBusy(HTTPException): pass
class HTTP2616ConnectionClosed(HTTPException): pass



class HTTPRelativeQualityToken:
	def __init__(self,token="*",q=None):
		self.token=token
		self.q=q

	def __str__(self):
		if self.q is not None:
			if self.q==0:
				formatStr="%s;q=0"%self.token
			else:
				formatStr="%s;q=%.3f"%(self.token,self.q)
				if formatStr[-2:]=='00':
					formatStr=formatStr[:-2]
				elif formatStr[-1]=='0':
					formatStr=qStr[:-1]
		else:
			formatStr=self.token
		return formatStr

				
def ParseRelativeQualityToken(words,rqToken,pos=0):
	mode=None
	nWords=0
	while pos<len(words):
		word=words[pos]
		pos=pos+1
		if mode==None:
			if word[0] in HTTP_SEPARATORS:
				break
			rqToken.token=word
			rqToken.q=None
			mode=';'
			nWords+=1
		elif mode==';':
			if word==mode:
				mode='q'
			else:
				break
		elif mode=='q':
			if word==mode:
				mode='='
			else:
				break
		elif mode=='=':
			if word==mode:
				mode='#'
			else:
				break
		elif mode=='#':
			try:
				rqToken.q=float(word)
			except ValueError:
				# If the q value is not a float, then we stop the parser just before the ';'
				break
			# If q value is a float, but an invalid one, then we just contrain it silently
			# be generous with what you accept and all that.
			if rqToken.q<0:
				rqToken.q=0
			elif rqToken.q>1.0:
				rqToken.q=1.0
			nWords+=4
	return nWords

class HTTPETag:
	def __init__(self):
		self.weak=False
		self.tag=None

def ParseETag(words,eTag,pos=0):
	mode=None
	nWords=0
	token=None
	while pos<len(words):
		word=words[pos]
		pos=pos+1
		if mode==None:
			if word.upper()=='W':
				eTag.weak=True
				nWords+=1
				mode='/'
			else:
				# optional weak specifier not found, try again with strong tag
				eTag.weak=False
				pos=pos-1
				mode=DQUOTE
		elif mode=='/':
			if word[0]=='/':
				nWords+=1
				mode=DQUOTE
			else:
				# Looked like a weak tag but wasn't, we're done
				nWords=0
				break
		elif mode==DQUOTE:
			if word[0]==DQUOTE:
				eTag.tag=DecodeQuotedString(word)
				nWords+=1
			else:
				nWords=0
				break
	return nWords

	
def CheckToken(t):
	for c in t:
		if c in HTTP_SEPARATORS:
			raise ValueError("Separator found in token: %s"%t)
		elif IsCTL(c) or not IsCHAR(c):
			raise ValueError("Non-ASCII or CTL found in token: %s"%t)

HTTP_DAY_NUM={
	"monday":0, "mon":0,
	"tuesday":1, "tue":1,
	"wednesday":2, "wed":2,
	"thursday":3, "thu":3,
	"friday":4, "fri":4,
	"saturday":5, "sat":5,
	"sunday":6, "sun":6 }

# Note that in Python time/datetime objects Jan has index 1!
HTTP_MONTH_NUM={
	"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12
	}
	
def ParseDate(dateStr):
	date=string.split(dateStr.strip().lower())
	if len(date)==4:
		# e.g., "Sunday, 06-Nov-94 08:49:37 GMT"
		date=date[0:1]+date[1].split('-')+date[2].split(':')+date[3:]
	elif len(date)==5:
		# e.g., "Sun Nov  6 08:49:37 1994"
		date=[date[0]+',',date[2],date[1],date[4]]+date[3].split(':')+['gmt']
	elif len(date)==6:
		# e.g., "Sun, 06 Nov 1994 08:49:37 GMT" - the preferred format!
		date=date[0:4]+date[4].split(':')+date[5:]
	if len(date)!=8:
		raise ValueError("Badly formed date: %s"%dateStr)
	wday=HTTP_DAY_NUM[date[0][:-1]]
	mday=int(date[1])
	mon=HTTP_MONTH_NUM[date[2]]
	year=int(date[3])
	# No obvious guidance on base year for two-digit years by HTTP was
	# first used in 1990 so dates before that are unlikely!
	if year<90:
		year=year+2000
	elif year<100:
		year=year+1900
	hour=int(date[4])
	min=int(date[5])
	sec=int(date[6])
	if date[7]!='gmt':
		raise ValueError("HTTP date must have GMT timezone: %s"%dateStr)
	result=datetime.datetime(year,mon,mday,hour,min,sec)
	if result.weekday()!=wday:
		raise ValueError("Weekday mismatch in: %s"%dateStr)
	return result


HTTP_DAYS=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
HTTP_MONTHS=["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

def FormatDate(date):
	# E.g., "Sun, 06 Nov 1994 08:49:37 GMT"
	return "%s, %02i %s %04i %02i:%02i:%02i GMT"%(
			HTTP_DAYS[date.weekday()],
			date.day,
			HTTP_MONTHS[date.month],
			date.year,
			date.hour,
			date.minute,
			date.second)



class HTTPRequestManager:
	def __init__(self):
		self.requestQueue=[]
		self.connections={}
		self.nextConnection=None
		self.credentials=[]
		self.socketSelect=select.select
		self.dnsCache={}
		self.logLevel=HTTP_LOG_NONE
		self.logStream=None
		self.logLineLen=80
		self.logString=''
		self.httpUserAgent="pyslet.rfc2616.HTTPRequestManager"
		
	def SetLog(self,level,logStream=None,lineLen=80):
		self.logLevel=level
		self.logStream=logStream
		self.logLineLen=lineLen
		
	def Log(self,level,logString):
		"""A method that prints a string to a log of some sort.  The string is
		qualified with a level from the contstants defined at the top of the
		file."""
		if level<=self.logLevel and logString!=self.logString:
			if len(logString)>self.logLineLen:
				print >> self.logStream, logString[:self.logLineLen]+'... + %i chars'%(len(logString)-self.logLineLen)
			else:
				print >> self.logStream, logString
			self.logString=logString			

	def AddCredentials(self,credentials):
		self.credentials.append(credentials)
	
	def FindCredentials(self,challenge):
		for c in self.credentials:
			if c.Match(challenge):
				return c
	
	def DNSLookup(self,host,port):
		if (host,port) not in self.dnsCache:
			self.Log(HTTP_LOG_DETAIL,"Looking up %s"%host)
			self.dnsCache[(host,port)]=socket.getaddrinfo(host,port, 0, socket.SOCK_STREAM)
		return self.dnsCache[(host,port)]
		
	def ProcessRequest(self,request,timeout=60):
		self.QueueRequest(request)
		self.ManagerLoop(timeout)
		
	def QueueRequest(self,request):
		"""Commits a request to the queue for processing.
		
		The default implementation adds a User-Agent header from
		:py:attr:`httpUserAgent` if not None.  You can override this method to
		add other headers appropriate for a specific context prior to passing on
		to this call.

		The request is added to the internal request queue and the request is
		notified that is being actively managed through a call to
		:py:meth:`HTTPRequest.SetManager`."""
		if self.httpUserAgent:
			request.SetHeader('User-Agent',self.httpUserAgent)
		self.requestQueue.append(request)
		request.SetManager(self)

	def ManagerLoop(self,timeout=60):
		while True:
			self.ProcessQueue()
			if self.ProcessConnections(timeout) and not self.requestQueue:
				# it is possible that the connections all went idle but
				# that the queue has been re-filled (e.g., by redirects)
				# We must only break if we really are done!
				break
		self.Close()

	def Close(self):
		for connection in self.connections.values():
			connection.Close()
		
	def ProcessQueue(self):
		while self.requestQueue:
			request=self.requestQueue[0]
			if self.nextConnection:
				if self.nextConnection.StartRequest(request):
					self.nextConnection=None
					self.requestQueue=self.requestQueue[1:]
				else:
					# Connection is not ready for us
					break
			else:
				# Find or create a connection for the next request
				key=(request.scheme,request.hostname,request.port)
				self.nextConnection=self.connections.get(key,None)
				if self.nextConnection is None:
					self.nextConnection=self.NewConnection(key[0],key[1],key[2])
					self.connections[key]=self.nextConnection			
				
	def ProcessConnections(self,timeout):
		"""Processes the connections blocking for at most timeout (where possible).
		Returns True if the connections are all idle, otherwise returns False."""
		readers=[]
		writers=[]
		for c in self.connections.values():
			r,w=c.ConnectionTask()
			if r:
				readers.append(r)
			if w:
				writers.append(w)
		if not readers and not writers:
			return True
		else:
			try:
				self.ManagerTask()
				self.Log(HTTP_LOG_DETAIL,"Socket select for: readers=%s, writers=%s, timeout=%i"%(repr(readers),repr(writers),timeout))
				r,w,e=self.socketSelect(readers,writers,[],timeout)
			except select.error, err:
				pass
			# We don't bother checking as we'll just go around the loop and find the connection
			# concerned anyway
			return False
		
	def NewConnection(self,scheme,host,port):
		if scheme=='http':
			return HTTPConnection(self,host,port)
		elif scheme=='https':
			return HTTPSConnection(self,host,port)
		else:
			raise ValueError

	def ManagerTask(self):
		"""Designed to allow sub-classing for periodic tasks during idle time such as
		updating status displays"""
		pass
		

class HTTPConnection:
	# States
	REQ_READY=0
	REQ_BODY_WAITING=1
	REQ_BODY_SENDING=2
	CLOSE_WAIT=3
	
	IDEMPOTENT={"GET":1,"HEAD":1,"PUT":1,"DELETE":1,"OPTIONS":1,"TRACE":1,"CONNECT":0,"POST":0}
	
	def __init__(self,manager,host,port=HTTP_PORT):
		self.manager=manager
		self.host=host
		self.port=port
		self.request=None
		self.requestMode=self.REQ_READY
		self.continueWaitMax=60.0	# If we don't get a continue in 1 minute, send the data anyway
		self.continueWaitStart=0
		self.response=None
		self.responseQueue=[]
		# Low-level socket members
		self.socket=None
		self.socketFile=None
		self.sendBuffer=[]
		self.recvBuffer=[]
		self.recvBufferSize=0

	def __repr__(self):
		return "HTTP(%s,%i)"%(self.host,self.port)
		
	def StartRequest(self,request):
		"""Starts processing the request.  Returns True if the request has
		been accepted for processing, False otherwise."""
		if self.requestMode!=self.REQ_READY:
			return False
		elif self.response and not self.IDEMPOTENT.get(request.method,0):
			# We are waiting for a response and will only accept idempotent methods
			return False
		self.request=request
		self.request.SetConnection(self)
		headers=self.request.ReadRequestHeader()
		for h in headers.split(CRLF):
			self.manager.Log(HTTP_LOG_DETAIL,"Request header: %s"%h)
		self.sendBuffer.append(headers)
		# Now check to see if we have an expect header set
		if self.request.GetExpectContinue():
			self.requestMode=self.REQ_BODY_WAITING
			self.continueWaitStart=0
		else:
			self.requestMode=self.REQ_BODY_SENDING
		if self.response:
			# Queue a response as we're still handling the last one!
			self.responseQueue.append(HTTPResponse(self.request))
		else:
			self.response=HTTPResponse(self.request)
		return True
		
	def RequestDisconnect(self):
		# Request wants us to hang up during request processing, in CLOSE_WAIT,
		# we refuse new requests but finish processing any responses before closing the
		# connection.
		self.request.Disconnect()
		self.request=None
		if self.response:
			self.sendBuffer=[]
			self.requestMode=self.CLOSE_WAIT
		else:
			self.Close()
			
	def ReadyToStart(self,request):
		# Are we ready to start sending a new request?
		# in the future we can add support for pipelining
		if self.request:
			# If we are currently processing a request, we're busy
			return False
		elif self.response and not self.IDEMPOTENT.get(request.method,0):
			# We are waiting for a response and will only accept idempotent methods
			return False
		return True
	
	def Continue(self,request):
		"""Called when a request receives 100-Continue or other informational
		response, if we are holding this request's body while waiting for
		a response from the server then this is our signal to stop waiting and
		get on with it."""
		self.manager.Log(HTTP_LOG_INFO,"100 Continue received... ready to send request")
		if request is self.request and self.requestMode==self.REQ_BODY_WAITING:
			self.requestMode=self.REQ_BODY_SENDING
			
	def ConnectionTask(self):
		"""Processes the connection, sending requests and receiving responses.  It
		returns a r,w pair of file numbers suitable for passing to select indicating
		whether the connection is waiting to read and/or write.  It will return
		None,None if the connection is currently idle."""
		rBusy=None;wBusy=None
		if self.request or self.response:
			if self.socket is None:
				self.NewSocket()
			while 1:
				rBusy=None;wBusy=None
				self.manager.Log(HTTP_LOG_DEBUG,"%s: request mode=%i, sendBuffer=%s"%(self.host,self.requestMode,repr(self.sendBuffer)))
				if self.response:
					if self.recvBufferSize<4096:
						self.manager.Log(HTTP_LOG_DEBUG,"%s: response mode=%i, recvBuffer=%s"%(self.host,self.response.mode,repr(self.recvBuffer)))
					else:
						self.manager.Log(HTTP_LOG_DEBUG,"%s: response mode=%i, recvBufferSize=%i"%(self.host,self.response.mode,self.recvBufferSize))						
				else:
					self.manager.Log(HTTP_LOG_DEBUG,"%s: no response waiting"%self.host)
				# The section deals with the sending cycle, we pass on to the
				# response section only if we are in a waiting mode or we are
				# waiting for the socket to be ready before we can write data
				if self.sendBuffer:
					try:
						r,w,e=self.socketSelect([],[self.socketFile],[],0.0)
					except select.error,err:
						self.Close(err)
						w=[]
					if w:
						# We can write
						self.SendRequestData()
					if self.sendBuffer:
						# We are waiting to write, move on to the response section!
						wBusy=self.socketFile
					else:
						continue
				elif self.requestMode==self.REQ_BODY_WAITING:
					# empty buffer and we're waiting for a 100-continue (that may never come)
					if self.continueWaitStart:
						if time.time()-self.continueWaitStart>self.continueWaitMax:
							self.requestMode=self.REQ_BODY_SENDING
					else:
						self.continueWaitStart=time.time()
				elif self.requestMode==self.REQ_BODY_SENDING:
					# Buffer is empty, refill it from the request
					data=self.request.ReadRequestBody()
					if data:
						self.sendBuffer.append(data)
						# Go around again to send the buffer
						continue
					else:
						# Buffer is empty, request is exhausted, we're done with it!
						# we might want to tell the associated respone that it is
						# now waiting, but matching is hard when pipelining!
						# self.response.StartWaiting()
						self.request.Disconnect()
						self.request=None
						self.requestMode=self.REQ_READY
				# This section deals with the response cycle, we only get here if the
				# buffer is empty and we don't have any more data to send (or we are
				# waiting for a response before sending it).
				if self.response:
					try:
						r,w,e=self.socketSelect([self.socketFile],[],[self.socketFile],0)
					except select.error, err:
						r=[]
						self.Close(err)
					if e:
						# there is an error on our socket...
						self.Close("socket error indicated by select")
					elif r:
						if self.RecvResponseData():
							# The response is done
							if self.responseQueue:
								self.response=self.responseQueue[0]
								self.responseQueue=self.responseQueue[1:]
							elif self.response:
								self.response=None
								if self.requestMode==self.CLOSE_WAIT:
									# no response and waiting to close the connection
									self.Close()
						# Any data received on the connection could change the request
						# state, so we loop round again
						continue
					else:
						rBusy=self.socketFile
				break
		return rBusy,wBusy

	def SendRequestData(self):
		"""Sends the next chunk of data in the buffer"""
		if not self.sendBuffer:
			return
		data=self.sendBuffer[0]
		if data:
			try:
				nBytes=self.socket.send(data)
			except socket.error, err:
				# stop everything
				self.Close(err)
				return
			if nBytes==0:
				# We can't send any more data to the socket
				# The other side has closed the connection
				# Strangely, there is nothing much to do here,
				# if the server fails to send a response that
				# will be handled more seriously.  However,
				# we do change to a mode that prevents future
				# requests!
				self.request.Disconnect()
				self.request=None
				self.requestMode==self.CLOSE_WAIT
				self.sendBuffer=[]
			elif nBytes<len(data):
				# Some of the data went:
				self.sendBuffer[0]=data[nBytes:]
			else:
				del self.sendBuffer[0]
		else:
			# shouldn't get empty strings in the buffer but if we do, delete them
			del self.sendBuffer[0]
		
	def RecvResponseData(self):
		"""We ask the response what it is expecting and try and satisfy that, we return True
		when the response has been received completely, False otherwise"""
		err=None
		try:
			data=self.socket.recv(SOCKET_CHUNK)
		except socket.error, e:
			# We can't truly tell if the server hung-up except by getting an error
			# here so this error could be fairly benign.
			err=e
			data=None
		self.manager.Log(HTTP_LOG_DEBUG,"%s: reading %s"%(self.host,repr(data)))
		if data:
			nBytes=len(data)
			self.recvBuffer.append(data)
			self.recvBufferSize+=nBytes
		else:
			self.manager.Log(HTTP_LOG_DEBUG,"%s: closing connection after recv returned no data on ready to read socket"%self.host)
			self.Close()
			return True
		# Now loop until we can't satisfy the response anymore (or the response is done)
		while self.response is not None:
			recvNeeds=self.response.RecvNeeds()
			if recvNeeds==CRLF:
				# scan for CRLF, consolidate first
				data=string.join(self.recvBuffer,'')
				pos=data.find(CRLF)
				if pos>=0:
					line=data[0:pos+2]
					data=data[pos+2:]
				elif err:
					self.Close(err)
					return True
				else:
					# We didn't find the data we wanted this time
					break
				if data:
					self.recvBuffer=[data]
					self.recvBufferSize=len(data)
				else:
					self.recvBuffer=[]
					self.recvBufferSize=0
				if line:
					self.manager.Log(HTTP_LOG_DETAIL,"Response Header: %s"%repr(line))
					self.response.RecvLine(line)
			elif type(recvNeeds) is types.IntType:
				nBytes=int(recvNeeds)
				if nBytes is 0:
					# As many as possible please
					self.manager.Log(HTTP_LOG_DEBUG,"Response reading until connection closes")
					if self.recvBufferSize>0:
						bytes=string.join(self.recvBuffer,'')
						self.recvBuffer=[]
						self.recvBufferSize=0
					else:
						# recvBuffer is empty but we still want more
						break
				elif self.recvBufferSize<nBytes:
					self.manager.Log(HTTP_LOG_DEBUG,"Response waiting for %s bytes"%str(nBytes-self.recvBufferSize))
					# We can't satisfy the response
					break
				else:
					gotBytes=0
					buffPos=0
					while gotBytes<nBytes:
						data=self.recvBuffer[buffPos]
						if gotBytes+len(data)<nBytes:
							buffPos+=1
							gotBytes+=len(data)
							continue
						elif gotBytes+len(data)==nBytes:
							bytes=string.join(self.recvBuffer[0:buffPos+1],'')
							self.recvBuffer=self.recvBuffer[buffPos+1:]
							break
						else:
							# Tricky case, only some of this string is needed
							bytes=string.join(self.recvBuffer[0:buffPos]+[data[0:nBytes-gotBytes]],'')
							self.recvBuffer=[data[nBytes-gotBytes:]]+self.recvBuffer[buffPos+1:]
							break
					self.recvBufferSize=self.recvBufferSize-len(bytes)
				self.manager.Log(HTTP_LOG_DETAIL,"Response Data: %s"%repr(bytes))
				self.response.RecvBytes(bytes)
			elif recvNeeds is None:
				# We don't need any bytes at all, the response is done
				return True
			else:
				raise HTTPException("Unexpected RecvNeeds response: %s"%repr(recvNeeds))
		return False
		
	def NewSocket(self):
		self.socket=None
		self.socketFile=None
		self.socketSelect=select.select
		try:
			for target in self.manager.DNSLookup(self.host,self.port):
				family, socktype, protocol, canonname, address = target
				try:
					self.socket=socket.socket(family, socktype, protocol)
					self.socket.connect(address)
				except socket.error, msg:
					if self.socket:
						self.socket.close()
						self.socket=None
					continue
				break
		except socket.gaierror,e:
			self.socket=None
			raise HTTPException("failed to connect to %s (%s)"%(self.host,e[1]))
		if not self.socket:
			raise HTTPException("failed to connect to %s"%self.host)
		else:
			self.socketFile=self.socket.fileno()
	
	def Close(self,err=None):
		if err:
			self.manager.Log(HTTP_LOG_ERROR,"%s: closing connection after error %s"%(self.host,str(err)))
		else:
			self.manager.Log(HTTP_LOG_DEBUG,"%s: closing connection"%self.host)
		if self.request:
			self.request.Disconnect()
			self.request=None
			self.requestMode=self.CLOSE_WAIT
		while self.response:
			# If we get Closed while waiting for a response then we tell
			# the response about the error before hanging up
			self.response.ServerDisconnect(err)
			if self.responseQueue:
				self.response=self.responseQueue[0]
				self.responseQueue=self.responseQueue[1:]
			else:
				self.response=None
		if self.socket:
			try:
				self.socket.shutdown(socket.SHUT_RDWR)
			except socket.error, msg:
				# ignore errors, most likely the server has stopped listening
				pass
			try:
				self.socket.close()
			except socket.error, msg:
				pass
			self.socket=None
		self.sendBuffer=[]
		self.recvBuffer=[]
		self.recvBufferSize=0
		self.requestMode=self.REQ_READY


class HTTPSConnection(HTTPConnection):

	def NewSocket(self):
		HTTPConnection.NewSocket(self)
		try:
			self.socketSSL=socket.ssl(self.socket)
			self.socketTransport=self.socket
			self.socket=self
		except socket.error,err:
			raise HTTPException("failed to build secure connection to %s"%self.host)

	def send(self,data):
		# Prob need to think about SSL errors here
		return self.socketSSL.write(data)
	
	def recv(self,maxBytes):
		# Prob need to think about SSL errors here
		return self.socketSSL.read(maxBytes)

	def shutdown(self,mode):
		# end of SSL connection
		self.socket=self.socketTransport
		self.socketTransport=None
		self.socketSSL=None
		# pass on to the original socket
		self.socket.shutdown(mode)
	
	def close(self):
		# end of SSL connection
		self.socket=self.socketTransport
		self.socketTransport=None
		self.socketSSL=None
		# pass on to the original socket
		self.socket.close()

			
class HTTPMessage:

	def Reset(self,resetHeaders=False):
		if resetHeaders:
			self.headers={}
		# Transfer fields are set by CalculateTransferLength
		self.transferChunked=False
		self.transferLength=None
		self.transferPos=0
		self.transferDone=False
		
	def GetHeaderList(self):
		hList=self.headers.keys()
		hList.sort()
		return hList
	
	def GetHeader(self,fieldName):
		return self.headers.get(fieldName.lower(),[None,None])[1]

	def SetHeader(self,fieldName,fieldValue,appendMode=False):
		fieldNameKey=fieldName.lower()
		if fieldValue is None:
			if fieldNameKey in self.headers:
				del self.headers[fieldNameKey]
		else:
			if fieldNameKey in self.headers and appendMode:
				fieldValue=self.headers[fieldNameKey][1]+", "+fieldValue
			self.headers[fieldNameKey]=[fieldName,fieldValue]

	def GetAcceptEncoding(self):
		fieldValue=self.GetHeader("Accept-Encoding")
		if fieldValue is not None:
			rqTokens=[]
			for item in SplitItems(SplitWords(fieldValue)):
				rqToken=HTTPRelativeQualityToken()
				ParseRelativeQualityToken(item,rqToken)
				rqTokens.append(rqToken)
			return rqTokens
		else:
			return None
			
	def SetAcceptEncoding(self,rqTokens=[HTTPRelativeQualityToken("identity")]):
		if rqTokens is None:
			self.SetHeader("Accept-Encoding",None)
		else:
			self.SetHeader("Accept-Encoding",string.join(map(str,rqTokens),', '))

	def GetContentLength(self):
		fieldValue=self.GetHeader("Content-Length")
		if fieldValue is not None:
			return int(fieldValue.strip())
		else:
			return None

	def SetContentLength(self,length):
		if length is None:
			self.SetHeader("Content-Length",None)
		else:
			self.SetHeader("Content-Length",str(length))

	def GetContentType(self):
		fieldValue=self.GetHeader("Content-Type")
		if fieldValue is not None:
			mtype=MediaType(fieldValue)
			return mtype
		else:
			return None
	
	def SetContentType(self,mtype=None):
		if mtype is None:
			self.SetHeader('Content-Type',None)
		else:
			self.SetHeader('Content-Type',str(mtype))
		
	def GetContentMD5(self):
		fieldValue=self.GetHeader("Content-MD5")
		if fieldValue is not None:
			return base64.decodestring(fieldValue.strip())
		else:
			return None
	
	def SetContentMD5(self,hash):
		if hash is None:
			self.SetHeader("Content-MD5",None)
		else:
			self.SetHeader("Content-MD5",base64.encodestring(hash).strip())
			
	def GetDate(self):
		fieldValue=self.GetHeader("Date")
		if fieldValue is not None:
			return ParseDate(fieldValue)
		else:
			return None

	def SetDate(self,date='now'):
		if date=='now':
			date=datetime.datetime.utcnow()
		if date is None:
			self.SetHeader("Date",None)
		else:
			self.SetHeader("Date",FormatDate(date))
			
	
	def GetExpectContinue(self):
		fieldValue=self.GetHeader("Expect")
		if fieldValue is not None:
			return fieldValue.strip().lower()=="100-continue"
		else:
			return False
	
	def SetExpectContinue(self,flag=True):
		if flag:
			self.SetHeader("Expect","100-continue")
		else:
			self.SetHeader("Expect",None)
			
	def GetTransferEncoding(self):
		return self.GetHeader("Transfer-Encoding")
		
	def SetTransferEncoding(self,fieldValue):
		self.SetHeader("Transfer-Encoding",fieldValue)

	def GetHost(self):
		return self.GetHeader("Host")
		
	def SetHost(self,server):
		self.SetHeader("Host",server)
	
	def GetWWWAuthenticateChallenges(self):
		fieldValue=self.GetHeader("WWW-Authenticate")
		if fieldValue is not None:
			items=SplitItems(SplitWords(fieldValue))
			challenges=[]
			for item in items:
				if item[0].lower()=='basic':
					c=BasicChallenge()
					ParseAuthParams(item,c,1)
					challenges.append(c)
			return challenges
		else:
			return None
		
		
	def CalculateTransferLength(self,body=None):
		"""See section 4.4 of RFC2616.
		The transfer-length of a message is the length of the message-body as
		it appears in the message; that is, after any transfer-codings have
		been applied. When a message-body is included with a message, the
		transfer-length of that body is determined by one of the following
		(in order of precedence)....
		
		Note that the body may be a string or None and is compared
		with or used to set the headers appropriately.  Use None if you
		don't know the size of the body or you have already set the
		Content-Length."""
		self.transferChunked=False
		if isinstance(self,HTTPResponse) and (self.status//100==1 or
			self.status==204 or self.status==304 or self.request.method=='HEAD'):
			self.transferLength=0
			return
		# If there is an encoding other than 'identity' then we're using chunked
		encoding=self.GetTransferEncoding()
		if encoding is not None and encoding!="identity":
			self.transferChunked=True
			self.transferLength=None
			# overrides any Content-Length setting
			return
		# If there is a Content-Length header
		contentLength=self.GetContentLength()
		if contentLength is not None:
			self.transferLength=contentLength
			if body is not None:
				# If we know the body then raise errors if these don't match our calculation
				if len(body)<self.transferLength:
					raise HTTPException("Too little data in message body")
				elif len(body)>self.transferLength:
					raise HTTPException("Too much data in message body")
			return
		# We don't yet support multipart/byteranges....so skip this
		if isinstance(self,HTTPRequest):
			if body is None:
				# We don't know the body size, so force chunked
				self.SetTransferEncoding("chunked")
				self.transferChunked=True
				return			
			elif body or not (self.method.upper() in ("GET","HEAD","DELETE")):
				# We have a non empty body but there are no headers set, add in the Content-Length
				self.SetContentLength(len(body))
				self.transferLength=len(body)
				return
			else:
				# If it is GET, HEAD or DELETE request with an empty body we don't set headers or send an entity!
				return
		else:
			# If it is a response with an unknown transfer length: we'll read forever!
			return
	
	
class HTTPRequest(HTTPMessage):
	def __init__(self,uri,method="GET",reqBody='',resBody=None,protocolVersion=HTTP_VERSION):
		HTTPMessage.Reset(self,True)
		self.manager=None
		self.connection=None
		self.response=None
		self.status=0
		self.SetRequestURI(uri)
		self.method=method
		self.protocolVersion=HTTPVersion(protocolVersion)
		if type(reqBody) is types.StringType:
			self.reqBody=reqBody
			self.reqBodyStream=None
		else:
			# assume that the reqBody is a stream like object,
			# record the current position to support Resend
			self.reqBodyStream=reqBody
			self.reqBodyStart=reqBody.tell()
			self.reqBody=None
		self.resBody=''
		self.resBuffer=[]
		if resBody is not None:
			# assume that the resBody is a stream like object
			self.resBodyStream=resBody
			self.resBodyStart=resBody.tell()
		else:
			self.resBodyStream=None
		self.autoRedirect=True
		self.done=False
		
	def Resend(self,uri=None):
		self.done=False
		self.manager.Log(HTTP_LOG_INFO,"Resending request to: %s"%str(uri))
		self.Reset()
		self.status=0
		if uri is not None:
			self.SetRequestURI(uri)
		if self.reqBodyStream:
			self.reqBodyStream.seek(self.reqBodyStart)
		if self.resBodyStream:
			self.resBodyStream.seek(self.resBodyStart)
			self.resBodyStream.truncate()
		else:
			self.resBuffer=[]
		self.manager.QueueRequest(self)

	def SetRequestURI(self,uri):
		# From the uri, we'll set the following:
		#  The Host: header
		#  scheme
		#  port
		#  uri (for request line)
		self.requestURI=uri
		url=urlparse.urlsplit(uri)
		if url.username:
			raise HTTPException("Auth not yet supported")
		if url.path:
			self.uri=url.path
		else:
			self.uri='/'
		if url.query:
			self.uri=self.uri+'?'+url.query
		self.scheme=url.scheme.lower()
		self.hostname=url.hostname
		if self.scheme=='http':
			self.port=HTTP_PORT
		elif self.scheme=='https':
			self.port=HTTPS_PORT
		else:
			raise HTTPException("Scheme not supported: %s"%self.scheme)
		if url.port:
			# Custom port in the URL
			self.port=url.port
			customPort=self.port
		else:
			customPort=None
		# The Host request-header field (section 14.23) MUST accompany all
		# HTTP/1.1 requests.
		if url.hostname:
			if customPort is None:
				self.SetHost(url.hostname)
			else:
				self.SetHost("%s:%i"%(url.hostname,customPort))				
		else:
			raise HTTPException("No host in request URL")

	def SetManager(self,manager):
		"""Called when we are queued in an HTTPRequestManager"""
		self.manager=manager
	
	def SetConnection(self,connection):
		"""Called when we are assigned to an HTTPConnection"""
		self.connection=connection
		
	def SetResponse(self,response):
		"""Called when a response has been created"""
		self.response=response

	def Disconnect(self):
		"""Called when the connection has finished sending the
		request, may be before or after the response is received
		and handled!"""
		self.connection=None
		if self.status>0:
			# The response has finished
			self.Finished()
		
	def ReadRequestHeader(self):
		"""Returns a data string ready to send to the server"""
		buffer=[]
		self.manager.Log(HTTP_LOG_INFO,"Sending request to %s"%self.GetHost())
		self.manager.Log(HTTP_LOG_INFO,"%s %s %s"%(self.method,self.uri,str(self.protocolVersion)))
		# Calculate the length of the message body for transfer
		self.CalculateTransferLength(self.reqBody)
		buffer.append("%s %s %s\r\n"%(self.method,self.uri,str(self.protocolVersion)))
		hList=self.GetHeaderList()
		for hKey in hList:
			hName,hValue=self.headers[hKey]
			buffer.append("%s: %s\r\n"%(hName,hValue))
		buffer.append("\r\n")
		return string.join(buffer,'')
	
	def ReadRequestBody(self):
		if self.transferDone:
			return ''
		if self.reqBodyStream:
			# We're reading from a stream
			if self.transferChunked:
				data=self.reqBodyStream.read(SOCKET_CHUNK)
				self.transferPos+=len(data)
				buffer=[]
				if data:
					buffer.append("%x\r\n"%len(data))
					buffer.append(data)
					buffer.append(CRLF)
					data=string.join(buffer,'')
				else:
					data="0\r\n\r\n"
					self.transferDone=True
				return data
			else:
				chunkLen=self.transferLength-self.transferPos
				if chunkLen:
					if chunkLen>SOCKET_CHUNK:
						chunkLen=SOCKET_CHUNK
					data=self.reqBodyStream.read(chunkLen)
					if data:
						self.transferPos+=len(data)
						return data
					else:
						raise HTTPException('EOF in request stream') 
				else:
					self.transferDone=True
					return ''
		else:
			# We're just sending the body string
			if self.transferChunked:
				buffer=[]
				# Send the first chunk size
				buffer.append("%x\r\n"%len(self.reqBody))
				buffer.append(self.reqBody)
				buffer.append(CRLF)
				buffer.append("0\r\n\r\n")
				self.transferPos=len(self.reqBody)
				self.transferDone=True
				return string.join(buffer,'')
			else:
				# This else handles an empty body too, not chunked and no transferLength 
				self.transferPos=len(self.reqBody)
				self.transferDone=True
				return self.reqBody
	
	def HandleResponseHeader(self):
		"""This method is called when a set of response headers has been received from
		the server, before the associated data is received!  After this call,
		WriteResponse will be called zero or more times until ResponseFinished is
		called indicating the end of the response.
		
		If you need to handle the response in a special way, such as writing the
		response data to a stream, then you can override this method to signal
		the start of the response.  Override the Finished method to clean up
		and process the data."""
		self.manager.Log(HTTP_LOG_DEBUG,"Request: %s %s %s"%(self.method,self.uri,str(self.protocolVersion)))
		self.manager.Log(HTTP_LOG_DEBUG,"Got Response: %i %s"%(self.response.status,self.response.reason))
		self.manager.Log(HTTP_LOG_DEBUG,"Response headers: %s"%repr(self.response.headers))
		pass
		
	def WriteResponse(self,data):
		if data:
			if self.resBodyStream:
				self.resBodyStream.write(data)
			else:
				self.resBuffer.append(data)
		
	def ResponseFinished(self):
		self.status=self.response.status
		if self.status is None:
			self.manager.Log(HTTP_LOG_ERROR,"Error receiving response, %s"%str(self.response.connectionError))
			self.status=0
			self.Finished()
		else:
			self.manager.Log(HTTP_LOG_INFO,"Finished Response, status %i"%self.status)
			if self.resBodyStream:
				self.resBodyStream.flush()
			else:
				self.resBody=string.join(self.resBuffer,'')
				self.resBuffer=[]
			if self.response.status>=100 and self.response.status<=199:
				"""Received after a 100 continue or other 1xx status response, we may be waiting
				for the connection to call our ReadRequestBody method.  We need to tell it not
				to wait any more!"""
				if self.connection:
					self.connection.Continue(self)
				# We're not finished though, wait for the final response to be sent.
				# No need to reset as the 100 response should not have a body
			elif self.connection:
				# The response was received before the connection finished with us
				if self.status>=300:
					# Some type of error condition....
					if self.ReadRequestBody():
						# There was more data to send in the request but we
						# don't plan to send it so we have to hang up!
						self.connection.RequestDisconnect()
					# else, we were finished anyway... the connection will discover this itself
				elif self.response>=200:
					# For 2xx result codes we let the connection finish spooling
					# and disconnect from us when it is done
					pass
				else:
					# A bad information response (with body) or a bad status code
					self.connection.RequestDisconnect()
			else:
				# The request is already disconnected, we're done
				self.Finished()

	def Finished(self):
		"""Called when we have a final response *and* have disconnected from the connection
		There is no guarantee that the server got all of our data, it might even have
		have returned a 2xx series code and then hung up before reading the data, maybe
		it already had what it needed, maybe it thinks a 2xx response is more likely to make
		us go away.  Whatever.  The point is that you can't be sure that all the data
		was transmitted just because you got here and the server says everything is OK"""
		self.done=True
		if self.autoRedirect and self.status>=300 and self.status<=399 and (self.status!=302 or self.method.upper() in ("GET","HEAD")):
			# If the 302 status code is received in response to a request other
			# than GET or HEAD, the user agent MUST NOT automatically redirect the
			# request unless it can be confirmed by the user
			location=self.response.GetHeader("Location").strip()
			if location:
				url=urlparse.urlsplit(location)
				if not url.hostname:
					# This is an error but a common one (thanks IIS!)
					location=urlparse.urljoin(self.requestURI,location)
				self.Resend(location)
		elif self.status==401:
			challenges=self.response.GetWWWAuthenticateChallenges()
			for c in challenges:
				c.protectionSpace=uri.URIFactory.URI(self.requestURI).GetCanonicalRoot()
				credentials=self.manager.FindCredentials(c)
				if credentials:
					oldValue=self.GetHeader('Authorization')
					if oldValue!=str(credentials):
						# need to avoid uselessly sending the same credentials
						self.SetHeader('Authorization',str(credentials))
						self.Resend()
	

class HTTPResponse(HTTPMessage):
	
	RESP_LINE_MODES=100
	RESP_STATUS=101
	RESP_HEADER=102
	RESP_CHUNK_SIZE=103
	RESP_CHUNK_DATA=4
	RESP_CHUNK_TRAILER=105
	RESP_DATA=7
	RESP_DONE=-1
	
	def __init__(self,request):
		self.Reset()
		self.request=request
		self.request.SetResponse(self)

	def Reset(self):
		HTTPMessage.Reset(self,True)
		self.connectionError=None
		self.protocolVersion=None
		self.status=None
		self.reason=None
		self.mode=self.RESP_STATUS
		self.currHeader=None
		self.waitStart=None
		
	def StartWaiting(self):
		# called after the send buffer for our request is cleared
		# indicating that we are now just waiting for a response from
		# the server....
		self.waitStart=time.time()
	
	def RecvNeeds(self):
		if self.NeedLine():
			return CRLF
		else:
			return self.NeedBytes()
			
	def NeedLine(self):
		return self.mode>self.RESP_LINE_MODES

	def NeedBytes(self):
		"""Returns the number of bytes we are waiting for from the server or None
		if we are done, 0 if we we want to read forever, otherwise the minimum
		number of bytes we expect (we may ask for more later)."""
		if self.mode==self.RESP_DONE:
			return None
		elif self.mode<self.RESP_LINE_MODES:
			# How much data do we need?
			if self.transferLength:
				return self.transferLength-self.transferPos
			else:
				# reading forever always returns 0 bytes
				return 0
		else:
			return None
	
	def RecvLine(self,line):
		if self.mode==self.RESP_STATUS:
			# Read the status line
			statusLine=WordParser(line[:-2],ignoreSpace=False)
			self.protocolVersion=HTTPVersion()
			self.protocolVersion.ParseWords(statusLine)
			statusLine.ParseSP()
			if statusLine.IsInteger():
				self.status=statusLine.ParseInteger()
			else:
				self.status=0
			statusLine.ParseSP()
			self.reason=statusLine.ParseRemainder()
			self.mode=self.RESP_HEADER
		elif self.mode==self.RESP_HEADER:
			self.ReadHeader(line)
			if line==CRLF:
				self.CalculateTransferLength()
				if self.transferChunked:
					self.mode=self.RESP_CHUNK_SIZE
				elif self.transferLength is None:
					# We're going to read forever
					self.transferLength=self.transferPos=0
					self.mode=self.RESP_DATA
				elif self.transferLength:
					self.transferPos=0
					self.mode=self.RESP_DATA
				else:
					self.transferLength=self.transferPos=0
					self.mode=self.RESP_DONE
				self.request.HandleResponseHeader()
		elif self.mode==self.RESP_CHUNK_SIZE:
			# Read the chunk size
			chunkLine=SplitWords(line[:-2])[0]
			self.transferLength=int(chunkLine,16)
			self.transferPos=0
			if self.transferLength==0:
				# We've read the last chunk, parse through any headers
				self.mode=self.RESP_CHUNK_TRAILER
			else:
				self.transferLength+=2  # allow for trailing CRLF
				self.transferPos=0
				self.mode=self.RESP_CHUNK_DATA
		elif self.mode==self.RESP_CHUNK_DATA:
			# should not get here!
			raise HTTPException("RecvLine while reading chunk")
		elif self.mode==self.RESP_CHUNK_TRAILER:
			self.ReadHeader(line)
			if line==CRLF:
				self.mode=self.RESP_DONE
		elif self.mode==self.RESP_DATA:
			raise HTTPException("RecvLine while reading data")
		else:
			raise HTTPException("RecvLine when in unknown mode: %i"%self.mode)
		if self.mode==self.RESP_DONE:
			self.Finished()
	
	def ReadHeader(self,h):
		if h==CRLF:
			if self.currHeader:
				# strip off the trailing CRLF
				self.SetHeader(self.currHeader[0],self.currHeader[1][:-2],True)
				self.currHeader=None
			return False
		else:
			spLen=ParseLWS(h)
			if spLen and self.currHeader:
				# a continuation line
				self.currHeader[1]=self.currHeader[1]+h
			else:
				if self.currHeader:
					self.SetHeader(self.currHeader[0],self.currHeader[1][:-2],True)
				ch=h.split(':',1)
				if len(ch)==2:
					self.currHeader=ch
				else:
					# badly formed header line
					raise HTTP2616ProtocolError("Badly formed header line: %s"%h)
			return True

	def RecvBytes(self,data):
		if self.mode==self.RESP_CHUNK_DATA:
			self.transferPos+=len(data)
			extra=self.transferPos-(self.transferLength-2)
			if extra>0:
				self.request.WriteResponse(data[:-extra])
			else:
				self.request.WriteResponse(data)
			if self.transferPos>=self.transferLength:
				# We've read all the data for this chunk, read the next one
				self.mode=self.RESP_CHUNK_SIZE
		elif self.mode==self.RESP_DATA:
			self.transferPos+=len(data)
			if self.transferLength:
				if self.transferPos>self.transferLength:
					extra=self.transferPos-self.transferLength
					self.request.WriteResponse(data[:extra])
				else:
					self.request.WriteResponse(data)
				if self.transferPos>=self.transferLength:
					self.mode=self.RESP_DONE
			else:
				# keep reading until connection closed
				self.request.WriteResponse(data)
		if self.mode==self.RESP_DONE:
			self.Finished()
			
	def Finished(self):
		self.request.ResponseFinished()
		if self.status>=100 and self.status<=199:
			# Re-read this response, we're not done!
			self.Reset()
	
	def ServerDisconnect(self,err):
		"""Called when the server disconnects before we've completed reading the
		response.  We pass this information on to the request.  Note that if we
		are reading forever 'err' may or may not be set when the server finally
		hangs up and stops sending."""
		self.connectionError=err
		self.request.ResponseFinished()
	