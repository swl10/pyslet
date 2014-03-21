#! /usr/bin/env python

HTTP_PORT=80
HTTPS_PORT=443
HTTP_VERSION="HTTP/1.1"

SOCKET_TIMEOUT=120
SOCKET_CHUNK=8192

import logging
import string
import time
import datetime
import socket
import select
import types
import base64
import threading
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
class ConnectionClosed(HTTPException): pass

class ConnectionPool(object):
	"""Represents a pool of connections to a specific HTTP endpoint."""
	def __init__(self,scheme,hostname,port,manager,maxConnections=3):
		self.manager=manager
		self.scheme=scheme.lower()
		self.hostname=hostname.lower()
		self.port=port
		self.maxConnections=maxConnections
		self.cActivePool={}			#: dictionary keyed on thread id
		self.cIdlePool=[]			#: a list of idle connections

	def Key(self):
		return (self.scheme,self.hostname,self.port)
	
	def QueueRequest(self,request,timeout=None):
		"""Queues a request, waiting for a connection if necessary.
		
		This method is only called by the request manager and only when
		the managerLock is in force."""
		threadId=threading.current_thread().ident
		now=start=time.time()
		while True:
			if threadId in self.cActivePool:
				# great, add this request to the queue on that connection
				connection=self.cActivePool[threadId]
				break
			elif self.cIdlePool:
				# grab this connection and assign to our thread
				connection=self.cIdlePool.pop()
				self.cActivePool[threadId]=connection
				self.manager.ActivateConnection(connection)
				break
			elif len(self.cActivePool)+len(self.cIdlePool)<self.maxConnections:
				# expand the pool
				connection=self.manager.NewConnection(self,timeout)
				self.cActivePool[threadId]=connection
				self.manager.ActivateConnection(connection)
				break
			else:
				# we have to wait for a connection to become available
				now=time.time()
				if timeout is not None and now>start+timeout:
					logging.warn("Thread[%i] timed out waiting for an HTTP connection",threadId)
					raise RequestManagerBusy
				logging.debug("Thread[%i] forced to wait for an HTTP connection",threadId)
				self.manager.Wait(timeout)
				#	self.manager.managerLock.wait(timeout)
				logging.debug("Thread[%i] resuming search for an HTTP connection",threadId)
		connection.requestQueue.append(request)
	
	def ConnectionIdle(self,connection):
		"""Called during the connection's
		:py:meth:`Connection.ConnectionTask` method when the connection
		is idle."""
		with self.manager.managerLock:
			if connection.threadId in self.cActivePool:
				if connection.threadId in self.cActivePool:
					del self.cActivePool[connection.threadId]
				self.cIdlePool.append(connection)
				self.manager.ConnectionIdle(connection)
					
	def __hash__(self):
		return hash(self.Key())
	
	def __cmp__(self,other):
		if not isinstance(other,ConnectionPool):
			raise TypeError
		result=cmp(self.hostname,other.hostname)
		if not result:
			result=cmp(self.scheme,other.scheme)
		if not result:
			result=cmp(self.port,other.port)
		return result
	
		
class Connection(object):
	"""Represents an HTTP connection.  Used internally by the request manager
	to manage connections to HTTP servers."""

	REQ_READY=0			#:	ready to start a request
	REQ_BODY_WAITING=1	#:	waiting to send the request body
	REQ_BODY_SENDING=2	#:	sending the request body
	CLOSE_WAIT=3		#:	waiting to disconnect
	
	MODE_STRINGS={0:"Ready",1:"Waiting",2:"Sending",3:"Closing"}
	
	IDEMPOTENT={"GET":1,"HEAD":1,"PUT":1,"DELETE":1,"OPTIONS":1,"TRACE":1,"CONNECT":0,"POST":0}
	
	def __init__(self,pool):
		self.pool=pool						#: the ConnectionPool that contains this connection
		self.manager=self.pool.manager		#: the RequestManager that contains the pool
		self.id=self.manager.NextId()		#: the id of this connection object
		self.threadId=None					#: the thread we're currently bound to
		self.lastActive=0					#: time at which this connection was last active
		self.requestQueue=[]				#: the queue of requests we are processing
		scheme,self.host,self.port=pool.Key()
		self.request=None
		self.requestMode=self.REQ_READY
		self.continueWaitMax=60.0			# If we don't get a continue in 1 minute, send the data anyway
		self.continueWaitStart=0
		self.response=None
		self.responseQueue=[]
		# Low-level socket members
		self.socket=None
		self.socketFile=None
		self.sendBuffer=[]
		self.recvBuffer=[]
		self.recvBufferSize=0

	def __hash__(self):
		return self.id
	
	def __cmp__(self,other):
		if not isinstance(other,Connection):
			raise TypeError
		return cmp(self.lastActive,other.lastActive)
		
	def __repr__(self):
		return "Connection(%s,%i)"%(self.host,self.port)
		
	def StartRequest(self,request):
		"""Starts processing the request.  Returns True if the request has
		been accepted for processing, False otherwise."""
		if self.requestMode!=self.REQ_READY:
			return False
		elif self.response and not self.IDEMPOTENT.get(request.method,0):
			# We are waiting for a response and will only accept idempotent methods
			return False
		self.request=request
		self.request.SetHTTPConnection(self)
		headers=self.request.ReadRequestHeader()
		for h in headers.split(CRLF):
			logging.debug("Request header: %s",h)
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
			
	def Continue(self,request):
		"""Called when a request receives 100-Continue or other informational
		response, if we are holding this request's body while waiting for
		a response from the server then this is our signal to stop waiting and
		get on with it."""
		logging.info("100 Continue received... ready to send request")
		if request is self.request and self.requestMode==self.REQ_BODY_WAITING:
			self.requestMode=self.REQ_BODY_SENDING
			
	def ConnectionTask(self):
		"""Processes the connection, sending requests and receiving responses.  It
		returns a r,w pair of file numbers suitable for passing to select indicating
		whether the connection is waiting to read and/or write.  It will return
		None,None if the connection is not blocked on I/O."""
		rBusy=None;wBusy=None
		while True:
			self.lastActive=time.time()
			if self.request is None and self.requestQueue:
				request=self.requestQueue[0]
				if self.StartRequest(request):
					self.requestQueue=self.requestQueue[1:]
			if self.request or self.response:
				if self.socket is None:
					self.NewSocket()
				rBusy=None;wBusy=None
				logging.debug("%s: request mode=%s, sendBuffer=%s",self.host,self.MODE_STRINGS[self.requestMode],repr(self.sendBuffer))
				if self.response:
					if self.recvBufferSize<4096:
						logging.debug("%s: response mode=%s, recvBuffer=%s",self.host,self.MODE_STRINGS[self.requestMode],repr(self.recvBuffer))
					else:
						logging.debug("%s: response mode=%s, recvBufferSize=%i",self.host,self.MODE_STRINGS[self.requestMode],self.recvBufferSize)
				else:
					logging.debug("%s: no response waiting",self.host)
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
						# We are still waiting to write, move on to the response section!
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
							closeConnection=False
							if self.response:
								closeConnection="close" in self.response.GetConnection() or self.response.protocolVersion<HTTP_1_1
							if self.responseQueue:
								self.response=self.responseQueue[0]
								self.responseQueue=self.responseQueue[1:]
							elif self.response:
								self.response=None
								if self.requestMode==self.CLOSE_WAIT:
									# no response and waiting to close the connection
									closeConnection=True
							if closeConnection:
								self.Close()
						# Any data received on the connection could change the request
						# state, so we loop round again
						continue
					else:
						rBusy=self.socketFile
				break
			else:
				# no request or response, we're idle
				if self.requestMode==self.CLOSE_WAIT:
					# clean up if necessary
					self.Close()
				self.pool.ConnectionIdle(self)
				rBusy=None;wBusy=None
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
		logging.debug("%s: reading %s",self.host,repr(data))
		if data:
			nBytes=len(data)
			self.recvBuffer.append(data)
			self.recvBufferSize+=nBytes
		else:
			logging.debug("%s: closing connection after recv returned no data on ready to read socket",self.host)
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
					logging.debug("Response Header: %s",repr(line))
					self.response.RecvLine(line)
			elif type(recvNeeds) is types.IntType:
				nBytes=int(recvNeeds)
				if nBytes is 0:
					# As many as possible please
					logging.debug("Response reading until connection closes")
					if self.recvBufferSize>0:
						bytes=string.join(self.recvBuffer,'')
						self.recvBuffer=[]
						self.recvBufferSize=0
					else:
						# recvBuffer is empty but we still want more
						break
				elif self.recvBufferSize<nBytes:
					logging.debug("Response waiting for %s bytes",str(nBytes-self.recvBufferSize))
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
				logging.debug("Response Data: %s",repr(bytes))
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
			logging.error("%s: closing connection after error %s",self.host,str(err))
		else:
			logging.debug("%s: closing connection",self.host)
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


class SecureConnection(Connection):

	def NewSocket(self):
		super(SecureConnection,self).NewSocket()
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

			
class HTTPRequestManager(object):
	"""An object for managing the sending of HTTP requests and receiving
	of responses.
	
	"""
	ConnectionClass=Connection
	SecureConnectionClass=SecureConnection
	
	def __init__(self,maxPerPool=3,maxConnections=100):
		self.managerLock=threading.Condition()
		self.nextId=1			#: the id of the next connection object we'll create
		self.cPool={}			#: pool of ConnectionPool objects keyed on (scheme,hostname,port)
		self.cTaskList={}		#: a dict of dicts of Connection objects keyed on thread id then connection id
		self.cActiveList={}		#: the pool of active Connection objects keyed on connection id
		self.cIdleList={}		#: the pool of idle Connection objects keyed on connection id
		self.closing=False		#: True if we are closing
		self.maxConnections=maxConnections	#: maximum number of connections to manage
		self.maxPerPool=maxPerPool			#: maximum number of connections per pool (scheme+host+port)
		self.dnsCache={}		#: cached results from socket.getaddrinfo keyed on (hostname,port)
		self.requestQueue=[]
		self.connections={}
		self.nextConnection=None
		self.credentials=[]
		self.socketSelect=select.select
		self.httpUserAgent="pyslet.rfc2616.HTTPRequestManager"
		
	def QueueRequest(self,request,timeout=None):
		"""Instructs the manager to start processing *request*.
		
		request
			A :py:class:`Connection` object.
		
		timeout
			Number of seconds to wait for a free connection before timing
			out.  A timeout raises :py:class:`RequestManagerBusy`
			
		The default implementation adds a User-Agent header from
		:py:attr:`httpUserAgent` if not None.  You can override this method to
		add other headers appropriate for a specific context prior to passing on
		to this call."""
		if self.httpUserAgent:
			request.SetHeader('User-Agent',self.httpUserAgent)
		# assign this request to a connection straight away
		key=(request.scheme,request.hostname,request.port)
		with self.managerLock:
			if self.closing:
				raise ConnectionClosed
			pool=self.cPool.get(key,None)
			if pool is None:
				pool=ConnectionPool(*key,manager=self,maxConnections=self.maxPerPool)
				self.cPool[pool.Key()]=pool
			pool.QueueRequest(request,timeout)
		#	self.requestQueue.append(request)
		request.SetManager(self)

	def NextId(self):
		"""Returns the next connection id"""
		with self.managerLock:
			id=self.nextId
			self.nextId+=1
		return id
		
	def NewConnection(self,pool,timeout=None):
		"""Called by a ConnectionPool when a new connection is required."""
		scheme,host,port=pool.Key()
		threadId=threading.current_thread().ident
		with self.managerLock:
			while True:
				if len(self.cActiveList)+len(self.cIdleList)<self.maxConnections:
					if scheme=='http':
						connection=self.ConnectionClass(pool)
					elif scheme=='https':
						connection=self.SecureConnectionClass(pool)
					else:
						raise NotImplementedError("Unsupported connection scheme: %s"%scheme)
					# add the new connection to the idle list
					self.cIdleList[connection.id]=connection
					return connection
				elif self.cIdleList:
					# get rid of the oldest connection
					cIdle=self.cIdleList.values()
					cIdle.sort()
					connection=cIdle[0]
					del self.cIdleList[connection.id]
					connection.pool.DeleteConnection(connection)
					# next time around the loop we'll create a new one in the correct *pool*
				else:					
					# all connections are active, wait for notification of one becoming idle
					now=time.time()
					if timeout is not None and now>start+timeout:
						logging.warn("Thread[%i] timed out waiting for an HTTP connection",threadId)
						raise RequestManagerBusy
					logging.debug("Thread[%i] forced to wait for an HTTP connection",threadId)
					self.managerLock.wait(timeout)
					logging.debug("Thread[%i] resuming search for an HTTP connection",threadId)

	def Wait(self,timeout=None):
		"""Yields the lock until a notification."""
		self.managerLock.wait(timeout)

	def ActivateConnection(self,connection):
		"""Called when a connection becomes active."""
		threadId=threading.current_thread().ident
		with self.managerLock:
			if connection.id in self.cIdleList:
				del self.cIdleList[connection.id]
			connection.threadId=threadId
			self.cActiveList[connection.id]=connection
			if threadId in self.cTaskList:
				self.cTaskList[threadId][connection.id]=connection
			else:
				self.cTaskList[threadId]={connection.id:connection}

	def ConnectionIdle(self,connection):
		"""Called when a connection becomes idle."""
		threadId=connection.threadId
		with self.managerLock:
			if threadId in self.cTaskList:
				tasks=self.cTaskList[threadId]
				if connection.id in tasks:
					del tasks[connection.id]
			connection.threadId=None
			if connection.id in self.cActiveList:
				del self.cActiveList[connection.id]
			self.cIdleList[connection.id]=connection
		
	def ThreadTask(self,timeout):
		"""Processes all connections bound to the current thread
		blocking for at most timeout (where possible). Returns True if
		at least one connection is active, otherwise returns False."""
		threadId=threading.current_thread().ident
		with self.managerLock:
			connections=self.cTaskList[threadId].values()
		if not connections:
			return False
		readers=[]
		writers=[]
		for c in connections:
			r,w=c.ConnectionTask()
			if r:
				readers.append(r)
			if w:
				writers.append(w)
		if readers or writers:
			try:
				logging.debug("Socket select for: readers=%s, writers=%s, timeout=%i",repr(readers),repr(writers),timeout)
				r,w,e=self.socketSelect(readers,writers,[],timeout)
			except select.error, err:
				logging.error("Socket error from select: %s",str(err)) 
		return True
			
	def AddCredentials(self,credentials):
		"""Adds a :py:class:`pyslet.rfc2617.Credentials` instance to this
		manager.
		
		Credentials are used in response to challenges received in HTTP
		401 responses."""
		with self.managerLock:
			self.credentials.append(credentials)
	
	def DNSLookup(self,host,port):
		"""Given a host name (string) and a port number performs a DNS lookup
		using the native socket.getaddrinfo function.  The resulting value is
		added to an internal dns cache so that subsequent calls for the same
		host name and port do not use the network unnecessarily.
		
		If you want to flush the cache you must do so manually using
		:py:meth:`DNSFlush`."""
		with self.managerLock:
			result=self.dnsCache.get((host,port),None)
		if result is None:
			# do not hold the lock while we do the DNS lookup, this may
			# result in multiple overlapping DNS requests but this is
			# better than a complete block.
			logging.debug("Looking up %s",host)
			result=socket.getaddrinfo(host,port, 0, socket.SOCK_STREAM)
			with self.managerLock:
				# blindly populate the cache
				self.dnsCache[(host,port)]=result
		return result
	
	def DNSFlush(self):
		"""Flushes the DNS cache."""
		with self.managerLock:
			self.dnsCache={}
			
	def FindCredentials(self,challenge):
		"""Searches for credentials that match *challenge*"""
		logging.debug("HTTPRequestManager searching for credentials in %s with challenge %s",challenge.protectionSpace,str(challenge))
		with self.managerLock:
			for c in self.credentials:
				if c.MatchChallenge(challenge):
					return c
	
	def FindCredentialsForURL(self,url):
		"""Searches for credentials that match *url*"""
		with self.managerLock:
			for c in self.credentials:
				if c.MatchURL(url):
					return c
	
	def SetLog(self,level,logStream=None,lineLen=80):
		warnings.warn("HTTPRequestManager.SetLog is deprecated, use logging module instead", DeprecationWarning, stacklevel=2)		
		
	def Log(self,level,logString):
		warnings.warn("HTTPRequestManager.Log is deprecated, use logging module instead", DeprecationWarning, stacklevel=2)		

	def ProcessRequest(self,request,timeout=60):
		"""Process an :py:class:`HTTPRequest` object."""
		self.QueueRequest(request,timeout)
		self.ThreadLoop(timeout)
		
	def ThreadLoop(self,timeout=60,callback=None):
		while True:
			if not self.ThreadTask(timeout):
				break
			if callback is not None:
				callback()
		# self.Close()

# 	def Close(self):
# 		for connection in self.connections.values():
# 			connection.Close()
		
	def ProcessQueue(self):
		pass
# 		with self.managerLock:
# 			for pool in self.cPool.itervalues():
# 				pool.ProcessQueue(self)
# 		while self.requestQueue:
# 			request=self.requestQueue[0]
# 			if self.nextConnection:
# 				if self.nextConnection.StartRequest(request):
# 					self.nextConnection=None
# 					self.requestQueue=self.requestQueue[1:]
# 				else:
# 					# Connection is not ready for us
# 					break
# 			else:
# 				# Find or create a connection for the next request
# 				key=(request.scheme,request.hostname,request.port)
# 				self.nextConnection=self.connections.get(key,None)
# 				if self.nextConnection is None:
# 					self.nextConnection=self.NewConnection(key[0],key[1],key[2])
# 					self.connections[key]=self.nextConnection			
				
		
	def ManagerTask(self):
		"""Designed to allow sub-classing for periodic tasks during idle time such as
		updating status displays"""
		pass
		



class HTTPMessage(object):
	"""An abstract class to represent an HTTP message.
	
	The methods of this class are thread safe, using :py:attr:`lock` to
	protect all access to internal structures."""
	def __init__(self):
		self.lock=threading.RLock()			#: a lock used by :py:class:`HTTPClient`
		self.Reset(True)
		
	def Reset(self,resetHeaders=False):
		"""Resets this messages allowing it to be reused.
		
		*resetHeaders*
			Removes all existing headers."""
		with self.lock:
			if resetHeaders:
				self.headers={}
			# Transfer fields are set by CalculateTransferLength
			self.transferChunked=False
			self.transferLength=None
			self.transferPos=0
			self.transferDone=False
		
	def GetHeaderList(self):
		"""Returns an alphabetically sorted list of lower-cased header names."""
		with self.lock:
			hList=self.headers.keys()
			hList.sort()
			return hList
	
	def HasHeader(self,fieldName):
		"""Return True if this message has a header with *fieldName*, False otherwise"""
		with self.lock:
			return fieldName.lower() in self.headers
		
	def GetHeader(self,fieldName):
		"""Returns the header with *fieldName* as a string.
		
		If there is no header with *fieldName* then None is returned."""
		with self.lock:
			return self.headers.get(fieldName.lower(),[None,None])[1]

	def SetHeader(self,fieldName,fieldValue,appendMode=False):
		"""Sets the header with *fieldName* to the string *fieldValue*.
		
		If *fieldValue* is None then the header is removed (if present).
		
		If a header already exists with *fieldName* then the behaviour is
		determined by *appendMode*:
		
		appendMode==True
			*fieldValue* is joined to the existing value using ", " as
			a separator.
		
		appendMode==False (Default)
			*fieldValue* replaces the existing value."""
		with self.lock:
			fieldNameKey=fieldName.lower()
			if fieldValue is None:
				if fieldNameKey in self.headers:
					del self.headers[fieldNameKey]
			else:
				if fieldNameKey in self.headers and appendMode:
					fieldValue=self.headers[fieldNameKey][1]+", "+fieldValue
				self.headers[fieldNameKey]=[fieldName,fieldValue]

	def GetAllow(self):
		"""Returns an :py:class:`Allow` instance or None if no "Allow"
		header is present."""
		fieldValue=self.GetHeader("Allow")
		if fieldValue is not None:
			return Allow.FromString(fieldValue)
		else:
			return None
			
	def SetAllow(self,allowed):
		"""Sets the "Allow" header, replacing any existing value.
		
		*allowed*
			A :py:class:`Allow` instance or a string that one can be
			parsed from.
		
		If allowed is None any existing Allow header is removed."""
		if allowed is None:
			self.SetHeader("Allow",None)
		else:
			if type(acceptValue) in StringTypes:
				allowed=Allow.FromString(allowed)
			if not isinstance(allowed,Allow):
				raise TypeError
			self.SetHeader("Allow",str(allowed))

	def GetCacheControl(self):
		"""Returns an :py:class:`CacheControl` instance or None if no
		"Cache-Control" header is present."""
		fieldValue=self.GetHeader("Cache-Control")
		if fieldValue is not None:
			return CacheControl.FromString(fieldValue)
		else:
			return None

	def SetCacheControl(self,cc):
		"""Sets the "Cache-Control" header, replacing any existing value.
		
		*cc*
			A :py:class:`CacheControl` instance or a string that one can
			be parsed from.
		
		If *cc* is None any existing Cache-Control header is removed."""
		if cc is None:
			self.SetHeader("Cache-Control",None)
		else:
			if type(cc) in StringTypes:
				cc=CacheControl.FromString(cc)
			if not isinstance(cc,CacheControl):
				raise TypeError
			self.SetHeader("Cache-Control",str(cc))
			
	def GetConnection(self):
		"""Returns a set of connection tokens from the Connection header
		
		If no Connection header was present an empty set is returned."""
		fieldValue=self.GetHeader("Connection")
		if fieldValue:
			hp=HeaderParser(fieldValue)
			return set(map(lambda x:x.lower(),hp.ParseTokenList()))
		else:
			return set()
		
	def SetConnection(self,connectionTokens):
		"""Set the Connection tokens from a an iterable set of *connectionTokens*
		
		If the list is empty any existing header is removed."""
		if connectionTokens:
			self.SetHeader("Connection",string.join(list(connectionTokens),", "))
		else:
			self.SetHeader("Connection",None)
		
	def GetContentEncoding(self):
		"""Returns a *list* of lower-cased content-coding tokens from
		the Content-Encoding header
		
		If no Content-Encoding header was present an empty list is
		returned.
		
		Content-codings are always listed in the order they have been
		applied."""
		fieldValue=self.GetHeader("Content-Encoding")
		if fieldValue:
			hp=HeaderParser(fieldValue)
			return map(lambda x:x.lower(),hp.ParseTokenList())
		else:
			return []
		
	def SetContentEncoding(self,contentCodings):
		"""Sets the Content-Encoding header from a an iterable list of
		*content-coding* tokens.  If the list is empty any existing
		header is removed."""
		if contentCodings:
			self.SetHeader("Content-Encoding",string.join(list(contentCodings),", "))
		else:
			self.SetHeader("Content-Encoding",None)
		
	def GetContentLanguage(self):
		"""Returns a *list* of :py:class:`LanguageTag` instances from
		the Content-Language header
		
		If no Content-Language header was present an empty list is
		returned."""
		fieldValue=self.GetHeader("Content-Language")
		if fieldValue:
			hp=HeaderParser(fieldValue)
			return LanguageTag.ListFromString(fieldValue)
		else:
			return []
		
	def SetContentLanguage(self,langList):
		"""Sets the Content-Language header from a an iterable list of
		:py:class:`LanguageTag` instances."""
		if langList:
			self.SetHeader("Content-Language",string.join(map(str,langList),", "))
		else:
			self.SetHeader("Content-Language",None)
		
	def GetContentLength(self):
		"""Returns the integer size of the entity from the
		Content-Length header
		
		If no Content-Length header was present None is returned."""
		fieldValue=self.GetHeader("Content-Length")
		if fieldValue is not None:
			return int(fieldValue.strip())
		else:
			return None

	def SetContentLength(self,length):
		"""Sets the Content-Length header from an integer or removes it
		if *length* is None."""
		if length is None:
			self.SetHeader("Content-Length",None)
		else:
			self.SetHeader("Content-Length",str(length))

	def GetContentLocation(self):
		"""Returns a :py:class:`pyslet.rfc2396.URI` instance created from
		the Content-Location header.
		
		If no Content-Location header was present None is returned."""
		fieldValue=self.GetHeader("Content-Location")
		if fieldValue is not None:
			return uri.URIFactory.URI(fieldValue.strip())
		else:
			return None
	
	def SetContentLocation(self,location):
		"""Sets the Content-Location header from location, a
		:py:class:`pyslet.rfc2396.URI` instance or removes it if
		*location* is None."""
		if location is None:
			self.SetHeader("Content-Location",None)
		else:
			self.SetHeader("Content-Location",str(location))

	def GetContentMD5(self):
		"""Returns a 16-byte binary string read from the Content-MD5
		header or None if no Content-MD5 header was present.
		
		The result is suitable for comparing directly with the output
		of the Python's MD5 digest method."""
		fieldValue=self.GetHeader("Content-MD5")
		if fieldValue is not None:
			return base64.b64decode(fieldValue.strip())
		else:
			return None
	
	def SetContentMD5(self,digest):
		"""Sets the Content-MD5 header from a 16-byte binary string
		returned by Python's MD5 digest method or similar.  If digest is
		None any existing Content-MD5 header is removed."""
		if digest is None:
			self.SetHeader("Content-MD5",None)
		else:
			self.SetHeader("Content-MD5",base64.b64encode(digest))

	def GetContentRange(self):
		"""Returns a :py:class:`ContentRange` instance parsed from the
		Content-Range header.

		If no Content-Range header was present None is returned."""
		fieldValue=self.GetHeader("Content-Range")
		if fieldValue is not None:
			return ContentRange.FromString(fieldValue)
		else:
			return None
	
	def SetContentRange(self,range):
		"""Sets the Content-Range header from range, a
		:py:class:`ContentRange` instance or removes it if
		*range* is None."""
		if range is None:
			self.SetHeader("Content-Range",None)
		else:
			self.SetHeader("Content-Range",str(range))

	def GetContentType(self):
		"""Returns a :py:class:`MediaType` instance parsed from the
		Content-Type header.

		If no Content-Type header was present None is returned."""
		fieldValue=self.GetHeader("Content-Type")
		if fieldValue is not None:
			mtype=MediaType.FromString(fieldValue)
			return mtype
		else:
			return None
	
	def SetContentType(self,mtype=None):
		"""Sets the Content-Type header from mtype, a
		:py:class:`MediaType` instance, or removes it if
		*mtype* is None."""
		if mtype is None:
			self.SetHeader('Content-Type',None)
		else:
			self.SetHeader('Content-Type',str(mtype))
		
	def GetDate(self):
		"""Returns a :py:class:`FullDate` instance parsed from the
		Date header.

		If no Date header was present None is returned."""
		fieldValue=self.GetHeader("Date")
		if fieldValue is not None:
			return FullDate.FromHTTPString(fieldValue)
		else:
			return None

	def SetDate(self,date=None):
		"""Sets the Date header from *date*, a
		:py:class:`FullDate` instance, or removes it if
		*date* is None.
		
		To set the date header to the current date use::
		
			SetDate(FullDate.FromNowUTC())"""
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
	"""
	"""	
	def __init__(self,url,method="GET",reqBody='',resBody=None,protocolVersion=HTTP_VERSION):
		super(HTTPRequest,self).__init__()
		self.manager=None
		self.connection=None
		self.response=None
		self.status=0
		self.SetRequestURI(url)
		self.method=method
		self.protocolVersion=HTTPVersion.FromString(protocolVersion)
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
		self.tryCredentials=None	#: used to try out credentials in response to a 401
		
	def Resend(self,url=None):
		self.done=False
		logging.info("Resending request to: %s",str(url))
		self.Reset()
		self.status=0
		if url is not None:
			self.SetRequestURI(url)
		if self.reqBodyStream:
			self.reqBodyStream.seek(self.reqBodyStart)
		if self.resBodyStream:
			self.resBodyStream.seek(self.resBodyStart)
			self.resBodyStream.truncate()
		else:
			self.resBuffer=[]
		self.manager.QueueRequest(self)

	def SetRequestURI(self,url):
		# From the url, we'll set the following:
		#  The Host: header
		#  scheme
		#  port
		#  url (for request line)
		if not isinstance(url,uri.URI):
			url=uri.URIFactory.URI(url)
		self.requestURI=url
		if self.requestURI.userinfo:
			raise HTTPException("username(:password) in URL not yet supported")
		if self.requestURI.absPath:
			self.url=self.requestURI.absPath
		else:
			self.url="/"			
		if self.requestURI.query is not None:
			self.url=self.url+'?'+self.requestURI.query
		if not isinstance(self.requestURI,HTTPURL):
			raise HTTPException("Scheme not supported: %s"%self.requestURI.scheme)
		elif isinstance(self.requestURI,HTTPSURL):
			self.scheme='https'
		else:
			self.scheme='http'
		self.hostname=self.requestURI.host
		customPort=False
		if self.requestURI.port:
			# custom port, perhaps
			self.port=int(self.requestURI.port)
			if self.port!=self.requestURI.DEFAULT_PORT:
				customPort=True
		else:
			self.port=self.requestURI.DEFAULT_PORT
		# The Host request-header field (section 14.23) MUST accompany all
		# HTTP/1.1 requests.
		if self.hostname:
			if not customPort:
				self.SetHost(self.hostname)
			else:
				self.SetHost("%s:%i"%(self.hostname,self.port))				
		else:
			raise HTTPException("No host in request URL")
		
		
	def GetAccept(self):
		"""Returns an :py:class:`AcceptList` instance or None if no
		"Accept" header is present."""
		fieldValue=self.GetHeader("Accept")
		if fieldValue is not None:
			return AcceptList.FromString(fieldValue)
		else:
			return None
			
	def SetAccept(self,acceptValue):
		"""Sets the "Accept" header, replacing any existing value.
		
		*acceptValue*
			A :py:class:`AcceptList` instance or a string that one can
			be parsed from."""
		if type(acceptValue) in StringTypes:
			acceptValue=AcceptList.FromString(acceptValue)
		if not isinstance(acceptValue,AcceptList):
			raise TypeError
		self.SetHeader("Accept",str(acceptValue))

	def GetAcceptCharset(self):
		"""Returns an :py:class:`AcceptCharsetList` instance or None if
		no "Accept-Charset" header is present."""
		fieldValue=self.GetHeader("Accept-Charset")
		if fieldValue is not None:
			return AcceptCharsetList.FromString(fieldValue)
		else:
			return None
			
	def SetAcceptCharset(self,acceptValue):
		"""Sets the "Accept-Charset" header, replacing any existing value.
		
		*acceptValue*
			A :py:class:`AcceptCharsetList` instance or a string that
			one can be parsed from."""
		if type(acceptValue) in StringTypes:
			acceptValue=AcceptCharsetList.FromString(acceptValue)
		if not isinstance(acceptValue,AcceptCharsetList):
			raise TypeError
		self.SetHeader("Accept-Charset",str(acceptValue))

	def GetAcceptEncoding(self):
		"""Returns an :py:class:`AcceptEncodingList` instance or None if
		no "Accept-Encoding" header is present."""
		fieldValue=self.GetHeader("Accept-Encoding")
		if fieldValue is not None:
			return AcceptEncodingList.FromString(fieldValue)
		else:
			return None
			
	def SetAcceptEncoding(self,acceptValue):
		"""Sets the "Accept-Encoding" header, replacing any existing value.
		
		*acceptValue*
			A :py:class:`AcceptEncodingList` instance or a string that
			one can be parsed from."""
		if type(acceptValue) in StringTypes:
			acceptValue=AcceptEncodingList.FromString(acceptValue)
		if not isinstance(acceptValue,AcceptEncodingList):
			raise TypeError
		self.SetHeader("Accept-Encoding",str(acceptValue))

	def SetManager(self,manager):
		"""Called when we are queued in an HTTPRequestManager"""
		self.manager=manager
	
	def SetHTTPConnection(self,connection):
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
		logging.info("Sending request to %s",self.GetHost())
		logging.info("%s %s %s",self.method,self.url,str(self.protocolVersion))
		# Calculate the length of the message body for transfer
		self.CalculateTransferLength(self.reqBody)
		buffer.append("%s %s %s\r\n"%(self.method,self.url,str(self.protocolVersion)))
		# Check authorization and add credentials if the manager has them
		if not self.HasHeader("Authorization"):
			credentials=self.manager.FindCredentialsForURL(self.requestURI)
			if credentials:
				self.SetHeader('Authorization',str(credentials))			
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
		logging.debug("Request: %s %s %s",self.method,self.url,str(self.protocolVersion))
		logging.debug("Got Response: %i %s",self.response.status,self.response.reason)
		logging.debug("Response headers: %s",repr(self.response.headers))
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
			logging.error("Error receiving response, %s",str(self.response.connectionError))
			self.status=0
			self.Finished()
		else:
			logging.info("Finished Response, status %i",self.status)
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
		if self.tryCredentials is not None:
			# we were trying out some credentials, if this is not a 401 assume they're good
			if self.status==401:
				# we must remove these credentials, they matched the challenge but still resulted 401
				self.manager.RemoveCredentials(self.tryCredentials)
			else:
				if isinstance(self.tryCredentials,BasicCredentials):
					# path rule only works for BasicCredentials
					self.tryCredentials.AddSuccessPath(self.requestURI.absPath)
			self.tryCredentials=None
		if self.autoRedirect and self.status>=300 and self.status<=399 and (self.status!=302 or self.method.upper() in ("GET","HEAD")):
			# If the 302 status code is received in response to a request other
			# than GET or HEAD, the user agent MUST NOT automatically redirect the
			# request unless it can be confirmed by the user
			location=self.response.GetHeader("Location").strip()
			if location:
				url=uri.URIFactory.URI(location)
				if not url.host:
					# This is an error but a common one (thanks IIS!)
					location=location.Resolve(self.requestURI)
				self.Resend(location)
		elif self.status==401:
			challenges=self.response.GetWWWAuthenticate()
			for c in challenges:
				c.protectionSpace=self.requestURI.GetCanonicalRoot()
				self.tryCredentials=self.manager.FindCredentials(c)
				if self.tryCredentials:
					self.SetHeader('Authorization',str(self.tryCredentials))
					self.Resend()	# to the same URL

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
		super(HTTPResponse,self).__init__()
		self.Reset()
		self.request=request
		self.request.SetResponse(self)

	def Reset(self,resetHeaders=True):
		super(HTTPResponse,self).Reset(resetHeaders)
		self.connectionError=None
		self.protocolVersion=None
		self.status=None
		self.reason=None
		self.mode=self.RESP_STATUS
		self.currHeader=None
		self.waitStart=None
		
	def GetAcceptRanges(self):
		"""Returns an :py:class:`AcceptRanges` instance or None if no
		"Accept-Ranges" header is present."""
		fieldValue=self.GetHeader("Accept-Ranges")
		if fieldValue is not None:
			return AcceptRanges.FromString(fieldValue)
		else:
			return None
			
	def SetAcceptRanges(self,acceptValue):
		"""Sets the "Accept-Ranges" header, replacing any existing value.
		
		*acceptValue*
			A :py:class:`AcceptRanges` instance or a string that
			one can be parsed from."""
		if type(acceptValue) in StringTypes:
			acceptValue=AcceptRanges.FromString(acceptValue)
		if not isinstance(acceptValue,AcceptRanges):
			raise TypeError
		self.SetHeader("Accept-Ranges",str(acceptValue))

	def GetAge(self):
		"""Returns an integer or None if no "Age" header is present."""
		fieldValue=self.GetHeader("Age")
		if fieldValue is not None:
			hp=HeaderParser(fieldValue)
			return hp.RequireProductionEnd(hp.ParseDeltaSeconds())
		else:
			return None
			
	def SetAge(self,age):
		"""Sets the "Age" header, replacing any existing value.
		
		age
			an integer or long value or None to remove the header"""
		if age is None:
			self.SetHeader("Age",None)
		else:
			self.SetHeader("Age",str(age))

	def GetETag(self):
		"""Returns a :py:class:`EntityTag` instance parsed from the ETag
		header or None if no "ETag" header is present."""
		fieldValue=self.GetHeader("ETag")
		if fieldValue is not None:
			return EntityTag.FromString(fieldValue)
		else:
			return None
			
	def SetETag(self,eTag):
		"""Sets the "ETag" header, replacing any existing value.
		
		eTag
			a :py:class:`EntityTag` instance or None to remove
			any ETag header."""
		if eTag is None:
			self.SetHeader("ETag",None)
		else:
			self.SetHeader("ETag",str(eTag))		

	def GetWWWAuthenticate(self):
		"""Returns a list of :py:class:`~pyslet.rfc2617.Challenge`
		instances.
		
		If there are no challenges an empty list is returned."""
		fieldValue=self.GetHeader("WWW-Authenticate")
		if fieldValue is not None:
			return Challenge.ListFromString(fieldValue)
		else:
			return None

	def SetWWWAuthenticate(self,challenges):
		"""Sets the "WWW-Authenticate" header, replacing any exsiting
		value.
		
		challenges
			a list of :py:class:`~pyslet.rfc2617.Challenge` instances"""
		self.SetHeader("WWW-Authenticate",string.join(map(str,challenges),", "))

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
			statusLine=ParameterParser(line[:-2],ignoreSpace=False)
			self.protocolVersion=statusLine.ParseHTTPVersion()
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
			p=ParameterParser(line[:-2])
			chunkLink=p.ParseToken()
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
			fold=HTTPParser(h).ParseLWS()
			if fold and self.currHeader:
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
