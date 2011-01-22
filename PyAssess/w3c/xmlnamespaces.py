import xml
from re import compile

XMLNamespace="http://www.w3.org/XML/1998/namespace"

def IsNCNameChar(c):
	return c is not None and (xml.IsLetter(c) or xml.IsDigit(c) or
		c in ".-_" or xml.IsCombiningChar(c) or xml.IsExtender(c))

def CheckNCName(ncName):
	if ncName:
		if not (xml.IsLetter(ncName[0]) or ncName[0]=='_'):
			return 0
		for c in ncName[1:]:
			if not IsNCNameChar(c):
				return 0
		return 1
	return 0
