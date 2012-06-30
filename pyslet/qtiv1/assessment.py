#! /usr/bin/env python

import pyslet.xml20081126.structures as xml
import pyslet.xsdatatypes20041028 as xsi
import pyslet.imsqtiv2p1 as qtiv2

import core, common

import string

class Assessment(common.QTICommentContainer):
	"""The Assessment data structure is used to contain the exchange of test
	data structures. It will always contain at least one Section and may contain
	meta-data, objectives, rubric control switches, assessment-level processing,
	feedback and selection and sequencing information for sections::
	
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
		<!ATTLIST assessment  ident CDATA  #REQUIRED
							   %I_Title;
							   xml:lang CDATA  #IMPLIED >"""
	XMLNAME="assessment"
	XMLATTR_ident='ident'		
	XMLATTR_title='title'
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		common.QTICommentContainer.__init__(self,parent)
		self.ident=None
		self.title=None
		self.Duration=None
		self.QTIMetadata=[]
		self.Objectives=[]
		self.AssessmentControl=[]
		self.Rubric=[]
		self.PresentationMaterial=None
		self.QTIOutcomesProcessing=[]
		self.AssessProcExtension=None
		self.AssessFeedback=[]
		self.QTISelectionOrdering=None
		self.QTIReference=None
		self.SectionMixin=[]
		
	def SectionRef(self):
		child=SectionRef(self)
		self.SectionMixin.append(child)
		return child
		
	def Section(self):
		child=Section(self)
		self.SectionMixin.append(child)
		return child
		
	def GetChildren(self):
		for child in itertools.chain(
			QTIComment.GetChildren(self),
			self.QTIMetadata,
			self.Objectives,
			self.AssessmentControl,
			self.Rubric):
			yield child
		if self.PresentationMaterial: yield self.PresentationMaterial
		for child in self.QTIOutcomesProcessing: yield child
		if self.QTIAssessProcExtension: yield self.QTIAssessProcExtension
		for child in self.AssessFeedback: yield child
		if self.QTISelectionOrdering: yield self.QTISelectionOrdering
		if self.QTIReference: yield self.QTIReference
		for child in self.SectionMixin: yield child

	def MigrateV2(self,output):
		"""Converts this assessment to QTI v2
		
		For details, see QuesTestInterop.MigrateV2."""
		for obj in self.SectionMixin:
			obj.MigrateV2(output)


class AssessmentControl(common.QTICommentContainer):
	"""The control switches that are used to enable or disable the display of
	hints, solutions and feedback within the Assessment::

		<!ELEMENT assessmentcontrol (qticomment?)>
		<!ATTLIST assessmentcontrol
			hintswitch  (Yes | No )  'Yes'
			solutionswitch  (Yes | No )  'Yes'
			view	(All | Administrator | AdminAuthority | Assessor | Author |
					Candidate | InvigilatorProctor | Psychometrician | Scorer | 
					Tutor ) 'All'
			feedbackswitch  (Yes | No )  'Yes' >"""
	XMLNAME='assessmentcontrol'
	XMLATTR_hintswitch=('hintSwitch',core.ParseYesNo,core.FormatYesNo)
	XMLATTR_solutionswitch=('solutionSwitch',core.ParseYesNo,core.FormatYesNo)
	XMLATTR_view=('view',core.View.DecodeLowerValue,core.View.EncodeValue)
	XMLATTR_feedbackswitch=('feedbackSwitch',core.ParseYesNo,core.FormatYesNo)
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		common.QTICommentContainer.__init__(self,parent)
		self.view=core.View.DEFAULT
		self.hintSwitch=True
		self.solutionSwitch=True
		self.feedbackSwitch=True


class AssessProcExtension(core.QTIElement):
	"""This is used to contain proprietary alternative Assessment-level
	processing functionality::

	<!ELEMENT assessproc_extension ANY>"""
	XMLNAME="assessproc_extension"
	XMLCONTENT=xml.XMLMixedContent


class AssessFeedback(common.QTICommentContainer,common.ContentMixin):
	"""The container for the Assessment-level feedback that is to be presented
	as a result of Assessment-level processing of the user responses::
	
		<!ELEMENT assessfeedback (qticomment? , (material+ | flow_mat+))>
		<!ATTLIST assessfeedback  
			view	(All | Administrator | AdminAuthority | Assessor | Author |
					Candidate | InvigilatorProctor | Psychometrician | Scorer | 
					Tutor ) 'All'
			ident CDATA  #REQUIRED
			title CDATA  #IMPLIED >"""
	XMLNAME='assessfeedback'
	XMLATTR_view=('view',core.View.DecodeLowerValue,core.View.EncodeValue)
	XMLATTR_ident='ident'		
	XMLATTR_title='title'
	XMLCONTENT=xml.ElementContent

	def __init__(self,parent):
		common.QTICommentContainer.__init__(self,parent)
		common.ContentMixin.__init__(self)
		self.view=core.View.DEFAULT
		self.ident=None
		self.title=None
	
	def GetChildren(self):
		return itertools.chain(
			common.QTICommentContainer.GetChildren(self),
			common.ContentMixin.GetContentChildren(self))

	def ContentMixin(self,childClass):
		if childClass in (common.Material,common.QTIFlowMat):
			common.ContentMixin.ContentMixin(self,childClass)
		else:
			raise TypeError
	

