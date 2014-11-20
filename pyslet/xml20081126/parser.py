#! /usr/bin/env python

import logging
import string

from pyslet.pep8 import PEP8Compatibility
import pyslet.xml20081126.structures as xml


def is_valid_nmtoken(nm_token):
    """Tests if nm_token is a string matching production [5] Nmtoken"""
    if nm_token:
        for c in nm_token:
            if not xml.IsNameChar(c):
                return False
        return True
    else:
        return False


class XMLParser(PEP8Compatibility):

    """An XMLParser object

    entity
        The :py:class:`~pyslet.xml20081126.structures.XMLEntity` to
        parse.

    XMLParser objects are used to parse entities for the constructs
    defined by the numbered productions in the XML specification.

    XMLParser has a number of optional attributes, all of which default
    to False. Attributes with names started 'check' increase the
    strictness of the parser.  All other parser flags, if set to True,
    will not result in a conforming XML processor."""

    DocumentClassTable = {}
    """A dictionary mapping doctype parameters onto class objects.

    For more information about how this is used see
    :py:meth:`get_document_class` and
    :py:func:`~pyslet.xml20081126.structures.RegisterDocumentClass`."""

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
        #: checks XML validity constraints
        #: If *checkValidity* is True, and all other options are left at
        #: their default (False) setting then the parser will behave as
        #: a validating XML parser.
        self.checkValidity = False
        #: Flag indicating if the document is valid, only set if
        #: :py:attr:`checkValidity` is True
        self.valid = None
        #: A list of non-fatal errors discovered during parsing, only
        #: populated if :py:attr:`checkValidity` is True
        self.nonFatalErrors = []
        #: checks XML compatibility constraints; will cause
        #: :py:attr:`checkValidity` to be set to True when parsing
        self.checkCompatibility = False
        #: checks all constraints; will cause :py:attr:`checkValidity`
        #: and :py:attr:`checkCompatibility` to be set to True when
        #: parsing.
        self.checkAllErrors = False
        #: treats validity errors as fatal errors
        self.raiseValidityErrors = False
        #: provides a loose parser for XML-like documents
        self.dontCheckWellFormedness = False
        #: See http://www.w3.org/TR/unicode-xml/
        self.unicodeCompatibility = False
        #: option that simulates SGML's NAMECASE GENERAL YES
        self.sgmlNamecaseGeneral = False
        #: option that simulates SGML's NAMECASE ENTITY YES
        self.sgmlNamecaseEntity = False
        self.sgmlOmittag = False    #: option that simulates SGML's OMITTAG YES
        #: option that simulates SGML's SHORTTAG YES
        self.sgmlShorttag = False
        self.sgmlContent = False
        """This option simulates some aspects of SGML content handling
        based on class attributes of the element being parsed.

        Element classes with XMLCONTENT=:py:data:`XMLEmpty` are treated
        as elements declared EMPTY, these elements are treated as if
        they were introduced with an empty element tag even if they
        weren't, as per SGML's rules.  Note that this SGML feature "has
        nothing to do with markup minimization" (i.e.,
        :py:attr:`sgmlOmittag`.)"""
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
            return string.join(self.buff[1:], '')
        else:
            return ''

    def push_entity(self, entity):
        """Starts parsing an entity

        entity
            An :py:class:`~pyslet.xml20081126.structures.XMLEntity`
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
        if entity.buffText:
            self.buff_text(entity.buffText)

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
            An :py:class:`~pyslet.xml20081126.structures.XMLEntity`
            instance which is being parsed.

        declared_encoding
            A string containing the declared encoding in any declaration
            or None if there was no declared encoding in the entity."""
        if not self.EncodingNotRequired.get(entity.encoding.lower(), False):
            # Encoding required!
            if declared_encoding is None:
                self.processing_error(
                    "Encoding declaration required in %s (%s) but missing" %
                    (entity.GetName(), entity.encoding))
        if self.BOMRequired.get(entity.encoding.lower(), False):
            if not (entity.bom or
                    (declared_encoding and
                     declared_encoding.lower() == 'iso-10646-ucs-2')):
                self.processing_error(
                    "Byte order mark required in %s (%s) was missing" %
                    (entity.GetName(), entity.encoding))

    def get_external_entity(self):
        """Returns the external entity currently being parsed.

        If no external entity is being parsed then None is returned."""
        if self.entity.IsExternal():
            return self.entity
        else:
            i = len(self.entityStack)
            while i:
                i = i - 1
                e = self.entityStack[i]
                if e.IsExternal():
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
            error_class=xml.XMLWellFormedError):
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
        raise error_class("%s: %s" % (self.entity.GetPositionStr(), msg))

    def validity_error(self, msg="validity error",
                       error=xml.XMLValidityError):
        """Called when the parser encounters a validity error.

        msg
            An optional message string

        error
            An optional error class or instance which must be a (class)
            object derived from py:class:`XMLValidityError`.

        The behaviour varies depending on the setting of the
        :py:attr:`checkValidity` and :py:attr:`raiseValidityErrors`
        options. The default (both False) causes validity errors to be
        ignored.  When checking validity an error message is logged to
        :py:attr:`nonFatalErrors` and :py:attr:`valid` is set to False.
        Furthermore, if :py:attr:`raiseValidityErrors` is True *error*
        is raised (or a new instance of *error* is raised) and parsing
        terminates.

        This method can be overridden by derived parsers to implement
        more sophisticated error logging."""
        if self.checkValidity:
            self.valid = False
            if isinstance(error, xml.XMLValidityError):
                self.nonFatalErrors.append(
                    "%s: %s (%s)" %
                    (self.entity.GetPositionStr(), msg, str(error)))
                if self.raiseValidityErrors:
                    raise error
            elif issubclass(error, xml.XMLValidityError):
                msg = "%s: %s" % (self.entity.GetPositionStr(), msg)
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
                "%s: %s" % (self.entity.GetPositionStr(), msg))

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
                "%s: %s" % (self.entity.GetPositionStr(), msg))

    def parse_literal(self, match):
        """Parses an optional literal string.

        match
            The literal string to match

        Returns True if *match* is successfully parsed and False
        otherwise. There is no partial matching, if *match* is not found
        then the parser is left in its original position."""
        match_len = 0
        for m in match:
            if m != self.the_char and (not self.sgmlNamecaseGeneral or
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
        return string.join(data, '')

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
        return string.join(data, '')

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
            The :py:class:`~pyslet.xml20081126.structures.Document`
            instance that will be parsed.  The declaration, dtd and
            elements are added to this document.  If *doc* is None then
            a new instance is created using
            :py:meth:`get_document_class` to identify the correct class
            to use to represent the document based on information in the
            prolog or, if the prolog lacks a declaration, the root
            element.

        This method returns the document that was parsed, an instance of
        :py:class:`~pyslet.xml20081126.structures.Document`."""
        self.refMode == XMLParser.RefModeInContent
        self.doc = doc
        if self.checkAllErrors:
            self.checkCompatibility = True
        if self.checkCompatibility:
            self.checkValidity = True
        if self.checkValidity:
            self.valid = True
        else:
            self.valid = None
        self.nonFatalErrors = []
        self.parse_prolog()
        if self.doc is None:
            if self.dtd.name is not None:
                # create the document based on information in the DTD
                self.doc = self.get_document_class(self.dtd)()
        self.parse_element()
        if self.checkValidity:
            for idref in self.idRefTable.keys():
                if idref not in self.idTable:
                    self.validity_error(
                        "IDREF: %s does not match any ID attribute value")
        self.parse_misc()
        if self.the_char is not None and not self.dontCheckWellFormedness:
            self.well_formedness_error(
                "Unparsed characters in entity after document: %s" %
                repr(
                    self.the_char))
        return self.doc

    def get_document_class(self, dtd):
        """Returns a class object suitable for this dtd

        dtd
            A :py:class:`~pyslet.xml20081126.structures.XMLDTD` instance

        Returns a *class* object derived from
        :py:class:`~pyslet.xml20081126.structures.Document` suitable for
        representing a document with the given document type declaration.

        In cases where no doctype declaration is made a dummy
        declaration is created based on the name of the root element.
        For example, if the root element is called "database" then the
        dtd is treated as if it was declared as follows::

            <!DOCTYPE database>

        This default implementation uses the following three pieces of
        information to locate a class registered with
        :py:func:`~pyslet.xml20081126.structures.RegisterDocumentClass`.
        The PublicID, SystemID and the name of the root element.  If an
        exact match is not found then wildcard matches are attempted,
        ignoring the SystemID, PublicID and finally the root element in
        turn.  If a document class still cannot be found then wildcard
        matches are tried matching *only* the PublicID, SystemID and
        root element in turn.

        If no document class cab be found,
        :py:class:`~pyslet.xml20081126.structures.Document` is
        returned."""
        root_name = dtd.name
        if dtd.external_id is None:
            public_id = None
            system_id = None
            doc_class = XMLParser.DocumentClassTable.get(
                (root_name, None, None), None)
        else:
            public_id = dtd.external_id.public
            system_id = dtd.external_id.system
            doc_class = XMLParser.DocumentClassTable.get(
                (root_name, public_id, system_id), None)
            if doc_class is None:
                doc_class = XMLParser.DocumentClassTable.get(
                    (root_name, public_id, None), None)
            if doc_class is None:
                doc_class = XMLParser.DocumentClassTable.get(
                    (root_name, None, system_id), None)
            if doc_class is None:
                doc_class = XMLParser.DocumentClassTable.get(
                    (None, public_id, system_id), None)
            if doc_class is None:
                doc_class = XMLParser.DocumentClassTable.get(
                    (None, public_id, None), None)
            if doc_class is None:
                doc_class = XMLParser.DocumentClassTable.get(
                    (None, None, system_id), None)
            if doc_class is None:
                doc_class = XMLParser.DocumentClassTable.get(
                    (root_name, None, None), None)
        if doc_class is None:
            doc_class = xml.Document
        return doc_class

    # Production [2] is implemented with the function IsChar

    def is_s(self):
        """Tests if the current character matches S

        Returns a boolean value, True if S is matched.

        By default calls :py:func:`~pyslet.xml20081126.structures.is_s`

        In Unicode compatibility mode the function maps the unicode
        white space characters at code points 2028 and 2029 to line feed
        and space respectively."""
        if self.unicodeCompatibility:
            if self.the_char == u"\u2028":
                self.the_char = "\n"
            elif self.the_char == u"\u2029":
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
                if xml.IsNameStartChar(self.the_char):
                    self.parse_pe_reference(True)
                else:
                    # '%' followed by anything other than name start is
                    # not a reference.
                    self.buff_text('%')
                    break
            elif self.unicodeCompatibility:
                if self.the_char == u"\u2028":
                    s.append('\n')
                elif self.the_char == u"\u2029":
                    s.append(' ')
                else:
                    break
            else:
                break
            slen += 1
        return string.join(s, '')

    def parse_required_s(self, production="[3] S"):
        """[3] S: Parses required white space

        production
            An optional string describing the production being parsed.
            This allows more useful errors than simply 'expected [3]
            S' to be logged.

        If there is no white space then a well-formedness error is
        raised."""
        if not self.parse_s() and not self.dontCheckWellFormedness:
            self.well_formedness_error(
                production + ": Expected white space character")

    # Production [4] is implemented with the function IsNameStartChar
    # Production [4a] is implemented with the function IsNameChar.

    def parse_name(self):
        """[5] Name

        Parses an optional name.  The name is returned as a unicode
        string.  If no Name can be parsed then None is returned."""
        name = []
        if xml.IsNameStartChar(self.the_char):
            name.append(self.the_char)
            self.next_char()
            while xml.IsNameChar(self.the_char):
                name.append(self.the_char)
                self.next_char()
        if name:
            return string.join(name, '')
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
        while self.the_char == u' ':
            self.next_char()
            name = self.parse_name()
            if name is None:
                self.buff_text(u' ')
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
        while xml.IsNameChar(self.the_char):
            nmtoken.append(self.the_char)
            self.next_char()
        if nmtoken:
            return string.join(nmtoken, '')
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
        while self.the_char == u' ':
            self.next_char()
            nmtoken = self.parse_nmtoken()
            if nmtoken is None:
                self.buff_text(u' ')
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
            elif xml.IsChar(self.the_char):
                value.append(self.the_char)
                self.next_char()
            elif self.the_char is None:
                self.well_formedness_error("Incomplete EntityValue")
            else:
                self.well_formedness_error("Unexpected data in EntityValue")
        self.refMode = save_mode
        return string.join(value, '')

    def parse_att_value(self):
        """[10] AttValue

        The value is returned without the surrounding quotes and with
        any references expanded.

        The behaviour of this method is affected significantly by the
        setting of the :py:attr:`dontCheckWellFormedness` flag.  When
        set, attribute values can be parsed without surrounding quotes.
        For compatibility with SGML these values should match one of the
        formal value types (e.g., Name) but this is not enforced so
        values like width=100% can be parsed without error."""
        production = "[10] AttValue"
        value = []
        try:
            q = self.parse_quote()
            end = ''
        except xml.XMLWellFormedError:
            if not self.dontCheckWellFormedness:
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
                    value.append(unichr(0x20))
                    self.next_char()
                elif self.the_char == '<':
                    self.well_formedness_error("No < in Attribute Values")
                else:
                    value.append(self.the_char)
                    self.next_char()
            except xml.XMLWellFormedError:
                if not self.dontCheckWellFormedness:
                    raise
                elif self.the_char == '<':
                    value.append(self.the_char)
                    self.next_char()
                elif self.the_char is None:
                    break
        self.refMode = save_mode
        return string.join(value, '')

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
            elif xml.IsChar(self.the_char):
                value.append(self.the_char)
                self.next_char()
            elif self.the_char is None:
                self.well_formedness_error(
                    production + ": Unexpected end of file")
            else:
                self.well_formedness_error(
                    production +
                    ": Illegal character %s" % repr(self.the_char))
        return string.join(value, '')

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
            elif xml.IsPubidChar(self.the_char):
                value.append(self.the_char)
                self.next_char()
            elif self.the_char is None:
                self.well_formedness_error(
                    production + ": Unexpected End of file")
            else:
                self.well_formedness_error(
                    production +
                    ": Illegal character %s" % repr(self.the_char))
        return string.join(value, '')

    def parse_char_data(self):
        """[14] CharData

        Parses a run of character data.  The method adds the parsed data
        to the current element.  In the default parsing mode it returns
        None.

        When the parser option :py:attr:`sgmlOmittag` is selected the
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
                if self.parse_literal(']]>'):
                    self.buff_text(']]>')
                    break
            self.is_s()     # force Unicode compatible white space handling
            data.append(self.the_char)
            self.next_char()
            if len(data) >= xml.XMLEntity.ChunkSize:
                data = string.join(data, '')
                try:
                    self.handle_data(data)
                except xml.XMLValidityError:
                    if self.sgmlOmittag:
                        return xml.StripLeadingS(data)
                    raise
                data = []
        data = string.join(data, '')
        try:
            self.handle_data(data)
        except xml.XMLValidityError:
            if self.sgmlOmittag:
                return xml.StripLeadingS(data)
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
                if nhyphens > 2 and not self.dontCheckWellFormedness:
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
                # we must be in dontCheckWellFormedness here, we don't
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
                    if nhyphens >= 2 and not self.dontCheckWellFormedness:
                        self.well_formedness_error("-- in Comment")
                    data.append('-' * nhyphens)
                    nhyphens = 0
                data.append(self.the_char)
                self.next_char()
        return string.join(data, '')

    def parse_pi(self, got_literal=False):
        """[16] PI: parses a processing instruction.

        got_literal
            If True the method assumes the '<?' literal has already been
            parsed.

        This method calls the
        :py:meth:`Node.ProcessingInstruction` of the current
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
            self.element.ProcessingInstruction(target, string.join(data, ''))
        elif self.doc:
            self.doc.ProcessingInstruction(target, string.join(data, ''))

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

    def parse_cdsect(self, got_literal=False, cdend=u']]>'):
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
        self.parse_required_literal('<![CDATA[', "[19] CDStart")

    def parse_cdata(self, cdend=']]>'):
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
            if len(data) >= xml.XMLEntity.ChunkSize:
                data = string.join(data, '')
                self.handle_data(data, True)
                data = []
        data = string.join(data, '')
        self.handle_data(data, True)

    def parse_cdend(self):
        """[21] CDEnd

        Parses the end of a CDATA section."""
        self.parse_required_literal(']]>', "[21] CDEnd")

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
        self.entity.KeepEncoding()
        self.parse_misc()
        if self.parse_literal('<!DOCTYPE'):
            self.parse_doctypedecl(True)
            self.parse_misc()
        else:
            # document has no DTD, treat as standalone
            self.validity_error(
                production + ": missing document type declaration")
            self.dtd = xml.XMLDTD()
        if self.checkValidity:
            # Some checks can only be done after the prolog is complete.
            for ename in self.dtd.elementList.keys():
                etype = self.dtd.elementList[ename]
                adefs = self.dtd.GetAttributeList(ename)
                if adefs:
                    if etype.contentType == xml.ElementType.Empty:
                        for aname in adefs.keys():
                            adef = adefs[aname]
                            if (adef.type ==
                                    xml.XMLAttributeDefinition.Notation):
                                self.validity_error(
                                    "No Notation on Empty Element: "
                                    "attribute %s on element %s cannot have "
                                    "NOTATION type" % (aname, ename))
            for ename in self.dtd.generalEntities.keys():
                edef = self.dtd.generalEntities[ename]
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
        :py:class:`~pyslet.xml20081126.structures.XMLDeclaration`
        instance.  Also, if an encoding is given in the declaration then
        the method changes the encoding of the current entity to match.
        For more information see
        :py:meth:`~pyslet.xml20081126.structures.XMLEntity.ChangeEncoding`."""
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
            self.entity.ChangeEncoding(encoding)
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
        self.parse_required_literal(u'1.')
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
        self.parse_required_literal(u'=', production)
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
        :py:class:`~pyslet.xml20081126.structures.XMLDTD` and assigns it
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
        if self.checkValidity and self.dtd.external_id:
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
        self.entity.KeepEncoding()
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
            A :py:class:`~pyslet.xml20081126.structures.XMLEntity`
            object, the entity we should still be parsing.

        Checks the well-formedness constraint on use of PEs between
        declarations."""
        if self.checkValidity and self.entity is not check_entity:
            self.validity_error(
                "Proper Declaration/PE Nesting: found '>' in entity %s" %
                self.entity.GetName())
        if (not self.dontCheckWellFormedness and
                self.entity is not check_entity and
                check_entity.flags.get('DeclSep', False)):
            # a badly nested declaration in an entity opened within a
            # DeclSep is a well-formedness error
            self.well_formedness_error(
                "[31] extSubsetDecl: failed for entity %s included "
                "in a DeclSep" % check_entity.GetName())

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
        if self.the_char == u'y':
            result = True
            match = u'yes'
        else:
            result = False
            match = u'no'
        self.parse_required_literal(match, production)
        self.parse_quote(q)
        return result

    def parse_element(self):
        """[39] element

        The class used to represent the element is determined by calling
        the
        :py:meth:`~pyslet.xml20081126.structures.Document.get_element_class`
        method of the current document. If there is no document yet then
        a new document is created automatically (see
        :py:meth:`parse_document` for more information).

        The element is added as a child of the current element using
        :py:meth:`Node.ChildElement`.

        The method returns a boolean value:

        True
            the element was parsed normally

        False
            the element is not allowed in this context

        The second case only occurs when the :py:attr:`sgmlOmittag`
        option is in use and it indicates that the content of the
        enclosing element has ended.  The Tag is buffered so that it can
        be reparsed when the stack of nested :py:meth:`parse_content`
        and :py:meth:`parse_element` calls is unwound to the point where
        it is allowed by the context."""
        production = "[39] element"
        save_element = self.element
        save_element_type = self.elementType
        save_cursor = None
        if self.sgmlOmittag and self.the_char != '<':
            # Leading data means the start tag was omitted (perhaps at the
            # start of the doc)
            name = None
            attrs = {}
            empty = False
        else:
            name, attrs, empty = self.parse_stag()
            self.check_attributes(name, attrs)
            if self.checkValidity:
                if (self.element is None and
                        self.dtd.name is not None and self.dtd.name != name):
                    self.validity_error(
                        "Root Element Type: expected element %s" %
                        self.dtd.name)
                # The current particle map must have an entry for name...
                self.check_expected_particle(name)
                save_cursor = self.cursor
                self.elementType = self.dtd.GetElementType(name)
                if self.elementType is None:
                    # An element is valid if there is a declaration
                    # matching elementdecl where the Name matches the
                    # element type...
                    self.validity_error(
                        "Element Valid: no element declaration for %s" % name)
                    self.cursor = None
                else:
                    self.cursor = xml.ContentParticleCursor(self.elementType)
            if self.stagBuffer:
                name, attrs, empty = self.stagBuffer
                self.stagBuffer = None
        element_class, element_name, bufferTag = self.get_stag_class(name,
                                                                     attrs)
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
            # this start tag indicates an omitted end tag: always
            # buffered
            if name:
                self.stagBuffer = (name, attrs, empty)
                self.buff_text("<:>")
            return False
        if self.element is None:
            self.element = self.doc.ChildElement(element_class, element_name)
        else:
            self.element = self.element.ChildElement(element_class,
                                                     element_name)
        self.element.reset()
        if (self.sgmlContent and
                getattr(element_class, 'XMLCONTENT', xml.XMLMixedContent) ==
                xml.XMLEmpty):
            empty = True
        for attr in attrs.keys():
            try:
                self.element.SetAttribute(attr, attrs[attr])
            except ValueError as e:
                if self.raiseValidityErrors:
                    raise xml.XMLValidityError(str(e))
                else:
                    logging.warn("Bad attribute value for %s: %s",
                                 unicode(attr), attrs[attr])
            except xml.XMLValidityError:
                if self.raiseValidityErrors:
                    raise
        if not empty:
            save_data_count = self.dataCount
            if (self.sgmlContent and
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
                        self.element.AddData('</' + end_name)
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
                    if self.sgmlOmittag:
                        # do we have a matching open element?
                        if self.dontCheckWellFormedness:
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
                        if self.dontCheckWellFormedness:
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
            alist = self.dtd.GetAttributeList(name)
        else:
            alist = None
        if alist:
            for a in alist.keys():
                adef = alist[a]
                check_standalone = self.declared_standalone(
                ) and adef.entity is not self.docEntity
                value = attrs.get(a, None)
                if value is None:
                    # check for default
                    if adef.presence == xml.XMLAttributeDefinition.Default:
                        attrs[a] = adef.defaultValue
                        if check_standalone:
                            self.validity_error(
                                "Standalone Document Declaration: "
                                "specification for attribute %s required "
                                "(externally defined default)" % a)
                    elif adef.presence == xml.XMLAttributeDefinition.Required:
                        self.validity_error(
                            "Required Attribute: %s must be specified for "
                            "element %s" % (a, name))
                else:
                    if adef.type != xml.XMLAttributeDefinition.CData:
                        # ...then the XML processor must further process
                        # the normalized attribute value by discarding
                        # any leading and trailing space (#x20)
                        # characters, and by replacing sequences of
                        # space (#x20) characters by a single space
                        # (#x20) character.
                        new_value = xml.NormalizeSpace(value)
                        if check_standalone and new_value != value:
                            self.validity_error(
                                "Standalone Document Declaration: "
                                "specification for attribute %s altered by "
                                "normalization (externally defined tokenized "
                                "type)" % a)
                        attrs[a] = new_value
                if adef.presence == xml.XMLAttributeDefinition.Fixed:
                    if value != adef.defaultValue:
                        self.validity_error(
                            "Fixed Attribute Default: %s must match the "
                            "#FIXED value %s" % (value, adef.defaultValue))
        if self.checkValidity:
            for a in attrs.keys():
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
                        if not xml.IsValidName(value):
                            self.validity_error(
                                "ID: %s does not match the Name production" %
                                value)
                        if value in self.idTable:
                            self.validity_error(
                                "ID: value %s already in use" % value)
                        else:
                            self.idTable[value] = True
                    elif (adef.type == xml.XMLAttributeDefinition.IDRef or
                            adef.type == xml.XMLAttributeDefinition.IDRefs):
                        if adef.type == xml.XMLAttributeDefinition.IDRef:
                            values = [value]
                        else:
                            values = value.split(' ')
                        for iValue in values:
                            if not xml.IsValidName(iValue):
                                self.validity_error(
                                    "IDREF: %s does not match the Name "
                                    "production" % iValue)
                            self.idRefTable[iValue] = True
                    elif (adef.type == xml.XMLAttributeDefinition.Entity or
                            adef.type == xml.XMLAttributeDefinition.Entities):
                        if adef.type == xml.XMLAttributeDefinition.Entity:
                            values = [value]
                        else:
                            values = value.split(' ')
                        for iValue in values:
                            if not xml.IsValidName(iValue):
                                self.validity_error(
                                    "Entity Name: %s does not match the Name "
                                    "production" % iValue)
                            e = self.dtd.GetEntity(iValue)
                            if e is None:
                                self.validity_error(
                                    "Entity Name: entity %s has not been "
                                    "declared" % iValue)
                            elif e.notation is None:
                                self.validity_error(
                                    "Entity Name: entity %s is not unparsed" %
                                    iValue)
                    elif (adef.type == xml.XMLAttributeDefinition.NmToken or
                            adef.type == xml.XMLAttributeDefinition.NmTokens):
                        if adef.type == xml.XMLAttributeDefinition.NmToken:
                            values = [value]
                        else:
                            values = value.split(' ')
                        for iValue in values:
                            if not is_valid_nmtoken(iValue):
                                self.validity_error(
                                    "Name Token: %s does not match the "
                                    "NmToken production" % iValue)
                    elif adef.type == xml.XMLAttributeDefinition.Notation:
                        if adef.values.get(value, None) is None:
                            self.validity_error(
                                "Notation Attributes: %s is not one of the "
                                "notation names included in the declaration "
                                "of %s" % (value, a))
                    elif adef.type == xml.XMLAttributeDefinition.Enumeration:
                        # must be one of the values
                        if adef.values.get(value, None) is None:
                            self.validity_error(
                                "Enumeration: %s is not one of the NmTokens "
                                "in the declaration of %s" % (value, a))

    def match_xml_name(self, element, name):
        """Tests if *name* is a possible name for *element*.

        element
            A :py:class:`~pyslet.xml20081126.structures.Element`
            instance.

        name
            The name of an end tag, as a string.

        This method is used by the parser to determine if an end tag is
        the end tag of this element.  It is provided as a separate
        method to allow it to be overridden by derived parsers.

        The default implementation simply compares *name* with
        :py:meth:`~pyslet.xml20081126.structures.Element.GetXMLName`"""
        return element.GetXMLName() == name

    def check_expected_particle(self, name):
        """Checks the validity of element name in the current context.

        name
            The name of the element encountered. An empty string for
            *name* indicates the enclosing end tag was found.

        This method also maintains the position of a pointer into the
        element's content model."""
        if self.cursor is not None:
            if not self.cursor.Next(name):
                # content model violation
                expected = string.join(self.cursor.Expected(), ' | ')
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

        If there is no
        :py:class:`~pyslet.xml20081126.structures.Document` instance yet
        this method assumes that it is being called for the root element
        and selects an appropriate class based on the contents of the
        prolog and/or *name*.

        When using the :py:attr:`sgmlOmittag` option *name* may be None
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
            the name of the element (to pass to ChildElement) or None to
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
        context = self.get_context()
        if self.sgmlOmittag:
            if name:
                stag_class = context.get_element_class(name)
                if stag_class is None:
                    stag_class = self.doc.get_element_class(name)
            else:
                stag_class = None
            element_class = context.GetChildClass(stag_class)
            if element_class is not stag_class:
                return element_class, None, True
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
                    if not self.dontCheckWellFormedness and aname in attrs:
                        self.well_formedness_error(
                            "Unique Att Spec: attribute %s appears more than "
                            "once" % aname)
                    attrs[aname] = aValue
                else:
                    self.well_formedness_error(
                        "Expected S, '>' or '/>', found '%s'" % self.the_char)
            except xml.XMLWellFormedError:
                if not self.dontCheckWellFormedness:
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
            :py:attr:`sgmlShorttag` is True and a short form attribute
            value was supplied.

        value
            the attribute value.

        If :py:attr:`dontCheckWellFormedness` is set the parser uses a
        very generous form of parsing attribute values to accomodate
        common syntax errors."""
        production = "[41] Attribute"
        name = self.parse_required_name(production)
        if self.sgmlShorttag:
            # name on its own may be OK
            s = self.parse_s()
            if self.the_char != '=':
                self.buff_text(s)
                return '@' + name, name
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
        if self.dontCheckWellFormedness:
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

        The second case only occurs when the :py:attr:`sgmlOmittag`
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
                        if (self.checkValidity and
                                self.elementType.contentType ==
                                xml.ElementType.Empty):
                            self.validity_error(
                                "Element Valid: comment not allowed in "
                                "element declared EMPTY: %s" %
                                self.elementType.name)
                    elif self.the_char == '[':
                        self.parse_required_literal('[CDATA[')
                        # can CDATA sections imply missing markup?
                        if self.sgmlOmittag and not self.element.IsMixed():
                            # CDATA can only be put in elements that can
                            # contain data!
                            self.buff_text('<![CDATA[')
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
                    if (self.checkValidity and
                            self.elementType.contentType ==
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
                if self.sgmlOmittag and not self.element.IsMixed():
                    # we step in before resolving the reference, just in
                    # case this reference results in white space that is
                    # supposed to be the first data character after the
                    # omitted tag.
                    self.unhandled_data('')
                else:
                    data = self.parse_reference()
                    if (self.checkValidity and
                            self.elementType and
                            self.elementType.contentType ==
                            xml.ElementType.Empty):
                        self.validity_error(
                            "Element Valid: reference not allowed in element "
                            "declared EMPTY: %s" % self.elementType.name)
                    self.handle_data(data, True)
            elif self.the_char is None:
                # end of entity
                if self.sgmlOmittag:
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
        :py:meth:`~pyslet.xml20081126.structures.Element.AddData`
        even if the data is optional white space."""
        if data and self.element:
            if self.checkValidity and self.elementType:
                check_standalone = (
                    self.declared_standalone() and
                    self.elementType.entity is not self.docEntity)
                if (check_standalone and
                        self.elementType.contentType ==
                        xml.ElementType.ElementContent and
                        xml.ContainsS(data)):
                    self.validity_error(
                        "Standalone Document Declaration: white space not "
                        "allowed in element %s (externally defined as "
                        "element content)" % self.elementType.name)
                if self.elementType.contentType == xml.ElementType.Empty:
                    self.validity_error(
                        "Element Valid: content not allowed in element "
                        "declared EMPTY: %s" % self.elementType.name)
                if (self.elementType.contentType ==
                        xml.ElementType.ElementContent and
                        (cdata or not xml.IsWhiteSpace(data))):
                    self.validity_error(
                        "Element Valid: character data is not allowed in "
                        "element %s" % self.elementType.name)
            self.element.AddData(data)
            self.dataCount += len(data)

    def unhandled_data(self, data):
        """[43] content

        data
            A string of unhandled data

        This method is only called when the :py:attr:`sgmlOmittag`
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
            self.buff_text(xml.EscapeCharData(data))
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
        if self.checkValidity and self.dtd:
            etype.BuildModel()
            if not etype.IsDeterministic():
                self.compatibility_error(
                    "Deterministic Content Model: <%s> has non-deterministic "
                    "content model" % etype.name)
            if self.dtd.GetElementType(etype.name) is not None:
                self.validity_error(
                    "Unique Element Type Declaration: <%s> already declared" %
                    etype.name)
            self.dtd.DeclareElementType(etype)

    def parse_content_spec(self, etype):
        """[46] contentspec

        etype
            An :py:class:`~pyslet.xml20081126.structures.ElementType`
            instance.

        Sets the
        :py:attr:`~pyslet.xml20081126.structures.ElementType.contentType`
        and
        :py:attr:`~pyslet.xml20081126.structures.ElementType.contentModel`
        attributes of *etype*, there is no return value."""
        production = "[46] contentspec"
        if self.parse_literal('EMPTY'):
            etype.contentType = xml.ElementType.Empty
            etype.contentModel = None
        elif self.parse_literal('ANY'):
            etype.contentType = xml.ElementType.Any
            etype.contentModel = None
        elif self.parse_literal('('):
            group_entity = self.entity
            self.parse_s()
            if self.parse_literal('#PCDATA'):
                etype.contentType = xml.ElementType.Mixed
                etype.contentModel = self.parse_mixed(True, group_entity)
            else:
                etype.contentType = xml.ElementType.ElementContent
                etype.contentModel = self.parse_children(True, group_entity)
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
            :py:class:`~pyslet.xml20081126.structures.XMLEntity` object.
            If *got_literal* is True then *group_entity* must be the
            entity in which the opening '(' was parsed which started the
            choice group.

        The method returns an instance of
        :py:class:`~pyslet.xml20081126.structures.XMLContentParticle`."""
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
        :py:class:`~pyslet.xml20081126.structures.XMLContentParticle`
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
            :py:class:`~pyslet.xml20081126.structures.XMLContentParticle`
            instance. If present the method assumes that the first
            particle and any following white space has already been
            parsed.

        group_entity
            An optional
            :py:class:`~pyslet.xml20081126.structures.XMLEntity` object.
            If *first_child* is given then *group_entity* must be the
            entity in which the opening '(' was parsed which started the
            choice group.

        Returns an
        :py:class:`~pyslet.xml20081126.structures.XMLChoiceList`
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
                if self.checkValidity and self.entity is not group_entity:
                    self.validity_error(
                        "Proper Group/PE Nesting: found ')' in entity %s" %
                        self.entity.GetName())
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
            :py:class:`~pyslet.xml20081126.structures.XMLContentParticle`
            instance.  If present the method assumes that the first
            particle and any following white space has already been
            parsed.  In this case, *group_entity* must be set to the
            entity which contained the opening '(' literal.

        group_entity
            An optional
            :py:class:`~pyslet.xml20081126.structures.XMLEntity` object,
            see above.

        Returns a
        :py:class:`~pyslet.xml20081126.structures.XMLSequenceList`
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
                if self.checkValidity and self.entity is not group_entity:
                    self.validity_error(
                        "Proper Group/PE Nesting: found ')' in entity %s" %
                        self.entity.GetName())
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
            :py:class:`~pyslet.xml20081126.structures.XMLEntity` object,
            see above.

        Returns an instance of
        :py:class:`~pyslet.xml20081126.structures.XMLChoiceList` with
        occurrence
        :py:attr:`~pyslet.xml20081126.structures.XMLContentParticle.ZeroOrMore`
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
                if self.checkValidity and self.entity is not group_entity:
                    self.validity_error(
                        "Proper Group/PE Nesting: found ')' in entity %s" %
                        self.entity.GetName())
                break
            elif self.the_char == '|':
                self.next_char()
                self.parse_s()
                cp_child = xml.XMLNameParticle()
                cp_child.name = self.parse_required_name(production)
                if self.checkValidity:
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
                    if self.checkValidity:
                        if a.type == xml.XMLAttributeDefinition.ID:
                            if (a.presence !=
                                    xml.XMLAttributeDefinition.Implied and
                                    a.presence !=
                                    xml.XMLAttributeDefinition.Required):
                                self.validity_error(
                                    "ID Attribute Default: ID attribute %s "
                                    "must have a declared default of #IMPLIED "
                                    "or #REQUIRED" % a.name)
                            alist = self.dtd.GetAttributeList(name)
                            if alist:
                                for ia in alist.values():
                                    if (ia.type ==
                                            xml.XMLAttributeDefinition.ID):
                                        self.validity_error(
                                            "One ID per Element Type: "
                                            "attribute %s must not be of type "
                                            "ID, element %s already has an "
                                            "ID attribute" % (a.name, name))
                        elif a.type == xml.XMLAttributeDefinition.Notation:
                            alist = self.dtd.GetAttributeList(name)
                            if alist:
                                for ia in alist.values():
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
                    self.dtd.DeclareAttribute(name, a)

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
        :py:class:`~pyslet.xml20081126.structures.XMLAttributeDefinition`."""
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
            :py:class:`~pyslet.xml20081126.structures.XMLAttributeDefinition`
            instance.

        This method sets the
        :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.type`
        and
        :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.values`
        fields of *a*.

        Note that, to avoid unnecessary look ahead, this method does not
        call
        :py:meth:`parse_string_type` or
        :py:meth:`parse_enumerated_type`."""
        if self.parse_literal('CDATA'):
            a.type = xml.XMLAttributeDefinition.CData
            a.values = None
        elif self.parse_literal('NOTATION'):
            a.type = xml.XMLAttributeDefinition.Notation
            a.values = self.parse_notation_type(True)
        elif self.the_char == '(':
            a.type = xml.XMLAttributeDefinition.Enumeration
            a.values = self.parse_enumeration()
        else:
            self.parse_tokenized_type(a)

    def parse_string_type(self, a):
        """[55] StringType

        a
            A required
            :py:class:`~pyslet.xml20081126.structures.XMLAttributeDefinition`
            instance.

        This method sets the
        :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.type`
        and
        :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.values`
        fields of *a*.

        This method is provided for completeness.  It is not called
        during normal parsing operations."""
        production = "[55] StringType"
        self.parse_required_literal('CDATA', production)
        a.type = xml.XMLAttributeDefinition.CData
        a.values = None

    def parse_tokenized_type(self, a):
        """[56] TokenizedType

        a
            A required
            :py:class:`~pyslet.xml20081126.structures.XMLAttributeDefinition`
            instance.

        This method sets the
        :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.type`
        and
        :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.values`
        fields of *a*."""
        production = "[56] TokenizedType"
        if self.parse_literal('ID'):
            if self.parse_literal('REF'):
                if self.parse_literal('S'):
                    a.type = xml.XMLAttributeDefinition.IDRefs
                else:
                    a.type = xml.XMLAttributeDefinition.IDRef
            else:
                a.type = xml.XMLAttributeDefinition.ID
        elif self.parse_literal('ENTIT'):
            if self.parse_literal('Y'):
                a.type = xml.XMLAttributeDefinition.Entity
            elif self.parse_literal('IES'):
                a.type = xml.XMLAttributeDefinition.Entities
            else:
                self.well_formedness_error(
                    production + ": Expected 'ENTITY' or 'ENTITIES'")
        elif self.parse_literal('NMTOKEN'):
            if self.parse_literal('S'):
                a.type = xml.XMLAttributeDefinition.NmTokens
            else:
                a.type = xml.XMLAttributeDefinition.NmToken
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
            :py:class:`~pyslet.xml20081126.structures.XMLAttributeDefinition`
            instance.

        This method sets the
        :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.type`
        and
        :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.values`
        fields of *a*.

        This method is provided for completeness.  It is not called
        during normal parsing operations."""
        if self.parse_literal('NOTATION'):
            a.type = xml.XMLAttributeDefinition.Notation
            a.values = self.parse_notation_type(True)
        elif self.the_char == '(':
            a.type = xml.XMLAttributeDefinition.Enumeration
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
            if self.checkValidity and name in value:
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
                if self.checkValidity and token in value:
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
            :py:class:`~pyslet.xml20081126.structures.XMLAttributeDefinition`
            instance.

        This method sets the
        :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.presence`
        and
        :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.defaultValue`
        fields of *a*."""
        if self.parse_literal('#REQUIRED'):
            a.presence = xml.XMLAttributeDefinition.Required
            a.defaultValue = None
        elif self.parse_literal('#IMPLIED'):
            a.presence = xml.XMLAttributeDefinition.Implied
            a.defaultValue = None
        else:
            if self.parse_literal('#FIXED'):
                a.presence = xml.XMLAttributeDefinition.Fixed
                self.parse_required_s("[60] DefaultDecl")
            else:
                a.presence = xml.XMLAttributeDefinition.Default
            a.defaultValue = self.parse_att_value()
            if a.type != xml.XMLAttributeDefinition.CData:
                a.defaultValue = xml.NormalizeSpace(a.defaultValue)
            if self.checkValidity:
                if (a.type == xml.XMLAttributeDefinition.IDRef or
                        a.type == xml.XMLAttributeDefinition.Entity):
                    if not xml.IsValidName(a.defaultValue):
                        self.validity_error(
                            "Attribute Default Value Syntactically Correct: "
                            "%s does not match the Name production" %
                            xml.EscapeCharData(a.defaultValue, True))
                elif (a.type == xml.XMLAttributeDefinition.IDRefs or
                        a.type == xml.XMLAttributeDefinition.Entities):
                    values = a.defaultValue.split(' ')
                    for iValue in values:
                        if not xml.IsValidName(iValue):
                            self.validity_error(
                                "Attribute Default Value Syntactically "
                                "Correct: %s does not match the Names "
                                "production" %
                                xml.EscapeCharData(a.defaultValue, True))
                elif a.type == xml.XMLAttributeDefinition.NmToken:
                    if not is_valid_nmtoken(a.defaultValue):
                        self.validity_error(
                            "Attribute Default Value Syntactically Correct: "
                            "%s does not match the Nmtoken production" %
                            xml.EscapeCharData(a.defaultValue, True))
                elif a.type == xml.XMLAttributeDefinition.NmTokens:
                    values = a.defaultValue.split(' ')
                    for iValue in values:
                        if not is_valid_nmtoken(iValue):
                            self.validity_error(
                                "Attribute Default Value Syntactically "
                                "Correct: %s does not match the Nmtokens "
                                "production" %
                                xml.EscapeCharData(a.defaultValue, True))
                elif (a.type == xml.XMLAttributeDefinition.Notation or
                        a.type == xml.XMLAttributeDefinition.Enumeration):
                    if a.values.get(a.defaultValue, None) is None:
                        self.validity_error(
                            "Attribute Default Value Syntactically Correct: "
                            "%s is not one of the allowed enumerated values" %
                            xml.EscapeCharData(a.defaultValue, True))

    def parse_conditional_sect(self, got_literal_entity=None):
        """[61] conditionalSect

        got_literal_entity
            An optional
            :py:class:`~pyslet.xml20081126.structures.XMLEntity` object.
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
            :py:class:`~pyslet.xml20081126.structures.XMLEntity` object.
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
        if self.checkValidity and self.entity is not got_literal_entity:
            self.validity_error(
                production + ": Proper Conditional Section/PE Nesting")
        self.parse_required_literal('[', production)
        self.parse_ext_subset_decl()
        if self.checkValidity and self.entity is not got_literal_entity:
            self.validity_error(
                production + ": Proper Conditional Section/PE Nesting")
        self.parse_required_literal(']]>', production)

    def parse_ignore_sect(self, got_literal_entity=None):
        """[63] ignoreSect

        got_literal_entity
            An optional
            :py:class:`~pyslet.xml20081126.structures.XMLEntity` object.
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
        if self.checkValidity and self.entity is not got_literal_entity:
            self.validity_error(
                "Proper Conditional Section/PE Nesting: [ must not be in "
                "replacement text of %s" % self.entity.GetName())
        self.parse_required_literal('[', production)
        self.parse_ignore_sect_contents()
        if self.checkValidity and self.entity is not got_literal_entity:
            self.validity_error(
                "Proper Conditional Section/PE Nesting: ]]> must not be in "
                "replacement text of %s" % self.entity.GetName())
        self.parse_required_literal(']]>', production)

    def parse_ignore_sect_contents(self):
        """[64] ignoreSectContents

        Parses the contents of an ignored section.  The method returns
        no data."""
        self.parse_ignore()
        if self.parse_literal('<!['):
            self.parse_ignore_sect_contents()
            self.parse_required_literal(']]>', "[64] ignoreSectContents")
            self.parse_ignore()

    def parse_ignore(self):
        """[65] Ignore

        Parses a run of characters in an ignored section.  This method
        returns no data."""
        while xml.IsChar(self.the_char):
            if self.the_char == '<' and self.parse_literal('<!['):
                self.buff_text(u'<![')
                break
            elif self.the_char == ']' and self.parse_literal(']]>'):
                self.buff_text(u']]>')
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
            data = unichr(int(digits, 16))
        else:
            qualifier = ''
            digits = self.parse_required_decimal_digits(production)
            data = unichr(int(digits))
        self.parse_required_literal(';', production)
        if self.refMode == XMLParser.RefModeInDTD:
            raise xml.XMLForbiddenEntityReference(
                "&#%s%s; forbidden by context" % (qualifier, digits))
        elif self.refMode == XMLParser.RefModeAsAttributeValue:
            data = "&#%s%s;" % (qualifier, digits)
        elif not xml.IsChar(data):
            raise xml.XMLWellFormedError(
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
        if self.dontCheckWellFormedness:
            name = self.parse_name()
            if not name:
                return '&'
        else:
            name = self.parse_required_name(production)
        if self.dontCheckWellFormedness:
            self.parse_literal(';')
        else:
            self.parse_required_literal(';', production)
        if self.refMode == XMLParser.RefModeInEntityValue:
            return "&%s;" % name
        elif self.refMode in (XMLParser.RefModeAsAttributeValue,
                              XMLParser.RefModeInDTD):
            raise xml.XMLForbiddenEntityReference(
                "&%s; forbidden by context" % name)
        else:
            data = self.lookup_predefined_entity(name)
            if data is not None:
                return data
            else:
                e = None
                if self.dtd:
                    e = self.dtd.GetEntity(name)
                    if (e and self.declared_standalone() and
                            e.entity is not self.docEntity):
                        self.validity_error(
                            "Standalone Document Declaration: reference to "
                            "entity %s not allowed (externally defined)" %
                            e.GetName())
                if e is not None:
                    if e.notation is not None:
                        self.well_formedness_error(
                            "Parsed Entity: &%s; reference to unparsed "
                            "entity not allowed" % name)
                    else:
                        if (not self.dontCheckWellFormedness and
                                self.refMode ==
                                XMLParser.RefModeInAttributeValue and
                                e.IsExternal()):
                            self.well_formedness_error(
                                "No External Entity References: &%s; not "
                                "allowed in attribute value" % name)
                        if e.IsOpen() or (e is entity):
                            # if the last char of the entity is a ';'
                            # closing a recursive entity reference then
                            # the entity will have been closed so we
                            # must check the context of the reference #
                            # too, not just whether it is currently open
                            self.well_formedness_error(
                                "No Recursion: entity &%s; is already open" %
                                name)
                        e.Open()
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
                e = self.dtd.GetParameterEntity(name)
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
                            e.GetName())
                if self.checkValidity:
                    # An external markup declaration is defined as a
                    # markup declaration occurring in the external
                    # subset or in a parameter entity (external or
                    # internal, the latter being included because
                    # non-validating processors are not required to read
                    # them
                    if e.IsOpen() or (e is entity):
                        self.well_formedness_error(
                            "No Recursion: entity %%%s; is already open" %
                            name)
                    if self.refMode == XMLParser.RefModeInEntityValue:
                        # Parameter entities are fed back into the parser
                        # somehow
                        e.Open()
                        self.push_entity(e)
                    elif self.refMode == XMLParser.RefModeInDTD:
                        e.OpenAsPE()
                        self.push_entity(e)
            return ''

    def parse_entity_decl(self, got_literal=False):
        """[70] EntityDecl

        got_literal
            If True, assumes that the literal '<!ENTITY' has already
            been parsed.

        Returns an instance of either
        :py:class:`~pyslet.xml20081126.structures.XMLGeneralEntity` or
        :py:class:`~pyslet.xml20081126.structures.XMLParameterEntity`
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
        if e.IsExternal():
            # Resolve the external ID relative to xentity
            e.location = self.resolve_external_id(e.definition, xentity)
        if self.dtd:
            e.entity = dentity
            self.dtd.DeclareEntity(e)
        return e

    def parse_ge_decl(self, got_literal=False):
        """[71] GEDecl

        got_literal
            If True, assumes that the literal '<!ENTITY' *and the
            required S* has already been parsed.

        Returns an instance of
        :py:class:`~pyslet.xml20081126.structures.XMLGeneralEntity`."""
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
        :py:class:`~pyslet.xml20081126.structures.XMLParameterEntity`."""
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
            :py:attr:`~pyslet.xml20081126.structures.XMLGeneralEntity`
            instance.

        This method sets the
        :py:attr:`~pyslet.xml20081126.structures.XMLGeneralEntity.definition`
        and
        :py:attr:`~pyslet.xml20081126.structures.XMLGeneralEntity.notation`
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
            :py:class:`~pyslet.xml20081126.structures.XMLParameterEntity`
            instance.

        This method sets the
        :py:attr:`~pyslet.xml20081126.structures.XMLParameterEntity.definition`
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
        :py:class:`~pyslet.xml20081126.structures.XMLExternalID`
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
        # catch for dontCheckWellFormedness ??
        return xml.XMLExternalID(pub_id, system_id)

    def resolve_external_id(self, external_id, entity=None):
        """[75] ExternalID: resolves an external ID, returning a URI.

        external_id
            A :py:class:`~pyslet.xml20081126.structures.XMLExternalID`
            instance.

        entity
            An optional
            :py:class:`~pyslet.xml20081126.structures.XMLEntity`
            instance.  Can be used to force the resolution of relative
            URIs to be relative to the base of the given entity.  If it
            is None then the currently open external entity (where
            available) is used instead.

        Returns an instance of :py:class:`pyslet.rfc2396.URI` or None if
        the external ID cannot be resolved.

        The default implementation simply calls
        :py:meth:`~pyslet.xml20081126.structures.XMLExternalID.get_location`
        with the entity's base URL and ignores the public ID.  Derived
        parsers may recognize public identifiers and resolve
        accordingly."""
        base = None
        if entity is None:
            entity = self.get_external_entity()
        if entity:
            base = entity.location
        return external_id.get_location(base)

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
        :py:class:`~pyslet.xml20081126.structures.XMLTextDeclaration`
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
            self.entity.ChangeEncoding(encoding)
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
        if xml.EncNameStartCharClass.Test(self.the_char):
            name.append(self.the_char)
            self.next_char()
            while xml.EncNameCharClass.Test(self.the_char):
                name.append(self.the_char)
                self.next_char()
        if name:
            return string.join(name, '')
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
            if self.checkValidity and not (self.dtd.GetNotation(name) is None):
                self.validity_error(
                    "Unique Notation Name: %s has already been declared" %
                    name)
            self.dtd.DeclareNotation(xml.XMLNotation(name, xid))

    def parse_public_id(self):
        """[83] PublicID

        The literal string is returned without the PUBLIC prefix or the
        enclosing quotes."""
        production = "[83] PublicID"
        self.parse_required_literal('PUBLIC', production)
        self.parse_required_s(production)
        return self.parse_pubid_literal()
