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
from pyslet.qtiv1.section import *
from pyslet.qtiv1.assessment import *
from pyslet.qtiv1.objectbank import *
#from pyslet.qtiv1.main import *

#IMSQTI_NAMESPACE="http://www.imsglobal.org/xsd/ims_qtiasiv1p2"
QTI_SOURCE='QTIv1'


class QuesTestInterop(QTICommentContainer):
	"""The <questestinterop> element is the outermost container for the QTI
	contents i.e. the container of the Assessment(s), Section(s) and Item(s)::

	<!ELEMENT questestinterop (qticomment? , (objectbank | assessment | (section | item)+))>"""

	XMLNAME='questestinterop'

	def __init__(self,parent):
		QTICommentContainer.__init__(self,parent)
		self.ObjectBank=None
		self.Assessment=None
		self.ObjectMixin=[]
	
	def GetChildren(self):
		for child in QTICommentContainer.GetChildren(self): yield child
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

<!ENTITY % I_Case " case  (Yes | No )  'No'">

<!ENTITY % I_EntityRef " entityref ENTITY  #IMPLIED">

<!ENTITY % I_Index " index CDATA  #IMPLIED">
"""


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

	<!ATTLIST vocabulary  uri CDATA  #IMPLIED
		entityref ENTITY  #IMPLIED
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
	
	<!ATTLIST interpretvar  view (All | Administrator | AdminAuthority | Assessor | Author | Candidate |
	InvigilatorProctor | Psychometrician | Scorer | Tutor )  'All'
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
				expression=parent.ChildElement(qtiv2.Match)
			elif d.baseType==qtiv2.BaseType.integer:
				expression=parent.ChildElement(qtiv2.Match)
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
		



class QTIReference(QTICommentContainer):
	"""Represent presentation_material element
	
::

	<!ELEMENT reference (qticomment? , (material | mattext | matemtext | matimage | mataudio |
		matvideo | matapplet | matapplication | matbreak | mat_extension)+)>"""
	XMLNAME="reference"
	XMLCONTENT=xml.ElementContent
	

class QTISelectionOrdering(QTICommentContainer):
	"""Represent selection_ordering element.
	
::

	<!ELEMENT selection_ordering (qticomment? , sequence_parameter* , selection* , order?)>
	
	<!ATTLIST selection_ordering  sequence_type CDATA  #IMPLIED >"""
	XMLNAME="selection_ordering"
	XMLCONTENT=xml.ElementContent
		

class OutcomesProcessing(QTICommentContainer):
	"""Represent outcomes_processing element.
	
::

	<!ELEMENT outcomes_processing (qticomment? , outcomes , objects_condition* ,
		processing_parameter* , map_output* , outcomes_feedback_test*)>
	
	<!ATTLIST outcomes_processing  scoremodel CDATA  #IMPLIED >"""
	XMLNAME="outcomes_processing"
	XMLCONTENT=xml.ElementContent

		
#
#	EXTENSION DEFINITIONS
#
class MatExtension(QTIElement):
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


class RespCondExtension(QTIElement):
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
class QTIObjectsCondition(QTICommentContainer):
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
	
	
class OutcomesFeedbackTest(QTIElement):
	"""Represents the outcomes_feedback_test element.
	
::

	<!ELEMENT outcomes_feedback_test (test_variable , displayfeedback+)>

	<!ATTLIST outcomes_feedback_test  title CDATA  #IMPLIED >
	"""
	XMLNAME='outcomes_feedback_test'
	XMLCONTENT=xml.ElementContent
	

class OutcomesMetadata(QTIElement):
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
		"""Registers a MatThing instance in the dictionary of matThings."""
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
		:py:class:`MatThingMixin` if it can't find a :py:class:`Material`
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
