from PyAssess.w3c.xmlschema import XMLSchemaNamespace

from common import *
from assessmentItem import AssessmentItem, RubricBlock

class SectionPart:
	def __init__(self,identifier):
		self.SetIdentifier(identifier)
		self.required=1
		self.fixed=0
		self.preCondition=[]
		self.branchRule=[]
		self.itemSessionControl=ItemSessionControl()
		self.timeLimits=TimeLimits()
		
	def SetXMLAttributes(self,element):
		element.SetAttribute(None,'identifier',self.identifier)
		if not self.required:
			element.SetAttribute(None,'required',FormatBoolean(0))
		if self.fixed:
			element.SetAttribute(None,'fixed',FormatBoolean(1))
	
	def WriteXMLContent(self,xf):
		for e in self.preCondition:
			e.WriteXML(xf)
		for e in self.branchRule:
			e.WriteXML(xf)
		self.itemSessionControl.WriteXML(xf)
		self.timeLimits.WriteXML(xf)
					
	def SetIdentifier(self,identifier):
		if type(identifier) in StringTypes:
			self.identifier=identifier
		else:
			raise TypeError	

	def SetRequired(self,required):
		if required in (0,1):
			self.required=required
		else:
			raise ValueError
	
	def SetFixed(self,fixed):
		if fixed in (0,1):
			self.fixed=fixed
		else:
			raise ValueError

class ItemSessionControl:
	def __init__(self):
		self.maxAttempts=1
		self.showFeedback=0
		self.allowReview=1
		self.showSolution=0
		self.allowComment=0
	
	def WriteXML(self,xf):
		if self.maxAttempts!=1 or self.showFeedback or not self.allowReview or self.showSolution or self.allowComment:
			# settings other than the default: write out an element
			xe=Element(IMSQTINamespace,'itemSessionControl')
			if self.maxAttempts!=1:
				xe.SetAttribute(None,'maxAttempts',FormatInteger(self.maxAttempts))
			if self.showFeedback:
				xe.SetAttribute(None,'showFeedback',FormatBoolean(1))
			if not self.allowReview:
				xe.SetAttribute(None,'allowReview',FormatBoolean(0))
			if self.showSolution:
				xe.SetAttribute(None,'showSolution',FormatBoolean(1))
			if self.allowComment:
				xe.SetAttribute(None,'allowComment',FormatBoolean(0))
			xf.AppendEmptyTag(xe)
			
	def SetMaxAttempts(self,maxAttempts):
		if type(maxAttempts) in (IntType,LongType) and maxAttempts>=0:
			self.maxAttempts=maxAttempts
		else:
			raise ValueError
	
	def SetShowFeedback(self,showFeedback):
		if showFeedback in (0,1):
			self.showFeedback=showFeedback
		else:
			raise ValueError
	
	def SetAllowReview(self,allowReview):
		if allowReview in (0,1):
			self.allowReview=allowReview
		else:
			raise ValueError
	
	def SetShowSolution(self,showSolution):
		if showSolution in (0,1):
			self.showSolution=showSolution
		else:
			raise ValueError
	
	def SetAllowComment(self,allowComment):
		if allowComment in (0,1):
			self.allowComment=allowComment
		else:
			raise ValueError

class TimeLimits:
	def __init__(self):
		self.minTime=None
		self.maxTime=None
	
	def WriteXML(self,xf):
		if self.minTime is not None or self.maxTime is not None:
			xe=Element(IMSQTINamespace,'timeLimits')
			if self.minTime is not None:
				xe.SetAttribute(None,'minTime',FormatQTIFloat(self.minTime))
			if self.maxTime is not None:
				xe.SetAttribute(None,'maxTime',FormatQTIFloat(self.maxTime))
			xf.AppendEmptyTag(xe)
		
	def SetMinTime(self,minTime):
		if type(minTime) in (IntType,LongType,FloatType) and minTime>=0:
			self.minTime=float(minTime)
		elif minTime is None:
			self.minTime=None
		else:
			raise ValueError
	
	def SetMaxTime(self,maxTime):
		if type(maxTime) in (IntType,LongType,FloatType) and maxTime>=0:
			self.maxTime=float(maxTime)
		elif maxTime is None:
			self.maxTime=None
		else:
			raise ValueError
	
								
class AssessmentSection(SectionPart):
	def __init__(self,identifier,title,visible):
		SectionPart.__init__(self,identifier)
		self.SetTitle(title)
		self.SetVisible(visible)
		self.keepTogether=1
		self.selection=Selection(0)
		self.ordering=None
		self.rubricBlock=[]
		self.children=[]
		
	def WriteXML(self,xf):
		xe=Element(IMSQTINamespace,'assessmentSection')
		if xf.Root():
			xe.SetAttribute(None,'xmlns:xsi',XMLSchemaNamespace)
			xe.SetAttribute(XMLSchemaNamespace,'schemaLocation',IMSQTINamespace+' '+IMSQTISchemaLocation)
		SectionPart.SetXMLAttributes(self,xe)		
		xe.SetAttribute(None,'title',self.title)
		xe.SetAttribute(None,'visible',FormatBoolean(self.visible))
		if not self.keepTogether:
			xe.SetAttribute(None,'keepTogether',FormatBoolean(self.keepTogether))
		xf.AppendStartTag(xe,1)
		SectionPart.WriteXMLContent(self,xf)
		self.selection.WriteXML(xf)
		#self.ordering.WriteXML(xf)
		for e in self.rubricBlock:
			e.WriteXML(xf)
		for e in self.children:
			e.WriteXML(xf)
		# add all the other stuff
		xf.AppendEndTag()

	def SetTitle(self,title):
		if type(title) in StringTypes:
			self.title=title
		else:
			raise TypeError
	
	def SetVisible(self,visible):
		if visible in (0,1):
			self.visible=visible
		else:
			raise ValueError
	
	def SetKeepTogether(self,keepTogether):
		if keepTogether in (0,1):
			self.keepTogether=keepTogether
		else:
			raise ValueError
	
	def CreatSelection(self,select):
		self.selection=Selection(select)

	def AddRubric(self,rubric):
		if isinstance(rubric,RubricBlock):
			self.rubricBlock.append(rubric)
		else:
			raise TypeError
	
	def DeleteRubric(self,rubric):
		self.rubricBlock.remove(rubric)

	def AddChild(self,childPart):
		if isinstance(childPart,SectionPart):
			self.children.append(childPart)
		else:
			raise TypeError
					
class AssessmentItemRef(SectionPart):
	def __init__(self,href):
		if isinstance(href,AssessmentItem):
			# This reference is being created from an existing item instead
			self.item=href
			self.href=None
		else:
			self.href=href
			self.item=None
		self.category=[]
		self.variableMapping={}
		self.weight={}
	
							
class Selection:
	def __init__(self,select):
		# we interpret a select value of 0 as 'all'
		self.SetSelect(select)
		self.withReplacement=0
	
	def WriteXML(self,xf):
		if self.select!=0:
			# only show the element if there is something to say
			xe=Element(IMSQTINamespace,'selection')
			xe.SetAttribute(None,'select',FormatInteger(self.select))
			if self.withReplacement:
				xe.SetAttribute(None,'withReplacement',FormatBoolean(1))
			xf.AppendEmptyTag(xe)
			
	def SetSelect(self,select):
		if type(select) in (IntType,LongType) and select>=0:
			self.select=select
		else:
			raise ValueError
	
	def SetWithReplacement(self,withReplacement):
		if withReplacement in (0,1):
			self.withReplacement=withReplacement
		elif withReplacement is None:
			self.withReplacement=0
		else:
			raise ValueError
			
	