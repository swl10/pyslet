#! /usr/bin/env python

import unittest

import pyslet.iso8601 as iso
import pyslet.html401 as html
import pyslet.rfc2396 as uri
import pyslet.xml.structures as xml

from pyslet.py2 import (
    dict_items,
    is_text,
    range3,
    to_text,
    uempty,
    ul)
from pyslet.http.params import MediaType


def suite():
    return unittest.TestSuite((
        unittest.makeSuite(CustomTypeTests, 'test'),
        unittest.makeSuite(ElementTests, 'test'),
        unittest.makeSuite(ParserTests, 'test'),
    ))


class CustomTypeTests(unittest.TestCase):

    def test_named(self):
        class TestName(html.NamedBoolean):
            name = "TEST"

        self.assertTrue(TestName.from_str('TEST'))
        self.assertTrue(TestName.from_str(' TEST  '))
        self.assertFalse(TestName.from_str(None))
        try:
            TestName.from_str('TESTING')
            self.fail("Expected ValueError")
        except ValueError:
            pass
        # check upper case
        self.assertTrue(TestName.from_str_upper('test'))
        self.assertTrue(TestName.from_str_upper('  Test '))
        # check output
        self.assertTrue(TestName.to_str(True) == "TEST")
        self.assertTrue(TestName.to_str(False) is None)
        self.assertTrue(TestName.to_str(None) is None)
        # Finally check lower casing (cheat a bit)
        try:
            TestName.from_str_lower('TEST')
            self.fail("Expected ValueError")
        except ValueError:
            pass
        TestName.name = 'test'
        self.assertTrue(TestName.from_str_lower('TEST'))

    def test_color(self):
        c = html.Color("Black")
        self.assertTrue(c.r == 0)
        self.assertTrue(c.g == 0)
        self.assertTrue(c.b == 0)
        c = html.Color((1, 2, 3))
        self.assertTrue(to_text(c) == "#010203")
        self.assertTrue(html.BLACK == "#000000")
        self.assertTrue(html.GREEN == "#008000")
        self.assertTrue(html.SILVER == "#C0C0C0")
        self.assertTrue(html.LIME == "#00FF00")
        self.assertTrue(html.GRAY == "#808080")
        self.assertTrue(html.OLIVE == "#808000")
        self.assertTrue(html.WHITE == "#FFFFFF")
        self.assertTrue(html.YELLOW == "#FFFF00")
        self.assertTrue(html.MAROON == "#800000")
        self.assertTrue(html.NAVY == "#000080")
        self.assertTrue(html.RED == "#FF0000")
        self.assertTrue(html.BLUE == "#0000FF")
        self.assertTrue(html.PURPLE == "#800080")
        self.assertTrue(html.TEAL == "#008080")
        self.assertTrue(html.FUCHSIA == "#FF00FF")
        self.assertTrue(html.AQUA == "#00FFFF")

    def test_length(self):
        l = html.Length(10, html.Length.PERCENTAGE)
        self.assertTrue(l.type == html.Length.PERCENTAGE, "Specified type")
        self.assertTrue(l.value == 10, "Specified value")
        self.assertTrue(l.resolve_value(50) == 5, "Percentage value")
        # comparison
        self.assertTrue(l == html.Length(10, html.Length.PERCENTAGE))
        self.assertFalse(l == html.Length(11, html.Length.PERCENTAGE))
        self.assertFalse(l == html.Length(10, html.Length.PIXEL))
        l = html.Length(10)
        self.assertTrue(l.type == html.Length.PIXEL, "Specified type")
        self.assertTrue(l.value == 10, "Specified value")
        self.assertTrue(l.resolve_value(50) == 10, "Pixel value")
        self.assertFalse(l == html.Length(10, html.Length.PERCENTAGE))
        self.assertFalse(l == html.Length(11, html.Length.PIXEL))
        self.assertTrue(l == html.Length(10, html.Length.PIXEL))
        l2 = html.Length(l)
        self.assertTrue(l2.type == html.Length.PIXEL, "Copied type")
        self.assertTrue(l2.value == 10, "Copied value")

    def test_multi_length(self):
        l = html.MultiLength(10, html.MultiLength.PERCENTAGE)
        self.assertTrue(
            l.type == html.MultiLength.PERCENTAGE, "Specified type")
        self.assertTrue(l.value == 10, "Specified value")
        self.assertTrue(l.resolve_value(50) == 5, "Percentage value")
        # comparison
        self.assertTrue(l == html.MultiLength(10, html.MultiLength.PERCENTAGE))
        self.assertFalse(
            l == html.MultiLength(11, html.MultiLength.PERCENTAGE))
        self.assertFalse(l == html.MultiLength(10, html.MultiLength.PIXEL))
        self.assertFalse(l == html.MultiLength(10, html.MultiLength.RELATIVE))
        l = html.MultiLength(10)
        self.assertTrue(l.type == html.MultiLength.PIXEL, "Default type")
        self.assertTrue(l.value == 10, "Specified value")
        self.assertTrue(l.resolve_value(50) == 10, "Pixel value")
        self.assertFalse(
            l == html.MultiLength(10, html.MultiLength.PERCENTAGE))
        self.assertFalse(l == html.MultiLength(11, html.MultiLength.PIXEL))
        self.assertTrue(l == html.MultiLength(10, html.MultiLength.PIXEL))
        self.assertFalse(l == html.MultiLength(10, html.MultiLength.RELATIVE))
        l = html.MultiLength(10, html.MultiLength.RELATIVE)
        self.assertTrue(l.type == html.MultiLength.RELATIVE, "Specified type")
        self.assertTrue(l.value == 10, "Specified value")
        self.assertTrue(l.resolve_value(50) == 50, "ommitted dim is greedy")
        self.assertTrue(l.resolve_value(50, 100) == 5, "Relative value")
        self.assertFalse(
            l == html.MultiLength(10, html.MultiLength.PERCENTAGE))
        self.assertFalse(l == html.MultiLength(11, html.MultiLength.RELATIVE))
        self.assertFalse(l == html.MultiLength(10, html.MultiLength.PIXEL))
        self.assertTrue(l == html.MultiLength(10, html.MultiLength.RELATIVE))
        l2 = html.Length(l)
        self.assertTrue(l2.type == html.MultiLength.RELATIVE, "Copied type")
        self.assertTrue(l2.value == 10, "Copied value")

    def test_media_desc(self):
        m = html.MediaDesc.from_str(
            "screen, 3d-glasses,  , print and resolution > 90dpi, @paper")
        # ignore empty or illegal values
        self.assertTrue(len(m) == 3)
        self.assertTrue("screen" in m)
        # case insensitive contains!
        self.assertTrue("3D-glasses" in m)
        self.assertTrue("print" in m)
        self.assertTrue(str(m) == "3d-glasses,print,screen")
        # construct from iterable of strings
        m1 = html.MediaDesc(["TV", "projection"])
        self.assertTrue(len(m1) == 2)
        self.assertTrue(str(m1) == "projection,tv")
        # combine using |
        m2 = m | m1
        self.assertTrue(len(m2) == 5)
        self.assertTrue("tv" in m2)
        self.assertTrue("screen" in m2)
        self.assertTrue(str(m2) == "3d-glasses,print,projection,screen,tv")
        # combine using | from string
        m3 = m | "tv, projection system"
        self.assertTrue(len(m3) == 5)
        self.assertTrue("projection" in m3)
        self.assertTrue("screen" in m3)
        # check the reverse operation
        m3 = "tv, projection system" | m
        self.assertTrue(len(m3) == 5)
        self.assertTrue("projection" in m3)
        self.assertTrue("screen" in m3)
        # compare for equality
        self.assertTrue(m2 == m3)
        self.assertFalse(m2 == m1)
        # combine using intersection &
        m4 = m2 & html.MediaDesc(["TV HD", "screen", "HandHeld"])
        # compare with string
        self.assertTrue(m4 == "tv, screen")
        # check reverse
        m4 = "handheld, tv hd, screen" & m2
        self.assertTrue("tv, screen" == m4)

    def test_commalist(self):
        cl = html.CommaList.from_str("abc,def,,ghi")
        self.assertTrue(len(cl) == 4)
        self.assertTrue("abc" in cl)
        self.assertTrue("def" in cl)
        self.assertTrue(str(cl) == "abc,def,,ghi", str(cl))
        # construct from iterable of strings
        cl1 = html.CommaList(["Location", "Date"])
        self.assertTrue(len(cl1) == 2)
        self.assertTrue(str(cl1) == "Location,Date")
        # equality with instance
        cl2 = html.CommaList(["Location", "Date"])
        self.assertTrue(cl1 == cl2)
        # equality with string
        self.assertTrue(cl1 == "Location,Date")
        self.assertTrue("Location,Date" == cl2)
        # equality with list of strings
        self.assertTrue(cl1 == ["Location", "Date"])
        self.assertTrue(["Location", "Date"] == cl2)
        # indexing
        self.assertTrue(cl1[0] == "Location")
        self.assertTrue(cl1[1] == "Date")
        try:
            cl1[2]
            self.fail("Index out of range")
        except IndexError:
            pass
        # check iteration
        self.assertTrue(list(x for x in cl1) == ["Location", "Date"])

    def test_contenttypes(self):
        ctypes = html.ContentTypes.from_str(
            'text/html, application/xml; charset="utf-8",image/png')
        self.assertTrue(len(ctypes) == 3)
        self.assertTrue(MediaType('text', 'html') in ctypes)
        self.assertFalse(MediaType('application', 'xml') in ctypes)
        self.assertTrue(
            str(ctypes) ==
            'text/html,application/xml; charset=utf-8,image/png',
            str(ctypes))
        # construct from iterable of MediaTypes
        ctypes1 = html.ContentTypes([MediaType('text', 'plain'),
                                     MediaType('application', 'xml')])
        self.assertTrue(len(ctypes1) == 2)
        self.assertTrue(str(ctypes1) == "text/plain,application/xml")
        # equality with instance
        ctypes2 = html.ContentTypes([MediaType('text', 'plain'),
                                     MediaType('application', 'xml')])
        self.assertTrue(ctypes1 == ctypes2)
        # equality with string
        self.assertTrue(ctypes1 == "text/plain,application/xml")
        self.assertTrue("text/plain,application/xml" == ctypes2)
        # equality with list of instances
        self.assertTrue(ctypes1 == [MediaType("text", "plain"),
                                    MediaType("application", "xml")])
        self.assertTrue([MediaType("text", "plain"),
                         MediaType("application", "xml")] == ctypes2)
        # indexing
        self.assertTrue(isinstance(ctypes1[0], MediaType))
        self.assertTrue(ctypes1[0] == MediaType("text", "plain"))
        self.assertTrue(isinstance(ctypes1[1], MediaType))
        self.assertTrue(ctypes1[1] == MediaType("application", "xml"))
        try:
            ctypes1[2]
            self.fail("Index out of range")
        except IndexError:
            pass
        # check iteration
        for x in ctypes1:
            self.assertTrue(isinstance(x, MediaType))
        self.assertTrue(
            list(x for x in ctypes1) ==
            [MediaType("text", "plain"), MediaType("application", "xml")])

    def test_coords_rect(self):
        sample_rect = (2, 3, 8, 4)
        result1 = """..........
..........
..........
..*#####..
........+.
.........."""
        result2 = """....................
....................
....................
....................
....................
....................
....................
....................
....................
....*###########....
....############....
....############....
................+...
....................
....................
....................
....................
...................."""
        c = html.Coords(html.Length(l, html.Length.PIXEL) for l in sample_rect)
        result = []
        for y in range3(6):
            s = []
            for x in range3(10):
                v = False
                for i in range3(len(sample_rect) // 2):
                    if x == sample_rect[2 * i] and y == sample_rect[2 * i + 1]:
                        v = True
                        break
                if c.test_rect(x, y, 300, 300):
                    s.append('*' if v else '#')
                else:
                    s.append('+' if v else '.')
            result.append(''.join(s))
        result = '\n'.join(result)
        self.assertTrue(result == result1, "Bad Rect test:\n%s" % result)
        c = html.Coords(
            html.Length(l, html.Length.PERCENTAGE) for l in sample_rect)
        result = []
        for y in range3(18):
            s = []
            for x in range3(20):
                v = False
                for i in range3(len(sample_rect) // 2):
                    if x == 2 * sample_rect[2 * i] and \
                            y == 3 * sample_rect[2 * i + 1]:
                        v = True
                        break
                if c.test_rect(x, y, 200, 300):
                    s.append('*' if v else '#')
                else:
                    s.append('+' if v else '.')
            result.append(''.join(s))
        result = '\n'.join(result)
        self.assertTrue(result == result2, "Bad Rect test:\n%s" % result)

    def test_coords_circle(self):
        sample_circle = (4, 5, 3)
        result1 = """..........
..........
....#.....
..#####...
..#####...
.###*###..
..#####...
..#####...
....#.....
.........."""
        result2 = """....................
....................
....................
....................
....................
....................
....................
....................
....................
........#...........
.....#######........
....#########.......
...###########......
...###########......
...###########......
..######*######.....
...###########......
...###########......
...###########......
....#########.......
.....#######........
........#...........
....................
....................
....................
....................
....................
....................
....................
...................."""
        c = html.Coords(
            html.Length(l, html.Length.PIXEL) for l in sample_circle)
        result = []
        for y in range3(10):
            s = []
            for x in range3(10):
                v = False
                if x == sample_circle[0] and y == sample_circle[1]:
                    v = True
                if c.test_circle(x, y, 300, 300):
                    s.append('*' if v else '#')
                else:
                    s.append('+' if v else '.')
            result.append(''.join(s))
        result = '\n'.join(result)
        self.assertTrue(result == result1, "Bad Circle test:\n%s" % result)
        c = html.Coords(
            html.Length(l, html.Length.PERCENTAGE) for l in sample_circle)
        result = []
        for y in range3(30):
            s = []
            for x in range3(20):
                v = False
                if x == 2 * sample_circle[0] and y == 3 * sample_circle[1]:
                    v = True
                if c.test_circle(x, y, 200, 300):
                    s.append('*' if v else '#')
                else:
                    s.append('+' if v else '.')
            result.append(''.join(s))
        result = '\n'.join(result)
        self.assertTrue(result == result2, "Bad Circle test:\n%s" % result)

    def test_coords_poly(self):
        sample_poly = (3, 1, 1, 3, 2, 6, 3, 4, 5, 3, 6, 6, 4, 7, 7, 8, 9,
                       7, 8, 5, 11, 6, 13, 6, 14, 3, 12, 1, 12, 3, 10, 1,
                       7, 2, 3, 1)
        result1 = """................
...+......+.+...
..#####*###.#...
.*###*######*#+.
..#+..########..
..#...##*#####..
..+...*##..+.+..
....*####+......
.......+........
................"""
        result2 = """................................
................................
................................
......+.............+...+.......
......###.........###...#.......
.....#######....######..##......
....##########*#######..##......
....###################.###.....
...#########################....
..*#######*#############*###+...
...######..#################....
...#####...#################....
...###+....#################....
...###.....#################....
....##......###############.....
....#.......####*##########.....
....#.......#####.#########.....
....#.......#####...#######.....
....+.......*####.....+...+.....
...........#######..............
..........########..............
........*#########+.............
..........#######...............
............####................
..............+.................
................................
................................"""
        c = html.Coords(
            html.Length(l, html.Length.PIXEL) for l in sample_poly)
        result = []
        for y in range3(10):
            s = []
            for x in range3(16):
                v = False
                for i in range3(len(sample_poly) // 2):
                    if x == sample_poly[2 * i] and y == sample_poly[2 * i + 1]:
                        v = True
                        break
                if c.test_poly(x, y, 300, 300):
                    s.append('*' if v else '#')
                else:
                    s.append('+' if v else '.')
            result.append(''.join(s))
        result = '\n'.join(result)
        self.assertTrue(result == result1, "Bad Poly test:\n%s" % result)
        c = html.Coords(
            html.Length(l, html.Length.PERCENTAGE) for l in sample_poly)
        result = []
        for y in range3(27):
            s = []
            for x in range3(32):
                v = False
                for i in range3(len(sample_poly) // 2):
                    if x == 2 * sample_poly[2 * i] and \
                            y == 3 * sample_poly[2 * i + 1]:
                        v = True
                        break
                if c.test_poly(x, y, 200, 300):
                    s.append('*' if v else '#')
                else:
                    s.append('+' if v else '.')
            result.append(''.join(s))
        result = '\n'.join(result)
        self.assertTrue(result == result2, "Bad Poly test:\n%s" % result)


class ElementTests(unittest.TestCase):

    def load_example(self, example):
        doc = html.XHTMLDocument()
        with xml.XMLEntity(example) as e:
            doc.read(e)
        return doc

    def check_unmapped(self, element, alist, **kws):
        for aname in alist:
            self.assertFalse(hasattr(element, aname))
            try:
                avalue = element.get_attribute(aname)
                self.assertTrue(aname in kws,
                                "Unexpected attribute: %s" % aname)
                self.assertTrue(avalue == kws[aname],
                                "Unmapped %s = %s" % (aname, avalue))
            except KeyError:
                self.assertFalse(aname in kws)

    def check_bodycolors(self, element, **kws):
        self.check_unmapped(element, ['bgcolor', 'text', 'link', 'vlink',
                                      'alink'], **kws)

    def check_core_attrs(self, element, **kws):
        self.assertTrue(element.id == kws.get('id', None))
        self.assertTrue(element.style_class == kws.get('style_class', None))
        self.assertTrue(element.style == kws.get('style', None))
        self.assertTrue(element.title == kws.get('title', None))
        if 'id' in kws:
            # check this is registered with the document (if any)
            doc = element.get_document()
            if doc:
                self.assertTrue(doc.get_element_by_id(kws['id']) is element)

    def check_events(self, element, **kws):
        # don't map these attributes
        events = ["ondblclick", "onmousedown", "onmouseup", "onmouseover",
                  "onmousemove", "onmouseout", "onkeypress", "onkeydown",
                  "onkeyup"]
        self.check_unmapped(element, events, **kws)

    def check_i18n(self, element, **kws):
        self.assertTrue(element.lang == kws.get('lang', None))
        self.assertTrue(element.dir == kws.get('dir', None))
        if 'lang' in kws:
            # check get_lang
            self.assertTrue(element.get_lang() == kws['lang'])

    def check_reserved(self, element, **kws):
        reserved = ["datasrc", "datafld", "dataformatas"]
        self.check_unmapped(element, reserved, **kws)

    def check_attrs(self, element, **kws):
        self.check_core_attrs(element, **kws)
        self.check_i18n(element, **kws)
        self.check_events(element, **kws)

    def check_cellalign(self, element, **kws):
        self.assertTrue(element.align == kws.get('align', None))
        self.assertTrue(element.char == kws.get('char', None))
        self.assertTrue(element.charoff == kws.get('charoff', None))
        self.assertTrue(element.valign == kws.get('valign', None))

    def check_tablecell(self, element, **kws):
        self.check_attrs(element, **kws)
        self.assertTrue(element.abbr == kws.get('abbr', None))
        self.assertTrue(element.axis == kws.get('axis', None))
        self.assertTrue(element.headers == kws.get('headers', None))
        self.assertTrue(element.scope == kws.get('scope', None))
        self.assertTrue(element.rowspan == kws.get('rowspan', None))
        self.assertTrue(element.colspan == kws.get('colspan', None))
        self.check_cellalign(element, **kws)
        self.check_unmapped(element, ['nowrap', 'bgcolor', 'width', 'height'],
                            **kws)

    def test_a(self):
        e = html.A(None)
        self.assertTrue(isinstance(e, html.SpecialMixin))
        self.assertTrue(isinstance(e, html.InlineContainer))
        self.check_attrs(e)
        self.assertTrue(e.charset is None)
        self.assertTrue(e.type is None)
        self.assertTrue(e.name is None)
        self.assertTrue(e.href is None)
        self.assertTrue(e.hreflang is None)
        self.assertTrue(e.rel is None)
        self.assertTrue(e.rev is None)
        self.assertTrue(e.accesskey is None)
        # default to None - imply rect in cases where used for maps
        self.assertTrue(e.shape is None)
        self.assertTrue(e.coords is None)
        self.assertTrue(e.tabindex is None)
        self.check_unmapped(e, ['onfocus', 'onblur'])
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
    <p>For more information about Pyslet, please consult the
    <A lang="en-US" dir="ltr" id="home" class="A B"
        style="font-size: medium;" title="Home Page"
        onclick="alert('Hi');" href="http://www.pyslet.org/"
        name="homelink" charset="utf-8" type="text/html"
        hreflang="en-GB" rel="next" rev="prev" accesskey="H"
        tabindex="3" onfocus="alert('Click me!');">Pyslet Web site</A>.
    <MAP name="map1">
       <P>Navigate the site:
       <A href="guide.html" shape="rect" coords="0,0,118,28">Access Guide</a>,
       <A href="shortcut.html" shape="rect" coords="118,0,184,28">Go</A>,
       <A href="search.html" shape="circle" coords="184,200,60">Search</A>,
       <A href="top10.html" shape="poly"
           coords="276,0,276,28,100,200,50,50,276,0">Top Ten</A>
     </MAP></p>
</body>
</html>""")
        alist = list(doc.root.find_children_depth_first(html.A))
        self.assertTrue(len(alist) == 5)
        e = alist[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="home",
            style_class=["A", "B"], style="font-size: medium;",
            title="Home Page", onclick="alert('Hi');")
        self.assertTrue(e.charset == "utf-8")
        self.assertTrue(isinstance(e.type, MediaType))
        self.assertTrue(e.type == "text/html")
        self.assertTrue(e.name == "homelink")
        self.assertTrue(isinstance(e.href, uri.URI))
        self.assertTrue(e.href == "http://www.pyslet.org/")
        self.assertTrue(e.hreflang == "en-GB")
        self.assertTrue(e.rel == ["next"])
        self.assertTrue(e.rev == ["prev"])
        self.assertTrue(e.accesskey == "H")
        self.assertTrue(e.shape is None)
        self.assertTrue(e.coords is None)
        self.assertTrue(e.tabindex == 3)
        self.check_unmapped(e, ['onfocus', 'onblur'],
                            onfocus="alert('Click me!');")
        self.assertTrue(e.get_value() == "Pyslet Web site")
        e = alist[1]
        self.assertTrue(e.shape == html.Shape.rect)
        self.assertTrue(isinstance(e.coords, html.Coords))
        self.assertTrue(e.coords == [0, 0, 118, 28])
        e = alist[4]
        self.assertTrue(e.shape == html.Shape.poly)
        self.assertTrue(len(e.coords) == 10)

    def test_address(self):
        e = html.Address(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.BlockMixin))
        self.assertTrue(isinstance(e, html.FlowMixin))
        # and it can contain any inline + <p>
        self.assertTrue(isinstance(e, html.InlineContainer))
        self.check_attrs(e)
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
    <address lang="en-US" dir="ltr" id="home_address" class="A B"
    style="font-size: medium;" title="Home Address" onclick="alert('Hi');">
    23 High Street<br />
    <b>Capital City</b><br />
    <p>ELBONIA</p></address>
</body>
</html>""")
        e = list(doc.root.Body.find_children_depth_first(html.Address))[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="home_address",
            style_class=["A", "B"], style="font-size: medium;",
            title="Home Address", onclick="alert('Hi');")

    def test_area(self):
        e = html.Area(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.check_attrs(e)
        self.assertTrue(e.shape == html.Shape.rect)
        self.assertTrue(e.coords is None)
        self.assertTrue(e.href is None)
        self.assertTrue(e.target is None)
        self.assertTrue(e.nohref is None)
        self.assertTrue(e.alt == "")
        self.assertTrue(e.tabindex is None)
        self.assertTrue(e.accesskey is None)
        self.check_unmapped(e, ['onfocus', 'onblur'])
        doc = self.load_example("""<html>
<head><title>Area Test</title></head>
<body>
<p><map name="WhereAmI">
    <p>Do you know the way to the...</p>
    <area lang="en-US" dir="ltr" id="area51" class="A B"
        style="font-size: medium;" title="Area Test"
        onclick="alert('You are here!');"
        shape="rect" coords="0,0,118,28" href="guide.html" target="_blank"
        alt="Access Guide" tabindex="1" accesskey="H"
        onfocus="alert('Are you there?');">
    <area nohref alt="Search" shape="rect"
        coords="184,0,276,28">
    <area href="shortcut.html" alt="Go" shape="circle" coords="184,200,60">
    <area href="top10.html" alt="Top Ten" shape="poly"
        coords="276,0,276,28,100,200,50,50,276,0">
<map></p>
</body>
</html>""")
        alist = list(doc.root.find_children_depth_first(html.Area))
        self.assertTrue(len(alist) == 4)
        e = alist[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id='area51',
            style_class=["A", "B"], style="font-size: medium;",
            title="Area Test")
        self.assertTrue(e.shape == html.Shape.rect)
        self.assertTrue(isinstance(e.coords, html.Coords))
        self.assertTrue(e.coords == [0, 0, 118, 28])
        self.assertTrue(isinstance(e.href, uri.URI))
        self.assertTrue(e.href == "guide.html")
        self.assertTrue(e.target == "_blank")
        self.assertTrue(e.nohref is None)
        self.assertTrue(e.alt == "Access Guide")
        self.assertTrue(e.tabindex == 1)
        self.assertTrue(e.accesskey == "H")
        self.check_unmapped(
            e, ['onfocu', 'onblur'], onfocus="alert('Are you there?');")
        e = alist[1]
        self.assertTrue(e.nohref)
        e = alist[2]
        self.assertTrue(e.shape == html.Shape.circle)
        e = alist[3]
        self.assertTrue(e.shape == html.Shape.poly)
        self.assertTrue(len(e.coords) == 10)

    def test_base(self):
        # create an orphan
        e = html.Base(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.HeadContentMixin))
        # check default attributes
        self.assertTrue(e.href is None)
        doc = self.load_example("""<html>
    <head>
        <title>Hi</title>
        <base href="http://www.example.com/index.html"/>
    </head>
</html>""")
        e = doc.root.Head.Base
        self.assertTrue(isinstance(e, html.Base))
        # check href
        self.assertTrue(isinstance(e.href, uri.URI))
        url = uri.URI.from_octets("http://www.example.com/index.html")
        self.assertTrue(e.href == url)
        # treat this as equivalent to xml:base on root element
        self.assertTrue(doc.root.get_base() == url)

    def test_basefont(self):
        e = html.BaseFont(None)
        self.assertTrue(isinstance(e, html.PreExclusionMixin))
        self.assertTrue(isinstance(e, html.SpecialMixin))
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(e.id is None)
        self.assertTrue(e.size == "")
        self.assertTrue(e.color is None)
        self.assertTrue(e.face is None)
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<p><basefont id="font1" size="10" color="#FF0000"
    face="Chicago, Helvetica"></p>
</body></html>""")
        e = list(doc.root.find_children_depth_first(html.BaseFont))[0]
        self.assertTrue(e.id == "font1")
        # check this is registered with the document (if any)
        self.assertTrue(doc.get_element_by_id('font1') is e)
        self.assertTrue(e.size == "10")
        self.assertTrue(isinstance(e.color, html.Color))
        self.assertTrue(e.color == html.RED)
        self.assertTrue(isinstance(e.face, html.CommaList))
        self.assertTrue(e.face == ['Chicago', ' Helvetica'])

    def test_bdo(self):
        e = html.BDO(self)
        self.assertTrue(isinstance(e, html.InlineContainer))
        self.assertTrue(isinstance(e, html.SpecialMixin))
        self.check_core_attrs(e)
        self.assertTrue(e.lang is None)
        self.assertTrue(e.dir == html.Direction.ltr)
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<p><bdo lang="en-US" dir="rtl" id="odb" class="A B"
    style="font-size: medium;" title="BDO Test">!dlroW olleH</bdo></p>
</body></html>""")
        e = list(doc.root.find_children_depth_first(html.BDO))[0]
        self.check_core_attrs(
            e, id="odb", style_class=["A", "B"],
            style="font-size: medium;", title="BDO Test")
        self.assertTrue(e.lang == "en-US")
        self.assertTrue(e.dir == html.Direction.rtl)
        self.assertTrue(e.get_value() == "!dlroW olleH")

    def test_blockquote(self):
        e = html.Blockquote(None)
        self.assertTrue(isinstance(e, html.BlockContainer))
        self.assertTrue(isinstance(e, html.BlockMixin))
        self.check_attrs(e)
        self.assertTrue(e.cite is None)
        doc = self.load_example("""<html>
<head><title>Blockquote Test</title></head>
<body>
<blockquote lang="en-US" dir="ltr" id="q1"
    class="A B" style="font-size: medium;" title="Blockquote Test"
    onclick="alert('That is the question');"
    cite="https://en.wikipedia.org/wiki/To_be,_or_not_to_be">
    To be, or not to be</blockquote>
<blockquote>
    <script>alert("Unwrapped');</script>
    <p>Hello</p>
</blockquote>
</body>
</html>""")
        elist = list(doc.root.find_children_depth_first(html.Blockquote))
        e = elist[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="q1",
            style_class=["A", "B"], style="font-size: medium;",
            title="Blockquote Test", onclick="alert('That is the question');")
        self.assertTrue(isinstance(e.cite, uri.URI))
        self.assertTrue(
            e.cite == "https://en.wikipedia.org/wiki/To_be,_or_not_to_be")
        clist = list(e.get_children())
        self.assertTrue(len(clist) == 1)
        self.assertTrue(isinstance(clist[0], html.Div))
        self.assertTrue(clist[0].get_value().strip() == "To be, or not to be")
        e = elist[1]
        clist = list(e.get_children())
        self.assertTrue(len(clist) == 2)
        self.assertTrue(isinstance(clist[0], html.Script))
        self.assertTrue(clist[1].get_value() == "Hello")

    def test_body(self):
        # create an orphan
        e = html.Body(None)
        self.assertTrue(isinstance(e, html.Body))
        # check default attributes
        self.check_attrs(e)
        self.check_unmapped(e, ['onload', 'onunload'])
        self.assertTrue(e.background is None)
        self.check_bodycolors(e)
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body lang="en-US" dir="ltr" id="body1" class="A B"
    style="font-size: medium;" title="Test Object" onclick="alert('Hi');"
    onload="alert('Hello');" background="http://www.example.com/bg.png"
    bgcolor="#FFFFFF" text="Black" link="Navy" vlink="Blue" alink="Red">
</body>
</html>""")
        e = doc.root.Body
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="body1",
            style_class=["A", "B"], style="font-size: medium;",
            title="Test Object", onclick="alert('Hi');")
        self.check_unmapped(e, ['onload', 'onunload'],
                            onload="alert('Hello');")
        self.assertTrue(isinstance(e.background, uri.URI))
        self.assertTrue(e.background == "http://www.example.com/bg.png")
        self.check_bodycolors(
            e, bgcolor=html.Color((255, 255, 255)), text=html.BLACK,
            link=html.NAVY, vlink=html.BLUE, alink=html.RED)
        # check missing stag
        doc = self.load_example("""<html>
<head><title>Hello</title></head>
<p>My Document</p>
</body></html>""")
        e = doc.root.Body
        self.assertTrue(isinstance(e, html.Body))
        self.assertTrue(
            sum(1 for i in e.find_children_depth_first(html.P)) == 1)
        # check missing etag
        doc = self.load_example("""<html>
<head><title>Hello</title></head>
<body><p>My Document</p></html>""")
        e = doc.root.Body
        self.assertTrue(isinstance(e, html.Body))
        self.assertTrue(
            sum(1 for i in e.find_children_depth_first(html.P)) == 1)

    def test_br(self):
        e = html.Br(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.SpecialMixin))
        self.check_core_attrs(e)
        self.check_unmapped(e, ['clear'])
        doc = self.load_example("""<html>
<head><title>BR Test</title></head>
<body>
    <p>Hello<BR id="br1" class="A B" style="font-size: medium;"
        title="BR Test" clear="all">
    World<BR />
    <br/>
    </p>
</body></html>""")
        p = list(doc.root.Body.find_children_depth_first(html.P))[0]
        br_list = list(p.find_children_depth_first(html.Br, max_depth=1))
        self.assertTrue(len(br_list) == 3)
        e = br_list[0]
        self.check_core_attrs(
            e, id="br1", style_class=["A", "B"], style="font-size: medium;",
            title="BR Test")
        self.check_unmapped(e, ['clear'], clear="all")

    def test_button(self):
        e = html.Button(None)
        self.assertTrue(isinstance(e, html.FlowContainer))
        self.assertTrue(isinstance(e, html.FormCtrlMixin))
        self.check_attrs(e)
        self.assertTrue(e.name is None)
        self.assertTrue(e.value is None)
        self.assertTrue(e.type == html.ButtonType.submit)
        self.assertTrue(e.disabled is None)
        self.assertTrue(e.tabindex is None)
        self.assertTrue(e.accesskey is None)
        self.check_unmapped(e, ['onfocus', 'onblur'])
        self.check_reserved(e)
        doc = self.load_example("""<html>
<head><title>Button Test</title></head>
<body>
<FORM action="http://somesite.com/prog/adduser" method="post">
    <P>
    First name: <INPUT type="text" name="firstname"><BR>
    Last name: <INPUT type="text" name="lastname"><BR>
    email: <INPUT type="text" name="email"><BR>
    <INPUT type="radio" name="sex" value="Male"> Male<BR>
    <INPUT type="radio" name="sex" value="Female"> Female<BR>
    <BUTTON lang="en-US" dir="ltr" id="but1" class="A B"
        style="font-size: medium;" title="Button Test"
        onclick="alert('Hi');" name="submit" value="submit" type="submit"
        disabled tabindex="1" accesskey="S" onfocus="alert('Go on!');">
    Send<IMG src="/icons/wow.gif" alt="wow"></BUTTON>
    <BUTTON name="reset" type="reset">
    Reset<IMG src="/icons/oops.gif" alt="oops"></BUTTON>
    </P>
</FORM>
</body></html>""")
        blist = list(doc.root.find_children_depth_first(html.Button))
        self.assertTrue(len(blist) == 2)
        e = blist[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="but1",
            style_class=["A", "B"], style="font-size: medium;",
            title="Button Test", onclick="alert('Hi');")
        self.assertTrue(e.name == "submit")
        self.assertTrue(e.value == "submit")
        self.assertTrue(e.type == html.ButtonType.submit)
        self.assertTrue(e.disabled)
        self.assertTrue(e.tabindex == 1)
        self.assertTrue(e.accesskey == "S")
        self.check_unmapped(
            e, ['onfocus', 'onblur'], onfocus="alert('Go on!');")
        self.check_reserved(e)
        self.assertTrue(e.get_value(ignore_elements=True).strip() == "Send")
        try:
            doc = self.load_example("""<html>
<head><title>Button Test</title></head>
<body>
<P><BUTTON name="submit" value="submit" type="submit">
    <div>Hello <a href="wrong.htm">World</a></div></BUTTON>
</P>
</body></html>""")
            self.fail("a in button")
        except html.XHTMLValidityError:
            pass
        try:
            doc = self.load_example("""<html>
<head><title>Button Test</title></head>
<body>
<P><BUTTON name="submit" value="submit" type="submit">
    <div>Hello <input type="text"/></div></BUTTON>
</P>
</body></html>""")
            self.fail("form control in button")
        except html.XHTMLValidityError:
            pass
        try:
            doc = self.load_example("""<html>
<head><title>Button Test</title></head>
<body>
<P><BUTTON name="submit" value="submit" type="submit">
    <div><FORM action="http://somesite.com/prog/adduser" method="post"></div>
</BUTTON>
</P>
</body></html>""")
            self.fail("form in button")
        except html.XHTMLValidityError:
            pass
        try:
            doc = self.load_example("""<html>
<head><title>Button Test</title></head>
<body>
<P><BUTTON name="submit" value="submit" type="submit">
    <div><isindex></div>
    </BUTTON></P>
</body></html>""")
            self.fail("iframe in button")
        except html.XHTMLValidityError:
            pass
        try:
            doc = self.load_example("""<html>
<head><title>Button Test</title></head>
<body>
<P><BUTTON name="submit" value="submit" type="submit">
    <div><FIELDSET>
        <LEGEND>Submission</LEGEND>
    </FIELDSET></div>
    </BUTTON></P>
</body></html>""")
            self.fail("fieldset in button")
        except html.XHTMLValidityError:
            pass
        try:
            doc = self.load_example("""<html>
<head><title>Button Test</title></head>
<body>
<P><BUTTON name="submit" value="submit" type="submit">
    <div><iframe src="http://www.example.com/iframe.html">
        Wot no frames?</iframe></div>
    </BUTTON></P>
</body></html>""")
            self.fail("iframe in button")
        except html.XHTMLValidityError:
            pass

    def test_caption(self):
        e = html.Caption(None)
        self.assertTrue(isinstance(e, html.InlineContainer))
        self.check_attrs(e)
        self.check_unmapped(e, ['align'])
        doc = self.load_example("""<html>
<head><title>Caption Test</title></head>
<body>
<table><caption lang="en-US" dir="ltr" id="cap1"
    class="A B" style="font-size: medium;" title="Caption Test"
    onclick="alert('Hi');" align="bottom">This is a table</caption>
    <tr><th>Heading</th></tr>
</table>
</body></html>""")
        table = list(doc.root.find_children_depth_first(html.Table))[0]
        e = list(doc.root.find_children_depth_first(html.Caption))[0]
        self.assertTrue(table.Caption is e)
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="cap1",
            style_class=["A", "B"], style="font-size: medium;",
            title="Caption Test", onclick="alert('Hi');")
        self.check_unmapped(e, ['align'], align="bottom")
        self.assertTrue(e.get_value() == "This is a table")

    def test_center(self):
        e = html.Center(None)
        self.assertTrue(isinstance(e, html.FlowContainer))
        self.assertTrue(isinstance(e, html.BlockMixin))
        self.check_attrs(e)
        doc = self.load_example("""<html>
<head><title>Center Test</title></head>
<body>
<center lang="en-US" dir="ltr" id="cen1" class="A B" style="font-size: medium;"
    title="Center Test" onclick="alert('Hi');">Hello <p>world!</p></center>
</body>
</html>""")
        elist = list(doc.root.find_children_depth_first(html.Center))
        e = elist[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="cen1",
            style_class=["A", "B"], style="font-size: medium;",
            title="Center Test", onclick="alert('Hi');")
        self.assertTrue(e.get_value(ignore_elements=True) == "Hello ")
        elist = list(e.get_children())
        self.assertTrue(len(elist) == 2)
        self.assertTrue(elist[1].get_value() == "world!")

    def test_col(self):
        e = html.Col(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.TableColMixin))
        self.check_attrs(e)
        self.assertTrue(e.span == 1)
        self.assertTrue(e.width is None)
        self.check_cellalign(e)
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<table>
    <col lang="en-US" dir="ltr" id="c1" class="A B"
        style="font-size: medium;" title="Col Test"
        onclick="alert('Hi');" span=2 width="2*" align="char" char="."
        charoff="10%" valign="top">
</table>
</body></html>""")
        table = list(doc.root.find_children_depth_first(html.Table))[0]
        self.assertTrue(len(table.TableColMixin) == 1)
        e = table.TableColMixin[0]
        self.check_attrs(e, lang="en-US", dir=html.Direction.ltr, id="c1",
                         style_class=["A", "B"], style="font-size: medium;",
                         title="Col Test", onclick="alert('Hi');")
        self.assertTrue(e.span == 2)
        self.assertTrue(isinstance(e.width, html.MultiLength))
        self.assertTrue(e.width == "2*")
        self.check_cellalign(
            e, align=html.HAlign.char, char='.',
            charoff=html.Length(10, html.Length.Percentage),
            valign=html.VAlign.top)

    def test_colgroup(self):
        e = html.ColGroup(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.TableColMixin))
        self.check_attrs(e)
        self.assertTrue(e.span == 1)
        self.assertTrue(e.width is None)
        self.check_cellalign(e)
        self.assertTrue(isinstance(e.Col, list))
        self.assertTrue(len(e.Col) == 0)
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<table>
    <colgroup lang="en-US" dir="ltr" id="cg1" class="A B"
        style="font-size: medium;" title="ColGroup Test"
        onclick="alert('Hi');" span=2 width="2*" align="char" char="."
        charoff="10%" valign="top">
        <col title="col1">
        <col title="col2">
    <colgroup span="1">
</table>
</body></html>""")
        table = list(doc.root.find_children_depth_first(html.Table))[0]
        self.assertTrue(len(table.TableColMixin) == 2)
        e = table.TableColMixin[0]
        self.check_attrs(e, lang="en-US", dir=html.Direction.ltr, id="cg1",
                         style_class=["A", "B"], style="font-size: medium;",
                         title="ColGroup Test", onclick="alert('Hi');")
        self.assertTrue(e.span == 2)
        self.assertTrue(isinstance(e.width, html.MultiLength))
        self.assertTrue(e.width == "2*")
        self.check_cellalign(
            e, align=html.HAlign.char, char='.',
            charoff=html.Length(10, html.Length.Percentage),
            valign=html.VAlign.top)
        self.assertTrue(sum(1 for c in e.get_children()) == 2)
        self.assertTrue(isinstance(table.TableColMixin[1], html.ColGroup))

    def test_dd(self):
        e = html.DD(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.FlowContainer))
        self.check_attrs(e)
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<dl>
    <dd lang="en-US" dir="ltr" id="def1" class="A B"
        style="font-size: medium;" title="DD Test"
        onclick="alert('Hi');">Def1
    <dd>Def2</dd>
    <p>Block implies DD.</p></dl>
</body></html>""")
        elist = list(doc.root.find_children_depth_first(html.DD))
        e = elist[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="def1",
            style_class=["A", "B"], style="font-size: medium;",
            title="DD Test", onclick="alert('Hi');")
        self.assertTrue(e.get_value().strip() == "Def1")
        self.assertTrue(len(elist) == 3)
        e = elist[1]
        self.assertTrue(e.get_value().strip() == "Def2")
        e = elist[2]
        clist = list(e.get_children())
        self.assertTrue(len(clist) == 1)
        self.assertTrue(isinstance(clist[0], html.P))
        self.assertTrue(clist[0].get_value() == "Block implies DD.")

    def test_div(self):
        e = html.Div(None)
        self.assertTrue(isinstance(e, html.BlockMixin))
        self.assertTrue(isinstance(e, html.FlowContainer))
        self.check_attrs(e)
        self.check_unmapped(e, ["align"])
        self.check_reserved(e)
        doc = self.load_example("""<html>
<head><title>Div Test</title></head>
<body>
<div lang="en-US" dir="ltr" id="div1" class="A B" style="font-size: medium;"
    title="Div Test" onclick="alert('Hi');" align="justify"
    >Hello <p>world!</p></div>
</body>
</html>""")
        div_list = list(doc.root.find_children_depth_first(html.Div))
        e = div_list[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="div1",
            style_class=["A", "B"], style="font-size: medium;",
            title="Div Test", onclick="alert('Hi');")
        self.check_unmapped(e, ["align"], align="justify")
        self.assertTrue(e.get_value(ignore_elements=True) == "Hello ")
        elist = list(e.get_children())
        self.assertTrue(len(elist) == 2)
        self.assertTrue(elist[1].get_value() == "world!")

    def test_dl(self):
        e = html.DL(None)
        self.assertTrue(isinstance(e, html.BlockMixin))
        self.check_attrs(e)
        self.check_unmapped(e, ['compact'])
        doc = self.load_example("""<html>
<head><title>DL Test</title></head>
<body>
    <dl lang="en-US" dir="ltr" id="dl1" class="A B"
    style="font-size: medium;" title="Test DL" onclick="alert('Hi');"
    compact="compact">
        <dt>Item 1</dt>
        <dd>Definition 1</dd>
        <dt>Item 2</dt>
        <!-- implicit term -->
        Term 3
        <!-- implicit definition -->
        <p>Definition 3</p>
    </dl>
</body>
</html>""")
        e = list(doc.root.Body.find_children_depth_first(html.DL))[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="dl1",
            style_class=["A", "B"], style="font-size: medium;",
            title="Test DL", onclick="alert('Hi');")
        self.check_unmapped(e, ['compact'], compact="compact")
        self.assertTrue(
            sum(1 for dt in e.find_children_depth_first(html.DT)) == 3)
        ddlist = list(e.find_children_depth_first(html.DD))
        self.assertTrue(len(ddlist) == 2)
        self.assertTrue(ddlist[0].get_value() == "Definition 1")
        self.assertTrue(
            list(ddlist[1].get_children())[0].get_value().strip() ==
            "Definition 3")

    def test_dt(self):
        e = html.DT(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.InlineContainer))
        self.check_attrs(e)
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<dl>
    <dt lang="en-US" dir="ltr" id="term1" class="A B"
        style="font-size: medium;" title="DT Test"
        onclick="alert('Hi');">term1
    <dt>term2
    <p>Block implies DD.</p>
</dl>
</body></html>""")
        elist = list(doc.root.find_children_depth_first(html.DT))
        e = elist[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="term1",
            style_class=["A", "B"], style="font-size: medium;",
            title="DT Test", onclick="alert('Hi');")
        self.assertTrue(e.get_value().strip() == "term1")
        e = elist[1]
        self.assertTrue(e.get_value().strip() == "term2")

    def test_fieldset(self):
        e = html.FieldSet(None)
        self.assertTrue(isinstance(e, html.BlockMixin))
        self.assertTrue(isinstance(e, html.FlowContainer))
        self.check_attrs(e)
        self.assertTrue(isinstance(e.Legend, html.Legend))
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<FORM action="handler.py" method="post">
 <P>
 <FIELDSET lang="en-US" dir="ltr" id="fs1" class="A B"
    style="font-size: medium;" title="FieldSet Test"
    onclick="alert('Hi');">
  Last Name: <INPUT name="personal_lastname" type="text" tabindex="1">
  First Name: <INPUT name="personal_firstname" type="text" tabindex="2">
  Address: <INPUT name="personal_address" type="text" tabindex="3">
  <LEGEND>Personal Information</LEGEND>
 </FIELDSET>
</FORM>
</body></html>
""")
        e = list(doc.root.find_children_depth_first(html.FieldSet))[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="fs1",
            style_class=["A", "B"], style="font-size: medium;",
            title="FieldSet Test", onclick="alert('Hi');")
        elist = list(e.get_children())
        self.assertTrue(isinstance(e.Legend, html.Legend))
        self.assertTrue(elist[0] is e.Legend)
        self.assertTrue(elist[0].get_value() == "Personal Information")
        self.assertTrue(sum(1 for i in e.find_children_depth_first(
                            html.Input, max_depth=1)) == 3)

    def test_font(self):
        e = html.Font(None)
        self.assertTrue(isinstance(e, html.SpecialMixin))
        self.assertTrue(isinstance(e, html.InlineContainer))
        self.check_core_attrs(e)
        self.check_i18n(e)
        self.assertTrue(e.size is None)
        self.assertTrue(e.color is None)
        self.assertTrue(e.face is None)
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<p><font lang="en-US" dir="ltr" id="font1" class="A B"
    style="font-size: medium;" title="Font Test" size="10"
    color="#FF0000" face="Chicago, Helvetica">Hello World!</font></p>
</body></html>""")
        e = list(doc.root.find_children_depth_first(html.Font))[0]
        self.check_core_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="font1",
            style_class=["A", "B"], style="font-size: medium;",
            title="Font Test")
        self.assertTrue(e.size == "10")
        self.assertTrue(isinstance(e.color, html.Color))
        self.assertTrue(e.color == html.RED)
        self.assertTrue(isinstance(e.face, html.CommaList))
        self.assertTrue(e.face == ['Chicago', ' Helvetica'])
        self.assertTrue(e.get_value() == "Hello World!")

    def test_fontstyle(self):
        fontstyles = {
            "tt": html.TT,
            "i": html.I,
            "b":  html.B,
            "u": html.U,
            "s": html.S,
            "strike": html.Strike,
            "big": html.Big,
            "small": html.Small}
        for ename, eclass in dict_items(fontstyles):
            e = eclass(None)
            self.assertTrue(isinstance(e, html.FontStyle))
            if ename in ('big', 'small'):
                self.assertTrue(isinstance(e, html.PreExclusionMixin))
            self.check_attrs(e)
            doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<p><%s lang="en-US" dir="ltr" id="fs1" class="A B"
    style="font-size: medium;" title="FontStyle Test"
    onclick="alert('Hi');">Hello World!</%s></p>
</body></html>""" % (ename, ename))
            e = list(doc.root.find_children_depth_first(eclass))[0]
            self.check_attrs(
                e, lang="en-US", dir=html.Direction.ltr, id="fs1",
                style_class=["A", "B"], style="font-size: medium;",
                title="FontStyle Test", onclick="alert('Hi');")
            self.assertTrue(e.get_value() == "Hello World!")

    def test_form(self):
        e = html.Form(None)
        self.assertTrue(isinstance(e, html.BlockContainer))
        self.assertTrue(isinstance(e, html.BlockMixin))
        self.check_attrs(e)
        self.assertTrue(isinstance(e.action, uri.URI))
        self.assertTrue(e.action == "")
        self.assertTrue(e.method == html.Method.GET)
        self.assertTrue(isinstance(e.enctype, MediaType))
        self.assertTrue(e.enctype == "application/x-www-form-urlencoded")
        self.assertTrue(e.accept is None)
        self.assertTrue(e.name is None)
        self.assertTrue(e.target is None)
        self.assertTrue(e.accept_charset is None)
        self.check_unmapped(e, ['onsubmit', 'onreset'])
        doc = self.load_example("""<html>
<head><title>Form Test</title></head>
<body>
    <form lang="en-US" dir="ltr" id="form1" class="A B"
        style="font-size: medium;" title="Form Test"
        onclick="alert('Hi');" action="action.py" method="post"
        enctype="multipart/form-data" accept="text/html, text/xml"
        name="FormOne" target="_blank" accept-charset="utf-8 iso-8859-1"
        onsubmit="alert('Submitting...');"
        ><script>alert('OK?');</script><input type="submit"/></form>
</body></html>""")
        e = list(doc.root.find_children_depth_first(html.Form))[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="form1",
            style_class=["A", "B"], style="font-size: medium;",
            title="Form Test", onclick="alert('Hi');")
        self.assertTrue(isinstance(e.action, uri.URI))
        self.assertTrue(e.action == "action.py")
        self.assertTrue(e.method == html.Method.POST)
        self.assertTrue(isinstance(e.enctype, MediaType))
        self.assertTrue(e.enctype == "multipart/form-data")
        self.assertTrue(isinstance(e.accept, html.ContentTypes))
        self.assertTrue(e.accept == ["text/html", "text/xml"])
        self.assertTrue(e.name == "FormOne")
        self.assertTrue(e.target == "_blank")
        self.assertTrue(isinstance(e.accept_charset, list))
        self.assertTrue(e.accept_charset == ['utf-8', 'iso-8859-1'])
        self.check_unmapped(e, ['onsubmit', 'onreset'],
                            onsubmit="alert('Submitting...');")
        # check that input is wrapped to adhere to block|script
        elist = list(e.get_children())
        self.assertTrue(len(elist) == 2)
        e = elist[0]
        self.assertTrue(isinstance(e, html.Script))
        e = elist[1]
        self.assertTrue(isinstance(e, html.Div))
        self.assertTrue(isinstance(list(e.get_children())[0], html.Input))
        # now check the form exclusion
        try:
            doc = self.load_example("""<html>
<head><title>Form Test</title></head>
<body>
    <form action="action.py" method="post">
        <p>This is the first form: <input type="submit" /></p>
        <div><form action="nested.py" method="get">
            <p>This is the second form: <input type="submit" /></p>
        </div>
    </form>
</body></html>""")
            self.fail("Form in Form")
        except html.XHTMLValidityError:
            pass

    def test_frame(self):
        e = html.Frame(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.FrameElement))
        self.check_core_attrs(e)
        self.assertTrue(e.longdesc is None)
        self.assertTrue(e.name is None)
        self.assertTrue(e.src is None)
        self.assertTrue(e.noresize is None)
        self.assertTrue(e.scrolling == html.Scrolling.auto)
        self.check_unmapped(e, ['frameborder', 'marginwidth', 'marginheight'])
        doc = self.load_example("""<!DOCTYPE HTML PUBLIC
    "-//W3C//DTD HTML 4.01 Frameset//EN"
    "http://www.w3.org/TR/html4/frameset.dtd">
<html>
<head><title>Frame Test</title></head>
<frameset">
    <frame id="frame1" class="A B" style="font-size: medium;"
        title="Frame Test" name="frame"
        src="http://www.example.com/frame.html"
        longdesc="http://www.example.com/content.html"
        name="Frame1" NORESIZE scrolling="yes"
        frameborder="1" marginwidth="5" marginheight="5">
    <frame>
    <noframes>Sorry no frames</noframes>
</frameset>
</html>""")
        e = list(doc.root.find_children_depth_first(html.Frame))[0]
        self.check_core_attrs(e, id="frame1", style_class=["A", "B"],
                              style="font-size: medium;", title="Frame Test")
        self.assertTrue(isinstance(e.longdesc, uri.URI))
        self.assertTrue(e.longdesc == "http://www.example.com/content.html")
        self.assertTrue(e.name == "Frame1")
        self.assertTrue(isinstance(e.src, uri.URI))
        self.assertTrue(e.src == "http://www.example.com/frame.html")
        self.assertTrue(e.noresize)
        self.assertTrue(e.scrolling == html.Scrolling.yes)
        self.check_unmapped(
            e, ['frameborder', 'marginwidth', 'marginheight'],
            frameborder="1", marginwidth="5", marginheight="5")

    def test_frameset(self):
        e = html.Frameset(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.FrameElement))
        self.check_core_attrs(e)
        self.assertTrue(e.rows is None)
        self.assertTrue(e.cols is None)
        self.check_unmapped(e, ['onload', 'onunload'])
        self.assertTrue(len(e.FrameElement) == 0)
        self.assertTrue(e.NoFramesFrameset is None)
        doc = self.load_example("""<!DOCTYPE HTML PUBLIC
    "-//W3C//DTD HTML 4.01 Frameset//EN"
    "http://www.w3.org/TR/html4/frameset.dtd">
<html>
<head><title>Frameset Test</title></head>
<frameset id="fs1" class="A B" style="font-size: medium;"
    title="Frameset Test" rows="10, 20% ,30*" cols="50,50%,50*"
    onload="alert('Hello Frames!');">
    <frameset id="fs2">
        <frame id="f1">
        <frame id="f2">
    </frameset>
    <frame id="f3">
    <noframes>Sorry no frames</noframes>
</frameset>
</html>""")
        e = doc.root.Frameset
        self.assertTrue(isinstance(e, html.Frameset))
        self.check_core_attrs(
            e, id="fs1", style_class=["A", "B"], style="font-size: medium;",
            title="Frameset Test")
        self.assertTrue(isinstance(e.rows, html.MultiLengths))
        self.assertTrue(len(e.rows) == 3)
        self.assertTrue(e.rows[0] == "10")
        self.assertTrue(e.rows[1] == "20%")
        self.assertTrue(e.rows[2] == "30*")
        self.assertTrue(isinstance(e.cols, html.MultiLengths))
        self.assertTrue(len(e.cols) == 3)
        self.assertTrue(e.cols[0] == "50")
        self.assertTrue(e.cols[1] == "50%")
        self.assertTrue(e.cols[2] == "50*")
        self.check_unmapped(e, ['onload', 'onunload'],
                            onload="alert('Hello Frames!');")
        # check children
        self.assertTrue(len(e.FrameElement) == 2)
        fs2 = e.FrameElement[0]
        self.assertTrue(isinstance(fs2, html.FrameElement))
        self.assertTrue(len(fs2.FrameElement) == 2)
        f3 = e.FrameElement[1]
        self.assertTrue(isinstance(f3, html.Frame))
        self.assertTrue(isinstance(e.NoFramesFrameset, html.NoFramesFrameset))

    def test_head(self):
        # create an orphan
        e = html.Head(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        # check default attributes
        self.check_i18n(e)
        self.assertTrue(e.profile is None)
        doc = self.load_example("""<html>
<head lang="en-US" dir="ltr" profile="http://www.example.com/profile"><head>
</html>""")
        e = doc.root.Head
        self.assertTrue(isinstance(e, html.Head))
        self.check_i18n(e, lang="en-US", dir=html.Direction.ltr)
        # check profile
        self.assertTrue(isinstance(e.profile, uri.URI))
        self.assertTrue(e.profile ==
                        uri.URI.from_octets("http://www.example.com/profile"))
        # check missing stag
        doc = self.load_example("""<head><title>Hello</title></head></html>""")
        e = doc.root.Head
        self.assertTrue(isinstance(e, html.Head))
        # check missing etag
        doc = self.load_example("""<html><head><title>Hello</title></html>""")
        e = doc.root.Head
        self.assertTrue(isinstance(e, html.Head))

    def test_heading(self):
        headings = {
            "h1": html.H1,
            "h2": html.H2,
            "h3":  html.H3,
            "h4": html.H4,
            "h5": html.H5,
            "h6": html.H6}
        for ename, eclass in dict_items(headings):
            e = eclass(None)
            self.assertTrue(isinstance(e, html.InlineContainer))
            self.assertTrue(isinstance(e, html.Heading))
            self.assertTrue(isinstance(e, html.BlockMixin))
            self.check_attrs(e)
            doc = self.load_example("""<html>
<head><title>Test</title></head>
<body><%s lang="en-US" dir="ltr" id="h1" class="A B"
    style="font-size: medium;" title="Heading Test"
    onclick="alert('Hi');">Hello World!</%s></body></html>""" %
                                    (ename, ename))
            e = list(doc.root.Body.get_children())[0]
            self.assertTrue(isinstance(e, eclass))
            self.check_attrs(
                e, lang="en-US", dir=html.Direction.ltr, id="h1",
                style_class=["A", "B"], style="font-size: medium;",
                title="Heading Test", onclick="alert('Hi');")
            self.assertTrue(e.get_value() == "Hello World!")

    def test_hr(self):
        e = html.HR(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.BlockMixin))
        self.check_attrs(e)
        self.check_unmapped(e, ['align', 'noshade', 'size', 'width'])
        doc = self.load_example("""<html>
<head><title>HR Test</title></head>
<body>
    <hr lang="en-US" dir="ltr" id="hr1" class="A B"
        style="font-size: medium;" title="HR Test"
        onclick="alert('Hi');" align="left" noshade size="10" width="80%">
    <hr id="hr2" />
    <p>Para ends in rule
    <HR>
    <HR/>
</body></html>""")
        hr_list = list(
            doc.root.Body.find_children_depth_first(html.HR, max_depth=1))
        self.assertTrue(len(hr_list) == 4)
        e = hr_list[0]
        self.check_attrs(e, lang="en-US", dir=html.Direction.ltr, id="hr1",
                         style_class=["A", "B"], style="font-size: medium;",
                         title="HR Test", onclick="alert('Hi');")
        self.check_unmapped(
            e, ['align', 'noshade', 'size', 'width'], align="left",
            noshade="noshade", size="10", width="80%")

    def test_html(self):
        # create an orphan
        e = html.HTML(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        # check default attributes
        self.check_i18n(e)
        doc = self.load_example("""<html lang="en-US" dir="ltr"></html>""")
        e = doc.root
        self.assertTrue(isinstance(e, html.HTML))
        self.check_i18n(e, lang="en-US", dir=html.Direction.ltr)
        # check missing stag
        doc = self.load_example("""<head><title>Hello</title></head></html>""")
        e = doc.root
        self.assertTrue(isinstance(e, html.HTML))
        # check missing etag
        doc = self.load_example("""<html><head><title>Hello</title></head>""")
        e = doc.root
        self.assertTrue(isinstance(e, html.HTML))

    def test_html_frameset(self):
        e = html.HTMLFrameset(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.check_i18n(e)
        doc = self.load_example("""<!DOCTYPE HTML PUBLIC
    "-//W3C//DTD HTML 4.01 Frameset//EN"
    "http://www.w3.org/TR/html4/frameset.dtd">
<html lang="en-US" dir="ltr"></html>""")
        e = doc.root
        self.assertTrue(isinstance(e, html.HTMLFrameset))
        self.check_i18n(e, lang="en-US", dir=html.Direction.ltr)
        # check missing stag
        doc = self.load_example("""<!DOCTYPE HTML PUBLIC
    "-//W3C//DTD HTML 4.01 Frameset//EN"
    "http://www.w3.org/TR/html4/frameset.dtd">
<head><title>Hello</title></head></html>""")
        e = doc.root
        self.assertTrue(isinstance(e, html.HTMLFrameset))
        # check missing etag
        doc = self.load_example("""<!DOCTYPE HTML PUBLIC
    "-//W3C//DTD HTML 4.01 Frameset//EN"
    "http://www.w3.org/TR/html4/frameset.dtd">
<html><head><title>Hello</title></head>""")
        e = doc.root
        self.assertTrue(isinstance(e, html.HTMLFrameset))
        # special Body handling, Frameset is required...
        try:
            doc = self.load_example("""<!DOCTYPE HTML PUBLIC
    "-//W3C//DTD HTML 4.01 Frameset//EN"
    "http://www.w3.org/TR/html4/frameset.dtd">
<head><title>Hello</title></head><body><p>No frames</p></body></html>""")
            self.fail("Frameset document with no frameset")
        except html.XHTMLValidityError:
            pass

    def test_iframe(self):
        e = html.IFrame(None)
        self.assertTrue(isinstance(e, html.FlowContainer))
        self.assertTrue(isinstance(e, html.SpecialMixin))
        self.check_core_attrs(e)
        self.assertTrue(e.longdesc is None)
        self.assertTrue(e.name is None)
        self.assertTrue(e.src is None)
        self.assertTrue(e.height is None)
        self.assertTrue(e.width is None)
        self.assertTrue(e.scrolling == html.Scrolling.auto)
        self.check_unmapped(e, ['frameborder', 'marginwidth',
                                'marginheight', 'align'])
        doc = self.load_example("""<html>
<head><title>IFrame Test</title></head>
<body>
    <p><iframe id="frame1" class="A B" style="font-size: medium;"
        title="IFrame Test" name="frame"
        src="http://www.example.com/iframe.html"
        longdesc="http://www.example.com/content.html"
        name="embedded" height="80%" width="40%" scrolling="yes"
        frameborder="1" align="right" marginwidth="5" marginheight="5">
        Wot no frames?</iframe>
</body></html>""")
        e = list(doc.root.find_children_depth_first(html.IFrame))[0]
        self.check_core_attrs(e, id="frame1", style_class=["A", "B"],
                              style="font-size: medium;", title="IFrame Test")
        self.assertTrue(isinstance(e.longdesc, uri.URI))
        self.assertTrue(e.longdesc == "http://www.example.com/content.html")
        self.assertTrue(e.name == "embedded")
        self.assertTrue(isinstance(e.src, uri.URI))
        self.assertTrue(e.src == "http://www.example.com/iframe.html")
        self.assertTrue(e.height == html.Length(80, html.Length.Percentage))
        self.assertTrue(e.width == html.Length(40, html.Length.Percentage))
        self.assertTrue(e.scrolling == html.Scrolling.yes)
        self.check_unmapped(
            e, ['frameborder', 'marginwidth', 'marginheight', 'align'],
            frameborder="1", marginwidth="5", marginheight="5", align="right")
        self.assertTrue(e.get_value().strip() == "Wot no frames?")

    def test_img(self):
        e = html.Img(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.PreExclusionMixin))
        self.assertTrue(isinstance(e, html.SpecialMixin))
        self.check_attrs(e)
        self.assertTrue(e.src is None)  # required but no default URL
        self.assertTrue(e.alt == "")    # required, blank string
        self.assertTrue(e.longdesc is None)
        self.assertTrue(e.name is None)
        self.assertTrue(e.height is None)
        self.assertTrue(e.width is None)
        self.assertTrue(e.usemap is None)
        self.assertTrue(e.ismap is None)
        self.check_unmapped(e, ['align', 'border', 'hspace', 'vspace'])
        doc = self.load_example("""<html>
<head><title>Image Test</title></head>
<body>
    <p><img lang="en-US" dir="ltr" id="img1" class="A B"
        style="font-size: medium;" title="Image Test"
        onclick="alert('Hi');" src="http://www.example.com/image.png"
        alt="Company Logo" longdesc="http://www.example.com/brand.html"
        name="logo" height="32" width="50%" usemap="#logomap" align="right"
        border="5" hspace="10" vspace="20">
    <p><a href="http://www.acme.com/cgi-bin/competition">
        <IMG src="game.gif" ismap alt="target"></a>
</body></html>""")
        img_list = list(doc.root.find_children_depth_first(html.Img))
        self.assertTrue(len(img_list) == 2)
        e = img_list[0]
        self.check_attrs(e, lang="en-US", dir=html.Direction.ltr, id="img1",
                         style_class=["A", "B"], style="font-size: medium;",
                         title="Image Test", onclick="alert('Hi');")
        self.assertTrue(isinstance(e.src, uri.URI))
        self.assertTrue(e.src == "http://www.example.com/image.png")
        self.assertTrue(e.alt == "Company Logo")
        self.assertTrue(isinstance(e.longdesc, uri.URI))
        self.assertTrue(e.longdesc == "http://www.example.com/brand.html")
        self.assertTrue(e.name == "logo")
        self.assertTrue(isinstance(e.height, html.Length))
        self.assertTrue(e.height == html.Length(32))
        self.assertTrue(isinstance(e.width, html.Length))
        self.assertTrue(e.width == html.Length(50, html.Length.Percentage))
        self.assertTrue(isinstance(e.usemap, uri.URI))
        self.assertTrue(e.usemap == "#logomap")
        self.assertTrue(e.ismap is None)
        self.check_unmapped(e, ['align', 'border', 'hspace', 'vspace'],
                            align="right", border="5", hspace="10",
                            vspace="20")
        e = img_list[1]
        self.assertTrue(e.src == "game.gif")
        self.assertTrue(e.alt == "target")
        self.assertTrue(e.ismap)

    def test_input(self):
        e = html.Input(None)
        self.assertTrue(e, html.XHTMLElement)
        self.assertTrue(e, html.FormCtrlMixin)
        self.check_attrs(e)
        self.assertTrue(e.type == html.InputType.text)
        self.assertTrue(e.name is None)
        self.assertTrue(e.value is None)
        self.assertTrue(e.checked is None)
        self.assertTrue(e.disabled is None)
        self.assertTrue(e.readonly is None)
        self.assertTrue(e.size is None)
        self.assertTrue(e.maxlength is None)
        self.assertTrue(e.src is None)
        self.assertTrue(e.alt is None)
        self.assertTrue(e.usemap is None)
        self.assertTrue(e.ismap is None)
        self.assertTrue(e.tabindex is None)
        self.assertTrue(e.accesskey is None)
        self.check_unmapped(
            e, ['onfocus', 'onblur', 'onselect', 'onchange', 'align'])
        self.assertTrue(e.accept is None)
        self.check_reserved(e)
        doc = self.load_example("""<html>
<head><title>Input Test</title></head>
<body>
    <p><input lang="en-US" dir="ltr" id="field1" class="A B"
        style="font-size: medium;" title="Input Test"
        onclick="alert('Hi');" type="password" name="secret"
        readonly="readonly" size="8" maxlength="20" alt="It's a secret!"
        tabindex="3" accesskey="P" onfocus="alert('Is anyone looking?');"
        align="right">
    <input type="checkbox" checked="checked" disabled="disabled" name="option"
        value="yes">
    <input type="image" src="http://www.example.com/pass.png">
    <input type="image" ismap="ismap" usemap="#map">
    <input type="file" accept="text/html, text/plain">
    </p>
</body></html>""")
        ilist = list(doc.root.find_children_depth_first(html.Input))
        self.assertTrue(len(ilist) == 5)
        e = ilist[0]
        self.check_attrs(e, lang="en-US", dir=html.Direction.ltr, id="field1",
                         style_class=["A", "B"], style="font-size: medium;",
                         title="Input Test", onclick="alert('Hi');")
        self.assertTrue(e.type == html.InputType.password)
        self.assertTrue(e.name == "secret")
        self.assertTrue(e.readonly)
        self.assertTrue(e.size == 8)
        self.assertTrue(e.maxlength == 20)
        self.assertTrue(e.alt == "It's a secret!")
        self.assertTrue(e.tabindex == 3)
        self.assertTrue(e.accesskey == "P")
        self.check_unmapped(
            e, ['onfocus', 'onblur', 'onselect', 'onchange', 'align'],
            onfocus="alert('Is anyone looking?');", align="right")
        self.check_reserved(e)
        e = ilist[1]
        self.assertTrue(e.type == html.InputType.checkbox)
        self.assertTrue(e.name == "option")
        self.assertTrue(e.value == "yes")
        self.assertTrue(e.checked)
        self.assertTrue(e.disabled)
        e = ilist[2]
        self.assertTrue(e.type == html.InputType.image)
        self.assertTrue(isinstance(e.src, uri.URI))
        self.assertTrue(e.src == "http://www.example.com/pass.png")
        e = ilist[3]
        self.assertTrue(e.ismap)
        self.assertTrue(isinstance(e.usemap, uri.URI))
        self.assertTrue(e.usemap == "#map")
        e = ilist[4]
        self.assertTrue(e.type == html.InputType.file)
        self.assertTrue(isinstance(e.accept, html.ContentTypes))
        self.assertTrue(e.accept == "text/html, text/plain")

    def test_insdel(self):
        for name, eclass in dict_items({'ins': html.Ins, 'del': html.Del}):
            e = eclass(None)
            self.assertTrue(isinstance(e, html.FlowContainer))
            self.check_attrs(e)
            self.assertTrue(e.cite is None)
            self.assertTrue(e.datetime is None)
            doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<%(name)s lang="en-US" dir="ltr" id="change1" class="A B"
    style="font-size: medium;" title="Ins/Del Test"
    onclick="alert('Hi');" cite="http://www.example.com/version2"
    datetime="2016-03-05T14:30:00Z"><p>Block 1</p></%(name)s>
<p><%(name)s><b>Inline 1</b></%(name)s></p>
</body></html>
""" % {'name': name})
            elist = list(doc.root.find_children_depth_first(eclass))
            self.assertTrue(len(elist) == 2)
            e = elist[0]
            self.check_attrs(
                e, lang="en-US", dir=html.Direction.ltr, id="change1",
                style_class=["A", "B"], style="font-size: medium;",
                title="Ins/Del Test", onclick="alert('Hi');")
            self.assertTrue(isinstance(e.cite, uri.URI))
            self.assertTrue(e.cite == "http://www.example.com/version2")
            self.assertTrue(isinstance(e.datetime, iso.TimePoint))
            self.assertTrue(e.datetime == "2016-03-05T14:30:00Z")
            child_list = list(e.get_children())
            self.assertTrue(isinstance(child_list[0], html.P))
            self.assertTrue(child_list[0].get_value() == "Block 1")
            child_list = list(elist[1].get_children())
            self.assertTrue(isinstance(child_list[0], html.B))
            self.assertTrue(child_list[0].get_value() == "Inline 1")
            try:
                doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<p><%(name)s><p>Block 1</p></%(name)s></p>
</body></html>
""" % {'name': name})
                # ins/del can't be a block in this context
                self.fail("ins/del block inside block")
            except html.XHTMLValidityError:
                pass
        try:
            doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<p><ins>Block 1 <del>inline</del></ins></p>
</body></html>
""")
            # del is not in the content model of ins (or vice versa)
            self.fail("del inside ins")
        except html.XHTMLValidityError:
            pass
        try:
            doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<p><del>Block 1 <ins>inline</ins></del></p>
</body></html>
""")
            self.fail("ins inside del")
        except html.XHTMLValidityError:
            pass

    def test_isindex(self):
        e = html.IsIndex(None)
        self.assertTrue(isinstance(e, html.HeadContentMixin))
        self.assertTrue(isinstance(e, html.BlockMixin))
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.check_core_attrs(e)
        self.check_i18n(e)
        self.assertTrue(e.prompt is None)
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<ISINDEX lang="en-US" dir="ltr" id="index1" class="A B"
    style="font-size: medium;" title="Index Test"
    prompt="Enter your search phrase: ">
</body></html>
""")
        e = list(doc.root.find_children_depth_first(html.IsIndex))[0]
        self.check_core_attrs(e, id="index1", style_class=["A", "B"],
                              style="font-size: medium;", title="Index Test")
        self.check_i18n(e, lang="en-US", dir=html.Direction.ltr)
        self.assertTrue(e.prompt == "Enter your search phrase: ")

    def test_label(self):
        e = html.Label(None)
        self.assertTrue(isinstance(e, html.InlineContainer))
        self.assertTrue(isinstance(e, html.FormCtrlMixin))
        self.check_attrs(e)
        self.assertTrue(e.for_field is None)
        self.assertTrue(e.accesskey is None)
        self.check_unmapped(e, ['onfocus', 'onblur'])
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<FORM action="handler.py" method="post">
    <p><LABEL lang="en-US" dir="ltr" id="lab1" class="A B"
        style="font-size: medium;" title="Label Test"
        onclick="alert('Hi');" for="fname" accesskey="F"
        onfocus="alert('Who are you?');">First Name</LABEL>:
    <INPUT type="text" name="firstname" id="fname"><BR>
    <LABEL>
        <INPUT type="text" name="lastname"> : Last Name
    </LABEL>
</FORM>
</body></html>
""")
        lablist = list(doc.root.find_children_depth_first(html.Label,
                                                          sub_match=False))
        e = lablist[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="lab1",
            style_class=["A", "B"], style="font-size: medium;",
            title="Label Test", onclick="alert('Hi');")
        self.assertTrue(e.for_field == "fname")
        self.assertTrue(e.accesskey == "F")
        self.check_unmapped(e, ['onfocus', 'onblur'],
                            onfocus="alert('Who are you?');")
        self.assertTrue(len(lablist) == 2)
        e = lablist[1]
        # contains one input element
        self.assertTrue(
            sum(1 for i in e.find_children_depth_first(html.Input)) == 1)
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<FORM action="handler.py" method="post">
    <p><INPUT type="text" name="fname"></p>
    <LABEL>
        <span><LABEL for="fname">First Name</LABEL></span>
        <INPUT type="text" name="lastname"> : Last Name
    </LABEL>
</FORM>
</body></html>
""")
        # label cannot be in label, so nested label terminates label
        lablist = list(doc.root.find_children_depth_first(html.Label,
                                                          sub_match=False))
        # we find these even without sub_match
        self.assertTrue(len(lablist) == 2)
        self.assertTrue(lablist[0].parent is lablist[1].parent)
        # label must not contain more than ONE field
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<FORM action="handler.py" method="post">
    <p><LABEL>First Name: <INPUT type="text" name="fname">
        <INPUT type="text" name="lastname"> : Last Name
    </LABEL></p>
</FORM>
</body></html>
""")
        # the second formctrl ends the label as if the etag was omitted
        e = list(doc.root.find_children_depth_first(html.Label))[0]
        # just one input in the label
        self.assertTrue(
            sum(1 for i in e.find_children_depth_first(html.Input)) == 1)
        # but two inputs in the label's parent
        self.assertTrue(
            sum(1 for i in
                e.parent.find_children_depth_first(html.Input)) == 2)

    def test_legend(self):
        e = html.Legend(None)
        self.assertTrue(isinstance(e, html.InlineContainer))
        self.check_attrs(e)
        self.assertTrue(e.accesskey is None)
        self.check_unmapped(e, ['align'])
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<FORM action="handler.py" method="post">
 <P>
 <FIELDSET>
  <LEGEND lang="en-US" dir="ltr" id="leg1" class="A B"
        style="font-size: medium;" title="Legend Test"
        onclick="alert('Hi');" accesskey="P"
        align="right"><b>Personal</b> Information</LEGEND>
  Last Name: <INPUT name="personal_lastname" type="text" tabindex="1">
  First Name: <INPUT name="personal_firstname" type="text" tabindex="2">
  Address: <INPUT name="personal_address" type="text" tabindex="3">
 </FIELDSET>
</FORM>
</body></html>
""")
        e = list(doc.root.find_children_depth_first(html.Legend))[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="leg1",
            style_class=["A", "B"], style="font-size: medium;",
            title="Legend Test", onclick="alert('Hi');")
        self.assertTrue(e.accesskey == "P")
        self.check_unmapped(e, ['align'], align="right")
        elist = list(e.get_children())
        self.assertTrue(len(elist) == 2)
        self.assertTrue(isinstance(elist[0], html.B))
        self.assertTrue(elist[0].get_value() == "Personal")
        self.assertTrue(elist[1] == " Information")

    def test_li(self):
        e = html.LI(None)
        self.assertTrue(isinstance(e, html.FlowContainer))
        self.check_attrs(e)
        self.check_unmapped(e, ['type', 'value'])
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<ol>
    <!-- check omitted end tag -->
    <li lang="en-US" dir="ltr" id="listitem1" class="A B"
        style="font-size: medium;" title="LI Test"
        onclick="alert('Hi');" type="square" value="2">Item 2</li>
    <li>Item 3
    <li>Item 4
</ol>
</body></html>
""")
        # check backwards compatible synomym
        items = list(doc.root.find_children_depth_first(html.LI))
        e = items[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="listitem1",
            style_class=["A", "B"], style="font-size: medium;",
            title="LI Test", onclick="alert('Hi');")
        self.check_unmapped(e, ['type', 'value'], type="square", value="2")
        self.assertTrue(len(items) == 3)
        self.assertTrue(items[1].get_value().strip() == "Item 3")

    def test_link(self):
        # create an orphan
        e = html.Link(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.HeadMiscMixin))
        # check default attributes
        self.check_attrs(e)
        self.assertTrue(e.charset is None)
        self.assertTrue(e.href is None)
        self.assertTrue(e.hreflang is None)
        self.assertTrue(e.type is None)
        self.assertTrue(e.rel is None)
        self.assertTrue(e.rev is None)
        self.assertTrue(e.media is None)
        doc = self.load_example("""<html>
<head><title>Test</title>
<link lang="en-US" dir="ltr" id="link1" class="A B"
    style="font-size: medium;" title="Test Link" onclick="alert('Hi');"
    charset="utf-8" href="http://www.example.com/link" hreflang="en-GB"
    type="text/html" rel="alternate" rev="Section contents"
    media="screen, tv"/>
</head>
</html>""")
        e = list(doc.root.find_children_depth_first(html.Link))[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="link1",
            style_class=["A", "B"], style="font-size: medium;",
            title="Test Link", onclick="alert('Hi');")
        self.assertTrue(e.charset == "utf-8")
        self.assertTrue(isinstance(e.href, uri.URI))
        self.assertTrue(e.href == "http://www.example.com/link")
        self.assertTrue(e.hreflang == "en-GB")
        self.assertTrue(isinstance(e.type, MediaType))
        self.assertTrue(e.type == "text/html")
        self.assertTrue(e.rel == ["alternate"])
        self.assertTrue(e.rev == ["section", "contents"])
        self.assertTrue(isinstance(e.media, html.MediaDesc))
        self.assertTrue(e.media == "tv, screen")

    def test_map(self):
        e = html.Map(None)
        # it's a special type of block container that also allows <area>
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.SpecialMixin))
        self.check_attrs(e)
        # name is required
        self.assertTrue(e.name == "")
        doc = self.load_example("""<html>
<head><title>Map Test</title></head>
<body>
<p><map lang="en-US" dir="ltr" id="map1"
    class="A B" style="font-size: medium;" title="Map Test"
    onclick="alert('Do you know the way to the...');"
    name="WhereAmI">
    <p>You are here!</p>
    <area href="guide.html" alt="Access Guide" shape="rect"
        coords="0,0,118,28">
    <area href="search.html" alt="Search" shape="rect"
        coords="184,0,276,28">
    <area href="shortcut.html" alt="Go" shape="circle" coords="184,200,60">
    <area href="top10.html" alt="Top Ten" shape="poly"
        coords="276,0,276,28,100,200,50,50,276,0">
<map></p>
</body>
</html>""")
        e = list(doc.root.find_children_depth_first(html.Map))[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="map1",
            style_class=["A", "B"], style="font-size: medium;",
            title="Map Test",
            onclick="alert('Do you know the way to the...');")
        self.assertTrue(e.name == "WhereAmI")
        # as a block container my map can contain <p>, which is weird
        # for an inline element but hey...
        p = list(e.find_children_depth_first(html.P))[0]
        self.assertTrue(p.get_value().strip() == "You are here!")
        areas = list(e.find_children_depth_first(html.Area))
        self.assertTrue(len(areas) == 4)

    def test_meta(self):
        # create an orphan
        e = html.Meta(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.HeadMiscMixin))
        # check default attributes
        self.check_i18n(e)
        self.assertTrue(e.http_equiv is None)
        self.assertTrue(e.name is None)
        # required, so should be an empty string
        self.assertTrue(e.content == "")
        self.assertTrue(e.scheme is None)
        doc = self.load_example("""<html>
<head><title>Test</title>
<meta lang="en-US" dir="ltr" http-equiv="Metadata" name="test-info"
    content="blah blah" scheme="Gobbledygook"/>
</head>
</html>""")
        e = list(doc.root.find_children_depth_first(html.Meta))[0]
        self.check_i18n(e, lang="en-US", dir=html.Direction.ltr)
        self.assertTrue(e.http_equiv == "Metadata")
        self.assertTrue(e.name == "test-info")
        self.assertTrue(e.content == "blah blah")
        self.assertTrue(e.scheme == "Gobbledygook")

    def test_noframes(self):
        e = html.NoFrames(None)
        # doesn't feature in the strict DTD
        # loose DTD: flow container
        self.assertTrue(isinstance(e, html.FlowContainer))
        self.assertTrue(isinstance(e, html.BlockMixin))
        self.check_attrs(e)
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<noframes lang="en-US" dir="ltr" id="nf1" class="A B"
    style="font-size: medium;" title="NoFrames Test"
    onclick="alert('Hi');"><p>Block</p> and flow.
</noframes>
</body></html>
""")
        e = list(doc.root.find_children_depth_first(html.NoFrames))[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="nf1",
            style_class=["A", "B"], style="font-size: medium;",
            title="NoFrames Test", onclick="alert('Hi');")
        elist = list(e.get_children())
        self.assertTrue(isinstance(elist[0], html.P))
        self.assertTrue(is_text(elist[1]))
        self.assertTrue(elist[1].strip() == "and flow.")

    def test_noframes_frameset(self):
        e = html.NoFramesFrameset(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e.Body, html.Body))
        self.check_attrs(e)
        doc = self.load_example("""<!DOCTYPE HTML PUBLIC
    "-//W3C//DTD HTML 4.01 Frameset//EN"
    "http://www.w3.org/TR/html4/frameset.dtd">
<html>
<head><title>Test</title></head>
<frameset>
    <noframes lang="en-US" dir="ltr" id="nf1" class="A B"
    style="font-size: medium;" title="NoFrames Test"
    onclick="alert('Hi');"><p>Block</p> and flow.
    </noframes>
    <frame />
    <frameset>
        <frame />
        <noframes><p>Nested frame</p></noframes>
    </frameset>
</frameset></html>
""")
        nflist = list(
            doc.root.find_children_depth_first(html.NoFramesFrameset))
        self.assertTrue(len(nflist) == 2)
        # noframes always output after frames
        e = nflist[1]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="nf1",
            style_class=["A", "B"], style="font-size: medium;",
            title="NoFrames Test", onclick="alert('Hi');")
        # mus only have one child, the Body
        elist = list(e.get_children())
        self.assertTrue(len(elist) == 1)
        # implicit body
        self.assertTrue(elist[0] is e.Body)
        elist = list(e.Body.get_children())
        self.assertTrue(isinstance(elist[0], html.P))
        # implicit div inside body
        self.assertTrue(isinstance(elist[1], html.Div))
        self.assertTrue(elist[1].get_value().strip() == "and flow.")
        # check the nested frame.
        self.assertTrue(len(nflist) == 2)
        e = nflist[0]
        # implicit div inside body
        elist = list(e.Body.get_children())
        self.assertTrue(isinstance(elist[0], html.P))
        self.assertTrue(elist[0].get_value().strip() == "Nested frame")
        # check noframes exclusion
        try:
            doc = self.load_example("""<!DOCTYPE HTML PUBLIC
    "-//W3C//DTD HTML 4.01 Frameset//EN"
    "http://www.w3.org/TR/html4/frameset.dtd">
<html>
<head><title>Test</title></head>
<frameset>
    <frame />
    <noframes>
        <body>
            <p>NOFRAMES allowed in BODY?</p>
            <noframes>Yes, but not in FRAMESET</noframes>
        </body>
    </noframes>
</frameset></html>
""")
            self.fail("No NOFRAMES allowed in NOFRAMES")
        except html.XHTMLValidityError:
            pass

    def test_noscript(self):
        e = html.NoScript(None)
        # go with the stricter DTD
        self.assertTrue(isinstance(e, html.BlockContainer))
        self.assertTrue(isinstance(e, html.BlockMixin))
        self.check_attrs(e)
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<noscript lang="en-US" dir="ltr" id="ns1" class="A B"
    style="font-size: medium;" title="NoScript Test"
    onclick="alert('Hi');">
    <p>Block</p> and flow.
</noscript>
</body></html>
""")
        # check enforced strict rules with implicit div
        e = list(doc.root.find_children_depth_first(html.NoScript))[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="ns1",
            style_class=["A", "B"], style="font-size: medium;",
            title="NoScript Test", onclick="alert('Hi');")
        elist = list(e.get_children())
        self.assertTrue(isinstance(elist[0], html.P))
        self.assertTrue(isinstance(elist[1], html.Div))
        self.assertTrue(elist[1].get_value().strip() == "and flow.")
        # use of link inside body is not allowed and appears in header!
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<noscript>
    <p>Block1</p>
    <link href="http://www.example.com/help" rel="help" />
    <p>Block2</p>
</noscript>
</body></html>
""")
        # link will be moved to <head>
        self.assertTrue(
            len(list(doc.root.Head.find_children_depth_first(html.Link))) == 1)
        # and it will terminate noscript early
        elist = list(doc.root.Body.get_children())
        self.assertTrue(
            len(elist) == 2 and isinstance(elist[0], html.NoScript) and
            isinstance(elist[1], html.P))
        ns = elist[0]
        p = elist[1]
        elist = list(ns.get_children())
        self.assertTrue(len(elist) == 1 and isinstance(elist[0], html.P))
        self.assertTrue(elist[0].get_value() == "Block1")
        self.assertTrue(p.get_value() == "Block2")
        # link OK in head
        doc = self.load_example("""<html>
<head><title>Test</title>
<noscript>
    <link href="http://www.example.com/help" rel="help" />
    Flow
</noscript>
</head>
</html>
""")
        e = list(doc.root.find_children_depth_first(html.NoScript))[0]
        elist = list(e.get_children())
        self.assertTrue(len(elist) == 1)
        self.assertTrue(isinstance(elist[0], html.Link))
        # where did block go?  implicit end of noscript and head
        elist = list(doc.root.Body.get_children())
        self.assertTrue(len(elist) == 1)
        self.assertTrue(isinstance(elist[0], html.Div))
        elist = list(elist[0].get_children())
        self.assertTrue(len(elist) == 1)
        self.assertTrue(is_text(elist[0]))
        self.assertTrue(elist[0].strip() == "Flow")

    def test_object(self):
        # create an orphan
        e = html.Object(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.HeadMiscMixin))
        # check default attributes
        self.check_core_attrs(e)
        self.check_i18n(e)
        self.check_events(e)
        self.assertTrue(e.declare is None)
        self.assertTrue(e.classid is None)
        self.assertTrue(e.codebase is None)
        self.assertTrue(e.data is None)
        self.assertTrue(e.type is None)
        self.assertTrue(e.codetype is None)
        self.assertTrue(e.archive is None)
        self.assertTrue(e.standby is None)
        self.assertTrue(e.height is None)
        self.assertTrue(e.width is None)
        self.assertTrue(e.usemap is None)
        self.assertTrue(e.name is None)
        self.assertTrue(e.tabindex is None)
        self.check_reserved(e)
        doc = self.load_example("""<html>
    <head>
        <title>Hi</title>
        <object lang="en-US" dir="ltr" id="object_1" class="A B"
            style="font-size: medium;" title="Test Object"
            onclick="alert('Hi');" declare="declare"
            classid="http://www.example.com/classid"
            codebase="http://www.example.com/codebase"
            data="http://www.example.com/data"
            type="text/plain" codetype="application/xml"
            archive="http://www.example.com/archive1
                http://www.example.com/archive2"
            standby="Please wait..." height="100%" width="640"
            usemap="http://www.example.com/imagemap.png"
            name="test" tabindex="3"
            datasrc="http://www.example.com/datasrc">Sorry</object>
    </head>
</html>""")
        e = list(doc.root.find_children_depth_first(html.Object))[0]
        self.check_core_attrs(
            e, id="object_1", style_class=["A", "B"],
            style="font-size: medium;", title="Test Object")
        self.check_i18n(e, lang="en-US", dir=html.Direction.ltr)
        self.check_events(e, onclick="alert('Hi');")
        self.assertTrue(e.declare)
        self.assertTrue(isinstance(e.classid, uri.URI))
        self.assertTrue(e.classid == "http://www.example.com/classid")
        self.assertTrue(isinstance(e.codebase, uri.URI))
        self.assertTrue(e.codebase == "http://www.example.com/codebase")
        self.assertTrue(isinstance(e.data, uri.URI))
        self.assertTrue(e.data == "http://www.example.com/data")
        self.assertTrue(isinstance(e.type, MediaType))
        self.assertTrue(e.type == "text/plain")
        self.assertTrue(isinstance(e.codetype, MediaType))
        self.assertTrue(e.codetype == "application/xml")
        self.assertTrue(len(e.archive) == 2)
        self.assertTrue(isinstance(e.archive[0], uri.URI) and
                        isinstance(e.archive[1], uri.URI))
        self.assertTrue(e.archive[0] == "http://www.example.com/archive1")
        self.assertTrue(e.archive[1] == "http://www.example.com/archive2")
        self.assertTrue(e.standby == "Please wait...")
        self.assertTrue(e.height == html.Length(100, html.Length.PERCENTAGE))
        self.assertTrue(e.width == html.Length(640, html.Length.PIXEL))
        self.assertTrue(isinstance(e.usemap, uri.URI))
        self.assertTrue(e.usemap == "http://www.example.com/imagemap.png")
        self.assertTrue(e.name == "test")
        self.assertTrue(e.tabindex == 3)
        self.assertFalse(hasattr(e, 'datasrc'))
        self.assertTrue(e.get_attribute('datasrc') ==
                        "http://www.example.com/datasrc")

    def test_ol(self):
        e = html.OL(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.List))
        self.assertTrue(isinstance(e, html.BlockMixin))
        self.assertTrue(isinstance(e, html.FlowMixin))
        self.check_attrs(e)
        self.check_unmapped(e, ['type', 'compact', 'start'])
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<ol lang="en-US" dir="ltr" id="list1" class="A B"
    style="font-size: medium;" title="OL Test"
    onclick="alert('Hi');" type="square" compact="compact" start="3">
    <!-- check forced open list item -->
    item 1
    <li>Item 2</li>
</ol>
</body></html>
""")
        # check backwards compatible synomym
        e = list(doc.root.find_children_depth_first(html.OL))[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="list1",
            style_class=["A", "B"], style="font-size: medium;",
            title="OL Test", onclick="alert('Hi');")
        self.check_unmapped(e, ['type', 'compact', 'start'], type="square",
                            compact="compact", start="3")
        items = list(e.get_children())
        self.assertTrue(len(items) == 2)
        self.assertTrue(items[0].get_value().strip() == "item 1")

    def test_optgroup(self):
        e = html.OptGroup(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.OptItemMixin))
        self.check_attrs(e)
        self.assertTrue(e.disabled is None)
        self.assertTrue(e.label == "OPTGROUP")
        doc = self.load_example("""<html>
<head><title>Option Test</title></head>
<body>
<p>In which of these seasons did Reading FC compete in the Premier
League: <select name="season">
    <optgroup lang="en-US" dir="ltr" id="og1"
        class="A B" style="font-size: medium;" title="OptGroup Test"
        onclick="alert('Hi');" disabled="disabled" label="2000s">
        <option>2004-05</option>
        <option>2005-06</option>
        <option>2006-07</option>
        <option>2007-08</option>
        <option>2008-09</option>
    </optgroup>
    <optgroup>
        <option>2011-12</option>
        <option>2012-13</option>
        <option>2013-14</option>
    </optgroup></select></p>
</body>
</html>""")
        oglist = list(doc.root.find_children_depth_first(html.OptGroup))
        e = oglist[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="og1",
            style_class=["A", "B"], style="font-size: medium;",
            title="OptGroup Test", onclick="alert('Hi');")
        self.assertTrue(e.disabled)
        self.assertTrue(e.label == "2000s")
        # check content model
        self.assertTrue(sum(1 for i in e.get_children()) == 5)
        self.assertTrue(
            "|".join(opt.get_value() for opt in e.get_children()) ==
            "2004-05|2005-06|2006-07|2007-08|2008-09")
        # check bad content model
        doc = self.load_example("""<html>
<head><title>Option Test</title></head>
<body>
<p>In which of these seasons did Reading FC compete in the Premier
League: <select name="season">
    <optgroup label="all">
        <optgroup label="2000s">
            <option>2004-05</option>
            <option>2005-06</option>
            <option>2006-07</option>
            <option>2007-08</option>
            <option>2008-09</option>
        </optgroup>
        <optgroup>
            <option>2011-12</option>
            <option>2012-13</option>
            <option>2013-14</option>
        </optgroup></select></p>
    </optgroup>
</body>
</html>""")
        # optgroup not allowed in optgroup, assume missing etag
        oglist = list(doc.root.find_children_depth_first(html.OptGroup))
        self.assertTrue(len(oglist) == 3)
        self.assertTrue(sum(1 for i in oglist[0].get_children()) == 0)
        self.assertTrue(sum(1 for i in oglist[1].get_children()) == 5)
        self.assertTrue(sum(1 for i in oglist[2].get_children()) == 3)

    def test_option(self):
        e = html.Option(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.OptItemMixin))
        self.check_attrs(e)
        self.assertTrue(e.selected is None)
        self.assertTrue(e.disabled is None)
        self.assertTrue(e.label is None)
        self.assertTrue(e.value is None)
        doc = self.load_example("""<html>
<head><title>Option Test</title></head>
<body>
<p>In which of these seasons did Reading FC compete in the Premier
League: <select name="season">
    <option lang="en-US" dir="ltr" id="opt1"
        class="A B" style="font-size: medium;" title="Option Test"
        onclick="alert('Hi');" selected="selected" disabled="disabled"
        label="04-05" value="05">2004-05</option>
    <option>2005-06
    <option>2006-07
    <option>2007-08
    <option>2008-09</select></p>
</body>
</html>""")
        optlist = list(doc.root.find_children_depth_first(html.Option))
        e = optlist[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="opt1",
            style_class=["A", "B"], style="font-size: medium;",
            title="Option Test", onclick="alert('Hi');")
        self.assertTrue(e.selected)
        self.assertTrue(e.disabled)
        self.assertTrue(e.label == "04-05")
        self.assertTrue(e.value == "05")
        # now check the missing options end tags worked
        self.assertTrue(len(optlist) == 5)
        e = optlist[1]
        self.assertTrue(e.get_value().strip() == "2005-06")

    def test_p(self):
        e = html.P(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.BlockMixin))
        self.assertTrue(isinstance(e, html.FlowMixin))
        self.check_attrs(e)
        self.check_unmapped(e, ["align"])
        doc = self.load_example("""<html>
<head><title>P Test</title></head>
<body>
<p lang="en-US" dir="ltr" id="p1" class="A B" style="font-size: medium;"
    title="P Test" onclick="alert('Hi');" align="justify">Hello World!</p>
<p>Para 2<!-- check omitted close tag -->
<p>Para 3</p>
</body>
</html>""")
        plist = list(doc.root.find_children_depth_first(html.P))
        e = plist[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="p1",
            style_class=["A", "B"], style="font-size: medium;",
            title="P Test", onclick="alert('Hi');")
        self.check_unmapped(e, ["align"], align="justify")
        self.assertTrue(e.get_value() == "Hello World!")
        self.assertTrue(len(plist) == 3)
        e = plist[1]
        self.assertTrue(e.get_value().strip() == "Para 2")

    def test_phrase(self):
        phrases = {
            "em": html.Em,
            "strong": html.Strong,
            "dfn":  html.Dfn,
            "code": html.Code,
            "samp": html.Samp,
            "kbd": html.Kbd,
            "var": html.Var,
            "cite": html.Cite,
            "abbr": html.Abbr,
            "acronym": html.Acronym}
        for ename, eclass in dict_items(phrases):
            e = eclass(None)
            self.assertTrue(isinstance(e, html.Phrase))
            self.assertTrue(isinstance(e, html.InlineMixin))
            self.assertTrue(isinstance(e, html.FlowMixin))
            self.check_attrs(e)
            doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<p><%s lang="en-US" dir="ltr" id="phrase1" class="A B"
    style="font-size: medium;" title="Phrase Test"
    onclick="alert('Hi');">Hello World!</%s></p>
</body></html>
""" % (ename, ename))
            e = list(doc.root.find_children_depth_first(eclass))[0]
            self.check_attrs(
                e, lang="en-US", dir=html.Direction.ltr, id="phrase1",
                style_class=["A", "B"], style="font-size: medium;",
                title="Phrase Test", onclick="alert('Hi');")
            self.assertTrue(e.get_value() == "Hello World!")

    def test_param(self):
        e = html.Param(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(e.id is None)
        self.assertTrue(e.name == "_")
        self.assertTrue(e.value is None)
        self.assertTrue(e.valuetype is None)
        self.assertTrue(e.type is None)
        doc = self.load_example("""<html>
<head><title>Pre Test</title></head>
<body>
<p><object>
    <param id="param1" name="arg" value="http://www.example.com/param_value"
        valuetype="REF" type="text/plain" /></object></p>
</body>
</html>""")
        e = list(doc.root.find_children_depth_first(html.Param))[0]
        self.assertTrue(e.id == "param1")
        self.assertTrue(doc.get_element_by_id("param1") is e)
        self.assertTrue(e.name == "arg")
        self.assertTrue(is_text(e.value))
        self.assertTrue(e.value == "http://www.example.com/param_value")
        self.assertTrue(e.valuetype == html.ParamValueType.ref)
        self.assertTrue(isinstance(e.type, MediaType))
        self.assertTrue(e.type == "text/plain")

    def test_pre(self):
        e = html.Pre(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.BlockMixin))
        self.assertTrue(isinstance(e, html.FlowMixin))
        self.check_attrs(e)
        self.check_unmapped(e, ["width"])
        doc = self.load_example("""<html>
<head><title>Pre Test</title></head>
<body>
<pre lang="en-US" dir="ltr" id="pre1"
    class="A B" style="font-size: medium;" title="Pre Test"
    onclick="alert('Hi');" width="80"><span> Span is OK </span></pre>
</body>
</html>""")
        e = list(doc.root.find_children_depth_first(html.Pre))[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="pre1",
            style_class=["A", "B"], style="font-size: medium;",
            title="Pre Test", onclick="alert('Hi');")
        self.check_unmapped(e, ["width"], width="80")
        self.assertTrue(e.get_value(True) == "")
        e = list(doc.root.find_children_depth_first(html.Span))[0]
        self.assertTrue(e.get_value() == " Span is OK ", e.get_value())
        # now check pretty printed output
        doc = self.load_example("""<html>
<head><title>Pretty Test</title></head>
<body>
<pre>
if e == pre:
  <span> Span is OK </span></pre>
</body>
</html>""")
        output = uempty.join(s for s in doc.root.generate_xml(tab="    "))
        self.assertTrue(output.strip() ==
                        """<html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <title>Pretty Test</title>
    </head>
    <body>
        <pre>
if e == pre:
  <span> Span is OK </span></pre>
    </body>
</html>""", output)
        # finally, check excluded elements are excluded
        doc = self.load_example("""<html>
<head><title>Exclude Test</title></head>
<body>
<pre>E=mc<sup>2</sup>
<span>E=mc<sup>2</sup></span></pre>
</body>
</html>""")
        e = list(doc.root.find_children_depth_first(html.Pre))[0]
        # there must be no sup element inside it
        self.assertTrue(
            sum(1 for i in e.find_children_depth_first(html.Sup)) == 0)

    def test_q(self):
        e = html.Q(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.SpecialMixin))
        self.assertTrue(isinstance(e, html.InlineMixin))
        self.assertTrue(isinstance(e, html.FlowMixin))
        self.check_attrs(e)
        self.assertTrue(e.cite is None)
        doc = self.load_example("""<html>
<head><title>Q Test</title></head>
<body>
<p><q lang="en-US" dir="ltr" id="q1"
    class="A B" style="font-size: medium;" title="Quote Test"
    onclick="alert('That is the question');"
    cite="https://en.wikipedia.org/wiki/To_be,_or_not_to_be">
    To be, or not to be</q></p>
</body>
</html>""")
        e = list(doc.root.find_children_depth_first(html.Q))[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="q1",
            style_class=["A", "B"], style="font-size: medium;",
            title="Quote Test", onclick="alert('That is the question');")
        self.assertTrue(isinstance(e.cite, uri.URI))
        self.assertTrue(
            e.cite == "https://en.wikipedia.org/wiki/To_be,_or_not_to_be")
        self.assertTrue(e.get_value().strip() == "To be, or not to be")

    def test_script(self):
        # create an orphan
        e = html.Script(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.HeadMiscMixin))
        self.assertTrue(isinstance(e, html.SpecialMixin))
        self.assertTrue(isinstance(e, html.InlineMixin))
        self.assertTrue(isinstance(e, html.FlowMixin))
        # check default attributes
        self.assertTrue(e.charset is None)
        self.assertTrue(isinstance(e.type, MediaType))
        self.assertTrue(e.type == "text/javascript")
        self.assertTrue(e.src is None)
        self.assertTrue(e.defer is None)
        # event and 'for' attributes are left unmapped
        self.check_unmapped(e, ['event', 'for'])
        doc = self.load_example("""<html>
<head><title>Test</title>
<script charset="utf-8" type="text/python" src="http://www.example.com/script"
    defer="defer" event="reserved" for="five" />
</head>
</html>""")
        e = list(doc.root.find_children_depth_first(html.Script))[0]
        self.assertTrue(e.charset == "utf-8")
        self.assertTrue(isinstance(e.type, MediaType))
        self.assertTrue(e.type == "text/python")
        self.assertTrue(isinstance(e.src, uri.URI))
        self.assertTrue(e.src == "http://www.example.com/script")
        self.assertTrue(e.defer)
        self.check_unmapped(e, ['event', 'for'], event="reserved",
                            **{'for': 'five'})

    def test_select(self):
        e = html.Select(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.FormCtrlMixin))
        self.assertTrue(isinstance(e, html.InlineMixin))
        self.assertTrue(isinstance(e, html.FlowMixin))
        self.check_attrs(e)
        self.assertTrue(e.name is None)
        self.assertTrue(e.size is None)
        self.assertTrue(e.multiple is None)
        self.assertTrue(e.disabled is None)
        self.assertTrue(e.tabindex is None)
        self.check_unmapped(e, ["onfocus", "onblur", "onchange"])
        self.check_reserved(e)
        doc = self.load_example("""<html>
<head><title>Select Test</title></head>
<body>
<p>In which of these seasons did Reading FC compete in the Premier
League: <select lang="en-US" dir="ltr" id="menu1"
    class="A B" style="font-size: medium;" title="Select Test"
    onclick="alert('Hi');" name="season" size="5" multiple="multiple"
    disabled="disabled" tabindex="3" onchange="alert('Sure?');">
    <option>2004-05</option>
    <option>2005-06</option>
    <option>2006-07</option>
    <option>2007-08</option>
    <option>2008-09</option>
    <optgroup label="McDermott">
        <option>2011-12</option>
        <option>2012-13</option>
        <option>2013-14</option>
    </optgroup></select></p>
</body>
</html>""")
        e = list(doc.root.find_children_depth_first(html.Select))[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="menu1",
            style_class=["A", "B"], style="font-size: medium;",
            title="Select Test", onclick="alert('Hi');")
        self.assertTrue(e.name == "season")
        self.assertTrue(e.size == 5)
        self.assertTrue(e.multiple)
        self.assertTrue(e.disabled)
        self.assertTrue(e.tabindex == 3)
        self.check_unmapped(e, ["onfocus", "onblur", "onchange"],
                            onchange="alert('Sure?');")
        self.check_reserved(e)
        self.assertTrue(sum(1 for i in e.get_children()) == 6)
        self.assertTrue(isinstance(list(e.get_children())[5], html.OptGroup))
        self.assertTrue(
            sum(1 for i in e.find_children_depth_first(html.Option)) == 8)
        # check that bad elements terminate the model (even though
        # omittag is not supported.
        try:
            doc = self.load_example("""<html>
<head><title>Select Test</title></head>
<body>
<p>In which of these seasons did Reading FC compete in the Premier
League: <select name="season">
    <option>2004-05</option>
    <option>2005-06</option>
    <option>2006-07</option>
    <option>2007-08</option>
    <option>2008-09</option>
    <input type="text" name="other" />
    <option>2011-12</option>
    <option>2012-13</option>
    <option>2013-14</option>
</body>
</html>""")
            self.fail("Bad SELECT")
        except html.XHTMLValidityError:
            pass

    def test_span(self):
        e = html.Span(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.SpecialMixin))
        self.assertTrue(isinstance(e, html.InlineMixin))
        self.assertTrue(isinstance(e, html.FlowMixin))
        self.check_attrs(e)
        self.check_reserved(e)
        doc = self.load_example("""<html>
<head><title>Span Test</title></head>
<body>
<p><span lang="en-US" dir="ltr" id="span1"
    class="A B" style="font-size: medium;" title="Span Test"
    onclick="alert('Hi');">1864</span></p>
</body>
</html>""")
        e = list(doc.root.find_children_depth_first(html.Span))[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="span1",
            style_class=["A", "B"], style="font-size: medium;",
            title="Span Test", onclick="alert('Hi');")
        self.check_reserved(e)
        self.assertTrue(e.get_value() == "1864")

    def test_style(self):
        # create an orphan
        e = html.Style(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.HeadMiscMixin))
        # check default attributes
        self.check_i18n(e)
        self.assertTrue(isinstance(e.type, MediaType))
        self.assertTrue(e.type == "text/css")
        self.assertTrue(e.media is None)
        self.assertTrue(e.title is None)
        doc = self.load_example("""<html>
<head><title>Test</title>
<style lang="en-US" dir="ltr" type="text/css3" media="print"
    title="Styles for Print">H1 {border-width:
    1; border: solid; text-align: center}</style>
</head>
</html>""")
        e = list(doc.root.find_children_depth_first(html.Style))[0]
        self.check_i18n(e, lang="en-US", dir=html.Direction.ltr)
        self.assertTrue(isinstance(e.type, MediaType))
        self.assertTrue(e.type == "text/css3")
        self.assertTrue(isinstance(e.media, html.MediaDesc))
        self.assertTrue(e.media == "print")
        self.assertTrue(e.title == "Styles for Print")
        self.assertTrue(e.get_value().startswith('H1 {border-width:'))

    def test_subsup(self):
        for ename, eclass in dict_items({"sub": html.Sub, "sup": html.Sup}):
            e = eclass(None)
            self.assertTrue(isinstance(e, html.XHTMLElement))
            self.assertTrue(isinstance(e, html.SpecialMixin))
            self.assertTrue(isinstance(e, html.InlineMixin))
            self.assertTrue(isinstance(e, html.FlowMixin))
            self.assertTrue(isinstance(e, html.PreExclusionMixin))
            self.check_attrs(e)
            doc = self.load_example("""<html>
<head><title>Sub/Sup Test</title></head>
<body>
<p>There'ss nothing for a pair: <%s lang="en-US" dir="ltr" id="sscript"
    class="A B" style="font-size: medium;" title="Sub/Sup Test"
    onclick="alert('Hi');">not in this game</%s></p>
</body>
</html>
""" % (ename, ename))
            e = list(doc.root.find_children_depth_first(eclass))[0]
            self.check_attrs(
                e, lang="en-US", dir=html.Direction.ltr, id="sscript",
                style_class=["A", "B"], style="font-size: medium;",
                title="Sub/Sup Test", onclick="alert('Hi');")
            self.assertTrue(e.get_value() == "not in this game")

    def test_table(self):
        e = html.Table(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.BlockMixin))
        self.assertTrue(isinstance(e, html.FlowMixin))
        self.check_attrs(e)
        self.assertTrue(e.summary is None)
        self.assertTrue(e.width is None)
        self.assertTrue(e.border is None)
        self.assertTrue(e.frame is None)
        self.assertTrue(e.rules is None)
        self.assertTrue(e.cellspacing is None)
        self.assertTrue(e.cellpadding is None)
        self.check_reserved(e)
        self.check_unmapped(e, ['datapagesize'])
        self.assertTrue(e.Caption is None)
        self.assertTrue(isinstance(e.TableColMixin, list))
        self.assertTrue(len(e.TableColMixin) == 0)
        self.assertTrue(e.THead is None)
        self.assertTrue(e.TFoot is None)
        self.assertTrue(isinstance(e.TBody, list))
        self.assertTrue(len(e.TBody) == 0)
        doc = self.load_example("""<html>
<head><title>Table Test</title></head>
<body>
<table lang="en-US" dir="ltr" id="table1" class="A B"
    style="font-size: medium;" title="Table Test"
    onclick="alert('Hi');" summary="Quick Test"
    width="80%" border="10" frame="border" rules="all"
    cellspacing="3%" cellpadding="4" datapagesize="60">
<!-- check implicit table cell -->
CellA</table>
</body>
</html>""")
        e = list(doc.root.find_children_depth_first(html.Table))[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="table1",
            style_class=["A", "B"], style="font-size: medium;",
            title="Table Test", onclick="alert('Hi');")
        self.assertTrue(e.summary == "Quick Test")
        self.assertTrue(e.width == html.Length(80, html.Length.Percentage))
        self.assertTrue(e.border == 10)
        self.assertTrue(e.frame == html.TFrame.border)
        self.assertTrue(e.rules == html.TRules.all)
        self.assertTrue(e.cellspacing ==
                        html.Length(3, html.Length.Percentage))
        self.assertTrue(e.cellpadding == html.Length(4, html.Length.Pixel))
        self.check_reserved(e)
        self.check_unmapped(e, ['datapagesize'], datapagesize="60")
        self.assertTrue(len(e.TBody) == 1)
        td = list(e.find_children_depth_first(html.TD))[0]
        self.assertTrue(td.get_value().strip() == "CellA")

    def test_tbody(self):
        e = html.TBody(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.check_attrs(e)
        self.check_cellalign(e)
        doc = self.load_example("""<html>
<head><title>TBody Test</title></head>
<body>
<table>
<tbody lang="en-US" dir="ltr" id="tbody1" class="A B"
    style="font-size: medium;" title="TBody Test"
    onclick="alert('Hi');" align="char" char="." charoff="10%"
    valign="top">
<tr><th>Head</th><td>CellA</td></tr></tbody>
<!-- check missing stag and etag -->
<tr><th>Foot</th><td>CellB</td></tr></table>
</body>
</html>""")
        tbodylist = list(doc.root.find_children_depth_first(html.TBody))
        e = tbodylist[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="tbody1",
            style_class=["A", "B"], style="font-size: medium;",
            title="TBody Test", onclick="alert('Hi');")
        self.check_cellalign(
            e, align=html.HAlign.char, char='.',
            charoff=html.Length(10, html.Length.Percentage),
            valign=html.VAlign.top)
        # check correct containment of TR (and hence TD)
        e = list(e.find_children_depth_first(html.TD))[0]
        self.assertTrue(e.get_value().strip() == "CellA")
        # check second hidden body
        self.assertTrue(len(tbodylist) == 2)
        e = tbodylist[1]
        e = list(e.find_children_depth_first(html.TD))[0]
        self.assertTrue(e.get_value().strip() == "CellB")

    def test_td(self):
        e = html.TD(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.check_tablecell(e)
        doc = self.load_example("""<html>
<head><title lang="en-US" dir="ltr">TD Test</title></head>
<body>
<table>
<tr>
    <th id="th1">TH1</th>
    <th id="th2"></th>
    <td lang="en-US" dir="ltr" id="td1" class="A B"
        style="font-size: medium;" title="TD Test"
        onclick="alert('Hi');" align="char" char="." charoff="10%"
        valign="top" abbr="Hi" axis="Greeting,Salutation" headers="th2 th1"
        scope="col" rowspan="2" colspan="1" nowrap="nowrap" bgcolor="#FF0000"
        width="15%" height="20">Hi there</td>
    <td id="td2">Hello<!-- check missing closing tag -->
<tr><th>Head</th><td>Cell</td><td>Goodbye</td></tr>
</table>
</body>
</html>""")
        tdlist = list(doc.root.find_children_depth_first(html.TD))
        e = tdlist[0]
        self.check_tablecell(
            e, lang="en-US", dir=html.Direction.ltr, id="td1",
            style_class=["A", "B"], style="font-size: medium;",
            title="TD Test", onclick="alert('Hi');", align=html.HAlign.char,
            char=".", charoff=html.Length(10, html.Length.Percentage),
            valign=html.VAlign.top, abbr="Hi", axis=["Greeting", "Salutation"],
            headers=["th2", "th1"], scope=html.Scope.col, rowspan=2,
            colspan=1, nowrap="nowrap", bgcolor=html.RED,
            width=html.Length(15, html.Length.Percentage),
            height=html.Length(20, html.Length.Pixel))
        self.assertTrue(e.get_value().strip() == "Hi there")
        e = tdlist[1]
        self.assertTrue(e.get_value().strip() == "Hello")

    def test_textarea(self):
        e = html.TextArea(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.FormCtrlMixin))
        self.assertTrue(isinstance(e, html.InlineMixin))
        self.assertTrue(isinstance(e, html.FlowMixin))
        self.check_attrs(e)
        self.assertTrue(e.name is None)
        self.assertTrue(e.rows == 1)
        self.assertTrue(e.cols == 80)
        self.assertTrue(e.disabled is None)
        self.assertTrue(e.readonly is None)
        self.assertTrue(e.tabindex is None)
        self.assertTrue(e.accesskey is None)
        self.check_unmapped(e, ['onfocus', 'onblur', 'onselect', 'onchange'])
        self.check_reserved(e)
        doc = self.load_example("""<html>
<head><title lang="en-US" dir="ltr">TextArea Test</title></head>
<body>
    <textarea lang="en-US" dir="ltr" id="tx1" class="A B"
        style="font-size: medium;" title="TextArea Test"
        onclick="alert('Hi');" name="essay" rows="100" cols="120"
        disabled="disabled" readonly="readonly" tabindex="3"
        accesskey="T" onfocus="alert('Type something');">
        Type your essay</textarea>
</body></html>""")
        e = list(doc.root.find_children_depth_first(html.TextArea))[0]
        self.check_attrs(e, lang="en-US", dir=html.Direction.ltr, id="tx1",
                         style_class=["A", "B"], style="font-size: medium;",
                         title="TextArea Test", onclick="alert('Hi');")
        self.assertTrue(e.name == "essay")
        self.assertTrue(e.rows == 100)
        self.assertTrue(e.cols == 120)
        self.assertTrue(e.disabled)
        self.assertTrue(e.readonly)
        self.assertTrue(e.tabindex == 3)
        self.assertTrue(e.accesskey == "T")
        self.check_unmapped(e, ['onfocus', 'onblur', 'onselect', 'onchange'],
                            onfocus="alert('Type something');")
        self.check_reserved(e)
        self.assertTrue(e.get_value().strip() == "Type your essay")

    def test_tfoot(self):
        e = html.TFoot(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.check_attrs(e)
        self.check_cellalign(e)
        doc = self.load_example("""<html>
<head><title lang="en-US" dir="ltr">TR Test</title></head>
<body>
<table>
<tfoot lang="en-US" dir="ltr" id="tfoot1" class="A B"
    style="font-size: medium;" title="TFoot Test"
    onclick="alert('Hi');" align="char" char="." charoff="10%"
    valign="top">
<!-- check missing etag -->
<tr><th>Head</th><td>Cell</td></tr>
</table>
</body>
</html>""")
        e = list(doc.root.find_children_depth_first(html.TFoot))[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="tfoot1",
            style_class=["A", "B"], style="font-size: medium;",
            title="TFoot Test", onclick="alert('Hi');")
        self.check_cellalign(
            e, align=html.HAlign.char, char='.',
            charoff=html.Length(10, html.Length.Percentage),
            valign=html.VAlign.top)
        # check correct containment of TR (and hence TD)
        e = list(e.find_children_depth_first(html.TD))[0]
        self.assertTrue(e.get_value().strip() == "Cell")

    def test_th(self):
        e = html.TH(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.check_tablecell(e)
        doc = self.load_example("""<html>
<head><title lang="en-US" dir="ltr">TD Test</title></head>
<body>
<table>
<tr>
    <th id="th1">TH1</th>
    <th id="th2"></th>
    <th lang="en-US" dir="ltr" id="th3" class="A B"
        style="font-size: medium;" title="TH Test"
        onclick="alert('Hi');" align="char" char="." charoff="10%"
        valign="top" abbr="Hi" axis="Greeting,Salutation" headers="th2 th1"
        scope="col" rowspan="2" colspan="1" nowrap="nowrap" bgcolor="#FF0000"
        width="15%" height="20">Hi there</td>
    <th id="th4">Hello<!-- check missing closing tag -->
<tr><th>Head</th><td>Cell</td><td>Goodbye</td></tr>
</table>
</body>
</html>""")
        thlist = list(doc.root.find_children_depth_first(html.TH))
        e = thlist[2]
        self.check_tablecell(
            e, lang="en-US", dir=html.Direction.ltr, id="th3",
            style_class=["A", "B"], style="font-size: medium;",
            title="TH Test", onclick="alert('Hi');", align=html.HAlign.char,
            char=".", charoff=html.Length(10, html.Length.Percentage),
            valign=html.VAlign.top, abbr="Hi", axis=["Greeting", "Salutation"],
            headers=["th2", "th1"], scope=html.Scope.col, rowspan=2,
            colspan=1, nowrap="nowrap", bgcolor=html.RED,
            width=html.Length(15, html.Length.Percentage),
            height=html.Length(20, html.Length.Pixel))
        self.assertTrue(e.get_value().strip() == "Hi there")
        e = thlist[3]
        self.assertTrue(e.get_value().strip() == "Hello")

    def test_thead(self):
        e = html.THead(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.check_attrs(e)
        self.check_cellalign(e)
        doc = self.load_example("""<html>
<head><title lang="en-US" dir="ltr">TR Test</title></head>
<body>
<table>
<thead lang="en-US" dir="ltr" id="thead1" class="A B"
    style="font-size: medium;" title="THead Test"
    onclick="alert('Hi');" align="char" char="." charoff="10%"
    valign="top">
<tr><th>Head</th><td>Cell</td></tr>
<!-- check missing etag -->
</table>
</body>
</html>""")
        e = list(doc.root.find_children_depth_first(html.THead))[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="thead1",
            style_class=["A", "B"], style="font-size: medium;",
            title="THead Test", onclick="alert('Hi');")
        self.check_cellalign(
            e, align=html.HAlign.char, char='.',
            charoff=html.Length(10, html.Length.Percentage),
            valign=html.VAlign.top)
        # check correct containment of TR (and hence TD)
        e = list(e.find_children_depth_first(html.TD))[0]
        self.assertTrue(e.get_value().strip() == "Cell")

    def test_title(self):
        # create an orphan
        e = html.Title(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.HeadContentMixin))
        # check default attributes
        self.check_i18n(e)
        doc = self.load_example("""<html>
<head><title lang="en-US" dir="ltr">Hello World</title></head></html>""")
        e = doc.root.Head.Title
        self.assertTrue(isinstance(e, html.Title))
        self.check_i18n(e, lang="en-US", dir=html.Direction.ltr)
        # check content
        self.assertTrue(e.get_value() == "Hello World")

    def test_tr(self):
        e = html.TR(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.check_attrs(e)
        self.check_cellalign(e)
        self.check_unmapped(e, ['bgcolor'])
        doc = self.load_example("""<html>
<head><title lang="en-US" dir="ltr">TR Test</title></head>
<body>
<table>
<tr lang="en-US" dir="ltr" id="tr1" class="A B"
    style="font-size: medium;" title="TR Test"
    onclick="alert('Hi');" align="char" char="." charoff="10%"
    valign="middle" bgcolor="#FF0000">
    <th>Head</th><!-- check forced TD -->Cell</tr>
<tr id="tr2"><th>Tail</th><td>Soft</td><!-- check missing etag -->
</table>
</body>
</html>""")
        tr_list = list(doc.root.find_children_depth_first(html.TR))
        e = tr_list[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="tr1",
            style_class=["A", "B"], style="font-size: medium;",
            title="TR Test", onclick="alert('Hi');")
        self.check_cellalign(
            e, align=html.HAlign.char, char='.',
            charoff=html.Length(10, html.Length.Percentage),
            valign=html.VAlign.middle)
        self.check_unmapped(e, ['bgcolor'], bgcolor=html.RED)
        # check forced TD
        e = list(e.find_children_depth_first(html.TD))[0]
        self.assertTrue(e.get_value().strip() == "Cell")
        self.assertTrue(len(tr_list) == 2)
        self.assertTrue(tr_list[1].id == "tr2")

    def test_ul(self):
        e = html.UL(None)
        self.assertTrue(isinstance(e, html.XHTMLElement))
        self.assertTrue(isinstance(e, html.List))
        self.assertTrue(isinstance(e, html.BlockMixin))
        self.assertTrue(isinstance(e, html.FlowMixin))
        self.check_attrs(e)
        doc = self.load_example("""<html>
<head><title>Test</title></head>
<body>
<ul lang="en-US" dir="ltr" id="list1" class="A B"
    style="font-size: medium;" title="UL Test"
    onclick="alert('Hi');" type="square" compact="compact">
    <!-- check forced open list item -->
    item 1
    <li>Item 2</li>
</ul>
</body></html>
""")
        # check backwards compatible synomym
        e = list(doc.root.find_children_depth_first(html.UL))[0]
        self.check_attrs(
            e, lang="en-US", dir=html.Direction.ltr, id="list1",
            style_class=["A", "B"], style="font-size: medium;",
            title="UL Test", onclick="alert('Hi');")
        items = list(e.get_children())
        self.assertTrue(len(items) == 2)
        self.assertTrue(items[0].get_value().strip() == "item 1")


class ParserTests(unittest.TestCase):

    def test_constants(self):
        self.assertTrue(html.HTML40_PUBLICID == "-//W3C//DTD HTML 4.01//EN")

    def test_constructor(self):
        e = xml.XMLEntity(
            "Preamble\n<P>Hello&nbsp;<b>World!<P>Pleased to meet you.</P>")
        p = html.HTMLParser(e)
        doc = p.parse_document(html.XHTMLDocument())
        self.assertTrue(
            isinstance(doc, html.XHTMLDocument), "Type of document parsed")
        fragment = list(doc.root.Body.get_children())
        self.assertTrue(len(fragment) == 1, "Expected a single child")
        self.assertTrue(
            isinstance(fragment[0], html.Div), "Expected a single Div child")
        fragment = list(fragment[0].get_children())
        self.assertTrue(
            fragment[0] == 'Preamble\n', "Preamble: %s" % repr(fragment[0]))
        tag = fragment[1]
        self.assertTrue(isinstance(tag, html.P), "P Tag: %s" % repr(tag))
        children = list(tag.get_children())
        self.assertTrue(
            children[0] == ul('Hello\xA0'), "nbsp: %s" % repr(children[0]))
        self.assertTrue(
            isinstance(children[1], html.B), "B Tag: %s" % repr(children[1]))
        self.assertTrue(children[1].get_value() == "World!")
        tag = fragment[2]
        self.assertTrue(isinstance(tag, html.P), "P Tag: %s" % repr(tag))
        self.assertTrue(tag.get_value() == "Pleased to meet you.")


"""sgml_omittag Feature:

Empty elements are handled by a simple XMLCONTENT attribute:

<!ELEMENT BASEFONT - O EMPTY        -- base font size -->
<!ELEMENT BR - O EMPTY              -- forced line break -->
<!ELEMENT IMG - O EMPTY             -- Embedded image -->
<!ELEMENT HR - O EMPTY              -- horizontal rule -->
<!ELEMENT INPUT - O EMPTY           -- form control -->
<!ELEMENT FRAME - O EMPTY           -- subwindow -->
<!ELEMENT ISINDEX - O EMPTY         -- single line prompt -->
<!ELEMENT BASE - O EMPTY            -- document base URI -->
<!ELEMENT META - O EMPTY            -- generic metainformation -->
<!ELEMENT AREA - O EMPTY            -- client-side image map area -->
<!ELEMENT LINK - O EMPTY            -- a media-independent link -->
<!ELEMENT PARAM - O EMPTY           -- named property value -->
<!ELEMENT COL      - O EMPTY        -- table column -->


Missing start tags must be handled in the context where these elements
may occur:

<!ELEMENT BODY O O (%flow;)* +(INS|DEL)     -- document body -->
<!ELEMENT TBODY    O O (TR)+                -- table body -->
<!ELEMENT HEAD O O (%head.content;) +(%head.misc;)
                                            -- document head -->
<!ELEMENT HTML O O (%html.content;)         -- document root element -->


Missing end tags must be handled in the elements themselves:

<!ELEMENT P - O (%inline;)*          -- paragraph -->
<!ELEMENT DT - O (%inline;)*         -- definition term -->
<!ELEMENT DD - O (%flow;)*           -- definition description -->
<!ELEMENT LI - O (%flow;)*           -- list item -->
<!ELEMENT OPTION - O (#PCDATA)       -- selectable choice -->
<!ELEMENT THEAD    - O (TR)+         -- table header -->
<!ELEMENT TFOOT    - O (TR)+         -- table footer -->
<!ELEMENT COLGROUP - O (COL)*        -- table column group -->
<!ELEMENT TR       - O (TH|TD)+      -- table row -->
<!ELEMENT (TH|TD)  - O (%flow;)*     -- table header cell, table data cell-->


No special action required::

    <!ENTITY % Datetime "CDATA"
        -- date and time information. ISO date format -->
    <!ENTITY % FrameTarget "CDATA" -- render in this frame -->


Headings and list classes are defined later with proper base classes::

        <!ENTITY % heading "H1|H2|H3|H4|H5|H6">
        <!ENTITY % list "UL | OL |  DIR | MENU">
        <!ENTITY % preformatted "PRE">

HTML Entities are implemented directly from native python libraries::

        <!ENTITY % HTMLlat1 PUBLIC
           "-//W3C//ENTITIES Latin1//EN//HTML"
           "HTMLlat1.ent">
        %HTMLlat1;

        <!ENTITY % HTMLsymbol PUBLIC
           "-//W3C//ENTITIES Symbols//EN//HTML"
           "HTMLsymbol.ent">
        %HTMLsymbol;

        <!ENTITY % HTMLspecial PUBLIC
           "-//W3C//ENTITIES Special//EN//HTML"
           "HTMLspecial.ent">
        %HTMLspecial;

Pixels is just handled directly using xsi integer concept
    ::
        <!ENTITY % Pixels "CDATA" -- integer representing length in pixels -->
"""

if __name__ == "__main__":
    unittest.main()
