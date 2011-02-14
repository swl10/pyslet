#! /usr/bin/env python
"""This module implements the QTI 1.2.1 specification defined by IMS GLC
"""


import pyslet.xml20081126 as xml
import pyslet.imsqtiv2p1 as qtiv2

import string, codecs
import os.path, urllib

#IMSQTI_NAMESPACE="http://www.imsglobal.org/xsd/ims_qtiasiv1p2"
qti_comment='qticomment'
qti_item='item'
qti_questestinterop='questestinterop'

# Attribute names

qti_ident='ident'
# <!ENTITY % I_Ident " ident CDATA  #REQUIRED">
qti_title='title'
# <!ENTITY % I_Title " title CDATA  #IMPLIED">


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
	"""<!ELEMENT questestinterop (qticomment? , (objectbank | assessment | (section | item)+))>"""
	
	XMLNAME=qti_questestinterop

	def __init__(self,parent):
		QTIElement.__init__(self,parent)
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
		elif isinstance(child,QTIComment):
			self.comment=child
		else:
			QTIElement.AddChild(self,child)

	def MigrateV2(self):
		"""Converts this element to QTI v2
		
		Returns a list of tuples of the form:
		( <QTIv2 Document>, <Metadata>, <List of Log Messages> ).
		
		One tuple is returned for each of the objects found. In QTIv2 there is
		no equivalent of QuesTestInterop.  The baseURI of each document is set
		from the baseURI of the QuesTestInterop element using the object
		identifier to derive a file name."""
		output=[]
		# ignore objectBank for the moment
		# ignore assessment for the moment
		for object in self.objectList:
			output.append(object.MigrateV2())
		if self.comment:
			if self.objectBank:
				# where to put the comment?
				pass
			elif self.assessment:
				if len(self.objectList)==0:
					# Add this comment as a metadata description on the assessment
					pass
			elif len(self.objectList)==1:
				# Add this comment to this object's metdata description
				pass
		return output


class QTIItem(QTIElement):
	"""
	<!ELEMENT item (qticomment? , duration? , itemmetadata? , objectives* , itemcontrol* , itemprecondition* , itempostcondition* , (itemrubric | rubric)* , presentation? , resprocessing* , itemproc_extension? , itemfeedback* , reference?)>

	<!ATTLIST item  maxattempts CDATA  #IMPLIED
		%I_Label;
		%I_Ident;
		%I_Title;
		xml:lang    CDATA  #IMPLIED >"""
	XMLNAME=qti_item

	def MigrateV2(self):
		"""Converts this item to QTI v2
		
		For details, see QTIQuesTestInterop.MigrateV2."""
		doc=qtiv2.QTIDocument(root=qtiv2.QTIAssessmentItem)
		item=doc.rootElement
		metadata=None
		log=[]
		value=self.GetAttribute(qti_ident)
		newValue=qtiv2.MakeValidNCName(value)
		if value!=newValue:
			log.append("Warning: illegal NCName for ident: %s, replaced with: %s"%(value,newValue))
		identifier=newValue
		item.SetIdentifier(identifier)			
		value=self.GetAttribute(qti_title)
		if value is None:
			value=identifier
		item.SetTitle(value)
		return (doc, metadata, log)
		
		
class QTIComment(QTIElement):
	XMLNAME=qti_comment


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
		qti_comment:QTIComment,
		qti_item:QTIItem,
		qti_questestinterop:QTIQuesTestInterop
		}

	def MigrateV2(self,cp):
		"""Converts the contents of this document to QTI v2
		
		The output is stored into the content package passed in cp."""
		if isinstance(self.rootElement,QTIQuesTestInterop):
			results=self.rootElement.MigrateV2()
			# list of tuples ( <QTIv2 Document>, <Metadata>, <Log Messages> )
			if results:
				# Make a directory to hold the files (makes it easier to find unique names for media files)
				if self.url.path:
					dName=urllib.url2pathname(self.url.path.split('/')[-1])
				else:
					dName="questestinterop"
				dName,ext=os.path.splitext(dName)
				dName=cp.GetUniqueFile(dName)
				for doc,metadata,log in results:
					doc.AddToContentPackage(cp,dName)
		else:
			pass
		

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
	application, declares a codec search function that fixes this issue."""
	codecs.register(CNBig5CodecSearch)