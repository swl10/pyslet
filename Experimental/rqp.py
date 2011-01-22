#!/usr/bin/env python

from types import *

from sys import exc_info
from traceback import print_exception

from os import listdir
from os.path import join as pathjoin

from SOAPpy import SOAPProxy, SOAPServer

from PyAssess.ims.qti.common import CheckValue
import PyAssess.ims.qti.asi as item
from PyAssess.ims.qti.session import ItemSession, AssessmentItemState

RQP_Version="0.3.4"

"""
Note that RQP states:

Situations where only grading is required are likely to be fairly rare so the
performance penalty incurred by needlessly rendering is not likely to be
important for most systems.
"""

class RQPException(Exception): pass

class UnregisteredItem(RQPException): pass
class ProtocolError(RQPException): pass
class VariableTypeMismatch(RQPException): pass

class MarkingServer:
	def __init__(self,host,port):
		self.items={}
		self.p=item.AssessmentItemParser()
		self.server=SOAPServer((host,port))
		self.server.registerKWFunction(self.MarkingService)

	def ReadItem(self,fName):
		item=None
		try:
			f=file(fName,'r')
		except IOError:
			print "Failed to read file %s"%fName
			err,errValue,tb=exc_info()
			print_exception(err,errValue,None)				
			return
		try:
			item=self.p.ReadAssessmentItem(f)
			print "Read item id %s from %s: OK"%(item.identifier,fName)
		except:
			print "Failed to parse item from %s: see below for details"%fName
			err,errValue,tb=exc_info()
			print_exception(err,errValue,tb)
		f.close()
		if item:
			self.items[item.identifier]=item

	def ReadItemDirectory(self,dpath):
		for fName in listdir(dpath):
			# we are only interested in xml files
			if fName[-4:].lower()!=".xml":
				continue
			self.ReadItem(pathjoin(dpath,fName))
					
	def StartServer(self):
		self.server.serve_forever()
	
	def MarkingService(self,**kw):
		item=self.items.get(kw.get('identifier'))
		print kw
		if item is None:
			raise UnregisteredItem
		variables=kw.get('variables')
#		if variables is None or type(variables) is not DictionaryType:
#			raise ProtocolError
		session=ItemSession(item)
		session.BeginAttempt()
		for v in variables:
			name=v['name']
			cardinality=v['cardinality']
			baseType=v['baseType']
			newValue=v['value']
			value=session.GetVariableValue(name)
			if value[0]!=cardinality or value[1]!=baseType:
				raise VariableTypeMismatch
			if newValue is not None:
				CheckValue(value[0],value[1],newValue)
			value[2]=newValue
		# forces response processing to be carried out
		session.EndAttempt()
		#report back the new set of variables (responses will not be updated)
		variables=[]
		for v in session.GetVariableNames():
			value=session.GetVariableValue(v)
			variables.append({'name':v, 'cardinality':value[0],
				'baseType':value[1], 'value':value[2]})		
		return variables
		

class RQPClient:
	def __init__(self,url):
		self.url=url
		self.server=SOAPProxy(url)
	
	def GetServerInformation(self):
		info=self.server.RQP_ServerInformation()
		self.identifier=info.identifier
		self.name=info.name
		self.description=info.description
		self.cloning=info.cloning
		self.implicitCloning=info.implicitCloning
		self.rendering=info.rendering
		self.itemFormats=info.itemFormats['item']
		self.renderFormats=info.renderFormats['item']

if __name__ == "__main__":
	from sys import argv
	if len(argv)>=2:
		hostname=argv[1]
	else:
		hostname="localhost"
	server=MarkingServer(hostname,8080)
	server.ReadItemDirectory('../testdata/valid')
	print "Starting MarkingService on %s"%hostname
	server.StartServer()
