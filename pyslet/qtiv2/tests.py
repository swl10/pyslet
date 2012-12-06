#! /usr/bin/env python

import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsi
import pyslet.html40_19991224 as html

import pyslet.qtiv2.core as core

import string, itertools, random

		
class AssessmentTest(core.QTIElement,core.DeclarationContainer):
	"""A test is a group of assessmentItems with an associated set of rules that
	determine which of the items the candidate sees, in what order, and in what
	way the candidate interacts with them. The rules describe the valid paths
	through the test, when responses are submitted for response processing and
	when (if at all) feedback is to be given::

		<xsd:attributeGroup name="assessmentTest.AttrGroup">
			<xsd:attribute name="identifier" type="string.Type" use="required"/>
			<xsd:attribute name="title" type="string.Type" use="required"/>
			<xsd:attribute name="toolName" type="string256.Type" use="optional"/>
			<xsd:attribute name="toolVersion" type="string256.Type" use="optional"/>
		</xsd:attributeGroup>
		
		<xsd:group name="assessmentTest.ContentGroup">
			<xsd:sequence>
				<xsd:element ref="outcomeDeclaration" minOccurs="0" maxOccurs="unbounded"/>
				<xsd:element ref="timeLimits" minOccurs="0" maxOccurs="1"/>
				<xsd:element ref="testPart" minOccurs="1" maxOccurs="unbounded"/>
				<xsd:element ref="outcomeProcessing" minOccurs="0" maxOccurs="1"/>
				<xsd:element ref="testFeedback" minOccurs="0" maxOccurs="unbounded"/>
			</xsd:sequence>
		</xsd:group>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'assessmentTest')
	XMLATTR_identifier='identifier'		
	XMLATTR_title='title'	
	XMLATTR_toolName='toolName'	
	XMLATTR_toolVersion='toolVersion'
	XMLCONTENT=xmlns.ElementContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		core.DeclarationContainer.__init__(self)
		self.identifier=None
		self.title=None
		self.toolName=None
		self.toolVersion=None
		self.OutcomeDeclaration=[]
		self.TimeLimits=None
		self.TestPart=[]
		self.OutcomeProcessing=None
		self.TestFeedback=[]
		self.parts={}	#: a dictionary of testPart, assessmentSection and assessmentItemRef keyed on identifier
		
	def GetChildren(self):
		for d in self.OutcomeDeclaration: yield d
		if self.TimeLimits: yield self.TimeLimits
		for d in self.TestPart: yield d
		if self.OutcomeProcessing: yield self.OutcomeProcessing
		for child in self.TestFeedback: yield child
	
	def ContentChanged(self):
		self.SortDeclarations()
		
	def SortDeclarations(self):
		"""Sort the outcome declarations so that they are in identifier order. 
		This is not essential but it does help ensure that output is
		predictable. This method is called automatically when reading items from
		XML files."""
		self.OutcomeDeclaration.sort()

	def RegisterPart(self,part):
		"""Registers a testPart, asssessmentSection or assessmentItemRef in
		:py:attr:`parts`."""
		if part.identifier in self.parts:
			raise KeyError("Duplicate identifier: %s"%part.identifier)
		else:
			self.parts[part.identifier]=part
	
	def GetPart(self,identifier):
		"""Returns the testPart, assessmentSection or assessmentItemRef with the
		given identifier."""
		return self.parts[identifier]
		

class NavigationMode(xsi.Enumeration):
	"""The navigation mode determines the general paths that the candidate may
	take. A testPart in linear mode restricts the candidate to attempt each item
	in turn. Once the candidate moves on they are not permitted to return. A
	testPart in nonlinear mode removes this restriction - the candidate is free
	to navigate to any item in the test at any time::
	
		<xsd:simpleType name="navigationMode.Type">
			<xsd:restriction base="xsd:NMTOKEN">
				<xsd:enumeration value="linear"/>
				<xsd:enumeration value="nonlinear"/>
			</xsd:restriction>
		</xsd:simpleType>
	
	Defines constants for the above modes.  Usage example::

		NavigationMode.linear
	
	Note that::
		
		NavigationMode.DEFAULT == None

	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
	decode={
		'linear':1,
		'nonlinear':2
		}
xsi.MakeEnumeration(NavigationMode)


class SubmissionMode(xsi.Enumeration):
	"""The submission mode determines when the candidate's responses are
	submitted for response processing. A testPart in individual mode requires
	the candidate to submit their responses on an item-by-item basis. In
	simultaneous mode the candidate's responses are all submitted together at
	the end of the testPart::
	
		<xsd:simpleType name="submissionMode.Type">
			<xsd:restriction base="xsd:NMTOKEN">
				<xsd:enumeration value="individual"/>
				<xsd:enumeration value="simultaneous"/>
			</xsd:restriction>
		</xsd:simpleType>
	
	Defines constants for the above modes.  Usage example::

		SubmissionMode.individual
	
	Note that::
		
		SubmissionMode.DEFAULT == None

	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
	decode={
		'individual':1,
		'simultaneous':2
		}
xsi.MakeEnumeration(SubmissionMode)


class TestPart(core.QTIElement):
	"""Each test is divided into one or more parts which may in turn be divided
	into sections, sub-sections, and so on::
	
		<xsd:attributeGroup name="testPart.AttrGroup">
			<xsd:attribute name="identifier" type="identifier.Type" use="required"/>
			<xsd:attribute name="navigationMode" type="navigationMode.Type" use="required"/>
			<xsd:attribute name="submissionMode" type="submissionMode.Type" use="required"/>
		</xsd:attributeGroup>
		
		<xsd:group name="testPart.ContentGroup">
			<xsd:sequence>
				<xsd:element ref="preCondition" minOccurs="0" maxOccurs="unbounded"/>
				<xsd:element ref="branchRule" minOccurs="0" maxOccurs="unbounded"/>
				<xsd:element ref="itemSessionControl" minOccurs="0" maxOccurs="1"/>
				<xsd:element ref="timeLimits" minOccurs="0" maxOccurs="1"/>
				<xsd:element ref="assessmentSection" minOccurs="1" maxOccurs="unbounded"/>
				<xsd:element ref="testFeedback" minOccurs="0" maxOccurs="unbounded"/>
			</xsd:sequence>
		</xsd:group>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'testPart')
	XMLATTR_identifier='identifier'		
	XMLATTR_navigationMode=('navigationMode',NavigationMode.DecodeValue,NavigationMode.EncodeValue)	
	XMLATTR_submissionMode=('submissionMode',SubmissionMode.DecodeValue,SubmissionMode.EncodeValue)	
	XMLCONTENT=xmlns.ElementContent

	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.identifier=None
		self.navigationMode=NavigationMode.DEFAULT
		self.submissionMode=SubmissionMode.DEFAULT
		self.PreCondition=[]
		self.BranchRule=[]
		self.ItemSessionControl=None
		self.TimeLimits=None
		self.AssessmentSection=[]
		self.TestFeedback=[]
	
	def GetChildren(self):
		for c in self.PreCondition: yield c
		for c in self.BranchRule: yield c
		if self.ItemSessionControl: yield self.ItemSessionControl
		if self.TimeLimits: yield self.TimeLimits
		for c in self.AssessmentSection: yield c
		for c in self.TestFeedback: yield c

	def ContentChanged(self):
		test=self.FindParent(AssessmentTest)
		if test:
			test.RegisterPart(self)


class Selection(core.QTIElement):
	"""The selection class specifies the rules used to select the child elements
	of a section for each test session::
	
		<xsd:attributeGroup name="selection.AttrGroup">
			<xsd:attribute name="select" type="integer.Type" use="required"/>
			<xsd:attribute name="withReplacement" type="boolean.Type" use="optional"/>
			<xsd:anyAttribute namespace="##other"/>
		</xsd:attributeGroup>
		
		<xsd:group name="selection.ContentGroup">
			<xsd:sequence>
			<xsd:any namespace="##any" minOccurs="0" maxOccurs="unbounded" processContents="skip"/>
			</xsd:sequence>
		</xsd:group>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'selection')
	XMLATTR_select=('select',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_withReplacement=('withReplacement',xsi.DecodeBoolean,xsi.EncodeBoolean)
	XMLCONTENT=xmlns.ElementContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.select=None
		self.withReplacement=False


class Ordering(core.QTIElement):
	"""The ordering class specifies the rule used to arrange the child elements
	of a section following selection. If no ordering rule is given we assume
	that the elements are to be ordered in the order in which they are defined::
	
		<xsd:attributeGroup name="ordering.AttrGroup">
			<xsd:attribute name="shuffle" type="boolean.Type" use="required"/>
			<xsd:anyAttribute namespace="##other"/>
		</xsd:attributeGroup>
		
		<xsd:group name="ordering.ContentGroup">
			<xsd:sequence>
			<xsd:any namespace="##any" minOccurs="0" maxOccurs="unbounded" processContents="skip"/>
			</xsd:sequence>
		</xsd:group>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'ordering')
	XMLATTR_shuffle=('shuffle',xsi.DecodeBoolean,xsi.EncodeBoolean)
	XMLCONTENT=xmlns.ElementContent

	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.shuffle=False
			
	
class SectionPart(core.QTIElement):
	"""Sections group together individual item references and/or sub-sections. A
	number of common parameters are shared by both types of child element::
	
		<xsd:attributeGroup name="sectionPart.AttrGroup">
			<xsd:attribute name="identifier" type="identifier.Type" use="required"/>
			<xsd:attribute name="required" type="boolean.Type" use="optional"/>
			<xsd:attribute name="fixed" type="boolean.Type" use="optional"/>
		</xsd:attributeGroup>
		
		<xsd:group name="sectionPart.ContentGroup">
			<xsd:sequence>
				<xsd:element ref="preCondition" minOccurs="0" maxOccurs="unbounded"/>
				<xsd:element ref="branchRule" minOccurs="0" maxOccurs="unbounded"/>
				<xsd:element ref="itemSessionControl" minOccurs="0" maxOccurs="1"/>
				<xsd:element ref="timeLimits" minOccurs="0" maxOccurs="1"/>
			</xsd:sequence>
		</xsd:group>"""
	XMLATTR_identifier='identifier'
	XMLATTR_required=('required',xsi.DecodeBoolean,xsi.EncodeBoolean)
	XMLATTR_fixed=('fixed',xsi.DecodeBoolean,xsi.EncodeBoolean)	

	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.identifier=None
		self.required=False
		self.fixed=False
		self.PreCondition=[]
		self.BranchRule=[]
		self.ItemSessionControl=None
		self.TimeLimits=None
	
	def GetChildren(self):
		for c in self.PreCondition: yield c
		for c in self.BranchRule: yield c
		if self.ItemSessionControl: yield self.ItemSessionControl
		if self.TimeLimits: yield self.TimeLimits

	def ContentChanged(self):
		test=self.FindParent(AssessmentTest)
		if test:
			test.RegisterPart(self)
			
		
class AssessmentSection(SectionPart):
	"""Represents assessmentSection element
	::
	
		<xsd:attributeGroup name="assessmentSection.AttrGroup">
			<xsd:attributeGroup ref="sectionPart.AttrGroup"/>
			<xsd:attribute name="title" type="string.Type" use="required"/>
			<xsd:attribute name="visible" type="boolean.Type" use="required"/>
			<xsd:attribute name="keepTogether" type="boolean.Type" use="optional"/>
		</xsd:attributeGroup>
		
		<xsd:group name="assessmentSection.ContentGroup">
			<xsd:sequence>
				<xsd:group ref="sectionPart.ContentGroup"/>
				<xsd:element ref="selection" minOccurs="0" maxOccurs="1"/>
				<xsd:element ref="ordering" minOccurs="0" maxOccurs="1"/>
				<xsd:element ref="rubricBlock" minOccurs="0" maxOccurs="unbounded"/>
				<xsd:group ref="sectionPart.ElementGroup" minOccurs="0" maxOccurs="unbounded"/>
			</xsd:sequence>
		</xsd:group>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'assessmentSection')
	XMLATTR_title='title'
	XMLATTR_visible=('visible',xsi.DecodeBoolean,xsi.EncodeBoolean)
	XMLATTR_keepTogether=('keepTogether',xsi.DecodeBoolean,xsi.EncodeBoolean)	
	XMLCONTENT=xmlns.ElementContent

	def __init__(self,parent):
		SectionPart.__init__(self,parent)
		self.title=None
		self.visible=None
		self.keepTogether=True
		self.Selection=None
		self.Ordering=None
		self.RubricBlock=[]
		self.SectionPart=[]
		
	def GetChildren(self):
		for c in SectionPart.GetChildren(self): yield c
		if self.Selection: yield self.Selection
		if self.Ordering: yield self.Ordering
		for c in self.RubricBlock: yield c
		for c in self.SectionPart: yield c


class AssessmentItemRef(SectionPart):
	"""Items are incorporated into the test by reference and not by direct
	aggregation::
	
		<xsd:attributeGroup name="assessmentItemRef.AttrGroup">
			<xsd:attributeGroup ref="sectionPart.AttrGroup"/>
			<xsd:attribute name="href" type="uri.Type" use="required"/>
			<xsd:attribute name="category" use="optional">
				<xsd:simpleType>
					<xsd:list itemType="identifier.Type"/>
				</xsd:simpleType>
			</xsd:attribute>
		</xsd:attributeGroup>
		
		<xsd:group name="assessmentItemRef.ContentGroup">
			<xsd:sequence>
				<xsd:group ref="sectionPart.ContentGroup"/>
				<xsd:element ref="variableMapping" minOccurs="0" maxOccurs="unbounded"/>
				<xsd:element ref="weight" minOccurs="0" maxOccurs="unbounded"/>
				<xsd:element ref="templateDefault" minOccurs="0" maxOccurs="unbounded"/>
			</xsd:sequence>
		</xsd:group>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'assessmentItemRef')
	XMLATTR_href=('href',html.DecodeURI,html.EncodeURI)
	XMLATTR_category='category'
	XMLCONTENT=xmlns.ElementContent

	def __init__(self,parent):
		SectionPart.__init__(self,parent)
		self.href=None
		self.category=[]
		self.VariableMapping=[]
		self.Weight=[]
		self.TemplateDefault=[]
		
	def GetChildren(self):
		for c in SectionPart.GetChildren(self): yield c
		for c in self.VariableMapping: yield c
		for c in self.Weight: yield c
		for c in self.TemplateDefault: yield c


class TestForm(object):
	"""A TestForm is a particular instance of a test, after selection and
	ordering rules have been applied.
	
	QTI tests can contain selection and ordering rules that enable basic
	variation between instances, or 'forms' of the test.  Selection and ordering
	is not the only source of variation but it provides the basic framework for
	the test.

	The TestForm acts like a (read-only) dictionary of compound identifiers of
	form (identifier,number).  The identifier is the identifier of a test
	component and the number is an instance number - 0 being the first instance
	of the component in the test, 1 the second instance, etc.
	
	Test components are either test parts or sections.  The values in the
	dictionary are lists of the compound identifiers of the child components.
	Invisible sections are not present in the dictionary, the children of a
	hidden section are mixed in to their parent's list.  This extends to hidden
	subsections and so on as forms are built depth-first."""
	
	def __init__(self,test):
		self.test=test		#: the test from which this form was created
		self.parts=[]		#: an ordered list of identifiers of each part 
		self.map={}
		for part in self.test.TestPart:
			partList=[]
			self.parts.append(part.identifier)
			# A part always contains all child sections
			for s in part.AssessmentSection:				
				if s.visible:
					self.Select(s,0)
					partList.append((s.identifier,0))
				else:
					# no shuffling in test parts, just add a hidden section as a block					
					partList=partList+self.Select(s)
			self.map[(part.identifier,0)]=partList
			
	def Select(self,section,instanceNumber=None):
		"""Runs the selection and ordering rules for *section*.
		
		It returns a list of 2-tuples consisting of the part identifier and an instance
		number.  Instance numbers start at 0.
		
		If instanceNumber is provided then it also adds the list to the dictionary."""
		children=section.SectionPart
		if section.Ordering:
			shuffle=section.Ordering.shuffle
		else:
			shuffle=False
		if section.Selection:
			targetSize=section.Selection.select
			withReplacement=section.Selection.withReplacement
		else:
			targetSize=len(children)
			withReplacement=False
		selection=[]
		bag=list(xrange(len(children)))
		shuffleList=[]
		# Step 1: make sure we select required children at least once
		for i in xrange(len(children)):
			if children[i].required:
				selection.append(i)
				if not withReplacement:
					bag.remove(i)
		if len(selection)>targetSize:
			raise core.SelectionError("#%s contains a selection rule that selects fewer child elements than the number of required elements"%section.identifier)
		# Step 2: top up the selection until we reach the target size
		while len(selection)<targetSize:
			if bag:
				i=random.choice(bag)
				selection.append(i)
				if not withReplacement:
					bag.remove(i)
			else:
				raise core.SelectionError("Number of children to select in #%s exceeds the number of child elements, use withReplacement to resolve"%section.identifier)
		shuffleList=[]
		# Step 3: sort the list to ensure the position of fixed children is honoured  						
		selection.sort()
		# Step 4: transform to a list of identifiers...
		#			replace invisible sections with their contents if we need to split/shuffle them
		#			replace floating children with empty slots and put them in the shuffle list
		newSelection=[]
		for i in selection:
			child=children[i]
			invisibleSection=isinstance(child,AssessmentSection) and not child.visible
			if shuffle and not child.fixed:
				# We're shuffling, add a free slot to the selection
				newSelection.append(None)
				if invisibleSection and not child.keepTogether:
					# the grand-children go into the shuffleList independently
					# What does a fixed grand-child mean in this situation?
					# we raise an error at the moment
					for gChildID,gChildNum in self.Select(child):
						gChild=self.test.GetPart(gChildID)
						if gChild.fixed:
							raise core.SelectionError("Fixed child of invisible section #%s is subject to parent shuffling, use keepTogether to resolve"%child.identifier)
						shuffleList.append(gChildID)
				else:
					# invisible sections with keepTogether go in to the shuffle list just like items
					shuffleList.append(child.identifier)
			else:
				# We're not shuffling or this child is fixed in position
				if invisibleSection:
					for gChildID,gChildNum in self.Select(child):
						newSelection.append(gChildID)
				else:
					# regular item or sub-section
					newSelection.append(child.identifier)
		selection=newSelection
		if shuffleList:
			# Step 5: shuffle!
			random.shuffle(shuffleList)
			# Expanded invisible sections may mean we have more shuffled items than free slots
			# We need to partition the shuffle list into n buckets where n is the number of slots
			# We choose to put one item in each bucket initially then randomly assign the rest
			# This gives the expected result in the case where the shuffle list contains one
			# item for each slot.  It also preserves the relative order of fixed items and
			# ensures that adjacent fixed items are not split by a random choice.  Similarly,
			# items fixed at the start or end of the section remain in place
			i=0
			buckets=[]
			for child in selection:
				if child is None:
					buckets.append([shuffleList[i]])
					i+=1
			while i<len(shuffleList):
				# choose a random bucket
				random.choice(buckets).append(shuffleList[i])
				i+=1
			# Now splice the buckets into the selection
			for b in buckets:
				i=selection.index(None)
				selection[i:i+1]=b
			# Step 6: finally, we are ready to bring in the rest of the invisible sections
			#			only required if we are shuffling of course
			newSelection=[]
			for childID in selection:
				child=self.test.GetPart(childID)
				if isinstance(child,AssessmentSection) and not child.visible:
					for gChildID,gChildNum in self.Select(child):
						newSelection.append(gChildID)
				else:
					newSelection.append(childID)
			selection=newSelection
		# Step 7: add instance numbers to the selection
		idCount={}
		for i in xrange(len(selection)):
			childID=selection[i]
			n=idCount.get(childID,0)
			selection[i]=(childID,n)
			idCount[childID]=n+1
		if instanceNumber is not None:
			# We are being asked to record this section in the map
			self.map[(section.identifier,instanceNumber)]=selection
		return selection
			
	def __len__(self):
		return len(self.map)
			
	def __getitem__(self,identifier):
		"""Returns the list of children of *identifier* or raises KeyError if
		there is no test part or (selected) section with that identity."""
		return self.map[identifier]
			
	def __setitem__(self,varName,value):
		raise TypeError("TestForms are read-only")

	def __delitem__(self,varName):
		raise TypeError("TestForms are read-only")
	
	def __iter__(self):
		return iter(self.map)

	def __contains__(self,identifier):
		return identifier in self.map
			