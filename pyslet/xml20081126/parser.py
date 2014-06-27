#! /usr/bin/env python

from pyslet.xml20081126.structures import *


def IsValidNmToken(nmToken):
    """Tests if nmToken is a string matching production [5] Nmtoken"""
    if nmToken:
        for c in nmToken:
            if not IsNameChar(c):
                return False
        return True
    else:
        return False


class XMLParser:

    DocumentClassTable = {}
    """A dictionary mapping doctype parameters onto class objects.
	
	For more information about how this is used see :py:meth:`GetDocumentClass` and
	:py:func:`~pyslet.xml20081126.structures.RegisterDocumentClass`."""

    RefModeNone = 0				#: Default constant used for setting :py:attr:`refMode`
    RefModeInContent = 1			#: Treat references as per "in Content" rules
    # : Treat references as per "in Attribute Value" rules
    RefModeInAttributeValue = 2
    # : Treat references as per "as Attribute Value" rules
    RefModeAsAttributeValue = 3
    RefModeInEntityValue = 4		#: Treat references as per "in EntityValue" rules
    RefModeInDTD = 5				#: Treat references as per "in DTD" rules

    PredefinedEntities = {
        'lt': '<',
        'gt': '>',
        'apos': "'",
        'quot': '"',
        'amp': '&'}
    """A mapping from the names of the predefined entities (lt, gt, amp, apos, quot) to their
	replacement characters."""

    def __init__(self, entity):
        """Returns an XMLParser object constructed from the :py:class:`~pyslet.xml20081126.structures.XMLEntity` to parse.

        XMLParser objects are used to parse entities for the constructs defined
        by the numbered productions in the XML specification.

        XMLParser has a number of optional attributes, all of which default to
        False. Attributes with names started 'check' increase the strictness of
        the parser.  All other parser flags, if set to True, will not result in
        a conforming XML processor."""
        self.checkValidity = False
        """checks XML validity constraints
		
		If *checkValidity* is True, and all other options are left at their
		default (False) setting then the parser will behave as a validating XML
		parser."""
        self.valid = None
        """Flag indicating if the document is valid, only set if :py:attr:`checkValidity` is True."""
        self.nonFatalErrors = []
        """A list of non-fatal errors discovered during parsing, only populated if :py:attr:`checkValidity` is True."""
        self.checkCompatibility = False
        """checks XML compatibility constraints; will cause :py:attr:`checkValidity` to be set to True when parsing."""
        self.checkAllErrors = False
        """checks all constraints; will cause :py:attr:`checkValidity` and
		:py:attr:`checkCompatibility` to be set to True when parsing."""
        self.raiseValidityErrors = False		#: treats validity errors as fatal errors
        # : provides a loose parser for XML-like documents
        self.dontCheckWellFormedness = False
        #: See http://www.w3.org/TR/unicode-xml/
        self.unicodeCompatibility = False
        #: option that simulates SGML's NAMECASE GENERAL YES
        self.sgmlNamecaseGeneral = False
        #: option that simulates SGML's NAMECASE ENTITY YES
        self.sgmlNamecaseEntity = False
        self.sgmlOmittag = False				#: option that simulates SGML's OMITTAG YES
        #: option that simulates SGML's SHORTTAG YES
        self.sgmlShorttag = False
        self.sgmlContent = False
        """This option simulates some aspects of SGML content handling based on class
		attributes of the element being parsed.
		
		-	Element classes with XMLCONTENT=:py:data:`XMLEmpty` are treated
			as elements declared EMPTY, these elements are treated as if they
			were introduced with an empty element tag even if they weren't, as per SGML's
			rules.  Note that this SGML feature "has nothing to do with markup
			minimization" (i.e., :py:attr:`sgmlOmittag`.)
		"""
        self.refMode = XMLParser.RefModeNone
        """The current parser mode for interpreting references.

		XML documents can contain five different types of reference: parameter
		entity, internal general entity, external parsed entity, (external)
		unparsed entity and character entity.

		The rules for interpreting these references vary depending on the
		current mode of the parser, for example, in content a reference to an
		internal entity is replaced, but in the definition of an entity value it
		is not.  This means that the behaviour of the :py:meth:`ParseReference`
		method will differ depending on the mode.

		The parser takes care of setting the mode automatically but if you wish
		to use some of the parsing methods in isolation to parse fragments of
		XML documents, then you will need to set the *refMode* directly using
		one of the RefMode* family of constants defined above."""
        self.entity = entity					#: The current entity being parsed
        self.entityStack = []
        if self.entity:
            # : the current character; None indicates end of stream
            self.the_char = self.entity.the_char
        else:
            self.the_char = None
        self.buff = []
        self.stagBuffer = None
        self.declaration = None
        """The declaration parsed or None."""
        self.dtd = None
        """The documnet type declaration of the document being parsed.
		
		This member is initialised to None as well-formed XML documents are not
		required to have an associated dtd."""
        self.doc = None
        """The document being parsed."""
        self.docEntity = entity
        """The document entity."""
        self.element = None
        """The current element being parsed."""
        self.elementType = None
        """The element type of the current element."""
        self.idTable = {}
        self.idRefTable = {}
        self.cursor = None
        self.dataCount = 0
        self.noPERefs = False
        self.gotPERef = False

    def GetContext(self):
        if self.element is None:
            return self.doc
        else:
            return self.element

    def NextChar(self):
        """Moves to the next character in the stream.

        The current character can always be read from :py:attr:`the_char`.  If
        there are no characters left in the current entity then entities are
        popped from an internal entity stack automatically."""
        if self.buff:
            self.buff = self.buff[1:]
        if self.buff:
            self.the_char = self.buff[0]
        else:
            self.entity.NextChar()
            self.the_char = self.entity.the_char
            while self.the_char is None and self.entityStack:
                self.entity.Close()
                self.entity = self.entityStack.pop()
                self.the_char = self.entity.the_char

    def BuffText(self, unusedChars):
        if unusedChars:
            if self.buff:
                self.buff = list(unusedChars) + self.buff
            else:
                self.buff = list(unusedChars)
                if self.entity.the_char is not None:
                    self.buff.append(self.entity.the_char)
            self.the_char = self.buff[0]

    def GetBuff(self):
        if len(self.buff) > 1:
            return string.join(self.buff[1:], '')
        else:
            return ''

    def PushEntity(self, entity):
        """Starts parsing *entity*

        :py:attr:`the_char` is set to the current character in the entity's
        stream.  The current entity is pushed onto an internal stack and will be
        resumed when this entity has been parsed completely.

        Note that in the degenerate case where the entity being pushed is empty
        (or is already positioned at the end of the file) then PushEntity does
        nothing."""
        if entity.the_char is not None:
            self.entityStack.append(self.entity)
            self.entity = entity
            self.entity.flags = {}
            self.the_char = self.entity.the_char
        else:
            # Harsh but fair, if we had reason to believe that this entity used UTF-16 but it
            # was completely empty (not even a BOM) then that is an error.
            self.CheckEncoding(entity, None)
        if entity.buffText:
            self.BuffText(entity.buffText)

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

    def CheckEncoding(self, entity, declaredEncoding):
        """Checks the entity against the declared encoding (if any) and the rules on entity encodings."""
        if not self.EncodingNotRequired.get(entity.encoding.lower(), False):
            # Encoding required!
            if declaredEncoding is None:
                self.ProcessingError(
                    "Encoding declaration required in %s (%s) but missing" %
                    (entity.GetName(), entity.encoding))
        if self.BOMRequired.get(entity.encoding.lower(), False):
            if not (entity.bom or (declaredEncoding and declaredEncoding.lower() == 'iso-10646-ucs-2')):
                self.ProcessingError(
                    "Byte order mark required in %s (%s) was missing" %
                    (entity.GetName(), entity.encoding))

    def GetExternalEntity(self):
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

    def Standalone(self):
        """True if the document being parsed should be treated as standalone.

        A document may be declared standalone or it may effectively be standalone
        due to the absence of a DTD, or the absence of an external DTD subset and
        parameter entity references."""
        if self.DeclaredStandalone():
            return True
        if self.dtd is None or self.dtd.externalID is None:
            # no dtd or just an internal subset
            return not self.gotPERef

    def DeclaredStandalone(self):
        """True if the current document was declared standalone."""
        return self.declaration and self.declaration.standalone

    def WellFormednessError(
            self,
            msg="well-formedness error",
            errorClass=XMLWellFormedError):
        """Raises an XMLWellFormedError error.

        Called by the parsing methods whenever a well-formedness constraint is
        violated. The method takes an optional message string, *msg* and an
        optional error class which must be a class object derived from
        py:class:`XMLWellFormednessError`.

        The method raises an instance of *errorClass* and does not return.  This
        method can be overridden by derived parsers to implement more
        sophisticated error logging."""
        raise errorClass("%s: %s" % (self.entity.GetPositionStr(), msg))

    def ValidityError(self, msg="validity error", error=XMLValidityError):
        """Called when the parser encounters a validity error.

        The method takes an optional message string, *msg* and an optional error
        class or instance which must be a (class) object derived from
        py:class:`XMLValidityError`.

        The behaviour varies depending on the setting of the
        :py:attr:`checkValidity` and :py:attr:`raiseValidityErrors` options. The
        default (both False) causes validity errors to be ignored.  When
        checking validity an error message is logged to
        :py:attr:`nonFatalErrors` and :py:attr:`valid` is set to False.
        Furthermore, if :py:attr:`raiseValidityErrors` is True *error* is raised
        (or a new instance of *error* is raised) and parsing terminates.

        This method can be overridden by derived parsers to implement more
        sophisticated error logging."""
        if self.checkValidity:
            self.valid = False
            if isinstance(error, XMLValidityError):
                self.nonFatalErrors.append(
                    "%s: %s (%s)" %
                    (self.entity.GetPositionStr(), msg, str(error)))
                if self.raiseValidityErrors:
                    raise error
            elif issubclass(error, XMLValidityError):
                msg = "%s: %s" % (self.entity.GetPositionStr(), msg)
                self.nonFatalErrors.append(msg)
                if self.raiseValidityErrors:
                    raise error(msg)
            else:
                raise TypeError(
                    "ValidityError expected class or instance of XMLValidityError (found %s)" %
                    repr(error))

    def CompatibilityError(self, msg="compatibility error"):
        """Called when the parser encounters a compatibility error.

        The method takes an optional message string, *msg*.

        The behaviour varies depending on the setting of the
        :py:attr:`checkCompatibility` flag.  The default (False) causes
        compatibility errors to be ignored.  When checking compatibility an
        error message is logged to :py:attr:`nonFatalErrors`.

        This method can be overridden by derived parsers to implement more
        sophisticated error logging."""
        if self.checkCompatibility:
            self.nonFatalErrors.append(
                "%s: %s" % (self.entity.GetPositionStr(), msg))

    def ProcessingError(self, msg="Processing error"):
        """Called when the parser encounters a general processing error.

        The method takes an optional message string, *msg* and an optional error
        class or instance which must be a (class) object derived from
        py:class:`XMLProcessingError`.

        The behaviour varies depending on the setting of the
        :py:attr:`checkAllErrors` flag.  The default (False) causes processing
        errors to be ignored.  When checking all errors an error message is
        logged to :py:attr:`nonFatalErrors`.

        This method can be overridden by derived parsers to implement more
        sophisticated error logging."""
        if self.checkAllErrors:
            self.nonFatalErrors.append(
                "%s: %s" % (self.entity.GetPositionStr(), msg))

    def ParseLiteral(self, match):
        """Parses a literal string, passed in *match*.

        Returns True if *match* is successfully parsed and False otherwise.
        There is no partial matching, if *match* is not found then the parser is
        left in its original position."""
        matchLen = 0
        for m in match:
            if m != self.the_char and (not self.sgmlNamecaseGeneral or
                                       self.the_char is None or
                                       m.lower() != self.the_char.lower()):
                self.BuffText(match[:matchLen])
                break
            matchLen += 1
            self.NextChar()
        return matchLen == len(match)

    def ParseRequiredLiteral(self, match, production="Literal String"):
        """Parses a required literal string raising a wellformed error if not matched.

        *production* is an optional string describing the context in which the
        literal was expected.
        """
        if not self.ParseLiteral(match):
            self.WellFormednessError("%s: Expected %s" % (production, match))

    def ParseDecimalDigits(self):
        """Parses a, possibly empty, string of decimal digits matching [0-9]*."""
        data = []
        while self.the_char is not None and self.the_char in "0123456789":
            data.append(self.the_char)
            self.NextChar()
        return string.join(data, '')

    def ParseRequiredDecimalDigits(self, production="Digits"):
        """Parses a required sring of decimal digits matching [0-9]+.

        *production* is an optional string describing the context in which the
        digits were expected."""
        digits = self.ParseDecimalDigits()
        if not digits:
            self.WellFormednessError(production + ": Expected [0-9]+")
        return digits

    def ParseHexDigits(self):
        """Parses a, possibly empty, string of hexadecimal digits matching [0-9a-fA-F]."""
        data = []
        while self.the_char is not None and self.the_char in "0123456789abcdefABCDEF":
            data.append(self.the_char)
            self.NextChar()
        return string.join(data, '')

    def ParseRequiredHexDigits(self, production="Hex Digits"):
        """Parses a required sring of hexadecimal digits matching [0-9a-fA-F].

        *production* is an optional string describing the context in which the
        hexadecimal digits were expected."""
        digits = self.ParseHexDigits()
        if not digits:
            self.WellFormednessError(production + ": Expected [0-9a-fA-F]+")
        return digits

    def ParseQuote(self, q=None):
        """Parses the quote character, *q*, or one of "'" or '"' if q is None.

        Returns the character parsed or raises a well formed error."""
        if q:
            if self.the_char == q:
                self.NextChar()
                return q
            else:
                self.WellFormednessError("Expected %s" % q)
        elif self.the_char == '"' or self.the_char == "'":
            q = self.the_char
            self.NextChar()
            return q
        else:
            self.WellFormednessError("Expected '\"' or \"'\"")

    def ParseDocument(self, doc=None):
        """[1] document: parses an Document.

        *doc* is the :py:class:`~pyslet.xml20081126.structures.Document`
        instance that will be parsed.  The declaration, dtd and elements are
        added to this document.  If *doc* is None then a new instance is created
        using :py:meth:`GetDocumentClass` to identify the correct class to use
        to represent the document based on information in the prolog or, if the
        prolog lacks a declaration, the root element.

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
        self.ParseProlog()
        if self.doc is None:
            if self.dtd.name is not None:
                # create the document based on information in the DTD
                self.doc = self.GetDocumentClass(self.dtd)()
        self.ParseElement()
        if self.checkValidity:
            for idref in self.idRefTable.keys():
                if not idref in self.idTable:
                    self.ValidityError(
                        "IDREF: %s does not match any ID attribute value")
        self.ParseMisc()
        if self.the_char is not None and not self.dontCheckWellFormedness:
            self.WellFormednessError(
                "Unparsed characters in entity after document: %s" %
                repr(
                    self.the_char))
        return self.doc

    def GetDocumentClass(self, dtd):
        """Returns a class object derived from
        :py:class:`~pyslet.xml20081126.structures.Document` suitable for
        representing a document with the given document type declaration.

        In cases where no doctype declaration is made a dummy declaration is
        created based on the name of the root element.  For example, if the root
        element is called "database" then the dtd is treated as if it was
        declared as follows::

        <!DOCTYPE database>

        This default implementation uses the following three pieces of
        information to locate class registered with
        :py:func:`~pyslet.xml20081126.structures.RegisterDocumentClass`.  The
        PublicID, SystemID and the name of the root element.  If an exact match
        is not found then wildcard matches are attempted, ignoring the SystemID,
        PublicID and finally the root element in turn.  If a document class
        still cannot be found then wildcard matches are tried matching *only*
        the PublicID, SystemID and root element in turn.

        If no document class cab be found,
        :py:class:`~pyslet.xml20081126.structures.Document` is returned."""
        rootName = dtd.name
        if dtd.externalID is None:
            publicID = None
            systemID = None
            docClass = XMLParser.DocumentClassTable.get(
                (rootName, None, None), None)
        else:
            publicID = dtd.externalID.public
            systemID = dtd.externalID.system
            docClass = XMLParser.DocumentClassTable.get(
                (rootName, publicID, systemID), None)
            if docClass is None:
                docClass = XMLParser.DocumentClassTable.get(
                    (rootName, publicID, None), None)
            if docClass is None:
                docClass = XMLParser.DocumentClassTable.get(
                    (rootName, None, systemID), None)
            if docClass is None:
                docClass = XMLParser.DocumentClassTable.get(
                    (None, publicID, systemID), None)
            if docClass is None:
                docClass = XMLParser.DocumentClassTable.get(
                    (None, publicID, None), None)
            if docClass is None:
                docClass = XMLParser.DocumentClassTable.get(
                    (None, None, systemID), None)
            if docClass is None:
                docClass = XMLParser.DocumentClassTable.get(
                    (rootName, None, None), None)
        if docClass is None:
            docClass = Document
        return docClass

    #	Production [2] is implemented with the function IsChar

    def IsS(self):
        """By default just calls the module level :py:func:`~pyslet.xml20081126.structures.IsS`

        In Unicode compatibility mode the function maps the unicode white space
        characters at code points 2028 and 2029 to line feed and space
        respectively."""
        if self.unicodeCompatibility:
            if self.the_char == u"\u2028":
                self.the_char = "\n"
            elif self.the_char == u"\u2029":
                self.the_char = ' '
        return IsS(self.the_char)

    def ParseS(self):
        """[3] S: Parses white space from the stream matching the production for S.

        If there is no white space at the current position then an empty string
        is returned.

        The productions in the specification do not make explicit mention of
        parameter entity references, they are covered by the general statement
        that "Parameter entity references are recognized anwhere in the DTD..."
        In practice, this means that while parsing the DTD, anywhere that an S
        is permitted a parameter entity reference may also be recognized.  This
        method implements this behaviour, recognizing parameter entity references
        within S when :py:attr:`refMode` is :py:attr:`RefModeInDTD`."""
        s = []
        sLen = 0
        while True:
            if self.IsS():
                s.append(self.the_char)
                self.NextChar()
            elif self.the_char == '%' and self.refMode == XMLParser.RefModeInDTD:
                self.NextChar()
                if IsNameStartChar(self.the_char):
                    self.ParsePEReference(True)
                else:
                    # '%' followed by anything other than name start is not a reference.
                    self.BuffText('%')
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
            sLen += 1
        return string.join(s, '')

    def ParseRequiredS(self, production="[3] S"):
        """[3] S: Parses required white space from the stream.

        If there is no white space then a well-formedness error is raised.
        *production* is an optional string describing the context in which the
        space was expected."""
        if not self.ParseS() and not self.dontCheckWellFormedness:
            self.WellFormednessError(
                production + ": Expected white space character")

    # Production [4] is implemented with the function IsNameStartChar
    # Production [4a] is implemented with the function IsNameChar.

    def ParseName(self):
        """[5] Name: parses a Name

        The name is returned as a unicode string.  If no Name can be parsed then
        None is returned."""
        name = []
        if IsNameStartChar(self.the_char):
            name.append(self.the_char)
            self.NextChar()
            while IsNameChar(self.the_char):
                name.append(self.the_char)
                self.NextChar()
        if name:
            return string.join(name, '')
        else:
            return None

    def ParseRequiredName(self, production="Name"):
        """[5] Name: Parses a required Name.

        If no name can be parsed then a well-formed error is raised."""
        name = self.ParseName()
        if name is None:
            self.WellFormednessError(production + ": Expected NameStartChar")
        return name

    def ParseNames(self):
        """ [6] Names: parses a list of Names.

        This method returns a tuple of unicode strings.  If no names can be
        parsed then None is returned."""
        names = []
        name = self.ParseName()
        if name is None:
            return None
        names.append(name)
        while self.the_char == u' ':
            self.NextChar()
            name = self.ParseName()
            if name is None:
                self.BuffText(u' ')
                break
            names.append(name)
        if names:
            return names
        else:
            return None

    def ParseNmtoken(self):
        """[7] Nmtoken: parses a single Nmtoken.

        If no Nmtoken can be parsed then None is returned."""
        nmtoken = []
        while IsNameChar(self.the_char):
            nmtoken.append(self.the_char)
            self.NextChar()
        if nmtoken:
            return string.join(nmtoken, '')
        else:
            return None

    def ParseNmtokens(self):
        """[8] Nmtokens: parses a list of Nmtokens.

        This method returns a tuple of unicode strings.  If no tokens can be
        parsed then None is returned."""
        nmtokens = []
        nmtoken = self.ParseNmtoken()
        if nmtoken is None:
            return None
        nmtokens.append(nmtoken)
        while self.the_char == u' ':
            self.NextChar()
            nmtoken = self.ParseNmtoken()
            if nmtoken is None:
                self.BuffText(u' ')
                break
            nmtokens.append(nmtoken)
        if nmtokens:
            return nmtokens
        else:
            return None

    def ParseEntityValue(self):
        """[9] EntityValue: parses an EntityValue, returning it as a unicode string.

        This method automatically expands other parameter entity references but
        does not expand general or character references."""
        saveMode = self.refMode
        qEntity = self.entity
        q = self.ParseQuote()
        self.refMode = XMLParser.RefModeInEntityValue
        value = []
        while True:
            if self.the_char == '&':
                value.append(self.ParseReference())
            elif self.the_char == '%':
                self.ParsePEReference()
            elif self.the_char == q:
                if self.entity is qEntity:
                    self.NextChar()
                    break
                else:
                    # a quote but in a different entity is treated as data
                    value.append(self.the_char)
                    self.NextChar()
            elif IsChar(self.the_char):
                value.append(self.the_char)
                self.NextChar()
            elif self.the_char is None:
                self.WellFormednessError("Incomplete EntityValue")
            else:
                self.WellFormednessError("Unexpected data in EntityValue")
        self.refMode = saveMode
        return string.join(value, '')

    def ParseAttValue(self):
        """[10] AttValue: parses an attribute value.

        The value is returned without the surrounding quotes and with any references
        expanded.

        The behaviour of this method is affected significantly by the setting of
        the :py:attr:`dontCheckWellFormedness` flag.  When set, attribute values
        can be parsed without surrounding quotes.  For compatibility with SGML
        these values should match one of the formal value types (e.g., Name) but
        this is not enforced so values like width=100% can be parsed without
        error."""
        production = "[10] AttValue"
        value = []
        try:
            q = self.ParseQuote()
            end = ''
        except XMLWellFormedError:
            if not self.dontCheckWellFormedness:
                raise
            q = None
            end = '<"\'> \t\r\n'
        qEntity = self.entity
        saveMode = self.refMode
        self.refMode = XMLParser.RefModeInAttributeValue
        while True:
            try:
                if self.the_char is None:
                    self.WellFormednessError(production + ":EOF in AttValue")
                elif self.the_char == q:
                    if self.entity is qEntity:
                        self.NextChar()
                        break
                    else:
                        value.append(self.the_char)
                        self.NextChar()
                elif self.the_char in end and self.entity is qEntity:
                    # only when not checking well-formedness mode only
                    break
                elif self.the_char == '&':
                    refData = self.ParseReference()
                    value.append(refData)
                elif self.IsS():
                    value.append(unichr(0x20))
                    self.NextChar()
                elif self.the_char == '<':
                    self.WellFormednessError("No < in Attribute Values")
                else:
                    value.append(self.the_char)
                    self.NextChar()
            except XMLWellFormedError:
                if not self.dontCheckWellFormedness:
                    raise
                elif self.the_char == '<':
                    value.append(self.the_char)
                    self.NextChar()
                elif self.the_char is None:
                    break
        self.refMode = saveMode
        return string.join(value, '')

    def ParseSystemLiteral(self):
        """[11] SystemLiteral: Parses a literal value matching the production for SystemLiteral.

        The value of the literal is returned as a string *without* the enclosing
        quotes."""
        production = "[11] SystemLiteral"
        q = self.ParseQuote()
        value = []
        while True:
            if self.the_char == q:
                self.NextChar()
                break
            elif IsChar(self.the_char):
                value.append(self.the_char)
                self.NextChar()
            elif self.the_char is None:
                self.WellFormednessError(
                    production + ": Unexpected end of file")
            else:
                self.WellFormednessError(
                    production + ": Illegal character %s" % repr(self.the_char))
        return string.join(value, '')

    def ParsePubidLiteral(self):
        """[12] PubidLiteral: Parses a literal value matching the production for PubidLiteral.

        The value of the literal is returned as a string *without* the enclosing
        quotes."""
        production = "[12] PubidLiteral"
        q = self.ParseQuote()
        value = []
        while True:
            if self.the_char == q:
                self.NextChar()
                break
            elif IsPubidChar(self.the_char):
                value.append(self.the_char)
                self.NextChar()
            elif self.the_char is None:
                self.WellFormednessError(
                    production + ": Unexpected End of file")
            else:
                self.WellFormednessError(
                    production + ": Illegal character %s" % repr(self.the_char))
        return string.join(value, '')

    def ParseCharData(self):
        """[14] CharData: parses a run of character data

        The method adds the parsed data to the current element.  In the default
        parsing mode it returns None.

        When the parser option :py:attr:`sgmlOmittag` is selected the method
        returns any parsed character data that could not be added to the current
        element due to a model violation.  Note that in this SGML-like mode any
        S is treated as being in the current element as the violation doesn't
        occurr until the first non-S character (so any implied start tag is
        treated as being immediately prior to the first non-S)."""
        data = []
        while self.the_char is not None:
            if self.the_char == '<' or self.the_char == '&':
                break
            if self.the_char == ']':
                if self.ParseLiteral(']]>'):
                    self.BuffText(']]>')
                    break
            self.IsS()		# force Unicode compatible white space handling
            data.append(self.the_char)
            self.NextChar()
            if len(data) >= XMLEntity.ChunkSize:
                data = string.join(data, '')
                try:
                    self.HandleData(data)
                except XMLValidityError:
                    if self.sgmlOmittag:
                        return StripLeadingS(data)
                    raise
                data = []
        data = string.join(data, '')
        try:
            self.HandleData(data)
        except XMLValidityError:
            if self.sgmlOmittag:
                return StripLeadingS(data)
            raise
        return None

    def parse_comment(self, gotLiteral=False):
        """[15] Comment: parses a comment.

        If *gotLiteral* is True then the method assumes that the '<!--' literal
        has already been parsed."""
        production = "[15] Comment"
        data = []
        nHyphens = 0
        if not gotLiteral:
            self.ParseRequiredLiteral('<!--', production)
        cEntity = self.entity
        while self.the_char is not None:
            if self.the_char == '-':
                self.NextChar()
                nHyphens += 1
                if nHyphens > 2 and not self.dontCheckWellFormedness:
                    self.WellFormednessError("-- in Comment")
            elif self.the_char == '>':
                if nHyphens == 2:
                    self.CheckPEBetweenDeclarations(cEntity)
                    self.NextChar()
                    break
                elif nHyphens < 2:
                    self.NextChar()
                    data.append('-' * nHyphens + '>')
                    nHyphens = 0
                # we must be in dontCheckWellFormedness here, we don't need to
                # check.
                else:
                    data.append('-' * (nHyphens - 2))
                    self.NextChar()
                    break
            elif self.IsS():
                if nHyphens < 2:
                    data.append('-' * nHyphens + self.the_char)
                    nHyphens = 0
                # space does not change the hyphen count
                self.NextChar()
            else:
                if nHyphens:
                    if nHyphens >= 2 and not self.dontCheckWellFormedness:
                        self.WellFormednessError("-- in Comment")
                    data.append('-' * nHyphens)
                    nHyphens = 0
                data.append(self.the_char)
                self.NextChar()
        return string.join(data, '')

    def ParsePI(self, gotLiteral=False):
        """[16] PI: parses a processing instruction.

        This method calls the
        :py:meth:`Node.ProcessingInstruction` of the current
        element or of the document if no element has been parsed yet.

        If *gotLiteral* is True the method assumes the '<?' literal has already
        been parsed."""
        production = "[16] PI"
        data = []
        if not gotLiteral:
            self.ParseRequiredLiteral('<?', production)
        dEntity = self.entity
        target = self.ParsePITarget()
        if self.ParseS():
            while self.the_char is not None:
                if self.the_char == '?':
                    self.NextChar()
                    if self.the_char == '>':
                        self.NextChar()
                        break
                    else:
                        # just a single '?'
                        data.append('?')
                data.append(self.the_char)
                self.NextChar()
        else:
            self.CheckPEBetweenDeclarations(dEntity)
            self.ParseRequiredLiteral('?>', production)
        if self.element:
            self.element.ProcessingInstruction(target, string.join(data, ''))
        elif self.doc:
            self.doc.ProcessingInstruction(target, string.join(data, ''))

    def ParsePITarget(self):
        """[17] PITarget: parses a processing instruction target name"""
        name = self.ParseName()
        if name.lower() == 'xml':
            self.BuffText(name)
            self.WellFormednessError(
                "[17] PITarget: Illegal target: %s" % name)
        return name

    def ParseCDSect(self, gotLiteral=False, cdEnd=u']]>'):
        """[18] CDSect: parses a CDATA section.

        This method adds any parsed data to the current element.

        If *gotLiteral* is True then the method assumes the initial literal has
        already been parsed.  (By default, CDStart.)  The literal used to
        signify the end of the CDATA section can be overridden by passing an
        alternative literal in *cdEnd*."""
        production = "[18] CDSect"
        data = []
        if not gotLiteral:
            self.ParseCDStart()
        self.ParseCData(cdEnd)
        self.ParseRequiredLiteral(cdEnd, production)

    def ParseCDStart(self):
        """[19] CDStart: parses the literal that starts a CDATA section."""
        self.ParseRequiredLiteral('<![CDATA[', "[19] CDStart")

    def ParseCData(self, cdEnd=']]>'):
        """[20] CData: parses a run of CData up to but not including *cdEnd*.

        This method adds any parsed data to the current element."""
        data = []
        while self.the_char is not None:
            if self.ParseLiteral(cdEnd):
                self.BuffText(cdEnd)
                break
            data.append(self.the_char)
            self.NextChar()
            if len(data) >= XMLEntity.ChunkSize:
                data = string.join(data, '')
                self.HandleData(data, True)
                data = []
        data = string.join(data, '')
        self.HandleData(data, True)

    def ParseCDEnd(self):
        """[21] CDEnd: parses the end of a CDATA section."""
        self.ParseRequiredLiteral(']]>', "[21] CDEnd")

    def ParseProlog(self):
        """[22] prolog: parses the document prolog, including the XML declaration and dtd."""
        production = "[22] prolog"
        if self.ParseLiteral('<?xml'):
            self.ParseXMLDecl(True)
        else:
            self.declaration = None
            self.CheckEncoding(self.entity, None)
        self.entity.KeepEncoding()
        self.ParseMisc()
        if self.ParseLiteral('<!DOCTYPE'):
            self.ParseDoctypedecl(True)
            self.ParseMisc()
        else:
            # document has no DTD, treat as standalone
            self.ValidityError(
                production + ": missing document type declaration")
            self.dtd = XMLDTD()
        if self.checkValidity:
            # Some checks can only be done after the prolog is complete.
            for eName in self.dtd.elementList.keys():
                eType = self.dtd.elementList[eName]
                aDefs = self.dtd.GetAttributeList(eName)
                if aDefs:
                    if eType.contentType == ElementType.Empty:
                        for aName in aDefs.keys():
                            aDef = aDefs[aName]
                            if aDef.type == XMLAttributeDefinition.Notation:
                                self.ValidityError(
                                    "No Notation on Empty Element: attribute %s on element %s cannot have NOTATION type" %
                                    (aName, eName))
            for eName in self.dtd.generalEntities.keys():
                eDef = self.dtd.generalEntities[eName]
                if eDef.notation and not eDef.notation in self.dtd.notations:
                    self.ValidityError(
                        "Notation Declared: notation %s used in declaration of entity %s has not been declared" %
                        (eDef.notation, eName))

    def ParseXMLDecl(self, gotLiteral=False):
        """[23] XMLDecl: parses an XML declaration.

        This method returns an :py:class:`~pyslet.xml20081126.structures.XMLDeclaration` instance.  Also, if an
        encoding is given in the declaration then the method changes the
        encoding of the current entity to match.  For more information see
        :py:meth:`~pyslet.xml20081126.structures.XMLEntity.ChangeEncoding`.

        If *gotLiteral* is True the initial literal '<?xml' is assumed to have
        already been parsed."""
        production = '[23] XMLDecl'
        if not gotLiteral:
            self.ParseRequiredLiteral('<?xml', production)
        version = self.ParseVersionInfo()
        encoding = None
        standalone = False
        if self.ParseS():
            if self.ParseLiteral('encoding'):
                encoding = self.ParseEncodingDecl(True)
                if self.ParseS():
                    if self.ParseLiteral('standalone'):
                        standalone = self.ParseSDDecl(True)
            elif self.ParseLiteral('standalone'):
                standalone = self.ParseSDDecl(True)
        self.ParseS()
        self.CheckEncoding(self.entity, encoding)
        if encoding is not None and self.entity.encoding.lower() != encoding.lower():
            self.entity.ChangeEncoding(encoding)
        self.ParseRequiredLiteral('?>', production)
        self.declaration = XMLDeclaration(version, encoding, standalone)
        return self.declaration

    def ParseVersionInfo(self, gotLiteral=False):
        """[24] VersionInfo: parses XML version number.

        The version number is returned as a string.  If *gotLiteral* is True then
        it is assumed that the preceding white space and 'version' literal have
        already been parsed."""
        production = "[24] VersionInfo"
        if not gotLiteral:
            self.ParseRequiredS(production)
            self.ParseRequiredLiteral('version', production)
        self.ParseEq(production)
        q = self.ParseQuote()
        self.ParseRequiredLiteral(u'1.')
        digits = self.ParseRequiredDecimalDigits(production)
        version = "1." + digits
        self.ParseQuote(q)
        return version

    def ParseEq(self, production="[25] Eq"):
        """[25] Eq: parses an equal sign, optionally surrounded by white space"""
        self.ParseS()
        self.ParseRequiredLiteral(u'=', production)
        self.ParseS()

    def ParseVersionNum(self):
        """[26] VersionNum: parses the XML version number, returns it as a string."""
        production = "[26] VersionNum"
        self.ParseRequiredLiteral('1.', production)
        return '1.' + self.ParseRequiredDecimalDigits(production)

    def ParseMisc(self):
        """[27] Misc: parses multiple Misc items.

        This method parses everything that matches the production Misc*"""
        production = "[27] Misc"
        while True:
            if self.IsS():
                self.NextChar()
                continue
            elif self.ParseLiteral('<!--'):
                self.parse_comment(True)
                continue
            elif self.ParseLiteral('<?'):
                self.ParsePI(True)
                continue
            else:
                break

    def ParseDoctypedecl(self, gotLiteral=False):
        """[28] doctypedecl: parses a doctype declaration.

        This method creates a new instance of
        :py:class:`~pyslet.xml20081126.structures.XMLDTD` and assigns it to
        :py:attr:`dtd`, it also returns this instance as the result.

        If *gotLiteral* is True the method assumes that the initial literal
        '<!DOCTYPE' has already been parsed."""
        production = "[28] doctypedecl"
        if not gotLiteral:
            self.ParseRequiredLiteral('<!DOCTYPE', production)
        saveMode = self.refMode
        self.refMode = XMLParser.RefModeInDTD
        self.dtd = XMLDTD()
        self.ParseRequiredS(production)
        self.dtd.name = self.ParseRequiredName(production)
        if self.ParseS():
            # could be an ExternalID
            if self.the_char != '[' and self.the_char != '>':
                self.dtd.externalID = self.ParseExternalID()
                self.ParseS()
        if self.ParseLiteral('['):
            # If there is no externalID we treat as standalone (until a PE ref)
            self.ParseIntSubset()
            self.ParseRequiredLiteral(']', production)
            self.ParseS()
        if self.checkValidity and self.dtd.externalID:
            # Before we parse the closing literal we load any external subset
            # but only if we are checking validity
            src = self.ResolveExternalID(self.dtd.externalID)
            if src:
                externalDTDSubset = XMLEntity(src)
                self.PushEntity(externalDTDSubset)
                self.ParseExtSubset()
        self.ParseRequiredLiteral('>', production)
        self.refMode = saveMode
        return self.dtd

    def ParseDeclSep(self):
        """[28a] DeclSep: parses a declaration separator."""
        gotSep = False
        while True:
            if self.the_char == '%':
                refEntity = self.entity
                self.ParsePEReference()
                if self.entity is not refEntity:
                    # we have a new entity, flag it as being opened in DeclSep
                    self.entity.flags['DeclSep'] = True
                gotSep = True
            elif self.IsS():
                self.NextChar()
                gotSep = True
            else:
                break
        if not gotSep:
            self.WellFormednessError(
                "[28a] DeclSep: expected PEReference or S, found %s" %
                repr(
                    self.the_char))

    def ParseIntSubset(self):
        """[28b] intSubset: parses an internal subset."""
        subsetEntity = self.entity
        while True:
            if self.the_char == '<':
                self.noPERefs = (self.GetExternalEntity() is subsetEntity)
                self.ParseMarkupDecl()
                self.noPERefs = False
            elif self.the_char == '%' or self.IsS():
                self.ParseDeclSep()
            else:
                break

    def ParseMarkupDecl(self, gotLiteral=False):
        """[29] markupDecl: parses a markup declaration.

        Returns True if a markupDecl was found, False otherwise."""
        production = "[29] markupDecl"
        if not gotLiteral:
            self.ParseRequiredLiteral('<', production)
        if self.the_char == '?':
            self.NextChar()
            self.ParsePI(True)
        elif self.the_char == '!':
            self.NextChar()
            if self.the_char == '-':
                self.ParseRequiredLiteral('--', production)
                self.parse_comment(True)
            elif self.ParseLiteral('ELEMENT'):
                self.ParseElementDecl(True)
            elif self.ParseLiteral('ATTLIST'):
                self.ParseAttlistDecl(True)
            elif self.ParseLiteral('ENTITY'):
                self.ParseEntityDecl(True)
            elif self.ParseLiteral('NOTATION'):
                self.ParseNotationDecl(True)
            else:
                self.WellFormednessError(
                    production + ": expected markup declaration")
        else:
            self.WellFormednessError(
                production + ": expected markup declaration")

    def ParseExtSubset(self):
        """[30] extSubset: parses an external subset"""
        if self.ParseLiteral('<?xml'):
            self.ParseTextDecl(True)
        else:
            self.CheckEncoding(self.entity, None)
        self.entity.KeepEncoding()
        self.ParseExtSubsetDecl()

    def ParseExtSubsetDecl(self):
        """[31] extSubsetDecl: parses declarations in the external subset."""
        initialStack = len(self.entityStack)
        while len(self.entityStack) >= initialStack:
            literalEntity = self.entity
            if self.the_char == '%' or self.IsS():
                self.ParseDeclSep()
            elif self.ParseLiteral("<!["):
                self.ParseConditionalSect(literalEntity)
            elif self.the_char == '<':
                self.ParseMarkupDecl()
            else:
                break

    def CheckPEBetweenDeclarations(self, checkEntity):
        """[31] extSubsetDecl: checks the well-formedness constraint on use of PEs between declarations.

        *checkEntity* is the entity we should still be in!"""
        if self.checkValidity and self.entity is not checkEntity:
            self.ValidityError(
                "Proper Declaration/PE Nesting: found '>' in entity %s" %
                self.entity.GetName())
        if not self.dontCheckWellFormedness and self.entity is not checkEntity and checkEntity.flags.get('DeclSep', False):
            # a badly nested declaration in an entity opened within a DeclSep
            # is a well-formedness error
            self.WellFormednessError(
                "[31] extSubsetDecl: failed for entity %s included in a DeclSep" %
                checkEntity.GetName())

    def ParseSDDecl(self, gotLiteral=False):
        """[32] SDDecl: parses a standalone declaration

        Returns True if the document should be treated as standalone; False otherwise."""
        production = "[32] SDDecl"
        if not gotLiteral:
            self.ParseRequiredS(production)
            self.ParseRequiredLiteral('standalone', production)
        self.ParseEq(production)
        q = self.ParseQuote()
        if self.the_char == u'y':
            result = True
            match = u'yes'
        else:
            result = False
            match = u'no'
        self.ParseRequiredLiteral(match, production)
        self.ParseQuote(q)
        return result

    def ParseElement(self):
        """[39] element: parses an element, including its content.

        The class used to represent the element is determined by calling the
        :py:meth:`~pyslet.xml20081126.structures.Document.GetElementClass` method of the current document.
        If there is no document yet then a new document is created automatically
        (see :py:meth:`ParseDocument` for more information).

        The element is added as a child of the current element using
        :py:meth:`Node.ChildElement`.

        The method returns:

        -	True: indicates that an element was parsed normally
        -	False: indicates that the element is not allowed in this context

        The second case only occurs when the :py:attr:`sgmlOmittag` option is in
        use and it indicates that the content of the enclosing element has
        ended.  The Tag is buffered so that it can be reparsed when the stack of
        nested :py:meth:`ParseContent` and :py:meth:`ParseElement` calls is
        unwound to the point where it is allowed by the context."""
        production = "[39] element"
        saveElement = self.element
        saveElementType = self.elementType
        saveCursor = None
        if self.sgmlOmittag and self.the_char != '<':
            # Leading data means the start tag was omitted (perhaps at the
            # start of the doc)
            name = None
            attrs = {}
            empty = False
        else:
            name, attrs, empty = self.ParseSTag()
            self.CheckAttributes(name, attrs)
            if self.checkValidity:
                if self.element is None and self.dtd.name is not None and self.dtd.name != name:
                    self.ValidityError(
                        "Root Element Type: expected element %s" %
                        self.dtd.name)
                # The current particle map must have an entry for name...
                self.CheckExpectedParticle(name)
                saveCursor = self.cursor
                self.elementType = self.dtd.GetElementType(name)
                if self.elementType is None:
                    # An element is valid if there is a declaration matching elementdecl where
                    # the Name matches the element type...
                    self.ValidityError(
                        "Element Valid: no element declaration for %s" % name)
                    self.cursor = None
                else:
                    self.cursor = ContentParticleCursor(self.elementType)
            if self.stagBuffer:
                name, attrs, empty = self.stagBuffer
                self.stagBuffer = None
        elementClass, elementName, bufferTag = self.GetSTagClass(name, attrs)
        if elementClass:
            if bufferTag and name:
                # elementClass represents an omitted start tag
                self.stagBuffer = (name, attrs, empty)
                # This strange text is a valid start tag that ensures we'll be
                # called again
                self.BuffText("<:>")
                # omitted start tags introduce elements that have no attributes
                # and must not be empty
                attrs = {}
                empty = False
        else:
            # this start tag indicates an omitted end tag: always buffered
            if name:
                self.stagBuffer = (name, attrs, empty)
                self.BuffText("<:>")
            return False
        if self.element is None:
            self.element = self.doc.ChildElement(elementClass, elementName)
        else:
            self.element = self.element.ChildElement(elementClass, elementName)
        self.element.Reset()
        if self.sgmlContent and getattr(elementClass, 'XMLCONTENT', XMLMixedContent) == XMLEmpty:
            empty = True
        for attr in attrs.keys():
            try:
                self.element.SetAttribute(attr, attrs[attr])
            except ValueError as e:
                if self.raiseValidityErrors:
                    raise XMLValidityError(str(e))
            except XMLValidityError:
                if self.raiseValidityErrors:
                    raise
        if not empty:
            saveDataCount = self.dataCount
            if self.sgmlContent and getattr(self.element, 'SGMLCONTENT', None) == ElementType.SGMLCDATA:
                # Alternative parsing of SGMLCDATA elements...
                # SGML says that the content ends at the first ETAGO
                while True:
                    self.ParseCData('</')
                    if self.the_char is None:
                        break
                    self.ParseRequiredLiteral('</', "SGML CDATA Content:")
                    endName = self.ParseName()
                    if endName != name:
                        # but this is such a common error we ignore it
                        self.element.AddData('</' + endName)
                    else:
                        self.ParseS()
                        self.ParseRequiredLiteral('>', "SGML CDATA ETag")
                        break
            else:
                # otherwise content detected end of element (so end tag was
                # omitted)
                while self.ParseContent():
                    endName = self.ParseETag()
                    if endName == name:
                        break
                    spuriousTag = True
                    if self.sgmlOmittag:
                        # do we have a matching open element?
                        if self.dontCheckWellFormedness:
                            # by starting the check at the current element we allow
                            # mismatched but broadly equivalent STags and ETags
                            iElement = self.element
                        else:
                            iElement = self.element.parent
                        while isinstance(iElement, Element):
                            if self.MatchXMLName(iElement, endName):
                                spuriousTag = False
                                # push a closing tag back onto the parser
                                self.BuffText('</%s>' % endName)
                                break
                            else:
                                iElement = iElement.parent
                    if spuriousTag:
                        if self.dontCheckWellFormedness:
                            # ignore spurious end tags, we probably inferred
                            # them earlier
                            continue
                        else:
                            self.WellFormednessError(
                                "Element Type Mismatch: found </%s>, expected <%s/>" %
                                (endName, name))
                    else:
                        break
                self.CheckExpectedParticle('')
            if name is None and self.dataCount == saveDataCount:
                # This element was triggered by data which elementClass was supposed to consume
                # It didn't consume any data so we raise an error here to
                # prevent a loop
                raise XMLFatalError(
                    production +
                    ": element implied by PCDATA had empty content %s" %
                    self.element)
        self.element.ContentChanged()
        self.element = saveElement
        self.elementType = saveElementType
        self.cursor = saveCursor
        return True

    def CheckAttributes(self, name, attrs):
        """Checks *attrs* against the declarations for element *name*.

        This method will add any omitted defaults to the attribute list.  Also,
        checking the validity of the attributes may result in values being
        further normalized as per the rules for collapsing spaces in tokenized
        values."""
        if self.dtd:
            aList = self.dtd.GetAttributeList(name)
        else:
            aList = None
        if aList:
            for a in aList.keys():
                aDef = aList[a]
                checkStandalone = self.DeclaredStandalone(
                ) and aDef.entity is not self.docEntity
                value = attrs.get(a, None)
                if value is None:
                    # check for default
                    if aDef.presence == XMLAttributeDefinition.Default:
                        attrs[a] = aDef.defaultValue
                        if checkStandalone:
                            self.ValidityError(
                                "Standalone Document Declaration: specification for attribute %s required (externally defined default)" %
                                a)
                    elif aDef.presence == XMLAttributeDefinition.Required:
                        self.ValidityError(
                            "Required Attribute: %s must be specified for element %s" %
                            (a, name))
                else:
                    if aDef.type != XMLAttributeDefinition.CData:
                        # ...then the XML processor must further process the normalized attribute value by
                        # discarding any leading and trailing space (#x20) characters, and by replacing
                        # sequences of space (#x20) characters by a single
                        # space (#x20) character.
                        newValue = NormalizeSpace(value)
                        if checkStandalone and newValue != value:
                            self.ValidityError(
                                "Standalone Document Declaration: specification for attribute %s altered by normalization (externally defined tokenized type)" %
                                a)
                        attrs[a] = newValue
                if aDef.presence == XMLAttributeDefinition.Fixed:
                    if value != aDef.defaultValue:
                        self.ValidityError(
                            "Fixed Attribute Default: %s must match the #FIXED value %s" %
                            (value, aDef.defaultValue))
        if self.checkValidity:
            for a in attrs.keys():
                if aList:
                    aDef = aList.get(a, None)
                else:
                    aDef = None
                if aDef is None:
                    self.ValidityError(
                        "Attribute Value Type: attribute %s must be declared" %
                        a)
                else:
                    value = attrs[a]
                    if aDef.type == XMLAttributeDefinition.ID:
                        if not IsValidName(value):
                            self.ValidityError(
                                "ID: %s does not match the Name production" %
                                value)
                        if value in self.idTable:
                            self.ValidityError(
                                "ID: value %s already in use" % value)
                        else:
                            self.idTable[value] = True
                    elif aDef.type == XMLAttributeDefinition.IDRef or aDef.type == XMLAttributeDefinition.IDRefs:
                        if aDef.type == XMLAttributeDefinition.IDRef:
                            values = [value]
                        else:
                            values = value.split(' ')
                        for iValue in values:
                            if not IsValidName(iValue):
                                self.ValidityError(
                                    "IDREF: %s does not match the Name production" %
                                    iValue)
                            self.idRefTable[iValue] = True
                    elif aDef.type == XMLAttributeDefinition.Entity or aDef.type == XMLAttributeDefinition.Entities:
                        if aDef.type == XMLAttributeDefinition.Entity:
                            values = [value]
                        else:
                            values = value.split(' ')
                        for iValue in values:
                            if not IsValidName(iValue):
                                self.ValidityError(
                                    "Entity Name: %s does not match the Name production" %
                                    iValue)
                            e = self.dtd.GetEntity(iValue)
                            if e is None:
                                self.ValidityError(
                                    "Entity Name: entity %s has not been declared" %
                                    iValue)
                            elif e.notation is None:
                                self.ValidityError(
                                    "Entity Name: entity %s is not unparsed" %
                                    iValue)
                    elif aDef.type == XMLAttributeDefinition.NmToken or aDef.type == XMLAttributeDefinition.NmTokens:
                        if aDef.type == XMLAttributeDefinition.NmToken:
                            values = [value]
                        else:
                            values = value.split(' ')
                        for iValue in values:
                            if not IsValidNmToken(iValue):
                                self.ValidityError(
                                    "Name Token: %s does not match the NmToken production" %
                                    iValue)
                    elif aDef.type == XMLAttributeDefinition.Notation:
                        if aDef.values.get(value, None) is None:
                            self.ValidityError(
                                "Notation Attributes: %s is not one of the notation names included in the declaration of %s" %
                                (value, a))
                    elif aDef.type == XMLAttributeDefinition.Enumeration:
                        # must be one of the values
                        if aDef.values.get(value, None) is None:
                            self.ValidityError(
                                "Enumeration: %s is not one of the NmTokens in the declaration of %s" %
                                (value, a))

    def MatchXMLName(self, element, name):
        """Tests if *name* is a possible name for this element.

        This method is used by the parser to determine if an end tag is the end
        tag of this element.  It is provided a separate method to allow it to be
        overridden by derived parsers"""
        return element.GetXMLName() == name

    def CheckExpectedParticle(self, name):
        """Tests if <name> fits with the cursor and raises a validity error if not.

        An empty string for *name* indicates the enclosing end tag was found.

        The method updates the current cursor as appropriate."""
        if self.cursor is not None:
            if not self.cursor.Next(name):
                # content model violation
                expected = string.join(self.cursor.Expected(), ' | ')
                self.ValidityError(
                    "Element Valid: found %s, expected (%s)" %
                    (name, expected))
                # don't generate any more errors for this element
                self.cursor = None

    def GetSTagClass(self, name, attrs=None):
        """[40] STag: returns information suitable for starting element *name* with
        attributes *attrs* in the current context

        If there is no :py:class:`~pyslet.xml20081126.structures.Document`
        instance yet this method assumes that it is being called for the root
        element and selects an appropriate class based on the contents of the
        prolog and/or *name*.

        When using the :py:attr:`sgmlOmittag` option *name* may be None
        indicating that the method should return information about the element
        implied by PCDATA in the current context (only called when an attempt to
        add data to the current context has already failed).

        The result is a triple of:

        -	elementClass:
                the element class that this STag must introduce or None if this STag
                does not belong (directly or indirectly) in the current context
        -	elementName:
                the name of the element (to pass to ChildElement) or None to use the
                default
        -	buffFlag:
                True indicates an omitted tag and that the triggering STag (i.e.,
                the STag with name *name*) should be buffered.
        """
        if self.doc is None:
            if self.dtd is None:
                self.dtd = XMLDTD()
            if self.dtd.name is None:
                self.dtd.name = name
            elif name is None:
                # document starts with PCDATA, use name declared in DOCTYPE
                name = self.dtd.name
            self.doc = self.GetDocumentClass(self.dtd)()
        context = self.GetContext()
        if self.sgmlOmittag:
            if name:
                stagClass = context.GetElementClass(name)
                if stagClass is None:
                    stagClass = self.doc.GetElementClass(name)
            else:
                stagClass = None
            elementClass = context.GetChildClass(stagClass)
            if elementClass is not stagClass:
                return elementClass, None, True
            else:
                return elementClass, name, False
        else:
            stagClass = context.GetElementClass(name)
            if stagClass is None:
                stagClass = self.doc.GetElementClass(name)
            return stagClass, name, False

    def ParseSTag(self):
        """[40] STag, [44] EmptyElemTag: parses a start tag or an empty element tag.

        This method returns a triple of name, attrs, emptyFlag where:

        -	*name*
                is the name of the element parsed.
        -	*attrs*
                is a dictionary of attribute values keyed by attribute name
        -	*emptyFlag*
                is a boolean; True indicates that the tag was an empty element
                tag."""
        production = "[40] STag"
        empty = False
        self.ParseRequiredLiteral('<')
        name = self.ParseRequiredName()
        attrs = {}
        while True:
            try:
                s = self.ParseS()
                if self.the_char == '>':
                    self.NextChar()
                    break
                elif self.the_char == '/':
                    self.ParseRequiredLiteral('/>')
                    empty = True
                    break
                if s:
                    aName, aValue = self.ParseAttribute()
                    if not self.dontCheckWellFormedness and aName in attrs:
                        self.WellFormednessError(
                            "Unique Att Spec: attribute %s appears more than once" %
                            aName)
                    attrs[aName] = aValue
                else:
                    self.WellFormednessError(
                        "Expected S, '>' or '/>', found '%s'" % self.the_char)
            except XMLWellFormedError:
                if not self.dontCheckWellFormedness:
                    raise
                # spurious character inside a start tag, in compatibility mode we
                # just discard it and keep going
                self.NextChar()
                continue
        return name, attrs, empty

    def ParseAttribute(self):
        """[41] Attribute: parses an attribute

        Returns *name*, *value* where:

        -	name
                is the name of the attribute or None if :py:attr:`sgmlShorttag` is
                True and a short form attribute value was supplied.
        -	value is the attribute value.

        If :py:attr:`dontCheckWellFormedness` the parser uses a very generous
        form of parsing attribute values to accomodate common syntax errors."""
        production = "[41] Attribute"
        name = self.ParseRequiredName(production)
        if self.sgmlShorttag:
            # name on its own may be OK
            s = self.ParseS()
            if self.the_char != '=':
                self.BuffText(s)
                return '@' + name, name
        self.ParseEq(production)
        value = self.ParseAttValue()
        return name, value

    def ParseETag(self, gotLiteral=False):
        """[42] ETag: parses an end tag

        If *gotLiteral* is True then the method assumes the initial '</' literal
        has been parsed alread.

        The method returns the name of the end element parsed."""
        production = "[42] ETag"
        if not gotLiteral:
            self.ParseRequiredLiteral('</')
        name = self.ParseRequiredName(production)
        self.ParseS()
        if self.dontCheckWellFormedness:
            # ignore all rubbish in end tags
            while self.the_char is not None:
                if self.the_char == '>':
                    self.NextChar()
                    break
                self.NextChar()
        else:
            self.ParseRequiredLiteral('>', production)
        return name

    def ParseContent(self):
        """[43] content: parses the content of an element.

        The method returns:

        -	True:
                indicates that the content was parsed normally
        -	False:
                indicates that the content contained data or markup not allowed in
                this context

        The second case only occurs when the :py:attr:`sgmlOmittag` option is in
        use and it indicates that the enclosing element has ended (i.e., the
        element's ETag has been omitted).  See py:meth:`ParseElement` for more
        information."""
        while True:
            if self.the_char == '<':
                # element, CDSect, PI or Comment
                self.NextChar()
                if self.the_char == '!':
                    # CDSect or Comment
                    self.NextChar()
                    if self.the_char == '-':
                        self.ParseRequiredLiteral('--')
                        self.parse_comment(True)
                        if self.checkValidity and self.elementType.contentType == ElementType.Empty:
                            self.ValidityError(
                                "Element Valid: comment not allowed in element declared EMPTY: %s" %
                                self.elementType.name)
                    elif self.the_char == '[':
                        self.ParseRequiredLiteral('[CDATA[')
                        # can CDATA sections imply missing markup?
                        if self.sgmlOmittag and not self.element.IsMixed():
                            # CDATA can only be put in elements that can
                            # contain data!
                            self.BuffText('<![CDATA[')
                            self.UnhandledData('')
                        else:
                            self.ParseCDSect(True)
                    else:
                        self.WellFormednessError("Expected Comment or CDSect")
                elif self.the_char == '?':
                    # PI
                    self.NextChar()
                    self.ParsePI(True)
                    if self.checkValidity and self.elementType.contentType == ElementType.Empty:
                        self.ValidityError(
                            "Element Valid: processing instruction not allowed in element declared EMPTY: %s" %
                            self.elementType.name)
                elif self.the_char != '/':
                    # element
                    self.BuffText('<')
                    if not self.ParseElement():
                        return False
                else:
                    # end of content
                    self.BuffText('<')
                    break
            elif self.the_char == '&':
                # Reference
                if self.sgmlOmittag and not self.element.IsMixed():
                    # we step in before resolving the reference, just in case
                    # this reference results in white space that is supposed
                    # to be the first data character after the omitted tag.
                    self.UnhandledData('')
                else:
                    data = self.ParseReference()
                    if self.checkValidity and self.elementType and self.elementType.contentType == ElementType.Empty:
                        self.ValidityError(
                            "Element Valid: reference not allowed in element declared EMPTY: %s" %
                            self.elementType.name)
                    self.HandleData(data, True)
            elif self.the_char is None:
                # end of entity
                if self.sgmlOmittag:
                    return False
                else:
                    # leave the absence of an end tag for ParseElement to worry
                    # about
                    return True
            else:
                pcdata = self.ParseCharData()
                if pcdata and not self.UnhandledData(pcdata):
                    # indicates end of the containing element
                    return False
        return True

    def HandleData(self, data, cdata=False):
        """[43] content: handles character data in content.

        When validating, the data is checked to see if it is optional white
        space.  However, if *cdata* is True the data is treated as character
        data (even if it matches the production for S)."""
        if data and self.element:
            if self.checkValidity and self.elementType:
                checkStandalone = self.DeclaredStandalone(
                ) and self.elementType.entity is not self.docEntity
                if checkStandalone and self.elementType.contentType == ElementType.ElementContent and ContainsS(data):
                    self.ValidityError(
                        "Standalone Document Declaration: white space not allowed in element %s (externally defined as element content)" %
                        self.elementType.name)
                if self.elementType.contentType == ElementType.Empty:
                    self.ValidityError(
                        "Element Valid: content not allowed in element declared EMPTY: %s" %
                        self.elementType.name)
                if self.elementType.contentType == ElementType.ElementContent and (cdata or not IsWhiteSpace(data)):
                    self.ValidityError(
                        "Element Valid: character data is not allowed in element %s" %
                        self.elementType.name)
            self.element.AddData(data)
            self.dataCount += len(data)

    def UnhandledData(self, data):
        """[43] content: manages unhandled data in content.

        This method is only called when the :py:attr:`sgmlOmittag` option is in use.
        It processes *data* that occurs in a context where data is not allowed.

        It returns a boolean result:

        -	True:
                the data was consumed by a sub-element (with an omitted start tag)
        -	False:
                the data has been buffered and indicates the end of the current
                content (an omitted end tag)."""
        if data:
            self.BuffText(EscapeCharData(data))
        # Two choices: PCDATA starts a new element or ends this one
        elementClass, elementName, ignore = self.GetSTagClass(None)
        if elementClass:
            return self.ParseElement()
        else:
            return False

    def ParseEmptyElemTag(self):
        """[44] EmptyElemTag: there is no method for parsing empty element tags alone.

        This method raises NotImplementedError.  Instead, you should call
        :py:meth:`ParseSTag` and examine the result.  If it returns False then
        an empty element was parsed."""
        raise NotImplementedError

    def ParseElementDecl(self, gotLiteral=False):
        """[45] elementdecl: parses an element declaration

        If *gotLiteral* is True the method assumes that the '<!ELEMENT' literal
        has already been parsed."""
        production = "[45] elementdecl"
        eType = ElementType()
        if not gotLiteral:
            self.ParseRequiredLiteral('<!ELEMENT', production)
        eType.entity = self.entity
        self.ParseRequiredS(production)
        eType.name = self.ParseRequiredName(production)
        self.ParseRequiredS(production)
        self.ParseContentSpec(eType)
        self.ParseS()
        self.CheckPEBetweenDeclarations(eType.entity)
        self.ParseRequiredLiteral('>', production)
        if self.checkValidity and self.dtd:
            eType.BuildModel()
            if not eType.IsDeterministic():
                self.CompatibilityError(
                    "Deterministic Content Model: <%s> has non-deterministic content model" %
                    eType.name)
            if self.dtd.GetElementType(eType.name) is not None:
                self.ValidityError(
                    "Unique Element Type Declaration: <%s> already declared" %
                    eType.name)
            self.dtd.DeclareElementType(eType)

    def ParseContentSpec(self, eType):
        """[46] contentspec: parses the content specification for an element type """
        production = "[46] contentspec"
        if self.ParseLiteral('EMPTY'):
            eType.contentType = ElementType.Empty
            eType.contentModel = None
        elif self.ParseLiteral('ANY'):
            eType.contentType = ElementType.Any
            eType.contentModel = None
        elif self.ParseLiteral('('):
            groupEntity = self.entity
            self.ParseS()
            if self.ParseLiteral('#PCDATA'):
                eType.contentType = ElementType.Mixed
                eType.contentModel = self.ParseMixed(True, groupEntity)
            else:
                eType.contentType = ElementType.ElementContent
                eType.contentModel = self.ParseChildren(True, groupEntity)
        else:
            self.WellFormednessError(
                production, ": expected 'EMPTY', 'ANY' or '('")

    def ParseChildren(self, gotLiteral=False, groupEntity=None):
        """[47] children: parses an element content model comprising children.

        If *gotLiteral* is True the method assumes that the initial '(' literal
        has already been parsed, including any following white space.

        The method returns an instance of :py:class:`~pyslet.xml20081126.structures.XMLContentParticle`."""
        production = "[47] children"
        if not gotLiteral:
            groupEntity = self.entity
            if not self.ParseLiteral('('):
                self.WellFormednessError(
                    production + ": expected choice or seq")
            self.ParseS()
        # choice or seq
        firstChild = self.ParseCP()
        self.ParseS()
        if self.the_char == ',' or self.the_char == ')':
            cp = self.ParseSeq(firstChild, groupEntity)
        elif self.the_char == '|':
            cp = self.ParseChoice(firstChild, groupEntity)
        else:
            self.WellFormednessError(production + ": expected seq or choice")
        if self.the_char == '?':
            cp.occurrence = XMLContentParticle.ZeroOrOne
            self.NextChar()
        elif self.the_char == '*':
            cp.occurrence = XMLContentParticle.ZeroOrMore
            self.NextChar()
        elif self.the_char == '+':
            cp.occurrence = XMLContentParticle.OneOrMore
            self.NextChar()
        return cp

    def ParseCP(self):
        """[48] cp: parses a content particle"""
        production = "[48] cp"
        if self.ParseLiteral('('):
            groupEntity = self.entity
            # choice or seq
            self.ParseS()
            firstChild = self.ParseCP()
            self.ParseS()
            if self.the_char == ',' or self.the_char == ')':
                cp = self.ParseSeq(firstChild, groupEntity)
            elif self.the_char == '|':
                cp = self.ParseChoice(firstChild, groupEntity)
            else:
                self.WellFormednessError(
                    production + ": expected seq or choice")
        else:
            cp = XMLNameParticle()
            cp.name = self.ParseRequiredName(production)
        if self.the_char == '?':
            cp.occurrence = XMLContentParticle.ZeroOrOne
            self.NextChar()
        elif self.the_char == '*':
            cp.occurrence = XMLContentParticle.ZeroOrMore
            self.NextChar()
        elif self.the_char == '+':
            cp.occurrence = XMLContentParticle.OneOrMore
            self.NextChar()
        return cp

    def ParseChoice(self, firstChild=None, groupEntity=None):
        """[49] choice: parses a sequence of content particles.

        *firstChild* is an optional
        :py:class:`~pyslet.xml20081126.structures.XMLContentParticle` instance.
        If present the method assumes that the first particle and any following
        white space has already been parsed.  If *firstChild* is given then
        *groupEntity* must be the entity in which the opening '(' was parsed
        which started the choice group."""
        production = "[49] choice"
        cp = XMLChoiceList()
        if firstChild is None:
            groupEntity = self.entity
            self.ParseRequiredLiteral('(', production)
            self.ParseS()
            firstChild = self.ParseCP()
            self.ParseS()
        cp.children.append(firstChild)
        while True:
            if self.the_char == '|':
                self.NextChar()
            elif self.the_char == ')':
                if self.checkValidity and self.entity is not groupEntity:
                    self.ValidityError(
                        "Proper Group/PE Nesting: found ')' in entity %s" %
                        self.entity.GetName())
                if len(cp.children) > 1:
                    self.NextChar()
                    break
                else:
                    self.WellFormednessError(
                        production +
                        ": Expected '|', found %s" %
                        repr(
                            self.the_char))
            else:
                self.WellFormednessError(
                    production +
                    ": Expected '|' or ')', found %s" %
                    repr(
                        self.the_char))
            self.ParseS()
            cp.children.append(self.ParseCP())
            self.ParseS()
        return cp

    def ParseSeq(self, firstChild=None, groupEntity=None):
        """[50] seq: parses a sequence of content particles.

        *firstChild* is an optional :py:class:`~pyslet.xml20081126.structures.XMLContentParticle` instance.  If
        present the method assumes that the first particle and any following
        white space has already been parsed."""
        production = "[50] seq"
        cp = XMLSequenceList()
        if firstChild is None:
            groupEntity = self.entity
            self.ParseRequiredLiteral('(', production)
            self.ParseS()
            firstChild = self.ParseCP()
            self.ParseS()
        cp.children.append(firstChild)
        while True:
            if self.the_char == ',':
                self.NextChar()
            elif self.the_char == ')':
                if self.checkValidity and self.entity is not groupEntity:
                    self.ValidityError(
                        "Proper Group/PE Nesting: found ')' in entity %s" %
                        self.entity.GetName())
                self.NextChar()
                break
            else:
                self.WellFormednessError(
                    production +
                    ": Expected ',' or ')', found %s" %
                    repr(
                        self.the_char))
            self.ParseS()
            cp.children.append(self.ParseCP())
            self.ParseS()
        return cp

    def ParseMixed(self, gotLiteral=False, groupEntity=None):
        """[51] Mixed: parses a mixed content type.

        If *gotLiteral* is True the method assumes that the #PCDATA literal has
        already been parsed.  In this case, *groupEntity* must be set to the
        entity which contained the opening '(' literal.

        Returns an instance of :py:class:`~pyslet.xml20081126.structures.XMLChoiceList` with occurrence
        :py:attr:`~pyslet.xml20081126.structures.XMLContentParticle.ZeroOrMore` representing the list of
        elements that may appear in the mixed content model. If the mixed model
        contains #PCDATA only then the choice list will be empty."""
        production = "[51] Mixed"
        cp = XMLChoiceList()
        names = {}
        cp.occurrence = XMLContentParticle.ZeroOrMore
        if not gotLiteral:
            groupEntity = self.entity
            self.ParseRequiredLiteral('(', production)
            self.ParseS()
            self.ParseRequiredLiteral('#PCDATA', production)
        while True:
            self.ParseS()
            if self.the_char == ')':
                if self.checkValidity and self.entity is not groupEntity:
                    self.ValidityError(
                        "Proper Group/PE Nesting: found ')' in entity %s" %
                        self.entity.GetName())
                break
            elif self.the_char == '|':
                self.NextChar()
                self.ParseS()
                cpChild = XMLNameParticle()
                cpChild.name = self.ParseRequiredName(production)
                if self.checkValidity:
                    if cpChild.name in names:
                        self.ValidityError(
                            "No Duplicate Types: %s appears multiple times in mixed-content declaration" %
                            cpChild.name)
                    else:
                        names[cpChild.name] = True
                cp.children.append(cpChild)
                continue
            else:
                self.WellFormednessError(production + ": Expected '|' or ')'")
        if len(cp.children):
            self.ParseRequiredLiteral(')*')
        else:
            self.ParseRequiredLiteral(')')
            self.ParseLiteral('*')
        return cp

    def ParseAttlistDecl(self, gotLiteral=False):
        """[52] AttlistDecl: parses an attribute list definition.

        If *gotLiteral* is True the method assumes that the '<!ATTLIST' literal
        has already been parsed.
        """
        production = "[52] AttlistDecl"
        dEntity = self.entity
        if not gotLiteral:
            self.ParseRequiredLiteral("<!ATTLIST", production)
        self.ParseRequiredS(production)
        name = self.ParseRequiredName(production)
        while True:
            if self.ParseS():
                if self.the_char == '>':
                    break
                a = self.ParseAttDef(True)
                if self.dtd:
                    if self.checkValidity:
                        if a.type == XMLAttributeDefinition.ID:
                            if a.presence != XMLAttributeDefinition.Implied and a.presence != XMLAttributeDefinition.Required:
                                self.ValidityError(
                                    "ID Attribute Default: ID attribute %s must have a declared default of #IMPLIED or #REQUIRED" %
                                    a.name)
                            aList = self.dtd.GetAttributeList(name)
                            if aList:
                                for ia in aList.values():
                                    if ia.type == XMLAttributeDefinition.ID:
                                        self.ValidityError(
                                            "One ID per Element Type: attribute %s must not be of type ID, element %s already has an ID attribute" %
                                            (a.name, name))
                        elif a.type == XMLAttributeDefinition.Notation:
                            aList = self.dtd.GetAttributeList(name)
                            if aList:
                                for ia in aList.values():
                                    if ia.type == XMLAttributeDefinition.Notation:
                                        self.ValidityError(
                                            "One Notation per Element Type: attribute %s must not be of type NOTATION, element %s already has a NOTATION attribute" %
                                            (a.name, name))
                    a.entity = dEntity
                    self.dtd.DeclareAttribute(name, a)

            else:
                break
        self.CheckPEBetweenDeclarations(dEntity)
        self.ParseRequiredLiteral('>', production)

    def ParseAttDef(self, gotS=False):
        """[53] AttDef: parses an attribute definition.

        If *gotS* is True the method assumes that the leading S has already been
        parsed.

        Returns an instance of :py:class:`~pyslet.xml20081126.structures.XMLAttributeDefinition`."""
        production = "[53] AttDef"
        if not gotS:
            self.ParseRequiredS(production)
        a = XMLAttributeDefinition()
        a.name = self.ParseRequiredName(production)
        self.ParseRequiredS(production)
        self.ParseAttType(a)
        self.ParseRequiredS(production)
        self.ParseDefaultDecl(a)
        return a

    def ParseAttType(self, a):
        """[54] AttType: parses an attribute type.

        *a* must be an :py:class:`~pyslet.xml20081126.structures.XMLAttributeDefinition` instance.  This method sets the
        :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.type` and :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.values`
        fields of *a*.

        Note that, to avoid unnecessary look ahead, this method does not call
        :py:meth:`ParseStringType` or :py:meth:`ParseEnumeratedType`."""
        production = "[54] AttType"
        if self.ParseLiteral('CDATA'):
            a.type = XMLAttributeDefinition.CData
            a.values = None
        elif self.ParseLiteral('NOTATION'):
            a.type = XMLAttributeDefinition.Notation
            a.values = self.ParseNotationType(True)
        elif self.the_char == '(':
            a.type = XMLAttributeDefinition.Enumeration
            a.values = self.ParseEnumeration()
        else:
            self.ParseTokenizedType(a)

    def ParseStringType(self, a):
        """[55] StringType: parses an attribute's string type.

        This method is provided for completeness.  It is not called during normal
        parsing operations.

        *a* must be an :py:class:`~pyslet.xml20081126.structures.XMLAttributeDefinition` instance.  This method sets the
        :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.type` and :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.values`
        fields of *a*."""
        production = "[55] StringType"
        self.ParseRequiredLiteral('CDATA', production)
        a.type = XMLAttributeDefinition.CData
        a.values = None

    def ParseTokenizedType(self, a):
        """[56] TokenizedType: parses an attribute's tokenized type.

        *a* must be an :py:class:`~pyslet.xml20081126.structures.XMLAttributeDefinition` instance.  This method sets the
        :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.type` and :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.values`
        fields of *a*."""
        production = "[56] TokenizedType"
        if self.ParseLiteral('ID'):
            if self.ParseLiteral('REF'):
                if self.ParseLiteral('S'):
                    a.type = XMLAttributeDefinition.IDRefs
                else:
                    a.type = XMLAttributeDefinition.IDRef
            else:
                a.type = XMLAttributeDefinition.ID
        elif self.ParseLiteral('ENTIT'):
            if self.ParseLiteral('Y'):
                a.type = XMLAttributeDefinition.Entity
            elif self.ParseLiteral('IES'):
                a.type = XMLAttributeDefinition.Entities
            else:
                self.WellFormednessError(
                    production + ": Expected 'ENTITY' or 'ENTITIES'")
        elif self.ParseLiteral('NMTOKEN'):
            if self.ParseLiteral('S'):
                a.type = XMLAttributeDefinition.NmTokens
            else:
                a.type = XMLAttributeDefinition.NmToken
        else:
            self.WellFormednessError(
                production +
                ": Expected 'ID', 'IDREF', 'IDREFS', 'ENTITY', 'ENTITIES', 'NMTOKEN' or 'NMTOKENS'")
        a.values = None

    def ParseEnumeratedType(self, a):
        """[57] EnumeratedType: parses an attribute's enumerated type.

        This method is provided for completeness.  It is not called during normal
        parsing operations.

        *a* must be an :py:class:`~pyslet.xml20081126.structures.XMLAttributeDefinition` instance.  This method sets the
        :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.type` and :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.values`
        fields of *a*."""
        if self.ParseLiteral('NOTATION'):
            a.type = XMLAttributeDefinition.Notation
            a.values = self.ParseNotationType(True)
        elif self.the_char == '(':
            a.type = XMLAttributeDefinition.Enumeration
            a.values = self.ParseEnumeration()
        else:
            self.WellFormednessError(
                "[57] EnumeratedType: expected 'NOTATION' or Enumeration")

    def ParseNotationType(self, gotLiteral=False):
        """[58] NotationType: parses a notation type.

        If *gotLiteral* is True the method assumes that the leading 'NOTATION' literal
        has already been parsed.

        Returns a list of strings representing the names of the declared notations being
        referred to."""
        production = "[58] NotationType"
        value = {}
        if not gotLiteral:
            self.ParseRequiredLiteral('NOTATION', production)
        self.ParseRequiredS(production)
        self.ParseRequiredLiteral('(', production)
        while True:
            self.ParseS()
            name = self.ParseRequiredName(production)
            if self.checkValidity and name in value:
                self.ValidityError(
                    "No Duplicate Tokens: %s already declared" % name)
            value[name] = True
            self.ParseS()
            if self.the_char == '|':
                self.NextChar()
                continue
            elif self.the_char == ')':
                self.NextChar()
                break
            else:
                self.WellFormednessError(
                    production +
                    ": expected '|' or ')', found %s" %
                    repr(
                        self.the_char))
        return value

    def ParseEnumeration(self):
        """[59] Enumeration: parses an enumeration.

        Returns a dictionary of strings representing the tokens in the enumeration."""
        production = "[59] Enumeration"
        value = {}
        self.ParseRequiredLiteral('(', production)
        while True:
            self.ParseS()
            token = self.ParseNmtoken()
            if token:
                if self.checkValidity and token in value:
                    self.ValidityError(
                        "No Duplicate Tokens: %s already declared" % token)
                value[token] = True
            else:
                self.WellFormednessError(production + ": expected Nmtoken")
            self.ParseS()
            if self.the_char == '|':
                self.NextChar()
                continue
            elif self.the_char == ')':
                self.NextChar()
                break
            else:
                self.WellFormednessError(
                    production +
                    ": expected '|' or ')', found %s" %
                    repr(
                        self.the_char))
        return value

    def ParseDefaultDecl(self, a):
        """[60] DefaultDecl: parses an attribute's default declaration.

        *a* must be an
        :py:class:`~pyslet.xml20081126.structures.XMLAttributeDefinition`
        instance.  This method sets the
        :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.presence
        ` and
        :py:attr:`~pyslet.xml20081126.structures.XMLAttributeDefinition.
        defaultValue` fields of *a*."""
        if self.ParseLiteral('#REQUIRED'):
            a.presence = XMLAttributeDefinition.Required
            a.defaultValue = None
        elif self.ParseLiteral('#IMPLIED'):
            a.presence = XMLAttributeDefinition.Implied
            a.defaultValue = None
        else:
            if self.ParseLiteral('#FIXED'):
                a.presence = XMLAttributeDefinition.Fixed
                self.ParseRequiredS("[60] DefaultDecl")
            else:
                a.presence = XMLAttributeDefinition.Default
            a.defaultValue = self.ParseAttValue()
            if a.type != XMLAttributeDefinition.CData:
                a.defaultValue = NormalizeSpace(a.defaultValue)
            if self.checkValidity:
                if a.type == XMLAttributeDefinition.IDRef or a.type == XMLAttributeDefinition.Entity:
                    if not IsValidName(a.defaultValue):
                        self.ValidityError(
                            "Attribute Default Value Syntactically Correct: %s does not match the Name production" %
                            EscapeCharData(
                                a.defaultValue,
                                True))
                elif a.type == XMLAttributeDefinition.IDRefs or a.type == XMLAttributeDefinition.Entities:
                    values = a.defaultValue.split(' ')
                    for iValue in values:
                        if not IsValidName(iValue):
                            self.ValidityError(
                                "Attribute Default Value Syntactically Correct: %s does not match the Names production" %
                                EscapeCharData(
                                    a.defaultValue,
                                    True))
                elif a.type == XMLAttributeDefinition.NmToken:
                    if not IsValidNmToken(a.defaultValue):
                        self.ValidityError(
                            "Attribute Default Value Syntactically Correct: %s does not match the Nmtoken production" %
                            EscapeCharData(
                                a.defaultValue,
                                True))
                elif a.type == XMLAttributeDefinition.NmTokens:
                    values = a.defaultValue.split(' ')
                    for iValue in values:
                        if not IsValidNmToken(iValue):
                            self.ValidityError(
                                "Attribute Default Value Syntactically Correct: %s does not match the Nmtokens production" %
                                EscapeCharData(
                                    a.defaultValue,
                                    True))
                elif a.type == XMLAttributeDefinition.Notation or a.type == XMLAttributeDefinition.Enumeration:
                    if a.values.get(a.defaultValue, None) is None:
                        self.ValidityError(
                            "Attribute Default Value Syntactically Correct: %s is not one of the allowed enumerated values" %
                            EscapeCharData(
                                a.defaultValue,
                                True))

    def ParseConditionalSect(self, gotLiteralEntity=None):
        """[61] conditionalSect: parses a conditional section.

        If *gotLiteralEntity* is set to an :py:class:`~pyslet.xml20081126.structures.XMLEntity` object the
        method assumes that the initial literal '<![' has already been parsed
        from that entity."""
        production = "[61] conditionalSect"
        if gotLiteralEntity is None:
            gotLiteralEntity = self.entity
            self.ParseRequiredLiteral('<![', production)
        self.ParseS()
        if self.ParseLiteral('INCLUDE'):
            self.ParseIncludeSect(gotLiteralEntity)
        elif self.ParseLiteral('IGNORE'):
            self.ParseIgnoreSect(gotLiteralEntity)
        else:
            self.WellFormednessError(
                production + ": Expected INCLUDE or IGNORE")

    def ParseIncludeSect(self, gotLiteralEntity=None):
        """[62] includeSect: parses an included section.

        If *gotLiteralEntity* is set to an
        :py:class:`~pyslet.xml20081126.structures.XMLEntity` object the method
        assumes that the production, up to and including the keyword 'INCLUDE'
        has already been parsed and that the opening '<![' literal was parsed
        from that entity."""
        production = "[62] includeSect"
        if gotLiteralEntity is None:
            gotLiteralEntity = self.entity
            self.ParseRequiredLiteral('<![', production)
            self.ParseS()
            self.ParseRequiredLiteral('INCLUDE', production)
        self.ParseS()
        if self.checkValidity and not self.entity is gotLiteralEntity:
            self.ValidityError(
                production + ": Proper Conditional Section/PE Nesting")
        self.ParseRequiredLiteral('[', production)
        self.ParseExtSubsetDecl()
        if self.checkValidity and not self.entity is gotLiteralEntity:
            self.ValidityError(
                production + ": Proper Conditional Section/PE Nesting")
        self.ParseRequiredLiteral(']]>', production)

    def ParseIgnoreSect(self, gotLiteralEntity=None):
        """[63] ignoreSect: parses an ignored section.

        If *gotLiteralEntity* is set to an
        :py:class:`~pyslet.xml20081126.structures.XMLEntity` object the method
        assumes that the production, up to and including the keyword 'IGNORE'
        has already been parsed and that the opening '<![' literal was parsed
        from that entity."""
        production = "[63] ignoreSect"
        if gotLiteralEntity is None:
            gotLiteralEntity = self.entity
            self.ParseRequiredLiteral('<![', production)
            self.ParseS()
            self.ParseRequiredLiteral('IGNORE', production)
        self.ParseS()
        if self.checkValidity and not self.entity is gotLiteralEntity:
            self.ValidityError(
                "Proper Conditional Section/PE Nesting: [ must not be in replacement text of %s" %
                self.entity.GetName())
        self.ParseRequiredLiteral('[', production)
        self.ParseIgnoreSectContents()
        if self.checkValidity and not self.entity is gotLiteralEntity:
            self.ValidityError(
                "Proper Conditional Section/PE Nesting: ]]> must not be in replacement text of %s" %
                self.entity.GetName())
        self.ParseRequiredLiteral(']]>', production)

    def ParseIgnoreSectContents(self):
        """[64] ignoreSectContents: parses the contents of an ignored section.

        The method returns no data."""
        self.ParseIgnore()
        if self.ParseLiteral('<!['):
            self.ParseIgnoreSectContents()
            self.ParseRequiredLiteral(']]>', "[64] ignoreSectContents")
            self.ParseIgnore()

    def ParseIgnore(self):
        """[65] Ignore: parses a run of characters in an ignored section.

        This method returns no data."""
        while IsChar(self.the_char):
            if self.the_char == '<' and self.ParseLiteral('<!['):
                self.BuffText(u'<![')
                break
            elif self.the_char == ']' and self.ParseLiteral(']]>'):
                self.BuffText(u']]>')
                break
            else:
                self.NextChar()

    def ParseCharRef(self, gotLiteral=False):
        """[66] CharRef: parses a character reference.

        If *gotLiteral* is True the method assumes that the leading '&' literal
        has already been parsed.

        The method returns a unicode string containing the character referred
        to."""
        production = "[66] CharRef"
        if not gotLiteral:
            self.ParseRequiredLiteral('&', production)
        self.ParseRequiredLiteral('#', production)
        if self.ParseLiteral('x'):
            qualifier = 'x'
            digits = self.ParseRequiredHexDigits(production)
            data = unichr(int(digits, 16))
        else:
            qualifier = ''
            digits = self.ParseRequiredDecimalDigits(production)
            data = unichr(int(digits))
        self.ParseRequiredLiteral(';', production)
        if self.refMode == XMLParser.RefModeInDTD:
            raise XMLForbiddenEntityReference(
                "&#%s%s; forbidden by context" % (qualifier, digits))
        elif self.refMode == XMLParser.RefModeAsAttributeValue:
            data = "&#%s%s;" % (qualifier, digits)
        elif not IsChar(data):
            raise XMLWellFormedError(
                "Legal Character: &#%s%s; does not match production for Char" %
                (qualifier, digits))
        return data

    def ParseReference(self):
        """[67] Reference: parses a reference.

        This method returns any data parsed as a result of the reference.  For a
        character reference this will be the character referred to.  For a
        general entity the data returned will depend on the parsing context. For
        more information see :py:meth:`ParseEntityRef`."""
        self.ParseRequiredLiteral('&', "[67] Reference")
        if self.the_char == '#':
            return self.ParseCharRef(True)
        else:
            return self.ParseEntityRef(True)

    def ParseEntityRef(self, gotLiteral=False):
        """[68] EntityRef: parses a general entity reference.

        If *gotLiteral* is True the method assumes that the leading '&' literal
        has already been parsed.

        This method returns any data parsed as a result of the reference.  For
        example, if this method is called in a context where entity references
        are bypassed then the string returned will be the literal characters
        parsed, e.g., "&ref;".

        If the entity reference is parsed successfully in a context where Entity
        references are recognized, the reference is looked up according to the
        rules for validating and non-validating parsers and, if required by the
        parsing mode, the entity is opened and pushed onto the parser so that
        parsing continues with the first character of the entity's replacement
        text.

        A special case is made for the predefined entities.  When parsed in a
        context where entity references are recognized these entities are
        expanded immediately and the resulting character returned.  For example,
        the entity &amp; returns the '&' character instead of pushing an entity
        with replacement text '&#38;'.

        Inclusion of an unescaped & is common so when we are not checking well-
        formedness we treat '&' not followed by a name as if it were '&amp;'.
        Similarly we are generous about the missing ';'."""
        production = "[68] EntityRef"
        if not gotLiteral:
            self.ParseRequiredLiteral('&', production)
        entity = self.entity
        if self.dontCheckWellFormedness:
            name = self.ParseName()
            if not name:
                return '&'
        else:
            name = self.ParseRequiredName(production)
        if self.dontCheckWellFormedness:
            self.ParseLiteral(';')
        else:
            self.ParseRequiredLiteral(';', production)
        if self.refMode == XMLParser.RefModeInEntityValue:
            return "&%s;" % name
        elif self.refMode in (XMLParser.RefModeAsAttributeValue, XMLParser.RefModeInDTD):
            raise XMLForbiddenEntityReference(
                "&%s; forbidden by context" % name)
        else:
            data = self.LookupPredefinedEntity(name)
            if data is not None:
                return data
            else:
                e = None
                if self.dtd:
                    e = self.dtd.GetEntity(name)
                    if e and self.DeclaredStandalone() and e.entity is not self.docEntity:
                        self.ValidityError(
                            "Standalone Document Declaration: reference to entity %s not allowed (externally defined)" %
                            e.GetName())
                if e is not None:
                    if e.notation is not None:
                        self.WellFormednessError(
                            "Parsed Entity: &%s; reference to unparsed entity not allowed" %
                            name)
                    else:
                        if not self.dontCheckWellFormedness and self.refMode == XMLParser.RefModeInAttributeValue and e.IsExternal():
                            self.WellFormednessError(
                                "No External Entity References: &%s; not allowed in attribute value" %
                                name)
                        if e.IsOpen() or (e is entity):
                            # if the last char of the entity is a ';' closing a
                            # recursive entity reference then # the entity will
                            # have been closed so we must check the context of the
                            # reference # too, not just whether it is currently
                            # open
                            self.WellFormednessError(
                                "No Recursion: entity &%s; is already open" %
                                name)
                        e.Open()
                        self.PushEntity(e)
                    return ''
                elif self.Standalone():
                    self.WellFormednessError(
                        "Entity Declared: undeclared general entity %s in standalone document" %
                        name)
                else:
                    self.ValidityError(
                        "Entity Declared: undeclared general entity %s" % name)

    def LookupPredefinedEntity(self, name):
        """Utility function used to look up pre-defined entities, e.g., "lt"

        This method can be overridden by variant parsers to implement other pre-defined
        entity tables."""
        return XMLParser.PredefinedEntities.get(name, None)

    def ParsePEReference(self, gotLiteral=False):
        """[69] PEReference: parses a parameter entity reference.

        If *gotLiteral* is True the method assumes that the initial '%' literal
        has already been parsed.

        This method returns any data parsed as a result of the reference.  Normally
        this will be an empty string because the method is typically called in
        contexts where PEReferences are recognized.  However, if this method is
        called in a context where PEReferences are not recognized the returned
        string will be the literal characters parsed, e.g., "%ref;"

        If the parameter entity reference is parsed successfully in a context
        where PEReferences are recognized, the reference is looked up according
        to the rules for validating and non-validating parsers and, if required
        by the parsing mode, the entity is opened and pushed onto the parser so
        that parsing continues with the first character of the entity's
        replacement text."""
        production = "[69] PEReference"
        if not gotLiteral:
            self.ParseRequiredLiteral('%', production)
        entity = self.entity
        name = self.ParseRequiredName(production)
        self.ParseRequiredLiteral(';', production)
        if self.refMode in (XMLParser.RefModeNone, XMLParser.RefModeInContent,
                            XMLParser.RefModeInAttributeValue, XMLParser.RefModeAsAttributeValue):
            return "%%%s;" % name
        else:
            self.gotPERef = True
            if self.noPERefs:
                self.WellFormednessError(
                    production +
                    ": PE referenced in Internal Subset, %%%s;" %
                    name)
            if self.dtd:
                e = self.dtd.GetParameterEntity(name)
            else:
                e = None
            if e is None:
                if self.DeclaredStandalone() and entity is self.docEntity:
                    # in a standalone document, PERefs in the internal subset
                    # must be declared
                    self.WellFormednessError(
                        "Entity Declared: Undeclared parameter entity %s in standalone document" %
                        name)
                else:
                    self.ValidityError(
                        "Entity Declared: undeclared parameter entity %s" %
                        name)
            else:
                if self.DeclaredStandalone() and e.entity is not self.docEntity:
                    if entity is self.docEntity:
                        self.WellFormednessError(
                            "Entity Declared: parameter entity %s declared externally but document is standalone" %
                            name)
                    else:
                        self.ValidityError(
                            "Standalone Document Declaration: reference to entity %s not allowed (externally defined)" %
                            e.GetName())
                if self.checkValidity:
                    """An external markup declaration is defined as a markup
                    declaration occurring in the external subset or in a parameter
                    entity (external or internal, the latter being included because
                    non-validating processors are not required to read them"""
                    if e.IsOpen() or (e is entity):
                        self.WellFormednessError(
                            "No Recursion: entity %%%s; is already open" %
                            name)
                    if self.refMode == XMLParser.RefModeInEntityValue:
                        # Parameter entities are fed back into the parser
                        # somehow
                        e.Open()
                        self.PushEntity(e)
                    elif self.refMode == XMLParser.RefModeInDTD:
                        e.OpenAsPE()
                        self.PushEntity(e)
            return ''

    def ParseEntityDecl(self, gotLiteral=False):
        """[70] EntityDecl: parses an entity declaration.

        Returns an instance of either :py:class:`~pyslet.xml20081126.structures.XMLGeneralEntity` or
        :py:class:`~pyslet.xml20081126.structures.XMLParameterEntity` depending on the type of entity parsed.
        If *gotLiteral* is True the method assumes that the leading '<!ENTITY'
        literal has already been parsed."""
        production = "[70] EntityDecl"
        if not gotLiteral:
            self.ParseRequiredLiteral('<!ENTITY', production)
        dEntity = self.entity
        xEntity = self.GetExternalEntity()
        self.ParseRequiredS(production)
        if self.the_char == '%':
            e = self.ParsePEDecl(True)
        else:
            e = self.ParseGEDecl(True)
        if e.IsExternal():
            # Resolve the external ID relative to xEntity
            e.location = self.ResolveExternalID(e.definition, xEntity)
        if self.dtd:
            e.entity = dEntity
            self.dtd.DeclareEntity(e)
        return e

    def ParseGEDecl(self, gotLiteral=False):
        """[71] GEDecl: parses a general entity declaration.

        Returns an instance of :py:class:`~pyslet.xml20081126.structures.XMLGeneralEntity`.  If *gotLiteral* is
        True the method assumes that the leading '<!ENTITY' literal *and the
        required S* have already been parsed."""
        production = "[71] GEDecl"
        dEntity = self.entity
        ge = XMLGeneralEntity()
        if not gotLiteral:
            self.ParseRequiredLiteral('<!ENTITY', production)
            self.ParseRequiredS(production)
        ge.name = self.ParseRequiredName(production)
        self.ParseRequiredS(production)
        self.ParseEntityDef(ge)
        self.ParseS()
        self.CheckPEBetweenDeclarations(dEntity)
        self.ParseRequiredLiteral('>', production)
        return ge

    def ParsePEDecl(self, gotLiteral=False):
        """[72] PEDecl: parses a parameter entity declaration.

        Returns an instance of :py:class:`~pyslet.xml20081126.structures.XMLParameterEntity`.  If *gotLiteral*
        is True the method assumes that the leading '<!ENTITY' literal *and the
        required S* have already been parsed."""
        production = "[72] PEDecl"
        dEntity = self.entity
        pe = XMLParameterEntity()
        if not gotLiteral:
            self.ParseRequiredLiteral('<!ENTITY', production)
            self.ParseRequiredS(production)
        self.ParseRequiredLiteral('%', production)
        self.ParseRequiredS(production)
        pe.name = self.ParseRequiredName(production)
        self.ParseRequiredS(production)
        self.ParsePEDef(pe)
        self.ParseS()
        self.CheckPEBetweenDeclarations(dEntity)
        self.ParseRequiredLiteral('>', production)
        return pe

    def ParseEntityDef(self, ge):
        """[73] EntityDef: parses the definition of a general entity.

        The general entity being parsed must be passed in *ge*.  This method
        sets the :py:attr:`~pyslet.xml20081126.structures.XMLGeneralEntity.definition` and
        :py:attr:`~pyslet.xml20081126.structures.XMLGeneralEntity.notation` fields from the parsed entity
        definition."""
        ge.definition = None
        ge.notation = None
        if self.the_char == '"' or self.the_char == "'":
            ge.definition = self.ParseEntityValue()
        elif self.the_char == 'S' or self.the_char == 'P':
            ge.definition = self.ParseExternalID()
            s = self.ParseS()
            if s:
                if self.ParseLiteral('NDATA'):
                    ge.notation = self.ParseNDataDecl(True)
                else:
                    self.BuffText(s)
        else:
            self.WellFormednessError(
                "[73] EntityDef: Expected EntityValue or ExternalID")

    def ParsePEDef(self, pe):
        """[74] PEDef: parses a parameter entity definition.

        The parameter entity being parsed must be passed in *pe*.  This method
        sets the :py:attr:`~pyslet.xml20081126.structures.XMLParameterEntity.definition` field from the parsed
        parameter entity definition."""
        pe.definition = None
        if self.the_char == '"' or self.the_char == "'":
            pe.definition = self.ParseEntityValue()
        elif self.the_char == 'S' or self.the_char == 'P':
            pe.definition = self.ParseExternalID()
        else:
            self.WellFormednessError(
                "[74] PEDef: Expected EntityValue or ExternalID")

    def ParseExternalID(self, allowPublicOnly=False):
        """[75] ExternalID: parses an external ID returning an XMLExternalID instance.

        An external ID must have a SYSTEM literal, and may have a PUBLIC identifier.
        If *allowPublicOnly* is True then the method will also allow an external
        identifier with a PUBLIC identifier but no SYSTEM literal.  In this mode
        the parser behaves as it would when parsing the production::

                (ExternalID | PublicID) S?"""
        if allowPublicOnly:
            production = "[75] ExternalID | [83] PublicID"
        else:
            production = "[75] ExternalID"
        if self.ParseLiteral('SYSTEM'):
            pubID = None
            allowPublicOnly = False
        elif self.ParseLiteral('PUBLIC'):
            self.ParseRequiredS(production)
            pubID = self.ParsePubidLiteral()
        else:
            self.WellFormednessError(
                production + ": Expected 'PUBLIC' or 'SYSTEM'")
        if (allowPublicOnly):
            if self.ParseS():
                if self.the_char == '"' or self.the_char == "'":
                    systemID = self.ParseSystemLiteral()
                else:
                    # we've consumed the trailing S, not a big deal
                    systemID = None
            else:
                # just a PublicID
                systemID = None
        else:
            self.ParseRequiredS(production)
            systemID = self.ParseSystemLiteral()
        # catch for dontCheckWellFormedness ??
        return XMLExternalID(pubID, systemID)

    def ResolveExternalID(self, externalID, entity=None):
        """[75] ExternalID: resolves an external ID, returning a URI reference.

        Returns an instance of :py:class:`pyslet.rfc2396.URI` or None if the
        external ID cannot be resolved.

        *entity* can be used to force the resolution of relative URI to be
        relative to the base of the given entity.  If it is None then the
        currently open external entity (where available) is used instead.

        The default implementation simply calls
        :py:meth:`~pyslet.xml20081126.structures.XMLExternalID.GetLocation` with the entities base URL and
        ignores the public ID.  Derived parsers may recognize public identifiers
        and resolve accordingly."""
        base = None
        if entity is None:
            entity = self.GetExternalEntity()
        if entity:
            base = entity.location
        return externalID.GetLocation(base)

    def ParseNDataDecl(self, gotLiteral=False):
        """[76] NDataDecl: parses an unparsed entity notation reference.

        Returns the name of the notation used by the unparsed entity as a string
        without the preceding 'NDATA' literal."""
        production = "[76] NDataDecl"
        if not gotLiteral:
            self.ParseRequiredS(production)
            self.ParseRequiredLiteral('NDATA', production)
        self.ParseRequiredS(production)
        return self.ParseRequiredName(production)

    def ParseTextDecl(self, gotLiteral=False):
        """[77] TextDecl: parses a text declataion.

        Returns an XMLTextDeclaration instance."""
        production = "[77] TextDecl"
        if not gotLiteral:
            self.ParseRequiredLiteral("<?xml", production)
        self.ParseRequiredS(production)
        if self.ParseLiteral('version'):
            version = self.ParseVersionInfo(True)
            encoding = self.ParseEncodingDecl()
        elif self.ParseLiteral('encoding'):
            version = None
            encoding = self.ParseEncodingDecl(True)
        else:
            self.WellFormednessError(
                production + ": Expected 'version' or 'encoding'")
        self.CheckEncoding(self.entity, encoding)
        if encoding is not None and self.entity.encoding.lower() != encoding.lower():
            self.entity.ChangeEncoding(encoding)
        self.ParseS()
        self.ParseRequiredLiteral('?>', production)
        return XMLTextDeclaration(version, encoding)

    def ParseEncodingDecl(self, gotLiteral=False):
        """[80] EncodingDecl: parses an encoding declaration

        Returns the declaration name without the enclosing quotes.  If *gotLiteral* is
        True then the method assumes that the literal 'encoding' has already been parsed."""
        production = "[80] EncodingDecl"
        if not gotLiteral:
            self.ParseRequiredS(production)
            self.ParseRequiredLiteral('encoding', production)
        self.ParseEq(production)
        q = self.ParseQuote()
        encName = self.ParseEncName()
        if not encName:
            self.WellFormednessError("Expected EncName")
        self.ParseQuote(q)
        return encName

    def ParseEncName(self):
        """[81] EncName: parses an encoding declaration name

        Returns the encoding name as a string or None if no valid encoding name
        start character was found."""
        name = []
        if EncNameStartCharClass.Test(self.the_char):
            name.append(self.the_char)
            self.NextChar()
            while EncNameCharClass.Test(self.the_char):
                name.append(self.the_char)
                self.NextChar()
        if name:
            return string.join(name, '')
        else:
            return None

    def ParseNotationDecl(self, gotLiteral=False):
        """[82] NotationDecl: Parses a notation declaration matching production NotationDecl

        This method assumes that the literal '<!NOTATION' has already been parsed.  It
        declares the notation in the :py:attr:`dtd`."""
        production = "[82] NotationDecl"
        dEntity = self.entity
        if not gotLiteral:
            self.ParseRequiredLiteral("<!NOTATION", production)
        self.ParseRequiredS(production)
        name = self.ParseRequiredName(production)
        self.ParseRequiredS(production)
        xID = self.ParseExternalID(True)
        self.ParseS()
        self.CheckPEBetweenDeclarations(dEntity)
        self.ParseRequiredLiteral('>')
        if self.dtd:
            if self.checkValidity and not (self.dtd.GetNotation(name) is None):
                self.ValidityError(
                    "Unique Notation Name: %s has already been declared" %
                    name)
            self.dtd.DeclareNotation(XMLNotation(name, xID))

    def ParsePublicID(self):
        """[83] PublicID: Parses a literal matching the production for PublicID.

        The literal string is returned without the PUBLIC prefix or the
        enclosing quotes."""
        production = "[83] PublicID"
        self.ParseRequiredLiteral('PUBLIC', production)
        self.ParseRequiredS(production)
        return self.ParsePubidLiteral()
