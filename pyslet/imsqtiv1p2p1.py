#! /usr/bin/env python
"""This module implements the QTI 1.2.1 specification defined by IMS GLC
"""


import pyslet.xml20081126 as xml
import pyslet.imsqtiv2p1 as qtiv2
import pyslet.imsmdv1p2p1 as imsmd

import string, codecs
import os.path, urllib

#IMSQTI_NAMESPACE="http://www.imsglobal.org/xsd/ims_qtiasiv1p2"
QTI_SOURCE='QTIv1'


# Attribute definitions
# <!ENTITY % I_EntityRef " entityref ENTITY  #IMPLIED">
# <!ENTITY % I_Ident " ident CDATA  #REQUIRED">
# <!ENTITY % I_Title " title CDATA  #IMPLIED">
# <!ENTITY % I_Uri " uri CDATA  #IMPLIED">

class QTIError(Exception): pass
class QTIUnimplementedError(QTIError): pass

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

def ParseYesNo(src):
	return src.strip().lower()=='yes'

def FormatYesNo(value):
	if value:
		return 'Yes'
	else:
		return 'No'

def ParseInteger(src):
	try:
		return int(src)
	except:
		return None

def FormatInteger(value):
	return "%i"%value

		
class QTIElement(xml.XMLElement):
	"""Basic element to represent all QTI elements"""
	
	def DeclareMetadata(self,label,entry,definition=None):
		"""Declares a piece of metadata associated with the element.
		
		Most QTIElements will be contained by some type of metadata container
		that collects metadata in a format suitable for easy lookup and export
		to other metadata formats.  The default implementation simply passes the
		call to the parent QTIElement or ignores the definition"""
		if isinstance(self.parent,QTIElement):
			self.parent.DeclareMetadata(label,entry,definition)
		else:
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
		self.QTIObjectBank=None
		self.QTIAssessment=None
		self.objectList=[]
	
	def GetChildren(self):
		children=QTICommentElement.GetChildren(self)
		if self.QTIObjectBank:
			children.append(self.QTIObjectBank)
		elif self.QTIAssessment:
			children.append(self.QTIAssessment)
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
		# ignore QTIObjectBank for the moment
		# ignore QTIAssessment for the moment
		if self.QTIAssessment:
			self.QTIAssessment.MigrateV2(output)
		for object in self.objectList:
			object.MigrateV2(output)
		if self.QTIComment:
			if self.QTIObjectBank:
				# where to put the comment?
				pass
			elif self.QTIAssessment:
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


class QTIAssessment(QTICommentElement):
	"""Represents the assessment element.
	
	<!ELEMENT assessment (qticomment? ,
		duration? ,
		qtimetadata* ,
		objectives* ,
		assessmentcontrol* ,
		rubric* ,
		presentation_material? ,
		outcomes_processing* ,
		assessproc_extension? ,
		assessfeedback* ,
		selection_ordering? ,
		reference? ,
		(sectionref | section)+
		)>
	
	<!ATTLIST assessment  %I_Ident;
						   %I_Title;
						   xml:lang CDATA  #IMPLIED >
	"""
	XMLNAME="assessment"
	XMLCONTENT=xml.XMLElementContent
	
	def __init__(self,parent):
		QTICommentElement.__init__(self,parent)
		self.ident=None
		self.title=None
		self.QTIDuration=None
		self.QTIMetadata=[]
		self.QTIObjectives=[]
		self.QTIAssessmentControl=[]
		self.QTIRubric=[]
		self.QTIPresentationMaterial=None
		self.QTIOutcomesProcessing=[]
		self.QTIAssessProcExtension=None
		self.QTIAssessFeedback=[]
		self.QTISelectionOrdering=None
		self.QTIReference=None
		self.objectList=[]
		
	def GetAttributes(self):
		attrs=QTICommentElement.GetAttributes(self)
		if self.ident:
			attrs['ident']=self.ident
		if self.title:
			attrs['title']=self.title
		return attrs
		
	def Set_ident(self,value):
		self.ident=value
		
	def Set_title(self,value):
		self.title=value
	
	def QTISectionRef(self):
		child=QTISectionRef(self)
		self.objectList.append(child)
		return child
		
	def QTISection(self):
		child=QTISection(self)
		self.objectList.append(child)
		return child
		
	def GetChildren(self):
		children=QTIComment.GetChildren(self)
		children=children+self.QTIMetadata+self.QTIObjectives+self.QTIAssessmentControl+self.QTIRubric
		xml.OptionalAppend(children,self.QTIPresentationMaterial)
		children=children+QTIOutcomesProcessing
		xml.OptionalAppend(children,self.QTIAssessProcExtension)
		children=children+self.QTIAssessFeedback
		xml.OptionalAppend(children,self.QTISelectionOrdering)
		xml.OptionalAppend(children,self.QTIReference)
		return children+self.objectList

	def MigrateV2(self,output):
		"""Converts this assessment to QTI v2
		
		For details, see QTIQuesTestInterop.MigrateV2."""
		for object in self.objectList:
			object.MigrateV2(output)


class QTISection(QTICommentElement):
	"""Represents section element.
	<!ELEMENT section (qticomment? ,
		duration? ,
		qtimetadata* ,
		objectives* ,
		sectioncontrol* ,
		sectionprecondition* ,
		sectionpostcondition* ,
		rubric* ,
		presentation_material? ,
		outcomes_processing* ,
		sectionproc_extension? ,
		sectionfeedback* ,
		selection_ordering? ,
		reference? ,
		(itemref | item | sectionref | section)*
		)>
	
	<!ATTLIST section  %I_Ident;
						%I_Title;
						xml:lang CDATA  #IMPLIED >
	"""
	XMLNAME="section"
	XMLCONTENT=xml.XMLElementContent
	
	def __init__(self,parent):
		QTICommentElement.__init__(self,parent)
		self.ident=None
		self.title=None
		self.QTIDuration=None
		self.QTIMetadata=[]
		self.QTIObjectives=[]
		self.QTISectionControl=[]
		self.QTISectionPrecondition=[]
		self.QTISectionPostcondition=[]
		self.QTIRubric=[]
		self.QTIPresentationMaterial=None
		self.QTIOutcomesProcessing=[]
		self.QTISectionProcExtension=None
		self.QTISectionFeedback=[]
		self.QTISelectionOrdering=None
		self.QTIReference=None
		self.objectList=[]
		
	def GetAttributes(self):
		attrs=QTICommentElement.GetAttributes(self)
		if self.ident:
			attrs['ident']=self.ident
		if self.title:
			attrs['title']=self.title
		return attrs
		
	def Set_ident(self,value):
		self.ident=value
		
	def Set_title(self,value):
		self.title=value
	
	def QTIItemRef(self):
		child=QTIItemRef(self)
		self.objectList.append(child)
		return child
		
	def QTIItem(self):
		child=QTIItem(self)
		self.objectList.append(child)
		return child
		
	def QTISectionRef(self):
		child=QTISectionRef(self)
		self.objectList.append(child)
		return child
		
	def QTISection(self):
		child=QTISection(self)
		self.objectList.append(child)
		return child
		
	def GetChildren(self):
		children=QTIComment.GetChildren(self)
		children=children+self.QTIMetadata+self.QTIObjectives+self.QTISectionControl+self.QTISectionPrecondition+self.QTISectionPostcondition+self.QTIRubric
		xml.OptionalAppend(children,self.QTIPresentationMaterial)
		children=children+QTIOutcomesProcessing
		xml.OptionalAppend(children,self.QTISectionProcExtension)
		children=children+self.QTISectionFeedback
		xml.OptionalAppend(children,self.QTISelectionOrdering)
		xml.OptionalAppend(children,self.QTIReference)
		return children+self.objectList

	def MigrateV2(self,output):
		"""Converts this section to QTI v2
		
		For details, see QTIQuesTestInterop.MigrateV2."""
		for object in self.objectList:
			object.MigrateV2(output)
	
	
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
		self.QTIRubric=[]
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
		return attrs
		
	def Set_maxattempts(self,value):
		self.maxattempts=value
		
	def Set_label(self,value):
		self.label=value
		
	def Set_ident(self,value):
		self.ident=value
		
	def Set_title(self,value):
		self.title=value
	
	def QTIItemRubric(self):
		"""itemrubric is deprecated in favour of rubric."""
		child=QTIItemRubric(self)
		self.QTIRubric.append(child)
		return child
		
	def GetChildren(self):
		children=QTIComment.GetChildren(self)
		xml.OptionalAppend(children,self.QTIDuration)
		xml.OptionalAppend(children,self.QTIItemMetadata)
		children=children+self.QITObjectives+self.QTIItemControl+self.QTIItemPrecondition+self.QTIPostCondition+self.QTIRubric
		xml.OptionalAppend(children,self.QTIPresentation)
		children=children+self.QTIResprocessing
		xml.OptionalAppend(children,self.QTIItemProcExtension)
		children=children+self.QTIItemFeedback
		xml.OptionalAppend(children,self.QTIReference)
		return children
	
	def MigrateV2(self,output):
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
		# may be specified in the metadata
		if self.QTIItemMetadata:
			mdTitles=self.QTIItemMetadata.metadata.get('title',())
		else:
			mdTitles=()
		if title:
			item.Set_title(title)
		elif mdTitles:
			item.Set_title(mdTitles[0][0])
		else:
			item.Set_title(ident)
		if self.maxattempts is not None:
			log.append("Warning: maxattempts can not be controlled at item level, ignored: maxattempts='"+self.maxattempts+"'")
		if self.label:
			item.Set_label(self.label)
		lang=self.GetLang()
		item.SetLang(lang)
		general=lom.LOMGeneral()
		id=general.LOMIdentifier()
		id.SetValue(self.ident)
		if title:
			lomTitle=general.ChildElement(imsmd.LOMTitle).LangString(title)
			if lang:
				lomTitle.SetLang(lang)
		if mdTitles:
			if title:
				# If we already have a title, then we have to add qmd_title as description metadata
				# you may think qmd_title is a better choice than the title attribute
				# but qmd_title is an extension so the title attribute takes precedence
				i=0
			else:
				lomTitle=general.ChildElement(imsmd.LOMTitle).LangString(mdTitles[0][0])
				lang=mdTitles[0][1].ResolveLang()
				if lang:
					lomTitle.SetLang(lang)
				i=1
			for mdTitle in mdTitles[i:]:
				lomTitle=general.LOMDescription().LangString(mdTitle[0])
				mdLang=mdTitle[1].ResolveLang()
				if mdLang:
					lomTitle.SetLang(mdLang)
		if self.QTIComment:
			# A comment on an item is added as a description to the metadata
			description=general.LOMDescription().LangString(self.QTIComment.GetValue())
		if self.QTIDuration:
			log.append("Warning: duration is currently outside the scope of version 2: ignored "+self.QTIDuration.GetValue())
		if self.QTIItemMetadata:
			self.QTIItemMetadata.MigrateV2(doc,lom,log)
		for objective in self.QTIObjectives:
			if objective.view.lower()!='all':
				objective.MigrateV2(item,log)
			else:
				objective.LRMMigrateObjectives(lom,log)
		if self.QTIItemControl:
			log.append("Warning: itemcontrol is currently outside the scope of version 2")
		for rubric in self.QTIRubric:
			rubric.MigrateV2(item,log)
		if self.QTIPresentation:
			self.QTIPresentation.MigrateV2(item,log)
		output.append((doc, lom, log))
		

class QTIDuration(QTIElement):
	XMLNAME='duration'

class QTIMetadata(QTIElement):
	"""
	<!ELEMENT qtimetadata (vocabulary? , qtimetadatafield+)>
	"""
	XMLNAME='qtimetadata'
	XMLCONTENT=xml.XMLElementContent
	
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.QTIVocabulary=None
		self.QTIMetadataField=[]
	
	def GetChildren(self):
		children=[]
		xml.OptionalAppend(children,self.QTIVocabulary)
		return children+self.QTIMetadataField+QTIElement.GetChildren(self)

class QTIVocabulary(QTIElement):
	"""
	<!ELEMENT vocabulary (#PCDATA)>

	<!ATTLIST vocabulary  %I_Uri;
		%I_EntityRef;
		vocab_type  CDATA  #IMPLIED >
	"""
	XMLNAME="vocabulary"

	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.uri=None
		self.entityRef=None
		self.vocabType=None
	
	def GetAttributes(self):
		attrs=QTIElement.GetAttributes(self)
		if self.uri:
			attrs['uri']=self.uri
		if self.entityRef:
			attrs['entityref']=self.entityRef
		if self.vocabType:
			attrs['vocab_type']=self.vocabType
		return attrs
		
	def Set_uri(self,value):
		self.uri=value
		
	def Set_entityref(self,value):
		self.entityRef=value
		
	def Set_vocab_type(self,value):
		self.vocabType=value


class QTIMetadataField(QTIElement):
	"""
	<!ELEMENT qtimetadatafield (fieldlabel , fieldentry)>

	<!ATTLIST qtimetadatafield  xml:lang CDATA  #IMPLIED >
	"""
	XMLNAME='qtimetadatafield'
	XMLCONTENT=xml.XMLElementContent
	
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.QTIFieldLabel=QTIFieldLabel(self)
		self.QTIFieldEntry=QTIFieldEntry(self)
	
	def GetChildren(self):
		return [self.QTIFieldLabel,self.QTIFieldEntry]
	
	def GotChildren(self):
		label=self.QTIFieldLabel.GetValue()
		label={'marks':'maximumscore',
			'qmd_marks':'maximumscore',
			'name':'title',
			'qmd_name':'title',
			'syllabusarea':'topic',
			'qmd_syllabusarea':'topic',
			'item type':'itemtype',
			'question type':'itemtype',
			'qmd_layoutstatus':'status',
			'layoutstatus':'status'}.get(label,label)
		# Still need to handle creator and owner	
		self.DeclareMetadata(label,self.QTIFieldEntry.GetValue(),self)
		
class QTIFieldLabel(QTIElement):
	XMLNAME="fieldlabel"

class QTIFieldEntry(QTIElement):
	XMLNAME="fieldentry"

class QMDMetadataElement(QTIElement):
	"""Abstract class to represent old-style qmd_ tags"""
	
	def GotChildren(self):
		self.DeclareMetadata(self.GetXMLName(),self.GetValue(),self)
		
class QMDComputerScored(QMDMetadataElement):
	XMLNAME='qmd_computerscored'
	
class QMDFeedbackPermitted(QMDMetadataElement):
	XMLNAME='qmd_feedbackpermitted'
	
class QMDHintsPermitted(QMDMetadataElement):
	XMLNAME='qmd_hintspermitted'

class QMDItemType(QMDMetadataElement):
	XMLNAME='qmd_itemtype'

class QMDLevelOfDifficulty(QMDMetadataElement):
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

class QMDMaximumScore(QMDMetadataElement):
	XMLNAME='qmd_maximumscore'

class QMDRenderingType(QMDMetadataElement):
	XMLNAME='qmd_renderingtype'

class QMDResponseType(QMDMetadataElement):
	XMLNAME='qmd_responsetype'

class QMDScoringPermitted(QMDMetadataElement):
	XMLNAME='qmd_scoringpermitted'

class QMDSolutionsPermitted(QMDMetadataElement):
	XMLNAME='qmd_solutionspermitted'

QMDStatusSourceMap={
	'draft':imsmd.LOM_SOURCE,
	'final':imsmd.LOM_SOURCE,
	'revised':imsmd.LOM_SOURCE,
	'unavailable':imsmd.LOM_SOURCE,
	'experimental':QTI_SOURCE,
	'normal':QTI_SOURCE,
	'retired':QTI_SOURCE
	}

class QMDStatus(QMDMetadataElement):
	XMLNAME='qmd_status'

class QMDTimeDependence(QMDMetadataElement):
	XMLNAME='qmd_timedependence'

class QMDTimeLimit(QMDMetadataElement):
	XMLNAME='qmd_timelimit'

class QMDToolVendor(QMDMetadataElement):
	XMLNAME='qmd_toolvendor'
		
class QMDTopic(QMDMetadataElement):
	XMLNAME='qmd_topic'

class QMDWeighting(QMDMetadataElement):
	XMLNAME='qmd_weighting'

class QMDMaterial(QMDMetadataElement):
	XMLNAME='qmd_material'

class QMDTypeOfSolution(QMDMetadataElement):
	XMLNAME='qmd_typeofsolution'


class QMDAuthor(QMDMetadataElement):
	"""Not defined by QTI but seems to be in common use."""
	XMLNAME='qmd_author'

class QMDDescription(QMDMetadataElement):
	"""Not defined by QTI but seems to be in common use."""
	XMLNAME='qmd_description'
	
class QMDDomain(QMDMetadataElement):
	"""Not defined by QTI but seems to be in common use."""
	XMLNAME='qmd_domain'

class QMDKeywords(QMDMetadataElement):
	"""Not defined by QTI but seems to be in common use."""
	XMLNAME='qmd_keywords'

class QMDOrganization(QMDMetadataElement):
	"""Not defined by QTI but seems to be in common use."""
	XMLNAME='qmd_organization'

class QMDTitle(QMDMetadataElement):
	"""Not defined by QTI but seems to be in common use."""
	XMLNAME='qmd_title'
	

class QTIMetadataContainer(QTIElement):
	"""An abstract class used to hold dictionaries of metadata.
	
	There is a single dictionary maintained to hold all metadata values, each
	value is a list of tuples of the form (value string, defining element).
	Values are keyed on the field label or tag name with any leading qmd_ prefix
	removed."""
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.metadata={}

	def DeclareMetadata(self,label,entry,definition=None):
		label=label.lower()
		if label[:4]=="qmd_":
			label=label[4:]
		if not self.metadata.has_key(label):
			self.metadata[label]=[]
		self.metadata[label].append((entry,definition))


class QTIItemMetadata(QTIMetadataContainer):
	"""Represents the QTIItemMetadata element.
	
	This element contains more structure than is in common use, at the moment we
	represent this structure directly and automaticaly conform output to it,
	adding extension elements at the end.  In the future we might be more
	generous and allow input *and* output of elements in any sequence and
	provide separate methods for conforming these elements.
	
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
		QTIMetadataContainer.__init__(self,parent)
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
		self.QMDOrganization=[]
		self.QMDTitle=None
		
	def GetChildren(self):
		children=self.QTIMetadata
		xml.OptionalAppend(children,self.QMDComputerScored)
		xml.OptionalAppend(children,self.QMDFeedbackPermitted)
		xml.OptionalAppend(children,self.QMDHintsPermitted)
		xml.OptionalAppend(children,self.QMDItemType)
		xml.OptionalAppend(children,self.QMDLevelOfDifficulty)
		xml.OptionalAppend(children,self.QMDMaximumScore)
		children=children+self.QMDRenderingType+self.QMDResponseType
		xml.OptionalAppend(children,self.QMDScoringPermitted)
		xml.OptionalAppend(children,self.QMDSolutionsPermitted)
		xml.OptionalAppend(children,self.QMDStatus)
		xml.OptionalAppend(children,self.QMDTimeDependence)
		xml.OptionalAppend(children,self.QMDTimeLimit)
		xml.OptionalAppend(children,self.QMDToolVendor)
		xml.OptionalAppend(children,self.QMDTopic)
		xml.OptionalAppend(children,self.QMDWeighting)
		children=children+self.QMDMaterial
		xml.OptionalAppend(children,self.QMDTypeOfSolution)
		children=children+self.QMDAuthor+self.QMDDescription+self.QMDDomain+self.QMDKeywords+self.QMDOrganization
		xml.OptionalAppend(children,self.QMDTitle)
		return children+QTIMetadataContainer.GetChildren(self)
	
	def LRMMigrateLevelOfDifficulty(self,lom,log):
		difficulty=self.metadata.get('levelofdifficulty',())
		for value,definition in difficulty:
			# IMS Definition says: The options are: "Pre-school", "School" or
			# "HE/FE", # "Vocational" and "Professional Development" so we bind
			# this value to the "Context" in LOM if one of the QTI or LOM
			# defined terms have been used, otherwise, we bind to Difficulty, as
			# this seems to be more common usage.
			context,lomFlag=QMDLevelOfDifficultyMap.get(value.lower(),(None,False))
			educational=lom.ChildElement(imsmd.LOMEducational)
			if context is None:
				# add value as difficulty
				value,lomFlag=QMDDifficultyMap.get(value.lower(),(value,False))
				d=educational.ChildElement(imsmd.LOMDifficulty)
				if lomFlag:
					d.LRMSource.LangString.SetValue(imsmd.LOM_SOURCE)
				else:
					d.LRMSource.LangString.SetValue(imsmd.LOM_UNKNOWNSOURCE)					
				d.LRMSource.LangString.SetLang("x-none")
				d.LRMValue.LangString.SetValue(value)
				d.LRMValue.LangString.SetLang("x-none")
			else:
				# add value as educational context
				c=educational.ChildElement(imsmd.LOMContext)
				if lomFlag:
					c.LRMSource.LangString.SetValue(imsmd.LOM_SOURCE)
				else:
					c.LRMSource.LangString.SetValue(imsmd.LOM_UNKNOWNSOURCE)					
				c.LRMSource.LangString.SetLang("x-none")
				c.LRMValue.LangString.SetValue(context)
				c.LRMValue.LangString.SetLang("x-none")
	
	def LRMMigrateStatus(self,lom,log):
		status=self.metadata.get('status',())
		for value,definition in status:
			s=lom.ChildElement(imsmd.LOMLifecycle).ChildElement(imsmd.LOMStatus)
			value=value.lower()
			source=QMDStatusSourceMap.get(value,imsmd.LOM_UNKNOWNSOURCE)
			s.LRMSource.LangString.SetValue(source)
			s.LRMSource.LangString.SetLang("x-none")
			s.LRMValue.LangString.SetValue(value)
			s.LRMValue.LangString.SetLang("x-none")
	
	def LRMMigrateTopic(self,lom,log):
		topics=self.metadata.get('topic',())
		for value,definition in topics:
			lang=definition.ResolveLang()
			value=value.strip()
			description=lom.ChildElement(imsmd.LOMEducational).ChildElement(imsmd.LOMDescription)
			description.AddString(lang,value)
	
	def LRMMigrateContributor(self,fieldName,lomRole,lom,log):
		contributors=self.metadata.get(fieldName,())
		if contributors:
			if imsmd.vobject is None:
				log.append('Warning: qmd_%s support disabled (vobject not installed)'%fieldName)
			else:
				for value,definition in contributors:
					lifecycle=lom.ChildElement(imsmd.LOMLifecycle)
					contributor=lifecycle.ChildElement(imsmd.LOMContribute)
					role=contributor.LOMRole
					role.LRMSource.LangString.SetValue(imsmd.LOM_SOURCE)
					role.LRMSource.LangString.SetLang("x-none")
					role.LRMValue.LangString.SetValue(lomRole)
					role.LRMValue.LangString.SetLang("x-none")
					names=value.strip().split(',')
					for name in names:
						if not name.strip():
							continue
						vcard=imsmd.vobject.vCard()
						vcard.add('n')
						vcard.n.value=imsmd.vobject.vcard.Name(family=name,given='')
						vcard.add('fn')
						vcard.fn.value=name.strip()
						contributor.ChildElement(imsmd.LOMCEntity).LOMVCard.SetValue(vcard)	
	
	def LRMMigrateDescription(self,lom,log):
		descriptions=self.metadata.get('description',())
		for value,definition in descriptions:
			lang=definition.ResolveLang()
			genDescription=lom.ChildElement(imsmd.LOMGeneral).ChildElement(imsmd.LOMDescription).LangString(value)
			if lang:
				genDescription.SetLang(lang)

	def LRMMigrateDomain(self,lom,log):
		domains=self.metadata.get('domain',())
		warn=False
		for value,definition in domains:
			lang=definition.ResolveLang()
			kwValue=value.strip()
			if kwValue:
				kwContainer=lom.ChildElement(imsmd.LOMGeneral).ChildElement(imsmd.LOMKeyword).LangString(kwValue)
				# set the language of the kw
				if lang:
					kwContainer.SetLang(lang)
				if not warn:
					log.append("Warning: qmd_domain extension field will be added as LOM keyword")
					warn=True
	
	def LRMMigrateKeywords(self,lom,log):
		keywords=self.metadata.get('keywords',())
		for value,definition in keywords:
			lang=definition.ResolveLang()
			values=string.split(value,',')
			for kwValue in values:
				v=kwValue.strip()
				if v:
					kwContainer=lom.ChildElement(imsmd.LOMGeneral).ChildElement(imsmd.LOMKeyword).LangString(v)
					# set the language of the kw
					if lang:
						kwContainer.SetLang(lang)
	
	def LRMMigrateOrganization(self,lom,log):
		organizations=self.metadata.get('organization',())
		if organizations:
			if imsmd.vobject is None:
				log.append('Warning: qmd_organization support disabled (vobject not installed)')
			else:
				for value,definition in organizations:
					lifecycle=lom.ChildElement(imsmd.LOMLifecycle)
					contributor=lifecycle.ChildElement(imsmd.LOMContribute)
					role=contributor.LOMRole
					role.LRMSource.LangString.SetValue(imsmd.LOM_SOURCE)
					role.LRMSource.LangString.SetLang("x-none")
					role.LRMValue.LangString.SetValue("unknown")
					role.LRMValue.LangString.SetLang("x-none")
					name=value.strip()
					vcard=imsmd.vobject.vCard()
					vcard.add('n')
					vcard.n.value=imsmd.vobject.vcard.Name(family=name,given='')
					vcard.add('fn')
					vcard.fn.value=name
					vcard.add('org')
					vcard.org.value=[name]
					contributor.ChildElement(imsmd.LOMCEntity).LOMVCard.SetValue(vcard)	
			
	def MigrateV2(self,doc,lom,log):
		item=doc.root
		itemtypes=self.metadata.get('itemtype',())
		for itemtype,itemtypeDef in itemtypes:
			log.append("Warning: qmd_itemtype now replaced by qtiMetadata.interactionType in manifest, ignoring %s"%itemtype)
		self.LRMMigrateLevelOfDifficulty(lom,log)
		self.LRMMigrateStatus(lom,log)
		vendors=self.metadata.get('toolvendor',())
		for value,definition in vendors:
			item.metadata.ChildElement(qtiv2.QMDToolVendor).SetValue(value)
		self.LRMMigrateTopic(lom,log)
		self.LRMMigrateContributor('author','author',lom,log)
		self.LRMMigrateContributor('creator','initiator',lom,log)
		self.LRMMigrateContributor('owner','publisher',lom,log)
		self.LRMMigrateDescription(lom,log)
		self.LRMMigrateDomain(lom,log)
		self.LRMMigrateKeywords(lom,log)
		self.LRMMigrateOrganization(lom,log)


class QTIContentMixin:
	"""Mixin class for handling content elements."""

	def IsInline(self):
		"""True if this element can be inlined, False if it is block level
		
		The default implementation return True if all children can be inlined."""
		return self.InlineChildren()
		
	def InlineChildren(self):
		"""True if this element's children can all be inlined."""
		children=QTIElement.GetChildren(self)
		for child in children:
			if not child.IsInline():
				return False
		return True
		
	def MigrateV2Content(self,parent,log):
		"""Migrates this content to v2 adding it to the parent content node."""
		raise QTIUnimplementedError

		
class QTIFlowMatContainer(QTICommentElement, QTIContentMixin):
	"""Abstract class used to represent objects that contain flow_mat
	
	<!ELEMENT XXXXXXXXXX (qticomment? , (material+ | flow_mat+))>
	"""
	def __init__(self,parent):
		QTICommentElement.__init__(self,parent)

	def GetChildren(self):
		children=QTICommentElement.GetChildren(self)+QTIElement.GetChildren(self)
		return children

	def ExtractText(self):
		"""Returns text,lang representing this object."""
		result=[]
		children=QTIElement.GetChildren(self)
		lang=None
		for child in children:
			childText,childLang=child.ExtractText()
			if lang is None:
				lang=childLang
			if childText:
				result.append(childText.strip())
		return string.join(result,' '),lang

	def MigrateV2Content(self,parent,log):
		children=QTIElement.GetChildren(self)
		# initially assume we can just use a paragraph
		p=parent.ChildElement(qtiv2.XHTMLP)
		for child in children:
			child.MigrateV2Content(p,log)


class QTIViewMixin:
	"""Mixin class for handling view attribute.
	
	VIEWMAP attribute maps lower-cased view names from v1.2 onto corresponding v2 view values.
	"""
	VIEWMAP={
		'administrator':'proctor',
		'adminauthority':'proctor',
		'assessor':'scorer',
		'author':'author',
		'candidate':'candidate',
		'invigilator':'proctor',
		'proctor':'proctor',
		'invigilatorproctor':'proctor',
		'psychometrician':'testConstructor',
		'tutor':'tutor',
		'scorer':'scorer'}
		
	VIEWALL='author candidate proctor scorer testConstructor tutor'

	def __init__(self):
		self.view='All'

	def Set_view(self,value):
		self.view=value
				
	def GetViewAttributes(self,attrs):
		attrs['view']=self.view

	
class QTIObjectives(QTIFlowMatContainer,QTIViewMixin,QTIContentMixin):
	"""Represents the objectives element
	
	<!ELEMENT objectives (qticomment? , (material+ | flow_mat+))>

	<!ATTLIST objectives  %I_View; >"""
	XMLNAME='objectives'
	XMLCONTENT=xml.XMLElementContent
		
	def __init__(self,parent):
		QTIFlowMatContainer.__init__(self,parent)
		QTIViewMixin.__init__(self)
		self.view='All'
		
	def GetAttributes(self):
		attrs=QTIFlowMatContainer.GetAttributes(self)
		QTIViewElement.GetViewAttributes(self,attrs)
		return attrs
		
	def MigrateV2(self,v2item,log):
		"""Adds rubric representing these objectives to the given item's body"""
		rubric=v2item.ChildElement(qtiv2.QTIItemBody).ChildElement(qtiv2.QTIRubricBlock)
		if self.view.lower()=='all':
			rubric.Set_view(QTIObjectives.VIEWALL)
		else:
			oldView=self.view.lower()
			view=QTIObjectives.VIEWMAP.get(oldView,'author')
			if view!=oldView:
				log.append("Warning: changing view %s to %s"%(self.view,view))
			rubric.Set_view(view)
		self.MigrateV2Content(rubric,log)
				
	def LRMMigrateObjectives(self,lom,log):
		"""Adds educational description from these objectives."""
		description,lang=self.ExtractText()
		eduDescription=lom.ChildElement(imsmd.LOMEducational).ChildElement(imsmd.LOMDescription)
		eduDescription.AddString(lang,description)


class QTIMaterial(QTICommentElement,QTIContentMixin):
	"""Represents the material element
	
	<!ELEMENT material (qticomment? , (mattext | matemtext | matimage | mataudio | matvideo | matapplet | matapplication | matref | matbreak | mat_extension)+ , altmaterial*)>
	
	<!ATTLIST material  %I_Label;
						xml:lang CDATA  #IMPLIED >
	"""
	XMLNAME='material'
	XMLCONTENT=xml.XMLElementContent
	
	def __init__(self,parent):
		QTICommentElement.__init__(self,parent)
		self.label=None
		
	def GetAttributes(self):
		attrs=QTICommentElement.GetAttributes(self)
		if self.label: attrs['label']=self.label
		return attrs
		
	def Set_label(self,label):
		self.label=label
				
	def MigrateV2Content(self,parent,log):
		children=QTIElement.GetChildren(self)
		# ignore material for the moment
		for child in children:
			child.MigrateV2Content(parent,log)

	def ExtractText(self):
		result=[]
		children=QTIElement.GetChildren(self)
		lang=None
		for child in children:
			childText,childLang=child.ExtractText()
			if lang is None:
				lang=childLang
			if childText:
				result.append(childText.strip())
		if lang is None:
			lang=self.ResolveLang()
		return string.join(result,' '),lang
		

class QTIMatText(QTIElement,QTIContentMixin):
	"""Represents the mattext element

	<!ELEMENT mattext (#PCDATA)>
	
	<!ATTLIST mattext  texttype    CDATA  'text/plain'
						%I_Label;
						%I_CharSet;
						%I_Uri;
						xml:space    (preserve | default )  'default'
						xml:lang    CDATA  #IMPLIED
						%I_EntityRef;
						%I_Width;
						%I_Height;
						%I_Y0;
						%I_X0; >	
	"""
	XMLNAME='mattext'
	XMLCONTENT=xml.XMLMixedContent
	
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.texttype='text/plain'
		self.label=None

	def GetAttributes(self):
		attrs=QTIElement.GetAttributes(self)
		if self.label: attrs['label']=self.label
		attrs['texttype']=self.texttype
		return attrs
		
	def Set_texttype(self,texttype):
		self.texttype=texttype
				
	def Set_label(self,label):
		self.label=label

	def IsInline(self):
		if self.texttype=='text/plain':
			return True
		else:
			# we need to be smart here
			print self
			raise QTIUnimplementedError(self.texttype)
			
	def MigrateV2Content(self,parent,log):
		if self.texttype=='text/plain':
			lang=self.GetLang()
			if lang or self.label:
				span=parent.ChildElement(qtiv2.XHTMLSpan)
				if lang:
					span.SetLang(lang)
				if self.label:
					span.Set_label(self.label)
				span.AddData(self.GetValue())
			else:
				parent.AddData(self.GetValue())
		else:
			raise QTIUnimplementedError

	def ExtractText(self):
		return self.GetValue(),self.ResolveLang()

	def GotChildren(self):
		if self.texttype=='text/html':
			# parse the HTML content into an empty div
			try:
				text=self.GetValue()
			except xml.XMLMixedContentError:
				print self
		elif self.texttype=='text/rtf':
			# parse the RTF content
			pass
	
class QTIItemControl(QTICommentElement,QTIViewMixin):
	"""Represents the itemcontrol element
	
	<!ELEMENT itemcontrol (qticomment?)>
	
	<!ATTLIST itemcontrol  %I_FeedbackSwitch;
							%I_HintSwitch;
							%I_SolutionSwitch;
							%I_View; >
	"""
	XMLNAME='itemcontrol'
	XMLCONTENT=xml.XMLElementContent

	def __init__(self,parent):
		QTICommentElement.__init__(self,parent)
		QTIViewMixin.__init__(self)
		self.feedbackswitch=True
		self.hintswitch=True
		self.solutionswitch=True	

	def GetAttributes(self):
		attrs=QTICommentElement.GetAttributes(self)
		QTIViewElement.GetViewAttributes(self,attrs)
		attrs['feedbackswitch']=FormatYesNo(self.feedbackswitch)
		attrs['hintswitch']=FormatYesNo(self.hintswitch)
		attrs['solutionswitch']=FormatYesNo(self.solutionswitch)
		return attrs
		
	def Set_feedbackswitch(self,switchValue):
		self.feedbackswitch=ParseYesNo(switchValue)
				
	def Set_hintswitch(self,switchValue):
		self.hintswitch=ParseYesNo(switchValue)

	def Set_solutionswitch(self,switchValue):
		self.solutionswitch=ParseYesNo(switchValue)


class QTIItemPreCondition(QTIElement):
	"""Represents the itemprecondition element
	
	<!ELEMENT itemprecondition (#PCDATA)>"""
	XMLNAME='itemprecondition'


class QTIItemPostCondition(QTIElement):
	"""Represents the itempostcondition element
	
	<!ELEMENT itempostcondition (#PCDATA)>"""
	XMLNAME='itempostcondition'


class QTIRubric(QTIFlowMatContainer,QTIViewMixin):
	"""Represents the rubric element.
	
	<!ELEMENT rubric (qticomment? , (material+ | flow_mat+))>
	
	<!ATTLIST rubric  %I_View; >"""
	XMLNAME='rubric'
	XMLCONTENT=xml.XMLElementContent
	
	def __init__(self,parent):
		QTIFlowMatContainer.__init__(self,parent)
		QTIViewMixin.__init__(self)

	def GetAttributes(self):
		attrs=QTIFlowMatContainer.GetAttributes(self)
		QTIViewElement.GetViewAttributes(self,attrs)
		return attrs		
	
	def MigrateV2(self,v2item,log):
		if self.view.lower()=='all':
			log.append('Warning: rubric with view="All" replaced by <div> with class="rubric"')
			rubric=v2item.ChildElement(qtiv2.QTIItemBody).ChildElement(qtiv2.XHTMLDiv)
			rubric.Set_class('rubric')
		else:
			rubric=v2item.ChildElement(qtiv2.QTIItemBody).ChildElement(qtiv2.QTIRubricBlock)
			oldView=self.view.lower()
			view=QTIObjectives.VIEWMAP.get(oldView,'author')
			if view!=oldView:
				log.append("Warning: changing view %s to %s"%(self.view,view))
			rubric.Set_view(view)
		self.MigrateV2Content(rubric,log)


class QTIItemRubric(QTIRubric):
	"""Represents the itemrubric element.
	
	<!ELEMENT itemrubric (material)>

	<!ATTLIST itemrubric  %I_View; >
	
	We are generous with this element, extending the allowable content model
	to make it equivalent to <rubric> which is a superset.  <itemrubric> was
	deprecated in favour of <rubric> with QTI v1.2
	"""
	XMLNAME='itemrubric'
	XMLCONTENT=xml.XMLElementContent


class QTIPositionMixin:
	def __init__(self):
		self.x0=None
		self.y0=None
		self.width=None
		self.height=None

	def Set_x0(self,value):
		self.x0=ParseInteger(value)
		
	def Set_y0(self,value):
		self.y0=ParseInteger(value)
		
	def Set_width(self,value):
		self.width=ParseInteger(value)
		
	def Set_height(self,value):
		self.height=ParseInteger(value)
		
	def GetPositionAttributes(self,attrs):
		if self.x0 is not None: attrs['x0']=FormatInteger(self.x0)
		if self.y0 is not None: attrs['y0']=FormatInteger(self.y0)
		if self.width is not None: attrs['width']=FormatInteger(self.width)
		if self.height is not None: attrs['height']=FormatInteger(self.height)

	def GotPosition(self):
		return self.x0 is not None or self.y0 is not None or self.width is not None or self.height is not None
		
		
class QTIFlowContainer(QTICommentElement,QTIContentMixin):
	"""Abstract class used to represent objects that contain flow_mat
	
	<!ELEMENT XXXXXXXXXX (qticomment? , (material | flow | response_*)* )>
	"""
	def __init__(self,parent):
		QTICommentElement.__init__(self,parent)

	def GetChildren(self):
		children=QTICommentElement.GetChildren(self)+QTIElement.GetChildren(self)
		return children

	def MigrateV2Content(self,parent,log):
		children=QTIElement.GetChildren(self)
		if self.InlineChildren():
			# we add our children directly to the parent
			for child in children:
				child.MigrateV2Content(parent,log)
		else:
			p=None
			for child in children:
				if child.IsInline():
					if p is None:
						p=parent.ChildElement(qtiv2.XHTMLP)
						#p.Set_label(self.__class__.__name__)
					child.MigrateV2Content(p,log)
				else:
					# stop collecting inlines
					p=None
					child.MigrateV2Content(parent,log)
					
		
class QTIPresentation(QTIFlowContainer,QTIPositionMixin):
	"""Represents the presentation element.
	
	<!ELEMENT presentation (qticomment? ,
		(flow |
			(material |
			response_lid |
			response_xy |
			response_str |
			response_num |
			response_grp |
			response_extension)+
			)
		)>
	
	<!ATTLIST presentation  %I_Label;
							 xml:lang CDATA  #IMPLIED
							 %I_Y0;
							 %I_X0;
							 %I_Width;
							 %I_Height; >"""
	XMLNAME='presentation'
	XMLCONTENT=xml.XMLElementContent
	
	def __init__(self,parent):
		QTIFlowContainer.__init__(self,parent)
		QTIPositionMixin.__init__(self)
		self.label=None
		
	def GetAttributes(self):
		attrs=QTIFlowContainer.GetAttributes(self)
		QTIPositionMixin.GetPositionAttributes(self,attrs)
		if self.label is not None: attrs['label']=self.label
		return attrs		
	
	def Set_label(self,value):
		self.label=value
		
	def MigrateV2(self,v2Item,log):
		"""Presentation maps to the main content in itemBody."""
		itemBody=v2Item.ChildElement(qtiv2.QTIItemBody)
		if self.GotPosition():
			log.append("Warning: discarding absolute positioning information on presentation")
		if self.InlineChildren():
			p=itemBody.ChildElement(qtiv2.XHTMLP)
			if self.label is not None:
				p.Set_label(self.label)
			self.MigrateV2Content(p,log)
		elif self.label is not None:
			# We must generate a div to hold the label, we can't rely on owning itemBody
			div=itemBody.ChildElement(qtiv2.XHTMLDiv)
			div.Set_label(self.label)
			self.MigrateV2Content(div,log)
		else:
			self.MigrateV2Content(itemBody,log)

	def IsInline(self):
		return False
		

class QTIFlow(QTIFlowContainer):
	"""Represents the flow element.
	
	<!ELEMENT flow (qticomment? ,
		(flow |
		material |
		material_ref |
		response_lid |
		response_xy |
		response_str |
		response_num |
		response_grp |
		response_extension)+
		)>
	
	<!ATTLIST flow  %I_Class; >
	"""
	XMLNAME='flow'
	XMLCONTENT=xml.XMLElementContent
	
	def __init__(self,parent):
		QTIFlowContainer.__init__(self,parent)
		self.flowClass=None
		
	def GetAttributes(self):
		attrs=QTIFlowContainer.GetAttributes(self)
		if self.flowClass is not None: attrs['class']=self.flowClass
		return attrs		
	
	def Set_flowClass(self,value):
		self.flowClass=value
	
	def IsInline(self):
		"""flow is always treated as a block if flowClass is specified, otherwise
		it is treated as a block unless it is an only child."""
		if len(QTIElement.GetChildren(self.parent))==1 and self.flowClass is None:
			return self.InlineChildren()
		else:
			return False

	def MigrateV2Content(self,parent,log):
		"""flow typically maps to a div element.
		
		If the presentation only contains inline items then we create
		a paragraph to hold them."""
		if len(QTIElement.GetChildren(self.parent))==1 and self.flowClass is None:
			QTIFlowContainer.MigrateV2Content(self,parent,log)
		else:
			if self.flowClass is not None:
				div=parent.ChildElement(qtiv2.XHTMLDiv)
				div.Set_class(self.flowClass)
				parent=div
			if self.InlineChildren():
				p=parent.ChildElement(qtiv2.XHTMLP)
				QTIFlowContainer.MigrateV2Content(self,p,log)
			else:
				# we don't generate classless divs
				QTIFlowContainer.MigrateV2Content(self,itemBody,log)
			

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

