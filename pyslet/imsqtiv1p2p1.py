#! /usr/bin/env python
"""This module implements the QTI 1.2.1 specification defined by IMS GLC
"""


import pyslet.xml20081126 as xml
import pyslet.imsqtiv2p1 as qtiv2
import pyslet.imsmdv1p2p1 as imsmd

import string, codecs
import os.path, urllib

#IMSQTI_NAMESPACE="http://www.imsglobal.org/xsd/ims_qtiasiv1p2"

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
	XMLNAME='qticomment'

class QTICommentElement(QTIElement):
	"""Basic element to represent all QTI elements that can contain a comment"""
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.QTIComment=None

	def GetChildren(self):
		if self.QTIComment:
			return [self.QTIComment]
		else:
			return []

	
class QTIQuesTestInterop(QTICommentElement):
	"""<!ELEMENT questestinterop (qticomment? , (objectbank | assessment | (section | item)+))>"""
	
	XMLNAME='questestinterop'

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
		if self.QTIComment:
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
				description.SetValue(self.QTIComment.GetValue())
		return output


class QTIItem(QTICommentElement):
	"""
	<!ELEMENT item (qticomment?
		duration?
		itemmetadata?
		objectives*
		itemcontrol*
		itemprecondition*
		itempostcondition*
		(itemrubric | rubric)*
		presentation?
		resprocessing*
		itemproc_extension?
		itemfeedback*
		reference?)>

	<!ATTLIST item  maxattempts CDATA  #IMPLIED
		%I_Label;
		%I_Ident;
		%I_Title;
		xml:lang    CDATA  #IMPLIED >"""
	XMLNAME='item'
	XMLCONTENT=xml.XMLElementContent
	
	def __init__(self,parent):
		QTICommentElement.__init__(self,parent)
		self.maxattempts=None
		self.label=None
		self.ident=None
		self.title=None
		self.QTIDuration=None
		self.QTIItemMetadata=None
		self.QTIObjectives=[]
		self.QTIItemControl=[]
		self.QTIItemPrecondition=[]
		self.QTIItemPostcondition=[]
		self.rubric=[]
		self.QTIPresentation=None
		self.QTIResprocessing=[]
		self.QTIItemProcExtension=None
		self.QTIItemFeedback=[]
		self.QTIReference=None
		
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
	
	def GetChildren(self):
		children=QTIComment.GetChildren(self)
		OptionalAppend(children,self.QTIDuration)
		OptionalAppend(children,self.QTIItemMetadata)
		children=children+self.QITObjectives+self.QTIItemControl+self.QTIItemPrecondition+self.QTIPostCondition+self.rubric
		OptionalAppend(children,self.QTIPresentation)
		children=children+self.QTIResprocessing
		OptionalAppend(children,QTIItemProcExtension)
		children=children+self.QTIItemFeedback
		OptionalAppend(children,QTIReference)
		return children
	
	def MigrateV2(self):
		"""Converts this item to QTI v2
		
		For details, see QTIQuesTestInterop.MigrateV2."""
		doc=qtiv2.QTIDocument(root=qtiv2.QTIAssessmentItem)
		item=doc.root
		lom=imsmd.LOM(None)
		log=[]
		ident=qtiv2.MakeValidNCName(self.ident)
		if self.ident!=ident:
			log.append("Warning: illegal NCName for ident: %s, replaced with: %s"%(self.ident,ident))
		item.Set_identifier(ident)
		title=self.title
		if title is None:
			# may be specified in the metadata
			if self.QTIItemMetadata and self.QTIItemMetadata.QMDTitle:
				title=self.QTIItemMetadata.QMDTitle.GetValue()
			else:
				title=ident
		item.Set_title(title)
		if self.maxattempts is not None:
			log.append("Warning: maxattempts can not be controlled at item level, ignored: maxattempts='"+self.maxattempts+"'")
			log.append("Note: in future, maxattempts will probably be controllable at assessment or assessment section level")
		if self.label:
			item.Set_label(self.label)
		lang=self.GetLang()
		item.SetLang(lang)
		general=lom.LOMGeneral()
		id=general.LOMIdentifier()
		id.SetValue(self.ident)
		if self.title:
			title=general.ChildElement(imsmd.LOMTitle).LangString(self.title)
			if lang:
				title.SetLang(lang)
		if self.QTIItemMetadata and self.QTIItemMetadata.QMDTitle:
			title=self.QTIItemMetadata.QMDTitle.GetValue()
			mdLang=self.QTIItemMetadata.QMDTitle.ResolveLang()
			if self.title:
				# If we already have a title, then we add qmd_title as addition metadata
				# you may think qmd_title is a better choice than the title attribute
				# but qmd_title is an extension so the title attribute takes precedence
				mdTitle=general.LOMDescription().LangString(title)
			else:
				mdTitle=general.ChildElement(imsmd.LOMTitle).LangString(title)
			if mdLang:
				mdTitle.SetLang(mdLang)
		if self.QTIComment:
			# A comment on an item is added as a description to the metadata
			description=general.LOMDescription().LangString(self.QTIComment.GetValue())
		if self.QTIDuration:
			log.append("Warning: duration is currently outside the scope of version 2: ignored "+self.QTIDuration.GetValue())
		if self.QTIItemMetadata:
			self.QTIItemMetadata.MigrateV2(doc,lom,log)
			
		return (doc, lom, log)
		

class QTIDuration(QTIElement):
	XMLNAME='duration'

class QTIMetadata(QTIElement):
	XMLNAME='qtimetadata'
	
class QMDComputerScored(QTIElement):
	XMLNAME='qmd_computerscored'
	
class QMDFeedbackPermitted(QTIElement):
	XMLNAME='qmd_feedbackpermitted'
	
class QMDHintsPermitted(QTIElement):
	XMLNAME='qmd_hintspermitted'

class QMDItemType(QTIElement):
	XMLNAME='qmd_itemtype'

class QMDLevelOfDifficulty(QTIElement):
	"""<!ELEMENT qmd_levelofdifficulty (#PCDATA)>"""	
	XMLNAME='qmd_levelofdifficulty'

QMDLevelOfDifficultyMap={
	"pre-school":("pre-school",False), # value is outside LOM defined vocab
	"school":("school",True),
	"he/fe":("higher education",True),
	"vocational":("vocational",False), # value is outside LOM defined vocab
	"professional development":("training",True)
	}

QMDDifficultyMap={
	"very easy":1,
	"easy":1,
	"medium":1,
	"difficult":1,
	"very difficult":1
	}

class QMDMaximumScore(QTIElement):
	XMLNAME='qmd_maximumscore'

	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.value=None
	
	def GetValue(self):
		return self.value
	
	def SetValue(self,value):
		self.value=float(value)			
		QTIElement.SetValue(self,unicode(value))
		
	def GotChildren(self):
		self.value=float(QTIElement.GetValue(self).strip())


class QMDRenderingType(QTIElement):
	XMLNAME='qmd_renderingtype'

class QMDResponseType(QTIElement):
	XMLNAME='qmd_responsetype'

class QMDScoringPermitted(QTIElement):
	XMLNAME='qmd_scoringpermitted'

class QMDSolutionsPermitted(QTIElement):
	XMLNAME='qmd_solutionspermitted'

class QMDStatus(QTIElement):
	XMLNAME='qmd_status'

class QMDTimeDependence(QTIElement):
	XMLNAME='qmd_timedependence'

class QMDTimeLimit(QTIElement):
	XMLNAME='qmd_timelimit'

class QMDToolVendor(QTIElement):
	XMLNAME='qmd_toolvendor'

class QMDTopic(QTIElement):
	XMLNAME='qmd_topic'

class QMDWeighting(QTIElement):
	XMLNAME='qmd_weighting'

class QMDMaterial(QTIElement):
	XMLNAME='qmd_material'

class QMDTypeOfSolution(QTIElement):
	XMLNAME='qmd_typeofsolution'


class QMDAuthor(QTIElement):
	"""Not defined by QTI but seems to be in common use."""
	XMLNAME='qmd_author'
	
class QMDDescription(QTIElement):
	"""Not defined by QTI but seems to be in common use."""
	XMLNAME='qmd_description'
	
class QMDDomain(QTIElement):
	"""Not defined by QTI but seems to be in common use."""
	XMLNAME='qmd_domain'

class QMDKeywords(QTIElement):
	"""Not defined by QTI but seems to be in common use."""
	XMLNAME='qmd_keywords'

class QMDTitle(QTIElement):
	"""Not defined by QTI but seems to be in common use."""
	XMLNAME='qmd_title'
	
	
class QTIItemMetadata(QTIElement):
	"""
	<!ELEMENT itemmetadata (
		qtimetadata*
		qmd_computerscored?
		qmd_feedbackpermitted?
		qmd_hintspermitted?
		qmd_itemtype?
		qmd_levelofdifficulty?
		qmd_maximumscore?
		qmd_renderingtype*
		qmd_responsetype*
		qmd_scoringpermitted?
		qmd_solutionspermitted?
		qmd_status?
		qmd_timedependence?
		qmd_timelimit?
		qmd_toolvendor?
		qmd_topic?
		qmd_weighting?
		qmd_material*
		qmd_typeofsolution?
		)>
	"""
	XMLNAME='itemmetadata'
	XMLCONTENT=xml.XMLElementContent
	
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.QTIMetadata=[]
		self.QMDComputerScored=None
		self.QMDFeedbackPermitted=None
		self.QMDHintsPermitted=None
		self.QMDItemType=None
		self.QMDLevelOfDifficulty=None
		self.QMDMaximumScore=None
		self.QMDRenderingType=[]
		self.QMDResponseType=[]
		self.QMDScoringPermitted=None
		self.QMDSolutionsPermitted=None
		self.QMDStatus=None
		self.QMDTimeDependence=None
		self.QMDTimeLimit=None
		self.QMDToolVendor=None
		self.QMDTopic=None
		self.QMDWeighting=None
		self.QMDMaterial=[]
		self.QMDTypeOfSolution=None
		# Extensions in common use....
		self.QMDAuthor=[]
		self.QMDDescription=[]
		self.QMDDomain=[]
		self.QMDKeywords=[]
		self.QMDTitle=None
		
	def GetChildren(self):
		children=self.QTIMetadata
		OptionalAppend(children,self.QMDComputerScored)
		OptionalAppend(children,self.QMDFeedbackPermitted)
		OptionalAppend(children,self.QMDHintsPermitted)
		OptionalAppend(children,self.QMDItemType)
		OptionalAppend(children,self.QMDLevelOfDifficulty)
		OptionalAppend(children,self.QMDMaximumScore)
		children=children+self.QMDRenderingType+self.QMDResponseType
		OptionalAppend(children,self.QMDScoringPermitted)
		OptionalAppend(children,self.QMDSolutionsPermitted)
		OptionalAppend(children,self.QMDStatus)
		OptionalAppend(children,self.QMDTimeDependence)
		OptionalAppend(children,self.QMDTimeLimit)
		OptionalAppend(children,self.QMDToolVendor)
		OptionalAppend(children,self.QMDTopic)
		OptionalAppend(children,self.QMDWeighting)
		children=children+self.QMDMaterial
		OptionalAppend(children,self.QMDTypeOfSolution)
		children=children+self.QMDAuthor+self.QMDDescription+self.QMDDomain+self.QMDKeywords
		OptionalAppend(children,self.QMDTitle)
		return children
		
	def MigrateV2(self,doc,lom,log):
		if self.QMDLevelOfDifficulty:
			# IMS Definition says: The options are: "Pre-school", "School" or
			# "HE/FE", # "Vocational" and "Professional Development" so we bind
			# this value to the "Context" in LOM if one of the QTI or LOM
			# defined terms have been used, otherwise, we bind to Difficulty, as
			# this seems to be more common usage.
			value=self.QMDLevelOfDifficulty.GetValue().strip()
			context,lomFlag=QMDLevelOfDifficultyMap.get(value.lower(),(None,False))
			educational=lom.ChildElement(imsmd.LOMEducational)
			if context is None:
				# add value as difficulty
				difficulty,lomFlag=QMDDifficultyMap.get(value.lower(),(value,False))
				d=educational.ChildElement(imsmd.LOMDifficulty)
				if lomFlag:
					d.LRMSource.LangString.SetValue(imsmd.LOM_SOURCE)
				else:
					d.LRMSource.LangString.SetValue("None")					
				d.LRMSource.LangString.SetLang("x-none")
				d.LRMValue.LangString.SetValue(difficulty)
				d.LRMValue.LangString.SetLang("x-none")
			else:
				# add value as educational context
				c=educational.ChildElement(imsmd.LOMContext)
				if lomFlag:
					c.LRMSource.LangString.SetValue(imsmd.LOM_SOURCE)
				else:
					c.LRMSource.LangString.SetValue("None")					
				c.LRMSource.LangString.SetLang("x-none")
				c.LRMValue.LangString.SetValue(context)
				c.LRMValue.LangString.SetLang("x-none")
		warn=False
		if self.QMDTopic:
			lang=self.QMDTopic.ResolveLang()
			value=self.QMDTopic.GetValue().strip()
			description=lom.ChildElement(imsmd.LOMEducational).ChildElement(imsmd.LOMDescription).LangString(value)
			if lang:
				description.SetLang(lang)
		if len(self.QMDAuthor):
			if imsmd.vobject is None:
				log.append('Warning: qmd_author support disabled (vobject not installed)')
			else:
				for author in self.QMDAuthor:
					lifecycle=lom.ChildElement(imsmd.LOMLifecycle)
					contributor=lifecycle.ChildElement(imsmd.LOMContribute)
					role=contributor.LOMRole
					role.LRMSource.LangString.SetValue(imsmd.LOM_SOURCE)
					role.LRMSource.LangString.SetLang("x-none")
					role.LRMValue.LangString.SetValue("author")
					role.LRMValue.LangString.SetLang("x-none")
					names=author.GetValue().strip().split(',')
					for name in names:
						if not name.strip():
							continue
						vcard=imsmd.vobject.vCard()
						vcard.add('n')
						vcard.n.value=imsmd.vobject.vcard.Name(family=name,given='')
						vcard.add('fn')
						vcard.fn.value=name
						contributor.ChildElement(imsmd.LOMCEntity).LOMVCard.SetValue(vcard)		
		for description in self.QMDDescription:
			lang=description.ResolveLang()
			general=lom.ChildElement(imsmd.LOMGeneral)
			dValue=description.GetValue()
			genDescription=lom.ChildElement(imsmd.LOMGeneral).ChildElement(imsmd.LOMDescription).LangString(dValue)
			if lang:
				genDescription.SetLang(lang)
		for domain in self.QMDDomain:
			lang=domain.ResolveLang()
			general=lom.ChildElement(imsmd.LOMGeneral)
			kwValue=domain.GetValue().strip()
			if kwValue:
				kwContainer=general.ChildElement(imsmd.LOMKeyword).LangString(kwValue)
				# set the language of the kw
				if lang:
					kwContainer.SetLang(lang)
				if not warn:
					log.append("Warning: qmd_domain extension field will be added as LOM keyword")
					warn=True
		for kw in self.QMDKeywords:
			lang=kw.ResolveLang()
			general=lom.ChildElement(imsmd.LOMGeneral)
			values=string.split(kw.GetValue(),',')
			for value in values:
				kwValue=value.strip()
				if kwValue:
					kwContainer=general.ChildElement(imsmd.LOMKeyword).LangString(kwValue)
					# set the language of the kw
					if lang:
						kwContainer.SetLang(lang)

				
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
					if log:
						annotation=metadata.LOMAnnotation()
						annotationMsg=string.join(log,'\n')
						description=annotation.ChildElement(imsmd.LOMDescription)
						description.LangString(annotationMsg)
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

