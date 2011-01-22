from types import *
import string

from PyAssess.ietf.rfc3066 import LanguageTag, LanguageRange
from PyAssess.ietf.rfc2426 import VCard
from PyAssess.iso.iso8601 import Date, Time, TimePoint, Duration

class LOMError(Exception): pass

# LOMv1.0 Vocabularies
LOMStructureVocabulary={
	'atomic':"an object that is indivisible (in this context).",
	'collection':"a set of objects with no specified relationship between them.",
	'networked':"a set of objects with relationships that are unspecified.",
	'hierarchical':"a set of objects whose relationships can be represented by a tree structure.",
	'linear':"a set of objects that are fully ordered. (Example: A set of objects that are connected by ``previous'' and ``next'' relationships.)"}

LOMAggregationLevelVocabulary={
	'1':"the smallest level of aggregation, e.g., raw media data or fragments.",
	'2':"a collection of level 1 learning objects, e.g., a lesson.",
	'3':"a collection of level 2 learning objects, e.g., a course.",
	'4':"the largest level of granularity, e.g., a set of courses that lead to a certificate."}

LOMStatusVocabulary={
	'draft':'',
	'final':'',
	'revised':'',
	'unavailable':''
	}

LOMLifeCycleRoleVocabulary={
	'author':'',
	'publisher':'',
	'unknown':'',
	'initiator':'',
	'terminator':'the entity that made the learning object unavailable',
	'validator':'',
	'editor':'',
	'graphical designer':'',
	'technical implementer':'',
	'content provider':'',
	'technical validator':'',
	'educational validator':'',
	'script writer':'',
	'instructional designer':'',
	'subject matter expert':''
	}

LOMMetadataRoleVocabulary={
	'creator':'',
	'validator':''
	}

LOMInteractivityTypeVocabulary={
	'active':"""active documents (with learner's action):
	- simulation (manipulates, controls or enters data or parameters);
	- questionnaire (chooses or writes answers);
	- exercise (finds solution);
	- problem statement (writes solution).""",
	'expositive':"""expositive documents (with learner's action):
	- hypertext document (reads, navigates);
	- video (views, rewinds, starts, stops);
	- graphical material (views);
	- audio material (listens, rewinds, starts, stops).""",
	'mixed':"""mixed document:
	- hypermedia document with embedded simulation applet."""
	}

LOMLearningResourceTypeVocabulary={
	'exercise':'',
	'simulation':'',
	'questionnaire':'',
	'diagram':'',
	'figure':'',
	'graph':'',
	'index':'',
	'slide':'',
	'table':'',
	'narrative text':'',
	'exam':'',
	'experiment':'',
	'problem statement':'',
	'self assessment':'',
	'lecture':''
	}
	
LOMInteractivityLevelVocabulary={
	'very low':'',
	'low':'',
	'medium':'',
	'high':'',
	'very high':''
	}
	
LOMSemanticDensityVocabulary={
	'very low':'',
	'low':'',
	'medium':'',
	'high':'',
	'very high':''
	}

LOMIntendedEndUserRoleVocabulary={
	'teacher':'',
	'author':'',
	'learner':'',
	'manager':''
	}

LOMDifficultyVocabulary={
	'very easy':'',
	'easy':'',
	'medium':'',
	'difficult':'',
	'very difficult':''
	}

LOMContextVocabulary={
	'school':'',
	'higher education':'',
	'training':'',
	'other':''
	}
		
LOMOrCompositeTypeVocabulary={
	'operating system':'',
	'browser':''
	}

LOMOrCompositeNameVocabulary={
	'pc-dos':'operating system',
	'ms-windows':'operating system',
	'macos':'operating system',
	'unix':'operating system',
	'multi-os':'operating system',
	'none':'operating system',
	'any':'browser',
	'netscape':'browser',
	'communicator':'browser',
	'ms-internet explorer':'browser',
	'opera':'browser',
	'amaya':'browser'
	}


def CharacterString(data):
	if type(data) in StringTypes:
		if data:
			return unicode(data)
		else:
			return None
	elif data is None:
		return None
	else:
		raise TypeError


class LOMMetadata:
	def __init__(self):
		self.general=LOMGeneral()
		self.lifeCycle=LOMLifeCycle()
		self.metaMetadata=LOMMetaMetadata()
		self.technical=LOMTechnical()
		self.educational=LOMEducational()

class LOMGeneral:
	def __init__(self):
		self.identifier=[]
		self.title=None
		self.language=[]
		self.description=[]
		self.keyword=[]
		self.coverage=[]
		self.structure=None
		self.aggregationLevel=None
		
	def __nonzero__(self):
		if self.identifier or self.title or self.language or self.description or \
			self.keyword or self.coverage or self.structure or self.aggregationLevel:
			return 1
		else:
			return 0

	def AddIdentifier(self,identifier):
		if identifier:
			if not isinstance(identifier,LOMIdentifier):
				identifier=LOMIdentifier(identifier)
			self.identifier.append(identifier)
		
	def GetCatalogEntries(self,catalog):
		result=[]
		for identifier in self.identifier:
			if identifier.catalog==catalog:
				result.append(identifier.entry)
		return result
	
	def SetTitle(self,title):
		if not isinstance(title,LOMLangString):
			title=LOMLangString(title)
		if title:
			self.title=title
		else:
			self.title=None
	
	def AddLanguage(self,language):
		if not isinstance(language,LanguageTag):
			language=LanguageTag(language)
		if language:
			self.language.append(language)

	def AddDescription(self,description):
		if not isinstance(description,LOMLangString):
			description=LOMLangString(description)
		if description:
			self.description.append(description)
			
	def AddKeyword(self,keyword):
		if not isinstance(keyword,LOMLangString):
			keyword=LOMLangString(keyword)
		if keyword:
			self.keyword.append(keyword)
			
	def AddCoverage(self,coverage):
		if not isinstance(coverage,LOMLangString):
			coverage=LOMLangString(coverage)
		if coverage:
			self.coverage.append(coverage)
						
	def SetStructure(self,structure):
		if not isinstance(structure,LOMVocabulary):
			structure=LOMVocabulary(structure)
		if structure:
			if structure.source=="LOMv1.0" and structure.value and \
				not LOMStructureVocabulary.has_key(structure.value):
				raise LOMError("LOMv1.0:"+structure.value+" not valid for General.Structure")
			self.structure=structure
		else:
			self.structure=None
			 
	def SetAggregationLevel(self,level):
		if not isinstance(level,LOMVocabulary):
			level=LOMVocabulary(level)
		if level:
			if level.source=="LOMv1.0" and level.value and \
				not LOMAggregationLevelVocabulary.has_key(level.value):
				raise LOMError("LOMv1.0:"+level.value+" not valid for General.AggregationLevel")
			self.aggregationLevel=level
		else:
			self.aggregationLevel=None


class LOMLifeCycle:
	def __init__(self):
		self.version=None
		self.status=None
		self.contribute=[]
		
	def __nonzero__(self):
		if self.status or self.version or self.contribute:
			return 1
		else:
			return 0

	def SetVersion(self,version):
		if not isinstance(version,LOMLangString):
			version=LOMLangString(version)
		if version:
			self.version=version
		else:
			self.version=None
					
	def SetStatus(self,status):
		if not isinstance(status,LOMVocabulary):
			status=LOMVocabulary(status)
		if status:
			if status.source=="LOMv1.0" and status.value and \
				not LOMStatusVocabulary.has_key(status.value):
				raise LOMError("LOMv1.0: %s not valid for LifeCycle.Status"%status.value)
			self.status=status
		else:
			self.status=None
			 
	def AddContribute(self,contribute):
		if not isinstance(contribute,LOMLifeCycleContribute):
			raise TypeError
		if contribute:
			self.contribute.append(contribute)


class LOMMetaMetadata:
	def __init__(self):
		self.identifier=[]
		self.contribute=[]
		self.metadataSchema=[]
		self.language=None

	def __nonzero__(self):
		if self.identifier or self.contribute or self.metadataSchema or self.language:
			return 1
		else:
			return 0

	def AddIdentifier(self,identifier):
		if identifier:
			if not isinstance(identifier,LOMIdentifier):
				identifier=LOMIdentifier(identifier)
			self.identifier.append(identifier)
		
	def GetCatalogEntries(self,catalog):
		result=[]
		for identifier in self.identifier:
			if identifier.catalog==catalog:
				result.append(identifier.entry)
		return result
	
	def AddContribute(self,contribute):
		if not isinstance(contribute,LOMMetadataContribute):
			raise TypeError
		if contribute:
			self.contribute.append(contribute)

	def AddMetadataSchema(self,schema):
		schema=CharacterString(schema)
		if schema:
			self.metadataSchema.append(schema)
				
	def SetLanguage(self,language):
		if language is None:
			self.language=None
		else:
			if not isinstance(language,LanguageTag):
				language=LanguageTag(language)
			self.language=language


class LOMTechnical:
	def __init__(self):
		self.format=[]
		self.size=None
		self.location=[]
		self.requirement=[]
		self.installationRemarks=None
		self.otherPlatformRequirements=None
		self.duration=None
		
	def __nonzero__(self):
		# it is possible that size=0, which should make the instance non-zero overall
		if self.format or (self.size is not None) or self.location or self.requirement or \
			self.installationRemarks or self.otherPlatformRequirements or self.duration:
			return 1
		else:
			return 0
	
	def AddFormat(self,format):
		# In future we should use a MIMEType object of some sort
		format=CharacterString(format)
		if format:
			self.format.append(format)
	
	def SetSize(self,size):
		if type(size) is IntType or size is None:
			self.size=size
		elif type(size) in StringTypes:
			if size.isdigit():
				self.size=int(size)
			else:
				raise ValueError(size)
		else:
			raise TypeError

	def AddLocation(self,location):
		location=CharacterString(location)
		if location:
			self.location.append(location)
	
	def AddRequirement(self,requirement):
		if not isinstance(requirement,LOMRequirement):
			raise TypeError
		if requirement:
			self.requirement.append(requirement)

	def SetInstallationRemarks(self,installationRemarks):
		if not isinstance(installationRemarks,LOMLangString):
			installationRemarks=LOMLangString(installationRemarks)
		if installationRemarks:
			self.installationRemarks=installationRemarks
		else:
			self.installationRemarks=None
	
	def SetOtherPlatformRequirements(self,otherPlatformRequirements):
		if not isinstance(otherPlatformRequirements,LOMLangString):
			otherPlatformRequirements=LOMLangString(otherPlatformRequirements)
		if otherPlatformRequirements:
			self.otherPlatformRequirements=otherPlatformRequirements
		else:
			self.otherPlatformRequirements=None
	
	def SetDuration(self,duration):
		if duration is None:
			self.duration=None
		else:
			if not isinstance(duration,LOMDuration):
				duration=LOMDuration(duration)
			self.duration=duration


class LOMRequirement:
	def __init__(self):
		self.orComposite=[]
	
	def __nonzero__(self):
		if self.orComposite:
			return 1
		else:
			return 0
		
	def AddOrComposite(self,orComposite):
		if not isinstance(orComposite,LOMOrComposite):
			raise TypeError
		if orComposite:
			self.orComposite.append(orComposite)
	

class LOMOrComposite:
	def __init__(self):
		self.type=None
		self.name=None
		self.minimumVersion=None
		self.maximumVersion=None

	def __nonzero__(self):
		if self.type or self.name or self.minimumVersion or self.maximumVersion:
			return 1
		else:
			return 0

	def SetType(self,type):
		if not isinstance(type,LOMVocabulary):
			type=LOMVocabulary(type)
		if type:
			if type.source=="LOMv1.0":
				if type.value and not LOMOrCompositeTypeVocabulary.has_key(type.value):
					raise LOMError("LOMv1.0: %s not valid for OrComposite.type"%type.value)
				if self.name and self.name.source=="LOMv1.0" and \
					LOMOrCompositeNameVocabulary[self.name.value]!=type.value:
					raise LOMError("LOMv1.0: %s not a valid type for OrComposite.name: %s"%
						(type.value,self.name.value))
			self.type=type
		else:
			self.type=None
	
	def SetName(self,name):
		if not isinstance(name,LOMVocabulary):
			name=LOMVocabulary(name)
		if name:
			if name.source=="LOMv1.0":
				if name.value and not LOMOrCompositeNameVocabulary.has_key(name.value):
					raise LOMError("LOMv1.0: %s not valid for OrComposite.name"%name.value)
				if self.type and self.type.source=="LOMv1.0" and \
					LOMOrCompositeNameVocabulary[name.value]!=self.type.value:
					raise LOMError("LOMv1.0: %s not a valid name for OrComposite.type: %s"%
						(type.name,self.type.value))
			self.name=name
		else:
			self.name=None
	
	def SetMinimumVersion(self,minimumVersion):
		self.minimumVersion=CharacterString(minimumVersion)

	def SetMaximumVersion(self,maximumVersion):
		self.maximumVersion=CharacterString(maximumVersion)
			
			
class LOMEducational:
	def __init__(self):
		self.interactivityType=None
		self.learningResourceType=[]
		self.interactivityLevel=None
		self.semanticDensity=None
		self.intendedEndUserRole=[]
		self.context=[]
		self.typicalAgeRange=[]
		self.difficulty=None
		self.typicalLearningTime=None
		self.description=[]
		self.language=[]

	def __nonzero__(self):
		if self.interactivityType or self.learningResourceType or \
			self.interactivityLevel or self.semanticDensity or self.intendedEndUserRole or \
			self.context or self.typicalAgeRange or self.difficulty or\
			self.typicalLearningTime or self.description or self.language:
			return 1
		else:
			return 0
	
	def SetInteractivityType(self,interactivityType):
		if not isinstance(interactivityType,LOMVocabulary):
			interactivityType=LOMVocabulary(interactivityType)
		if interactivityType:
			if interactivityType.source=="LOMv1.0" and interactivityType.value and \
				not LOMInteractivityTypeVocabulary.has_key(interactivityType.value):
				raise LOMError("LOMv1.0: %s not valid for Educational.InteractivityType"%interactivityType.value)
			self.interactivityType=interactivityType
		else:
			self.interactivityType=None

	def AddLearningResourceType(self,learningResourceType):
		if not isinstance(learningResourceType,LOMVocabulary):
			learningResourceType=LOMVocabulary(learningResourceType)
		if learningResourceType:
			if learningResourceType.source=="LOMv1.0" and learningResourceType and \
				not LOMLearningResourceTypeVocabulary.has_key(learningResourceType.value):
				raise LOMError("LOMv1.0: %s not valid for Educational.LearningResourceType"%
					learningResourceType.value)
			self.learningResourceType.append(learningResourceType)
	
	def SetInteractivityLevel(self,interactivityLevel):
		if not isinstance(interactivityLevel,LOMVocabulary):
			interactivityLevel=LOMVocabulary(interactivityLevel)
		if interactivityLevel:
			if interactivityLevel.source=="LOMv1.0" and interactivityLevel.value and \
				not LOMInteractivityLevelVocabulary.has_key(interactivityLevel.value):
				raise LOMError("LOMv1.0: %s not valid for Educational.InteractivityTyp"%interactivityLevel.value)
			self.interactivityLevel=interactivityLevel
		else:
			self.interactivityLevel=None
			
	def SetSemanticDensity(self,semanticDensity):
		if not isinstance(semanticDensity,LOMVocabulary):
			semanticDensity=LOMVocabulary(semanticDensity)
		if semanticDensity:
			if semanticDensity.source=="LOMv1.0" and semanticDensity.value and \
				not LOMSemanticDensityVocabulary.has_key(semanticDensity.value):
				raise LOMError("LOMv1.0: %s not valid for Educational.SemanticDensity"%semanticDensity.value)
			self.semanticDensity=semanticDensity
		else:
			self.semanticDensity=None

	def AddIntendedEndUserRole(self,intendedEndUserRole):
		if not isinstance(intendedEndUserRole,LOMVocabulary):
			intendedEndUserRole=LOMVocabulary(intendedEndUserRole)
		if intendedEndUserRole:
			if intendedEndUserRole.source=="LOMv1.0" and intendedEndUserRole and \
				not LOMIntendedEndUserRoleVocabulary.has_key(intendedEndUserRole.value):
				raise LOMError("LOMv1.0: %s not valid for Educational.IntendedEndUserRole"%
					intendedEndUserRole.value)
			self.intendedEndUserRole.append(intendedEndUserRole)
		
	def AddContext(self,context):
		if not isinstance(context,LOMVocabulary):
			context=LOMVocabulary(context)
		if context:
			if context.source=="LOMv1.0" and context and \
				not LOMContextVocabulary.has_key(context.value):
				raise LOMError("LOMv1.0: %s not valid for Educational.Context"%
					context.value)
			self.context.append(context)
	
	def AddTypicalAgeRange(self,typicalAgeRange):
		if not isinstance(typicalAgeRange,LOMLangString):
			typicalAgeRange=LOMLangString(typicalAgeRange)
		if typicalAgeRange:
			self.typicalAgeRange.append(typicalAgeRange)

	def SetDifficulty(self,difficulty):
		if not isinstance(difficulty,LOMVocabulary):
			difficulty=LOMVocabulary(difficulty)
		if difficulty:
			if difficulty.source=="LOMv1.0" and difficulty.value and \
				not LOMDifficultyVocabulary.has_key(difficulty.value):
				raise LOMError("LOMv1.0: %s not valid for Educational.Difficulty"%difficulty.value)
			self.difficulty=difficulty
		else:
			self.difficulty=None
		
	def AddDescription(self,description):
		if not isinstance(description,LOMLangString):
			description=LOMLangString(description)
		if description:
			self.description.append(description)
			
	def SetTypicalLearningTime(self,typicalLearningTime):
		if typicalLearningTime is None:
			self.typicalLearningTime=None
		else:
			if not isinstance(typicalLearningTime,LOMDuration):
				typicalLearningTime=LOMDuration(typicalLearningTime)
			self.typicalLearningTime=typicalLearningTime

	def AddLanguage(self,language):
		if not isinstance(language,LanguageTag):
			language=LanguageTag(language)
		if language:
			self.language.append(language)


class LOMContribute:
	def __init__(self):
		self.role=None
		self.entity=[]
		self.date=None
		
	def __nonzero__(self):
		if self.role or self.entity or self.date:
			return 1
		else:
			return 0
	
	def SetRole(self,role):
		if not isinstance(role,LOMVocabulary):
			role=LOMVocabulary(role)
		if role:
			if role.source=="LOMv1.0" and role.value and \
				not self.roleVocab.has_key(role.value):
				raise LOMError("LOMv1.0: %s not valid for Contribute.Role in this context"%role.value)
			self.role=role
		else:
			self.role=None
			
	def AddEntity(self,entity):
		if not isinstance(entity,VCard):
			if type(entity) in StringTypes:
				# Conform line endings to CRLF given that LOM seems relaxed about this distinction
				lines=entity.splitlines()
				if lines:
					# Add a blank to force the data to end in CRLF
					lines.append('')
					entity=VCard(string.join(lines,'\r\n'))
				else:
					entity=""
		if entity:
			self.entity.append(entity)
	
	def SetDate(self,date):
		if date is None:
			self.date=None
		else:
			if not isinstance(date,LOMDateTime):
				date=LOMDateTime(date)
			self.date=date


class LOMLifeCycleContribute(LOMContribute):
	roleVocab=LOMLifeCycleRoleVocabulary


class LOMMetadataContribute(LOMContribute):
	roleVocab=LOMMetadataRoleVocabulary


class LOMIdentifier:
	def __init__(self,entry=None,catalog=None):
		self.SetCatalog(catalog)
		self.SetEntry(entry)

	def __repr__(self):
		return "LOMIdentifier("+repr(self.entry)+", "+repr(self.catalog)+")"
	
	def __cmp__(self,other):
		if not isinstance(other,LOMIdentifier):
			other=LOMIdentifier(None,other)
		result=cmp(self.catalog,other.catalog)
		if not result:
			result=cmp(self.entry,other.entry)
		return result
			
	def __nonzero__(self):
		if self.catalog or self.entry:
			return 1
		else:
			return 0
	
	def SetCatalog(self,catalog):
		self.catalog=CharacterString(catalog)
			
	def SetEntry(self,entry):
		self.entry=CharacterString(entry)			


class LOMLangString:
	def __init__(self,arg=None):
		self.strings=[]
		if type(arg) in (ListType,TupleType):
			for s in arg:
				self.AddString(s)
		elif arg:
			self.AddString(arg)
	
	def __repr__(self):
		if self:
			return "LOMLangString(["+string.join(map(repr,self.strings),", ")+"])"
		else:
			return "LOMLangString()"
			
	def AddString(self,s):
		if isinstance(s,LOMString):
			if s:
				self.strings.append(s)
		elif type(s) in StringTypes:
			if s:
				self.strings.append(LOMString(None,s))
		else:
			raise TypeError
			
	def __nonzero__(self):
		if self.strings:
			return 1
		else:
			return 0
	
	def __len__(self):
		return len(self.strings)
				
	def MatchLanguage(self,range,default=None):
		result=[]
		if not isinstance(range,LanguageRange):
			range=LanguageRange(range)
		defaultMatch=0
		if default:
			defaultMatch=range.MatchLanguage(default)
		for s in self.strings:
			if s.language:
				if range.MatchLanguage(s.language):
					result.append(s.string)
			elif defaultMatch:
				result.append(s.string)
		return result
		

class LOMString:
	def __init__(self,language=None,string=None):
		if isinstance(language,LOMString):
			# copy constructor
			string=language.string
			language=language.language
		self.SetLanguage(language)
		self.SetString(string)
	
	def __repr__(self):
		if self.language:
			langStr=str(self.language)
		else:
			langStr=None
		return "LOMString("+repr(langStr)+", "+repr(self.string)+")"

	def __cmp__(self,other):
		if not isinstance(other,LOMString):
			other=LOMString(None,other)
		return cmp(self.string,other.string)
		
	def __nonzero__(self):
		if self.string:
			return 1
		else:
			return 0
		
	def SetLanguage(self,language):
		if language:
			self.language=LanguageTag(language)
		else:
			self.language=None
			
	def SetString(self,string):
		self.string=CharacterString(string)
		if self.string and '\00' in self.string:
			self.string=None
			raise LOMError("NUL character in LangString")

		
LOMDateTimeFormats={
	'YYYY':1,
	'YYYY-MM':1,
	'YYYY-MM-DD':1,
	'YYYY-MM-DDThh':1,
	'YYYY-MM-DDThh:mm':1,
	'YYYY-MM-DDThh:mm:ss':1,
	'YYYY-MM-DDThh:mm:ss.s':1,
	'YYYY-MM-DDThhZ':1,
	'YYYY-MM-DDThh:mmZ':1,
	'YYYY-MM-DDThh:mm:ssZ':1,
	'YYYY-MM-DDThh:mm:ss.sZ':1,
	'YYYY-MM-DDThh+hh:mm':1,
	'YYYY-MM-DDThh:mm+hh:mm':1,
	'YYYY-MM-DDThh:mm:ss+hh:mm':1,
	'YYYY-MM-DDThh:mm:ss.s+hh:mm':1
	}
	
class LOMDateTime:
	def __init__(self,date=None,description=None):
		self.SetDateTime(date)
		self.SetDescription(description)
	
	def __nonzero__(self):
		if self.dateTime or self.description:
			return 1
		else:
			return 0

	def SetDateTime(self,date):
		if isinstance(date,(Date,TimePoint)):
			self.dateTime=date
		elif type(date) in StringTypes:
			if 'T' in date:
				dt=TimePoint()
				format=dt.SetFromString(date)
				if not LOMDateTimeFormats.has_key(format):
					raise LOMError("date-time format")
				self.dateTime=dt
				date=dt.date
			else:
				d=Date()
				format=d.SetFromString(date)
				if not LOMDateTimeFormats.has_key(format):
					raise LOMError("date-time format")
				self.dateTime=d
				date=d
			if date.GetPrecision()==Date.CompletePrecision:
				if date<"15821015":
					# We must be a Julian date then
					c,y,m,d=date.GetCalendarDay()
					# Convert to a julian day
					date.SetJulianDay(c*100+y,m,d)
		elif date is None:
			self.dateTime=None
		else:
			raise TypeError
					
	def SetDescription(self,description):
		if isinstance(description,LOMLangString):
			self.description=description
		elif description is None:
			self.description=None
		else:
			self.description=LOMLangString(description)
	
class LOMDuration:
	def __init__(self,duration=None,description=None):
		self.SetDuration(duration)
		self.SetDescription(description)
	
	def __nonzero__(self):
		if self.duration or self.description:
			return 1
		else:
			return 0

	def SetDuration(self,duration):
		if isinstance(duration,Duration):
			self.duration=duration
		elif type(duration) in StringTypes:
			durationNew=Duration()
			format=durationNew.SetFromString(duration)
			if 'W' in format or ',' in format or ('.' in format and not 'S' in format):
				# LOM disallows use of the comma and only allows decimals for seconds
				raise LOMError("duration format")
			self.duration=durationNew
		elif duration is None:
			self.duration=None
		else:
			raise TypeError
					
	def SetDescription(self,description):
		if isinstance(description,LOMLangString):
			self.description=description
		elif description is None:
			self.description=None
		else:
			self.description=LOMLangString(description)


class LOMVocabulary:
	def __init__(self,value=None,source=None):
		self.SetSource(source)
		self.SetValue(value)

	def __repr__(self):
		return "LOMVocabulary("+repr(self.value)+", "+repr(self.source)+")"
	
	def __cmp__(self,other):
		if not isinstance(other,LOMVocabulary):
			other=LOMVocabulary(None,other)
		result=cmp(self.value,other.value)
		if not result:
			result=cmp(self.source,other.source)
		return result
			
	def __nonzero__(self):
		if self.source or self.value:
			return 1
		else:
			return 0
	
	def SetSource(self,source):
		self.source=CharacterString(source)
			
	def SetValue(self,value):
		self.value=CharacterString(value)			


