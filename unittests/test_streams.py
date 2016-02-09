#! /usr/bin/env python

import errno
import io
import logging
import random
import threading
import time
import unittest

from pyslet.py2 import range3, byte_to_bstr
from pyslet.streams import Pipe, BufferedStreamWrapper, io_timedout


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(BufferedStreamWrapperTests, 'test'),
        unittest.makeSuite(PipeTests, 'test'),
    ))


class BufferedStreamWrapperTests(unittest.TestCase):

    def test_goodsize(self):
        data = b"How long is a piece of string?"
        src = io.BytesIO(data)
        # default buffer is larger than src
        b = BufferedStreamWrapper(src)
        self.assertTrue(isinstance(b, io.RawIOBase))
        self.assertTrue(b.readable())
        self.assertFalse(b.writable())
        self.assertTrue(b.seekable())
        self.assertTrue(b.length == len(data))
        pos = b.tell()
        self.assertTrue(pos == 0, "buffer starts at beginning of stream")
        for i in range3(100):
            # check seek and read
            newpos = random.randint(0, len(data) + 1)
            rlen = random.randint(0, len(data) + 1)
            whence = random.choice((io.SEEK_SET, io.SEEK_CUR, io.SEEK_END))
            if whence == io.SEEK_CUR:
                adj = newpos - pos
            elif whence == io.SEEK_END:
                adj = newpos - len(data)
            elif whence == io.SEEK_SET:
                adj = newpos
            b.seek(adj, whence)
            self.assertTrue(b.tell() == newpos,
                            "Expected %i found %i" % (newpos, b.tell()))
            pos = newpos
            xlen = max(0, min(len(data) - pos, rlen))
            rdata = b.read(rlen)
            self.assertTrue(len(rdata) == xlen)
            self.assertTrue(rdata == data[pos:pos + rlen])
            pos += xlen

    def test_badsize(self):
        data = b"How long is a piece of string?"
        src = io.BytesIO(data)
        # make buffer smaller than src
        b = BufferedStreamWrapper(src, len(data) // 2)
        self.assertTrue(isinstance(b, io.RawIOBase))
        self.assertTrue(b.readable())
        self.assertFalse(b.writable())
        self.assertFalse(b.seekable())
        self.assertTrue(b.length is None)
        buff = []
        while True:
            rdata = b.read(7)
            if rdata == b'':
                break
            else:
                buff.append(rdata)
        result = b''.join(buff)
        self.assertTrue(result == data, repr(result))
        # now read to align with buffer size
        src.seek(0)
        b = BufferedStreamWrapper(src, 10)
        buff = []
        while True:
            rdata = b.read(5)
            if rdata == b'':
                break
            else:
                buff.append(rdata)
        result = b''.join(buff)
        self.assertTrue(result == data, repr(result))
        # now read exactly buffer size
        src.seek(0)
        b = BufferedStreamWrapper(src, 10)
        buff = []
        while True:
            rdata = b.read(10)
            if rdata == b'':
                break
            else:
                buff.append(rdata)
        result = b''.join(buff)
        self.assertTrue(result == data, repr(result))

    def test_boundarysize(self):
        data = b"How long is a piece of string?"
        src = io.BytesIO(data)
        # make buffer same length as src
        b = BufferedStreamWrapper(src, len(data))
        self.assertTrue(isinstance(b, io.RawIOBase))
        self.assertTrue(b.readable())
        self.assertFalse(b.writable())
        # not seekable as we can't peek past the end of src so it counts
        # as an overflow.
        self.assertFalse(b.seekable())
        self.assertTrue(b.length is None)
        # treat as readall
        result = b.read()
        self.assertTrue(result == data, repr(result))

    def test_blocked(self):
        data = b"How long is a piece of string?"
        src = Pipe(rblocking=False, name="test_blocked")
        src.write(data)
        # no eof, default buffer size will trigger block
        b = BufferedStreamWrapper(src)
        self.assertTrue(b.readable())
        self.assertFalse(b.writable())
        self.assertFalse(b.seekable())
        self.assertTrue(b.length is None)
        # but note that we can still peek on the data
        # that we have buffered
        self.assertTrue(b.peek(3) == data[0:3])

    def test_unblocked(self):
        data = b"How long is a piece of string?"
        src = Pipe(rblocking=False, name="test_unblocked")
        # write one byte at a time
        for c in data:
            src.write(byte_to_bstr(c))
        src.write_eof()
        # default buffer size outgrows pipe
        b = BufferedStreamWrapper(src)
        self.assertTrue(b.readable())
        self.assertFalse(b.writable())
        self.assertTrue(b.seekable())
        self.assertTrue(b.length == len(data))
        # the buffer also smooths access to the data
        self.assertTrue(b.read(10) == data[0:10])

    def test_peek(self):
        data = b"How long is a piece of string?"
        src = io.BytesIO(data)
        # make buffer smaller than src
        b = BufferedStreamWrapper(src, 10)
        self.assertTrue(b.peek(3) == data[0:3])
        self.assertTrue(b.read(8) == data[0:8], "Data consumed by peek")
        self.assertTrue(b.peek(3) == data[8:10], "Peek to end of buffer")
        nbytes = 0
        while nbytes < 3:
            rdata = b.read(3 - nbytes)
            self.assertTrue(rdata, "reading past buffer")
            nbytes += len(rdata)
        # now peek should always return empty
        self.assertTrue(b.peek(1) == b"", "Can't peek past end of buffer")


class PipeTests(unittest.TestCase):

    def test_simple(self):
        p = Pipe()
        # default constructor
        self.assertTrue(isinstance(p, io.RawIOBase))
        self.assertFalse(p.closed)
        try:
            p.fileno()
            self.fail("fileno should raise IOError")
        except IOError:
            pass
        self.assertFalse(p.isatty())
        self.assertTrue(p.readable())
        self.assertFalse(p.seekable())
        self.assertTrue(p.writable())
        # now for our custom attributes
        self.assertTrue(p.readblocking())
        self.assertTrue(p.writeblocking())
        self.assertTrue(p.canwrite() == io.DEFAULT_BUFFER_SIZE)
        self.assertFalse(p.canread())
        # now try a quick read and write test
        data = b"The quick brown fox jumped over the lazy dog"
        wlen = p.write(data)
        self.assertTrue(wlen == len(data))
        self.assertTrue(p.canwrite() == io.DEFAULT_BUFFER_SIZE - len(data))
        self.assertTrue(p.canread())
        self.assertTrue(p.read(3) == data[:3])
        self.assertTrue(p.canwrite() == io.DEFAULT_BUFFER_SIZE - len(data) + 3)
        self.assertTrue(p.canread())
        # now deal with EOF conditions
        p.write_eof()
        try:
            p.write(b"extra")
            self.fail("write past EOF")
        except IOError:
            pass
        try:
            p.canwrite()
            self.fail("canwrite called past EOF")
        except IOError:
            pass
        self.assertTrue(p.canread(), "But can still read")
        self.assertFalse(p.closed)
        self.assertTrue(p.readall() == data[3:])
        self.assertTrue(p.canread(), "Can still read")
        self.assertTrue(p.read(3) == b'')
        self.assertTrue(len(p.read()) == 0)
        self.assertTrue(len(p.readall()) == 0)
        p.close()
        self.assertTrue(p.closed)
        try:
            p.canread()
            self.fail("canread called on closed pipe")
        except IOError:
            pass

    def test_blocking(self):
        p = Pipe(timeout=1, bsize=10)
        self.assertTrue(p.readblocking())
        self.assertTrue(p.writeblocking())
        try:
            # should block for 1 second and then timeout
            rresult = p.read(1)
            self.fail("blocked read returned %s" % repr(rresult))
        except IOError as e:
            self.assertTrue(io_timedout(e))
        p.write(b"123")
        # should not block!
        rresult = p.read(5)
        self.assertTrue(rresult == b"123")
        # should not block, just!
        p.write(bytearray(b"1234567890"))
        try:
            # should block for 1 second
            wresult = p.write(b"extra")
            self.fail("blocked write returned %s" % repr(wresult))
        except IOError as e:
            self.assertTrue(io_timedout(e))
        try:
            # should block for 1 second
            logging.debug("flush waiting for 1s timeout...")
            p.flush()
            self.fail("blocked flush returned")
        except IOError as e:
            logging.debug("flush caught 1s timeout; %s", str(e))

    def wrunner(self, p):
        # write some data to the pipe p
        time.sleep(1)
        p.write(b"1234567890")

    def test_rblocking(self):
        p = Pipe(timeout=15)
        t = threading.Thread(target=self.wrunner, args=(p,))
        t.start()
        try:
            # should block until the other thread writes
            rresult = p.read(1)
            self.assertTrue(rresult == b"1")
        except IOError as e:
            self.fail("Timeout on mutlithreaded pipe; %s" % str(e))

    def rrunner(self, p):
        # read some data from the pipe p
        time.sleep(1)
        p.read(1)

    def rallrunner(self, p):
        # read all the data from p until there is no more
        time.sleep(1)
        logging.debug("rallrunner: calling readall")
        p.readall()

    def test_rdetect(self):
        p = Pipe(timeout=15, bsize=10)
        rflag = threading.Event()
        # set a read event
        p.set_rflag(rflag)
        self.assertFalse(rflag.is_set())
        t = threading.Thread(target=self.rrunner, args=(p,))
        t.start()
        # the runner will issue a read call, should trigger the event
        rflag.wait(5.0)
        self.assertTrue(rflag.is_set())
        # write 10 bytes, thread should terminate
        p.write(b"1234567890")
        t.join()
        # one byte read, write another byte
        p.write(b"A")
        # buffer should now be full at this point...
        self.assertFalse(p.canwrite())
        self.assertFalse(rflag.is_set())
        # the next call to read should set the flag again
        p.read(1)
        self.assertTrue(rflag.is_set())

    def test_wblocking(self):
        p = Pipe(timeout=15, bsize=10)
        t = threading.Thread(target=self.rrunner, args=(p,))
        p.write(b"1234567890")
        data = b"extra"
        t.start()
        try:
            # should block until the other thread reads
            wresult = p.write(bytearray(data))
            # and should then write at most 1 byte
            self.assertTrue(wresult == 1, repr(wresult))
        except IOError as e:
            self.fail("Timeout on mutlithreaded pipe; %s" % str(e))
        t = threading.Thread(target=self.rallrunner, args=(p,))
        t.start()
        try:
            # should block until all data has been read
            logging.debug("flush waiting...")
            p.flush()
            logging.debug("flush complete")
            self.assertTrue(p.canwrite() == 10, "empty after flush")
        except IOError as e:
            self.fail("flush timeout on mutlithreaded pipe; %s" % str(e))
        # put the other thread out of its misery
        p.write_eof()
        logging.debug("eof written, joining rallrunner")
        t.join()

    def test_rnblocking(self):
        p = Pipe(timeout=1, bsize=10, rblocking=False)
        self.assertFalse(p.readblocking())
        self.assertTrue(p.writeblocking())
        try:
            # should not block
            rresult = p.read(1)
            self.assertTrue(rresult is None)
        except IOError as e:
            self.fail("Timeout on non-blocking read; %s" % str(e))
        # write should still block
        p.write(b"1234567890")
        try:
            # should block for 1 second
            wresult = p.write(b"extra")
            self.fail("blocked write returned %s" % repr(wresult))
        except IOError as e:
            self.assertTrue(io_timedout(e))

    def test_wnblocking(self):
        p = Pipe(timeout=1, bsize=10, wblocking=False)
        self.assertTrue(p.readblocking())
        self.assertFalse(p.writeblocking())
        p.write(b"1234567890")
        data = b"extra"
        try:
            # should not block
            wresult = p.write(data)
            self.assertTrue(wresult is None, repr(wresult))
        except IOError as e:
            self.fail("Timeout on non-blocking write; %s" % str(e))
        # read all the data to empty the buffer
        self.assertTrue(len(p.read(10)) == 10, "in our case, True!")
        try:
            # should block for 1 second and then timeout
            rresult = p.read(1)
            self.fail("blocked read returned %s" % repr(rresult))
        except IOError as e:
            self.assertTrue(io_timedout(e))
        p.write(b"1234567890")
        try:
            # should not block!
            p.flush()
            self.fail("non-blocking flush returned with data")
        except io.BlockingIOError:
            pass
        except IOError as e:
            self.fail("non-blocking flush timed out; %s" % str(e))

    def wwait_runner(self, p):
        time.sleep(1)
        p.read(1)

    def test_wwait(self):
        p = Pipe(timeout=1, bsize=10, wblocking=False)
        p.write(b"1234567890")
        data = b"extra"
        wresult = p.write(data)
        self.assertTrue(wresult is None, "write blocked")
        try:
            p.write_wait(timeout=1)
            self.fail("wait should time out")
        except IOError as e:
            self.assertTrue(io_timedout(e))
        t = threading.Thread(target=self.wwait_runner, args=(p,))
        t.start()
        time.sleep(0)
        try:
            p.write_wait(timeout=5)
            pass
        except IOError:
            self.fail("write_wait error on multi-threaded read; %s" % str(e))

    def rwait_runner(self, p):
        time.sleep(1)
        p.write(b"1234567890")

    def test_rwait(self):
        p = Pipe(timeout=1, bsize=10, rblocking=False)
        rresult = p.read(1)
        self.assertTrue(rresult is None, "read blocked")
        try:
            p.read_wait(timeout=1)
            self.fail("wait should time out")
        except IOError as e:
            self.assertTrue(io_timedout(e))
        t = threading.Thread(target=self.rwait_runner, args=(p,))
        t.start()
        time.sleep(0)
        try:
            p.read_wait(timeout=5)
            pass
        except IOError as e:
            self.fail("read_wait error on multi-threaded write; %s" % str(e))

    def test_eof(self):
        p = Pipe(timeout=1, bsize=10)
        p.write(b"123")
        self.assertTrue(p.canread())
        p.read(3)
        self.assertFalse(p.canread())
        p.write_eof()
        self.assertTrue(p.canread())
        self.assertTrue(p.read(3) == b'')

    def test_readall(self):
        p = Pipe(timeout=1, bsize=10, rblocking=False)
        p.write(b"123")
        # readall should block and timeout
        try:
            data = p.readall()
            self.fail("blocked readall returned: %s" % data)
        except IOError as e:
            self.assertTrue(io_timedout(e))

    def test_nbreadmatch(self):
        p = Pipe(timeout=1, bsize=10, rblocking=False)
        p.write(b"12")
        p.write(b"3\r\n")
        self.assertTrue(p.readmatch() == b"123\r\n")
        # now check behaviour when no line is present
        p.write(b"1")
        p.write(b"2")
        p.write(b"3")
        self.assertTrue(p.readmatch() is None, "non-blocking readmatch")
        p.write(b"\r")
        self.assertTrue(p.readmatch() is None, "non-blocking partial match")
        p.write(b"\nabc")
        self.assertTrue(p.readmatch() == b"123\r\n")
        # now check for buffer size exceeded
        p.write(b"\r3\n4\r56\n")
        try:
            p.readmatch()
            self.fail("non-blocking full buffer")
        except IOError as e:
            self.assertTrue(e.errno == errno.ENOBUFS)
        # now add an EOF and it should change the result
        p.write_eof()
        self.assertTrue(p.readmatch() == b'')

    def test_breadmatch(self):
        p = Pipe(timeout=1, bsize=10, rblocking=True)
        p.write(b"12")
        p.write(b"3\r\n")
        self.assertTrue(p.readmatch() == b"123\r\n")
        # now check behaviour when no line is present
        p.write(b"1")
        p.write(b"2")
        p.write(b"3")
        try:
            p.readmatch()
            self.fail("blocking readmatch")
        except IOError as e:
            self.assertTrue(io_timedout(e))
        p.write(b"\r")
        p.write(b"\nabc")
        self.assertTrue(p.readmatch() == b"123\r\n")
        # now check for buffer size exceeded
        p.write(b"\r3\n4\r56\n")
        try:
            p.readmatch()
            self.fail("blocking full buffer")
        except IOError as e:
            self.assertTrue(e.errno == errno.ENOBUFS)
        # now add an EOF and it should change the result
        p.write_eof()
        self.assertTrue(p.readmatch() == b'')


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
