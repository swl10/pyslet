#! /usr/bin/env python

import base64
import decimal
import uuid

from .. import iso8601 as iso
from ..py2 import (
    byte,
    character,
    range3,
    uempty,
    ul,
    )
from ..unicode5 import (
    BasicParser,
    CharClass,
    ParserError
    )
from ..xml import xsdatatypes as xsi

from . import (
    comex,
    geotypes as geo,
    names,
    query,
    )


_oid_start_char = CharClass("_")
_oid_start_char.add_class(CharClass.ucd_category("L"))
_oid_start_char.add_class(CharClass.ucd_category("Nl"))

_oid_char = CharClass()
for c in ("L", "Nl", "Nd", "Mn", "Mc", "Pc", "Cf"):
    _oid_char.add_class(CharClass.ucd_category(c))

_word_char = CharClass()
_word_char.add_class(CharClass.ucd_category("L"))
_word_char.add_class(CharClass.ucd_category("Nl"))


class Parser(BasicParser):

    """A Parser for the OData ABNF"""

    # Line 164
    count = ul('/$count')

    # Line 165
    ref = ul('/$ref')

    # Line 166
    value = ul('/$value')

    # Line 245
    def require_expand(self):
        """Parse the value component of expand

        We only parse::

            expandItem *( COMMA expandItem )

        Returns a list of :class:`query.ExpandItem`."""
        items = []
        items.append(self.require_expand_item())
        while self.parse(self.COMMA):
            items.append(self.require_expand_item())
        return items

    # Line 246
    def require_expand_item(self):
        """Parse the production expandItem

        Returns a :class:`query.ExpandItem` instance."""
        if self.parse(self.STAR):
            path = [self.STAR, ]
            if self.parse(self.ref):
                path.append("$ref")
                item = query.ExpandItem(tuple(path))
            elif self.parse(self.OPEN):
                # levels doesn't consume the option name
                item = query.ExpandItem(tuple(path))
                self.require('$levels=')
                levels = self.require_levels()
                self.require(self.CLOSE)
                item.options.set_levels(levels)
            else:
                item = query.ExpandItem(tuple(path))
            return item
        path = self.require_expand_path()
        if self.parse(self.ref):
            path.append("$ref")
            item = query.ExpandItem(tuple(path))
            if self.parse(self.OPEN):
                self.require_expand_ref_option(item.options)
                while self.parse(self.SEMI):
                    self.require_expand_ref_option(item.options)
                self.require(self.CLOSE)
        elif self.parse(self.count):
            path.append("$count")
            item = query.ExpandItem(tuple(path))
            if self.parse(self.OPEN):
                self.require_expand_count_option(item.options)
                while self.parse(self.SEMI):
                    self.require_expand_count_option(item.options)
                self.require(self.CLOSE)
        elif self.parse(self.OPEN):
            item = query.ExpandItem(tuple(path))
            self.require_expand_option(item.options)
            while self.parse(self.SEMI):
                self.require_expand_option(item.options)
            self.require(self.CLOSE)
        else:
            item = query.ExpandItem(tuple(path))
        return item

    # Line 252
    def require_expand_path(self):
        """Parses production expandPath

        The syntax is a bit obscure from the definition due to
        the equivalence of many of the constructs but it
        reduces to::

            [ qualifiedName "/" ] odataIdentifier
                *( "/" [ qualifiedName "/" ] odataIdentifier )
                [ "/" qualifiedName ]

        We return a list of strings and/or :class:`QualifiedName`
        instances containing the path elements without separators. There
        is no ambiguity as the path can neither start nor end in a
        separator."""
        result = []
        qname = self.parse_production(self.require_qualified_name)
        if qname:
            result.append(qname)
            self.require("/")
            result.append(self.require_odata_identifier())
        else:
            result.append(self.require_odata_identifier())
        while True:
            savepos = self.pos
            if self.parse("/"):
                if self.match('$'):
                    self.pos = savepos
                    break
                qname = self.parse_production(self.require_qualified_name)
                if qname:
                    result.append(qname)
                    savepos = self.pos
                    if self.parse("/"):
                        if self.match('$'):
                            self.pos = savepos
                            break
                        result.append(self.require_odata_identifier())
                    else:
                        break
                else:
                    result.append(self.require_odata_identifier())
            else:
                break
        return result

    # Line 256
    def require_expand_count_option(self, options):
        """Parses production expandCountOption"""
        if self.parse('$filter'):
            self.require(self.EQ)
            options.set_filter(self.require_filter())
        else:
            self.require('$search')
            self.require(self.EQ)
            options.set_search(self.require_search())

    # Line 258
    def require_expand_ref_option(self, options):
        """Parses production expandRefOption

        The option is updated in options."""
        if self.parse('$orderby'):
            self.require(self.EQ)
            options.set_orderby(self.require_orderby())
        elif self.parse('$skip'):
            self.require(self.EQ)
            options.set_skip(self.require_skip())
        elif self.parse('$top'):
            self.require(self.EQ)
            options.set_top(self.require_top())
        elif self.parse('$inlinecount'):
            self.require(self.EQ)
            options.set_inlinecount(self.require_inlinecount())
        else:
            self.require_expand_count_option(options)

    # Line 263
    def require_expand_option(self, options):
        """Parses production expandOption

        Returns a name, value pair."""
        if self.parse('$select'):
            self.require(self.EQ)
            options.add_select_item(self.require_select())
        elif self.parse('$expand'):
            self.require(self.EQ)
            options.add_expand_item(self.require_expand())
        elif self.parse('$levels'):
            self.require(self.EQ)
            options.set_levels(self.require_levels())
        else:
            return self.require_expand_ref_option(options)

    # Line 268
    def require_levels(self):
        """Parses production filter

        Does *not* parse the $levels= but parses just the value of the
        levels option returning an integer with 0 indicating 'max'."""
        if self.parse('max'):
            return 0
        else:
            result = self.parse_integer(min=1)
            if result is None:
                self.parser_error("non-zero digit in levels")
            return result

    # Line 270
    def require_filter(self):
        """Parses production filter

        Does *not* parse the $filter= but parses just the value of the
        filter option (a boolCommonExpr)."""
        return self.require_bool_common_expr()

    # Line 272
    def require_orderby(self):
        """Parses production orderby

        Does *not* parse the $orderby= but parses just the value of the
        orderby option (a list of orderbyItems)."""
        result = []
        result.append(self.require_orderby_item())
        while self.parse(self.COMMA):
            result.append(self.require_orderby_item())
        return result

    # Line 273
    def require_orderby_item(self):
        """Parses production orderbyItem"""
        expr = self.require_common_expr()
        direction = 1
        savepos = self.pos
        if self.parse_bws():
            if self.parse('desc'):
                direction = -1
            elif self.parse('asc'):
                direction = 1
            else:
                self.setpos(savepos)
        item = query.OrderbyItem(expr, direction)
        return item

    # Line 288
    def require_search(self):
        """Parses production search

        Does *not* parse the $search= but parses just the value of the
        search option returning a CommonExpression object representing
        the limited expression syntax of search expressions."""
        return self.require_search_expr()

    # Line 289
    def require_search_expr(self):
        """Parses production search_expr

        This is a cut-down version of the parser we use for common
        expressions."""
        # For more details on the implementationsee the code for common
        # expressions.
        left_op = None
        right_op = None
        op_stack = []
        while True:
            # step 1: find the next atom
            if self.match(self.DQUOTE):
                # unambiguous, must be string primitiveLiteral
                right_op = comex.PhraseExpression(self.require_search_phrase())
            elif self.parse(self.OPEN):
                self.parse_bws()
                right_op = self.require_search_expr()
                self.parse_bws()
                self.require(self.CLOSE)
            else:
                # we expect a name (or qname) but it could still
                # be a literal
                word = self.parse_production(self.require_search_word)
                if word:
                    right_op = comex.WordExpression(word)
                elif self.parse('NOT'):
                    right_op = comex.SUnaryExpression(comex.Operator.bool_not)
                    self.require_rws()
                else:
                    self.parser_error()
            # step 2: find the next operator
            if not isinstance(
                    right_op, comex.UnaryExpression) or right_op.operands:
                operand = right_op
                if self.parse_bws():
                    if self.parse('AND'):
                        op_code = comex.Operator.bool_and
                        right_op = comex.SBinaryExpression(op_code)
                        self.require_rws()
                    elif self.parse('OR'):
                        op_code = comex.Operator.bool_or
                        right_op = comex.SBinaryExpression(op_code)
                        self.require_rws()
                    else:
                        right_op = None
                else:
                    right_op = None
                if right_op is None:
                    while left_op is not None:
                        left_op.add_operand(operand)
                        operand = left_op
                        if op_stack:
                            left_op = op_stack.pop()
                        else:
                            left_op = None
                    return operand
            else:
                operand = None
            while True:
                if left_op is None or left_op < right_op:
                    if operand is not None:
                        right_op.add_operand(operand)
                    if left_op is not None:
                        op_stack.append(left_op)
                    left_op = right_op
                    right_op = None
                    operand = None
                    break
                else:
                    left_op.add_operand(operand)
                    operand = left_op
                    if op_stack:
                        left_op = op_stack.pop()
                    else:
                        left_op = None

    # Line 299
    def require_search_phrase(self):
        """Parses production searchPhrase

        Returns a string.

        The syntax is complex due to the desire to represent the percent
        encoded form.  It appears that any character is allowed except &
        and the double-quote.  The restriction on & is curious because
        query parameters must be split before decoding so an encoded &
        (%26) shouldn't cause a problem but we still raise a parser
        error if we encounter one.  The same cannot be said for %22
        (double-quote) which would be decoded to the closing
        double-quote and just be detected through the following
        unexpected content"""
        self.require(self.DQUOTE)
        phrase = []
        while True:
            if self.the_char is None or self.match(self.AMP):
                self.parser_error("search phrase")
            if self.parse(self.DQUOTE):
                break
            phrase.append(self.the_char)
            self.next_char()
        phrase = ''.join(phrase)
        if not len(phrase):
            self.parser_error("search phrase")
        return phrase

    # Line 300
    def require_search_word(self):
        """Parses production searchWord

        Returns a string.

        Syntax described as 1*ALPHA but with the qualification that it
        can contain "any character from the Unicode categories L or Nl,
        but not the words AND, OR, and NOT"."""
        word = []
        while _word_char.test(self.the_char):
            word.append(self.the_char)
            self.next_char()
        word = ''.join(word)
        if word in ('', 'AND', 'OR', 'NOT'):
            self.parser_error("search word")
        return word

    # Line 303
    def require_select(self):
        """Parse the value component of select

        We only parse::

            selectItem *( COMMA selectItem )

        Returns a list of path tuples."""
        items = []
        items.append(self.require_select_item())
        while self.parse(self.COMMA):
            items.append(self.require_select_item())
        return items

    # Line 304
    def require_select_item(self):
        """Parses production selectItem

        The syntax is complex and highly redundant but it does reduce
        to::

            selectItem = STAR
                / namespace "." STAR
                / [ qualifiedName "/" ] (
                    odataIdentifier [ "/" qualifiedName ]
                        *( "/" ( odataIdentifier [ "/" qualifiedName ] ) )
                    / qualifiedName )

        Which essentially means that you can only have two consecutive
        qualified names if they define the entire path.

        We return a path tuple consisting of items that are either
        strings or QualifiedName instances.  Note that unusual case that
        a path consisting of a single item may contain the name "*" or a
        QualifiedName in which the name component is "*"
        """
        path = []
        name = []
        while True:
            if self.parse(self.STAR):
                # end of this path, this must be the only item
                if path:
                    self.parser_error("identifier")
                if name:
                    name = names.QualfiedName('.'.join(name), self.STAR)
                else:
                    name = self.STAR
                return (name, )
            name.append(self.require_odata_identifier())
            if self.parse('.'):
                # this name continues
                continue
            # this name is done
            if len(name) > 1:
                name = names.QualifiedName(".".join(name[:-1]), name[-1])
            else:
                name = name[0]
            path.append(name)
            name = []
            if self.parse('/'):
                # this path continues
                continue
            else:
                break
        return tuple(path)

    # Line 384
    def require_common_expr(self):
        """Parses production commonExpr

        Returns a CommonExpression object."""
        expr = self._require_common_expr()
        # TODO: validate that this is a common expression!
        return expr

    # Line 402
    def require_bool_common_expr(self):
        """Parses production boolCommonExpr

        Returns a CommonExpression object."""
        expr = self._require_common_expr()
        if expr.is_bool_common():
            return expr
        else:
            self.parser_error("boolCommonExpr; found %r" % expr)

    BinaryOperators = {
        "eq": comex.EqExpression,
        "ne": comex.NeExpression,
        "lt": comex.LtExpression,
        "le": comex.LeExpression,
        "gt": comex.GtExpression,
        "ge": comex.GeExpression,
        "has": comex.HasExpression,
        "and": comex.AndExpression,
        "or": comex.OrExpression,
        "add": comex.AddExpression,
        "sub": comex.SubExpression,
        "mul": comex.MulExpression,
        "div": comex.DivExpression,
        "mod": comex.ModExpression}

    def _require_common_expr(self):
        """Parses a common expression

        We split our expression up into operators and atoms.  Operators
        take 0 or more sub-expressions as arguments whereas atoms are
        indivisible and can be evaluated directly given a suitable
        context."""
        left_op = None
        right_op = None
        op_stack = []
        while True:
            # step 1: find the next atom
            if self.match(self.SQUOTE):
                # unambiguous, must be string primitiveLiteral
                right_op = comex.StringExpression(self.require_string())
            elif self.match_digit():
                right_op = self.require_primitive_literal()
            elif self.parse(self.AT):
                # must be parameterAlias
                right_op = comex.ParameterExpression(
                    self.require_odata_identifier())
            elif self.match('['):
                # must be JSON array
                right_op = self.require_array_or_object()
            elif self.match("{"):
                # must be JSON object
                right_op = self.require_array_or_object()
            elif self.parse('$'):
                # a reserved name
                name = self.require_odata_identifier()
                if name == "it":
                    right_op = comex.ItExpression()
                elif name == "root":
                    right_op = comex.RootExpression()
                elif name == "count":
                    right_op = comex.CountExpression()
                else:
                    self.parser_error("it, root or count expression")
            elif self.match('+'):
                # unambiguous, must be a numeric literal
                # note: dates do not support a leading +
                right_op = self.require_primitive_literal()
            elif self.parse(self.OPEN):
                self.parse_bws()
                right_op = self._require_common_expr()
                self.parse_bws()
                self.require(self.CLOSE)
                right_op.bracket_hint = True
            elif self.match('-'):
                # getting harder, could be a negative literal.  We can't
                # just treat this as a unary negation operator because
                # we don't support general forms like -date and we might
                # trip over parsing a number that is too big for +ve int
                # but OK for -ve int.
                savepos = self.pos
                self.parse('-')
                if self.match_digit() or self.match('INF'):
                    # it must be a negative numeric literal
                    self.setpos(savepos)
                    right_op = self.require_primitive_literal()
                else:
                    # negateExpr
                    self.parse_bws()
                    right_op = comex.NegateExpression()
            else:
                # we expect a name (or qname) but it could still
                # be a literal
                savepos = self.pos
                try:
                    name = self.require_odata_identifier()
                    if self.match('.'):
                        qname = [name]
                        while self.parse('.'):
                            qname.append(self.require_odata_identifier())
                        qname = names.QualifiedName(
                            ".".join(qname[:-1]), qname[-1])
                    else:
                        qname = None
                    if self.match(self.SQUOTE):
                        # name followed by quote is duration, binary, geo...
                        # qname followed by quote is enum
                        self.setpos(savepos)
                        right_op = self.require_primitive_literal()
                    elif self.match('-') and len(name) == 8 and qname is None:
                        # a guid that starts off looking like a name
                        self.setpos(savepos)
                        right_op = self.require_primitive_literal()
                    elif self.match(self.OPEN):
                        # this is a call or key predicate, we actually
                        # treat it like an operator but as the syntax is
                        # unique and it binds more tightly than any
                        # other we deal with it directly here
                        if qname:
                            callable = comex.QNameExpression(qname)
                        else:
                            callable = comex.IdentifierExpression(name)
                        while self.parse(self.OPEN):
                            right_op = comex.CallExpression()
                            arguments = comex.ArgsExpression()
                            right_op.add_operand(callable)
                            right_op.add_operand(arguments)
                            comma = False
                            self.parse_bws()
                            while not self.parse(self.CLOSE):
                                if comma:
                                    self.require(self.COMMA)
                                    self.parse_bws()
                                else:
                                    comma = True
                                arguments.add_operand(
                                    self._require_common_expr())
                                self.parse_bws()
                            # yes, you can call the result of a callable
                            # directly, e.g.:
                            # schema.Top10Products(region=1)(4)
                            # might return the Product with key 4 only
                            # if it is in the Top10 products for region
                            # 1.  The second call is a key-predicate
                            # of course.
                            callable = right_op
                    elif qname is None and name == "not" and self.parse_bws():
                        # always the not operator
                        right_op = comex.NotExpression()
                    elif qname:
                        right_op = comex.QNameExpression(qname)
                    else:
                        right_op = comex.IdentifierExpression(name)
                except ValueError:
                    if isinstance(left_op, comex.NotExpression):
                        # special case: expression ending in 'not '
                        # we assume that not was supposed to be
                        # an identifier, discard left_op!
                        right_op = comex.IdentifierExpression("not")
                        if op_stack:
                            left_op = op_stack.pop()
                        else:
                            left_op = None
                    else:
                        self.parser_error()
            # step 2: find the next operator
            # if we have an *unbound* unary operator, skip the search
            # for a binary operator
            if not isinstance(
                    right_op, comex.UnaryExpression) or right_op.operands:
                operand = right_op
                # start with operators that do not accept spaces
                if self.parse('/'):
                    right_op = comex.MemberExpression()
                elif self.parse('='):
                    # yes, we have an assignment operator for binding
                    # expressions to names (in calls)
                    right_op = comex.BindExpression()
                elif self.parse(':'):
                    self.parse_bws()
                    right_op = comex.LambdaBindExpression()
                else:
                    savepos = self.pos
                    if self.parse_bws():
                        if self.parse(':'):
                            self.parse_bws()
                            right_op = comex.LambdaBindExpression()
                        else:
                            try:
                                name = self.require_odata_identifier()
                                self.require_rws()
                                cls = self.BinaryOperators.get(name, None)
                                if cls is not None:
                                    right_op = cls()
                                else:
                                    raise ValueError
                            except ValueError:
                                self.setpos(savepos)
                                right_op = None
                    else:
                        right_op = None
                if right_op is None:
                    # end of the expression, rotate to the left to bind
                    # the current operand and keep rotating until we're
                    # done
                    while left_op is not None:
                        left_op.add_operand(operand)
                        operand = left_op
                        if op_stack:
                            left_op = op_stack.pop()
                        else:
                            left_op = None
                    return operand
            else:
                operand = None
            # we now have:
            # left_op (may be None)
            # operand (None only if right_op is an unbound unary)
            # right_op (an operator expression, never None)
            # next job, determine who binds more tightly, left or right?
            while True:
                if left_op is None or left_op < right_op or operand is None:
                    # Example: + 3 *
                    # bind the operand to the right, this causes a
                    # rotation to the left that pushes the current
                    # left_op (if any) onto the stack.
                    # Special case: not (None) not
                    # two unary operators must always bind to the right!
                    if operand is not None:
                        right_op.add_operand(operand)
                    if left_op is not None:
                        op_stack.append(left_op)
                    left_op = right_op
                    right_op = None
                    operand = None
                    break
                else:
                    # Example: 2 * 3 +
                    # bind the operand to the left, this causes a
                    # rotation to the right with the operand being bound
                    # to the left_op and then the left_op being replaced
                    # by the item on top of the stack (if any).  We
                    # repeat the binding until we can rotate the other
                    # way, we're binding a binary operator here so there
                    # must always be something more to the right.
                    # Example: 2 + 3 -
                    # in cases of equal precedence we left associate
                    # 2 + 3 - 4 = (2 + 3) - 4
                    left_op.add_operand(operand)
                    operand = left_op
                    if op_stack:
                        left_op = op_stack.pop()
                    else:
                        left_op = None

    # Line 417
    def require_root_expr(self):
        """Parses production rootExpr

        Returns a CommonExpression instance for which
        :meth:`comex.CommonExpression.is_root` returns True."""
        expr = self._require_common_expr()
        if not expr.is_root():
            self.parser_error("rootExpr, found %r" % expr)
        return expr

    # Line 419
    def require_first_member_expr(self):
        """Parses production firstMemberExpr

        Returns a CommonExpression instance for which
        :meth:`comex.CommonExpression.is_first_member` returns
        True."""
        expr = self._require_common_expr()
        if not expr.is_first_member():
            self.parser_error("firstMemberExpr, found %r" % expr)
        return expr

    # Line 422
    def require_member_expr(self):
        """Parses production memberExpr

        Returns a CommonExpression instance for which
        :meth:`comex.CommonExpression.is_member` returns
        True."""
        expr = self._require_common_expr()
        if not expr.is_member():
            self.parser_error("memberExpr, found %r" % expr)
        return expr

    # Line 427
    def require_property_path_expr(self):
        """Parses production propertyPathExpr

        Returns a CommonExpression instance for which
        :meth:`comex.CommonExpression.is_property_path` returns
        True."""
        expr = self._require_common_expr()
        if not expr.is_property_path():
            self.parser_error("propertyPathExpr, found %r" % expr)
        return expr

    # Line 436
    def require_inscope_variable_expr(self):
        """Parses production inscopeVariableExpr

        Returns either an :class:`comex.ItExpression` or an
        :class:`comex.IdentifierExpression` instance."""
        if self.match('$'):
            self.require(self.implicit_variable_expr)
            return comex.ItExpression()
        else:
            identifier = self.require_odata_identifier()
            return comex.IdentifierExpression(identifier)

    # Line 438
    implicit_variable_expr = "$it"

    # Line 439
    def require_lambda_variable_expr(self):
        identifier = self.require_odata_identifier()
        return comex.IdentifierExpression(identifier)

    # Line 446
    def require_single_navigation_expr(self):
        """Parses production singleNavigationExpr

        Returns a CommonExpression instance for which
        :meth:`comex.CommonExpression.is_member` returns True.  Note
        that the leading "/" operator required by the syntax is assumed
        to have been parsed already!"""
        return self.require_member_expr()

    # Line 448
    def require_collection_path_expr(self):
        """Parses production collectionPathExpr

        Returns a CommonExpression instance for which the
        :meth:`comex.CommonExpression.is_collection_path` returns True.
        Note that the leading "/" operator required by the syntax is
        assumed to have been parsed already."""
        expr = self._require_common_expr()
        if not expr.is_collection_path():
            self.parser_error("collectionPathExpr, found %r" % expr)
        return expr

    # Line 453
    def require_complex_path_expr(self):
        """Parses production complexPathExpr

        See :meth:`require_member_expr` as the syntax is identical
        except for the leading "/" operator which is assumed to have
        been parsed already by this method."""
        return self.require_member_expr()

    # Line 458
    def require_single_path_expr(self):
        """Parses production singlePathExpr

        See :meth:`require_function_expr`.  Note that the leading "/"
        operator required by the syntax is assumed to have been parsed
        already."""
        return self.require_function_expr()

    # Line 460
    def require_bound_function_expr(self):
        """Parses production boundFunctionExpr

        See :meth:`require_function_expr`."""
        return self.require_function_expr()

    # Line 463
    def require_function_expr(self):
        """Parses production singlePathExpr

        Returns a CommonExpression instance for which
        :meth:`comex.CommonExpression.is_function` returns True."""
        expr = self._require_common_expr()
        if not expr.is_function():
            self.parser_error("functionExpr, found %r" % expr)
        return expr

    # Line 472
    # functionExprParameters parsed only as part of functionExpr

    # Line 473
    # functionExprParameter parsed only as part of functionExpr

    # Line 475
    def require_any_expr(self):
        """Parses production anyExpr

        Returns a CallExpression instance with an IdentifierExpression
        with identifier 'any' and with arguments that return True for
        :meth:`comex.ArgsExpression.is_any`."""
        expr = self._require_common_expr()
        if isinstance(expr, comex.CallExpression) and len(expr.operands) == 2:
            if (isinstance(expr.operands[0], comex.IdentifierExpression) and
                    expr.operands[0].identifier == "any" and
                    isinstance(expr.operands[1], comex.ArgsExpression) and
                    expr.operands[1].is_any()):
                return expr
        self.parser_error("anyExpr, found %r" % expr)

    # Line 476
    def require_all_expr(self):
        """Parses production allExpr

        Returns a CallExpression instance with an IdentifierExpression
        with identifier 'all' and with arguments that return True for
        :meth:`comex.ArgsExpression.is_all()`."""
        expr = self._require_common_expr()
        if isinstance(expr, comex.CallExpression) and len(expr.operands) == 2:
            if (isinstance(expr.operands[0], comex.IdentifierExpression) and
                    expr.operands[0].identifier == "all" and
                    isinstance(expr.operands[1], comex.ArgsExpression) and
                    expr.operands[1].is_all()):
                return expr
        self.parser_error("allExpr, found %r" % expr)

    # Line 477
    def require_lambda_predicate_expr(self):
        """Parses production lambdaPredicateExpr

        See :meth:`require_bool_common_expr` as the syntax is identical."""
        return self.require_bool_common_expr()

    # Line 479
    def require_method_call_expr(self):
        """Parses production methodCallExpr

        Returns a CallExpression instance with a method attribute that
        is not None and with arguments that return True for
        :meth:`comex.ArgsExpression.is_method_parameters()`.  The
        number and type of arguments is only checked during
        evaluation."""
        expr = self._require_common_expr()
        if isinstance(expr, comex.CallExpression) and len(expr.operands) == 2:
            if (expr.method is not None and
                    isinstance(expr.operands[1], comex.ArgsExpression) and
                    expr.operands[1].is_method_parameters()):
                return expr
        self.parser_error("methodCallExpr, found %r" % expr)

    # Line 582
    def require_array_or_object(self):
        """Parses production arrayOrObject

        Returns either a :class:`comex.CollectionExpression` indicating
        an array or a :class:`comex.RecordExpression` indicating an
        object."""
        self.parse_bws()
        if self.parse("["):
            self.parse_bws()
            e = comex.CollectionExpression()
            self.parse_bws()
            item_prod = None
            while not self.parse("]"):
                if not item_prod:
                    if self.match("{"):
                        item_prod = "complexInUri"
                        item = self.require_complex_in_uri()
                    elif self.match("$"):
                        # rootExpr
                        item_prod = "rootExpr"
                        item = self.require_root_expr()
                    else:
                        item_prod = "primitiveLiteralInJSON"
                        item = self.require_primitive_literal_in_json()
                else:
                    self.require(self.value_separator)
                    self.parse_bws()
                    if item_prod == "complexInUri":
                        item = self.require_complex_in_uri()
                    elif item_prod == "rootExpr":
                        item = self.require_root_expr()
                    else:
                        item = self.require_primitive_literal_in_json()
                self.parse_bws()
                e.add_operand(item)
            return e
        elif self.match("{"):
            return self.require_complex_in_uri()
        else:
            self.parser_error("arrayOrObject")

    # Line 591
    def require_complex_in_uri(self):
        self.parse_bws()
        self.require("{")
        self.parse_bws()
        e = comex.RecordExpression()
        while not self.parse("}"):
            if e.operands:
                self.require(self.value_separator)
                self.parse_bws()
            name = self.require_string_in_json()
            self.parse_bws()
            self.require(":")
            self.parse_bws()
            if name.startswith('@'):
                # This is a term reference, not a simple property name
                name = comex.TermRefExpression(names.TermRef.from_str(name))
                if self.match_one("{["):
                    item = self.require_array_or_object()
                    if (isinstance(item, comex.CollectionExpression) and
                            len(item.operands) and item.operands[0].is_root()):
                        # you can't have a rootExpr in an annotation
                        self.parser_error("annotationInUri")
                else:
                    item = self.require_primitive_literal_in_json()
            else:
                name = comex.IdentifierExpression(
                    names.simple_identifier_from_str(name))
                # arrayOrObject / rootExpr / primitiveLiteralInJSON
                if self.match_one("{["):
                    item = self.require_array_or_object()
                elif self.match("$"):
                    item = self.require_root_expr()
                else:
                    item = self.require_primitive_literal_in_json()
            binding = comex.MemberBindExpression()
            binding.add_operand(name)
            binding.add_operand(item)
            e.add_operand(binding)
            self.parse_bws()
        return e

    # Line 648
    begin_object = "{"

    # Line 649
    end_object = "}"

    # Line 651
    begin_array = "["

    # Line 652
    end_array = "]"

    # Line 654
    quotation_mark = '"'

    # Line 655
    name_separator = ":"

    # Line 656
    value_separator = ","

    # Line 658
    def require_primitive_literal_in_json(self):
        if self.match(self.quotation_mark):
            return comex.StringExpression(self.require_string_in_json())
        elif self.match_digit() or self.match('-'):
            return self.require_number_in_json()
        elif self.match('t'):
            self.require('true')
            return comex.BooleanExpression(True)
        elif self.match('f'):
            self.require('false')
            return comex.BooleanExpression(False)
        elif self.match('n'):
            self.require('null')
            return comex.NullExpression()
        else:
            self.parser_error("primitiveLiteralInJSON")

    # Line 664
    def require_string_in_json(self):
        result = []
        self.require(self.quotation_mark)
        while True:
            if self.parse(self.quotation_mark):
                break
            elif self.the_char is not None:
                result.append(self.require_char_in_json())
            else:
                self.parser_error("quotation-mark")
        return uempty.join(result)

    # Line 665
    def require_char_in_json(self):
        if self.parse(self.escape):
            c = self.parse_one('"\\/bfnrt')
            if c:
                return {'"': '"',
                        '\\': '\\',
                        '/': '/',
                        'b': ul('\x08'),
                        'f': ul('\x0c'),
                        'n': ul('\x0a'),
                        'r': ul('\x0d'),
                        't': ul('\x09')
                        }[c]
            if self.parse('u'):
                h = self.parse_hex_digits(4, 4)
                if h is None:
                    self.parser_error("4HEXDIG")
                return character(int(h, 16))
            else:
                self.parser_error("escaped charInJSON")
        elif self.the_char is not None:
            c = self.the_char
            self.next_char()
            return c
        else:
            self.parser_error("charInJSON")

    # Line 680
    escape = "\\"

    # Line 682
    def require_number_in_json(self):
        sign = self.parse('-')
        if sign is None:
            sign = ''
        istr = self.require_production(self.parse_digits(1), "int")
        if self.parse("."):
            fracstr = "." + self.require_production(
                self.parse_digits(1), "frac")
        else:
            fracstr = ""
        if self.parse_one("eE"):
            esign = self.parse_one('-+')
            if esign is None:
                esign = ''
            estr = "e" + esign + self.require_production(
                self.parse_digits(1), "exp")
        else:
            estr = ''
        value = decimal.Decimal(sign + istr + fracstr + estr)
        if estr:
            return comex.DoubleExpression(value)
        elif fracstr:
            return comex.DecimalExpression(value)
        else:
            return comex.Int64Expression(int(value))

    # Line 701-704
    def require_qualified_name(self):
        """Parses productions of the form qualified<type>Name

        Returns a named tuple of (namespace, name).

        Although split out in the ABNF these definitions are all
        equivalent and can't be differentiated in the syntax without
        reference to a specific model."""
        result = []
        result.append(self.require_odata_identifier())
        self.require(".")
        result.append(self.require_odata_identifier())
        while self.parse("."):
            result.append(self.require_odata_identifier())
        return names.QualifiedName(".".join(result[:-1]), result[-1])

    # Line 707
    def require_namespace(self):
        """Parses procution namespace

        Returns a string representing the namespace.  This method is
        greedy, it will parse as many identifiers as it can."""
        result = []
        result.append(self.require_odata_identifier())
        while self.parse("."):
            result.append(self.require_odata_identifier())
        return ".".join(result)

    # Line 720
    def require_odata_identifier(self):
        result = []
        if not _oid_start_char.test(self.the_char):
            self.parser_error("simple identifier")
        result.append(self.the_char)
        self.next_char()
        while _oid_char.test(self.the_char):
            result.append(self.the_char)
            self.next_char()
        if len(result) > 128:
            self.parser_error("simple identifier; 128 chars or fewer")
        return ''.join(result)

    # Line 795
    def require_primitive_literal(self):
        """Parses production primitiveLiteral

        Returns a sub-class of :class:`comex.LiteralExpression` that
        evaluates to a :class:`PrimitiveValue`."""
        save_pos = self.pos
        if self.match_one('-1234567890'):
            # try and parse an integer
            try:
                value = self.require_int64_value()
            except ParserError:
                # must be -INF
                value = self.require_double_value()
                return comex.DoubleExpression(value)
            if self.match("."):
                # must be decimal or float
                self.setpos(save_pos)
                value = self.require_decimal_value()
                if self.match_one("eE"):
                    # must be float
                    self.setpos(save_pos)
                    value = self.require_double_value()
                    # return an expression that preserves the literal
                    return comex.DoubleExpression(
                        decimal.Decimal(self.src[save_pos:self.pos]))
                else:
                    return comex.DecimalExpression(value)
            elif self.match("-"):
                # could be guid, date, dateTimeOffset
                self.setpos(save_pos)
                value = self.parse_production(self.require_date_value)
                if value:
                    if self.match_one("Tt"):
                        self.setpos(save_pos)
                        value = self.require_date_time_offset_value()
                        return comex.DateTimeOffsetExpression(
                            value, self.src[save_pos:self.pos])
                    else:
                        return comex.DateExpression(value)
                else:
                    # guide that looks like a number...
                    return comex.GuidExpression(self.require_guid_value())
            elif self.match(":"):
                # must be time of day
                self.setpos(save_pos)
                value = self.require_time_of_day_value()
                return comex.TimeOfDayExpression(
                    value, self.src[save_pos:self.pos])
            elif self.match_one("Ee"):
                # might be a guid
                value = self.parse_production(self.require_guid_value)
                if value is None:
                    # could be integer + exponent
                    self.setpos(save_pos)
                    value = self.require_double_value()
                    # return an expression that preserves the literal
                    return comex.DoubleExpression(
                        decimal.Decimal(self.src[save_pos:self.pos]))
                else:
                    return comex.GuidExpression(value)
            elif self.match_one("ABCDEFabcdef"):
                # must be a guid
                self.setpos(save_pos)
                return comex.GuidExpression(self.require_guid_value())
            else:
                # must have been an integer all along
                return comex.Int64Expression(value)
        elif self.match("+"):
            # must be numeric
            value = self.require_int64_value()
            if self.match_one(".eE"):
                # must be decimal or float
                self.setpos(save_pos)
                value = self.require_decimal_value()
                if self.match_one("eE"):
                    # must be float
                    self.setpos(save_pos)
                    value = self.require_double_value()
                    # return an expression that preserves the literal
                    return comex.DoubleExpression(
                        decimal.Decimal(self.src[save_pos:self.pos]))
            else:
                return comex.Int64Expression(value)
        elif self.match("'"):
            # a string
            return comex.StringExpression(self.require_string())
        else:
            value = self.require_odata_identifier()
            if self.match_one("."):
                # a qualified name (enum)
                self.setpos(save_pos)
                qname = self.require_qualified_name()
                self.require("'")
                enum_value = self.require_enum_value()
                self.require("'")
                return comex.EnumExpression(
                    names.EnumLiteral(qname, tuple(enum_value)))
            elif self.match_one("-"):
                # must be a guid again (8HEXDIGIT could look like a name)
                self.setpos(save_pos)
                return comex.GuidExpression(self.require_guid_value())
            elif self.match_one("'"):
                # must be a selector
                value = value.lower()
                self.next_char()
                save_pos = self.pos
                if value == "duration":
                    value = self.require_duration_value()
                    value = comex.DurationExpression(
                            value, self.src[save_pos:self.pos])
                elif value == "binary":
                    value = comex.BinaryDataExpression(
                        self.require_binary_value())
                elif value == "geography" or value == "geometry":
                    srid = self.require_srid_literal()
                    if self.match_insensitive("c"):
                        lv = self.require_collection_literal()
                        v = geo.CollectionLiteral(srid, lv)
                    elif self.match_insensitive("l"):
                        lv = self.require_line_string_literal()
                        v = geo.LineStringLiteral(srid, lv)
                    elif self.match_insensitive("poi"):
                        lv = self.require_point_literal()
                        v = geo.PointLiteral(srid, lv)
                    elif self.match_insensitive("pol"):
                        lv = self.require_polygon_literal()
                        v = geo.PolygonLiteral(srid, lv)
                    elif self.match_insensitive("multil"):
                        lv = self.require_multi_line_string_literal()
                        v = geo.MultiLineStringLiteral(srid, lv)
                    elif self.match_insensitive("multipoi"):
                        lv = self.require_multi_point_literal()
                        v = geo.MultiPointLiteral(srid, lv)
                    elif self.match_insensitive("multipol"):
                        lv = self.require_multi_polygon_literal()
                        v = geo.MultiPolygonLiteral(srid, lv)
                    else:
                        # unknown geo type
                        self.parser_error("geo literal")
                    if value == "geography":
                        value = comex.GeographyExpression(
                            v, self.src[save_pos:self.pos])
                    else:
                        value = comex.GeometryExpression(
                            v, self.src[save_pos:self.pos])
                else:
                    # unknown selector
                    self.parser_error("primitive literal")
                self.require("'")
                return value
            elif value == "null":
                return comex.NullExpression()
            elif value == 'NaN':
                return comex.DoubleExpression(float('nan'))
            elif value == 'INF':
                return comex.DoubleExpression(float('inf'))
            elif value.lower() == 'true':
                return comex.BooleanExpression(True)
            elif value.lower() == 'false':
                return comex.BooleanExpression(False)
            else:
                # just some random word that we don't understand
                self.parser_error("primitive literal")

    # Line 829
    def require_primitive_value(self):
        """Parses production: primitiveValue"""
        raise NotImplementedError

    # Line 856
    #: Matches production: nullValue
    null_value = 'null'

    # Line 859
    def require_binary(self):
        """Parses production: binary

        Returns a :class:`BinaryValue` instance or raises a parser
        error."""
        # binary = "binary" SQUOTE binaryValue SQUOTE
        self.require_production(self.parse_insensitive("binary"), "binary")
        self.require("'")
        v = self.require_binary_value()
        self.require("'")
        return v

    # Line 860
    def require_binary_value(self):
        """Parses production: binaryValue

        Returns a bytes instance or raises a parser error."""
        result = bytearray()
        while self.base64_char.test(self.the_char):
            result.append(byte(self.the_char))
            self.next_char()
        # in OData, the trailing "=" are optional but if given they must
        # result in the correct length string.
        pad = len(result) % 4
        if pad == 3:
            self.parse('=')
            result.append(byte('='))
        elif pad == 2:
            self.parse('==')
            result.append(byte('='))
            result.append(byte('='))
        return base64.urlsafe_b64decode(bytes(result))

    # Line 863
    #: a character class representing production base64char
    base64_char = CharClass(('A', 'Z'), ('a', 'z'), ('0', '9'), '-', '_')

    # Line 865
    def require_boolean_value(self):
        """Parses production: booleanValue

        Returns a :class:`BooleanValue` instance or raises a parser
        error."""
        if self.parse_insensitive("true"):
            return True
        elif self.parse_insensitive("false"):
            return False
        else:
            self.parser_error("booleanValue")

    # Line 867
    def require_decimal_value(self):
        """Parses production: decimalValue

        Returns a :class:`DecimalValue` instance or raises a parser
        error."""
        sign = self.parse_sign()
        ldigits = self.require_production(self.parse_digits(1),
                                          "decimal digits")
        if self.parse('.'):
            rdigits = self.require_production(self.parse_digits(1),
                                              "decimal fraction")
            return decimal.Decimal(sign + ldigits + '.' + rdigits)
        else:
            return decimal.Decimal(sign + ldigits)

    # Line 869
    def require_double_value(self):
        """Parses production: doubleValue

        Returns a :class:`DoubleValue` instance or raises a parser
        error."""
        sign = self.parse_one('+-')
        if not sign:
            if self.parse('INF'):
                return float('inf')
            elif self.parse('NaN'):
                return float('nan')
            sign = ''
        elif sign == '-' and self.parse('INF'):
            return float('-inf')
        ldigits = self.require_production(self.parse_digits(1),
                                          "decimal digits")
        if self.parse('.'):
            rdigits = self.require_production(self.parse_digits(1),
                                              "decimal fraction")
            dec = sign + ldigits + '.' + rdigits
        else:
            dec = sign + ldigits
        if self.parse_insensitive('e'):
            sign = self.parse_one('+-')
            if not sign:
                sign = ''
            edigits = self.require_production(self.parse_digits(1), "exponent")
            exp = 'E' + sign + edigits
        else:
            exp = ''
        return float(dec + exp)

    # Line 870
    def require_single_value(self):
        """Parses production: singleValue

        Returns a :class:`SingleValue` instance or raises a parser
        error."""
        return self.require_double_value()

    # Line 873
    def require_guid_value(self):
        """Parses production: guidValue

        Returns a UUID instance or raises a parser error."""
        hex_parts = []
        part = self.parse_hex_digits(8, 8)
        if not part:
            self.parser_error("8HEXDIG")
        hex_parts.append(part)
        for i in range3(3):
            self.require('-')
            part = self.parse_hex_digits(4, 4)
            if not part:
                self.parser_error("4HEXDIG")
            hex_parts.append(part)
        self.require('-')
        part = self.parse_hex_digits(12, 12)
        if not part:
            self.parser_error("12HEXDIG")
        hex_parts.append(part)
        return uuid.UUID(hex=''.join(hex_parts))

    # Line 875
    def require_byte_value(self):
        """Parses production: byteValue

        Returns a :class:`ByteValue` instance of raises a parser
        error."""
        #   1*3DIGIT
        digits = self.require_production(self.parse_digits(1, 3), "byteValue")
        try:
            result = int(digits)
            if result < 0 or result > 255:
                raise ValueError
            return result
        except ValueError:
            self.parser_error('byte in range [0, 255]')

    # Line 876
    def require_sbyte_value(self):
        """Parses production: sbyteValue

        Returns an integer or raises a parser error."""
        sign = self.parse_sign()
        digits = self.require_production(self.parse_digits(1, 3), "sbyteValue")
        try:
            result = int(sign + digits)
            if result < -128 or result > 127:
                raise ValueError
            return result
        except ValueError:
            self.parser_error('sbyte in range [-128, 127]')

    # Line 877
    def require_int16_value(self):
        """Parses production: int16Value

        Returns a :class:`Int16Value` instance of raises a parser
        error."""
        sign = self.parse_sign()
        digits = self.require_production(self.parse_digits(1, 5), "int16Value")
        try:
            result = int(sign + digits)
            if result < -32768 or result > 32767:
                raise ValueError
            return result
        except ValueError:
            self.parser_error('int16 in range [-32768, 32767]')

    # Line 878
    def require_int32_value(self):
        """Parses production: int32Value

        Returns a :class:`Int32Value` instance of raises a parser
        error."""
        sign = self.parse_sign()
        digits = self.require_production(
            self.parse_digits(1, 10), "int32Value")
        try:
            result = int(sign + digits)
            if result < -2147483648 or result > 2147483647:
                raise ValueError
            return result
        except ValueError:
            self.parser_error('int32 in range [-2147483648, 2147483647]')

    # Line 879
    def require_int64_value(self):
        """Parses production: int64Value

        Returns a :class:`Int64Value` instance or raises a parser
        error."""
        sign = self.parse_sign()
        digits = self.require_production(self.parse_digits(1, 19),
                                         "int64Value")
        try:
            result = int(sign + digits)
            if result < -9223372036854775808 or result > 9223372036854775807:
                raise ValueError
            return result
        except ValueError:
            self.parser_error(
                'int64 in range [-9223372036854775808, 9223372036854775807]')

    # Line 881
    def require_string(self):
        """Parses production: string

        Returns a *character* string or raises a parser error. Note that
        this is the literal quoted form of the string for use in URLs,
        string values in XML and JSON payloads are represented using
        native representations.  It is assumed that the input *has
        already* been decoded from the URL and is represented as a
        character string (it may also contain non-ASCII characters
        interpreted from the URL in an appropriate way), i.e., the only
        escaping we use is the quote-doubling rule for escaping the
        single quote character."""
        result = []
        self.require("'")
        while True:
            if self.parse("'"):
                if self.parse("'"):
                    # an escaped single quote
                    result.append("'")
                else:
                    break
            elif self.the_char is not None:
                result.append(self.the_char)
                self.next_char()
            else:
                self.parser_error("SQUOTE")
        return uempty.join(result)

    # Line 884
    def require_date_value(self):
        """Parses the production: dateValue

        Returns a :class:`DateValue` instance or raises a parser
        error."""
        year = self.require_year()
        self.require('-')
        month = self.require_month()
        self.require('-')
        day = self.require_day()
        bce, c, y = iso.Date.split_year(year)
        try:
            result = iso.Date(bce=bce, century=c, year=y, month=month,
                              day=day, xdigits=-1)
            return result
        except iso.DateTimeError:
            self.parser_error("valid dateValue")

    # Line 886
    def require_date_time_offset_value(self):
        """Parses production: dateTimeOffsetValue

        Returns a :class:`DateTimeOffsetValue` instance or raises a
        parser error."""
        year = self.require_year()
        self.require('-')
        month = self.require_month()
        self.require('-')
        day = self.require_day()
        bce, c, y = iso.Date.split_year(year)
        self.require('T')
        hour = self.require_hour()
        self.require(':')
        minute = self.require_minute()
        if self.parse(':'):
            second = self.require_second()
            if self.parse('.'):
                fraction = self.require_production(self.parse_digits(1, 12))
                second = float(second) + float('0.' + fraction)
            else:
                second = int(second)
        else:
            second = 0
        if self.parse('Z'):
            zdirection = zhour = zminute = 0
        else:
            if self.parse('+'):
                zdirection = 1
            else:
                self.require('-')
                zdirection = -1
            zhour = self.require_hour()
            self.require(':')
            zminute = self.require_minute()
        try:
            result = iso.TimePoint(
                date=iso.Date(bce=bce, century=c, year=y, month=month, day=day,
                              xdigits=-1),
                time=iso.Time(hour=hour, minute=minute, second=second,
                              zdirection=zdirection, zhour=zhour,
                              zminute=zminute))
            return result
        except iso.DateTimeError:
            self.parser_error("valid dateTimeOffsetValue")

    # Line 889
    def require_duration_value(self):
        """Parses production: durationValue

        Returns a :class:`DurationValue` instance or raises a parser
        error."""
        sign = self.parse_sign_int()
        self.require("P")
        digits = self.parse_digits(1)
        if digits:
            self.require("D")
            days = int(digits)
        else:
            days = 0
        hours = minutes = seconds = 0
        if self.parse("T"):
            # time fields
            digits = self.parse_digits(1)
            if digits and self.parse("H"):
                hours = int(digits)
                digits = None
            if not digits:
                digits = self.parse_digits(1)
            if digits and self.parse('M'):
                minutes = int(digits)
                digits = None
            if not digits:
                digits = self.parse_digits(1)
            if digits:
                if self.parse('.'):
                    rdigits = self.require_production(
                        self.parse_digits(1), "fractional seconds")
                    self.require("S")
                    seconds = float(digits + "." + rdigits)
                elif self.parse("S"):
                    seconds = int(digits)
        d = xsi.Duration()
        d.sign = sign
        d.days = days
        d.hours = hours
        d.minutes = minutes
        d.seconds = seconds
        return d

    # Line 893
    def require_time_of_day_value(self):
        """Parses production: timeOfDayValue

        Returns a :class:`pyselt.iso8601.Time` instance or raises a
        parser error."""
        hour = self.require_hour()
        self.require(':')
        minute = self.require_minute()
        if self.parse(':'):
            second = self.require_second()
            if self.parse('.'):
                fraction = self.require_production(self.parse_digits(1, 12))
                second = float(second) + float('0.' + fraction)
            else:
                second = int(second)
        else:
            second = 0
        try:
            return iso.Time(hour=hour, minute=minute, second=second)
        except iso.DateTimeError:
            self.parser_error("valid timeOfDayValue")

    # Line 896
    def require_zero_to_fifty_nine(self, production):
        """Parses production: zeroToFiftyNine

        Returns an integer in the range 0..59 or raises a parser
        error."""
        digits = self.require_production(self.parse_digits(2, 2), production)
        i = int(digits)
        if i > 59:
            self.parser_error("%s in range [0..59]" % production)
        return i

    # Line 897
    def require_year(self):
        """Parses production: year

        Returns an integer representing the parsed year or raises a
        parser error."""
        if self.parse('-'):
            sign = -1
        else:
            sign = 1
        if self.parse('0'):
            digits = self.parse_digits(3, 3)
        else:
            digits = self.parse_digits(4)
        if not digits:
            self.parser_error("year")
        return sign * int(digits)

    # Line 898
    def require_month(self):
        """Parses production: month

        Returns an integer representing the month or raises a parser
        error."""
        if self.parse('0'):
            digits = self.parse_digit()
        elif self.parse('1'):
            digits = '1' + self.require_production(
                self.parse_one("012"), "month")
        else:
            digits = None
        if not digits:
            self.parser_error("month")
        return int(digits)

    # Line 900
    def require_day(self):
        """Parses production: day

        Returns an integer representing the day or raises a parser
        error."""
        if self.parse("0"):
            digits = self.parse_digit()
        else:
            d = self.parse_one("12")
            if d:
                digits = d + self.require_production(
                    self.parse_digit(), "day")
            elif self.parse("3"):
                digits = '3' + self.require_production(
                    self.parse_one("01"), "day")
            else:
                digits = None
        if not digits:
            self.parser_error("day")
        return int(digits)

    # Line 903
    def require_hour(self):
        """Parses production: hour

        Returns an integer representing the hour or raises a parser
        error."""
        digits = self.require_production(self.parse_digits(2, 2), "hour")
        hour = int(digits)
        if hour > 23:
            self.parser_error("hour in range [0..23]")
        return hour

    # Line 905
    def require_minute(self):
        """Parses production: minute

        Returns an integer representation of the minute or raises a
        parser error."""
        return self.require_zero_to_fifty_nine("minute")

    # Line 906
    def require_second(self):
        """Parses production: second

        Returns an integer representation of the second or raises a
        parser error."""
        return self.require_zero_to_fifty_nine("second")

    # Line 910
    def require_enum_value(self):
        """Parses production: enumValue

        Returns a non-empty *list* of strings and/or integers or raises
        a parser error."""
        result = []
        result.append(self.require_single_enum_value())
        while self.parse(","):
            # no need to use look ahead
            result.append(self.require_single_enum_value())
        return result

    # Line 911
    def require_single_enum_value(self):
        """Parses production: singleEnumValue

        Reuturns either a simple identifier string, an integer or raises
        a parser error."""
        name = self.parse_production(self.require_odata_identifier)
        if name:
            return name
        else:
            return self.require_int64_value()

    # Line 915
    def require_full_collection_literal(self):
        """Parses production: fullCollectionLiteral

        Returns a :class:`geotypes.GeoCollectionLiteral` instance, a
        named tuple consisting of 'srid' and 'items' members."""
        srid = self.require_srid_literal()
        items = self.require_collection_literal()
        return geo.GeoCollectionLiteral(srid, items)

    # Line 916
    def require_collection_literal(self):
        """Parses production: collectionLiteral

        Returns a :class:`geotypes.GeoCollection` instance."""
        self.require_production(
            self.parse_insensitive("collection("), "collectionLiteral")
        items = [self.require_geo_literal()]
        while self.parse(self.COMMA):
            items.append(self.require_geo_literal())
        self.require(self.CLOSE)
        return geo.GeoCollection(items)

    # Line 917
    def require_geo_literal(self):
        """Parses production: geoLiteral

        Returns a :class:`geotypes.GeoItem` instance."""
        item = self.parse_production(self.require_collection_literal)
        if not item:
            item = self.parse_production(self.require_line_string_literal)
        if not item:
            item = self.parse_production(self.require_multi_point_literal)
        if not item:
            item = self.parse_production(
                self.require_multi_line_string_literal)
        if not item:
            item = self.parse_production(
                self.require_multi_polygon_literal)
        if not item:
            item = self.parse_production(self.require_point_literal)
        if not item:
            item = self.parse_production(self.require_polygon_literal)
        if not item:
            self.parser_error("geoLiteral")
        return item

    # Line 926
    def require_full_line_string_literal(self):
        """Parses production: fullLineStringLiteral

        Returns a :class:`geotypes.LineStringLiteral` instance, a named
        tuple consisting of 'srid' and 'line_string' members."""
        srid = self.require_srid_literal()
        l = self.require_line_string_literal()
        return geo.LineStringLiteral(srid, l)

    # Line 927
    def require_line_string_literal(self):
        """Parses production: lineStringLiteral

        Returns a :class:`geotypes.LineString` instance."""
        self.require_production(
            self.parse_insensitive("linestring"), "lineStringLiteral")
        return self.require_line_string_data()

    # Line 928
    def require_line_string_data(self):
        """Parses production: lineStringData

        Returns a :class:`geotypes.LineString` instance."""
        self.require(self.OPEN)
        coords = []
        coords.append(self.require_position_literal())
        while self.parse(self.COMMA):
            coords.append(self.require_position_literal())
        self.require(self.CLOSE)
        return geo.LineString(coords)

    # Line 931
    def require_full_multi_line_string_literal(self):
        """Parses production: fullMultiLineStringLiteral

        Returns a :class:`geotypes.MultiLineStringLiteral` instance."""
        srid = self.require_srid_literal()
        ml = self.require_multi_line_string_literal()
        return geo.MultiLineStringLiteral(srid, ml)

    # Line 932
    def require_multi_line_string_literal(self):
        """Parses production: multiLineStringLiteral

        Returns a :class:`geotypes.MultiLineString` instance."""
        try:
            self.require_production(
                self.parse_insensitive("multilinestring("),
                "MultiLineStringLiteral")
            # may be empty
            line_strings = []
            l = self.parse_production(self.require_line_string_data)
            if l:
                line_strings.append(l)
                while self.parse(self.COMMA):
                    line_strings.append(self.require_line_string_data())
            self.require(self.CLOSE)
        except ParserError:
            self.parser_error()
        return geo.MultiLineString(line_strings)

    # Line 935
    def require_full_multi_point_literal(self):
        """Parses production: fullMultiPointLiteral

        Returns a :class:`geotypes.MultiPointLiteral` instance."""
        srid = self.require_srid_literal()
        mp = self.require_multi_point_literal()
        return geo.MultiPointLiteral(srid, mp)

    # Line 936
    def require_multi_point_literal(self):
        """Parses production: multiPointLiteral

        Returns a :class:`geotypes.MultiPoint` instance."""
        self.require_production(
            self.parse_insensitive("multipoint("), "MultiPointLiteral")
        # may be empty
        points = []
        p = self.parse_production(self.require_point_data)
        if p:
            points.append(p)
            while self.parse(self.COMMA):
                points.append(self.require_point_data())
        self.require(self.CLOSE)
        return geo.MultiPoint(points)

    # Line 939
    def require_full_multi_polygon_literal(self):
        """Parses production: fullMultiPolygonLiteral

        Returns a :class:`geotypes.MultiPolygonLiteral` instance."""
        srid = self.require_srid_literal()
        mp = self.require_multi_polygon_literal()
        return geo.MultiPolygonLiteral(srid, mp)

    # Line 940
    def require_multi_polygon_literal(self):
        """Parses production: multiPolygonLiteral

        Returns a :class:`geotypes.MultiPolygon` instance."""
        try:
            self.require_production(
                self.parse_insensitive("multipolygon("), "MultiPolygonLiteral")
            # may be empty
            polygons = []
            p = self.parse_production(self.require_polygon_data)
            if p:
                polygons.append(p)
                while self.parse(self.COMMA):
                    polygons.append(self.require_polygon_data())
            self.require(self.CLOSE)
        except ParserError:
            self.parser_error()
        return geo.MultiPolygon(polygons)

    # Line 943
    def require_full_point_literal(self):
        """Parses production: fullPointLiteral

        Returns a :class:`geotypes.PointLiteral` instance, a named tuple
        consisting of "srid" and "point" members."""
        srid = self.require_srid_literal()
        p = self.require_point_literal()
        return geo.PointLiteral(srid, p)

    # Line 944
    def require_srid_literal(self):
        """Parses production: sridLiteral

        Returns an integer reference for the SRID or raises a parser
        error."""
        self.require_production(
            self.parse_insensitive("srid"), "SRID")
        self.require(self.EQ)
        digits = self.require_production(self.parse_digits(1, 5))
        self.require(self.SEMI)
        return int(digits)

    # Line 945
    def require_point_literal(self):
        """Parses production: pointLiteral

        Reuturns a Point instance."""
        self.require_production(
            self.parse_insensitive("point"), "pointLiteral")
        return self.require_point_data()

    # Line 946
    def require_point_data(self):
        """Parses production: pointData

        Returns a :class:`geotypes.Point` instance."""
        self.require(self.OPEN)
        coords = self.require_position_literal()
        self.require(self.CLOSE)
        return geo.Point(*coords)

    # Line 947
    def require_position_literal(self):
        """Parses production: positionLiteral

        Returns a tuple of two float values or raises a parser error.
        Although the ABNF refers to "longitude then latitude" this
        production is used for all co-ordinate reference systems in both
        Geography and Geometry types so we make no such judgement
        ourselves and simply return an unamed tuple."""
        d1 = self.require_double_value()
        self.require(self.SP)
        d2 = self.require_double_value()
        return (d1, d2)

    # Line 950
    def require_full_polygon_literal(self):
        """Parses production: fullPolygonLiteral

        Returns a :class:`geotypes.PolygonLiteral` instance."""
        srid = self.require_srid_literal()
        p = self.require_polygon_literal()
        return geo.PolygonLiteral(srid, p)

    # Line 951
    def require_polygon_literal(self):
        """Parses production: polygonLiteral

        Returns a :class:`geotypes.Polygon` instance."""
        self.require_production(
            self.parse_insensitive("polygon"), "polygonLiteral")
        return self.require_polygon_data()

    # Line 952
    def require_polygon_data(self):
        """Parses production: polygonData

        Returns a :class:`geotypes.Polygon` instance."""
        self.require(self.OPEN)
        rings = []
        rings.append(self.require_ring_literal())
        while self.parse(self.COMMA):
            rings.append(self.require_ring_literal())
        self.require(self.CLOSE)
        return geo.Polygon(rings)

    # Line 953
    def require_ring_literal(self):
        """Parses production: ringLiteral

        Returns a :class:`geotypes.Ring` instance."""
        self.require(self.OPEN)
        coords = []
        coords.append(self.require_position_literal())
        while self.parse(self.COMMA):
            coords.append(self.require_position_literal())
        self.require(self.CLOSE)
        return geo.Ring(coords)

    # Line 1045
    def require_rws(self):
        """Parses required white space

        We assume that percent encoding has already been removed."""
        if not self.parse_bws():
            self.parser_error("RWS")

    # Line 1046
    def parse_bws(self):
        """Parses (optional) bad white space

        We assume that percent-encoding has already been removed."""
        count = 0
        while self.parse_one(" \t"):
            count += 1
        return count

    # Line 1048
    AT = ul("@")

    # Line 1050
    COMMA = ul(",")

    # Line 1051
    EQ = ul("=")

    # Line 1052
    def parse_sign_int(self):
        """Parses production: SIGN (aka sign)

        Returns the integer 1 or -1 depending on the sign.  If no sign
        is parsed then 1 is returned."""
        sign = self.parse_one('+-')
        return -1 if sign == "-" else 1

    # Line 1052
    def parse_sign(self):
        """Parses production: SIGN (aka sign)

        This production is typically optional so we either return "+",
        "-" or "" depending on the sign character parsed.  The ABNF
        allows for the percent encoded value "%2B" instead of "+" but we
        assume that percent-encoding has been removed before parsing.
        (That may not be true in XML documents but it seems
        unintentional to allow this form in that context.)"""
        sign = self.parse_one('+-')
        return sign if sign else ''

    # Line 1053
    SEMI = ul(";")

    # Line 1054
    STAR = ul("*")

    # Line 1055
    SQUOTE = ul("'")

    # Line 1057
    OPEN = ul("(")

    # Line 1058
    CLOSE = ul(")")

    # Line 1161
    DQUOTE = ul('"')

    # Line 1162
    SP = ul(" ")
