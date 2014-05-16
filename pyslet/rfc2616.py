#! /usr/bin/env python

import logging
import string
import time
import datetime
import socket, ssl
import select
import types
import base64
import threading
import io
import pyslet.info as info
from pyslet.rfc2616_core import *
from pyslet.rfc2616_params import *
from pyslet.rfc2616_headers import *
from pyslet.rfc2617 import *
import pyslet.rfc2396 as uri

class RequestManagerBusy(HTTPException):
	"""Raised when attempting to queue a request and no connections
	become available within the specified timeout."""
	pass

class ConnectionClosed(HTTPException):
	"""Raised when attempting to queue a request when the manager object
	is in the process of closing."""
	pass

HTTP_PORT=80		#: symbolic name for the default HTTP port
HTTPS_PORT=443		#: symbolic name for the default HTTPS port

HTTP_VERSION=HTTPVersion(1,1)
"""A :py:class:`HTTPVersion` instance representing HTTP version 1.1"""

SOCKET_CHUNK=io.DEFAULT_BUFFER_SIZE
"""The default chunk size to use when reading from network sockets."""

USER_AGENT=ProductToken('pyslet',info.version)
"""A :py:class:`ProductToken` instance that can be used to represent the
current version of Pyslet."""
	
		
class Connection(object):
	"""Represents an HTTP connection.  Used internally by the request
	manager to manage connections to HTTP servers.  Each connection is
	assigned a unique :py:attr:`id` on construction.  In normal use you
	won't need to call any of these methods yourself but the interfaces
	are documented to make it easier to override the behaviour of the
	:py:class:`HTTPRequest` object that *may* call some of these
	connection methods to indicate protocol exceptions.
	
	Connections define comparison methods, if c1 and c2 are both
	instances then::
	
		c1 < c2 == True 
	
	...if c1 was last active before c2.  The connection's active time is
	updated each time :py:meth:`ConnectionTask` is called.
	
	Connections are shared across threads but are never in use by more
	than one thread at a time.  The thread currently bound to a
	connection is indicated by :py:attr:`threadId`.  The value of this
	attribute is managed by the associated
	:py:class:`HTTPRequestManager`. Methods *must only* be called
	from this thread unless otherwise stated.
	
	The scheme, hostname and port are defined on construction and
	do not change."""
	REQ_READY=0			#	ready to start a request
	REQ_BODY_WAITING=1	#	waiting to send the request body
	REQ_BODY_SENDING=2	#	sending the request body
	CLOSE_WAIT=3		#	waiting to disconnect
	
	MODE_STRINGS={0:"Ready",1:"Waiting",2:"Sending",3:"Closing"}
	
	IDEMPOTENT={"GET":1,"HEAD":1,"PUT":1,"DELETE":1,"OPTIONS":1,"TRACE":1,"CONNECT":0,"POST":0}
	
	def __init__(self,manager,scheme,hostname,port):
		self.manager=manager				#: the RequestManager that owns this connection
		self.id=self.manager._NextId()		#: the id of this connection object
		self.scheme=scheme					#: the http scheme in use, 'http' or 'https'
		self.host=hostname					#: the target host of this connection
		self.port=port						#: the target port of this connection
		self.threadId=None					#: the thread we're currently bound to
		self.lastActive=0					#: time at which this connection was last active
		self.requestQueue=[]				#: the queue of requests we are waiting to process
		self.request=None					#: the current request we are processing
		self.responseQueue=[]				#: the queue of responses we are waiting to process
		self.response=None					#: the current response we are processing
		self.requestMode=self.REQ_READY
		self.continueWaitMax=60.0			# If we don't get a continue in 1 minute, send the data anyway
		self.continueWaitStart=0
		# Low-level socket members
		self.connectionLock=threading.RLock()
		self.connectionClosed=False
		self.socket=None
		self.socketFile=None
		self.sendBuffer=[]
		self.recvBuffer=[]
		self.recvBufferSize=0

	def ThreadTargetKey(self):
		return (self.threadId,self.scheme,self.host,self.port)

	def TargetKey(self):
		return (self.scheme,self.host,self.port)
				
	def __cmp__(self,other):
		if not isinstance(other,Connection):
			raise TypeError
		return cmp(self.lastActive,other.lastActive)
		
	def __repr__(self):
		return "Connection(%s,%i)"%(self.host,self.port)
		
	def ConnectionTask(self):
		"""Processes the requests and responses for this connection.
		
		This method is mostly non-blocking.  It returns a (r,w) pair of
		file numbers suitable for passing to select indicating whether
		the connection is waiting to read and/or write data.  It will
		return None,None if the connection is not currently blocked on
		I/O.
		
		The connection object acts as a small buffer between the HTTP
		message itself and the server.  The implementation breaks down
		in to a number of phases:
		
		1.	Start processing a request if one is queued and we're ready
			for it.  For idempotent requests (in practice, everything
			except POST) we take advantage of HTTP pipelining to send
			the request without waiting for the previous response(s).
			
			The only exception is when the request has an Expect:
			100-continue header.  In this case the pipeline stalls until
			the server has caught up with us and sent the 100 response
			code.
		
		2.	Send as much data to the server as we can without blocking.

		3.	Read and process as much data from the server as we can
			without blocking.
		
		The above steps are repeated until we are blocked at which point
		we return.
		
		Although data is streamed in a non-blocking manner there are
		situations in which the method will block.  DNS name resolution
		and creation/closure of sockets may block."""
		rBusy=None;wBusy=None
		while True:
			self.lastActive=time.time()
			if self.requestQueue and self.requestMode==self.REQ_READY:
				request=self.requestQueue[0]
				if self.response is None or self.IDEMPOTENT.get(request.method,False):
					# If we are waiting for a response we only accept idempotent methods
					self.requestQueue=self.requestQueue[1:]
				self._StartRequest(request)
			if self.request or self.response:
				if self.socket is None:
					self.NewSocket()
				rBusy=None;wBusy=None
				# The first section deals with the sending cycle, we
				# pass on to the response section only if we are in a
				# waiting mode or we are waiting for the socket to be
				# ready before we can write data
				if self.sendBuffer:
					try:
						r,w,e=self.socketSelect([],[self.socketFile],[],0.0)
					except select.error,err:
						self.Close(err)
						w=[]
					if w:
						# We can write
						self._SendRequestData()
					if self.sendBuffer:
						# We are still waiting to write, move on to the response section!
						wBusy=self.socketFile
					else:
						continue
				elif self.requestMode==self.REQ_BODY_WAITING:
					# empty buffer and we're waiting for a 100-continue (that may never come)
					if self.continueWaitStart:
						if time.time()-self.continueWaitStart>self.continueWaitMax:
							logging.warn("%s timeout while waiting for 100-Continue response; sending anyway")
							self.requestMode=self.REQ_BODY_SENDING
					else:
						self.continueWaitStart=time.time()
				elif self.requestMode==self.REQ_BODY_SENDING:
					# Buffer is empty, refill it from the request
					data=self.request.ReadRequestBody()
					if data:
						logging.debug("Sending to %s: \n%s",self.host,data)
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
						if self._RecvResponseData():
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
				self.manager._DeactivateConnection(self)
				rBusy=None;wBusy=None
				break
		return rBusy,wBusy

	def RequestDisconnect(self):
		"""Disconnects the connection, aborting the current request."""
		self.request.Disconnect()
		self.request=None
		if self.response:
			self.sendBuffer=[]
			self.requestMode=self.CLOSE_WAIT
		else:
			self.Close()
			
	def Continue(self,request):
		"""Instructs the connection to start sending any pending request body.
		
		If a request had an "Expect: 100-continue" header then the
		connection will not send the data until instructed to do so by a
		call to this method, or
		:py:attr:`continueWaitMax` seconds have elapsed."""
		logging.debug("100 Continue received... ready to send request")
		if request is self.request and self.requestMode==self.REQ_BODY_WAITING:
			self.requestMode=self.REQ_BODY_SENDING
			
	def Close(self,err=None):
		"""Closes this connection nicelly, optionally logging the
		exception *err*

		The connection disconnects from the current request and
		terminates any responses we are waiting for by calling their
		:py:meth:`HTTPResponse.ServerDisconnect` methods.

		Finally, the socket is closed and all internal structures are
		reset ready to reconnect when the next request is queued."""		
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
		with self.connectionLock:
			if self.socket:
				oldS=self.socket
				self.socket=None
				if oldS is not None:
					self._CloseSocket(oldS)
		self.sendBuffer=[]
		self.recvBuffer=[]
		self.recvBufferSize=0
		self.requestMode=self.REQ_READY

	def Kill(self):
		"""Kills the connection, typically called from a different
		thread than the one currently bound (if any).
		
		No request methods are invoked, it is assumed that after this
		method the manager will relinquish control of the connection
		object creating space in the pool for other connections.  Once
		killed, a connection is never reconnected.
		
		If the owning thread calls ConnectionTask after Kill completes
		it will get a socket error or unexpectedly get zero-bytes on
		recv indicating the connection is broken.  We don't close the
		socket here, just shut it down to be nice to the server.
		
		If the owning thread really died, Python's garbage collection
		will take care of actually closing the socket and freeing up the
		file descriptor."""
		with self.connectionLock:
			logging.debug("Killing connection to %s",self.host)
			if not self.connectionClosed and self.socket:
				try:
					logging.warn("Connection.Kill forcing socket shutdown for %s",self.host)
					self.socket.shutdown(socket.SHUT_RDWR)
				except socket.error, msg:
					# ignore errors, most likely the server has stopped listening
					pass
				self.connectionClosed=True

	def _StartRequest(self,request):
		# Starts processing the request.  Returns True if the request
		# has been accepted for processing, False otherwise.
		self.request=request
		self.request.SetHTTPConnection(self)
		headers=self.request.ReadRequestHeader()
		logging.debug("Sending to %s: \n%s",self.host,headers)
		self.sendBuffer.append(headers)
		# Now check to see if we have an expect header set
		if self.request.GetExpectContinue():
			self.requestMode=self.REQ_BODY_WAITING
			self.continueWaitStart=0
		else:
			self.requestMode=self.REQ_BODY_SENDING
		logging.debug("%s: request mode=%s",self.host,self.MODE_STRINGS[self.requestMode])
		if self.response:
			# Queue a response as we're still handling the last one!
			self.responseQueue.append(HTTPResponse(self.request))
		else:
			self.response=HTTPResponse(self.request)
		return True
		
	def _SendRequestData(self):
		#	Sends the next chunk of data in the buffer
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
		
	def _RecvResponseData(self):
		#	We ask the response what it is expecting and try and
		#	satisfy that, we return True when the response has been
		#	received completely, False otherwise"""
		err=None
		try:
			data=self.socket.recv(SOCKET_CHUNK)
		except socket.error, e:
			# We can't truly tell if the server hung-up except by getting an error
			# here so this error could be fairly benign.
			err=e
			data=None
		logging.debug("Reading from %s: \n%s",self.host,repr(data))
		if data:
			nBytes=len(data)
			self.recvBuffer.append(data)
			self.recvBufferSize+=nBytes
		else:
			# TODO: this is typically a signal that the other end hung
			# up, we should implement the HTTP retry strategy for the
			# related request
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
		with self.connectionLock:
			if self.connectionClosed:
				logging.error("NewSocket called on dead connection to %s",self.host)
				raise HTTPException("Connection closed")
			self.socket=None
			self.socketFile=None
			self.socketSelect=select.select
		try:
			for target in self.manager.DNSLookup(self.host,self.port):
				family, socktype, protocol, canonname, address = target
				try:
					sNew=socket.socket(family, socktype, protocol)
					sNew.connect(address)
				except socket.error, msg:
					if sNew:
						sNew.close()
						sNew=None
					continue
				break
		except socket.gaierror,e:
			sNew=None
			raise HTTPException("failed to connect to %s (%s)"%(self.host,e[1]))
		if not sNew:
			raise HTTPException("failed to connect to %s"%self.host)
		else:
			with self.connectionLock:
				if self.connectionClosed:
					# This connection has been killed
					self._CloseSocket(newS)
					logging.error("Connection killed while connecting to %s",self.host)
					raise HTTPException("Connection closed")
				else:
					self.socket=sNew
					self.socketFile=self.socket.fileno()
					self.socketSelect=select.select
	
	def _CloseSocket(self,s):
		try:
			s.shutdown(socket.SHUT_RDWR)
		except socket.error, msg:
			# ignore errors, most likely the server has stopped listening
			pass
		try:
			s.close()
		except socket.error, msg:
			pass
		

class SecureConnection(Connection):

	def __init__(self,manager,scheme,hostname,port,ca_certs=None):
		super(SecureConnection,self).__init__(manager,scheme,hostname,port)
		self.ca_certs=ca_certs
		
	def NewSocket(self):
		super(SecureConnection,self).NewSocket()
		try:
			with self.connectionLock:
				if self.socket is not None:
					socketSSL=ssl.wrap_socket(self.socket,ca_certs=self.ca_certs,
						cert_reqs=ssl.CERT_REQUIRED if self.ca_certs is not None else ssl.CERT_NONE)
					# self.socketSSL=socket.ssl(self.socket)
					self.socketTransport=self.socket
					self.socket=socketSSL
					logging.info("Connected to %s with %s, %s, key length %i",self.host,*self.socket.cipher())
		except socket.error,err:
			raise HTTPException("failed to build secure connection to %s"%self.host)

			
class HTTPRequestManager(object):
	"""An object for managing the sending of HTTP/1.1 requests and
	receiving of responses.  There are a number of keyword arguments
	that can be used to set operational parameters:
	
	maxConnections
		The maximum number of HTTP connections that may be open at any one
		time.  The method :py:meth:`QueueRequest` will block (or raise
		:py:class:`RequestManagerBusy`) if an attempt to queue a request
		would cause this limit to be exceeded.
	
	ca_certs
		The file name of a certificate file to use when checking SSL
		connections.  For more information see
		http://docs.python.org/2.7/library/ssl.html

	.. warning::

		By default, ca_certs is optional and can be passed as None.  In this
		mode certificates will not be checked and your connections are not
		secure from man in the middle attacks.  In production use you should
		always specify a certificate file if you expect to use the object to
		make calls to https URLs.
	
	Although maxConnections allows you to make multiple connections to
	the same host+port the request manager imposes an additional
	restriction. Each thread can make at most 1 connection to each
	host+port.  If multiple requests are made to the same host+port from
	the same thread then they are queued and will be sent to the server
	over the same connection using HTTP/1.1 pipelining. The manager
	(mostly) takes care of the following restriction imposed by RFC2616:
	
		Clients SHOULD NOT pipeline requests using non-idempotent
		methods or non-idempotent sequences of methods	

	In other words, a POST 	(or CONNECT) request will cause the
	pipeline to stall until all the responses have been received.  Users
	should beware of non-idempotent sequences as these are not
	automatically detected by the manager.  For example, a GET,PUT
	sequence on the same resource is not idempotent. Users should wait
	for the GET request to finish fetching the resource before queuing a
	PUT request that overwrites it.
	
	In summary, to take advantage of multiple simultaneous connections
	to the same host+port you must use multiple threads."""
	ConnectionClass=Connection
	SecureConnectionClass=SecureConnection
	
	def __init__(self,maxConnections=100,ca_certs=None):
		self.managerLock=threading.Condition()
		self.nextId=1			# the id of the next connection object we'll create
		self.cActiveThreadTargets={}
		#	A dict of active connections keyed on thread and target (always unique)
		self.cActiveThreads={}
		#	A dict of dicts of active connections keyed on thread id then connection id
		self.cIdleTargets={}
		#	A dict of dicts of idle connections keyed on target and then connection id
		self.cIdleList={}
		#	A dict of idle connections keyed on connection id (for keeping count)
		self.closing=False					# True if we are closing
		self.maxConnections=maxConnections	# maximum number of connections to manage (set only on construction)
		self.dnsCache={}					# cached results from socket.getaddrinfo keyed on (hostname,port)
		self.ca_certs=ca_certs
		self.credentials=[]
		self.socketSelect=select.select
		self.httpUserAgent="%s (HTTPRequestManager)"%str(USER_AGENT)
		"""The default User-Agent string to use."""
		
	def QueueRequest(self,request,timeout=None):
		"""Instructs the manager to start processing *request*.
		
		request
			A :py:class:`HTTPRequest` object.
		
		timeout
			Number of seconds to wait for a free connection before timing
			out.  A timeout raises :py:class:`RequestManagerBusy`
			
			None means wait forever, 0 means don't block.
			
		The default implementation adds a User-Agent header from
		:py:attr:`httpUserAgent` if none has been specified already. 
		You can override this method to add other headers appropriate
		for a specific context but you must pass this call on to this
		implementation for proper processing."""
		if self.httpUserAgent and not request.HasHeader('User-Agent'):
			request.SetHeader('User-Agent',self.httpUserAgent)
		# assign this request to a connection straight away
		start=time.time()
		threadId=threading.current_thread().ident
		threadTarget=(threadId,request.scheme,request.hostname,request.port)
		target=(request.scheme,request.hostname,request.port)
		with self.managerLock:
			if self.closing:
				raise ConnectionClosed
			while True:
				# Step 1: search for an active connection to the same
				# target already bound to our thread
				if threadTarget in self.cActiveThreadTargets:
					connection=self.cActiveThreadTargets[threadTarget]
					break
				# Step 2: search for an idle connection to the same
				# target and bind it to our thread
				elif target in self.cIdleTargets:
					cIdle=self.cIdleTargets[target].values()
					cIdle.sort()
					# take the youngest connection
					connection=cIdle[-1]
					self._ActivateConnection(connection,threadId)
					break
				# Step 3: create a new connection
				elif len(self.cActiveThreadTargets)+len(self.cIdleList)<self.maxConnections:
					connection=self._NewConnection(target)
					self._ActivateConnection(connection,threadId)
					break
				# Step 4: delete the oldest idle connection and go round again
				elif len(self.cIdleList):
					cIdle=self.cIdleList.values()
					cIdle.sort()
					connection=cIdle[0]
					self._DeleteIdleConnection(connection)
				# Step 5: wait for something to change
				else:
					now=time.time()
					if timeout==0:
						logging.warn("non-blocking call to QueueRequest failed to obtain an HTTP connection") 
						raise RequestManagerBusy
					elif timeout is not None and now>start+timeout:
						logging.warn("QueueRequest timed out while waiting for an HTTP connection")
						raise RequestManagerBusy
					logging.debug("QueueRequest forced to wait for an HTTP connection")
					self.managerLock.wait(timeout)
					logging.debug("QueueRequest resuming search for an HTTP connection")
			# add this request tot he queue on the connection
			connection.requestQueue.append(request)
			request.SetManager(self)

	def ActiveCount(self):
		"""Returns the total number of active connections."""
		with self.managerLock:
			return len(self.cActiveThreadTargets)

	def ThreadActiveCount(self):
		"""Returns the total number of active connections associated
		with the current thread."""
		threadId=threading.current_thread().ident
		with self.managerLock:
			return len(self.cActiveThreads.get(threadId,{}))
		
	def _ActivateConnection(self,connection,threadId):
		# safe if connection is new and not in the idle list
		connection.threadId=threadId
		target=connection.TargetKey()
		threadTarget=connection.ThreadTargetKey()
		with self.managerLock:
			self.cActiveThreadTargets[threadTarget]=connection
			if threadId in self.cActiveThreads:
				self.cActiveThreads[threadId][connection.id]=connection
			else:
				self.cActiveThreads[threadId]={connection.id:connection}
			if connection.id in self.cIdleList:
				del self.cIdleList[connection.id]
				del self.cIdleTargets[target][connection.id]
				if not self.cIdleTargets[target]:
					del self.cIdleTargets[target]

	def _DeactivateConnection(self,connection):
		# called when connection goes idle, it is possible that this
		# connection has been killed and just doesn't know it (like
		# Bruce Willis in Sixth Sense) so we take care to return it
		# to the idle pool only if it was in the active pool
		target=connection.TargetKey()
		threadTarget=connection.ThreadTargetKey()
		with self.managerLock:
			if threadTarget in self.cActiveThreadTargets:
				del self.cActiveThreadTargets[threadTarget]
				self.cIdleList[connection.id]=connection
				if target in self.cIdleTargets:
					self.cIdleTargets[target][connection.id]=connection
				else:
					self.cIdleTargets[target]={connection.id:connection}
				# tell any threads waiting for a connection
				self.managerLock.notify()			
			if connection.threadId in self.cActiveThreads:
				if connection.id in self.cActiveThreads[connection.threadId]:
					del self.cActiveThreads[connection.threadId][connection.id]
				if not self.cActiveThreads[connection.threadId]:
					del self.cActiveThreads[connection.threadId]
			connection.threadId=None
			
	def _DeleteIdleConnection(self,connection):
		if connection.id in self.cIdleList:
			target=connection.TargetKey()
			del self.cIdleList[connection.id]
			del self.cIdleTargets[target][connection.id]
			if not self.cIdleTargets[target]:
				del self.cIdleTargets[target]
			connection.Close()
			
	def _NextId(self):
		#	Used internally to manage auto-incrementing connection ids
		with self.managerLock:
			id=self.nextId
			self.nextId+=1
		return id
		
	def _NewConnection(self,target,timeout=None):
		#	Called by a connection pool when a new connection is required
		scheme,host,port=target
		if scheme=='http':
			connection=self.ConnectionClass(self,scheme,host,port)
		elif scheme=='https':
			connection=self.SecureConnectionClass(self,scheme,host,port,self.ca_certs)
		else:
			raise NotImplementedError("Unsupported connection scheme: %s"%scheme)
		return connection
		
	def ThreadTask(self,timeout=None):
		"""Processes all connections bound to the current thread then
		blocks for at most timeout (0 means don't block) while waiting
		to send/receive data from any active sockets.
		
		Each active connection receives one call to
		:py:meth:`Connection.ConnectionTask` There are some situations
		where this method may still block even with timeout=0.  For
		example, DNS name resolution and SSL handshaking.  These may be
		improved in future.
		
		Returns True if at least one connection is active, otherwise
		returns False."""
		threadId=threading.current_thread().ident
		with self.managerLock:
			connections=self.cActiveThreads.get(threadId,{}).values()
		if not connections:
			return False
		readers=[]
		writers=[]
		for c in connections:
			try:
				r,w=c.ConnectionTask()
				if r:
					readers.append(r)
				if w:
					writers.append(w)
			except HTTPException, err:
				c.Close(err)
				pass
		if (timeout is None or timeout>0) and (readers or writers):
			try:
				#	logging.debug("Socket select for: readers=%s, writers=%s, timeout=%i",repr(readers),repr(writers),timeout)
				r,w,e=self.socketSelect(readers,writers,[],timeout)
			except select.error, err:
				logging.error("Socket error from select: %s",str(err)) 
		return True
			
	def ThreadLoop(self,timeout=60):
		"""Repeatedly calls :py:meth:`ThreadTask` until it returns False."""		
		while self.ThreadTask(timeout):
			continue
		# self.Close()

	def ProcessRequest(self,request,timeout=60):
		"""Process an :py:class:`HTTPRequest` object.
		
		The request is queued and then :py:meth:`ThreadLoop` is called to exhaust all
		HTTP activity initiated by the current thread."""
		self.QueueRequest(request,timeout)
		self.ThreadLoop(timeout)
	
	def IdleCleanup(self,maxInactive=15):
		"""Cleans up any idle connections that have been inactive for
		more than *maxInactive* seconds."""
		cList=[]
		now=time.time()
		with self.managerLock:
			for connection in self.cIdleList.values():
				if connection.lastActive<now-maxInactive:
					cList.append(connection)
					del self.cIdleList[connection.id]
					target=connection.TargetKey()
					if target in self.cIdleTargets:
						del self.cIdleTargets[target][connection.id]
						if not self.cIdleTargets[target]:
							del self.cIdleTargets[target]
		# now we can clean up these connections in a more leisurely fashion
		if cList:
			logging.debug("IdleCleanup closing connections...")  		
			for connection in cList:
				connection.Close()		
	
	def ActiveCleanup(self,maxInactive=90):
		"""Clean up active connections that have been inactive for
		more than *maxInactive* seconds.
		
		This method can be called from any thread and can be used to
		remove connections that have been abandoned by their owning
		thread.  This can happen if the owning thread stops calling
		:py:meth:`ThreadTask` leaving some connections active.
		
		Inactive connections are killed using :py:meth:`Connection.Kill`
		and then removed from the active list.  Should the owning thread
		wake up and attempt to finish processing the requests a socket
		error or :py:class:`HTTPException` will be reported."""
		cList=[]
		now=time.time()
		with self.managerLock:
			for threadId in self.cActiveThreads:
				for connection in self.cActiveThreads[threadId].values():
					if connection.lastActive<now-maxInactive:
						# remove this connection from the active lists
						del self.cActiveThreads[threadId][connection.id]
						del self.cActiveThreadTargets[connection.ThreadTargetKey()]
						cList.append(connection)
			if cList:
				# if stuck threads were blocked waiting for a connection
				# then we can wake them up, one for each connection
				# killed
				self.managerLock.notify(len(cList))		
		if cList:
			logging.debug("ActiveCleanup killing connections...")  		
			for connection in cList:
				connection.Kill()
	
	def Close(self):
		"""Closes all connections and sets the manager to a state where
		new connections cannot not be created.
		
		Active connections are killed, idle connections are closed."""
		while True:
			with self.managerLock:
				self.closing=True
				if len(self.cActiveThreadTargets)+len(self.cIdleList)==0:
					break
			self.ActiveCleanup(0)
			self.IdleCleanup(0)
		
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
				if c.TestURL(url):
					return c
	
# 	def Close(self):
# 		for connection in self.connections.values():
# 			connection.Close()		


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
	"""Represents an HTTP request.
	
	To make an HTTP request, create an instance of this class and then
	pass it to an :py:class:`HTTPRequestManager` instance using either
	:py:meth:`HTTPRequestManager.QueueRequest` or
	:py:meth:`HTTPRequestManager.ProcessRequest`.
	
	url
		An absolute URI using either http or https schemes.  A
		:py:class:`pyslet.rfc2396.URI` instance or an object that can be
		passed to its constructor.

	method
		A string.  The HTTP method to use, defaults to "GET"
	
	reqBody
		A string or stream-like object containing the request body. 
		Defaults to an empty string.  For stream-like objects the tell
		and seek methods must be supported to enable resending the
		request if required.
	
	resBody
		A stream-like object to write data to.  Defaults to None, in
		which case the response body is returned as a string the
		:py:attr:`resBody`.
	
	protocolVersion
		An :py:class:`HTTPVersion` object, defaults to HTTPVersion(1,1)"""
	def __init__(self,url,method="GET",reqBody='',resBody=None,protocolVersion=HTTP_VERSION):
		super(HTTPRequest,self).__init__()
		self.manager=None
		self.connection=None
		self.response=None		#: the associated :py:class:`HTTPResponse`
		self.status=0			#: the status code received, 0 indicates a failed or unsent request
		self.error=None			#: If status==0, the error raised during processing 
		self.SetRequestURI(url)
		self.method=method		#: the method
		if type(protocolVersion) in StringTypes:
			self.protocolVersion=HTTPVersion.FromString(protocolVersion)
		elif isinstance(protocolVersion,HTTPVersion):
			self.protocolVersion=protocolVersion
		else:
			raise TypeError("illegal value for protocolVersion")
		if type(reqBody) is types.StringType:
			self.reqBody=reqBody
			self.reqBodyStream=None
		else:
			# assume that the reqBody is a stream like object,
			# record the current position to support Resend
			self.reqBodyStream=reqBody
			self.reqBodyStart=reqBody.tell()
			self.reqBody=None
		self.resBody=''			#: the response body received (only used if not streaming)
		self.resBuffer=[]
		if resBody is not None:
			# assume that the resBody is a stream like object
			self.resBodyStream=resBody
			self.resBodyStart=resBody.tell()
		else:
			self.resBodyStream=None
		self.autoRedirect=True	#: flag indicating whether or not to auto-redirect 3xx responses
		self.done=False			
		self.tryCredentials=None
		
	def Resend(self,url=None):
		self.done=False
		logging.info("Resending request to: %s",str(url))
		self.Reset()
		self.status=0
		self.error=None
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
		"""Called when we are queued for processing by an :py:class:`HTTPRequestManager`"""
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
		
	def ResponseFinished(self,err=None):
		self.status=self.response.status
		self.error=err
		if self.status is None:
			logging.error("Error receiving response, %s",str(self.error))
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
		"""Called when we have a final response *and* have disconnected
		from the connection There is no guarantee that the server got
		all of our data, it might even have returned a 2xx series code
		and then hung up before reading the data, maybe it already had
		what it needed, maybe it thinks a 2xx response is more likely to
		make us go away.  Whatever.  The point is that you can't be sure
		that all the data was transmitted just because you got here and
		the server says everything is OK"""
		self.done=True
		if self.tryCredentials is not None:
			# we were trying out some credentials, if this is not a 401 assume they're good
			if self.status==401:
				# we must remove these credentials, they matched the challenge but still resulted in 401
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
			chunkLine=p.ParseToken()
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
		self.reason=str(err)
		self.request.ResponseFinished(err)
