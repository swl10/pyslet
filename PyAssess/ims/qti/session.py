from common import *
from assessmentItem import ResponseDeclaration, OutcomeDeclaration
from random import shuffle

class AssessmentItemState:
	"""Item State enumeration"""
	Initial=1
	Interacting=2
	Suspended=3
	Submitted=4
	ModalFeedback=5
	Closed=6
	Solution=7
	Review=8
	
	MaxValue=8
	

class ItemSession:
	def __init__(self,item):
		self.item=item
		self.variables={
			'completionStatus':[Cardinality.Single,BaseType.Identifier,'not_attempted']
			}
		if item.timeDependent:
			self.variables['duration']=[Cardinality.Single,BaseType.Duration,0.0]
		# import pdb; pdb.set_trace()
		# Set response variables to their defaults
		for v in self.item.variables.keys():
			vd=self.item.variables[v]
			if isinstance(vd,ResponseDeclaration):
				# All responses start off as NULL
				self.variables[v]=[vd.cardinality,vd.baseType,None]
		self.SetOutcomeDefaults()
		self.userState=AssessmentItemState.Initial
		self.attempts=0
		self.shuffledChoices={}
	
	def GetVariableNames(self):
		return self.variables.keys()
				
	def GetVariableValue(self,identifier):
		return self.variables[identifier]
			
	def GetOutcomeValue(self,identifier):
		if identifier=='completionStatus' or isinstance(self.item.LookupVariableDeclaration(identifier),OutcomeDeclaration):
			return self.variables[identifier]
		else:
			raise IMSQTIError("undeclared outcome %s"%identifier)
			
	def GetResponseValue(self,identifier):
		if identifier=='duration' or isinstance(self.item.LookupVariableDeclaration(identifier),ResponseDeclaration):
			return self.variables[identifier]
		else:
			raise IMSQTIError("undeclared response %s"%identifier)
	
	def SetOutcomeDefaults(self):
		for v in self.item.variables.keys():
			vd=self.item.variables[v]
			if isinstance(vd,OutcomeDeclaration):
				# All outcomes take the default value or NULL (except numbers, which auto-default to 0)
				if vd.defaultValue is None:
					if vd.baseType==BaseType.Integer:
						value=0
					elif vd.baseType==BaseType.Float:
						value=0.0
					else:
						value=None
				else:
					value=vd.defaultValue
				self.variables[v]=[vd.cardinality,vd.baseType,value]
	
	def GetShuffledChoices(self,interaction):
		"""Returns a list of shuffled choices for the interaction ordered for this session.
		This method works 'on demand' and then stores the result in a dictionary keyed
		on response identifier."""
		if interaction.shuffle:
			choices=self.shuffledChoices.get(interaction.responseIdentifier,None)
			if choices is None:
				shuffleChoices=[]
				for choice in interaction.children:
					if not choice.fixed:
						shuffleChoices.append(choice)
				shuffle(shuffleChoices)
				choices=[]
				for choice in interaction.children:
					if not choice.fixed:
						choices.append(shuffleChoices.pop())
					else:
						choices.append(choice)
				self.shuffledChoices[interaction.responseIdentifier]=choices
		else:
			choices=interaction.children
		return choices
				
	def BeginAttempt(self):
		# if this is the  beginning of the first attempt, set all response variables to their defaults
		if self.userState==AssessmentItemState.Initial:
			for v in self.item.variables.keys():
				vd=self.item.variables[v]
				if isinstance(vd,ResponseDeclaration):
					self.variables[v][2]=vd.defaultValue
		self.userState=AssessmentItemState.Interacting
		self.variables['completionStatus'][2]='unknown'
		self.attempts+=1
		
	def EndAttempt(self,responseValues={}):
		# Step 1: update the response values as requested
		if self.userState not in (AssessmentItemState.Interacting, AssessmentItemState.Suspended):
			raise IMSQTIError("Invalid session state transition")
		for v in responseValues.keys():
			value=self.variables[v]
			newValue=responseValues[v]
			if isinstance(self.item.variables[v],ResponseDeclaration):
				CheckValue(value[0],value[1],newValue)
				value[2]=newValue
			else:
				raise IMSQTIError("Bad variable updated in session: %s"%v)
		# Step 2: for non-adaptive items, reset the outcomes to defaults if necessary
		if self.attempts and not self.item.adaptive:
			self.SetOutcomeDefaults()
		self.userState=AssessmentItemState.Submitted
		if self.item.responseProcessing:
			self.item.responseProcessing.Run(self)
			self.ResponseProcessingComplete()
	
	def ResponseProcessingComplete(self):
		if self.userState==AssessmentItemState.Submitted:
			self.userState=AssessmentItemState.ModalFeedback
		else:
			raise IMSQTIError("Invalid session state transition")
			