#! /usr/bin/env python

import logging
from sys import maxunicode

from ..py2 import (
    character,
    dict_keys,
    dict_values,
    to_text,
    ul,
    uspace)
from ..rfc2396 import FileURL
from ..pep8 import PEP8Compatibility, old_function
from ..unicode5 import CharClass

from . import structures as xml


class XMLFatalError(xml.XMLError):

    """Raised by a fatal error in the parser."""
    pass


class XMLWellFormedError(XMLFatalError):

    """Raised by when a well-formedness error is encountered."""
    pass


class XMLForbiddenEntityReference(XMLFatalError):

    """Raised when a forbidden entity reference is encountered."""
    pass


if maxunicode < 0x10FFFF:
    char = CharClass(('\t', '\n'), '\r', (' ', character(0xD7FF)),
                     (character(0xE000), character(0xFFFD)))
else:
    char = CharClass(('\t', '\n'), '\r', (' ', character(0xD7FF)),
                     (character(0xE000), character(0xFFFD)),
                     (character(0x00010000), character(0x0010FFFF)))

is_char = char.test


if maxunicode < 0x10FFFF:
    discouraged = CharClass(
        (character(0x7F), character(0x84)),
        (character(0x86), character(0x9F)),
        (character(0xFDD0), character(0xFDEF)))
else:
    discouraged = CharClass(
        (character(0x7F), character(0x84)),
        (character(0x86), character(0x9F)),
        (character(0xFDD0), character(0xFDEF)),
        (character(0x0001FFFE), character(0x0001FFFF)),
        (character(0x0002FFFE), character(0x0002FFFF)),
        (character(0x0003FFFE), character(0x0003FFFF)),
        (character(0x0004FFFE), character(0x0004FFFF)),
        (character(0x0005FFFE), character(0x0005FFFF)),
        (character(0x0006FFFE), character(0x0006FFFF)),
        (character(0x0007FFFE), character(0x0007FFFF)),
        (character(0x0008FFFE), character(0x0008FFFF)),
        (character(0x0009FFFE), character(0x0009FFFF)),
        (character(0x000AFFFE), character(0x000AFFFF)),
        (character(0x000BFFFE), character(0x000BFFFF)),
        (character(0x000CFFFE), character(0x000CFFFF)),
        (character(0x000DFFFE), character(0x000DFFFF)),
        (character(0x000EFFFE), character(0x000EFFFF)),
        (character(0x000FFFFE), character(0x000FFFFF)),
        (character(0x0010FFFE), character(0x0010FFFF)))


def is_discouraged(c):
    """Tests if a character is discouraged in the specification.

    Note that this test will be limited by the range of unicode
    characters in narrow python builds."""
    return discouraged.test(c)


def is_white_space(data):
    """Tests if every character in *data* matches S"""
    for c in data:
        if not xml.is_s(c):
            return False
    return True


def contains_s(data):
    """Tests if data contains any S characters"""
    for c in data:
        if xml.is_s(c):
            return True
    return False


def strip_leading_s(data):
    """Returns data with all leading S removed."""
    s = 0
    for c in data:
        if xml.is_s(c):
            s += 1
        else:
            break
    if s:
        return data[s:]
    else:
        return data


def normalize_space(data):
    """Implements attribute value normalization

    Returns data normalized according to the further processing rules
    for attribute-value normalization:

        "...by discarding any leading and trailing space (#x20)
        characters, and by replacing sequences of space (#x20)
        characters by a single space (#x20) character"
    """
    result = []
    scount = 2  # 0=no space; 1=add space; 2=don't add space
    for c in data:
        if c == ' ':
            if scount == 0:
                scount = 1
        else:
            if scount == 1:
                result.append(' ')
            result.append(c)
            scount = 0
    return ''.join(result)


def is_valid_nmtoken(nm_token):
    """Tests if nm_token is a string matching production [5] Nmtoken"""
    if nm_token:
        for c in nm_token:
            if not xml.is_name_char(c):
                return False
        return True
    else:
        return False


pubid_char = CharClass(' ', character(0x0D), character(0x0A), ('0', '9'),
                       ('A', 'Z'), ('a', 'z'), "-'()+,./:=?;!*#@$_%")
is_pubid_char = pubid_char.test


base_char = CharClass(
    ('A', 'Z'), ('a', 'z'), (character(0xC0), character(0xD6)),
    (character(0xD8), character(0xF6)), (character(0xF8), character(0x0131)),
    (character(0x0134), character(0x013E)),
    (character(0x0141), character(0x0148)),
    (character(0x014A), character(0x017E)),
    (character(0x0180), character(0x01C3)),
    (character(0x01CD), character(0x01F0)),
    (character(0x01F4), character(0x01F5)),
    (character(0x01FA), character(0x0217)),
    (character(0x0250), character(0x02A8)),
    (character(0x02BB), character(0x02C1)), character(0x0386),
    (character(0x0388), character(0x038A)), character(0x038C),
    (character(0x038E), character(0x03A1)),
    (character(0x03A3), character(0x03CE)),
    (character(0x03D0), character(0x03D6)),
    character(0x03DA), character(0x03DC), character(0x03DE), character(0x03E0),
    (character(0x03E2), character(0x03F3)),
    (character(0x0401), character(0x040C)),
    (character(0x040E), character(0x044F)),
    (character(0x0451), character(0x045C)),
    (character(0x045E), character(0x0481)),
    (character(0x0490), character(0x04C4)),
    (character(0x04C7), character(0x04C8)),
    (character(0x04CB), character(0x04CC)),
    (character(0x04D0), character(0x04EB)),
    (character(0x04EE), character(0x04F5)),
    (character(0x04F8), character(0x04F9)),
    (character(0x0531), character(0x0556)), character(0x0559),
    (character(0x0561), character(0x0586)),
    (character(0x05D0), character(0x05EA)),
    (character(0x05F0), character(0x05F2)),
    (character(0x0621), character(0x063A)),
    (character(0x0641), character(0x064A)),
    (character(0x0671), character(0x06B7)),
    (character(0x06BA), character(0x06BE)),
    (character(0x06C0), character(0x06CE)),
    (character(0x06D0), character(0x06D3)),
    character(0x06D5), (character(0x06E5), character(0x06E6)),
    (character(0x0905), character(0x0939)), character(0x093D),
    (character(0x0958), character(0x0961)),
    (character(0x0985), character(0x098C)),
    (character(0x098F), character(0x0990)),
    (character(0x0993), character(0x09A8)),
    (character(0x09AA), character(0x09B0)), character(0x09B2),
    (character(0x09B6), character(0x09B9)),
    (character(0x09DC), character(0x09DD)),
    (character(0x09DF), character(0x09E1)),
    (character(0x09F0), character(0x09F1)),
    (character(0x0A05), character(0x0A0A)),
    (character(0x0A0F), character(0x0A10)),
    (character(0x0A13), character(0x0A28)),
    (character(0x0A2A), character(0x0A30)),
    (character(0x0A32), character(0x0A33)),
    (character(0x0A35), character(0x0A36)),
    (character(0x0A38), character(0x0A39)),
    (character(0x0A59), character(0x0A5C)),
    character(0x0A5E), (character(0x0A72), character(0x0A74)),
    (character(0x0A85), character(0x0A8B)), character(0x0A8D),
    (character(0x0A8F), character(0x0A91)),
    (character(0x0A93), character(0x0AA8)),
    (character(0x0AAA), character(0x0AB0)),
    (character(0x0AB2), character(0x0AB3)),
    (character(0x0AB5), character(0x0AB9)),
    character(0x0ABD), character(0x0AE0),
    (character(0x0B05), character(0x0B0C)),
    (character(0x0B0F), character(0x0B10)),
    (character(0x0B13), character(0x0B28)),
    (character(0x0B2A), character(0x0B30)),
    (character(0x0B32), character(0x0B33)),
    (character(0x0B36), character(0x0B39)),
    character(0x0B3D), (character(0x0B5C), character(0x0B5D)),
    (character(0x0B5F), character(0x0B61)),
    (character(0x0B85), character(0x0B8A)),
    (character(0x0B8E), character(0x0B90)),
    (character(0x0B92), character(0x0B95)),
    (character(0x0B99), character(0x0B9A)), character(0x0B9C),
    (character(0x0B9E), character(0x0B9F)),
    (character(0x0BA3), character(0x0BA4)),
    (character(0x0BA8), character(0x0BAA)),
    (character(0x0BAE), character(0x0BB5)),
    (character(0x0BB7), character(0x0BB9)),
    (character(0x0C05), character(0x0C0C)),
    (character(0x0C0E), character(0x0C10)),
    (character(0x0C12), character(0x0C28)),
    (character(0x0C2A), character(0x0C33)),
    (character(0x0C35), character(0x0C39)),
    (character(0x0C60), character(0x0C61)),
    (character(0x0C85), character(0x0C8C)),
    (character(0x0C8E), character(0x0C90)),
    (character(0x0C92), character(0x0CA8)),
    (character(0x0CAA), character(0x0CB3)),
    (character(0x0CB5), character(0x0CB9)),
    character(0x0CDE), (character(0x0CE0), character(0x0CE1)),
    (character(0x0D05), character(0x0D0C)),
    (character(0x0D0E), character(0x0D10)),
    (character(0x0D12), character(0x0D28)),
    (character(0x0D2A), character(0x0D39)),
    (character(0x0D60), character(0x0D61)),
    (character(0x0E01), character(0x0E2E)), character(0x0E30),
    (character(0x0E32), character(0x0E33)),
    (character(0x0E40), character(0x0E45)),
    (character(0x0E81), character(0x0E82)),
    character(0x0E84), (character(0x0E87), character(0x0E88)),
    character(0x0E8A), character(0x0E8D),
    (character(0x0E94), character(0x0E97)),
    (character(0x0E99), character(0x0E9F)),
    (character(0x0EA1), character(0x0EA3)),
    character(0x0EA5), character(0x0EA7),
    (character(0x0EAA), character(0x0EAB)),
    (character(0x0EAD), character(0x0EAE)),
    character(0x0EB0), (character(0x0EB2), character(0x0EB3)),
    character(0x0EBD), (character(0x0EC0), character(0x0EC4)),
    (character(0x0F40), character(0x0F47)),
    (character(0x0F49), character(0x0F69)),
    (character(0x10A0), character(0x10C5)),
    (character(0x10D0), character(0x10F6)), character(0x1100),
    (character(0x1102), character(0x1103)),
    (character(0x1105), character(0x1107)), character(0x1109),
    (character(0x110B), character(0x110C)),
    (character(0x110E), character(0x1112)), character(0x113C),
    character(0x113E), character(0x1140), character(0x114C), character(0x114E),
    character(0x1150), (character(0x1154), character(0x1155)),
    character(0x1159), (character(0x115F), character(0x1161)),
    character(0x1163), character(0x1165), character(0x1167), character(0x1169),
    (character(0x116D), character(0x116E)),
    (character(0x1172), character(0x1173)), character(0x1175),
    character(0x119E), character(0x11A8), character(0x11AB),
    (character(0x11AE), character(0x11AF)),
    (character(0x11B7), character(0x11B8)),
    character(0x11BA), (character(0x11BC), character(0x11C2)),
    character(0x11EB), character(0x11F0), character(0x11F9),
    (character(0x1E00), character(0x1E9B)),
    (character(0x1EA0), character(0x1EF9)),
    (character(0x1F00), character(0x1F15)),
    (character(0x1F18), character(0x1F1D)),
    (character(0x1F20), character(0x1F45)),
    (character(0x1F48), character(0x1F4D)),
    (character(0x1F50), character(0x1F57)), character(0x1F59),
    character(0x1F5B), character(0x1F5D),
    (character(0x1F5F), character(0x1F7D)),
    (character(0x1F80), character(0x1FB4)),
    (character(0x1FB6), character(0x1FBC)),
    character(0x1FBE), (character(0x1FC2), character(0x1FC4)),
    (character(0x1FC6), character(0x1FCC)),
    (character(0x1FD0), character(0x1FD3)),
    (character(0x1FD6), character(0x1FDB)),
    (character(0x1FE0), character(0x1FEC)),
    (character(0x1FF2), character(0x1FF4)),
    (character(0x1FF6), character(0x1FFC)), character(0x2126),
    (character(0x212A), character(0x212B)), character(0x212E),
    (character(0x2180), character(0x2182)),
    (character(0x3041), character(0x3094)),
    (character(0x30A1), character(0x30FA)),
    (character(0x3105), character(0x312C)),
    (character(0xAC00), character(0xD7A3)))

ideographic = CharClass(
    (character(0x4E00), character(0x9FA5)), character(0x3007),
    (character(0x3021), character(0x3029)))

letter = CharClass(base_char, ideographic)
is_letter = letter.test

is_base_char = base_char.test

is_ideographic = ideographic.test


combining_char = CharClass(
    (character(0x0300), character(0x0345)),
    (character(0x0360), character(0x0361)),
    (character(0x0483), character(0x0486)),
    (character(0x0591), character(0x05A1)),
    (character(0x05A3), character(0x05B9)),
    (character(0x05BB), character(0x05BD)),
    character(0x05BF), (character(0x05C1), character(0x05C2)),
    character(0x05C4), (character(0x064B), character(0x0652)),
    character(0x0670), (character(0x06D6), character(0x06E4)),
    (character(0x06E7), character(0x06E8)),
    (character(0x06EA), character(0x06ED)),
    (character(0x0901), character(0x0903)), character(0x093C),
    (character(0x093E), character(0x094D)),
    (character(0x0951), character(0x0954)),
    (character(0x0962), character(0x0963)),
    (character(0x0981), character(0x0983)), character(0x09BC),
    (character(0x09BE), character(0x09C4)),
    (character(0x09C7), character(0x09C8)),
    (character(0x09CB), character(0x09CD)), character(0x09D7),
    (character(0x09E2), character(0x09E3)), character(0x0A02),
    character(0x0A3C), (character(0x0A3E), character(0x0A42)),
    (character(0x0A47), character(0x0A48)),
    (character(0x0A4B), character(0x0A4D)),
    (character(0x0A70), character(0x0A71)),
    (character(0x0A81), character(0x0A83)), character(0x0ABC),
    (character(0x0ABE), character(0x0AC5)),
    (character(0x0AC7), character(0x0AC9)),
    (character(0x0ACB), character(0x0ACD)),
    (character(0x0B01), character(0x0B03)),
    character(0x0B3C), (character(0x0B3E), character(0x0B43)),
    (character(0x0B47), character(0x0B48)),
    (character(0x0B4B), character(0x0B4D)),
    (character(0x0B56), character(0x0B57)),
    (character(0x0B82), character(0x0B83)),
    (character(0x0BBE), character(0x0BC2)),
    (character(0x0BC6), character(0x0BC8)),
    (character(0x0BCA), character(0x0BCD)),
    character(0x0BD7), (character(0x0C01), character(0x0C03)),
    (character(0x0C3E), character(0x0C44)),
    (character(0x0C46), character(0x0C48)),
    (character(0x0C4A), character(0x0C4D)),
    (character(0x0C55), character(0x0C56)),
    (character(0x0C82), character(0x0C83)),
    (character(0x0CBE), character(0x0CC4)),
    (character(0x0CC6), character(0x0CC8)),
    (character(0x0CCA), character(0x0CCD)),
    (character(0x0CD5), character(0x0CD6)),
    (character(0x0D02), character(0x0D03)),
    (character(0x0D3E), character(0x0D43)),
    (character(0x0D46), character(0x0D48)),
    (character(0x0D4A), character(0x0D4D)),
    character(0x0D57), character(0x0E31),
    (character(0x0E34), character(0x0E3A)),
    (character(0x0E47), character(0x0E4E)),
    character(0x0EB1), (character(0x0EB4), character(0x0EB9)),
    (character(0x0EBB), character(0x0EBC)),
    (character(0x0EC8), character(0x0ECD)),
    (character(0x0F18), character(0x0F19)), character(0x0F35),
    character(0x0F37), character(0x0F39),
    (character(0x0F3E), character(0x0F3F)),
    (character(0x0F71), character(0x0F84)),
    (character(0x0F86), character(0x0F8B)),
    (character(0x0F90), character(0x0F95)), character(0x0F97),
    (character(0x0F99), character(0x0FAD)),
    (character(0x0FB1), character(0x0FB7)), character(0x0FB9),
    (character(0x20D0), character(0x20DC)), character(0x20E1),
    (character(0x302A), character(0x302F)),
    (character(0x3099), character(0x309A)))
is_combining_char = combining_char.test

digit = CharClass(
    ('0', '9'), (character(0x0660), character(0x0669)),
    (character(0x06F0), character(0x06F9)),
    (character(0x0966), character(0x096F)),
    (character(0x09E6), character(0x09EF)),
    (character(0x0A66), character(0x0A6F)),
    (character(0x0AE6), character(0x0AEF)),
    (character(0x0B66), character(0x0B6F)),
    (character(0x0BE7), character(0x0BEF)),
    (character(0x0C66), character(0x0C6F)),
    (character(0x0CE6), character(0x0CEF)),
    (character(0x0D66), character(0x0D6F)),
    (character(0x0E50), character(0x0E59)),
    (character(0x0ED0), character(0x0ED9)),
    (character(0x0F20), character(0x0F29)))
is_digit = digit.test

extender = CharClass(
    character(0xB7), (character(0x02D0), character(0x02D1)), character(0x0387),
    character(0x0640), character(0x0E46), character(0x0EC6), character(0x3005),
    (character(0x3031), character(0x3035)),
    (character(0x309D), character(0x309E)),
    (character(0x30FC), character(0x30FE)))
is_extender = extender.test


enc_name = CharClass('-', '.', ('0', '9'), ('A', 'Z'), '_', ('a', 'z'))
is_enc_name = enc_name.test

enc_name_start = CharClass(('A', 'Z'), ('a', 'z'))
is_enc_name_start = enc_name_start.test


@old_function('RegisterDocumentClass')
def register_doc_class(doc_class, root_name, public_id=None, system_id=None):
    XMLParser.register_doc_class(doc_class, root_name, public_id, system_id)


class ContentParticleCursor(object):

    """Used to traverse an element's content model.

    The cursor records its position within the content model by
    recording the list of particles that may represent the current child
    element. When the next start tag is found the particles' maps are
    used to change the position of the cursor.  The end of the content
    model is represented by a special entry that maps the empty string
    to None.

    If a start tag is found that doesn't have an entry in any of the
    particles' maps then the document is not valid.

    Note that this cursor is tolerant of non-deterministic models as it
    keeps track of all possible matching particles within the model."""

    START_STATE = 0     #: State constant representing the start state
    PARTICLE_STATE = 1  #: State constant representing a particle
    END_STATE = 2       #: State constant representing the end state

    def __init__(self, element_type):
        self.element_type = element_type
        self.state = ContentParticleCursor.START_STATE
        self.plist = []

    def next(self, name=''):
        """Called when a child element with *name* is encountered.

        Returns True if *name* is a valid element and advances the
        model.  If *name* is not valid then it returns False and the
        cursor is unchanged."""
        if self.state == ContentParticleCursor.START_STATE:
            if self.element_type.particle_map is not None:
                if name in self.element_type.particle_map:
                    self.plist = self.element_type.particle_map[name]
                    if self.plist is None:
                        self.state = ContentParticleCursor.END_STATE
                    else:
                        if not isinstance(self.plist, list):
                            self.plist = [self.plist]
                        self.state = ContentParticleCursor.PARTICLE_STATE
                    return True
                else:
                    return False
            elif self.element_type.content_type == xml.ElementType.ANY:
                # anything goes for an Any element, we stay in the start
                # state
                if not name:
                    self.state = ContentParticleCursor.END_STATE
                return True
            elif self.element_type.content_type in (
                    xml.ElementType.EMPTY, xml.ElementType.SGMLCDATA):
                # empty elements, or unparsed elements, can only get an
                # end tag
                if not name:
                    self.state = ContentParticleCursor.END_STATE
                    return True
                else:
                    return False
        elif self.state == ContentParticleCursor.PARTICLE_STATE:
            new_plist = []
            for p in self.plist:
                # go through all possible particles
                if name in p.particle_map:
                    ps = p.particle_map[name]
                    if ps is None:
                        # short cut to end state
                        new_plist = None
                        self.state = ContentParticleCursor.END_STATE
                        break
                    if isinstance(ps, list):
                        new_plist = new_plist + ps
                    else:
                        new_plist.append(ps)
            if new_plist is None or len(new_plist) > 0:
                # success if we got to the end state or have found
                # particles
                self.plist = new_plist
                return True
            else:
                return False
        else:
            # when in the end state everything is invalid
            return False

    def expected(self):
        """Sorted list of valid element names in the current state.

        If the closing tag is valid it appends a representation of the
        closing tag too, e.g., </element>.  If the cursor is in the end
        state an empty list is returned."""
        expected = {}
        end_tag = None
        if self.state == ContentParticleCursor.START_STATE:
            for name in dict_keys(self.element_type.particle_map):
                if name:
                    expected[name] = True
                else:
                    end_tag = "</%s>" % self.element_type.name
        elif self.state == ContentParticleCursor.PARTICLE_STATE:
            for p in self.plist:
                for name in dict_keys(p.particle_map):
                    if name:
                        expected[name] = True
                    else:
                        end_tag = "</%s>" % self.element_type.name
        result = sorted(dict_keys(expected))
        if end_tag:
            result.append(end_tag)
        return result


class XMLParser(PEP8Compatibility):

    """An XMLParser object

    entity
        The :py:class:`~pyslet.xml.structures.XMLEntity` to
        parse.

    XMLParser objects are used to parse entities for the constructs
    defined by the numbered productions in the XML specification.

    XMLParser has a number of optional attributes, all of which default
    to False. Attributes with names started 'check' increase the
    strictness of the parser.  All other parser flags, if set to True,
    will not result in a conforming XML processor."""

    _doc_class_table = {}
    """A dictionary mapping doctype parameters onto class objects.

    For more information about how this is used see
    :py:meth:`get_document_class` and :py:meth:`register_doc_class`."""

    @classmethod
    def register_doc_class(cls, doc_class, root_name, public_id=None,
                           system_id=None):
        """Registers a document class

        Internally XMLParser maintains a single table of document
        classes which can be used to identify the correct class to use
        to represent a document based on the information obtained from
        the DTD.

        doc_class
            the class object being registered, it must be derived from
            :py:class:`Document`

        root_name
            the name of the root element or None if this class can be
            used with any root element.

        public_id
            the optional public ID of the doctype, if None or omitted
            any doctype can be used with this document class.

        system_id
            the optional system ID of the doctype, if None or omitted
            (the usual case) the document class can match any system
            ID."""
        cls._doc_class_table[(root_name, public_id, system_id)] = doc_class

    #: Default constant used for setting :py:attr:`refMode`
    RefModeNone = 0

    #: Treat references as per "in Content" rules
    RefModeInContent = 1

    #: Treat references as per "in Attribute Value" rules
    RefModeInAttributeValue = 2

    #: Treat references as per "as Attribute Value" rules
    RefModeAsAttributeValue = 3

    #: Treat references as per "in EntityValue" rules
    RefModeInEntityValue = 4

    #: Treat references as per "in DTD" rules
    RefModeInDTD = 5

    PredefinedEntities = {
        'lt': '<',
        'gt': '>',
        'apos': "'",
        'quot': '"',
        'amp': '&'}
    """A mapping from the names of the predefined entities (lt, gt, amp,
    apos, quot) to their replacement characters."""

    def __init__(self, entity):
        PEP8Compatibility.__init__(self)
        self.check_validity = False
        """Checks XML validity constraints

        If *check_validity* is True, and all other options are left at
        their default (False) setting then the parser will behave as a
        validating XML parser."""
        #: whether or not to open external entities
        self.open_external_entities = False
        #: whether or not to open remote entities (i.e., via http(s))
        #: requires open_external_entities to be True
        self.open_remote_entities = False
        #: Flag indicating if the document is valid, only set if
        #: :py:attr:`check_validity` is True
        self.valid = None
        #: A list of non-fatal errors discovered during parsing, only
        #: populated if :py:attr:`check_validity` is True
        self.nonFatalErrors = []
        #: checks XML compatibility constraints; will cause
        #: :py:attr:`check_validity` to be set to True when parsing
        self.checkCompatibility = False
        #: checks all constraints; will cause :py:attr:`check_validity`
        #: and :py:attr:`checkCompatibility` to be set to True when
        #: parsing.
        self.checkAllErrors = False
        #: treats validity errors as fatal errors
        self.raiseValidityErrors = False
        #: provides a loose parser for XML-like documents
        self.dont_check_wellformedness = False
        #: See http://www.w3.org/TR/unicode-xml/
        self.unicodeCompatibility = False
        self.sgml_namecase_general = False
        """Option that simulates SGML's NAMECASE GENERAL YES

        Defaults to False for XML behaviour.  When True, literals within
        the document are treated as case insensitive.  Although the SGML
        specification refers to names being folded to uppercase, we actually
        fold to lower-case internally in keeping with XML common practice.

        Therefore, an attribute called 'NAME' will be treated as if it
        had been called 'name' in the document."""
        self.sgml_omittag = False
        """Option that simulates SGML's OMITTAG YES

        With ths option the parser will call
        :meth:`structures.Element.get_child_class` to determine if an
        element indicates a missing start or end tag."""
        #: option that simulates SGML's SHORTTAG YES
        self.sgml_shorttag = False
        """This option simulates the special attribute handling of the
        SGML shorttag feature.  If an attribute is declared without a
        value::

            <section title="Notes to Editor" hidden>

        then the tag is treated as if it had been written::

            <section title="Notes to Editor" hidden="hidden">

        In most cases this enables simple attribute mappings to be used,
        even if there are multiple possible tokens permissible, for
        example::

            class Book(Element):
                XMLATTR_hidden = 'visible'
                XMLATTR_shown = 'visible'

        Will result in the instance attribute *visible* being set to
        either 'hidden' or 'shown' even though the attribute name is
        minimized away with use of the shorttag feature.  This technique
        is used extensively in HTML where many attributes are declared
        using single-token #IMPLIED form, such as the disabled attribute
        of INPUT::

             disabled    (disabled)     #IMPLIED"""
        self.sgml_content = False
        """This option simulates some aspects of SGML content handling
        based on class attributes of the element being parsed.

        Element classes with XMLCONTENT=:py:data:`XMLEmpty` are treated
        as elements declared EMPTY, these elements are treated as if
        they were introduced with an empty element tag even if they
        weren't, as per SGML's rules.  Note that this SGML feature "has
        nothing to do with markup minimization" (i.e.,
        :py:attr:`sgml_omittag`.)"""
        self.refMode = XMLParser.RefModeNone
        """The current parser mode for interpreting references.

        XML documents can contain five different types of reference:
        parameter entity, internal general entity, external parsed
        entity, (external) unparsed entity and character entity.

        The rules for interpreting these references vary depending on
        the current mode of the parser, for example, in content a
        reference to an internal entity is replaced, but in the
        definition of an entity value it is not.  This means that the
        behaviour of the :py:meth:`parse_reference` method will differ
        depending on the mode.

        The parser takes care of setting the mode automatically but if
        you wish to use some of the parsing methods in isolation to
        parse fragments of XML documents, then you will need to set the
        *refMode* directly using one of the RefMode* family of constants
        defined above."""
        #: The current entity being parsed
        self.entity = entity
        self.entityStack = []
        if self.entity:
            #: the current character; None indicates end of stream
            self.the_char = self.entity.the_char
        else:
            self.the_char = None
        self.buff = []
        self.stagBuffer = None
        #: The declaration being parsed or None
        self.declaration = None
        #: The documnet type declaration of the document being parsed.
        #: This member is initialised to None as well-formed XML
        #: documents are not required to have an associated dtd.
        self.dtd = None
        #: The document being parsed
        self.doc = None
        #: The document entity
        self.docEntity = entity
        #: The current element being parsed
        self.element = None
        #: The element type of the current element
        self.elementType = None
        self.idTable = {}
        self.idRefTable = {}
        self.cursor = None
        self.dataCount = 0
        self.noPERefs = False
        self.gotPERef = False

    def get_context(self):
        """Returns the parser's context

        This is either the current element or the document if no element
        is being parsed."""
        if self.element is None:
            return self.doc
        else:
            return self.element

    def next_char(self):
        """Moves to the next character in the stream.

        The current character can always be read from
        :py:attr:`the_char`.  If there are no characters left in the
        current entity then entities are popped from an internal entity
        stack automatically."""
        if self.buff:
            self.buff = self.buff[1:]
        if self.buff:
            self.the_char = self.buff[0]
        else:
            self.entity.next_char()
            self.the_char = self.entity.the_char
            while self.the_char is None and self.entityStack:
                self.entity.close()
                self.entity = self.entityStack.pop()
                self.the_char = self.entity.the_char

    def buff_text(self, unused_chars):
        """Buffers characters that have already been parsed.

        unused_chars
            A string of characters to be pushed back to the parser in
            the order in which they are to be parsed.

        This method enables characters to be pushed back into the parser
        forcing them to be parsed next.  The current character is saved
        and will be parsed (again) once the buffer is exhausted."""
        if unused_chars:
            if self.buff:
                self.buff = list(unused_chars) + self.buff
            else:
                self.buff = list(unused_chars)
                if self.entity.the_char is not None:
                    self.buff.append(self.entity.the_char)
            self.the_char = self.buff[0]

    def _get_buff(self):
        if len(self.buff) > 1:
            return ''.join(self.buff[1:])
        else:
            return ''

    def push_entity(self, entity):
        """Starts parsing an entity

        entity
            An :py:class:`~pyslet.xml.structures.XMLEntity`
            instance which is to be parsed.

        :py:attr:`the_char` is set to the current character in the
        entity's stream.  The current entity is pushed onto an internal
        stack and will be resumed when this entity has been parsed
        completely.

        Note that in the degenerate case where the entity being pushed
        is empty (or is already positioned at the end of the file) then
        push_entity does nothing."""
        if entity.the_char is not None:
            self.entityStack.append(self.entity)
            self.entity = entity
            self.entity.flags = {}
            self.the_char = self.entity.the_char
        else:
            # Harsh but fair, if we had reason to believe that this
            # entity used UTF-16 but it was completely empty (not even a
            # BOM) then that is an error.
            self.check_encoding(entity, None)
        if entity.buff_text:
            self.buff_text(entity.buff_text)

    BOMRequired = {
        'utf_16': True,
        'utf-16': True,
        'u16': True,
        'utf16': True,
        'utf_16_be': True,
        'utf-16-be': True,
        'utf_16be': True,
        'utf-16be': True,
        'utf_16_le': True,
        'utf-16-le': True,
        'utf_16le': True,
        'utf-16le': True}

    EncodingNotRequired = {
        'utf_16': True,
        'utf-16': True,
        'u16': True,
        'utf16': True,
        'utf_16_be': True,
        'utf-16-be': True,
        'utf_16be': True,
        'utf-16be': True,
        'utf_16_le': True,
        'utf-16-le': True,
        'utf_16le': True,
        'utf-16le': True,
        'utf_8': True,
        'utf-8': True,
        'u8': True,
        'utf': True,
        'utf8': True}

    def check_encoding(self, entity, declared_encoding):
        """Checks the entity against the declared encoding

        entity
            An :py:class:`~pyslet.xml.structures.XMLEntity`
            instance which is being parsed.

        declared_encoding
            A string containing the declared encoding in any declaration
            or None if there was no declared encoding in the entity."""
        if not self.EncodingNotRequired.get(entity.encoding.lower(), False):
            # Encoding required!
            if declared_encoding is None:
                self.processing_error(
                    "Encoding declaration required in %s (%s) but missing" %
                    (entity.get_name(), entity.encoding))
        if self.BOMRequired.get(entity.encoding.lower(), False):
            if not (entity.bom or
                    (declared_encoding and
                     declared_encoding.lower() == 'iso-10646-ucs-2')):
                self.processing_error(
                    "Byte order mark required in %s (%s) was missing" %
                    (entity.get_name(), entity.encoding))

    def get_external_entity(self):
        """Returns the external entity currently being parsed.

        If no external entity is being parsed then None is returned."""
        if self.entity.is_external():
            return self.entity
        else:
            i = len(self.entityStack)
            while i:
                i = i - 1
                e = self.entityStack[i]
                if e.is_external():
                    return e
        return None

    def standalone(self):
        """True if the document should be treated as standalone.

        A document may be declared standalone or it may effectively be
        standalone due to the absence of a DTD, or the absence of an
        external DTD subset and parameter entity references."""
        if self.declared_standalone():
            return True
        if self.dtd is None or self.dtd.external_id is None:
            # no dtd or just an internal subset
            return not self.gotPERef

    def declared_standalone(self):
        """True if the current document was declared standalone."""
        return self.declaration and self.declaration.standalone

    def well_formedness_error(
            self,
            msg="well-formedness error",
            error_class=XMLWellFormedError):
        """Raises an XMLWellFormedError error.

        msg
            An optional message string

        error_class
            an optional error class which must be a class object derived
            from py:class:`XMLWellFormednessError`.

        Called by the parsing methods whenever a well-formedness
        constraint is violated.

        The method raises an instance of *error_class* and does not
        return.  This method can be overridden by derived parsers to
        implement more sophisticated error logging."""
        raise error_class("%s: %s" % (self.entity.get_position_str(), msg))

    def validity_error(self, msg="validity error",
                       error=xml.XMLValidityError):
        """Called when the parser encounters a validity error.

        msg
            An optional message string

        error
            An optional error class or instance which must be a (class)
            object derived from py:class:`XMLValidityError`.

        The behaviour varies depending on the setting of the
        :py:attr:`check_validity` and :py:attr:`raiseValidityErrors`
        options. The default (both False) causes validity errors to be
        ignored.  When checking validity an error message is logged to
        :py:attr:`nonFatalErrors` and :py:attr:`valid` is set to False.
        Furthermore, if :py:attr:`raiseValidityErrors` is True *error*
        is raised (or a new instance of *error* is raised) and parsing
        terminates.

        This method can be overridden by derived parsers to implement
        more sophisticated error logging."""
        if self.check_validity:
            self.valid = False
            if isinstance(error, xml.XMLValidityError):
                self.nonFatalErrors.append(
                    "%s: %s (%s)" %
                    (self.entity.get_position_str(), msg, str(error)))
                if self.raiseValidityErrors:
                    raise error
            elif issubclass(error, xml.XMLValidityError):
                msg = "%s: %s" % (self.entity.get_position_str(), msg)
                self.nonFatalErrors.append(msg)
                if self.raiseValidityErrors:
                    raise error(msg)
            else:
                raise TypeError(
                    "validity_error expected class or instance of "
                    "XMLValidityError (found %s)" % repr(error))

    def compatibility_error(self, msg="compatibility error"):
        """Called when the parser encounters a compatibility error.

        msg
            An optional message string

        The behaviour varies depending on the setting of the
        :py:attr:`checkCompatibility` flag.  The default (False) causes
        compatibility errors to be ignored.  When checking compatibility
        an error message is logged to :py:attr:`nonFatalErrors`.

        This method can be overridden by derived parsers to implement
        more sophisticated error logging."""
        if self.checkCompatibility:
            self.nonFatalErrors.append(
                "%s: %s" % (self.entity.get_position_str(), msg))

    def processing_error(self, msg="Processing error"):
        """Called when the parser encounters a general processing error.

        msg
            An optional message string

        The behaviour varies depending on the setting of the
        :py:attr:`checkAllErrors` flag.  The default (False) causes
        processing errors to be ignored.  When checking all errors an
        error message is logged to :py:attr:`nonFatalErrors`.

        This method can be overridden by derived parsers to implement
        more sophisticated error logging."""
        if self.checkAllErrors:
            self.nonFatalErrors.append(
                "%s: %s" % (self.entity.get_position_str(), msg))

    def parse_literal(self, match):
        """Parses an optional literal string.

        match
            The literal string to match

        Returns True if *match* is successfully parsed and False
        otherwise. There is no partial matching, if *match* is not found
        then the parser is left in its original position."""
        match_len = 0
        for m in match:
            if m != self.the_char and (not self.sgml_namecase_general or
                                       self.the_char is None or
                                       m.lower() != self.the_char.lower()):
                self.buff_text(match[:match_len])
                break
            match_len += 1
            self.next_char()
        return match_len == len(match)

    def parse_required_literal(self, match, production="Literal String"):
        """Parses a required literal string.

        match
            The literal string to match

        production
            An optional string describing the context in which the
            literal was expected.

        There is no return value.  If the literal is not matched a
        wellformed error is generated."""
        if not self.parse_literal(match):
            self.well_formedness_error("%s: Expected %s" % (production, match))

    def parse_decimal_digits(self):
        """Parses a, possibly empty, string of decimal digits.

        Decimal digits match [0-9].  Returns the parsed digits as a
        string or an *empty string* if no digits were matched."""
        data = []
        while self.the_char is not None and self.the_char in "0123456789":
            data.append(self.the_char)
            self.next_char()
        return ''.join(data)

    def parse_required_decimal_digits(self, production="Digits"):
        """Parses a required sring of decimal digits.

        production
            An optional string describing the context in which the
            decimal digits were expected.

        Decimal digits match [0-9].  Returns the parsed digits as a
        string."""
        digits = self.parse_decimal_digits()
        if not digits:
            self.well_formedness_error(production + ": Expected [0-9]+")
        return digits

    def parse_hex_digits(self):
        """Parses a, possibly empty, string of hexadecimal digits

        Hex digits match [0-9a-fA-F].  Returns the parsed digits as a
        string or an *empty string* if no digits were matched."""
        data = []
        while (self.the_char is not None and
                self.the_char in "0123456789abcdefABCDEF"):
            data.append(self.the_char)
            self.next_char()
        return ''.join(data)

    def parse_required_hex_digits(self, production="Hex Digits"):
        """Parses a required string of hexadecimal digits.

        production
            An optional string describing the context in which the
            hexadecimal digits were expected.

        Hex digits match [0-9a-fA-F].  Returns the parsed digits as a
        string."""
        digits = self.parse_hex_digits()
        if not digits:
            self.well_formedness_error(production + ": Expected [0-9a-fA-F]+")
        return digits

    def parse_quote(self, q=None):
        """Parses the quote character

        q
            An optional character to parse as if it were a quote. By
            default either one of "'" or '"' is accepted.

        Returns the character parsed or raises a well formed error."""
        if q:
            if self.the_char == q:
                self.next_char()
                return q
            else:
                self.well_formedness_error("Expected %s" % q)
        elif self.the_char == '"' or self.the_char == "'":
            q = self.the_char
            self.next_char()
            return q
        else:
            self.well_formedness_error("Expected '\"' or \"'\"")

    def parse_document(self, doc=None):
        """[1] document: parses a Document.

        doc
            The :py:class:`~pyslet.xml.structures.Document`
            instance that will be parsed.  The declaration, dtd and
            elements are added to this document.  If *doc* is None then
            a new instance is created using
            :py:meth:`get_document_class` to identify the correct class
            to use to represent the document based on information in the
            prolog or, if the prolog lacks a declaration, the root
            element.

        This method returns the document that was parsed, an instance of
        :py:class:`~pyslet.xml.structures.Document`."""
        self.refMode == XMLParser.RefModeInContent
        self.doc = doc
        if self.checkAllErrors:
            self.checkCompatibility = True
        if self.checkCompatibility:
            self.check_validity = True
        if self.check_validity:
            self.valid = True
        else:
            self.valid = None
        self.nonFatalErrors = []
        self.parse_prolog()
        if self.doc is None:
            if self.dtd.name is not None:
                # create the document based on information in the DTD
                self.doc = self.get_document_class(self.dtd)()
                # set the document's dtd
                self.doc.dtd = self.dtd
        elif self.doc.dtd is None:
            # override the document's DTD
            self.doc.dtd = self.dtd
        self.parse_element()
        if self.check_validity:
            for idref in dict_keys(self.idRefTable):
                if idref not in self.idTable:
                    self.validity_error(
                        "IDREF: %s does not match any ID attribute value")
        self.parse_misc()
        if self.the_char is not None and not self.dont_check_wellformedness:
            self.well_formedness_error(
                "Unparsed characters in entity after document: %s" %
                repr(
                    self.the_char))
        return self.doc

    def get_document_class(self, dtd):
        """Returns a class object suitable for this dtd

        dtd
            A :py:class:`~pyslet.xml.structures.XMLDTD` instance

        Returns a *class* object derived from
        :py:class:`~pyslet.xml.structures.Document` suitable for
        representing a document with the given document type declaration.

        In cases where no doctype declaration is made a dummy
        declaration is created based on the name of the root element.
        For example, if the root element is called "database" then the
        dtd is treated as if it was declared as follows::

            <!DOCTYPE database>

        This default implementation uses the following three pieces of
        information to locate a class registered with
        :py:func:`~pyslet.xml.structures.register_doc_class`.
        The PublicID, SystemID and the name of the root element.  If an
        exact match is not found then wildcard matches are attempted,
        ignoring the SystemID, PublicID and finally the root element in
        turn.  If a document class still cannot be found then wildcard
        matches are tried matching *only* the PublicID, SystemID and
        root element in turn.

        If no document class cab be found,
        :py:class:`~pyslet.xml.structures.Document` is
        returned."""
        root_name = dtd.name
        if dtd.external_id is None:
            public_id = None
            system_id = None
            doc_class = XMLParser._doc_class_table.get(
                (root_name, None, None), None)
        else:
            public_id = dtd.external_id.public
            system_id = dtd.external_id.system
            doc_class = XMLParser._doc_class_table.get(
                (root_name, public_id, system_id), None)
            if doc_class is None:
                doc_class = XMLParser._doc_class_table.get(
                    (root_name, public_id, None), None)
            if doc_class is None:
                doc_class = XMLParser._doc_class_table.get(
                    (root_name, None, system_id), None)
            if doc_class is None:
                doc_class = XMLParser._doc_class_table.get(
                    (None, public_id, system_id), None)
            if doc_class is None:
                doc_class = XMLParser._doc_class_table.get(
                    (None, public_id, None), None)
            if doc_class is None:
                doc_class = XMLParser._doc_class_table.get(
                    (None, None, system_id), None)
            if doc_class is None:
                doc_class = XMLParser._doc_class_table.get(
                    (root_name, None, None), None)
        if doc_class is None:
            doc_class = xml.Document
        return doc_class

    # Production [2] is implemented with the function is_char

    def is_s(self):
        """Tests if the current character matches S

        Returns a boolean value, True if S is matched.

        By default calls :py:func:`~pyslet.xml.structures.is_s`

        In Unicode compatibility mode the function maps the unicode
        white space characters at code points 2028 and 2029 to line feed
        and space respectively."""
        if self.unicodeCompatibility:
            if self.the_char == character(0x2028):
                self.the_char = "\n"
            elif self.the_char == character(0x2029):
                self.the_char = ' '
        return xml.is_s(self.the_char)

    def parse_s(self):
        """[3] S

        Parses white space returning it as a string.  If there is no
        white space at the current position then an *empty string* is
        returned.

        The productions in the specification do not make explicit
        mention of parameter entity references, they are covered by the
        general statement that "Parameter entity references are
        recognized anwhere in the DTD..." In practice, this means that
        while parsing the DTD, anywhere that an S is permitted a
        parameter entity reference may also be recognized.  This method
        implements this behaviour, recognizing parameter entity
        references within S when :py:attr:`refMode` is
        :py:attr:`RefModeInDTD`."""
        s = []
        slen = 0
        while True:
            if self.is_s():
                s.append(self.the_char)
                self.next_char()
            elif (self.the_char == '%' and
                    self.refMode == XMLParser.RefModeInDTD):
                self.next_char()
                if xml.is_name_start_char(self.the_char):
                    self.parse_pe_reference(True)
                else:
                    # '%' followed by anything other than name start is
                    # not a reference.
                    self.buff_text('%')
                    break
            elif self.unicodeCompatibility:
                if self.the_char == character(0x2028):
                    s.append('\n')
                elif self.the_char == character(0x2029):
                    s.append(' ')
                else:
                    break
            else:
                break
            slen += 1
        return ''.join(s)

    def parse_required_s(self, production="[3] S"):
        """[3] S: Parses required white space

        production
            An optional string describing the production being parsed.
            This allows more useful errors than simply 'expected [3]
            S' to be logged.

        If there is no white space then a well-formedness error is
        raised."""
        if not self.parse_s() and not self.dont_check_wellformedness:
            self.well_formedness_error(
                production + ": Expected white space character")

    # Production [4] is implemented with the function is_name_start_char
    # Production [4a] is implemented with the function is_name_char.

    def parse_name(self):
        """[5] Name

        Parses an optional name.  The name is returned as a unicode
        string.  If no Name can be parsed then None is returned."""
        name = []
        if xml.is_name_start_char(self.the_char):
            name.append(self.the_char)
            self.next_char()
            while xml.is_name_char(self.the_char):
                name.append(self.the_char)
                self.next_char()
        if name:
            return ''.join(name)
        else:
            return None

    def parse_required_name(self, production="Name"):
        """[5] Name

        production
            An optional string describing the production being parsed.
            This allows more useful errors than simply 'expected [5]
            Name' to be logged.

        Parses a required Name, returning it as a string.  If no name
        can be parsed then a well-formed error is raised."""
        name = self.parse_name()
        if name is None:
            self.well_formedness_error(production + ": Expected NameStartChar")
        return name

    def parse_names(self):
        """[6] Names

        This method returns a tuple of unicode strings.  If no names can
        be parsed then None is returned."""
        names = []
        name = self.parse_name()
        if name is None:
            return None
        names.append(name)
        while self.the_char == uspace:
            self.next_char()
            name = self.parse_name()
            if name is None:
                self.buff_text(uspace)
                break
            names.append(name)
        if names:
            return names
        else:
            return None

    def parse_nmtoken(self):
        """[7] Nmtoken

        Returns a Nmtoken as a string or, if no Nmtoken can be parsed
        then None is returned."""
        nmtoken = []
        while xml.is_name_char(self.the_char):
            nmtoken.append(self.the_char)
            self.next_char()
        if nmtoken:
            return ''.join(nmtoken)
        else:
            return None

    def parse_nmtokens(self):
        """[8] Nmtokens

        This method returns a tuple of unicode strings.  If no tokens
        can be parsed then None is returned."""
        nmtokens = []
        nmtoken = self.parse_nmtoken()
        if nmtoken is None:
            return None
        nmtokens.append(nmtoken)
        while self.the_char == uspace:
            self.next_char()
            nmtoken = self.parse_nmtoken()
            if nmtoken is None:
                self.buff_text(uspace)
                break
            nmtokens.append(nmtoken)
        if nmtokens:
            return nmtokens
        else:
            return None

    def parse_entity_value(self):
        """[9] EntityValue

        Parses an EntityValue, returning it as a unicode string.

        This method automatically expands other parameter entity
        references but does not expand general or character
        references."""
        save_mode = self.refMode
        qentity = self.entity
        q = self.parse_quote()
        self.refMode = XMLParser.RefModeInEntityValue
        value = []
        while True:
            if self.the_char == '&':
                value.append(self.parse_reference())
            elif self.the_char == '%':
                self.parse_pe_reference()
            elif self.the_char == q:
                if self.entity is qentity:
                    self.next_char()
                    break
                else:
                    # a quote but in a different entity is treated as data
                    value.append(self.the_char)
                    self.next_char()
            elif is_char(self.the_char):
                value.append(self.the_char)
                self.next_char()
            elif self.the_char is None:
                self.well_formedness_error("Incomplete EntityValue")
            else:
                self.well_formedness_error("Unexpected data in EntityValue")
        self.refMode = save_mode
        return ''.join(value)

    def parse_att_value(self):
        """[10] AttValue

        The value is returned without the surrounding quotes and with
        any references expanded.

        The behaviour of this method is affected significantly by the
        setting of the :py:attr:`dont_check_wellformedness` flag.  When
        set, attribute values can be parsed without surrounding quotes.
        For compatibility with SGML these values should match one of the
        formal value types (e.g., Name) but this is not enforced so
        values like width=100% can be parsed without error."""
        production = "[10] AttValue"
        value = []
        try:
            q = self.parse_quote()
            end = ''
        except XMLWellFormedError:
            if not self.dont_check_wellformedness:
                raise
            q = None
            end = '<"\'> \t\r\n'
        qentity = self.entity
        save_mode = self.refMode
        self.refMode = XMLParser.RefModeInAttributeValue
        while True:
            try:
                if self.the_char is None:
                    self.well_formedness_error(production + ":EOF in AttValue")
                elif self.the_char == q:
                    if self.entity is qentity:
                        self.next_char()
                        break
                    else:
                        value.append(self.the_char)
                        self.next_char()
                elif self.the_char in end and self.entity is qentity:
                    # only when not checking well-formedness mode only
                    break
                elif self.the_char == '&':
                    ref_data = self.parse_reference()
                    value.append(ref_data)
                elif self.is_s():
                    value.append(character(0x20))
                    self.next_char()
                elif self.the_char == '<':
                    self.well_formedness_error("No < in Attribute Values")
                else:
                    value.append(self.the_char)
                    self.next_char()
            except XMLWellFormedError:
                if not self.dont_check_wellformedness:
                    raise
                elif self.the_char == '<':
                    value.append(self.the_char)
                    self.next_char()
                elif self.the_char is None:
                    break
        self.refMode = save_mode
        return ''.join(value)

    def parse_system_literal(self):
        """[11] SystemLiteral

        The value of the literal is returned as a string *without* the
        enclosing quotes."""
        production = "[11] SystemLiteral"
        q = self.parse_quote()
        value = []
        while True:
            if self.the_char == q:
                self.next_char()
                break
            elif is_char(self.the_char):
                value.append(self.the_char)
                self.next_char()
            elif self.the_char is None:
                self.well_formedness_error(
                    production + ": Unexpected end of file")
            else:
                self.well_formedness_error(
                    production +
                    ": Illegal character %s" % repr(self.the_char))
        return ''.join(value)

    def parse_pubid_literal(self):
        """[12] PubidLiteral

        The value of the literal is returned as a string *without* the
        enclosing quotes."""
        production = "[12] PubidLiteral"
        q = self.parse_quote()
        value = []
        while True:
            if self.the_char == q:
                self.next_char()
                break
            elif is_pubid_char(self.the_char):
                value.append(self.the_char)
                self.next_char()
            elif self.the_char is None:
                self.well_formedness_error(
                    production + ": Unexpected End of file")
            else:
                self.well_formedness_error(
                    production +
                    ": Illegal character %s" % repr(self.the_char))
        return ''.join(value)

    def parse_char_data(self):
        """[14] CharData

        Parses a run of character data.  The method adds the parsed data
        to the current element.  In the default parsing mode it returns
        None.

        When the parser option :py:attr:`sgml_omittag` is selected the
        method returns any parsed character data that could not be added
        to the current element due to a model violation.  Note that in
        this SGML-like mode any S is treated as being in the current
        element as the violation doesn't occur until the first non-S
        character (so any implied start tag is treated as being
        immediately prior to the first non-S)."""
        data = []
        while self.the_char is not None:
            if self.the_char == '<' or self.the_char == '&':
                break
            if self.the_char == ']':
                if self.parse_literal(xml.CDATA_END):
                    self.buff_text(xml.CDATA_END)
                    break
            self.is_s()     # force Unicode compatible white space handling
            data.append(self.the_char)
            self.next_char()
            if len(data) >= xml.XMLEntity.chunk_size:
                data = ''.join(data)
                try:
                    self.handle_data(data)
                except xml.XMLValidityError:
                    if self.sgml_omittag:
                        return strip_leading_s(data)
                    raise
                data = []
        data = ''.join(data)
        try:
            self.handle_data(data)
        except xml.XMLValidityError:
            if self.sgml_omittag:
                return strip_leading_s(data)
            raise
        return None

    def parse_comment(self, got_literal=False):
        """[15] Comment

        got_literal
            If True then the method assumes that the '<!--' literal has
            already been parsed.

        Returns the comment as a string."""
        production = "[15] Comment"
        data = []
        nhyphens = 0
        if not got_literal:
            self.parse_required_literal('<!--', production)
        centity = self.entity
        while self.the_char is not None:
            if self.the_char == '-':
                self.next_char()
                nhyphens += 1
                if nhyphens > 2 and not self.dont_check_wellformedness:
                    self.well_formedness_error("-- in Comment")
            elif self.the_char == '>':
                if nhyphens == 2:
                    self.check_pe_between_declarations(centity)
                    self.next_char()
                    break
                elif nhyphens < 2:
                    self.next_char()
                    data.append('-' * nhyphens + '>')
                    nhyphens = 0
                # we must be in dont_check_wellformedness here, we don't
                # need to check.
                else:
                    data.append('-' * (nhyphens - 2))
                    self.next_char()
                    break
            elif self.is_s():
                if nhyphens < 2:
                    data.append('-' * nhyphens + self.the_char)
                    nhyphens = 0
                # space does not change the hyphen count
                self.next_char()
            else:
                if nhyphens:
                    if nhyphens >= 2 and not self.dont_check_wellformedness:
                        self.well_formedness_error("-- in Comment")
                    data.append('-' * nhyphens)
                    nhyphens = 0
                data.append(self.the_char)
                self.next_char()
        return ''.join(data)

    def parse_pi(self, got_literal=False):
        """[16] PI: parses a processing instruction.

        got_literal
            If True the method assumes the '<?' literal has already been
            parsed.

        This method calls the
        :py:meth:`Node.processing_instruction` of the current
        element or of the document if no element has been parsed yet."""
        production = "[16] PI"
        data = []
        if not got_literal:
            self.parse_required_literal('<?', production)
        dentity = self.entity
        target = self.parse_pi_target()
        if self.parse_s():
            while self.the_char is not None:
                if self.the_char == '?':
                    self.next_char()
                    if self.the_char == '>':
                        self.next_char()
                        break
                    else:
                        # just a single '?'
                        data.append('?')
                data.append(self.the_char)
                self.next_char()
        else:
            self.check_pe_between_declarations(dentity)
            self.parse_required_literal('?>', production)
        if self.element:
            self.element.processing_instruction(target, ''.join(data))
        elif self.doc:
            self.doc.processing_instruction(target, ''.join(data))

    def parse_pi_target(self):
        """[17] PITarget

        Parses a processing instruction target name, the name is
        returned."""
        name = self.parse_name()
        if name.lower() == 'xml':
            self.buff_text(name)
            self.well_formedness_error(
                "[17] PITarget: Illegal target: %s" % name)
        return name

    def parse_cdsect(self, got_literal=False, cdend=xml.CDATA_END):
        """[18] CDSect

        got_literal
            If True then the method assumes the initial literal has
            already been parsed.  (By default, CDStart.)

        cdend
            Optional string.  The literal used to signify the end of the
            CDATA section can be overridden by passing an alternative
            literal in *cdend*.  Defaults to ']]>'

        This method adds any parsed data to the current element, there
        is no return value."""
        production = "[18] CDSect"
        if not got_literal:
            self.parse_cdstart()
        self.parse_cdata(cdend)
        self.parse_required_literal(cdend, production)

    def parse_cdstart(self):
        """[19] CDStart

        Parses the literal that starts a CDATA section."""
        self.parse_required_literal(xml.CDATA_START, "[19] CDStart")

    def parse_cdata(self, cdend=xml.CDATA_END):
        """[20] CData

        Parses a run of CData up to but not including *cdend*.

        This method adds any parsed data to the current element, there
        is no return value."""
        data = []
        while self.the_char is not None:
            if self.parse_literal(cdend):
                self.buff_text(cdend)
                break
            data.append(self.the_char)
            self.next_char()
            if len(data) >= xml.XMLEntity.chunk_size:
                data = ''.join(data)
                self.handle_data(data, True)
                data = []
        data = ''.join(data)
        self.handle_data(data, True)

    def parse_cdend(self):
        """[21] CDEnd

        Parses the end of a CDATA section."""
        self.parse_required_literal(xml.CDATA_END, "[21] CDEnd")

    def parse_prolog(self):
        """[22] prolog

        Parses the document prolog, including the XML declaration and
        dtd."""
        production = "[22] prolog"
        if self.parse_literal('<?xml'):
            self.parse_xml_decl(True)
        else:
            self.declaration = None
            self.check_encoding(self.entity, None)
        self.entity.keep_encoding()
        self.parse_misc()
        if self.parse_literal('<!DOCTYPE'):
            self.parse_doctypedecl(True)
            self.parse_misc()
        else:
            # document has no DTD, treat as standalone
            self.validity_error(
                production + ": missing document type declaration")
            self.dtd = xml.XMLDTD()
        if self.check_validity:
            # Some checks can only be done after the prolog is complete.
            for ename in dict_keys(self.dtd.element_list):
                etype = self.dtd.element_list[ename]
                adefs = self.dtd.get_attribute_list(ename)
                if adefs:
                    if etype.content_type == xml.ElementType.Empty:
                        for aname in dict_keys(adefs):
                            adef = adefs[aname]
                            if (adef.type ==
                                    xml.XMLAttributeDefinition.NOTATION):
                                self.validity_error(
                                    "No Notation on Empty Element: "
                                    "attribute %s on element %s cannot have "
                                    "NOTATION type" % (aname, ename))
            for ename in dict_keys(self.dtd.general_entities):
                edef = self.dtd.general_entities[ename]
                if edef.notation and edef.notation not in self.dtd.notations:
                    self.validity_error(
                        "Notation Declared: notation %s used in declaration "
                        "of entity %s has not been declared" %
                        (edef.notation, ename))

    def parse_xml_decl(self, got_literal=False):
        """[23] XMLDecl

        got_literal
            If True the initial literal '<?xml' is assumed to have
            already been parsed.

        Returns an
        :py:class:`~pyslet.xml.structures.XMLDeclaration`
        instance.  Also, if an encoding is given in the declaration then
        the method changes the encoding of the current entity to match.
        For more information see
        :py:meth:`~pyslet.xml.structures.XMLEntity.change_encoding`."""
        production = '[23] XMLDecl'
        if not got_literal:
            self.parse_required_literal('<?xml', production)
        version = self.parse_version_info()
        encoding = None
        standalone = False
        if self.parse_s():
            if self.parse_literal('encoding'):
                encoding = self.parse_encoding_decl(True)
                if self.parse_s():
                    if self.parse_literal('standalone'):
                        standalone = self.parse_sd_decl(True)
            elif self.parse_literal('standalone'):
                standalone = self.parse_sd_decl(True)
        self.parse_s()
        self.check_encoding(self.entity, encoding)
        if (encoding is not None and
                self.entity.encoding.lower() != encoding.lower()):
            self.entity.change_encoding(encoding)
        self.parse_required_literal('?>', production)
        self.declaration = xml.XMLDeclaration(version, encoding, standalone)
        return self.declaration

    def parse_version_info(self, got_literal=False):
        """[24] VersionInfo

        got_literal
            If True, the method assumes the initial white space and
            'version' literal has been parsed already.

        The version number is returned as a string."""
        production = "[24] VersionInfo"
        if not got_literal:
            self.parse_required_s(production)
            self.parse_required_literal('version', production)
        self.parse_eq(production)
        q = self.parse_quote()
        self.parse_required_literal('1.')
        digits = self.parse_required_decimal_digits(production)
        version = "1." + digits
        self.parse_quote(q)
        return version

    def parse_eq(self, production="[25] Eq"):
        """[25] Eq

        production
            An optional string describing the production being parsed.
            This allows more useful errors than simply 'expected [25]
            Eq' to be logged.

        Parses an equal sign, optionally surrounded by white space"""
        self.parse_s()
        self.parse_required_literal('=', production)
        self.parse_s()

    def parse_version_num(self):
        """[26] VersionNum

        Parses the XML version number, returning it as a string, e.g.,
        "1.0"."""
        production = "[26] VersionNum"
        self.parse_required_literal('1.', production)
        return '1.' + self.parse_required_decimal_digits(production)

    def parse_misc(self):
        """[27] Misc

        This method parses everything that matches the production Misc*"""
        while True:
            if self.is_s():
                self.next_char()
                continue
            elif self.parse_literal('<!--'):
                self.parse_comment(True)
                continue
            elif self.parse_literal('<?'):
                self.parse_pi(True)
                continue
            else:
                break

    def parse_doctypedecl(self, got_literal=False):
        """[28] doctypedecl

        got_literal
            If True, the method assumes the initial '<!DOCTYPE' literal
            has been parsed already.

        This method creates a new instance of
        :py:class:`~pyslet.xml.structures.XMLDTD` and assigns it
        to py:attr:`dtd`, it also returns this instance as the result."""
        production = "[28] doctypedecl"
        if not got_literal:
            self.parse_required_literal('<!DOCTYPE', production)
        save_mode = self.refMode
        self.refMode = XMLParser.RefModeInDTD
        self.dtd = xml.XMLDTD()
        self.parse_required_s(production)
        self.dtd.name = self.parse_required_name(production)
        if self.parse_s():
            # could be an ExternalID
            if self.the_char != '[' and self.the_char != '>':
                self.dtd.external_id = self.parse_external_id()
                self.parse_s()
        if self.parse_literal('['):
            # If there is no external_id we treat as standalone (until a
            # PE ref)
            self.parse_int_subset()
            self.parse_required_literal(']', production)
            self.parse_s()
        if self.check_validity and self.dtd.external_id:
            # Before we parse the closing literal we load any external subset
            # but only if we are checking validity
            src = self.resolve_external_id(self.dtd.external_id)
            if src:
                external_dtd_subset = xml.XMLEntity(src)
                self.push_entity(external_dtd_subset)
                self.parse_ext_subset()
        self.parse_required_literal('>', production)
        self.refMode = save_mode
        return self.dtd

    def parse_decl_sep(self):
        """[28a] DeclSep

        Parses a declaration separator."""
        got_sep = False
        while True:
            if self.the_char == '%':
                ref_entity = self.entity
                self.parse_pe_reference()
                if self.entity is not ref_entity:
                    # we have a new entity, flag it as being opened in
                    # DeclSep
                    self.entity.flags['DeclSep'] = True
                got_sep = True
            elif self.is_s():
                self.next_char()
                got_sep = True
            else:
                break
        if not got_sep:
            self.well_formedness_error(
                "[28a] DeclSep: expected PEReference or S, found %s" %
                repr(self.the_char))

    def parse_int_subset(self):
        """[28b] intSubset

        Parses an internal subset."""
        subset_entity = self.entity
        while True:
            if self.the_char == '<':
                self.noPERefs = (self.get_external_entity() is subset_entity)
                self.parse_markup_decl()
                self.noPERefs = False
            elif self.the_char == '%' or self.is_s():
                self.parse_decl_sep()
            else:
                break

    def parse_markup_decl(self, got_literal=False):
        """[29] markupDecl

        got_literal
            If True, the method assumes the initial '<' literal
            has been parsed already.

        Returns True if a markupDecl was found, False otherwise."""
        production = "[29] markupDecl"
        if not got_literal:
            self.parse_required_literal('<', production)
        if self.the_char == '?':
            self.next_char()
            self.parse_pi(True)
        elif self.the_char == '!':
            self.next_char()
            if self.the_char == '-':
                self.parse_required_literal('--', production)
                self.parse_comment(True)
            elif self.parse_literal('ELEMENT'):
                self.parse_element_decl(True)
            elif self.parse_literal('ATTLIST'):
                self.parse_attlist_decl(True)
            elif self.parse_literal('ENTITY'):
                self.parse_entity_decl(True)
            elif self.parse_literal('NOTATION'):
                self.parse_notation_decl(True)
            else:
                self.well_formedness_error(
                    production + ": expected markup declaration")
        else:
            self.well_formedness_error(
                production + ": expected markup declaration")

    def parse_ext_subset(self):
        """[30] extSubset

        Parses an external subset"""
        if self.parse_literal('<?xml'):
            self.parse_text_decl(True)
        else:
            self.check_encoding(self.entity, None)
        self.entity.keep_encoding()
        self.parse_ext_subset_decl()

    def parse_ext_subset_decl(self):
        """[31] extSubsetDecl

        Parses declarations in the external subset."""
        initial_stack = len(self.entityStack)
        while len(self.entityStack) >= initial_stack:
            literal_entity = self.entity
            if self.the_char == '%' or self.is_s():
                self.parse_decl_sep()
            elif self.parse_literal("<!["):
                self.parse_conditional_sect(literal_entity)
            elif self.the_char == '<':
                self.parse_markup_decl()
            else:
                break

    def check_pe_between_declarations(self, check_entity):
        """[31] extSubsetDecl

        check_entity
            A :py:class:`~pyslet.xml.structures.XMLEntity`
            object, the entity we should still be parsing.

        Checks the well-formedness constraint on use of PEs between
        declarations."""
        if self.check_validity and self.entity is not check_entity:
            self.validity_error(
                "Proper Declaration/PE Nesting: found '>' in entity %s" %
                self.entity.get_name())
        if (not self.dont_check_wellformedness and
                self.entity is not check_entity and
                check_entity.flags.get('DeclSep', False)):
            # a badly nested declaration in an entity opened within a
            # DeclSep is a well-formedness error
            self.well_formedness_error(
                "[31] extSubsetDecl: failed for entity %s included "
                "in a DeclSep" % check_entity.get_name())

    def parse_sd_decl(self, got_literal=False):
        """[32] SDDecl

        got_literal
            If True, the method assumes the initial 'standalone' literal
            has been parsed already.

        Returns True if the document should be treated as standalone;
        False otherwise."""
        production = "[32] SDDecl"
        if not got_literal:
            self.parse_required_s(production)
            self.parse_required_literal('standalone', production)
        self.parse_eq(production)
        q = self.parse_quote()
        if self.the_char == 'y':
            result = True
            match = 'yes'
        else:
            result = False
            match = 'no'
        self.parse_required_literal(match, production)
        self.parse_quote(q)
        return result

    def parse_element(self):
        """[39] element

        The class used to represent the element is determined by calling
        the
        :py:meth:`~pyslet.xml.structures.Document.get_element_class`
        method of the current document. If there is no document yet then
        a new document is created automatically (see
        :py:meth:`parse_document` for more information).

        The element is added as a child of the current element using
        :py:meth:`Node.add_child`.

        The method returns a boolean value:

        True
            the element was parsed normally

        False
            the element is not allowed in this context

        The second case only occurs when the :py:attr:`sgml_omittag`
        option is in use and it indicates that the content of the
        enclosing element has ended.  The Tag is buffered so that it can
        be reparsed when the stack of nested :py:meth:`parse_content`
        and :py:meth:`parse_element` calls is unwound to the point where
        it is allowed by the context."""
        production = "[39] element"
        save_element = self.element
        save_element_type = self.elementType
        save_cursor = None
        if self.sgml_omittag and self.the_char != '<':
            # Leading data means the start tag was omitted (perhaps at the
            # start of the doc)
            name = None
            attrs = {}
            empty = False
        else:
            name, attrs, empty = self.parse_stag()
            self.check_attributes(name, attrs)
            if self.check_validity:
                if (self.element is None and
                        self.dtd.name is not None and self.dtd.name != name):
                    self.validity_error(
                        "Root Element Type: expected element %s" %
                        self.dtd.name)
                # The current particle map must have an entry for name...
                self.check_expected_particle(name)
                save_cursor = self.cursor
                self.elementType = self.dtd.get_element_type(name)
                if self.elementType is None:
                    # An element is valid if there is a declaration
                    # matching elementdecl where the Name matches the
                    # element type...
                    self.validity_error(
                        "Element Valid: no element declaration for %s" % name)
                    self.cursor = None
                else:
                    self.cursor = ContentParticleCursor(self.elementType)
            if self.stagBuffer:
                name, attrs, empty = self.stagBuffer
                self.stagBuffer = None
        element_class, element_name, bufferTag = self.get_stag_class(name,
                                                                     attrs)
        # wait until get_stag_class before getting context as it may be
        # None right up until that time
        context = self.get_context()
        if element_class:
            if bufferTag and name:
                # element_class represents an omitted start tag
                self.stagBuffer = (name, attrs, empty)
                # This strange text is a valid start tag that ensures
                # we'll be called again
                self.buff_text("<:>")
                # omitted start tags introduce elements that have no
                # attributes and must not be empty
                attrs = {}
                empty = False
        else:
            # this start tag (or data) indicates an omitted end tag
            if name:
                self.stagBuffer = (name, attrs, empty)
                self.buff_text("<:>")
            return False
        self.element = context.add_child(element_class, element_name)
        # self.element.reset()
        if (self.sgml_content and
                getattr(element_class, 'XMLCONTENT', xml.XMLMixedContent) ==
                xml.XMLEmpty):
            empty = True
        for attr in dict_keys(attrs):
            try:
                self.element.set_attribute(attr, attrs[attr])
            except ValueError as e:
                if self.raiseValidityErrors:
                    raise xml.XMLValidityError(str(e))
                else:
                    logging.warn("Bad attribute value for %s: %s",
                                 to_text(attr), attrs[attr])
            except xml.XMLValidityError:
                if self.raiseValidityErrors:
                    raise
        if not empty:
            save_data_count = self.dataCount
            if (self.sgml_content and
                    getattr(self.element, 'SGMLCONTENT', None) ==
                    xml.ElementType.SGMLCDATA):
                # Alternative parsing of SGMLCDATA elements...
                # SGML says that the content ends at the first ETAGO
                while True:
                    self.parse_cdata('</')
                    if self.the_char is None:
                        break
                    self.parse_required_literal('</', "SGML CDATA Content:")
                    end_name = self.parse_name()
                    if end_name != name:
                        # but this is such a common error we ignore it
                        self.element.add_data('</' + end_name)
                    else:
                        self.parse_s()
                        self.parse_required_literal('>', "SGML CDATA ETag")
                        break
            else:
                # otherwise content detected end of element (so end tag
                # was omitted)
                while self.parse_content():
                    end_name = self.parse_etag()
                    if end_name == name:
                        break
                    spurious_tag = True
                    if self.sgml_omittag:
                        # do we have a matching open element?
                        if self.dont_check_wellformedness:
                            # by starting the check at the current
                            # element we allow mismatched but broadly
                            # equivalent STags and ETags
                            ielement = self.element
                        else:
                            ielement = self.element.parent
                        while isinstance(ielement, xml.Element):
                            if self.match_xml_name(ielement, end_name):
                                spurious_tag = False
                                # push a closing tag back onto the parser
                                self.buff_text('</%s>' % end_name)
                                break
                            else:
                                ielement = ielement.parent
                    if spurious_tag:
                        if self.dont_check_wellformedness:
                            # ignore spurious end tags, we probably
                            # inferred them earlier
                            continue
                        else:
                            self.well_formedness_error(
                                "Element Type Mismatch: found </%s>, "
                                "expected <%s/>" % (end_name, name))
                    else:
                        break
                self.check_expected_particle('')
            if name is None and self.dataCount == save_data_count:
                # This element was triggered by data which element_class
                # was supposed to consume It didn't consume any data so
                # we raise an error here to prevent a loop
                raise xml.XMLFatalError(
                    production +
                    ": element implied by PCDATA had empty content %s" %
                    self.element)
        self.element.content_changed()
        self.element = save_element
        self.elementType = save_element_type
        self.cursor = save_cursor
        return True

    def check_attributes(self, name, attrs):
        """Checks *attrs* against the declarations for an element.

        name
            The name of the element

        attrs
            A dictionary of attributes

        Adds any omitted defaults to the attribute list. Also, checks
        the validity of the attributes which may result in values being
        further normalized as per the rules for collapsing spaces in
        tokenized values."""
        if self.dtd:
            alist = self.dtd.get_attribute_list(name)
        else:
            alist = None
        if alist:
            for a in dict_keys(alist):
                adef = alist[a]
                check_standalone = self.declared_standalone(
                ) and adef.entity is not self.docEntity
                value = attrs.get(a, None)
                if value is None:
                    # check for default
                    if adef.presence == xml.XMLAttributeDefinition.DEFAULT:
                        attrs[a] = adef.defaultValue
                        if check_standalone:
                            self.validity_error(
                                "Standalone Document Declaration: "
                                "specification for attribute %s required "
                                "(externally defined default)" % a)
                    elif adef.presence == xml.XMLAttributeDefinition.REQUIRED:
                        self.validity_error(
                            "Required Attribute: %s must be specified for "
                            "element %s" % (a, name))
                else:
                    if adef.type != xml.XMLAttributeDefinition.CDATA:
                        # ...then the XML processor must further process
                        # the normalized attribute value by discarding
                        # any leading and trailing space (#x20)
                        # characters, and by replacing sequences of
                        # space (#x20) characters by a single space
                        # (#x20) character.
                        new_value = normalize_space(value)
                        if check_standalone and new_value != value:
                            self.validity_error(
                                "Standalone Document Declaration: "
                                "specification for attribute %s altered by "
                                "normalization (externally defined tokenized "
                                "type)" % a)
                        attrs[a] = new_value
                if adef.presence == xml.XMLAttributeDefinition.FIXED:
                    if value != adef.defaultValue:
                        self.validity_error(
                            "Fixed Attribute Default: %s must match the "
                            "#FIXED value %s" % (value, adef.defaultValue))
        if self.check_validity:
            for a in dict_keys(attrs):
                if alist:
                    adef = alist.get(a, None)
                else:
                    adef = None
                if adef is None:
                    self.validity_error(
                        "Attribute Value Type: attribute %s must be "
                        "declared" % a)
                else:
                    value = attrs[a]
                    if adef.type == xml.XMLAttributeDefinition.ID:
                        if not xml.is_valid_name(value):
                            self.validity_error(
                                "ID: %s does not match the Name production" %
                                value)
                        if value in self.idTable:
                            self.validity_error(
                                "ID: value %s already in use" % value)
                        else:
                            self.idTable[value] = True
                    elif (adef.type == xml.XMLAttributeDefinition.IDREF or
                            adef.type == xml.XMLAttributeDefinition.IDREFS):
                        if adef.type == xml.XMLAttributeDefinition.IDREF:
                            values = [value]
                        else:
                            values = value.split(' ')
                        for iValue in values:
                            if not xml.is_valid_name(iValue):
                                self.validity_error(
                                    "IDREF: %s does not match the Name "
                                    "production" % iValue)
                            self.idRefTable[iValue] = True
                    elif (adef.type == xml.XMLAttributeDefinition.ENTITY or
                            adef.type == xml.XMLAttributeDefinition.ENTITIES):
                        if adef.type == xml.XMLAttributeDefinition.ENTITY:
                            values = [value]
                        else:
                            values = value.split(' ')
                        for iValue in values:
                            if not xml.is_valid_name(iValue):
                                self.validity_error(
                                    "Entity Name: %s does not match the Name "
                                    "production" % iValue)
                            e = self.dtd.get_entity(iValue)
                            if e is None:
                                self.validity_error(
                                    "Entity Name: entity %s has not been "
                                    "declared" % iValue)
                            elif e.notation is None:
                                self.validity_error(
                                    "Entity Name: entity %s is not unparsed" %
                                    iValue)
                    elif (adef.type == xml.XMLAttributeDefinition.NMTOKEN or
                            adef.type == xml.XMLAttributeDefinition.NMTOKENS):
                        if adef.type == xml.XMLAttributeDefinition.NMTOKEN:
                            values = [value]
                        else:
                            values = value.split(' ')
                        for iValue in values:
                            if not is_valid_nmtoken(iValue):
                                self.validity_error(
                                    "Name Token: %s does not match the "
                                    "NmToken production" % iValue)
                    elif adef.type == xml.XMLAttributeDefinition.NOTATION:
                        if adef.values.get(value, None) is None:
                            self.validity_error(
                                "Notation Attributes: %s is not one of the "
                                "notation names included in the declaration "
                                "of %s" % (value, a))
                    elif adef.type == xml.XMLAttributeDefinition.ENUMERATION:
                        # must be one of the values
                        if adef.values.get(value, None) is None:
                            self.validity_error(
                                "Enumeration: %s is not one of the NmTokens "
                                "in the declaration of %s" % (value, a))

    def match_xml_name(self, element, name):
        """Tests if *name* is a possible name for *element*.

        element
            A :py:class:`~pyslet.xml.structures.Element`
            instance.

        name
            The name of an end tag, as a string.

        This method is used by the parser to determine if an end tag is
        the end tag of this element.  It is provided as a separate
        method to allow it to be overridden by derived parsers.

        The default implementation simply compares *name* with
        :py:meth:`~pyslet.xml.structures.Element.GetXMLName`"""
        return element.get_xmlname() == name

    def check_expected_particle(self, name):
        """Checks the validity of element name in the current context.

        name
            The name of the element encountered. An empty string for
            *name* indicates the enclosing end tag was found.

        This method also maintains the position of a pointer into the
        element's content model."""
        if self.cursor is not None:
            if not self.cursor.next(name):
                # content model violation
                expected = ' | '.join(self.cursor.expected())
                self.validity_error(
                    "Element Valid: found %s, expected (%s)" %
                    (name, expected))
                # don't generate any more errors for this element
                self.cursor = None

    def get_stag_class(self, name, attrs=None):
        """[40] STag

        name
            The name of the element being started

        attrs
            A dictionary of attributes of the element being started

        Returns information suitable for starting the element in the
        current context.

        If there is no :py:class:`~pyslet.xml.structures.Document`
        instance yet this method assumes that it is being called for the
        root element and selects an appropriate class based on the
        contents of the prolog and/or *name*.

        When using the :py:attr:`sgml_omittag` option *name* may be None
        indicating that the method should return information about the
        element implied by PCDATA in the current context (only called
        when an attempt to add data to the current context has already
        failed).

        The result is a triple of:

        element_class
            the element class that this STag must introduce or None if
            this STag does not belong (directly or indirectly) in the
            current context

        element_name
            the name of the element (to pass to add_child) or None to
            use the default

        buff_flag
            True indicates an omitted tag and that the triggering STag
            (i.e., the STag with name *name*) should be buffered."""
        if self.doc is None:
            if self.dtd is None:
                self.dtd = xml.XMLDTD()
            if self.dtd.name is None:
                self.dtd.name = name
            elif name is None:
                # document starts with PCDATA, use name declared in DOCTYPE
                name = self.dtd.name
            self.doc = self.get_document_class(self.dtd)()
            # copy the dtd to the document
            self.doc.dtd = self.dtd
        context = self.get_context()
        if self.sgml_omittag:
            if name:
                stag_class = context.get_element_class(name)
                if stag_class is None:
                    stag_class = self.doc.get_element_class(name)
            else:
                stag_class = str
            element_class = context.get_child_class(stag_class)
            if element_class is not stag_class:
                return element_class, None, True
            elif element_class is str:
                # unhanded data, end tag omission not supported
                self.validity_error(
                    "data not allowed in %s (and end-tag omission not "
                    "supported)" % context.__class__.__name__)
                return None, name, False
            else:
                return element_class, name, False
        else:
            stag_class = context.get_element_class(name)
            if stag_class is None:
                stag_class = self.doc.get_element_class(name)
            return stag_class, name, False

    def parse_stag(self):
        """[40] STag, [44] EmptyElemTag

        This method returns a tuple of (name, attrs, emptyFlag) where:

        name
            the name of the element parsed

        attrs
            a dictionary of attribute values keyed by attribute name

        emptyFlag
            a boolean; True indicates that the tag was an empty element
            tag."""
        empty = False
        self.parse_required_literal('<')
        name = self.parse_required_name()
        attrs = {}
        while True:
            try:
                s = self.parse_s()
                if self.the_char == '>':
                    self.next_char()
                    break
                elif self.the_char == '/':
                    self.parse_required_literal('/>')
                    empty = True
                    break
                if s:
                    aname, aValue = self.parse_attribute()
                    if not self.dont_check_wellformedness and aname in attrs:
                        self.well_formedness_error(
                            "Unique Att Spec: attribute %s appears more than "
                            "once" % aname)
                    attrs[aname] = aValue
                else:
                    self.well_formedness_error(
                        "Expected S, '>' or '/>', found '%s'" % self.the_char)
            except XMLWellFormedError:
                if not self.dont_check_wellformedness:
                    raise
                # spurious character inside a start tag, in
                # compatibility mode we just discard it and keep going
                self.next_char()
                continue
        return name, attrs, empty

    def parse_attribute(self):
        """[41] Attribute

        Returns a tuple of (*name*, *value*) where:

        name
            is the name of the attribute or None if
            :py:attr:`sgml_shorttag` is True and a short form attribute
            value was supplied.

        value
            the attribute value.

        If :py:attr:`dont_check_wellformedness` is set the parser uses a
        very generous form of parsing attribute values to accomodate
        common syntax errors."""
        production = "[41] Attribute"
        name = self.parse_required_name(production)
        if self.sgml_namecase_general:
            name = name.lower()
        if self.sgml_shorttag:
            # name on its own may be OK
            s = self.parse_s()
            if self.the_char != '=':
                self.buff_text(s)
                return name, name
        self.parse_eq(production)
        value = self.parse_att_value()
        return name, value

    def parse_etag(self, got_literal=False):
        """[42] ETag

        got_literal
            If True, the method assumes the initial '</' literal has
            been parsed already.

        The method returns the name of the end element parsed."""
        production = "[42] ETag"
        if not got_literal:
            self.parse_required_literal('</')
        name = self.parse_required_name(production)
        self.parse_s()
        if self.dont_check_wellformedness:
            # ignore all rubbish in end tags
            while self.the_char is not None:
                if self.the_char == '>':
                    self.next_char()
                    break
                self.next_char()
        else:
            self.parse_required_literal('>', production)
        return name

    def parse_content(self):
        """[43] content

        The method returns:

        True
            indicates that the content was parsed normally

        False
            indicates that the content contained data or markup not
            allowed in this context

        The second case only occurs when the :py:attr:`sgml_omittag`
        option is in use and it indicates that the enclosing element has
        ended (i.e., the element's ETag has been omitted).  See
        py:meth:`parse_element` for more information."""
        while True:
            if self.the_char == '<':
                # element, CDSect, PI or Comment
                self.next_char()
                if self.the_char == '!':
                    # CDSect or Comment
                    self.next_char()
                    if self.the_char == '-':
                        self.parse_required_literal('--')
                        self.parse_comment(True)
                        if (self.check_validity and
                                self.elementType.content_type ==
                                xml.ElementType.Empty):
                            self.validity_error(
                                "Element Valid: comment not allowed in "
                                "element declared EMPTY: %s" %
                                self.elementType.name)
                    elif self.the_char == '[':
                        self.parse_required_literal('[CDATA[')
                        # can CDATA sections imply missing markup?
                        if self.sgml_omittag and not self.element.is_mixed():
                            # CDATA can only be put in elements that can
                            # contain data!
                            self.buff_text(xml.CDATA_START)
                            self.unhandled_data('')
                        else:
                            self.parse_cdsect(True)
                    else:
                        self.well_formedness_error(
                            "Expected Comment or CDSect")
                elif self.the_char == '?':
                    # PI
                    self.next_char()
                    self.parse_pi(True)
                    if (self.check_validity and
                            self.elementType.content_type ==
                            xml.ElementType.Empty):
                        self.validity_error(
                            "Element Valid: processing instruction not "
                            "allowed in element declared EMPTY: %s" %
                            self.elementType.name)
                elif self.the_char != '/':
                    # element
                    self.buff_text('<')
                    if not self.parse_element():
                        return False
                else:
                    # end of content
                    self.buff_text('<')
                    break
            elif self.the_char == '&':
                # Reference
                if self.sgml_omittag and not self.element.is_mixed():
                    # we step in before resolving the reference, just in
                    # case this reference results in white space that is
                    # supposed to be the first data character after the
                    # omitted tag.
                    self.unhandled_data('')
                else:
                    data = self.parse_reference()
                    if (self.check_validity and
                            self.elementType and
                            self.elementType.content_type ==
                            xml.ElementType.Empty):
                        self.validity_error(
                            "Element Valid: reference not allowed in element "
                            "declared EMPTY: %s" % self.elementType.name)
                    self.handle_data(data, True)
            elif self.the_char is None:
                # end of entity
                if self.sgml_omittag:
                    return False
                else:
                    # leave the absence of an end tag for parse_element
                    # to worry about
                    return True
            else:
                pcdata = self.parse_char_data()
                if pcdata and not self.unhandled_data(pcdata):
                    # indicates end of the containing element
                    return False
        return True

    def handle_data(self, data, cdata=False):
        """[43] content

        data
            A string of data to be handled

        cdata
            If True *data* is treated as character data (even if it
            matches the production for S).

        Data is handled by calling
        :py:meth:`~pyslet.xml.structures.Element.add_data`
        even if the data is optional white space."""
        if data and self.element:
            if self.check_validity and self.elementType:
                check_standalone = (
                    self.declared_standalone() and
                    self.elementType.entity is not self.docEntity)
                if (check_standalone and
                        self.elementType.content_type ==
                        xml.ElementType.ElementContent and
                        contains_s(data)):
                    self.validity_error(
                        "Standalone Document Declaration: white space not "
                        "allowed in element %s (externally defined as "
                        "element content)" % self.elementType.name)
                if self.elementType.content_type == xml.ElementType.Empty:
                    self.validity_error(
                        "Element Valid: content not allowed in element "
                        "declared EMPTY: %s" % self.elementType.name)
                if (self.elementType.content_type ==
                        xml.ElementType.ElementContent and
                        (cdata or not is_white_space(data))):
                    self.validity_error(
                        "Element Valid: character data is not allowed in "
                        "element %s" % self.elementType.name)
            self.element.add_data(data)
            self.dataCount += len(data)

    def unhandled_data(self, data):
        """[43] content

        data
            A string of unhandled data

        This method is only called when the :py:attr:`sgml_omittag`
        option is in use. It processes *data* that occurs in a context
        where data is not allowed.

        It returns a boolean result:

        True
            the data was consumed by a sub-element (with an omitted
            start tag)

        False
            the data has been buffered and indicates the end of the
            current content (an omitted end tag)."""
        if data:
            self.buff_text(xml.escape_char_data(data))
        # Two choices: PCDATA starts a new element or ends this one
        element_class, element_name, ignore = self.get_stag_class(None)
        if element_class:
            return self.parse_element()
        else:
            return False

    def parse_empty_elem_tag(self):
        """[44] EmptyElemTag

        There is no method for parsing empty element tags alone.

        This method raises NotImplementedError.  Instead, you should call
        :py:meth:`parse_stag` and examine the result.  If it returns
        False then an empty element was parsed."""
        raise NotImplementedError

    def parse_element_decl(self, got_literal=False):
        """[45] elementdecl

        got_literal
            If True, the method assumes that the '<!ELEMENT' literal has
            already been parsed.

        Declares the element type in the :py:attr:`dtd`, (if present).
        There is no return result."""
        production = "[45] elementdecl"
        etype = xml.ElementType()
        if not got_literal:
            self.parse_required_literal('<!ELEMENT', production)
        etype.entity = self.entity
        self.parse_required_s(production)
        etype.name = self.parse_required_name(production)
        self.parse_required_s(production)
        self.parse_content_spec(etype)
        self.parse_s()
        self.check_pe_between_declarations(etype.entity)
        self.parse_required_literal('>', production)
        if self.check_validity and self.dtd:
            etype.build_model()
            if not etype.is_deterministic():
                self.compatibility_error(
                    "Deterministic Content Model: <%s> has non-deterministic "
                    "content model" % etype.name)
            if self.dtd.get_element_type(etype.name) is not None:
                self.validity_error(
                    "Unique Element Type Declaration: <%s> already declared" %
                    etype.name)
            self.dtd.declare_element_type(etype)

    def parse_content_spec(self, etype):
        """[46] contentspec

        etype
            An :py:class:`~pyslet.xml.structures.ElementType`
            instance.

        Sets the
        :py:attr:`~pyslet.xml.structures.ElementType.content_type`
        and
        :py:attr:`~pyslet.xml.structures.ElementType.content_model`
        attributes of *etype*, there is no return value."""
        production = "[46] contentspec"
        if self.parse_literal('EMPTY'):
            etype.content_type = xml.ElementType.Empty
            etype.content_model = None
        elif self.parse_literal('ANY'):
            etype.content_type = xml.ElementType.Any
            etype.content_model = None
        elif self.parse_literal('('):
            group_entity = self.entity
            self.parse_s()
            if self.parse_literal('#PCDATA'):
                etype.content_type = xml.ElementType.Mixed
                etype.content_model = self.parse_mixed(True, group_entity)
            else:
                etype.content_type = xml.ElementType.ElementContent
                etype.content_model = self.parse_children(True, group_entity)
        else:
            self.well_formedness_error(
                production, ": expected 'EMPTY', 'ANY' or '('")

    def parse_children(self, got_literal=False, group_entity=None):
        """[47] children

        got_literal
            If True, the method assumes that the initial '(' literal has
            already been parsed, including any following white space.

        group_entity
            An optional
            :py:class:`~pyslet.xml.structures.XMLEntity` object.
            If *got_literal* is True then *group_entity* must be the
            entity in which the opening '(' was parsed which started the
            choice group.

        The method returns an instance of
        :py:class:`~pyslet.xml.structures.XMLContentParticle`."""
        production = "[47] children"
        if not got_literal:
            group_entity = self.entity
            if not self.parse_literal('('):
                self.well_formedness_error(
                    production + ": expected choice or seq")
            self.parse_s()
        # choice or seq
        first_child = self.parse_cp()
        self.parse_s()
        if self.the_char == ',' or self.the_char == ')':
            cp = self.parse_seq(first_child, group_entity)
        elif self.the_char == '|':
            cp = self.parse_choice(first_child, group_entity)
        else:
            self.well_formedness_error(production + ": expected seq or choice")
        if self.the_char == '?':
            cp.occurrence = xml.XMLContentParticle.ZeroOrOne
            self.next_char()
        elif self.the_char == '*':
            cp.occurrence = xml.XMLContentParticle.ZeroOrMore
            self.next_char()
        elif self.the_char == '+':
            cp.occurrence = xml.XMLContentParticle.OneOrMore
            self.next_char()
        return cp

    def parse_cp(self):
        """[48] cp

        Returns an
        :py:class:`~pyslet.xml.structures.XMLContentParticle`
        instance."""
        production = "[48] cp"
        if self.parse_literal('('):
            group_entity = self.entity
            # choice or seq
            self.parse_s()
            first_child = self.parse_cp()
            self.parse_s()
            if self.the_char == ',' or self.the_char == ')':
                cp = self.parse_seq(first_child, group_entity)
            elif self.the_char == '|':
                cp = self.parse_choice(first_child, group_entity)
            else:
                self.well_formedness_error(
                    production + ": expected seq or choice")
        else:
            cp = xml.XMLNameParticle()
            cp.name = self.parse_required_name(production)
        if self.the_char == '?':
            cp.occurrence = xml.XMLContentParticle.ZeroOrOne
            self.next_char()
        elif self.the_char == '*':
            cp.occurrence = xml.XMLContentParticle.ZeroOrMore
            self.next_char()
        elif self.the_char == '+':
            cp.occurrence = xml.XMLContentParticle.OneOrMore
            self.next_char()
        return cp

    def parse_choice(self, first_child=None, group_entity=None):
        """[49] choice

        first_child
            An optional
            :py:class:`~pyslet.xml.structures.XMLContentParticle`
            instance. If present the method assumes that the first
            particle and any following white space has already been
            parsed.

        group_entity
            An optional
            :py:class:`~pyslet.xml.structures.XMLEntity` object.
            If *first_child* is given then *group_entity* must be the
            entity in which the opening '(' was parsed which started the
            choice group.

        Returns an
        :py:class:`~pyslet.xml.structures.XMLChoiceList`
        instance."""
        production = "[49] choice"
        cp = xml.XMLChoiceList()
        if first_child is None:
            group_entity = self.entity
            self.parse_required_literal('(', production)
            self.parse_s()
            first_child = self.parse_cp()
            self.parse_s()
        cp.children.append(first_child)
        while True:
            if self.the_char == '|':
                self.next_char()
            elif self.the_char == ')':
                if self.check_validity and self.entity is not group_entity:
                    self.validity_error(
                        "Proper Group/PE Nesting: found ')' in entity %s" %
                        self.entity.get_name())
                if len(cp.children) > 1:
                    self.next_char()
                    break
                else:
                    self.well_formedness_error(
                        production +
                        ": Expected '|', found %s" %
                        repr(
                            self.the_char))
            else:
                self.well_formedness_error(
                    production +
                    ": Expected '|' or ')', found %s" %
                    repr(
                        self.the_char))
            self.parse_s()
            cp.children.append(self.parse_cp())
            self.parse_s()
        return cp

    def parse_seq(self, first_child=None, group_entity=None):
        """[50] seq

        first_child
            An optional
            :py:class:`~pyslet.xml.structures.XMLContentParticle`
            instance.  If present the method assumes that the first
            particle and any following white space has already been
            parsed.  In this case, *group_entity* must be set to the
            entity which contained the opening '(' literal.

        group_entity
            An optional
            :py:class:`~pyslet.xml.structures.XMLEntity` object,
            see above.

        Returns a
        :py:class:`~pyslet.xml.structures.XMLSequenceList`
        instance."""
        production = "[50] seq"
        cp = xml.XMLSequenceList()
        if first_child is None:
            group_entity = self.entity
            self.parse_required_literal('(', production)
            self.parse_s()
            first_child = self.parse_cp()
            self.parse_s()
        cp.children.append(first_child)
        while True:
            if self.the_char == ',':
                self.next_char()
            elif self.the_char == ')':
                if self.check_validity and self.entity is not group_entity:
                    self.validity_error(
                        "Proper Group/PE Nesting: found ')' in entity %s" %
                        self.entity.get_name())
                self.next_char()
                break
            else:
                self.well_formedness_error(
                    production +
                    ": Expected ',' or ')', found %s" %
                    repr(
                        self.the_char))
            self.parse_s()
            cp.children.append(self.parse_cp())
            self.parse_s()
        return cp

    def parse_mixed(self, got_literal=False, group_entity=None):
        """[51] Mixed

        got_literal
            If True, the method assumes that the #PCDATA literal has
            already been parsed.  In this case, *group_entity* must be
            set to the entity which contained the opening '(' literal.

        group_entity
            An optional
            :py:class:`~pyslet.xml.structures.XMLEntity` object,
            see above.

        Returns an instance of
        :py:class:`~pyslet.xml.structures.XMLChoiceList` with
        occurrence
        :py:attr:`~pyslet.xml.structures.XMLContentParticle.ZeroOrMore`
        representing the list of elements that may appear in the mixed
        content model. If the mixed model contains #PCDATA only the
        choice list will be empty."""
        production = "[51] Mixed"
        cp = xml.XMLChoiceList()
        names = {}
        cp.occurrence = xml.XMLContentParticle.ZeroOrMore
        if not got_literal:
            group_entity = self.entity
            self.parse_required_literal('(', production)
            self.parse_s()
            self.parse_required_literal('#PCDATA', production)
        while True:
            self.parse_s()
            if self.the_char == ')':
                if self.check_validity and self.entity is not group_entity:
                    self.validity_error(
                        "Proper Group/PE Nesting: found ')' in entity %s" %
                        self.entity.get_name())
                break
            elif self.the_char == '|':
                self.next_char()
                self.parse_s()
                cp_child = xml.XMLNameParticle()
                cp_child.name = self.parse_required_name(production)
                if self.check_validity:
                    if cp_child.name in names:
                        self.validity_error(
                            "No Duplicate Types: %s appears multiple times "
                            "in mixed-content declaration" % cp_child.name)
                    else:
                        names[cp_child.name] = True
                cp.children.append(cp_child)
                continue
            else:
                self.well_formedness_error(production +
                                           ": Expected '|' or ')'")
        if len(cp.children):
            self.parse_required_literal(')*')
        else:
            self.parse_required_literal(')')
            self.parse_literal('*')
        return cp

    def parse_attlist_decl(self, got_literal=False):
        """[52] AttlistDecl

        got_literal
            If True, assumes that the leading '<!ATTLIST' literal has
            already been parsed.

        Declares the attriutes in the :py:attr:`dtd`, (if present).
        There is no return result."""
        production = "[52] AttlistDecl"
        dentity = self.entity
        if not got_literal:
            self.parse_required_literal("<!ATTLIST", production)
        self.parse_required_s(production)
        name = self.parse_required_name(production)
        while True:
            if self.parse_s():
                if self.the_char == '>':
                    break
                a = self.parse_att_def(True)
                if self.dtd:
                    if self.check_validity:
                        if a.type == xml.XMLAttributeDefinition.ID:
                            if (a.presence !=
                                    xml.XMLAttributeDefinition.IMPLIED and
                                    a.presence !=
                                    xml.XMLAttributeDefinition.REQUIRED):
                                self.validity_error(
                                    "ID Attribute Default: ID attribute %s "
                                    "must have a declared default of #IMPLIED "
                                    "or #REQUIRED" % a.name)
                            alist = self.dtd.get_attribute_list(name)
                            if alist:
                                for ia in dict_values(alist):
                                    if (ia.type ==
                                            xml.XMLAttributeDefinition.ID):
                                        self.validity_error(
                                            "One ID per Element Type: "
                                            "attribute %s must not be of type "
                                            "ID, element %s already has an "
                                            "ID attribute" % (a.name, name))
                        elif a.type == xml.XMLAttributeDefinition.NOTATION:
                            alist = self.dtd.get_attribute_list(name)
                            if alist:
                                for ia in dict_values(alist):
                                    if (ia.type ==
                                            xml.XMLAttributeDefinition.
                                            Notation):
                                        self.validity_error(
                                            "One Notation per Element Type: "
                                            "attribute %s must not be of "
                                            "type NOTATION, element %s "
                                            "already has a NOTATION "
                                            "attribute" % (a.name, name))
                    a.entity = dentity
                    self.dtd.declare_attribute(name, a)

            else:
                break
        self.check_pe_between_declarations(dentity)
        self.parse_required_literal('>', production)

    def parse_att_def(self, got_s=False):
        """[53] AttDef

        got_s
            If True, the method assumes that the leading S has already
            been parsed.

        Returns an instance of
        :py:class:`~pyslet.xml.structures.XMLAttributeDefinition`."""
        production = "[53] AttDef"
        if not got_s:
            self.parse_required_s(production)
        a = xml.XMLAttributeDefinition()
        a.name = self.parse_required_name(production)
        self.parse_required_s(production)
        self.parse_att_type(a)
        self.parse_required_s(production)
        self.parse_default_decl(a)
        return a

    def parse_att_type(self, a):
        """[54] AttType

        a
            A required
            :py:class:`~pyslet.xml.structures.XMLAttributeDefinition`
            instance.

        This method sets the
        :py:attr:`~pyslet.xml.structures.XMLAttributeDefinition.TYPE`
        and
        :py:attr:`~pyslet.xml.structures.XMLAttributeDefinition.VALUES`
        fields of *a*.

        Note that, to avoid unnecessary look ahead, this method does not
        call
        :py:meth:`parse_string_type` or
        :py:meth:`parse_enumerated_type`."""
        if self.parse_literal('CDATA'):
            a.type = xml.XMLAttributeDefinition.CDATA
            a.values = None
        elif self.parse_literal('NOTATION'):
            a.type = xml.XMLAttributeDefinition.NOTATION
            a.values = self.parse_notation_type(True)
        elif self.the_char == '(':
            a.type = xml.XMLAttributeDefinition.ENUMERATION
            a.values = self.parse_enumeration()
        else:
            self.parse_tokenized_type(a)

    def parse_string_type(self, a):
        """[55] StringType

        a
            A required
            :py:class:`~pyslet.xml.structures.XMLAttributeDefinition`
            instance.

        This method sets the
        :py:attr:`~pyslet.xml.structures.XMLAttributeDefinition.TYPE`
        and
        :py:attr:`~pyslet.xml.structures.XMLAttributeDefinition.VALUES`
        fields of *a*.

        This method is provided for completeness.  It is not called
        during normal parsing operations."""
        production = "[55] StringType"
        self.parse_required_literal('CDATA', production)
        a.type = xml.XMLAttributeDefinition.CDATA
        a.values = None

    def parse_tokenized_type(self, a):
        """[56] TokenizedType

        a
            A required
            :py:class:`~pyslet.xml.structures.XMLAttributeDefinition`
            instance.

        This method sets the
        :py:attr:`~pyslet.xml.structures.XMLAttributeDefinition.TYPE`
        and
        :py:attr:`~pyslet.xml.structures.XMLAttributeDefinition.VALUES`
        fields of *a*."""
        production = "[56] TokenizedType"
        if self.parse_literal('ID'):
            if self.parse_literal('REF'):
                if self.parse_literal('S'):
                    a.type = xml.XMLAttributeDefinition.IDREFS
                else:
                    a.type = xml.XMLAttributeDefinition.IDREF
            else:
                a.type = xml.XMLAttributeDefinition.ID
        elif self.parse_literal('ENTIT'):
            if self.parse_literal('Y'):
                a.type = xml.XMLAttributeDefinition.ENTITY
            elif self.parse_literal('IES'):
                a.type = xml.XMLAttributeDefinition.ENTITIES
            else:
                self.well_formedness_error(
                    production + ": Expected 'ENTITY' or 'ENTITIES'")
        elif self.parse_literal('NMTOKEN'):
            if self.parse_literal('S'):
                a.type = xml.XMLAttributeDefinition.NMTOKENS
            else:
                a.type = xml.XMLAttributeDefinition.NMTOKEN
        else:
            self.well_formedness_error(
                production +
                ": Expected 'ID', 'IDREF', 'IDREFS', 'ENTITY', 'ENTITIES', "
                "'NMTOKEN' or 'NMTOKENS'")
        a.values = None

    def parse_enumerated_type(self, a):
        """[57] EnumeratedType

        a
            A required
            :py:class:`~pyslet.xml.structures.XMLAttributeDefinition`
            instance.

        This method sets the
        :py:attr:`~pyslet.xml.structures.XMLAttributeDefinition.TYPE`
        and
        :py:attr:`~pyslet.xml.structures.XMLAttributeDefinition.VALUES`
        fields of *a*.

        This method is provided for completeness.  It is not called
        during normal parsing operations."""
        if self.parse_literal('NOTATION'):
            a.type = xml.XMLAttributeDefinition.NOTATION
            a.values = self.parse_notation_type(True)
        elif self.the_char == '(':
            a.type = xml.XMLAttributeDefinition.ENUMERATION
            a.values = self.parse_enumeration()
        else:
            self.well_formedness_error(
                "[57] EnumeratedType: expected 'NOTATION' or Enumeration")

    def parse_notation_type(self, got_literal=False):
        """[58] NotationType

        got_literal
            If True, assumes that the leading 'NOTATION' literal has
            already been parsed.

        Returns a list of strings representing the names of the declared
        notations being referred to."""
        production = "[58] NotationType"
        value = {}
        if not got_literal:
            self.parse_required_literal('NOTATION', production)
        self.parse_required_s(production)
        self.parse_required_literal('(', production)
        while True:
            self.parse_s()
            name = self.parse_required_name(production)
            if self.check_validity and name in value:
                self.validity_error(
                    "No Duplicate Tokens: %s already declared" % name)
            value[name] = True
            self.parse_s()
            if self.the_char == '|':
                self.next_char()
                continue
            elif self.the_char == ')':
                self.next_char()
                break
            else:
                self.well_formedness_error(
                    production +
                    ": expected '|' or ')', found %s" %
                    repr(
                        self.the_char))
        return value

    def parse_enumeration(self):
        """[59] Enumeration

        Returns a dictionary of strings representing the tokens in the
        enumeration."""
        production = "[59] Enumeration"
        value = {}
        self.parse_required_literal('(', production)
        while True:
            self.parse_s()
            token = self.parse_nmtoken()
            if token:
                if self.check_validity and token in value:
                    self.validity_error(
                        "No Duplicate Tokens: %s already declared" % token)
                value[token] = True
            else:
                self.well_formedness_error(production + ": expected Nmtoken")
            self.parse_s()
            if self.the_char == '|':
                self.next_char()
                continue
            elif self.the_char == ')':
                self.next_char()
                break
            else:
                self.well_formedness_error(
                    production +
                    ": expected '|' or ')', found %s" %
                    repr(
                        self.the_char))
        return value

    def parse_default_decl(self, a):
        """[60] DefaultDecl: parses an attribute's default declaration.

        a
            A required
            :py:class:`~pyslet.xml.structures.XMLAttributeDefinition`
            instance.

        This method sets the
        :py:attr:`~pyslet.xml.structures.XMLAttributeDefinition.PRESENCE`
        and
        :py:attr:`~pyslet.xml.structures.XMLAttributeDefinition.DEFAULTVALUE`
        fields of *a*."""
        if self.parse_literal('#REQUIRED'):
            a.presence = xml.XMLAttributeDefinition.REQUIRED
            a.defaultValue = None
        elif self.parse_literal('#IMPLIED'):
            a.presence = xml.XMLAttributeDefinition.IMPLIED
            a.defaultValue = None
        else:
            if self.parse_literal('#FIXED'):
                a.presence = xml.XMLAttributeDefinition.FIXED
                self.parse_required_s("[60] DefaultDecl")
            else:
                a.presence = xml.XMLAttributeDefinition.DEFAULT
            a.defaultValue = self.parse_att_value()
            if a.type != xml.XMLAttributeDefinition.CDATA:
                a.defaultValue = normalize_space(a.defaultValue)
            if self.check_validity:
                if (a.type == xml.XMLAttributeDefinition.IDREF or
                        a.type == xml.XMLAttributeDefinition.ENTITY):
                    if not xml.is_valid_name(a.defaultValue):
                        self.validity_error(
                            "Attribute Default Value Syntactically Correct: "
                            "%s does not match the Name production" %
                            xml.escape_char_data(a.defaultValue, True))
                elif (a.type == xml.XMLAttributeDefinition.IDREFS or
                        a.type == xml.XMLAttributeDefinition.ENTITIES):
                    values = a.defaultValue.split(' ')
                    for iValue in values:
                        if not xml.is_valid_name(iValue):
                            self.validity_error(
                                "Attribute Default Value Syntactically "
                                "Correct: %s does not match the Names "
                                "production" %
                                xml.escape_char_data(a.defaultValue, True))
                elif a.type == xml.XMLAttributeDefinition.NMTOKEN:
                    if not is_valid_nmtoken(a.defaultValue):
                        self.validity_error(
                            "Attribute Default Value Syntactically Correct: "
                            "%s does not match the Nmtoken production" %
                            xml.escape_char_data(a.defaultValue, True))
                elif a.type == xml.XMLAttributeDefinition.NMTOKENS:
                    values = a.defaultValue.split(' ')
                    for iValue in values:
                        if not is_valid_nmtoken(iValue):
                            self.validity_error(
                                "Attribute Default Value Syntactically "
                                "Correct: %s does not match the Nmtokens "
                                "production" %
                                xml.escape_char_data(a.defaultValue, True))
                elif (a.type == xml.XMLAttributeDefinition.NOTATION or
                        a.type == xml.XMLAttributeDefinition.ENUMERATION):
                    if a.values.get(a.defaultValue, None) is None:
                        self.validity_error(
                            "Attribute Default Value Syntactically Correct: "
                            "%s is not one of the allowed enumerated values" %
                            xml.escape_char_data(a.defaultValue, True))

    def parse_conditional_sect(self, got_literal_entity=None):
        """[61] conditionalSect

        got_literal_entity
            An optional
            :py:class:`~pyslet.xml.structures.XMLEntity` object.
            If given,  the method assumes that the initial literal '<!['
            has already been parsed from that entity."""
        production = "[61] conditionalSect"
        if got_literal_entity is None:
            got_literal_entity = self.entity
            self.parse_required_literal('<![', production)
        self.parse_s()
        if self.parse_literal('INCLUDE'):
            self.parse_include_sect(got_literal_entity)
        elif self.parse_literal('IGNORE'):
            self.parse_ignore_sect(got_literal_entity)
        else:
            self.well_formedness_error(
                production + ": Expected INCLUDE or IGNORE")

    def parse_include_sect(self, got_literal_entity=None):
        """[62] includeSect:

        got_literal_entity
            An optional
            :py:class:`~pyslet.xml.structures.XMLEntity` object.
            If given,  the method assumes that the production, up to and
            including the keyword 'INCLUDE' has already been parsed and
            that the opening '<![' literal was parsed from that
            entity.

        There is no return value."""
        production = "[62] includeSect"
        if got_literal_entity is None:
            got_literal_entity = self.entity
            self.parse_required_literal('<![', production)
            self.parse_s()
            self.parse_required_literal('INCLUDE', production)
        self.parse_s()
        if self.check_validity and self.entity is not got_literal_entity:
            self.validity_error(
                production + ": Proper Conditional Section/PE Nesting")
        self.parse_required_literal('[', production)
        self.parse_ext_subset_decl()
        if self.check_validity and self.entity is not got_literal_entity:
            self.validity_error(
                production + ": Proper Conditional Section/PE Nesting")
        self.parse_required_literal(xml.CDATA_END, production)

    def parse_ignore_sect(self, got_literal_entity=None):
        """[63] ignoreSect

        got_literal_entity
            An optional
            :py:class:`~pyslet.xml.structures.XMLEntity` object.
            If given, the method assumes that the production, up to and
            including the keyword 'IGNORE' has already been parsed and
            that the opening '<![' literal was parsed from this entity.

        There is no return value."""
        production = "[63] ignoreSect"
        if got_literal_entity is None:
            got_literal_entity = self.entity
            self.parse_required_literal('<![', production)
            self.parse_s()
            self.parse_required_literal('IGNORE', production)
        self.parse_s()
        if self.check_validity and self.entity is not got_literal_entity:
            self.validity_error(
                "Proper Conditional Section/PE Nesting: [ must not be in "
                "replacement text of %s" % self.entity.get_name())
        self.parse_required_literal('[', production)
        self.parse_ignore_sect_contents()
        if self.check_validity and self.entity is not got_literal_entity:
            self.validity_error(
                "Proper Conditional Section/PE Nesting: ]]> must not be in "
                "replacement text of %s" % self.entity.get_name())
        self.parse_required_literal(xml.CDATA_END, production)

    def parse_ignore_sect_contents(self):
        """[64] ignoreSectContents

        Parses the contents of an ignored section.  The method returns
        no data."""
        self.parse_ignore()
        if self.parse_literal('<!['):
            self.parse_ignore_sect_contents()
            self.parse_required_literal(xml.CDATA_END,
                                        "[64] ignoreSectContents")
            self.parse_ignore()

    def parse_ignore(self):
        """[65] Ignore

        Parses a run of characters in an ignored section.  This method
        returns no data."""
        while is_char(self.the_char):
            if self.the_char == '<' and self.parse_literal('<!['):
                self.buff_text(ul('<!['))
                break
            elif self.the_char == ']' and self.parse_literal(xml.CDATA_END):
                self.buff_text(xml.CDATA_END)
                break
            else:
                self.next_char()

    def parse_char_ref(self, got_literal=False):
        """[66] CharRef

        got_literal
            If True, assumes that the leading '&' literal has already
            been parsed.

        The method returns a unicode string containing the character
        referred to."""
        production = "[66] CharRef"
        if not got_literal:
            self.parse_required_literal('&', production)
        self.parse_required_literal('#', production)
        if self.parse_literal('x'):
            qualifier = 'x'
            digits = self.parse_required_hex_digits(production)
            data = character(int(digits, 16))
        else:
            qualifier = ''
            digits = self.parse_required_decimal_digits(production)
            data = character(int(digits))
        self.parse_required_literal(';', production)
        if self.refMode == XMLParser.RefModeInDTD:
            raise XMLForbiddenEntityReference(
                "&#%s%s; forbidden by context" % (qualifier, digits))
        elif self.refMode == XMLParser.RefModeAsAttributeValue:
            data = "&#%s%s;" % (qualifier, digits)
        elif not is_char(data):
            raise XMLWellFormedError(
                "Legal Character: &#%s%s; does not match production for Char" %
                (qualifier, digits))
        return data

    def parse_reference(self):
        """[67] Reference

        This method returns any data parsed as a result of the
        reference.  For a character reference this will be the character
        referred to.  For a general entity the data returned will depend
        on the parsing context. For more information see
        :py:meth:`parse_entity_ref`."""
        self.parse_required_literal('&', "[67] Reference")
        if self.the_char == '#':
            return self.parse_char_ref(True)
        else:
            return self.parse_entity_ref(True)

    def parse_entity_ref(self, got_literal=False):
        """[68] EntityRef

        got_literal
            If True, assumes that the leading '&' literal has already
            been parsed.

        This method returns any data parsed as a result of the
        reference.  For example, if this method is called in a context
        where entity references are bypassed then the string returned
        will be the literal characters parsed, e.g., "&ref;".

        If the entity reference is parsed successfully in a context
        where Entity references are recognized, the reference is looked
        up according to the rules for validating and non-validating
        parsers and, if required by the parsing mode, the entity is
        opened and pushed onto the parser so that parsing continues with
        the first character of the entity's replacement text.

        A special case is made for the predefined entities.  When parsed
        in a context where entity references are recognized these
        entities are expanded immediately and the resulting character
        returned.  For example, the entity &amp; returns the '&'
        character instead of pushing an entity with replacement text
        '&#38;'.

        Inclusion of an unescaped & is common so when we are not
        checking well-formedness we treat '&' not followed by a name as
        if it were '&amp;'. Similarly we are generous about the missing
        ';'."""
        production = "[68] EntityRef"
        if not got_literal:
            self.parse_required_literal('&', production)
        entity = self.entity
        if self.dont_check_wellformedness:
            name = self.parse_name()
            if not name:
                return '&'
        else:
            name = self.parse_required_name(production)
        if self.dont_check_wellformedness:
            self.parse_literal(';')
        else:
            self.parse_required_literal(';', production)
        if self.refMode == XMLParser.RefModeInEntityValue:
            return "&%s;" % name
        elif self.refMode in (XMLParser.RefModeAsAttributeValue,
                              XMLParser.RefModeInDTD):
            raise XMLForbiddenEntityReference(
                "&%s; forbidden by context" % name)
        else:
            data = self.lookup_predefined_entity(name)
            if data is not None:
                return data
            else:
                e = None
                if self.dtd:
                    e = self.dtd.get_entity(name)
                    if (e and self.declared_standalone() and
                            e.entity is not self.docEntity):
                        self.validity_error(
                            "Standalone Document Declaration: reference to "
                            "entity %s not allowed (externally defined)" %
                            e.get_name())
                if e is not None:
                    if e.notation is not None:
                        self.well_formedness_error(
                            "Parsed Entity: &%s; reference to unparsed "
                            "entity not allowed" % name)
                    else:
                        if (not self.dont_check_wellformedness and
                                self.refMode ==
                                XMLParser.RefModeInAttributeValue and
                                e.is_external()):
                            self.well_formedness_error(
                                "No External Entity References: &%s; not "
                                "allowed in attribute value" % name)
                        if e.is_open() or (e is entity):
                            # if the last char of the entity is a ';'
                            # closing a recursive entity reference then
                            # the entity will have been closed so we
                            # must check the context of the reference #
                            # too, not just whether it is currently open
                            self.well_formedness_error(
                                "No Recursion: entity &%s; is already open" %
                                name)
                        e.open()
                        self.push_entity(e)
                    return ''
                elif self.standalone():
                    self.well_formedness_error(
                        "Entity Declared: undeclared general entity %s "
                        "in standalone document" % name)
                else:
                    self.validity_error(
                        "Entity Declared: undeclared general entity %s" % name)

    def lookup_predefined_entity(self, name):
        """Looks up pre-defined entities, e.g., "lt"

        This method can be overridden by variant parsers to implement
        other pre-defined entity tables."""
        return XMLParser.PredefinedEntities.get(name, None)

    def parse_pe_reference(self, got_literal=False):
        """[69] PEReference

        got_literal
            If True, assumes that the initial '%' literal has already
            been parsed.

        This method returns any data parsed as a result of the
        reference.  Normally this will be an empty string because the
        method is typically called in contexts where PEReferences are
        recognized.  However, if this method is called in a context
        where PEReferences are not recognized the returned string will
        be the literal characters parsed, e.g., "%ref;"

        If the parameter entity reference is parsed successfully in a
        context where PEReferences are recognized, the reference is
        looked up according to the rules for validating and
        non-validating parsers and, if required by the parsing mode, the
        entity is opened and pushed onto the parser so that parsing
        continues with the first character of the entity's replacement
        text."""
        production = "[69] PEReference"
        if not got_literal:
            self.parse_required_literal('%', production)
        entity = self.entity
        name = self.parse_required_name(production)
        self.parse_required_literal(';', production)
        if self.refMode in (XMLParser.RefModeNone,
                            XMLParser.RefModeInContent,
                            XMLParser.RefModeInAttributeValue,
                            XMLParser.RefModeAsAttributeValue):
            return "%%%s;" % name
        else:
            self.gotPERef = True
            if self.noPERefs:
                self.well_formedness_error(
                    production +
                    ": PE referenced in Internal Subset, %%%s;" %
                    name)
            if self.dtd:
                e = self.dtd.get_parameter_entity(name)
            else:
                e = None
            if e is None:
                if self.declared_standalone() and entity is self.docEntity:
                    # in a standalone document, PERefs in the internal
                    # subset must be declared
                    self.well_formedness_error(
                        "Entity Declared: Undeclared parameter entity %s "
                        "in standalone document" % name)
                else:
                    self.validity_error(
                        "Entity Declared: undeclared parameter entity %s" %
                        name)
            else:
                if (self.declared_standalone() and
                        e.entity is not self.docEntity):
                    if entity is self.docEntity:
                        self.well_formedness_error(
                            "Entity Declared: parameter entity %s declared "
                            "externally but document is standalone" %
                            name)
                    else:
                        self.validity_error(
                            "Standalone Document Declaration: reference to "
                            "entity %s not allowed (externally defined)" %
                            e.get_name())
                if self.check_validity:
                    # An external markup declaration is defined as a
                    # markup declaration occurring in the external
                    # subset or in a parameter entity (external or
                    # internal, the latter being included because
                    # non-validating processors are not required to read
                    # them
                    if e.is_open() or (e is entity):
                        self.well_formedness_error(
                            "No Recursion: entity %%%s; is already open" %
                            name)
                    if self.refMode == XMLParser.RefModeInEntityValue:
                        # Parameter entities are fed back into the parser
                        # somehow
                        e.open()
                        self.push_entity(e)
                    elif self.refMode == XMLParser.RefModeInDTD:
                        e.open_as_pe()
                        self.push_entity(e)
            return ''

    def parse_entity_decl(self, got_literal=False):
        """[70] EntityDecl

        got_literal
            If True, assumes that the literal '<!ENTITY' has already
            been parsed.

        Returns an instance of either
        :py:class:`~pyslet.xml.structures.XMLGeneralEntity` or
        :py:class:`~pyslet.xml.structures.XMLParameterEntity`
        depending on the type of entity parsed."""
        production = "[70] EntityDecl"
        if not got_literal:
            self.parse_required_literal('<!ENTITY', production)
        dentity = self.entity
        xentity = self.get_external_entity()
        self.parse_required_s(production)
        if self.the_char == '%':
            e = self.parse_pe_decl(True)
        else:
            e = self.parse_ge_decl(True)
        if e.is_external():
            # Resolve the external ID relative to xentity
            e.location = self.resolve_external_id(e.definition, xentity)
        if self.dtd:
            e.entity = dentity
            self.dtd.declare_entity(e)
        return e

    def parse_ge_decl(self, got_literal=False):
        """[71] GEDecl

        got_literal
            If True, assumes that the literal '<!ENTITY' *and the
            required S* has already been parsed.

        Returns an instance of
        :py:class:`~pyslet.xml.structures.XMLGeneralEntity`."""
        production = "[71] GEDecl"
        dentity = self.entity
        ge = xml.XMLGeneralEntity()
        if not got_literal:
            self.parse_required_literal('<!ENTITY', production)
            self.parse_required_s(production)
        ge.name = self.parse_required_name(production)
        self.parse_required_s(production)
        self.parse_entity_def(ge)
        self.parse_s()
        self.check_pe_between_declarations(dentity)
        self.parse_required_literal('>', production)
        return ge

    def parse_pe_decl(self, got_literal=False):
        """[72] PEDecl

        got_literal
            If True, assumes that the literal '<!ENTITY' *and the
            required S* has already been parsed.

        Returns an instance of
        :py:class:`~pyslet.xml.structures.XMLParameterEntity`."""
        production = "[72] PEDecl"
        dentity = self.entity
        pe = xml.XMLParameterEntity()
        if not got_literal:
            self.parse_required_literal('<!ENTITY', production)
            self.parse_required_s(production)
        self.parse_required_literal('%', production)
        self.parse_required_s(production)
        pe.name = self.parse_required_name(production)
        self.parse_required_s(production)
        self.parse_pe_def(pe)
        self.parse_s()
        self.check_pe_between_declarations(dentity)
        self.parse_required_literal('>', production)
        return pe

    def parse_entity_def(self, ge):
        """[73] EntityDef

        ge
            The general entity being parsed, an
            :py:attr:`~pyslet.xml.structures.XMLGeneralEntity`
            instance.

        This method sets the
        :py:attr:`~pyslet.xml.structures.XMLGeneralEntity.definition`
        and
        :py:attr:`~pyslet.xml.structures.XMLGeneralEntity.notation`
        fields from the parsed entity definition."""
        ge.definition = None
        ge.notation = None
        if self.the_char == '"' or self.the_char == "'":
            ge.definition = self.parse_entity_value()
        elif self.the_char == 'S' or self.the_char == 'P':
            ge.definition = self.parse_external_id()
            s = self.parse_s()
            if s:
                if self.parse_literal('NDATA'):
                    ge.notation = self.parse_ndata_decl(True)
                else:
                    self.buff_text(s)
        else:
            self.well_formedness_error(
                "[73] EntityDef: Expected EntityValue or ExternalID")

    def parse_pe_def(self, pe):
        """[74] PEDef

        pe
            The parameter entity being parsed, an
            :py:class:`~pyslet.xml.structures.XMLParameterEntity`
            instance.

        This method sets the
        :py:attr:`~pyslet.xml.structures.XMLParameterEntity.definition`
        field from the parsed parameter entity definition.  There is no
        return value."""
        pe.definition = None
        if self.the_char == '"' or self.the_char == "'":
            pe.definition = self.parse_entity_value()
        elif self.the_char == 'S' or self.the_char == 'P':
            pe.definition = self.parse_external_id()
        else:
            self.well_formedness_error(
                "[74] PEDef: Expected EntityValue or ExternalID")

    def parse_external_id(self, allow_public_only=False):
        """[75] ExternalID

        allow_public_only
            An external ID must have a SYSTEM literal, and may have a
            PUBLIC identifier. If *allow_public_only* is True then the
            method will also allow an external identifier with a PUBLIC
            identifier but no SYSTEM literal.  In this mode the parser
            behaves as it would when parsing the production::

                (ExternalID | PublicID) S?

        Returns an
        :py:class:`~pyslet.xml.structures.XMLExternalID`
        instance."""
        if allow_public_only:
            production = "[75] ExternalID | [83] PublicID"
        else:
            production = "[75] ExternalID"
        if self.parse_literal('SYSTEM'):
            pub_id = None
            allow_public_only = False
        elif self.parse_literal('PUBLIC'):
            self.parse_required_s(production)
            pub_id = self.parse_pubid_literal()
        else:
            self.well_formedness_error(
                production + ": Expected 'PUBLIC' or 'SYSTEM'")
        if (allow_public_only):
            if self.parse_s():
                if self.the_char == '"' or self.the_char == "'":
                    system_id = self.parse_system_literal()
                else:
                    # we've consumed the trailing S, not a big deal
                    system_id = None
            else:
                # just a PublicID
                system_id = None
        else:
            self.parse_required_s(production)
            system_id = self.parse_system_literal()
        # catch for dont_check_wellformedness ??
        return xml.XMLExternalID(pub_id, system_id)

    def resolve_external_id(self, external_id, entity=None):
        """[75] ExternalID: resolves an external ID, returning a URI.

        external_id
            A :py:class:`~pyslet.xml.structures.XMLExternalID`
            instance.

        entity
            An optional
            :py:class:`~pyslet.xml.structures.XMLEntity`
            instance.  Can be used to force the resolution of relative
            URIs to be relative to the base of the given entity.  If it
            is None then the currently open external entity (where
            available) is used instead.

        Returns an instance of :py:class:`pyslet.rfc2396.URI` or None if
        the external ID cannot be resolved.

        The default implementation simply calls
        :py:meth:`~pyslet.xml.structures.XMLExternalID.get_location`
        with the entity's base URL and ignores the public ID.  Derived
        parsers may recognize public identifiers and resolve
        accordingly."""
        if self.open_external_entities:
            base = None
            if entity is None:
                entity = self.get_external_entity()
            if entity:
                base = entity.location
            location = external_id.get_location(base)
            if not self.open_remote_entities and \
                    not isinstance(location, FileURL):
                return None
            return location
        else:
            return None

    def parse_ndata_decl(self, got_literal=False):
        """[76] NDataDecl

        got_literal
            If True, assumes that the literal 'NDATA' has already been
            parsed.

        Returns the name of the notation used by the unparsed entity as
        a string without the preceding 'NDATA' literal."""
        production = "[76] NDataDecl"
        if not got_literal:
            self.parse_required_s(production)
            self.parse_required_literal('NDATA', production)
        self.parse_required_s(production)
        return self.parse_required_name(production)

    def parse_text_decl(self, got_literal=False):
        """[77] TextDecl

        got_literal
            If True, assumes that the literal '<?xml' has already
            been parsed.

        Returns an
        :py:class:`~pyslet.xml.structures.XMLTextDeclaration`
        instance."""
        production = "[77] TextDecl"
        if not got_literal:
            self.parse_required_literal("<?xml", production)
        self.parse_required_s(production)
        if self.parse_literal('version'):
            version = self.parse_version_info(True)
            encoding = self.parse_encoding_decl()
        elif self.parse_literal('encoding'):
            version = None
            encoding = self.parse_encoding_decl(True)
        else:
            self.well_formedness_error(
                production + ": Expected 'version' or 'encoding'")
        self.check_encoding(self.entity, encoding)
        if (encoding is not None and
                self.entity.encoding.lower() != encoding.lower()):
            self.entity.change_encoding(encoding)
        self.parse_s()
        self.parse_required_literal('?>', production)
        return xml.XMLTextDeclaration(version, encoding)

    def parse_encoding_decl(self, got_literal=False):
        """[80] EncodingDecl

        got_literal
            If True, assumes that the literal 'encoding' has already
            been parsed.

        Returns the declaration name without the enclosing quotes."""
        production = "[80] EncodingDecl"
        if not got_literal:
            self.parse_required_s(production)
            self.parse_required_literal('encoding', production)
        self.parse_eq(production)
        q = self.parse_quote()
        enc_name = self.parse_enc_name()
        if not enc_name:
            self.well_formedness_error("Expected EncName")
        self.parse_quote(q)
        return enc_name

    def parse_enc_name(self):
        """[81] EncName

        Returns the encoding name as a string or None if no valid
        encoding name start character was found."""
        name = []
        if is_enc_name_start(self.the_char):
            name.append(self.the_char)
            self.next_char()
            while is_enc_name(self.the_char):
                name.append(self.the_char)
                self.next_char()
        if name:
            return ''.join(name)
        else:
            return None

    def parse_notation_decl(self, got_literal=False):
        """[82] NotationDecl

        got_literal
            If True, assumes that the literal '<!NOTATION' has already
            been parsed.

        Declares the notation in the :py:attr:`dtd`, (if present).
        There is no return result."""
        production = "[82] NotationDecl"
        dentity = self.entity
        if not got_literal:
            self.parse_required_literal("<!NOTATION", production)
        self.parse_required_s(production)
        name = self.parse_required_name(production)
        self.parse_required_s(production)
        xid = self.parse_external_id(True)
        self.parse_s()
        self.check_pe_between_declarations(dentity)
        self.parse_required_literal('>')
        if self.dtd:
            if self.check_validity and not (self.dtd.get_notation(name) is
                                            None):
                self.validity_error(
                    "Unique Notation Name: %s has already been declared" %
                    name)
            self.dtd.declare_notation(xml.XMLNotation(name, xid))

    def parse_public_id(self):
        """[83] PublicID

        The literal string is returned without the PUBLIC prefix or the
        enclosing quotes."""
        production = "[83] PublicID"
        self.parse_required_literal('PUBLIC', production)
        self.parse_required_s(production)
        return self.parse_pubid_literal()


def parse_xml_class(class_def_str):
    """Creates a CharClass from a XML-style definition

    The purpose of this function is to provide a convenience for
    creating character class definitions from the XML specification
    documents.  The format of those declarations is along these lines
    (this is the definition for Char)::

        #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] |
            #[#x10000-#x10FFFF]

    We parse strings in this format into a :class:`pyslet.unicode5.CharClass`
    instance returning it as the result::

        >>> from pyslet.xml import structures as xml
        >>> xml.parse_xml_class("#x9 | #xA | #xD | [#x20-#xD7FF] |
            [#xE000-#xFFFD] | #[#x10000-#x10FFFF]")
        WARNING:root:Warning: character range outside narrow python build
            (10000-10FFFF)
        CharClass(('\\t', '\\n'), '\\r', (' ', '\\ud7ff'),
            ('\\ue000', '\\ufffd'))

    The builtin function repr can be used to print a representation
    suitable for copy-pasting into Python code."""
    c = CharClass()
    definitions = class_def_str.split('|')
    for d in definitions:
        hex_str = []
        for di in d:
            if di in '[]#x':
                continue
            else:
                hex_str.append(di)
        range_def = [int(h, 16) for h in ''.join(hex_str).split('-')]
        if len(range_def) == 1:
            a = range_def[0]
            if a > maxunicode:
                logging.warning("Warning: character outside narrow "
                                "python build (%X)", a)
            else:
                c.add_char(character(a))
        elif len(range_def) == 2:
            a, b = range_def
            if a > maxunicode:
                logging.warning("Warning: character range outside narrow "
                                "python build (%X-%X)", a, b)
            elif b > maxunicode:
                logging.warning("Warning: character range truncated due to "
                                "narrow python build (%X-%X)", a, b)
                b = maxunicode
                c.add_range(character(a), character(b))
            else:
                c.add_range(character(a), character(b))
    return c
