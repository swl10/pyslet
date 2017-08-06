#! /usr/bin/env python
"""This module add some useful stream classes"""

import errno
import io
import logging
import os
import threading
import time

from .py26 import memoryview, RawIOBase


if hasattr(errno, 'WSAEWOULDBLOCK'):
    _blockers = set((errno.EAGAIN, errno.EWOULDBLOCK, errno.WSAEWOULDBLOCK))
else:
    _blockers = set((errno.EAGAIN, errno.EWOULDBLOCK))


def io_blocked(err):
    """Returns True if IO operation is blocked

    err
        An IOError exception (or similar object with errno attribute).

    Bear in mind that EAGAIN and EWOULDBLOCK are not necessarily the
    same value and that when running under windows WSAEWOULDBLOCK may be
    raised instead.  This function removes this complexity making it
    easier to write cross platform non-blocking IO code."""
    return err.errno in _blockers


if hasattr(errno, 'WSAETIMEDOUT'):
    _timeouts = set((errno.ETIMEDOUT, errno.WSAETIMEDOUT))
else:
    _timeouts = set((errno.ETIMEDOUT, ))


def io_timedout(err):
    """Returns True if an IO operation timed out

    err
        An IOError exception (or similar object with errno attribute).

    Tests for ETIMEDOUT and when running under windows WSAETIMEDOUT
    too."""
    return err.errno in _timeouts


class BufferedStreamWrapper(RawIOBase):

    """A buffered wrapper for file-like objects.

    src
        A file-like object, we only require a read method

    buffsize
        The maximum size of the internal buffer

    On construction the src is read until an end of file condition is
    encountered or until buffsize bytes have been read.  EOF is signaled
    by an empty string returned by src's read method.  Instances then
    behave like readable streams transparently reading from the buffer
    or from the remainder of the src as applicable.

    Instances behave differently depending on whether or not the entire
    src is buffered.  If it is they become seekable and set a value for
    the length attribute.  Otherwise they are not seekable and the
    length attribute is None.

    If src is a non-blocking data source and it becomes blocked,
    indicated by read returning None rather than an empty string, then
    the instance reverts to non-seekable behaviour."""

    def __init__(self, src, buffsize=io.DEFAULT_BUFFER_SIZE):
        self.src = src
        self.buff = io.BytesIO()
        self.bsize = 0
        self.overflow = False
        self.length = None
        while True:
            nbytes = buffsize - self.bsize
            if nbytes <= 0:
                # we've run out of buffer space
                self.overflow = True
                break
            data = src.read(nbytes)
            if data is None:
                # blocked, treat as overflow
                self.overflow = True
                break
            elif data:
                self.buff.write(data)
                self.bsize += len(data)
            else:
                # EOF
                break
        self.pos = 0
        self.buff.seek(0)
        if not self.overflow:
            self.length = self.bsize

    def readable(self):
        return True

    def writable(self):
        return False

    def seekable(self):
        return not self.overflow

    def tell(self):
        if self.overflow:
            raise io.UnsupportedOperation
        else:
            return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        if self.overflow:
            raise io.UnsupportedOperation
        elif whence == io.SEEK_SET:
            self.pos = offset
        elif whence == io.SEEK_CUR:
            self.pos += offset
        elif whence == io.SEEK_END:
            self.pos = self.length + offset
        else:
            raise ValueError("unrecognized whence value in seek: %s" %
                             repr(whence))
        self.buff.seek(self.pos)

    def readinto(self, b):
        if self.pos < self.bsize:
            # read from the buffer
            data = self.buff.read(len(b))
        elif self.overflow:
            # read from the original source
            data = self.src.read(len(b))
            if data is None:
                # handle blocked read
                return None
        else:
            # end of file
            data = b''
        self.pos += len(data)
        b[0:len(data)] = data
        return len(data)

    def peek(self, nbytes):
        """Read up to nbytes without advancing the position

        If the stream is not seekable and we have read past the end of
        the internal buffer then an empty string will be returned."""
        if self.pos < self.bsize:
            data = self.buff.read(nbytes)
            # reset the position of the buffer
            self.buff.seek(self.pos)
            return data
        else:
            return b''


class Pipe(RawIOBase):

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
        """closed the Pipe

        This implementation works on a 'reader closes' principle.  The
        writer should simply write the EOF marker to the Pipe (see
        :meth:`write_eof`.

        If the buffer still contains data when it is closed a warning is
        logged."""
        # throw away all data
        logging.debug("Pipe.close %s", repr(self))
        with self.lock:
            if self.buffer:
                logging.warning("Pipe.close for %s discarded non-empty buffer",
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
        # if someone is waiting for a reader - wake them as the reader
        # will never come
        if self.rflag is not None:
            self.rflag.set()

    def readable(self):
        """Pipe's are always readable"""
        return True

    def writable(self):
        """Pipe's are always writeable"""
        return True

    def readblocking(self):
        """Returns True if reads may block"""
        return self.rblocking

    def set_readblocking(self, blocking=True):
        """Sets the readblocking mode of the Pipe.

        blocking
            A boolean, defaults to True indicating that reads may
            block."""
        with self.lock:
            self.rblocking = blocking

    def writeblocking(self):
        """Returns True if writes may block"""
        return self.wblocking

    def set_writeblocking(self, blocking=True):
        """Sets the writeblocking mode of the Pipe.

        blocking
            A boolean, defaults to True indicating that writes may
            block."""
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
                        logging.warning("Pipe.wait timedout on %s", repr(self))
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
        """Sets an Event triggered when a reader is detected.

        rflag
            An Event instance from the threading module.

        The event will be set each time the Pipe is read.  The flag may
        be cleared at any time by the caller but as a convenience it
        will always be cleared when :py:meth:`canwrite` returns 0.

        The purpose of this flag is to allow a writer to use a custom
        event to monitor whether or not the Pipe is ready to be written.
        If the Pipe is full then the writer will want to wait on this
        flag until a reader appears before attempting to write again.
        Therefore, when canwrite indicates that the buffer is full it
        makes sense that the flag is also cleared.

        If the pipe is closed then the event is set as a warning that
        the pipe will never be read.  (The next call to write will
        then fail.)"""
        with self.lock:
            self.rflag = rflag
            if self.closed:
                self.rflag.set()

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
        """Returns True if the next call to read will *not* block.

        False indicates that the pipe's buffer is empty and that a call
        to read will block.

        Note that if the buffer is empty but the EOF signal has been
        given with :py:meth:`write_eof` then canread returns True! The
        next call to read will not block but return an empty string
        indicating the EOF."""
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
                            logging.warning("Pipe.write timed out for %s",
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
        """Writes the EOF flag to the Pipe

        Any waiting readers are notified and will wake to process the
        Pipe.  After this call the Pipe will not accept any more data."""
        with self.lock:
            self._eof = True
            self.wstate += 1
            self.lock.notify_all()

    def flush(self):
        """flushes the Pipe

        The intention of flush to push any written data out to the
        destination, in this case the thread that is reading the data.

        In write-blocking mode this call will wait until the buffer is
        empty, though if the reader is idle for more than
        :attr:`timeout` seconds then it will raise IOError.

        In non-blocking mode it simple raises IOError with EWOULDBLOCK
        if the buffer is not empty.

        Given that flush is called automatically by :meth:`close` for
        classes that inherit from the base io classes our implementation
        of close discards the buffer rather than risk an exception."""
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
                            logging.warning("Pipe.flush timed out for %s",
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
                        return b''.join(data)
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
                self.buffer = [b''.join(self.buffer)]

    def readmatch(self, match=b'\r\n'):
        """Read until a byte string is matched

        match
            A binary string, defaults to CRLF.

        This operation will block if the string is not matched unless
        the buffer becomes full without a match, in which case IOError
        is raised with code ENOBUFS."""
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
                        return b''
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
                                logging.warning(
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
        """read data from the pipe

        May return fewer than nbytes if the result can be returned
        without copying data.  Otherwise :meth:`readinto` is used."""
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
                    return bytes(b[:nbytes])

    def readinto(self, b):
        """Reads data from the Pipe into a bytearray.

        Returns the number of bytes read.  0 indicates EOF, None
        indicates an operation that would block in a Pipe that is
        non-blocking for read operations.  May return fewer bytes than
        would fit into the bytearray as it returns as soon as it has at
        least some data."""
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
                            logging.warning("Pipe.read timed out for %s",
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
