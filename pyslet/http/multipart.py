#! /usr/bin/env python


import base64
import errno
import io
import os
import random

from ..py2 import (
    byte,
    is_byte,
    is_unicode,
    join_bytes,
    range3)
from ..py26 import RawIOBase
from .. import unicode5

from . import grammar
from .messages import (
    Message,
    ProtocolError,
    RecvWrapper,
    RecvWrapperBase,
    SendWrapper)
from .params import MediaType, APPLICATION_OCTETSTREAM


class MultipartError(ProtocolError):
    pass


SPECIALS = set('()<>@,;:\\".[]'.encode('ascii'))


def is_special(b):
    """Returns True if a byte is an RFC822 special"""
    return b in SPECIALS


def decode_domain_literal(dstring):
    """Decodes a domain-literal, returning the unencoded string.

    Surrounding brackets are removed and quoted bytes, bytes preceded by
    $5C (backslash), are unescaped.

    The return value is decoded using us-ascii as, in practice, anything
    outside that character set will be non-portable.  It is therefore
    returned as a character string."""
    dstring = dstring[1:-1]
    if dstring.find(b'\\') >= 0:
        # skip the loop if we don't have any escape sequences
        dbuff = []
        escape = False
        for b in dstring:
            if not escape and b == grammar.REVERSE_SOLIDUS:
                escape = True
                continue
            dbuff.append(b)
            escape = False
        return join_bytes(dbuff).decode('ascii')
    else:
        return dstring.decode('ascii')


def encode_domain_literal(literal):
    """Places a literal in square brackets.

    literal
        A string of ASCII characters

    This is the reverse of :py:func:`decode_domain_literal` so it
    returns a binary string of bytes.  Note that only the square
    brackets, \\ and CR characters are quoted in the output as per the
    definition of dtext"""
    dstring = [grammar.LEFT_SQUARE_BRACKET]
    for b in literal.encode('ascii'):
        if b in (grammar.REVERSE_SOLIDUS, grammar.LEFT_SQUARE_BRACKET,
                 grammar.RIGHT_SQUARE_BRACKET, grammar.CR):
            dstring.append(grammar.REVERSE_SOLIDUS)
        dstring.append(b)
    dstring.append(grammar.RIGHT_SQUARE_BRACKET)
    return join_bytes(dstring)


class RFC822OctetParser(grammar.OctetParser):

    def parse_atom(self):
        """Parses an atom.

        Parses a single instance of the production atom.  The return
        value is the matching atom as a binary string or None if no atom
        was found."""
        atom = []
        while self.the_char is not None:
            if self.the_char == grammar.SP or is_special(self.the_char) or \
                    grammar.is_ctl(self.the_char):
                break
            else:
                atom.append(self.the_char)
                self.next_char()
        if atom:
            return join_bytes(atom)
        else:
            return None

    def parse_domain_literal(self):
        """Parses a domain literal.

        Parses a single instance of the production domain-literal.  The
        return value is the entire matching string (including the brackets
        and any quoted pairs) or None if no domain-literal was found."""
        if not self.parse(b'['):
            return None
        dl = [b'[']
        while self.the_char is not None:
            if self.parse(b']'):
                dl.append(b']')
                break
            elif self.match(b"\\"):
                qp = self.parse_quoted_pair()
                if qp:
                    dl.append(qp)
                else:
                    self.parser_error("quoted pair")
            else:
                dtext = self.parse_dtext()
                if dtext:
                    dl.append(dtext)
                else:
                    self.parser_error('<]>')
        return b''.join(dl)

    def parse_dtext(self):
        """Parses dtext.

        Parses a run of characters matching the production dtext.  The
        return value is the matching dtext string (including any LWS)
        or None if no dtext was found.

        Any folding LWS is replaced with a single SP."""
        dtext = []
        while self.the_char is not None:
            if self.match_one(b'[]\\\r'):
                break
            else:
                t = self.parse_onetext(True)
                if t is not None:
                    if is_byte(t):
                        dtext.append(t)
                    else:
                        dtext += list(t)
                else:
                    break
        if dtext:
            return join_bytes(dtext)
        else:
            return None


class RFC822Parser(unicode5.ParserMixin):

    """A parser and tokeniser for the RFC822 grammar.

    source
        The binary string to be parsed into tokens.  It will normally be
        valid TEXT but it can contain control characters if they are
        escaped as part of a comment, quoted string or domain literal.
        For compatibility, character strings are accepted provided they
        only contain US ASCII characters

    The source is parsed completely into tokens on construction using
    :class:`grammar.OctetParser`. If the source contains a CRLF (or any
    other non-TEXT bytes) that is not part of a folding or escape
    sequence it raises :class:`~pyslet.unicode5.ParserError`.

    For the purposes of this parser, a token may be either a single byte
    (in which case it is a special or SP, note that HT is never stored
    in the token list) or a binary string, in which case it is an atom,
    a comment, a quoted string or a domain literal.  Warning: in Python
    2 a single byte is indistinguishable from a binary string of length
    1.

    Methods follow the same pattern as that described in the related
    :class:`pyslet.unicode5.BasicParser` using match\_, parse\_ and
    require\_ naming conventions.  It also includes the
    :class:`pyslet.unicode5.ParseMixin` class to enable the convenience
    methods for converting between look-ahead and non-look-ahead parsing
    modes."""

    def __init__(self, source):
        self.source = source
        self.tokens = []
        self.src_pos = []
        #: a pointer to the current token in the list
        self.pos = 0
        #: the current token or None
        self.the_token = None
        self.last_error = None
        self._init_parser(source)

    def _init_parser(self, source):
        p = RFC822OctetParser(source)
        while p.the_char is not None:
            src_pos = p.pos
            while p.parse_lws():
                pass
            if is_special(p.the_char):
                if p.the_char == grammar.LEFT_PARENTHESIS:
                    # comments are not added to the token list
                    p.parse_comment(True)
                elif p.the_char == grammar.DQUOTE:
                    self.tokens.append(p.parse_quoted_string(True))
                elif p.the_char == grammar.LEFT_SQUARE_BRACKET:
                    self.tokens.append(p.parse_domain_literal())
                else:
                    self.tokens.append(p.the_char)
                    p.next_char()
                self.src_pos.append(src_pos)
            elif p.the_char is None:
                break
            else:
                self.tokens.append(p.require_production(p.parse_atom(),
                                                        "atom"))
                self.src_pos.append(src_pos)
        self.pos = 0
        if self.tokens:
            self.the_token = self.tokens[0]
        else:
            self.the_token = None

    def setpos(self, pos):
        """Sets the current position of the parser.

        See :meth:`grammar.WordParser.setpos` for example usage"""
        self.pos = pos
        if self.pos < len(self.tokens):
            self.the_token = self.tokens[self.pos]
        else:
            self.the_token = None

    def parser_error(self, production=None):
        """Raises an error encountered by the parser

        See :class:`BadSyntax` for details.

        If production is None then the previous error is re-raised. If
        multiple errors have been raised previously the one with the
        most advanced parser position is used.  The operation is similar
        to :meth:`pyslet.unicode5.BasicParser.parser_error`.

        To improve the quality of error messages an internal record of
        the starting position of each token is kept (within the original
        source).

        The position of the parser is always set to the position of the
        error raised."""
        if production:
            e = grammar.BadSyntax(production, self)
        elif self.last_error is not None and self.pos <= self.last_error.pos:
            e = self.last_error
        else:
            e = grammar.BadSyntax('', self)
        if self.last_error is None or e.pos > self.last_error.pos:
            self.last_error = e
        if e.pos != self.pos:
            self.setpos(e.pos)
        raise e

    def match_end(self):
        """True if all of :attr:`tokens` have been parsed"""
        return self.the_token is None

    def peek(self):
        """Returns the next token

        If there are no more tokens, returns None."""
        if self.the_token:
            return self.the_token
        else:
            return ""

    def parse_token(self):
        """Parses any token from the list

        Returns the token parsed or None if the parser was already at the
        end of the token list."""
        result = self.the_token
        self.pos += 1
        if self.pos < len(self.tokens):
            self.the_token = self.tokens[self.pos]
        else:
            self.the_token = None
        return result

    def is_atom(self):
        """Returns True if the current token is an atom"""
        # atoms are never empty!
        return isinstance(self.the_token, bytes) and \
            self.the_token[0] not in SPECIALS

    def parse_atom(self):
        """Parses an atom from the list of tokens

        Returns the atom or None if the next token was not an atom.  The
        return value is a binary string.  This is consistent with the
        use of this method for parsing atoms in contexts where an atom
        or a quoted string may be present."""
        if self.is_atom():
            return self.parse_token()
        else:
            return None

    def require_atom(self, expected="atom"):
        """Returns the current atom or raises :py:class:`BadSyntax`

        expected
            the name of the expected production, it defaults to
            "atom"."""
        atom = self.parse_atom()
        if atom is None:
            self.parser_error(expected)
        else:
            return atom

    def is_special(self, s):
        """Returns True if the current token matches *s*"""
        return self.the_token == s

    def parse_special(self, s):
        """Parses a *s* from the list of tokens.

        Returns True if the current token matches *s* and False
        otherwise."""
        if self.the_token == s:
            self.parse_token()
            return True
        else:
            return False

    def require_special(self, s, expected=None):
        """Parses *s* or raises :py:class:`BadSyntax`

        s
            A special byte (not a binary string).

        expected
            can be set to the name of the expected object"""
        if self.the_token == s:
            self.parse_token()
        else:
            self.parser_error(expected)

    def is_quoted_string(self):
        """Returns True if the current token is a quoted string."""
        return isinstance(self.the_token, bytes) and \
            self.the_token[0] == grammar.DQUOTE

    def parse_quoted_string(self):
        """Parses a quoted string from the list of tokens.

        Returns the *decoded* value of the quoted string or None."""
        if self.is_quoted_string():
            return grammar.decode_quoted_string(self.parse_token())
        else:
            return None

    def is_domain_literal(self):
        """Returns True if the current token is a domain literal."""
        return isinstance(self.the_token, bytes) and \
            self.the_token[0] == grammar.LEFT_SQUARE_BRACKET

    def parse_domain_literal(self):
        """Parses a domain literal from the list of tokens.

        Returns the *decoded* value of the domain literal or None."""
        if self.is_domain_literal():
            return decode_domain_literal(self.parse_token())
        else:
            return None

    def parse_sub_domain(self):
        """Parses a sub-domain from the list of tokens.

        Returns a character string representing the sub-domain.  If the
        sub-domain parsed is a domain literal it is brakceted and any
        required escapes are applied resulting in a canonical
        representation.

        Returns None if no sub-domain is found."""
        if self.is_atom():
            return self.parse_atom().decode('ascii')
        elif self.is_domain_literal():
            return encode_domain_literal(
                self.parse_domain_literal()).decode('ascii')
        else:
            return None

    def require_domain(self):
        """Parses a domain from the list of tokens.

        Returns a character string containing the domain parsed.  We
        adhere to the rules of RFC822 leaving the individual components
        uninterpreted so sub-domains are not converted to lower case for
        example.  However, domain literals are canonicalised with
        respect to escaping.

        If no domain can be parsed BadSyntax is raised."""
        sub_domains = []
        while True:
            save_pos = self.pos
            try:
                if sub_domains:
                    self.require_special(byte('.'))
                sd = self.require_production(self.parse_sub_domain(),
                                             'sub-domain')
                sub_domains.append(sd)
            except grammar.BadSyntax:
                self.setpos(save_pos)
                break
        if sub_domains:
            return ".".join(sub_domains)
        else:
            return self.parser_error()

    def require_localpart(self):
        """Parses a localpart from the list of tokens.

        Returns a character string containing the localpart parsed.  We
        adhere to the rules of RFC822 leaving the individual components
        uninterpreted so words are not case converted and quoted strings
        are left quoted though they are canonicalised to remove
        unnecessary quoted strings or quoted pairs.

        If no localpart can be parsed BadSyntax is raised."""
        parts = []
        while True:
            save_pos = self.pos
            try:
                if parts:
                    self.require_special(byte('.'))
                if self.is_atom():
                    parts.append(self.parse_atom().decode('ascii'))
                elif self.is_quoted_string():
                    q = self.parse_quoted_string()
                    parts.append(
                        grammar.quote_string(q, False).decode('ascii'))
                else:
                    self.parser_error("word")
            except grammar.BadSyntax:
                self.setpos(save_pos)
                break
        if parts:
            return ".".join(parts)
        else:
            return self.parser_error()

    def require_addr_spec(self):
        """Parses an addr-spec from the list of tokens.

        Returns a character string containing the entire address."""
        localpart = self.require_localpart()
        self.require_special(grammar.COMMERCIAL_AT)
        domain = self.require_domain()
        return localpart + '@' + domain

    def require_msg_id(self):
        """Parses a msg-id from the list of tokens.

        Returns a character string containing the entire msg-id but
        without the enclosing angle-brackets."""
        self.require_special(grammar.LESSTHAN_SIGN)
        msg_id = self.require_addr_spec()
        self.require_special(grammar.GREATERTHAN_SIGN)
        return msg_id


_BCHARNOSP_SPECIALS = set("'()+_,-./:=?".encode('ascii'))


def is_bcharnospace(b):
    """Returns True if a byte satisfies product bcharnospace"""
    return grammar.is_digit(b) or grammar.is_alpha(b) or \
        b in _BCHARNOSP_SPECIALS


_BCHAR_SPECIALS = set("'()+_,-./:=? ".encode('ascii'))


def is_bchars(b):
    """Returns True if a byte satisfies product bchars"""
    return grammar.is_digit(b) or grammar.is_alpha(b) or b in _BCHAR_SPECIALS


def make_boundary_delimiter(prefix=b""):
    """Returns a boundary delimiter selected randomly

    The result is a binary string."""
    if prefix:
        if not is_valid_boundary(prefix):
            raise ValueError("bad prefix")
    s = []
    for i in range3(30):
        s.append(byte(random.randint(0, 255)))
    return prefix + base64.b64encode(join_bytes(s))


def is_valid_boundary(boundary):
    """Checks the syntax of boundary

    The input parameter is a character string."""
    if len(boundary) > 70 or len(boundary) < 1:
        return False
    if not is_bcharnospace(boundary[0]):
        return False
    for b in boundary[1:]:
        if not is_bchars(b):
            return False
    return True


def get_boundary_delimiter(mtype):
    """Returns the boundary delimiter for a mediatype

    mtype
        A :class:`~pyslet.http.params.MediaType` instance.  If it is
        not a multipart type then a ValueError is raised.

    The boundary parameter is extracted from the media type and is
    combined with *preceding* CRLF and "--" strings to create the
    boundary delimiter."""
    if mtype.type != "multipart":
        raise ValueError("%s is not a multiplart type" % str(mtype))
    try:
        boundary = mtype['boundary'].decode('ascii')
        if len(boundary) > 70:
            raise MultipartError("multipart boundary too long")
        return "\r\n--" + boundary
    except UnicodeError:
        raise MultipartError("non-ASCII multipart boundary")


class MessagePart(Message):

    DEFAULT_TYPE = MediaType.from_str("text/plain; charset=us-ascii")

    def __init__(self, **kws):
        super(MessagePart, self).__init__(**kws)

    def send_start(self):
        """A MIME message part has no start line"""
        return b""

    def send_transferlength(self):
        """A MIME message does not need a content length

        By overriding this method we also suppress any transfer
        encoding.  Note that content-transfer encoding is managed by the
        calling application, i.e., the entity body must already have
        been transformed to match the value of the header."""
        self.transferchunked = False
        self.transferbody = self.entity_body
        if self.transferbody is None:
            self.transferlength = 0
        else:
            self.transferlength = None

    def send_header(self):
        """Returns a data string ready to send to the server

        Overridden to impose constrains on the headers that are
        returned as per...

             Any field not beginning with "content-" can have no defined
             meaning and may be ignored."""
        buffer = []
        # Calculate the length of the message body for transfer
        self.send_transferlength()
        hlist = self.get_headerlist()
        for hKey in hlist:
            if not hKey.startswith(b"content-") and \
                    not hKey.startswith(b"x-"):
                # allow "X-" for custom headers
                continue
            h = self.headers[hKey]
            hname = h[0]
            for hvalue in h[1:]:
                buffer.append(b"%s: %s\r\n" % (hname, hvalue))
        buffer.append(b"\r\n")
        return b''.join(buffer)

    def start_receiving(self):
        """A MIME message part has no start line so advance the mode."""
        super(MessagePart, self).start_receiving()
        with self.lock:
            self.transfermode = self.HEADER_MODE

    def recv_transferlength(self):
        # we always transfer up until end of file is detected in the
        # source ignoring any Content-Length header
        self.transferlength = None

    def get_content_type(self):
        # check the content-transfer-encoding
        encoding = self.get_content_transfer_encoding()
        if encoding is None or encoding not in ('7bit', '8bit', 'binary',
                                                'quoted-printable', 'base64'):
            # unrecognized type
            return APPLICATION_OCTETSTREAM
        mtype = super(MessagePart, self).get_content_type()
        if mtype is None:
            # we need a default type
            mtype = self.DEFAULT_TYPE
        return mtype

    def set_content_transfer_encoding(self, token):
        token = token.encode('ascii')
        grammar.check_token(token)
        self.set_header('Content-Transfer-Encoding', token)

    def get_content_transfer_encoding(self):
        """Returns any content transfer encoding header

        The result is a character string or None if the header does not
        contain a valid token.  If the header is missing then the
        default value '7bit' is returned."""
        token = self.get_header('Content-Transfer-Encoding')
        if token is not None:
            try:
                return grammar.check_token(token.lower())
            except ValueError:
                return None
        else:
            return '7bit'

    def set_content_id(self, id):
        """Sets the Content-ID header from a character string

        id
            The ID of this message part.  The id should not have the
            enclosing angle-brackets, these are added automatically. The
            value is parsed to check it matches the specification for
            addr-spec in RFC822.  In brief, that means it should look
            like an email address in localpart@domain form."""
        p = RFC822Parser(id.encode('ascii'))
        id = p.require_addr_spec()
        p.require_end()
        self.set_header('Content-ID', b"<%s>" % id.encode('ascii'))

    def get_content_id(self):
        """Retrieves the Content-ID header

        The header value is parsed according to RFC822's msg-id
        production and the angle brackets removed to return just the
        addr-spec of the ID.  If there is no Content-ID header or
        the parse fails then None is returned."""
        id = self.get_header('Content-ID')
        if id is not None:
            try:
                p = RFC822Parser(id)
                id = p.require_msg_id()
                p.require_end()
            except ValueError:
                id = None
        return id

    def set_content_description(self, text):
        """Sets the Content-Description header

        text
            Either a character string or a binary string.  Character
            strings must be encodable with US-ASCII."""
        if is_unicode(text):
            text = text.encode('ascii')
        self.set_header('Content-Description', text)

    def get_content_description(self):
        """Gets the Content-Description header value

        Returned as raw bytes, if there is no such header None is
        returned."""
        return self.get_header('Content-Description')


class MultipartRecvWrapper(RecvWrapperBase):

    """A stream wrapper for multipart message bodies

    src
        The source stream from which the multipart message will be read,
        must be an object supporting the RawIOBase interface.

    mtype
        A :class:`params.MediaType` instance that describes the media
        type of the entity body to be read from source.  It must be a
        multipart type and have a valid boundary parameter.

    Instances behave like streams (supporing the RawIOBase interface)
    wrapping the source but signaling an end of file when the multipart
    boundary is encountered.  You can skip forward to the next part at
    any time using the :meth:`read_boundary` method.

    The stream returns all the data in each part of the message
    including any headers but *excluding* any boundary lines. Therefore,
    on construction the stream points to the preamble (even if it is
    empty).

    You won't normally read the multipart stream directly (unless you
    want to read the preamble and epilogue data).  Instead, you'll use
    :meth:`next_part` to obtain stream wrappers for each part."""

    def __init__(self, src, mtype):
        RecvWrapperBase.__init__(self, src)
        self.mtype = mtype
        self.boundary_str = get_boundary_delimiter(mtype).encode('ascii')
        self.boundary_len = len(self.boundary_str)
        # start bmatch as if we already matched CRLF, this catches the
        # case where the preamble is empty and the body starts with the
        # dash-boundary
        self.bmatch = [2, 0]
        self.bmatch_pos = 0
        self.bmax = 0
        self._boundary_detected = False
        self.epilogue = False
        self.parts = []

    def readable(self):
        return True

    def writable(self):
        return False

    def _detect_boundary(self):
        blen = len(self.buffer)
        while self.bmatch_pos < blen and not self._boundary_detected:
            b = byte(self.buffer[self.bmatch_pos])
            new_bmatch = [0]
            for mpos in self.bmatch:
                if b == self.boundary_str[mpos]:
                    mpos += 1
                    new_bmatch.append(mpos)
            self.bmatch_pos += 1
            max_match = max(new_bmatch)
            self.bmax = max(0, self.bmatch_pos - max_match)
            if max_match >= self.boundary_len:
                # we have a complete match
                new_bmatch = [0]
                self._boundary_detected = True
            self.bmatch = new_bmatch

    def readinto(self, b):
        """Read up to len(b) bytes into bytearray b and return the
        number of bytes read. If the object is in non-blocking mode and
        no bytes are available, None is returned."""
        if self.closed:
            raise IOError(errno.EBADF, os.strerror(errno.EBADF),
                          "stream is closed")
        if self.bmax < 0:
            # indicates we're blocked reading a boundary, continue
            # to return EOF.
            return 0
        # is the buffer empty?
        if not self.bmax:
            # if we're in the epilogue, just read directly from
            # the source
            if self.epilogue:
                return self.src.readinto(b)
            elif self._boundary_detected:
                # EOF
                return 0
            # otherwise we're waiting on a boundary
            try:
                while not self.bmax and not self._boundary_detected:
                    # go around until we inch forward or hit EOF
                    if not self.fill_buffer():
                        return None
                    self._detect_boundary()
            except ProtocolError:
                # unexpected EOF, there should be a terminating boundary
                # without one we can't be sure we got all the data so we
                # want to raise an error but to be nice, we empty the
                # buffer before throwing one.  This helps in cases where
                # the terminating boundary is the only thing that is
                # missing and the entity has its own method of
                # determining content length.  In these cases, the
                # caller probably won't call us again and be none the
                # wiser.
                self.bmax = len(self.buffer)
                # remove any partial match
                self.bmatch = [0]
                self.bmatch_pos = self.bmax
                if not self.bmax:
                    # buffer empty, no more data, no boundary
                    raise MultipartError("expected multipart boundary")
        # there's something in the buffer
        nbytes = len(b)
        if self.bmax >= nbytes:
            # send all requested bytes
            b[:] = self.buffer[:nbytes]
        else:
            # send bmax bytes
            b[:self.bmax] = self.buffer[:self.bmax]
            nbytes = self.bmax
        del self.buffer[:nbytes]
        self.bmax = self.bmax - nbytes
        self.bmatch_pos = self.bmatch_pos - nbytes
        return nbytes

    def read_boundary(self):
        """Reads the boundary, discarding any trailing data.

        Returns True to indicate another part, False indicating just the
        epilogue and None if the src is read blocked."""
        # it is an error to call this function during the epilogue
        if self.epilogue:
            raise MultipartError("no boundary in epilogue")
        if self.bmax >= 0:
            # discard the remaining data in the stream
            while True:
                data = self.read(io.DEFAULT_BUFFER_SIZE)
                if data is None:
                    return None
                elif data:
                    continue
                elif self._boundary_detected:
                    break
                else:
                    raise MultipartError("expected multipart boundary")
            # so we must have _boundary_detected, EOF and bmax = 0
            # discard the matched boundary delimiter
            del self.buffer[:self.bmatch_pos]
            self.bmatch_pos = 0
            # signal to read (and ourselves) that we are reading the
            # rest of the boundary line at the moment
            self.bmax = -1
        while True:
            # search for the end of the boundary line
            pos = self.buffer.find(b"\r\n")
            if pos < 0:
                # fill the buffer, ignoring the boundary and loop
                try:
                    if self.fill_buffer():
                        return None
                    continue
                except ProtocolError:
                    # raised if come to the end of the source stream
                    # OK assuming this is the last boundary (check later)
                    break
            else:
                break
        # OK, does the rest of the line start with '--'?
        self._boundary_detected = False
        if self.buffer.startswith(b"--"):
            if pos >= 0:
                tp_end = pos
            else:
                # EOF in terminating boundary
                tp_end = len(self.buffer)
            # we're in the epilogue (even if it's empty)
            self.epilogue = True
            # check and discard the transport padding
            for c in self.buffer[2:tp_end]:
                if byte(c) not in b" \t":
                    raise MultipartError(
                        "multipart boundary found in message part")
            # the CRLF is not part of the epilogue
            if pos >= 0:
                del self.buffer[:tp_end + 2]
            else:
                del self.buffer[:tp_end]
            self.bmax = len(self.buffer)
        elif pos < 0:
            # there must be another part to follow so the CRLF is
            # required
            raise MultipartError("expected next part in multipart message")
        else:
            for c in self.buffer[:pos]:
                if byte(c) not in b" \t":
                    raise MultipartError(
                        "multipart boundary found in message part")
            del self.buffer[:pos + 2]
            self.bmax = 0
            # new part, we may already have the boundary in the buffer
            self.bmatch_pos = 0
            self.bmatch = [0]
            self._detect_boundary()
        return not self.epilogue

    def next_part(self):
        """Returns the next message part

        Returns a :class:`RecvWrapper` instance that reads a
        :class:`MessagePart` from the source stream.  If the
        previous part has any remaining data this is read *and
        discarded* first.

        If the source stream is blocked then None is returned.

        If there are no more parts then StopIteration is raised."""
        if self.epilogue:
            raise StopIteration
        boundary = self.read_boundary()
        if boundary is None:
            # call us again!
            return None
        elif not boundary:
            if not self.parts:
                # this is an error, you can't end the epilogue
                # with a terminating boundary.
                raise MultipartError(
                    "multipart message must contain at least one part")
            raise StopIteration
        else:
            part = RecvWrapper(self, MessagePart)
            self.parts.append(part.message)
            return part

    def read_parts(self):
        """Generator that will iterate through all the parts

        Each part is a :class:`RecvWrapper` instance that reads a
        :class:`MessagePart` from the source stream.  You must
        read any data you need from each part before advancing the
        iterator to the next part as the generator calls
        :meth:`next_part` which will discard any remaining data.

        The difference between iterating this way and using
        :meth:`next_part` on its own is that this generator will ensure
        the headers are loaded before yielding the part enabling you to
        examine the headers before deciding whether or not to read the
        part's body data or not.

        The iterator will yield None when the source stream is
        in non-blocking mode and is read blocked."""
        while True:
            try:
                part = self.next_part()
                if part is None:
                    yield None
                    continue
                while True:
                    message = part.read_message_header()
                    if message is None:
                        yield None
                    else:
                        break
                yield part
            except StopIteration:
                return


class MultipartSendWrapper(RawIOBase):

    def __init__(self, mtype, parts, preamble=None, epilogue=None):
        self.mtype = mtype
        self.delimiter = get_boundary_delimiter(mtype).encode('ascii')
        self.parts = iter(parts)
        if preamble is None:
            # start with an empty buffer
            self.buffer = b""
        else:
            self.buffer = preamble + b"\r\n"
        self.bpos = 0
        self.epilogue = epilogue
        self.part = SendWrapper(next(self.parts))
        # now add the dash-boundary + CRLF
        self.buffer += self.delimiter[2:] + b"\r\n"

    def readable(self):
        return True

    def writable(self):
        return False

    def write(self, b):
        raise IOError(errno.EPERM, os.strerror(errno.EPERM),
                      "stream not writable")

    def readinto(self, b):
        if self.closed:
            raise IOError(errno.EBADF, os.strerror(errno.EBADF),
                          "stream is closed")
        while True:
            if self.buffer is None:
                # end of file condition
                return 0
            nbytes = len(b)
            bbytes = len(self.buffer) - self.bpos
            if bbytes <= 0:
                # attempt to refill the buffer
                if self.part is None:
                    # EOF condition
                    self.buffer = None
                    return 0
                new_buffer = self.part.read(io.DEFAULT_BUFFER_SIZE)
                if new_buffer is None:
                    # read blocked
                    return None
                elif not new_buffer:
                    try:
                        self.part = SendWrapper(next(self.parts))
                        # add the boundary to the buffer + CRLF
                        new_buffer = self.delimiter + b"\r\n"
                    except StopIteration:
                        # no more parts
                        self.part = None
                        # add the close-delimiter and epilogue
                        new_buffer = self.delimiter + b"--"
                        if self.epilogue is not None:
                            new_buffer += b"\r\n" + self.epilogue
                bbytes = len(new_buffer)
                self.buffer = new_buffer
                self.bpos = 0
            if bbytes > 0:
                # return the remains of the buffer
                if nbytes > bbytes:
                    nbytes = bbytes
                b[:nbytes] = self.buffer[self.bpos:self.bpos + nbytes]
                self.bpos += nbytes
                return nbytes
            else:
                # buffer was not refilled but not EOF
                return None
