#! /usr/bin/env python

import logging
import string
import time
import socket
import ssl
import select
import types
import threading
import io
import errno
import os
import random

import pyslet.info as info
import pyslet.rfc2396 as uri
from pyslet.pep8 import PEP8Compatibility

import grammar
import params
import messages
import auth


class RequestManagerBusy(messages.HTTPException):

    """The HTTP client is busy

    Raised when attempting to queue a request and no connections become
    available within the specified timeout."""
    pass


class ConnectionClosed(messages.HTTPException):

    """The HTTP client has been closed

    Raised when attempting to queue a request for a :py:class:`Client`
    object that is in the process of closing."""
    pass


USER_AGENT = params.ProductToken('pyslet', info.version)
"""A :py:class:`ProductToken` instance

This value is used as the default UserAgent string and is based on the
current version of the Pyslet library.  E.g.::

    pyslet-0.5.20120801"""


class Connection(object):

    """Represents an HTTP connection.

    manager
        The :py:class:`Client` instance that owns us

    scheme
        The scheme we are being opened for ('http' or 'https')

    hostname
        The host name we should connect to

    port
        The port we should connect to

    timeout
        The maximum time to wait for a connection.  If the connection
        has not been able to read or write data for more than this
        timeout value it will assume the server has hung up.  Defaults
        to None, no timeout.

    Used internally by the :py:class:`Client` to manage connections to
    HTTP servers.  Each connection is assigned a unique :py:attr:`id` on
    construction.  In normal use you won't need to call any of these
    methods yourself but the interfaces are documented to make it easier
    to override the behaviour of the
    :py:class:`messages.Message` object that *may* call some of these
    connection methods to indicate protocol exceptions.

    Connections define comparison methods, if c1 and c2 are both
    instances then::

        c1 < c2 == True

    ...if c1 was last active before c2.  The connection's active time is
    updated each time :py:meth:`connection_task` is called.

    Connections are shared across threads but are never in use by more
    than one thread at a time.  The thread currently bound to a
    connection is indicated by :py:attr:`thread_id`.  The value of this
    attribute is managed by the associated
    :py:class:`Client`. Methods *must only* be called
    from this thread unless otherwise stated.

    The scheme, hostname and port are defined on construction and do not
    change."""

    # mode constant: ready to start a request
    REQ_READY = 0

    # mode constant: waiting to send the request body
    REQ_BODY_WAITING = 1

    # mode constant: sending the request body
    REQ_BODY_SENDING = 2

    # mode constant: waiting to disconnect
    CLOSE_WAIT = 3

    # a mapping to make debugging messages easier to read
    MODE_STRINGS = {0: "Ready", 1: "Waiting", 2: "Sending", 3: "Closing"}

    def __init__(self, manager, scheme, hostname, port, timeout=None):
        #: the RequestManager that owns this connection
        self.manager = manager
        #: the id of this connection object
        self.id = self.manager._nextid()
        #: the http scheme in use, 'http' or 'https'
        self.scheme = scheme
        #: the target host of this connection
        self.host = hostname
        #: the target port of this connection
        self.port = port
        #: the protocol version of the last response from the server
        self.protocol = None
        #: the thread we're currently bound to
        self.thread_id = None
        #: time at which this connection was last active
        self.last_active = 0
        #: timeout (seconds) for our connection
        self.timeout = timeout
        #: time of the last successful read or write operation
        self.last_rw = None
        #: the queue of requests we are waiting to process
        self.request_queue = []
        #: the current request we are processing
        self.request = None
        #: the queue of responses we are waiting to process
        self.response_queue = []
        #: the current response we are processing
        self.response = None
        self.request_mode = self.REQ_READY
        # If we don't get a continue in 1 minute, send the data anyway
        if timeout is None:
            self.continue_waitmax = 60.0
        else:
            # this rather odd simplification is based on a typical
            # request timeout of 90s on a server corresponding to a wait
            # of 15s for the 100 Continue response.
            self.continue_waitmax = timeout / 6
        self.continue_waitstart = 0
        # a lock for our structures to help us go multi-threaded
        self.lock = threading.RLock()
        # True if we are closed or closing
        self.closed = False
        # Low-level socket members
        self.socket = None
        self.socket_file = None
        self.send_buffer = []
        # the number of bytes buffered for sending
        self.buffered_bytes = 0
        #: The number of bytes sent to the server since the connection
        #: was last established
        self.sent_bytes = 0
        self.recv_buffer = []
        self.recv_buffer_size = 0

    def thread_target_key(self):
        return (self.thread_id, self.scheme, self.host, self.port)

    def target_key(self):
        return (self.scheme, self.host, self.port)

    def __cmp__(self, other):
        if not isinstance(other, Connection):
            raise TypeError
        return cmp(self.last_active, other.last_active)

    def __repr__(self):
        return "Connection(%s,%i)" % (self.host, self.port)

    def queue_request(self, request):
        self.request_queue.append(request)

    def connection_task(self):
        """Processes the requests and responses for this connection.

        This method is mostly non-blocking.  It returns a (r,w,wait)
        triple consisting of two sockets or file numbers and a wait time
        (in seconds).  The first two values are suitable for passing
        to select and indicate whether the connection is waiting to read
        and/or write data.  Either or both may be None.  The third value
        indicates the desired maximum amount of time to wait before the next
        call and is usually set to the connection's timeout.

        The connection object acts as a small buffer between the HTTP
        message itself and the server.  The implementation breaks down
        in to a number of phases:

        1.  Start processing a request if one is queued and we're ready
            for it.  For idempotent requests (in practice, everything
            except POST) we take advantage of HTTP pipelining to send
            the request without waiting for the previous response(s).

            The only exception is when the request has an Expect:
            100-continue header.  In this case the pipeline stalls until
            the server has caught up with us and sent the 100 response
            code.

        2.  Send as much data to the server as we can without blocking.

        3.  Read and process as much data from the server as we can
            without blocking.

        The above steps are repeated until we are blocked at which point
        we return.

        Although data is streamed in a non-blocking manner there are
        situations in which the method will block.  DNS name resolution
        and creation/closure of sockets may block."""
        while True:
            rbusy = False
            wbusy = False
            tbusy = None
            self.last_active = time.time()
            if self.request_queue and self.request_mode == self.REQ_READY:
                request = self.request_queue[0]
                if (request.is_idempotent() or
                    (self.response is None and
                     not self.send_buffer)):
                    # only pipeline idempotent methods, our pipelining
                    # is strict for POST requests, wait for the
                    # response, request and buffer to be finished.
                    wait_time = request.retry_time - time.time()
                    if wait_time <= 0:
                        self.request_queue = self.request_queue[1:]
                        self._start_request(request)
                    elif tbusy is None or wait_time < tbusy:
                        tbusy = wait_time
            if self.request or self.response:
                if self.socket is None:
                    self.new_socket()
                rbusy = False
                wbusy = False
                # The first section deals with the sending cycle, we
                # pass on to the response section only if we are in a
                # waiting mode or we are waiting for the socket to be
                # ready before we can write data
                if self.send_buffer:
                    send_rbusy, send_wbusy = self._send_request_data()
                    rbusy = rbusy or send_rbusy
                    wbusy = wbusy or send_wbusy
                    if rbusy or wbusy:
                        if (self.last_rw is not None and
                                self.timeout is not None and
                                self.last_rw + self.timeout < time.time()):
                            # assume we're dead in the water
                            raise IOError(
                                errno.ETIMEDOUT,
                                os.strerror(errno.ETIMEDOUT),
                                "pyslet.http.client.Connection")
                    else:
                        continue
                elif self.request_mode == self.REQ_BODY_WAITING:
                    # empty buffer and we're waiting for a 100-continue
                    # (that may never come)
                    if self.continue_waitstart:
                        logging.info("%s waiting for 100-Continue...",
                                     self.host)
                        wait_time = (self.continue_waitmax -
                                     (time.time() - self.continue_waitstart))
                        if (wait_time < 0):
                            logging.warn("%s timeout while waiting for "
                                         "100-Continue response",
                                         self.host)
                            self.request_mode = self.REQ_BODY_SENDING
                            # change of mode, restart the loop
                            continue
                        else:
                            # we need to be called again in at most
                            # wait_time seconds so we can give up
                            # waiting for the 100 response
                            if tbusy is None or tbusy > wait_time:
                                tbusy = wait_time
                    else:
                        self.continue_waitstart = time.time()
                        wait_time = self.continue_waitmax
                        if tbusy is None or tbusy > wait_time:
                            tbusy = wait_time
                elif self.request_mode == self.REQ_BODY_SENDING:
                    # Buffer is empty, refill it from the request
                    data = self.request.send_body()
                    if data:
                        logging.debug("Sending to %s: \n%s", self.host, data)
                        self.send_buffer.append(data)
                        self.buffered_bytes += len(data)
                        # Go around again to send the buffer
                        continue
                    elif data is None:
                        logging.debug("send_body blocked "
                                      "waiting for message body")
                        # continue on to the response section
                    else:
                        # Buffer is empty, request is exhausted, we're
                        # done with it! we might want to tell the
                        # associated respone that it is now waiting, but
                        # matching is hard when pipelining!
                        # self.response.StartWaiting()
                        self.request.disconnect(self.sent_bytes)
                        self.request = None
                        self.request_mode = self.REQ_READY
                # This section deals with the response cycle, we only
                # get here once the buffer is empty or we're blocked on
                # sending.
                if self.response:
                    recv_done, recv_rbusy, recv_wbusy = self._recv_task()
                    rbusy = rbusy or recv_rbusy
                    wbusy = wbusy or recv_wbusy
                    if rbusy or wbusy:
                        if (self.last_rw is not None and
                                self.timeout is not None and
                                self.last_rw + self.timeout < time.time()):
                            # assume we're dead in the water
                            raise IOError(
                                errno.ETIMEDOUT,
                                os.strerror(errno.ETIMEDOUT),
                                "pyslet.http.client.Connection")
                    else:
                        if recv_done:
                            # The response is done
                            close_connection = False
                            if self.response:
                                self.protocol = self.response.protocol
                                close_connection = not self.response.keep_alive
                            if self.response_queue:
                                self.response = self.response_queue[0]
                                self.response_queue = self.response_queue[1:]
                                self.response.start_receiving()
                            elif self.response:
                                self.response = None
                                if self.request_mode == self.CLOSE_WAIT:
                                    # no response and waiting to close the
                                    # connection
                                    close_connection = True
                            if close_connection:
                                self.close()
                        # Any data received on the connection could
                        # change the request state, so we loop round
                        # again
                        continue
                break
            elif self.request_queue:
                # no request or response but we're waiting for a retry
                rbusy = False
                wbusy = False
                break
            else:
                # no request or response, we're idle
                if self.request_mode == self.CLOSE_WAIT:
                    # clean up if necessary
                    self.close()
                self.manager._deactivate_connection(self)
                rbusy = False
                wbusy = False
                break
        if (rbusy or wbusy) and (tbusy is None or tbusy > self.timeout):
            # waiting for i/o, make sure the timeout is capped
            tbusy = self.timeout
        if rbusy:
            rbusy = self.socket_file
        if wbusy:
            wbusy = self.socket_file
        logging.debug("connection_task returning %s, %s, %s",
                      repr(rbusy), repr(wbusy), str(tbusy))
        if not rbusy and not wbusy and tbusy is not None and tbusy > 50:
            import pdb
            pdb.set_trace()
        return rbusy, wbusy, tbusy

    def request_disconnect(self):
        """Disconnects the connection, aborting the current request."""
        self.request.disconnect(self.sent_bytes)
        self.request = None
        if self.response:
            self.send_buffer = []
            self.request_mode = self.CLOSE_WAIT
        else:
            self.close()

    def continue_sending(self, request):
        """Instructs the connection to start sending any pending request body.

        If a request had an "Expect: 100-continue" header then the
        connection will not send the data until instructed to do so by a
        call to this method, or
        :py:attr:`continue_waitmax` seconds have elapsed."""
        logging.debug("100 Continue received... ready to send request")
        if (request is self.request and
                self.request_mode == self.REQ_BODY_WAITING):
            self.request_mode = self.REQ_BODY_SENDING

    def close(self, err=None):
        """Closes this connection nicelly, optionally logging the
        exception *err*

        The connection disconnects from the current request and
        terminates any responses we are waiting for by calling their
        :py:meth:`ClientResponse.handle_disconnect` methods.

        Finally, the socket is closed and all internal structures are
        reset ready to reconnect when the next request is queued."""
        if err:
            logging.error(
                "%s: closing connection after error %s", self.host, str(err))
        else:
            logging.debug("%s: closing connection", self.host)
        if self.request:
            self.request.disconnect(self.sent_bytes)
            self.request = None
            self.request_mode = self.CLOSE_WAIT
        resend = True
        while self.response:
            response = self.response
            # remove it from the queue
            if self.response_queue:
                self.response = self.response_queue[0]
                self.response_queue = self.response_queue[1:]
            else:
                self.response = None
            # check for resends
            if err or response.status is None and resend:
                # terminated by an error or before we read the response
                if response.request.can_retry():
                    # resend this request
                    logging.warn("retrying %s", response.request.get_start())
                    self.queue_request(response.request)
                    continue
                else:
                    resend = False
            response.handle_disconnect(err)
        with self.lock:
            if self.socket:
                olds = self.socket
                self.socket = None
                if olds is not None:
                    self._close_socket(olds)
        self.send_buffer = []
        self.buffered_bytes = 0
        self.sent_bytes = 0
        self.recv_buffer = []
        self.recv_buffer_size = 0
        self.request_mode = self.REQ_READY

    def kill(self):
        """Kills the connection, typically called from a different
        thread than the one currently bound (if any).

        No request methods are invoked, it is assumed that after this
        method the manager will relinquish control of the connection
        object creating space in the pool for other connections.  Once
        killed, a connection is never reconnected.

        If the owning thread calls connection_task after kill completes
        it will get a socket error or unexpectedly get zero-bytes on
        recv indicating the connection is broken.  We don't close the
        socket here, just shut it down to be nice to the server.

        If the owning thread really died, Python's garbage collection
        will take care of actually closing the socket and freeing up the
        file descriptor."""
        with self.lock:
            logging.debug("Killing connection to %s", self.host)
            if not self.closed and self.socket:
                try:
                    logging.warn(
                        "Connection.kill forcing socket shutdown for %s",
                        self.host)
                    self.socket.shutdown(socket.SHUT_RDWR)
                except IOError:
                    # ignore errors, most likely the server has stopped
                    # listening
                    pass
                self.closed = True

    def _start_request(self, request):
        # Starts processing the request.  Returns True if the request
        # has been accepted for processing, False otherwise.
        self.request = request
        self.request.connect(self, self.buffered_bytes)
        self.request.start_sending(self.protocol)
        headers = self.request.send_start() + self.request.send_header()
        logging.debug("Sending to %s: \n%s", self.host, headers)
        self.send_buffer.append(headers)
        self.buffered_bytes += len(headers)
        # Now check to see if we have an expect header set
        if self.request.get_expect_continue():
            self.request_mode = self.REQ_BODY_WAITING
            self.continue_waitstart = 0
        else:
            self.request_mode = self.REQ_BODY_SENDING
        logging.debug("%s: request mode=%s", self.host,
                      self.MODE_STRINGS[self.request_mode])
        if self.response:
            # Queue a response as we're still handling the last one!
            self.response_queue.append(request.response)
        else:
            self.response = request.response
            self.response.start_receiving()
        return True

    def _send_request_data(self):
        #   Sends the next chunk of data in the buffer
        if not self.send_buffer:
            return
        data = self.send_buffer[0]
        if data:
            try:
                nbytes = self.socket.send(data)
                self.sent_bytes += nbytes
                self.last_rw = time.time()
            except ssl.SSLError as err:
                if err.args[0] == ssl.SSL_ERROR_WANT_READ:
                    # we're blocked on recv, really this can happen!
                    return (True, False)
                elif err.args[0] == ssl.SSL_ERROR_WANT_WRITE:
                    # we're blocked on send, really this can happen!
                    return (False, True)
                else:
                    # we're going to swallow this error, log it
                    logging.error("socket.recv raised %s", str(err))
                    data = None
            except IOError as err:
                if err.errno == errno.EAGAIN:
                    # we're blocked on send
                    return (False, True)
                # stop everything
                self.close(err)
                return (False, False)
            if nbytes == 0:
                # We can't send any more data to the socket
                # The other side has closed the connection
                # Strangely, there is nothing much to do here,
                # if the server fails to send a response that
                # will be handled more seriously.  However,
                # we do change to a mode that prevents future
                # requests!
                self.request.disconnect(self.sent_bytes)
                self.request = None
                self.request_mode == self.CLOSE_WAIT
                self.send_buffer = []
            elif nbytes < len(data):
                # Some of the data went:
                self.send_buffer[0] = data[nbytes:]
            else:
                del self.send_buffer[0]
        else:
            # shouldn't get empty strings in the buffer but if we do, delete
            # them, no change to the buffer size!
            del self.send_buffer[0]
        return (False, False)

    def _recv_task(self):
        #   We ask the response what it is expecting and try and
        #   satisfy that, we return True when the response has been
        #   received completely, False otherwise"""
        err = None
        try:
            data = self.socket.recv(io.DEFAULT_BUFFER_SIZE)
            self.last_rw = time.time()
        except ssl.SSLError as err:
            if err.args[0] == ssl.SSL_ERROR_WANT_READ:
                # we're blocked on recv
                return (False, True, False)
            elif err.args[0] == ssl.SSL_ERROR_WANT_WRITE:
                # we're blocked on send, really this can happen!
                return (False, False, True)
            else:
                # we're going to swallow this error, log it
                logging.error("socket.recv raised %s", str(err))
                data = None
        except IOError as err:
            if err.errno == errno.EAGAIN:
                # we're blocked on recv
                return (False, True, False)
            # We can't truly tell if the server hung-up except by
            # getting an error here so this error could be fairly benign.
            logging.warn("socket.recv raised %s", str(err))
            data = None
        logging.debug("Reading from %s: \n%s", self.host, repr(data))
        if data:
            nbytes = len(data)
            self.recv_buffer.append(data)
            self.recv_buffer_size += nbytes
        else:
            # TODO: this is typically a signal that the other end hung
            # up, we should implement the HTTP retry strategy for the
            # related request
            logging.debug("%s: closing connection after recv returned no "
                          "data on ready to read socket", self.host)
            self.close()
            return (True, False, False)
        # Now loop until we can't satisfy the response anymore (or the response
        # is done)
        while self.response is not None:
            recv_needs = self.response.recv_mode()
            if recv_needs is None:
                # We don't need any bytes at all, the response is done
                return (True, False, False)
            elif recv_needs == messages.Message.RECV_HEADERS:
                # scan for CRLF, consolidate first
                data = string.join(self.recv_buffer, '')
                pos = data.find(grammar.CRLF)
                if pos == 0:
                    # just a blank line, no headers
                    lines = [grammar.CRLF]
                    data = data[2:]
                elif pos > 0:
                    # we need CRLFCRLF actually
                    pos = data.find(grammar.CRLF + grammar.CRLF)
                    # pos can't be 0 now...
                if pos > 0:
                    # split the data into lines
                    lines = map(
                        lambda x: x + grammar.CRLF,
                        data[0:pos + 2].split(grammar.CRLF))
                    data = data[pos + 4:]
                elif err:
                    self.close(err)
                    return (True, False, False)
                elif pos < 0:
                    # We didn't find the data we wanted this time
                    break
                if data:
                    self.recv_buffer = [data]
                    self.recv_buffer_size = len(data)
                else:
                    self.recv_buffer = []
                    self.recv_buffer_size = 0
                if lines:
                    logging.debug("Response Headers: %s", repr(lines))
                    self.response.recv(lines)
            elif recv_needs == messages.Message.RECV_LINE:
                # scan for CRLF, consolidate first
                data = string.join(self.recv_buffer, '')
                pos = data.find(grammar.CRLF)
                if pos >= 0:
                    line = data[0:pos + 2]
                    data = data[pos + 2:]
                elif err:
                    self.close(err)
                    return (True, False, False)
                else:
                    # We didn't find the data we wanted this time
                    break
                if data:
                    self.recv_buffer = [data]
                    self.recv_buffer_size = len(data)
                else:
                    self.recv_buffer = []
                    self.recv_buffer_size = 0
                if line:
                    logging.debug("Response Header: %s", repr(line))
                    self.response.recv(line)
            elif recv_needs == 0:
                # we're blocked
                logging.debug("Response blocked on write")
                self.response.recv(None)
            else:
                nbytes = int(recv_needs)
                if nbytes < 0:
                    # As many as possible please
                    logging.debug("Response reading until connection closes")
                    if self.recv_buffer_size > 0:
                        bytes = string.join(self.recv_buffer, '')
                        self.recv_buffer = []
                        self.recv_buffer_size = 0
                    else:
                        # recv_buffer is empty but we still want more
                        break
                elif self.recv_buffer_size < nbytes:
                    logging.debug("Response waiting for %s bytes",
                                  str(nbytes - self.recv_buffer_size))
                    # We can't satisfy the response
                    break
                else:
                    got_bytes = 0
                    buff_pos = 0
                    while got_bytes < nbytes:
                        data = self.recv_buffer[buff_pos]
                        if got_bytes + len(data) < nbytes:
                            buff_pos += 1
                            got_bytes += len(data)
                            continue
                        elif got_bytes + len(data) == nbytes:
                            bytes = string.join(
                                self.recv_buffer[0:buff_pos + 1], '')
                            self.recv_buffer = self.recv_buffer[buff_pos + 1:]
                            break
                        else:
                            # Tricky case, only some of this string is needed
                            bytes = string.join(
                                self.recv_buffer[0:buff_pos] +
                                [data[0:nbytes - got_bytes]], '')
                            self.recv_buffer = (
                                [data[nbytes - got_bytes:]] +
                                self.recv_buffer[buff_pos + 1:])
                            break
                    self.recv_buffer_size = self.recv_buffer_size - len(bytes)
                logging.debug("Response Data: %s", repr(bytes))
                self.response.recv(bytes)
        return (False, False, False)

    def new_socket(self):
        with self.lock:
            if self.closed:
                logging.error(
                    "new_socket called on dead connection to %s", self.host)
                raise messages.HTTPException("Connection closed")
            self.socket = None
            self.socket_file = None
            self.socketSelect = select.select
        try:
            for target in self.manager.dnslookup(self.host, self.port):
                family, socktype, protocol, canonname, address = target
                try:
                    snew = socket.socket(family, socktype, protocol)
                    snew.connect(address)
                except IOError:
                    if snew:
                        snew.close()
                        snew = None
                    continue
                break
        except socket.gaierror, e:
            snew = None
            raise messages.HTTPException(
                "failed to connect to %s (%s)" % (self.host, e[1]))
        if not snew:
            raise messages.HTTPException("failed to connect to %s" % self.host)
        else:
            with self.lock:
                if self.closed:
                    # This connection has been killed
                    self._close_socket(snew)
                    logging.error(
                        "Connection killed while connecting to %s", self.host)
                    raise messages.HTTPException("Connection closed")
                else:
                    self.socket = snew
                    self.socket_file = self.socket.fileno()
                    self.socket.setblocking(False)
                    self.socketSelect = select.select

    def _close_socket(self, s):
        try:
            s.shutdown(socket.SHUT_RDWR)
        except IOError:
            # ignore errors, most likely the server has stopped listening
            pass
        try:
            s.close()
        except IOError:
            pass


class SecureConnection(Connection):

    def __init__(self, manager, scheme, hostname, port, ca_certs=None):
        super(SecureConnection, self).__init__(manager, scheme, hostname, port)
        self.ca_certs = ca_certs

    def new_socket(self):
        super(SecureConnection, self).new_socket()
        try:
            with self.lock:
                if self.socket is not None:
                    self.socket.setblocking(True)
                    socket_ssl = ssl.wrap_socket(
                        self.socket, ca_certs=self.ca_certs,
                        cert_reqs=ssl.CERT_REQUIRED if
                        self.ca_certs is not None else ssl.CERT_NONE)
                    # self.socket_ssl=socket.ssl(self.socket)
                    self.socketTransport = self.socket
                    self.socket.setblocking(False)
                    self.socket = socket_ssl
                    logging.info(
                        "Connected to %s with %s, %s, key length %i",
                        self.host, *self.socket.cipher())
        except IOError as e:
            logging.warn(str(e))
            raise messages.HTTPException(
                "failed to build secure connection to %s" % self.host)


class Client(PEP8Compatibility, object):

    """An HTTP client

    .. note::

        In Pyslet 0.4 and earlier the name HTTPRequestManager was used,
        this name is still available as an alias for Client.

    The object manages the sending and receiving of HTTP/1.1 requests
    and responses respectively.  There are a number of keyword arguments
    that can be used to set operational parameters:

    max_connections
        The maximum number of HTTP connections that may be open at any
        one time.  The method :py:meth:`queue_request` will block (or
        raise :py:class:`RequestManagerBusy`) if an attempt to queue a
        request would cause this limit to be exceeded.

    timeout
        The maximum wait time on the connection.  This is not the same
        as a limit on the total time to receive a request but a limit on
        the time the client will wait with no activity on the connection
        before assuming that the server is no longer responding.
        Defaults to None, no timeout.

    ca_certs
        The file name of a certificate file to use when checking SSL
        connections.  For more information see
        http://docs.python.org/2.7/library/ssl.html

        In practice, there seem to be serious limitations on SSL
        connections and certificate validation in Python distributions
        linked to earlier versions of the OpenSSL library (e.g., Python
        2.6 installed by default on OS X and Windows).

    .. warning::

        By default, ca_certs is optional and can be passed as None.  In
        this mode certificates will not be checked and your connections
        are not secure from man in the middle attacks.  In production
        use you should always specify a certificate file if you expect
        to use the object to make calls to https URLs.

    Although max_connections allows you to make multiple connections to
    the same host+port the request manager imposes an additional
    restriction. Each thread can make at most 1 connection to each
    host+port.  If multiple requests are made to the same host+port from
    the same thread then they are queued and will be sent to the server
    over the same connection using HTTP/1.1 pipelining. The manager
    (mostly) takes care of the following restriction imposed by RFC2616:

        Clients SHOULD NOT pipeline requests using non-idempotent
        methods or non-idempotent sequences of methods

    In other words, a POST  (or CONNECT) request will cause the
    pipeline to stall until all the responses have been received.  Users
    should beware of non-idempotent sequences as these are not
    automatically detected by the manager.  For example, a GET,PUT
    sequence on the same resource is not idempotent. Users should wait
    for the GET request to finish fetching the resource before queuing a
    PUT request that overwrites it.

    In summary, to take advantage of multiple simultaneous connections
    to the same host+port you must use multiple threads."""
    ConnectionClass = Connection
    SecureConnectionClass = SecureConnection

    def __init__(self, max_connections=100, ca_certs=None, timeout=None):
        PEP8Compatibility.__init__(self)
        self.managerLock = threading.Condition()
        # the id of the next connection object we'll create
        self.nextId = 1
        self.cActiveThreadTargets = {}
        # A dict of active connections keyed on thread and target (always
        # unique)
        self.cActiveThreads = {}
        # A dict of dicts of active connections keyed on thread id then
        # connection id
        self.cIdleTargets = {}
        # A dict of dicts of idle connections keyed on target and then
        # connection id
        self.cIdleList = {}
        # A dict of idle connections keyed on connection id (for keeping count)
        self.closing = False                    # True if we are closing
        # maximum number of connections to manage (set only on construction)
        self.max_connections = max_connections
        # maximum wait time on connections
        self.timeout = timeout
        # cached results from socket.getaddrinfo keyed on (hostname,port)
        self.dnsCache = {}
        self.ca_certs = ca_certs
        self.credentials = []
        self.socketSelect = select.select
        self.httpUserAgent = "%s (http.client.Client)" % str(USER_AGENT)
        """The default User-Agent string to use, defaults to a string
        derived from the installed version of Pyslet, e.g.::

            pyslet 0.5.20140727 (http.client.Client)"""

    def queue_request(self, request, timeout=None):
        """Starts processing an HTTP *request*

        request
            A :py:class:`messages.Request` object.

        timeout
            Number of seconds to wait for a free connection before
            timing out.  A timeout raises :py:class:`RequestManagerBusy`

            None means wait forever, 0 means don't block.

        The default implementation adds a User-Agent header from
        :py:attr:`httpUserAgent` if none has been specified already.
        You can override this method to add other headers appropriate
        for a specific context but you must pass this call on to this
        implementation for proper processing."""
        if self.httpUserAgent and not request.has_header('User-Agent'):
            request.set_header('User-Agent', self.httpUserAgent)
        # assign this request to a connection straight away
        start = time.time()
        thread_id = threading.current_thread().ident
        thread_target = (
            thread_id, request.scheme, request.hostname, request.port)
        target = (request.scheme, request.hostname, request.port)
        with self.managerLock:
            if self.closing:
                raise ConnectionClosed
            while True:
                # Step 1: search for an active connection to the same
                # target already bound to our thread
                if thread_target in self.cActiveThreadTargets:
                    connection = self.cActiveThreadTargets[thread_target]
                    break
                # Step 2: search for an idle connection to the same
                # target and bind it to our thread
                elif target in self.cIdleTargets:
                    cidle = self.cIdleTargets[target].values()
                    cidle.sort()
                    # take the youngest connection
                    connection = cidle[-1]
                    self._activate_connection(connection, thread_id)
                    break
                # Step 3: create a new connection
                elif (len(self.cActiveThreadTargets) + len(self.cIdleList) <
                      self.max_connections):
                    connection = self._new_connection(target)
                    self._activate_connection(connection, thread_id)
                    break
                # Step 4: delete the oldest idle connection and go round again
                elif len(self.cIdleList):
                    cidle = self.cIdleList.values()
                    cidle.sort()
                    connection = cidle[0]
                    self._delete_idle_connection(connection)
                # Step 5: wait for something to change
                else:
                    now = time.time()
                    if timeout == 0:
                        logging.warn(
                            "non-blocking call to queue_request failed to "
                            "obtain an HTTP connection")
                        raise RequestManagerBusy
                    elif timeout is not None and now > start + timeout:
                        logging.warn(
                            "queue_request timed out while waiting for "
                            "an HTTP connection")
                        raise RequestManagerBusy
                    logging.debug(
                        "queue_request forced to wait for an HTTP connection")
                    self.managerLock.wait(timeout)
                    logging.debug(
                        "queue_request resuming search for an HTTP connection")
            # add this request to the queue on the connection
            connection.queue_request(request)
            request.set_client(self)

    def active_count(self):
        """Returns the total number of active connections."""
        with self.managerLock:
            return len(self.cActiveThreadTargets)

    def thread_active_count(self):
        """Returns the total number of active connections associated
        with the current thread."""
        thread_id = threading.current_thread().ident
        with self.managerLock:
            return len(self.cActiveThreads.get(thread_id, {}))

    def _activate_connection(self, connection, thread_id):
        # safe if connection is new and not in the idle list
        connection.thread_id = thread_id
        target = connection.target_key()
        thread_target = connection.thread_target_key()
        with self.managerLock:
            self.cActiveThreadTargets[thread_target] = connection
            if thread_id in self.cActiveThreads:
                self.cActiveThreads[thread_id][connection.id] = connection
            else:
                self.cActiveThreads[thread_id] = {connection.id: connection}
            if connection.id in self.cIdleList:
                del self.cIdleList[connection.id]
                del self.cIdleTargets[target][connection.id]
                if not self.cIdleTargets[target]:
                    del self.cIdleTargets[target]

    def _deactivate_connection(self, connection):
        # called when connection goes idle, it is possible that this
        # connection has been killed and just doesn't know it (like
        # Bruce Willis in Sixth Sense) so we take care to return it
        # to the idle pool only if it was in the active pool
        target = connection.target_key()
        thread_target = connection.thread_target_key()
        with self.managerLock:
            if thread_target in self.cActiveThreadTargets:
                del self.cActiveThreadTargets[thread_target]
                self.cIdleList[connection.id] = connection
                if target in self.cIdleTargets:
                    self.cIdleTargets[target][connection.id] = connection
                else:
                    self.cIdleTargets[target] = {connection.id: connection}
                # tell any threads waiting for a connection
                self.managerLock.notify()
            if connection.thread_id in self.cActiveThreads:
                if connection.id in self.cActiveThreads[connection.thread_id]:
                    del self.cActiveThreads[
                        connection.thread_id][connection.id]
                if not self.cActiveThreads[connection.thread_id]:
                    del self.cActiveThreads[connection.thread_id]
            connection.thread_id = None

    def _delete_idle_connection(self, connection):
        if connection.id in self.cIdleList:
            target = connection.target_key()
            del self.cIdleList[connection.id]
            del self.cIdleTargets[target][connection.id]
            if not self.cIdleTargets[target]:
                del self.cIdleTargets[target]
            connection.close()

    def _nextid(self):
        #   Used internally to manage auto-incrementing connection ids
        with self.managerLock:
            id = self.nextId
            self.nextId += 1
        return id

    def _new_connection(self, target, timeout=None):
        #   Called by a connection pool when a new connection is required
        scheme, host, port = target
        if scheme == 'http':
            connection = self.ConnectionClass(self, scheme, host, port,
                                              timeout=self.timeout)
        elif scheme == 'https':
            connection = self.SecureConnectionClass(
                self, scheme, host, port, self.ca_certs)
        else:
            raise NotImplementedError(
                "Unsupported connection scheme: %s" % scheme)
        return connection

    def thread_task(self, timeout=None):
        """Processes all connections bound to the current thread then
        blocks for at most timeout (0 means don't block) while waiting
        to send/receive data from any active sockets.

        Each active connection receives one call to
        :py:meth:`Connection.connection_task` There are some situations
        where this method may still block even with timeout=0.  For
        example, DNS name resolution and SSL handshaking.  These may be
        improved in future.

        Returns True if at least one connection is active, otherwise
        returns False."""
        thread_id = threading.current_thread().ident
        with self.managerLock:
            connections = self.cActiveThreads.get(thread_id, {}).values()
        if not connections:
            return False
        readers = []
        writers = []
        wait_time = None
        for c in connections:
            try:
                r, w, tmax = c.connection_task()
                if wait_time is None or (tmax is not None and
                                         wait_time > tmax):
                    # shorten the timeout
                    wait_time = tmax
                if r:
                    readers.append(r)
                if w:
                    writers.append(w)
            except Exception as err:
                c.close(err)
                pass
        if readers or writers:
            if timeout is not None:
                if wait_time is not None:
                    if timeout < wait_time:
                        wait_time = timeout
            try:
                logging.debug("thread_task waiting for select: "
                              "readers=%s, writers=%s, timeout=%f",
                              repr(readers), repr(writers), timeout)
                r, w, e = self.socketSelect(readers, writers, [], wait_time)
            except select.error, err:
                logging.error("Socket error from select: %s", str(err))
        elif wait_time is not None:
            # not waiting for i/o, let time pass
            logging.debug("thread_task waiting to retry: %f", wait_time)
            time.sleep(wait_time)
        return True

    def thread_loop(self, timeout=60):
        """Repeatedly calls :py:meth:`thread_task` until it returns False."""
        while self.thread_task(timeout):
            continue
        # self.close()

    def process_request(self, request, timeout=60):
        """Process an :py:class:`messages.Message` object.

        The request is queued and then :py:meth:`thread_loop` is called
        to exhaust all HTTP activity initiated by the current thread."""
        self.queue_request(request, timeout)
        self.thread_loop(timeout)

    def idle_cleanup(self, max_inactive=15):
        """Cleans up any idle connections that have been inactive for
        more than *max_inactive* seconds."""
        clist = []
        now = time.time()
        with self.managerLock:
            for connection in self.cIdleList.values():
                if connection.last_active < now - max_inactive:
                    clist.append(connection)
                    del self.cIdleList[connection.id]
                    target = connection.target_key()
                    if target in self.cIdleTargets:
                        del self.cIdleTargets[target][connection.id]
                        if not self.cIdleTargets[target]:
                            del self.cIdleTargets[target]
        # now we can clean up these connections in a more leisurely fashion
        if clist:
            logging.debug("idle_cleanup closing connections...")
            for connection in clist:
                connection.close()

    def active_cleanup(self, max_inactive=90):
        """Clean up active connections that have been inactive for
        more than *max_inactive* seconds.

        This method can be called from any thread and can be used to
        remove connections that have been abandoned by their owning
        thread.  This can happen if the owning thread stops calling
        :py:meth:`thread_task` leaving some connections active.

        Inactive connections are killed using :py:meth:`Connection.kill`
        and then removed from the active list.  Should the owning thread
        wake up and attempt to finish processing the requests a socket
        error or :py:class:`messages.HTTPException` will be reported."""
        clist = []
        now = time.time()
        with self.managerLock:
            for thread_id in self.cActiveThreads:
                for connection in self.cActiveThreads[thread_id].values():
                    if connection.last_active < now - max_inactive:
                        # remove this connection from the active lists
                        del self.cActiveThreads[thread_id][connection.id]
                        del self.cActiveThreadTargets[
                            connection.thread_target_key()]
                        clist.append(connection)
            if clist:
                # if stuck threads were blocked waiting for a connection
                # then we can wake them up, one for each connection
                # killed
                self.managerLock.notify(len(clist))
        if clist:
            logging.debug("active_cleanup killing connections...")
            for connection in clist:
                connection.kill()

    def close(self):
        """Closes all connections and sets the manager to a state where
        new connections cannot not be created.

        Active connections are killed, idle connections are closed."""
        while True:
            with self.managerLock:
                self.closing = True
                if len(self.cActiveThreadTargets) + len(self.cIdleList) == 0:
                    break
            self.active_cleanup(0)
            self.idle_cleanup(0)

    def add_credentials(self, credentials):
        """Adds a :py:class:`pyslet.http.auth.Credentials` instance to
        this manager.

        Credentials are used in response to challenges received in HTTP
        401 responses."""
        with self.managerLock:
            self.credentials.append(credentials)

    def remove_credentials(self, credentials):
        """Removes credentials from this manager.

        credentials
            A :py:class:`pyslet.http.auth.Credentials` instance
            previously added with :py:meth:`add_credentials`.

        If the credentials can't be found then they are silently ignored
        as it is possible that two threads may independently call the
        method with the same credentials."""
        with self.managerLock:
            for i in xrange(len(self.credentials)):
                if self.credentials[i] is credentials:
                    del self.credentials[i]

    def dnslookup(self, host, port):
        """Given a host name (string) and a port number performs a DNS lookup
        using the native socket.getaddrinfo function.  The resulting value is
        added to an internal dns cache so that subsequent calls for the same
        host name and port do not use the network unnecessarily.

        If you want to flush the cache you must do so manually using
        :py:meth:`flush_dns`."""
        with self.managerLock:
            result = self.dnsCache.get((host, port), None)
        if result is None:
            # do not hold the lock while we do the DNS lookup, this may
            # result in multiple overlapping DNS requests but this is
            # better than a complete block.
            logging.debug("Looking up %s", host)
            result = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
            with self.managerLock:
                # blindly populate the cache
                self.dnsCache[(host, port)] = result
        return result

    def flush_dns(self):
        """Flushes the DNS cache."""
        with self.managerLock:
            self.dnsCache = {}

    def find_credentials(self, challenge):
        """Searches for credentials that match *challenge*"""
        logging.debug("Client searching for credentials in "
                      "%s with challenge %s",
                      challenge.protectionSpace, str(challenge))
        with self.managerLock:
            for c in self.credentials:
                if c.match_challenge(challenge):
                    return c

    def find_credentials_by_url(self, url):
        """Searches for credentials that match *url*"""
        with self.managerLock:
            for c in self.credentials:
                if c.test_url(url):
                    return c


HTTPRequestManager = Client


class ClientRequest(messages.Request):

    """Represents an HTTP request.

    To make an HTTP request, create an instance of this class and then
    pass it to an :py:class:`Client` instance using either
    :py:meth:`Client.queue_request` or
    :py:meth:`Client.process_request`.

    url
        An absolute URI using either http or https schemes.  A
        :py:class:`pyslet.rfc2396.URI` instance or an object that can be
        passed to its constructor.

    And the following keyword arguments:

    method
        A string.  The HTTP method to use, defaults to "GET"

    entity_body
        A string or stream-like object containing the request body.
        Defaults to None meaning no message body.  For stream-like
        objects the tell and seek methods must be supported to enable
        resending the request if required.

    res_body
        A stream-like object to write data to.  Defaults to None, in
        which case the response body is returned as a string the
        :py:attr:`res_body`.

    protocol
        An :py:class:`params.HTTPVersion` object, defaults to
        HTTPVersion(1,1)

    autoredirect
        Whether or not the request will follow redirects, defaults to
        True.

    max_retries
        The maximum number of times to attempt to resend the request
        following an error on the connection or an unexpected hang-up.
        Defaults to 3, you should not use a value lower than 1 because,
        when pipelining, it is always possible that the server has
        gracefully closed the socket and we won't notice until we've
        sent the request and get 0 bytes back on recv.  Although
        'normal' this scenario counts as a retry."""

    def __init__(self, url, method="GET", res_body=None,
                 protocol=params.HTTP_1p1, auto_redirect=True,
                 max_retries=3, min_retry_time=5, **kwargs):
        super(ClientRequest, self).__init__(**kwargs)
        #: the :py:class:`Client` object that is managing us
        self.manager = None
        #: the :py:class:`Connection` object that is currently sending us
        self.connection = None
        # private member used to determine if we've been sent
        self._send_pos = 0
        #: the status code received, 0 indicates a failed or unsent request
        self.status = 0
        #: If status == 0, the error raised during processing
        self.error = None
        #: the scheme of the request (http or https)
        self.scheme = None
        #: the hostname of the origin server
        self.hostname = None
        #: the port on the origin server
        self.port = None
        #: the full URL of the requested resource
        self.url = None
        self.set_url(url)
        # copy over the keyword arguments
        self.method = method
        if type(protocol) in types.StringTypes:
            self.protocol = params.HTTPVersion.from_str(protocol)
        elif isinstance(protocol, params.HTTPVersion):
            self.protocol = protocol
        else:
            raise TypeError("illegal value for protocol")
        #: the response body received (only used if not streaming)
        self.res_body = ''
        if res_body is not None:
            # assume that the res_body is a stream like object
            self.res_bodystream = res_body
        else:
            self.res_bodystream = None
        #: whether or not auto redirection is in force for 3xx responses
        self.auto_redirect = auto_redirect
        #: the maximum number of retries we'll attempt
        self.max_retries = max_retries
        #: the number of retries we've had
        self.nretries = 0
        self.retry_time = 0
        self._rt1 = 0
        self._rt2 = min_retry_time
        #: the associated :py:class:`ClientResponse`
        self.response = ClientResponse(request=self)
        # the credentials we're using in this request, this attribute is
        # used when we are responding to a 401 and the managing Client
        # has credentials that meet the challenge received in the
        # response.  We keep track of them here to avoid constantly
        # looping with the same broken credentials. to set the
        # Authorization header and
        self.tried_credentials = None

    def set_url(self, url):
        """Sets the URL for this request

        This method sets the Host header and the following local
        attributes:
        :py:attr:`scheme`, :py:attr:`hostname`, :py:attr:`port` and
        :py:attr:`request_uri`."""
        with self.lock:
            if not isinstance(url, uri.URI):
                url = uri.URIFactory.URI(url)
            self.url = url
            if self.url.userinfo:
                raise NotImplementedError(
                    "username(:password) in URL not yet supported")
            if self.url.absPath:
                self.request_uri = self.url.absPath
            else:
                self.request_uri = "/"
            if self.url.query is not None:
                self.request_uri = self.request_uri + '?' + self.url.query
            if not isinstance(self.url, params.HTTPURL):
                raise messages.HTTPException(
                    "Scheme not supported: %s" % self.url.scheme)
            elif isinstance(self.url, params.HTTPSURL):
                self.scheme = 'https'
            else:
                self.scheme = 'http'
            self.hostname = self.url.host
            custom_port = False
            if self.url.port:
                # custom port, perhaps
                self.port = int(self.url.port)
                if self.port != self.url.DEFAULT_PORT:
                    custom_port = True
            else:
                self.port = self.url.DEFAULT_PORT
            # The Host request-header field (section 14.23) MUST
            # accompany all HTTP/1.1 requests.
            if self.hostname:
                if not custom_port:
                    self.set_host(self.hostname)
                else:
                    self.set_host("%s:%i" % (self.hostname, self.port))
            else:
                raise messages.HTTPException("No host in request URL")

    def can_retry(self):
        """Returns True if we reconnect and retry this request"""
        if self.nretries > self.max_retries:
            logging.error("%s retry limit exceeded", self.get_start())
            return False
        else:
            return True

    def resend(self, url=None):
        logging.info("Resending request to: %s", str(url))
        self.status = 0
        self.error = None
        if url is not None:
            self.set_url(url)
        self.manager.queue_request(self)

    def set_client(self, client):
        """Called when we are queued for processing.

        client
            an :py:class:`Client` instance"""
        self.manager = client

    def connect(self, connection, send_pos):
        """Called when we are assigned to an HTTPConnection"

        connection
            A :py:class:`Connection` object

        send_pos
            The position of the sent bytes pointer after which this
            request has been (or at least has started to be) sent."""
        self.connection = connection
        self._send_pos = send_pos

    def disconnect(self, send_pos):
        """Called when the connection has finished sending us

        This may be before or after the response is received and
        handled!

        send_pos
            The number of bytes sent on this connection before the
            disconnect.  This value is compared with the value passed to
            :py:meth:`connect` to determine if the request was actually
            sent to the server or abandoned without a byte being sent.

            For idempotent methods we lose a life every time.  For
            non-idempotent methods (e.g., POST) we do the same except
            that if we been (at least partially) sent then we lose all
            lives to prevent "indeterminate results"."""
        self.nretries += 1
        if self.is_idempotent() or send_pos <= self._send_pos:
            self.retry_time = (time.time() +
                               self._rt1 * (5 - 2 * random.random()) / 4)
            rtnext = self._rt1 + self._rt2
            self._rt2 = self._rt1
            self._rt1 = rtnext
        else:
            self.max_retries = 0
        self.connection = None
        if self.status > 0:
            # The response has finished
            self.finished()

    def send_header(self):
        # Check authorization and add credentials if the manager has them
        if not self.has_header("Authorization"):
            credentials = self.manager.find_credentials_by_url(self.url)
            if credentials:
                self.set_authorization(credentials)
        return super(ClientRequest, self).send_header()

    def response_finished(self, err=None):
        # called when the response has been received
        self.status = self.response.status
        self.error = err
        if self.status is None:
            logging.error("Error receiving response, %s", str(self.error))
            self.status = 0
            self.finished()
        else:
            logging.info("Finished Response, status %i", self.status)
            if self.res_bodystream:
                self.res_bodystream.flush()
            else:
                self.res_body = self.response.entity_body.getvalue()
            if self.response.status >= 100 and self.response.status <= 199:
                """Received after a 100 continue or other 1xx status
                response, we may be waiting for the connection to call
                our send_body method.  We need to tell it not to
                wait any more!"""
                if self.connection:
                    self.connection.continue_sending(self)
                # We're not finished though, wait for the final response
                # to be sent. No need to reset as the 100 response
                # should not have a body
            elif self.connection:
                # The response was received before the connection
                # finished with us
                if self.status >= 300:
                    # Some type of error condition....
                    if isinstance(self.send_body(), str):
                        # There was more data to send in the request but we
                        # don't plan to send it so we have to hang up!
                        self.connection.request_disconnect()
                    # else, we were finished anyway... the connection will
                    # discover this itself
                elif self.response >= 200:
                    # For 2xx result codes we let the connection finish
                    # spooling and disconnect from us when it is done
                    pass
                else:
                    # A bad information response (with body) or a bad status
                    # code
                    self.connection.request_disconnect()
            else:
                # The request is already disconnected, we're done
                self.finished()

    def finished(self):
        """Called when we have a final response *and* have disconnected
        from the connection There is no guarantee that the server got
        all of our data, it might even have returned a 2xx series code
        and then hung up before reading the data, maybe it already had
        what it needed, maybe it thinks a 2xx response is more likely to
        make us go away.  Whatever.  The point is that you can't be sure
        that all the data was transmitted just because you got here and
        the server says everything is OK"""
        if self.tried_credentials is not None:
            # we were trying out some credentials, if this is not a 401 assume
            # they're good
            if self.status == 401:
                # we must remove these credentials, they matched the challenge
                # but still resulted in 401
                self.manager.remove_credentials(self.tried_credentials)
            else:
                if isinstance(self.tried_credentials, auth.BasicCredentials):
                    # path rule only works for BasicCredentials
                    self.tried_credentials.add_success_path(self.url.absPath)
            self.tried_credentials = None
        if (self.auto_redirect and self.status >= 300 and
                self.status <= 399 and
                (self.status != 302 or
                 self.method.upper() in ("GET", "HEAD"))):
            # If the 302 status code is received in response to a
            # request other than GET or HEAD, the user agent MUST NOT
            # automatically redirect the request unless it can be
            # confirmed by the user
            location = self.response.get_header("Location").strip()
            if location:
                url = uri.URIFactory.URI(location)
                if not url.host:
                    # This is an error but a common one (thanks IIS!)
                    location = location.Resolve(self.url)
                self.resend(location)
        elif self.status == 401:
            challenges = self.response.get_www_authenticate()
            for c in challenges:
                c.protectionSpace = self.url.GetCanonicalRoot()
                self.tried_credentials = self.manager.find_credentials(c)
                if self.tried_credentials:
                    self.set_authorization(self.tried_credentials)
                    self.resend()  # to the same URL


class ClientResponse(messages.Response):

    def __init__(self, request, **kwargs):
        super(ClientResponse, self).__init__(
            request=request, entity_body=request.res_bodystream, **kwargs)

    def handle_headers(self):
        """Hook for response header processing.

        This method is called when a set of response headers has been
        received from the server, before the associated data is
        received!  After this call, recv will be called zero or more
        times until handle_message or handle_disconnect is called
        indicating the end of the response.

        Override this method, for example, if you want to reject or
        invoke special processing for certain responses (e.g., based on
        size) before the data itself is received.  To abort the
        response, close the connection using
        :py:meth:`Connection.request_disconnect`.

        Override the :py:meth:`Finished` method instead to clean up and
        process the complete response normally."""
        logging.debug(
            "Request: %s %s %s", self.request.method, self.request.url,
            str(self.request.protocol))
        logging.debug(
            "Got Response: %i %s", self.status, self.reason)
        logging.debug("Response headers: %s", repr(self.headers))
        super(ClientResponse, self).handle_headers()

    def handle_message(self):
        """Hook for normal completion of response"""
        self.finished()
        super(ClientResponse, self).handle_message()

    def handle_disconnect(self, err):
        """Hook for abnormal completion of the response

        Called when the server disconnects before we've completed
        reading the response.  Note that if we are reading forever this
        may be expected behaviour and *err* may be None.

        We pass this information on to the request."""
        if err is not None:
            self.reason = str(err)
        self.request.response_finished(err)

    def finished(self):
        self.request.response_finished()
        if self.status >= 100 and self.status <= 199:
            # Re-read this response, we're not done!
            self.start_receiving()
