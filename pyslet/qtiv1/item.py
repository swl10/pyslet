#! /usr/bin/env python

import pyslet.xml20081126.structures as xml
import pyslet.xsdatatypes20041028 as xsi
import pyslet.html40_19991224 as html
import pyslet.imsqtiv2p1 as qtiv2
import pyslet.imsmdv1p2p1 as imsmd

import core, common

import string
from types import StringTypes



class QTIObjectives(common.FlowMatContainer,core.QTIViewMixin):
	"""Represents the objectives element
	
::

	<!ELEMENT objectives (qticomment? , (material+ | flow_mat+))>

	<!ATTLIST objectives  %I_View; >"""
	XMLNAME='objectives'
	XMLCONTENT=xml.ElementContent
		
	def __init__(self,parent):
		common.FlowMatContainer.__init__(self,parent)
		core.QTIViewMixin.__init__(self)
		
	def MigrateV2(self,v2Item,log):
		"""Adds rubric representing these objectives to the given item's body"""
		rubric=v2Item.ChildElement(qtiv2.QTIItemBody).ChildElement(qtiv2.QTIRubricBlock)
		if self.view.lower()=='all':
			rubric.SetAttribute('view',(QTIObjectives.V2_VIEWALL))
		else:
			oldView=self.view.lower()
			view=QTIObjectives.V2_VIEWMAP.get(oldView,'author')
			if view!=oldView:
				log.append("Warning: changing view %s to %s"%(self.view,view))
			rubric.SetAttribute('view',view)
		# rubric is not a flow-container so we force inlines to be p-wrapped
		self.MigrateV2Content(rubric,html.BlockMixin,log)
				
	def LRMMigrateObjectives(self,lom,log):
		"""Adds educational description from these objectives."""
		description,lang=self.ExtractText()
		eduDescription=lom.ChildElement(imsmd.LOMEducational).ChildElement(imsmd.Description)
		eduDescription.AddString(lang,description)


class QTIRubric(common.FlowMatContainer,core.QTIViewMixin):
	"""Represents the rubric element.
	
::

	<!ELEMENT rubric (qticomment? , (material+ | flow_mat+))>
	
	<!ATTLIST rubric  %I_View; >"""
	XMLNAME='rubric'
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		common.FlowMatContainer.__init__(self,parent)
		core.QTIViewMixin.__init__(self)
	
	def MigrateV2(self,v2Item,log):
		if self.view.lower()=='all':
			log.append('Warning: rubric with view="All" replaced by <div> with class="rubric"')
			rubric=v2Item.ChildElement(qtiv2.QTIItemBody).ChildElement(html.Div,(qtiv2.IMSQTI_NAMESPACE,'div'))
			rubric.styleClass='rubric'
		else:
			rubric=v2Item.ChildElement(qtiv2.QTIItemBody).ChildElement(qtiv2.QTIRubricBlock)
			oldView=self.view.lower()
			view=QTIObjectives.V2_VIEWMAP.get(oldView,'author')
			if view!=oldView:
				log.append("Warning: changing view %s to %s"%(self.view,view))
			rubric.SetAttribute('view',view)
		# rubric is not a flow-container so we force inlines to be p-wrapped
		self.MigrateV2Content(rubric,html.BlockMixin,log)


class QTIItemRubric(QTIRubric):
	"""Represents the itemrubric element.
	
::

	<!ELEMENT itemrubric (material)>

	<!ATTLIST itemrubric  %I_View; >
	
	We are generous with this element, extending the allowable content model
	to make it equivalent to <rubric> which is a superset.  <itemrubric> was
	deprecated in favour of <rubric> with QTI v1.2
	"""
	XMLNAME='itemrubric'
	XMLCONTENT=xml.ElementContent


class QTIPresentation(common.FlowContainer,common.QTIPositionMixin):
	"""Represents the presentation element.
	
::

	<!ELEMENT presentation (qticomment? ,
		(flow |
			(material |
			response_lid |
			response_xy |
			response_str |
			response_num |
			response_grp |
			response_extension)+
			)
		)>
	
	<!ATTLIST presentation  %I_Label;
							 xml:lang CDATA  #IMPLIED
							 %I_Y0;
							 %I_X0;
							 %I_Width;
							 %I_Height; >"""
	XMLNAME='presentation'
	XMLATTR_label='label'	
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		common.FlowContainer.__init__(self,parent)
		common.QTIPositionMixin.__init__(self)
		self.label=None
		
	def MigrateV2(self,v2Item,log):
		"""Presentation maps to the main content in itemBody."""
		itemBody=v2Item.ChildElement(qtiv2.QTIItemBody)
		if self.GotPosition():
			log.append("Warning: discarding absolute positioning information on presentation")
		if self.InlineChildren():
			p=itemBody.ChildElement(html.P,(qtiv2.IMSQTI_NAMESPACE,'p'))
			if self.label is not None:
				#p.label=self.label
				p.SetAttribute('label',self.label)
			self.MigrateV2Content(p,html.InlineMixin,log)
		elif self.label is not None:
			# We must generate a div to hold the label, we can't rely on owning the whole itemBody
			div=itemBody.ChildElement(html.Div,(qtiv2.IMSQTI_NAMESPACE,'div'))
			div.SetAttribute('label',self.label)
			# Although div will take an inline directly we force blocking at the top level
			self.MigrateV2Content(div,html.BlockMixin,log)
		else:
			# mixture or block children, force use of blocks
			self.MigrateV2Content(itemBody,html.BlockMixin,log)
		self.CleanHotspotImages(itemBody)
	
	def CleanHotspotImages(self,itemBody):
		"""Removes spurious img tags which represent images used in hotspotInteractions.
		
		Unfortunately we have to do this because images needed in hotspot interactions
		are often clumsily placed outside the response/render constructs.  Rather than
		fiddle around at the time we simply migrate the lot, duplicating the images
		in the hotspotInteractions.  When the itemBody is complete we do a grand tidy
		up to remove spurious images."""
		hotspots=[]
		itemBody.FindChildren((qtiv2.QTIHotspotInteraction,qtiv2.QTISelectPointInteraction),hotspots)
		images=[]
		itemBody.FindChildren(html.Img,images)
		for hs in hotspots:
			for img in images:
				# migrated images/hotspots will always have absolute URIs
				if img.src and str(img.src)==str(hs.Object.data):
					parent=img.parent
					parent.DeleteChild(img)
					if isinstance(parent,html.P) and len(list(parent.GetChildren()))==0:
						# It is always safe to remove a paragraph left empty by deleting an image
						# The chance are the paragraphic was created by us to house a matimage
						parent.parent.DeleteChild(parent)
					
		
	def IsInline(self):
		return False


class ResponseThing(common.ResponseCommon):
	"""Abstract class for the main response_* elements::
	
	<!ELEMENT response_* ((material | material_ref)? ,
		(render_choice | render_hotspot | render_slider | render_fib | render_extension) ,
		(material | material_ref)?)>

	<!ATTLIST response_*  %I_Rcardinality;
                         %I_Rtiming;
                         %I_Ident; >		
	"""
	XMLATTR_ident='ident'
	XMLATTR_rcardinality=('rCardinality',core.RCardinality.DecodeTitleValue,core.RCardinality.EncodeValue)
	XMLATTR_rtiming=('rTiming',core.ParseYesNo,core.FormatYesNo)	
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		common.ResponseCommon.__init__(self,parent)
		self.ident=None
		self.rCardinality=core.RCardinality.DEFAULT
		self.rTiming=False
		self.intro=[]
		self.prompt=[]
		self.inlinePrompt=True
		self.render=None
		self.outro=[]
		self.footer=[]
		self.inlineFooter=True

	def Material(self):
		child=common.Material(self)
		if self.render:
			self.outro.append(child)
		else:
			self.intro.append(child)
		return child
	
	def MaterialRef(self):
		child=common.MaterialRef(self)
		if self.render:
			self.outro.append(child)
		else:
			self.intro.append(child)
		return child
	
	def QTIRenderThing(self,childClass):
		child=childClass(self)
		self.render=child
		return child
		
	def QTIRenderExtension(self):
		child=QTIRenderExtension(self)
		self.render=child
		return child
	
	def GetChildren(self):
		for child in self.intro: yield child
		if self.render: yield self.render
		for child in self.outro: yield child

	def ContentChanged(self):
		if isinstance(self.render,QTIRenderFIB) and self.render.MixedModel():
			# use simplified prompt logic.
			self.prompt=self.intro
			self.inlintPrompt=True
			for child in self.prompt:
				if not child.IsInline():
					self.inlinePrompt=False
			self.footer=self.outro			
			self.inlineFooter=True
			for child in self.footer:
				if not child.IsInline():
					self.inlineFooter=False
		elif self.render:
			# all the material up to the first response_label is the prompt
			self.prompt=[]
			self.inlinePrompt=True
			renderChildren=self.render.GetLabelContent()
			for child in self.intro+renderChildren:
				#print child.__class__,child.xmlname
				if isinstance(child,QTIResponseLabel):
					break
				self.prompt.append(child)
				if not child.IsInline():
					self.inlinePrompt=False
			self.footer=[]
			self.inlineFooter=True
			foundLabel=False
			for child in renderChildren+self.outro:
				if isinstance(child,QTIResponseLabel):
					self.footer=[]
					self.inlineFooter=True
					foundLabel=True
					continue
				if foundLabel:
					self.footer.append(child)
					if not child.IsInline():
						self.inlineFooter=False
			
	def InlineChildren(self):
		return self.inlinePrompt and (self.render is None or self.render.IsInline()) and self.inlineFooter

	def GetBaseType(self,interaction):
		"""Returns the base type to use for the given interaction."""
		raise QTIUnimplementedError("BaseType selection for %s"%self.__class__.__name__)

	def MigrateV2Content(self,parent,childType,log):
		if self.inlinePrompt:
			interactionPrompt=self.prompt
		else:
			if childType is html.InlineMixin:
				raise QTIError("Unexpected attempt to inline interaction")
			interactionPrompt=None
			if isinstance(self.render,QTIRenderHotspot):
				div=parent.ChildElement(html.Div,(qtiv2.IMSQTI_NAMESPACE,'div'))
				common.ContentMixin.MigrateV2Content(self,div,html.FlowMixin,log,self.prompt)
				# Now we need to find any images and pass them to render hotspot instead
				# which we do by reusing the interactionPrompt (currently we only find
				# the first image).
				interactionPrompt=[]
				div.FindChildren(html.Img,interactionPrompt,1)
			else:
				common.ContentMixin.MigrateV2Content(self,parent,childType,log,self.prompt)
		if self.render:
			interactionList=self.render.MigrateV2Interaction(parent,childType,interactionPrompt,log)
			item=parent.FindParent(qtiv2.QTIAssessmentItem)
			if len(interactionList)>1 and self.rCardinality==core.RCardinality.Single:
				log.append("Error: unable to migrate a response with Single cardinality to a single interaction: %s"%self.ident) 
				interactionList=[]
				responseList=[]
			else:
				baseIdentifier=qtiv2.ValidateIdentifier(self.ident)
				responseList=[]
				if len(interactionList)>1:
					i=0
					for interaction in interactionList:
						i=i+1
						while True:
							rIdentifier="%s_%02i"%(baseIdentifier,i)
							if item is None or not item.IsDeclared(rIdentifier):
								break
						interaction.responseIdentifier=rIdentifier
						responseList.append(rIdentifier)
				elif interactionList:	
					interaction=interactionList[0]
					interaction.responseIdentifier=baseIdentifier
					responseList=[interaction.responseIdentifier]
			if item:
				for i,r in zip(interactionList,responseList):
					d=item.ChildElement(qtiv2.QTIResponseDeclaration)
					d.identifier=r
					d.cardinality=core.MigrateV2Cardinality(self.rCardinality)
					d.baseType=self.GetBaseType(interactionList[0])
					self.render.MigrateV2InteractionDefault(d,i)
					item.RegisterDeclaration(d)
				if len(responseList)>1:
					d=item.ChildElement(qtiv2.QTIOutcomeDeclaration)
					d.identifier=baseIdentifier
					d.cardinality=core.MigrateV2Cardinality(self.rCardinality)
					d.baseType=self.GetBaseType(interactionList[0])
					item.RegisterDeclaration(d)
					# now we need to fix this outcome up with a value in response processing
					selfItem=self.FindParent(QTIItem)
					if selfItem:
						for rp in selfItem.QTIResProcessing:
							rp._interactionFixup[baseIdentifier]=responseList
		# the footer is in no-man's land so we just back-fill
		common.ContentMixin.MigrateV2Content(self,parent,childType,log,self.footer)


class QTIResponseLId(ResponseThing):
	"""Represents the response_lid element::

	<!ELEMENT response_lid ((material | material_ref)? ,
		(render_choice | render_hotspot | render_slider | render_fib | render_extension) ,
		(material | material_ref)?)>

	<!ATTLIST response_lid  %I_Rcardinality;
                         %I_Rtiming;
                         %I_Ident; >
	"""
	XMLNAME='response_lid'
	
	def GetBaseType(self,interaction):
		"""We always return identifier for response_lid."""
		return qtiv2.BaseType.identifier

		
class QTIResponseXY(ResponseThing):
	"""Represents the response_xy element::

	<!ELEMENT response_xy ((material | material_ref)? ,
		(render_choice | render_hotspot | render_slider | render_fib | render_extension) ,
		(material | material_ref)?)>
	
	<!ATTLIST response_xy  %I_Rcardinality;
							%I_Rtiming;
							%I_Ident; >
	"""
	XMLNAME='response_xy'

	def GetBaseType(self,interaction):
		"""We always return identifier for response_lid."""
		if isinstance(interaction,qtiv2.QTISelectPointInteraction):
			return qtiv2.BaseType.point
		else:
			return ResponseThing.GetBaseType(self)


class QTIResponseStr(ResponseThing):
	"""Represents the response_str element.
	
::

	<!ELEMENT response_str ((material | material_ref)? ,
		(render_choice | render_hotspot | render_slider | render_fib | render_extension) ,
		(material | material_ref)?)>
	
	<!ATTLIST response_str  %I_Rcardinality;
							 %I_Ident;
							 %I_Rtiming; >
	"""
	XMLNAME='response_str'

	def GetBaseType(self,interaction):
		"""We always return string for response_str."""
		return qtiv2.BaseType.string


class QTIResponseNum(ResponseThing):
	"""Represents the response_num element.
	
::

	<!ELEMENT response_num ((material | material_ref)? ,
		(render_choice | render_hotspot | render_slider | render_fib | render_extension) ,
		(material | material_ref)?)>
	
	<!ATTLIST response_num  numtype         (Integer | Decimal | Scientific )  'Integer'
							 %I_Rcardinality;
							 %I_Ident;
							 %I_Rtiming; >
	"""
	XMLNAME='response_num'
	XMLATTR_numtype=('numType',core.NumType.DecodeTitleValue,core.NumType.EncodeValue)	
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		ResponseThing.__init__(self,parent)
		self.numType=core.NumType.Integer

	def GetBaseType(self,interaction):
		"""We always return string for response_str."""
		if self.numType==core.NumType.Integer:
			return qtiv2.BaseType.integer
		else:
			return qtiv2.BaseType.float


class QTIResponseGrp(core.QTIElement,common.ContentMixin):
	"""Represents the response_grp element.
	
::

	<!ELEMENT response_grp ((material | material_ref)? ,
		(render_choice | render_hotspot | render_slider | render_fib | render_extension) ,
		(material | material_ref)?)>
	
	<!ATTLIST response_grp  %I_Rcardinality;
							 %I_Ident;
							 %I_Rtiming; >
	"""
	XMLNAME='response_grp'
	XMLCONTENT=xml.ElementContent


class QTIResponseNA(core.QTIElement):
	"""Represents the response_na element.
	
::

	<!ELEMENT response_na ANY>"""
	XMLNAME='response_na'
	XMLCONTENT=xml.XMLMixedContent


class QTIRenderThing(core.QTIElement,common.ContentMixin):
	"""Abstract base class for all render_* objects::
	
	<!ELEMENT render_* ((material | material_ref | response_label | flow_label)* , response_na?)>	
	"""
	XMLCONTENT=xml.ElementContent

	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		common.ContentMixin.__init__(self)
		self.QTIResponseNA=None

	def Material(self):
		child=common.Material(self)
		self.contentChildren.append(child)
		return child
		
	def MaterialRef(self):
		child=common.MaterialRef(self)
		self.contentChildren.append(child)
		return child
		
	def QTIResponseLabel(self):
		child=QTIResponseLabel(self)
		self.contentChildren.append(child)
		return child
		
	def FlowLabel(self):
		child=common.FlowLabel(self)
		self.contentChildren.append(child)
		return child
		
	def GetChildren(self):
		for child in self.contentChildren: yield child
		if self.QTIResponseNA: yield self.QTIResponseNA
	
	def GetLabelContent(self):
		children=[]
		for child in self.contentChildren:
			if isinstance(child,common.FlowLabel):
				children=children+child.GetLabelContent()
			else:
				children.append(child)
		return children

	def IsInline(self):
		for child in self.GetLabelContent():
			if not child.IsInline():
				return False
		return True

	def MigrateV2Interaction(self,parent,childType,prompt,log):
		raise QTIUnimplementedError("%s x %s"%(self.parent.__class__.__name__,self.__class__.__name__))
		
	def MigrateV2InteractionDefault(self,parent,interaction):
		# Most interactions do not need default values.
		pass

		
class QTIRenderChoice(QTIRenderThing):
	"""Represents the render_choice element.
	
::

	<!ELEMENT render_choice ((material | material_ref | response_label | flow_label)* , response_na?)>
	
	<!ATTLIST render_choice  shuffle      (Yes | No )  'No'
							  %I_MinNumber;
							  %I_MaxNumber; >
	"""
	XMLNAME='render_choice'
	XMLATTR_maxnumber=('maxNumber',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_minnumber=('minNumber',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_shuffle=('shuffle',core.ParseYesNo,core.FormatYesNo)
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		QTIRenderThing.__init__(self,parent)
		self.shuffle=False
		self.minNumber=None
		self.maxNumber=None
	
	def IsInline(self):
		"""This always results in a block-like interaction."""
		return False
		
	def MigrateV2Interaction(self,parent,childType,prompt,log):
		"""Migrates this content to v2 adding it to the parent content node."""
		interaction=None
		if isinstance(self.parent,QTIResponseLId):
			if childType is html.InlineMixin:
				raise QTIError("Unexpected attempt to put block interaction in inline context")
			if self.parent.rCardinality==core.RCardinality.Ordered:
				raise QTIUnimplementedError("OrderInteraction")
			else:
				interaction=parent.ChildElement(qtiv2.QTIChoiceInteraction)
		else:		
			raise QTIUnimplementedError("%s x render_choice"%self.parent.__class__.__name__)
		if prompt:
			interactionPrompt=interaction.ChildElement(qtiv2.QTIPrompt)
			for child in prompt:
				child.MigrateV2Content(interactionPrompt,html.InlineMixin,log)			
		if self.minNumber is not None:
			interaction.minChoices=self.minNumber
		if self.maxNumber is not None:
			interaction.maxChoices=self.maxNumber
		interaction.shuffle=self.shuffle
		for child in self.GetLabelContent():
			if isinstance(child,QTIResponseLabel):
				child.MigrateV2SimpleChoice(interaction,log)
		return [interaction]

		
class QTIRenderHotspot(QTIRenderThing):
	"""Represents the render_hotspot element.
	
::

	<!ELEMENT render_hotspot ((material | material_ref | response_label | flow_label)* , response_na?)>
	
	<!ATTLIST render_hotspot  %I_MaxNumber;
							   %I_MinNumber;
							   showdraw     (Yes | No )  'No' >
	"""
	XMLNAME='render_hotspot'
	XMLATTR_maxnumber=('maxNumber',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_minnumber=('minNumber',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_showdraw=('showDraw',core.ParseYesNo,core.FormatYesNo)
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		QTIRenderThing.__init__(self,parent)
		self.minNumber=None
		self.maxNumber=None
		self.showDraw=False
	
	def IsInline(self):
		"""This always results in a block-like interaction."""
		return False

	def MigrateV2Interaction(self,parent,childType,prompt,log):
		"""Migrates this content to v2 adding it to the parent content node."""
		interaction=None
		if isinstance(self.parent,QTIResponseLId):
			if self.parent.rCardinality==core.RCardinality.Ordered:
				raise QTIUnimplementedError("GraphicOrderInteraction")
			else:
				interaction=parent.ChildElement(qtiv2.QTIHotspotInteraction)
		elif isinstance(self.parent,QTIResponseXY):
			if self.parent.rCardinality==core.RCardinality.Ordered:
				raise QTIUnimplementedError('response_xy x render_hotspot')
			else:
				interaction=parent.ChildElement(qtiv2.QTISelectPointInteraction)
		else:
			raise QTIUnimplementedError("%s x render_hotspot"%self.parent.__class__.__name__)
		if self.showDraw:
			log.append('Warning: ignoring showdraw="Yes", what did you really want to happen?')
		if self.minNumber is not None:
			interaction.minChoices=self.minNumber
		if self.maxNumber is not None:
			interaction.maxChoices=self.maxNumber
		labels=[]
		self.FindChildren(QTIResponseLabel,labels)
		# prompt is either a single <img> tag we already migrated or.. a set of inline
		# objects that are still to be migrated (and which should contain the hotspot image).
		img=None
		interactionPrompt=None
		hotspotImage=interaction.ChildElement(html.Object,(qtiv2.IMSQTI_NAMESPACE,'object'))
		if prompt:
			if not isinstance(prompt[0],html.Img):					
				interactionPrompt=interaction.ChildElement(qtiv2.QTIPrompt)
				for child in prompt:
					child.MigrateV2Content(interactionPrompt,html.InlineMixin,log)
				prompt=[]
				interactionPrompt.FindChildren(html.Img,prompt,1)				
		if prompt:
			# now the prompt should be a list containing a single image to use as the hotspot
			img=prompt[0]
			hotspotImage.data=img.src
			hotspotImage.height=img.height
			hotspotImage.width=img.width
			if img.src:
				# Annoyingly, Img throws away mime-type information from matimage
				images=[]
				self.parent.FindChildren(common.QTIMatImage,images,1)
				if images and images[0].uri:
					# Check that this is the right image in case img was embedded in QTIMatText
					if str(images[0].ResolveURI(images[0].uri))==str(img.ResolveURI(img.src)):
						hotspotImage.type=images[0].imageType
			for child in labels:
				if isinstance(child,QTIResponseLabel):
					child.MigrateV2HotspotChoice(interaction,log)
			return [interaction]
		else:
			# tricky, let's start by getting all the matimage elements in the presentation
			images=[]
			presentation=self.FindParent(QTIPresentation)
			if presentation:
				presentation.FindChildren(common.QTIMatImage,images)
			hsi=[]
			if len(images)==1:
				# Single image that must have gone AWOL
				hsi.append((images[0],labels))
			else:
				# multiple images are scanned for those at fixed positions in the presentation
				# which are hit by a hotspot (interpreted relative to the presentation).
				for img in images:
					hits=[]
					for child in labels:
						if child.HotspotInImage(img):
							hits.append(child)
					if hits:
						# So some of our hotspots hit this image
						hsi.append((img,hits))
			if len(hsi)==0:	
				log.append("Error: omitting render_hotspot with no hotspot image")
				return []
			else:
				img,hits=hsi[0]
				hotspotImage.data=img.ResolveURI(img.uri)
				hotspotImage.type=img.imageType
				hotspotImage.height=html.LengthType(img.height)
				hotspotImage.width=html.LengthType(img.width)
				# it will get cleaned up later
				if len(hsi)>0:
					# Worst case: multiple images => multiple hotspot interactions
					if self.maxNumber is not None:
						log.append("Warning: multi-image hotspot maps to multiple interactions, maxChoices can no longer be enforced")
					interaction.minChoices=None
					for child in hits:
						child.MigrateV2HotspotChoice(interaction,log,img.x0,img.y0)
					interactionList=[interaction]
					for img,hits in hsi[1:]:
						interaction=parent.ChildElement(qtiv2.QTIHotspotInteraction)
						if self.maxNumber is not None:
							interaction.maxChoices=self.maxNumber
						hotspotImage=interaction.ChildElement(html.Object,(qtiv2.IMSQTI_NAMESPACE,'object'))
						hotspotImage.data=img.ResolveURI(img.uri)
						hotspotImage.type=img.imageType
						hotspotImage.height=html.LengthType(img.height)
						hotspotImage.width=html.LengthType(img.width)
						for child in hits:
							child.MigrateV2HotspotChoice(interaction,log,img.x0,img.y0)
						interactionList.append(interaction)
					return interactionList
				else:
					# Best case: single image that just went AWOL
					for child in labels:
						child.MigrateV2HotspotChoice(interaction,log,img.x0,img.y0)
					return [interaction]


V2ORIENTATION_MAP={
	core.Orientation.Horizontal:qtiv2.Orientation.horizontal,
	core.Orientation.Vertical:qtiv2.Orientation.vertical
	}

class QTIRenderSlider(QTIRenderThing):
	"""Represents the render_slider element.
	
::

	<!ELEMENT render_slider ((material | material_ref | response_label | flow_label)* , response_na?)>
	
	<!ATTLIST render_slider  orientation  (Horizontal | Vertical )  'Horizontal'
							  lowerbound  CDATA  #REQUIRED
							  upperbound  CDATA  #REQUIRED
							  step        CDATA  #IMPLIED
							  startval    CDATA  #IMPLIED
							  steplabel    (Yes | No )  'No'
							  %I_MaxNumber;
							  %I_MinNumber; >
	"""
	XMLNAME='render_slider'
	XMLATTR_orientation=('orientation',core.Orientation.DecodeTitleValue,core.Orientation.EncodeValue)
	XMLATTR_lowerbound=('lowerBound',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_upperbound=('upperBound',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_step=('step',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_startval=('startVal',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_steplabel=('stepLabel',core.ParseYesNo,core.FormatYesNo)
	XMLATTR_maxnumber=('maxNumber',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_minnumber=('minNumber',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLCONTENT=xml.ElementContent
		
	def __init__(self,parent):
		QTIRenderThing.__init__(self,parent)
		self.orientation=core.Orientation.Horizontal
		self.lowerBound=None
		self.upperBound=None
		self.step=None
		self.startVal=None
		self.stepLabel=False
		self.minNumber=None
		self.maxNumber=None

	def IsInline(self):
		"""This always results in a block-like interaction."""
		return False

	def MigrateV2Interaction(self,parent,childType,prompt,log):
		"""Migrates this content to v2 adding it to the parent content node."""
		interaction=None
		labels=[]
		self.FindChildren(QTIResponseLabel,labels)
		if self.maxNumber is None:
			maxChoices=len(labels)
		else:
			maxChoices=self.maxNumber
		if isinstance(self.parent,QTIResponseLId):
			if self.parent.rCardinality==core.RCardinality.Single:
				log.append("Warning: choice-slider replaced with choiceInteraction.slider")
				interaction=parent.ChildElement(qtiv2.QTIChoiceInteraction)
				interaction.styleClass='slider'
				interaction.minChoices=1
				interaction.maxChoices=1
			elif self.parent.rCardinality==core.RCardinality.Ordered:
				log.append("Error: ordered-slider replaced with orderInteraction.slider")
				raise QTIUnimplementedError("OrderInteraction")
			else:
				log.append("Error: multiple-slider replaced with choiceInteraction.slider")
				interaction=parent.ChildElement(qtiv2.QTIChoiceInteraction)
				interaction.styleClass='slider'
				if self.minNumber is not None:
					interaction.minChoices=self.minNumber
				else:
					interaction.minChoices=maxChoices
				interaction.maxChoices=maxChoices
			interaction.shuffle=False
			for child in labels:
				child.MigrateV2SimpleChoice(interaction,log)
		elif isinstance(self.parent,QTIResponseNum):
			if self.parent.rCardinality==core.RCardinality.Single:
				interaction=parent.ChildElement(qtiv2.SliderInteraction)
				interaction.lowerBound=float(self.lowerBound)
				interaction.upperBound=float(self.upperBound)
				if self.step is not None:
					interaction.step=self.step
				if self.orientation is not None:
					interaction.orientation=V2ORIENTATION_MAP[self.orientation]
				# startValues are handled below after the variable is declared
			else:
				raise QTIUnimplementedError("Multiple/Ordered SliderInteraction")
		else:	
			raise QTIUnimplementedError("%s x render_slider"%self.parent.__class__.__name__)
		if prompt:
			interactionPrompt=interaction.ChildElement(qtiv2.QTIPrompt)
			for child in prompt:
				child.MigrateV2Content(interactionPrompt,html.InlineMixin,log)			
		return [interaction]
		
	def MigrateV2InteractionDefault(self,declaration,interaction):
		# Most interactions do not need default values.
		if isinstance(interaction,qtiv2.SliderInteraction) and self.startVal is not None:
			value=declaration.ChildElement(qtiv2.QTIDefaultValue).ChildElement(qtiv2.QTIValue)
			if declaration.baseType==qtiv2.BaseType.integer:
				value.SetValue(xsi.EncodeInteger(self.startVal))
			elif declaration.baseType==qtiv2.BaseType.float:
				value.SetValue(xsi.EncodeFloat(self.startVal))
			else:
				# slider bound to something else?
				raise QTIError("Unexpected slider type for default: %s"%qtiv2.EncodeBaseType(declaration.baseType))


class QTIRenderFIB(QTIRenderThing):
	"""Represents the render_fib element.
	
::

	<!ELEMENT render_fib ((material | material_ref | response_label | flow_label)* , response_na?)>
	
	<!ATTLIST render_fib  encoding    CDATA  'UTF_8'
						   fibtype      (String | Integer | Decimal | Scientific )  'String'
						   rows        CDATA  #IMPLIED
						   maxchars    CDATA  #IMPLIED
						   prompt       (Box | Dashline | Asterisk | Underline )  #IMPLIED
						   columns     CDATA  #IMPLIED
						   %I_CharSet;
						   %I_MaxNumber;
						   %I_MinNumber; >
	"""
	XMLNAME='render_fib'
	XMLATTR_encoding='encoding'
	XMLATTR_fibtype=('fibType',core.FIBType.DecodeTitleValue,core.FIBType.EncodeValue)
	XMLATTR_rows=('rows',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_maxchars=('maxChars',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_prompt=('prompt',core.PromptType.DecodeTitleValue,core.PromptType.EncodeValue)
	XMLATTR_columns=('columns',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_charset='charset'		
	XMLATTR_maxnumber=('maxNumber',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_minnumber=('minNumber',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLCONTENT=xml.ElementContent
		
	def __init__(self,parent):
		QTIRenderThing.__init__(self,parent)
		self.encoding='UTF_8'
		self.fibType=core.FIBType.String
		self.rows=None
		self.maxChars=None
		self.prompt=None
		self.columns=None
		self.charset='ascii-us'
		self.minNumber=None
		self.maxNumber=None
		self.labels=[]
		
	def ContentChanged(self):
		self.labels=[]
		self.FindChildren(QTIResponseLabel,self.labels)

	def MixedModel(self):
		"""Indicates whether or not this FIB uses a mixed model or not.
		
		A mixed model means that render_fib is treated as a mixture of
		interaction and content elements.  In an unmixed model the render_fib is
		treated as a single block interaction with an optional prompt.
		
		If the render_fib contains content, followed by labels, then we treat
		it as a prompt + fib and return False
		
		If the render_fib contains a mixture of content and labels, then we
		return True
		
		If the render_fib contains no content at all we assume it needs to be
		mixed into the surrounding content and return True."""
		children=self.GetLabelContent()
		foundLabel=False
		foundContent=False
		for child in children:
			if isinstance(child,QTIResponseLabel):
				foundLabel=True
			elif foundLabel:
				# any content after the first label means mixed mode.
				return True
			else:
				foundContent=True
		return not foundContent
		
	def IsInline(self):
		if self.MixedModel():
			return QTIRenderThing.IsInline(self)
		else:
			return False
	
	def InlineFIBLabel(self):
		if self.rows is None or self.rows==1:
			return True
		else:
			return False

	def MigrateV2FIBLabel(self,label,parent,childType,log):
		if self.InlineFIBLabel() or childType is html.InlineMixin:
			interaction=parent.ChildElement(qtiv2.TextEntryInteraction)
		else:
			interaction=parent.ChildElement(qtiv2.ExtendedTextInteraction)
		if list(label.GetChildren()):
			log.append("Warning: ignoring content in render_fib.response_label")

	def MigrateV2Interaction(self,parent,childType,prompt,log):
		if self.InlineFIBLabel() or childType is html.InlineMixin:
			interactionType=qtiv2.TextEntryInteraction
		else:
			interactionType=qtiv2.ExtendedTextInteraction
		interactionList=[]
		parent.FindChildren(interactionType,interactionList)
		iCount=len(interactionList)
		# now migrate this object
		QTIRenderThing.MigrateV2Content(self,parent,childType,log)
		interactionList=[]
		parent.FindChildren(interactionType,interactionList)
		# ignore any pre-existing interactions of this type
		interactionList=interactionList[iCount:]
		if self.parent.rCardinality==core.RCardinality.Single and len(interactionList)>1:
			log.append("Warning: single response fib ignoring all but last <response_label>")
			for interaction in interactionList[:-1]:
				interaction.parent.DeleteChild(interaction)
			interactionList=interactionList[-1:]
		for interaction in interactionList:
			if self.maxChars is not None:
				interaction.expectedLength=self.maxChars
			elif self.rows is not None and self.columns is not None:
				interaction.expectedLength=self.rows*self.columns
			if interactionType is qtiv2.ExtendedTextInteraction:
				if self.rows is not None:
					interaction.expectedLines=self.rows
		return interactionList


class QTIRenderExtension(QTIRenderThing):
	"""Represents the render_extension element."""
	XMLNAME="render_extension"
	XMLCONTENT=xml.XMLMixedContent


class QTIResponseLabel(common.ResponseLabelCommon):
	"""Represents the response_label element.
	
::

	<!ELEMENT response_label (#PCDATA | qticomment | material | material_ref | flow_mat)*>
	
	<!ATTLIST response_label  rshuffle     (Yes | No )  'Yes'
							   rarea        (Ellipse | Rectangle | Bounded )  'Ellipse'
							   rrange       (Exact | Range )  'Exact'
							   labelrefid  CDATA  #IMPLIED
							   %I_Ident;
							   match_group CDATA  #IMPLIED
							   match_max   CDATA  #IMPLIED >
	"""
	XMLNAME='response_label'
	XMLATTR_ident='ident'
	XMLATTR_rshuffle=('rShuffle',core.ParseYesNo,core.FormatYesNo)
	XMLATTR_rarea=('rArea',core.Area.DecodeTitleValue,core.Area.EncodeValue)
	XMLCONTENT=xml.XMLMixedContent

	def __init__(self,parent):
		common.ResponseLabelCommon.__init__(self,parent)
		self.ident=''
		self.rShuffle=True
		self.rArea=None
	
	def ContentMixin(self,childClass):
		"""Although we inherit from the ContentMixin class we don't define
		custom setters to capture child elements in the contentChildren list
		because this element has mixed content - though in practice it really
		should have either data or element content."""
		return None

	def IsInline(self):
		"""Whether or not a response_label is inline depends on the context...
		
		render_choice: a choice is a block
		render_hotspot: at most a label on the image so treated as inline
		render_fib: always inline
		"""
		render=self.FindParent(QTIRenderThing)
		if isinstance(render,QTIRenderChoice):
			return False
		elif isinstance(render,QTIRenderHotspot):
			return True
		elif isinstance(render,QTIRenderFIB):
			return render.InlineFIBLabel()
		else:
			return self.InlineChildren()
		
	def InlineChildren(self):		
		for child in core.QTIElement.GetChildren(self):
			if type(child) in StringTypes:
				continue
			elif issubclass(child.__class__,common.ContentMixin):
				if child.IsInline():
					continue
				return False
			else:
				# QTIComment most likely
				continue
		return True
		
	def MigrateV2Content(self,parent,childType,log):
		"""Migrates this content to v2 adding it to the parent content node."""
		render=self.FindParent(QTIRenderThing)
		if isinstance(render,QTIRenderFIB):
			render.MigrateV2FIBLabel(self,parent,childType,log)
		
	def MigrateV2SimpleChoice(self,interaction,log):
		"""Migrate this label into a v2 simpleChoice in interaction."""
		choice=interaction.ChildElement(qtiv2.QTISimpleChoice)
		choice.identifier=qtiv2.ValidateIdentifier(self.ident)
		if isinstance(interaction,qtiv2.QTIChoiceInteraction) and interaction.shuffle:			
			choice.fixed=not self.rShuffle
		data=[]
		gotElements=False
		for child in core.QTIElement.GetChildren(self):
			if type(child) in StringTypes:
				if len(child.strip()):
					data.append(child)
			elif isinstance(child,common.QTIComment):
				continue
			else:
				gotElements=True
		if data and gotElements:
			log.append('Warning: ignoring PCDATA in <response_label>, "%s"'%string.join(data,' '))
		elif data:
			for d in data:
				choice.AddData(d)
		else:
			content=[]
			for child in core.QTIElement.GetChildren(self):
				if isinstance(child,common.ContentMixin):
					content.append(child)
			common.ContentMixin.MigrateV2Content(self,choice,html.FlowMixin,log,content)

	def MigrateV2HotspotChoice(self,interaction,log,xOffset=0,yOffset=0):
		"""Migrate this label into a v2 hotspotChoice in interaction."""
		if isinstance(interaction,qtiv2.QTISelectPointInteraction):
			log.append("Warning: ignoring response_label in selectPointInteraction (%s)"%self.ident)
			return
		choice=interaction.ChildElement(qtiv2.QTIHotspotChoice)
		choice.identifier=qtiv2.ValidateIdentifier(self.ident)
		# Hard to believe I know, but we sift the content of the response_label
		# into string data (which is parsed for coordinates) and elements which
		# have their text extracted for the hotspot label.
		lang,labelData,valueData=self.ParseValue()
		choice.shape,coords=core.MigrateV2AreaCoords(self.rArea,valueData,log)
		if xOffset or yOffset:
			qtiv2.OffsetShape(choice.shape,coords,xOffset,yOffset)
		for c in coords:
			choice.coords.values.append(html.LengthType(c))
		if lang is not None:
			choice.SetLang(lang)
		if labelData:
			choice.hotspotLabel=labelData
		
	def HotspotInImage(self,matImage):
		"""Tests this hotspot to see if it overlaps with matImage.
		
		The coordinates in the response label are interpreted relative to
		a notional 'stage' on which the presentation takes place.  If the
		image does not have X0,Y0 coordinates then it is ignored and
		we return 0.
		"""
		if matImage.x0 is None or matImage.y0 is None:
			return False
		if matImage.width is None or matImage.height is None:
			return False
		lang,label,value=self.ParseValue()
		shape,coords=core.MigrateV2AreaCoords(self.rArea,value,[])
		bounds=qtiv2.CalculateShapeBounds(shape,coords)
		if bounds[0]>matImage.x0+matImage.width or bounds[2]<matImage.x0:
			return False
		if bounds[1]>matImage.y0+matImage.height or bounds[3]<matImage.y0:
			return False
		return True
	
	def ParseValue(self):
		"""Returns lang,label,coords parsed from the value."""
		valueData=[]
		labelData=[]
		lang=None
		for child in self.GetChildren():
			if type(child) in StringTypes:
				valueData.append(child)
			else:
				childLang,text=child.ExtractText()
				if lang is None and childLang is not None:
					lang=childLang
				labelData.append(text)
		valueData=string.join(valueData,' ')
		labelData=string.join(labelData,' ')
		return lang,labelData,valueData


class QTIItem(common.CommentContainer,core.ObjectMixin):
	"""Represents the item element.
	
::

	<!ELEMENT item (qticomment?
		duration?
		itemmetadata?
		objectives*
		itemcontrol*
		itemprecondition*
		itempostcondition*
		(itemrubric | rubric)*
		presentation?
		resprocessing*
		itemproc_extension?
		itemfeedback*
		reference?)>

	<!ATTLIST item  maxattempts CDATA  #IMPLIED
		%I_Label;
		%I_Ident;
		%I_Title;
		xml:lang    CDATA  #IMPLIED >"""
	XMLNAME='item'
	XMLATTR_ident='ident'
	XMLATTR_label='label'
	XMLATTR_maxattempts='maxattempts'		
	XMLATTR_title='title'
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		common.CommentContainer.__init__(self,parent)
		self.maxattempts=None
		self.label=None
		self.ident=None
		self.title=None
		self.QTIDuration=None
		self.QTIItemMetadata=None
		self.QTIObjectives=[]
		self.QTIItemControl=[]
		self.QTIItemPrecondition=[]
		self.QTIItemPostcondition=[]
		self.QTIRubric=[]
		self.QTIPresentation=None
		self.QTIResProcessing=[]
		self.QTIItemProcExtension=None
		self.QTIItemFeedback=[]
		self.QTIReference=None
					
	def QTIItemRubric(self):
		"""itemrubric is deprecated in favour of rubric."""
		child=QTIItemRubric(self)
		self.QTIRubric.append(child)
		return child
		
	def GetChildren(self):
		for child in QTIComment.GetChildren(self): yield child
		if self.QTIDuration: yield self.QTIDuration
		if self.QTIItemMetadata: yield self.QTIItemMetadata
		for child in itertools.chain(
			self.QTIObjectives,
			self.QTIItemControl,
			self.QTIItemPreCondition,
			self.QTIPostCondition,
			self.QTIRubric):
			yield child
		if self.QTIPresentation: yield self.QTIPresentation
		for child in self.QTIResProcessing: yield child
		if self.QTIItemProcExtension: yield self.QTIItemProcExtension
		for child in self.QTIItemFeedback: yield child
		if self.QTIReference: yield self.QTIReference
	
	def MigrateV2(self,output):
		"""Converts this item to QTI v2
		
		For details, see QuesTestInterop.MigrateV2."""
		# First thing we do is initialize any fixups
		for rp in self.QTIResProcessing:
			rp._interactionFixup={}
		doc=qtiv2.QTIDocument(root=qtiv2.QTIAssessmentItem)
		item=doc.root
		lom=imsmd.LOM(None)
		log=[]
		ident=qtiv2.MakeValidNCName(self.ident)
		if self.ident!=ident:
			log.append("Warning: illegal NCName for ident: %s, replaced with: %s"%(self.ident,ident))
		item.identifier=ident
		title=self.title
		# may be specified in the metadata
		if self.QTIItemMetadata:
			mdTitles=self.QTIItemMetadata.metadata.get('title',())
		else:
			mdTitles=()
		if title:
			item.title=title
		elif mdTitles:
			item.title=mdTitles[0][0]
		else:
			item.title=ident
		if self.maxattempts is not None:
			log.append("Warning: maxattempts can not be controlled at item level, ignored: maxattempts='"+self.maxattempts+"'")
		if self.label:
			item.label=self.label
		lang=self.GetLang()
		item.SetLang(lang)
		general=lom.LOMGeneral()
		id=general.LOMIdentifier()
		id.SetValue(self.ident)
		if title:
			lomTitle=general.ChildElement(imsmd.LOMTitle)
			lomTitle=lomTitle.ChildElement(lomTitle.LangStringClass)
			lomTitle.SetValue(title)
			if lang:
				lomTitle.SetLang(lang)
		if mdTitles:
			if title:
				# If we already have a title, then we have to add qmd_title as description metadata
				# you may think qmd_title is a better choice than the title attribute
				# but qmd_title is an extension so the title attribute takes precedence
				i=0
			else:
				lomTitle=general.ChildElement(imsmd.LOMTitle)
				lomTitle=lomTitle.ChildElement(lomTitle.LangStringClass)
				lomTitle.SetValue(mdTitles[0][0])
				lang=mdTitles[0][1].ResolveLang()
				if lang:
					lomTitle.SetLang(lang)
				i=1
			for mdTitle in mdTitles[i:]:
				description=general.ChildElement(general.DescriptionClass)
				lomTitle=description.ChildElement(description.LangStringClass)
				lomTitle.SetValue(mdTitle[0])
				mdLang=mdTitle[1].ResolveLang()
				if mdLang:
					lomTitle.SetLang(mdLang)
		if self.QTIComment:
			# A comment on an item is added as a description to the metadata
			description=general.ChildElement(general.DescriptionClass)
			description.ChildElement(description.LangStringClass).SetValue(self.QTIComment.GetValue())
		if self.QTIDuration:
			log.append("Warning: duration is currently outside the scope of version 2: ignored "+self.QTIDuration.GetValue())
		if self.QTIItemMetadata:
			self.QTIItemMetadata.MigrateV2(doc,lom,log)
		for objective in self.QTIObjectives:
			if objective.view.lower()!='all':
				objective.MigrateV2(item,log)
			else:
				objective.LRMMigrateObjectives(lom,log)
		if self.QTIItemControl:
			log.append("Warning: itemcontrol is currently outside the scope of version 2")
		for rubric in self.QTIRubric:
			rubric.MigrateV2(item,log)
		if self.QTIPresentation:
			self.QTIPresentation.MigrateV2(item,log)
		if self.QTIResProcessing:
			if len(self.QTIResProcessing)>1:
				log.append("Warning: multiople <resprocessing> not supported, ignoring all but the last")
			self.QTIResProcessing[-1].MigrateV2(item,log)
		for feedback in self.QTIItemFeedback:
			feedback.MigrateV2(item,log)
		output.append((doc, lom, log))
		#print doc.root
