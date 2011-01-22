from xml.sax import make_parser, handler

from PyAssess.ieee.p1484_12 import LOMMetadata
from PyAssess.w3c.xmlnamespaces import XMLNamespace
from PyAssess.iso.iso8601 import Duration
from PyAssess.ims.md import IMSIdentifier

from common import *
from asi import AssessmentSection, AssessmentItemRef, AssessmentItem, RubricBlock, Div, Paragraph, Span, Object, TextRun, ParseView

VIEW_MAP={'administrator':'invigilator','adminauthority':'invigilator',
	'assessor':'scorer','author':'author','candidate':'candidate',
	'invigilator':'invigilator','proctor':'invigilator','psychometrician':'scorer',
	'tutor':'tutor',
	'scorer':'scorer'}

class QuestestinteropParser(handler.ContentHandler, handler.ErrorHandler):
	def __init__(self):
		self.parser=make_parser()
		self.parser.setFeature(handler.feature_namespaces,1)
		self.parser.setContentHandler(self)
		self.parser.setErrorHandler(self)

	def ReadQuestestinterop(self,f):
		self.ResetParser()
		self.parser.parse(f)
		return self.objects
		
	def ResetParser(self):
		self.foundQuestestinterop=0
		self.mixedContent=0
		self.qtiNamespace=None
		self.objects=[]
		self.md=None
		self.comments=[]
		self.cObject=None
		self.objectStack=[]
		self.metadataStack=[]
		self.skipping=0
		self.data=[]
		
	def setDocumentLocator(self,locator):
		self.locator=locator

	def Position(self):
		return str(locator.getLineNumber())+str(locator.getColumnNumber())
					
	def startElementNS(self,name,qname,attrs):
		ns,localName=name
		if self.foundQuestestinterop:
			if self.skipping:
				self.skipping+=1
			elif ns==self.qtiNamespace:
				# make sure we collect any data *before* we start the new element
				# when handling mixed content model (i.e., body elements)
				if self.mixedContent:
					if self.data:
						self.ProcessTextRun()
				method=self.startMethods.get(localName)
				if method:
					method(self,ns,localName,attrs)
				else:
					raise IMSQTIError("Unknown QTI version 1 element <%s>"%localName)
			else:
				self.StartSkipped(ns,localName,attrs)
		else:
			if localName!="questestinterop":
				raise IMSQTIError("expected <questestinterop>, found <%s>"%localName)
			# we ignore the namespace as 1.x was based on DTDs
			self.qtiNamespace=ns
			self.foundQuestestinterop=1
			self.md=LOMMetadata()
			self.objects=[self.md]
			
	def endElementNS(self,name,qname):
		ns,localName=name
		if self.skipping:
			self.skipping-=1
		elif ns==self.qtiNamespace:
			method=self.endMethods.get(localName)
			if method:
				method(self,ns,localName)
				
	def characters(self,content):
		self.data.append(content)
	
	def PushObject(self,newObject):
		self.objectStack.append(self.cObject)
		self.cObject=newObject
	
	def PopObject(self):
		oldObject=self.cObject
		self.cObject=self.objectStack.pop()
		return oldObject
	
	def PushMetadata(self):
		self.metadataStack.append((self.md,self.comments))
		self.md=LOMMetadata()
		self.comments=[]
			
	def PopMetadata(self):
		oldMD=self.md
		if self.comments:
			oldMD.general.AddDescription(join(self.comments,'\n'))
		self.md,self.comments=self.metadataStack.pop()
		return oldMD
			
	def StartSkipped(self,ns,localName,attrs):
		self.skipping+=1
		print "Skipping element <%s>"%localName

	def ProcessTextRun(self):
		data=join(self.data,'')
		self.data=[]
		#if self.bodyElement.PreserveSpace():
		#	TextRun(self.bodyElement,data)
	
	def MigrationComment(self,comment):
		self.comments+=comment.splitlines()
		
	def EndDuration(self,ns,localName):
		d=Duration(join(self.data,''))
		if d.years or d.months or d.weeks:
			self.MigrationComment("incompatible duration: %s"%d.GetString(1))			
		if isinstance(self.cObject,AssessmentSection):
			maxTime=d.days*86400+d.hours*3600+60*d.minutes
			if d.seconds is not None:
				maxTime+=d.seconds
			self.cObject.timeLimits.SetMaxTime(maxTime)
		else:
			raise IMSQTIError("duration not allowed here")
		
	def EndFieldEntry(self,ns,localName):
		self.fieldentry=join(self.data,'')
		
	def EndFieldLabel(self,ns,localName):
		self.fieldlabel=join(self.data,'')
	
	def StartItem(self,ns,localName,attrs):
		identifier=attrs.get((None,'ident'))
		id=IMSIdentifier()
		id.SetIdentifier(identifier)
		label=attrs.get((None,'label'))
		maxattempts=attrs.get((None,'maxattempts'))
		lang=attrs.get((XMLNamespace,"lang"))
		title=attrs.get((None,'title'),'')
		# can't be adaptive or time dependent		
		item=AssessmentItem(identifier,title,0,0)
		if label:
			item.SetLabel(label)
		if lang:
			item.SetLanguage(lang)
		if maxattempts:
			# This only applies when the item is the context of a test
			pass
		self.PushObject(item)
		self.PushMetadata()
		self.md.general.AddIdentifier(id)
		
	def EndItem(self,ns,localName):
		item=self.PopObject()
		md=self.PopMetadata()
		if isinstance(self.cObject,AssessmentSection):
			# we need to generate a reference to this item, and the identifier must be unique			
			self.cObject.AddChild(AssessmentItemRef(item.identifier,item))
		self.objects+=[md,item]
	
	def StartMaterial(self,ns,localName,attrs):
		"""Material is a nothing element except where a language or label is used
		in which case we have to map it to either a div or span depending on what
		it contains.  We start by mapping it to a div and change strategy later
		if it turns out that all its children are actually inline."""
		label=attrs.get((None,'label'))
		lang=attrs.get((XMLNamespace,"lang"))
		m=Div(self.cObject)
		if label:
			m.SetLabel(label)
		if lang:
			m.SetLanguage(lang)
		self.PushObject(m)		
	
	def EndMaterial(self,ns,localName):
		"""A div which doesn't have a lang or a label can be thrown away if the
		parent allows the children to be direct leaves."""
		m=self.PopObject()
		if isinstance(self.cObject,RubricBlock):
			if m.HasOnlyInlineChildren():
				# convert the existing div to a paragraph
				p=Paragraph(self.cObject)
				p.SetLabel(m.label)
				p.SetLanguage(m.language)
				p.children=m.children
				self.cObject.DeleteChild(m)
		else:
			assert "Material not in RubricBlock"
	
	def StartMattext(self,ns,localName,attrs):
		self.data=[]
		if not isinstance(self.cObject,Div):
			raise IMSQTIError("<mattext> not allowed here")
		type=attrs.get((None,'texttype'),'text/plain')
		label=attrs.get((None,'label'))
		charset=attrs.get((None,'charset'))
		if charset:
			if charset.lower()!='ascii-us':
				self.MigrationComment("Warning: charset attribute no longer supported (%s)"%charset)
		uri=attrs.get((None,'uri'))
		space=attrs.get((XMLNamespace,'space'))
		lang=attrs.get((XMLNamespace,"lang"))		
		for aName in ('width','height','y0','x0'):
			value=attrs.get((None,aName))
			if value:
				self.MigrationComment("Warning: discarding %s coordinate on mattext (%s)"%(aName,value))
		entity=attrs.get((None,'entityref'))
		if entity:
			self.MigrationComment("Unsupported: inclusion of material through external entities (%s)"%entity)
		if uri:
			m=Object(self.cObject,uri,type)
			m.SetLabel(label)
			m.SetLanguage(lang)
			# we could have added width and height, but we already threw them away
			self.PushObject(m)
		elif type=="text/plain":
			if label or lang:
				self.PushObject(Span(self.cObject))
				self.cObject.SetLabel(label)
				self.cObject.SetLanguage(lang)
			else:
				self.PushObject(TextRun(self.cObject,''))
		else:
			m=Div(self.cObject)
			m.SetLabel(label)
			m.SetLanguage(lang)
			m.SetClass(self.type)
			self.PushObject(m)
			
	def EndMattext(self,ns,localName):
		m=self.PopObject()
		data=join(self.data,'')		
		if isinstance(m,Object):
			# characters in a mattext that has an external URI?  The alternative text.
			TextRun(m,data)
		elif isinstance(m,Span):
			# text/plain node
			TextRun(m,data)
		elif isinstance(m,TextRun):
			# just update the data
			m.text=data
		elif isinstance(m,Div):
			if m.type=="text/html":
				# turn the data into a stream of tag messages
				assert "HTML decoding not yet supported"
			elif m.type=="text/rtf":
				self.MigrationComment("Unsupported: RTF text converted with decoding")
				TextRun(m,data)
			else:
				# weird text format
				self.MigrationComment("Warning: unrecognized text type (%s) treated as plain text")
				TextRun(m,data)
			
	def StartObjectBank(self,ns,localName,attrs):
		if self.cObject:
			raise IMSQTIError("<objectBank> not allowed here")					
		id=IMSIdentifier()
		id.SetIdentifier(attrs.get((None,'ident')))
		self.md.general.AddIdentifier(id)
	
	def EndObjectBank(self,ns,localName):
		if self.comments:
			self.md.general.AddDescription(join(self.comments,'\n'))
			self.comments=[]
			
	def StartObjectives(self,ns,localName,attrs):
		"""We map objectives to rubric, initially.  If there is no view given on the
		objectives then we map this to all views as rubric requires a view."""
		if not isinstance(self.cObject,(AssessmentSection,AssessmentItem)):
			raise IMSQTIError("<objectives> not allowed here")
		view=attrs.get((None,'view'))
		if view:
			view=self.MigrateView(view)
		if view is None:
			view=View.All			
		rubric=RubricBlock(self.cObject,view)
		self.PushObject(rubric)
	
	def EndObjectives(self,ns,localName):
		"""If the objectives have a restricted view, then they clearly aren't the type
		of objectives that should be treated as metadata so we retain them as the
		rubric which we used to collect them.  However, if they are indiscriminately
		targetted at all views we turn it them into metadata for the current object."""	
		rubric=self.PopObject()
		if rubric.view==View.All:
			self.md.educational.AddDescription(rubric.ExtractText())
			self.cObject.DeleteRubric(rubric)
				
	def EndQTIComment(self,ns,localName):
		comment=join(self.data,'')
		if comment:
			self.MigrationComment("QTIComment: "+comment)
		self.data=[]
				
	def StartQTIMetadataField(self,ns,localName,attrs):
		self.fieldlabel=self.fieldentry=None
	
	def EndQTIMetadataField(self,ns,localName):
		# lookup things of interest to this object
		self.MigrationComment(self.fieldlabel+': '+self.fieldentry)
	
	def StartSection(self,ns,localName,attrs):
		identifier=attrs.get((None,'ident'))
		id=IMSIdentifier()
		id.SetIdentifier(identifier)
		lang=attrs.get((XMLNamespace,"lang"))
		title=attrs.get((None,'title'),'')
		# When migrating we only have visible sections
		section=AssessmentSection(identifier,title,1)
		self.PushObject(section)
		self.PushMetadata()
		self.md.general.AddIdentifier(id)
		
	def EndSection(self,ns,localname):
		section=self.PopObject()
		md=self.PopMetadata()
		# do some sanity checks on this section
		if not section.children:
			# we can't have empty sections in v2
			self.MigrationComment('Removed empty section id="%s"'%section.identifier)
		else:
			self.objects+=[md,section]
	
	def StartSelection(self,ns,localName,attrs):
		self.sourcebankRef=None
		self.selectionNumber=None
		self.selectionMetadata=0
		self.selectionExtension=0
		
	def EndSelection(self,ns,localName):
		if self.sourcebankRef:
			self.MigrationComment('sourcebank_ref not supported, ignoring selection from "%s"'%sourcebankRef)
		elif self.selectionMetadata:
			self.MigrationComment('selection_metadata is not supported')
		elif self.selectionExtension:
			self.MigrationComment('selection_extension unsupported, ignored selection rule')
		elif self.selectionNumber:
			# this is the partial use case
			if self.parameters.get('selectionNumber',None):
				self.MigrationComment('ignoring duplicate selection_number: %i'%self.selectionNumber)
			else:
				self.parameters['selection_number']=str(self.selectionNumber)			
	
	def StartSelectionExtension(self,ns,localName,attrs):
		self.selectionExtension=1
							
	def StartSelectionMetadata(self,ns,localName,attrs):
		self.selectionMetadata=1
				
	def StartSelectionOrdering(self,ns,localName,attrs):
		sequenceType=attrs.get((None,'sequence_type'),'').lower()
		if sequenceType=='randomrepeat' or sequenceType=='repeat':
			# we accept RandomRepeat due to a typo in the SAO specification
			self.withReplacement=1
		else:
			self.withReplacement=0
		self.parameters={}

	def EndSelectionOrdering(self,ns,localName):
		if isinstance(self.cObject,AssessmentSection):
			select=self.parameters.get('totalnumberobjects',None)
			if select is None:
				select=self.parameters.get('totalobjectnumber',None)
			if self.withReplacement:
				if select is None or not select.isdigit():
					raise IMSQTIError("missing or malformed sequence_parameter totalobjectnumber/totalnumberobjects")
				select=int(select)
			else:
				# in "Normal" we get this from the individual selection rules, but we allow
				# values from the selection_ordering element to fall through
				select=self.parameters.get('selection_number',select)
				if select:
					select=int(select)					
			if select:
				self.cObject.CreateSelection(int(select))
				self.cObject.selection.SetWithReplacement(self.withReplacement)
								 
	def StartSequenceParameter(self,ns,localName,attrs):
		self.pname=attrs.get((None,'pname')).lower()
		self.data=[]
		
	def EndSequenceParameter(self,ns,localName):
		self.parameters[self.pname]=join(self.data,'')
		self.data=[]
	
	def EndSourcebankRef(self,ns,localName):
		self.sourcebankRef=join(self.data,'')

	def EndSelectionNumber(self,ns,localName):
		self.selectionNumber=int(join(self.data,''))
				
	def StartNoOperation(self,ns,localName,attrs):
		# we don't need to do anything
		pass
	
	def ClearData(self,ns,localName,attrs):
		self.data=[]
		
	startMethods={
		'and_selection':StartNoOperation,
		'duration':ClearData,
		'fieldentry':ClearData,
		'fieldlabel':ClearData,
		'item':StartItem,
		'material':StartMaterial,
		'mattext':StartMattext,
		'not_selection':StartNoOperation,
		'objectbank':StartObjectBank,
		'objectives':StartObjectives,
		'or_selection':StartNoOperation,
		'qticomment':ClearData,
		'qtimetadata':StartNoOperation,
		'qtimetadatafield':StartQTIMetadataField,
		'section':StartSection,
		'selection':StartSelection,
		'selection_extension':StartSelectionExtension,
		'selection_metadata':StartSelectionMetadata,
		'selection_number':ClearData,
		'selection_ordering':StartSelectionOrdering,
		'sequence_parameter':StartSequenceParameter,
		'sourcebank_ref':ClearData
		}
	
	endMethods={
		'duration':EndDuration,
		'fieldentry':EndFieldEntry,
		'fieldlabel':EndFieldLabel,
		'item':EndItem,
		'material':EndMaterial,
		'mattext':EndMattext,
		'objectbank':EndObjectBank,
		'objectives':EndObjectives,
		'qticomment':EndQTIComment,
		'qtimetadatafield':EndQTIMetadataField,
		'section':EndSection,
		'selection_number':EndSelectionNumber,
		'selection_ordering':EndSelectionOrdering,
		'sequence_parameter':EndSequenceParameter,
		'sourcebank_ref':EndSourcebankRef
		}
	
	def MigrateView(self,oldView):
		"""The MigrateView method converts a view expressed in version 1.x format
		into a version 2 format view.  In 1.x, the information model suggests that
		multiple values of the view are allowed for each element to which it is
		applied but none of the examples illustrate this and the DTD does not allow it.
		We therefore assume that the incoming view is a simple string.  The value
		"All" is converted to the special value None as that is the normal interpretation
		of a missing view value."""
		view=oldView.strip().lower()
		if view!='all':
			if VIEW_MAP.has_key(view):
				newView=VIEW_MAP[view]
				if newView!=view:
					self.MigrationComment('Warning: changing %s to %s'%(view,newView))
				view=ParseView(newView)
			else:
				self.MigrationComment('Warning: ignoring unknown view (%s)'%view)
				view=None
		else:
			view=None
		return view
	