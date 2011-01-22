from types import *
import string
import os.path
from xml.sax import make_parser, handler

from PyAssess.w3c.xml import EscapeCharData, EscapeAttributeValue, StartTag, EmptyTag, EndTag
from PyAssess.w3c.xmlnamespaces import CheckNCName,XMLNamespace
from PyAssess.w3c.xmlschema import ParseBoolean, FormatBoolean
from PyAssess.ietf.rfc2396 import URIReference

from md import IMSMetadataNamespace, IMSMetadataNamespaces, MetadataParser, WriteLRMXML
from PyAssess.ieee.p1484_12 import LOMMetadata

IMSContentPackagingNamespace="http://www.imsglobal.org/xsd/imscp_v1p1"

class CPError(Exception):
	pass

class ContentPackage:
	def __init__(self,path):
		self.ids={}
		self.manifest=None
		if os.path.isdir(path):
			self.basePath=path
			manifestPath=os.path.join(path,"imsmanifest.xml")
		else:
			self.basePath,manifestName=os.path.split(path)
			if os.path.normcase(manifestName)!="imsmanifest.xml":
				raise CPError("bad name for manifest file")
			manifestPath=path
		if os.path.isfile(manifestPath):
			# Read the manifest from this file
			manifestFile=file(manifestPath,'r')
			try:
				self.ReadManifestFile(manifestFile)
			finally:
				manifestFile.close()
		else:
			self.manifest=Manifest(self)
			self.DeclareObject(self.manifest.identifier,self.manifest)
					
	def ReadManifestFile(self,manifestFile):
		self.ids={}
		parser=ContentPackageParser()
		parser.ReadManifest(self,manifestFile)
				
	def Erase(self):
		pass

	def DeclareObject(self,identifier,object):
		if self.ids.has_key(identifier):
			raise CPError("duplicate identifier")
		else:
			self.ids[identifier]=object
	
	def FreeObject(self,identifier):
		if self.ids.has_key(identifier):
			del self.ids[identifier]
		else:
			raise CPError("free for undeclared object in package")
	
	def GetObject(self,identifier):
		return self.ids.get(identifier)
		
	def GetUniqueIdentifier(self,stem):
		tryID=stem
		for i in xrange(1000):
			if self.ids.has_key(tryID):
				tryID=stem+"_%03i"%i
			else:
				return tryID
		raise CPError("failed to get a unique identifier")

	def GetIdentifier(self,identifier,stem):
		"""Checks the syntax of identifier or makes a new unique identifier
		based on the given stem."""
		if type(identifier) in StringTypes:
			if CheckNCName(identifier):
				if self.GetObject(identifier):
					raise CPError("duplicate identifier: %s"%identifier)
				return identifier
			else:
				raise CPError("illegal identifier: %s"%identifier)
		elif identifier is None:
			return self.GetUniqueIdentifier(stem)
		else:
			raise TypeError
		

class Metadata:
	def __init__(self):
		self.mdSchema=None
		self.mdSchemaVersion=None
		self.metadata=[]

	def SetMDSchemaInfo(self,schema,schemaVersion):
		self.mdSchema=schema
		self.mdSchemaVersion=schemaVersion
	
	def AddMetadata(self,metadata):
		self.metadata.append(metadata)

	def RemoveMetadata(self,i):
		del self.metadata[i]
	
	def HasMetadata(self):
		return self.metadata or self.mdSchema or self.mdSchemaVersion
			
	def WriteXML(self,f,indent='\n'):
		if self.HasMetadata():
			f.write(indent+str(StartTag('','metadata')))
			if self.mdSchema:
				f.write(indent+'\t'+str(StartTag('','schema')))
				f.write(EscapeCharData(self.mdSchema))
				f.write(str(EndTag('','schema')))
			if self.mdSchemaVersion:
				f.write(indent+'\t'+str(StartTag('','schemaversion')))
				f.write(EscapeCharData(self.mdSchemaVersion))
				f.write(str(EndTag('','schemaversion')))
			for md in self.metadata:
				if isinstance(md,LOMMetadata):
					WriteLRMXML(f,md,'imsmd',indent+'\t')
			f.write(indent+str(EndTag('','metadata')))
	
class Manifest(Metadata):
	def __init__(self,parent,identifier=None):
		if isinstance(parent,ContentPackage):
			self.package=parent
			self.parentManifest=None
		elif isinstance(parent,Manifest):
			self.package=parent.package
			self.parentManifest=parent	
		else:
			raise TypeError
		Metadata.__init__(self)
		self.identifier=self.package.GetIdentifier(identifier,"manifest")
		self.version=None
		self.base=None
		self.defaultOrganization=None
		self.organizations=[]
		self.resourceBase=None
		self.resources=[]
		self.subManifests=[]
		if isinstance(parent,Manifest):
			parent.AddSubManifest(self)

	def CheckIDs(self):
		if self.defaultOrganization is not None and \
			not isinstance(self.package.GetObject(self.defaultOrganization),Organization):
			raise CPError("Failed organization reference: %s"%self.identifierRef)
		for organization in self.organizations:
			organization.CheckIDs()
		for resource in self.resources:
			resource.CheckIDs()
		for subManifest in self.subManifests:
			subManifest.CheckIDs()
					
	def SetIdentifier(self,identifier):
		if identifier is None:
			raise ValueError
		elif self.identifier!=identifier:
			identifier=self.package.GetIdentifier(identifier,"manifest")
			self.package.FreeObject(self.identifier)
			self.identifier=identifier
			self.package.DeclareObject(self.identifier,self)

	def SetVersion(self,version):
		if type(version) in StringTypes:
			if len(version)>20:
				raise ValueError
			self.version=version
		elif version is None:
			self.version=None
		else:
			raise TypeError

	def SetBase(self,base):
		if base is None:
			self.base=None
		elif isinstance(base,URIReference):
			self.base=base
		else:
			self.base=URIReference(base)
	
	def SetDefaultOrganization(self,defaultOrganization):
		if defaultOrganization is None:
			self.defaultOrganization=None
		elif CheckNCName(defaultOrganization):
			self.defaultOrganization=defaultOrganization
		else:
			raise CPError("illegal identifier: %s"%defaultOrganization)

	def AddOrganization(self,organization):
		self.package.DeclareObject(organization.identifier,organization)
		self.organizations.append(organization)

	def RemoveOrganization(self,identifier):
		for i in xrange(len(self.organizations)):
			if self.organizations[i].identifier==identifier:
				del self.organizations[i]
				self.package.FreeObject(identifier)
				return
		raise KeyError

	def SetResourceBase(self,resourceBase):
		if resourceBase is None:
			self.resourceBase=None
		elif isinstance(resourceBase,URIReference):
			self.resourceBase=resourceBase
		else:
			self.resourceBase=URIReference(resourceBase)
	
	def AddResource(self,resource):
		self.package.DeclareObject(resource.identifier,resource)
		self.resources.append(resource)
		
	def RemoveResource(self,identifier):
		for i in xrange(len(self.resources)):
			if self.resources[i].identifier==identifier:
				del self.resources[i]
				self.package.FreeObject(identifier)
				return
		raise KeyError

	def AddSubManifest(self,manifest):
		self.subManifests.append(manifest)
		self.package.DeclareObject(manifest.identifier,manifest)

	def RemoveManifest(self,identifier):
		for i in xrange(len(self.subManifests)):
			if self.subManifests[i].identifier==identifier:
				del self.subManifests[i]
				self.package.FreeObject(identifier)
				return
		raise KeyError
			
	def WriteXML(self,f):
		start=StartTag('','manifest')
		start.SetAttribute('','xmlns',IMSContentPackagingNamespace)
		start.SetAttribute('xmlns','imsmd',IMSMetadataNamespace)
		start.SetAttribute('','identifier',self.identifier)
		if self.version is not None:
			start.SetAttribute('','version',self.version)
		if self.base is not None:
			start.SetAttribute('xml','base',str(self.base))
		f.write(str(start))
		Metadata.WriteXML(self,f,'\n\t')
		if self.defaultOrganization:
			attrs={'default':self.defaultOrganization}
		else:
			attrs={}
		if self.organizations:
			f.write('\n\t'+str(StartTag('','organizations',attrs)))
			for organization in self.organizations:
				organization.WriteXML(f,'\n\t\t')
			f.write('\n\t'+str(EndTag('','organizations')))
		else:
			f.write('\n\t'+str(EmptyTag('','organizations',attrs)))
		if self.resourceBase:
			attrs={'xml:base':str(self.resourceBase)}
		else:
			attrs={}
		if self.resources:
			f.write('\n\t'+str(StartTag('','resources',attrs)))
			for resource in self.resources:
				resource.WriteXML(f,'\n\t\t')
			f.write('\n\t'+str(EndTag('','resources')))
		else:
			f.write('\n\t'+str(EmptyTag('','resources',attrs)))				
		f.write("\n"+str(EndTag('','manifest'))+"\n")
		
class ItemContainer:
	def __init__(self,parent):
		if isinstance(parent,Manifest):
			self.manifest=parent
		else:
			self.manifest=parent.manifest
		self.parent=parent
		self.title=None
		self.items=[]

	def CheckIDs(self):
		for item in self.items:
			item.CheckIDs()
		
	def SetTitle(self,title):
		if type(title) in StringTypes:
			if len(title)>200:
				raise ValueError
			self.title=title
		elif title is None:
			self.title=None
		else:
			raise TypeError

	def AddItem(self,item):
		self.manifest.package.DeclareObject(item.identifier,item)
		self.items.append(item)
		
	def RemoveItem(self,identifier):
		for i in xrange(len(self.items)):
			if self.items[i].identifier==identifier:
				del self.items[i]
				self.manifest.package.FreeObject(identifier)
				return
		raise KeyError
		
	def WriteXML(self,f,indent='\n'):
		if self.title:
			f.write(indent+str(StartTag('','title')))
			f.write(EscapeCharData(self.title))
			f.write(str(EndTag('','title')))
		for item in self.items:
			item.WriteXML(f,indent)


class Organization(ItemContainer,Metadata):
	def __init__(self,manifest,identifier=None):
		ItemContainer.__init__(self,manifest)
		Metadata.__init__(self)
		self.identifier=manifest.package.GetIdentifier(identifier,"organization")
		self.structure="hierarchical"
		manifest.AddOrganization(self)

	def SetStructure(self,structure):
		if type(structure) in StringTypes:
			if len(structure)>200:
				raise ValueError
			self.structure=structure
		elif structure is None:
			self.structure=None
		else:
			raise TypeError

	def WriteXML(self,f,indent='\n'):
		start=StartTag('','organization',{'identifier':self.identifier})
		if self.structure:
			start.SetAttribute('','structure',self.structure)
		f.write(indent+str(start))
		ItemContainer.WriteXML(self,f,indent+'\t')
		Metadata.WriteXML(self,f,indent+'\t')
		f.write(indent+str(EndTag('','organization')))

		
class Item(ItemContainer,Metadata):
	def __init__(self,parent,identifier=None):
		ItemContainer.__init__(self,parent)
		Metadata.__init__(self)
		self.identifierRef=None
		self.isVisible=1
		self.parameters=None
		self.identifier=self.manifest.package.GetIdentifier(identifier,"item")
		parent.AddItem(self)

	def CheckIDs(self):
		if self.identifierRef is not None and \
			not isinstance(self.manifest.package.GetObject(self.identifierRef),(Resource,Manifest)):
			raise CPError("Failed resource/manifest reference: %s"%self.identifierRef)
		ItemContainer.CheckIDs(self)
		
	def SetIdentifierRef(self,identifierRef):
		if identifierRef is None:
			self.identifierRef=None
		elif CheckNCName(identifierRef):
			self.identifierRef=identifierRef
		else:
			raise CPError("illegal identifier: %s"%identifierRef)
		
	def SetIsVisible(self,isVisible):
		if type(isVisible) in StringTypes:
			self.isVisible=ParseBoolean(isVisible)
		elif isVisible is None:
			# revert to default
			self.isVisible=1
		else:
			self.isVisible=(isVisible!=0)
	
	def SetParameters(self,parameters):
		if type(parameters) in StringTypes:
			if len(parameters)>1000:
				raise ValueError
			self.parameters=parameters
		elif parameters is None:
			self.parameters=None
		else:
			raise TypeError

	def WriteXML(self,f,indent='\n'):
		start=StartTag('','item',{
			'identifier':self.identifier,
			'isvisible':FormatBoolean(self.isVisible)
			})
		if self.identifierRef:
			start.SetAttribute('','identifierref',self.identifierRef)
		if self.parameters:
			start.SetAttribute('','parameters',self.parameters)
		f.write(indent+str(start))
		ItemContainer.WriteXML(self,f,indent+'\t')
		Metadata.WriteXML(self,f,indent+'\t')
		f.write(indent+str(EndTag('','item')))

	
class Resource(Metadata):
	def __init__(self,manifest,identifier=None,type="webcontent"):
		Metadata.__init__(self)
		self.manifest=manifest
		self.identifier=manifest.package.GetIdentifier(identifier,"resource")
		self.type=type
		self.href=None
		self.base=None
		self.files=[]
		self.dependencies=[]
		manifest.AddResource(self)
	
	def CheckIDs(self):
		for dependency in self.dependencies:
			if not isinstance(self.manifest.package.GetObject(dependency),Resource):
				raise CPError("Failed resource dependency: %s"%dependency)
				
	def SetType(self,resourceType):
		if type(resourceType) in StringTypes:
			if len(resourceType)>1000:
				raise ValueError
			self.type=resourceType
		elif resourceType is None:
			self.type=None
		else:
			raise TypeError

	def SetHREF(self,href):
		if href is None:
			self.href=None
		else:
			self.href=URIReference(href)

	def SetBase(self,base):
		if base is None:
			self.base=None
		elif isinstance(base,URIReference):
			self.base=base
		else:
			self.base=URIReference(base)

	def AddFile(self,resourceFile):
		self.files.append(resourceFile)
		
	def RemoveFile(self,href):
		for i in xrange(len(self.files)):
			if self.files[i].href==href:
				del self.files[i]
				return
		raise KeyError
		
	def AddDependency(self,identifierRef):
		if CheckNCName(identifierRef):
			self.dependencies.append(identifierRef)

	def RemoveDependency(self,identifierRef):
		for i in xrange(len(self.dependencies)):
			if self.dependencies[i]==identifierRef:
				del dependencies[i]
				return
		raise KeyError
				
	def WriteXML(self,f,indent='\n'):
		start=StartTag('','resource',{
			'identifier':self.identifier,
			'type':self.type,
			})
		if self.base:
			start.SetAttribute('xml','base',str(self.base))
		if self.href:
			start.SetAttribute('','href',str(self.href))
		f.write(indent+str(start))
		Metadata.WriteXML(self,f,indent+'\t')
		for fi in self.files:
			fi.WriteXML(f,indent+'\t')
		for dependency in self.dependencies:
			f.write(indent+'\t'+str(EmptyTag('','dependency',{'identifierref':dependency})))
		f.write(indent+str(EndTag('','resource')))


class File(Metadata):
	def __init__(self,href):
		Metadata.__init__(self)
		self.href=URIReference(href)
		
	def WriteXML(self,f,indent='\n'):
		attrs={'href':str(self.href)}
		if self.HasMetadata():
			f.write(indent+str(StartTag('','file',attrs)))
			Metadata.WriteXML(self,f,indent)
			f.write(indent+str(EndTag('','file')))
		else:
			f.write(indent+str(EmptyTag('','file',attrs)))
		

class ContentPackageParser(handler.ContentHandler, handler.ErrorHandler):
	def __init__(self):
		self.parser=make_parser()
		self.parser.setFeature(handler.feature_namespaces,1)
		self.parser.setContentHandler(self)
		self.parser.setErrorHandler(self)

	def ReadManifest(self,package,manifestFile):
		self.package=package
		self.manifest=None
		self.organization=None
		self.item=None
		self.resource=None
		self.mdObject=None
		self.cpNamespace=None
		self.skipping=0
		self.skippingParser=None
		self.data=[]
		self.parser.parse(manifestFile)
		
	def startElementNS(self,name,qname,attrs):
		ns,localName=name
		if self.manifest:
			if self.skipping:
				self.skipping+=1
				if self.skippingParser:
					self.skippingParser.startElementNS(name,qname,attrs)
			elif ns==self.cpNamespace:
				method=self.startMethods.get(localName)
				if method:
					method(self,ns,localName,attrs)
			else:
				self.StartSkipped(ns,localName,attrs)
				nsURI=str(URIReference(ns))
				if IMSMetadataNamespaces.get(nsURI):
					self.skippingParser=MetadataParser()
					self.skippingParser.ResetParser()
					self.skippingParser.startElementNS(name,qname,attrs)
		else:
			if localName!="manifest":
				raise CPError("expected <manifest>")
			# There are a variety of namespaces that could be used to
			# describe content packaging so we just store this so that
			# we can tell which future elements should be handled as
			# belonging to the package.
			self.cpNamespace=ns
			self.StartManifest(ns,localName,attrs)
			
	def endElementNS(self,name,qname):
		ns,localName=name
		if self.skipping:
			self.skipping-=1
			if self.skippingParser:
				self.skippingParser.endElementNS(name,qname)
				if not self.skipping:
					# currently skippingParser can only be MetadataParser
					if self.mdObject:
						self.mdObject.AddMetadata(self.skippingParser.lom)
					self.skippingParser=None
		elif ns==self.cpNamespace:
			method=self.endMethods.get(localName)
			if method:
				method(self,ns,localName)			

	def characters(self,content):
		if self.skipping:
			if self.skippingParser:
				self.skippingParser.characters(content)
		else:
			self.data.append(content)
		
	def StartManifest(self,ns,localName,attrs):
		if self.manifest:
			# This is a sub-manifest
			self.manifest=Manifest(self.manifest,attrs.get((None,'identifier')))
		else:
			self.manifest=Manifest(self.package,attrs.get((None,'identifier')))
			self.package.manifest=self.manifest
		self.manifest.SetBase(attrs.get((XMLNamespace,'base')))
		self.manifest.SetVersion(attrs.get((None,'version')))
		self.mdObject=self.manifest
		
	def EndManifest(self,ns,localName):
		if self.manifest==self.package.manifest:
			# that should be the end of parse
			self.mdObject=None
		else:
			self.manifest=self.manifest.parentManifest
			self.mdObject=self.manifest
	
	def EndSchema(self,ns,localName):
		if self.mdObject:
			self.mdObject.SetMDSchemaInfo(string.join(self.data,''),self.mdObject.mdSchemaVersion)
			
	def EndSchemaVersion(self,ns,localName):
		if self.mdObject:
			self.mdObject.SetMDSchemaInfo(self.mdObject.mdSchema,string.join(self.data,''))
	
	def StartOrganizations(self,ns,localName,attrs):
		self.manifest.SetDefaultOrganization(attrs.get((None,'default')))
	
	def StartOrganization(self,ns,localName,attrs):
		self.organization=Organization(self.manifest,attrs.get((None,'identifier')))
		self.organization.SetStructure(attrs.get((None,'structure')))
		self.mdObject=self.organization
	
	def EndOrganization(self,ns,localName):
		self.organization=None
		self.mdObject=None
	
	def StartItem(self,ns,localName,attrs):
		parent=None
		if self.item:
			parent=self.item
		elif self.organization:
			parent=self.organization
		if parent:
			self.item=Item(parent,attrs.get((None,'identifier')))
			self.mdObject=self.item
			self.item.SetIdentifierRef(attrs.get((None,'identifierref')))
			self.item.SetIsVisible(attrs.get((None,'isvisible')))
			self.item.SetParameters(attrs.get((None,'parameters')))
	
	def EndItem(self,ns,localName):
		if isinstance(self.item.parent,Item):
			self.item=self.item.parent
			self.mdObject=self.item
		else:
			self.item=None
			self.mdObject=self.organization
				
	def EndTitle(self,ns,localName):
		title=string.join(self.data,'')
		if self.item:
			self.item.SetTitle(title)
		elif self.organization:
			self.organization.SetTitle(title)

	def StartResources(self,ns,localName,attrs):
		self.manifest.SetResourceBase(attrs.get((XMLNamespace,'base')))
		
	def StartResource(self,ns,localName,attrs):
		if self.resource:
			raise CPError("can't nest resource")
		self.resource=Resource(self.manifest,attrs.get((None,'identifier')))
		self.resource.SetType(attrs.get((None,'type')))
		self.resource.SetHREF(attrs.get((None,'href')))
		self.resource.SetBase(attrs.get((XMLNamespace,'base')))
		self.mdObject=self.resource
		
	def EndResource(self,ns,localName):
		self.resource=None
		self.mdObject=None
		
	def StartFile(self,ns,localName,attrs):
		if self.resource:
			f=File(attrs.get((None,'href')))
			self.resource.AddFile(f)
			self.mdObject=f
	
	def EndFile(self,ns,localName):
		self.mdObject=None
	
	def StartDependency(self,ns,localName,attrs):
		if self.resource:
			self.resource.AddDependency(attrs.get((None,'identifierRef')))
						
	def ZeroData(self,ns,localName,attrs):
		self.data=[]
			
	def StartSkipped(self,ns,localName,attrs):
		self.skipping+=1
		# print "Skipping element <%s>"%localName
		
	startMethods={
		'manifest':StartManifest,
		'schema':ZeroData,
		'schemaversion':ZeroData,
		'organizations':StartOrganizations,
		'organization':StartOrganization,
		'item':StartItem,
		'resources':StartResources,
		'resource':StartResource,
		'file':StartFile,
		'dependency':StartDependency,
		'title':ZeroData
		}
	endMethods={
		'manifest':EndManifest,
		'schema':EndSchema,
		'schemaversion':EndSchemaVersion,
		'organization':EndOrganization,
		'item':EndItem,
		'resource':EndResource,
		'file':EndFile,
		'title':EndTitle
		}
	
	
	
