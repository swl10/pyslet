from string import split, join

from common import *
from assessmentItem import ChoiceInteraction, SimpleChoice

class TextCmdIndexError(IMSQTIError): pass

class AssessmentItemView:
	"""Abstract class for implementing instances of item delivery engines"""
	def __init__(self,session):
		self.session=session

	def RenderText(self,text):
		raise NotImplemented

	def RenderItemBody(self,body):
		body.RenderChildren(self)

	def UnimplementedXHTML(self,bodyElement):
		raise NotImplementedError
	
	# Text Elements
	RenderAbbreviation=UnimplementedXHTML
	RenderAcronym=UnimplementedXHTML
	RenderAddress=UnimplementedXHTML
	RenderBlockquote=UnimplementedXHTML
	RenderLineBreak=UnimplementedXHTML
	RenderCitation=UnimplementedXHTML
	RenderCodeFragment=UnimplementedXHTML
	RenderDefinition=UnimplementedXHTML
	RenderDiv=UnimplementedXHTML
	RenderEmphasis=UnimplementedXHTML
	RenderHeading1=UnimplementedXHTML
	RenderHeading2=UnimplementedXHTML
	RenderHeading3=UnimplementedXHTML
	RenderHeading4=UnimplementedXHTML
	RenderHeading5=UnimplementedXHTML
	RenderHeading6=UnimplementedXHTML
	RenderKeyboardInput=UnimplementedXHTML
	RenderParagraph=UnimplementedXHTML
	RenderPreformattedText=UnimplementedXHTML
	RenderQuotation=UnimplementedXHTML
	RenderSampleOutput=UnimplementedXHTML
	RenderSpan=UnimplementedXHTML
	RenderStrongEmphasis=UnimplementedXHTML
	RenderPragramVariable=UnimplementedXHTML
	# List Elements
	RenderDefinitionList=UnimplementedXHTML
	RenderDefinitionTerm=UnimplementedXHTML
	RenderDefinitionItem=UnimplementedXHTML
	RenderOrderedList=UnimplementedXHTML
	RenderUnorderedList=UnimplementedXHTML
	RenderListItem=UnimplementedXHTML
	# Object Elements
	RenderObject=UnimplementedXHTML
	# Presentation Elements
	RenderBold=UnimplementedXHTML
	RenderBig=UnimplementedXHTML
	RenderHorizontalRule=UnimplementedXHTML
	RenderItalic=UnimplementedXHTML
	RenderSmall=UnimplementedXHTML
	RenderSubscript=UnimplementedXHTML
	RenderSuperscript=UnimplementedXHTML
	RenderTeletype=UnimplementedXHTML
	# Table Elements
	RenderTable=UnimplementedXHTML
	# Image Element
	RenderImage=UnimplementedXHTML	
	# Hypertext Element
	RenderHypertextLink=UnimplementedXHTML
	
	# Interactions
	def UnimplementedInteraction(self,interaction):
		raise NotImplementedError

	RenderChoiceInteraction=UnimplementedInteraction
	RenderOrderInteraction=UnimplementedInteraction
		
	
class TextItemView(AssessmentItemView):
	def __init__(self,session,fOut):
		AssessmentItemView.__init__(self,session)
		self.fOut=fOut
		self.ResetView()
				
	def ResetView(self):
		self.firstBlock=1
		self.firstInline=0
		self.cmdObjects=[]
	
	def RenderItemBody(self,body):
		self.ResetView()
		body.RenderChildren(self)

	def RenderText(self,text):
		# colapse spaces
		if text:
			words=[]
			if text[0] in " \t\n\r" and not self.firstInline:
				words=['']
			words=words+(split(text))
			if text[-1] in " \t\n\r":
				words.append([''])
			self.fOut.write(join(words,' '))
		self.firstInline=0
		
	def RenderChoiceInteraction(self,choiceInteraction):
		if choiceInteraction.prompt:
			# Blank line before prompt
			if not self.firstBlock:
				self.fOut.write('\n')
			self.firstBlock=0
			self.firstInline=1
			choiceInteraction.prompt.RenderChildren(self)
			self.fOut.write('\n\n')
		# to do: deal with shuffled choices in itemSession
		value=self.session.GetResponseValue(choiceInteraction.responseIdentifier)
		for choice in choiceInteraction.children:
			selected=(value[0]==Cardinality.Single and value[2]==choice.identifier) or \
				(value[0]==Cardinality.Multiple and choice.identifier in value[2])
			if selected:
				selected='*'
			else:
				selected=' '
			self.firstBlock=0
			self.cmdObjects.append(choice)
			self.fOut.write('[%i%s] '%(len(self.cmdObjects),selected))
			choice.RenderChildren(self)
			self.fOut.write('\n')

	def RenderParagraph(self,p):
		"""Blank line before, always ends in a line break"""
		if not self.firstBlock:
			self.fOut.write('\n')
		else:
			self.firstBlock=0
		self.firstInline=1
		p.RenderChildren(self)
		self.fOut.write('\n')
		
	def DoAction(self,cmdStr):
		cmd=split(cmdStr)
		if cmd[0].isdigit():
			cmdNum=int(cmd[0])-1
			if cmdNum<0 or cmdNum>=len(self.cmdObjects):
				raise TextCmdIndexError()
			cmdObject=self.cmdObjects[cmdNum]
			if isinstance(cmdObject,SimpleChoice):
				if isinstance(cmdObject.parent,ChoiceInteraction):
					cmdObject.parent.Select(cmdObject,self.session)
			else:
				raise NotImplementedError
			