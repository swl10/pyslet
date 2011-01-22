import string
from xml.sax import make_parser, handler

from PyAssess.w3c.xml import EscapeCharData, EscapeAttributeValue, StartTag, EmptyTag, EndTag
from PyAssess.w3c.xmlnamespaces import XMLNamespace

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
		
def WriteLRMXML(f,lom,prefix='',indent='\n'):
	tag=StartTag(prefix,'lom')
	if not prefix:
		tag.SetAttribute('','xmlns',IMSMetadataNamespace)
	f.write(indent+str(tag))
	if lom.general:
		WriteLRMGeneralXML(f,lom.general,prefix,indent+TAB)
	if lom.lifeCycle:
		WriteLRMLifeCycleXML(f,lom.lifeCycle,prefix,indent+TAB)
	if lom.metaMetadata:
		WriteLRMMetaMetadataXML(f,lom.metaMetadata,prefix,indent+TAB)
	if lom.technical:
		WriteLRMTechnicalXML(f,lom.technical,prefix,indent+TAB)
	if lom.educational:
		WriteLRMEducationalXML(f,lom.educational,prefix,indent+TAB)
	f.write(indent+str(EndTag(prefix,'lom')))


def WriteLRMGeneralXML(f,general,prefix='',indent='\n'):
	f.write(indent+str(StartTag(prefix,'general')))
	for identifier in general.identifier:
		if isinstance(identifier,IMSIdentifier) and not identifier.isCatalogEntry:
			# Handle this one as an identifier
			WriteLRMIdentifierXML(f,identifier,prefix,indent+TAB)
	if general.title:
		WriteLRMLangStringXMLTag(f,general.title,prefix,'title',indent+TAB)
	for identifier in general.identifier:
		if isinstance(identifier,IMSIdentifier) and not identifier.isCatalogEntry:
			# already written as an <identifier>
			continue
		WriteLRMCatalogEntryXML(f,identifier,prefix,indent+TAB)
	for language in general.language:
		f.write(indent+TAB+str(StartTag(prefix,'language')))
		f.write(EscapeCharData(str(language)))
		f.write(str(EndTag(prefix,'language')))
	for description in general.description:
		WriteLRMLangStringXMLTag(f,description,prefix,'description',indent+TAB)
	for keyword in general.keyword:
		WriteLRMLangStringXMLTag(f,keyword,prefix,'keyword',indent+TAB)
	for coverage in general.coverage:
		WriteLRMLangStringXMLTag(f,coverage,prefix,'coverage',indent+TAB)
	if general.structure:
		WriteLRMVocabularyXML(f,'structure',general.structure,prefix,indent+TAB)
	if general.aggregationLevel:
		WriteLRMVocabularyXML(f,'aggregationlevel',general.aggregationLevel,prefix,indent+TAB)
	f.write(indent+str(EndTag(prefix,'general')))


def WriteLRMLifeCycleXML(f,lifeCycle,prefix='',indent='\n'):
	f.write(indent+str(StartTag(prefix,'lifecycle')))
	if lifeCycle.version:
		WriteLRMLangStringXMLTag(f,lifeCycle.version,prefix,'version',indent+TAB)
	if lifeCycle.status:
		WriteLRMVocabularyXML(f,'status',lifeCycle.status,prefix,indent+TAB)
	for contribute in lifeCycle.contribute:
		WriteLRMContributeXML(f,contribute,prefix,indent+TAB)
	f.write(indent+str(EndTag(prefix,'lifecycle')))


def WriteLRMMetaMetadataXML(f,metaMetadata,prefix='',indent='\n'):
	f.write(indent+str(StartTag(prefix,'metametadata')))
	for identifier in metaMetadata.identifier:
		if isinstance(identifier,IMSIdentifier) and not identifier.isCatalogEntry:
			WriteLRMIdentifierXML(f,identifier,prefix,indent+TAB)
	for identifier in metaMetadata.identifier:
		if isinstance(identifier,IMSIdentifier) and not identifier.isCatalogEntry:
			continue
		WriteLRMCatalogEntryXML(f,identifier,prefix,indent+TAB)
	for contribute in metaMetadata.contribute:
		WriteLRMContributeXML(f,contribute,prefix,indent+TAB)
	for metadataSchema in metaMetadata.metadataSchema:
		f.write(indent+TAB+str(StartTag(prefix,'metadatascheme')))
		f.write(EscapeCharData(metadataSchema))
		f.write(str(EndTag(prefix,'metadatascheme')))
	if metaMetadata.language:
		f.write(indent+TAB+str(StartTag(prefix,'language')))
		f.write(EscapeCharData(str(metaMetadata.language)))
		f.write(str(EndTag(prefix,'language')))
	f.write(indent+str(EndTag(prefix,'metametadata')))


def WriteLRMTechnicalXML(f,technical,prefix='',indent='\n'):
	f.write(indent+str(StartTag(prefix,'technical')))
	for format in technical.format:
		f.write(indent+TAB+str(StartTag(prefix,'format')))
		f.write(EscapeCharData(format))
		f.write(EndTag(prefix,'format'))
	if technical.size is not None:
		f.write(indent+TAB+str(StartTag(prefix,'size'))+str(technical.size)+
			str(EndTag(prefix,'size')))
	locationType=getattr(technical,'locationType',None)
	for i in xrange(len(technical.location)):
		tag=StartTag(prefix,'location')
		location=technical.location[i]
		if locationType and locationType[i]:
			tag.SetAttribute('','type',locationType[i])
		f.write(indent+TAB+str(tag)+EscapeCharData(location)+str(EndTag(prefix,'location')))
	skipRequirements=0
	for requirement in technical.requirement:
		if len(requirement.orComposite)>1:
			skipRequirements=1
	if skipRequirements:
		f.write(indent+TAG+"<!-- Complex LOM requirements cannot be represented using LRM -->")
	else:
		for requirement in technical.requirement:
			WriteLRMRequirementXML(f,requirement,prefix,indent+TAB)
	if technical.installationRemarks:
		WriteLRMLangStringXMLTag(f,technical.installationRemarks,prefix,'installationremarks',indent+TAB)
	if technical.otherPlatformRequirements:
		WriteLRMLangStringXMLTag(f,technical.otherPlatformRequirements,prefix,'otherplatformrequirements',
		indent+TAB)
	if technical.duration:
		WriteLRMDurationXML(f,technical.duration,prefix,'duration',indent+TAG)
	f.write(indent+str(EndTag(prefix,'technical')))


def WriteLRMRequirementXML(f,requirement,prefix,indent):
	# This function only writes out the first requirement in the orComposite list
	if len(requirement.orComposite)>0:
		requirement=requirement.orComposite[0]
		f.write(indent+str(StartTag(prefix,'requirement')))
		if requirement.type:
			WriteLRMVocabularyXML(f,'type',requirement.type,prefix,indent+TAB)
		if requirement.name:
			WriteLRMVocabularyXML(f,'name',requirement.name,prefix,indent+TAB)
		if requirement.minimumVersion:
			f.write(indent+TAB+str(StartTag(prefix,'minimumVersion')))
			f.write(EscapeCharData(requirement.minimumVersion)+str(EndTag(prefix,'minimumVersion')))
		if requirement.maximumVersion:
			f.write(indent+TAB+str(StartTag(prefix,'maximumversion')))
			f.write(EscapeCharData(requirement.maximumVersion)+str(EndTag(prefix,'maximumversion')))
		f.write(indent+str(EndTag(prefix,'requirement')))


def WriteLRMEducationalXML(f,educational,prefix,indent):
	f.write(indent+str(StartTag(prefix,'educational')))
	if educational.interactivityType:
		WriteLRMVocabularyXML(f,'interactivitytype',educational.interactivityType,prefix,indent+TAB)
	for learningResourceType in educational.learningResourceType:
		WriteLRMVocabularyXML(f,'learningresourcetype',learningResourceType,prefix,indent+TAB)
	if educational.interactivityLevel:
		WriteLRMVocabularyXML(f,'interactivitylevel',educational.interactivityLevel,prefix,indent+TAB)
	if educational.semanticDensity:
		WriteLRMVocabularyXML(f,'semanticdensity',educational.semanticDensity,prefix,indent+TAB)
	for intendedEndUserRole in educational.intendedEndUserRole:
		WriteLRMVocabularyXML(f,'intendedenduserrole',intendedEndUserRole,prefix,indent+TAB)
	for context in educational.context:
		if context.source and context.source==LRMVocabExtrasSource:
			# duplicate the vocab value with a revised source
			context=LOMVocabulary(context.value,"LOMv1.0")
		WriteLRMVocabularyXML(f,'context',context,prefix,indent+TAB)
	for typicalAgeRange in educational.typicalAgeRange:
		WriteLRMLangStringXMLTag(f,typicalAgeRange,prefix,'typicalagerange',indent+TAB)	
	if educational.difficulty:
		WriteLRMVocabularyXML(f,'difficulty',educational.difficulty,prefix,indent+TAB)
	if educational.typicalLearningTime:
		WriteLRMDurationXML(f,educational.typicalLearningTime,prefix,'typicallearningtime',indent+TAB)
	descriptionCount=0
	for description in educational.description:
		if descriptionCount:
			commentFile=StringIO()
			WriteLRMLangStringXMLTag(commentFile,description,prefix,'description',indent+TAB)
			f.write(str(Comment(commentFile.getvalue())))
		else:
			WriteLRMLangStringXMLTag(f,description,prefix,'description',indent+TAB)
	f.write(indent+str(EndTag(prefix,'educational')))
		

def WriteLRMIdentifierXML(f,identifier,prefix,indent):
	f.write(indent+str(StartTag(prefix,'identifier')))
	f.write(EscapeCharData(identifier.entry))
	f.write(str(EndTag(prefix,'identifier')))


def WriteLRMCatalogEntryXML(f,identifier,prefix,indent):
	f.write(indent+str(StartTag(prefix,'catalogentry')))
	if identifier.catalog:
		f.write(indent+TAB+str(StartTag(prefix,'catalog')))
		f.write(EscapeCharData(identifier.catalog))
		f.write(str(EndTag(prefix,'catalog')))
	else:
		f.write(indent+TAB+str(EmptyTag(prefix,'catalog')))
	if identifier.entry:
		f.write(indent+TAB+str(StartTag(prefix,'entry')))
		if isinstance(identifier,IMSIdentifier):
			WriteLRMLangStringXML(f,identifier.fullEntry,prefix,indent+TABTAB)
		else:
			WriteLRMLangStringXML(f,LOMLangString(identifier.entry),prefix,indent+TABTAB)
		f.write(indent+TAB+str(EndTag(prefix,'entry')))
	else:
		f.write(indent+TAB+str(EmptyTag(prefix,'entry')))
	f.write(indent+str(EndTag(prefix,'catalogentry')))


def WriteLRMContributeXML(f,contribute,prefix,indent):
	f.write(indent+str(StartTag(prefix,'contribute')))
	if contribute.role:
		WriteLRMVocabularyXML(f,'role',contribute.role,prefix,indent+TAB)
	for entity in contribute.entity:
		f.write(indent+TAB+str(StartTag(prefix,'centity')))
		f.write(indent+TABTAB+str(StartTag(prefix,'vcard')))
		f.write(EscapeCharData(str(entity))+str(EndTag(prefix,'vcard')))
		f.write(indent+TAB+str(EndTag(prefix,'centity')))
	if contribute.date:
		WriteLRMDateXML(f,contribute.date,prefix,'date',indent+TAB)
	f.write(indent+str(EndTag(prefix,'contribute')))


def WriteLRMDurationXML(f,duration,prefix,localName,indent):
	f.write(indent+str(StartTag(prefix,localName)))
	if duration.duration:
		f.write(indent+TAB+str(StartTag(prefix,'datetime')))
		f.write(EscapeCharData(duration.duration.GetString(1)))
		f.write(str(EndTag(prefix,'datetime')))
	if duration.description:
		WriteLRMLangStringXMLTag(f,date.description,prefix,'description',indent+TAB)
	f.write(indent+str(EndTag(prefix,localName)))


def WriteLRMDateXML(f,date,prefix,localName,indent):
	f.write(indent+str(StartTag(prefix,localName)))
	if date.dateTime:
		f.write(indent+TAB+str(StartTag(prefix,'datetime')))
		# cheeky line coming up, both Date and DateTime have GetCalendarString methods
		f.write(EscapeCharData(date.dateTime.GetCalendarString(0)))
		f.write(str(EndTag(prefix,'datetime')))
	if date.description:
		WriteLRMLangStringXMLTag(f,date.description,prefix,'description',indent+TAB)
	f.write(indent+str(EndTag(prefix,localName)))
			

def WriteLRMVocabularyXML(f,name,vocabulary,prefix,indent):
	f.write(indent+str(StartTag(prefix,name)))
	if vocabulary.source is not None:
		f.write(indent+TAB+str(StartTag(prefix,'source')))
		f.write(indent+TABTAB+str(StartTag(prefix,'langstring')))
		f.write(EscapeCharData(str(vocabulary.source)))
		f.write(EndTag(prefix,'langstring'))
		f.write(indent+TAB+str(EndTag(prefix,'source')))
	if vocabulary.value is not None:
		f.write(indent+TAB+str(StartTag(prefix,'value')))
		f.write(indent+TABTAB+str(StartTag(prefix,'langstring')))
		f.write(EscapeCharData(str(vocabulary.value)))
		f.write(EndTag(prefix,'langstring'))
		f.write(indent+TAB+str(EndTag(prefix,'value')))
	f.write(indent+str(EndTag(prefix,name)))

		
def WriteLRMLangStringXMLTag(f,langString,prefix,localName,indent):
	f.write(indent+str(StartTag(prefix,localName)))
	WriteLRMLangStringXML(f,langString,prefix,indent+TAB)
	f.write(indent+str(EndTag(prefix,localName)))
	

def WriteLRMLangStringXML(f,langString,prefix,indent):
	for s in langString.strings:
		start=StartTag(prefix,'langstring')
		if s.language:
			start.SetAttribute('xml','lang',str(s.language))
		f.write(indent+str(start))
		if s.string:
			f.write(EscapeCharData(s.string))
		f.write(str(EndTag(prefix,'langstring')))


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
