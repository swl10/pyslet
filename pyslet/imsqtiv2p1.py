#! /usr/bin/env python
"""This module implements the QTI 2.1 specification defined by IMS GLC
"""

import pyslet.xml20081126 as xml
import pyslet.xmlnames20091208 as xmlns

import string
import os.path, urllib, urlparse

IMSQTI_NAMESPACE="http://www.imsglobal.org/xsd/imsqti_v2p1"
IMSQTI_ITEM_RESOURCETYPE="imsqti_item_xmlv2p1"

qti_assessmentItem=(IMSQTI_NAMESPACE,'assessmentItem')
qti_responseDeclaration=(IMSQTI_NAMESPACE,'responseDeclaration')

qti_identifier='identifier'
qti_title='title'

def MakeValidNCName(name):
	"""This function takes a string that is supposed to match the production for
	NCName in XML and forces to to comply by replacing illegal characters with
	'_', except the ':' which is replaced with a hyphen for compatibility with
	previous versions of the QTI migraiton script.  If name starts with a valid
	name character but not a valid name start character, it is prefixed with '_'
	too."""
	if name:
		goodName=[]
		if not xmlns.IsNameStartChar(name[0]):
			goodName.append('_')
		elif name[0]==':':
			# Previous versions of the migrate script didn't catch this problem
			# as a result, we deviate from its broken behaviour or using '-'
			goodName.append('_')			
		for c in name:
			if c==':':
				goodName.append('-')
			elif xmlns.IsNameChar(c):
				goodName.append(c)
			else:
				goodName.append('_')
		return string.join(goodName,'')
	else:
		return '_'

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
		
	def GetIdentifier(self):
		return self.attrs.get(qti_identifier,None)
		
	def SetIdentifier(self,identifier):
		QTIElement.SetAttribute(self,qti_identifier,identifier)
		
	def GetTitle(self):
		return self.attrs.get(qti_title,None)
		
	def SetTitle(self,title):
		QTIElement.SetAttribute(self,qti_title,title)
		
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

	def AddToContentPackage(self,cp,dName=None):
		"""Adds this QTI document to a content package and returns the resource ID used.
		
		An optional directory name can be specified in which to put the resource files."""
		if not isinstance(self.rootElement,QTIAssessmentItem):
			print self.rootElement
			raise TypeError
		# Add doc to the content package
		resourceID=cp.manifest.GetUniqueID(self.rootElement.GetIdentifier())
		resource=cp.manifest.rootElement.resources.CPResource(resourceID,IMSQTI_ITEM_RESOURCETYPE)
		# Security alert: we're leaning heavily on MackValidNCName assuming it returns a good file name
		fPath=MakeValidNCName(resourceID).encode('utf-8')+'.xml'
		if dName:
			fPath=os.path.join(dName,fPath)
		fPath=cp.GetUniqueFile(fPath)
		# This will be the path to the file in the package
		fullPath=os.path.join(cp.dPath,fPath)
		uri='file://'+urllib.pathname2url(fullPath)
		# Turn this file path into a relative URL in the context of the new resource
		href=resource.RelativeURI(uri)
		f=cp.CPFile(resource,href)
		# To do....
		# Change the base of doc to the new location
		resource.SetHREF(href)
		# Create CPFile's and copy all the local media/linked files, fixing up links etc.
		# Write doc out into the package		