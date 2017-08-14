#! /usr/bin/env python

import base64
import decimal
import uuid

from .. import iso8601 as iso
from ..py2 import (
    byte,
    range3,
    ul,
    )
from ..unicode5 import (
    BasicParser,
    CharClass,
    ParserError
    )
from ..xml import xsdatatypes as xsi

from . import geotypes as geo
from . import types


_oid_start_char = CharClass("_")
_oid_start_char.add_class(CharClass.ucd_category("L"))
_oid_start_char.add_class(CharClass.ucd_category("Nl"))

_oid_char = CharClass()
for c in ("L", "Nl", "Nd", "Mn", "Mc", "Pc", "Cf"):
    _oid_char.add_class(CharClass.ucd_category(c))


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

        Returns a list of :class:`types.ExpandItem`."""
        items = []
        items.append(self.require_expand_item())
        while self.parse(self.COMMA):
            items.append(self.require_expand_item())
        return items

    # Line 246
    def require_expand_item(self):
        """Parse theh production expandItem

        Returns a :class:`types.ExpandItem` instance."""
        item = types.ExpandItem()
        if self.parse(self.STAR):
            item.path = (self.STAR, )
            if self.parse(self.ref):
                item.qualifier = types.PathQualifier.ref
            elif self.parse(self.OPEN):
                levels = self.require_levels()
                self.require(self.CLOSE)
                item.options.levels = levels
            return item
        item.path = tuple(self.require_expand_path())
        if self.parse(self.ref):
            item.qualifier = types.PathQualifier.ref
            if self.parse(self.OPEN):
                item.set_option(*self.require_expand_ref_option())
                while self.parse(self.SEMI):
                    item.set_option(*self.require_expand_ref_option())
                self.require(self.CLOSE)
        elif self.parse(self.count):
            item.qualifier = types.PathQualifier.count
            if self.parse(self.OPEN):
                item.set_option(*self.require_expand_count_option())
                while self.parse(self.SEMI):
                    item.set_option(*self.require_expand_count_option())
                self.require(self.CLOSE)
        elif self.parse(self.OPEN):
            item.set_option(*self.require_expand_option())
            while self.parse(self.SEMI):
                item.set_option(*self.require_expand_option())
            self.require(self.CLOSE)
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
        while self.parse("/"):
            qname = self.parse_production(self.require_qualified_name)
            if qname:
                result.append(qname)
                if self.parse("/"):
                    result.append(self.require_odata_identifier())
                else:
                    break
            else:
                result.append(self.require_odata_identifier())
        return result

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
                    name = types.QualfiedName('.'.join(name), self.STAR)
                else:
                    name = self.STAR
                return (name, )
            name.append(self.require_odata_identifier())
            if self.parse('.'):
                # this name continues
                continue
            # this name is done
            if len(name) > 1:
                name = types.QualifiedName(".".join(name[:-1]), name[-1])
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
        return types.QualifiedName(".".join(result[:-1]), result[-1])

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
        """Parses production primitiveLiteral"""
        save_pos = self.pos
        if self.match_one('-1234567890'):
            # try and parse an integer
            try:
                value = self.require_int64_value()
            except ParserError:
                # must be -INF
                return self.require_double_value()
            if self.match("."):
                # must be decimal or float
                self.setpos(save_pos)
                value = self.require_decimal_value()
                if self.match_one("eE"):
                    # must be float
                    self.setpos(save_pos)
                    value = self.require_double_value()
            elif self.match("-"):
                # could be guid, date, dateTimeOffset
                value = self.parse_production(self.require_date_value)
                if value:
                    if self.match_one("Tt"):
                        self.setpos(save_pos)
                        value = self.require_date_time_offset_value()
                else:
                    value = self.require_guid_value()
            elif self.match(":"):
                # must be time of day
                self.setpos(save_pos)
                value = self.require_time_of_day_value()
            elif self.match_one("ABCDEFabcdef"):
                self.setpos(save_pos)
                value = self.require_guid()
            return value
        elif self.match("'"):
            # a string
            return self.require_string()
        else:
            value = self.require_odata_identifier()
            if self.match_one("."):
                # a qualified name (enum)
                self.setpos(save_pos)
                qname = self.require_qualified_name()
                self.require("'")
                enum_value = self.require_enum_value()
                self.require("'")
                return types.EnumLiteral(qname, tuple(enum_value))
            elif self.match_one("-"):
                # must be a guid again (8HEXDIGIT could look like a name)
                self.setpos(save_pos)
                return self.require_guid()
            elif self.match_one("'"):
                # must be a selector
                value = value.lower()
                self.next_char()
                if value == "duration":
                    value = self.require_duration_value()
                elif value == "binary":
                    value = self.require_binary_value()
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
                    return geo.GeoTypeLiteral(type=geo.GeoType[value], item=v)
                else:
                    # unknown selector
                    self.parser_error("primitive literal")
                self.require("'")
                return value
            elif value == "null":
                return None
            elif value == 'NaN':
                return float('nan')
            elif value == 'INF':
                return float('inf')
            elif value.lower() == 'true':
                return True
            elif value.lower() == 'false':
                return False
            else:
                # just some random word that we don't understand
                self.parser_error("primitive literal")

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

        Returns a :class:`StringValue` instance or raises a parser
        error. Note that this is the literal quoted form of the string
        for use in URLs, string values in XML and JSON payloads are
        represented using native representations.  It is assumed that
        the input *has already* been decoded from the URL and is
        represented as a character string (it may also contain non-ASCII
        characters interpreted from the URL in an appropriate way)."""
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
        return "".join(result)

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

    # Line 1053
    SEMI = ul(";")

    # Line 1054
    STAR = ul("*")

    # Line 1057
    OPEN = ul("(")
    # Line 1058
    CLOSE = ul(")")

    # Line 1162
    SP = ul(" ")
