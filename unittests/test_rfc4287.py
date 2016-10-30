#! /usr/bin/env python

import os
import unittest

from io import BytesIO

import pyslet.rfc4287 as atom

from pyslet import iso8601
from pyslet.py2 import dict_keys
from pyslet.xml import namespace as xmlns


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(AtomElementTests, 'test'),
        unittest.makeSuite(AtomTextTests, 'test'),
        unittest.makeSuite(PersonTests, 'test'),
        unittest.makeSuite(AtomDateTests, 'test'),
        unittest.makeSuite(FeedTests, 'test'),
        unittest.makeSuite(EntryTests, 'test'),
        unittest.makeSuite(Atom4287Tests, 'test')
    ))


EXAMPLE_1 = b"""<?xml version="1.0" encoding="utf-8"?>
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

EXAMPLE_2 = b"""<?xml version="1.0" encoding="utf-8"?>
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

    def test_constants(self):
        self.assertTrue(atom.ATOM_NAMESPACE == "http://www.w3.org/2005/Atom",
                        "Wrong atom namespace: %s" % atom.ATOM_NAMESPACE)
        self.assertTrue(atom.ATOM_MIMETYPE == "application/atom+xml",
                        "Wrong atom mime type: %s" % atom.ATOM_MIMETYPE)


class AtomElementTests(unittest.TestCase):

    def test_constructor(self):
        e = atom.AtomElement(None)
        self.assertTrue(e.parent is None, 'empty parent on construction')
        self.assertTrue(e.xmlname is None, 'element name on construction')
        self.assertTrue(e.get_base() is None,
                        "xml:base present on construction")
        self.assertTrue(e.get_lang() is None,
                        "xml:lang present on construction")
        attrs = e.get_attributes()
        self.assertTrue(sum(1 for k in dict_keys(attrs)) == 0,
                        "Attributes present on construction")
        e2 = atom.AtomElement(e)
        self.assertTrue(e2.parent is e, 'non-empty parent on construction')

    def test_get_set(self):
        e = atom.AtomElement(None)
        e.set_base("http://www.example.com/")
        self.assertTrue(e.get_base() == "http://www.example.com/",
                        "Get/Set example xml:base value")
        e.set_lang("en-US")
        self.assertTrue(e.get_lang() == "en-US",
                        "Get/Set example xml:lang value")
        attrs = e.get_attributes()
        self.assertTrue(sum(1 for k in dict_keys(attrs)) == 2,
                        "Two attributes expected")
        self.assertTrue(attrs[(xmlns.XML_NAMESPACE, 'base')] ==
                        "http://www.example.com/", "Base attribute")
        self.assertTrue(attrs[(xmlns.XML_NAMESPACE, 'lang')] == "en-US",
                        "Lang attribute")
        e.set_base(None)
        attrs = e.get_attributes()
        self.assertTrue(e.get_base() is None, "Get/Set empty xml:base value")
        self.assertTrue(sum(1 for k in dict_keys(attrs)) == 1,
                        "One attribute expected")
        e.set_lang(None)
        attrs = e.get_attributes()
        self.assertTrue(e.get_lang() is None, "Get/Set empty xml:lang value")
        self.assertTrue(sum(1 for k in dict_keys(attrs)) == 0,
                        "No attributes expected")


class AtomTextTests(unittest.TestCase):

    """Untested:
    If the value is "text", the content of the Text construct MUST NOT
    contain child elements.
    If the value of "type" is "html", the content of the Text construct
    MUST NOT contain child elements
    If the value of "type" is "xhtml", the content of the Text construct
    MUST be a single XHTML div element [XHTML]
    The XHTML div element itself MUST NOT be considered part of the content."""

    def test_constructor(self):
        text = atom.Text(None)
        self.assertTrue(text.xmlname is None, 'element name on construction')
        self.assertTrue(isinstance(text, atom.AtomElement),
                        "Text not an AtomElement")
        self.assertTrue(text.get_base() is None,
                        "xml:base present on construction")
        self.assertTrue(text.get_lang() is None,
                        "xml:lang present on construction")
        attrs = text.get_attributes()
        self.assertTrue(sum(1 for k in dict_keys(attrs)) == 1,
                        "Attributes present on construction")
        self.assertTrue(text.get_value() == '',
                        "Content present on construction")

    def test_string_value(self):
        text = atom.Text(None)
        text.set_value("Some text")
        self.assertTrue(text.get_value() == "Some text",
                        "String constructor data")
        self.assertTrue(text.type == atom.TextType.text,
                        "Default text type not 'text' on construction")
        text = atom.Text(None)
        text.set_value("Some other text", atom.TextType.xhtml)
        self.assertTrue(text.get_value() == 'Some other text',
                        "String constructor data: found %s" % text.get_value())
        self.assertTrue(text.type == atom.TextType.xhtml,
                        "Override text type on construction")

    def test_types(self):
        """Text constructs MAY have a "type" attribute.  When present,
        the value MUST be one of "text", "html", or "xhtml".  If the
        "type" attribute is not provided, Atom Processors MUST behave as
        though it were present with a value of "text"."""
        text = atom.Text(None)
        attrs = text.get_attributes()
        self.assertTrue(text.type == atom.TextType.text and
                        attrs[(xmlns.NO_NAMESPACE, 'type')] == "text",
                        "Default text type not 'text' on construction")
        text.set_value('<p>Hello', atom.TextType.html)
        self.assertTrue(text.type == atom.TextType.html,
                        "html text type failed")
        text.set_value('<p>Hello</p>', atom.TextType.xhtml)
        self.assertTrue(text.type == atom.TextType.xhtml,
                        "xhtml text type failed")
        try:
            text.set_value('Hello\\par ', 'rtf')
            self.fail("rtf text type failed to raise error")
        except ValueError:
            pass


class PersonTests(unittest.TestCase):

    """Untested:
    The "atom:name" element's content conveys a human-readable name for
    the person.  The content of atom:name is Language-Sensitive.  Person
    constructs MUST contain exactly one "atom:name" element.
    Person constructs MAY contain an atom:uri element, but MUST
    NOT contain more than one.
    Person constructs MAY contain an
    atom:email element, but MUST NOT contain more than one.  Its content
    MUST conform to the "addr-spec" production in [RFC2822]."""

    def test_constructor(self):
        person = atom.Person(None)
        self.assertTrue(person.xmlname is None, 'element name on construction')
        self.assertTrue(isinstance(person, atom.AtomElement),
                        "Person not an AtomElement")
        self.assertTrue(person.get_base() is None,
                        "xml:base present on construction")
        self.assertTrue(person.get_lang() is None,
                        "xml:lang present on construction")
        attrs = person.get_attributes()
        self.assertTrue(sum(1 for k in dict_keys(attrs)) == 0,
                        "Attributes present on construction")
        self.assertTrue(isinstance(person.Name, atom.Name),
                        "Name on construction")
        self.assertTrue(person.URI is None, "URI on construction")
        self.assertTrue(person.Email is None, "Email on construction")


class AtomDateTests(unittest.TestCase):

    """Untested:

    Note that there MUST NOT be any white space in a Date construct or
    in any IRI.  Some XML-emitting implementations erroneously insert
    white space around values by default, and such implementations will
    emit invalid Atom Documents.

    In addition, an uppercase "T" character MUST be used to separate
    date and time, and an uppercase "Z" character MUST be present in the
    absence of a numeric time zone offset."""

    def test_atom_date_constructor(self):
        date = atom.Date(None)
        self.assertTrue(date.xmlname is None, 'element name on construction')
        self.assertTrue(isinstance(date, atom.AtomElement),
                        "Date not an AtomElement")
        self.assertTrue(date.get_base() is None,
                        "xml:base present on construction")
        self.assertTrue(date.get_lang() is None,
                        "xml:lang present on construction")
        attrs = date.get_attributes()
        self.assertTrue(sum(1 for k in dict_keys(attrs)) == 0,
                        "Attributes present on construction")
        self.assertTrue(isinstance(date.get_value(), iso8601.TimePoint),
                        "Value not a TimePoint")
        date.set_value("2016-10-22T19:10:00Z")
        date2 = date.get_value()
        self.assertTrue(isinstance(date2, iso8601.TimePoint),
                        "Value not a TimePoint")
        self.assertTrue(
            date2 == iso8601.TimePoint.from_str("2016-10-22T19:10:00Z"))


class FeedTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.cwd = os.getcwd()

    def tearDown(self):     # noqa
        os.chdir(self.cwd)

    def test_constructor(self):
        feed = atom.Feed(None)
        self.assertTrue(
            isinstance(feed, atom.AtomElement), "Feed not an AtomElement")
        self.assertTrue(feed.xmlname == "feed", "Feed XML name")
        self.assertTrue(
            feed.get_base() is None, "xml:base present on construction")
        self.assertTrue(
            feed.get_lang() is None, "xml:lang present on construction")
        self.assertTrue(len(feed.Entry) == 0, "Non-empty feed on construction")
        attrs = feed.get_attributes()
        self.assertTrue(sum(1 for k in dict_keys(attrs)) == 0,
                        "Attributes present on construction")

    def test_read_xml(self):
        doc = atom.AtomDocument()
        doc.read(src=BytesIO(EXAMPLE_1))
        feed = doc.root
        self.assertTrue(isinstance(feed, atom.Feed), "Example 1 not a feed")
        title = feed.Title
        self.assertTrue(isinstance(title, atom.Text) and
                        title.get_value() == "Example Feed",
                        "Example 1 title: " + str(title))
        link = feed.Link[0]
        self.assertTrue(isinstance(link, atom.Link) and link.href ==
                        "http://example.org/", "Example 1 link")
        updated = feed.Updated
        self.assertTrue(
            isinstance(updated.get_value(), iso8601.TimePoint) and
            updated.get_value() ==
            iso8601.TimePoint.from_str("2003-12-13T18:30:02Z"),
            "Example 1 updated: found %s" % updated.get_value())
        author = feed.Author[0]
        self.assertTrue(
            isinstance(author, atom.Person) and author.Name.get_value() ==
            "John Doe", "Example 1 author")
        self.assertTrue(
            isinstance(feed.AtomId, atom.AtomId) and
            feed.AtomId.get_value() ==
            "urn:uuid:60a76c80-d399-11d9-b93C-0003939e0af6", "Example 1 id")
        entries = feed.Entry
        self.assertTrue(
            len(entries) == 1,
            "Example 1: wrong number of entries (%i)" % len(entries))
        entry = entries[0]
        title = entry.Title
        self.assertTrue(
            isinstance(title, atom.Text) and title.get_value() ==
            "Atom-Powered Robots Run Amok", "Example 1 entry title")
        link = entry.Link[0]
        self.assertTrue(isinstance(link, atom.Link) and link.href ==
                        "http://example.org/2003/12/13/atom03",
                        "Example 1 entry link")
        self.assertTrue(
            isinstance(entry.AtomId, atom.AtomId) and
            entry.AtomId.get_value() ==
            "urn:uuid:1225c695-cfb8-4ebb-aaaa-80da344efa6a",
            "Example 1 entry id")
        updated = entry.Updated
        self.assertTrue(isinstance(updated, atom.Date) and
                        updated.get_value() ==
                        iso8601.TimePoint.from_str("2003-12-13T18:30:02Z"),
                        "Example 1 entry updated")
        summary = entry.Summary
        self.assertTrue(isinstance(summary, atom.Text) and
                        summary.get_value() == "Some text.",
                        "Example 1 entry summary")
        doc.read(src=BytesIO(EXAMPLE_2))
        feed = doc.root
        subtitle = feed.Subtitle
        self.assertTrue(
            isinstance(subtitle, atom.Subtitle) and
            subtitle.type == atom.TextType.html and
            subtitle.get_value().strip() ==
            "A <em>lot</em> of effort went into making this effortless",
            "Example 2 subtitle")
        links = feed.Link
        self.assertTrue(
            links[0].rel == "alternate" and
            links[0].type == "text/html" and
            links[0].hreflang == "en" and
            links[0].href == "http://example.org/",
            "Example 2, link 0 attributes")
        self.assertTrue(
            links[1].rel == "self" and
            links[1].type == "application/atom+xml" and
            links[1].hreflang is None and
            links[1].href == "http://example.org/feed.atom",
            "Example 2, link 1 attributes")
        rights = feed.Rights
        self.assertTrue(
            isinstance(rights, atom.Rights) and rights.get_value() ==
            "Copyright (c) 2003, Mark Pilgrim", "Example 2, rights")
        generator = feed.Generator
        self.assertTrue(
            isinstance(generator, atom.Generator) and
            generator.uri == "http://www.example.com/" and
            generator.version == "1.0" and
            generator.get_value().strip() == "Example Toolkit",
            "Example 2, generator")

        """<entry>
            <title>Atom draft-07 snapshot</title>
            <link rel="alternate" type="text/html"
            <href="http://example.org/2005/04/02/atom"/>
            <link rel="enclosure" type="audio/mpeg" length="1337"
            <href="http://example.org/audio/ph34r_my_podcast.mp3"/>
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
            <xml:base="http://diveintomark.org/">
                <div xmlns="http://www.w3.org/1999/xhtml">
                <p><i>[Update: The Atom draft is finished.]</i></p>
                </div>
            </content>
            </entry>
        </feed>"""

    def test_constraint1(self):
        """TODO

*   atom:feed elements MUST contain one or more atom:author elements,
    unless all of the atom:feed element's child atom:entry elements
    contain at least one atom:author element.

*   atom:feed elements MUST NOT contain more than one atom:generator
    element.

*   atom:feed elements MUST NOT contain more than one atom:icon element.

*   atom:feed elements MUST NOT contain more than one atom:logo element.

*   atom:feed elements MUST contain exactly one atom:id element.

*   atom:feed elements SHOULD contain one atom:link element with a rel
    attribute value of "self".  This is the preferred URI for retrieving
    Atom Feed Documents representing this Atom feed.

*   atom:feed elements MUST NOT contain more than one atom:link element
    with a rel attribute value of "alternate" that has the same
    combination of type and hreflang attribute values.

*   atom:feed elements MAY contain additional atom:link elements beyond
    those described above.

*   atom:feed elements MUST NOT contain more than one atom:rights
    element.

*   atom:feed elements MUST NOT contain more than one atom:subtitle
    element.

*   atom:feed elements MUST contain exactly one atom:title element.

*   atom:feed elements MUST contain exactly one atom:updated element."""
        pass


class EntryTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.feed = atom.Feed(None)

    def tearDown(self):     # noqa
        pass

    def test_constructor(self):
        entry = atom.Entry(None)
        self.assertTrue(
            isinstance(entry, atom.AtomElement), "Entry not an AtomElement")
        self.assertTrue(
            entry.get_base() is None, "xml:base present on construction")
        self.assertTrue(
            entry.get_lang() is None, "xml:lang present on construction")
        attrs = entry.get_attributes()
        self.assertTrue(sum(1 for k in dict_keys(attrs)) == 0,
                        "Attributes present on construction")

    def test_constraints(self):
        """TODO

*   atom:entry elements MUST contain one or more atom:author elements,
    unless the atom:entry contains an atom:source element that contains
    an atom:author element or, in an Atom Feed Document, the atom:feed
    element contains an atom:author element itself.

*   atom:entry elements MAY contain any number of atom:category elements.

*   atom:entry elements MUST NOT contain more than one atom:content
    element.

*   atom:entry elements MAY contain any number of atom:contributor
    elements.

*   atom:entry elements MUST contain exactly one atom:id element.

*   atom:entry elements that contain no child atom:content element MUST
    contain at least one atom:link element with a rel attribute value of
    "alternate".

*   atom:entry elements MUST NOT contain more than one atom:link element
    with a rel attribute value of "alternate" that has the same
    combination of type and hreflang attribute values.

*   atom:entry elements MAY contain additional atom:link elements beyond
    those described above.

*   atom:entry elements MUST NOT contain more than one atom:published
    element.

*   atom:entry elements MUST NOT contain more than one atom:rights
    element.

*   atom:entry elements MUST NOT contain more than one atom:source
    element.

*   atom:entry elements MUST contain an atom:summary element in either
    of the following cases:

    -   the atom:entry contains an atom:content that has a "src"
        attribute (and is thus empty).

    -   the atom:entry contains content that is encoded in Base64; i.e.,
        the "type" attribute of atom:content is a MIME media type
        [MIMEREG], but is not an XML media type [RFC3023], does not
        begin with "text/", and does not end with "/xml" or "+xml".

*   atom:entry elements MUST NOT contain more than one atom:summary
    element.

*   atom:entry elements MUST contain exactly one atom:title element.

*   atom:entry elements MUST contain exactly one atom:updated element.
"""
        pass

if __name__ == "__main__":
    unittest.main()
