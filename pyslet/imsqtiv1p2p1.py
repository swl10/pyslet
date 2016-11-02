#! /usr/bin/env python
"""This module implements the QTI 1.2.1 specification defined by IMS GLC"""

import logging
import string
import codecs
import itertools
import os.path
from types import StringTypes

import pyslet.xml.structures as xml
import pyslet.xml.parser as xmlparser
import pyslet.imsmdv1p2p1 as imsmd
import pyslet.html401 as html
import pyslet.xml.xsdatatypes as xsi
import pyslet.rfc2396 as uri

from pyslet.qtiv1.core import *
from pyslet.qtiv1.common import *
from pyslet.qtiv1.item import *
from pyslet.qtiv1.section import *
from pyslet.qtiv1.assessment import *
from pyslet.qtiv1.objectbank import *
from pyslet.qtiv1.sao import *
from pyslet.qtiv1.outcomes import *
# from pyslet.qtiv1.main import *

# IMSQTI_NAMESPACE="http://www.imsglobal.org/xsd/ims_qtiasiv1p2"
QTI_SOURCE = 'QTIv1'


class QuesTestInterop(QTICommentContainer):

    """Outermost container for QTI content

    The <questestinterop> element is the outermost container for the QTI
    contents i.e. the container of the Assessment(s), Section(s) and
    Item(s)::

        <!ELEMENT questestinterop (qticomment? , (objectbank | assessment |
            (section | item)+))>"""

    XMLNAME = 'questestinterop'

    def __init__(self, parent):
        QTICommentContainer.__init__(self, parent)
        self.ObjectBank = None
        self.Assessment = None
        self.ObjectMixin = []

    def get_children(self):
        for child in QTICommentContainer.get_children(self):
            yield child
        if self.ObjectBank:
            yield self.ObjectBank
        elif self.Assessment:
            yield self.Assessment
        else:
            for child in self.ObjectMixin:
                yield child

    def MigrateV2(self):
        """Converts this element to QTI v2

        Returns a list of tuples of the form:
        ( <QTIv2 Document>, <Metadata>, <List of Log Messages> ).

        One tuple is returned for each of the objects found. In QTIv2 there is
        no equivalent of QuesTestInterop.  The baseURI of each document is set
        from the baseURI of the QuesTestInterop element using the object
        identifier to derive a file name."""
        output = []
        if self.ObjectBank:
            self.ObjectBank.MigrateV2(output)
        if self.Assessment:
            self.Assessment.MigrateV2(output)
        for obj in self.ObjectMixin:
            obj.MigrateV2(output)
        if self.QTIComment:
            if self.ObjectBank:
                # where to put the comment?
                pass
            elif self.Assessment:
                if len(self.ObjectMixin) == 0:
                    # Add this comment as a metadata description on the
                    # assessment
                    pass
            elif len(self.ObjectMixin) == 1:
                # Add this comment to this object's metdata description
                doc, lom, log = output[0]
                general = lom.LOMGeneral()
                description = general.add_child(general.DescriptionClass)
                descriptionString = description.add_child(
                    description.LangStringClass)
                descriptionString.set_value(self.QTIComment.get_value())
        return output


class QTIDocument(xml.Document):

    """Class for working with QTI documents."""

    def __init__(self, **args):
        """We turn off the parsing of external general entities to prevent a
        missing DTD causing the parse to fail.  This is a significant
        limitation as it is possible that some sophisticated users have used
        general entities to augment the specification or to define boiler-plate
        code.
        If this causes problems then you can turn the setting back on again for
        specific instances of the parser that will be used with that type of
        data."""
        xml.Document.__init__(self, **args)
        self.material = {}
        self.matThings = {}

    def XMLParser(self, entity):
        """Adds some options to the basic XMLParser to improve QTI
        compatibility."""
        p = xmlparser.XMLParser(entity)
        p.unicodeCompatibility = True
        return p

    classMap = {}

    def get_element_class(self, name):
        """Returns the class to use to represent an element with the given name.

        This method is used by the XML parser.  The class object is looked up
        in the classMap, if no specialized class is found then the general
        :py:class:`pyslet.xml.structures.Element` class is returned."""
        return QTIDocument.classMap.get(
            name, QTIDocument.classMap.get(None, xml.Element))

    def RegisterMatThing(self, matThing):
        """Registers a MatThing instance in the dictionary of matThings."""
        if matThing.label is not None:
            self.matThings[matThing.label] = matThing

    def UnregisterMatThing(self, mathThing):
        if (matThing.label is not None and
           matThing is self.matThings.get(matThing.label, None)):
            del self.matThings[matThing.label]

    def FindMatThing(self, linkRefID):
        """Returns the mat<thing> element with label matching the *linkRefID*.

        The specification says that material_ref should be used if you want to
        refer a material object, not matref, however this rule is not
        universally observed so if we don't find a basic mat<thing> we will
        search the material objects too and return a :py:class:`Material`
        instance instead."""
        matThing = self.matThings.get(linkRefID, None)
        if matThing is None:
            matThing = self.material.get(linkRefID, None)
        return matThing

    def RegisterMaterial(self, material):
        """Registers a Material instance in the dictionary of labelled material
        objects."""
        if material.label is not None:
            self.material[material.label] = material

    def UnregisterMaterial(self, material):
        if (material.label is not None and
           material is self.material.get(material.label, None)):
            del self.material[material.label]

    def FindMaterial(self, linkRefID):
        """Returns the material element with label matching *linkRefID*.

        Like :py:meth:`FindMatThing` this method will search for instances of
        :py:class:`MatThingMixin` if it can't find a :py:class:`Material`
        element to match.  The specification is supposed to be strict about
        matching the two types of reference but errors are common, even in the
        official example set."""
        material = self.material.get(linkRefID, None)
        if material is None:
            # We could this all in one line but in the future we might want
            # break out a stricter parsing mode here to help validate the
            # QTI v1 content.
            material = self.matThings.get(linkRefID, None)
        return material

    def MigrateV2(self, cp):
        """Converts the contents of this document to QTI v2

        The output is stored into the content package passed in cp.  Errors and
        warnings generated by the migration process are added as annotations to
        the resulting resource objects in the content package.

        The function returns a list of 4-tuples, one for each object migrated.

        Each tuple comprises ( <QTI v2 Document>, <LOM Metadata>, <log>,
        <Resource> )"""
        if isinstance(self.root, QuesTestInterop):
            logging.debug("Migrating QTI v1 file:\n%s", str(self.root))
            results = self.root.MigrateV2()
            # list of tuples ( <QTIv2 Document>, <Metadata>, <Log Messages> )
            newResults = []
            if results:
                # Make a directory to hold the files (makes it easier to find
                # unique names for media files)
                if isinstance(self.base_uri, uri.FileURL):
                    ignore, dname = os.path.split(self.base_uri.get_pathname())
                else:
                    dname = "questestinterop"
                dname, ext = os.path.splitext(dname)
                dname = cp.GetUniqueFile(dname)
                for doc, metadata, log in results:
                    logging.debug("\nQTIv2 Output:\n%s", str(doc))
                    if log:
                        # clean duplicate lines from the log then add as an
                        # annotation
                        logCleaner = {}
                        i = 0
                        while i < len(log):
                            if log[i] in logCleaner:
                                del log[i]
                            else:
                                logCleaner[log[i]] = i
                                i = i + 1
                        annotation = metadata.LOMAnnotation()
                        annotationMsg = string.join(log, ';\n')
                        logging.info(annotationMsg)
                        description = annotation.add_child(
                            imsmd.Description)
                        description.add_child(
                            description.LangStringClass).set_value(
                            annotationMsg)
                    r = doc.AddToContentPackage(cp, metadata, dname)
                    newResults.append((doc, metadata, log, r))
                cp.manifest.update()
            return newResults
        else:
            return []

xml.map_class_elements(QTIDocument.classMap, globals())


try:
    CNBIG5 = codecs.lookup('cn-big5')
    pass
except LookupError:
    CNBIG5 = None
    try:
        BIG5 = codecs.lookup('big5')
        CNBIG5 = codecs.CodecInfo(BIG5.encode, BIG5.decode,
                                  streamreader=BIG5.streamreader,
                                  streamwriter=BIG5.streamwriter,
                                  incrementalencoder=BIG5.incrementalencoder,
                                  incrementaldecoder=BIG5.incrementaldecoder,
                                  name='cn-big5')
    except LookupError:
        # we'll have to do without cn-big5
        pass

try:
    APPLESYMBOL = codecs.lookup('apple-symbol')
    pass
except LookupError:
    import pyslet.unicode_apple_symbol as symbol
    APPLESYMBOL = symbol.getregentry()


def QTICodecSearch(name):
    if name.lower() == "cn-big5" and CNBIG5:
        return CNBIG5
    elif name.lower() == "apple-symbol":
        return APPLESYMBOL


def RegisterCodecs():
    """The example files that are distributed with the QTI specification contain
    a set of Chinese examples encoded using big5.  However, the xml
    declarations on these files refer to the charset as "CN-BIG5" and this
    causes errors when parsing them as this is a non-standard way of refering
    to big5.

    QTI also requires use of the apple symbol font mapping for interpreting
    symbol-encoded maths text in questions."""
    codecs.register(QTICodecSearch)

# Force registration of codecs on module load
RegisterCodecs()

# Legacy function no longer needed


def FixupCNBig5():
    pass
