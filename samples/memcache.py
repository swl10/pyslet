#! /usr/bin/env python
"""Creates an OData in-memory cache of key value pairs"""

SERVICE_PORT=8080
SERVICE_ROOT="http://localhost:%i/"%SERVICE_PORT
CLEANUP_SLEEP=10

import logging, threading, time
from wsgiref.simple_server import make_server

import pyslet.iso8601 as iso
import pyslet.odata2.csdl as edm
import pyslet.odata2.core as core
import pyslet.odata2.metadata as edmx
from pyslet.odata2.server import Server
from pyslet.odata2.memds import InMemoryEntityContainer


cacheApp=None		#: our Server instance


def LoadMetadata():
	"""Loads the metadata file from the current directory."""
	doc=edmx.Document()
	with open('MemCacheSchema.xml','rb') as f:
		doc.Read(f)
	return doc


def TestData(memCache):
	with memCache.OpenCollection() as collection:
		for i in xrange(26):
			e=collection.new_entity()
			e.set_key(str(i))
			e['Value'].set_from_value(unichr(0x41+i))
			e['Expires'].set_from_value(iso.TimePoint.FromUnixTime(time.time()+10*i))
			collection.insert_entity(e)

def TestModel():
	"""Read and write some key value pairs"""
	doc=LoadMetadata()
	container=InMemoryEntityContainer(doc.root.DataServices['MemCacheSchema.MemCache'])
	memCache=doc.root.DataServices['MemCacheSchema.MemCache.KeyValuePairs']
	TestData(memCache)
	with memCache.OpenCollection() as collection:
		for e in collection.itervalues():
			print "%s: %s (expires %s)"%(e['Key'].value,e['Value'].value,str(e['Expires'].value))


def runCacheServer():
	"""Starts the web server running"""
	server=make_server('',SERVICE_PORT,cacheApp)
	logging.info("Starting HTTP server on port %i..."%SERVICE_PORT)
	# Respond to requests until process is killed
	server.serve_forever()


def CleanupForever(memCache):
	"""Runs a loop continuously cleaning up expired items"""
	now=edm.DateTimeValue()
	expires=core.PropertyExpression(u"Expires")
	t=core.LiteralExpression(now)
	filter=core.BinaryExpression(core.Operator.lt)
	filter.operands.append(expires)
	filter.operands.append(t)
	while True:
		now.set_from_value(iso.TimePoint.FromNowUTC())
		logging.info("Cleanup thread running at %s",str(now.value))
		with memCache.OpenCollection() as cacheEntries:
			cacheEntries.set_filter(filter)
			expiredList=list(cacheEntries)
			if expiredList:
				logging.info("Cleaning %i cache entries",len(expiredList))
				for expired in expiredList:
					del cacheEntries[expired]
			cacheEntries.set_filter(None)
			logging.info("Cleanup complete, %i cache entries remain",len(cacheEntries))			
		time.sleep(CLEANUP_SLEEP)

	
def main():
	"""Executed when we are launched"""
	doc=LoadMetadata()
	container=InMemoryEntityContainer(doc.root.DataServices['MemCacheSchema.MemCache'])
	server=Server(serviceRoot=SERVICE_ROOT)
	server.SetModel(doc)
	# The server is now ready to serve forever
	global cacheApp
	cacheApp=server
	t=threading.Thread(target=runCacheServer)
	t.setDaemon(True)
	t.start()
	logging.info("MemCache starting HTTP server on %s"%SERVICE_ROOT)
	CleanupForever(doc.root.DataServices['MemCacheSchema.MemCache.KeyValuePairs'])
	

if __name__ == '__main__':
	logging.basicConfig(level=logging.INFO)
	main()
