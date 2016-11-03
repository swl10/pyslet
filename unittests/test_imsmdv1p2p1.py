#! /usr/bin/env python

import io
import logging
import unittest

import pyslet.imscpv1p2 as imscp
import pyslet.imsmdv1p2p1 as imsmd


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(LRMTests, 'test'),
        unittest.makeSuite(LRMElementTests, 'test'),
        unittest.makeSuite(LRMEducationalTests, 'test'),
        unittest.makeSuite(LRMDocumentTests, 'test')
    ))


try:
    import pkg_resources
except ImportError:
    pkg_resources = None

if imsmd.vobject is None:
    logging.warning("""vobject tests skipped
    Try installing vobject from http://vobject.skyhouseconsulting.com/
        (vobject-0.8.1c) also requires http://labix.org/python-dateutil""")
elif pkg_resources:
    vv = pkg_resources.get_distribution("vobject").version
    dv = pkg_resources.get_distribution("python-dateutil").version
    if vv != '0.8.1c':
        logging.warning(
            "Designed for vobject-0.8.1c, testing with version %s", vv)
    if dv != '1.5':
        logging.warning(
            "Designed for python-dateutil-1.5, testing with version %s", dv)
else:
    logging.warning("""    Cannot determine vobject package version,
        install setuptools to remove this message""")


class LRMTests(unittest.TestCase):

    def test_constants(self):
        self.assertTrue(imsmd.IMSLRM_NAMESPACE ==
                        "http://www.imsglobal.org/xsd/imsmd_v1p2",
                        "Wrong LRM namespace: %s" % imsmd.IMSLRM_NAMESPACE)
        self.assertTrue(len(imsmd.IMSLRM_NAMESPACE_ALIASES) == 2)
        for alias in imsmd.IMSLRM_NAMESPACE_ALIASES:
            self.assertFalse(alias == imsmd.IMSLRM_NAMESPACE)
        self.assertTrue(
            imsmd.IMSLRM_SCHEMALOCATION ==
            "http://www.imsglobal.org/xsd/imsmd_v1p2p4.xsd",
            "LRM schemaLocation: %s" % imsmd.IMSLRM_SCHEMALOCATION)
        self.assertTrue(imsmd.LOM_SOURCE == "LOMv1.0", "LOM_SOURCE")

    def test_class_map(self):
        self.assertTrue(
            imsmd.get_element_class((imsmd.IMSLRM_NAMESPACE, 'lom')) is
            imsmd.LOM)
        for alias in imsmd.IMSLRM_NAMESPACE_ALIASES:
            self.assertTrue(imsmd.get_element_class((alias, 'lom')) is
                            imsmd.LOM)
        self.assertFalse(
            imsmd.get_element_class(('http://www.example.com/', 'lom')) is
            imsmd.LOM)
        self.assertTrue(
            imsmd.get_element_class(
                (imsmd.IMSLRM_NAMESPACE, 'x-undefined')) is imsmd.LRMElement)


class LRMElementTests(unittest.TestCase):

    def test_constructor(self):
        imsmd.LRMElement(None)
        # self.assertTrue(e.ns==imsmd.IMSLRM_NAMESPACE,'ns on construction')


EXAMPLE_1 = b"""<manifest
    xmlns="http://www.imsglobal.org/xsd/imscp_v1p1"
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


class LRMEducationalTests(unittest.TestCase):

    def test_description(self):
        """We have to deal with the LRM binding's lack of multiplicity
        on educational description. That means that we need method in
        lists of LangStrings that allow us to add language-tagged text
        to an existing list of langstrings."""
        edu = imsmd.LOMEducational(None)
        description = edu.add_child(imsmd.Description)
        hello = description.add_child(description.LangStringClass)
        hello.set_value("Hello")
        hello.set_lang('en-GB')
        ciao = description.add_child(description.LangStringClass)
        ciao.set_value("Ciao")
        ciao.set_lang('it')
        hello_test = description.GetLangString('en')
        self.assertTrue(hello_test.get_value() == 'Hello')
        ciao_test = description.GetLangString('it')
        self.assertTrue(ciao_test.get_value() == 'Ciao')
        ciao_test = description.GetLangString('it-IT')
        self.assertTrue(ciao_test.get_value() == 'Ciao')
        description.AddString('en', 'World')
        hello_test = description.GetLangString('en')
        self.assertTrue(hello_test.get_value() == 'Hello; World')
        description.AddString('fr', 'Bonjour')
        bonjour_test = description.GetLangString('fr')
        self.assertTrue(bonjour_test.get_value() == 'Bonjour')
        description.AddString(None, 'Hi')
        unknown_test = description.GetLangString(None)
        self.assertTrue(unknown_test.get_value() == 'Hi')


class LRMDocumentTests(unittest.TestCase):

    def test_example1(self):
        doc = imscp.ManifestDocument()
        doc.read(src=io.BytesIO(EXAMPLE_1))
        r = doc.get_element_by_id('choice')
        self.assertTrue(
            isinstance(list(r.Metadata.get_children())[0], imsmd.LOM), "LOM")

if __name__ == "__main__":
    unittest.main()
