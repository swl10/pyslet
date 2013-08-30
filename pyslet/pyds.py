#! /usr/bin/env python
"""This module provides a simple implementation of an EntitySet using a python list object."""


import pyslet.mc_csdl as edm
import pyslet.mc_edmx as edmx
import pyslet.odatav2 as odata
import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.iso8601 as iso8601
import pyslet.rfc2616 as http

# class EntityCollection(edm.EntityCollection):
# 	"""An iterable of :py:class:`Entity` instances.
# 	
# 	Initialised with an entity set to iterate over.  If keys is not None then it
# 	is an iterable list of the keys describing the sub-set."""
# 	def __init__(self,es,keys=None):
# 		edm.EntityCollection.__init__(self,es)
# 		# return all the values at the moment
# 		if keys is None:
# 			self.values=list(es.data.iterkeys()).__iter__()
# 		else:
# 			self.values=keys.__iter__()
# 	
# 	def SubsetValues(self,keys):
# 		for k in keys:
# 			yield self.es.data[k]
# 			
# 	def __iter__(self):
# 		return self
# 		
# 	def GetTitle(self):
# 		"""Returns the title of this list of entities."""
# 		return self.es.name
# 	
# 	def GetUpdated(self):
# 		"""Returns a TimePoint indicating when the collection was updated."""
# 		updated=iso8601.TimePoint()
# 		updated.Now()
# 		return updated			
# 
# 	def next(self):
# 		"""Returns the next Entity in the collection."""
# 		key=self.values.next()
# 		return self.es[key]


class EntitySet(odata.EntitySet):
	"""Implements an in-memory entity set using a python dictionary.
	
	Each entity is stored as a tuple of values in the order in which the
	properties of that entity type are declared.  Complex values are stored as
	nested tuples.
	
	We use OData's EntitySet class to indicate that we support the media-streaming
	methods.  Media streams are simply strings stored in a parallel dictionary
	mapping keys on to a tuple of media-type and string."""	
	
	def __init__(self,parent):
		super(EntitySet,self).__init__(parent)
		self.data={}		#: simple dictionary of the values
		self.streams={}		#: simple dictionary of streams
		self.delHooks=[]	#: list of functions to call during deletion
	
	def __len__(self):
		return len(self.data)

	def itervalues(self):
		for k in self.data:
			yield self[k]
		
	def __getitem__(self,key):
		e=edm.Entity(self)
		for pName,pValue in zip(e.iterkeys(),self.data[self.KeyValue(key)]):
			p=e[pName]
			if isinstance(p,edm.Complex):
				self.SetComplexFromTuple(p,pValue)
			else:
				p.pyValue=pValue
		return e
	
	def SetComplexFromTuple(self,complexValue,t):
		for pName,pValue in zip(complexValue.iterkeys(),t):
			p=complexValue[pName]
			if isinstance(p,edm.Complex):
				self.SetComplexFromTuple(p,pValue)
			else:
				p.pyValue=pValue
	
	def __setitem__(self,key,e):
		# e is an EntityTypeInstance, we need to convert it to a tuple
		value=[]
		for pName in e.iterkeys():
			p=e[pName]
			if isinstance(p,edm.Complex):
				value.append(self.GetTupleFromComplex(p))
			else:
				value.append(p.GetSimpleValue())
		self.data[self.KeyValue(key)]=tuple(value)

	def SetItemStream(self,key,streamType,stream):
		self.streams[self.KeyValue(key)]=(streamType,stream)

	def GetTupleFromComplex(self,complexValue):
		value=[]
		for pName in complexValue.iterkeys():
			p=complexValue[pName]
			if isinstance(p,edm.Complex):
				value.append(self.GetTupleFromComplex(p))
			else:
				value.append(p.GetSimpleValue())
		return tuple(value)
	
	def __delitem__(self,key):
		for hook in self.delHooks:
			hook(key)
		del self.data[self.KeyValue(key)]
	
	def UpdateSetRefs(self,scope,stopOnErrors=False):
		"""We use this method to clear the delete hook lists."""
		edm.EntitySet.UpdateSetRefs(self,scope,stopOnErrors)
		self.delHooks=[]

	def AddDeleteHook(self,delHook):
		"""Adds a function to call during entity deletion."""
		self.delHooks.append(delHook)

	def GetStreamType(self,entity):
		"""Returns the content type of the entity's media stream.
		
		Must return a :py:class:`pyslet.rfc2616.MediaType` instance."""
		key=entity.Key()
		if key in self.streams:
			type,stream=self.streams[key]
			return type
		else:
			return http.MediaType('application/octet-stream')
			
	def GetStreamSize(self,entity):
		"""Returns the size of the entity's media stream in bytes."""
		key=entity.Key()
		if key in self.streams:
			type,stream=self.streams[key]
			return len(stream)
		else:
			return 0
		
	def GetStreamGenerator(self,entity):
		"""A generator function that yields blocks (strings) of data from the entity's media stream."""
		key=entity.Key()
		if key in self.streams:
			type,stream=self.streams[key]
			yield stream
		else:
			yield ''

		

class AssociationSet(edm.AssociationSet):
	
	def GetElementClass(self,name):
		if xmlns.NSEqualNames((edm.EDM_NAMESPACE,'End'),name,edm.EDM_NAMESPACE_ALIASES):
			return AssociationSetEnd
		else:
			return None

	def Associate(self,fromKey,toKey):
		self.AssociationSetEnd[0].AddLink(fromKey,toKey)


class NavigationEntitySet(edm.NavigationEntitySet):
	
	def itervalues(self):
		result=self.sourceEnd.index[self.sourceKey]
		for k in result:
			yield self.sourceEnd.otherEnd.entitySet[k]
		

class AssociationSetEnd(edm.AssociationSetEnd):
	# XMLNAME=(EDM_NAMESPACE,'End')
	
	def __init__(self,parent):
		edm.AssociationSetEnd.__init__(self,parent)
		self.index={}		#: a dictionary mapping source keys on to target keys	
		
	def Navigate(self,fromKey):
		"""We keep a simple index dictionary mapping source keys to target keys.
		
		We use dictionaries of target keys as the values in the index for simplicity."""
		if self.IsEntityCollection():
			return NavigationEntitySet(self,fromKey)
		else:
			result=self.index.get(fromKey,None)
			if result is None:
				return None
			elif len(result)==1:
				k=result.keys()[0]
				return self.otherEnd.entitySet[k]
			else:
				raise KeyError("Navigation error, found multiple entities")

	def UpdateSetRefs(self,scope,stopOnErrors=False):
		"""We use this method to add a delete hook to the entity set."""
		edm.AssociationSetEnd.UpdateSetRefs(self,scope,stopOnErrors)
		if self.entitySet is not None:
			self.entitySet.AddDeleteHook(self.DeleteHook)
	
	def AddLink(self,fromKey,toKey):
		"""Adds a link from *fromKey* to *toKey*"""
		self.index.setdefault(fromKey,{})[toKey]=True
		self.otherEnd.index.setdefault(toKey,{})[fromKey]=True

	def DeleteHook(self,key):
		"""Called when the source entity key is being deleted."""
		try:
			result=self.index[key]
			for otherKey in result:
				otherResut=self.otherEnd.index[otherKey]
				del otherResult[key]
				if len(otherResult)==0:
					del self.otherEnd.index[otherKey]
			del self.index[key]			
		except KeyError:
			pass


class Document(edmx.Document):
	"""This class overrides the default EDMX implementation to given the
	EntitySet class used."""

	classMap={}

	def __init__(self,**args):
		edmx.Document.__init__(self,**args)

	def GetElementClass(self,name):
		eClass=Document.classMap.get(name,Document.classMap.get((name[0],None),None))
		if eClass:
			return eClass
		else:
			return super(Document,self).GetElementClass(name)

xmlns.MapClassElements(Document.classMap,globals(),edm.NAMESPACE_ALIASES)
