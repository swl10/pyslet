"""Copyright (c) 2004, University of Cambridge.

All rights reserved.

Redistribution and use of this software in source and binary forms
(where applicable), with or without modification, are permitted
provided that the following conditions are met:

 *  Redistributions of source code must retain the above copyright
    notice, this list of conditions, and the following disclaimer.

 *  Redistributions in binary form must reproduce the above
    copyright notice, this list of conditions, and the following
    disclaimer in the documentation and/or other materials provided with
    the distribution.
    
 *  Neither the name of the University of Cambridge, nor the names of
    any other contributors to the software, may be used to endorse or
    promote products derived from this software without specific prior
    written permission.

THIS SOFTWARE IS PROVIDED ``AS IS'', WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."""


import types
import random

from pyslet.pep8 import PEP8Compatibility

# We read 64K
READ_BUFFER_SIZE = 65536

#	Exceptions


class RFC2234Error(Exception):
    pass


class RFC2234RuleError (RFC2234Error):
    pass


class RFCParserError(Exception):

    def __init__(self, str, lineNum=None, linePos=None):
        Exception.__init__(self, str)
        self.lineNum = lineNum
        self.linePos = linePos

    def __str__(self):
        return self.AppendLineInfo(self.GetStem() + ": " + Exception.__str__(self))

    def GetStem(self):
        return "Error"

    def AppendLineInfo(self, msg):
        if self.lineNum is not None:
            msg = msg + "; Line " + str(self.lineNum)
            if self.linePos is not None:
                msg = msg + "." + str(self.linePos)
        return msg


class RFCSyntaxError(RFCParserError):

    def GetStem(self):
        return "Syntax Error"


class RFCValidityError(RFCParserError):

    def GetStem(self):
        return "Validity Error"

    def AppendLineInfo(self, msg):
        """We override this method for validity errors because they generally
        relate to what we have just parsed, rather than what we are about to
        parse.  As such, we make the output more approximate (reporting only
        the line number) and if we are at the beginning of a line we report
        the previous line instead to prevent misleading the user."""
        if self.lineNum is not None:
            lineNum = self.lineNum
            if self.linePos is not None:
                if self.linePos == 0 and self.lineNum:
                    lineNum = self.lineNum - 1
            msg = msg + "; Line " + str(lineNum)
        return msg


class RFCParserWarning (RFCParserError):

    def GetStem(self):
        return "Warning"


class RFC2234Parser(PEP8Compatibility):

    """
    A general purpose RFC2234 Parser class, the data source can be a string,
    a file or another RFC2234Parser instance.
    """

    def __init__(self, source=None):
        PEP8Compatibility.__init__(self)
        self.validationMode = RFC2234Parser.kStopOnFatalErrors
        if source is None:
            self.ResetParser("")
        else:
            self.ResetParser(source)

    def ResetParser(self, src, baseLine=0, basePos=0):
        if isinstance(src, RFC2234Parser):
            self.parent = src
            self.the_char = self.parent.the_char
        else:
            self.parent = None
            if type(src) in (types.StringType, types.UnicodeType):
                self.data = src
                self.dataSource = None
            elif type(src) is types.FileType:
                self.data = ''
                self.dataSource = src
            else:
                raise ValueError
            self.lineNum = baseLine
            self.basePos = basePos
            self.dataPos = 0
            self.the_char = None
            self.errors = []
            self.parserStack = []
            if len(self.data) == 0 and self.dataSource:
                self.data = self.dataSource.read(READ_BUFFER_SIZE)
            if len(self.data):
                self.the_char = self.data[0]
            else:
                self.the_char = None

    def next_char(self):
        if self.the_char is not None:
            if self.parent:
                self.parent.next_char()
                self.the_char = self.parent.the_char
            else:
                self.dataPos = self.dataPos + 1
                if self.dataPos >= len(self.data) and self.dataSource:
                    if self.parserStack:
                        self.data = self.data + \
                            self.dataSource.read(READ_BUFFER_SIZE)
                    else:
                        self.basePos = self.basePos - len(self.data)
                        self.data = self.dataSource.read(READ_BUFFER_SIZE)
                        self.dataPos = 0
                if self.dataPos < len(self.data):
                    self.the_char = self.data[self.dataPos]
                else:
                    self.the_char = None

    def NextLine(self):
        if self.parent:
            self.parent.NextLine()
        else:
            self.lineNum = self.lineNum + 1
            self.basePos = self.dataPos

    # Constants used for setting validation mode
    kStopOnFatalErrors = 0
    kStopOnAllErrors = 1
    kStopOnWarnings = 2

    def SetValidationMode(self, validationMode):
        self.validationMode = validationMode

    # Constants used for passing to the error methods
    kFatal = 1
    kNonFatal = 0

    def BadSyntax(self, msgStr=None, fatal=1):
        if self.parent:
            self.parent.BadSyntax(msgStr, fatal)
        else:
            self.errors.append(
                RFCSyntaxError(msgStr, self.lineNum, self.dataPos - self.basePos))
            if fatal or self.validationMode >= RFC2234Parser.kStopOnAllErrors:
                raise self.errors[-1]

    def validity_error(self, msgStr=None, fatal=1):
        if self.parent:
            self.parent.validity_error(msgStr, fatal)
        else:
            self.errors.append(
                RFCValidityError(msgStr, self.lineNum, self.dataPos - self.basePos))
            if fatal or self.validationMode >= RFC2234Parser.kStopOnAllErrors:
                raise self.errors[-1]

    def Warning(self, msgStr=None):
        if self.parent:
            self.parent.Warning(msgStr)
        else:
            self.errors.append(
                RFCWarning(msgStr, self.lineNum, self.dataPos - self.basePos))
            if self.validationMode == RFC2234Parser.kStopOnWarnings:
                raise self.errors[-1]

    def PushParser(self):
        if self.parent:
            self.parent.PushParser()
        else:
            self.parserStack.append(
                (self.lineNum, self.basePos, self.dataPos, self.the_char, len(self.errors)))

    def PopParser(self, rewind):
        if self.parent:
            self.parent.PopParser(rewind)
            self.the_char = self.parent.the_char
        else:
            if rewind:
                self.lineNum, self.basePos, self.dataPos, self.the_char, nErrors = self.parserStack.pop()
                del self.errors[nErrors:]
            else:
                self.parserStack.pop()

    def ParseTerminal(self, terminal):
        for c in terminal:
            if self.the_char == c:
                self.next_char()
            else:
                if not IsVCHAR(c):
                    expected = "expected chr(" + str(ord(c)) + ")"
                else:
                    expected = "expected '" + c + "'"
                self.BadSyntax(expected)
        return terminal

    def parse_literal(self, literal):
        result = ""
        for c in literal.lower():
            if self.the_char is not None and self.the_char.lower() == c:
                result = result + self.the_char
                self.next_char()
            else:
                if not IsVCHAR(c):
                    expected = "expected chr(" + str(ord(c)) + ")"
                else:
                    expected = 'expected "' + c + '"'
                self.BadSyntax(expected)
        return result

    def ParseValueRange(self, lowerBound, upperBound):
        if self.the_char is not None and ord(self.the_char) >= lowerBound and ord(self.the_char) <= upperBound:
            the_char = self.the_char
            self.next_char()
            return the_char
        else:
            if not IsVCHAR(unichr(lowerBound)) or not IsVCHAR(unichr(upperBound)):
                expected = "expected char(" + str(lowerBound) + \
                    ")-chr(" + str(upperBound) + ")"
            else:
                # VCHAR can only be ASCII so safe to use chr
                expected = "expected '" + \
                    chr(lowerBound) + "'-'" + chr(upperBound) + "'"
            self.BadSyntax(expected)

    def ParseEndOfData(self):
        if self.the_char is not None:
            self.BadSyntax("expected end-of-data")


#	Common Terminals
CR = chr(0x0D)
DQUOTE = chr(0x22)
HTAB = chr(0x09)
LF = chr(0x0A)
SP = chr(0x20)
#	CRLF
CRLF = CR + LF

#	Some utility functions for core syntax productions


def is_alpha(c):
    return c and ((ord(c) >= 0x41 and ord(c) <= 0x5A) or (ord(c) >= 0x61 and ord(c) <= 0x7A))


def IsBIT(c):
    return c == '0' or c == '1'


def is_char(c):
    return c and ord(c) <= 0x7F


def IsCR(c):
    return c == CR


def is_ctl(c):
    return c is not None and (ord(c) <= 0x1F or ord(c) == 0x7F)


def is_digit(c):
    return c and (ord(c) >= 0x30 and ord(c) <= 0x39)


def IsDQUOTE(c):
    return c == DQUOTE


def IsHEXDIG(c):
    return is_digit(c) or (c and ((ord(c) >= 0x41 and ord(c) <= 0x46) or (ord(c) >= 0x61 and ord(c) <= 0x66)))


def IsHTAB(c):
    return c == HTAB


def IsLF(c):
    return c == LF


def is_octet(c):
    return c is not None and (ord(c) <= 0xFF)


def IsSP(c):
    return c == SP


def IsVCHAR(c):
    return c and (ord(c) >= 0x21 and ord(c) <= 0x7E)


def IsWSP(c):
    return c == SP or c == HTAB


class RFC2234CoreParser (RFC2234Parser):

    def ParseRepeat(self, testFunction):
        result = ""
        while testFunction(self.the_char):
            result = result + self.the_char
            self.next_char()
        return result

    def ParseALPHA(self):
        if is_alpha(self.the_char):
            the_char = self.the_char
            self.next_char()
            return the_char
        else:
            self.BadSyntax('expected ALPHA')

    def ParseBIT(self):
        if IsBIT(self.the_char):
            bit = self.the_char
            self.next_char()
            return bit == "1"
        else:
            self.BadSyntax("expected BIT")

    def ParseBITRepeat(self):
        value = -1
        while IsBIT(self.the_char):
            if value < 0:
                value = (self.the_char == "1")
            else:
                value = value * 2 + (self.the_char == "1")
            self.next_char()
        return value

    def ParseCHAR(self):
        if is_char(self.the_char):
            the_char = self.the_char
            self.next_char()
            return the_char
        else:
            self.BadSyntax("expected CHAR")

    def ParseCR(self):
        if IsCR(self.the_char):
            self.next_char()
            return CR
        else:
            self.BadSyntax("expected CR")

    def ParseCRLF(self):
        if IsCR(self.the_char):
            self.next_char()
            if IsLF(self.the_char):
                self.next_char()
                self.NextLine()
                return CRLF
        self.BadSyntax("expected CRLF")

    def ParseCTL(self):
        if is_ctl(self.the_char):
            the_char = self.the_char
            self.next_char()
            return the_char
        else:
            self.BadSyntax("expected CTL")

    def ParseDIGIT(self):
        if is_digit(self.the_char):
            value = ord(self.the_char) - ord('0')
            self.next_char()
            return value
        else:
            self.BadSyntax("expected DIGIT")

    def ParseDIGITRepeat(self):
        value = None
        while is_digit(self.the_char):
            if value is None:
                value = ord(self.the_char) - ord('0')
            else:
                value = value * 10 + (ord(self.the_char) - ord('0'))
            self.next_char()
        return value

    def ParseDQUOTE(self):
        if IsDQUOTE(self.the_char):
            self.next_char()
            return DQUOTE
        else:
            self.BadSyntax("expected DQUOTE")

    def ParseHEXDIG(self):
        value = -1
        if self.the_char:
            theCharCode = ord(self.the_char)
            if is_digit(self.the_char):
                value = theCharCode - ord('0')
            elif (theCharCode >= ord('a') and theCharCode <= ord('f')):
                value = theCharCode - ord('a') + 10
            elif (theCharCode >= ord('A') and theCharCode <= ord('F')):
                value = theCharCode - ord('A') + 10
        if value >= 0:
            self.next_char()
            return value
        else:
            self.BadSyntax("expected HEXDIG")

    def ParseHEXDIGRepeat(self):
        value = None
        while self.the_char:
            theCharCode = ord(self.the_char)
            if is_digit(self.the_char):
                digitValue = theCharCode - ord('0')
            elif (theCharCode >= ord('a') and theCharCode <= ord('f')):
                digitValue = theCharCode - ord('a') + 10
            elif (theCharCode >= ord('A') and theCharCode <= ord('F')):
                digitValue = theCharCode - ord('A') + 10
            else:
                break
            if value is None:
                value = digitValue
            else:
                value = value * 16 + digitValue
            self.next_char()
        return value

    def ParseHTAB(self):
        if IsHTAB(self.the_char):
            self.next_char()
            return HTAB
        else:
            self.BadSyntax("expected HTAB")

    def ParseLF(self):
        if IsLF(self.the_char):
            self.next_char()
            return LF
        else:
            self.BadSyntax("expected LF")

    def ParseLWSP(self):
        lwsp = ""
        while 1:
            if IsWSP(self.the_char):
                lwsp = lwsp + self.the_char
                self.next_char()
            elif IsCR(self.the_char):
                try:
                    self.PushParser()
                    lwsp = lwsp + (self.ParseCRLF() + self.ParseWSP())
                    self.PopParser(0)
                except RFC2234Error:
                    self.PopParser(1)
                    break
        return lwsp

    def ParseOCTET(self):
        if is_octet(self.the_char):
            the_char = self.the_char
            self.next_char()
            return the_char
        else:
            self.BadSyntax("expected OCTET")

    def parse_sp(self):
        if self.the_char == 0x20:
            self.next_char()
            return ' '
        else:
            self.BadSyntax("expected SP")

    def ParseVCHAR(self):
        theCharCode = ord(self.the_char)
        if theCharCode >= 0x21 and theCharCode <= 0x7E:
            the_char = self.the_char
            self.next_char()
            return the_char
        else:
            self.BadSyntax("expected VCHAR")

    def ParseWSP(self):
        if IsWSP(self.the_char):
            the_char = self.the_char
            self.next_char()
            return the_char
        else:
            self.BadSyntax("expected WSP")


#	Our parsers can parse several different types of object
kUndefinedRule = 0  # A pattern that has not been defined
kTerminalRule = 1		# A string of characters to be matched literally
# A string of characters to be matched literally case-insensitive
kLiteralRule = 2
# A tuple of two values representing lower and upper bounds on a single value
kValueRangeRule = 3
kSequenceRule = 4		# A tuple of elements that must appear in sequence
kAlternativeRule = 5  # A tuple of elements, one of which must appear
# A tuple of min and max count followed directly by the next element
kRepeatRule = 6
# A string of character representing a human-readable description of the rule
kProseRule = 7
kAliasRule = 8		# A simple pointer to a different rule

#	Our parses recognize two types of rule
kBasicRule = 0
kIncrementalRule = 1


class RFC2234ABNFRuleBase:

    def __init__(self):
        self.reset()

    def reset(self):
        self.rules = {}
        self.ruleID = {}
        self.nextRuleID = 0

    def AddRule(self, rule):
        for r in self.rules:
            # This loop slows us down but the trade is a tidying ruleBase with no repeated
            # patterns unless they form identically defined rules with
            # different names
            if rule == self.rules[r][1:]:
                return r
        ruleID = self.nextRuleID
        self.nextRuleID = self.nextRuleID + 1
        self.rules[ruleID] = [None] + rule
        return ruleID

    def DeclareRule(self, ruleName):
        # If rule name is already declared, returns the existing ruleID
        lcRuleName = ruleName.lower()
        if lcRuleName in self.ruleID:
            return self.ruleID[lcRuleName]
        else:
            ruleID = self.nextRuleID
            self.nextRuleID = self.nextRuleID + 1
            self.rules[ruleID] = [ruleName, kUndefinedRule]
            self.ruleID[lcRuleName] = ruleID
            return ruleID

    def DefineRule(self, ruleName, ruleType, ruleID):
        lcRuleName = ruleName.lower()
        rule = self.rules[ruleID]
        if ruleType == kBasicRule:
            # This is a basic rule definition
            if lcRuleName in self.ruleID:
                # Already defined
                oldID = self.ruleID[lcRuleName]
                oldRule = self.rules[oldID]
                if oldRule[1] == kUndefinedRule:
                    if rule[0]:
                        # This rule already has a name, so we use the old
                        # ruleID instead
                        ruleID = oldID
                        self.rules[ruleID] = [ruleName] + rule[1:]
                    else:
                        # Turn the old rule into an alias, best removed later
                        # during compaction
                        self.rules[oldID] = [None, kAliasRule, ruleID]
                        rule[0] = ruleName
                else:
                    raise RFC2234RuleError(ruleName)
            elif rule[0]:
                # This rule already has a name, duplicate it
                ruleID = self.nextRuleID
                self.nextRuleID = self.nextRuleID + 1
                self.rules[ruleID] = [ruleName] + rule[1:]
            else:
                # Simple case, just add the name to the rule
                rule[0] = ruleName
        else:
            # Incremental rule, combine old and new in a new rule
            if not lcRuleName in self.ruleID:
                raise RFC2234RuleError(ruleName)
            basicID = self.ruleID[ruleName]
            basicRule = self.rules[basicID]
            if basicRule[1] == kUndefinedRule:
                raise RFC2234RuleError(ruleName)
            newRuleID = self.nextRuleID
            self.nextRuleID = self.nextRuleID + 1
            self.rules[newRuleID] = [
                ruleName, kAlternativeRule, basicID, ruleID]
            self.rules[basicID][0] = None
            ruleID = newRuleID
        self.ruleID[lcRuleName] = ruleID

    def GetRuleID(self, ruleName):
        lcRuleName = ruleName.lower()
        if lcRuleName in self.ruleID:
            return self.ruleID[lcRuleName]
        else:
            raise RFC2234RuleError(ruleName)

    def PrintRuleBase(self):
        result = ""
        ruleNames = self.ruleID.keys()
        ruleNames.sort()
        for r in ruleNames:
            result = result + self.PrintRuleDefinition(r) + CRLF
        return result

    def PrintRuleDefinition(self, ruleName):
        ruleID = self.GetRuleID(ruleName)
        return self.rules[ruleID][0] + " = " + self.PrintRule(ruleID, 0, 1)

    def PrintRule(self, ruleID, bracket=0, expandRule=0):
        rule = self.rules[ruleID]
        if not expandRule and rule[0]:
            return rule[0]
        ruleType = rule[1]
        if ruleType == kUndefinedRule:
            return "<undefined>"
        elif ruleType == kTerminalRule:
            terminalStr = rule[2]
            result = "%d" + str(ord(terminalStr[0]))
            for c in terminalStr[1:]:
                result = result + "." + str(ord(c))
            return result
        elif ruleType == kLiteralRule:
            return '"' + rule[2] + '"'
        elif ruleType == kValueRangeRule:
            return "%d" + str(rule[2]) + "-" + str(rule[3])
        elif ruleType == kSequenceRule:
            if bracket:
                result = "("
            else:
                result = ""
            result = result + self.PrintRule(rule[2], 1)
            for r in rule[3:]:
                result = result + " " + self.PrintRule(r, 1)
            if bracket:
                result = result + ")"
            return result
        elif ruleType == kAlternativeRule:
            if bracket:
                result = "("
            else:
                result = ""
            result = result + self.PrintRule(rule[2], 1)
            for r in rule[3:]:
                result = result + " / " + self.PrintRule(r, 1)
            if bracket:
                result = result + ")"
            return result
        elif ruleType == kRepeatRule:
            minRepeat = rule[2]
            maxRepeat = rule[3]
            if minRepeat == 0 and maxRepeat == 1:
                result = "[" + self.PrintRule(rule[4], 0) + "]"
            elif minRepeat == maxRepeat:
                result = str(minRepeat) + self.PrintRule(rule[4], 1)
            else:
                if minRepeat > 0:
                    result = str(minRepeat)
                else:
                    result = ""
                result = result + "*"
                if maxRepeat is not None:
                    result = result + str(maxRepeat)
                result = result + self.PrintRule(rule[4], 1)
            return result
        elif ruleType == kProseRule:
            return "<" + rule[2] + ">"
        elif ruleType == kAliasRule:
            return self.PrintRule(rule[2], bracket)
        else:
            raise RFC2234RuleError("internal rule-base error")

    def GenerateData(self, ruleName, maxOptRepeat):
        result = ""
        ruleStack = [(self.GetRuleID(ruleName), None)]
        recursionControl = [0] * len(self.rules)
        while ruleStack:
            ruleID, rulePos = ruleStack.pop()
            rule = self.rules[ruleID]
            ruleType = rule[1]
            if ruleType == kTerminalRule:
                result = result + rule[2]
            elif ruleType == kLiteralRule:
                literalStr = rule[2]
                for c in literalStr:
                    if is_alpha(c):
                        if random.randrange(2):
                            result = result + c.lower()
                        else:
                            result = result + c.upper()
                    else:
                        result = result + c
            elif ruleType == kValueRangeRule:
                if rule[3] > 0x7F:
                    result = result + \
                        unichr(random.randrange(rule[2], rule[3] + 1))
                else:
                    result = result + \
                        chr(random.randrange(rule[2], rule[3] + 1))
            elif ruleType == kSequenceRule or ruleType == kAliasRule:
                if rulePos is None:
                    rulePos = 2
                    recursionControl[ruleID] = recursionControl[ruleID] + 1
                else:
                    rulePos = rulePos + 1
                if rulePos < len(rule):
                    # push ourselves first
                    ruleStack.append((ruleID, rulePos))
                    ruleStack.append((rule[rulePos], None))
                else:
                    recursionControl[ruleID] = recursionControl[ruleID] - 1
            elif ruleType == kAlternativeRule:
                # Select one at random
                if rulePos is None:
                    recursionControl[ruleID] = recursionControl[ruleID] + 1
                    choices = []
                    for r in rule[2:]:
                        if recursionControl[r] < maxOptRepeat:
                            choices.append(r)
                    if not choices:
                        raise RFC2234RuleError("too much recursion")
                    ruleStack.append((ruleID, 1))
                    ruleStack.append(
                        (choices[random.randrange(len(choices))], None))
                else:
                    recursionControl[ruleID] = recursionControl[ruleID] - 1
            elif ruleType == kRepeatRule:
                minRepeat = rule[2]
                maxRepeat = rule[3]
                if rulePos is None:
                    adjustedMaxOpt = maxOptRepeat - recursionControl[ruleID]
                    if adjustedMaxOpt < 0:
                        adjustedMaxOpt = 0
                    if maxRepeat is None or maxRepeat > minRepeat + adjustedMaxOpt:
                        maxRepeat = minRepeat + adjustedMaxOpt
                    rulePos = [random.randrange(minRepeat, maxRepeat + 1), 0]
                    rulePos[1] = rulePos[0] - minRepeat
                    recursionControl[ruleID] = recursionControl[
                        ruleID] + rulePos[1]
                else:
                    rulePos[0] = rulePos[0] - 1
                if rulePos[0]:
                    ruleStack.append((ruleID, rulePos))
                    ruleStack.append((rule[4], None))
                else:
                    recursionControl[ruleID] = recursionControl[
                        ruleID] - rulePos[1]
            elif ruleType == kProseRule:
                raise RFC2234RuleError("can't generate from prose description")
            else:
                raise RFC2234RuleError("internal rule-base error")
        return result

    def ValidateData(self, ruleName, data):
        ruleStack = [(self.GetRuleID(ruleName), None, None)]
        errorPos = -1
        pos = 0
        parserStack = [(pos, ruleStack)]
        while 1:
            parserStack.sort()
            pos, ruleStack = parserStack[0]
            del parserStack[0]
            if not ruleStack:
                break
            ruleID, rulePos, ruleName = ruleStack.pop()
            try:
                rule = self.rules[ruleID]
                if rule[0]:
                    ruleName = rule[0]
                ruleType = rule[1]
                if ruleType == kTerminalRule:
                    terminalStr = rule[2]
                    match = data[pos:pos + len(terminalStr)]
                    if match != terminalStr:
                        raise RFCValidyError("in production " + ruleName)
                    pos = pos + len(terminalStr)
                elif ruleType == kLiteralRule:
                    literalStr = rule[2].lower()
                    match = data[pos:pos + len(literalStr)].lower()
                    if match != literalStr:
                        raise RFCValidyError("in production " + ruleName)
                    pos = pos + len(literalStr)
                elif ruleType == kValueRangeRule:
                    c = data[pos:pos + 1]
                    if not (c and ord(c) >= rule[2] and ord(c) <= rule[3]):
                        raise RFCValidyError("in production " + ruleName)
                    pos = pos + 1
                elif ruleType == kSequenceRule:
                    if rulePos is None:
                        rulePos = 2
                    else:
                        rulePos = rulePos + 1
                    if rulePos < len(rule):
                        if rulePos < len(rule) - 1:  # push ourselves first
                            ruleStack.append((ruleID, rulePos, ruleName))
                        ruleStack.append((rule[rulePos], None, ruleName))
                elif ruleType == kAlternativeRule:
                    if rulePos is None:  # first time
                        rulePos = 2
                    else:  # recover from failure, try next option
                        rulePos = rulePos + 1
                    if rulePos < len(rule):
                        if rulePos < len(rule) - 1:
                            # Save the parser for all but the last item, adding ourselves
                            # to the saved ruleStack ready to recover from
                            # failure
                            parserStack.append(
                                (pos, ruleStack + [(ruleID, rulePos, ruleName)]))
                        ruleStack.append((rule[rulePos], None, ruleName))
                elif ruleType == kRepeatRule:
                    minRepeat = rule[2]
                    maxRepeat = rule[3]
                    subRuleID = rule[4]
                    if rulePos is None:  # first time
                        rulePos = 0
                    else:
                        rulePos = rulePos + 1
                    if rulePos < minRepeat:  # Next one is required
                        ruleStack.append((ruleID, rulePos, ruleName))
                        ruleStack.append((subRuleID, None, ruleName))
                    # This one is optional
                    elif maxRepeat is None or rulePos < maxRepeat:
                        parserStack.append((pos, ruleStack[:]))
                        ruleStack.append((ruleID, rulePos, ruleName))
                        ruleStack.append((subRuleID, None, ruleName))
                    # else: success
                elif ruleType == kProseRule:
                    raise RFC2234RuleError(
                        "can't validate against prose description")
                elif ruleType == kAliasRule:
                    ruleStack.append((rule[2], None, ruleName))
                else:
                    raise RFC2234RuleError("internal rule-base error")
                parserStack.append((pos, ruleStack))
            except RFCValidyError, err:
                if pos > errorPos:
                    maxError = err
                    errorPos = pos
                if not len(parserStack):
                    raise maxError


class RFC2234ABNFParser (RFC2234CoreParser):

    def __init__(self, ruleBase=None):
        if not ruleBase:
            ruleBase = RFC2234ABNFRuleBase()
        RFC2234CoreParser.__init__(self)
        self.SetRuleBase(ruleBase)

    def SetRuleBase(self, ruleBase):
        self.ruleBase = ruleBase

    def GetRuleBase(self):
        return self.ruleBase

    def ParseRulelist(self):
        loopCount = 0
        while self.the_char:
            if is_alpha(self.the_char):
                self.ParseRule()
            else:
                self.ParseCWspRepeat()
                self.ParseCNl()
            loopCount = loopCount + 1
        if not loopCount:
            self.BadSyntax("expected rule, comment or newline")

    def ParseRule(self):
        ruleName = self.ParseRulename()
        ruleType = self.ParseDefinedAs()
        ruleID = self.ParseElements()
        self.ParseCNl()
        ruleID = self.ruleBase.DefineRule(ruleName, ruleType, ruleID)
        return ruleID

    def ParseRulename(self):
        name = self.ParseALPHA()
        while is_alpha(self.the_char) or is_digit(self.the_char) or self.the_char == "-":
            name = name + self.the_char
            self.next_char()
        return name

    def ParseDefinedAs(self):
        self.ParseCWspRepeat()
        if self.the_char == "=":
            self.next_char()
            if self.the_char == "/":
                self.next_char()
                result = kIncrementalRule
            else:
                result = kBasicRule
        else:
            self.BadSyntax("expected '='")
        self.ParseCWspRepeat()
        return result

    def ParseElements(self):
        result = self.ParseAlternation()
        self.ParseCWspRepeat()
        return result

    def ParseCWsp(self):
        if IsWSP(self.the_char):
            self.next_char()
        else:
            self.ParseCNl()
            self.ParseWSP()

    def ParseCWspRepeat(self):
        while self.the_char:
            if IsWSP(self.the_char):
                self.next_char()
            elif IsCR(self.the_char) or self.the_char == ";":
                try:
                    self.PushParser()
                    self.ParseCNl()
                    self.ParseWSP()
                    self.PopParser(0)
                except:
                    self.PopParser(1)
                    break
            else:
                break

    def ParseCNl(self):
        # Ignore c-nl
        if self.the_char == ";":
            self.parse_comment()
        else:
            self.ParseCRLF()

    def parse_comment(self):
        comment = ''
        if self.the_char == ";":
            self.next_char()
            while IsWSP(self.the_char) or IsVCHAR(self.the_char):
                comment = comment + self.the_char
                self.next_char()
            self.ParseCRLF()
            return comment
        else:
            self.BadSyntax("expected ';'")

    def ParseAlternation(self):
        alternation = [kAlternativeRule]
        alternation.append(self.ParseConcatenation())
        while self.the_char:
            try:
                self.PushParser()
                self.ParseCWspRepeat()
                self.parse_literal("/")
                self.ParseCWspRepeat()
                alternation.append(self.ParseConcatenation())
                self.PopParser(0)
            except RFC2234Error:
                self.PopParser(1)
                break
        if len(alternation) == 2:
            return alternation[1]
        else:
            return self.ruleBase.AddRule(alternation)

    def ParseConcatenation(self):
        concatenation = [kSequenceRule]
        concatenation.append(self.ParseRepetition())
        while self.the_char:
            try:
                self.PushParser()
                self.ParseCWsp()
                self.ParseCWspRepeat()
                concatenation.append(self.ParseRepetition())
                self.PopParser(0)
            except RFC2234Error:
                self.PopParser(1)
                break
        if len(concatenation) == 2:
            return concatenation[1]
        else:
            return self.ruleBase.AddRule(concatenation)

    def ParseRepetition(self):
        if is_digit(self.the_char) or self.the_char == "*":
            minRepeat, maxRepeat = self.ParseRepeat()
            return self.ruleBase.AddRule([kRepeatRule, minRepeat, maxRepeat, self.parse_element()])
        else:
            return self.parse_element()

    def ParseRepeat(self):
        minRepeat = self.ParseDIGITRepeat()
        if self.the_char == "*":
            self.next_char()
            maxRepeat = self.ParseDIGITRepeat()
            if minRepeat is None:
                minRepeat = 0
        elif minRepeat is None:
            self.BadSyntax("expected DIGIT or '*'")
        else:
            maxRepeat = minRepeat
        return (minRepeat, maxRepeat)

    def parse_element(self):
        if is_alpha(self.the_char):
            return self.ruleBase.DeclareRule(self.ParseRulename())
        elif self.the_char == "(":
            return self.ParseGroup()
        elif self.the_char == "[":
            return self.ParseOption()
        elif IsDQUOTE(self.the_char):
            return self.ParseCharVal()
        elif self.the_char == "%":
            return self.ParseNumVal()
        elif self.the_char == "<":
            return self.ParseProseVal()
        else:
            self.BadSyntax("expected element")

    def ParseGroup(self):
        if self.the_char == "(":
            self.next_char()
            self.ParseCWspRepeat()
            result = self.ParseAlternation()
            self.ParseCWspRepeat()
            if self.the_char == ")":
                self.next_char()
                return result
        self.Syntaxerror("expected '('")

    def ParseOption(self):
        if self.the_char == "[":
            self.next_char()
            self.ParseCWspRepeat()
            result = self.ParseAlternation()
            self.ParseCWspRepeat()
            if self.the_char == "]":
                self.next_char()
                return self.ruleBase.AddRule([kRepeatRule, 0, 1, result])
        self.BadSyntax("expected '['")

    def ParseCharVal(self):
        if IsDQUOTE(self.the_char):
            literalStr = ""
            self.next_char()
            while self.the_char:
                if IsDQUOTE(self.the_char):
                    self.next_char()
                    return self.ruleBase.AddRule([kLiteralRule, literalStr])
                theCharCode = ord(self.the_char)
                if theCharCode >= 0x20 and theCharCode <= 0x7E:
                    literalStr = literalStr + self.the_char
                    self.next_char()
                else:
                    break
        self.BadSyntax("expected DQUOTE")

    def ParseNumVal(self):
        # Parses a TerminalRule, or ValueRangeRule
        if self.the_char == "%":
            self.next_char()
            if self.the_char == "b" or self.the_char == "B":
                val = self.ParseBinVal()
            elif self.the_char == "d" or self.the_char == "D":
                val = self.ParseDecVal()
            else:
                val = self.ParseHexVal()
            if type(val) is types.TupleType:
                return self.ruleBase.AddRule([kValueRangeRule, val[0], val[1]])
            else:
                return self.ruleBase.AddRule([kTerminalRule, val])
        else:
            self.BadSyntax("expected num-val")

    def ParseBinVal(self):
        if self.the_char == "b" or self.the_char == "B":
            self.next_char()
            return self.ParseVal(self.ParseBITRepeat)
        else:
            self.BadSyntax("expected bin-val")

    def ParseDecVal(self):
        if self.the_char == "d" or self.the_char == "D":
            self.next_char()
            return self.ParseVal(self.ParseDIGITRepeat)
        else:
            self.BadSyntax("expected dec-val")

    def ParseHexVal(self):
        if self.the_char == "x" or self.the_char == "X":
            self.next_char()
            return self.ParseVal(self.ParseHEXDIGRepeat)
        else:
            self.BadSyntax("expected hex-val")

    def ParseVal(self, fValueParser):
        value = fValueParser()
        if value is None:
            self.BadSyntax("expected value")
        if self.the_char == "-":
            self.PushParser()
            # It's a value range, maybe
            self.next_char()
            value2 = fValueParser()
            if value2 is None:
                # It's a one-value terminal
                self.PopParser(1)
            else:
                # Its a value range, definately
                self.PopParser(0)
                return (value, value2)
        # It's a terminal
        if value > 0x7F:
            terminalStr = unichr(value)
        else:
            terminalStr = chr(value)
        while self.the_char == ".":
            self.PushParser()
            self.next_char()
            value = fValueParser()
            if value is None:
                self.PopParser(1)
                break
            else:
                self.PopParser(0)
                if value > 0x7F:
                    terminalStr = terminalStr + unichr(value)
                else:
                    terminalStr = terminalStr + chr(value)
        return terminalStr

    def ParseProseVal(self):
        if self.the_char == "<":
            proseStr = ""
            self.next_char()
            while self.the_char:
                theCharCode = ord(self.the_char)
                if theCharCode == 0x3E:
                    self.next_char()
                    return self.ruleBase.AddRule([kProseRule, proseStr])
                if theCharCode >= 0x20 and theCharCode <= 0x7E:
                    proseStr = proseStr + self.the_char
                    self.next_char()
                else:
                    self.BadSyntax("expected '>'")
        self.BadSyntax("expected '<'")
