#! /usr/bin/env python

import unittest

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(AtomElementTests,'test') ,
		unittest.makeSuite(AtomTextTests,'test') ,
		unittest.makeSuite(AtomPersonTests,'test') ,
		unittest.makeSuite(AtomDateTests,'test') ,
		unittest.makeSuite(AtomFeedTests,'test') ,
		unittest.makeSuite(AtomEntryTests,'test'),
		unittest.makeSuite(Atom4287Tests,'test')
		))

from pyslet.rfc4287 import *

import os
from StringIO import StringIO

EXAMPLE_1="""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">

 <title>Example Feed</title>
 <link href="http://example.org/"/>
 <updated>2003-12-13T18:30:02Z</updated>
 <author>
	<name>John Doe</name>
 </author>
 <id>urn:uuid:60a76c80-d399-11d9-b93C-0003939e0af6</id>

 <entry>
	<title>Atom-Powered Robots Run Amok</title>
	<link href="http://example.org/2003/12/13/atom03"/>
	<id>urn:uuid:1225c695-cfb8-4ebb-aaaa-80da344efa6a</id>
	<updated>2003-12-13T18:30:02Z</updated>
	<summary>Some text.</summary>
 </entry>

</feed>"""

EXAMPLE_2="""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
 <title type="text">dive into mark</title>
 <subtitle type="html">
	A &lt;em&gt;lot&lt;/em&gt; of effort went into making this effortless
 </subtitle>
 <updated>2005-07-31T12:29:29Z</updated>
 <id>tag:example.org,2003:3</id>
 <link rel="alternate" type="text/html"
  hreflang="en" href="http://example.org/"/>
 <link rel="self" type="application/atom+xml"
  href="http://example.org/feed.atom"/>
 <rights>Copyright (c) 2003, Mark Pilgrim</rights>
 <generator uri="http://www.example.com/" version="1.0">
	Example Toolkit
 </generator>
 <entry>
	<title>Atom draft-07 snapshot</title>
	<link rel="alternate" type="text/html"
	href="http://example.org/2005/04/02/atom"/>
	<link rel="enclosure" type="audio/mpeg" length="1337"
	href="http://example.org/audio/ph34r_my_podcast.mp3"/>
	<id>tag:example.org,2003:3.2397</id>
	<updated>2005-07-31T12:29:29Z</updated>
	<published>2003-12-13T08:29:29-04:00</published>
	<author>
		<name>Mark Pilgrim</name>
		<uri>http://example.org/</uri>
		<email>f8dy@example.com</email>
	</author>
	<contributor>
		<name>Sam Ruby</name>
	</contributor>
	<contributor>
		<name>Joe Gregorio</name>
	</contributor>
	<content type="xhtml" xml:lang="en"
	xml:base="http://diveintomark.org/">
		<div xmlns="http://www.w3.org/1999/xhtml">
		<p><i>[Update: The Atom draft is finished.]</i></p>
		</div>
	</content>
 </entry>
</feed>"""


class Atom4287Tests(unittest.TestCase):
	def testCaseConstants(self):
		self.failUnless(ATOM_NAMESPACE=="http://www.w3.org/2005/Atom","Wrong atom namespace: %s"%ATOM_NAMESPACE)
		self.failUnless(ATOM_MIMETYPE=="application/atom+xml","Wrong atom mime type: %s"%ATOM_MIMETYPE)

class AtomElementTests(unittest.TestCase):
	def testCaseConstructor(self):
		e=AtomElement(None)
		self.failUnless(e.parent is None,'empty parent on construction')
		self.failUnless(e.xmlname==None,'element name on construction')
		self.failUnless(e.GetBase() is None,"xml:base present on construction")
		self.failUnless(e.GetLang() is None,"xml:lang present on construction")
		attrs=e.GetAttributes()
		self.failUnless(len(attrs.keys())==0,"Attributes present on construction")
		e2=AtomElement(e)
		self.failUnless(e2.parent is e,'non-empty parent on construction')
		
	def testCaseGetSet(self):
		e=AtomElement(None)
		e.SetBase("http://www.example.com/")
		self.failUnless(e.GetBase()=="http://www.example.com/","Get/Set example xml:base value")
		e.SetLang("en-US")
		self.failUnless(e.GetLang()=="en-US","Get/Set example xml:lang value")
		attrs=e.GetAttributes()
		self.failUnless(len(attrs.keys())==2,"Two attributes expected")
		self.failUnless(attrs[(xmlns.XML_NAMESPACE,'base')]=="http://www.example.com/","Base attribute")
		self.failUnless(attrs[(xmlns.XML_NAMESPACE,'lang')]=="en-US","Lang attribute")
		e.SetBase(None)
		attrs=e.GetAttributes()
		self.failUnless(e.GetBase() is None,"Get/Set empty xml:base value")
		self.failUnless(len(attrs.keys())==1,"One attribute expected")
		e.SetLang(None)
		attrs=e.GetAttributes()
		self.failUnless(e.GetLang() is None,"Get/Set empty xml:lang value")
		self.failUnless(len(attrs.keys())==0,"No attributes expected")


class AtomTextTests(unittest.TestCase):
	"""Untested:
	If the value is "text", the content of the Text construct MUST NOT
	contain child elements.
	If the value of "type" is "html", the content of the Text construct
	MUST NOT contain child elements
	If the value of "type" is "xhtml", the content of the Text construct
	MUST be a single XHTML div element [XHTML]
	The XHTML div element itself MUST NOT be considered part of the content."""
	def testCaseConstructor(self):
		text=AtomText(None)
		self.failUnless(text.xmlname==None,'element name on construction')
		self.failUnless(isinstance(text,AtomElement),"AtomText not an AtomElement")
		self.failUnless(text.GetBase() is None,"xml:base present on construction")
		self.failUnless(text.GetLang() is None,"xml:lang present on construction")
		attrs=text.GetAttributes()
		self.failUnless(len(attrs.keys())==1,"Attributes present on construction")
		self.failUnless(text.GetValue() is None,"Content present on construction")

	def testCaseStringValue(self):
		text=AtomText(None)
		text.SetValue("Some text")
		self.failUnless(text.GetValue()=="Some text","String constructor data")
		self.failUnless(text.type=="text","Default text type not 'text' on construction")		
		text=AtomText(None)
		text.SetValue("Some other text","xhtml")
		self.failUnless(text.GetValue()=="Some other text","String constructor data")		
		self.failUnless(text.type=="xhtml","Override text type on construction")		

	def testCaseTypes(self):
		"""Text constructs MAY have a "type" attribute.  When present, the value
		MUST be one of "text", "html", or "xhtml".  If the "type" attribute
		is not provided, Atom Processors MUST behave as though it were
		present with a value of "text"."""
		text=AtomText(None)
		attrs=text.GetAttributes()
		self.failUnless(text.type=="text" and attrs['type']=="text","Default text type not 'text' on construction")
		text.SetValue('<p>Hello','html')
		self.failUnless(text.type=='html',"html text type failed")
		text.SetValue('<p>Hello</p>','xhtml')
		self.failUnless(text.type=='xhtml',"xhtml text type failed")
		try:
			text.SetValue('Hello\\par ','rtf')
			self.fail("rtf text type failed to raise error")
		except ValueError:
			pass

class AtomPersonTests(unittest.TestCase):
	"""Untested:
	The "atom:name" element's content conveys a human-readable name for
	the person.  The content of atom:name is Language-Sensitive.  Person
	constructs MUST contain exactly one "atom:name" element.
	Person constructs MAY contain an atom:uri element, but MUST
	NOT contain more than one.
	Person constructs MAY contain an
	atom:email element, but MUST NOT contain more than one.  Its content
	MUST conform to the "addr-spec" production in [RFC2822]."""
	def testCaseConstructor(self):
		person=AtomPerson(None)
		self.failUnless(person.xmlname==None,'element name on construction')
		self.failUnless(isinstance(person,AtomElement),"AtomPerson not an AtomElement")
		self.failUnless(person.GetBase() is None,"xml:base present on construction")
		self.failUnless(person.GetLang() is None,"xml:lang present on construction")
		attrs=person.GetAttributes()
		self.failUnless(len(attrs.keys())==0,"Attributes present on construction")
		#name=person.name
		#self.failUnless(isinstance(name,AtomText) and name.type=='text',"Name on construction")
		self.failUnless(person.name is None,"Name on construction")
		self.failUnless(person.uri is None,"URI on construction")
		self.failUnless(person.email is None,"Email on construction")


class AtomDateTests(unittest.TestCase):
	"""
	Untested:
	Note that there MUST NOT be any white space in a Date construct or in
	any IRI.  Some XML-emitting implementations erroneously insert white
	space around values by default, and such implementations will emit
	invalid Atom Documents.
	In addition, an uppercase "T"
	character MUST be used to separate date and time, and an uppercase
	"Z" character MUST be present in the absence of a numeric time zone
	offset.
	"""
	def testAtomDateConstructor(self):
		date=AtomDate(None)
		self.failUnless(date.xmlname==None,'element name on construction')
		self.failUnless(isinstance(date,AtomElement),"AtomDate not an AtomElement")
		self.failUnless(date.GetBase() is None,"xml:base present on construction")
		self.failUnless(date.GetLang() is None,"xml:lang present on construction")
		attrs=date.GetAttributes()
		self.failUnless(len(attrs.keys())==0,"Attributes present on construction")
		self.failUnless(isinstance(date.GetValue(),iso8601.TimePoint),"Value not a TimePoint")

			
class AtomFeedTests(unittest.TestCase):
	def setUp(self):
		self.cwd=os.getcwd()
		
	def tearDown(self):
		os.chdir(self.cwd)

	def testCaseConstructor(self):
		feed=AtomFeed(None)
		self.failUnless(isinstance(feed,AtomElement),"AtomFeed not an AtomElement")
		self.failUnless(feed.xmlname=="feed","AtomFeed XML name")
		self.failUnless(feed.GetBase() is None,"xml:base present on construction")
		self.failUnless(feed.GetLang() is None,"xml:lang present on construction")
		self.failUnless(len(feed.entries)==0,"Non-empty feed on construction")
		attrs=feed.GetAttributes()
		self.failUnless(len(attrs.keys())==0,"Attributes present on construction")
		metadata=feed.metadata
		self.failUnless(len(metadata.keys())==0,"Metadata present on construction")
	
	def testCaseReadXML(self):
		doc=AtomDocument()
		doc.Read(src=StringIO(EXAMPLE_1))
		feed=doc.root
		self.failUnless(isinstance(feed,AtomFeed),"Example 1 not a feed")
		title=feed.GetTitle()
		self.failUnless(isinstance(title,AtomText) and title.GetValue()=="Example Feed","Example 1 title: "+str(title))
		link=feed.GetLinks()[0]
		self.failUnless(isinstance(link,AtomLink) and link.href=="http://example.org/","Example 1 link")
		updated=feed.GetUpdated()
		self.failUnless(isinstance(updated,AtomDate) and updated.GetValue()=="2003-12-13T18:30:02Z","Example 1 updated")
		author=feed.GetAuthors()[0]
		self.failUnless(isinstance(author,AtomPerson) and author.name.GetValue()=="John Doe","Example 1 author")
		id=feed.GetId()
		self.failUnless(isinstance(id,AtomId) and id.GetValue()=="urn:uuid:60a76c80-d399-11d9-b93C-0003939e0af6",
			"Example 1 id")
		entries=feed.entries
		self.failUnless(len(entries)==1,"Example 1: wrong number of entries (%i)"%len(entries))
		entry=entries[0]
		title=entry.GetTitle()
		self.failUnless(isinstance(title,AtomText) and title.GetValue()=="Atom-Powered Robots Run Amok","Example 1 entry title")
		link=entry.GetLinks()[0]
		self.failUnless(isinstance(link,AtomLink) and link.href=="http://example.org/2003/12/13/atom03","Example 1 entry link")
		id=entry.GetId()
		self.failUnless(isinstance(id,AtomId) and id.GetValue()=="urn:uuid:1225c695-cfb8-4ebb-aaaa-80da344efa6a",
			"Example 1 entry id")
		updated=entry.GetUpdated()
		self.failUnless(isinstance(updated,AtomDate) and updated.GetValue()=="2003-12-13T18:30:02Z","Example 1 entry updated")
		summary=entry.GetSummary()
		self.failUnless(isinstance(summary,AtomText) and summary.GetValue()=="Some text.","Example 1 entry summary")
		doc.Read(src=StringIO(EXAMPLE_2))
		feed=doc.root
		subtitle=feed.GetSubtitle()
		self.failUnless(isinstance(subtitle,AtomSubtitle) and subtitle.type=='html'
			and subtitle.GetValue().strip()=="A <em>lot</em> of effort went into making this effortless","Example 2 subtitle")
		links=feed.GetLinks()
		self.failUnless(links[0].rel=="alternate" and links[0].type=="text/html" and links[0].hreflang=="en" and
			links[0].href=="http://example.org/","Example 2, link 0 attributes")
		self.failUnless(links[1].rel=="self" and links[1].type=="application/atom+xml" and links[1].hreflang is None and
			links[1].href=="http://example.org/feed.atom","Example 2, link 1 attributes")
		rights=feed.GetRights()
		self.failUnless(isinstance(rights,AtomRights) and rights.GetValue()=="Copyright (c) 2003, Mark Pilgrim","Example 2, rights")
		generator=feed.GetGenerator()
		self.failUnless(isinstance(generator,AtomGenerator) and generator.uri=="http://www.example.com/" and
			generator.version=="1.0" and generator.GetValue().strip()=="Example Toolkit","Example 2, generator")

		""" <entry>
			<title>Atom draft-07 snapshot</title>
			<link rel="alternate" type="text/html"
			href="http://example.org/2005/04/02/atom"/>
			<link rel="enclosure" type="audio/mpeg" length="1337"
			href="http://example.org/audio/ph34r_my_podcast.mp3"/>
			<id>tag:example.org,2003:3.2397</id>
			<updated>2005-07-31T12:29:29Z</updated>
			<published>2003-12-13T08:29:29-04:00</published>
			<author>
				<name>Mark Pilgrim</name>
				<uri>http://example.org/</uri>
				<email>f8dy@example.com</email>
			</author>
			<contributor>
				<name>Sam Ruby</name>
			</contributor>
			<contributor>
				<name>Joe Gregorio</name>
			</contributor>
			<content type="xhtml" xml:lang="en"
			xml:base="http://diveintomark.org/">
				<div xmlns="http://www.w3.org/1999/xhtml">
				<p><i>[Update: The Atom draft is finished.]</i></p>
				</div>
			</content>
			</entry>
		</feed>"""
		
		
	def testCaseConstraint1(self):
		"""atom:feed elements MUST contain one or more atom:author elements,
				unless all of the atom:feed element's child atom:entry elements
				contain at least one atom:author element.
					
		atom:feed elements MUST NOT contain more than one atom:generator
				element.
		o  atom:feed elements MUST NOT contain more than one atom:icon
				element.
		o  atom:feed elements MUST NOT contain more than one atom:logo
				element.
		o  atom:feed elements MUST contain exactly one atom:id element.
		o  atom:feed elements SHOULD contain one atom:link element with a rel
				attribute value of "self".  This is the preferred URI for
				retrieving Atom Feed Documents representing this Atom feed.
		o  atom:feed elements MUST NOT contain more than one atom:link
				element with a rel attribute value of "alternate" that has the
				same combination of type and hreflang attribute values.
		o  atom:feed elements MAY contain additional atom:link elements
				beyond those described above.
		o  atom:feed elements MUST NOT contain more than one atom:rights
				element.
		o  atom:feed elements MUST NOT contain more than one atom:subtitle
				element.
		o  atom:feed elements MUST contain exactly one atom:title element.
		o  atom:feed elements MUST contain exactly one atom:updated element."""
		pass
			
class AtomEntryTests(unittest.TestCase):
	def setUp(self):
		self.feed=AtomFeed(None)
	
	def tearDown(self):
		pass
		
	def testCaseConstructor(self):
		entry=AtomEntry(None)
		self.failUnless(isinstance(entry,AtomElement),"AtomEntry not an AtomElement")
		self.failUnless(entry.GetBase() is None,"xml:base present on construction")
		self.failUnless(entry.GetLang() is None,"xml:lang present on construction")
		attrs=entry.GetAttributes()
		self.failUnless(len(attrs.keys())==0,"Attributes present on construction")
	
	def textCaseConstraints(self):
		"""
		o  atom:entry elements MUST contain one or more atom:author elements,
			unless the atom:entry contains an atom:source element that
			contains an atom:author element or, in an Atom Feed Document, the
			atom:feed element contains an atom:author element itself.
		o  atom:entry elements MAY contain any number of atom:category
			elements.
		o  atom:entry elements MUST NOT contain more than one atom:content
			element.
		o  atom:entry elements MAY contain any number of atom:contributor
			elements.
		o  atom:entry elements MUST contain exactly one atom:id element.
		o  atom:entry elements that contain no child atom:content element
			MUST contain at least one atom:link element with a rel attribute
			value of "alternate".
		o  atom:entry elements MUST NOT contain more than one atom:link
			element with a rel attribute value of "alternate" that has the
			same combination of type and hreflang attribute values.
		o  atom:entry elements MAY contain additional atom:link elements
			beyond those described above.
		o  atom:entry elements MUST NOT contain more than one atom:published
				element.
		o  atom:entry elements MUST NOT contain more than one atom:rights
			element.
		o  atom:entry elements MUST NOT contain more than one atom:source
			element.
		o  atom:entry elements MUST contain an atom:summary element in either
			of the following cases:
			*  the atom:entry contains an atom:content that has a "src"
				attribute (and is thus empty).
			*  the atom:entry contains content that is encoded in Base64;
				i.e., the "type" attribute of atom:content is a MIME media type
				[MIMEREG], but is not an XML media type [RFC3023], does not
				begin with "text/", and does not end with "/xml" or "+xml".
		o  atom:entry elements MUST NOT contain more than one atom:summary
			element.
		o  atom:entry elements MUST contain exactly one atom:title element.
		o  atom:entry elements MUST contain exactly one atom:updated element.
		"""
		pass
		
if __name__ == "__main__":
	unittest.main()

