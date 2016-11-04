#! /usr/bin/env python

from . import common
from ..xml import structures as xml


class ObjectBank(common.MetadataContainerMixin, common.QTICommentContainer):

    """This is the container for the Section(s) and/or Item(s) that are to be
    grouped as an object-bank. The object-bank is assigned its own unique
    identifier and can have the full set of QTI-specific meta-data::

    <!ELEMENT objectbank (qticomment? , qtimetadata* , (section | item)+)>
    <!ATTLIST objectbank  ident CDATA  #REQUIRED >"""
    XMLNAME = "objectbank"
    XMLATTR_ident = 'ident'
    XMLCONTENT = xml.ElementContent

    def __init__(self, parent):
        common.QTICommentContainer.__init__(self, parent)
        self.ident = None
        self.QTIMetadata = []
        self.ObjectMixin = []

    def migrate_to_v2(self, output):
        for sectionOrItem in self.ObjectMixin:
            sectionOrItem.migrate_to_v2(output)
