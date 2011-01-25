#! /usr/bin/env python
"""This module implements the QTI 1.2.1 specification defined by IMS GLC
"""


import pyslet.xml20081126 as xml

IMSQTI_NAMESPACE="http://www.imsglobal.org/xsd/ims_qtiasiv1p2"
qti_item=(IMSQTI_NAMESPACE,'item')
qti_questestinterop=(IMSQTI_NAMESPACE,'questestinterop')


class QTIElement(xml.XMLElement):
	"""Basic element to represent all QTI elements"""  
	def __init__(self,parent):
		xml.XMLElement.__init__(self,parent)
		self.SetXMLName((IMSQTI_NAMESPACE,None))


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


class QTIParser(xml.XMLParser):
	def __init__(self):
		"""In addition to adding our custom classes to the classMap for this parser we make
		two important changes to the parser.  Firstly, we set our QTI namespace as the default
		namespace to use for elements without an explicit namespace set.  Secondly, we turn
		off the parsing of external general entities to prevent a missing DTD causing the parse
		to fail.  This is a significant limitation as it is possible that some sophisticated
		users have used general entities to augment the specification or to define boiler-plate
		code.  If this causes problems then you can turn the setting back on again for
		specific instances of the parser that will be used with that type of data."""
		xml.XMLParser.__init__(self)
		self.parser.setFeature(xml.handler.feature_external_ges, False)
		self.defaultNS=IMSQTI_NAMESPACE
		self.classMap={
			qti_item:QTIItem,
			qti_questestinterop:QTIQuesTestInterop
			}
		