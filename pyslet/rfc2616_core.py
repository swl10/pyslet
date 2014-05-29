#! /usr/bin/env python

import string
from pyslet.unicode5 import BasicParser


class HTTPException(Exception):

    """Abstract class for all HTTP errors."""
    pass


class SyntaxError(HTTPException):

    """Raised when a syntax error is encountered parsing an HTTP production."""
    pass

HTTPParameterError = SyntaxError


def IsOCTET(c):
    """Given a character, returns True if it matches the production for OCTET.

    The HTTP protocol only deals with octets but as a convenience, and
    due to the blurring of octet and character strings in Python 2.x
    we process characters as if they were octets."""
    return ord(c) < 256


def IsCHAR(c):
    """Given a character returns True if it matches the production for CHAR."""
    return ord(c) < 128


def IsUPALPHA(c):
    """Given a character returns True if it matches the production for UPALPHA."""
    return ord('A') <= ord(c) and ord(c) <= ord('Z')


def IsLOALPHA(c):
    """Given a character returns True if it matches the production for LOALPHA."""
    return ord('a') <= ord(c) and ord(c) <= ord('z')


def IsALPHA(c):
    """Given a character returns True if it matches the production for ALPHA."""
    return IsUPALPHA(c) or IsLOALPHA(c)


def IsDIGIT(c):
    """Given a character returns True if it matches the production for DIGIT."""
    return ord('0') <= ord(c) and ord(c) <= ord('9')


def IsDIGITS(src):
    """Given a string, returns True if all characters match the production for DIGIT.

    Empty strings return False"""
    if src:
        for c in src:
            if not IsDIGIT(c):
                return False
        return True
    else:
        return False


def IsCTL(c):
    """Given a character returns True if it matches the production for CTL."""
    return ord(c) < 32 or ord(c) == 127

CR = chr(13)		#: octet 13 (carriage return)
LF = chr(10)		#: octet 10 (linefeed)
SP = chr(32)		#: octet 32 (space)
HT = chr(9)		#: octet 9 (horizontal tab)
DQUOTE = chr(34)  # : octet 34 (double quote)
CRLF = CR + LF		#: the string consisting of CR followed by LF


def IsHEX(c):
    """Given a character returns True if it matches the production for HEX."""
    return IsDIGIT(c) or (ord('A') <= ord(c) and ord(c) <= ord('F')) or (ord('a') <= ord(c) and ord(c) <= ord('f'))


def IsHEXDIGITS(c):
    """Given a string, returns True if all characters match the production for HEX.

    Empty strings return False"""
    if src:
        for c in src:
            if not IsHEX(c):
                return False
        return True
    else:
        return False

SEPARATORS = set('()<>@,;:\\"/[]?={} \t')
"""A set consisting of all the HTTP separator characters.  For example::

	if c in SEPARATORS:
		# do something"""


def IsSEPARATOR(c):
    """Given a characters returns True if it matches the production for separators"""
    return c in SEPARATORS


def CheckToken(t):
    """Raises ValueError if *t* is *not* a valid token"""
    for c in t:
        if c in SEPARATORS:
            raise ValueError("Separator found in token: %s" % t)
        elif IsCTL(c) or not IsCHAR(c):
            raise ValueError("Non-ASCII or CTL found in token: %s" % t)


class HTTPParser(BasicParser):

    """A special purpose parser for parsing core HTTP productions."""

    def ParseLWS(self):
        """Parses a single instance of the production LWS

        The return value is the LWS string parsed of None if there is no
        LWS."""
        savePos = self.pos
        lws = []
        if self.Parse(CRLF):
            lws.append(CRLF)
        spLen = 0
        while True:
            c = self.ParseOne(SP + HT)
            if c is None:
                break
            else:
                lws.append(c)
                spLen += 1
        if lws and spLen:
            return string.join(lws, '')
        self.SetPos(savePos)
        return None

    def ParseOneTEXT(self, unfold=False):
        """Parses a single TEXT instance.

        Parses a single character or run of LWS matching the production
        TEXT.  The return value is the matching character, LWS string or
        None if no TEXT was found.

        If *unfold* is True then any folding LWS is replaced with a
        single SP.  It defaults to False"""
        lws = self.ParseLWS()
        if lws:
            if unfold and lws[:2] == CRLF:
                return SP
            else:
                return lws
        elif IsOCTET(self.theChar) and not IsCTL(self.theChar):
            result = self.theChar
            self.NextChar()
            return result
        else:
            return None

    def ParseTEXT(self, unfold=False):
        """Parses TEXT.

        Parses a run of characters matching the production TEXT.  The
        return value is the matching TEXT string (including any LWS) or
        None if no TEXT was found.

        If *unfold* is True then any folding LWS is replaced with a
        single SP.  It defaults to False"""
        text = []
        while self.theChar is not None:
            t = self.ParseOneTEXT(unfold)
            if t is not None:
                text.append(t)
            else:
                break
        if text:
            return string.join(text, '')
        else:
            return None

    def ParseToken(self):
        """Parses a token.

        Parses a single instance of the production token.  The return
        value is the matching token string or None if no token was
        found."""
        token = []
        while self.theChar is not None:
            if IsCTL(self.theChar) or IsSEPARATOR(self.theChar):
                break
            else:
                token.append(self.theChar)
                self.NextChar()
        if token:
            return string.join(token, '')
        else:
            return None

    def ParseComment(self, unfold=False):
        """Parses a comment.

        Parses a single instance of the production comment.  The return
        value is the entire matching comment string (including the
        brackets, quoted pairs and any nested comments) or None if no
        comment was found.

        If *unfold* is True then any folding LWS is replaced with a
        single SP.  It defaults to False"""
        if not self.Parse("("):
            return None
        comment = ["("]
        depth = 1
        while self.theChar is not None:
            if self.Parse(")"):
                comment.append(")")
                depth -= 1
                if depth < 1:
                    break
            elif self.Parse("("):
                comment.append("(")
                depth += 1
            elif self.Match("\\"):
                qp = self.ParseQuotedPair()
                if qp:
                    comment.append(qp)
                else:
                    raise ValueError(
                        "Expected quoted pair: %s..." % self.Peek(5))
            else:
                ctext = self.ParseCText(unfold)
                if ctext:
                    comment.append(ctext)
                else:
                    break
        comment = string.join(comment, '')
        if depth:
            raise ValueError("Unclosed comment: %s" % comment)
        else:
            return comment

    def ParseCText(self, unfold=False):
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
        while self.theChar is not None:
            if self.MatchOne("()\\"):
                break
            else:
                t = self.ParseOneTEXT(unfold)
                if t is None:
                    break
                else:
                    ctext.append(t)
        if ctext:
            return string.join(ctext, '')
        else:
            return None

    def ParseQuotedString(self, unfold=False):
        """Parses a quoted-string.

        Parses a single instance of the production quoted-string.  The
        return value is the entire matching string (including the quotes
        and any quoted pairs or None if no quoted-string was found.

        If *unfold* is True then any folding LWS is replaced with a
        single SP.  It defaults to False"""
        if not self.Parse(DQUOTE):
            return None
        qs = [DQUOTE]
        while self.theChar is not None:
            if self.Parse(DQUOTE):
                qs.append(DQUOTE)
                break
            elif self.Match("\\"):
                qp = self.ParseQuotedPair()
                if qp:
                    qs.append(qp)
                else:
                    raise ValueError(
                        "Expected quoted pair: %s..." % self.Peek(5))
            else:
                qdtext = self.ParseQDText(unfold)
                if qdtext:
                    qs.append(qdtext)
                else:
                    raise ValueError(
                        "Expected closing <\">: %s%s..." % (string.join(qs, ''), self.Peek(5)))
        return string.join(qs, '')

    def ParseQDText(self, unfold=False):
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
        while self.theChar is not None:
            if self.MatchOne("\\" + DQUOTE):
                break
            else:
                t = self.ParseOneTEXT(unfold)
                if t is None:
                    break
                else:
                    qdtext.append(t)
        if qdtext:
            return string.join(qdtext, '')
        else:
            return None

    def ParseQuotedPair(self):
        """Parses a single quoted-pair.

        The return value is the matching string including the backslash
        so it will always be of length 2 or None if no quoted-pair was
        found."""
        savePos = self.pos
        if self.Parse("\\"):
            if IsCHAR(self.theChar):
                qdPair = "\\" + self.theChar
                self.NextChar()
                return qdPair
            else:
                self.SetPos(savePos)
        return None


class WordParser(object):

    """A word-level parser and tokeniser for the HTTP grammar.

    *source* is the string to be parsed into words.  It will normally be
    valid TEXT but it can contain control characters if they are escaped
    as part of a comment or quoted string.

    LWS is unfolded automatically.  By default the parser ignores spaces
    according to the rules for implied LWS in the specification and
    neither SP nor HT will be stored in the word list.  If you set
    *ignoreSpace* to False then LWS is not ignored and each run of LWS
    is returned as a single SP in the word list.

    The resulting words may be a token, a single separator character, a
    comment or a quoted string.  To determine the type of word, look at
    the first character.

            *	'(' means the word is a comment, surrounded by '(' and ')'

            *	a double quote means the word is an encoded quoted string (use
                    py:func:`DecodeQuotedString` to decode it)

            *	other separator chars are just themselves and only appear as single
                    character strings.  (HT is never returned.)

            *	Any other character indicates a token.

    Method of the form Require\* raise :py:class:`SyntaxError` if the
    production is not found."""

    def __init__(self, source, ignoreSpace=True):
        self.words = []
        self.pos = 0			#: a pointer to the current word in the list
        self.cWord = None		#: the current word or None
        self._InitParser(source, ignoreSpace)

    def _InitParser(self, source, ignoreSpace=True):
        p = HTTPParser(source)
        while p.theChar is not None:
            sp = False
            while p.ParseLWS():
                if not ignoreSpace:
                    sp = True
            if sp:
                self.words.append(SP)
            if IsSEPARATOR(p.theChar):
                if p.theChar == "(":
                    self.words.append(p.ParseComment(True))
                elif p.theChar == DQUOTE:
                    self.words.append(p.ParseQuotedString(True))
                else:
                    self.words.append(p.theChar)
                    p.NextChar()
            else:
                self.words.append(p.ParseToken())
        self.pos = 0
        if self.words:
            self.cWord = self.words[0]
        else:
            self.cWord = None

    def SetPos(self, pos):
        """Sets the current position of the parser.

        Example usage for look-ahead::

                # wp is a WordParser instance
                savePos=wp.pos
                try:
                        # parse a token/sub-token combination
                        token=wp.RequireToken()
                        wp.RequireSeparator('/')
                        subtoken=wp.RequireToken()
                        return token,subtoken
                except SyntaxError:
                        wp.SetPos(savePos)
                        return None,None"""
        self.pos = pos
        if self.pos < len(self.words):
            self.cWord = self.words[self.pos]
        else:
            self.cWord = None

    def Peek(self):
        """Returns the next word or an empty string if there are no more words."""
        if self.cWord:
            return self.cWord
        else:
            return ""

    def Error(self, expected):
        """Raises :py:class:`SyntaxError`.

        *expected* a descriptive string indicating the expected
        production."""
        if self.cWord:
            raise SyntaxError("Expected %s, found %s" %
                              (expected, repr(self.cWord)))
        else:
            raise SyntaxError("Expected %s" % expected)

    def RequireProduction(self, result, production=None):
        """Returns *result* if not None or raises SyntaxError.

        *production*
                can be used to customize the error message with the name of
                the expected production."""
        if result is None:
            if production is None:
                raise SyntaxError("Error at ...%s" % self.Peek())
            else:
                raise SyntaxError("Expected %s at ...%s" %
                                  (production, self.Peek()))
        else:
            return result

    def ParseProduction(self, requireMethod, *args):
        """Executes the bound method *requireMethod* passing *args*.

        If successful the result of the method is returned.  If
        SyntaxError is raised, the exception is caught, the parser
        rewound and None is returned."""
        savePos = self.pos
        try:
            return requireMethod(*args)
        except SyntaxError:
            self.SetPos(savePos)
            return None

    def RequireProductionEnd(self, result, production=None):
        """Returns *result* if not None and parsing is complete or raises SyntaxError.

        *production*
                can be used to customize the error message with the name of
                the expected production."""
        result = self.RequireProduction(result, production)
        self.RequireEnd(production)
        return result

    def RequireEnd(self, production=None):
        """Raises SyntaxError unless the parser is at the end of the word list.

        *production*
                can be used to customize the error message with the name of
                the production being parsed."""
        if self.cWord:
            if production:
                raise SyntaxError(
                    "Spurious data after %s: found %s" % (production, repr(self.cWord)))
            else:
                raise SyntaxError("Spurious data: %s" % repr(self.cWord))

    def ParseWord(self):
        """Parses any word from the list returning the word consumed by the parser"""
        result = self.cWord
        self.pos += 1
        if self.pos < len(self.words):
            self.cWord = self.words[self.pos]
        else:
            self.cWord = None
        return result

    def IsToken(self):
        """Returns True if the current word is a token"""
        return self.cWord and self.cWord[0] not in SEPARATORS

    def ParseToken(self):
        """Parses a token from the list of words, returning the token or None."""
        if self.IsToken():
            return self.ParseWord()
        else:
            return None

    def ParseTokenLower(self):
        """Parses a token from the list of words, returning the lower-cased token or None."""
        if self.IsToken():
            return self.ParseWord().lower()
        else:
            return None

    def ParseTokenList(self):
        """Parses a token list from the list of words, returning the list or []."""
        result = []
        while self.cWord:
            token = self.ParseToken()
            if token:
                result.append(token)
            elif self.ParseSeparator(','):
                continue
            else:
                break
        return result

    def RequireToken(self, expected="token"):
        """Returns the current token or raises SyntaxError.

        *expected*
                the name of the expected production, it defaults to
                "token"."""
        token = self.ParseToken()
        if token is None:
            self.Error(expected)
        else:
            return token

    def IsInteger(self):
        """Returns True if the current word is an integer token"""
        return self.cWord and IsDIGITS(self.cWord)

    def ParseInteger(self):
        """Parses an integer from the list of words, returning the integer value or None."""
        if self.IsInteger():
            return int(self.ParseWord())
        else:
            return None

    def RequireInteger(self, expected="integer"):
        """Parses an integer or raises SyntaxError.

        *	*expected* can be set to the name of the expected object."""
        result = self.ParseInteger()
        if result is None:
            self.Error(expected)
        else:
            return result

    def IsSeparator(self, sep):
        """Returns True if the current word matches *sep*"""
        return self.cWord == sep

    def ParseSeparator(self, sep):
        """Parses a *sep* from the list of words.

        Returns True if the current word matches *sep* and False otherwise."""
        if self.cWord == sep:
            self.ParseWord()
            return True
        else:
            return False

    def RequireSeparator(self, sep, expected=None):
        """Parses *sep* or raises SyntaxError.

        *	*expected* can be set to the name of the expected object."""
        if self.cWord == sep:
            self.ParseWord()
        else:
            self.Error(expected)

    def IsQuotedString(self):
        """Returns True if the current word is a quoted string."""
        return self.cWord and self.cWord[0] == DQUOTE

    def ParseQuotedString(self):
        """Parses a quoted string from the list of words.

        Returns the *unencoded* quoted string or None."""
        if self.IsQuotedString():
            return DecodeQuotedString(self.ParseWord())
        else:
            return None

    def ParseSP(self):
        """Parses a SP from the list of words.

        Returns True if the current word is a SP and False otherwise."""
        return self.ParseSeparator(SP)

    def ParseParameters(self, parameters, ignoreAllSpace=True, caseSensitive=False, qMode=None):
        """Parses a set of parameters from a list of words.

                *	*parameters* is the dictionary in which to store the parsed parameters

                *	*ignoreAllSpace* is a boolean (defaults to True) which causes the
                        function to ignore all LWS in the word list.  If set to False then space
                        around the '=' separator is treated as an error and raises SyntaxError.

                *	caseSensitive controls whether parameter names are treated as case
                        sensitive, defaults to False.

                *	qMode allows you to pass a special parameter name that will
                        terminate parameter parsing (without being parsed itself).  This is
                        used to support headers such as the "Accept" header in which the
                        parameter called "q" marks the boundary between media-type
                        parameters and Accept extension parameters.

        Updates the parameters dictionary with the new parameter definitions.
        The key in the dictionary is the parameter name (converted to lower case
        if parameters are being dealt with case insensitively) and the value is
        a 2-item list of [ name, value ] always preserving the original case of
        the parameter name."""
        self.ParseSP()
        while self.cWord:
            savePos = self.pos
            try:
                self.ParseSP()
                self.RequireSeparator(';')
                self.ParseSP()
                paramName = self.RequireToken("parameter")
                if not caseSensitive:
                    paramKey = paramName.lower()
                else:
                    paramKey = paramName
                if qMode and paramKey == qMode:
                    raise SyntaxError
                if ignoreAllSpace:
                    self.ParseSP()
                self.RequireSeparator('=', "parameter")
                if ignoreAllSpace:
                    self.ParseSP()
                if self.IsToken():
                    paramValue = self.ParseToken()
                elif self.IsQuotedString():
                    paramValue = self.ParseQuotedString()
                else:
                    self.Error("parameter value")
                parameters[paramKey] = [paramName, paramValue]
            except SyntaxError:
                self.SetPos(savePos)
                break

    def ParseRemainder(self, sep=''):
        """Parses the rest of the words, joining them into a single string with *sep*.

        Returns an empty string if the parser is at the end of the word list."""
        if self.cWord:
            result = string.join(self.words[self.pos:], sep)
        else:
            result = ''
        self.SetPos(len(self.words))
        return result


def DecodeQuotedString(qstring):
    """Decodes a quoted string, returning the unencoded string.

    Surrounding double quotes are removed and quoted characters (characters
    preceded by \\) are unescaped."""
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


def QuoteString(s, force=True):
    """Places a string in double quotes, returning the quoted string.

    This is the reverse of :py:func:`DecodeQuotedString`.  Note that
    only the double quote, \\ and CTL characters other than SP and HT
    are quoted in the output.

    If *force* is False then valid tokens are *not* quoted."""
    qstring = ['"']
    for c in s:
        if c in '\\"' or (IsCTL(c) and c not in SP + HT):
            qstring.append('\\' + c)
            force = True
        elif IsCTL(c) or IsSEPARATOR(c):
            force = True
            qstring.append(c)
        else:
            qstring.append(c)
    if force:
        qstring.append('"')
    else:
        del qstring[0]
    return string.join(qstring, '')


def FormatParameters(parameters):
    keys = parameters.keys()
    keys.sort()
    format = []
    for k in keys:
        format.append('; ')
        p, v = parameters[k]
        format.append(p)
        format.append('=')
        format.append(QuoteString(v, force=False))
    return string.join(format, '')
