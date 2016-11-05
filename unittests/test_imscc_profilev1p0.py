#! /usr/bin/env python

import logging
import os
import os.path
import shutil
import unittest

from tempfile import mkdtemp

from pyslet import imscc_profilev1p0 as imscc
from pyslet import imscpv1p2 as imscp


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(CCMiscTests, 'test'),
        unittest.makeSuite(CommonCartridgeTests, 'test'),
        unittest.makeSuite(CCConformanceTests, 'test')
    ))


class CCMiscTests(unittest.TestCase):

    def test_constants(self):
        self.assertTrue(imscc.CCOrganizationStructure == "rooted-hierarchy")
        self.assertTrue(imscc.CartridgeWebContentType == "webcontent")
        self.assertTrue(
            imscc.AssociatedContentType ==
            "associatedcontent/imscc_xmlv1p0/learning-application-resource")
        self.assertTrue(imscc.DiscussionTopicContentType == "imsdt_xmlv1p0")
        self.assertTrue(imscc.WebLinkContentType == "imswl_xmlv1p0")
        self.assertTrue(imscc.AssessmentContentType ==
                        "imsqti_xmlv1p2/imscc_xmlv1p0/assessment")
        self.assertTrue(imscc.QuestionBankContentType ==
                        "imsqti_xmlv1p2/imscc_xmlv1p0/question-bank")


class CommonCartridgeTests(unittest.TestCase):

    def setUp(self):        # noqa
        # make dataPath before we change directory (___file__ may be relative)
        self.dataPath = os.path.join(
            os.path.split(os.path.abspath(__file__))[0],
            'data_imscc_profilev1p0')
        self.cwd = os.getcwd()
        self.cpList = []
        self.tmpPath = mkdtemp('.d', 'pyslet-test_imscpv1p2-')
        os.chdir(self.tmpPath)

    def tearDown(self):     # noqa
        for cp in self.cpList:
            cp.Close()
        shutil.rmtree(self.tmpPath, True)
        os.chdir(self.cwd)

    def test_constructor(self):
        cc = imscc.CommonCartridge()
        self.assertTrue(isinstance(cc.cp, imscp.ContentPackage))
        self.cpList.append(cc.cp)
        self.assertTrue(len(cc.laoTable) == 0)
        cc = imscc.CommonCartridge(os.path.join(self.dataPath, 'sample_1'))
        self.assertTrue(len(cc.laoTable) == 3)
        cp = imscp.ContentPackage(os.path.join(self.dataPath, 'sample_1'))
        self.cpList.append(cp)
        cc = imscc.CommonCartridge(cp)
        self.assertTrue(len(cc.laoTable) == 3)
        dlist = sorted([cc.laoTable[x][0] for x in cc.laoTable])
        self.assertTrue(dlist == ['l0001', 'l0002', 'l0003'])
        # r6=cp.manifest.get_element_by_id('R0006')
        head, acr = cc.laoTable['R0006']
        self.assertTrue(acr is cp.manifest.get_element_by_id('R0007'))
        self.assertTrue(len(acr.File) == 3)

# Running tests on the cartridges on hold...


class CCConformanceTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.dataPath = os.path.join(
            os.path.split(os.path.abspath(__file__))[0],
            'data_imscc_profilev1p0')
        self.cwd = os.getcwd()
        self.tmpPath = mkdtemp('.d', 'pyslet-test_imscpv1p2-')
        os.chdir(self.tmpPath)
        cp = imscp.ContentPackage(os.path.join(self.dataPath, 'sample_1'))
        cp.ExportToPIF('sample_1.zip')
        self.cc = imscc.CommonCartridge('sample_1.zip')

    def tearDown(self):     # noqa
        self.cc.Close()
        shutil.rmtree(self.tmpPath, True)
        os.chdir(self.cwd)

    def test_pass(self):
        self.run_tests([])

    def test_1p4_associated_content_1(self):
        fpath = self.cc.cp.dPath.join('l0001', 'attachments', 'extra.txt')
        f = fpath.open('wb')
        f.write(b'Hello World!')
        f.close()
        self.cc.cp.RebuildFileTable()
        self.run_tests(['test_1_4_associated_content_1'])

    def test_1p4_associated_content_2(self):
        fpath = self.cc.cp.dPath.join('Extra.txt')
        f = fpath.open('wb')
        f.write(b'Hello World!')
        f.close()
        r1 = self.cc.cp.manifest.get_element_by_id('R0004')
        f = r1.add_child(r1.FileClass)
        f.set_attribute('href', 'Extra.txt')
        self.cc.cp.RebuildFileTable()
        self.run_tests(['test_1_4_associated_content_2'])

    def test_1p4_associated_content_3(self):
        r1 = self.cc.cp.manifest.get_element_by_id('R0004')
        dep = r1.add_child(r1.DependencyClass)
        dep.identifierref = 'R0001'
        self.run_tests(['test_1_4_associated_content_3'])

    def test_1p4_lao1(self):
        r3 = self.cc.cp.manifest.get_element_by_id('R0003')
        r3.File[0]
        self.cc.cp.DeleteFile('l0001/welcome.forum')
        self.run_tests(['test_1_4_lao_1'])

    def test_1p4_lao2(self):
        r3 = self.cc.cp.manifest.get_element_by_id('R0003')
        # Tricky, to prevent other tests failing we add a reference to a
        # file already referenced by the associated content for the
        # resource.
        f = r3.add_child(r3.FileClass)
        f.set_attribute('href', 'l0001/welcome.gif')
        self.run_tests(['test_1_4_lao_2'])

    def test_1p4_lao3(self):
        r3 = self.cc.cp.manifest.get_element_by_id('R0003')
        r3.DeleteDependency(r3.Dependency[0])
        self.run_tests(['test_1_4_lao_3'])

    def test_1p4_lao4(self):
        r3 = self.cc.cp.manifest.get_element_by_id('R0003')
        d = r3.add_child(r3.DependencyClass)
        d.identifierref = 'R0007'
        self.run_tests(['test_1_4_lao_4'])

    def test_1p4_web_content_1(self):
        r1 = self.cc.cp.manifest.get_element_by_id('R0001')
        f = r1.add_child(r1.FileClass)
        f.set_attribute('href', 'l0001/welcome.gif')
        self.run_tests(['test_1_4_web_content_1'])

    def run_tests(self, expected_failures):
        ccp = imscc.CCTestSuite(self.cc)
        r = unittest.TestResult()
        ccp.run(r)
        # Cross check with the expected failures:
        flist = [x[0].id().split('.')[-1] for x in r.failures]
        for e in r.errors:
            logging.debug(e[1])
        flist.sort()
        if flist != expected_failures:
            logging.error("%s : %s", self.id(), flist)
            logging.error("Errors %s : %s", self.id(), expected_failures)
            self.fail("CC Conformance test failures")

if __name__ == "__main__":
    # unittest.main()
    # we need can't use main because we don't want to pick up the the
    # conformance tests as they are designed to be run from within one
    # of the other tests.
    logging.basicConfig(level=logging.DEBUG)
    unittest.TextTestRunner().run(suite())
