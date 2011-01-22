from string import split, join
from sys import maxunicode, exc_info, exit
from pickle import dump,load
import os.path
from urllib import urlopen
from traceback import print_exception

def CharInClass (c,cClass):
	if cClass:
		rmax=len(cClass)
		if c>=cClass[0][0] and c<=cClass[rmax-1][1]:
			return RangeTest(c,cClass,0,rmax)
	return 0

def RangeTest (c,cClass,rmin,rmax):
	"""Recursive bisection algorithm on the given cClass."""
	if rmin==rmax:
		return 1
	else:
		rtry=(rmin+rmax)/2
		if c<=cClass[rtry][1]:
			return RangeTest(c,cClass,rmin,rtry)
		elif c>=cClass[rtry+1][0]:
			return RangeTest(c,cClass,rtry+1,rmax)
		else:
			return 0

def CompareCharRanges(ca,cb):
	result=cmp(ca[0],cb[0])
	if result:
		return result
	else:
		return cmp(ca[1],cb[1])
		
def MakeCharClass(c):
	c.sort(CompareCharRanges)
	cPos=0
	while cPos<len(c)-1:
		# should we merge cPos and cPos+1
		if ord(c[cPos][1])>=ord(c[cPos+1][0])-1:
			c[cPos:cPos+2]=[ [c[cPos][0],max(c[cPos+1][1],c[cPos][1])] ]
		else:
			cPos+=1
	return c

def SubtractCharClass(aClass,bClass):
	newClass=[]
	aPos=bPos=0
	aRange=bRange=None
	while aPos<len(aClass) and bPos<len(bClass):
		if aRange is None:
			aRange=aClass[aPos]
		if bRange is None:
			bRange=bClass[bPos]
		if aRange[1]<bRange[0]:
			# all of aRange are in
			newClass.append(aRange)
			aPos+=1;aRange=None
		elif bRange[1]<aRange[0]:
			# disregard all of bRange
			bPos+=1;bRange=None
		elif aRange[0]<bRange[0]:
			newClass.append([aRange[0],unichr(ord(bRange[0])-1)])
			if aRange[1]<=bRange[1]:
				if aRange[1]==bRange[1]:
					bPos+=1;bRange=None
				aPos+=1;aRange=None
			else:
				# modify aRange to remove this bRange
				aRange=[unichr(ord(bRange[1])+1),aRange[1]]
				bPos+=1;bRange=None
		elif aRange[0]==bRange[0]:
			if aRange[1]<=bRange[1]:
				# all of aRange are out
				if aRange[1]==bRange[1]:
					bPos+=1;bRange=None
				aPos+=1;aRange=None
			else:
				# remove bRange from aRange
				aRange=[unichr(ord(bRange[1])+1),aRange[1]]
				bPos+=1;bRange=None
		# else aRange[0]>bRange[0]
		elif aRange[1]<=bRange[1]:
			# all of a is out
			aPos+=1;aRange=None
		else:
			# remove this chunk of aRange
			aRange=[unichr(ord(bRange[1])+1),aRange[1]]
			bPos+=1;bRange=None
	while aPos<len(aClass):
		# add the rest of aClass in, but watch the current range
		# it may have been shortened
		if aRange is None:
			aRange=aClass[aPos]
		newClass.append(aRange)
		aPos+=1;aRange=None
	return newClass

def NegateCharClass(c):
	newC=[[unichr(0),unichr(maxunicode)]]
	return SubtractCharClass(newC,c)


CategoryTableIncomplete=0

def AssignCategory(codePoint0,codePoint1,category):
	global CategoryTable, CategoryTableIncomplete
	if codePoint0>maxunicode:
		CategoryTableIncomplete=1
		return
	if codePoint1>maxunicode:
		codePoint1=maxunicode
		CategoryTableIncomplete=1
	catClass=CategoryTable.get(category,[])
	if not catClass:
		CategoryTable[category]=catClass
	catClass.append([unichr(codePoint0),unichr(codePoint1)])
	MakeCharClass(catClass)
	if len(category)>1:
		catClass=CategoryTable.get(category[0],[])
		if not catClass:
			CategoryTable[category[0]]=catClass
		catClass.append([unichr(codePoint0),unichr(codePoint1)])
		MakeCharClass(catClass)
		
def ParseCategoryTable(unicodeData):
	global CategoryTable, CategoryTableIncomplete
	CategoryTable.clear()
	CategoryTableIncomplete=0
	unicodeData=unicodeData.splitlines()
	currCodePoint=-1
	currCategory=None
	currCategoryBase=-1
	markedRange=0
	for line in unicodeData:
		# disregard any comments
		line=line.split('#')[0]
		if not line:
			continue
		fields=line.split(';')
		codePoint=int(fields[0],16)
		assert codePoint>currCodePoint,"Unicode database error: code points went backwards"
		category=fields[2].strip()
		charName=fields[1].strip()
		if codePoint>currCodePoint+1 and not markedRange:
			# we have skipped a load of code-points
			if currCategory:
				# we were collecting for this category
				AssignCategory(currCategoryBase,currCodePoint,currCategory)
				currCategory=None
				currCategoryBase=-1
			# handle the unassigned block
			AssignCategory(currCodePoint+1,codePoint-1,'Cn')
		if markedRange:
			# end a marked range, but continue in case the following chars are in the same category
			assert category==currCategory, "Unicode character range end-points with non-matching general categories"
			markedRange=0
		else:
			# This next statement handles the case where a marked range immediately
			# follows on from a range of characters in the same category
			markedRange=(charName[0]=='<' and charName[-6:]=="First>")
			if currCategory:
				if category!=currCategory:
					AssignCategory(currCategoryBase,currCodePoint,currCategory)
					currCategory=category
					currCategoryBase=codePoint
			else:
				currCategory=category
				currCategoryBase=codePoint
		currCodePoint=codePoint
	# when we finally exit from this loop, we need to complete any open range
	assert not markedRange,"Unicode database ended during character range definition" 
	if currCategory:
		AssignCategory(currCategoryBase,currCodePoint,currCategory)
	if CategoryTableIncomplete:
		print "Warning: UnicodeData definitions exceed maxunicode (a compile-time Python option)"
	

def ParseBlockTable(blocks):
	global BlockTable
	BlockTable.clear()
	blocks=blocks.splitlines()
	for line in blocks:
		line=line.split('#')[0]
		if not line:
			continue
		fields=line.split(';')
		codePoints=fields[0].strip().split('..')
		codePoint0=int(codePoints[0],16)
		codePoint1=int(codePoints[1],16)
		# the Unicode standard tells us to remove -, _ and any whitespace before case-ignore comparison
		blockName=join(fields[1].split(),'')
		blockName=blockName.replace('-','')
		blockName=blockName.replace('_','').lower()
		if codePoint0>maxunicode:
			continue
		elif codePoint1>maxunicode:
			codePoint1=maxunicode
		BlockTable[blockName]=[unichr(codePoint0),unichr(codePoint1)]

def GetBlockRange(blockName):
	blockName=join(blockName.split(),'')
	blockName=blockName.replace('-','')
	blockName=blockName.replace('_','').lower()
	return BlockTable.get(blockName,None)
	
#
# We copy in a small taster of the true Unicode data which we use if we can't find
# the full pickled data tables in our module's directory.
#
BasicLatinCategoryData="""0000;<control>;Cc;0;BN;;;;;N;NULL;;;;
0001;<control>;Cc;0;BN;;;;;N;START OF HEADING;;;;
0002;<control>;Cc;0;BN;;;;;N;START OF TEXT;;;;
0003;<control>;Cc;0;BN;;;;;N;END OF TEXT;;;;
0004;<control>;Cc;0;BN;;;;;N;END OF TRANSMISSION;;;;
0005;<control>;Cc;0;BN;;;;;N;ENQUIRY;;;;
0006;<control>;Cc;0;BN;;;;;N;ACKNOWLEDGE;;;;
0007;<control>;Cc;0;BN;;;;;N;BELL;;;;
0008;<control>;Cc;0;BN;;;;;N;BACKSPACE;;;;
0009;<control>;Cc;0;S;;;;;N;CHARACTER TABULATION;;;;
000A;<control>;Cc;0;B;;;;;N;LINE FEED (LF);;;;
000B;<control>;Cc;0;S;;;;;N;LINE TABULATION;;;;
000C;<control>;Cc;0;WS;;;;;N;FORM FEED (FF);;;;
000D;<control>;Cc;0;B;;;;;N;CARRIAGE RETURN (CR);;;;
000E;<control>;Cc;0;BN;;;;;N;SHIFT OUT;;;;
000F;<control>;Cc;0;BN;;;;;N;SHIFT IN;;;;
0010;<control>;Cc;0;BN;;;;;N;DATA LINK ESCAPE;;;;
0011;<control>;Cc;0;BN;;;;;N;DEVICE CONTROL ONE;;;;
0012;<control>;Cc;0;BN;;;;;N;DEVICE CONTROL TWO;;;;
0013;<control>;Cc;0;BN;;;;;N;DEVICE CONTROL THREE;;;;
0014;<control>;Cc;0;BN;;;;;N;DEVICE CONTROL FOUR;;;;
0015;<control>;Cc;0;BN;;;;;N;NEGATIVE ACKNOWLEDGE;;;;
0016;<control>;Cc;0;BN;;;;;N;SYNCHRONOUS IDLE;;;;
0017;<control>;Cc;0;BN;;;;;N;END OF TRANSMISSION BLOCK;;;;
0018;<control>;Cc;0;BN;;;;;N;CANCEL;;;;
0019;<control>;Cc;0;BN;;;;;N;END OF MEDIUM;;;;
001A;<control>;Cc;0;BN;;;;;N;SUBSTITUTE;;;;
001B;<control>;Cc;0;BN;;;;;N;ESCAPE;;;;
001C;<control>;Cc;0;B;;;;;N;INFORMATION SEPARATOR FOUR;;;;
001D;<control>;Cc;0;B;;;;;N;INFORMATION SEPARATOR THREE;;;;
001E;<control>;Cc;0;B;;;;;N;INFORMATION SEPARATOR TWO;;;;
001F;<control>;Cc;0;S;;;;;N;INFORMATION SEPARATOR ONE;;;;
0020;SPACE;Zs;0;WS;;;;;N;;;;;
0021;EXCLAMATION MARK;Po;0;ON;;;;;N;;;;;
0022;QUOTATION MARK;Po;0;ON;;;;;N;;;;;
0023;NUMBER SIGN;Po;0;ET;;;;;N;;;;;
0024;DOLLAR SIGN;Sc;0;ET;;;;;N;;;;;
0025;PERCENT SIGN;Po;0;ET;;;;;N;;;;;
0026;AMPERSAND;Po;0;ON;;;;;N;;;;;
0027;APOSTROPHE;Po;0;ON;;;;;N;APOSTROPHE-QUOTE;;;;
0028;LEFT PARENTHESIS;Ps;0;ON;;;;;Y;OPENING PARENTHESIS;;;;
0029;RIGHT PARENTHESIS;Pe;0;ON;;;;;Y;CLOSING PARENTHESIS;;;;
002A;ASTERISK;Po;0;ON;;;;;N;;;;;
002B;PLUS SIGN;Sm;0;ES;;;;;N;;;;;
002C;COMMA;Po;0;CS;;;;;N;;;;;
002D;HYPHEN-MINUS;Pd;0;ES;;;;;N;;;;;
002E;FULL STOP;Po;0;CS;;;;;N;PERIOD;;;;
002F;SOLIDUS;Po;0;CS;;;;;N;SLASH;;;;
0030;DIGIT ZERO;Nd;0;EN;;0;0;0;N;;;;;
0031;DIGIT ONE;Nd;0;EN;;1;1;1;N;;;;;
0032;DIGIT TWO;Nd;0;EN;;2;2;2;N;;;;;
0033;DIGIT THREE;Nd;0;EN;;3;3;3;N;;;;;
0034;DIGIT FOUR;Nd;0;EN;;4;4;4;N;;;;;
0035;DIGIT FIVE;Nd;0;EN;;5;5;5;N;;;;;
0036;DIGIT SIX;Nd;0;EN;;6;6;6;N;;;;;
0037;DIGIT SEVEN;Nd;0;EN;;7;7;7;N;;;;;
0038;DIGIT EIGHT;Nd;0;EN;;8;8;8;N;;;;;
0039;DIGIT NINE;Nd;0;EN;;9;9;9;N;;;;;
003A;COLON;Po;0;CS;;;;;N;;;;;
003B;SEMICOLON;Po;0;ON;;;;;N;;;;;
003C;LESS-THAN SIGN;Sm;0;ON;;;;;Y;;;;;
003D;EQUALS SIGN;Sm;0;ON;;;;;N;;;;;
003E;GREATER-THAN SIGN;Sm;0;ON;;;;;Y;;;;;
003F;QUESTION MARK;Po;0;ON;;;;;N;;;;;
0040;COMMERCIAL AT;Po;0;ON;;;;;N;;;;;
0041;LATIN CAPITAL LETTER A;Lu;0;L;;;;;N;;;;0061;
0042;LATIN CAPITAL LETTER B;Lu;0;L;;;;;N;;;;0062;
0043;LATIN CAPITAL LETTER C;Lu;0;L;;;;;N;;;;0063;
0044;LATIN CAPITAL LETTER D;Lu;0;L;;;;;N;;;;0064;
0045;LATIN CAPITAL LETTER E;Lu;0;L;;;;;N;;;;0065;
0046;LATIN CAPITAL LETTER F;Lu;0;L;;;;;N;;;;0066;
0047;LATIN CAPITAL LETTER G;Lu;0;L;;;;;N;;;;0067;
0048;LATIN CAPITAL LETTER H;Lu;0;L;;;;;N;;;;0068;
0049;LATIN CAPITAL LETTER I;Lu;0;L;;;;;N;;;;0069;
004A;LATIN CAPITAL LETTER J;Lu;0;L;;;;;N;;;;006A;
004B;LATIN CAPITAL LETTER K;Lu;0;L;;;;;N;;;;006B;
004C;LATIN CAPITAL LETTER L;Lu;0;L;;;;;N;;;;006C;
004D;LATIN CAPITAL LETTER M;Lu;0;L;;;;;N;;;;006D;
004E;LATIN CAPITAL LETTER N;Lu;0;L;;;;;N;;;;006E;
004F;LATIN CAPITAL LETTER O;Lu;0;L;;;;;N;;;;006F;
0050;LATIN CAPITAL LETTER P;Lu;0;L;;;;;N;;;;0070;
0051;LATIN CAPITAL LETTER Q;Lu;0;L;;;;;N;;;;0071;
0052;LATIN CAPITAL LETTER R;Lu;0;L;;;;;N;;;;0072;
0053;LATIN CAPITAL LETTER S;Lu;0;L;;;;;N;;;;0073;
0054;LATIN CAPITAL LETTER T;Lu;0;L;;;;;N;;;;0074;
0055;LATIN CAPITAL LETTER U;Lu;0;L;;;;;N;;;;0075;
0056;LATIN CAPITAL LETTER V;Lu;0;L;;;;;N;;;;0076;
0057;LATIN CAPITAL LETTER W;Lu;0;L;;;;;N;;;;0077;
0058;LATIN CAPITAL LETTER X;Lu;0;L;;;;;N;;;;0078;
0059;LATIN CAPITAL LETTER Y;Lu;0;L;;;;;N;;;;0079;
005A;LATIN CAPITAL LETTER Z;Lu;0;L;;;;;N;;;;007A;
005B;LEFT SQUARE BRACKET;Ps;0;ON;;;;;Y;OPENING SQUARE BRACKET;;;;
005C;REVERSE SOLIDUS;Po;0;ON;;;;;N;BACKSLASH;;;;
005D;RIGHT SQUARE BRACKET;Pe;0;ON;;;;;Y;CLOSING SQUARE BRACKET;;;;
005E;CIRCUMFLEX ACCENT;Sk;0;ON;;;;;N;SPACING CIRCUMFLEX;;;;
005F;LOW LINE;Pc;0;ON;;;;;N;SPACING UNDERSCORE;;;;
0060;GRAVE ACCENT;Sk;0;ON;;;;;N;SPACING GRAVE;;;;
0061;LATIN SMALL LETTER A;Ll;0;L;;;;;N;;;0041;;0041
0062;LATIN SMALL LETTER B;Ll;0;L;;;;;N;;;0042;;0042
0063;LATIN SMALL LETTER C;Ll;0;L;;;;;N;;;0043;;0043
0064;LATIN SMALL LETTER D;Ll;0;L;;;;;N;;;0044;;0044
0065;LATIN SMALL LETTER E;Ll;0;L;;;;;N;;;0045;;0045
0066;LATIN SMALL LETTER F;Ll;0;L;;;;;N;;;0046;;0046
0067;LATIN SMALL LETTER G;Ll;0;L;;;;;N;;;0047;;0047
0068;LATIN SMALL LETTER H;Ll;0;L;;;;;N;;;0048;;0048
0069;LATIN SMALL LETTER I;Ll;0;L;;;;;N;;;0049;;0049
006A;LATIN SMALL LETTER J;Ll;0;L;;;;;N;;;004A;;004A
006B;LATIN SMALL LETTER K;Ll;0;L;;;;;N;;;004B;;004B
006C;LATIN SMALL LETTER L;Ll;0;L;;;;;N;;;004C;;004C
006D;LATIN SMALL LETTER M;Ll;0;L;;;;;N;;;004D;;004D
006E;LATIN SMALL LETTER N;Ll;0;L;;;;;N;;;004E;;004E
006F;LATIN SMALL LETTER O;Ll;0;L;;;;;N;;;004F;;004F
0070;LATIN SMALL LETTER P;Ll;0;L;;;;;N;;;0050;;0050
0071;LATIN SMALL LETTER Q;Ll;0;L;;;;;N;;;0051;;0051
0072;LATIN SMALL LETTER R;Ll;0;L;;;;;N;;;0052;;0052
0073;LATIN SMALL LETTER S;Ll;0;L;;;;;N;;;0053;;0053
0074;LATIN SMALL LETTER T;Ll;0;L;;;;;N;;;0054;;0054
0075;LATIN SMALL LETTER U;Ll;0;L;;;;;N;;;0055;;0055
0076;LATIN SMALL LETTER V;Ll;0;L;;;;;N;;;0056;;0056
0077;LATIN SMALL LETTER W;Ll;0;L;;;;;N;;;0057;;0057
0078;LATIN SMALL LETTER X;Ll;0;L;;;;;N;;;0058;;0058
0079;LATIN SMALL LETTER Y;Ll;0;L;;;;;N;;;0059;;0059
007A;LATIN SMALL LETTER Z;Ll;0;L;;;;;N;;;005A;;005A
007B;LEFT CURLY BRACKET;Ps;0;ON;;;;;Y;OPENING CURLY BRACKET;;;;
007C;VERTICAL LINE;Sm;0;ON;;;;;N;VERTICAL BAR;;;;
007D;RIGHT CURLY BRACKET;Pe;0;ON;;;;;Y;CLOSING CURLY BRACKET;;;;
007E;TILDE;Sm;0;ON;;;;;N;;;;;
007F;<control>;Cc;0;BN;;;;;N;DELETE;;;;"""

BasicLatinBlockData="""0000..007F; Basic Latin"""


def UpdateUnicodeData():
	ParseCategoryTable(urlopen("http://www.unicode.org/Public/UNIDATA/UnicodeData.txt").read())
	ParseBlockTable(urlopen("http://www.unicode.org/Public/UNIDATA/Blocks.txt").read())
	f=file(os.path.join(os.path.dirname(__file__),"ucd_tables.pck"),'w')
	dump((CategoryTable,BlockTable),f)
	f.close()

try:
	f=file(os.path.join(os.path.dirname(__file__),"ucd_tables.pck"),'r')
	CategoryTable,BlockTable=load(f)
	f.close()
except IOError, msg:
	CategoryTable={}
	BlockTable={}
	print "Failed to load UCD Tables - call UpdateUnicodeData to create new tables"
	err,errValue,tb=exc_info()
	print_exception(err,errValue,None)
	print "Unicode functions restricted to Basic Latin (0000..007F)"
	ParseCategoryTable(BasicLatinCategoryData)		
	ParseBlockTable(BasicLatinBlockData)

	
	



