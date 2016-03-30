#! /usr/bin/env python

import binascii
import hashlib
import io
import logging
import os
import random
import threading
import time

from .http import params
from .iso8601 import TimePoint
from .odata2 import core
from .odata2 import csdl as edm
from .py2 import (
    byte,
    join_bytes,
    range3)
from .vfs import OSFilePath as FilePath


MAX_BLOCK_SIZE = 65536
"""The default maximum block size for block stores: 64K"""


def _magic():
    """Calculate a magic string used to identify an object."""
    try:
        magic = os.urandom(4)
    except NotImplementedError:
        logging.warning("weak magic: urandom not available, "
                        "falling back to random.randint")
        magic = []
        for i in range3(4):
            magic.append(byte(random.randint(0, 255)))
        magic = join_bytes(magic)
    return binascii.hexlify(magic)


class BlockSize(Exception):

    """Raised when an attempt is made to store a block exceeding the
    maximum block size for the block store."""
    pass


class BlockMissing(Exception):

    """Raised when an attempt is made to retrieve a block with an
    unknown key."""
    pass


class LockError(Exception):

    """Raised when a timeout occurs during by
    :py:meth:`LockingBlockStore.lock`"""
    pass


class BlockStore(object):

    """Abstract class representing storage for blocks of data.

    max_block_size
        The maximum block size the store can hold.  Defaults to
        :py:attr:`MAX_BLOCK_SIZE`.

    hash_class
        The hashing object to use when calculating block keys. Defaults
        to hashlib.sha256."""

    def __init__(
            self,
            max_block_size=MAX_BLOCK_SIZE,
            hash_class=hashlib.sha256):
        self.hash_class = hash_class
        self.max_block_size = max_block_size

    def key(self, data):
        if isinstance(data, bytearray):
            data = bytes(data)
        return self.hash_class(data).hexdigest().lower()

    def store(self, data):
        """Stores a block of data, returning the hash key

        data
            A binary string not exceeding the maximum block size"""
        if len(data) > self.max_block_size:
            raise BlockSize
        else:
            raise NotImplementedError

    def retrieve(self, key):
        """Returns the block of data referenced by key

        key
            A hex string previously returned by :py:meth:`store`.

        If there is no block with *key* :py:class:`BlockMissing` is
        raised."""
        raise BlockMissing(key)

    def delete(self, key):
        """Deletes the block of data referenced by key

        key
            A hex string previously returned by :py:meth:`store`."""
        raise NotImplementedError


class FileBlockStore(BlockStore):

    """Class for storing blocks of data in the file system.

    Additional keyword arguments:

    dpath
        A :py:class:`FilePath` instance pointing to a directory in which
        to store the data blocks.  If this argument is omitted then a
        temporary directory is created using the builtin mkdtemp.

    Each block is saved as a single file but the hash key is decomposed
    into 3 components to reduce the number of files in a single
    directory.  For example, if the hash key is 'ABCDEF123' then the
    file would be stored at the path: 'AB/CD/EF123'"""

    def __init__(self, dpath=None, **kwargs):
        super(FileBlockStore, self).__init__(**kwargs)
        if dpath is None:
            # create a temporary directory
            self.dpath = FilePath.mkdtemp('.d', 'pyslet_blockstore-')
        else:
            self.dpath = dpath
        self.tmpdir = self.dpath.join('tmp')
        if not self.tmpdir.exists():
            try:
                self.tmpdir.mkdir()
            except OSError:
                # catch race condition where someone already created it
                pass
        self.magic = _magic()

    def store(self, data):
        # calculate the key
        key = self.key(data)
        parent = self.dpath.join(key[0:2], key[2:4])
        path = parent.join(key[4:])
        if path.exists():
            return key
        elif len(data) > self.max_block_size:
            raise BlockSize
        else:
            tmp_path = self.tmpdir.join(
                "%s_%i_%s" %
                (self.magic, threading.current_thread().ident, key[
                    0:32]))
            with tmp_path.open(mode="wb") as f:
                f.write(data)
            if not parent.exists():
                try:
                    parent.makedirs()
                except OSError:
                    # possible race condition, ignore for now
                    pass
            tmp_path.move(path)
            return key

    def retrieve(self, key):
        path = self.dpath.join(key[0:2], key[2:4], key[4:])
        if path.exists():
            with path.open('rb') as f:
                data = f.read()
            return data
        else:
            raise BlockMissing

    def delete(self, key):
        path = self.dpath.join(key[0:2], key[2:4], key[4:])
        if path.exists():
            try:
                path.remove()
            except OSError:
                # catch race condition where path is gone already
                pass


class EDMBlockStore(BlockStore):

    """Class for storing blocks of data in an EDM-backed data service.

    Additional keyword arguments:

    entity_set
        A :py:class:`pyslet.odata2.csdl.EntitySet` instance

    Each block is saved as a single entity using the hash as the key.
    The entity must have a string key property named *hash* large enough
    to hold the hex strings generated by the selected hashing module.
    It must also have a Binary *data* property capable of holding
    max_block_size bytes."""

    def __init__(self, entity_set, **kwargs):
        super(EDMBlockStore, self).__init__(**kwargs)
        self.entity_set = entity_set

    def store(self, data):
        key = self.key(data)
        with self.entity_set.open() as blocks:
            if key in blocks:
                return key
            elif len(data) > self.max_block_size:
                raise BlockSize
            try:
                block = blocks.new_entity()
                block['hash'].set_from_value(key)
                block['data'].set_from_value(data)
                blocks.insert_entity(block)
            except edm.ConstraintError:
                # race condition, duplicate key
                pass
        return key

    def retrieve(self, key):
        with self.entity_set.open() as blocks:
            try:
                block = blocks[key]
                return block['data'].value
            except KeyError:
                raise BlockMissing

    def delete(self, key):
        with self.entity_set.open() as blocks:
            try:
                del blocks[key]
            except KeyError:
                pass


class LockStoreContext(object):

    def __init__(self, ls, hash_key):
        self.ls = ls
        self.hash_key = hash_key

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.ls.unlock(self.hash_key)


class LockStore(object):

    """Class for storing simple locks

    entity_set
        A :py:class:`pyslet.odata2.csdl.EntitySet` instance for the
        locks.

    lock_timeout
        The maximum number of seconds that a lock is considered valid
        for.  If a lock is older than this time it will be reused
        automatically.  This value is a long-stop cut off which allows a
        system to recover automatically from bugs causing stale locks.

        Defaults to 180s (3 minutes)

    This object is designed for use in conjunction with the basic block
    store to provide locking.  The locks are managed using an EDM entity
    set.

    The entity must have a string key property named *hash* large enough
    to hold the hex strings generated by the block store - the hash
    values are not checked and can be any ASCII string so the LockStore
    class could be reused for other purposes if required.

    The entity must also have a string field named *owner* capable of
    holding an ASCII string up to 32 characters in length and a datetime
    field named *created* for storing the UTC timestamp when each lock
    is created. The created property is used for optimistic concurrency
    control during updates and must be identified as having fixed
    concurrency mode in the entity type's definition."""

    def __init__(self, entity_set, lock_timeout=180):
        self.entity_set = entity_set
        self.lock_timeout = lock_timeout
        self.magic = _magic()

    def lock(self, hash_key, timeout=60):
        """Acquires the lock on hash_key or raises LockError

        The return value is a context manager object that will
        automatically release the lock on hash_key when it exits.

        locks are not nestable, they can only be acquired once.  If the
        lock cannot be acquired a back-off strategy is implemented using
        random waits up to a total maximum of *timeout* seconds.  If the
        lock still cannot be obtained :py:class:`LockError` is raised."""
        owner = "%s_%i" % (self.magic, threading.current_thread().ident)
        with self.entity_set.open() as locks:
            tnow = time.time()
            tstop = tnow + timeout
            twait = 0
            while tnow < tstop:
                time.sleep(twait)
                lock = locks.new_entity()
                lock['hash'].set_from_value(hash_key)
                lock['owner'].set_from_value(owner)
                lock['created'].set_from_value(TimePoint.from_now_utc())
                try:
                    locks.insert_entity(lock)
                    return LockStoreContext(self, hash_key)
                except edm.ConstraintError:
                    pass
                try:
                    lock = locks[hash_key]
                except KeyError:
                    # someone deleted the lock, go straight round again
                    twait = 0
                    tnow = time.time()
                    continue
                # has this lock expired?
                locktime = lock['created'].value.with_zone(zdirection=0)
                if locktime.get_unixtime() + self.lock_timeout < tnow:
                    # use optimistic locking
                    lock['owner'].set_from_value(owner)
                    try:
                        locks.update_entity(lock)
                        logging.warning("LockingBlockStore removed stale lock "
                                        "on %s", hash_key)
                        return LockStoreContext(self, hash_key)
                    except KeyError:
                        twait = 0
                        tnow = time.time()
                        continue
                    except edm.ConstraintError:
                        pass
                twait = random.randint(0, timeout // 5)
                tnow = time.time()
        logging.warning("LockingBlockStore: timeout locking %s", hash_key)
        raise LockError

    def unlock(self, hash_key):
        """Releases the lock on *hash_key*

        Typically called by the context manager object returned by
        :py:meth:`lock` rather than called directly.

        Stale locks are handled automatically but three possible warning
        conditions may be logged.  All stale locks indicate that the
        process holding the lock was unexpectedly slow (or clients with
        poorly synchronised clocks) so these warnings suggest the need
        for increasing the lock_timeout.

        stale lock reused
            The lock was not released as it has been acquired by another
            owner.  Could indicate significant contention on this
            hash_key.

        stale lock detected
            The lock was no longer present and has since been acquired
            and released by another owner.  Indicates a slow process
            holding locks.

        stale lock race
            The lock timed out and was reused while we were removing it.
            Unlikely but indicates both significant contention and a
            slow process holding the lock."""
        owner = "%s_%i" % (self.magic, threading.current_thread().ident)
        with self.entity_set.open() as locks:
            try:
                lock = locks[hash_key]
                if lock['owner'].value == owner:
                    # this is our lock - delete it
                    # potential race condition here if we timeout between
                    # loading and deleting the entity so we check how
                    # close it is and buy more time if necessary
                    locktime = lock['created'].value.with_zone(zdirection=0)
                    if (locktime.get_unixtime() + self.lock_timeout <
                            time.time() + 1):
                        # less than 1 second left, buy more time
                        # triggers update of 'created' property using
                        # optimistic locking ensuring we still own
                        locks.update_entity(lock)
                    del locks[hash_key]
                else:
                    # we're not the owner
                    logging.warning("LockingBlockStore: stale lock reused "
                                    "on busy hash %s", hash_key)
            except KeyError:
                # someone deleted the lock already - timeout?
                logging.warning("LockingBlockStore: stale lock detected "
                                "on hash %s", hash_key)
                pass
            except edm.ConstraintError:
                logging.warning("LockingBlockStore: stale lock race "
                                "on busy hash %s", hash_key)


class StreamStore(object):

    """Class for storing stream objects

    Streams are split in to blocks that are stored in the associated
    BlockStore.  Timed locks are used to minimise the risk of conflicts
    during store and delete operations on each block but all other
    operations are done without locks. As a result, it is possible to
    delete or modify a stream while another client is using it.

    The intended use case for this store is to read and write entire
    streams - not for editing.  The stream identifiers are simply
    numbers so if you want to modify the stream associated with a
    resource in your application upload a new stream, switch the
    references in your application and then delete the old one.

    bs
        A :py:class:`BlockStore`: used to store the actual data.  The
        use of a block store to persist the data in the stream ensures
        that duplicate streams have only a small impact on storage
        requirements as the block references are all that is duplicated.
        Larger block sizes reduce this overhead and speed up access at
        the expense of keeping a larger portion of the stream in memory
        during streaming operations.  The block size is set when the
        block store is created.

    ls
        A :py:class:`LockStore`: used to lock blocks during write and
        delete operations.

    entity_set
        An :py:class:`~pyslet.odata2.csdl.EntitySet` to hold the Stream
        entities.

    The entity set must have the following properties:

    streamID
        An automatically generated integer stream identifier that is
        also the key

    mimetype
        An ASCII string to hold the stream's mime type (at least 64
        characters).

    created
        An Edm.DateTime property to hold the creation date.

    modified
        An Edm.DateTime property to hold the last modified date.

    size
        An Edm.Int64 to hold the stream's size

    md5
        An Edm.Binary field of fixed length 16 bytes to hold the
        MD5 checksum of the stream.

    Blocks
        A 1..Many navigation property to a related entity set with the
        following properties...

        blockID
            An automatically generated integer block identifier that is
            also the key

        num
            A block sequence integer

        hash
            The hash key of the block in the block store"""

    def __init__(self, bs, ls, entity_set):
        self.bs = bs
        self.ls = ls
        self.stream_set = entity_set
        self.block_set = entity_set.get_target('Blocks')

    def new_stream(self,
                   mimetype=params.MediaType('application', 'octet-stream'),
                   created=None):
        """Creates a new stream in the store.

        mimetype
            A :py:class:`~pyslet.http.params.MediaType` object

        Returns a stream entity which is an
        :py:class:`~pyslet.odata2.csdl.Entity` instance.

        The stream is identified by the stream entity's key which you
        can store elsewhere as a reference and pass to
        :py:meth:`get_stream` to retrieve the stream again later."""
        with self.stream_set.open() as streams:
            stream = streams.new_entity()
            if not isinstance(mimetype, params.MediaType):
                mimetype = params.MediaType.from_str(mimetype)
            stream['mimetype'].set_from_value(str(mimetype))
            now = TimePoint.from_now_utc()
            stream['size'].set_from_value(0)
            if created is None:
                stream['created'].set_from_value(now)
                stream['modified'].set_from_value(now)
            else:
                created = created.shift_zone(0)
                stream['created'].set_from_value(created)
                stream['modified'].set_from_value(created)
            stream['md5'].set_from_value(hashlib.md5().digest())
            streams.insert_entity(stream)
            return stream

    def get_stream(self, stream_id):
        """Returns the stream with identifier *stream_id*.

        Returns the stream entity as an
        :py:class:`~pyslet.odata2.csdl.Entity` instance."""
        with self.stream_set.open() as streams:
            stream = streams[stream_id]
        return stream

    def open_stream(self, stream, mode="r"):
        """Returns a file-like object for a stream.

        Returns an object derived from io.RawIOBase.

        stream
            A stream entity

        mode
            Files are always opened in binary mode.  The characters "r",
            "w" and "+" and "a" are honoured.

        Warning: read and write methods of the resulting objects do not
        always return all requested bytes.  In particular, read or write
        operations never cross block boundaries in a single call."""
        if stream is None:
            raise ValueError
        return BlockStream(self, stream, mode)

    def delete_stream(self, stream):
        """Deletes a stream from the store.

        Any data blocks that are orphaned by this deletion are
        removed."""
        with self.stream_set.open() as streams:
            self.delete_blocks(stream)
            del streams[stream.key()]
            stream.exists = False

    def store_block(self, stream, block_num, data):
        hash_key = self.bs.key(data)
        with stream['Blocks'].open() as blocks:
            block = blocks.new_entity()
            block['num'].set_from_value(block_num)
            block['hash'].set_from_value(hash_key)
            blocks.insert_entity(block)
            # now ensure that the data is stored
            with self.ls.lock(hash_key):
                self.bs.store(data)
            return block

    def update_block(self, block, data):
        hash_key = block['hash'].value
        new_hash = self.bs.key(data)
        if new_hash == hash_key:
            return
        filter = core.BinaryExpression(core.Operator.eq)
        filter.add_operand(core.PropertyExpression('hash'))
        hash_value = edm.EDMValue.from_type(edm.SimpleType.String)
        filter.add_operand(core.LiteralExpression(hash_value))
        # filter is: hash eq <hash_value>
        with self.block_set.open() as base_coll:
            with self.ls.lock(hash_key):
                with self.ls.lock(new_hash):
                    self.bs.store(data)
                    block['hash'].set_from_value(new_hash)
                    base_coll.update_entity(block)
                    # is the old hash key used anywhere?
                    hash_value.set_from_value(hash_key)
                    base_coll.set_filter(filter)
                    if len(base_coll) == 0:
                        # remove orphan block from block store
                        self.bs.delete(hash_key)

    def retrieve_blocklist(self, stream):
        with stream['Blocks'].open() as blocks:
            blocks.set_orderby(
                core.CommonExpression.orderby_from_str("num asc"))
            for block in blocks.itervalues():
                yield block

    def retrieve_block(self, block):
        return self.bs.retrieve(block['hash'].value)

    def delete_blocks(self, stream, from_num=0):
        blocks = list(self.retrieve_blocklist(stream))
        filter = core.BinaryExpression(core.Operator.eq)
        filter.add_operand(core.PropertyExpression('hash'))
        hash_value = edm.EDMValue.from_type(edm.SimpleType.String)
        filter.add_operand(core.LiteralExpression(hash_value))
        # filter is: hash eq <hash_value>
        with self.block_set.open() as base_coll:
            for block in blocks:
                if from_num and block['num'].value < from_num:
                    continue
                hash_key = block['hash'].value
                with self.ls.lock(hash_key):
                    del base_coll[block.key()]
                    # is this hash key used anywhere?
                    hash_value.set_from_value(hash_key)
                    base_coll.set_filter(filter)
                    if len(base_coll) == 0:
                        # remove orphan block from block store
                        self.bs.delete(hash_key)


class BlockStream(io.RawIOBase):

    """Provides a file-like interface to stored streams

    Based on the new style io.RawIOBase these streams are always in
    binary mode.  They are seekable but lack efficiency if random access
    is used across block boundaries.  The main design criteria is to
    ensure that no more than one block is kept in memory at any one
    time."""

    def __init__(self, ss, stream, mode="r"):
        self.ss = ss
        self.stream = stream
        self.r = "r" in mode or "+" in mode
        self.w = "w" in mode or "+" in mode
        self.size = stream['size'].value
        self.block_size = self.ss.bs.max_block_size
        self._bdata = None
        self._bnum = 0
        self._bpos = 0
        self._btop = 0
        self._bdirty = False
        self._md5 = None
        if "a" in mode:
            self.seek(self.size)
            self.blocks = list(self.ss.retrieve_blocklist(self.stream))
        else:
            self.seek(0)
            if "w" in mode:
                self.ss.delete_blocks(self.stream)
                self.blocks = []
                self._md5 = hashlib.md5()
                self._md5num = 0
            else:
                self.blocks = list(self.ss.retrieve_blocklist(self.stream))

    def close(self):
        super(BlockStream, self).close()
        self.blocks = None
        self.r = self.w = False

    def readable(self):
        return self.r

    def writable(self):
        return self.w

    def seekable(self):
        return True

    def seek(self, offset, whence=io.SEEK_SET):
        if whence == io.SEEK_SET:
            self.pos = offset
        elif whence == io.SEEK_CUR:
            self.pos += offset
        elif whence == io.SEEK_END:
            self.pos = self.size + offset
        else:
            raise IOError("bad value for whence in seek")
        new_bnum = self.pos // self.block_size
        if new_bnum != self._bnum:
            self.flush()
            self._bdata = None
            self._bnum = new_bnum
        self._bpos = self.pos % self.block_size
        self._set_btop()

    def _set_btop(self):
        if self.size // self.block_size == self._bnum:
            # we're pointing to the last block
            self._btop = self.size % self.block_size
        else:
            self._btop = self.block_size

    def flush(self):
        if self._bdirty:
            # the current block is dirty, write it out
            data = self._bdata[:self._btop]
            if data:
                block = self.blocks[self._bnum]
                if block.exists:
                    self.ss.update_block(block, bytes(data))
                else:
                    self.blocks[self._bnum] = self.ss.store_block(
                        self.stream, self._bnum, data)
                if self._md5 is not None and self._bnum == self._md5num:
                    self._md5.update(bytes(data))
                    self._md5num += 1
                else:
                    self._md5 = None
            if self.size != self.stream['size'].value:
                self.stream['size'].set_from_value(self.size)
            now = TimePoint.from_now_utc()
            self.stream['modified'].set_from_value(now)
            if self._md5 is not None:
                self.stream['md5'].set_from_value(self._md5.digest())
            else:
                self.stream['md5'].set_null()
            self.stream.commit()
            self._bdirty = False

    def tell(self):
        return self.pos

    def readinto(self, b):
        if not self.r:
            raise IOError("stream not open for reading")
        nbytes = self._btop - self._bpos
        if nbytes <= 0:
            # we must be at the file size limit
            return 0
        if self._bdata is None:
            # load the data
            if self.w:
                # create a full size block in case we also write
                self._bdata = bytearray(self.block_size)
                data = self.ss.retrieve_block(self.blocks[self._bnum])
                self._bdata[:len(data)] = data
            else:
                self._bdata = self.ss.retrieve_block(self.blocks[self._bnum])
        if nbytes > len(b):
            nbytes = len(b)
        b[:nbytes] = self._bdata[self._bpos:self._bpos + nbytes]
        self.seek(nbytes, io.SEEK_CUR)
        return nbytes

    def write(self, b):
        if not self.w:
            raise IOError("stream not open for writing")
        # we can always write something in the block, nbytes > 0
        nbytes = self.block_size - self._bpos
        if self._bdata is None:
            if self._btop <= 0:
                # add a new empty blocks first
                last_block = len(self.blocks)
                while last_block < self._bnum:
                    self.blocks.append(self.ss.store_block(
                        self.stream, last_block, bytearray(self.block_size)))
                    last_block += 1
                    self.size = last_block * self.block_size
                # force the new size to be written
                self._bdata = bytearray(self.block_size)
                self._bdirty = True
                self.flush()
                # finally add the last block, but don't store it yet
                with self.stream['Blocks'].open() as blist:
                    new_block = blist.new_entity()
                    new_block['num'].set_from_value(self._bnum)
                    self.blocks.append(new_block)
                self.size = self.pos
                self._set_btop()
                if self._bpos:
                    self._bdirty = True
            else:
                self._bdata = bytearray(self.block_size)
                data = self.ss.retrieve_block(self.blocks[self._bnum])
                self._bdata[:len(data)] = data
        if nbytes > len(b):
            nbytes = len(b)
        self._bdata[self._bpos:self._bpos + nbytes] = b[:nbytes]
        self._bdirty = True
        if self.pos + nbytes > self.size:
            self.size = self.pos + nbytes
            self._set_btop()
        self.seek(nbytes, io.SEEK_CUR)
        return nbytes
