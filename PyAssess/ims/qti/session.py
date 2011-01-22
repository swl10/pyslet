from common import *
from assessmentItem import ResponseDeclaration, OutcomeDeclaration

class AssessmentItemState:
	"""Item State enumeration"""
	Initial=1
	Interacting=2
	Suspended=3
	ModalFeedback=4
	Closed=5
	Solution=6
	Review=7
	
	MaxValue=7
	

class ItemSession:
	def __init__(self,item):
		self.item=item
		self.variables={
			'completionStatus':[Cardinality.Single,BaseType.Identifier,'not_attempted'],
			'duration':[Cardinality.Single,BaseType.Duration,0.0]
			}
		# import pdb; pdb.set_trace()
		for v in self.item.variables.keys():
			vd=self.item.variables[v]
			if isinstance(vd,ResponseDeclaration):
				# All responses start off as NULL
				self.variables[v]=[vd.cardinality,vd.baseType,None]
			elif isinstance(vd,OutcomeDeclaration):
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
		self.userState=AssessmentItemState.Initial
		self.attempts=0
		
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
			
	def BeginAttempt(self):
		# if this is the  beginning of the first attempt, set all response variables to their defaults
		if self.attempts==0:
			for v in self.item.variables.keys():
				vd=self.item.variables[v]
				if isinstance(vd,ResponseDeclaration):
					self.variables[v][2]=vd.defaultValue
		self.userState=AssessmentItemState.Interacting
		self.variables['completionStatus'][2]='unknown'
		self.attempts+=1
		
	def EndAttempt(self,responseValues):
		for v in responseValues.keys():
			value=self.variables[v]
			newValue=responseValues[v]
			if isinstance(self.item.variables[v],ResponseDeclaration):
				CheckValue(value[0],value[1],newValue)
				value[2]=newValue
			else:
				raise IMSQTIError("Bad variable updated in session: %s"%v)
			
	