#! /usr/bin/env python
"""This module implements the QTI 2.1 specification defined by IMS GLC
"""

import pyslet.xml20081126 as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsdatatypes

import string
import os.path, urllib, urlparse

IMSQTI_NAMESPACE="http://www.imsglobal.org/xsd/imsqti_v2p1"
IMSQTI_SCHEMALOCATION="http://www.imsglobal.org/xsd/imsqti_v2p1.xsd"
IMSQTI_ITEM_RESOURCETYPE="imsqti_item_xmlv2p1"
XMLSCHEMA_NAMESPACE="http://www.w3.org/2001/XMLSchema-instance"

qti_assessmentItem=(IMSQTI_NAMESPACE,'assessmentItem')
qti_responseDeclaration=(IMSQTI_NAMESPACE,'responseDeclaration')

qti_adaptive='adaptive'
qti_identifier='identifier'
qti_timeDependent='timeDependent'
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

	def AddToCPResource(self,cp,resource,baseURI):
		"""Adds any linked files that exist on the local file system to the content package."""
		for child in self.GetChildren():
			if isinstance(child,QTIElement):
				child.AddToCPResource(cp,resource,uri)


class QTIAssessmentItem(QTIElement):
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.SetXMLName(qti_assessmentItem)
		self.declarations={}
		self.SetAdaptive(False)
		self.SetTimeDependent(False)
		
	def GetIdentifier(self):
		return self.attrs.get(qti_identifier,None)
		
	def SetIdentifier(self,identifier):
		QTIElement.SetAttribute(self,qti_identifier,identifier)
		
	def GetTitle(self):
		return self.attrs.get(qti_title,None)
		
	def SetTitle(self,title):
		QTIElement.SetAttribute(self,qti_title,title)

	def GetAdaptive(self):
		return xsdatatypes.DecodeBoolean(self.attrs.get(qti_adaptive,None))
		
	def SetAdaptive(self,adaptive):
		if adaptive is None:
			# required attribute
			raise ValueError
		else:
			QTIElement.SetAttribute(self,qti_adaptive,xsdatatypes.EncodeBoolean(adaptive))
		
	def GetTimeDependent(self):
		return xsdatatypes.DecodeBoolean(self.attrs.get(qti_timeDepedent,None))
		
	def SetTimeDependent(self,timeDependent):
		if timeDependent is None:
			# required attribute
			raise ValueError
		else:
			QTIElement.SetAttribute(self,qti_timeDependent,xsdatatypes.EncodeBoolean(timeDependent))
		
	def GetDeclarations(self):
		return self.declarations

	def GetChildren(self):
		children=[]
		vars=self.declarations.keys()
		vars.sort()
		for v in vars:
			children.append(self.declarations[v])
		return children
		
	def AddChild(self,child):
		if isinstance(child,QTIResponseDeclaration):
			self.declarations[child.identifier]=child
		else:
			QTIElement.AddChild(self,child)

	def AddToContentPackage(self,cp,dName=None):
		"""Adds a resource and associated files to the content package."""
		resourceID=cp.manifest.GetUniqueID(self.GetIdentifier())
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
		resource.SetEntryPoint(f)
		for child in self.GetChildren():
			if isinstance(child,QTIElement):
				child.AddToCPResource(cp,resource,uri)
		return uri
	
		

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
		self.SetNSPrefix(XMLSCHEMA_NAMESPACE,'xsi')
		if isinstance(self.rootElement,QTIElement):
			self.rootElement.SetAttribute((XMLSCHEMA_NAMESPACE,'schemaLocation'),IMSQTI_NAMESPACE+' '+IMSQTI_SCHEMALOCATION)
			
	def GetElementClass(self,name):
		return QTIDocument.classMap.get(name,QTIDocument.classMap.get((name[0],None),xmlns.XMLNSElement))

	classMap={
		qti_assessmentItem:QTIAssessmentItem,
		qti_responseDeclaration:QTIResponseDeclaration
		}

	def AddToContentPackage(self,cp,dName=None):
		"""Copies this QTI document into a content package and returns the resource ID used.
		
		An optional directory name can be specified in which to put the resource files."""
		if not isinstance(self.rootElement,QTIAssessmentItem):
			print self.rootElement
			raise TypeError
		# We call the elemement's AddToContentPackage method which returns the new base URI
		# of the document.
		baseURI=self.rootElement.AddToContentPackage(cp,dName)
		self.SetBase(baseURI)
		# Finish by writing out the document to the new baseURI
		self.Create()
