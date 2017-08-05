#! /usr/bin/env python

from ..py2 import (
    byte,
    byte_to_bstr,
    byte_value,
    dict_keys,
    is_byte,
    is_unicode,
    join_bytes)
from ..unicode5 import BasicParser, ParserMixin


def is_octet(b):
    """Returns True if a byte matches the production for OCTET."""
    return b is not None and byte_value(b) < 256


def is_char(b):
    """Returns True if a byte matches the production for CHAR."""
    return b is not None and byte_value(b) < 128


def is_upalpha(b):
    """Returns True if a byte matches the production for UPALPHA."""
    return b is not None and 65 <= byte_value(b) <= 90


def is_loalpha(b):
    """Returns True if a byte matches the production for LOALPHA."""
    return b is not None and 97 <= byte_value(b) <= 122


def is_alpha(b):
    """Returns True if a byte matches the production for ALPHA."""
    return is_upalpha(b) or is_loalpha(b)


def is_digit(b):
    """Returns True if a byte matches the production for DIGIT."""
    return b is not None and 48 <= byte_value(b) <= 57


def is_digits(src):
    """Returns True if all bytes match the production for DIGIT.

    Empty strings return False"""
    if src:
        for b in src:
            if not is_digit(b):
                return False
        return True
    else:
        return False


def is_ctl(b):
    """Returns True if a byte matches the production for CTL."""
    return b is not None and (byte_value(b) < 32 or byte_value(b) == 127)


#: octet 13 (carriage return)
CR = byte(13)

#: octet 10 (linefeed)
LF = byte(10)

#: octet 32 (space)
SP = byte(32)

#: octet 9 (horizontal tab)
HT = byte(9)

# : octet 34 (double quote)
DQUOTE = byte(34)

#: the string consisting of CR followed by LF
CRLF = join_bytes([CR, LF])


def is_hex(b):
    """Returns True if a byte matches the production for HEX."""
    return (b is not None and is_digit(b) or (65 <= byte_value(b) <= 70) or
            (97 <= byte_value(b) <= 102))


def is_hexdigits(src):
    """Returns True if all bytes match the production for HEX.

    Empty strings return False"""
    if src:
        for c in src:
            if not is_hex(c):
                return False
        return True
    else:
        return False


SEPARATORS = set('()<>@,;:\\"/[]?={} \t'.encode('ascii'))

LEFT_PARENTHESIS = byte('(')        #: Left Parenthesis "("
RIGHT_PARENTHESIS = byte(')')       #: Right Parentheses "("
LESSTHAN_SIGN = byte('<')           #: Less-than Sign "<"
GREATERTHAN_SIGN = byte('>')        #: Greater-than Sign ">"
COMMERCIAL_AT = byte('@')           #: Commercial At "@"
COMMA = byte(',')                   #: Comma ","
SEMICOLON = byte(';')               #: Semicolon ";"
COLON = byte(':')                   #: Colon ":"
REVERSE_SOLIDUS = byte(0x5C)        #: Reverse solidus "\"
SOLIDUS = byte('/')                 #: Solidus "/"
LEFT_SQUARE_BRACKET = byte('[')     #: Left square bracket "["
RIGHT_SQUARE_BRACKET = byte(']')    #: Right square bracket "["
QUESTION_MARK = byte('?')           #: Question mark "?"
EQUALS_SIGN = byte('=')             #: Equals sign "="
LEFT_CURLY_BRACKET = byte('{')      #: Left curly bracket "{"
RIGHT_CURLY_BRACKET = byte('}')     #: Right curly bracket "}"


def is_separator(b):
    """Returns True if a byte is a separator"""
    return b in SEPARATORS


def check_token(t):
    """Raises ValueError if *t* is *not* a valid token

    t
        A binary string, will also accept a single byte.

    Returns a *character* string representing the token on success."""
    if not isinstance(t, bytes):
        # single byte
        t = bytes((t, ))
    for b in t:
        if b in SEPARATORS:
            raise ValueError("Separator found in token: %s" % t)
        elif is_ctl(b) or not is_char(b):
            raise ValueError("Non-ASCII or CTL found in token: %s" % t)
    return t.decode('iso-8859-1')


def decode_quoted_string(qstring):
    """Decodes a quoted string, returning the unencoded string.

    Surrounding double quotes are removed and quoted bytes, bytes
    preceded by $5C (backslash), are unescaped.

    The return value is a binary string.  In most cases you will want to
    decode it using the latin-1 (iso-8859-1) codec as that was the
    original intention of RFC2616 but in practice anything outside US
    ASCII is likely to be non-portable."""
    qstring = qstring[1:-1]
    if qstring.find(b'\\') >= 0:
        # skip the loop if we don't have any escape sequences
        qbuff = []
        escape = False
        for b in qstring:
            if not escape and b == REVERSE_SOLIDUS:
                escape = True
                continue
            qbuff.append(b)
            escape = False
        return join_bytes(qbuff)
    else:
        return qstring


def quote_string(s, force=True):
    """Places a string in double quotes, returning the quoted string.

    force
        Always quote the string, defaults to True.  If False then valid
        tokens are not quoted but returned as-is.

    This is the reverse of :py:func:`decode_quoted_string`.  Note that
    only the double quote, \\ and CTL characters other than SP and HT
    are quoted in the output."""
    qstring = [DQUOTE]
    for b in s:
        if b in (REVERSE_SOLIDUS, DQUOTE) or (is_ctl(b) and b not in (SP, HT)):
            qstring.append(REVERSE_SOLIDUS)
            qstring.append(b)
            force = True
        elif is_ctl(b) or is_separator(b):
            force = True
            qstring.append(b)
        else:
            qstring.append(b)
    if force:
        qstring.append(DQUOTE)
    else:
        del qstring[0]
    return join_bytes(qstring)


def format_parameters(parameters):
    """Formats a dictionary of parameters

    This function is suitable for formatting parameter dictionaries
    parsed by :py:meth:`WordParser.parse_parameters`.  These
    dictionaries are key/value pairs where the keys are *character*
    strings and the values are *binary* strings.

    Parameter values are quoted only if their values require it, that
    is, only if their values are *not* valid tokens."""
    keys = sorted(dict_keys(parameters))
    format = []
    for k in keys:
        format.append(b'; ')
        p, v = parameters[k]
        format.append(p.encode('ascii'))
        format.append(b'=')
        format.append(quote_string(v, force=False))
    return b''.join(format)


class OctetParser(BasicParser):

    """A special purpose parser for parsing HTTP productions

    Strictly speaking, HTTP operates only on bytes so the parser is
    always set to binary mode.  However, as a concession to the various
    normative references to HTTP in other specifications where character
    strings are parsed they will be accepted provided they only contain
    *US ASCII* characters."""

    def __init__(self, source):
        if is_unicode(source):
            source = source.encode('ascii')
        super(OctetParser, self).__init__(source)

    def parse_lws(self):
        """Parses a single instance of the production LWS

        The return value is the LWS string parsed or None if there is no
        LWS."""
        savepos = self.pos
        lws = []
        if self.parse(CRLF):
            lws += [CR, LF]
        splen = 0
        while True:
            b = self.parse_one((SP, HT))
            if b is None:
                break
            else:
                lws.append(b)
                splen += 1
        if lws and splen:
            return join_bytes(lws)
        self.setpos(savepos)
        return None

    def parse_onetext(self, unfold=False):
        """Parses a single TEXT instance.

        unfold
            Pass True to replace folding LWS with a single SP. Defaults
            to False.

        Parses a single byte or run of LWS matching the production TEXT.
        The return value is either:

            1   a single byte of TEXT (*not* a binary string) excluding
                the LWS characters

            2   a binary string of LWS

            3   None if no TEXT was found

        You may find the utility function :func:`pyslet.py2.is_byte`
        useful to distinguish cases 1 and 2 correctly in both Python 2
        and Python 3."""
        lws = self.parse_lws()
        if lws:
            if unfold and lws[:2] == CRLF:
                return byte_to_bstr(SP)
            else:
                return lws
        elif is_octet(self.the_char) and not is_ctl(self.the_char):
            result = self.the_char
            self.next_char()
            return result
        else:
            return None

    def parse_text(self, unfold=False):
        """Parses TEXT

        unfold
            Pass True to replace folding LWS with a single SP. Defaults
            to False.

        Parses a run of characters matching the production TEXT.  The
        return value is the matching TEXT as a binary string (including
        any LWS) or None if no TEXT was found."""
        text = []
        while self.the_char is not None:
            t = self.parse_onetext(unfold)
            if t is not None:
                if is_byte(t):
                    text.append(t)
                else:
                    text += list(t)
            else:
                break
        if text:
            return join_bytes(text)
        else:
            return None

    def parse_token(self):
        """Parses a token.

        Parses a single instance of the production token.  The return
        value is the matching token as a binary string or None if no
        token was found."""
        token = []
        while self.the_char is not None:
            if is_ctl(self.the_char) or is_separator(self.the_char):
                break
            else:
                token.append(self.the_char)
                self.next_char()
        if token:
            return join_bytes(token)
        else:
            return None

    def parse_comment(self, unfold=False):
        """Parses a comment.

        unfold
            Pass True to replace folding LWS with a single SP. Defaults
            to False.

        Parses a single instance of the production comment.  The return
        value is the entire matching comment as a binary string
        (including the brackets, quoted pairs and any nested comments)
        or None if no comment was found."""
        if not self.parse(b"("):
            return None
        comment = [b"("]
        depth = 1
        while self.the_char is not None:
            if self.parse(b")"):
                comment.append(b")")
                depth -= 1
                if depth < 1:
                    break
            elif self.parse(b"("):
                comment.append(b"(")
                depth += 1
            elif self.match(b"\\"):
                qp = self.parse_quoted_pair()
                if qp:
                    comment.append(qp)
                else:
                    self.parser_error("quoted pair")
            else:
                ctext = self.parse_ctext(unfold)
                if ctext:
                    comment.append(ctext)
                else:
                    break
        if depth:
            self.parser_error("comment close")
        else:
            return b''.join(comment)

    def parse_ctext(self, unfold=False):
        """Parses ctext.

        unfold
            Pass True to replace folding LWS with a single SP. Defaults
            to False.

        Parses a run of characters matching the production ctext.  The
        return value is the matching ctext as a binary string (including
        any LWS) or None if no ctext was found.

        The original text of RFC2616 is ambiguous in the definition of
        ctext but the later errata_ corrected this to exclude the
        backslash byte ($5C) so we stop if we encounter one.

        .. _errata: https://www.rfc-editor.org/errata_search.php?rfc=2616
        """
        ctext = []
        while self.the_char is not None:
            if self.match_one(b"()\\"):
                break
            else:
                t = self.parse_onetext(unfold)
                if t is not None:
                    if is_byte(t):
                        ctext.append(t)
                    else:
                        ctext += list(t)
                else:
                    break
        if ctext:
            return join_bytes(ctext)
        else:
            return None

    def parse_quoted_string(self, unfold=False):
        """Parses a quoted-string.

        unfold
            Pass True to replace folding LWS with a single SP. Defaults
            to False.

        Parses a single instance of the production quoted-string.  The
        return value is the entire matching string (including the quotes
        and any quoted pairs) or None if no quoted-string was found."""
        if not self.parse(b'"'):
            return None
        qs = [b'"']
        while self.the_char is not None:
            if self.parse(b'"'):
                qs.append(b'"')
                break
            elif self.match(b"\\"):
                qp = self.parse_quoted_pair()
                if qp:
                    qs.append(qp)
                else:
                    self.parser_error("quoted pair")
            else:
                qdtext = self.parse_qdtext(unfold)
                if qdtext:
                    qs.append(qdtext)
                else:
                    self.parser_error('<">')
        return b''.join(qs)

    def parse_qdtext(self, unfold=False):
        """Parses qdtext.

        Parses a run of characters matching the production qdtext.  The
        return value is the matching qdtext string (including any LWS)
        or None if no qdtext was found.

        If *unfold* is True then any folding LWS is replaced with a
        single SP.  It defaults to False

        Although the production for qdtext would include the backslash
        character we stop if we encounter one, following the RFC2616
        errata_ instead."""
        qdtext = []
        while self.the_char is not None:
            if self.match_one(b'"\\'):
                break
            else:
                t = self.parse_onetext(unfold)
                if t is not None:
                    if is_byte(t):
                        qdtext.append(t)
                    else:
                        qdtext += list(t)
                else:
                    break
        if qdtext:
            return join_bytes(qdtext)
        else:
            return None

    def parse_quoted_pair(self):
        """Parses a single quoted-pair.

        The return value is the matching binary string including the
        backslash so it will always be of length 2 or None if no
        quoted-pair was found."""
        savepos = self.pos
        if self.parse(b"\\"):
            if is_char(self.the_char):
                qdpair = b"\\" + byte_to_bstr(self.the_char)
                self.next_char()
                return qdpair
            else:
                self.setpos(savepos)
        return None


class BadSyntax(ValueError):

    """Raised by the :class:`WordParser`

    Whenever a syntax error is encountered by the parsers.  Note that
    tokenization errors are raised separately during construction itself.

    production
        The name of the production being parsed.  (Defaults to an empty
        string.)

    parser
        The :class:`WordParser` instance raising the error (optional)

    BadSyntax is a subclass of ValueError."""

    def __init__(self, production='', parser=None):
        self.production = production
        if parser:
            #: the position of the parser when the error was raised
            if parser.match_end():
                self.pos = len(parser.source)
            else:
                self.pos = parser.src_pos[parser.pos]
            #: up to 40 characters/bytes to the left of pos
            self.left = parser.source[max(0, self.pos - 40):self.pos]
            #: up to 40 characters/bytes to the right of pos
            self.right = parser.source[self.pos:self.pos + 40]
            if production:
                msg = "SyntaxError: expected %s at [%i]" % (production,
                                                            self.pos)
            else:
                msg = "SyntaxError: at [%i]" % self.pos
        else:
            self.pos = None
            self.left = None
            self.right = None
            if production:
                msg = "SyntaxError: expected %s" % production
            else:
                msg = "SyntaxError"
        ValueError.__init__(self, msg)


class WordParser(ParserMixin):

    """A word-level parser and tokeniser for the HTTP grammar.

    source
        The binary string to be parsed into words.  It will normally be
        valid TEXT but it can contain control characters if they are
        escaped as part of a comment or quoted string.  For
        compatibility, character strings are accepted provided they only
        contain US ASCII characters

    ingore_sp (defaults to True)
        LWS is unfolded automatically.  By default the parser ignores
        spaces according to the rules for implied LWS in the
        specification and neither SP nor HT will be stored in the word
        list.  If you set *ignore_sp* to False then LWS is not ignored
        and each run of LWS is returned as a single SP in the word list.

    The source is parsed completely into words on construction using
    :class:`OctetParser`. If the source contains a CRLF (or any other
    non-TEXT bytes) that is not part of a folding or escape sequence it
    raises :class:`~pyslet.unicode5.ParserError`.

    For the purposes of this parser, a word may be either a single byte
    (in which case it is a separator or SP, note that HT is never stored
    in the word list) or a binary string, in which case it is a token, a
    comment or a quoted string.  Warning: in Python 2 a single byte is
    indistinguishable from a binary string of length 1.

    Methods follow the same pattern as that described in the related
    :class:`pyslet.unicode5.BasicParser` using match\_, parse\_ and
    require\_ naming conventions.  It also includes the
    :class:`pyslet.unicode5.ParseMixin` class to enable the convenience
    methods for converting between look-ahead and non-look-ahead parsing
    modes."""

    def __init__(self, source, ignore_sp=True):
        self.source = source
        self.words = []
        self.src_pos = []
        #: a pointer to the current word in the list
        self.pos = 0
        #: the current word or None
        self.the_word = None
        self.last_error = None
        self._init_parser(source, ignore_sp)

    def _init_parser(self, source, ignore_sp=True):
        p = OctetParser(source)
        while p.the_char is not None:
            sp = False
            src_pos = p.pos
            while p.parse_lws():
                if not ignore_sp:
                    sp = True
            if sp:
                self.words.append(SP)
                self.src_pos.append(src_pos)
                src_pos = p.pos
            if is_separator(p.the_char):
                if p.the_char == LEFT_PARENTHESIS:
                    self.words.append(p.parse_comment(True))
                elif p.the_char == DQUOTE:
                    self.words.append(p.parse_quoted_string(True))
                else:
                    self.words.append(p.the_char)
                    p.next_char()
                self.src_pos.append(src_pos)
            elif p.the_char is None:
                break
            else:
                self.words.append(p.require_production(p.parse_token(),
                                                       "TEXT"))
                self.src_pos.append(src_pos)
        self.pos = 0
        if self.words:
            self.the_word = self.words[0]
        else:
            self.the_word = None

    def setpos(self, pos):
        """Sets the current position of the parser.

        Example usage for look-ahead::

                # wp is a WordParser instance
                savepos=wp.pos
                try:
                        # parse a token/sub-token combination
                        token=wp.require_token()
                        wp.require_separator(byte('/'))
                        subtoken=wp.require_token()
                        return token,subtoken
                except BadSyntax:
                        wp.setpos(savepos)
                        return None,None"""
        self.pos = pos
        if self.pos < len(self.words):
            self.the_word = self.words[self.pos]
        else:
            self.the_word = None

    def parser_error(self, production=None):
        """Raises an error encountered by the parser

        See :class:`BadSyntax` for details.

        If production is None then the previous error is re-raised. If
        multiple errors have been raised previously the one with the
        most advanced parser position is used.  The operation is similar
        to :meth:`pyslet.unicode5.BasicParser.parser_error`.

        To improve the quality of error messages an internal record of
        the starting position of each word is kept (within the original
        source).

        The position of the parser is always set to the position of the
        error raised."""
        if production:
            e = BadSyntax(production, self)
        elif self.last_error is not None and self.pos <= self.last_error.pos:
            e = self.last_error
        else:
            e = BadSyntax('', self)
        if self.last_error is None or e.pos > self.last_error.pos:
            self.last_error = e
        if e.pos != self.pos:
            self.setpos(e.pos)
        raise e

    def match_end(self):
        """True if all of :attr:`words` have been parsed"""
        return self.the_word is None

    def peek(self):
        """Returns the next word

        If there are no more words, returns None."""
        if self.the_word:
            return self.the_word
        else:
            return ""

    def parse_word(self):
        """Parses any word from the list

        Returns the word parsed or None if the parser was already at the
        end of the word list."""
        result = self.the_word
        self.pos += 1
        if self.pos < len(self.words):
            self.the_word = self.words[self.pos]
        else:
            self.the_word = None
        return result

    def parse_word_as_bstr(self):
        """Parses any word from the list

        Returns a binary string representing the word.  In cases where
        the next work is a separator it converts the word to a binary
        string (in Python 2 this is a noop) before returning it."""
        w = self.parse_word()
        if w is not None and not isinstance(w, bytes):
            w = byte_to_bstr(w)
        return w

    def is_token(self):
        """Returns True if the current word is a token"""
        # words are never empty!
        return isinstance(self.the_word, bytes) and \
            self.the_word[0] not in SEPARATORS

    def parse_token(self):
        """Parses a token from the list of words

        Returns the token or None if the next word was not a token.  The
        return value is a binary string.  This is consistent with the
        use of this method for parsing tokens in contexts where a token
        or a quoted string may be present."""
        if self.is_token():
            return self.parse_word()
        else:
            return None

    def parse_tokenlower(self):
        """Returns a lower-cased token parsed from the word list

        Returns None if the next word was not a token.  Unlike
        :meth:`parse_token` the result is a *character* string."""
        if self.is_token():
            return self.parse_word().lower().decode('ascii')
        else:
            return None

    def parse_tokenlist(self):
        """Parses a list of tokens

        Returns the list or [] if no tokens were found.  Lists are
        defined by RFC2616 as being comma-separated.  Note that empty
        items are ignored, so strings such as "x,,y" return just ["x",
        "y"].

        The list of tokens is returned as a list of character strings."""
        result = []
        while self.the_word:
            token = self.parse_token()
            if token:
                result.append(token.decode('ascii'))
            elif self.parse_separator(COMMA):
                continue
            else:
                break
        return result

    def require_token(self, expected="token"):
        """Returns the current token or raises :py:class:`BadSyntax`

        expected
            the name of the expected production, it defaults to
            "token"."""
        token = self.parse_token()
        if token is None:
            self.parser_error(expected)
        else:
            return token

    def is_integer(self):
        """Returns True if the current word is an integer token"""
        return self.the_word and is_digits(self.the_word)

    def parse_integer(self):
        """Parses an integer token from the list of words

        Return the integer's *value* or None."""
        if self.is_integer():
            return int(self.parse_word())
        else:
            return None

    def require_integer(self, expected="integer"):
        """Parses an integer or raises :py:class:`BadSyntax`

        expected
            can be set to the name of the expected object, defaults to
            "integer"."""
        result = self.parse_integer()
        if result is None:
            self.parser_error(expected)
        else:
            return result

    def is_hexinteger(self):
        """Returns True if the current word is a hex token"""
        return self.the_word and is_hexdigits(self.the_word)

    def parse_hexinteger(self):
        """Parses a hex integer token from the list of words

        Return the hex integer's *value* or None."""
        if self.is_hexinteger():
            return int(self.parse_word(), 16)
        else:
            return None

    def require_hexinteger(self, expected="hex integer"):
        """Parses a hex integer or raises :py:class:`BadSyntax`

        expected
            can be set to the name of the expected object, defaults to
            "hex integer"."""
        result = self.parse_hexinteger()
        if result is None:
            self.parser_error(expected)
        else:
            return result

    def is_separator(self, sep):
        """Returns True if the current word matches *sep*"""
        return self.the_word == sep

    def parse_separator(self, sep):
        """Parses a *sep* from the list of words.

        Returns True if the current word matches *sep* and False
        otherwise."""
        if self.the_word == sep:
            self.parse_word()
            return True
        else:
            return False

    def require_separator(self, sep, expected=None):
        """Parses *sep* or raises :py:class:`BadSyntax`

        sep
            A separtor byte (not a binary string).

        expected
            can be set to the name of the expected object"""
        if self.the_word == sep:
            self.parse_word()
        else:
            self.parser_error(expected)

    def is_quoted_string(self):
        """Returns True if the current word is a quoted string."""
        return isinstance(self.the_word, bytes) and self.the_word[0] == DQUOTE

    def parse_quoted_string(self):
        """Parses a quoted string from the list of words.

        Returns the *decoded* value of the quoted string or None."""
        if self.is_quoted_string():
            return decode_quoted_string(self.parse_word())
        else:
            return None

    def parse_sp(self):
        """Parses a SP from the list of words.

        Returns True if the current word is a SP and False otherwise."""
        return self.parse_separator(SP)

    def parse_parameters(self, parameters, ignore_allsp=True,
                         case_sensitive=False, qmode=None):
        """Parses a set of parameters

        parameters
            the dictionary in which to store the parsed parameters

        ignore_allsp
            a boolean (defaults to True) which causes the function to
            ignore all LWS in the word list.  If set to False then space
            around the '=' separator is treated as an error and raises
            BadSyntax.

        case_sensitive
            controls whether parameter names are treated as case
            sensitive, defaults to False.

        qmode
            allows you to pass a special parameter name that will
            terminate parameter parsing (without being parsed itself).
            This is used to support headers such as the "Accept" header
            in which the parameter called "q" marks the boundary between
            media-type parameters and Accept extension parameters.
            Defaults to None

        Updates the parameters dictionary with the new parameter
        definitions. The key in the dictionary is the parameter name
        (converted to lower case if parameters are being dealt with case
        insensitively) and the value is a 2-item tuple of (name, value)
        always preserving the original case of the parameter name.

        Returns the parameters dictionary as the result.  The method
        always succeeds as parameter lists can be empty.

        Compatibility warning: parameter names must be tokens and are
        therefore converted to *character* strings.  Parameter values,
        on the other hand, may be quoted strings containing characters
        from unknown character sets and are therefore always represented
        as binary strings."""
        self.parse_sp()
        while self.the_word:
            savepos = self.pos
            try:
                self.parse_sp()
                self.require_separator(SEMICOLON)
                self.parse_sp()
                param_name = self.require_token(
                    "parameter").decode('iso-8859-1')
                if not case_sensitive:
                    param_key = param_name.lower()
                else:
                    param_key = param_name
                if qmode and param_key == qmode:
                    raise BadSyntax
                if ignore_allsp:
                    self.parse_sp()
                self.require_separator(EQUALS_SIGN, "parameter")
                if ignore_allsp:
                    self.parse_sp()
                if self.is_token():
                    param_value = self.parse_token()
                elif self.is_quoted_string():
                    param_value = self.parse_quoted_string()
                else:
                    self.parser_error("parameter value")
                parameters[param_key] = (param_name, param_value)
            except BadSyntax:
                self.setpos(savepos)
                break
        return parameters

    def parse_remainder(self, sep=b''):
        """Parses the rest of the words

        The result is a single string representing the remaining words
        joined with *sep*, which defaults to an *empty* string.

        Returns an empty string if the parser is at the end of the word
        list."""
        if self.the_word:
            result = sep.join(w if isinstance(w, bytes) else byte_to_bstr(w)
                              for w in self.words[self.pos:])
        else:
            result = b''
        self.setpos(len(self.words))
        return result
