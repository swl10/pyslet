#! /usr/bin/env python
"""This module provides a simple implementation of an EntitySet using a python list object."""


import pyslet.odata2.csdl as edm
import pyslet.odata2.edmx as edmx
import pyslet.odata2.core as odata
import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.iso8601 as iso8601
import pyslet.rfc2616 as http

import string, hashlib, threading

			
class InMemoryEntityStore(object):
	"""Implements an in-memory entity set using a python dictionary.
	
	Each entity is stored as a tuple of values in the order in which the
	properties of that entity type are declared.  Complex values are
	stored as nested tuples.
	
	Media streams are simply strings stored in a parallel dictionary
	mapping keys on to a tuple of media-type and string.
	
	All access to the data itself uses the *container*'s lock to ensure
	this object can be called from multi-threaded programs.  Although
	individual collections must not be shared across threads multiple
	threads can open separate collections and access the entities
	safely."""
	
	def __init__(self,container,entitySet=None):
		self.container=container	#: the :py:class:`InMemoryEntityContainer` that contains this entity set
		self.entitySet=entitySet	#: the entity set we're bound to
		self.data={}				#: simple dictionary of the values
		self.streams={}				#: simple dictionary of streams
		self.associations={}		#: a mapping of association set names to :py:class:`InMemoryAssociation` instances *from* this entity set
		self.reverseAssociations={}	#: a mapping of association set names to :py:class:`InMemoryAssociation` index instances *to* this entity set
		self._deleting=set()
		self.nextKey=None
		if entitySet is not None:
			self.BindToEntitySet(entitySet)
			
	def BindToEntitySet(self,entitySet):
		"""Binds this entity store to the given entity set.
		
		Not thread safe."""
		entitySet.Bind(EntityCollection,entityStore=self)
		self.entitySet=entitySet
		
	def AddAssociation(self,associationIndex,reverse):
		"""Adds an association index from this entity set (if reverse is
		False) or to this entity set (reverse is True).
		
		Not thread safe."""
		if reverse:
			self.reverseAssociations[associationIndex.name]=associationIndex
		else:
			self.associations[associationIndex.name]=associationIndex
			
	def AddEntity(self,e):
		key=e.Key()
		value=[]
		for pName in e.DataKeys():
			if not e.Selected(pName):
				continue
			p=e[pName]
			if isinstance(p,edm.Complex):
				value.append(self.GetTupleFromComplex(p))
			elif isinstance(p,edm.SimpleValue):
				value.append(p.value)
		with self.container.lock:
			self.data[key]=tuple(value)
			# At this point the entity exists
			e.exists=True

	def CountEntities(self):
		with self.container.lock:
			return len(self.data)
			
	def GenerateEntities(self,select=None):
		"""A generator function that returns the entities in the entity set
		
		The implementation is a compromise, we don't lock the container
		for the duration of the iteration, instead we work on a copy of
		the list of keys.  This creates the slight paradox that an entity
		deleted during the iteration *may* not be yielded but an entity
		inserted during the iteration will never be yielded."""
		with self.container.lock:
			keys=self.data.keys()
		for k in keys:
			e=self.ReadEntity(k,select)
			if e is not None:
				yield e

	def ReadEntity(self,key,select=None):
		with self.container.lock:
			value=self.data.get(key,None)
			if value is None:
				return None
			e=Entity(self.entitySet,self)
			if select is not None:
				e.Expand(None,select)
			kv=zip(e.DataKeys(),value)
			for pName,pValue in kv:
				p=e[pName]
				if select is None or e.Selected(pName) or pName in self.entitySet.keys:
					# for speed, check if selection is an issue first
					# we always include the keys
					if isinstance(p,edm.Complex):
						self.SetComplexFromTuple(p,pValue)
					else:
						p.SetFromValue(pValue)
				else:
					if isinstance(p,edm.Complex):
						p.SetNull()
					else:
						p.SetFromValue(None)
			e.exists=True
		return e
		
	def SetComplexFromTuple(self,complexValue,t):
		for pName,pValue in zip(complexValue.iterkeys(),t):
			p=complexValue[pName]
			if isinstance(p,edm.Complex):
				self.SetComplexFromTuple(p,pValue)
			else:
				p.SetFromValue(pValue)

	def ReadStream(self,key):
		"""Returns a tuple of (content type, data) of the entity's media stream."""
		with self.container.lock:
			if key not in self.data:
				raise KeyError
			if key in self.streams:
				type,stream=self.streams[key]
				return type,stream
			else:
				return http.MediaType.FromString('application/octet-stream'),''

	def UpdateEntity(self,e):
		# e is an EntityTypeInstance, we need to convert it to a tuple
		key=e.Key()
		with self.container.lock:
			value=list(self.data[key])		
			i=0
			for pName in e.DataKeys():
				if e.Selected(pName):
					p=e[pName]
					if isinstance(p,edm.Complex):
						value[i]=self.GetTupleFromComplex(p)
					elif isinstance(p,edm.SimpleValue):
						value[i]=p.value
				i=i+1
			self.data[key]=tuple(value)

	def UpdateEntityStream(self,key,streamType,stream):
		with self.container.lock:
			self.streams[key]=(streamType,stream)

	def GetTupleFromComplex(self,complexValue):
		value=[]
		for pName in complexValue.iterkeys():
			p=complexValue[pName]
			if isinstance(p,edm.Complex):
				value.append(self.GetTupleFromComplex(p))
			else:
				value.append(p.value)
		return tuple(value)

	def StartDeletingEntity(self,key):
		"""Returns True if it is OK to start deleting the entity, False
		if it is already being deleted.
		
		Not thread-safe, must only be called if you have
		acquired the container lock."""
		if key in self._deleting:
			return False
		elif key not in self.data:
			raise KeyError(repr(key))
		else:
			self._deleting.add(key)
			return True
	
	def DeletingEntity(self,key):
		"""Returns True if the entity with key is currently being
		deleted.
		
		Not thread-safe, must only be called if you have
		acquired the container lock."""
		return key in self._deleting
		
	def StopDeletingEntity(self,key):
		"""Removes *key* from the list of entities being deleted.
		
		Not thread-safe, must only be called if you have
		acquired the container lock."""
		if key in self._deleting:
			self._deleting.remove(key)
					
	def DeleteEntity(self,key):
		with self.container.lock:		
			for associationIndex in self.associations.values():
				associationIndex.DeleteHook(key)
			for associationIndex in self.reverseAssociations.values():
				associationIndex.ReverseDeleteHook(key)
			del self.data[key]
			if key in self.streams:
				del self.streams[key]
		
	def NextKey(self):
		"""In the special case where the key is an integer, return the next free integer"""
		with self.container.lock:
			if self.nextKey is None:
				kps=list(self.entitySet.keys)
				if len(kps)!=1:
					raise KeyError("Can't get next value of compound key")
				key=self.entitySet.entityType[kps[0]]()
				if not isinstance(key,edm.NumericValue):
					raise KeyError("Can't get next value non-integer key")
				keys=self.data.keys()
				if keys:
					keys.sort()
					self.nextKey=keys[-1]
				else:
					key.SetToZero()
					self.nextKey=key.value
			while self.nextKey in self.data:
				self.nextKey+=1
			return self.nextKey


class InMemoryAssociationIndex(object):
	"""An in memory index that implements the association between two
	sets of entities.

	Instances of this class create storage for an association between
	*fromEntityStore* and *toEntityStore* which are
	:py:class:`InMemoryEntityStore` instances.
	
	If *propertyName* (and optionally *reverseName*) is provided then
	the index is immediately bound to the associated entity sets, see
	:py:meth:`Bind` for more information."""	
	def __init__(self,container,associationSet,fromEntityStore,toEntityStore,propertyName=None,reverseName=None):
		self.container=container		#: the :py:class:`InMemoryEntityContainer` that contains this index
		self.name=associationSet.name	#: the name of the association set this index represents
		self.index={}					#: a dictionary mapping source keys on to sets of target keys
		self.reverseIndex={}			#: the reverse index mapping target keys on to sets of source keys
		self.fromEntityStore=fromEntityStore
		fromEntityStore.AddAssociation(self,reverse=False)
		self.toEntityStore=toEntityStore
		toEntityStore.AddAssociation(self,reverse=True)
		if propertyName is not None:
			self.Bind(propertyName,reverseName)
			
	def Bind(self,propertyName,reverseName=None):
		"""Binds this index to the named property of the entity set
		bound to :py:attr:`fromEntityStore`.
		
		If the association is reversible *reverseName* can also be used
		to bind that property in the entity set bound to
		:py:attr:`toEntityStore`"""
		self.fromEntityStore.entitySet.BindNavigation(propertyName,NavigationEntityCollection,associationIndex=self,reverse=False)
		if reverseName is not None:
			self.toEntityStore.entitySet.BindNavigation(reverseName,NavigationEntityCollection,associationIndex=self,reverse=True)
	
	def BindReverse(self,reverseName):
		"""Binds this index to *reverseName* in the :py:attr:`toEntityStore`"""
		if reverseName is not None:
			self.toEntityStore.entitySet.BindNavigation(reverseName,NavigationEntityCollection,associationIndex=self,reverse=True)
				
	def AddLink(self,fromKey,toKey):
		"""Adds a link from *fromKey* to *toKey*"""
		with self.container.lock:
			self.index.setdefault(fromKey,set()).add(toKey)
			self.reverseIndex.setdefault(toKey,set()).add(fromKey)

	def GetLinksFrom(self,fromKey):
		"""Returns a tuple of toKeys linked from *fromKey*"""
		with self.container.lock:
			return tuple(self.index.get(fromKey,()))
		
	def GetLinksTo(self,toKey):
		"""Returns a tuple of fromKeys linked to *toKey*"""
		with self.container.lock:
			return tuple(self.reverseIndex.get(toKey,()))

	def RemoveLink(self,fromKey,toKey):
		"""Removes a link from *fromKey* to *toKey*"""
		with self.container.lock:
			self.index.get(fromKey,set()).discard(toKey)
			self.reverseIndex.get(toKey,set()).discard(fromKey)
		
	def DeleteHook(self,fromKey):
		"""Called only by :py:meth:`InMemoryEntityStore.DeleteEntity`"""
		try:
			toKeys=self.index[fromKey]
			for toKey in toKeys:
				fromKeys=self.reverseIndex[toKey]
				fromKeys.remove(fromKey)
				if len(fromKeys)==0:
					del self.reverseIndex[toKey]
			del self.index[fromKey]			
		except KeyError:
			pass

	def ReverseDeleteHook(self,toKey):
		"""Called only by :py:meth:`InMemoryEntityStore.DeleteEntity`"""
		try:
			fromKeys=self.reverseIndex[toKey]
			for fromKey in fromKeys:
				toKeys=self.index[fromKey]
				toKeys.remove(toKey)
				if len(toKeys)==0:
					del self.index[fromKey]
			del self.reverseIndex[toKey]			
		except KeyError:
			pass


class Entity(odata.Entity):
	"""We override OData's EntitySet class to support the
	media-streaming methods."""	

	def __init__(self,entitySet,entityStore):
		super(Entity,self).__init__(entitySet)
		self.entityStore=entityStore		#: points to the entity storage
			
	def GetStreamType(self):
		"""Returns the content type of the entity's media stream.
		
		Must return a :py:class:`pyslet.rfc2616.MediaType` instance."""
		key=self.Key()
		return self.entityStore.ReadStream(key)[0]
			
	def GetStreamSize(self):
		"""Returns the size of the entity's media stream in bytes."""
		key=self.Key()
		return len(self.entityStore.ReadStream(key)[1])
		
	def GetStreamGenerator(self):
		"""A generator function that yields blocks (strings) of data from the entity's media stream."""
		key=self.Key()
		yield self.entityStore.ReadStream(key)[1]

	def SetStreamFromGenerator(self,streamType,src):
		"""Replaces the contents of this stream with the strings output by iterating over src.
		
		If the entity has a concurrency token and it is a binary value,
		updates the token to be a hash of the stream."""
		key=self.Key()
		etag=self.ETagValues()
		if len(etag)==1 and isinstance(etag[0],edm.BinaryValue):
			h=hashlib.sha256()
			etag=etag[0]
		else:
			h=None
		value=[]
		for data in src:
			value.append(data)
		data=string.join(value,'')
		if h is not None:
			h.update(data)
			etag.SetFromValue(h.digest())
		if h is not None:
			# we need the lock to ensure the stream and etag are updated together
			with self.entityStore.container.lock:
				self.entityStore.UpdateEntityStream(key,streamType,data)
				self.Update()
		else:
			self.entityStore.UpdateEntityStream(key,streamType,data)
	

class EntityCollection(odata.EntityCollection):
	"""An entity collection that provides access to entities stored in
	the :py:class:`InMemoryEntitySet` *entityStore*."""
	
	def __init__(self,entitySet,entityStore):
		super(EntityCollection,self).__init__(entitySet)
		self.entityStore=entityStore
		
	def NewEntity(self,autoKey=False):
		"""Returns an OData aware instance"""
		e=Entity(self.entitySet,self.entityStore)	
		if autoKey:
			e.SetKey(self.entityStore.NextKey())
		return e 
	
	def InsertEntity(self,entity,fromEnd=None):
		"""The optional *fromEnd* is an
		:py:class:`AssociationSetEnd` instance that is bound to *this*
		collection's entity set.  It indicates that we are being created
		by a deep insert or through direct insertion into a
		:py:class:`NavigationEntityCollection` representing the
		corresponding association.  This information can be used to
		suppress a constraint check (on the assumption that it has
		already been checked) by passing *fromEnd* directly to
		:py:meth:`Entity.CheckNavigationConstraints`."""
		try:
			key=entity.Key()
		except KeyError:
			# if the entity doesn't have a key, autogenerate one
			key=self.entityStore.NextKey()
			entity.SetKey(key)
		with self.entityStore.container.lock:
			# This is a bit clumsy, but we lock the whole container while we
			# check all constraints and perform any nested deletes 
			if key in self:
				raise KeyError("%s already exists"%odata.ODataURI.FormatEntityKey(entity))
			# Check constraints
			entity.CheckNavigationConstraints(fromEnd)
			self.entityStore.AddEntity(entity)
			self.UpdateBindings(entity)
		
	def __len__(self):
		if self.filter is None:
			return self.entityStore.CountEntities()
		else:
			result=0
			for e in self.FilterEntities(self.entityStore.GenerateEntities()):
				result+=1
			return result
		
	def itervalues(self):
		return self.OrderEntities(
			self.ExpandEntities(
			self.FilterEntities(
			self.entityStore.GenerateEntities(self.select))))
		
	def __getitem__(self,key):
		e=self.entityStore.ReadEntity(key,self.select)
		if e is not None and self.CheckFilter(e):
			e.Expand(self.expand,self.select)
			return e
		else:
			raise KeyError

	def UpdateEntity(self,entity):
		# force an error if we don't have a key
		key=entity.Key()
		with self.entityStore.container.lock:
			self.entityStore.UpdateEntity(entity)
			# now process any bindings
			self.UpdateBindings(entity)
		
	def __delitem__(self,key):
		"""We do a cascade delete of everything that *must* be linked to
		us. We don't need to bother about deleting links because the
		delete hooks on entityStore do this automatically."""
		if not self.entityStore.StartDeletingEntity(key):
			# we're already being deleted so do nothing
			return
		try:
			for linkEnd,navName in self.entitySet.linkEnds.iteritems():
				if linkEnd.associationEnd.multiplicity==edm.Multiplicity.One:
					# there must be one of us, delete the other end with
					# the exception that if there is no navigation property
					# bound to this property then we won't do a cascade delete
					# We have to go straight to the storage layer to sort
					# this out. We are allowed to raise
					# edm.NavigationConstraintError here but then it would
					# be impossible to delete 1-1 related entities which is
					# a bit limited
					associationSetName=linkEnd.parent.name
					associationIndex=self.entityStore.associations.get(linkEnd.parent.name,None)
					if associationIndex:
						with associationIndex.toEntityStore.entitySet.OpenCollection() as toCollection:
							for toKey in associationIndex.GetLinksFrom(key):
								if navName is None and not associationIndex.toEntityStore.DeletingEntity(toKey):
									# if we are not in the process of deleting toKey
									# and there is no navigation property linking us
									# to it then raise an error
									raise edm.NavigationConstraintError("Can't cascade delete from an entity in %s as the association set %s is not bound to a navigation property"%(self.entitySet.name,associationSetName))
								# delete this link first to prevent infinite
								# recursion
								associationIndex.RemoveLink(key,toKey)
								del toCollection[toKey]
					else:
						associationIndex=self.entityStore.reverseAssociations.get(linkEnd.parent.name,None)
						with associationIndex.fromEntityStore.entitySet.OpenCollection() as fromCollection:
							for fromKey in associationIndex.GetLinksTo(key):
								if navName is None and not associationIndex.fromEntityStore.DeletingEntity(fromKey):
									raise edm.NavigationConstraintError("Can't cascade delete from an entity in %s as the association set %s is not bound to a navigation property"%(self.entitySet.name,associationSetName))
								associationIndex.RemoveLink(fromKey,key)
								del fromCollection[fromKey]
			self.entityStore.DeleteEntity(key)
		finally:
			self.entityStore.StopDeletingEntity(key)
	
class NavigationEntityCollection(odata.NavigationEntityCollection):
	
	def __init__(self,name,fromEntity,toEntitySet,associationIndex,reverse):
		self.associationIndex=associationIndex
		self.reverse=reverse
		if self.reverse:
			self.lookupMethod=self.associationIndex.GetLinksTo
			self.rLookupMethod=self.associationIndex.GetLinksFrom
		else:
			self.lookupMethod=self.associationIndex.GetLinksFrom
			self.rLookupMethod=self.associationIndex.GetLinksTo
		super(NavigationEntityCollection,self).__init__(name,fromEntity,toEntitySet)
		self.collection=self.entitySet.OpenCollection()
		self.key=self.fromEntity.Key()
	
	def NewEntity(self,autoKey=False):
		"""Returns an OData aware instance"""
		return self.collection.NewEntity(autoKey)	
	
	def close(self):
		if self.collection is not None:
			self.collection.close()
			self.collection=None
						
	def __len__(self):
		if self.filter is None:
			resultSet=self.lookupMethod(self.key)
			return len(resultSet)
		else:
			result=0
			for e in self.FilterEntities(self.entityGenerator()):
				result+=1
			return result

	def entityGenerator(self):
		# we create a collection from the appropriate entity set first
		resultSet=self.lookupMethod(self.key)
		for k in resultSet:
			yield self.collection[k]
		
	def itervalues(self):
		return self.OrderEntities(
			self.ExpandEntities(
			self.FilterEntities(
			self.entityGenerator())))

	def __getitem__(self,key):
		resultSet=self.lookupMethod(self.key)
		if key in resultSet:
			result=self.collection[key]
			if self.filter is None:
				if self.CheckFilter(result):
					return result
			else:
				return result
		raise KeyError(key)
		
	def __setitem__(self,key,value):
		resultSet=self.lookupMethod(self.key)
		if key in resultSet:
			# no operation
			return
		# forces a check of value to ensure it is good
		self.collection[key]=value
		if self.toMultiplicity!=edm.Multiplicity.Many:
			#	if not self.fromEntity.IsEntityCollection(self.name):
			#	Should be an error if we already have a link
			if resultSet:
				raise edm.NavigationConstraintError("Can't add multiple links to navigation property %s"%self.name)
		if self.fromMultiplicity!=edm.Multiplicity.Many:
			if self.rLookupMethod(key):
				raise edm.NavigationConstraintError("Entity %s is already bound through this association"%value.GetLocation())				
		# clear to add this one to the index
		if self.reverse:
			self.associationIndex.AddLink(key,self.key)
		else:
			self.associationIndex.AddLink(self.key,key)
	
	def __delitem__(self,key):
		#	Before we remove a link we need to know if either entity
		#	requires a link, if so, this deletion will result in a
		#	constraint violation
		if self.fromMultiplicity==edm.Multiplicity.One or self.toMultiplicity==edm.Multiplicity.One:
			raise edm.NavigationConstraintError("Can't remove a required link")
		resultSet=self.lookupMethod(self.key)
		if key not in resultSet:
			raise KeyError
		if self.reverse:
			self.associationIndex.RemoveLink(key,self.key)
		else:
			self.associationIndex.RemoveLink(self.key,key)

	def Replace(self,entity):
		key=entity.Key()
		resultSet=list(self.lookupMethod(self.key))
		if resultSet==[key]:
			# nothing to do!
			return
		if self.fromMultiplicity==edm.Multiplicity.One:
			if resultSet:
				# we can't delete these links because we are required
				raise edm.NavigationConstraintError("Can't remove a required link")
			else:
				self[key]=entity
		else:
			# add the new link first
			if key not in resultSet:
				if self.reverse:
					self.associationIndex.AddLink(key,self.key)
				else:
					self.associationIndex.AddLink(self.key,key)
			for oldKey in resultSet:
				# now remove all the old keys.  This implementation
				# is the same regardless of the allowed multiplicity.
				# This doesn't just save coding, it ensures that
				# corrupted indexes are self-correcting
				if oldKey!=key:
					if self.reverse:
						self.associationIndex.RemoveLink(oldKey,self.key)
					else:
						self.associationIndex.RemoveLink(self.key,oldKey)
		

class InMemoryEntityContainer(object):
	
	def __init__(self,containerDef):
		self.containerDef=containerDef		#: the :py:class:`csdl.EntityContainer` that defines this container
		self.lock=threading.RLock()			#: a lock that must be acquired before modifying any entity or association in this container
		self.entityStorage={}				#: a mapping from entity set names to :py:class:`InMemoryEntityStore` instances
		self.associationStorage={}			#: a mapping from association set name to :py:class:`InMemoryAssociationIndex` instances
		# for each entity set in this container, bind some storage
		for es in self.containerDef.EntitySet:
			self.entityStorage[es.name]=InMemoryEntityStore(self,es)
		for es in self.containerDef.EntitySet:
			fromStorage=self.entityStorage[es.name]
			if es.entityType is None:
				raise edm.ModelIncomplete("EntitySet %s is not bound to an entity type"%es.name)
			for np in es.entityType.NavigationProperty:
				if np.association is None:
					raise edm.ModelIncomplete("NavigationProperty %s.%s is not bound to an AssociationSet"%(es.name,np.name))
				associationSetEnd=es.navigation[np.name]
				associationSet=associationSetEnd.parent
				if associationSet.name in self.associationStorage:
					# we already have it, do the reverse binding
					self.associationStorage[associationSet.name].BindReverse(np.name)
				else:
					target=es.NavigationTarget(np.name)
					if target is None:
						raise edm.ModelIncomplete("Target of navigation property %s.%s is not bound to an entity set"%(es.name,np.name))
					toStorage=self.entityStorage[target.name]
					self.associationStorage[associationSet.name]=InMemoryAssociationIndex(self,associationSet,fromStorage,toStorage,np.name)