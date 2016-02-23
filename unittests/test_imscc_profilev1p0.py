#! /usr/bin/env python

import unittest

from tempfile import mkdtemp
import os
import os.path
import shutil


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(CCMiscTests, 'test'),
        unittest.makeSuite(CommonCartridgeTests, 'test'),
        unittest.makeSuite(CCConformanceTests, 'test')
    ))

from pyslet.imscc_profilev1p0 import *
import pyslet.imscpv1p2 as imscp


class CCMiscTests(unittest.TestCase):

    def testCaseConstants(self):
        self.assertTrue(CCOrganizationStructure == "rooted-hierarchy")
        self.assertTrue(CartridgeWebContentType == "webcontent")
        self.assertTrue(
            AssociatedContentType == "associatedcontent/imscc_xmlv1p0/learning-application-resource")
        self.assertTrue(DiscussionTopicContentType == "imsdt_xmlv1p0")
        self.assertTrue(WebLinkContentType == "imswl_xmlv1p0")
        self.assertTrue(
            AssessmentContentType == "imsqti_xmlv1p2/imscc_xmlv1p0/assessment")
        self.assertTrue(
            QuestionBankContentType == "imsqti_xmlv1p2/imscc_xmlv1p0/question-bank")


class CommonCartridgeTests(unittest.TestCase):

    def setUp(self):
        # make dataPath before we change directory (___file__ may be relative)
        self.dataPath = os.path.join(
            os.path.split(os.path.abspath(__file__))[0], 'data_imscc_profilev1p0')
        self.cwd = os.getcwd()
        self.cpList = []
        self.tmpPath = mkdtemp('.d', 'pyslet-test_imscpv1p2-')
        os.chdir(self.tmpPath)

    def tearDown(self):
        for cp in self.cpList:
            cp.Close()
        shutil.rmtree(self.tmpPath, True)
        os.chdir(self.cwd)

    def testCaseConstructor(self):
        cc = CommonCartridge()
        self.assertTrue(isinstance(cc.cp, imscp.ContentPackage))
        self.cpList.append(cc.cp)
        self.assertTrue(len(cc.laoTable.keys()) == 0)
        cc = CommonCartridge(os.path.join(self.dataPath, 'sample_1'))
        self.assertTrue(len(cc.laoTable.keys()) == 3)
        cp = imscp.ContentPackage(os.path.join(self.dataPath, 'sample_1'))
        self.cpList.append(cp)
        cc = CommonCartridge(cp)
        self.assertTrue(len(cc.laoTable.keys()) == 3)
        dList = map(lambda x: cc.laoTable[x][0], cc.laoTable.keys())
        dList.sort()
        self.assertTrue(dList == ['l0001', 'l0002', 'l0003'])
        # r6=cp.manifest.get_element_by_id('R0006')
        head, acr = cc.laoTable['R0006']
        self.assertTrue(acr is cp.manifest.get_element_by_id('R0007'))
        self.assertTrue(len(acr.File) == 3)

# Running tests on the cartridges on hold...


class CCConformanceTests(unittest.TestCase):

    def setUp(self):
        self.dataPath = os.path.join(
            os.path.split(os.path.abspath(__file__))[0], 'data_imscc_profilev1p0')
        self.cwd = os.getcwd()
        self.tmpPath = mkdtemp('.d', 'pyslet-test_imscpv1p2-')
        os.chdir(self.tmpPath)
        cp = imscp.ContentPackage(os.path.join(self.dataPath, 'sample_1'))
        cp.ExportToPIF('sample_1.zip')
        self.cc = CommonCartridge('sample_1.zip')

    def tearDown(self):
        self.cc.Close()
        shutil.rmtree(self.tmpPath, True)
        os.chdir(self.cwd)

    def testCasePass(self):
        self.RunTests([])

    def testCase1p4AssociatedContent_1(self):
        fPath = self.cc.cp.dPath.join('l0001', 'attachments', 'extra.txt')
        f = fPath.open('wb')
        f.write('Hello World!')
        f.close()
        self.cc.cp.RebuildFileTable()
        self.RunTests(['test1_4_AssociatedContent_1'])

    def testCase1p4AssociatedContent_2(self):
        fPath = self.cc.cp.dPath.join('Extra.txt')
        f = fPath.open('wb')
        f.write('Hello World!')
        f.close()
        r1 = self.cc.cp.manifest.get_element_by_id('R0004')
        f = r1.add_child(r1.FileClass)
        f.set_attribute('href', 'Extra.txt')
        self.cc.cp.RebuildFileTable()
        self.RunTests(['test1_4_AssociatedContent_2'])

    def testCase1p4AssociatedContent_3(self):
        r1 = self.cc.cp.manifest.get_element_by_id('R0004')
        dep = r1.add_child(r1.DependencyClass)
        dep.identifierref = 'R0001'
        self.RunTests(['test1_4_AssociatedContent_3'])

    def testCase1p4LAO_1(self):
        r3 = self.cc.cp.manifest.get_element_by_id('R0003')
        f = r3.File[0]
        self.cc.cp.DeleteFile('l0001/welcome.forum')
        self.RunTests(['test1_4_LAO_1'])

    def testCase1p4LAO_2(self):
        r3 = self.cc.cp.manifest.get_element_by_id('R0003')
        # Tricky, to prevent other tests failing we add a reference to a file already referenced
        # by the associated content for the resource.
        f = r3.add_child(r3.FileClass)
        f.set_attribute('href', 'l0001/welcome.gif')
        self.RunTests(['test1_4_LAO_2'])

    def testCase1p4LAO_3(self):
        r3 = self.cc.cp.manifest.get_element_by_id('R0003')
        r3.DeleteDependency(r3.Dependency[0])
        self.RunTests(['test1_4_LAO_3'])

    def testCase1p4LAO_4(self):
        r3 = self.cc.cp.manifest.get_element_by_id('R0003')
        d = r3.add_child(r3.DependencyClass)
        d.identifierref = 'R0007'
        self.RunTests(['test1_4_LAO_4'])

    def testCase1p4WebContent_1(self):
        r1 = self.cc.cp.manifest.get_element_by_id('R0001')
        f = r1.add_child(r1.FileClass)
        f.set_attribute('href', 'l0001/welcome.gif')
        self.RunTests(['test1_4_WebContent_1'])

    def RunTests(self, expectedFailures):
        ccp = CCTestSuite(self.cc)
        r = unittest.TestResult()
        ccp.run(r)
        # Cross check with the expected failures:
        fList = map(lambda x: x[0].id().split('.')[-1], r.failures)
        for e in r.errors:
            print e[1]
        fList.sort()
        if fList != expectedFailures:
            print
            print "%s : %s" % (self.id(), fList)
            print "Errors %s : %s" % (self.id(), expectedFailures)
            self.fail("CC Conformance test failures")

if __name__ == "__main__":
    # unittest.main()
    # we need can't use main because we don't want to pick up the the conformance tests
    # as they are designed to be run from within one of the other tests.
    unittest.TextTestRunner().run(suite())
