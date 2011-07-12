IMS Basic Learning Tools Interoperability (version 1.0)
=======================================================

The IMS Basic Learning Tools Interoperability (BLTI) specification was released
in 2010. The purpose of the specification is to provide a link between tool
consumers (such as Learning Management Systems and portals) and Tools (such as
specialist assessment management systems).  Official information about the
specification is available from the IMS GLC: http://www.imsglobal.org/lti/

This module requires the oauth module to be installed.  The oauth module is
available from http://pypi.python.org/pypi/oauth/1.0.1

.. py:module:: pyslet.imsbltiv1p0

This module is written from the point of view of the Tool Provider.  Consumers
are modeled by the BLTIConsumer class which does nothing more than implement the
recommended algorithm for checking the Nonces as recommended in the
specification.

Typical usage would be in an HTTP request handler, this code is modelled on the
code provided with the oauth module::

	import pyslet.imsbltiv1p0 as blti

	class BLTIRequestHandler(BaseHTTPRequestHandler):
		def __init__(self, *args, **kwargs):
			self.tp=blti.BLTIToolProvider()
			self.tp.LoadFromFile(open('consumers.txt'))
			BaseHTTPRequestHandler.__init__(self, *args, **kwargs)
		
		def do_GET(self):
			postdata = None
			if self.command=='POST':
				try:
					length = int(self.headers.getheader('content-length'))
					postdata = self.rfile.read(length)
				except:
					pass
			parts=urlparse.urlsplit(self.path)
			if not parts.scheme:
				scheme='http' # change here for https
				if not parts.netloc:
					netloc=self.headers['Host']
				else:
					netloc=parts.netloc
				url=urlparse.urlunsplit([scheme,netloc]+list(parts[2:]))
			else:
				url=self.path
			try:
				consumer,params=self.tp.Launch(self.command, url, headers=self.headers, query_string=postdata)
				self.ReturnPage("LTI Provider authorized request with parameters: \n%s"%str(params))
			except blti.BLTIOAuthParameterError:
				self.ReturnUnauthorized("Missing or incomplete authentication parameters in request")
			except blti.BLTIAuthenticationError, err:
				self.ReturnUnauhtorized("Access denied: "+str(err))
			return
	
		def do_POST(self):
			return self.do_GET()

		def ReturnPage(self,msg):
			self.send_response(200,'OK')
			self.send_header('Content-Type','text/plain')
			self.send_header('Content-Length',str(len(msg)))
			self.end_headers()
			self.wfile.write(msg)

		def ReturnUnauthorized(self,msg):
			self.send_response(403,"Unauthorized")
			self.end_headers()
			self.wfile.write(msg)


Reference
---------

..	autoclass:: BLTIToolProvider
	:members:
	:show-inheritance:


..	autoclass:: BLTIConsumer
	:members:
	:show-inheritance:

..	autoclass:: BLTIError
	:show-inheritance:

..	autoclass:: BLTIAuthenticationError
	:show-inheritance:
