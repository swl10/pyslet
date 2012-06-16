#! /usr/bin/env python
"""This module implements the QTI 1.2.1 specification defined by IMS GLC"""

import pyslet.xml20081126.structures as xml
import pyslet.xml20081126.parser as xmlparser
import pyslet.imsqtiv2p1 as qtiv2
import pyslet.imsmdv1p2p1 as imsmd
import pyslet.html40_19991224 as html
import pyslet.xsdatatypes20041028 as xsi
import pyslet.rfc2396 as uri
import pyslet.rfc2616 as http

import string, codecs, itertools
import os.path
from types import StringTypes

from pyslet.qtiv1.core import *
from pyslet.qtiv1.common import *
from pyslet.qtiv1.item import *
#from pyslet.qtiv1.section import *
from pyslet.qtiv1.assessment import *
from pyslet.qtiv1.objectbank import *
#from pyslet.qtiv1.main import *

#IMSQTI_NAMESPACE="http://www.imsglobal.org/xsd/ims_qtiasiv1p2"
QTI_SOURCE='QTIv1'


class QuesTestInterop(CommentContainer):
	"""The <questestinterop> element is the outermost container for the QTI
	contents i.e. the container of the Assessment(s), Section(s) and Item(s)::

	<!ELEMENT questestinterop (qticomment? , (objectbank | assessment | (section | item)+))>"""

	XMLNAME='questestinterop'

	def __init__(self,parent):
		CommentContainer.__init__(self,parent)
		self.ObjectBank=None
		self.Assessment=None
		self.ObjectMixin=[]
	
	def GetChildren(self):
		for child in CommentContainer.GetChildren(self): yield child
		if self.ObjectBank:
			yield self.ObjectBank
		elif self.Assessment:
			yield self.Assessment
		else:
			for child in self.ObjectMixin: yield child

	def MigrateV2(self):
		"""Converts this element to QTI v2
		
		Returns a list of tuples of the form:
		( <QTIv2 Document>, <Metadata>, <List of Log Messages> ).
		
		One tuple is returned for each of the objects found. In QTIv2 there is
		no equivalent of QuesTestInterop.  The baseURI of each document is set
		from the baseURI of the QuesTestInterop element using the object
		identifier to derive a file name."""
		output=[]
		if self.ObjectBank:
			self.ObjectBank.MigrateV2(output)
		if self.Assessment:
			self.Assessment.MigrateV2(output)
		for obj in self.ObjectMixin:
			obj.MigrateV2(output)
		if self.QTIComment:
			if self.ObjectBank:
				# where to put the comment?
				pass
			elif self.Assessment:
				if len(self.ObjectMixin)==0:
					# Add this comment as a metadata description on the assessment
					pass
			elif len(self.ObjectMixin)==1:
				# Add this comment to this object's metdata description
				doc,lom,log=output[0]
				general=lom.LOMGeneral()
				description=general.ChildElement(general.DescriptionClass)
				descriptionString=description.ChildElement(description.LangStringClass)
				descriptionString.SetValue(self.QTIComment.GetValue())
		return output


#
#	ENTITY DEFINITIONS
#
"""
These definitions are used for common attribute definitions in the specification
and map to mix-in classes to make implementing these attribute pattern easier.

<!ENTITY % I_Testoperator " testoperator  (EQ | NEQ | LT | LTE | GT | GTE )  #REQUIRED">

<!ENTITY % I_Pname " pname CDATA  #REQUIRED">

<!ENTITY % I_Class " class CDATA  'Block'">

<!ENTITY % I_Mdoperator " mdoperator  (EQ | NEQ | LT | LTE | GT | GTE )  #REQUIRED">

<!ENTITY % I_Mdname " mdname CDATA  #REQUIRED">

<!ENTITY % I_Title " title CDATA  #IMPLIED">

<!ENTITY % I_Label " label CDATA  #IMPLIED">

<!ENTITY % I_Ident " ident CDATA  #REQUIRED">
"""


	
"""...
<!ENTITY % I_FeedbackSwitch " feedbackswitch  (Yes | No )  'Yes'">

<!ENTITY % I_HintSwitch " hintswitch  (Yes | No )  'Yes'">

<!ENTITY % I_SolutionSwitch " solutionswitch  (Yes | No )  'Yes'">

<!ENTITY % I_Rtiming " rtiming  (Yes | No )  'No'">

<!ENTITY % I_Uri " uri CDATA  #IMPLIED">

<!ENTITY % I_Embedded " embedded CDATA  'base64'">
"""

class QTILinkRefIdMixin:
	"""Mixin class for handling linkrefid attribute::
	
	<!ENTITY % I_LinkRefId " linkrefid CDATA  #REQUIRED">
	"""
	XMLATTR_linkrefid='linkRefID'

	def __init__(self):
		self.linkRefID=None

"""
...
<!ENTITY % I_VarName " varname CDATA  'SCORE'">

<!ENTITY % I_RespIdent " respident CDATA  #REQUIRED">

<!ENTITY % I_Continue " continue  (Yes | No )  'No'">

<!ENTITY % I_CharSet " charset CDATA  'ascii-us'">

<!ENTITY % I_ScoreModel " scoremodel CDATA  #IMPLIED">

<!ENTITY % I_MinNumber " minnumber CDATA  #IMPLIED">

<!ENTITY % I_MaxNumber " maxnumber CDATA  #IMPLIED">
"""

class QTIFeedbackStyle:
	"""feedbackstyle enumeration::
	
	<!ENTITY % I_FeedbackStyle " feedbackstyle  (Complete | Incremental | Multilevel | Proprietary )  'Complete'">
	"""
	decode={
		'Complete':1,
		'Incremental':2,
		'Multilevel':3,
		'Proprietary':4
		}		
xsi.MakeEnumeration(QTIFeedbackStyle)

def DecodeFeedbackStyle(value):
	"""Decodes a feedbackstyle value from a string."""
	try:
		value=value.strip()
		value=value[0].upper()+value[1:].lower()
		return QTIFeedbackStyle.decode[value]
	except KeyError:
		raise ValueError("Can't decode feedbackstyle from %s"%value)

def EncodeFeedbackStyle(value):
	return QTIFeedbackStyle.encode.get(value,'Complete')


"""
<!ENTITY % I_Case " case  (Yes | No )  'No'">

<!ENTITY % I_EntityRef " entityref ENTITY  #IMPLIED">

<!ENTITY % I_Index " index CDATA  #IMPLIED">
"""

class QMDMetadataElement(QTIElement):
	"""Abstract class to represent old-style qmd\_ tags"""
	
	def ContentChanged(self):
		self.DeclareMetadata(self.GetXMLName(),self.GetValue(),self)

class QMDAuthor(QMDMetadataElement):
	"""Not defined by QTI but seems to be in common use."""
	XMLNAME='qmd_author'

class QMDComputerScored(QMDMetadataElement):
	XMLNAME='qmd_computerscored'
	
class QMDDescription(QMDMetadataElement):
	"""Not defined by QTI but seems to be in common use."""
	XMLNAME='qmd_description'
	
class QMDDomain(QMDMetadataElement):
	"""Not defined by QTI but seems to be in common use."""
	XMLNAME='qmd_domain'

class QMDFeedbackPermitted(QMDMetadataElement):
	XMLNAME='qmd_feedbackpermitted'
	
class QMDHintsPermitted(QMDMetadataElement):
	XMLNAME='qmd_hintspermitted'

class QMDItemType(QMDMetadataElement):
	XMLNAME='qmd_itemtype'

class QMDKeywords(QMDMetadataElement):
	"""Not defined by QTI but seems to be in common use."""
	XMLNAME='qmd_keywords'

class QMDMaximumScore(QMDMetadataElement):
	XMLNAME='qmd_maximumscore'

class QMDOrganization(QMDMetadataElement):
	"""Not defined by QTI but seems to be in common use."""
	XMLNAME='qmd_organization'

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

class QMDTitle(QMDMetadataElement):
	"""Not defined by QTI but seems to be in common use."""
	XMLNAME='qmd_title'

class QMDToolVendor(QMDMetadataElement):
	XMLNAME='qmd_toolvendor'
		
class QMDTopic(QMDMetadataElement):
	XMLNAME='qmd_topic'

class QMDMaterial(QMDMetadataElement):
	XMLNAME='qmd_material'

class QMDTypeOfSolution(QMDMetadataElement):
	XMLNAME='qmd_typeofsolution'

class QMDLevelOfDifficulty(QMDMetadataElement):
	"""Represents the level of difficulty element.
	
::

	<!ELEMENT qmd_levelofdifficulty (#PCDATA)>
	"""	
	XMLNAME='qmd_levelofdifficulty'

	LOMDifficultyMap={
		"very easy":1,
		"easy":1,
		"medium":1,
		"difficult":1,
		"very difficult":1
		}
	
	LOMContextMap={
		"pre-school":("pre-school",False), # value is outside LOM defined vocab
		"school":("school",True),
		"he/fe":("higher education",True),
		"vocational":("vocational",False), # value is outside LOM defined vocab
		"professional development":("training",True)
		}


class QMDWeighting(QMDMetadataElement):
	XMLNAME='qmd_weighting'

class QTIMetadata(QTIElement):
	"""
::

	<!ELEMENT qtimetadata (vocabulary? , qtimetadatafield+)>
	"""
	XMLNAME='qtimetadata'
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.QTIVocabulary=None
		self.QTIMetadataField=[]
	
	def GetChildren(self):
		if self.QTIVocabulary: yield self.QTIVocabulary
		for child in self.QTIMetadataField: yield child


class QTIVocabulary(QTIElement):
	"""
::

	<!ELEMENT vocabulary (#PCDATA)>

	<!ATTLIST vocabulary  %I_Uri;
		%I_EntityRef;
		vocab_type  CDATA  #IMPLIED >
	"""
	XMLNAME="vocabulary"
	XMLATTR_entityref='entityRef'
	XMLATTR_uri='uri'		
	XMLATTR_vocab_type='vocabType'

	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.uri=None
		self.entityRef=None
		self.vocabType=None		


class QTIMetadataField(QTIElement):
	"""
::

	<!ELEMENT qtimetadatafield (fieldlabel , fieldentry)>

	<!ATTLIST qtimetadatafield  xml:lang CDATA  #IMPLIED >
	"""
	XMLNAME='qtimetadatafield'
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.QTIFieldLabel=QTIFieldLabel(self)
		self.QTIFieldEntry=QTIFieldEntry(self)
	
	def GetChildren(self):
		yield self.QTIFieldLabel
		yield self.QTIFieldEntry
	
	def ContentChanged(self):
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


		

		
class MaterialRef(QTIElement):
	"""Represents material_ref element.
	
::

	<!ELEMENT material_ref EMPTY>
	
	<!ATTLIST material_ref  %I_LinkRefId; >
	"""
	XMLNAME="material_ref"
	XMLCONTENT=xml.XMLEmpty


class QTIAltMaterial(CommentContainer):
	"""Represents the altmaterial element.

::

	<!ELEMENT altmaterial (qticomment? ,
		(mattext | matemtext | matimage | mataudio | matvideo |
		matapplet | matapplication | matref | matbreak | mat_extension)+)>
	
	<!ATTLIST altmaterial  xml:lang CDATA  #IMPLIED >
	"""
	XMLNAME="material_ref"
	XMLCONTENT=xml.ElementContent
	
class QTIVarType:
	"""vartype enumeration."""
	decode={
		'Integer':1,
		'String':2,
		'Decimal':3,
		'Scientific':4,
		'Boolean':5,
		'Enumerated':5,
		'Set':6
		}
xsi.MakeEnumeration(QTIVarType)

def DecodeVarType(value):
	try:
		return QTIVarType.decode[value]
	except KeyError:
		if value:
			try:
				value=value[0].upper()+value[1:].lower()
				return QTIVarType.decode[value]
			except KeyError:
				pass
		return 0

def EncodeVarType(value):
	if value:
		return QTIVarType.encode[value]
	else:
		return ''
		

class QTIDecVar(QTIElement):
	"""Represents the decvar element
	
::

	<!ELEMENT decvar (#PCDATA)>
	
	<!ATTLIST decvar  %I_VarName;
					   vartype     (Integer | 
									String | 
									Decimal | 
									Scientific | 
									Boolean | 
									Enumerated | 
									Set )  'Integer'
					   defaultval CDATA  #IMPLIED
					   minvalue   CDATA  #IMPLIED
					   maxvalue   CDATA  #IMPLIED
					   members    CDATA  #IMPLIED
					   cutvalue   CDATA  #IMPLIED >
	"""
	XMLNAME="decvar"
	XMLATTR_cutvalue='cutValue'
	XMLATTR_defaultval='defaultValue'	
	XMLATTR_maxvalue='maxValue'
	XMLATTR_members='members'
	XMLATTR_minvalue='minValue'
	XMLATTR_varname='varName'
	XMLATTR_vartype=('varType',DecodeVarType,EncodeVarType)
	XMLCONTENT=xml.XMLMixedContent
	
	V2TYPEMAP={
		QTIVarType.Integer:qtiv2.BaseType.integer,
		QTIVarType.String:qtiv2.BaseType.string,
		QTIVarType.Decimal:qtiv2.BaseType.float,
		QTIVarType.Scientific:qtiv2.BaseType.float,
		QTIVarType.Boolean:qtiv2.BaseType.boolean,
		QTIVarType.Enumerated:qtiv2.BaseType.identifier,
		QTIVarType.Set:qtiv2.BaseType.identifier
		}
		
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.varName='SCORE'
		self.varType=QTIVarType.Integer
		self.defaultValue=None
		self.minValue=None
		self.maxValue=None
		self.members=None
		self.cutValue=None
			
	def MigrateV2(self,v2Item,log):
		d=v2Item.ChildElement(qtiv2.QTIOutcomeDeclaration)
		v2Type=QTIDecVar.V2TYPEMAP.get(self.varType,None)
		if self.varType==QTIVarType.Set:
			log.append('Warning: treating vartype="Set" as equivalent to "Enumerated"')
		elif v2Type is None:
			log.append('Error: bad vartype for decvar "%s"; defaulting to integer'%self.varName)
			v2Type=qtiv2.BaseType.integer
		d.baseType=v2Type
		d.cardinality=qtiv2.QTICardinality.single
		d.identifier=qtiv2.ValidateIdentifier(self.varName)
		if self.defaultValue is not None:
			value=d.ChildElement(qtiv2.QTIDefaultValue).ChildElement(qtiv2.QTIValue)
			value.SetValue(self.defaultValue)
		# to do... min and max were actually constraints in QTI v1 ...
		# so we will need to fix these up later with responseConditions to constraint the value
		if self.minValue is not None:
			d.normalMinimum=float(self.minValue)
		if self.maxValue is not None:
			d.normalMaximum=float(self.maxValue)
		if self.members is not None:
			log.append('Warning: enumerated members no longer supported, ignoring "%s"'%self.members)
		if v2Type in (qtiv2.BaseType.integer,qtiv2.BaseType.float):
			# we need to adjust minValue/maxValue later
			if self.cutValue is not None:
				d.masteryValue=float(self.cutValue)
		v2Item.RegisterDeclaration(d)

	def ContentChanged(self):
		"""The decvar element is supposed to be empty but QTI v1 content is all over the place."""
		try:
			value=self.GetValue()
			if value is not None:
				assert value.strip()==''
		except xml.XMLMixedContentError:
			# Even more confusing
			pass


class QTISetVarAction:
	"""action enumeration."""
	decode={
		'Set':1,
		'Add':2,
		'Subtract':3,
		'Multiply':4,
		'Divide':5
		}
xsi.MakeEnumeration(QTISetVarAction)

def DecodeSetVarAction(value):
	try:
		return QTISetVarAction.decode[value]
	except KeyError:
		if value:
			try:
				value=value[0].upper()+value[1:].lower()
				return QTISetVarAction.decode[value]
			except KeyError:
				pass
		return 0

def EncodeSetVarAction(value):
	if value:
		return QTISetVarAction.encode[value]
	else:
		return ''


class QTISetVar(QTIElement):
	"""Represents the setvar element.

::

	<!ELEMENT setvar (#PCDATA)>
	
	<!ATTLIST setvar  %I_VarName;
					   action     (Set | Add | Subtract | Multiply | Divide )  'Set' >
	"""
	XMLNAME="setvar"
	XMLATTR_varname='varName'
	XMLATTR_action=('action',DecodeSetVarAction,EncodeSetVarAction)
	XMLCONTENT=xml.XMLMixedContent
	
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.varName='SCORE'
		self.action=QTISetVarAction.Set
	
	def MigrateV2Rule(self,parent,log):
		v2Item=parent.GetAssessmentItem()
		identifier=qtiv2.ValidateIdentifier(self.varName)
		outcome=v2Item.declarations.get(identifier,None)
		if outcome is None:
			raise QTIUnimplementedError("Auto-declared outcomes")
		setValue=parent.ChildElement(qtiv2.QTISetOutcomeValue)
		setValue.identifier=identifier
		if outcome.cardinality!=qtiv2.QTICardinality.single:
			raise QTIUnimplementedError("setvar for '%s' with cardinality %s"%(identifier,
				qtiv2.QTICardinality.encode[outcome.cardinality]))
		value=None
		variable=None
		if not self.action or self.action==QTISetVarAction.Set:
			value=setValue.ChildElement(qtiv2.QTIBaseValue)
		else:
			if self.action==QTISetVarAction.Add:
				op=setValue.ChildElement(qtiv2.QTISum)
			elif self.action==QTISetVarAction.Subtract:
				op=setValue.ChildElement(qtiv2.QTISubtract)
			elif self.action==QTISetVarAction.Multiply:
				op=setValue.ChildElement(qtiv2.QTIProduct)
			elif self.action==QTISetVarAction.Divide:
				op=setValue.ChildElement(qtiv2.QTIDivide)
			variable=op.ChildElement(qtiv2.QTIVariable)
			variable.identifier=identifier
			value=op.ChildElement(qtiv2.QTIBaseValue)
		value.baseType=outcome.baseType
		value.SetValue(self.GetValue())
		

class QTIInterpretVar(QTIElement,ContentMixin,QTIViewMixin):
	"""Represents the interpretvar element.

::

	<!ELEMENT interpretvar (material | material_ref)>
	
	<!ATTLIST interpretvar  %I_View;
							 %I_VarName; >
	"""
	XMLNAME="interpretvar"
	XMLATTR_view='view'
	XMLATTR_varname='varName'
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		ContentMixin.__init__(self)
		QTIViewMixin.__init__(self)
		self.varName='SCORE'
	
	def Material(self):
		child=Material(self)
		self.contentChildren.append(child)
		return child
	
	def MaterialRef(self):
		child=MaterialRef(self)
		self.contentChildren.append(child)
		return child
	
	def MigrateV2(self,v2Item,log):
		identifier=qtiv2.ValidateIdentifier(self.varName)
		if self.view.lower()!='all':
			log.append('Warning: view restriction on outcome interpretation no longer supported (%s)'%self.view)
		d=v2Item.declarations.get(identifier)
		di,lang=self.ExtractText()
		di=xsi.WhiteSpaceCollapse(di)
		if d.interpretation:
			d.interpretation=d.interpretation+"; "+di
		else:
			d.interpretation=di
		# we drop the lang as this isn't supported on declarations
		
		
class QTIConditionVar(QTIElement):
	"""Represents the interpretvar element.

::

	<!ELEMENT conditionvar (not | and | or | unanswered | other | varequal | varlt |
		varlte | vargt | vargte | varsubset | varinside | varsubstring | durequal |
		durlt | durlte | durgt | durgte | var_extension)+>
	
	"""
	XMLNAME="conditionvar"
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.ExpressionMixin=[]
	
	def QTIVarExtension(self):
		child=QTIVarExtension(self)
		self.ExpressionMixin.append(child)
		return child
	
	def GetChildren(self):
		return iter(self.ExpressionMixin)

	def MigrateV2Expression(self,parent,log):
		if len(self.ExpressionMixin)>1:
			# implicit and
			eAnd=parent.ChildElement(qtiv2.QTIAnd)
			for ie in self.ExpressionMixin:
				ie.MigrateV2Expression(eAnd,log)
		elif self.ExpressionMixin:
			self.ExpressionMixin[0].MigrateV2Expression(parent,log)
		else:
			log.append("Warning: empty condition replaced with null operator")
			parent.ChildElement(qtiv2.QTINull)
		

class ExpressionMixin:
	"""Abstract mixin class to indicate an expression"""
	pass


class QTINot(QTIElement,ExpressionMixin):
	"""Represents the not element.

::

	<!ELEMENT not (and | or | not | unanswered | other | varequal | varlt | varlte |
		vargt | vargte | varsubset | varinside | varsubstring | durequal | durlt |
		durlte | durgt | durgte)>	
	"""
	XMLNAME="not"
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.ExpressionMixin=None
	
	def GetChildren(self):
		if self.ExpressionMixin: yield self.ExpressionMixin

	def MigrateV2Expression(self,parent,log):
		if self.ExpressionMixin is None:
			log.append("Warning: empty not condition replaced with null operator")
			parent.ChildElement(qtiv2.QTINull)
		else:
			eNot=parent.ChildElement(qtiv2.QTINot)
			self.ExpressionMixin.MigrateV2Expression(eNot,log)


class QTIAnd(QTIElement,ExpressionMixin):
	"""Represents the and element.

::

	<!ELEMENT and (not | and | or | unanswered | other | varequal | varlt | varlte |
		vargt | vargte | varsubset | varinside | varsubstring | durequal | durlt |
		durlte | durgt | durgte)+>	
	"""
	XMLNAME="and"
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.ExpressionMixin=[]
	
	def GetChildren(self):
		return iter(self.ExpressionMixin)

	def MigrateV2Expression(self,parent,log):
		if len(self.ExpressionMixin):
			eAnd=parent.ChildElement(qtiv2.QTIAnd)
			for e in self.ExpressionMixin:
				e.MigrateV2Expression(eAnd,log)
		else:
			log.append("Warning: empty and condition replaced with null operator")
			parent.ChildElement(qtiv2.QTINull)


class QTIOr(QTIElement,ExpressionMixin):
	"""Represents the or element.

::

	<!ELEMENT or (not | and | or | unanswered | other | varequal | varlt | varlte |
		vargt | vargte | varsubset | varinside | varsubstring | durequal | durlt |
		durlte | durgt | durgte)+>
	"""
	XMLNAME="or"
	XMLCONTENT=xml.ElementContent

	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.ExpressionMixin=[]
	
	def GetChildren(self):
		return iter(self.ExpressionMixin)

	def MigrateV2Expression(self,parent,log):
		if len(self.ExpressionMixin):
			eOr=parent.ChildElement(qtiv2.QTIOr)
			for e in self.ExpressionMixin:
				e.MigrateV2Expression(eOr,log)
		else:
			log.append("Warning: empty or condition replaced with null operator")
			parent.ChildElement(qtiv2.QTINull)
		

class QTIVarThing(QTIElement,ExpressionMixin):
	"""Abstract class for var* elements."""
	XMLATTR_respident='responseIdentifier'
	XMLATTR_index=('index',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLCONTENT=xml.XMLMixedContent

	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.responseIdentifier=''
		self.index=None

	def MigrateV2Missing(self,identifier,parent,log):
		log.append("Warning: test of undeclared response (%s) replaced with Null operator"%identifier)
		parent.ChildElement(qtiv2.QTINull)
	
	def MigrateV2Variable(self,d,parent,log):
		if self.index:
			if d.cardinality==qtiv2.QTICardinality.multiple:
				log.append("Warning: index ignored for response variable of cardinality multiple")
			elif d.cardinality==qtiv2.QTICardinality.single:
				log.append("Warning: index ignored for response variable of cardinality single")
			else:
				parent=parent.ChildElement(qtiv2.QTIIndex)
				parent.n=self.index
		varExpression=parent.ChildElement(qtiv2.QTIVariable)
		varExpression.identifier=d.identifier
	
	def MigrateV2Value(self,d,parent,log):
		value=self.GetValue().strip()
		if d.baseType in (qtiv2.BaseType.pair,qtiv2.BaseType.directedPair,qtiv2.BaseType.point):
			value=value.replace(',',' ')
		elif d.baseType==qtiv2.BaseType.identifier:
			value=qtiv2.ValidateIdentifier(value)
		bv=parent.ChildElement(qtiv2.QTIBaseValue)
		bv.baseType=d.baseType
		bv.SetValue(value)
		
	
class QTIVarEqual(QTIVarThing):
	"""Represents the varequal element.

::

	<!ELEMENT varequal (#PCDATA)>
	
	<!ATTLIST varequal  %I_Case;
						 %I_RespIdent;
						 %I_Index; >
	"""
	XMLNAME="varequal"
	XMLATTR_case=('case',ParseYesNo,FormatYesNo)

	def __init__(self,parent):
		QTIVarThing.__init__(self,parent)
		self.case=False
	
	def MigrateV2Expression(self,parent,log):
		v2Item=parent.GetAssessmentItem()
		identifier=qtiv2.ValidateIdentifier(self.responseIdentifier)
		d=v2Item.declarations.get(identifier,None)
		if d is None:
			self.MigrateV2Missing(identifier,parent,log)
		elif d.cardinality==qtiv2.QTICardinality.single:
			# simple test of equality
			if d.baseType==qtiv2.BaseType.identifier or d.baseType==qtiv2.BaseType.pair:
				if not self.case:
					log.append("Warning: case-insensitive comparison of identifiers not supported in version 2")
				expression=parent.ChildElement(qtiv2.QTIMatch)
			elif d.baseType==qtiv2.BaseType.integer:
				expression=parent.ChildElement(qtiv2.QTIMatch)
			elif d.baseType==qtiv2.BaseType.string:
				expression=parent.ChildElement(qtiv2.QTIStringMatch)
				expression.caseSensitive=self.case
			elif d.baseType==qtiv2.BaseType.float:
				log.append("Warning: equality operator with float values is deprecated")
				expression=parent.ChildElement(qtiv2.QTIEqual)
			else:
				raise QTIUnimplementedOperator("varequal(%s)"%qtiv2.BaseType.Encode(d.baseType))
			self.MigrateV2Variable(d,expression,log)
			self.MigrateV2Value(d,expression,log)
		else:
			# This test simply becomes a member-test operation
			if d.baseType==qtiv2.BaseType.identifier or qtiv2.BaseType.pair:
				if not self.case:
					log.append("Warning: case-insensitive comparison of identifiers not supported in version 2")
			elif d.baseType==qtiv2.BaseType.string:
				if not self.case:
					log.append("Warning: member operation cannot be case-insensitive when baseType is string")
			elif d.baseType==qtiv2.BaseType.float:
				log.append("Warning: member operation is deprecated when baseType is float")
			else:
				raise QTIUnimplementedOperator("varequal(%s)"%qtiv2.BaseType.Encode(d.baseType))
			expression=parent.ChildElement(qtiv2.QTIMember)
			self.MigrateV2Value(d,expression,log)
			self.MigrateV2Variable(d,expression,log)


class QTIVarInequality(QTIVarThing):
	"""Abstract class for varlt, varlte, vargt and vargte."""

	def MigrateV2Inequality(self):
		"""Returns the class to use in qtiv2"""
		raise QTIUnimplementedOperator(self.xmlname)
		
	def MigrateV2Expression(self,parent,log):
		v2Item=parent.GetAssessmentItem()
		identifier=qtiv2.ValidateIdentifier(self.responseIdentifier)
		d=v2Item.declarations.get(identifier,None)
		if d is None:
			self.MigrateV2Missing(identifier,parent,log)
		elif d.cardinality==qtiv2.QTICardinality.single:
			# simple inequality
			if d.baseType==qtiv2.BaseType.integer or d.baseType==qtiv2.BaseType.float:
				expression=parent.ChildElement(self.MigrateV2Inequality())
			else:
				raise QTIUnimplementedOperator("%s(%s)"%(self.xmlname,qtiv2.BaseType.Encode(d.baseType)))
			self.MigrateV2Variable(d,expression,log)
			self.MigrateV2Value(d,expression,log)
		else:
			raise QTIUnimplementedOperator("%s(%s:%s)"%(self.xmlname,qtiv2.Cardinality.Encode(d.cardinality),qtiv2.BaseType.Encode(d.baseType)))

	
class QTIVarLT(QTIVarInequality):
	"""Represents the varlt element::

	<!ELEMENT varlt (#PCDATA)>
	
	<!ATTLIST varlt  %I_RespIdent;
					  %I_Index; >
	"""
	XMLNAME="varlt"
	XMLCONTENT=xml.XMLMixedContent

	def MigrateV2Inequality(self):
		return qtiv2.LT


class QTIVarLTE(QTIVarInequality):
	"""Represents the varlte element::

	<!ELEMENT varlte (#PCDATA)>
	
	<!ATTLIST varlte  %I_RespIdent;
					   %I_Index; >
	"""
	XMLNAME="varlte"
	XMLCONTENT=xml.XMLMixedContent

	def MigrateV2Inequality(self):
		return qtiv2.LTE


class QTIVarGT(QTIVarInequality):
	"""Represents the vargt element::

	<!ELEMENT vargt (#PCDATA)>
	
	<!ATTLIST vargt  %I_RespIdent;
					  %I_Index; >
	"""
	XMLNAME="vargt"
	XMLCONTENT=xml.XMLMixedContent

	def MigrateV2Inequality(self):
		return qtiv2.GT


class QTIVarGTE(QTIVarInequality):
	"""Represents the vargte element::

	<!ELEMENT vargte (#PCDATA)>
	
	<!ATTLIST vargte  %I_RespIdent;
					   %I_Index; >
	"""
	XMLNAME="vargte"
	XMLCONTENT=xml.XMLMixedContent

	def MigrateV2Inequality(self):
		return qtiv2.GTE


class QTIVarSubset(QTIElement,ExpressionMixin):
	"""Represents the varsubset element.

::

	<!ELEMENT varsubset (#PCDATA)>
	
	<!ATTLIST varsubset  %I_RespIdent;
						  setmatch     (Exact | Partial )  'Exact'
						  %I_Index; >
	"""
	XMLNAME="varsubset"
	XMLCONTENT=xml.XMLMixedContent


class QTIVarInside(QTIVarThing):
	"""Represents the varinside element.

::

	<!ELEMENT varinside (#PCDATA)>
	
	<!ATTLIST varinside  areatype     (Ellipse | Rectangle | Bounded )  #REQUIRED
						  %I_RespIdent;
						  %I_Index; >
	"""
	XMLNAME="varinside"
	XMLATTR_areatype=('areaType',Area.DecodeTitleValue,Area.EncodeValue)
	XMLCONTENT=xml.XMLMixedContent

	def __init__(self,parent):
		QTIVarThing.__init__(self,parent)
		self.areaType=None
	
	def MigrateV2Expression(self,parent,log):
		v2Item=parent.FindParent(qtiv2.QTIAssessmentItem)
		identifier=qtiv2.ValidateIdentifier(self.responseIdentifier)
		d=v2Item.declarations.get(identifier,None)
		if d is None:
			self.MigrateV2Missing(identifier,parent,log)
		elif d.cardinality==qtiv2.QTICardinality.single:
			# is the point in the area?
			if d.baseType==qtiv2.BaseType.point:
				expression=parent.ChildElement(qtiv2.QTIInside)
				expression.shape,coords=MigrateV2AreaCoords(self.areaType,self.GetValue(),log)
				for c in coords:
					expression.coords.values.append(html.LengthType(c))
				self.MigrateV2Variable(d,expression,log)			
			else:
				raise QTIUnimplementedError("varinside(%s)"%qtiv2.EncodeBaseType(d.baseType))
		else:
			raise QTIUnimplementedError("varinside with multiple/orderd variable")


class QTIVarSubString(QTIElement,ExpressionMixin):
	"""Represents the varsubstring element.

::

	<!ELEMENT varsubstring (#PCDATA)>
	
	<!ATTLIST varsubstring  %I_Index;
							 %I_RespIdent;
							 %I_Case; >
	"""
	XMLNAME="varsubstring"
	XMLCONTENT=xml.XMLMixedContent


class QTIDurEqual(QTIElement,ExpressionMixin):
	"""Represents the durequal element.

::

	<!ELEMENT durequal (#PCDATA)>
	
	<!ATTLIST durequal  %I_Index;
						 %I_RespIdent; >
	"""
	XMLNAME="durequal"
	XMLCONTENT=xml.XMLMixedContent


class QTIDurLT(QTIElement,ExpressionMixin):
	"""Represents the durlt element.

::

	<!ELEMENT durlt (#PCDATA)>
	
	<!ATTLIST durlt  %I_Index;
					  %I_RespIdent; >
	"""
	XMLNAME="durlt"
	XMLCONTENT=xml.XMLMixedContent


class QTIDurLTE(QTIElement,ExpressionMixin):
	"""Represents the durlte element.

::

	<!ELEMENT durlte (#PCDATA)>
	
	<!ATTLIST durlte  %I_Index;
					   %I_RespIdent; >
	"""
	XMLNAME="durlte"
	XMLCONTENT=xml.XMLMixedContent


class QTIDurGT(QTIElement,ExpressionMixin):
	"""Represents the durgt element.

::

	<!ELEMENT durgt (#PCDATA)>
	
	<!ATTLIST durgt  %I_Index;
					  %I_RespIdent; >
	"""
	XMLNAME="durgt"
	XMLCONTENT=xml.XMLMixedContent


class QTIDurGTE(QTIElement,ExpressionMixin):
	"""Represents the durgte element.

::

	<!ELEMENT durgte (#PCDATA)>
	
	<!ATTLIST durgte  %I_Index;
					   %I_RespIdent; >
	"""
	XMLNAME="durgte"
	XMLCONTENT=xml.XMLMixedContent


class QTIUnanswered(QTIElement,ExpressionMixin):
	"""Represents the unanswered element.
	
::

	<!ELEMENT unanswered (#PCDATA)>
	
	<!ATTLIST unanswered  %I_RespIdent; >
	"""
	XMLNAME="unanswered"
	XMLCONTENT=xml.XMLMixedContent


class QTIOther(QTIElement,ExpressionMixin):
	"""Represents the other element::

	<!ELEMENT other (#PCDATA)>	
	"""
	XMLNAME="other"
	XMLCONTENT=xml.XMLMixedContent

	def MigrateV2Expression(self,parent,log):
		log.append("Warning: replacing <other/> with the base value true - what did you want me to do??")
		bv=parent.ChildElement(qtiv2.QTIBaseValue)
		bv.baseType=qtiv2.BaseType.boolean
		bv.SetValue('true')


class QTIDuration(QTIElement):
	"""Represents the duration element.
	
::

	<!ELEMENT duration (#PCDATA)>
	"""
	XMLNAME="duration"
	XMLCONTENT=xml.XMLMixedContent


class QTIDisplayFeedback(QTIElement,QTILinkRefIdMixin):
	"""Represents the displayfeedback element.
	
::

	<!ELEMENT displayfeedback (#PCDATA)>
	
	<!ATTLIST displayfeedback  feedbacktype  (Response | Solution | Hint )  'Response'
								%I_LinkRefId; >
	"""
	XMLNAME="displayfeedback"
	XMLATTR_feedbacktype='feedbackType'
	XMLCONTENT=xml.XMLMixedContent

	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		QTILinkRefIdMixin.__init__(self)
		self.feedbackType='Response'
		
	def MigrateV2Rule(self,parent,log):
		v2Item=parent.GetAssessmentItem()
		identifier=qtiv2.ValidateIdentifier(self.linkRefID,'FEEDBACK_')
		outcome=v2Item.declarations.get('FEEDBACK',None)
		if outcome is None:
			d=v2Item.ChildElement(qtiv2.QTIOutcomeDeclaration)
			d.baseType=qtiv2.BaseType.identifier
			d.cardinality=qtiv2.QTICardinality.multiple
			d.identifier='FEEDBACK'
			v2Item.RegisterDeclaration(d)
		setValue=parent.ChildElement(qtiv2.QTISetOutcomeValue)
		setValue.identifier='FEEDBACK'
		multiple=setValue.ChildElement(qtiv2.QTIMultiple)
		variable=multiple.ChildElement(qtiv2.QTIVariable)
		variable.identifier='FEEDBACK'
		value=multiple.ChildElement(qtiv2.QTIBaseValue)
		value.baseType=qtiv2.BaseType.identifier
		value.SetValue(self.linkRefID)
		



class QTIReference(CommentContainer):
	"""Represent presentation_material element
	
::

	<!ELEMENT reference (qticomment? , (material | mattext | matemtext | matimage | mataudio |
		matvideo | matapplet | matapplication | matbreak | mat_extension)+)>"""
	XMLNAME="reference"
	XMLCONTENT=xml.ElementContent
	

class QTISelectionOrdering(CommentContainer):
	"""Represent selection_ordering element.
	
::

	<!ELEMENT selection_ordering (qticomment? , sequence_parameter* , selection* , order?)>
	
	<!ATTLIST selection_ordering  sequence_type CDATA  #IMPLIED >"""
	XMLNAME="selection_ordering"
	XMLCONTENT=xml.ElementContent
		

class QTIOutcomesProcessing(CommentContainer):
	"""Represent outcomes_processing element.
	
::

	<!ELEMENT outcomes_processing (qticomment? , outcomes , objects_condition* ,
		processing_parameter* , map_output* , outcomes_feedback_test*)>
	
	<!ATTLIST outcomes_processing  %I_ScoreModel; >"""
	XMLNAME="outcomes_processing"
	XMLCONTENT=xml.ElementContent

		
#
#	EXTENSION DEFINITIONS
#
class QTIMatExtension(QTIElement):
	"""Represents the mat_extension element.
	
::

	<!ELEMENT mat_extension ANY>
	"""
	XMLNAME="mat_extension"
	XMLCONTENT=xml.XMLMixedContent


class QTIVarExtension(QTIElement):
	"""Represents the var_extension element.
	
::

	<!ELEMENT var_extension ANY>
	"""
	XMLNAME="var_extension"
	XMLCONTENT=xml.XMLMixedContent


class QTIResponseExtension(QTIElement):
	"""Represents the response_extension element.
	
::

	<!ELEMENT response_extension ANY>
	"""
	XMLNAME="response_extension"
	XMLCONTENT=xml.XMLMixedContent



class QTISectionProcExtension(QTIElement):
	"""Represents the sectionproc_extension element.
	
::

	<!ELEMENT sectionproc_extension ANY>
	"""
	XMLNAME="sectionproc_extension"
	XMLCONTENT=xml.XMLMixedContent


class QTIItemProcExtension(ContentMixin,QTIElement):
	"""Represents the itemproc_extension element.
	
::

	<!ELEMENT itemproc_extension ANY>
	"""
	XMLNAME="itemproc_extension"
	XMLCONTENT=xml.XMLMixedContent

	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		ContentMixin.__init__(self)
		
	def MigrateV2Rule(self,cMode,ruleContainer,log):
		"""Converts an itemProcExtension into v2 response processing rules.
		
		We only support one type of extension at the moment, the
		humanrater element used as an illustration in the specification
		examples.
		"""
		for child in self.GetChildren():
			if type(child) in StringTypes:
				# ignore data
				continue
			elif child.xmlname=='humanraterdata':
				# humanraterdata extension, migrate content with appropriate view
				v2Item=ruleContainer.FindParent(qtiv2.QTIAssessmentItem)
				rubric=v2Item.ChildElement(qtiv2.QTIItemBody).ChildElement(qtiv2.QTIRubricBlock)
				rubric.view=qtiv2.QTIView.scorer
				material=[]
				child.FindChildren(Material,material)
				self.MigrateV2Content(rubric,html.BlockMixin,log,material)
		return cMode,ruleContainer


class QTIRespCondExtension(QTIElement):
	"""Represents the respcond_extension element.
	
::

	<!ELEMENT respcond_extension ANY>
	"""
	XMLNAME="respcond_extension"
	XMLCONTENT=xml.XMLMixedContent


class QTISelectionExtension(QTIElement):
	"""Represents the selection_extension element.
	
::

	<!ELEMENT selection_extension ANY>
	"""
	XMLNAME="selection_extension"
	XMLCONTENT=xml.XMLMixedContent


class QTIObjectsCondExtension(QTIElement):
	"""Represents the objectscond_extension element.
	
::

	<!ELEMENT objectscond_extension (#PCDATA)>
	"""
	XMLNAME="objectscond_extension"
	XMLCONTENT=xml.XMLMixedContent


class QTIOrderExtension(QTIElement):
	"""Represents the order_extension element.
	
::

	<!ELEMENT order_extension ANY>
	"""
	XMLNAME="order_extension"
	XMLCONTENT=xml.XMLMixedContent



class SectionMixin:
	"""Mix-in class representing section-link objects."""
	pass
	
class SectionRef(SectionMixin,QTIElement):
	"""Represents the sectionref element::

	<!ELEMENT sectionref (#PCDATA)>	
	<!ATTLIST sectionref  %I_LinkRefId; >"""
	XMLNAME='sectionref'
	XMLCONTENT=xml.XMLMixedContent


#
#	SECTION OBJECT DEFINITIONS
#
class QTISection(ObjectMixin,SectionMixin,CommentContainer):
	"""Represents section element.
::

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
	XMLATTR_ident='ident'		
	XMLATTR_title='title'	
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		CommentContainer.__init__(self,parent)
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
		for child in itertools.chain(
			QTIComment.GetChildren(self),
			self.QTIMetadata,
			self.QTIObjectives,
			self.QTISectionControl,
			self.QTISectionPrecondition,
			self.QTISectionPostcondition,
			self.QTIRubric):
			yield child
		if self.QTIPresentationMaterial: yield self.QTIPresentationMaterial
		for child in self.QTIOutcomesProcessing: yield child
		if self.QTISectionProcExtension: yield self.QTISectionProcExtension
		for child in self.QTISectionFeedback: yield child
		if self.QTISelectionOrdering: yield self.QTISelectionOrdering
		if self.QTIReference: yield self.QTIReference
		for child in self.objectList: yield child

	def MigrateV2(self,output):
		"""Converts this section to QTI v2
		
		For details, see QuesTestInterop.MigrateV2."""
		for obj in self.objectList:
			obj.MigrateV2(output)
	
	
class QTISectionPrecondition(QTIElement):
	"""Represents the sectionprecondition element.
	
::

	<!ELEMENT sectionprecondition (#PCDATA)>"""
	XMLNAME='sectionprecondition'
	XMLCONTENT=xml.XMLMixedContent


class QTISectionPostcondition(QTIElement):
	"""Represents the sectionpostcondition element.
	
::

	<!ELEMENT sectionpostcondition (#PCDATA)>"""
	XMLNAME='sectionpostcondition'
	XMLCONTENT=xml.XMLMixedContent


class QTISectionControl(CommentContainer):
	"""Represents the sectioncontrol element.
	
::

	<!ELEMENT sectioncontrol (qticomment?)>
	
	<!ATTLIST sectioncontrol  %I_FeedbackSwitch;
							   %I_HintSwitch;
							   %I_SolutionSwitch;
							   %I_View; >
	"""
	XMLNAME='sectioncontrol'
	XMLCONTENT=xml.XMLMixedContent


class QTIItemRef(QTIElement):
	"""Represents the itemref element.
	
::

	<!ELEMENT itemref (#PCDATA)>
	
	<!ATTLIST itemref  %I_LinkRefId; >
	"""
	XMLNAME='itemref'
	XMLCONTENT=xml.XMLMixedContent


class QTISectionFeedback(CommentContainer):
	"""Represents the sectionfeedback element.
	
::

	<!ELEMENT sectionfeedback (qticomment? , (material+ | flow_mat+))>
	
	<!ATTLIST sectionfeedback  %I_View;
								%I_Ident;
								%I_Title; >
	"""
	XMLNAME='sectionfeedback'
	XMLCONTENT=xml.XMLMixedContent

		

class QTIItemMetadata(MetadataContainerMixin,QTIElement):
	"""Represents the QTIItemMetadata element.
	
	This element contains more structure than is in common use, at the moment we
	represent this structure directly and automaticaly conform output to it,
	adding extension elements at the end.  In the future we might be more
	generous and allow input *and* output of elements in any sequence and
	provide separate methods for conforming these elements.
	
::

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
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		MetadataContainerMixin.__init__(self)
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
		for child in self.QTIMetadata: yield child
		if self.QMDComputerScored: yield self.QMDComputerScored
		if self.QMDFeedbackPermitted: yield self.QMDFeedbackPermitted
		if self.QMDHintsPermitted: yield self.QMDHintsPermitted
		if self.QMDItemType: yield self.QMDItemType
		if self.QMDLevelOfDifficulty: yield self.QMDLevelOfDifficulty
		if self.QMDMaximumScore: yield self.QMDMaximumScore
		for child in itertools.chain(
			self.QMDRenderingType,
			self.QMDResponseType):
			yield child
		if self.QMDScoringPermitted: yield self.QMDScoringPermitted
		if self.QMDSolutionsPermitted: yield self.QMDSolutionsPermitted
		if self.QMDStatus: yield self.QMDStatus
		if self.QMDTimeDependence: yield self.QMDTimeDependence
		if self.QMDTimeLimit: yield self.QMDTimeLimit
		if self.QMDToolVendor: yield self.QMDToolVendor
		if self.QMDTopic: yield self.QMDTopic
		if self.QMDWeighting: yield self.QMDWeighting
		for child in self.QMDMaterial: yield child
		if self.QMDTypeOfSolution: yield self.QMDTypeOfSolution
		for child in itertools.chain(
			self.QMDAuthor,
			self.QMDDescription,
			self.QMDDomain,
			self.QMDKeywords,
			self.QMDOrganization):
			yield child
		if self.QMDTitle: yield self.QMDTitle
		for child in QTIElement.GetChildren(self): yield child
	
	def LRMMigrateLevelOfDifficulty(self,lom,log):
		difficulty=self.metadata.get('levelofdifficulty',())
		for value,definition in difficulty:
			# IMS Definition says: The options are: "Pre-school", "School" or
			# "HE/FE", # "Vocational" and "Professional Development" so we bind
			# this value to the "Context" in LOM if one of the QTI or LOM
			# defined terms have been used, otherwise, we bind to Difficulty, as
			# this seems to be more common usage.
			context,lomFlag=QMDLevelOfDifficulty.LOMContextMap.get(value.lower(),(None,False))
			educational=lom.ChildElement(imsmd.LOMEducational)
			if context is None:
				# add value as difficulty
				value,lomFlag=QMDLevelOfDifficulty.LOMDifficultyMap.get(value.lower(),(value,False))
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
			description=lom.ChildElement(imsmd.LOMEducational).ChildElement(imsmd.Description)
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
			genDescription=lom.ChildElement(imsmd.LOMGeneral).ChildElement(imsmd.Description)
			genDescription=genDescription.ChildElement(genDescription.LangStringClass)
			genDescription.SetValue(value)
			if lang:
				genDescription.SetLang(lang)

	def LRMMigrateDomain(self,lom,log):
		domains=self.metadata.get('domain',())
		warn=False
		for value,definition in domains:
			lang=definition.ResolveLang()
			kwValue=value.strip()
			if kwValue:
				kwContainer=lom.ChildElement(imsmd.LOMGeneral).ChildElement(imsmd.LOMKeyword)
				kwContainer=kwContainer.ChildElement(kwContainer.LangStringClass)
				kwContainer.SetValue(kwValue)
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
					kwContainer=lom.ChildElement(imsmd.LOMGeneral).ChildElement(imsmd.LOMKeyword)
					kwContainer=kwContainer.ChildElement(kwContainer.LangStringClass)
					kwContainer.SetValue(v)
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

	
class QTIItemControl(CommentContainer,QTIViewMixin):
	"""Represents the itemcontrol element
	
::

	<!ELEMENT itemcontrol (qticomment?)>
	
	<!ATTLIST itemcontrol  %I_FeedbackSwitch;
							%I_HintSwitch;
							%I_SolutionSwitch;
							%I_View; >
	"""
	XMLNAME='itemcontrol'
	XMLATTR_feedbackswitch=('feedbackSwitch',ParseYesNo,FormatYesNo)
	XMLATTR_hintswitch=('hintSwitch',ParseYesNo,FormatYesNo)
	XMLATTR_solutionswitch=('solutionSwitch',ParseYesNo,FormatYesNo)
	XMLCONTENT=xml.ElementContent

	def __init__(self,parent):
		CommentContainer.__init__(self,parent)
		QTIViewMixin.__init__(self)
		self.feedbackSwitch=True
		self.hintSwitch=True
		self.solutionSwitch=True	

	def GetChildren(self):
		return CommentContainer.GetChildren(self)
				

class QTIItemPreCondition(QTIElement):
	"""Represents the itemprecondition element
	
::

	<!ELEMENT itemprecondition (#PCDATA)>"""
	XMLNAME='itemprecondition'
	XMLCONTENT=xml.XMLMixedContent


class QTIItemPostCondition(QTIElement):
	"""Represents the itempostcondition element
	
::

	<!ELEMENT itempostcondition (#PCDATA)>"""
	XMLNAME='itempostcondition'
	XMLCONTENT=xml.XMLMixedContent




		

	


	
	



class QTIResProcessing(CommentContainer):
	"""Represents the resprocessing element.
	
::

	<!ELEMENT resprocessing (qticomment? , outcomes , (respcondition | itemproc_extension)+)>
	
	<!ATTLIST resprocessing  %I_ScoreModel; >
	"""
	XMLNAME='resprocessing'
	XMLATTR_scoremodel='scoreModel'
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		CommentContainer.__init__(self,parent)
		self.scoreModel=None
		self.QTIOutcomes=QTIOutcomes(self)
		self.conditions=[]
		
	def QTIRespCondition(self):
		child=QTIRespCondition(self)
		self.conditions.append(child)
		return child
	
	def QTIItemProcExtension(self):
		child=QTIItemProcExtension(self)
		self.conditions.append(child)
		return child
	
	def GetChildren(self):
		for child in CommentContainer.GetChildren(self): yield child
		yield self.QTIOutcomes
		for child in self.conditions: yield child

	def MigrateV2(self,v2Item,log):
		"""Migrates v1 resprocessing to v2 ResponseProcessing."""
		rp=v2Item.ChildElement(qtiv2.QTIResponseProcessing)
		for outcomeFixup in sorted(self._interactionFixup.keys()):
			setValue=rp.ChildElement(qtiv2.QTISetOutcomeValue)
			setValue.identifier=outcomeFixup
			multi=setValue.ChildElement(qtiv2.QTIMultiple)
			for rID in self._interactionFixup[outcomeFixup]:
				var=multi.ChildElement(qtiv2.QTIVariable)
				var.identifier=rID
		self.QTIOutcomes.MigrateV2(v2Item,log)
		cMode=True;ruleContainer=rp
		for condition in self.conditions:
			cMode,ruleContainer=condition.MigrateV2Rule(cMode,ruleContainer,log)
		
		
class QTIOutcomes(CommentContainer):
	"""Represents the outcomes element.
	
::

	<!ELEMENT outcomes (qticomment? , (decvar , interpretvar*)+)>
	
	The implementation of this element takes a liberty with the content model
	because, despite the formulation above, the link between variables and
	their interpretation is not related to the order of the elements within
	the outcomes element.  (An interpretation without a variable reference
	defaults to an interpretation of the default 'SCORE' outcome.)
	
	When we output this element we do the decvars first, followed by
	the interpretVars.
	"""
	XMLNAME='outcomes'
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		CommentContainer.__init__(self,parent)
		self.QTIDecVar=[]
		self.QTIInterpretVar=[]
	
	def GetChildren(self):
		return itertools.chain(
			CommentContainer.GetChildren(self),
			self.QTIDecVar,
			self.QTIInterpretVar)

	def MigrateV2(self,v2Item,log):
		for d in self.QTIDecVar:
			d.MigrateV2(v2Item,log)
		for i in self.QTIInterpretVar:
			i.MigrateV2(v2Item,log)

		
class QTIRespCondition(CommentContainer):
	"""Represents the respcondition element.
	
::

	<!ELEMENT respcondition (qticomment? , conditionvar , setvar* , displayfeedback* , respcond_extension?)>
	
	<!ATTLIST respcondition  %I_Continue;
							  %I_Title; >
	"""
	XMLNAME='respcondition'
	XMLATTR_continue=('continueFlag',ParseYesNo,FormatYesNo)
	XMLATTR_title='title'
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		CommentContainer.__init__(self,parent)
		self.continueFlag=False
		self.title=None
		self.QTIConditionVar=QTIConditionVar(self)
		self.QTISetVar=[]
		self.QTIDisplayFeedback=[]
		self.QTIRespCondExtension=None
	
	def GetChildren(self):
		for child in CommentContainer.GetChildren(self): yield child
		yield self.QTIConditionVar
		for child in itertools.chain(
			self.QTISetVar,
			self.QTIDisplayFeedback):
			yield child
		if self.QTIRespCondExtension: yield self.QTIRespCondExtension
	
	def MigrateV2Rule(self,cMode,ruleContainer,log):
		"""Converts a response condition into v2 response processing rules.
		
		This method contains some tricky logic to help implement the confusing
		'continue' attribute of response conditions.  The continue attribute
		is interpreted in the following way:
		
		True: regardless of whether or not the condition matches, carry on to
		evaluate the next expression.
		
		False: only evaluate the next expression if the condition fails.
		
		The incoming cMode tells us if the previous condition set continue mode
		(the default is False on the attribute but the algorithm starts with
		continue mode True as the first rule is always evaluated).
		
		The way the rules are implemented is best illustrated by example, where
		X(True) represents condition X with continue='Yes' etc:
		
		R1(True),R2(True|False) becomes...
		
		if R1.test:
			R1.rules
		if R2.test:
			R2.rules
		
		R1(False),R2(True) becomes...
		
		if R1.test:
			R1.rules
		else:
			if R2.test:
				R2.rules
		
		R1(False),R2(False) becomes...
		
		if R1.test:
			R1.rules
		elif R2.test:
			R2.rules
		"""
		if self.continueFlag:
			if not cMode:
				ruleContainer=ruleContainer.ChildElement(qtiv2.QTIResponseElse)
			rc=ruleContainer.ChildElement(qtiv2.QTIResponseCondition)
			rcIf=rc.ChildElement(qtiv2.QTIResponseIf)
		else:
			if cMode:
				rc=ruleContainer.ChildElement(qtiv2.QTIResponseCondition)
				ruleContainer=rc
				rcIf=rc.ChildElement(qtiv2.QTIResponseIf)
			else:
				rcIf=ruleContainer.ChildElement(qtiv2.QTIResponseElseIf)
		self.QTIConditionVar.MigrateV2Expression(rcIf,log)
		for rule in self.QTISetVar:
			rule.MigrateV2Rule(rcIf,log)
		for rule in self.QTIDisplayFeedback:
			rule.MigrateV2Rule(rcIf,log)
		return self.continueFlag,ruleContainer

		
class QTIItemFeedback(QTIElement,QTIViewMixin,ContentMixin):
	"""Represents the itemfeedback element.
	
::

	<!ELEMENT itemfeedback ((flow_mat | material) | solution | hint)+>
	
	<!ATTLIST itemfeedback  %I_View;
							 %I_Ident;
							 %I_Title; >
	"""
	XMLNAME='itemfeedback'
	XMLATTR_title='title'
	XMLATTR_ident='ident'		

	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		QTIViewMixin.__init__(self)
		ContentMixin.__init__(self)
		self.title=None
		self.ident=None

	def GetChildren(self):
		return itertools.chain(
			QTIElement.GetChildren(self),
			self.contentChildren)

	def Material(self):
		child=Material(self)
		self.contentChildren.append(child)
		return child
	
	def FlowMat(self):
		child=FlowMat(self)
		self.contentChildren.append(child)
		return child

	def QTISolution(self):
		child=QTISolution(self)
		self.contentChildren.append(child)
		return child

	def QTIHint(self):
		child=QTIHint(self)
		self.contentChildren.append(child)
		return child
		
	def MigrateV2(self,v2Item,log):
		feedback=v2Item.ChildElement(qtiv2.QTIModalFeedback)
		if not (self.view.lower()=='all' and self.view.lower()=='candidate'):
			log.append("Warning: discarding view on feedback (%s)"%self.view)
		identifier=qtiv2.ValidateIdentifier(self.ident,'FEEDBACK_')
		feedback.outcomeIdentifier='FEEDBACK'
		feedback.showHide=qtiv2.QTIShowHide.show
		feedback.identifier=identifier
		feedback.title=self.title
		ContentMixin.MigrateV2Content(self,feedback,html.FlowMixin,log)
			
		
class QTISolution(ContentMixin,CommentContainer):
	"""Represents the solution element::

	<!ELEMENT solution (qticomment? , solutionmaterial+)>
	
	<!ATTLIST solution  %I_FeedbackStyle; >
	"""
	XMLNAME='solution'
	XMLATTR_feedbackstyle=('feedbackStyle',DecodeFeedbackStyle,EncodeFeedbackStyle)
	XMLCONTENT=xml.ElementContent

	def __init__(self,parent):
		CommentContainer.__init__(self,parent)
		ContentMixin.__init__(self)
		self.feedbackStyle=QTIFeedbackStyle.Complete
	
	def GetChildren(self):
		return itertools.chain(
			CommentContainer.GetChildren(),
			self.contentChildren)

	def QTISolutionMaterial(self):
		child=QTISolutionMaterial(self)
		self.contentChildren.append(child)
		return child
		

class QTIFeedbackMaterial(ContentMixin,QTIElement):
	"""Abstract class for solutionmaterial and hintmaterial::

	<!ELEMENT * (material+ | flow_mat+)>
	"""
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		ContentMixin.__init__(self)

	def GetChildren(self):
		return iter(self.contentChildren)

	def Material(self):
		child=Material(self)
		self.contentChildren.append(child)
		return child
	
	def FlowMat(self):
		child=FlowMat(self)
		self.contentChildren.append(child)
		return child
		
	
class QTISolutionMaterial(QTIFeedbackMaterial):
	"""Represents the solutionmaterial element::

	<!ELEMENT solutionmaterial (material+ | flow_mat+)>
	"""
	XMLNAME='solutionmaterial'


class QTIHint(CommentContainer):
	"""Represents the hint element.
	
::

	<!ELEMENT hint (qticomment? , hintmaterial+)>
	
	<!ATTLIST hint  %I_FeedbackStyle; >
	"""
	XMLNAME='hint'
	XMLATTR_feedbackstyle=('feedbackStyle',DecodeFeedbackStyle,EncodeFeedbackStyle)
	XMLCONTENT=xml.ElementContent

	def __init__(self,parent):
		CommentContainer.__init__(self,parent)
		ContentMixin.__init__(self)
		self.feedbackStyle=QTIFeedbackStyle.Complete
	
	def GetChildren(self):
		return itertools.chain(
			CommentContainer.GetChildren(),
			self.contentChildren)
	
	def QTIHintMaterial(self):
		child=QTIHintMaterial(self)
		self.contentChildren.append(child)
		return child


class QTIHintMaterial(QTIFeedbackMaterial):
	"""Represents the hintmaterial element::

	<!ELEMENT hintmaterial (material+ | flow_mat+)>
	"""
	XMLNAME='hintmaterial'
	

#
#	SELECTION AND ORDERING OBJECT DEFINITIONS
#
class QTISelection(QTIElement):
	"""Represents the selection element.
	
::

	<!ELEMENT selection (sourcebank_ref? , selection_number? , selection_metadata? ,
		(and_selection | or_selection | not_selection | selection_extension)?)>
	"""
	XMLNAME='selection'
	XMLCONTENT=xml.ElementContent
	

class QTIOrder(QTIElement):
	"""Represents the order element.
	
::

	<!ELEMENT order (order_extension?)>
	
	<!ATTLIST order  order_type CDATA  #REQUIRED >
	"""
	XMLNAME='order'
	XMLCONTENT=xml.ElementContent
	

class QTISelectionNumber(QTIElement):
	"""Represents the selection_number element.
	
::

	<!ELEMENT selection_number (#PCDATA)>
	"""
	XMLNAME='selection_number'
	XMLCONTENT=xml.XMLMixedContent
	

class QTISelectionMetadata(QTIElement):
	"""Represents the selection_metadata element.
	
::

	<!ELEMENT selection_metadata (#PCDATA)>
	
	<!ATTLIST selection_metadata  %I_Mdname;
								   %I_Mdoperator; >
	"""
	XMLNAME='selection_metadata'
	XMLCONTENT=xml.XMLMixedContent
	

class QTISequenceParameter(QTIElement):
	"""Represents the sequence_parameter element.
	
::

	<!ELEMENT sequence_parameter (#PCDATA)>
	
	<!ATTLIST sequence_parameter  %I_Pname; >
	"""
	XMLNAME='sequence_parameter'
	XMLCONTENT=xml.XMLMixedContent
	

class QTISourcebankRef(QTIElement):
	"""Represents the sourcebank_ref element.
	
::

	<!ELEMENT sourcebank_ref (#PCDATA)>
	"""
	XMLNAME='sourcebank_ref'
	XMLCONTENT=xml.XMLMixedContent
	

class QTIAndSelection(QTIElement):
	"""Represents the and_selection element.
	
::

	<!ELEMENT and_selection (selection_metadata | and_selection | or_selection | not_selection)+>
	"""
	XMLNAME='and_selection'
	XMLCONTENT=xml.ElementContent
	

class QTIOrSelection(QTIElement):
	"""Represents the or_selection element.
	
::

	<!ELEMENT or_selection (selection_metadata | and_selection | or_selection | not_selection)+>
	"""
	XMLNAME='or_selection'
	XMLCONTENT=xml.ElementContent
	

class QTINotSelection(QTIElement):
	"""Represents the not_selection element.
	
::

	<!ELEMENT not_selection (selection_metadata | and_selection | or_selection | not_selection)>
	"""
	XMLNAME='not_selection'
	XMLCONTENT=xml.ElementContent
	

#
#	OUTCOMES PREOCESSING OBJECT DEFINITIONS
#
class QTIObjectsCondition(CommentContainer):
	"""Represents the objects_condition element.
	
::

	<!ELEMENT objects_condition (qticomment? ,
		(outcomes_metadata | and_objects | or_objects | not_objects)? ,
		objects_parameter* , map_input* , objectscond_extension?)>
	"""
	XMLNAME='objects_condition'
	XMLCONTENT=xml.ElementContent
	

class QTIMapOutput(QTIElement):
	"""Represents the map_output element.
	
::

	<!ELEMENT map_output (#PCDATA)>
	
	<!ATTLIST map_output  %I_VarName; >
	"""
	XMLNAME='map_output'
	XMLCONTENT=xml.XMLMixedContent
	
	
class QTIMapInput(QTIElement):
	"""Represents the map_input element.
	
::

	<!ELEMENT map_input (#PCDATA)>
	
	<!ATTLIST map_input  %I_VarName; >
	"""
	XMLNAME='map_input'
	XMLCONTENT=xml.XMLMixedContent
	
	
class QTIOutcomesFeedbackTest(QTIElement):
	"""Represents the outcomes_feedback_test element.
	
::

	<!ELEMENT outcomes_feedback_test (test_variable , displayfeedback+)>

	<!ATTLIST outcomes_feedback_test  %I_Title; >
	"""
	XMLNAME='outcomes_feedback_test'
	XMLCONTENT=xml.ElementContent
	

class QTIOutcomesMetadata(QTIElement):
	"""Represents the outcomes_metadata element.
	
::

	<!ELEMENT outcomes_metadata (#PCDATA)>

	<!ATTLIST outcomes_metadata  %I_Mdname;
								  %I_Mdoperator; >
	"""
	XMLNAME='outcomes_metadata'
	XMLCONTENT=xml.ElementContent

	
class QTIAndObjects(QTIElement):
	"""Represents the and_objects element.
	
::

	<!ELEMENT and_objects (outcomes_metadata | and_objects | or_objects | not_objects)+>
	"""
	XMLNAME='and_objects'
	XMLCONTENT=xml.ElementContent
	

class QTIOrObjects(QTIElement):
	"""Represents the or_objects element.
	
::

	<!ELEMENT or_objects (outcomes_metadata | and_objects | or_objects | not_objects)+>
	"""
	XMLNAME='or_objects'
	XMLCONTENT=xml.ElementContent
	
	
class QTINotObjects(QTIElement):
	"""Represents the not_objects element.
	
::

	<!ELEMENT not_objects (outcomes_metadata | and_objects | or_objects | not_objects)>
	"""
	XMLNAME='not_objects'
	XMLCONTENT=xml.ElementContent
	
class QTITestVariable(QTIElement):
	"""Represents the test_variable element.
	
::

	<!ELEMENT test_variable (variable_test | and_test | or_test | not_test)>
	"""
	XMLNAME='test_variable'
	XMLCONTENT=xml.ElementContent

class QTIProcessingParameter(QTIElement):
	"""Represents the processing_parameter element.
	
::

	<!ELEMENT processing_parameter (#PCDATA)>

	<!ATTLIST processing_parameter  %I_Pname; >
	"""
	XMLNAME='processing_parameter'
	XMLCONTENT=xml.XMLMixedContent


class QTIAndTest(QTIElement):
	"""Represents the and_test element.
	
::

	<!ELEMENT and_test (variable_test | and_test | or_test | not_test)+>
	"""
	XMLNAME='and_test'
	XMLCONTENT=xml.ElementContent
	

class QTIOrTest(QTIElement):
	"""Represents the or_test element.
	
::

	<!ELEMENT or_test (variable_test | and_test | or_test | not_test)+>
	"""
	XMLNAME='or_test'
	XMLCONTENT=xml.ElementContent
	

class QTINotTest(QTIElement):
	"""Represents the not_test element.
	
::

	<!ELEMENT not_test (variable_test | and_test | or_test | not_test)>
	"""
	XMLNAME='not_test'
	XMLCONTENT=xml.ElementContent


class QTIVariableTest(QTIElement):
	"""Represents the variable_test element.
	
::

	<!ELEMENT variable_test (#PCDATA)>

	<!ATTLIST variable_test  %I_VarName;
                          %I_Testoperator; >
	"""
	XMLNAME='variable_test'
	XMLCONTENT=xml.ElementContent



class QTIObjectsParameter(QTIElement):
	"""Represents the objects_parameter element.
	
::

	<!ELEMENT objects_parameter (#PCDATA)>

	<!ATTLIST objects_parameter  %I_Pname; >
	"""
	XMLNAME='objects_parameter'
	XMLCONTENT=xml.XMLMixedContent


#
#	END OF SPECIFICATION ELEMENT DEFINITIONS
#

class QTIDocument(xml.Document):
	"""Class for working with QTI documents."""
	
	def __init__(self,**args):
		"""We turn off the parsing of external general entities to prevent a
		missing DTD causing the parse to fail.  This is a significant limitation
		as it is possible that some sophisticated users have used general
		entities to augment the specification or to define boiler-plate code. 
		If this causes problems then you can turn the setting back on again for
		specific instances of the parser that will be used with that type of
		data."""
		xml.Document.__init__(self,**args)
		self.material={}
		self.matThings={}
		
	def XMLParser(self,entity):
		"""Adds some options to the basic XMLParser to improve QTI compatibility."""
		p=xmlparser.XMLParser(entity)
		p.unicodeCompatibility=True
		return p

	classMap={}
	
	def GetElementClass(self,name):
		"""Returns the class to use to represent an element with the given name.
		
		This method is used by the XML parser.  The class object is looked up in
		the classMap, if no specialized class is found then the general
		:py:class:`pyslet.xml20081126.Element` class is returned."""
		return QTIDocument.classMap.get(name,QTIDocument.classMap.get(None,xml.Element))

	def RegisterMatThing(self,matThing):
		"""Registers a QTIMatThing instance in the dictionary of matThings."""
		if matThing.label is not None:
			self.matThings[matThing.label]=matThing
	
	def UnregisterMatThing(self,mathThing):
		if matThing.label is not None and matThing is self.matThings.get(matThing.label,None):
			del self.matThings[matThing.label]			
	
	def FindMatThing(self,linkRefID):
		"""Returns the mat<thing> element with label matching the *linkRefID*.
		
		The specification says that material_ref should be used if you want to
		refer a material object, not matref, however this rule is not
		universally observed so if we don't find a basic mat<thing> we will
		search the material objects too and return a :py:class:`Material`
		instance instead."""
		matThing=self.matThings.get(linkRefID,None)
		if matThing is None:
			matThing=self.material.get(linkRefID,None)
		return matThing
	
	def RegisterMaterial(self,material):
		"""Registers a Material instance in the dictionary of labelled material objects."""
		if material.label is not None:
			self.material[material.label]=material
	
	def UnregisterMaterial(self,material):
		if material.label is not None and material is self.material.get(material.label,None):
			del self.material[material.label]			
	
	def FindMaterial(self,linkRefID):
		"""Returns the material element with label matching *linkRefID*.
		
		Like :py:meth:`FindMatThing` this method will search for instances of
		:py:class:`QTIMatThingMixin` if it can't find a :py:class:`Material`
		element to match.  The specification is supposed to be strict about
		matching the two types of reference but errors are common, even in the
		official example set."""
		material=self.material.get(linkRefID,None)
		if material is None:
			# We could this all in one line but in the future we might want
			# break out a stricter parsing mode here to help validate the
			# QTI v1 content.
			material=self.matThings.get(linkRefID,None)
		return material

	def MigrateV2(self,cp):
		"""Converts the contents of this document to QTI v2
		
		The output is stored into the content package passed in cp.  Errors and
		warnings generated by the migration process are added as annotations to
		the resulting resource objects in the content package.
		
		The function returns a list of 4-tuples, one for each object migrated.
		
		Each tuple comprises ( <QTI v2 Document>, <LOM Metadata>, <log>, <Resource> )"""
		if isinstance(self.root,QuesTestInterop):
			results=self.root.MigrateV2()
			# list of tuples ( <QTIv2 Document>, <Metadata>, <Log Messages> )
			newResults=[]
			if results:
				# Make a directory to hold the files (makes it easier to find unique names for media files)
				if isinstance(self.baseURI,uri.FileURL):
					ignore,dName=os.path.split(self.baseURI.GetPathname())
				else:
					dName="questestinterop"
				dName,ext=os.path.splitext(dName)
				dName=cp.GetUniqueFile(dName)
				for doc,metadata,log in results:
					if log:
						# clean duplicate lines from the log then add as an annotation
						logCleaner={}
						i=0
						while i<len(log):
							if log[i] in logCleaner:
								del log[i]
							else:
								logCleaner[log[i]]=i
								i=i+1
						annotation=metadata.LOMAnnotation()
						annotationMsg=string.join(log,';\n')
						description=annotation.ChildElement(imsmd.Description)
						description.ChildElement(description.LangStringClass).SetValue(annotationMsg)
					r=doc.AddToContentPackage(cp,metadata,dName)
					newResults.append((doc,metadata,log,r))
				cp.manifest.Update()
			return newResults
		else:
			return []

xml.MapClassElements(QTIDocument.classMap,globals())


try:
	CNBIG5=codecs.lookup('cn-big5')
	pass
except LookupError:
	CNBIG5=None
	try:
		BIG5=codecs.lookup('big5')
		CNBIG5=codecs.CodecInfo(BIG5.encode, BIG5.decode, streamreader=BIG5.streamreader,
			streamwriter=BIG5.streamwriter, incrementalencoder=BIG5.incrementalencoder,
			incrementaldecoder=BIG5.incrementaldecoder, name='cn-big5')
	except LookupError:
		# we'll have to do without cn-big5
		pass

try:
	APPLESYMBOL=codecs.lookup('apple-symbol')
	pass
except LookupError:
	import pyslet.unicode_apple_symbol as symbol
	APPLESYMBOL=symbol.getregentry()


def QTICodecSearch(name):
	if name.lower()=="cn-big5" and CNBIG5:
		return CNBIG5
	elif name.lower()=="apple-symbol":
		return APPLESYMBOL
	
def RegisterCodecs():
	"""The example files that are distributed with the QTI specification contain
	a set of Chinese examples encoded using big5.  However, the xml declarations
	on these files refer to the charset as "CN-BIG5" and this causes errors when
	parsing them as this is a non-standard way of refering to big5.
	
	QTI also requires use of the apple symbol font mapping for interpreting
	symbol-encoded maths text in questions."""
	codecs.register(QTICodecSearch)

# Force registration of codecs on module load
RegisterCodecs()

# Legacy function no longer needed
def FixupCNBig5(): pass
