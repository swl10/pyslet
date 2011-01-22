#! /usr/bin/env python

import unittest

import os, random, time
from threading import Thread
from SocketServer import ThreadingMixIn
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler

HTTP_PORT=random.randint(1111,9999)

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
	pass

class APPHandler(BaseHTTPRequestHandler):
	def do_GET(self):
		response=FAKE_SERVER.get(self.path,None)
		if response is None:
			self.send_response(404)
			self.send_header("Content-Length","0")
			self.end_headers()
		else:
			self.send_response(response[0])
			self.send_header("Content-type", response[1])
			self.send_header("Content-Length",str(len(response[2])))
			self.end_headers()
			self.wfile.write(response[2])

	def log_request(code=None, size=None):
		# BaseHTTPRequestHandler.log_request(self,code,size)
		# Prevent successful requests logging to stderr
		pass

		
def runAPPServer():
	server=ThreadingHTTPServer(("localhost",HTTP_PORT), APPHandler)
	server.serve_forever()


def suite():
	# kick-off a thread to run an HTTP server	
	t=Thread(target=runAPPServer)
	t.setDaemon(True)
	t.start()
	print "Starting HTTP server on localhost, port %i"%HTTP_PORT
	return unittest.TestSuite((
		unittest.makeSuite(APP5023Tests,'test'),
		unittest.makeSuite(APPElementTests,'test'),
		unittest.makeSuite(APPCategoriesTests,'test'),
		unittest.makeSuite(APPServiceTests,'test'),
		unittest.makeSuite(APPWorkspaceTests,'test'),
		unittest.makeSuite(APPCollectionTests,'test'),
		unittest.makeSuite(APPClientTests,'test')
		))


from pyslet.rfc5023 import *

CAT_EXAMPLE_1="""<?xml version="1.0" ?>
<app:categories
   xmlns:app="http://www.w3.org/2007/app"
   xmlns:atom="http://www.w3.org/2005/Atom"
   fixed="yes" scheme="http://example.com/cats/big3">
 <atom:category term="animal" />
 <atom:category term="vegetable" />
 <atom:category term="mineral" />
</app:categories>"""

SVC_EXAMPLE_1="""<?xml version="1.0" encoding='utf-8'?>
<service xmlns="http://www.w3.org/2007/app"
		xmlns:atom="http://www.w3.org/2005/Atom">
 <workspace>
   <atom:title>Main Site</atom:title>
   <collection
	   href="http://example.org/blog/main" >
	 <atom:title>My Blog Entries</atom:title>
	 <categories
		href="http://example.com/cats/forMain.cats" />
   </collection>
   <collection
	   href="http://example.org/blog/pic" >
	 <atom:title>Pictures</atom:title>
	 <accept>image/png</accept>
	 <accept>image/jpeg</accept>
	 <accept>image/gif</accept>
   </collection>
 </workspace>
 <workspace>
   <atom:title>Sidebar Blog</atom:title>
   <collection
	   href="http://example.org/sidebar/list" >
	 <atom:title>Remaindered Links</atom:title>
	 <accept>application/atom+xml;type=entry</accept>
	 <categories fixed="yes">
	   <atom:category
		 scheme="http://example.org/extra-cats/"
		 term="joke" />
	   <atom:category
		 scheme="http://example.org/extra-cats/"
		 term="serious" />
	 </categories>
   </collection>
 </workspace>
</service>"""

SVC_EXAMPLE_2="""<?xml version="1.0" encoding='utf-8'?>
<service xmlns="http://www.w3.org/2007/app"
		xmlns:atom="http://www.w3.org/2005/Atom">
 <workspace>
   <atom:title>Test Workspace</atom:title>
   <collection
	   href="/collections/blog" >
	 <atom:title>Test Blog</atom:title>
   </collection>
   <collection
	   xml:base="/morecollections/" href="blog" >
	 <atom:title>Test Blog</atom:title>
   </collection>
 </workspace>
</service>"""

FEED_TEST_BLOG="""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
 <title>Test Blog Feed</title>
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

FAKE_SERVER={
	'/service':(200,ATOMSVC_MIMETYPE,SVC_EXAMPLE_2),
	'/collections/blog':(200,atom.ATOM_MIMETYPE,FEED_TEST_BLOG),
	'/morecollections/blog':(200,atom.ATOM_MIMETYPE,FEED_TEST_BLOG)
	}
	
class APP5023Tests(unittest.TestCase):
	def testCaseConstants(self):
		self.failUnless(APP_NAMESPACE=="http://www.w3.org/2007/app","Wrong APP namespace: %s"%APP_NAMESPACE)
		self.failUnless(ATOMSVC_MIMETYPE=="application/atomsvc+xml","Wrong APP service mime type: %s"%ATOMSVC_MIMETYPE)
		self.failUnless(ATOMCAT_MIMETYPE=="application/atomcat+xml","Wrong APP category mime type: %s"%ATOMCAT_MIMETYPE)

	def testCaseTBA(self):
		"""
		Atom Publishing Protocol XML Documents MUST be "namespace-well-
		formed" as specified in Section 7 of [REC-xml-names]
		
		Foreign markup can be used anywhere
		within a Category or Service Document unless it is explicitly
		forbidden.  Processors that encounter foreign markup MUST NOT stop
		processing and MUST NOT signal an error.
	   """
	   
class APPElementTests(unittest.TestCase):
	def testCaseConstructor(self):
		e=APPElement(None)
		self.failUnless(e.ns==APP_NAMESPACE,'ns on construction')
		self.failUnless(e.xmlname==None,'element name on construction')
		self.failUnless(e.GetBase() is None,"xml:base present on construction")
		self.failUnless(e.GetLang() is None,"xml:lang present on construction")
		self.failUnless(e.GetSpace() is None,"xml:space present on construction")
		attrs=e.GetAttributes()
		self.failUnless(len(attrs.keys())==0,"Attributes present on construction")

class APPCategoriesTests(unittest.TestCase):
	def testCaseConstructor(self):
		e=APPCategories(None)
		self.failUnless(e.ns==APP_NAMESPACE,'ns on construction')
		self.failUnless(e.xmlname=="categories",'element name on construction')
		self.failUnless(e.GetBase() is None,"xml:base present on construction")
		self.failUnless(e.GetLang() is None,"xml:lang present on construction")
		self.failUnless(e.GetSpace() is None,"xml:space present on construction")
		attrs=e.GetAttributes()
		self.failUnless(len(attrs.keys())==0,"Attributes present on construction")
		self.failUnless(e.GetHREF() is None,"href present on construction")
		self.failUnless(e.GetFixed() is None and e.IsFixed() is False,"fixed on construction")
		self.failUnless(e.GetScheme() is None,"scheme present on construction")
		self.failUnless(len(e.GetCategoryList())==0,"Category  list non empty on construction")
		
class APPCollectionTests(unittest.TestCase):
	def testCaseConstructor(self):
		c=APPCollection(None)
		self.failUnless(isinstance(c,APPElement),"APPCollection not an APPElement")
		self.failUnless(c.xmlname=="collection","APPCollection XML name")
		self.failUnless(c.GetHREF() is None,"HREF present on construction")
		attrs=c.GetAttributes()
		self.failUnless(len(attrs.keys())==0,"Attributes present on construction")
		self.failUnless(c.GetTitle() is None,"Title present on construction")
		acceptList=c.GetAcceptList()
		self.failUnless(len(acceptList)==0,"Accept list non-empty on construction")
		categories=c.GetCategories()
		self.failUnless(isinstance(categories,APPCategories),"Categories not of correct class type")
		
class APPWorkspaceTests(unittest.TestCase):
	def testCaseConstructor(self):
		ws=APPWorkspace(None)
		self.failUnless(isinstance(ws,APPElement),"APPWorkspace not an APPElement")
		self.failUnless(ws.xmlname=="workspace","APPWorkspace XML name")
		attrs=ws.GetAttributes()
		self.failUnless(len(attrs.keys())==0,"Attributes present on construction")
		self.failUnless(ws.GetTitle() is None,"Title present on construction")
		collections=ws.GetCollections()
		self.failUnless(len(collections)==0,"Collections present on construction")

class APPServiceTests(unittest.TestCase):
	def testCaseConstructor(self):
		svc=APPService(None)
		self.failUnless(isinstance(svc,APPElement),"APPService not an APPElement")
		self.failUnless(svc.xmlname=="service","APPService XML name")
		attrs=svc.GetAttributes()
		self.failUnless(len(attrs.keys())==0,"Attributes present on construction")
		workspaces=svc.GetWorkspaces()
		self.failUnless(len(workspaces)==0,"Workspaces present on construction")

	def testCaseReadXML(self):
		p=APPParser()
		svc=p.ParseString(SVC_EXAMPLE_1)
		self.failUnless(isinstance(svc,APPService),"Example 1 not a service")
		wspace=svc.GetWorkspaces()
		self.failUnless(len(wspace)==2,"Example 1 has no workspaces")
		ws=wspace[0]
		title=ws.GetTitle()
		self.failUnless(isinstance(title,atom.AtomText) and title.GetValue()=="Main Site","Example 1, workspace 1 title")
		collections=ws.GetCollections()
		self.failUnless(len(collections)==2,"Example 1, workspace 1 has no collections")
		c=collections[0]
		self.failUnless(isinstance(c,APPCollection) and c.GetHREF()=="http://example.org/blog/main","Collection type or href")
		title=c.GetTitle()
		self.failUnless(isinstance(title,atom.AtomText) and title.GetValue()=="My Blog Entries","Collection title")
		cats=c.GetCategories()
		self.failUnless(isinstance(cats,APPCategories) and cats.GetHREF()=="http://example.com/cats/forMain.cats","Collection categories")
		accepts=collections[1].GetAcceptList()
		self.failUnless(len(accepts)==3 and accepts[0].GetValue()=="image/png" and accepts[2].GetValue()=="image/gif","Collection accepts")
		cats=wspace[1].GetCollections()[0].GetCategories()
		self.failUnless(cats.IsFixed(),"Collection categories fixed")
		catList=cats.GetCategoryList()
		self.failUnless(len(catList)==2,"Collection category list")
		cat=catList[0]
		self.failUnless(isinstance(cat,atom.AtomCategory) and cat.GetScheme()=="http://example.org/extra-cats/"
			and cat.GetTerm()=="joke","Collection category 1")
		cat=catList[1]
		self.failUnless(isinstance(cat,atom.AtomCategory) and cat.GetScheme()=="http://example.org/extra-cats/"
			and cat.GetTerm()=="serious","Collection category 2")


class APPClientTests(unittest.TestCase):
	def testCaseConstructor(self):
		client=APPClient()		
		self.failUnless(isinstance(client,http.HTTPRequestManager),'APPClient super')
		
	def testCaseAPPGet(self):
		client=APPClient()
		svc=client.Get('http://localhost:%i/service'%HTTP_PORT)
		self.failUnless(isinstance(svc,APPService),"GET /service")
		for ws in svc.GetWorkspaces():
			for c in ws.GetCollections():
				feed=client.Get(c.GetFeedURL())
				self.failUnless(isinstance(feed,atom.AtomFeed),"Collection not a feed for %s"%c.GetTitle().GetValue())

		
if __name__ == "__main__":
	unittest.main()
