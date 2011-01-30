#! /usr/bin/env python
"""This module implements the QTI 2.1 specification defined by IMS GLC
"""

import pyslet.xmlnames20091208 as xmlns

IMSQTI_NAMESPACE="http://www.imsglobal.org/xsd/imsqti_v2p1"
qti_assessmentItem=(IMSQTI_NAMESPACE,'assessmentItem')
qti_responseDeclaration=(IMSQTI_NAMESPACE,'responseDeclaration')


class QTIElement(xmlns.XMLNSElement):
	"""Basic element to represent all QTI elements"""  
	def __init__(self,parent):
		xmlns.XMLElement.__init__(self,parent)
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


class QTIDocument(xmlns.XMLNSDocument):
	def __init__(self,**args):
		""""""
		xmlns.XMLNSDocument.__init__(self,defaultNS=IMSQTI_NAMESPACE,**args)

	def GetElementClass(self,name):
		return QTIDocument.classMap.get(name,QTIDocument.classMap.get((name[0],None),xmlns.XMLNSElement))

	classMap={
		qti_assessmentItem:QTIAssessmentItem,
		qti_responseDeclaration:QTIResponseDeclaration
		}
