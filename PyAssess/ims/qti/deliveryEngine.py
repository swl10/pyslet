from string import split, join

from common import *
from assessmentItem import ChoiceInteraction, OrderInteraction, ExtendedTextInteraction, SimpleChoice, Orientation

class TextCmdIndexError(IMSQTIError): pass
class InvalidSelectionError(IMSQTIError): pass

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
	RenderProgramVariable=UnimplementedXHTML
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
	RenderExtendedTextInteraction=UnimplementedInteraction
	
class TextItemView(AssessmentItemView):
	def __init__(self,session,fOut):
		AssessmentItemView.__init__(self,session)
		self.fOut=fOut
		self.choiceTable={}
		self.ResetView()
				
	def ResetView(self):
		self.firstBlock=1
		self.firstInline=0
		self.preserveSpace=0
		self.cmdObjects=[]
			
	def RenderItemBody(self,body):
		self.ResetView()
		body.RenderChildren(self)

	def RenderText(self,text):
		if text:
			if self.preserveSpace:
				self.fOut.write(text)
			else:
				# colapse spaces
				words=[]
				if text[0] in " \t\n\r" and not self.firstInline:
					words=['']
				words=words+split(text)
				if text[-1] in " \t\n\r":
					words.append('')
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
		value=self.session.GetResponseValue(choiceInteraction.responseIdentifier)
		choices=self.session.GetShuffledChoices(choiceInteraction)
		for choice in choices:
			selected=(value[0]==Cardinality.Single and value[2]==choice.identifier) or \
				(value[0]==Cardinality.Multiple and value[2] is not None and
				choice.identifier in value[2])
			if selected:
				selected='*'
			else:
				selected=' '
			self.firstBlock=0
			self.cmdObjects.append(choice)
			self.fOut.write('[%i%s] '%(len(self.cmdObjects),selected))
			choice.RenderChildren(self)
			self.fOut.write('\n')

	def RenderOrderInteraction(self,orderInteraction):
		if orderInteraction.prompt:
			# Blank line before prompt
			if not self.firstBlock:
				self.fOut.write('\n')
			self.firstBlock=0
			self.firstInline=1
			orderInteraction.prompt.RenderChildren(self)
			self.fOut.write('\n\n')
		value=self.session.GetResponseValue(orderInteraction.responseIdentifier)
		choices=self.session.GetShuffledChoices(orderInteraction)
		if value[2] is None:
			# we take a copy of the choices so that we can reorder as we go
			value[2]=map(lambda x: x.identifier,choices)
		# We fill this table every time, which is a little wasteful but
		# we have no hard and fast way of determining if this is the first
		# time we have been rendered.
		for choice in choices:
			self.choiceTable[choice.identifier]=choice	
		for value in value[2]:
			choice=self.choiceTable[value]
			self.firstBlock=0
			self.cmdObjects.append(choice)
			self.fOut.write('[%i] '%len(self.cmdObjects))
			choice.RenderChildren(self)
			if orderInteraction.orientation==Orientation.Horizontal:
				self.fOut.write('  ')
			else:
				self.fOut.write('\n')
		if orderInteraction.orientation==Orientation.Horizontal:
			self.fOut.write('\n')

	def ExtendedTextInteractionDimensions(self,interaction):
		if interaction.expectedLines:
			rows=interaction.expectedLines
		else:
			rows=1
		if interaction.expectedLength:
			cols=interaction.expectedLength/rows
			if interaction.expectedLength%rows:
				cols+=1
			if cols>100:
				cols=100
		else:
			cols=80	
		return rows,cols
			
	def RenderExtendedTextInteraction(self,interaction):
		if interaction.prompt:
			# Blank line before prompt
			if not self.firstBlock:
				self.fOut.write('\n')
			self.firstBlock=0
			self.firstInline=1
			interaction.prompt.RenderChildren(self)
			self.fOut.write('\n')
		rows,cols=self.ExtendedTextInteractionDimensions(interaction)
		value=self.session.GetResponseValue(interaction.responseIdentifier)
		if value[0]==Cardinality.Single:
			self.cmdObjects.append(interaction)
			if value[2] is None:
				lines=[]
			else:
				lines=value[2].splitlines()
			if len(lines)>rows:
				rows=len(lines)
			else:
				while len(lines)<rows:
					lines.append(' '*cols)
			prompt='[%i'%len(self.cmdObjects)
			self.fOut.write(prompt+':'+lines[0])
			for i in range(1,len(lines)):
				self.fOut.write('\n'+' '*len(prompt)+'|'+lines[i])
			self.fOut.write(']\n')
		else:
			raise NotImplementedError	

	def RenderInvisible(self,element):
		element.RenderChildren(self)
		
	def RenderBlock(self,element):
		"""Blank line before, always ends in a line break"""
		if not self.firstBlock:
			self.fOut.write('\n')
		else:
			self.firstBlock=0
		self.firstInline=1
		element.RenderChildren(self)
		self.fOut.write('\n')
	
	def RenderHeading(self,element,level):
		"""As for block but with indent"""
		if not self.firstBlock:
			self.fOut.write('\n')
		else:
			self.firstBlock=0
		self.fOut.write(' '*(level-1)+'>> ')
		self.firstInline=1
		element.RenderChildren(self)
		self.fOut.write('\n')

	###
	# Text Elements
	###
	RenderAbbreviation=RenderInvisible
	RenderAcronym=RenderInvisible
	RenderAddress=RenderBlock
	RenderBlockquote=RenderBlock

	def RenderLineBreak(self,element):
		self.fOut.write('\n')
			
	RenderCitation=RenderInvisible
	RenderCodeFragment=RenderInvisible
	RenderDefinition=RenderInvisible
	RenderDiv=RenderInvisible
	
	def RenderEmphasis(self,element):
		self.fOut.write("*")
		element.RenderChildren(self)
		self.fOut.write("*")

	def RenderHeading1(self,element): self.RenderHeading(element,1)		
	def RenderHeading2(self,element): self.RenderHeading(element,2)		
	def RenderHeading3(self,element): self.RenderHeading(element,3)		
	def RenderHeading4(self,element): self.RenderHeading(element,4)		
	def RenderHeading5(self,element): self.RenderHeading(element,5)		
	def RenderHeading6(self,element): self.RenderHeading(element,6)		

	RenderKeyboardInput=RenderInvisible
	RenderParagraph=RenderBlock
	
	def RenderPreformattedText(self,element):
		save=self.preserveSpace
		self.preserveSpace=1
		self.RenderBlock(element)
		self.preserveSpace=save
			
	def RenderQuotation(self,element):
		self.fOut.write('"')
		element.RenderChildren(self)
		self.fOut.write('"')
			
	RenderSampleOutput=RenderInvisible
	RenderSpan=RenderInvisible

	def RenderStrongEmphasis(self,element):
		self.fOut.write("***")
		element.RenderChildren(self)
		self.fOut.write("***")
		
	RenderProgramVariable=RenderInvisible

	def DoAction(self,args):
		if args[0].isdigit():
			cmdNum=int(args[0])-1
			if cmdNum<0 or cmdNum>=len(self.cmdObjects):
				raise TextCmdIndexError()
			cmdObject=self.cmdObjects[cmdNum]
			if isinstance(cmdObject,SimpleChoice):
				if isinstance(cmdObject.parent,ChoiceInteraction):
					if not cmdObject.parent.Select(cmdObject,self.session):
						raise InvalidSelectionError()
				elif isinstance(cmdObject.parent,OrderInteraction) and len(args)>=2:
					direction=args[1].lower()
					value=self.session.GetResponseValue(cmdObject.parent.responseIdentifier)
					newPos=pos=value[2].index(cmdObject.identifier)
					if direction in ["up","u"]:
						if pos:
							newPos=pos-1
					elif direction in ["down","d"]:
						if pos<len(value[2])-1:
							newPos=pos+1
					if newPos!=pos:
						swp=value[2][pos]
						value[2][pos]=value[2][newPos]
						value[2][newPos]=swp
			elif isinstance(cmdObject,ExtendedTextInteraction):
				value=self.session.GetResponseValue(cmdObject.responseIdentifier)
				rows,cols=self.ExtendedTextInteractionDimensions(cmdObject)
				lines=['']
				for word in args[1:]:
					line=lines[-1]
					if (line):
						if len(line)+1+len(word)>cols:
							lines.append(word)
						else:
							lines[-1]=lines[-1]+' '+word
					else:
						lines[-1]=word
				value[2]=join(lines,'\n')
			else:
				raise NotImplementedError
			