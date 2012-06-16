#! /usr/bin/env python

import pyslet.xml20081126.structures as xml
import pyslet.xsdatatypes20041028 as xsi
import pyslet.imsqtiv2p1 as qtiv2

import core, common

import string

class Assessment(common.CommentContainer):
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
		common.CommentContainer.__init__(self,parent)
		self.ident=None
		self.title=None
		self.QTIDuration=None
		self.QTIMetadata=[]
		self.QTIObjectives=[]
		self.AssessmentControl=[]
		self.QTIRubric=[]
		self.QTIPresentationMaterial=None
		self.QTIOutcomesProcessing=[]
		self.AssessProcExtension=None
		self.AssessFeedback=[]
		self.QTISelectionOrdering=None
		self.QTIReference=None
		self.SectionMixin=[]
		
	def QTISectionRef(self):
		child=QTISectionRef(self)
		self.SectionMixin.append(child)
		return child
		
	def QTISection(self):
		child=QTISection(self)
		self.SectionMixin.append(child)
		return child
		
	def GetChildren(self):
		for child in itertools.chain(
			QTIComment.GetChildren(self),
			self.QTIMetadata,
			self.QTIObjectives,
			self.AssessmentControl,
			self.QTIRubric):
			yield child
		if self.QTIPresentationMaterial: yield self.QTIPresentationMaterial
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


class AssessmentControl(common.CommentContainer):
	"""The control switches that are used to enable or disable the display of
	hints, solutions and feedback within the Assessment::

	<!ELEMENT assessmentcontrol (qticomment?)>
	<!ATTLIST assessmentcontrol
		hintswitch  (Yes | No )  'Yes'
        solutionswitch  (Yes | No )  'Yes'
        %I_View;
        feedbackswitch  (Yes | No )  'Yes' >"""
	XMLNAME='assessmentcontrol'
	XMLATTR_hintswitch=('hintSwitch',core.ParseYesNo,core.FormatYesNo)
	XMLATTR_solutionswitch=('solutionSwitch',core.ParseYesNo,core.FormatYesNo)
	XMLATTR_view=('view',core.View.DecodeLowerValue,core.View.EncodeValue)
	XMLATTR_feedbackswitch=('feedbackSwitch',core.ParseYesNo,core.FormatYesNo)
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		common.CommentContainer.__init__(self,parent)
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


class AssessFeedback(common.CommentContainer,common.ContentMixin):
	"""The container for the Assessment-level feedback that is to be presented
	as a result of Assessment-level processing of the user responses::
	
	<!ELEMENT assessfeedback (qticomment? , (material+ | flow_mat+))>
	<!ATTLIST assessfeedback  %I_View;
		ident CDATA  #REQUIRED
		title CDATA  #IMPLIED >"""
	XMLNAME='assessfeedback'
	XMLATTR_view=('view',core.View.DecodeLowerValue,core.View.EncodeValue)
	XMLATTR_ident='ident'		
	XMLATTR_title='title'
	XMLCONTENT=xml.ElementContent

	def __init__(self,parent):
		common.CommentContainer.__init__(self,parent)
		self.view=core.View.DEFAULT
		self.ident=None
		self.title=None
	
	def GetChildren(self):
		return itertools.chain(
			CommentContainer.GetChildren(self),
			self.contentChildren)

	def ContentMixin(self,childClass):
		if childClass in (common.QTIMaterial,common.QTIFlowMat):
			common.ContentMixin.ContentMixin(self,childClass)
		else:
			raise TypeError
	

