#! /usr/bin/env python

from pyslet.py26 import *       # noqa

import io
import os
import errno
import threading
import time
import logging
import SocketServer
import Queue
import select
import socket
import ssl
import string

import pyslet.rfc2396 as uri

import pyslet.http.grammar as grammar
import pyslet.http.messages as messages
import pyslet.http.params as params


#: For useful information on HTTP header size limits see:
# : http://stackoverflow.com/questions/1097651/is-there-a-practical-http-header-length-limit     # noqa
#: we match Apache's value by default
MAX_HEADER_LINE = 8190

#: we match Apache's value by default
MAX_HEADER_SIZE = 2 * MAX_HEADER_LINE


class UnresponsiveScript(messages.HTTPException):
    pass


def cascading_wait(timeout, *events):
    wait_event = threading.Event()
    for e in events:
        e.cascade_to(wait_event)
    wait_event.wait(timeout)


class CascadingEvent(threading._Event):

    def __init__(self):
        super(CascadingEvent, self).__init__()
        self.cascade = None

    def cascade_to(self, e):
        """Instructs this event to cascade to e"""
        self.cascade = e
        # at this point, set will cascade, but if we
        # were set before we need to cascade now
        if self.is_set():
            e.set()

    def set(self):
        super(CascadingEvent, self).set()
        e = self.cascade
        if e is not None:
            e.set()


def split_socket(s, buffstr='', timeout=None,
                 maxline=MAX_HEADER_LINE,
                 maxlines=MAX_HEADER_SIZE):
    """Function to help reading from non-blocking sockets.

    s
        A socket object

    buffstr
        An optional string object containing buffered data returned
        from a previous call.

    timeout
        The length of time in seconds to wait for data on the
        socket. None indicates wait forever.

    maxline
        The maximum number of bytes to allow in a single header
        line, defaults to :py:data:`MAX_HEADER_LINE`.  Lines that
        exceed this value raise an :py:class:`HTTPException`.

    maxlines
        The maximum number of bytes to allow for all lines combined,
        defaults to :py:data:`MAX_HEADER_SIZE`.  Lines that exceed
        this total raise an :py:class:`HTTPException`.

    Returns a tuple of two items.  The first item is a list of
    line-strings read from the socket.  Each line string is
    terminated by CRLF, the last string in the list is a blank line
    consisting of CRLF only.  Therefore, the list is always
    non-empty on a successful return.

    The second item is any extra data read from the socket after the
    blank line.  It is always a string, but may be empty."""
    buffer = bytearray(buffstr)
    rpos = 0
    lines = []
    while True:
        # scan up to the next CRLF in buffer
        try:
            end = buffer.index(grammar.CRLF, rpos)
            line = str(buffer[rpos:end + 2])
            if len(line) > maxline:
                raise messages.HTTPException(
                    "max line length exceeded: %s..." + line[0:64])
            lines.append(line)
            rpos = end + 2
            if line == grammar.CRLF:
                # that was the last line
                return lines, str(buffer[rpos:])
            else:
                # read another line
                continue
        except ValueError:
            # not found, fill the buffer with data
            pass
        if len(buffer) >= maxlines:
            raise messages.HTTPException("max header length exceeded")
        data = read_socket(s, maxlines - len(buffer), timeout=timeout)
        if not data:
            raise messages.ProtocolError("Unexpected end of message")
        buffer = buffer + data


def split_socket1(s, buffstr='', timeout=None, maxline=MAX_HEADER_LINE):
    """Function to help reading from non-blocking sockets.

    s
        A socket object

    buffstr
        An optional string object containing buffered data returned
        from a previous call.

    timeout
        The length of time in seconds to wait for data on the
        socket. None indicates wait forever.

    maxline
        The maximum number of bytes to allow in a single header
        line, defaults to :py:data:`MAX_HEADER_LINE`.  Lines that
        exceed this value raise an :py:class:`HTTPException`.

    Returns a tuple of two items.  The first item is a string
    terminating in CRLF, the second item is any extra data read from the
    socket after the blank line.  It is always a string, but may be
    empty.

    If the other end of the socket has closed before a line was sent
    then the first item is None and the second is any data read from the
    socket before it was closed."""
    buffer = bytearray(buffstr)
    rpos = 0
    while True:
        # scan up to the next CRLF in buffer
        try:
            end = buffer.index(grammar.CRLF, rpos)
            line = str(buffer[rpos:end + 2])
            rpos = end + 2
            return line, str(buffer[rpos:])
        except ValueError:
            # not found, fill the buffer with data
            pass
        if len(buffer) >= maxline:
            raise HTTPException("max line length exceeded: %s..." +
                                buffer[0:64])
        data = read_socket(s, maxline - len(buffer), timeout=timeout)
        if not data:
            return None, str(buffer)
        buffer = buffer + data


def read_socket(s, nbytes, timeout=None):
    """Function to help reading from non-blocking sockets.

    s
        A socket object

    nbytes
        The maximum number of bytes to read.  The function will block
        attempting to read from the socket unless at least 1 byte is
        returned.

    timeout
        The length of time in seconds to wait for data on the
        socket. None indicates wait forever.

    This method has three outcomes, a data string is returned, None is
    returned (client hung up) or an IOError is raised indicating a
    timeout."""
    try:
        r, w, e = select.select([s], [], [], timeout)
        if not r:
            logging.info("socket timeout on recv")
            raise IOError(errno.ETIMEDOUT, os.strerror(errno.ETIMEDOUT),
                          "select in pyslet.http.messages.read_socket")
    except select.error as err:
        logging.error("Socket error from select: %s", str(err))
        raise IOError(err.args[0], err.args[1])
    try:
        data = s.recv(nbytes)
        # if data is empty the other end has hung up
        if data == '' and nbytes > 0:
            return None
        return data
    except socket.error:
        # error raised on recv ready socket indicates a hang-up
        # typically: i.e., no more data to come
        logging.info("Error raised on recv ready socket")
        return None


def write_socket(s, data, timeout=None):
    """Function to help writing to a non-blocking socket

    s
        A socket object

    data
        The data to write.  The function will block attempting to write
        to the socket until all the data has been written or an error is
        raised.

    timeout
        The length of time in seconds to wait for the socket to be ready
        to write.  None indicates wait forever."""
    while data:
        try:
            r, w, e = select.select([], [s], [], timeout)
            if not w:
                logging.info("socket timeout on send")
                raise IOError(errno.ETIMEDOUT, os.strerror(errno.ETIMEDOUT),
                              "select in pyslet.http.messages.write_socket")
        except select.error as err:
            logging.error("Socket error from select: %s", str(err))
            raise IOError(err.args[0], err.args[1])
        try:
            nbytes = s.send(data)
            if nbytes:
                if nbytes < len(data):
                    data = data[nbytes:]
                else:
                    data = None
            else:
                # socket was ready to write but didn't accept any data
                # more typically represented by socket.error caught below
                logging.info("Send failed on send-ready socket")
                raise IOError(errno.EPIPE, os.strerror(errno.EPIPE))
        except socket.error:
            # error raised on recv ready socket indicates a hang-up
            # typically: i.e., no more data to come
            logging.info("Error raised on send-ready socket")
            return None


class Connection(SocketServer.BaseRequestHandler):

    def handle(self):
        self.server.handle_connection(self)

    def begin(self):
        # a FIFO queue of responses
        self.request.setblocking(False)
        self.responseq = Queue.Queue()
        self.finished = threading.Event()

    def handle_requests(self):
        # these pipes are for the entity body, not the message body! in
        # otherwords, they deal with data after transfer encodings have
        # been removed
        try:
            while not self.finished.is_set():
                logging.debug("handle_request: reading request...")
                request = ServerRequest(self)
                rflag = CascadingEvent()
                request.recv_pipe.set_rflag(rflag)
                request.start_receiving()
                buffstr = ''
                timeout = self.server.idle_timeout
                send_continue = False
                send_continue_start = 0
                try:
                    while True:
                        mode = request.recv_mode()
                        if mode is None or request.aborted.is_set():
                            # the request is complete, simulate EOF on
                            # the recv_pipe to ensure that any read()
                            # call in the application terminates and
                            # doesn't just hang
                            logging.debug("%s : request complete",
                                          request.get_start())
                            request.recv_pipe.write_eof()
                            break
                        if send_continue:
                            if not rflag.is_set():
                                twait = (self.server.app_timeout -
                                         (time.time() - send_continue_start))
                                if twait < 0:
                                    # application timeout
                                    raise UnresponsiveScript(
                                        "timed out waiting to consume "
                                        "input data")
                                else:
                                    # wait for a reader before continuing
                                    cascading_wait(
                                        twait, rflag, request.aborted)
                                    continue
                            else:
                                # script is read blocked, send 100-Continue
                                request.response.send_continue.set()
                            send_continue = False
                        if mode == request.RECV_HEADERS:
                            headers, buffstr = split_socket(
                                self.request, buffstr, timeout=timeout)
                            request.recv(headers)
                            # at this point we should have a response
                            if request.get_expect_continue():
                                send_continue = True
                                send_continue_start = time.time()
                        elif mode == request.RECV_LINE:
                            # we need to read a line from the input stream
                            line, buffstr = split_socket1(
                                self.request, buffstr, timeout=timeout)
                            if line is None:
                                # hang up
                                if request.method:
                                    raise ProtocolError("Unexpected EOM")
                                else:
                                    # client hung up
                                    logging.debug("client hang up detected")
                                    self.finished.set()
                                    break
                            else:
                                request.recv(line)
                        elif mode > 0:
                            # we need to read some data from the socket
                            if len(buffstr) > mode:
                                data = buffstr[:mode]
                                buffstr = buffstr[mode:]
                                request.recv(data)
                            elif buffstr:
                                request.recv(buffstr)
                                buffstr = ''
                            else:
                                # read some data from the socket
                                data = read_socket(self.request, mode,
                                                   timeout=timeout)
                                if data is None:
                                    # client hang up when we expected
                                    # more data
                                    raise ProtocolError(
                                        "Unexpected EOM in data")
                                request.recv(data)
                        elif mode == request.RECV_ALL:
                            # unlimited read from the socket
                            if buffstr:
                                request.recv(buffstr)
                                buffstr = ''
                            else:
                                data = read_socket(self.request,
                                                   io.DEFAULT_BUFFER_SIZE,
                                                   timeout=timeout)
                                request.recv(data)
                                if not data:
                                    self.finished.set()
                        elif mode == 0:
                            # the request is write blocked, it doesn't
                            # want any data, it just wants time to
                            # digest what it has already.  Typically we
                            # get here when a POST or similar method is
                            # waiting for the script to read the last
                            # bit of the data.  It makes sense to wait
                            # for the script to finish processing which
                            # means waiting for a read on the recv_pipe
                            if rflag.is_set():
                                rflag.clear()
                                # next time around we'll wait for it
                            else:
                                logging.debug(
                                    "handle_request: recv_pipe blocked, "
                                    "waiting for app")
                                cascading_wait(self.server.app_timeout,
                                               rflag, request.aborted)
                                if not rflag.is_set():
                                    raise UnresponsiveScript(
                                        "timed out waiting for app to consume "
                                        "input data")
                            # give time to the message
                            request.recv(None)
                            pass
                        # once we're reading a request, switch to a longer
                        # timeout to prevent unexpected hang-ups
                        timeout = self.server.connection_timeout
                except messages.ProtocolError as e:
                    # log this error as a warning
                    # push a suitable response and then
                    # hang up, no good will come of this connection
                    response = ServerResponse(request=request,
                                              protocol=self.server.protocol)
                    self.responseq.put(response)
                    response.set_status(400)
                    response.clear_keep_alive()
                    txt = str(e)
                    response.set_content_type(params.PLAIN_TEXT)
                    response.set_content_length(len(txt))
                    response.write_response(txt)
                    self.finished.set()
                except NotImplementedError as e:
                    response = ServerResponse(request=request,
                                              protocol=self.server.protocol)
                    self.responseq.put(response)
                    response.set_status(501)
                    response.clear_keep_alive()
                    txt = str(e)
                    response.set_content_type(params.PLAIN_TEXT)
                    response.set_content_length(len(txt))
                    response.write_response(txt)
                    self.finished.set()
                except IOError as e:
                    if request.method:
                        logging.warn("Unexpected EOM: %s; %s",
                                     request.get_start(), str(e))
                    else:
                        # client may have hung up
                        logging.debug("timed out waiting for request")
                    request.clear_keep_alive()
                    self.finished.set()
                except Exception as e:
                    # log this error as an internal server error push a
                    # suitable 500 response and then hang up because
                    # we've messed up
                    response = ServerResponse(request=request,
                                              protocol=self.server.protocol)
                    self.responseq.put(response)
                    response.set_status(500)
                    response.clear_keep_alive()
                    txt = str(e)
                    logging.error("%s: %s", response.request.get_start(), txt)
                    response.set_content_type(params.PLAIN_TEXT)
                    response.set_content_length(len(txt))
                    response.write_response(txt)
                    self.finished.set()
                # we've finished reading the message, close the recv_pipe
                # to help clean things up quickly
                request.recv_pipe.close()
                if not request.keep_alive or request.response is None:
                    # the request wants us to close the connection or
                    # the client has hung up (or something has gone
                    # badly wrong)
                    break
                # wait for the response to be ready to send before
                # pipe-lining the next request in case it wants to
                # hang up the connection.
                logging.debug("handle_request: waiting for response...")
                request.response.ready_to_send.wait(self.server.app_timeout)
                if not request.response.keep_alive:
                    # the response is terminating the connection
                    break
                # request and response happy to keep the connection open
                continue
        except IOError:
            # socket may have timed-out while reading or waiting for a
            # request
            pass
        # add a dummy response to kill the handle_responses thread
        logging.debug("handle_request: terminating connection...")
        self.responseq.put(None)

    def handle_response(self, response):
        self.responseq.put(response)

    def handle_responses(self):
        # pull items from the responseq until we get None
        timeout = (self.server.connection_timeout +
                   self.server.app_timeout)
        try:
            keep_alive = True
            while keep_alive:
                logging.debug("handle_responses: waiting for responseq...")
                response = self.responseq.get(True, timeout)
                if response is None:
                    break
                # handle the response
                logging.debug("Waiting for response...")
                # triggered by a call to response.start_sending()
                # or the need for a 100-Continue
                cascading_wait(self.server.app_timeout,
                               response.ready_to_send,
                               response.send_continue)
                if response.request.get_expect_continue():
                    # ignore the semaphore, its purpose was purely
                    # to wake us up early
                    if (not response.ready_to_send.is_set() or
                            response.status is None or
                            (response.status >= 200 and
                             response.status < 400)):
                        logging.info("Sending response: %s %s",
                                     str(response.protocol), "100 Continue")
                        # Fake this response, as the app may already be
                        # setting the status, headers etc...
                        data = "%s %s\r\n\r\n" % (str(response.protocol),
                                                  "100 Continue")
                        write_socket(self.request, data,
                                     self.server.connection_timeout)
                        # now wait again until we're actually ready to send
                        response.ready_to_send.wait(self.server.app_timeout)
                    else:
                        # ready to send and status does not indicate
                        # success send a final code, abort reading the
                        # data and hang up the connection
                        if response.keep_alive:
                            # we missed this opportunity before
                            response.clear_keep_alive()
                            response.set_connection(["close"])
                        response.request.aborted.set()
                if not response.ready_to_send.is_set():
                    # script timeout: generate a 500 error then kill
                    # this connection
                    response.set_status(500)
                    response.clear_keep_alive()
                    # we can't risk writing data as a race condition
                    # could leave us dead-locked waiting for the loop
                    # below (that clears the response Pipe)
                    logging.error("%s: Application timeout",
                                  response.request.get_start())
                    response.set_content_length(0)
                    response.write_response('')
                logging.debug("...sending response")
                # send the response
                keep_alive = response.keep_alive
                data = response.send_start()
                write_socket(self.request, data,
                             self.server.connection_timeout)
                # now read the headers and the rest of the message
                data = response.send_header()
                write_socket(self.request, data,
                             self.server.connection_timeout)
                # now loop round reading the data
                while True:
                    data = response.send_body()
                    if data is None:
                        # we're read blocked, wait for the response's
                        # pipe to be readable
                        response.send_pipe.read_wait(
                            timeout=self.server.app_timeout)
                    elif data:
                        write_socket(self.request, data,
                                     self.server.connection_timeout)
                    else:
                        # end of body, close the response pipe
                        response.close()
                        break
        except Queue.Empty:
            # timeout waiting for a response object
            logging.error("HTTPServer: responseq timeout "
                          "(may indicate a stuck connection)")
        self.finished.set()
        logging.debug("handle_responses: done")

    def end(self):
        pass

    def service_unavailable(self):
        # return a 503 response
        write_socket(self.request,
                     "HTTP/1.1 503 Service Unavailable\r\n"
                     "Connection: close\r\n"
                     "\r\n",
                     self.server.connection_timeout)


class Server(SocketServer.ThreadingMixIn, SocketServer.TCPServer):

    """HTTP Server

    The purpose of this class is to provide a simple environment for
    testing and customising specialist aspects of HTTP handling.

    port
        The port on which to listen for connections

    max_connections
        The maximum number of connections to process at any one time.
        Connections are placed in a queue and processed using a round
        robin algorithm by a separate thread.  None, the default, means
        unlimited.

    app
        A wsgi callable that will handle requests

    protocol
        A :py:class:`params.HTTPVersion` instance representing the
        protocol implemented by the server.  The default is HTTP/1.1, if
        you specify :py:data:`params.HTTP_1p0` the server will behave
        more like an HTTP/1.0 server, reporting that version in
        responses.  It also suppresses the use of chunked encoding and
        persistent connections.

    authorities
        A list of strings representing the authorities for which we are
        serving.  The first authority in the list is considered the
        default authority and it will be used in cases where the request
        does not provide a host header (or absolute URI).  If the list
        is empty or missing (the default) then the default authority is
        set by adding the port number to the string "localhost:".  Use
        multiple names to enable the server to recognise other
        authorities, any unrecognized authority received in a request
        will return a 400 bad request message.

        The default authority is also used to determine the host string
        passed to the underlying system for binding the server.  The
        port given in the authority string is ignored when binding but
        in most cases it should correspond to the port passed as the
        first parmeter!

    keyfile, certfile
        Optional paths to an SSL key and certificate file.  If given the
        server is an https server.  For an explanation of these
        arguments see the builtin Python ssl.wrap_socket function to
        which they are passed."""
    #: overridden to allow our server to restart even if there are
    #: existing connections from a previous invocation.
    allow_reuse_address = True

    def __init__(self, port, max_connections=None, app=None,
                 protocol=params.HTTP_1p1, authorities=None,
                 keyfile=None, certfile=None):
        #: a dictionary mapping authority onto the WSGI callable that
        #: handles it
        self.authorities = {}
        if not authorities:
            #: the HOST we are bound to
            authorities = ["localhost" if port == params.HTTPURL.DEFAULT_PORT
                           else "localhost:%i" % port]
        #: the default authority
        self.default_authority = authorities[0].lower()
        self.host = uri.split_server(self.default_authority)[1]
        for a in authorities:
            self.authorities[a.lower()] = app
        #: the port we are bound to
        self.port = port
        #: whether or not we are serving using https
        self.https = False
        SocketServer.TCPServer.__init__(
            self, (self.host, self.port), Connection)
        if keyfile is not None:
            # This must be an HTTPS server
            self.socket = ssl.wrap_socket(
                self.socket, keyfile=keyfile, certfile=certfile,
                server_side=True, do_handshake_on_connect=True)
            self.https = True
        #: the protocol semantics we use for handling requests
        self.protocol = protocol
        self.lock = threading.RLock()
        self.con_count = 0
        self.con_max = max_connections
        self.nconnections = 0
        self.connections = {}
        #: seconds before a network recv/send times out
        self.connection_timeout = 10
        #: seconds before a working request handler is abandoned
        self.app_timeout = 10
        #: seconds before an idle connection is closed
        self.idle_timeout = 5
        #: a pipe for writing error strings
        self.error_pipe = Pipe(rblocking=False, timeout=self.app_timeout,
                               name="http.Server.error_pipe")

    def handle_connection(self, connection):
        # add this connection to the queue
        with self.lock:
            if (self.con_max is not None and
                    len(self.connections) > self.con_max):
                # refuse this connection, we're too busy
                connection.id = 0
            else:
                self.con_count += 1
                connection.id = self.con_count
                self.connections[connection.id] = connection
        if connection.id:
            connection.begin()
            t = threading.Thread(target=connection.handle_responses)
            t.start()
            connection.handle_requests()
            # now when we are done handling requests we just wait
            # for the responses thread to finish
            t.join()
            # end of this connection
            connection.end()
            self.stop_connection(connection)
        else:
            connection.service_unavailable()

    def stop_connection(self, connection):
        with self.lock:
            if connection.id and connection.id in self.connections:
                del self.connections[connection.id]

    def launch_app(self, environ, start_response):
        """Launches a WSGI application

        The default implementation returns a 404 error"""
        with self.lock:
            authority = environ.get('HTTP_HOST', self.default_authority)
            try:
                app = self.authorities[authority]
                if app is None:
                    # this implementation mainly for testing, we want to read
                    # all the data from the input string
                    response_headers = []
                    start_response("404 Page Not Found", response_headers)
                    return []
                else:
                    return app(environ, start_response)
            except KeyError:
                # bad host in request
                start_response("400 Bad Request", [])
                return []


class ServerRequest(messages.Request):

    def __init__(self, connection, **kwargs):
        self.connection = connection
        # the body won't block on write, but will block on read for up
        # to connection_timeout (as the data is coming from outside).
        self.recv_pipe = Pipe(wblocking=False,
                              timeout=connection.server.connection_timeout,
                              name="ServerRequest[%i].recv_pipe" %
                              self.connection.id)
        self.aborted = CascadingEvent()
        super(ServerRequest, self).__init__(entity_body=self.recv_pipe,
                                            **kwargs)

    def handle_headers(self):
        """Create a wsgi environment and start a processing thread"""
        # normalise the request URI to remove scheme and authority
        # ensures Host: is set correctly
        self.extract_authority()
        with self.lock:
            url = uri.URI.from_octets(self.request_uri)
            environ = {
                'REQUEST_METHOD': self.method,
                'SCRIPT_NAME': '',
                'PATH_INFO': uri.unescape_data(url.abs_path),
                'QUERY_STRING': url.query,
                'SERVER_NAME': self.connection.server.host,
                'SERVER_PORT': str(self.connection.server.port),
                'SERVER_PROTCOL': str(self.protocol),
                'REMOTE_ADDR': str(self.connection.client_address),
                'wsgi.version': (1, 0),
                'wsgi.url_scheme':
                'https' if self.connection.server.https else 'http',
                'wsgi.input': io.BufferedReader(self.recv_pipe),
                'wsgi.errors': self.connection.server.error_pipe,
                'wsgi.multithread': True,
                'wsgi.multiprocess': False,
                'wsgi.run_once': False}
            if url.query is not None:
                environ['QUERY_STRING'] = url.query
            content_type = self.get_header('Content-Type')
            if content_type is not None:
                environ['CONTENT_TYPE'] = content_type
            content_length = self.get_header('Content-Length')
            if content_length is not None:
                environ['CONTENT_LENGTH'] = content_length
            for hname, hvalue in self.headers.iteritems():
                hname = hname.replace("-", "_")
                environ['HTTP_' + hname.upper()] = hvalue[1]
        # now launch the application in a separate thread
        response = ServerResponse(
            request=self, protocol=self.connection.server.protocol)
        self.connection.handle_response(response)
        t = threading.Thread(target=response.launch_app, args=(environ, ))
        t.start()


class ServerResponse(messages.Response):

    def __init__(self, request, **kwargs):
        self.connection = request.connection
        # the body won't block on read, but will block on write for up
        # to connection_timeout (as the data is being sent outside).
        self.send_pipe = Pipe(
            rblocking=False,
            timeout=request.connection.server.connection_timeout,
            name="ServerResponse[%i].send_pipe" % self.connection.id)
        #: a CascadingEvent set when the response headers are sent
        self.ready_to_send = CascadingEvent()
        self.send_continue = CascadingEvent()
        super(ServerResponse, self).__init__(
            request=request, entity_body=self.send_pipe, **kwargs)

    def start_sending(self):
        super(ServerResponse, self).start_sending()
        self.ready_to_send.set()

    def launch_app(self, environ):
        logging.debug("Calling wsgi application...")
        data = self.connection.server.launch_app(environ, self.start_response)
        # does data support len?
        try:
            datalen = len(data)
        except TypeError:
            # length is unknown, probably a generator function
            datalen = None
        for item in data:
            if datalen == 1:
                # this is all the data, set the body_len
                self.body_len = len(item)
            if not self.ready_to_send.is_set():
                # don't send the headers until the first bit of data
                # has been yielded
                self.start_sending()
            wbytes = item
            while wbytes:
                nbytes = self.send_pipe.write(wbytes)
                if nbytes < len(wbytes):
                    wbytes = wbytes[nbytes:]
                else:
                    wbytes = None
            # self.send_pipe.flush()
            # I considered using flush here, given the following
            # requirement: "WSGI servers, gateways, and middleware must
            # not delay the transmission of any block". But we have a
            # separate thread for Connection.handle_responses and this
            # is an acceptable solution: "Use a different thread to
            # ensure that the block continues to be transmitted while
            # the application produces the next block"
            #
            # There's one caveat here though, if a transfer encoding is
            # in effect it is possible that a small number of the bytes
            # written to the send_pipe will be stuck in the codec
            # waiting for the next block (or a final flush).  Rather
            # than conclude that WSGI is incompatible with transparent
            # transport encodings we're going to ignore this issue.
        if not self.ready_to_send.is_set():
            # empty response, send it now
            self.body_len = 0
            self.start_sending()
        # when we are done writing data to the send_pipe we tell the
        # response that there is no more in case the body length was
        # indeterminate and the reader is reading forever
        self.send_pipe.write_eof()
        # HTTP requires us to read the entire input pipe even if
        # we didn't use all the data, so do that here.
        input = environ['wsgi.input']
        # we are limited in the methods we are allowed to use here
        # except that we know it is a BufferedReader over a Pipe object
        # set for read blocking up to the connection timeout
        spool_count = 0
        while not self.request.aborted.is_set():
            # this loop monitors the aborted flag for safety. In
            # practice the recv thread polices any bad clients (such as
            # those engaged in DoS activity) and if it aborts the
            # request it will also generate an EOF on the input stream.
            # We'll stop at whichever is detected first!
            logging.debug("reading trailing data...")
            data = input.read1(io.DEFAULT_BUFFER_SIZE)
            if data:
                if spool_count < io.DEFAULT_BUFFER_SIZE:
                    logging.warn("wsgi application discarded %i bytes of data",
                                 len(data))
                    logging.debug("discarding data: \n%s", data)
                spool_count += len(data)
            else:
                break

    def start_response(self, status, response_headers, exc_info=None):
        with self.lock:
            pstatus = params.ParameterParser(status, ignore_sp=False)
            if pstatus.is_integer():
                self.status = pstatus.parse_integer()
            else:
                self.status = 0
            pstatus.parse_sp()
            self.reason = pstatus.parse_remainder()
            for name, value in response_headers:
                self.set_header(name, value)
        return self.write_response

    def write_response(self, body_data):
        if not self.ready_to_send.is_set():
            # start sending the response, we've got legacy data
            self.start_sending()
        while body_data:
            nbytes = self.send_pipe.write(body_data)
            if nbytes < len(body_data):
                body_data = body_data[nbytes:]
            else:
                body_data = None
            # see comment above, we don't need to flush
            # self.send_pipe.flush()

    def close(self):
        self.send_pipe.close()


class Pipe(io.RawIOBase):

    """Buffered pipe for inter-thread communication

    The purpose of this class is to provide a thread-safe buffer to use
    for communicating between two parts of an application that support
    non-blocking io while reducing to a minimum the amount of
    byte-copying that takes place.

    Essentially, write calls with immutable byte strings are simply
    cached without copying (and always succeed) enabling them to be
    passed directly through to the corresponding read operation in
    streaming situations.  However, to improve flow control a canwrite
    method is provided to help writers moderate the amount of data that
    has to be held in the buffer::

        # data producer thread
        while busy:
            wmax = p.canwrite()
            if wmax:
                data = get_at_most_max_bytes(wmax)
                p.write(data)
            else:
                # do something else while the pipe is blocked
                spin_the_beach_ball()

    bsize
        The buffer size, this is used as a guide only.  When writing
        immutable bytes objects to the pipe the buffer size may be
        exceeded as these can simply be cached and returned directly to
        the reader more efficiently than slicing them up just to adhere
        to the buffer size.  However, if the buffer already contains
        bsize bytes all calls to write will block or return None.
        Defaults to io.DEFAULT_BUFFER_SIZE.

    rblocking
        Controls the blocking behaviour of the read end of this pipe.
        True indicates reads may block waiting for data, False that they
        will not and read may return None.  Defaults to True.

    wblocking
        Controls the blocking behaviour of the write end of the this
        pipe. True indicates writes may block waiting for data, False
        that they will not and write may return None.  Defaults to True.

    timeout
        The number of seconds before a blocked read or write operation
        will timeout.  Defaults to None, which indicates 'wait forever'.
        A value of 0 is not the same as placing both ends of the pipe in
        non-blocking mode (though the effect may be similar).

    name
        An optional name to use for this pipe, the name is used when
        raising errors and when logging"""

    def __init__(self, bsize=io.DEFAULT_BUFFER_SIZE,
                 rblocking=True, wblocking=True, timeout=None,
                 name=None):
        #: the name of the pipe
        self.name = name
        # the maximum buffer size, used for flow control, this
        # is not a hard limit
        self.max = bsize
        # buffered strings of bytes
        self.buffer = []
        # the total size of all strings in the buffer
        self.bsize = 0
        # offset into self.buffer[0]
        self.rpos = 0
        # eof indicator
        self._eof = False
        self.rblocking = rblocking
        # an Event that flags the arrival of a reader
        self.rflag = None
        self.wblocking = wblocking
        # timeout duration
        self.timeout = timeout
        # lock for multi-threading
        self.lock = threading.Condition()
        # state values used for monitoring changes
        self.wstate = 0
        self.rstate = 0
        super(Pipe, self).__init__()

    def __repr__(self):
        if self.name:
            return self.name
        else:
            return super(Pipe, self).__repr__()

    def close(self):
        # throw away all data
        logging.debug("Pipe.close %s", repr(self))
        # logging.debug(string.join(traceback.format_stack()))
        with self.lock:
            if self.buffer:
                logging.warn("Pipe.close for %s discarded non-empty buffer",
                             repr(self))
            self.buffer = []
            self.bsize = 0
            self.rpos = 0
            self._eof = True
            # kill anyone waiting
            self.rstate += 1
            self.wstate += 1
            self.lock.notify_all()
        super(Pipe, self).close()

    def readable(self):
        return True

    def writable(self):
        return True

    def readblocking(self):
        return self.rblocking

    def set_readblocking(self, blocking=True):
        with self.lock:
            self.rblocking = blocking

    def writeblocking(self):
        return self.wblocking

    def set_writeblocking(self, blocking=True):
        with self.lock:
            self.wblocking = blocking

    def wait(self, timeout, method):
        if timeout is not None:
            tstart = time.time()
        with self.lock:
            while not method():
                if timeout is None:
                    twait = None
                else:
                    twait = (tstart + timeout) - time.time()
                    if twait < 0:
                        logging.warn("Pipe.wait timedout on %s", repr(self))
                        raise IOError(errno.ETIMEDOUT,
                                      os.strerror(errno.ETIMEDOUT),
                                      "pyslet.http.server.Pipe.wait")
                logging.debug("Pipe.wait waiting for %s", repr(self))
                self.lock.wait(twait)

    def empty(self):
        """Returns True if the buffer is currently empty"""
        with self.lock:
            if self.buffer:
                return False
            else:
                return True

    def buffered(self):
        """Returns the number of buffered bytes in the Pipe"""
        with self.lock:
            return self.bsize - self.rpos

    def canwrite(self):
        """Returns the number of bytes that can be written.

        This value is the number of bytes that can be written in a
        single non-blocking call to write.  0 indicates that the pipe's
        buffer is full.  A call to write may accept more than this but
        *the next* call to write will always accept at least this many.

        This class is fully multithreaded so in situations where there
        are multiple threads writing this call is of limited use.

        If called on a pipe that has had the EOF mark written then
        IOError is raised."""
        with self.lock:
            if self.closed or self._eof:
                raise IOError(
                    errno.EPIPE,
                    "canwrite: can't write past EOF on Pipe object")
            wlen = self.max - self.bsize + self.rpos
            if wlen <= 0:
                wlen = 0
                if self.rflag is not None:
                    self.rflag.clear()
            return wlen

    def set_rflag(self, rflag):
        """Sets the Event triggered when a reader is detected.

        rflag
            An Event instance from the threading module.

        The event will be set each time the Pipe is read.  The flag may
        be cleared at any time by the caller but a convenience it will
        always be cleared when :py:meth:`canwrite` returns 0."""
        with self.lock:
            self.rflag = rflag

    def write_wait(self, timeout=None):
        """Waits for the pipe to become writable or raises IOError

        timeout
            Defaults to None: wait forever.  Otherwise the maximum
            number of seconds to wait for."""
        self.wait(timeout, self.canwrite)

    def flush_wait(self, timeout=None):
        """Waits for the pipe to become empty or raises IOError

        timeout
            Defaults to None: wait forever.  Otherwise the maximum
            number of seconds to wait for."""
        self.wait(timeout, self.empty)

    def canread(self):
        """Returns True if the next call to read will not block.

        False indicates that the pipe's buffer is empty and that a call
        to read will block.

        Note that if the buffer is empty but the EOF signal has been
        given with :py:meth:`write_eof` then canread returns True! The
        next call to read will not block but return an empty string
        indicating EOF.

        This class is fully multithreaded so in the unlikely situation
        where there are multiple threads reading this call is of limited
        use."""
        with self.lock:
            if self.closed:
                raise IOError(
                    errno.EPIPE, "can't read from a closed Pipe object")
            if self.buffer or self._eof:
                return True
            else:
                return False

    def read_wait(self, timeout=None):
        """Waits for the pipe to become readable or raises IOError

        timeout
            Defaults to None: wait forever.  Otherwise the maximum
            number of seconds to wait for."""
        self.wait(timeout, self.canread)

    def write(self, b):
        """writes data to the pipe

        The implementation varies depending on the type of b.  If b is
        an immutable bytes object then it is accepted even if this
        overfills the internal buffer (as it is not actually copied).
        If b is a bytearray then data is copied, up to the maximum
        buffer size."""
        if self.timeout is not None:
            tstart = time.time()
        with self.lock:
            if self.closed or self._eof:
                raise IOError(errno.EPIPE,
                              "write: can't write past EOF on Pipe object")
            if isinstance(b, memoryview):
                # catch memory view objects here
                b = b.tobytes()
            wlen = self.max - self.bsize + self.rpos
            while wlen <= 0:
                # block on write or return None
                if self.wblocking:
                    if self.timeout is None:
                        twait = None
                    else:
                        twait = (tstart + self.timeout) - time.time()
                        if twait < 0:
                            logging.warn("Pipe.write timed out for %s",
                                         repr(self))
                            raise IOError(errno.ETIMEDOUT,
                                          os.strerror(errno.ETIMEDOUT),
                                          "pyslet.http.server.Pipe.write")
                    logging.debug("Pipe.write waiting for %s", repr(self))
                    self.lock.wait(twait)
                    # check for eof again!
                    if self.closed or self._eof:
                        raise IOError(errno.EPIPE,
                                      "write: EOF or pipe closed after wait")
                    # recalculate the writable space
                    wlen = self.max - self.bsize + self.rpos
                else:
                    return None
            if isinstance(b, bytes):
                nbytes = len(b)
                if nbytes:
                    self.buffer.append(b)
                    self.bsize += nbytes
                    self.wstate += 1
                    self.lock.notify_all()
                return nbytes
            elif isinstance(b, bytearray):
                nbytes = len(b)
                if nbytes > wlen:
                    nbytes = wlen
                    # partial copy, creates transient bytearray :(
                    self.buffer.append(bytes(b[:nbytes]))
                else:
                    self.buffer.append(bytes(b))
                self.bsize += nbytes
                self.wstate += 1
                self.lock.notify_all()
                return nbytes
            else:
                raise TypeError(repr(type(b)))

    def write_eof(self):
        with self.lock:
            self._eof = True
            self.wstate += 1
            self.lock.notify_all()

    def flush(self):
        if self.timeout is not None:
            tstart = time.time()
        with self.lock:
            blen = self.bsize - self.rpos
            while self.buffer:
                if self.wblocking:
                    if self.timeout is None:
                        twait = None
                    else:
                        new_blen = self.bsize - self.rpos
                        if new_blen < blen:
                            # making progress, restart the clock
                            blen = new_blen
                            tstart = time.time()
                        twait = (tstart + self.timeout) - time.time()
                        if twait < 0:
                            logging.warn("Pipe.flush timed out for %s",
                                         repr(self))
                            logging.debug("Pipe.flush found stuck data: %s",
                                          repr(self.buffer))
                            raise IOError(errno.ETIMEDOUT,
                                          os.strerror(errno.ETIMEDOUT),
                                          "pyslet.http.server.Pipe.flush")
                    logging.debug("Pipe.flush waiting for %s", repr(self))
                    self.lock.wait(twait)
                else:
                    raise io.BlockingIOError(
                        errno.EWOULDBLOCK,
                        "Pipe.flush write blocked on %s" % repr(self))

    def readall(self):
        """Overridden to take care of non-blocking behaviour.

        Warning: readall always blocks until it has read EOF, regardless
        of the rblocking status of the Pipe.

        The problem is that, if the Pipe is set for non-blocking reads
        then we seem to have the choice of returning a partial read (and
        failing to signal that some of the data is still in the pipe) or
        raising an error and losing the partially read data.

        Perhaps ideally we'd return None indicating that we are blocked
        from reading the entire stream but this isn't listed as a
        possible return result for io.RawIOBase.readall and it would be
        tricky to implement anyway as we still need to deal with
        partially read data.

        Ultimately the safe choices are raise an error if called on a
        non-blocking Pipe or simply block.  We do the latter on the
        basis that anyone calling readall clearly intends to wait.

        For a deep discussion of the issues around non-blocking behaviour
        see http://bugs.python.org/issue13322"""
        data = []
        with self.lock:
            save_rblocking = self.rblocking
            try:
                self.rblocking = True
                while True:
                    part = self.read(io.DEFAULT_BUFFER_SIZE)
                    if not part:
                        # end of stream
                        return string.join(data, '')
                    else:
                        data.append(part)
            finally:
                self.rlocking = save_rblocking

    def _consolidate_buffer(self):
        with self.lock:
            if self.buffer:
                if self.rpos:
                    self.buffer[0] = self.buffer[0][self.rpos:]
                    self.rpos = 0
                self.buffer = [string.join(self.buffer, '')]

    def readmatch(self, match=grammar.CRLF):
        with self.lock:
            pos = -1
            while pos < 0:
                if self.buffer:
                    # take care of a special case first
                    pos = self.buffer[0].find(match, self.rpos)
                    if pos < 0:
                        # otherwise consolidate the buffer
                        self._consolidate_buffer()
                        pos = self.buffer[0].find(match)  # rpos is now 0
                if pos >= 0:
                    src = self.buffer[0]
                    result = src[self.rpos:pos + len(match)]
                    self.rpos += len(result)
                    if self.rpos >= len(src):
                        # discard src
                        self.buffer = self.buffer[1:]
                        self.bsize = self.bsize - len(src)
                        self.rpos = 0
                    self.rstate += 1
                    # success, set the reader flag
                    if self.rflag is not None:
                        self.rflag.set()
                    self.lock.notify_all()
                    return result
                else:
                    if self._eof:
                        return ''
                    # not found, should we block?
                    if self.canwrite():
                        # no match, but the buffer is not full so
                        # set the reader flag to indicate that we
                        # are now waiting to accept data.
                        if self.rflag is not None:
                            self.rflag.set()
                        if self.rblocking:
                            # we wait for something to happen on the
                            # Pipe hopefully a write operation!
                            cstate = self.wstate
                            logging.debug("Pipe.readmatch waiting for %s",
                                          repr(self))
                            self.lock.wait(self.timeout)
                            if self.wstate == cstate:
                                logging.warn(
                                    "Pipe.readmatch timed out for %s",
                                    repr(self))
                                raise IOError(
                                    errno.ETIMEDOUT,
                                    os.strerror(errno.ETIMEDOUT),
                                    "pyslet.http.server.Pipe.readmatch")
                            # go round the loop again
                        else:
                            # non-blocking readmatch returns None
                            return None
                    else:
                        # we can't write so no point in waiting
                        raise IOError(errno.ENOBUFS,
                                      os.strerror(errno.ENOBUFS),
                                      "pyslet.http.server.Pipe.readmatch")

    def read(self, nbytes=-1):
        if nbytes < 0:
            return self.readall()
        else:
            with self.lock:
                if self.buffer and self.rpos == 0:
                    # take care of one special case
                    src = self.buffer[0]
                    if len(src) <= nbytes:
                        self.buffer = self.buffer[1:]
                        self.bsize = self.bsize - len(src)
                        self.rstate += 1
                        # successful read
                        if self.rflag is not None:
                            self.rflag.set()
                        self.lock.notify_all()
                        return src
                b = bytearray(nbytes)
                nbytes = self.readinto(b)
                if nbytes is None:
                    return None
                else:
                    return str(b[:nbytes])

    def readinto(self, b):
        if self.timeout is not None:
            tstart = time.time()
        with self.lock:
            nbytes = len(b)
            # we're now reading
            if self.rflag is not None:
                self.rflag.set()
            while not self.buffer:
                if self._eof:
                    return 0
                elif self.rblocking:
                    if self.timeout is None:
                        twait = None
                    else:
                        twait = (tstart + self.timeout) - time.time()
                        if twait < 0:
                            logging.warn("Pipe.read timed out for %s",
                                         repr(self))
                            raise IOError(errno.ETIMEDOUT,
                                          os.strerror(errno.ETIMEDOUT),
                                          "pyslet.http.server.Pipe.read")
                    logging.debug("Pipe.read waiting for %s", repr(self))
                    self.lock.wait(twait)
                else:
                    return None
            src = self.buffer[0]
            rlen = len(src) - self.rpos
            if rlen < nbytes:
                nbytes = rlen
            if nbytes:
                b[:nbytes] = src[self.rpos:self.rpos + nbytes]
                self.rpos += nbytes
            if self.rpos >= len(src):
                # discard src
                self.buffer = self.buffer[1:]
                self.bsize = self.bsize - len(src)
                self.rpos = 0
            if nbytes:
                self.rstate += 1
                self.lock.notify_all()
            return nbytes
