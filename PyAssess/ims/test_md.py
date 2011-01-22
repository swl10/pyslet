import unittest
from StringIO import StringIO

from md import *
from PyAssess.ieee.p1484_12 import LOMMetadata

def suite():
	return unittest.makeSuite(MetadataParserTests,'test')


SAMPLE_METADATA="""<?xml version="1.0" encoding="UTF-8"?>
<!-- edited with XML Spy v3.5 (http://www.xmlspy.com) by Thor Anderson (private) -->
<!-- use the line below and comment out the XML Schema namespace declarations when you want to check validity against the DTD -->
<!-- <!DOCTYPE lom SYSTEM "imsmd_rootv1p2p1.dtd"> -->
<lom xmlns="http://www.imsglobal.org/xsd/imsmd_rootv1p2p1" 
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
     xsi:schemaLocation="http://www.imsglobal.org/xsd/imsmd_rootv1p2p1 imsmd_rootv1p2p1.xsd">
	<general>
		<title>
			<langstring xml:lang="en">Draft Standard for Learning Object Metadata</langstring>
			<langstring xml:lang="nl">Voorstel van Standaard voor Metadata van Leerobjecten</langstring>
		</title>
		<catalogentry>
			<catalog>IEEE</catalog>
			<entry>
				<langstring xml:lang="x-none">P1484.12.1</langstring>
			</entry>
		</catalogentry>
		<catalogentry>
			<catalog>ADL</catalog>
			<entry>
				<langstring xml:lang="x-none">SCORM 1.1</langstring>
			</entry>
		</catalogentry>
		<language>en</language>
		<description>
			<langstring xml:lang="en">Metadata is information about an object, be it physical or digital. As the number of objects grows exponentially and our needs for learning expand equally dramatically, the lack of information or metadata about objects places a critical and fundamental constraint on our ability to discover, manage and use objects.

This standard addresses this problem by defining a structure for interoperable descriptions of learning objects.</langstring>
			<langstring xml:lang="nl">Metadata is informatie over een object. Het kan hierbij gaan om een fysisch of een digitaal object. Het aantal dergelijke objecten groeit exponentieel aan en tegelijk neemt de nood aan opleiding en onderwijs dramatisch toe. Het gebrek aan informatie of metadata over objecten beperkt op een kritische en fundamentele manier onze mogelijkheden om objecten te ontdekken, beheren en gebruiken.

Deze standaard pakt dit probleem aan door een structuur te definieren voor interoperabele beschrijvingen van leerobjecten.</langstring>
		</description>
		<keyword>
			<langstring xml:lang="en">metadata</langstring>
			<langstring xml:lang="nl">metadata</langstring>
			<langstring xml:lang="fr">metadonnees</langstring>
		</keyword>
		<keyword>
			<langstring xml:lang="en">learning object</langstring>
			<langstring xml:lang="nl">leerobject</langstring>
			<langstring xml:lang="fr">objet d'apprentissage</langstring>
		</keyword>
		<coverage>
			<langstring xml:lang="en">contemporary</langstring>
			<langstring xml:lang="nl">hedendaags</langstring>
			<langstring xml:lang="fr">contemporel</langstring>
		</coverage>
		<structure>
			
				<source>
					<langstring xml:lang="x-none">LOMv1.0</langstring>
				</source>
				<value>
					<langstring xml:lang="x-none">Linear</langstring>
				</value>
			
		</structure>
		<aggregationlevel>
			
				<source>
					<langstring xml:lang="x-none">LOMv1.0</langstring>
				</source>
				<value>
					<langstring xml:lang="x-none">2</langstring>
				</value>
			
		</aggregationlevel>
	</general>
	<lifecycle>
		<version>
			<langstring xml:lang="x-none">1.0</langstring>
		</version>
		<status>
			
				<source>
					<langstring xml:lang="x-none">LOMv1.0</langstring>
				</source>
				<value>
					<langstring xml:lang="x-none">Draft</langstring>
				</value>
			
		</status>
		<contribute>
			<role>
				
					<source>
						<langstring xml:lang="x-none">LOMv1.0</langstring>
					</source>
					<value>
						<langstring xml:lang="x-none">Content Provider</langstring>
					</value>
				
			</role>
			<centity>
				<vcard>BEGIN:VCARD
FN:Tom Wason
END:VCARD</vcard>
			</centity>
			<centity>
				<vcard>BEGIN:VCARD
FN:Erik Duval
END:VCARD</vcard>
			</centity>
			<date>
				<datetime>1998</datetime>
			</date>
		</contribute>
		<contribute>
			<role>
				
					<source>
						<langstring xml:lang="x-none">LOMv1.0</langstring>
					</source>
					<value>
						<langstring xml:lang="x-none">Editor</langstring>
					</value>
				
			</role>
			<centity>
				<vcard>BEGIN:VCARD
FN:Erik Duval
END:VCARD</vcard>
			</centity>
			<date>
				<datetime>2000</datetime>
			</date>
		</contribute>
	</lifecycle>
	<metametadata>
		<catalogentry>
			<catalog>Erik Duval's set of metadata records.</catalog>
			<entry>
				<langstring xml:lang="x-none">2000121601</langstring>
			</entry>
		</catalogentry>
		<contribute>
			<role>
				
					<source>
						<langstring xml:lang="x-none">LOMv1.0</langstring>
					</source>
					<value>
						<langstring xml:lang="x-none">Creator</langstring>
					</value>
				
			</role>
			<centity>
				<vcard>BEGIN:VCARD
FN:Erik Duval
END:VCARD</vcard>
			</centity>
			<date>
				<datetime>2000-12-16</datetime>
			</date>
		</contribute>
		<metadatascheme>LOMv1.0</metadatascheme>
		<metadatascheme>ARIADNEv3</metadatascheme>
	</metametadata>
	<technical>
		<format>application/msword</format>
		<size>210000</size>
		<location type="URI">http://ltsc.ieee.org/wg12/exactreference.doc</location>
		<requirement>
			<type>
				
					<source>
						<langstring xml:lang="x-none">LOMv1.0</langstring>
					</source>
					<value>
						<langstring xml:lang="x-none">Operating System</langstring>
					</value>
				
			</type>
			<name>
				
					<source>
						<langstring xml:lang="x-none">LOMv1.0</langstring>
					</source>
					<value>
						<langstring xml:lang="x-none">MS-Windows</langstring>
					</value>
				
			</name>
		</requirement>
	</technical>
	<educational>
		<interactivitytype>
			
				<source>
					<langstring xml:lang="x-none">LOMv1.0</langstring>
				</source>
				<value>
					<langstring xml:lang="x-none">Expositive</langstring>
				</value>
			
		</interactivitytype>
		<learningresourcetype>
			
				<source>
					<langstring xml:lang="x-none">LOMv1.0</langstring>
				</source>
				<value>
					<langstring xml:lang="x-none">Narrative Text</langstring>
				</value>
			
		</learningresourcetype>
		<interactivitylevel>
			
				<source>
					<langstring xml:lang="x-none">LOMv1.0</langstring>
				</source>
				<value>
					<langstring xml:lang="x-none">very low</langstring>
				</value>
			
		</interactivitylevel>
		<semanticdensity>
			
				<source>
					<langstring xml:lang="x-none">LOMv1.0</langstring>
				</source>
				<value>
					<langstring xml:lang="x-none">high</langstring>
				</value>
			
		</semanticdensity>
		<intendedenduserrole>
			
				<source>
					<langstring xml:lang="x-none">LOMv1.0</langstring>
				</source>
				<value>
					<langstring xml:lang="x-none">Learner</langstring>
				</value>
			
		</intendedenduserrole>
		<context>
			
				<source>
					<langstring xml:lang="x-none">LOMv1.0</langstring>
				</source>
				<value>
					<langstring xml:lang="x-none">Higher Education</langstring>
				</value>
			
		</context>
		<typicalagerange>
			<langstring xml:lang="x-none">18-</langstring>
		</typicalagerange>
		<difficulty>
			
				<source>
					<langstring xml:lang="x-none">LOMv1.0</langstring>
				</source>
				<value>
					<langstring xml:lang="x-none">difficult</langstring>
				</value>
			
		</difficulty>
		<typicallearningtime>
			<datetime>PT3H</datetime>
		</typicallearningtime>
		<description>
			<langstring xml:lang="en">Comments on how this resource is to be used.</langstring>
			<langstring xml:lang="nl">Commentaar over hoe je dit document kan gebruiken.</langstring>
		</description>
		<language>en</language>
	</educational>
	<rights>
		<cost>
			
				<source>
					<langstring xml:lang="x-none">LOMv1.0</langstring>
				</source>
				<value>
					<langstring xml:lang="x-none">yes</langstring>
				</value>
			
		</cost>
		<copyrightandotherrestrictions>
			
				<source>
					<langstring xml:lang="x-none">LOMv1.0</langstring>
				</source>
				<value>
					<langstring xml:lang="x-none">yes</langstring>
				</value>
			
		</copyrightandotherrestrictions>
		<description>
			<langstring xml:lang="en">Copyright  2000 by the Institute of Electrical and Electronics Engineers, Inc.

3 Park Avenue

New York, NY 10016-5997, USA

All rights reserved.

This is an unapproved draft of a proposed IEEE Standard, subject to change. Permission is hereby granted for IEEE Standards Committee participants to reproduce this document for purposes of IEEE standardization activities. If this document is to be submitted to ISO or IEC, notification shall be given to the IEEE Copyright Administrator. Permission is also granted for member bodies and technical committees of ISO and IEC to reproduce this document for purposes of developing a national position. Other entities seeking permission to reproduce this document for standardization or other activities, or to reproduce portions of this document for these or other uses, must contact the IEEE Standards Department for the appropriate license. Use of information contained in this unapproved draft is at your own risk.

IEEE Standards Department

Copyright and Permissions

445 Hoes Lane, P.O. Box 1331

Piscataway, NJ 08855-1331, USA</langstring>
		</description>
	</rights>
	<relation>
		<kind>
			
				<source>
					<langstring xml:lang="x-none">LOMv1.0</langstring>
				</source>
				<value>
					<langstring xml:lang="x-none">IsBasedOn</langstring>
				</value>
			
		</kind>
		<resource>
			<catalogentry>
				<catalog>LOM WG12's set of base documents.</catalog>
				<entry>
					<langstring xml:lang="en">The joint ARIADNE-IMS submission to the LOM WG.</langstring>
				</entry>
			</catalogentry>
		</resource>
	</relation>
	<annotation>
		<person>
				<vcard>BEGIN:VCARD
FN:Philip Dodds
END:VCARD</vcard>
		</person>
		<date>
			<datetime>2000-12-17</datetime>
		</date>
		<description>
			<langstring xml:lang="en">I have read this with great attention and extreme interest. I think this is great!</langstring>
		</description>
	</annotation>
	<classification>
		<purpose>
			
				<source>
					<langstring xml:lang="x-none">LOMv1.0</langstring>
				</source>
				<value>
					<langstring xml:lang="x-none">Discipline</langstring>
				</value>
			
		</purpose>
		<taxonpath>
			<source>
				<langstring xml:lang="en">A great taxonomic source.</langstring>
			</source>
			<taxon>
				<entry>
					<langstring xml:lang="en">Information Science</langstring>
				</entry>
				<taxon>
					<entry>
						<langstring xml:lang="en">Information Processing</langstring>
					</entry>
					<taxon>
						<entry>
							<langstring xml:lang="en">Metadata</langstring>
						</entry>
					</taxon>
				</taxon>
			</taxon>
		</taxonpath>
	</classification>
</lom>
"""


class MetadataParserTests(unittest.TestCase):
	def setUp(self):
		self.f=StringIO(SAMPLE_METADATA)

	def testParser(self):
		parser=MetadataParser()
		md=parser.ReadMetadata(self.f)
		self.failUnless(md.general.title.MatchLanguage("en")==["Draft Standard for Learning Object Metadata"])
		self.failUnless(len(md.general.identifier)==2,"identifier count")
		identifier=md.general.identifier[1]
		self.failUnless(identifier.catalog=="ADL" and identifier.entry=="SCORM 1.1","identifier details")
		self.failUnless(len(md.general.language)==1 and md.general.language[0]=="en","language")
		self.failUnless(len(md.general.description)==1,"description")
		descriptionEN=md.general.description[0].MatchLanguage('en')
		descriptionNL=md.general.description[0].MatchLanguage('nl')
		self.failUnless(len(descriptionEN)==1 and len(descriptionNL)==1 and
			descriptionEN[0][:23]=="Metadata is information" and
			descriptionNL[0][:22]=="Metadata is informatie","description details")
		self.failUnless(len(md.general.keyword)==2,"keyword")
		keywordFR=md.general.keyword[1].MatchLanguage('fr')
		self.failUnless(len(keywordFR)==1 and keywordFR[0]=="objet d'apprentissage","keyword details")
		self.failUnless(len(md.general.coverage)==1,"coverage")
		coverageNL=md.general.coverage[0].MatchLanguage('nl')
		self.failUnless(len(coverageNL)==1 and coverageNL[0]=="hedendaags","coverage details")
		self.failUnless(md.general.structure and md.general.structure.source=="LOMv1.0"
			and md.general.structure.value=="linear","structure")
		self.failUnless(md.general.aggregationLevel and md.general.aggregationLevel.source=="LOMv1.0"
			and md.general.aggregationLevel.value=="2","aggregationLevel")
		self.failUnless(md.lifeCycle.version and md.lifeCycle.version.strings[0].language=="x-none"
			and md.lifeCycle.version.strings[0].string=="1.0","version")
		self.failUnless(md.lifeCycle.status and md.lifeCycle.status.source=="LOMv1.0"
			and md.lifeCycle.status.value=="draft","status")
	
	def testReadBack(self):
		"""Check read/write cycle of sample metadata"""
		parser=MetadataParser()
		md=parser.ReadMetadata(self.f)
		xmlOutput=StringIO()
		WriteLRMXML(xmlOutput,md)
		xmlOutput.seek(0)
		# print xmlOutput.read()
		xmlOutput.seek(0)
		md=parser.ReadMetadata(xmlOutput)
		# self.CheckSampleData(md)
			
if __name__ == "__main__":
	unittest.main()