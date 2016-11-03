#! /usr/bin/env python

import io
import unittest

import pyslet.imscpv1p2 as imscp
import pyslet.rfc2396 as uri

from pyslet.py2 import u8
from pyslet.vfs import OSFilePath as FilePath
from pyslet.xml import namespace as xmlns
from pyslet.xml import structures as xml


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(CPTests, 'test'),
        unittest.makeSuite(CPElementTests, 'test'),
        unittest.makeSuite(CPDocumentTests, 'test'),
        unittest.makeSuite(CPManifestTests, 'test'),
        unittest.makeSuite(CPResourcesTests, 'test'),
        unittest.makeSuite(CPResourceTests, 'test'),
        unittest.makeSuite(ContentPackageTests, 'test'),
    ))


TEST_DATA_DIR = FilePath(
    FilePath(__file__).abspath().split()[0], 'data_imscpv1p2')


class CPTests(unittest.TestCase):

    def test_constants(self):
        self.assertTrue(
            imscp.IMSCP_NAMESPACE == "http://www.imsglobal.org/xsd/imscp_v1p1",
            "Wrong CP namespace: %s" % imscp.IMSCP_NAMESPACE)
        self.assertTrue(
            imscp.IMSCPX_NAMESPACE ==
            "http://www.imsglobal.org/xsd/imscp_extensionv1p2",
            "Wrong extension namespace: %s" % imscp.IMSCPX_NAMESPACE)


class CPElementTests(unittest.TestCase):

    def test_constructor(self):
        imscp.CPElement(None)


EXAMPLE_1 = b"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns="http://www.imsglobal.org/xsd/imscp_v1p1"
    identifier="test"></manifest>"""

EXAMPLE_2 = b"""<manifest xmlns="http://www.imsglobal.org/xsd/imscp_v1p1"
    xmlns:imsmd="http://www.imsglobal.org/xsd/imsmd_v1p2"
    xmlns:imsqti="http://www.imsglobal.org/xsd/imsqti_v2p1"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    identifier="MANIFEST-QTI-1"
    xsi:schemaLocation="http://www.imsglobal.org/xsd/imscp_v1p1
        http://www.imsglobal.org/xsd/imscp_v1p1.xsd
        http://www.imsglobal.org/xsd/imsmd_v1p2 imsmd_v1p2p4.xsd
        http://www.imsglobal.org/xsd/imsqti_v2p1
        http://www.imsglobal.org/xsd/imsqti_v2p1.xsd">
    <organizations/>
    <resources>
        <resource identifier="choice" type="imsqti_item_xmlv2p1"
            href="choice.xml">
            <metadata>
                <imsmd:lom>
                    <imsmd:general>
                        <imsmd:identifier>qti_v2_item_01</imsmd:identifier>
                        <imsmd:title>
                            <imsmd:langstring xml:lang="en">Metadata
                                Example Item #1</imsmd:langstring>
                        </imsmd:title>
                        <imsmd:description>
                            <imsmd:langstring xml:lang="en">This is a
                                dummy item</imsmd:langstring>
                        </imsmd:description>
                    </imsmd:general>
                    <imsmd:lifecycle>
                        <imsmd:version>
                            <imsmd:langstring
                                xml:lang="en">1.0.1</imsmd:langstring>
                        </imsmd:version>
                        <imsmd:status>
                            <imsmd:source>
                                <imsmd:langstring
                                xml:lang="x-none">LOMv1.0</imsmd:langstring>
                            </imsmd:source>
                            <imsmd:value>
                                <imsmd:langstring
                                xml:lang="x-none">Draft</imsmd:langstring>
                            </imsmd:value>
                        </imsmd:status>
                    </imsmd:lifecycle>
                    <imsmd:metametadata>
                        <imsmd:metadatascheme>LOMv1.0</imsmd:metadatascheme>
                        <imsmd:metadatascheme>QTIv2.1</imsmd:metadatascheme>
                        <imsmd:language>en</imsmd:language>
                    </imsmd:metametadata>
                    <imsmd:technical>
                        <imsmd:format>text/x-imsqti-item-xml</imsmd:format>
                        <imsmd:format>image/png</imsmd:format>
                    </imsmd:technical>
                </imsmd:lom>
                <imsqti:qtiMetadata>
                    <imsqti:timeDependent>false</imsqti:timeDependent>
                    <imsqti:interactionType>choiceInteraction</imsqti:interactionType>
                    <imsqti:feedbackType>nonadaptive</imsqti:feedbackType>
                    <imsqti:solutionAvailable>true</imsqti:solutionAvailable>
                    <imsqti:toolName>XMLSPY</imsqti:toolName>
                    <imsqti:toolVersion>5.4</imsqti:toolVersion>
                    <imsqti:toolVendor>ALTOVA</imsqti:toolVendor>
                </imsqti:qtiMetadata>
            </metadata>
            <file href="choice.xml"/>
            <file href="images/sign.png"/>
        </resource>
    </resources>
</manifest>"""


class CPDocumentTests(unittest.TestCase):

    def test_constructor(self):
        doc = imscp.ManifestDocument()
        self.assertTrue(isinstance(doc, xmlns.XMLNSDocument))
        doc = imscp.ManifestDocument(root=imscp.Manifest)
        root = doc.root
        self.assertTrue(isinstance(root, imscp.Manifest))

    def test_example1(self):
        doc = imscp.ManifestDocument()
        doc.read(src=io.BytesIO(EXAMPLE_1))
        root = doc.root
        self.assertTrue(isinstance(root, imscp.Manifest))
        self.assertTrue(root.ns == imscp.IMSCP_NAMESPACE and
                        root.xmlname == 'manifest')
        self.assertTrue(root.id == 'test')

    def test_example2(self):
        doc = imscp.ManifestDocument()
        doc.read(src=io.BytesIO(EXAMPLE_2))
        resources = doc.root.Resources
        self.assertTrue(len(resources.Resource) == 1 and
                        isinstance(resources.Resource[0], imscp.Resource))
        manifest = doc.get_element_by_id("MANIFEST-QTI-1")
        self.assertTrue(doc.root is manifest and
                        isinstance(manifest, imscp.Manifest))
        resource = doc.get_element_by_id("choice")
        self.assertTrue(resource is resources.Resource[0])

    def test_set_i_d(self):
        doc = imscp.ManifestDocument()
        doc.read(src=io.BytesIO(EXAMPLE_1))
        manifest = doc.get_element_by_id("test")
        self.assertTrue(doc.root is manifest)
        manifest.set_id("manifest")
        self.assertTrue(doc.get_element_by_id("test") is None,
                        "Old identifier still declared")
        self.assertTrue(doc.get_element_by_id("manifest") is manifest,
                        "New identifier not declared")


class CPManifestTests(unittest.TestCase):

    def test_constructor(self):
        m = imscp.Manifest(None)
        self.assertTrue(m.Metadata is None, "Metadata present on construction")
        self.assertTrue(isinstance(m.Organizations, imscp.Organizations),
                        "Organizations element required on construction")
        self.assertTrue(isinstance(m.Resources, imscp.Resources),
                        "Resources element required on construction")
        self.assertTrue(len(m.Manifest) == 0,
                        "Child manifests present on construction")


class CPResourcesTests(unittest.TestCase):

    def test_constructor(self):
        r = imscp.Resources(None)
        self.assertTrue(len(r.Resource) == 0,
                        "Resource list not empty on constructio")

    def test_new_resource(self):
        doc = imscp.ManifestDocument(root=imscp.Manifest)
        resources = doc.root.Resources
        try:
            resource = resources.add_child(resources.ResourceClass)
            resource.set_id('resource#1')
            resource.type = 'imsqti_item_xmlv2p1'
            self.fail("Invalid Name for resource identifier")
        except xml.XMLIDValueError:
            pass
        resource.set_id('resource_1')
        resource.type = 'imsqti_item_xmlv2p1'
        self.assertTrue(isinstance(resource, imscp.Resource))
        self.assertTrue(doc.get_element_by_id('resource_1') is resource)
        self.assertTrue(len(resources.Resource) == 1 and
                        resources.Resource[0] is resource)


class CPResourceTests(unittest.TestCase):

    def test_constructor(self):
        r = imscp.Resource(None)
        self.assertTrue(len(r.File) == 0, "File list not empty on constructio")
        self.assertTrue(len(r.Dependency) == 0,
                        "Dependency list not empty on constructio")

    def test_new_file(self):
        doc = imscp.ManifestDocument()
        doc.read(src=io.BytesIO(EXAMPLE_2))
        r = doc.get_element_by_id('choice')
        index = len(r.File)
        f = r.add_child(r.FileClass)
        f.set_attribute('href', 'Extra.txt')
        self.assertTrue(isinstance(f, imscp.File))
        self.assertTrue(len(r.File) == index + 1 and r.File[index] is f)

    def test_delete_file(self):
        doc = imscp.ManifestDocument()
        doc.read(src=io.BytesIO(EXAMPLE_2))
        r = doc.get_element_by_id('choice')
        index = len(r.File)
        f = r.File[0]
        f1 = r.File[1]
        r.DeleteFile(f)
        self.assertTrue(len(r.File) == index - 1 and r.File[0] is f1)


class ContentPackageTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.cwd = FilePath.getcwd()
        self.dList = []
        self.d = FilePath.mkdtemp('.d', 'pyslet-test_imscpv1p2-')
        self.d.chdir()
        FilePath('package').mkdir()
        FilePath('mpackage').mkdir()
        mpath = FilePath('mpackage', 'imsmanifest.xml')
        f = mpath.open('wb')
        f.write(EXAMPLE_2)
        f.close()
        self.dList.append(self.d)

    def tearDown(self):     # noqa
        self.cwd.chdir()
        for d in self.dList:
            d.rmtree(True)

    def test_constructor(self):
        cp = imscp.ContentPackage()
        self.assertTrue(cp.dPath.isdir(),
                        "Default constructor must create a temp directory")
        self.assertTrue(cp.GetPackageName() == 'imscp',
                        "Default package name is not empty string")
        # Ensure the temporary directory is cleaned up
        self.dList.append(cp.dPath)
        url = uri.URI.from_octets(cp.manifest.get_base())
        self.assertTrue(isinstance(cp.manifest, xmlns.XMLNSDocument) and
                        isinstance(cp.manifest.root, imscp.Manifest),
                        "Constructor must create manifest")
        self.assertTrue(url.get_virtual_file_path().split()[1] ==
                        'imsmanifest.xml', "Manifest file name")
        self.assertTrue(isinstance(cp.manifest.root, imscp.Manifest),
                        "Constructor must create manifest element")
        id = cp.manifest.root.id
        self.assertTrue(cp.manifest.get_element_by_id(id) is cp.manifest.root,
                        "Manifest identifief not declared")
        self.assertTrue(url.get_virtual_file_path().isfile(),
                        "Constructor must create manifest file")
        cp = imscp.ContentPackage('newpackage')
        self.assertTrue(
            cp.dPath.isdir() and FilePath('newpackage').abspath() == cp.dPath,
            "Constructor creates specified directory")
        self.assertTrue(cp.GetPackageName() == 'newpackage',
                        "Package name not taken from directory")
        cp = imscp.ContentPackage('package')
        self.assertTrue(FilePath('package').abspath() == cp.dPath,
                        "Constructor with existing directory, no manifest")
        cp = imscp.ContentPackage('mpackage')
        self.assertTrue(cp.manifest.root.id == "MANIFEST-QTI-1",
                        "Constructor with existing directory and manifest")
        self.assertTrue(cp.GetPackageName() == 'mpackage',
                        "Package name wrongly affected by manifest")
        cp = imscp.ContentPackage(FilePath('mpackage', 'imsmanifest.xml'))
        self.assertTrue(
            cp.dPath.isdir() and FilePath('mpackage').abspath() == cp.dPath,
            "Constructor identifies pkg dir from manifest file")
        self.assertTrue(cp.manifest.root.id == "MANIFEST-QTI-1",
                        "Constructor from manifest file")

    def test_unicode(self):
        cp = imscp.ContentPackage(TEST_DATA_DIR.join('package_1'))
        resources = cp.manifest.root.Resources
        r = resources.Resource[0]
        self.assertTrue(len(r.File) == 1)
        f = r.File[0]
        self.assertTrue(isinstance(f, imscp.File) and
                        str(f.href) == "%E8%8B%B1%E5%9B%BD.xml", "File path")
        doc = xmlns.Document(baseURI=f.resolve_uri(f.href))
        doc.read()
        self.assertTrue(doc.root.xmlname == 'tag' and
                        doc.root.get_value() ==
                        u8(b'Unicode Test: \xe8\x8b\xb1\xe5\x9b\xbd'))
        cp2 = imscp.ContentPackage(
            TEST_DATA_DIR.join(u8(b'\xe8\x8b\xb1\xe5\x9b\xbd')))
        self.assertTrue(
            cp2.GetPackageName() == u8(b'\xe8\x8b\xb1\xe5\x9b\xbd'),
            "Unicode package name test")

    def test_zip_read(self):
        cp = imscp.ContentPackage(TEST_DATA_DIR.join('package_1.zip'))
        self.assertTrue(cp.dPath.isdir(),
                        "Zip constructor must create a temp directory")
        # Ensure the temporary directory is cleaned up
        self.dList.append(cp.dPath)
        self.assertTrue(cp.GetPackageName() == 'package_1',
                        "Zip extension not removed for name")
        resources = cp.manifest.root.Resources
        f = resources.Resource[0].File[0]
        doc = xmlns.Document(baseURI=f.resolve_uri(f.href))
        doc.read()
        self.assertTrue(doc.root.xmlname == 'tag' and
                        doc.root.get_value() ==
                        u8(b'Unicode Test: \xe8\x8b\xb1\xe5\x9b\xbd'))

    def test_zip_write(self):
        cp = imscp.ContentPackage(TEST_DATA_DIR.join('package_1.zip'))
        self.dList.append(cp.dPath)
        cp.ExportToPIF('Package2.zip')
        cp2 = imscp.ContentPackage('Package2.zip')
        self.dList.append(cp2.dPath)
        resources = cp2.manifest.root.Resources
        f = resources.Resource[0].File[0]
        doc = xmlns.Document(baseURI=f.resolve_uri(f.href))
        doc.read()
        self.assertTrue(doc.root.xmlname == 'tag' and
                        doc.root.get_value() ==
                        u8(b'Unicode Test: \xe8\x8b\xb1\xe5\x9b\xbd'))

    def test_file_table(self):
        cp = imscp.ContentPackage(TEST_DATA_DIR.join('package_3'))
        ft = cp.fileTable
        self.assertTrue(len(ft) == 6)
        self.assertTrue(
            len(ft[cp.FilePath('file_1.xml')]) == 2 and
            isinstance(ft[cp.FilePath('file_1.xml')][0], imscp.File))
        self.assertTrue(len(ft[cp.FilePath('file_4.xml')]) == 0, imscp.File)
        cp = imscp.ContentPackage(TEST_DATA_DIR.join('package_3'))
        cp.SetIgnoreFiles("\\..*|.*4.*")
        cp.RebuildFileTable()
        ft = cp.fileTable
        self.assertTrue(len(ft) == 5)

    def test_unique_file(self):
        cp = imscp.ContentPackage(TEST_DATA_DIR.join('package_3'))
        ft = cp.fileTable
        fpath = cp.GetUniqueFile('file_1.xml')
        self.assertFalse(fpath == 'file_1.xml', "file path must be unique")
        self.assertTrue(str(fpath)[-4:] == '.xml', "Must preserve extension")
        self.assertFalse(fpath in ft, "file path must not be in use")

    def test_delete_file(self):
        cp = imscp.ContentPackage(TEST_DATA_DIR.join('package_3'))
        cp.ExportToPIF('package_3.zip')
        cp2 = imscp.ContentPackage('package_3.zip')
        self.dList.append(cp2.dPath)
        r1 = cp2.manifest.get_element_by_id('test1')
        r2 = cp2.manifest.get_element_by_id('test2')
        r1_len = len(r1.File)
        r2_len = len(r2.File)
        cp2.DeleteFile('file_1.xml')
        self.assertTrue(len(r1.File) == r1_len - 1)
        self.assertTrue(len(r2.File) == r2_len - 1)

    def test_path_in_path(self):
        good_path = TEST_DATA_DIR.join('hello', 'world')
        self.assertTrue(imscp.PathInPath(good_path, TEST_DATA_DIR) ==
                        FilePath('hello', 'world'))
        self.assertTrue(
            imscp.PathInPath(good_path, TEST_DATA_DIR.join('hello')) ==
            'world')
        bad_path = TEST_DATA_DIR.join('hello', 'worlds', 'bad')
        self.assertTrue(imscp.PathInPath(bad_path, good_path) is None,
                        bad_path)
        self.assertTrue(imscp.PathInPath(good_path, good_path) == '', "Match")
        self.assertTrue(imscp.PathInPath(TEST_DATA_DIR, good_path) is None,
                        "Path contains Path")

    def test_package_paths(self):
        cp = imscp.ContentPackage(TEST_DATA_DIR.join('package_3'))
        good_path = FilePath(cp.dPath, 'hello', 'world')
        self.assertTrue(cp.PackagePath(good_path) ==
                        FilePath('hello', 'world'))
        bad_path = TEST_DATA_DIR.join('package_3x', 'hello', 'world')
        self.assertTrue(cp.PackagePath(bad_path) is None, bad_path)
        bad_path = TEST_DATA_DIR.join('package_x')
        self.assertTrue(cp.PackagePath(bad_path) is None, bad_path)
        bad_path = TEST_DATA_DIR
        self.assertTrue(cp.PackagePath(bad_path) is None, bad_path)

    def test_clean_up(self):
        cp = imscp.ContentPackage()
        dpath = cp.dPath
        self.assertTrue(dpath.isdir())
        cp.Close()
        self.assertTrue(cp.manifest is None, "Manifest not removed on close")
        self.assertFalse(dpath.isdir(), "Temp directory not deleted on close")
        cp = imscp.ContentPackage('package')
        dpath = cp.dPath
        self.assertTrue(dpath.isdir())
        cp.Close()
        self.assertTrue(cp.manifest is None, "Manifest not removed on close")
        self.assertTrue(dpath.isdir(), "Non-temp directory removed on close")


if __name__ == "__main__":
    unittest.main()
