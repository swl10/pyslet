#! /usr/bin/env python
"""This module implements the QTI 1.2.1 specification defined by IMS GLC
"""


import pyslet.xml20081126 as xml
import string, codecs

#IMSQTI_NAMESPACE="http://www.imsglobal.org/xsd/ims_qtiasiv1p2"
qti_item='item'
qti_questestinterop='questestinterop'


def MakeValidName(name):
	"""This function takes a string that is supposed to match the
	production for Name in XML and forces to to comply by replacing
	illegal characters with '_'.  If name starts with a valid name
	character but not a valid name start character, it is prefixed
	with '_' too."""
	if name:
		goodName=[]
		if not xml.IsNameStartChar(name[0]):
			goodName.append('_')
		for c in name:
			if xml.IsNameChar(c):
				goodName.append(c)
			else:
				goodName.append('_')
		return string.join(goodName,'')
	else:
		return '_'


class QTIElement(xml.XMLElement):
	"""Basic element to represent all QTI elements"""  
	def __init__(self,parent):
		xml.XMLElement.__init__(self,parent)


class QTIQuesTestInterop(QTIElement):
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.SetXMLName(qti_questestinterop)
		self.comment=None
		self.objectBank=None
		self.assessment=None
		self.objectList=[]
		
	def GetComment(self):
		return self.comment

	def GetObjectBank(self):
		return self.objectBank

	def GetAssessment(self):
		return self.assessment

	def GetObjectList(self):
		return self.objectList

	def AddChild(self,child):
		if isinstance(child,QTIItem):
			self.objectList.append(child)
		else:
			QTIElement.AddChild(self,child)


class QTIItem(QTIElement):
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.SetXMLName(qti_item)


class QTIDocument(xml.XMLDocument):
	def __init__(self,**args):
		"""We turn off the parsing of external general entities to prevent a
		missing DTD causing the parse to fail.  This is a significant limitation
		as it is possible that some sophisticated users have used general
		entities to augment the specification or to define boiler-plate code. 
		If this causes problems then you can turn the setting back on again for
		specific instances of the parser that will be used with that type of
		data."""
		xml.XMLDocument.__init__(self,**args)
		self.parser.setFeature(xml.handler.feature_external_ges, False)

	def GetElementClass(self,name):
		return QTIDocument.classMap.get(name,QTIDocument.classMap.get(None,xml.XMLElement))

	classMap={
		qti_item:QTIItem,
		qti_questestinterop:QTIQuesTestInterop
		}


try:
	BIG5=codecs.lookup('big5')
except LookupError:
	BIG5=None

# Obscure code alert
def CNBig5CodecSearch(name):
	if name=="cn-big5":
		return BIG5
	else:
		return None

def FixupCNBig5():
	"""The example files that are distributed with the QTI specification contain
	a set of Chinese examples encoded using big5.  However, the xml declarations
	on these files refer to the charset as "CN-BIG5" and this causes errors when
	parsing them as this is a non-standard way of refering to big5.  This
	function, which you should only call once (if at all) within your
	application, declares a codec search function that fixes this issues."""
	codecs.register(CNBig5CodecSearch)