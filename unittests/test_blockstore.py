#! /usr/bin/env python

import unittest
import logging
import hashlib
import os.path

from pyslet.vfs import OSFilePath as FilePath
import pyslet.odata2.edmx as edmx
from pyslet.odata2.memds import InMemoryEntityContainer

from pyslet.blockstore import *     # noqa


def suite():
    loader = unittest.TestLoader()
    loader.testMethodPrefix = 'test'
    return unittest.TestSuite((
        loader.loadTestsFromTestCase(CoreTests),
        loader.loadTestsFromTestCase(FileTests),
        loader.loadTestsFromTestCase(ODataTests),
        loader.loadTestsFromTestCase(LockingTests),
        loader.loadTestsFromTestCase(StreamStoreTests)
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
        self.bs = EDMBlockStore(entity_set=self.cdef['Blocks'])
        self.ls = LockStore(entity_set=self.cdef['BlockLocks'])

    def test_init(self):
        ss = StreamStore(bs=self.bs, ls=self.ls,
                         entity_set=self.cdef['Streams'])

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
            ss.store_block(stream1, 0, fox)
            ss.store_block(stream1, 1, cafe)
            ss.store_block(stream2, 0, cafe)
            self.assertTrue(len(blocks) == 3)
            blocks1 = list(ss.retrieve_blocklist(stream1))
            self.assertTrue(ss.retrieve_block(blocks1[0]) == fox)
            self.assertTrue(ss.retrieve_block(blocks1[1]) == cafe)
            blocks2 = list(ss.retrieve_blocklist(stream2))
            self.assertTrue(ss.retrieve_block(blocks2[0]) == cafe)
            ss.delete(stream1)
            self.assertTrue(len(blocks) == 1)
            try:
                ss.retrieve_block(blocks1[0])
                self.fail("Expected missing block")
            except BlockMissing:
                pass
            self.assertTrue(ss.retrieve_block(blocks2[0]) == cafe)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(thread)d] %(levelname)s %(message)s")
    unittest.main()
