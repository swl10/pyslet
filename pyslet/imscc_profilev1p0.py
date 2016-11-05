#! /usr/bin/env python
"""This module implements test to check against the IMSCC Profile 1.0
specification defined by IMS GLC"""

import logging
import unittest

from . import imscpv1p2 as imscp
from .pep8 import MigratedClass, old_method
from .py2 import is_text


CCOrganizationStructure = "rooted-hierarchy"
CartridgeWebContentType = "webcontent"
AssociatedContentType = ("associatedcontent/imscc_xmlv1p0/"
                         "learning-application-resource")
DiscussionTopicContentType = "imsdt_xmlv1p0"
WebLinkContentType = "imswl_xmlv1p0"
AssessmentContentType = "imsqti_xmlv1p2/imscc_xmlv1p0/assessment"
QuestionBankContentType = "imsqti_xmlv1p2/imscc_xmlv1p0/question-bank"


class CommonCartridge(MigratedClass):

    ContentPackageClass = imscp.ContentPackage

    def __init__(self, src=None):
        if is_text(src):
            self.cp = self.ContentPackageClass(src)
        elif isinstance(src, self.ContentPackageClass):
            self.cp = src
        elif src is None:
            self.cp = self.ContentPackageClass()
        else:
            raise ValueError
        self.scan_resources()

    @old_method('ScanResources')
    def scan_resources(self):
        """Scans the content package and builds lists of resources.

        Resources in Common Cartridge are either Cartridge Web Content
        resources, Learning Application Object (LAO) resources or an LAO's
        Associated Content resources.  Any other resources are treated as
        passengers."""
        self.cwcList = []
        self.laoTable = {}
        resources = self.cp.manifest.root.Resources
        # First pass is a search for CWCs and LAOs
        for r in resources.Resource:
            rtype = r.type
            if rtype == AssociatedContentType:
                # Associated content is linked from the LAO later
                continue
            if rtype == CartridgeWebContentType:
                self.cwcList.append(r)
                continue
            # All other resoure types are treated as LAOs
            if len(r.File) >= 1:
                lao_descriptor = r.File[0]
                fpath = lao_descriptor.PackagePath(self.cp)
                head, tail = fpath.split()
                if not head:
                    # The LAO must be in a directory, not at the top-level of
                    # the CP
                    head = None
            else:
                head = None
            # Is there associated content?
            acr = None
            dep_list = r.Dependency
            for dep in dep_list:
                rdep = self.cp.manifest.get_element_by_id(dep.identifierref)
                if (isinstance(rdep, imscp.Resource) and
                        rdep.type == AssociatedContentType):
                    acr = rdep
                    break
            self.laoTable[r.id] = [head, acr]

    @old_method('Close')
    def close(self):
        if self.cp:
            self.cp.Close()
        self.cp = None


class CCTestSuite(unittest.TestSuite):

    def __init__(self, cp):
        """This test suite requires an IMS Content Package to test"""
        unittest.TestSuite.__init__(self)
        loader = unittest.TestLoader()
        for tName in loader.getTestCaseNames(CCTestCase):
            self.addTest(CCTestCase(cp, tName))


class CCTestCase(unittest.TestCase):

    def __init__(self, cc, method):
        """We initialise the test case with the Common Cartridge being
        tested and the name of the method to call."""
        unittest.TestCase.__init__(self, method)
        self.cc = cc

    def test_1_4_associated_content_1(self):
        """A resource of the type associatedcontent must ...
        1. ...contain a file element for each file that exists in the directory
        that contains the associated Learning Application Object's descriptor
        file or any of its subdirectories."""
        for lao in self.cc.laoTable:
            lao_resource = self.cc.cp.manifest.get_element_by_id(lao)
            dpath, acr = self.cc.laoTable[lao]
            # acr must have a file element for all items in dpath
            fpaths = sorted(self.cc.cp.fileTable)
            for fpath in fpaths:
                if imscp.PathInPath(fpath, dpath):
                    flist = self.cc.cp.fileTable[fpath]
                    found_resource = False
                    for f in flist:
                        if f.parent is acr:
                            found_resource = True
                            break
                        elif f.parent is lao_resource:
                            found_resource = True
                            break
                    if not found_resource:
                        self.fail(fpath)

    def test_1_4_associated_content_2(self):
        """A resource of the type associatedcontent must ...
        2. It must not contain any references to files above the directory
        containing the associated Learning Application Object's descriptor
        file."""
        for lao in self.cc.laoTable:
            dpath, acr = self.cc.laoTable[lao]
            if acr is None:
                continue
            for f in acr.File:
                fpath = f.PackagePath(self.cc.cp)
                self.assertTrue(imscp.PathInPath(fpath, dpath))

    def test_1_4_associated_content_3(self):
        """A resource of the type associatedcontent must ...
        3. It must not contain any dependency elements."""
        for lao in self.cc.laoTable:
            dpath, acr = self.cc.laoTable[lao]
            if acr is None:
                continue
            self.assertFalse(len(acr.Dependency) > 0, acr.id)

    def test_1_4_lao_1(self):
        """A resource that represents a Learning Application Object has the
        following general restrictions:...
        1. It must contain a file element that points to the Learning
        Application Object's descriptor file."""
        for lao in self.cc.laoTable:
            lao_resource = self.cc.cp.manifest.get_element_by_id(lao)
            self.assertFalse(len(lao_resource.File) == 0)

    def test_1_4_lao_2(self):
        """A resource that represents a Learning Application Object has the
        following general restrictions:...
        2. It must not contain any other file elements."""
        for lao in self.cc.laoTable:
            lao_resource = self.cc.cp.manifest.get_element_by_id(lao)
            self.assertFalse(len(lao_resource.File) > 1)

    def get_acr_list_for_directory(self, dpath):
        """Returns a list of associated content resources that have file's
        that reside in dpath.  (Used internally.)"""
        acr_list = []
        fpaths = sorted(self.cc.cp.fileTable)
        for fpath in fpaths:
            if imscp.PathInPath(fpath, dpath):
                flist = self.cc.cp.fileTable[fpath]
                for f in flist:
                    if f.parent.type != AssociatedContentType:
                        continue
                    if f.parent in acr_list:
                        continue
                    acr_list.append(f.parent)
        return acr_list

    def test_1_4_lao_3(self):
        """A resource that represents a Learning Application Object has the
        following general restrictions:...
        3. If additional files exist in the directory containing the Learning
        Application Object's descriptor file, or any of its subdirectories, the
        resource must contain a dependency element that references the resource
        of type 'associatedcontent' which contains the references to these
        files."""
        for lao in self.cc.laoTable:
            lao_resource = self.cc.cp.manifest.get_element_by_id(lao)
            dpath, acr = self.cc.laoTable[lao]
            if dpath is None:  # this is a fail of a different sort
                continue
            acr_list = self.get_acr_list_for_directory(dpath)
            # Now we must have a dependency for each element of acr_list
            for d in lao_resource.Dependency:
                acr = self.cc.cp.manifest.get_element_by_id(d.identifierref)
                if acr in acr_list:
                    del acr_list[acr_list.index(acr)]
            self.assertFalse(len(acr_list))

    def test_1_4_lao_4(self):
        """A resource that represents a Learning Application Object has the
        following general restrictions:...
        4. It must not contain any other dependency elements of type
        'associatedcontent'."""
        for lao in self.cc.laoTable:
            lao_resource = self.cc.cp.manifest.get_element_by_id(lao)
            dpath, acr = self.cc.laoTable[lao]
            if dpath is None:  # this is a fail of a different sort
                continue
            acr_list = self.get_acr_list_for_directory(dpath)
            # The use of 'the' suggests that there must be only one such acr
            self.assertFalse(len(acr_list) > 1)
            if len(acr_list):
                # And hence all associated content dependencies in lao must be
                # to the single acr in this list.
                for d in lao_resource.Dependency:
                    acr = self.cc.cp.manifest.get_element_by_id(
                        d.identifierref)
                    if acr is None:
                        logging.info(d.identifierref)
                        logging.info(self.cc.cp.manifest.root)
                    if acr.type != AssociatedContentType:
                        continue
                    self.assertTrue(acr is acr_list[0])

    def test_1_4_web_content_1(self):
        """A resource of the type "webcontent" must comply with the following
        restrictions...
        1. It may contain a file element for any file that exists in the
        package so long as the file is not in a Learning Application Object
        directory or a subdirectory of any Learning Application Object
        directory."""
        dpath_list = []
        for lao in self.cc.laoTable:
            dpath, acr = self.cc.laoTable[lao]
            if dpath is not None:
                dpath_list.append(dpath)
        for wc in self.cc.cwcList:
            for f in wc.File:
                fpath = f.PackagePath(self.cc.cp)
                for dpath in dpath_list:
                    self.assertFalse(imscp.PathInPath(fpath, dpath))
