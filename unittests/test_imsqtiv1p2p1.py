#! /usr/bin/env python

import codecs
import io
import logging
import os
import os.path
import unittest

from pyslet import imscpv1p2 as imscp
from pyslet.qtiv1 import xml as qtiv1
from pyslet import rfc2396 as uri
from pyslet.py2 import dict_keys, range3
from pyslet.qtiv2 import xml as qtiv2
from pyslet.xml import structures as xml

try:
    import vobject
except ImportError:
    vobject = None


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(QTITests, 'test'),
        unittest.makeSuite(QTIElementTests, 'test'),
        unittest.makeSuite(QTIDocumentTests, 'test'),
        unittest.makeSuite(QTIV2ConversionTests, 'test')
    ))


class QTITests(unittest.TestCase):

    def test_constants(self):
        # self.assertTrue(
        #    IMSQTI_NAMESPACE=="http://www.imsglobal.org/xsd/ims_qtiasiv1p2",
        #    "Wrong QTI namespace: %s" % IMSQTI_NAMESPACE)
        pass

    def test_nc_name_fixup(self):
        self.assertTrue(qtiv1.core.MakeValidName("Simple") == "Simple")
        self.assertTrue(qtiv1.core.MakeValidName(":BadNCName") ==
                        ":BadNCName")
        self.assertTrue(qtiv1.core.MakeValidName("prefix:BadNCName") ==
                        "prefix:BadNCName")
        self.assertTrue(qtiv1.core.MakeValidName("_GoodNCName") ==
                        "_GoodNCName")
        self.assertTrue(qtiv1.core.MakeValidName("-BadName") == "_-BadName")
        self.assertTrue(qtiv1.core.MakeValidName(".BadName") == "_.BadName")
        self.assertTrue(qtiv1.core.MakeValidName("0BadName") == "_0BadName")
        self.assertTrue(qtiv1.core.MakeValidName("GoodName-0.12") ==
                        "GoodName-0.12")
        self.assertTrue(qtiv1.core.MakeValidName("BadName$") == "BadName_")
        self.assertTrue(qtiv1.core.MakeValidName("BadName+") == "BadName_")


class QTIElementTests(unittest.TestCase):

    def test_constructor(self):
        qtiv1.core.QTIElement(None)

    def test_ques_test_interop(self):
        e = qtiv1.QuesTestInterop(None)
        self.assertTrue(e.QTIComment is None)
        self.assertTrue(e.ObjectBank is None)
        self.assertTrue(e.Assessment is None)
        self.assertTrue(e.ObjectMixin == [])


EXAMPLE_1 = b"""<?xml version="1.0" encoding="utf-8"?>
<questestinterop></questestinterop>"""

EXAMPLE_2 = b"""<?xml version = "1.0" encoding = "UTF-8" standalone = "no"?>
<!DOCTYPE questestinterop SYSTEM "ims_qtiasiv1p2p1.dtd">
<questestinterop>
    <qticomment>Example2</qticomment>
    <item title = "Multiple Choice Item" ident = "EXAMPLE_002">
        <presentation label = "EXAMPLE_002">
            <flow>
                <material>
                    <mattext>What is the answer to the question?</mattext>
                </material>
                <response_lid ident = "RESPONSE" rcardinality = "Single"
                    rtiming = "No">
                    <render_choice shuffle = "Yes">
                        <flow_label>
                            <response_label ident = "A">
                                <material>
                                    <mattext>Yes</mattext>
                                </material>
                            </response_label>
                        </flow_label>
                        <flow_label>
                            <response_label ident = "B">
                                <material>
                                    <mattext>No</mattext>
                                </material>
                            </response_label>
                        </flow_label>
                        <flow_label>
                            <response_label ident = "C">
                                <material>
                                    <mattext>Maybe</mattext>
                                </material>
                            </response_label>
                        </flow_label>
                    </render_choice>
                </response_lid>
            </flow>
        </presentation>
    </item>
</questestinterop>"""


class QTIDocumentTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.cwd = os.getcwd()
        self.dataPath = os.path.join(
            os.path.split(__file__)[0], 'data_imsqtiv1p2p1')
        os.chdir(self.dataPath)

    def tearDown(self):     # noqa
        os.chdir(self.cwd)

    def test_constructor(self):
        doc = qtiv1.QTIDocument()
        self.assertTrue(isinstance(doc, xml.Document))

    def test_example1(self):
        doc = qtiv1.QTIDocument()
        doc.read(src=io.BytesIO(EXAMPLE_1))
        root = doc.root
        self.assertTrue(isinstance(root, qtiv1.QuesTestInterop))
        self.assertTrue(root.xmlname == 'questestinterop')

    def test_example2(self):
        doc = qtiv1.QTIDocument()
        doc.read(src=io.BytesIO(EXAMPLE_2))
        root = doc.root
        self.assertTrue(root.QTIComment.get_value() == 'Example2')
        objects = doc.root.ObjectMixin
        self.assertTrue(len(objects) == 1 and
                        isinstance(objects[0], qtiv1.item.Item))
        self.assertTrue(len(root.ObjectMixin) == 1)


class QTIV2ConversionTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.cwd = os.getcwd()
        self.dataPath = os.path.join(
            os.path.split(__file__)[0], 'data_imsqtiv1p2p1')
        self.cp = imscp.ContentPackage()

    def tearDown(self):     # noqa
        self.cp.Close()
        os.chdir(self.cwd)

    def test_output_v2(self):
        if vobject is None:
            logging.warn(
                "QTI v1 to v2 migration tests skipped: vobject required")
            return
        self.cp.manifest.root.set_id('outputv2')
        dpath = os.path.join(self.dataPath, 'input')
        flist = []
        for f in os.listdir(dpath):
            if self.cp.IgnoreFile(f):
                continue
            stem, ext = os.path.splitext(f)
            if ext.lower() == '.xml':
                flist.append(f)
        flist.sort()
        for f in flist:
            doc = qtiv1.QTIDocument(
                base_uri=str(uri.URI.from_path(os.path.join(dpath, f))))
            doc.read()
            doc.migrate_to_v2(self.cp)
        # Having migrated everything in the input folder, we now check
        # our CP against the output
        cp2 = imscp.ContentPackage(os.path.join(self.dataPath, 'outputv2'))
        # To do....
        # Compare the manifests
        # Compare each file
        flist1 = list(dict_keys(self.cp.fileTable))
        flist1.sort()
        flist2 = list(dict_keys(cp2.fileTable))
        flist2.sort()
        if flist1 != flist2:
            diagnosis = []
            for f in flist1:
                if f not in flist2:
                    diagnosis.append("Extra file found: %s" % f)
            for f in flist2:
                if f not in flist1:
                    diagnosis.append("Missing file: %s" % f)
            self.fail("File lists:\n  %s" % '\n  '.join(diagnosis))
        logging.debug(str(self.cp.manifest))
        logging.debug(str(cp2.manifest))
        output = self.cp.manifest.diff_string(cp2.manifest)
        self.assertTrue(self.cp.manifest.root == cp2.manifest.root,
                        "Manifests differ:\n%s" % output)
        for r in cp2.manifest.root.Resources.Resource:
            # Check the entry-point of each resource
            f = r.GetEntryPoint()
            if f:
                fpath = f.PackagePath(cp2)
                qti_doc = qtiv2.QTIDocument(
                    base_uri=str(
                        uri.URI.from_virtual_path(self.cp.dPath.join(fpath))))
                qti_doc.read()
                # logging.debug(str(qti_doc))
                qti_doc2 = qtiv2.QTIDocument(
                    base_uri=str(
                        uri.URI.from_virtual_path(cp2.dPath.join(fpath))))
                qti_doc2.read()
                # logging.debug(str(qti_doc2))
                output = qti_doc.diff_string(qti_doc2)
                result = (qti_doc.root == qti_doc2.root)
                if not result and output is None:
                    # This should not happen
                    self.print_pretty_weird(qti_doc.root, qti_doc2.root)
                self.assertTrue(
                    qti_doc.root == qti_doc2.root,
                    "QTI Files differ at %s (actual output shown first)\n%s" %
                    (fpath, output))
            for f in r.File:
                if f.href is None or f.href.is_absolute():
                    continue
                fpath = f.PackagePath(cp2)
                fabs_path = self.cp.dPath.join(fpath)
                fabs_path2 = cp2.dPath.join(fpath)
                base_uri = str(uri.URI.from_virtual_path(fabs_path))
                base_uri2 = str(
                    uri.URI.from_virtual_path(fabs_path2))
                if fabs_path.splitext()[1].lower() == '.xml':
                    # Two xml files, compare with simple XMLElement
                    doc = xml.Document(base_uri=base_uri)
                    doc.read()
                    doc2 = xml.Document(base_uri=base_uri2)
                    doc2.read()
                    output = doc.diff_string(doc2)
                    result = (doc.root == doc2.root)
                    if not result and output is None:
                        # This should not happen
                        self.print_pretty_weird(doc.root, doc2.root)
                    self.assertTrue(
                        doc.root == doc2.root,
                        "XML Files differ at %s "
                        "(actual output shown first)\n%s" % (fpath, output))
                else:
                    # Binary compare the two files.
                    f = fabs_path.open('rb')
                    f2 = fabs_path2.open('rb')
                    while True:
                        fdata = f.read(1024)
                        fdata2 = f2.read(1024)
                        self.assertTrue(fdata == fdata2,
                                        "Binary files don't match: %s" % fpath)
                        if not fdata:
                            break

    def print_pretty_weird(self, e1, e2):
        c1 = e1.get_canonical_children()
        c2 = e2.get_canonical_children()
        if len(c1) != len(c2):
            logging.debug(
                "Number of children mismatch in similar elements..."
                "\n>>>\n%s\n>>>\n%s\n>>>\n%s", repr(c1), repr(c2), str(e1))
            return
        for i in range3(len(c1)):
            if c1[i] != c2[i]:
                if isinstance(c1[i], xml.XMLElement) and \
                        isinstance(c2[i], xml.XMLElement):
                    self.print_pretty_weird(c1[i], c2[i])
                else:
                    logging.debug("Mismatch in similar elements..."
                                  "\n>>>\n%s\n>>>\n%s", repr(e1), repr(e2))


class QTIBig5Tests(unittest.TestCase):

    def test_big5(self):
        codecs.lookup('big5')
        try:
            codecs.lookup('CN-BIG5')
            pass
        except LookupError:
            self.fail("CN-BIG5 registration failed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
