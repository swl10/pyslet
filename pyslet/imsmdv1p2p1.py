#! /usr/bin/env python
"""This module implements the IMS LRM 1.2.1 specification defined by IMS GLC
"""

import pyslet.xmlnames20091208 as xmlns

IMSLRM_NAMESPACE="http://www.imsglobal.org/xsd/imsmd_v1p2"

IMSLRM_NAMESPACE_ALIASES={
#	"http://www.imsproject.org/metadata":"1.1",
#	"http://www.imsproject.org/metadata/":"1.1",
	"http://www.imsproject.org/xsd/imsmd_rootv1p2":IMSLRM_NAMESPACE,
	"http://www.imsglobal.org/xsd/imsmd_rootv1p2p1":IMSLRM_NAMESPACE}

lrm_lom=(IMSLRM_NAMESPACE,'lom')
lrm_wildcard=(IMSLRM_NAMESPACE,None)

md_lom=(IMSLRM_NAMESPACE,'lom')

class LRMException(Exception): pass

class LRMElement(xmlns.XMLNSElement):
	"""Basic element to represent all CP elements"""  
	def __init__(self,parent):
		xmlns.XMLNSElement.__init__(self,parent)
		self.SetXMLName((IMSLRM_NAMESPACE,None))

class LOM(LRMElement):
	pass
	
classMap={
	lrm_lom:LOM,
	lrm_wildcard:LRMElement
	}

def GetElementClass(name):
	ns,xmlname=name
	if IMSLRM_NAMESPACE_ALIASES.has_key(ns):
		ns=IMSLRM_NAMESPACE_ALIASES[ns]
	return classMap.get((ns,xmlname),classMap.get((ns,None),xmlns.XMLNSElement))
