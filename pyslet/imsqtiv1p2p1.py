#! /usr/bin/env python
"""This module implements the QTI 1.2.1 specification defined by IMS GLC
"""


import pyslet.xml20081126 as xml
import pyslet.imsqtiv2p1 as qtiv2
import pyslet.imsmdv1p2p1 as imsmd

import string, codecs
import os.path, urllib

#IMSQTI_NAMESPACE="http://www.imsglobal.org/xsd/ims_qtiasiv1p2"
qti_comment='qticomment'
qti_item='item'
qti_questestinterop='questestinterop'

# Attribute definitions
# <!ENTITY % I_Ident " ident CDATA  #REQUIRED">
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
	pass


class QTIComment(QTIElement):
	XMLNAME=qti_comment

class QTICommentElement(QTIElement):
	"""Basic element to represent all QTI elements that can contain a comment"""
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.comment=None

	def GetChildren(self):
		if self.comment:
			return [self.comment]
		else:
			return []
			
	def QTIComment(self):
		if self.comment:
			child=self.comment
		else:
			child=QTIComment(self)
			self.comment=child
		return child


	
class QTIQuesTestInterop(QTICommentElement):
	"""<!ELEMENT questestinterop (qticomment? , (objectbank | assessment | (section | item)+))>"""
	
	XMLNAME=qti_questestinterop

	def __init__(self,parent):
		QTICommentElement.__init__(self,parent)
		self.objectBank=None
		self.assessment=None
		self.objectList=[]
	
	def GetChildren(self):
		children=QTICommentElement.GetChildren(self)
		if self.objectBank:
			children.append(self.objectBank)
		elif self.assessment:
			children.append(self.assessment)
		else:
			children=children+self.objectList
		return children

	def QTIItem(self):
		child=QTIItem(self)
		self.objectList.append(child)
		return child
		
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
				doc,lom,log=output[0]
				general=lom.LOMGeneral()
				description=general.LOMDescription().LangString()
				description.SetValue(self.comment.GetValue())
		return output


class QTIItem(QTICommentElement):
	"""
	<!ELEMENT item (qticomment? , duration? , itemmetadata? , objectives* , itemcontrol* , itemprecondition* , itempostcondition* , (itemrubric | rubric)* , presentation? , resprocessing* , itemproc_extension? , itemfeedback* , reference?)>

	<!ATTLIST item  maxattempts CDATA  #IMPLIED
		%I_Label;
		%I_Ident;
		%I_Title;
		xml:lang    CDATA  #IMPLIED >"""
	XMLNAME=qti_item

	def __init__(self,parent):
		QTICommentElement.__init__(self,parent)
		self.maxattempts=None
		self.label=None
		self.ident=None
		self.title=None
	
	def GetAttributes(self):
		attrs=QTICommentElement.GetAttributes(self)
		if self.maxattempts:
			attrs['maxattempts']=self.maxattempts
		if self.label:
			attrs['label']=self.label
		if self.ident:
			attrs['ident']=self.ident
		if self.title:
			attrs['title']=self.title

	def Set_maxattempts(self,value):
		self.maxattempts=value
		
	def Set_label(self,value):
		self.label=value
		
	def Set_ident(self,value):
		self.ident=value
		
	def Set_title(self,value):
		self.title=value
		
	def MigrateV2(self):
		"""Converts this item to QTI v2
		
		For details, see QTIQuesTestInterop.MigrateV2."""
		doc=qtiv2.QTIDocument(root=qtiv2.QTIAssessmentItem)
		item=doc.root
		lom=imsmd.LOM(None)
		log=[]
		value=self.ident
		newValue=qtiv2.MakeValidNCName(value)
		if value!=newValue:
			log.append("Warning: illegal NCName for ident: %s, replaced with: %s"%(value,newValue))
		identifier=newValue
		item.Set_identifier(identifier)
		value=self.title
		if value is None:
			value=identifier
		item.Set_title(value)
		if self.maxattempts is not None:
			log.append("Warning: maxattempts can not be controlled at item level, ignored: maxattempts='"+self.maxattempts+"'")
			log.append("Note: in future, maxattempts will probably be controllable at assessment or assessment section level")
		if self.label:
			item.Set_label(self.label)
		item.SetLang(self.GetLang())
		# A comment on an item is added as a description to the metadata
		general=lom.LOMGeneral()
		id=general.LOMIdentifier()
		#id.SetValue(None,self.ident)	
		id.SetValue(self.ident)	
		if self.comment:
			description=general.LOMDescription().LangString()
			description.SetValue(self.comment.GetValue())						
		return (doc, lom, log)
		
		

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

	classMap={}
		#qti_comment:QTIComment,
		#qti_item:QTIItem,
		#qti_questestinterop:QTIQuesTestInterop
		#}

	def MigrateV2(self,cp):
		"""Converts the contents of this document to QTI v2
		
		The output is stored into the content package passed in cp."""
		if isinstance(self.root,QTIQuesTestInterop):
			results=self.root.MigrateV2()
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
					# ** Add the log as an annotation in the metadata
					for logEntry in log:
						a=metadata.LOMAnnotation()
						description=a.LOMDescription()
						a.LangString(logEntry)						
					doc.AddToContentPackage(cp,metadata,dName)
		else:
			pass

xml.MapClassElements(QTIDocument.classMap,globals())
		
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

