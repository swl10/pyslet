#! /usr/bin/env python

import unittest
import logging
import hashlib
import os.path

from pyslet.vfs import OSFilePath as FilePath
import pyslet.odata2.edmx as edmx
from pyslet.odata2.memds import InMemoryEntityContainer
from pyslet.odata2.sqlds import SQLiteEntityContainer

from pyslet.blockstore import *     # noqa


def suite():
    loader = unittest.TestLoader()
    loader.testMethodPrefix = 'test'
    return unittest.TestSuite((
        loader.loadTestsFromTestCase(CoreTests),
        loader.loadTestsFromTestCase(FileTests),
        loader.loadTestsFromTestCase(ODataTests),
        loader.loadTestsFromTestCase(LockingTests),
        loader.loadTestsFromTestCase(StreamStoreTests),
        loader.loadTestsFromTestCase(RandomStreamTests),
    ))


DATA_DIR = os.path.join(
    os.path.split(
        os.path.abspath(__file__))[0],
    'data_blockstore')


class CoreTests(unittest.TestCase):

    def test_init(self):
        bs = BlockStore()
        self.assertTrue(
            bs.max_block_size == MAX_BLOCK_SIZE,
            "default block size")
        self.assertTrue(
            bs.hash_class is hashlib.sha256,
            "default hash_class SHA256")

    def test_maxsize(self):
        bs = BlockStore(max_block_size=256)
        self.assertTrue(bs.max_block_size == 256, "custom block size")
        # try and store a block that exceeds this size
        try:
            bs.store("0123456789ABCDEF" * 16 + "X")
            self.fail("Max block size exceeded")
        except BlockSize:
            pass

    def test_hash(self):
        bs = BlockStore(hash_class=hashlib.md5)
        self.assertTrue(
            bs.hash_class is hashlib.md5,
            "custom hash_class setting")

    def test_store(self):
        bs = BlockStore()
        try:
            bs.store("The quick brown fox jumped over the lazy dog")
            self.fail("No storage engine")
        except NotImplementedError:
            pass


class BlockStoreCommon(unittest.TestCase):

    def fox_cafe(self, bs):
        fox = "The quick brown fox jumped over the lazy dog"
        cafe = u"Caf\xe9".encode('utf-8')
        kx = hashlib.sha256('x').hexdigest().lower()
        try:
            kfox = bs.store(fox)
            self.assertTrue(len(kfox) == 64)
            self.assertTrue(kfox == hashlib.sha256(fox).hexdigest().lower())
            kcafe = bs.store(cafe)
        except NotImplementedError:
            self.fail("No storage engine")
        # no read them back
        self.assertTrue(bs.retrieve(kfox) == fox, "Read back")
        self.assertTrue(bs.retrieve(kcafe) == cafe, "Read back binary")
        try:
            bs.retrieve(kx)
            self.fail("Read back non-existent block")
        except BlockMissing:
            pass
        kfox2 = bs.store(fox)
        self.assertTrue(kfox2 == kfox)

    def maxsize(self, bs):
        self.assertTrue(bs.max_block_size == 256, "custom block size")
        # try and store a block that exceeds this size
        try:
            bs.store("0123456789ABCDEF" * 16 + "X")
            self.fail("Max block size exceeded")
        except BlockSize:
            pass

    def checkmd5(self, bs):
        fox = "The quick brown fox jumped over the lazy dog"
        kfox = bs.store(fox)
        self.assertTrue(len(kfox) == 32)
        self.assertTrue(kfox == hashlib.md5(fox).hexdigest().lower())

    def cafeclosed(self, bs):
        fox = "The quick brown fox jumped over the lazy dog"
        kfox = bs.store(fox)
        cafe = u"Caf\xe9".encode('utf-8')
        kcafe = bs.store(cafe)
        self.assertTrue(bs.retrieve(kcafe))
        bs.delete(kcafe)
        try:
            bs.retrieve(kcafe)
            self.fail("Read back deleted block")
        except BlockMissing:
            pass
        self.assertTrue(bs.retrieve(kfox))


class FileTests(BlockStoreCommon):

    def setUp(self):  # noqa
        self.d = FilePath.mkdtemp('.d', 'pyslet-test_blockstore-')

    def tearDown(self):  # noqa
        self.d.rmtree(True)

    def test_init(self):
        bs = FileBlockStore()
        self.assertTrue(
            bs.max_block_size == MAX_BLOCK_SIZE,
            "default block size")
        self.assertTrue(
            bs.hash_class is hashlib.sha256,
            "default hash_class SHA256")

    def test_store(self):
        bs = FileBlockStore()
        self.fox_cafe(bs)

    def test_maxsize(self):
        bs = FileBlockStore(max_block_size=256)
        self.maxsize(bs)

    def test_dpath(self):
        bs = FileBlockStore(dpath=self.d)
        fox = "The quick brown fox jumped over the lazy dog"
        kfox = bs.store(fox)
        # default algorithm is to split twice
        d1 = self.d.join(kfox[0:2])
        self.assertTrue(d1.isdir(), "d1 exists")
        d2 = d1.join(kfox[2:4])
        self.assertTrue(d2.isdir(), "d2 exists")
        d3 = d2.join(kfox[4:6])
        self.assertFalse(d3.isdir(), "d3 does not exist")
        block = d2.join(kfox[4:])
        self.assertTrue(block.isfile(), "file exists")

    def test_hash(self):
        bs = FileBlockStore(hash_class=hashlib.md5)
        fox = "The quick brown fox jumped over the lazy dog"
        kfox = bs.store(fox)
        self.assertTrue(len(kfox) == 32)
        self.assertTrue(kfox == hashlib.md5(fox).hexdigest().lower())

    def test_delete(self):
        bs = FileBlockStore(dpath=self.d)
        self.cafeclosed(bs)


class ODataTests(BlockStoreCommon):

    def setUp(self):  # noqa
        path = os.path.join(DATA_DIR, 'blockstore.xml')
        self.doc = edmx.Document()
        with open(path, 'rb') as f:
            self.doc.Read(f)
        self.cdef = self.doc.root.DataServices['BlockSchema.BlockContainer']
        self.container = InMemoryEntityContainer(self.cdef)

    def test_init(self):
        bs = EDMBlockStore(entity_set=self.cdef['Blocks'])
        self.assertTrue(
            bs.max_block_size == MAX_BLOCK_SIZE,
            "default block size")
        self.assertTrue(
            bs.hash_class is hashlib.sha256,
            "default hash_class SHA256")

    def test_store(self):
        bs = EDMBlockStore(entity_set=self.cdef['Blocks'])
        self.fox_cafe(bs)

    def test_maxsize(self):
        bs = EDMBlockStore(entity_set=self.cdef['Blocks'], max_block_size=256)
        self.maxsize(bs)

    def test_hash(self):
        bs = EDMBlockStore(
            entity_set=self.cdef['Blocks'],
            hash_class=hashlib.md5)
        self.checkmd5(bs)

    def test_delete(self):
        bs = EDMBlockStore(entity_set=self.cdef['Blocks'])
        self.cafeclosed(bs)


class LockingTests(unittest.TestCase):

    def setUp(self):  # noqa
        path = os.path.join(DATA_DIR, 'blockstore.xml')
        self.doc = edmx.Document()
        with open(path, 'rb') as f:
            self.doc.Read(f)
        self.cdef = self.doc.root.DataServices['BlockSchema.BlockContainer']
        self.container = InMemoryEntityContainer(self.cdef)
        self.mt_lock = threading.Lock()
        self.mt_count = 0

    def test_init(self):
        ls = LockStore(entity_set=self.cdef['BlockLocks'])
        self.assertTrue(ls.lock_timeout == 180, "default lock timeout")

    def test_lock(self):
        ls = LockStore(entity_set=self.cdef['BlockLocks'])
        hash_key = hashlib.sha256('Lockme').hexdigest()
        hash_key2 = hashlib.sha256('andme').hexdigest()
        # locks are keyed
        ls.lock(hash_key2)
        # we can grab a lock, but now try again and it should fail
        ls.lock(hash_key)
        try:
            ls.lock(hash_key, timeout=1)
            self.fail("Expected timeout on acquire")
        except LockError:
            pass
        ls.unlock(hash_key)
        # unlocked it should work just fine
        ls.lock(hash_key, timeout=1)
        ls.unlock(hash_key)
        ls.unlock(hash_key2)
        # unlocking is benign - repeat and rinse
        ls.unlock(hash_key)
        ls.unlock(hash_key2)

    def test_lock2(self):
        # now turn the timeouts around, short locks, long waits
        ls = LockStore(entity_set=self.cdef['BlockLocks'],
                       lock_timeout=1)
        hash_key = hashlib.sha256('Lockme').hexdigest()
        ls.lock(hash_key)
        # now we should wait long enough to grab the lock again
        try:
            ls.lock(hash_key, timeout=5)
        except LockError:
            self.fail("Expected timeout on lock")
        ls.unlock(hash_key)

    def test_lock_multithread(self):
        ls = LockStore(entity_set=self.cdef['BlockLocks'],
                       lock_timeout=3)
        threads = []
        for i in xrange(50):
            threads.append(threading.Thread(target=self.lock_runner,
                                            args=(ls,)))
        for t in threads:
            t.start()
            time.sleep(1 if random.random() < 0.1 else 0)
        while threads:
            t = threads.pop()
            t.join()
        self.assertTrue(self.mt_count > 1)
        logging.info(
            "%i out of %i threads obtained the lock",
            self.mt_count, 50)

    def lock_runner(self, ls):
        hash_key = hashlib.sha256('Lockme').hexdigest()
        try:
            # by matching the lock_timeout we maximise risk of race
            # conditions
            ls.lock(hash_key, timeout=5)
        except LockError:
            logging.info("lock timeout during multithread test")
            return
        # we keep the lock for either 0 or 1s at random
        time.sleep(random.randint(0, 5))
        ls.unlock(hash_key)
        with self.mt_lock:
            self.mt_count += 1

    def test_context(self):
        # every lock/unlock pair needs a context object
        ls = LockStore(entity_set=self.cdef['BlockLocks'])
        hash_key = hashlib.sha256('Lockme').hexdigest()
        with ls.lock(hash_key):
            # do something
            pass
        try:
            ls.lock(hash_key, timeout=2)
        except LockError:
            self.fail("Context manager failed to unlock")


class StreamStoreTests(unittest.TestCase):

    def setUp(self):  # noqa
        path = os.path.join(DATA_DIR, 'blockstore.xml')
        self.doc = edmx.Document()
        with open(path, 'rb') as f:
            self.doc.Read(f)
        self.cdef = self.doc.root.DataServices['BlockSchema.BlockContainer']
        self.container = InMemoryEntityContainer(self.cdef)
        self.mt_lock = threading.Lock()
        self.mt_count = 0
        self.bs = EDMBlockStore(entity_set=self.cdef['Blocks'],
                                max_block_size=64)
        self.ls = LockStore(entity_set=self.cdef['BlockLocks'])

    def test_init(self):
        StreamStore(bs=self.bs, ls=self.ls, entity_set=self.cdef['Streams'])

    def test_store(self):
        ss = StreamStore(bs=self.bs, ls=self.ls,
                         entity_set=self.cdef['Streams'])
        with self.cdef['Streams'].OpenCollection() as streams,\
                self.cdef['BlockLists'].OpenCollection() as blocks:
            stream1 = streams.new_entity()
            stream1['mimetype'].SetFromValue("text/plain")
            now = TimePoint.FromNowUTC()
            stream1['created'].SetFromValue(now)
            stream1['modified'].SetFromValue(now)
            streams.insert_entity(stream1)
            stream2 = streams.new_entity()
            stream2['mimetype'].SetFromValue("text/plain")
            now = TimePoint.FromNowUTC()
            stream2['created'].SetFromValue(now)
            stream2['modified'].SetFromValue(now)
            streams.insert_entity(stream2)
            fox = "The quick brown fox jumped over the lazy dog"
            cafe = u"Caf\xe9".encode('utf-8')
            ss.store_block(stream1, 0, cafe)
            ss.store_block(stream1, 1, fox)
            ss.store_block(stream2, 0, cafe)
            self.assertTrue(len(blocks) == 3)
            blocks1 = list(ss.retrieve_blocklist(stream1))
            self.assertTrue(ss.retrieve_block(blocks1[0]) == cafe)
            self.assertTrue(ss.retrieve_block(blocks1[1]) == fox)
            blocks2 = list(ss.retrieve_blocklist(stream2))
            self.assertTrue(ss.retrieve_block(blocks2[0]) == cafe)
            ss.delete_blocks(stream1, 1)
            # should also have deleted fox from the block store
            self.assertTrue(len(blocks) == 2)
            try:
                ss.retrieve_block(blocks1[1])
                self.fail("Expected missing block")
            except BlockMissing:
                pass
            self.assertTrue(ss.retrieve_block(blocks1[0]) == cafe)
            ss.delete_blocks(stream1)
            self.assertTrue(len(blocks) == 1)
            self.assertTrue(ss.retrieve_block(blocks2[0]) == cafe)

    def test_create(self):
        ss = StreamStore(bs=self.bs, ls=self.ls,
                         entity_set=self.cdef['Streams'])
        s1 = ss.new_stream("text/plain")
        self.assertTrue(isinstance(s1, edm.Entity))
        self.assertTrue(s1['mimetype'].value == "text/plain")
        s2 = ss.new_stream(http.MediaType('text', 'plain',
                                          {'charset': ('charset', 'utf-8')}))
        self.assertTrue(isinstance(s2, edm.Entity))
        self.assertTrue(s2['mimetype'].value == "text/plain; charset=utf-8")
        skey1 = s1.Key()
        skey2 = s2.Key()
        s1 = ss.get_stream(skey1)
        self.assertTrue(isinstance(s1, edm.Entity))
        for i in xrange(10):
            try:
                ss.get_stream(i)
                self.assertTrue(i == skey1 or i == skey2)
            except KeyError:
                self.assertFalse(i == skey1 or i == skey2)

    def test_open_default(self):
        ss = StreamStore(bs=self.bs, ls=self.ls,
                         entity_set=self.cdef['Streams'])
        s1 = ss.new_stream("text/plain")
        self.assertTrue(s1['size'].value == 0)
        with ss.open_stream(s1) as s:
            self.assertTrue(isinstance(s, io.RawIOBase))
            self.assertFalse(s.closed)
            try:
                s.fileno()
                self.fail("streams do not have file numbers")
            except IOError:
                pass
            self.assertFalse(s.isatty())
            self.assertTrue(s.readable())
            self.assertFalse(s.writable())
            self.assertTrue(s.tell() == 0)
            self.assertTrue(s.seekable())
            # the stream is empty, so read should return EOF
            self.assertTrue(len(s.read()) == 0)

    def test_open_w_r(self):
        ss = StreamStore(bs=self.bs, ls=self.ls,
                         entity_set=self.cdef['Streams'])
        s1 = ss.new_stream("text/plain")
        with ss.open_stream(s1, 'w') as s:
            self.assertFalse(s.closed)
            self.assertFalse(s.readable())
            self.assertTrue(s.writable())
            self.assertTrue(s.tell() == 0)
            # try writing a multi-block string
            nbytes = 0
            fox = "The quick brown fox jumped over the lazy dog"
            cafe = u"Caf\xe9".encode('utf-8')
            data = fox + cafe + fox
            while nbytes < len(data):
                nbytes += s.write(data[nbytes:])
            self.assertTrue(s.tell() == nbytes)
        self.assertTrue(s1['size'].value == nbytes)
        with self.cdef['BlockLists'].OpenCollection() as blocks:
            # data should spill over to 2 blocks
            self.assertTrue(len(blocks) == 2)
        with ss.open_stream(s1, 'r') as s:
            self.assertFalse(s.closed)
            self.assertTrue(s.readable())
            self.assertFalse(s.writable())
            self.assertTrue(s.tell() == 0)
            rdata = s.read()
            self.assertTrue(rdata == data, "Read back %s" % repr(rdata))
            self.assertTrue(s.tell() == nbytes)


class BlockStoreContainer(SQLiteEntityContainer):

    def ro_name(self, source_path):
        # force auto numbering of primary keys
        if source_path == ('Streams', 'streamID'):
            return True
        elif source_path == ('BlockLists', 'blockID'):
            return True
        else:
            return super(BlockStoreContainer, self).ro_name(source_path)


class RandomStreamTests(unittest.TestCase):

    def setUp(self):  # noqa
        self.d = FilePath.mkdtemp('.d', 'pyslet-test_blockstore-')
        path = os.path.join(DATA_DIR, 'blockstore.xml')
        self.doc = edmx.Document()
        with open(path, 'rb') as f:
            self.doc.Read(f)
        self.cdef = self.doc.root.DataServices['BlockSchema.BlockContainer']
        self.block_size = random.randint(5, 100)
        logging.info("File block size: %i", self.block_size)
        self.f = self.d.join('blockstore.test').open('w+b')
        self.fox = (u"The quick brown fox jumped over the lazy dog "
                    u"Caf\xe9".encode('utf-8'))

    def tearDown(self):  # noqa
        self.f.close()
        self.d.rmtree(True)

    def random_rw(self):
        stream = self.ss.new_stream("text/plain; charset=utf-8")
        ssize = 0
        with self.ss.open_stream(stream, 'w+b') as sf:
            for i in xrange(100):
                pos = random.randint(0, ssize)
                nbytes = random.randint(0, len(self.fox))
                # read what we have
                sf.seek(pos)
                self.f.seek(pos)
                expectBytes = self.f.read(nbytes)
                gotBytes = ""
                while len(gotBytes) < nbytes:
                    newBytes = sf.read(nbytes - len(gotBytes))
                    if len(newBytes):
                        gotBytes = gotBytes + newBytes
                    else:
                        break
                logging.debug("Read @%i expected: %s", pos, repr(expectBytes))
                logging.debug("Read @%i received: %s", pos, repr(gotBytes))
                self.assertTrue(gotBytes == expectBytes)
                sf.seek(pos)
                wbytes = 0
                while wbytes < nbytes:
                    wbytes += sf.write(self.fox[wbytes:nbytes])
                self.f.seek(pos)
                self.f.write(self.fox[:nbytes])
                expectPos = self.f.tell()
                gotPos = sf.tell()
                logging.debug("Tell expected %i got %i after "
                              "writing %i bytes @%i", expectPos, gotPos, nbytes, pos)
                self.assertTrue(expectPos == gotPos)
                if expectPos > ssize:
                    ssize = expectPos
        stream = self.ss.get_stream(stream.Key())
        self.assertTrue(stream['size'].value == ssize)

    def test_mem_file(self):
        self.container = InMemoryEntityContainer(self.cdef)
        self.bs = FileBlockStore(dpath=self.d,
                                 max_block_size=self.block_size)
        self.ls = LockStore(entity_set=self.cdef['BlockLocks'])
        self.ss = StreamStore(bs=self.bs, ls=self.ls,
                              entity_set=self.cdef['Streams'])
        self.random_rw()

    def test_mem_mem(self):
        self.container = InMemoryEntityContainer(self.cdef)
        self.bs = EDMBlockStore(entity_set=self.cdef['Blocks'],
                                max_block_size=self.block_size)
        self.ls = LockStore(entity_set=self.cdef['BlockLocks'])
        self.ss = StreamStore(bs=self.bs, ls=self.ls,
                              entity_set=self.cdef['Streams'])
        self.random_rw()

    def test_sql_file(self):
        self.container = BlockStoreContainer(
            container=self.cdef,
            file_path=str(self.d.join('blockstore.db')))
        self.container.create_all_tables()
        self.bs = FileBlockStore(dpath=self.d,
                                 max_block_size=self.block_size)
        self.ls = LockStore(entity_set=self.cdef['BlockLocks'])
        self.ss = StreamStore(bs=self.bs, ls=self.ls,
                              entity_set=self.cdef['Streams'])
        self.random_rw()

    def test_sql_sql(self):
        self.container = BlockStoreContainer(
            container=self.cdef,
            file_path=str(self.d.join('blockstore.db')))
        self.container.create_all_tables()
        self.bs = EDMBlockStore(entity_set=self.cdef['Blocks'],
                                max_block_size=self.block_size)
        self.ls = LockStore(entity_set=self.cdef['BlockLocks'])
        self.ss = StreamStore(bs=self.bs, ls=self.ls,
                              entity_set=self.cdef['Streams'])
        self.random_rw()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(thread)d] %(levelname)s %(message)s")
    unittest.main()
