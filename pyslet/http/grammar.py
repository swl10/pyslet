#! /usr/bin/env python

import string
from pyslet.unicode5 import BasicParser


def is_octet(c):
    """Returns True if a character matches the production for OCTET."""
    return ord(c) < 256


def is_char(c):
    """Returns True if a character matches the production for CHAR."""
    return ord(c) < 128


def is_upalpha(c):
    """Returns True if a character matches the production for UPALPHA."""
    return ord('A') <= ord(c) and ord(c) <= ord('Z')


def is_loalpha(c):
    """Returns True if a character matches the production for LOALPHA."""
    return ord('a') <= ord(c) and ord(c) <= ord('z')


def is_alpha(c):
    """Returns True if a character matches the production for ALPHA."""
    return is_upalpha(c) or is_loalpha(c)


def is_digit(c):
    """Returns True if a character matches the production for DIGIT."""
    return ord('0') <= ord(c) and ord(c) <= ord('9')


def is_digits(src):
    """Returns True if all characters match the production for DIGIT.

    Empty strings return False"""
    if src:
        for c in src:
            if not is_digit(c):
                return False
        return True
    else:
        return False


def is_ctl(c):
    """Returns True if a character matches the production for CTL."""
    return ord(c) < 32 or ord(c) == 127


#: octet 13 (carriage return)
CR = chr(13)

#: octet 10 (linefeed)
LF = chr(10)

#: octet 32 (space)
SP = chr(32)

#: octet 9 (horizontal tab)
HT = chr(9)

# : octet 34 (double quote)
DQUOTE = chr(34)

#: the string consisting of CR followed by LF
CRLF = CR + LF


def is_hex(c):
    """Returns True if a characters matches the production for HEX."""
    return (is_digit(c) or
            (ord('A') <= ord(c) and ord(c) <= ord('F')) or
            (ord('a') <= ord(c) and ord(c) <= ord('f')))


def is_hexdigits(src):
    """Returns True if all characters match the production for HEX.

    Empty strings return False"""
    if src:
        for c in src:
            if not is_hex(c):
                return False
        return True
    else:
        return False


def check_token(t):
    """Raises ValueError if *t* is *not* a valid token"""
    for c in t:
        if c in SEPARATORS:
            raise ValueError("Separator found in token: %s" % t)
        elif is_ctl(c) or not is_char(c):
            raise ValueError("Non-ASCII or CTL found in token: %s" % t)


SEPARATORS = set('()<>@,;:\\"/[]?={} \t')
"""A set consisting of all the HTTP separator characters.  For example::

    if c in SEPARATORS:
        # do something"""


def is_separator(c):
    """Returns True if a character is a separator"""
    return c in SEPARATORS


def decode_quoted_string(qstring):
    """Decodes a quoted string, returning the unencoded string.

    Surrounding double quotes are removed and quoted characters
    (characters preceded by \\) are unescaped."""
    qstring = qstring[1:-1]
    if qstring.find('\\') >= 0:
        # skip the loop if we don't have any escape sequences
        qbuff = []
        escape = False
        for c in qstring:
            if not escape and c == '\\':
                escape = True
                continue
            qbuff.append(c)
            escape = False
        return string.join(qbuff, '')
    else:
        return qstring


def quote_string(s, force=True):
    """Places a string in double quotes, returning the quoted string.

    This is the reverse of :py:func:`decode_quoted_string`.  Note that
    only the double quote, \\ and CTL characters other than SP and HT
    are quoted in the output.

    If *force* is False then valid tokens are *not* quoted."""
    qstring = ['"']
    for c in s:
        if c in '\\"' or (is_ctl(c) and c not in SP + HT):
            qstring.append('\\' + c)
            force = True
        elif is_ctl(c) or is_separator(c):
            force = True
            qstring.append(c)
        else:
            qstring.append(c)
    if force:
        qstring.append('"')
    else:
        del qstring[0]
    return string.join(qstring, '')


def format_parameters(parameters):
    """Formats a dictionary of parameters

    This function is suitable for formatting parameter dictionaries
    parsed by :py:meth:`WordParser.parse_parameters`.

    Parameter values are quoted only if their values require it, that
    is, only if their values are *not* valid tokens."""
    keys = parameters.keys()
    keys.sort()
    format = []
    for k in keys:
        format.append('; ')
        p, v = parameters[k]
        format.append(p)
        format.append('=')
        format.append(quote_string(v, force=False))
    return string.join(format, '')


class BadSyntax(ValueError):

    """Raised when a syntax error is encountered by the parsers

    This is just a trivial sub-class of the built-in ValueError."""
    pass


class OctetParser(BasicParser):

    """A special purpose parser for parsing HTTP productions."""

    def parse_lws(self):
        """Parses a single instance of the production LWS

        The return value is the LWS string parsed or None if there is no
        LWS."""
        savepos = self.pos
        lws = []
        if self.parse(CRLF):
            lws.append(CRLF)
        splen = 0
        while True:
            c = self.parse_one(SP + HT)
            if c is None:
                break
            else:
                lws.append(c)
                splen += 1
        if lws and splen:
            return string.join(lws, '')
        self.setpos(savepos)
        return None

    def parse_onetext(self, unfold=False):
        """Parses a single TEXT instance.

        Parses a single character or run of LWS matching the production
        TEXT.  The return value is the matching character, LWS string or
        None if no TEXT was found.

        If *unfold* is True then any folding LWS is replaced with a
        single SP.  It defaults to False"""
        lws = self.parse_lws()
        if lws:
            if unfold and lws[:2] == CRLF:
                return SP
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

        Parses a run of characters matching the production TEXT.  The
        return value is the matching TEXT string (including any LWS) or
        None if no TEXT was found.

        If *unfold* is True then any folding LWS is replaced with a
        single SP.  It defaults to False"""
        text = []
        while self.the_char is not None:
            t = self.parse_onetext(unfold)
            if t is not None:
                text.append(t)
            else:
                break
        if text:
            return string.join(text, '')
        else:
            return None

    def parse_token(self):
        """Parses a token.

        Parses a single instance of the production token.  The return
        value is the matching token string or None if no token was
        found."""
        token = []
        while self.the_char is not None:
            if is_ctl(self.the_char) or is_separator(self.the_char):
                break
            else:
                token.append(self.the_char)
                self.next_char()
        if token:
            return string.join(token, '')
        else:
            return None

    def parse_comment(self, unfold=False):
        """Parses a comment.

        Parses a single instance of the production comment.  The return
        value is the entire matching comment string (including the
        brackets, quoted pairs and any nested comments) or None if no
        comment was found.

        If *unfold* is True then any folding LWS is replaced with a
        single SP.  It defaults to False"""
        if not self.parse("("):
            return None
        comment = ["("]
        depth = 1
        while self.the_char is not None:
            if self.parse(")"):
                comment.append(")")
                depth -= 1
                if depth < 1:
                    break
            elif self.parse("("):
                comment.append("(")
                depth += 1
            elif self.match("\\"):
                qp = self.parse_quoted_pair()
                if qp:
                    comment.append(qp)
                else:
                    raise ValueError(
                        "Expected quoted pair: %s..." % self.peek(5))
            else:
                ctext = self.parse_ctext(unfold)
                if ctext:
                    comment.append(ctext)
                else:
                    break
        comment = string.join(comment, '')
        if depth:
            raise ValueError("Unclosed comment: %s" % comment)
        else:
            return comment

    def parse_ctext(self, unfold=False):
        """Parses ctext.

        Parses a run of characters matching the production ctext.  The
        return value is the matching ctext string (including any LWS) or
        None if no ctext was found.

        If *unfold* is True then any folding LWS is replaced with a
        single SP.  It defaults to False

        Although the production for ctext would include the backslash
        character we stop if we encounter one as the grammar is
        ambiguous at this point."""
        ctext = []
        while self.the_char is not None:
            if self.MatchOne("()\\"):
                break
            else:
                t = self.parse_onetext(unfold)
                if t is None:
                    break
                else:
                    ctext.append(t)
        if ctext:
            return string.join(ctext, '')
        else:
            return None

    def parse_quoted_string(self, unfold=False):
        """Parses a quoted-string.

        Parses a single instance of the production quoted-string.  The
        return value is the entire matching string (including the quotes
        and any quoted pairs) or None if no quoted-string was found.

        If *unfold* is True then any folding LWS is replaced with a
        single SP.  It defaults to False"""
        if not self.parse(DQUOTE):
            return None
        qs = [DQUOTE]
        while self.the_char is not None:
            if self.parse(DQUOTE):
                qs.append(DQUOTE)
                break
            elif self.match("\\"):
                qp = self.parse_quoted_pair()
                if qp:
                    qs.append(qp)
                else:
                    raise ValueError(
                        "Expected quoted pair: %s..." % self.peek(5))
            else:
                qdtext = self.parse_qdtext(unfold)
                if qdtext:
                    qs.append(qdtext)
                else:
                    raise BadSyntax("Expected closing <\">: %s%s..." %
                                    (string.join(qs, ''), self.peek(5)))
        return string.join(qs, '')

    def parse_qdtext(self, unfold=False):
        """Parses qdtext.

        Parses a run of characters matching the production qdtext.  The
        return value is the matching qdtext string (including any LWS)
        or None if no qdtext was found.

        If *unfold* is True then any folding LWS is replaced with a
        single SP.  It defaults to False

        Although the production for qdtext would include the backslash
        character we stop if we encounter one as the grammar is
        ambiguous at this point."""
        qdtext = []
        while self.the_char is not None:
            if self.MatchOne("\\" + DQUOTE):
                break
            else:
                t = self.parse_onetext(unfold)
                if t is None:
                    break
                else:
                    qdtext.append(t)
        if qdtext:
            return string.join(qdtext, '')
        else:
            return None

    def parse_quoted_pair(self):
        """Parses a single quoted-pair.

        The return value is the matching string including the backslash
        so it will always be of length 2 or None if no quoted-pair was
        found."""
        savepos = self.pos
        if self.parse("\\"):
            if is_char(self.the_char):
                qdpair = "\\" + self.the_char
                self.next_char()
                return qdpair
            else:
                self.setpos(savepos)
        return None


class WordParser(object):

    """A word-level parser and tokeniser for the HTTP grammar.

    *source* is the string to be parsed into words.  It will normally be
    valid TEXT but it can contain control characters if they are escaped
    as part of a comment or quoted string.

    LWS is unfolded automatically.  By default the parser ignores spaces
    according to the rules for implied LWS in the specification and
    neither SP nor HT will be stored in the word list.  If you set
    *ignore_sp* to False then LWS is not ignored and each run of LWS is
    returned as a single SP in the word list.

    If the source contains a CRLF (or any other non-TEXT character) that
    is not part of a folding or escape sequence it raises ValueError

    The resulting words may be a token, a single separator character, a
    comment or a quoted string.  To determine the type of word, look at
    the first character.

    *   '(' means the word is a comment, surrounded by '(' and ')'

    *   a double quote means the word is an encoded quoted string (use
        py:func:`decode_quoted_string` to decode it)

    *   other separator chars are just themselves and only appear as
        single character strings.  (HT is never returned.)

    *   Any other character indicates a token.

    Methods of the form require\_\* raise :py:class:`BadSyntax` if the
    production is not found."""

    def __init__(self, source, ignore_sp=True):
        self.words = []
        #: a pointer to the current word in the list
        self.pos = 0
        #: the current word or None
        self.the_word = None
        self._init_parser(source, ignore_sp)

    def _init_parser(self, source, ignore_sp=True):
        p = OctetParser(source)
        while p.the_char is not None:
            sp = False
            while p.parse_lws():
                if not ignore_sp:
                    sp = True
            if sp:
                self.words.append(SP)
            if is_separator(p.the_char):
                if p.the_char == "(":
                    self.words.append(p.parse_comment(True))
                elif p.the_char == DQUOTE:
                    self.words.append(p.parse_quoted_string(True))
                else:
                    self.words.append(p.the_char)
                    p.next_char()
            elif p.the_char is None:
                break
            else:
                self.words.append(p.require_production(p.parse_token(),
                                                       "TEXT"))
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
                        wp.require_separator('/')
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

    def peek(self):
        """Returns the next word

        If there are no more words, returns None."""
        if self.the_word:
            return self.the_word
        else:
            return ""

    def syntax_error(self, expected):
        """Raises :py:class:`BadSyntax`.

        expected
            a descriptive string indicating the expected production."""
        if self.the_word:
            raise BadSyntax("Expected %s, found %s" %
                            (expected, repr(self.the_word)))
        else:
            raise BadSyntax("Expected %s" % expected)

    def require_production(self, result, production=None):
        """Returns *result* if *result* is not None

        If result is None, raises BadSyntax.

        production
            can be used to customize the error message with the name of
            the expected production."""
        if result is None:
            if production is None:
                raise BadSyntax("Error at ...%s" % self.peek())
            else:
                raise BadSyntax("Expected %s at ...%s" %
                                (production, self.peek()))
        else:
            return result

    def parse_production(self, require_method, *args):
        """Executes the bound method *require_method* passing *args*.

        If successful the result of the method is returned.  If
        BadSyntax is raised, the exception is caught, the parser rewound
        and None is returned."""
        savepos = self.pos
        try:
            return require_method(*args)
        except BadSyntax:
            self.setpos(savepos)
            return None

    def require_production_end(self, result, production=None):
        """Checks for a required production and the end of the word list

        Returns *result* if *result* is not None and parsing is now
        complete, otherwise raises BadSyntax.

        production
            can be used to customize the error message with the name of
            the expected production."""
        result = self.require_production(result, production)
        self.require_end(production)
        return result

    def require_end(self, production=None):
        """Checks for the end of the word list

        If the parser is not at the end of the word list
        :py:class:`BadSyntax` is raised.

        production
            can be used to customize the error message with the name of
            the production being parsed."""
        if self.the_word:
            if production:
                raise BadSyntax("Spurious data after %s: found %s" %
                                (production, repr(self.the_word)))
            else:
                raise BadSyntax("Spurious data: %s" % repr(self.the_word))

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

    def is_token(self):
        """Returns True if the current word is a token"""
        return self.the_word and self.the_word[0] not in SEPARATORS

    def parse_token(self):
        """Parses a token from the list of words

        Returns the token or None if the next word was not a token."""
        if self.is_token():
            return self.parse_word()
        else:
            return None

    def parse_tokenlower(self):
        """Returns a lower-cased token parsed from the word list

        Returns None if the next word was not a token."""
        if self.is_token():
            return self.parse_word().lower()
        else:
            return None

    def parse_tokenlist(self):
        """Parses a list of tokens

        Returns the list or [] if no tokens were found.  Lists are
        defined by RFC2616 as being comma-separated.  Note that empty
        items are ignored, so string such as "x,,y" return just ["x",
        "y"]."""
        result = []
        while self.the_word:
            token = self.parse_token()
            if token:
                result.append(token)
            elif self.parse_separator(','):
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
            self.syntax_error(expected)
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
            self.syntax_error(expected)
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
            self.syntax_error(expected)
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

        expected
            can be set to the name of the expected object"""
        if self.the_word == sep:
            self.parse_word()
        else:
            self.syntax_error(expected)

    def is_quoted_string(self):
        """Returns True if the current word is a quoted string."""
        return self.the_word and self.the_word[0] == DQUOTE

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
        always preserving the original case of the parameter name."""
        self.parse_sp()
        while self.the_word:
            savepos = self.pos
            try:
                self.parse_sp()
                self.require_separator(';')
                self.parse_sp()
                param_name = self.require_token("parameter")
                if not case_sensitive:
                    param_key = param_name.lower()
                else:
                    param_key = param_name
                if qmode and param_key == qmode:
                    raise BadSyntax
                if ignore_allsp:
                    self.parse_sp()
                self.require_separator('=', "parameter")
                if ignore_allsp:
                    self.parse_sp()
                if self.is_token():
                    param_value = self.parse_token()
                elif self.is_quoted_string():
                    param_value = self.parse_quoted_string()
                else:
                    self.syntax_error("parameter value")
                parameters[param_key] = (param_name, param_value)
            except BadSyntax:
                self.setpos(savepos)
                break

    def parse_remainder(self, sep=''):
        """Parses the rest of the words

        The result is a single string representing the remaining words
        joined with *sep*, which defaults to an *empty* string.

        Returns an empty string if the parser is at the end of the word
        list."""
        if self.the_word:
            result = string.join(self.words[self.pos:], sep)
        else:
            result = ''
        self.setpos(len(self.words))
        return result
