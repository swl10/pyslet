#! /usr/bin/env python
"""This module implements the QTI 2.1 specification defined by IMS GLC
"""

import pyslet.xml20081126 as xml

IMSQTI_NAMESPACE="http://www.imsglobal.org/xsd/imsqti_v2p1"
qti_assessmentItem=(IMSQTI_NAMESPACE,'assessmentItem')
qti_responseDeclaration=(IMSQTI_NAMESPACE,'responseDeclaration')


class QTIElement(xml.XMLElement):
	"""Basic element to represent all QTI elements"""  
	def __init__(self,parent):
		xml.XMLElement.__init__(self,parent)
		self.SetXMLName((IMSQTI_NAMESPACE,None))


class QTIAssessmentItem(QTIElement):
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.SetXMLName(qti_assessmentItem)
		self.declarations={}
		
	def GetDeclarations(self):
		return self.declarations

	def AddChild(self,child):
		if isinstance(child,QTIResponseDeclaration):
			self.declarations[child.identifier]=child
		else:
			QTIElement.AddChild(self,child)


class QTIResponseDeclaration(QTIElement):
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.SetXMLName(qti_responseDeclaration)
		self.identifier=None
	
	def SetAttribute(self,name,value):
		if name=='identifier':
			self.identifier=value
		else:
			QTIElement.SetAttribute(self,name,value)

	
class QTIItem(QTIElement):
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.SetXMLName(qti_item)


class QTIParser(xml.XMLParser):
	def __init__(self):
		""""""
		xml.XMLParser.__init__(self)
		self.defaultNS=IMSQTI_NAMESPACE
		self.classMap={
			qti_assessmentItem:QTIAssessmentItem,
			qti_responseDeclaration:QTIResponseDeclaration
			}
		