#! /usr/bin/env python

import unittest
from StringIO import StringIO
from codecs import encode


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

from pyslet.vfs import OSFilePath as FilePath

TEST_DATA_DIR = FilePath(
    FilePath(__file__).abspath().split()[0], 'data_imscpv1p2')

from pyslet.imscpv1p2 import *


class CPTests(unittest.TestCase):

    def testCaseConstants(self):
        self.assertTrue(IMSCP_NAMESPACE == "http://www.imsglobal.org/xsd/imscp_v1p1",
                        "Wrong CP namespace: %s" % IMSCP_NAMESPACE)
        self.assertTrue(IMSCPX_NAMESPACE == "http://www.imsglobal.org/xsd/imscp_extensionv1p2",
                        "Wrong extension namespace: %s" % IMSCPX_NAMESPACE)


class CPElementTests(unittest.TestCase):

    def testCaseConstructor(self):
        e = CPElement(None)

# class CPXElementTests(unittest.TestCase):
# 	def testCaseConstructor(self):
# 		e=CPXElement(None)
# 		self.assertTrue(e.ns==IMSCPX_NAMESPACE,'ns on construction')


EXAMPLE_1 = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns="http://www.imsglobal.org/xsd/imscp_v1p1" identifier="test"></manifest>"""

EXAMPLE_2 = """<manifest xmlns="http://www.imsglobal.org/xsd/imscp_v1p1" xmlns:imsmd="http://www.imsglobal.org/xsd/imsmd_v1p2" 
xmlns:imsqti="http://www.imsglobal.org/xsd/imsqti_v2p1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" identifier="MANIFEST-QTI-1" 
xsi:schemaLocation="http://www.imsglobal.org/xsd/imscp_v1p1 http://www.imsglobal.org/xsd/imscp_v1p1.xsd   
http://www.imsglobal.org/xsd/imsmd_v1p2 imsmd_v1p2p4.xsd  http://www.imsglobal.org/xsd/imsqti_v2p1 http://www.imsglobal.org/xsd/imsqti_v2p1.xsd">
	<organizations/>
	<resources>
		<resource identifier="choice" type="imsqti_item_xmlv2p1" href="choice.xml">
			<metadata>
				<imsmd:lom>
					<imsmd:general>
						<imsmd:identifier>qti_v2_item_01</imsmd:identifier>
						<imsmd:title>
							<imsmd:langstring xml:lang="en">Metadata Example Item #1</imsmd:langstring>
						</imsmd:title>
						<imsmd:description>
							<imsmd:langstring xml:lang="en">This is a dummy item</imsmd:langstring>
						</imsmd:description>
					</imsmd:general>
					<imsmd:lifecycle>
						<imsmd:version>
							<imsmd:langstring xml:lang="en">1.0.1</imsmd:langstring>
						</imsmd:version>
						<imsmd:status>
							<imsmd:source>
								<imsmd:langstring xml:lang="x-none">LOMv1.0</imsmd:langstring>
							</imsmd:source>
							<imsmd:value>
								<imsmd:langstring xml:lang="x-none">Draft</imsmd:langstring>
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

    def testCaseConstructor(self):
        doc = ManifestDocument()
        self.assertTrue(isinstance(doc, xmlns.XMLNSDocument))
        doc = ManifestDocument(root=Manifest)
        root = doc.root
        self.assertTrue(isinstance(root, Manifest))

    def testCaseExample1(self):
        doc = ManifestDocument()
        doc.Read(src=StringIO(EXAMPLE_1))
        root = doc.root
        self.assertTrue(isinstance(root, Manifest))
        self.assertTrue(
            root.ns == IMSCP_NAMESPACE and root.xmlname == 'manifest')
        self.assertTrue(root.id == 'test')

    def testCaseExample2(self):
        doc = ManifestDocument()
        doc.Read(src=StringIO(EXAMPLE_2))
        resources = doc.root.Resources
        self.assertTrue(
            len(resources.Resource) == 1 and isinstance(resources.Resource[0], Resource))
        manifest = doc.GetElementByID("MANIFEST-QTI-1")
        self.assertTrue(
            doc.root is manifest and isinstance(manifest, Manifest))
        resource = doc.GetElementByID("choice")
        self.assertTrue(resource is resources.Resource[0])

    def testCaseSetID(self):
        doc = ManifestDocument()
        doc.Read(src=StringIO(EXAMPLE_1))
        manifest = doc.GetElementByID("test")
        self.assertTrue(doc.root is manifest)
        manifest.SetID("manifest")
        self.assertTrue(
            doc.GetElementByID("test") is None, "Old identifier still declared")
        self.assertTrue(
            doc.GetElementByID("manifest") is manifest, "New identifier not declared")


class CPManifestTests(unittest.TestCase):

    def testCaseConstructor(self):
        m = Manifest(None)
        self.assertTrue(m.Metadata is None, "Metadata present on construction")
        self.assertTrue(isinstance(m.Organizations, Organizations),
                        "Organizations element required on construction")
        self.assertTrue(isinstance(m.Resources, Resources),
                        "Resources element required on construction")
        self.assertTrue(
            len(m.Manifest) == 0, "Child manifests present on construction")


class CPResourcesTests(unittest.TestCase):

    def testCaseConstructor(self):
        r = Resources(None)
        self.assertTrue(
            len(r.Resource) == 0, "Resource list not empty on constructio")

    def testCaseNewResource(self):
        doc = ManifestDocument(root=Manifest)
        resources = doc.root.Resources
        try:
            resource = resources.ChildElement(resources.ResourceClass)
            resource.SetID('resource#1')
            resource.type = 'imsqti_item_xmlv2p1'
            self.fail("Invalid Name for resource identifier")
        except xmlns.XMLIDValueError:
            pass
        resource.SetID('resource_1')
        resource.type = 'imsqti_item_xmlv2p1'
        self.assertTrue(isinstance(resource, Resource))
        self.assertTrue(doc.GetElementByID('resource_1') is resource)
        self.assertTrue(
            len(resources.Resource) == 1 and resources.Resource[0] is resource)


class CPResourceTests(unittest.TestCase):

    def testCaseConstructor(self):
        r = Resource(None)
        self.assertTrue(len(r.File) == 0, "File list not empty on constructio")
        self.assertTrue(
            len(r.Dependency) == 0, "Dependency list not empty on constructio")

    def testCaseNewFile(self):
        doc = ManifestDocument()
        doc.Read(src=StringIO(EXAMPLE_2))
        r = doc.GetElementByID('choice')
        index = len(r.File)
        f = r.ChildElement(r.FileClass)
        f.SetAttribute('href', 'Extra.txt')
        self.assertTrue(isinstance(f, File))
        self.assertTrue(len(r.File) == index + 1 and r.File[index] is f)

    def testCaseDeleteFile(self):
        doc = ManifestDocument()
        doc.Read(src=StringIO(EXAMPLE_2))
        r = doc.GetElementByID('choice')
        index = len(r.File)
        f = r.File[0]
        f1 = r.File[1]
        r.DeleteFile(f)
        self.assertTrue(len(r.File) == index - 1 and r.File[0] is f1)


class ContentPackageTests(unittest.TestCase):

    def setUp(self):
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

    def tearDown(self):
        self.cwd.chdir()
        for d in self.dList:
            d.rmtree(True)

    def testCaseConstructor(self):
        cp = ContentPackage()
        self.assertTrue(
            cp.dPath.isdir(), "Default constructor must create a temp directory")
        self.assertTrue(
            cp.GetPackageName() == 'imscp', "Default package name is not empty string")
        # Ensure the temporary directory is cleaned up
        self.dList.append(cp.dPath)
        url = uri.URI.from_octets(cp.manifest.GetBase())
        self.assertTrue(isinstance(cp.manifest, xmlns.XMLNSDocument) and isinstance(
            cp.manifest.root, Manifest), "Constructor must create manifest")
        self.assertTrue(
            url.get_virtual_file_path().split()[1] == 'imsmanifest.xml', "Manifest file name")
        self.assertTrue(isinstance(cp.manifest.root, Manifest),
                        "Constructor must create manifest element")
        id = cp.manifest.root.id
        self.assertTrue(cp.manifest.GetElementByID(
            id) is cp.manifest.root, "Manifest identifief not declared")
        self.assertTrue(
            url.get_virtual_file_path().isfile(), "Constructor must create manifest file")
        cp = ContentPackage('newpackage')
        self.assertTrue(cp.dPath.isdir() and FilePath(
            'newpackage').abspath() == cp.dPath, "Constructor creates specified directory")
        self.assertTrue(
            cp.GetPackageName() == 'newpackage', "Package name not taken from directory")
        cp = ContentPackage('package')
        self.assertTrue(FilePath('package').abspath() == cp.dPath,
                        "Constructor with existing directory, no manifest")
        cp = ContentPackage('mpackage')
        self.assertTrue(cp.manifest.root.id == "MANIFEST-QTI-1",
                        "Constructor with existing directory and manifest")
        self.assertTrue(
            cp.GetPackageName() == 'mpackage', "Package name wrongly affected by manifest")
        cp = ContentPackage(FilePath('mpackage', 'imsmanifest.xml'))
        self.assertTrue(cp.dPath.isdir() and FilePath('mpackage').abspath(
        ) == cp.dPath, "Constructor identifies pkg dir from manifest file")
        self.assertTrue(
            cp.manifest.root.id == "MANIFEST-QTI-1", "Constructor from manifest file")

    def testCaseUnicode(self):
        cp = ContentPackage(TEST_DATA_DIR.join('package_1'))
        resources = cp.manifest.root.Resources
        r = resources.Resource[0]
        self.assertTrue(len(r.File) == 1)
        f = r.File[0]
        self.assertTrue(isinstance(f, File) and str(
            f.href) == "%E8%8B%B1%E5%9B%BD.xml", "File path")
        doc = xmlns.Document(baseURI=f.ResolveURI(f.href))
        doc.Read()
        self.assertTrue(doc.root.xmlname == 'tag' and
                        doc.root.GetValue() == u"Unicode Test: \u82f1\u56fd")
        cp2 = ContentPackage(TEST_DATA_DIR.join(u'\u82f1\u56fd'))
        self.assertTrue(
            cp2.GetPackageName() == u'\u82f1\u56fd', "Unicode package name test")

    def testCaseZipRead(self):
        cp = ContentPackage(TEST_DATA_DIR.join('package_1.zip'))
        self.assertTrue(
            cp.dPath.isdir(), "Zip constructor must create a temp directory")
        # Ensure the temporary directory is cleaned up
        self.dList.append(cp.dPath)
        self.assertTrue(
            cp.GetPackageName() == 'package_1', "Zip extension not removed for name")
        resources = cp.manifest.root.Resources
        f = resources.Resource[0].File[0]
        doc = xmlns.Document(baseURI=f.ResolveURI(f.href))
        doc.Read()
        self.assertTrue(doc.root.xmlname == 'tag' and
                        doc.root.GetValue() == u"Unicode Test: \u82f1\u56fd")

    def testCaseZipWrite(self):
        cp = ContentPackage(TEST_DATA_DIR.join('package_1.zip'))
        self.dList.append(cp.dPath)
        cp.ExportToPIF('Package2.zip')
        cp2 = ContentPackage('Package2.zip')
        self.dList.append(cp2.dPath)
        resources = cp2.manifest.root.Resources
        f = resources.Resource[0].File[0]
        doc = xmlns.Document(baseURI=f.ResolveURI(f.href))
        doc.Read()
        self.assertTrue(doc.root.xmlname == 'tag' and
                        doc.root.GetValue() == u"Unicode Test: \u82f1\u56fd")

    def testCaseFileTable(self):
        cp = ContentPackage(TEST_DATA_DIR.join('package_3'))
        ft = cp.fileTable
        self.assertTrue(len(ft.keys()) == 6)
        self.assertTrue(len(ft[cp.FilePath('file_1.xml')]) == 2 and isinstance(
            ft[cp.FilePath('file_1.xml')][0], File))
        self.assertTrue(len(ft[cp.FilePath('file_4.xml')]) == 0, File)
        cp = ContentPackage(TEST_DATA_DIR.join('package_3'))
        cp.SetIgnoreFiles("\\..*|.*4.*")
        cp.RebuildFileTable()
        ft = cp.fileTable
        self.assertTrue(len(ft.keys()) == 5)

    def testCaseUniqueFile(self):
        cp = ContentPackage(TEST_DATA_DIR.join('package_3'))
        ft = cp.fileTable
        fPath = cp.GetUniqueFile('file_1.xml')
        self.assertFalse(fPath == 'file_1.xml', "file path must be unique")
        self.assertTrue(str(fPath)[-4:] == '.xml', "Must preserve extension")
        self.assertFalse(fPath in ft, "file path must not be in use")

    def testCaseDeleteFile(self):
        cp = ContentPackage(TEST_DATA_DIR.join('package_3'))
        cp.ExportToPIF('package_3.zip')
        cp2 = ContentPackage('package_3.zip')
        self.dList.append(cp2.dPath)
        r1 = cp2.manifest.GetElementByID('test1')
        r2 = cp2.manifest.GetElementByID('test2')
        r1Len = len(r1.File)
        r2Len = len(r2.File)
        cp2.DeleteFile('file_1.xml')
        self.assertTrue(len(r1.File) == r1Len - 1)
        self.assertTrue(len(r2.File) == r2Len - 1)

    def testCasePathInPath(self):
        goodPath = TEST_DATA_DIR.join('hello', 'world')
        self.assertTrue(
            PathInPath(goodPath, TEST_DATA_DIR) == FilePath('hello', 'world'))
        self.assertTrue(
            PathInPath(goodPath, TEST_DATA_DIR.join('hello')) == 'world')
        badPath = TEST_DATA_DIR.join('hello', 'worlds', 'bad')
        self.assertTrue(PathInPath(badPath, goodPath) is None, badPath)
        self.assertTrue(PathInPath(goodPath, goodPath) == '', "Match")
        self.assertTrue(
            PathInPath(TEST_DATA_DIR, goodPath) is None, "Path contains Path")

    def testCasePackagePaths(self):
        cp = ContentPackage(TEST_DATA_DIR.join('package_3'))
        goodPath = FilePath(cp.dPath, 'hello', 'world')
        self.assertTrue(cp.PackagePath(goodPath) == FilePath('hello', 'world'))
        badPath = TEST_DATA_DIR.join('package_3x', 'hello', 'world')
        self.assertTrue(cp.PackagePath(badPath) is None, badPath)
        badPath = TEST_DATA_DIR.join('package_x')
        self.assertTrue(cp.PackagePath(badPath) is None, badPath)
        badPath = TEST_DATA_DIR
        self.assertTrue(cp.PackagePath(badPath) is None, badPath)

    def testCaseCleanUp(self):
        cp = ContentPackage()
        dPath = cp.dPath
        self.assertTrue(dPath.isdir())
        cp.Close()
        self.assertTrue(cp.manifest is None, "Manifest not removed on close")
        self.assertFalse(dPath.isdir(), "Temp directory not deleted on close")
        cp = ContentPackage('package')
        dPath = cp.dPath
        self.assertTrue(dPath.isdir())
        cp.Close()
        self.assertTrue(cp.manifest is None, "Manifest not removed on close")
        self.assertTrue(dPath.isdir(), "Non-temp directory removed on close")


if __name__ == "__main__":
    unittest.main()
