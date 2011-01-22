import string
from xml.sax import make_parser, handler

from PyAssess.w3c.xml import EscapeCharData, EscapeAttributeValue, StartTag, EmptyTag
from PyAssess.w3c.xmlnamespaces import XMLNamespace
from PyAssess.w3c.xmlschema import XMLSchemaNamespace

from PyAssess.ieee.p1484_12 import LOMMetadata, LOMIdentifier, LOMVocabulary, LOMLangString, \
	LOMString, LOMLifeCycleContribute, LOMMetadataContribute, LOMDateTime, LOMRequirement, \
	LOMOrComposite, LOMDuration
	
class IMSMDError(Exception): pass

IMSMetadataNamespace="http://www.imsglobal.org/xsd/imsmd_v1p2"

IMSMetadataNamespaces={
	"http://www.imsproject.org/metadata":"1.1",
	"http://www.imsproject.org/metadata/":"1.1",
	"http://www.imsproject.org/xsd/imsmd_rootv1p2":"1.2",
	"http://www.imsglobal.org/xsd/imsmd_v1p2":"1.2",
	"http://www.imsglobal.org/xsd/imsmd_rootv1p2p1":"1.2.1"}

LRMVocabExtrasSource="LOMv1.0/IMSMDv1.2"

LRMContextVocabularyExtras={
	'primary education':'school',
	'secondary education':'school',
	'university first cycle':'higher education',
	'university second cycle':'higher education',
	'university postgrade':'higher education',
	'technical school first cycle':'other',
	'technical school second cycle':'other',
	'professional formation':'other',
	'continuous formation':'other',
	'vocational training':'training'
	}
	
class IMSIdentifier(LOMIdentifier):
	def __init__(self):
		LOMIdentifier.__init__(self)
		self.isCatalogEntry=0
		self.fullEntry=None

	def SetIdentifier(self,identifier):
		self.SetCatalog(None)
		self.SetEntry(identifier)
		self.isCatalogEntry=0
		self.fullEntry=None
		
	def SetCatalogEntry(self,catalog,fullEntry):
		self.SetCatalog(catalog)
		if fullEntry:
			self.SetEntry(fullEntry.strings[0].string)
		else:
			self.SetEntry(None)
		self.isCatalogEntry=1
		self.fullEntry=fullEntry

TAB='\t'
TABTAB='\t\t'

def WriteLRMXML(xf,lom):
	stag=StartTag(IMSMetadataNamespace,'lom')
	if xf.Root():
		stag.SetAttribute(None,'xmlns:xsi',XMLSchemaNamespace)
		stag.SetAttribute(XMLSchemaNamespace,'schemaLocation',
			'http://www.imsglobal.org/xsd/imsmd_v1p2 http://www.imsglobal.org/xsd/imsmd_v1p2p2.xsd')
	xf.AppendStartTag(stag,1)
	if lom.general:
		WriteLRMGeneralXML(xf,lom.general)
	if lom.lifeCycle:
		WriteLRMLifeCycleXML(xf,lom.lifeCycle)
	if lom.metaMetadata:
		WriteLRMMetaMetadataXML(xf,lom.metaMetadata)
	if lom.technical:
		WriteLRMTechnicalXML(xf,lom.technical)
	if lom.educational:
		WriteLRMEducationalXML(xf,lom.educational)
	xf.AppendEndTag()


def WriteLRMGeneralXML(xf,general):
	xf.AppendStartTag(StartTag(IMSMetadataNamespace,'general'),1)
	for identifier in general.identifier:
		if isinstance(identifier,IMSIdentifier) and not identifier.isCatalogEntry:
			# Handle this one as an identifier
			WriteLRMIdentifierXML(xf,identifier)
	if general.title:
		WriteLRMLangStringXMLTag(xf,general.title,'title')
	for identifier in general.identifier:
		if isinstance(identifier,IMSIdentifier) and not identifier.isCatalogEntry:
			# already written as an <identifier>
			continue
		WriteLRMCatalogEntryXML(xf,identifier)
	for language in general.language:
		xf.AppendStartTag(StartTag(IMSMetadataNamespace,'language'))
		xf.AppendData(str(language))
		xf.AppendEndTag()
	for description in general.description:
		WriteLRMLangStringXMLTag(xf,description,'description')
	for keyword in general.keyword:
		WriteLRMLangStringXMLTag(xf,keyword,'keyword')
	for coverage in general.coverage:
		WriteLRMLangStringXMLTag(xf,coverage,'coverage')
	if general.structure:
		WriteLRMVocabularyXML(xf,'structure',general.structure)
	if general.aggregationLevel:
		WriteLRMVocabularyXML(xf,'aggregationlevel',general.aggregationLevel)
	xf.AppendEndTag()


def WriteLRMLifeCycleXML(xf,lifeCycle):
	xf.AppendStartTag(StartTag(IMSMetadataNamespace,'lifecycle'))
	if lifeCycle.version:
		WriteLRMLangStringXMLTag(xf,lifeCycle.version,'version')
	if lifeCycle.status:
		WriteLRMVocabularyXML(xf,'status',lifeCycle.status)
	for contribute in lifeCycle.contribute:
		WriteLRMContributeXML(xf,contribute)
	xf.AppendEndTag()


def WriteLRMMetaMetadataXML(xf,metaMetadata):
	xf.AppendStartTag(StartTag(IMSMetadataNamespace,'metametadata'),1)
	for identifier in metaMetadata.identifier:
		if isinstance(identifier,IMSIdentifier) and not identifier.isCatalogEntry:
			WriteLRMIdentifierXML(xf,identifier)
	for identifier in metaMetadata.identifier:
		if isinstance(identifier,IMSIdentifier) and not identifier.isCatalogEntry:
			continue
		WriteLRMCatalogEntryXML(xf,identifier)
	for contribute in metaMetadata.contribute:
		WriteLRMContributeXML(xf,contribute)
	for metadataSchema in metaMetadata.metadataSchema:
		xf.AppendStartTag(StartTag(IMSMetadataNamespace,'metadatascheme'))
		xf.AppendData(metadataSchema)
		xf.AppendEndTag()
	if metaMetadata.language:
		xf.AppendStartTag(StartTag(IMSMetadataNamespace,'language'))
		xf.AppendData(str(metaMetadata.language))
		xf.AppendEndTag()
	xf.AppendEndTag()


def WriteLRMTechnicalXML(xf,technical):
	xf.AppendStartTag(StartTag(IMSMetadataNamespace,'technical'),1)
	for format in technical.format:
		xf.AppendStartTag(StartTag(IMSMetadataNamespace,'format'))
		xf.AppendData(format)
		xf.AppendEndTag()
	if technical.size is not None:
		xf.AppendStartTag(StartTag(IMSMetadataNamespace,'size'))
		xf.AppendData(str(technical.size))
		xf.AppendEndTag()
	locationType=getattr(technical,'locationType',None)
	for i in xrange(len(technical.location)):
		tag=StartTag(IMSMetadataNamespace,'location')
		location=technical.location[i]
		if locationType and locationType[i]:
			tag.SetAttribute('','type',locationType[i])
		xf.AppendStartTag(tag)
		xf.AppendData(location)
		xf.AppendEndTag()
	skipRequirements=0
	for requirement in technical.requirement:
		if len(requirement.orComposite)>1:
			skipRequirements=1
	if skipRequirements:
		xf.AppendComment(" Complex LOM requirements cannot be represented using LRM ")
	else:
		for requirement in technical.requirement:
			WriteLRMRequirementXML(xf,requirement)
	if technical.installationRemarks:
		WriteLRMLangStringXMLTag(xf,technical.installationRemarks,'installationremarks')
	if technical.otherPlatformRequirements:
		WriteLRMLangStringXMLTag(xf,technical.otherPlatformRequirements,'otherplatformrequirements')
	if technical.duration:
		WriteLRMDurationXML(xf,technical.duration,'duration')
	xf.AppendEndTag()


def WriteLRMRequirementXML(xf,requirement):
	# This function only writes out the first requirement in the orComposite list
	if len(requirement.orComposite)>0:
		requirement=requirement.orComposite[0]
		xf.AppendStartTag(StartTag(IMSMetadataNamespace,'requirement'),1)
		if requirement.type:
			WriteLRMVocabularyXML(xf,'type',requirement.type)
		if requirement.name:
			WriteLRMVocabularyXML(xf,'name',requirement.name)
		if requirement.minimumVersion:
			xf.AppendStartTag(StartTag(IMSMetadataNamespace,'minimumVersion'))
			xf.AppendData(requirement.minimumVersion)
			xf.AppendEndTag()
		if requirement.maximumVersion:
			xf.AppendStartTag(StartTag(IMSMetadataNamespace,'maximumversion'))
			xf.AppendData(requirement.maximumVersion)
			xf.AppendEndTag()			
		xf.AppendEndTag()


def WriteLRMEducationalXML(xf,educational):
	xf.AppendStartTag(StartTag(IMSMetadataNamespace,'educational'),1)
	if educational.interactivityType:
		WriteLRMVocabularyXML(xf,'interactivitytype',educational.interactivityType)
	for learningResourceType in educational.learningResourceType:
		WriteLRMVocabularyXML(xf,'learningresourcetype',learningResourceType)
	if educational.interactivityLevel:
		WriteLRMVocabularyXML(xf,'interactivitylevel',educational.interactivityLevel)
	if educational.semanticDensity:
		WriteLRMVocabularyXML(xf,'semanticdensity',educational.semanticDensity)
	for intendedEndUserRole in educational.intendedEndUserRole:
		WriteLRMVocabularyXML(xf,'intendedenduserrole',intendedEndUserRole)
	for context in educational.context:
		if context.source and context.source==LRMVocabExtrasSource:
			# duplicate the vocab value with a revised source
			context=LOMVocabulary(context.value,"LOMv1.0")
		WriteLRMVocabularyXML(xf,'context',context)
	for typicalAgeRange in educational.typicalAgeRange:
		WriteLRMLangStringXMLTag(xf,typicalAgeRange,'typicalagerange')	
	if educational.difficulty:
		WriteLRMVocabularyXML(xf,'difficulty',educational.difficulty)
	if educational.typicalLearningTime:
		WriteLRMDurationXML(xf,educational.typicalLearningTime,'typicallearningtime')
	descriptionCount=0
	for description in educational.description:
		if descriptionCount:
			commentFile=StringIO()
			WriteLRMLangStringXMLTag(commentFile,description,'description')
			f.write(str(Comment(commentFile.getvalue())))
		else:
			WriteLRMLangStringXMLTag(xf,description,'description')
	xf.AppendEndTag()
		

def WriteLRMIdentifierXML(xf,identifier):
	xf.AppendStartTag(StartTag(IMSMetadataNamespace,'identifier'))
	xf.AppendData(identifier.entry)
	xf.AppendEndTag()


def WriteLRMCatalogEntryXML(xf,identifier):
	xf.AppendStartTag(StartTag(IMSMetadataNamespace,'catalogentry'),1)
	if identifier.catalog:
		xf.AppendStartTag(StartTag(IMSMetadataNamespace,'catalog'))
		xf.AppendData(identifier.catalog)
		xf.AppendEndTag()
	else:
		xf.AppendEmptyTag(EmptyTag(IMSMetadataNamespace,'catalog'))
	if identifier.entry:
		xf.AppendStartTag(StartTag(IMSMetadataNamespace,'entry'))
		if isinstance(identifier,IMSIdentifier):
			WriteLRMLangStringXML(xf,identifier.fullEntry)
		else:
			WriteLRMLangStringXML(xf,LOMLangString(identifier.entry))
		xf.AppendEndTag()
	else:
		xf.AppendEmptyTag(EmptyTag(IMSMetadataNamespace,'entry'))
	xf.AppendEndTag()


def WriteLRMContributeXML(xf,contribute):
	xf.AppendStartTag(StartTag(IMSMetadataNamespace,'contribute'),1)
	if contribute.role:
		WriteLRMVocabularyXML(xf,'role',contribute.role)
	for entity in contribute.entity:
		xf.AppendStartTag(StartTag(IMSMetadataNamespace,'centity'),1)
		xf.AppendStartTag(StartTag(IMSMetadataNamespace,'vcard'))
		xf.AppendData(str(entity))
		xf.AppendEndTag()
		xf.AppendEndTag()
	if contribute.date:
		WriteLRMDateXML(xf,contribute.date,'date')
	xf.AppendEndTag()


def WriteLRMDurationXML(xf,duration,localName):
	xf.AppendStartTag(StartTag(IMSMetadataNamespace,localName),1)
	if duration.duration:
		xf.AppendStartTag(StartTag(IMSMetadataNamespace,'datetime'))
		xf.AppendData(duration.duration.GetString(1))
		xf.AppendEndTag()
	if duration.description:
		WriteLRMLangStringXMLTag(xf,date.description,'description')
	xf.AppendEndTag()


def WriteLRMDateXML(xf,date,localName):
	xf.AppendStartTag(StartTag(IMSMetadataNamespace,localName),1)
	if date.dateTime:
		xf.AppendStartTag(StartTag(IMSMetadataNamespace,'datetime'))
		# cheeky line coming up, both Date and DateTime have GetCalendarString methods
		xf.AppendData(date.dateTime.GetCalendarString(0))
		xf.AppendEndTag()
	if date.description:
		WriteLRMLangStringXMLTag(xf,date.description,'description')
	xf.AppendEndTag()
			

def WriteLRMVocabularyXML(xf,name,vocabulary):
	xf.AppendStartTag(StartTag(IMSMetadataNamespace,name),1)
	if vocabulary.source is not None:
		xf.AppendStartTag(StartTag(IMSMetadataNamespace,'source'),1)
		xf.AppendStartTag(StartTag(IMSMetadataNamespace,'langstring'))
		xf.AppendData(str(vocabulary.source))
		xf.AppendEndTag()
		xf.AppendEndTag()
	if vocabulary.value is not None:
		xf.AppendStartTag(StartTag(IMSMetadataNamespace,'value'),1)
		xf.AppendStartTag(StartTag(IMSMetadataNamespace,'langstring'))
		xf.AppendData(str(vocabulary.value))
		xf.AppendEndTag()
		xf.AppendEndTag()
	xf.AppendEndTag()

		
def WriteLRMLangStringXMLTag(xf,langString,localName):
	xf.AppendStartTag(StartTag(IMSMetadataNamespace,localName),1)
	WriteLRMLangStringXML(xf,langString)
	xf.AppendEndTag()
	

def WriteLRMLangStringXML(xf,langString):
	for s in langString.strings:
		start=StartTag(IMSMetadataNamespace,'langstring')
		if s.language:
			start.SetAttribute(XMLNamespace,'lang',str(s.language))
		xf.AppendStartTag(start)
		if s.string:
			xf.AppendData(s.string)
		xf.AppendEndTag()


class MetadataParser(handler.ContentHandler, handler.ErrorHandler):
	def __init__(self):
		self.parser=make_parser()
		self.parser.setFeature(handler.feature_namespaces,1)
		self.parser.setContentHandler(self)
		self.parser.setErrorHandler(self)

	def ReadMetadata(self,metadataFile):
		self.ResetParser()
		self.parser.parse(metadataFile)
		return self.lom
	
	def ResetParser(self):
		self.lom=None
		self.category=None
		self.contribute=None
		self.date=None
		self.duration=None
		self.langString=None
		self.vocabulary=None
		self.mdVersion=None
		self.mdNamespace=None
		self.skipping=0
		self.data=[]
			
	def startElementNS(self,name,qname,attrs):
		ns,localName=name
		if self.lom:
			if self.skipping:
				self.skipping+=1
			elif ns==self.mdNamespace:
				method=self.startMethods.get(localName)
				if method:
					method(self,ns,localName,attrs)
			else:
				self.StartSkipped(ns,localName,attrs)
		else:
			if localName!="lom":
				raise IMSMDError("expected <lom>, found <%s>"%localName)
			self.mdVersion=IMSMetadataNamespaces.get(ns)
			self.mdNamespace=ns
			self.lom=LOMMetadata()
						
	def endElementNS(self,name,qname):
		ns,localName=name
		if self.skipping:
			self.skipping-=1
		elif ns==self.mdNamespace:
			method=self.endMethods.get(localName)
			if method:
				method(self,ns,localName)			

	def characters(self,content):
		self.data.append(content)

	def StartGeneral(self,ns,localName,attrs):
		self.category=self.lom.general
	
	def EndGeneral(self,ns,localName):
		self.category=None
	
	def EndTitle(self,ns,localName):
		if self.category==self.lom.general:
			self.lom.general.SetTitle(self.langString)
		self.langString=None

	def EndKeyword(self,ns,localName):
		if self.category==self.lom.general:
			self.lom.general.AddKeyword(self.langString)
		self.langString=None

	def EndCoverage(self,ns,localName):
		if self.category==self.lom.general:
			self.lom.general.AddCoverage(self.langString)
		self.langString=None

	def EndStructure(self,ns,localName):
		if self.vocabulary:
			self.lom.general.SetStructure(self.vocabulary)
		self.vocabulary=None
		
	def EndAggregationLevel(self,ns,localName):
		if self.vocabulary:
			self.lom.general.SetAggregationLevel(self.vocabulary)
		self.vocabulary=None
	
	def StartLifeCycle(self,ns,localName,attrs):
		self.category=self.lom.lifeCycle
	
	def EndLifeCycle(self,ns,localName):
		self.category=None
		
	def EndVersion(self,ns,localName):
		if self.category==self.lom.lifeCycle:
			self.lom.lifeCycle.SetVersion(self.langString)
		self.langString=None
	
	def EndStatus(self,ns,localName):
		if self.vocabulary:
			self.lom.lifeCycle.SetStatus(self.vocabulary)
		self.vocabulary=None
	
	def StartMetaMetadata(self,ns,localName,attrs):
		self.category=self.lom.metaMetadata
	
	def EndMetaMetadata(self,ns,localName):
		self.category=None
	
	def EndMetadataScheme(self,ns,localName):
		if self.category is self.lom.metaMetadata:
			self.lom.metaMetadata.AddMetadataSchema(string.join(self.data,''))
		self.data=[]
	
	def StartTechnical(self,ns,localName,attrs):
		self.category=self.lom.technical
		self.lom.technical.locationType=[]
	
	def EndTechnical(self,ns,localName):
		self.category=None
	
	def EndFormat(self,ns,localName):
		if self.category is self.lom.technical:
			self.lom.technical.AddFormat(string.join(self.data,''))
	
	def EndSize(self,ns,localName):
		if self.category is self.lom.technical:
			self.lom.technical.SetSize(string.join(self.data,''))

	def StartLocation(self,ns,localName,attrs):
		self.locationType=attrs.get((None,'type'))
		self.data=[]
	
	def EndLocation(self,ns,localName):
		if self.category is self.lom.technical:
			oldLength=len(self.lom.technical.location)
			self.lom.technical.AddLocation(string.join(self.data,''))
			if len(self.lom.technical.location)>oldLength:
				self.lom.technical.locationType.append(self.locationType)
	
	def StartRequirement(self,ns,localName,attrs):
		self.requirement=LOMRequirement()
		self.orComposite=LOMOrComposite()
	
	def EndRequirement(self,ns,localName):
		if self.category is self.lom.technical:
			self.requirement.AddOrComposite(self.orComposite)
			self.lom.technical.AddRequirement(self.requirement)
		self.orComposite=None
		self.requirement=None
	
	def EndType(self,ns,localName):
		if self.vocabulary and self.orComposite is not None:
			self.orComposite.SetType(self.vocabulary)
		self.vocabulary=None
					
	def EndName(self,ns,localName):
		if self.vocabulary and self.orComposite is not None:
			self.orComposite.SetName(self.vocabulary)
		self.vocabulary=None
	
	def EndMinimumVersion(self,ns,localName):
		if self.orComposite is not None:
			self.orComposite.SetMinimumVersion(string.join(self.data,''))
					
	def EndMaximumVersion(self,ns,localName):
		if self.orComposite is not None:
			self.orComposite.SetMaximumVersion(string.join(self.data,''))

	def EndInstallationRemarks(self,ns,localName):
		if self.category==self.lom.technical:
			self.lom.technical.SetInstallationRemarks(self.langString)
		self.langString=None
					
	def EndOtherPlatformRequirements(self,ns,localName):
		if self.category==self.lom.technical:
			self.lom.technical.SetOtherPlatformRequirements(self.langString)
		self.langString=None

	def StartEducational(self,ns,localName,attrs):
		self.category=self.lom.educational
	
	def EndEducational(self,ns,localName):
		self.category=None
	
	def EndInteractivityType(self,ns,localName):
		if self.vocabulary:
			self.lom.educational.SetInteractivityType(self.vocabulary)
		self.vocabulary=None
	
	def EndLearningResourceType(self,ns,localName):
		if self.vocabulary:
			self.lom.educational.AddLearningResourceType(self.vocabulary)
		self.vocabulary=None
					
	def EndInteractivityLevel(self,ns,localName):
		if self.vocabulary:
			self.lom.educational.SetInteractivityLevel(self.vocabulary)
		self.vocabulary=None
	
	def EndSemanticDensity(self,ns,localName):
		if self.vocabulary:
			self.lom.educational.SetSemanticDensity(self.vocabulary)
		self.vocabulary=None
	
	def EndIntendedEndUserRole(self,ns,localName):
		if self.vocabulary:
			self.lom.educational.AddIntendedEndUserRole(self.vocabulary)
		self.vocabulary=None
	
	def EndContext(self,ns,localName):
		if self.vocabulary:
			if self.vocabulary.source and self.vocabulary.source=="LOMv1.0":
				mapTerm=LRMContextVocabularyExtras.get(self.vocabulary.value)
				if mapTerm:
					self.vocabulary.SetSource(LRMVocabExtrasSource)
			self.lom.educational.AddContext(self.vocabulary)
		self.vocabulary=None
	
	def EndTypicalAgeRange(self,ns,localName):
		if self.category==self.lom.educational:
			self.lom.educational.AddTypicalAgeRange(self.langString)
		self.langString=None

	def EndDifficulty(self,ns,localName):
		if self.vocabulary:
			self.lom.educational.SetDifficulty(self.vocabulary)
		self.vocabulary=None
	
	def EndTypicalLearningTime(self,ns,localName):
		if self.category==self.lom.educational:
			self.lom.educational.SetTypicalLearningTime(self.duration)
		self.duration=None
			
	def EndIdentifier(self,ns,localName):
		identifier=IMSIdentifier()
		identifier.SetIdentifier(string.join(self.data,''))
		if self.category is self.lom.general or self.category is self.lom.metaMetadata:
			self.category.AddIdentifier(identifier)
		self.data=[]
	
	def StartCatalogEntry(self,ns,localName,attrs):
		self.catalog=None
		self.langString=LOMLangString()
	
	def EndCatalogEntry(self,ns,localName):
		identifier=IMSIdentifier()
		identifier.SetCatalogEntry(self.catalog,self.langString)
		if self.category==self.lom.general or self.category is self.lom.metaMetadata:
			self.category.AddIdentifier(identifier)
		self.langString=None
		
	def EndCatalog(self,ns,localName):
		self.catalog=string.join(self.data,'')
	
	def StartContribute(self,ns,localName,attrs):
		if self.category is self.lom.lifeCycle:
			self.contribute=LOMLifeCycleContribute()
		elif self.category is self.lom.metaMetadata:
			self.contribute=LOMMetadataContribute()
		else:
			self.contribute=LOMContribute()
			
	def EndContribute(self,ns,localName):
		if self.category==self.lom.lifeCycle or self.category==self.lom.metaMetadata:
			self.category.AddContribute(self.contribute)
		self.contribute=None
	
	def EndRole(self,ns,localName):
		if self.vocabulary and self.contribute is not None:
			self.contribute.SetRole(self.vocabulary)
		self.vocabulary=None

	def EndVCard(self,ns,localName):
		if self.contribute is not None:
			self.contribute.AddEntity(string.join(self.data,''))
	
	def StartDuration(self,ns,localName,attrs):
		self.duration=LOMDuration()

	def EndDuration(self,ns,localName):
		if self.category==self.lom.technical:
			self.lom.technical.SetDuration(self.duration)
		self.duration=None
			
	def StartDate(self,ns,localName,attrs):
		self.date=LOMDateTime()
		
	def EndDate(self,ns,localName):
		if self.contribute:
			self.contribute.SetDate(self.date)
		self.date=None

	def EndDateTime(self,ns,localName):
		if self.date is not None:
			self.date.SetDateTime(string.join(self.data,''))
		elif self.duration is not None:
			durStr=string.join(self.data,'')
			if 'P' in durStr:
				# this is a LOM style duration
				self.duration.SetDuration(durStr)
			else:
				# assume an iso Time
				h,m,s=Time(durStr).GetTime()
				d=Duration()
				d.SetCalendarDuration(h,m,s)
				self.duration.SetDuration(d)
		
	def EndDescription(self,ns,localName):
		if self.date is not None:
			self.date.SetDescription(self.langString)
		elif self.duration is not None:
			self.duration.SetDescription(self.langString)
		elif self.category==self.lom.general:
			self.lom.general.AddDescription(self.langString)
		elif self.category==self.lom.educational:
			self.lom.educational.AddDescription(self.langString)
		self.langString=None

	def EndLanguage(self,ns,localName):
		if self.category is self.lom.general:
			self.lom.general.AddLanguage(string.join(self.data,''))
		elif self.category is self.lom.metaMetadata:
			self.lom.metaMetadata.SetLanguage(string.join(self.data,''))
		elif self.category is self.lom.educational:
			self.lom.educational.AddLanguage(string.join(self.data,''))
		self.data=[]

	def StartVocabulary(self,ns,localName,attrs):
		self.vocabulary=LOMVocabulary()
	
	def EndSource(self,ns,localName):
		if self.langString and self.vocabulary is not None:
			self.vocabulary.SetSource(self.langString.strings[0].string)
		self.langString=None
		
	def EndValue(self,ns,localName):
		if self.langString is not None and self.vocabulary is not None:
			value=self.langString.strings[0].string
			if self.vocabulary.source=="LOMv1.0":
				# When mapping LRM binding to LOM we lower-case all values
				value=value.lower()
			self.vocabulary.SetValue(value)
		self.langString=None

	def StartLangString(self,ns,localName,attrs):
		self.langString=LOMLangString()
	
	def StartLOMString(self,ns,localName,attrs):
		self.lomString=LOMString(attrs.get((XMLNamespace,"lang")))
		self.data=[]
	
	def EndLOMString(self,ns,localName):
		self.lomString.SetString(string.join(self.data,''))
		self.data=[]
		if self.langString is not None:
			self.langString.AddString(self.lomString)
		self.lomString=None

	def ZeroData(self,ns,localName,attrs):
		self.data=[]
			
	def StartSkipped(self,ns,localName,attrs):
		self.skipping+=1
		# print "Skipping element <%s>"%localName
		
	startMethods={
		'aggregationlevel':StartVocabulary,
		'catalog':ZeroData,
		'catalogentry':StartCatalogEntry,
		'context':StartVocabulary,
		'contribute':StartContribute,
		'coverage':StartLangString,
		'date':StartDate,
		'datetime':ZeroData,
		'description':StartLangString,
		'difficulty':StartVocabulary,
		'duration':StartDuration,
		'educational':StartEducational,
		'format':ZeroData,
		'general':StartGeneral,
		'identifier':ZeroData,
		'intendedenduserrole':StartVocabulary,
		'interactivitylevel':StartVocabulary,
		'interactivitytype':StartVocabulary,
		'keyword':StartLangString,
		'langstring':StartLOMString,
		'language':ZeroData,
		'learningresourcetype':StartVocabulary,
		'lifecycle':StartLifeCycle,
		'location':StartLocation,
		'maximumversion':ZeroData,
		'metadatascheme':ZeroData,
		'metametadata':StartMetaMetadata,
		'minimumversion':ZeroData,
		'name':StartVocabulary,
		'requirement':StartRequirement,
		'role':StartVocabulary,
		'semanticdensity':StartVocabulary,
		'size':ZeroData,
		'source':StartLangString,
		'status':StartVocabulary,
		'structure':StartVocabulary,
		'technical':StartTechnical,
		'title':StartLangString,
		'type':StartVocabulary,
		'typicalagerange':StartLangString,
		'typicallearningtime':StartDuration,
		'value':StartLangString,
		'vcard':ZeroData,
		'version':StartLangString
		}
		
	endMethods={
		'aggregationlevel':EndAggregationLevel,
		'catalog':EndCatalog,
		'catalogentry':EndCatalogEntry,
		'context':EndContext,
		'contribute':EndContribute,
		'coverage':EndCoverage,
		'date':EndDate,
		'datetime':EndDateTime,
		'description':EndDescription,
		'difficulty':EndDifficulty,
		'duration':EndDuration,
		'educational':EndEducational,
		'format':EndFormat,
		'general':EndGeneral,
		'identifier':EndIdentifier,
		'intendedenduserrole':EndIntendedEndUserRole,
		'interactivitylevel':EndInteractivityLevel,
		'interactivitytype':EndInteractivityType,
		'keyword':EndKeyword,
		'langstring':EndLOMString,
		'language':EndLanguage,
		'learningresourcetype':EndLearningResourceType,
		'lifecycle':EndLifeCycle,
		'location':EndLocation,
		'maximumversion':EndMaximumVersion,
		'metametadata':EndMetaMetadata,
		'metametascheme':EndMetadataScheme,
		'minimumversion':EndMinimumVersion,
		'name':EndName,
		'requirement':EndRequirement,
		'role':EndRole,
		'semanticdensity':EndSemanticDensity,
		'size':EndSize,
		'source':EndSource,
		'status':EndStatus,
		'structure':EndStructure,
		'technical':EndTechnical,
		'title':EndTitle,
		'type':EndType,
		'typicalagerange':EndTypicalAgeRange,
		'typicallearningtime':EndTypicalLearningTime,
		'value':EndValue,
		'vcard':EndVCard,
		'version':EndVersion
		}
			
class IMSMetadata:
	schema="IMS Content"
	schemaVersion="1.1"
