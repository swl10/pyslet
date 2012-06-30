#! /usr/bin/env python

import pyslet.xml20081126.structures as xml
import pyslet.xsdatatypes20041028 as xsi
import pyslet.html40_19991224 as html
import pyslet.imsqtiv2p1 as qtiv2
import pyslet.imsmdv1p2p1 as imsmd

import core

import string, itertools
from types import StringTypes

class QTICommentContainer(core.QTIElement):
	"""Basic element to represent all elements that can contain a comment as their first child::

		<!ELEMENT XXXXXXXXXXXX (qticomment? , ....... )>"""
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.QTIComment=None

	def GetChildren(self):
		if self.QTIComment: yield self.QTIComment


class QTIComment(core.QTIElement):
	"""This element contains the comments that are relevant to the host element.
	The comment is contained as a string::

		<!ELEMENT qticomment (#PCDATA)>	
		<!ATTLIST qticomment  xml:lang CDATA  #IMPLIED >"""
	XMLNAME='qticomment'
	XMLCONTENT=xml.XMLMixedContent


class Duration(core.QTIElement):
	"""The duration permitted for the completion of a particular activity. The
	duration is defined as per the ISO8601 standard. The information is entered
	as a string::

		<!ELEMENT duration (#PCDATA)>"""
	XMLNAME="duration"
	XMLCONTENT=xml.XMLMixedContent


class ContentMixin:
	"""Mixin class for handling all content-containing elements.
	
	This class is used by all elements that behave as content, the default
	implementation provides an additional contentChildren member that should
	be used to collect any content-like children."""

	def __init__(self):
		self.contentChildren=[]		#: the list of content children
	
	def ContentMixin(self,childClass):
		"""Creates a new ContentMixin child of this element.
		
		This factory method is called by the parser when it finds an element
		that is derived from ContentMixin.  By default we accept any type of
		content but derived classes override this behaviour to limit the range
		of elements to match their content models."""
		child=childClass(self)
		self.contentChildren.append(child)
		return child

	def GetContentChildren(self):
		"""Returns an iterable of the content children."""
		return iter(self.contentChildren)

	def IsInline(self):
		"""True if this element can be inlined, False if it is block level
		
		The default implementation returns True if all
		:py:attr:`contentChildren` can be inlined."""
		return self.InlineChildren()
		
	def InlineChildren(self):
		"""True if all of this element's :py:attr:`contentChildren` can all be inlined."""
		for child in self.contentChildren:
			if not child.IsInline():
				return False
		return True

	def ExtractText(self):
		"""Returns a tuple of (<text string>, <lang>).
		
		Sometimes it is desirable to have a plain text representation of a
		content object.  For example, an element may permit arbitrary content
		but a synopsis is required to set a metadata value.
		
		Our algorithm for determining the language of the text is to first check
		if the language has been specified for the context.  If it has then that
		language is used.  Otherwise the first language attribute encountered in
		the content is used as the language.  If no language is found then None
		is returned as the second value."""
		result=[]
		lang=self.GetLang()
		for child in self.contentChildren:
			childText,childLang=child.ExtractText()
			if lang is None:
				lang=childLang
			if childText:
				result.append(childText.strip())
		return string.join(result,' '),lang
	
	def MigrateV2Content(self,parent,childType,log,children=None):
		"""Migrates this content element to QTIv2.
		
		The resulting QTIv2 content is added to *parent*.
		
		*childType* indicates whether the context allows block, inline or a
		mixture of element content types (flow).  It is set to one of the
		following HTML classes: :py:class:`pyslet.html40_19991224.BlockMixin`,
		:py:class:`pyslet.html40_19991224.InlineMixin` or
		:py:class:`pyslet.html40_19991224.FlowMixin`.

		The default implementation adds each of *children* or, if *children* is
		None, each of the local :py:attr:`contentChildren`.  The algorithm
		handles flow elements by creating <p> elements where the context
		permits.  Nested flows are handled by the addition of <br/>."""
		if children is None:
			children=self.contentChildren
		if childType is html.InlineMixin or (childType is html.FlowMixin and self.InlineChildren()):
			# We can only hold inline children, raise an error if find anything else
			brBefore=brAfter=False
			firstItem=True
			for child in children:
				if isinstance(child,FlowMixin):
					brBefore=not firstItem
					brAfter=True
				elif brAfter:
					# we only honour brAfter if flow is followed by something other than flow
					parent.ChildElement(html.Br,(qtiv2.core.IMSQTI_NAMESPACE,'br'))
					brAfter=False				
				if brBefore:
					parent.ChildElement(html.Br,(qtiv2.core.IMSQTI_NAMESPACE,'br'))
					brBefore=False
				# we force InlineMixin here to prevent unnecessary checks on inline status
				child.MigrateV2Content(parent,html.InlineMixin,log)
				firstItem=False
		else:
			# childType is html.BlockMixin or html.FlowMixin and we have a mixture of inline/block children
			p=None
			brBefore=False
			brAfter=False
			for child in children:
				try:
					if child.IsInline():
						if brAfter:
							p.ChildElement(html.Br,(qtiv2.core.IMSQTI_NAMESPACE,'br'))
							brAfter=False
						if isinstance(child,FlowMixin):
							brBefore=brAfter=True
						if p is None:
							p=parent.ChildElement(html.P,(qtiv2.core.IMSQTI_NAMESPACE,'p'))
							brBefore=False
						if brBefore:
							p.ChildElement(html.Br)
							brBefore=False
						child.MigrateV2Content(p,html.InlineMixin,log)
					else:
						# stop collecting inlines
						p=None
						brBefore=brAfter=False
						child.MigrateV2Content(parent,html.BlockMixin,log)
				except AttributeError,e:
					print e
					raise core.QTIError("Error: unsupported QTI v1 content element "+child.xmlname)


class Material(QTICommentContainer,ContentMixin):
	"""This is the container for any content that is to be displayed by the
	question-engine. The supported content types are text (emphasized or not),
	images, audio, video, application and applet. The content can be internally
	referenced to avoid the need for duplicate copies. Alternative information
	can be defined - this is used if the primary content cannot be displayed::

		<!ELEMENT material (qticomment? , (mattext | matemtext | matimage |
			mataudio | matvideo | matapplet | matapplication | matref | matbreak
			| mat_extension)+ , altmaterial*)>
		<!ATTLIST material
			label CDATA  #IMPLIED
			xml:lang CDATA  #IMPLIED >"""
	XMLNAME='material'
	XMLATTR_label='label'
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		QTICommentContainer.__init__(self,parent)
		ContentMixin.__init__(self)
		self.AltMaterial=[]
		self.label=None
	
	def ContentMixin(self,childClass):
		if issubclass(childClass,MatThingMixin):
			return ContentMixin.ContentMixin(self,childClass)
		else:
			raise TypeError

	def GetChildren(self):
		return itertools.chain(
			QTICommentContainer.GetChildren(self),
			ContentMixin.GetContentChildren(self))
	
	def ContentChanged(self):
		if self.label:
			doc=self.GetDocument()
			if doc:
				doc.RegisterMaterial(self)
		QTICommentContainer.ContentChanged(self)


class AltMaterial(QTICommentContainer,ContentMixin):
	"""This is the container for alternative content. This content is to be
	displayed if, for whatever reason, the primary content cannot be rendered.
	Alternative language implementations of the host <material> element are also
	supported using this structure::

		<!ELEMENT altmaterial (qticomment? ,
			(mattext | matemtext | matimage | mataudio | matvideo |
			matapplet | matapplication | matref | matbreak | mat_extension)+)>
		<!ATTLIST altmaterial  xml:lang CDATA  #IMPLIED >"""
	XMLNAME="material_ref"
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		QTICommentContainer.__init__(self,parent)
		ContentMixin.__init__(self)
	
	def ContentMixin(self,childClass):
		if issubclass(childClass,MatThingMixin):
			return ContentMixin.ContentMixin(self,childClass)
		else:
			raise TypeError

	def GetChildren(self):
		return itertools.chain(
			QTICommentContainer.GetChildren(self),
			ContentMixin.GetContentChildren(self))


class MatThingMixin(ContentMixin):
	"""An abstract class used to help identify the mat* elements."""
	pass


class PositionMixin:
	"""Mixin to define the positional attributes
	::
		
		width	CDATA  #IMPLIED
		height	CDATA  #IMPLIED
		y0		CDATA  #IMPLIED
		x0		CDATA  #IMPLIED"""
	XMLATTR_height=('height',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_width=('width',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_x0=('x0',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLATTR_y0=('y0',xsi.DecodeInteger,xsi.EncodeInteger)
	
	def __init__(self):
		self.x0=None
		self.y0=None
		self.width=None
		self.height=None

	def GotPosition(self):
		return self.x0 is not None or self.y0 is not None or self.width is not None or self.height is not None


class MatText(core.QTIElement,PositionMixin,MatThingMixin):
	"""The <mattext> element contains any text that is to be displayed to the users
	::
		
		<!ELEMENT mattext (#PCDATA)>	
		<!ATTLIST mattext
			texttype    CDATA  'text/plain'
			label		CDATA  #IMPLIED
			charset		CDATA  'ascii-us'
			uri			CDATA  #IMPLIED
			xml:space	(preserve | default )  'default'
			xml:lang	CDATA  #IMPLIED
			entityref	ENTITY  #IMPLIED
			width		CDATA  #IMPLIED
			height		CDATA  #IMPLIED
			y0			CDATA  #IMPLIED
			x0			CDATA  #IMPLIED >"""
	XMLNAME='mattext'
	XMLATTR_label='label'
	XMLATTR_charset='charset'
	XMLATTR_uri=('uri',html.DecodeURI,html.EncodeURI)
	XMLATTR_texttype='texttype'				
	XMLCONTENT=xml.XMLMixedContent
	
	SymbolCharsets={
		'greek':True,
		'symbol':True
		}
		
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		PositionMixin.__init__(self)
		MatThingMixin.__init__(self)
		self.texttype='text/plain'
		self.label=None
		self.charset='ascii-us'
		self.uri=None
		self.matChildren=[]
		self.inlineWrapper=None		#: an inline html object used to wrap inline elements
		
	def ContentChanged(self):
		if self.label:
			doc=self.GetDocument()
			if doc:
				doc.RegisterMatThing(self)
		if self.texttype=='text/html':
			if self.uri:
				# The content is external, load it up
				uri=self.ResolveURI(self.uri)
				try:
					e=xml.XMLEntity(uri)
				except http.HTTP2616Exception,e:
					e=xml.XMLEntity(unicode(e))
			else:
				uri=self.ResolveBase()
				try:
					value=self.GetValue()
				except xml.XMLMixedContentError:
					# Assume that the element content was not protected by CDATA
					value=[]
					for child in self.GetChildren():
						value.append(unicode(child))
					value=string.join(value,'')
				if value:
					e=xml.XMLEntity(value)
			doc=html.XHTMLDocument(baseURI=uri)
			doc.ReadFromEntity(e)
			self.matChildren=list(doc.root.Body.GetChildren())
			if len(self.matChildren)==1 and isinstance(self.matChildren[0],html.Div):
				div=self.matChildren[0]
				if div.styleClass is None:
					# a single div with no style class is removed...
					self.matChildren=list(div.GetChildren())
		elif self.texttype=='text/rtf':
			# parse the RTF content
			raise QTIUnimplementedError

	def IsInline(self):
		if self.texttype=='text/plain':
			return True
		elif self.texttype=='text/html':
			# we are inline if all elements in matChildren are inline
			for child in self.matChildren:
				if type(child) in StringTypes or isinstance(child,html.InlineMixin):
					continue
				else:
					return False
			return True
		else:
			raise QTIUnimplementedError(self.texttype)
			
	def ExtractText(self):
		if self.matChildren:
			# we need to extract the text from these children
			results=[]
			para=[]
			for child in self.matChildren:
				if type(child) in StringTypes:
					para.append(child)
				elif isinstance(child,html.InlineMixin):
					para.append(child.RenderText())
				else:
					if para:
						results.append(string.join(para,''))
						para=[]
					results.append(child.RenderText())
			if para:
				results.append(string.join(para,''))
			return string.join(results,'\n\n'),self.ResolveLang()
		else:
			return self.GetValue(),self.ResolveLang()

	def MigrateV2Content(self,parent,childType,log):
		if self.texttype=='text/plain':
			data=self.GetValue(True)
			if self.charset.lower() in MatText.SymbolCharsets:
				# this data is in the symbol font, translate it
				# Note that the first page of unicode is the same as iso-8859-1
				data=data.encode('iso-8859-1').decode('apple-symbol')				
			lang=self.GetLang()
			if lang or self.label:
				if childType is html.BlockMixin:
					span=parent.ChildElement(html.P,(qtiv2.core.IMSQTI_NAMESPACE,'p'))
					if self.inlineWrapper:
						span=span.ChildElement(self.inlineWrapper,(qtiv2.core.IMSQTI_NAMESPACE,self.inlineWrapper.XMLNAME[1]))
				elif self.inlineWrapper:
					span=parent.ChildElement(self.inlineWrapper,(qtiv2.core.IMSQTI_NAMESPACE,self.inlineWrapper.XMLNAME[1]))
				else:
					span=parent.ChildElement(html.Span,(qtiv2.core.IMSQTI_NAMESPACE,'span'))
				if lang:
					span.SetLang(lang)
				if self.label:
					#span.label=self.label
					span.SetAttribute('label',self.label)
				# force child elements to render as inline XML
				span.AddData(data)
			elif childType is html.BlockMixin:
				p=parent.ChildElement(html.P,(qtiv2.core.IMSQTI_NAMESPACE,'p'))
				if self.inlineWrapper:
					p=p.ChildElement(self.inlineWrapper,(qtiv2.core.IMSQTI_NAMESPACE,self.inlineWrapper.XMLNAME[1]))
				p.AddData(data)
			else:
				# inline or flow, just add the text directly...
				if self.inlineWrapper:
					addNode=parent.ChildElement(self.inlineWrapper,(qtiv2.core.IMSQTI_NAMESPACE,self.inlineWrapper.XMLNAME[1]))
				else:
					addNode=parent
				parent.AddData(data)
		elif self.texttype=='text/html':		
			if childType is html.BlockMixin or (childType is html.FlowMixin and not self.IsInline()):
				# Block or mixed-up flow, wrap all text and inline elements in p
				p=None
				for child in self.matChildren:
					if type(child) in StringTypes or isinstance(child,html.InlineMixin):
						if p is None:
							p=parent.ChildElement(html.P,(qtiv2.core.IMSQTI_NAMESPACE,'p'))
							if self.inlineWrapper:
								p=p.ChildElement(self.inlineWrapper,(qtiv2.core.IMSQTI_NAMESPACE,self.inlineWrapper.XMLNAME[1]))
						if type(child) in StringTypes:
							p.AddData(child)
						else:
							newChild=child.Copy(p)
							qtiv2.FixHTMLNamespace(newChild)															
					else:
						# stop collecting inlines
						p=None
						if self.inlineWrapper:
							log.append('Warning: block level elements in text/html cannot be wrapped with <%s>'%self.inlineWrapper.XMLNAME[1])
						newChild=child.Copy(parent)
						qtiv2.FixHTMLNamespace(newChild)														
			else:
				# Flow context (with only inline children) or inline context
				if self.inlineWrapper:
					addNode=parent.ChildElement(self.inlineWrapper,(qtiv2.core.IMSQTI_NAMESPACE,self.inlineWrapper.XMLNAME[1]))
				else:
					addNode=parent
				for child in self.matChildren:
					if type(child) in StringTypes:
						addNode.AddData(child)
					else:
						newChild=child.Copy(addNode)
						qtiv2.FixHTMLNamespace(newChild)
		else:
			raise QTIUnimplementedError


class MatEmText(MatText):
	"""The <matemtext> element contains any emphasized text that is to be
	displayed to the users. The type of emphasis is dependent on the
	question-engine rendering the text::

		<!ELEMENT matemtext (#PCDATA)>	
		<!ATTLIST matemtext
			texttype	CDATA  'text/plain'
			label		CDATA  #IMPLIED
			charset		CDATA  'ascii-us'
			uri			CDATA  #IMPLIED
			xml:space	(preserve | default )  'default'
			xml:lang	CDATA  #IMPLIED
			entityref	ENTITY  #IMPLIED
			width		CDATA  #IMPLIED
			height		CDATA  #IMPLIED
			y0			CDATA  #IMPLIED
			x0			CDATA  #IMPLIED >"""
	XMLNAME="matemtext"
	XMLCONTENT=xml.XMLMixedContent
	
	def __init__(self,parent):
		MatText.__init__(self,parent)
		self.inlineWrapper=html.Em


class MatBreak(core.QTIElement,MatThingMixin):
	"""The element that is used to insert a break in the flow of the associated
	material. The nature of the 'break' is dependent on the display-rendering
	engine::

		<!ELEMENT matbreak EMPTY>"""
	XMLNAME="matbreak"
	XMLCONTENT=xml.XMLEmpty
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		MatThingMixin.__init__(self)
				
	def IsInline(self):
		return True
			
	def ExtractText(self):
		"""Returns a simple line break"""
		return "\n"

	def MigrateV2Content(self,parent,childType,log):
		if childType in (html.InlineMixin,html.FlowMixin):
			parent.ChildElement(html.Br,(qtiv2.core.IMSQTI_NAMESPACE,'br'))
		else:
			# a break in a group of block level elements is ignored
			pass			


class MatImage(core.QTIElement,PositionMixin,MatThingMixin):
	"""The <matimage> element is used to contain image content that is to be
	displayed to the users::

		<!ELEMENT matimage (#PCDATA)>	
		<!ATTLIST matimage
			imagtype    CDATA  'image/jpeg'
			label		CDATA  #IMPLIED
			height		CDATA  #IMPLIED
			uri			CDATA  #IMPLIED
			embedded	CDATA  'base64'
			width		CDATA  #IMPLIED
			y0			CDATA  #IMPLIED
			x0			CDATA  #IMPLIED
			entityref	ENTITY #IMPLIED >"""
	XMLNAME="matimage"
	XMLATTR_imagtype='imageType'
	XMLATTR_label='label'
	XMLATTR_uri=('uri',html.DecodeURI,html.EncodeURI)
	XMLATTR_embedded='embedded'
	XMLCONTENT=xml.XMLMixedContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		PositionMixin.__init__(self)
		MatThingMixin.__init__(self)
		self.imageType='image/jpeg'
		self.label=None
		self.uri=None
		self.embedded='base64'
				
	def IsInline(self):
		return True
			
	def ExtractText(self):
		"""We cannot extract text from matimage so we return a simple string."""
		return "[image]"

	def MigrateV2Content(self,parent,childType,log):
		if self.uri is None:
			raise QTIUnimplementedError("inclusion of inline images")
		if childType is html.BlockMixin:
			# We must wrap this img in a <p>
			p=parent.ChildElement(html.P,(qtiv2.core.IMSQTI_NAMESPACE,'p'))
			img=p.ChildElement(html.Img,(qtiv2.core.IMSQTI_NAMESPACE,'img'))
		else:
			img=parent.ChildElement(html.Img,(qtiv2.core.IMSQTI_NAMESPACE,'img'))
		img.src=self.ResolveURI(self.uri)
		if self.width is not None:
			img.width=html.LengthType(self.width)
		if self.height is not None:
			img.height=html.LengthType(self.height)


class MatAudio(core.QTIElement,MatThingMixin):
	"""The <mataudio> element is used to contain audio content that is to be
	displayed to the users::

		<!ELEMENT mataudio (#PCDATA)>	
		<!ATTLIST mataudio
			audiotype	CDATA  'audio/base'
			label		CDATA  #IMPLIED
			uri			CDATA  #IMPLIED
			embedded	CDATA  'base64'
			entityref	ENTITY  #IMPLIED >"""
	XMLNAME="mataudio"
	XMLCONTENT=xml.XMLMixedContent

	XMLATTR_audiotype='audioType'
	XMLATTR_label='label'
	XMLATTR_uri=('uri',html.DecodeURI,html.EncodeURI)
	XMLATTR_embedded='embedded'
	XMLCONTENT=xml.XMLMixedContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		MatThingMixin.__init__(self)
		self.audioType='audio/base'
		self.label=None
		self.uri=None
		self.embedded='base64'
		
	def IsInline(self):
		return True
			
	def ExtractText(self):
		"""We cannot extract text from mataudio so we return a simple string."""
		return "[sound]"

	def MigrateV2Content(self,parent,childType,log):
		if self.uri is None:
			raise QTIUnimplementedError("inclusion of inline audio")
		if childType is html.BlockMixin:
			# We must wrap this object in a <p>
			p=parent.ChildElement(html.P,(qtiv2.core.IMSQTI_NAMESPACE,'p'))
			obj=p.ChildElement(html.Object,(qtiv2.core.IMSQTI_NAMESPACE,'object'))
		else:
			obj=parent.ChildElement(html.Object,(qtiv2.core.IMSQTI_NAMESPACE,'object'))		
		obj.data=self.ResolveURI(self.uri)
		obj.type=self.audioType


class MatVideo(core.QTIElement,PositionMixin,MatThingMixin):
	"""The <matvideo> element is used to contain video content that is to be
	displayed to the users::

		<!ELEMENT matvideo (#PCDATA)>	
		<!ATTLIST matvideo
			videotype	CDATA  'video/avi'
			label		CDATA  #IMPLIED
			uri			CDATA  #IMPLIED
			width		CDATA  #IMPLIED
			height		CDATA  #IMPLIED
			y0			CDATA  #IMPLIED
			x0			CDATA  #IMPLIED
			embedded	CDATA  'base64'
			entityref	ENTITY  #IMPLIED >"""
	XMLNAME="matvideo"
	XMLCONTENT=xml.XMLMixedContent
	XMLATTR_videotype='videoType'
	XMLATTR_label='label'
	XMLATTR_uri=('uri',html.DecodeURI,html.EncodeURI)
	XMLATTR_embedded='embedded'
	XMLCONTENT=xml.XMLMixedContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		MatThingMixin.__init__(self)
		PositionMixin.__init__(self)
		self.videoType='video/avi'
		self.label=None
		self.uri=None
		self.embedded='base64'
		
	def IsInline(self):
		return True
			
	def ExtractText(self):
		"""We cannot extract text from matvideo so we return a simple string."""
		return "[video]"

	def MigrateV2Content(self,parent,childType,log):
		if self.uri is None:
			raise QTIUnimplementedError("inclusion of inline video")
		if childType is html.BlockMixin:
			# We must wrap this object in a <p>
			p=parent.ChildElement(html.P,(qtiv2.core.IMSQTI_NAMESPACE,'p'))
			obj=p.ChildElement(html.Object,(qtiv2.core.IMSQTI_NAMESPACE,'object'))
		else:
			obj=parent.ChildElement(html.Object,(qtiv2.core.IMSQTI_NAMESPACE,'object'))		
		obj.data=self.ResolveURI(self.uri)
		obj.type=self.videoType


class MatApplet(core.QTIElement,PositionMixin,MatThingMixin):
	"""The <matapplet> element is used to contain applet content that is to be
	displayed to the users. Parameters that are to be passed to the applet being
	launched should be enclosed in a CDATA block within the content of the
	<matapplet> element::

		<!ELEMENT matapplet (#PCDATA)>	
		<!ATTLIST matapplet
			label		CDATA  #IMPLIED
			uri			CDATA  #IMPLIED
			y0			CDATA  #IMPLIED
			height		CDATA  #IMPLIED
			width		CDATA  #IMPLIED
			x0			CDATA  #IMPLIED
			embedded	CDATA  'base64'
			entityref	ENTITY  #IMPLIED >"""
	XMLNAME="matapplet"
	XMLCONTENT=xml.XMLMixedContent
	XMLATTR_label='label'
	XMLATTR_uri=('uri',html.DecodeURI,html.EncodeURI)
	XMLATTR_embedded='embedded'
	XMLCONTENT=xml.XMLMixedContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		MatThingMixin.__init__(self)
		PositionMixin.__init__(self)
		self.label=None
		self.uri=None
		self.embedded='base64'
		
	def IsInline(self):
		return True
			
	def ExtractText(self):
		"""We cannot extract text from matapplet so we return a simple string."""
		return "[applet]"

	def MigrateV2Content(self,parent,childType,log):
		raise QTIUnimplementedError("matapplet")


class MatApplication(core.QTIElement,MatThingMixin):
	"""The <matapplication> element is used to contain application content that
	is to be displayed to the users. Parameters that are to be passed to the
	application being launched should be enclosed in a CDATA block within the
	content of the <matapplication> element::

		<!ELEMENT matapplication (#PCDATA)>	
		<!ATTLIST matapplication
			apptype		CDATA  #IMPLIED
			label		CDATA  #IMPLIED
			uri			CDATA  #IMPLIED
			embedded	CDATA  'base64'
			entityref	ENTITY  #IMPLIED >"""
	XMLNAME="matapplication"
	XMLCONTENT=xml.XMLMixedContent
	XMLATTR_apptype='appType'
	XMLATTR_label='label'
	XMLATTR_uri=('uri',html.DecodeURI,html.EncodeURI)
	XMLATTR_embedded='embedded'
	XMLCONTENT=xml.XMLMixedContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		MatThingMixin.__init__(self)
		self.appType=None
		self.label=None
		self.uri=None
		self.embedded='base64'
		
	def IsInline(self):
		return True
			
	def ExtractText(self):
		"""We cannot extract text from matapplication so we return a simple string."""
		return "[application]"

	def MigrateV2Content(self,parent,childType,log):
		raise QTIUnimplementedError("matapplication")


class MatRef(MatThingMixin,core.QTIElement):
	"""The <matref> element is used to contain a reference to the required
	material. This material will have had an identifier assigned to enable such
	a reference to be reconciled when the instance is parsed into the system.
	<matref> should only be used to reference a material component and not a
	<material> element (the element <material_ref> should be used for the
	latter)::

		<!ELEMENT matref EMPTY>	
		<!ATTLIST matref linkrefid CDATA  #REQUIRED >"""
	XMLNAME="matref"
	XMLATTR_linkrefid='linkRefID'
	XMLCONTENT=xml.XMLEmpty

	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		MatThingMixin.__init__(self)
		self.linkRefID=None
		
	def FindMatThing(self):
		matThing=None
		doc=self.GetDocument()
		if doc:
			matThing=doc.FindMatThing(self.linkRefID)
		if matThing is None:
			raise core.QTIError("Bad matref: %s"%str(self.linkRefID))
		return matThing
		
	def IsInline(self):
		return self.FindMatThing().IsInline()
	
	def ExtractText(self):
		return self.FindMatThing().ExtractText()
	
	def MigrateV2Content(self,parent,childType,log):
		self.FindMatThing().MigrateV2Content(parent,childType,log)


class MatExtension(core.QTIElement,MatThingMixin):
	"""The extension facility to enable proprietary types of material to be
	included with the corresponding data object::

		<!ELEMENT mat_extension ANY>"""
	XMLNAME="mat_extension"
	XMLCONTENT=xml.XMLMixedContent


class FlowMixin:
	"""Mix-in class to identify all flow elements::
	
		( flow | flow_mat | flow_label)"""
	pass

	
class FlowMatContainer(QTICommentContainer,ContentMixin):
	"""Abstract class used to represent objects that contain flow_mat::

		<!ELEMENT XXXXXXXXXX (qticomment? , (material+ | flow_mat+))>"""
	def __init__(self,parent):
		QTICommentContainer.__init__(self,parent)
		ContentMixin.__init__(self)

	def ContentMixin(self,childClass):
		if issubclass(childClass,(Material,FlowMat)):
			return ContentMixin.ContentMixin(self,childClass)
		else:
			raise TypeError

	def GetChildren(self):
		return itertools.chain(
			QTICommentContainer.GetChildren(self),
			ContentMixin.GetContentChildren(self))


class FlowMat(FlowMatContainer,FlowMixin):
	"""This element allows the materials to be displayed to the users to be
	grouped together using flows. The manner in which these flows are handled is
	dependent upon the display-engine::

		<!ELEMENT flow_mat (qticomment? , (flow_mat | material | material_ref)+)>	
		<!ATTLIST flow_mat  class CDATA  'Block' >"""
	XMLNAME="flow_mat"
	XMLATTR_class='flowClass'
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		FlowMatContainer.__init__(self,parent)
		self.flowClass=None
		
	def ContentMixin(self,childClass):
		if issubclass(childClass,MaterialRef):
			# We add material_ref to the basic definition
			return ContentMixin.ContentMixin(self,childClass)
		else:
			return FlowMatContainer.ContentMixin(self,childClass)

	def IsInline(self):
		"""flowmat is always treated as a block if flowClass is specified, otherwise
		it is treated as a block unless it is an only child."""
		if self.flowClass is None:
			return self.InlineChildren()
		else:
			return False

	def MigrateV2Content(self,parent,childType,log):
		"""flow typically maps to a div element.
		
		A flow with a specified class always becomes a div."""
		if self.flowClass is not None:
			if childType in (html.BlockMixin,html.FlowMixin):
				div=parent.ChildElement(html.Div,(qtiv2.core.IMSQTI_NAMESPACE,'div'))
				div.styleClass=self.flowClass
				FlowMatContainer.MigrateV2Content(self,div,html.FlowMixin,log)
			else:
				span=parent.ChildElement(html.Span,(qtiv2.core.IMSQTI_NAMESPACE,'span'))
				span.styleClass=self.flowClass
				FlowMatContainer.MigrateV2Content(self,span,html.InlineMixin,log)
		else:
			# ignore the flow, br handling is done automatically by the parent
			FlowMatContainer.MigrateV2Content(self,parent,childType,log)


class MetadataContainerMixin:
	"""A mix-in class used to hold dictionaries of metadata.
	
	There is a single dictionary maintained to hold all metadata values, each
	value is a list of tuples of the form (value string, defining element).
	Values are keyed on the field label or tag name with any leading qmd\_ prefix
	removed."""
	def __init__(self):
		self.metadata={}

	def DeclareMetadata(self,label,entry,definition=None):
		label=label.lower()
		if label[:4]=="qmd_":
			label=label[4:]
		if not label in self.metadata:
			self.metadata[label]=[]
		self.metadata[label].append((entry,definition))


class QTIMetadata(core.QTIElement):
	"""The container for all of the vocabulary-based QTI-specific meta-data.
	This structure is available to each of the four core ASI data structures::

	<!ELEMENT qtimetadata (vocabulary? , qtimetadatafield+)>"""
	XMLNAME='qtimetadata'
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.Vocabulary=None
		self.QTIMetadataField=[]
	
	def GetChildren(self):
		if self.Vocabulary: yield self.Vocabulary
		for child in self.QTIMetadataField: yield child


class Vocabulary(core.QTIElement):
	"""The vocabulary to be applied to the associated meta-data fields. The
	vocabulary is defined either using an external file or it is included as a
	comma separated list::

		<!ELEMENT vocabulary (#PCDATA)>
		<!ATTLIST vocabulary
			uri			CDATA  #IMPLIED
			entityref	ENTITY  #IMPLIED
			vocab_type	CDATA  #IMPLIED >"""
	XMLNAME="vocabulary"
	XMLATTR_entityref='entityRef'
	XMLATTR_uri='uri'		
	XMLATTR_vocab_type='vocabType'

	def __init__(self,parent):
		QTIElement.__init__(self,parent)
		self.uri=None
		self.entityRef=None
		self.vocabType=None		


class QTIMetadataField(core.QTIElement):
	"""The structure responsible for containing each of the QTI-specific
	meta-data fields::

		<!ELEMENT qtimetadatafield	(fieldlabel , fieldentry)>
		<!ATTLIST qtimetadatafield  xml:lang CDATA  #IMPLIED >"""
	XMLNAME='qtimetadatafield'
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.FieldLabel=FieldLabel(self)
		self.FieldEntry=FieldEntry(self)
		
	def GetChildren(self):
		yield self.FieldLabel
		yield self.FieldEntry
	
	def ContentChanged(self):
		label=self.FieldLabel.GetValue()
		label={'marks':'maximumscore',
			'qmd_marks':'maximumscore',
			'name':'title',
			'qmd_name':'title',
			'syllabusarea':'topic',
			'qmd_syllabusarea':'topic',
			'item type':'itemtype',
			'question type':'itemtype',
			'qmd_layoutstatus':'status',
			'layoutstatus':'status'}.get(label,label)
		# Still need to handle creator and owner
		self.DeclareMetadata(label,self.FieldEntry.GetValue(),self)


class FieldLabel(core.QTIElement):
	"""Used to contain the name of the QTI-specific meta-data field::
	
		<!ELEMENT fieldlabel (#PCDATA)>"""
	XMLNAME="fieldlabel"
	XMLCONTENT=xml.XMLMixedContent


class FieldEntry(core.QTIElement):
	"""Used to contain the actual data entry of the QTI-specific meta-data field
	named using the associated 'fieldlabel' element::

		<!ELEMENT fieldentry (#PCDATA)>"""
	XMLNAME="fieldentry"
	XMLCONTENT=xml.XMLMixedContent


class Objectives(FlowMatContainer):
	"""The objectives element is used to store the information that describes
	the educational aims of the Item. These objectives can be defined for each
	of the different 'view' perspectives. This element should not be used to
	contain information specific to an Item because the question-engine may not
	make this information available to the Item during the actual test::

		<!ELEMENT objectives (qticomment? , (material+ | flow_mat+))>
		<!ATTLIST objectives  view	(All | Administrator | AdminAuthority | Assessor | Author |
					Candidate | InvigilatorProctor | Psychometrician | Scorer | 
					Tutor ) 'All' >"""
	XMLNAME='objectives'
	XMLATTR_view=('view',core.View.DecodeLowerValue,core.View.EncodeValue)
	XMLCONTENT=xml.ElementContent
		
	def __init__(self,parent):
		FlowMatContainer.__init__(self,parent)
		self.view=core.View.DEFAULT
		
	def MigrateV2(self,v2Item,log):
		"""Adds rubric representing these objectives to the given item's body"""
		rubric=v2Item.ChildElement(qtiv2.ItemBody).ChildElement(qtiv2.RubricBlock)
		rubric.SetAttribute('view',qtiv2.core.View.EncodeValueList(core.MigrateV2View(self.view,log)))
		# rubric is not a flow-container so we force inlines to be p-wrapped
		self.MigrateV2Content(rubric,html.BlockMixin,log)
				
	def LRMMigrateObjectives(self,lom,log):
		"""Adds educational description from these objectives."""
		description,lang=self.ExtractText()
		eduDescription=lom.ChildElement(imsmd.LOMEducational).ChildElement(imsmd.Description)
		eduDescription.AddString(lang,description)


class Rubric(FlowMatContainer):
	"""The rubric element is used to contain contextual information that is
	important to the element e.g. it could contain standard data values that
	might or might not be useful for answering the question. Different sets of
	rubric can be defined for each of the possible 'views'. The material
	contained within the rubric must be displayed to the participant::

		<!ELEMENT rubric (qticomment? , (material+ | flow_mat+))>	
		<!ATTLIST rubric  view	(All | Administrator | AdminAuthority | Assessor | Author |
					Candidate | InvigilatorProctor | Psychometrician | Scorer | 
					Tutor ) 'All' >"""
	XMLNAME='rubric'
	XMLATTR_view=('view',core.View.DecodeLowerValue,core.View.EncodeValue)
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		FlowMatContainer.__init__(self,parent)
		self.view=core.View.DEFAULT
	
	def MigrateV2(self,v2Item,log):
		if self.view==core.View.All:
			log.append('Warning: rubric with view="All" replaced by <div> with class="rubric"')
			rubric=v2Item.ChildElement(qtiv2.ItemBody).ChildElement(html.Div,(qtiv2.core.IMSQTI_NAMESPACE,'div'))
			rubric.styleClass='rubric'
		else:
			rubric=v2Item.ChildElement(qtiv2.ItemBody).ChildElement(qtiv2.RubricBlock)
			rubric.SetAttribute('view',qtiv2.core.View.EncodeValueList(core.MigrateV2View(self.view,log)))
		# rubric is not a flow-container so we force inlines to be p-wrapped
		self.MigrateV2Content(rubric,html.BlockMixin,log)


class DecVar(core.QTIElement):
	"""The <decvar> element permits the declaration of the scoring variables
	::

		<!ELEMENT decvar (#PCDATA)>
		<!ATTLIST decvar  varname CDATA  'SCORE' ::
			vartype		(Integer |  String |  Decimal |  Scientific |  Boolean | 
				Enumerated | Set )  'Integer'
			defaultval 	CDATA  #IMPLIED
			minvalue   	CDATA  #IMPLIED
			maxvalue   	CDATA  #IMPLIED
			members    	CDATA  #IMPLIED
			cutvalue	CDATA  #IMPLIED >"""
	XMLNAME="decvar"
	XMLATTR_cutvalue='cutValue'
	XMLATTR_defaultval='defaultValue'	
	XMLATTR_maxvalue='maxValue'
	XMLATTR_members='members'
	XMLATTR_minvalue='minValue'
	XMLATTR_varname='varName'
	XMLATTR_vartype=('varType',core.VarType.DecodeTitleValue,core.VarType.EncodeValue)
	XMLCONTENT=xml.XMLMixedContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.varName='SCORE'
		self.varType=core.VarType.Integer
		self.defaultValue=None
		self.minValue=None
		self.maxValue=None
		self.members=None
		self.cutValue=None
			
	def MigrateV2(self,v2Item,log):
		d=v2Item.ChildElement(qtiv2.variables.OutcomeDeclaration)
		v2Type=core.MigrateV2VarType(self.varType,log)
		if self.varType==core.VarType.Set:
			log.append('Warning: treating vartype="Set" as equivalent to "Enumerated"')
		elif v2Type is None:
			log.append('Error: bad vartype for decvar "%s"; defaulting to integer'%self.varName)
			v2Type=qtiv2.variables.BaseType.integer
		d.baseType=v2Type
		d.cardinality=qtiv2.variables.Cardinality.single
		d.identifier=qtiv2.core.ValidateIdentifier(self.varName)
		if self.defaultValue is not None:
			value=d.ChildElement(qtiv2.variables.DefaultValue).ChildElement(qtiv2.variables.ValueElement)
			value.SetValue(self.defaultValue)
		# to do... min and max were actually constraints in QTI v1 ...
		# so we will need to fix these up later with responseConditions to constraint the value
		if self.minValue is not None:
			d.normalMinimum=float(self.minValue)
		if self.maxValue is not None:
			d.normalMaximum=float(self.maxValue)
		if self.members is not None:
			log.append('Warning: enumerated members no longer supported, ignoring "%s"'%self.members)
		if v2Type in (qtiv2.variables.BaseType.integer,qtiv2.variables.BaseType.float):
			# we need to adjust minValue/maxValue later
			if self.cutValue is not None:
				d.masteryValue=float(self.cutValue)
		v2Item.RegisterDeclaration(d)

	def ContentChanged(self):
		"""The decvar element is supposed to be empty but QTI v1 content is all over the place."""
		try:
			value=self.GetValue()
			if value is not None:
				assert value.strip()==''
		except xml.XMLMixedContentError:
			# Even more confusing
			pass


class InterpretVar(core.QTIElement,ContentMixin):
	"""The <interpretvar> element is used to provide statistical interpretation
	information about the associated variables::

		<!ELEMENT interpretvar (material | material_ref)>	
		<!ATTLIST interpretvar
			view	(All | Administrator | AdminAuthority | Assessor | Author | Candidate |
				InvigilatorProctor | Psychometrician | Scorer | Tutor )  'All'
				varname CDATA  'SCORE' >"""
	XMLNAME="interpretvar"
	XMLATTR_view=('view',core.View.DecodeLowerValue,core.View.EncodeValue)
	XMLATTR_varname='varName'
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		ContentMixin.__init__(self)
		self.view=core.View.DEFAULT
		self.varName='SCORE'
	
	def ContentMixin(self,childClass):
		if issubclass(childClass,(Material,MaterialRef)):
			return ContentMixin.ContentMixin(self,childClass)
		else:
			raise TypeError

	def GetChildren(self):
		return ContentMixin.GetContentChildren(self)
		
	def MigrateV2(self,v2Item,log):
		identifier=qtiv2.core.ValidateIdentifier(self.varName)
		if self.view!=core.View.All:
			log.append('Warning: view restriction on outcome interpretation no longer supported (%s)'%core.View.EncodeValue(self.view))
		d=v2Item.declarations.get(identifier)
		di,lang=self.ExtractText()
		di=xsi.WhiteSpaceCollapse(di)
		if d.interpretation:
			d.interpretation=d.interpretation+"; "+di
		else:
			d.interpretation=di
		# we drop the lang as this isn't supported on declarations


class SetVar(core.QTIElement):
	"""The <setvar> element is responsible for changing the value of the scoring
	variable as a result of the associated response processing test::

		<!ELEMENT setvar (#PCDATA)>	
		<!ATTLIST setvar  varname CDATA  'SCORE'
			action     (Set | Add | Subtract | Multiply | Divide )  'Set' >"""
	XMLNAME="setvar"
	XMLATTR_varname='varName'
	XMLATTR_action=('action',core.Action.DecodeTitleValue,core.Action.EncodeValue)
	XMLCONTENT=xml.XMLMixedContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.varName='SCORE'
		self.action=core.Action.DEFAULT
	
	def MigrateV2Rule(self,parent,log):
		v2Item=parent.FindParent(qtiv2.QTIAssessmentItem)
		identifier=qtiv2.core.ValidateIdentifier(self.varName)
		outcome=v2Item.declarations.get(identifier,None)
		if outcome is None:
			raise QTIUnimplementedError("Auto-declared outcomes")
		setValue=parent.ChildElement(qtiv2.QTISetOutcomeValue)
		setValue.identifier=identifier
		if outcome.cardinality!=qtiv2.variables.Cardinality.single:
			raise QTIUnimplementedError("setvar for '%s' with cardinality %s"%(identifier,
				qtiv2.variables.Cardinality.encode[outcome.cardinality]))
		value=None
		variable=None
		if not self.action or self.action==core.Action.Set:
			value=setValue.ChildElement(qtiv2.QTIBaseValue)
		else:
			if self.action==core.Action.Add:
				op=setValue.ChildElement(qtiv2.QTISum)
			elif self.action==core.Action.Subtract:
				op=setValue.ChildElement(qtiv2.QTISubtract)
			elif self.action==core.Action.Multiply:
				op=setValue.ChildElement(qtiv2.QTIProduct)
			elif self.action==core.Action.Divide:
				op=setValue.ChildElement(qtiv2.QTIDivide)
			variable=op.ChildElement(qtiv2.QTIVariable)
			variable.identifier=identifier
			value=op.ChildElement(qtiv2.QTIBaseValue)
		value.baseType=outcome.baseType
		value.SetValue(self.GetValue().strip())


class DisplayFeedback(core.QTIElement):
	"""The <displayfeedback> element is responsible for assigning an associated
	feedback to the response processing if the 'True' state is created through
	the associated response processing condition test::

		<!ELEMENT displayfeedback (#PCDATA)>
		<!ATTLIST displayfeedback
			feedbacktype	(Response | Solution | Hint )  'Response'
			linkrefid		CDATA  #REQUIRED >"""
	XMLNAME="displayfeedback"
	XMLATTR_feedbacktype=('feedbackType',core.FeedbackType.DecodeTitleValue,core.FeedbackType.EncodeValue)
	XMLATTR_linkrefid='linkRefID'
	XMLCONTENT=xml.XMLMixedContent

	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.feedbackType=core.FeedbackType.DEFAULT
		self.linkRefID=None
		
	def MigrateV2Rule(self,parent,log):
		v2Item=parent.FindParent(qtiv2.QTIAssessmentItem)
		identifier=qtiv2.core.ValidateIdentifier(self.linkRefID,'FEEDBACK_')
		outcome=v2Item.declarations.get('FEEDBACK',None)
		if outcome is None:
			d=v2Item.ChildElement(qtiv2.variables.OutcomeDeclaration)
			d.baseType=qtiv2.variables.BaseType.identifier
			d.cardinality=qtiv2.variables.Cardinality.multiple
			d.identifier='FEEDBACK'
			v2Item.RegisterDeclaration(d)
		setValue=parent.ChildElement(qtiv2.QTISetOutcomeValue)
		setValue.identifier='FEEDBACK'
		multiple=setValue.ChildElement(qtiv2.QTIMultiple)
		variable=multiple.ChildElement(qtiv2.QTIVariable)
		variable.identifier='FEEDBACK'
		value=multiple.ChildElement(qtiv2.QTIBaseValue)
		value.baseType=qtiv2.variables.BaseType.identifier
		value.SetValue(self.linkRefID)


class ConditionVar(core.QTIElement):
	"""The conditional test that is to be applied to the user's response. A wide
	range of separate and combinatorial test can be applied::

		<!ELEMENT conditionvar (not | and | or | unanswered | other | varequal | varlt |
			varlte | vargt | vargte | varsubset | varinside | varsubstring | durequal |
			durlt | durlte | durgt | durgte | var_extension)+>"""
	XMLNAME="conditionvar"
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.ExtendableExpressionMixin=[]
		
	def GetChildren(self):
		return iter(self.ExtendableExpressionMixin)

	def MigrateV2Expression(self,parent,log):
		if len(self.ExtendableExpressionMixin)>1:
			# implicit and
			eAnd=parent.ChildElement(qtiv2.And)
			for ie in self.ExtendableExpressionMixin:
				ie.MigrateV2Expression(eAnd,log)
		elif self.ExtendableExpressionMixin:
			self.ExtendableExpressionMixin[0].MigrateV2Expression(parent,log)
		else:
			log.append("Warning: empty condition replaced with null operator")
			parent.ChildElement(qtiv2.QTINull)


class ExtendableExpressionMixin:
	"""Abstract mixin class to indicate an expression, including var_extension"""

	def MigrateV2Expression(self,parent,log):
		raise QTIUnimplementedError("Expression element: %s"%self.__class__.__name__)

	
class ExpressionMixin(ExtendableExpressionMixin):
	"""Abstract mixin class to indicate an expression excluding var_extension"""
	pass


class VarThing(core.QTIElement,ExpressionMixin):
	"""Abstract class for var\\* elements
	::

		<!ATTLIST *
			respident	CDATA #REQUIRED
			index		CDATA  #IMPLIED >"""
	XMLATTR_respident='responseIdentifier'
	XMLATTR_index=('index',xsi.DecodeInteger,xsi.EncodeInteger)
	XMLCONTENT=xml.XMLMixedContent

	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.responseIdentifier=''
		self.index=None

	def MigrateV2Missing(self,identifier,parent,log):
		log.append("Warning: test of undeclared response (%s) replaced with Null operator"%identifier)
		parent.ChildElement(qtiv2.QTINull)
	
	def MigrateV2Variable(self,d,parent,log):
		if self.index:
			if d.cardinality==qtiv2.variables.Cardinality.multiple:
				log.append("Warning: index ignored for response variable of cardinality multiple")
			elif d.cardinality==qtiv2.variables.Cardinality.single:
				log.append("Warning: index ignored for response variable of cardinality single")
			else:
				parent=parent.ChildElement(qtiv2.QTIIndex)
				parent.n=self.index
		varExpression=parent.ChildElement(qtiv2.QTIVariable)
		varExpression.identifier=d.identifier
	
	def MigrateV2Value(self,d,parent,log):
		value=self.GetValue().strip()
		if d.baseType in (qtiv2.variables.BaseType.pair,qtiv2.variables.BaseType.directedPair,qtiv2.variables.BaseType.point):
			value=value.replace(',',' ')
		elif d.baseType==qtiv2.variables.BaseType.identifier:
			value=qtiv2.core.ValidateIdentifier(value)
		bv=parent.ChildElement(qtiv2.QTIBaseValue)
		bv.baseType=d.baseType
		bv.SetValue(value)
		
	
class VarEqual(VarThing):
	"""The <varequal> element is the test of equivalence. The data for the test
	is contained within the element's PCDATA string and must be the same as one
	of the <response_label> values (this were assigned using the ident
	attribute)::

		<!ELEMENT varequal (#PCDATA)>	
		<!ATTLIST varequal
			case  (Yes | No )  'No'
			respident CDATA  #REQUIRED"
			index CDATA  #IMPLIED >"""
	XMLNAME="varequal"
	XMLATTR_case=('case',core.ParseYesNo,core.FormatYesNo)

	def __init__(self,parent):
		VarThing.__init__(self,parent)
		self.case=False
	
	def MigrateV2Expression(self,parent,log):
		v2Item=parent.FindParent(qtiv2.QTIAssessmentItem)
		identifier=qtiv2.core.ValidateIdentifier(self.responseIdentifier)
		d=v2Item.declarations.get(identifier,None)
		if d is None:
			self.MigrateV2Missing(identifier,parent,log)
		elif d.cardinality==qtiv2.variables.Cardinality.single:
			# simple test of equality
			if d.baseType==qtiv2.variables.BaseType.identifier or d.baseType==qtiv2.variables.BaseType.pair:
				if not self.case:
					log.append("Warning: case-insensitive comparison of identifiers not supported in version 2")
				expression=parent.ChildElement(qtiv2.Match)
			elif d.baseType==qtiv2.variables.BaseType.integer:
				expression=parent.ChildElement(qtiv2.Match)
			elif d.baseType==qtiv2.variables.BaseType.string:
				expression=parent.ChildElement(qtiv2.QTIStringMatch)
				expression.caseSensitive=self.case
			elif d.baseType==qtiv2.variables.BaseType.float:
				log.append("Warning: equality operator with float values is deprecated")
				expression=parent.ChildElement(qtiv2.QTIEqual)
			else:
				raise QTIUnimplementedOperator("varequal(%s)"%qtiv2.variables.BaseType.Encode(d.baseType))
			self.MigrateV2Variable(d,expression,log)
			self.MigrateV2Value(d,expression,log)
		else:
			# This test simply becomes a member-test operation
			if d.baseType==qtiv2.variables.BaseType.identifier or qtiv2.variables.BaseType.pair:
				if not self.case:
					log.append("Warning: case-insensitive comparison of identifiers not supported in version 2")
			elif d.baseType==qtiv2.variables.BaseType.string:
				if not self.case:
					log.append("Warning: member operation cannot be case-insensitive when baseType is string")
			elif d.baseType==qtiv2.variables.BaseType.float:
				log.append("Warning: member operation is deprecated when baseType is float")
			else:
				raise QTIUnimplementedOperator("varequal(%s)"%qtiv2.variables.BaseType.Encode(d.baseType))
			expression=parent.ChildElement(qtiv2.QTIMember)
			self.MigrateV2Value(d,expression,log)
			self.MigrateV2Variable(d,expression,log)


class VarInequality(VarThing):
	"""Abstract class for varlt, varlte, vargt and vargte."""

	def MigrateV2Inequality(self):
		"""Returns the class to use in qtiv2"""
		raise QTIUnimplementedOperator(self.xmlname)
		
	def MigrateV2Expression(self,parent,log):
		v2Item=parent.FindParent(qtiv2.QTIAssessmentItem)
		identifier=qtiv2.core.ValidateIdentifier(self.responseIdentifier)
		d=v2Item.declarations.get(identifier,None)
		if d is None:
			self.MigrateV2Missing(identifier,parent,log)
		elif d.cardinality==qtiv2.variables.Cardinality.single:
			# simple inequality
			if d.baseType==qtiv2.variables.BaseType.integer or d.baseType==qtiv2.variables.BaseType.float:
				expression=parent.ChildElement(self.MigrateV2Inequality())
			else:
				raise QTIUnimplementedOperator("%s(%s)"%(self.xmlname,qtiv2.variables.BaseType.Encode(d.baseType)))
			self.MigrateV2Variable(d,expression,log)
			self.MigrateV2Value(d,expression,log)
		else:
			raise QTIUnimplementedOperator("%s(%s:%s)"%(self.xmlname,qtiv2.variables.Cardinality.Encode(d.cardinality),qtiv2.variables.BaseType.Encode(d.baseType)))

	
class VarLT(VarInequality):
	"""The <varlt> element is the 'less than' test. The data for the test is
	contained within the element's PCDATA string and is assumed to be numerical
	in nature::

		<!ELEMENT varlt (#PCDATA)>
		<!ATTLIST varlt
			respident	CDATA  #REQUIRED"
			index		CDATA  #IMPLIED >"""
	XMLNAME="varlt"
	XMLCONTENT=xml.XMLMixedContent

	def MigrateV2Inequality(self):
		return qtiv2.LT


class VarLTE(VarInequality):
	"""The <varlte> element is the 'less than or equal' test. The data for the
	test is contained within the element's PCDATA string and is assumed to be
	numerical in nature::

		<!ELEMENT varlte (#PCDATA)>	
		<!ATTLIST varlte
			respident CDATA  #REQUIRED"
			index CDATA  #IMPLIED >"""
	XMLNAME="varlte"
	XMLCONTENT=xml.XMLMixedContent

	def MigrateV2Inequality(self):
		return qtiv2.LTE


class VarGT(VarInequality):
	"""The <vargt> element is the 'greater than' test. The data for the test is
	contained within the element's PCDATA string and is assumed to be numerical
	in nature::

		<!ELEMENT vargt (#PCDATA)>	
		<!ATTLIST vargt
			respident CDATA  #REQUIRED"
			index CDATA  #IMPLIED >"""
	XMLNAME="vargt"
	XMLCONTENT=xml.XMLMixedContent

	def MigrateV2Inequality(self):
		return qtiv2.GT


class VarGTE(VarInequality):
	"""The <vargte> element is the 'greater than or equal to' test. The data for
	the test is contained within the element's PCDATA string and is assumed to
	be numerical in nature::

		<!ELEMENT vargte (#PCDATA)>	
		<!ATTLIST vargte
			respident CDATA  #REQUIRED"
			index CDATA  #IMPLIED >"""
	XMLNAME="vargte"
	XMLCONTENT=xml.XMLMixedContent

	def MigrateV2Inequality(self):
		return qtiv2.GTE


class VarSubset(core.QTIElement,ExpressionMixin):
	"""The <varsubset> element is the 'member of a list/set' test. The data for
	the test is contained within the element's PCDATA string. The set is a comma
	separated list with no enclosing parentheses::

		<!ELEMENT varsubset (#PCDATA)>
		<!ATTLIST varsubset
			respident CDATA  #REQUIRED"
			setmatch     (Exact | Partial )  'Exact'
			index CDATA  #IMPLIED >"""
	XMLNAME="varsubset"
	XMLCONTENT=xml.XMLMixedContent


class VarSubString(core.QTIElement,ExpressionMixin):
	"""The <varsubstring> element is used to determine if a given string is a
	substring of some other string::

		<!ELEMENT varsubstring (#PCDATA)>	
		<!ATTLIST varsubstring
			index CDATA  #IMPLIED
			respident CDATA  #REQUIRED"
			case  (Yes | No )  'No' >"""
	XMLNAME="varsubstring"
	XMLCONTENT=xml.XMLMixedContent


class VarInside(VarThing):
	"""The <varinside> element is the 'xy-co-ordinate inside an area' test. The
	data for the test is contained within the element's PCDATA string and is a
	set of co-ordinates that define the area::

		<!ELEMENT varinside (#PCDATA)>	
		<!ATTLIST varinside
			areatype     (Ellipse | Rectangle | Bounded )  #REQUIRED
			respident CDATA  #REQUIRED"
			index CDATA  #IMPLIED >"""
	XMLNAME="varinside"
	XMLATTR_areatype=('areaType',core.Area.DecodeTitleValue,core.Area.EncodeValue)
	XMLCONTENT=xml.XMLMixedContent

	def __init__(self,parent):
		VarThing.__init__(self,parent)
		self.areaType=None
	
	def MigrateV2Expression(self,parent,log):
		v2Item=parent.FindParent(qtiv2.QTIAssessmentItem)
		identifier=qtiv2.core.ValidateIdentifier(self.responseIdentifier)
		d=v2Item.declarations.get(identifier,None)
		if d is None:
			self.MigrateV2Missing(identifier,parent,log)
		elif d.cardinality==qtiv2.variables.Cardinality.single:
			# is the point in the area?
			if d.baseType==qtiv2.variables.BaseType.point:
				expression=parent.ChildElement(qtiv2.QTIInside)
				expression.shape,coords=core.MigrateV2AreaCoords(self.areaType,self.GetValue(),log)
				for c in coords:
					expression.coords.values.append(html.LengthType(c))
				self.MigrateV2Variable(d,expression,log)			
			else:
				raise QTIUnimplementedError("varinside(%s)"%qtiv2.variables.BaseType.EncodeValue(d.baseType))
		else:
			raise QTIUnimplementedError("varinside with multiple/orderd variable")


class DurEqual(core.QTIElement,ExpressionMixin):
	"""The <durequal> element is the 'duration equal to' test i.e. a test on the
	time taken to make the response::

		<!ELEMENT durequal (#PCDATA)>	
		<!ATTLIST durequal
			index CDATA  #IMPLIED
			respident CDATA  #REQUIRED" >"""
	XMLNAME="durequal"
	XMLCONTENT=xml.XMLMixedContent


class DurLT(core.QTIElement,ExpressionMixin):
	"""The <durlt> element is the 'duration less than' test i.e. a test on the
	time taken to make the response::

		<!ELEMENT durlt (#PCDATA)>
		<!ATTLIST durlt
			index		CDATA  #IMPLIED
			respident	CDATA  #REQUIRED" >"""
	XMLNAME="durlt"
	XMLCONTENT=xml.XMLMixedContent


class DurLTE(core.QTIElement,ExpressionMixin):
	"""The <durlte> element is the 'duration less than or equal to' test i.e. a
	test on the time taken to make the response::

		<!ELEMENT durlte (#PCDATA)>	
		<!ATTLIST durlte
			index		CDATA  #IMPLIED
			respident	CDATA  #REQUIRED" >"""
	XMLNAME="durlte"
	XMLCONTENT=xml.XMLMixedContent


class DurGT(core.QTIElement,ExpressionMixin):
	"""The <durgt> element is the 'duration greater than' test i.e. a test on
	the time taken to make the response::

		<!ELEMENT durgt (#PCDATA)>	
		<!ATTLIST durgt
			index		CDATA  #IMPLIED
			respident	CDATA  #REQUIRED" >"""
	XMLNAME="durgt"
	XMLCONTENT=xml.XMLMixedContent


class DurGTE(core.QTIElement,ExpressionMixin):
	"""The <durgte> element is the 'duration greater than or equal to' test i.e.
	a test on the time taken to make the response::

		<!ELEMENT durgte (#PCDATA)>	
		<!ATTLIST durgte
			index		CDATA  #IMPLIED
			respident	CDATA  #REQUIRED" >"""
	XMLNAME="durgte"
	XMLCONTENT=xml.XMLMixedContent


class Not(core.QTIElement,ExpressionMixin):
	"""The <not> element inverts the logical test outcome that is required. In
	the case of the <varequal> element produces a 'not equals' test::

		<!ELEMENT not (and | or | not | unanswered | other | varequal | varlt | varlte |
			vargt | vargte | varsubset | varinside | varsubstring | durequal | durlt |
			durlte | durgt | durgte)>"""
	XMLNAME="not"
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.ExpressionMixin=None
	
	def GetChildren(self):
		if self.ExpressionMixin: yield self.ExpressionMixin

	def MigrateV2Expression(self,parent,log):
		if self.ExpressionMixin is None:
			log.append("Warning: empty not condition replaced with null operator")
			parent.ChildElement(qtiv2.QTINull)
		else:
			eNot=parent.ChildElement(qtiv2.Not)
			self.ExpressionMixin.MigrateV2Expression(eNot,log)


class And(core.QTIElement,ExpressionMixin):
	"""The <and> element is used to create the Boolean 'AND' operation between
	the two or more enclosed tests. The result 'True' is returned if all of the
	tests return a 'True' value::

		<!ELEMENT and (not | and | or | unanswered | other | varequal | varlt | varlte |
			vargt | vargte | varsubset | varinside | varsubstring | durequal | durlt |
			durlte | durgt | durgte)+>"""
	XMLNAME="and"
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.ExpressionMixin=[]
	
	def GetChildren(self):
		return iter(self.ExpressionMixin)

	def MigrateV2Expression(self,parent,log):
		if len(self.ExpressionMixin):
			eAnd=parent.ChildElement(qtiv2.And)
			for e in self.ExpressionMixin:
				e.MigrateV2Expression(eAnd,log)
		else:
			log.append("Warning: empty and condition replaced with null operator")
			parent.ChildElement(qtiv2.QTINull)


class Or(core.QTIElement,ExpressionMixin):
	"""The <or> element is used to create the Boolean 'OR' operation between the
	two or more enclosed tests. The result 'True' is returned if one or more of
	the tests return a 'True' value::

		<!ELEMENT or (not | and | or | unanswered | other | varequal | varlt | varlte |
			vargt | vargte | varsubset | varinside | varsubstring | durequal | durlt |
			durlte | durgt | durgte)+>"""
	XMLNAME="or"
	XMLCONTENT=xml.ElementContent

	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.ExpressionMixin=[]
	
	def GetChildren(self):
		return iter(self.ExpressionMixin)

	def MigrateV2Expression(self,parent,log):
		if len(self.ExpressionMixin):
			eOr=parent.ChildElement(qtiv2.Or)
			for e in self.ExpressionMixin:
				e.MigrateV2Expression(eOr,log)
		else:
			log.append("Warning: empty or condition replaced with null operator")
			parent.ChildElement(qtiv2.QTINull)
		

class Unanswered(core.QTIElement,ExpressionMixin):
	"""The <unanswered> element is the condition to be applied if a response is
	not received for the Item i.e. it is unanswered::

		<!ELEMENT unanswered (#PCDATA)>
		<!ATTLIST unanswered  respident CDATA  #REQUIRED" >"""
	XMLNAME="unanswered"
	XMLCONTENT=xml.XMLMixedContent


class Other(core.QTIElement,ExpressionMixin):
	"""The <other> element is used to trigger the condition when all of the
	other tests have not returned a 'True' state::

		<!ELEMENT other (#PCDATA)>"""
	XMLNAME="other"
	XMLCONTENT=xml.XMLMixedContent

	def MigrateV2Expression(self,parent,log):
		log.append("Warning: replacing <other/> with the base value true - what did you want me to do??")
		bv=parent.ChildElement(qtiv2.QTIBaseValue)
		bv.baseType=qtiv2.variables.BaseType.boolean
		bv.SetValue('true')


class VarExtension(core.QTIElement,ExtendableExpressionMixin):
	"""This element contains proprietary extensions to be applied to condition
	tests. This enables vendors to create their own conditional tests to be used
	on the participant responses::

		<!ELEMENT var_extension ANY>"""
	XMLNAME="var_extension"
	XMLCONTENT=xml.XMLMixedContent


class PresentationMaterial(FlowMatContainer):
	"""This is material that must be presented to set the context of the parent
	evaluation. This could be at the Section level to contain common question
	material that is relevant to all of the contained Sections/Items. All the
	contained material must be presented::

		<!ELEMENT presentation_material (qticomment? , flow_mat+)>

	Our interpretation is generous here, we also accept <material> by default
	from :py:class:`FlowMatContainer`.  This element is one of the newer
	definitions in QTI v1, after the introduction of <flow>.  It excludes
	<material> because it was assumed there would no legacy content.  Adoption
	of flow was poor and it was replaced with direct inclusion of the html model
	in version 2 (where content is either inline or block level and flow is a
	general term to describe both for contexts where either is allowed)."""
	XMLNAME="presentation_material"
	XMLCONTENT=xml.ElementContent


class Reference(QTICommentContainer,ContentMixin):
	"""The container for all of the materials that can be referenced by other
	structures e.g. feedback material, presentation material etc. The
	presentation of this material is under the control of the structure that is
	referencing the material. There is no implied relationship between any of
	the contained material components::

		<!ELEMENT reference (qticomment? , (material | mattext | matemtext | matimage | mataudio |
			matvideo | matapplet | matapplication | matbreak | mat_extension)+)>"""
	XMLNAME="reference"
	XMLCONTENT=xml.ElementContent
	
	def ContentMixin(self,childClass):
		"""We override this method to prevent references from being included."""
		if issubclass(childClass,(Material,MatText,MatEmText,MatImage,MatAudio,
				MatVideo,MatApplet,MatApplication,MatBreak,MatExtension)):
			return ContentMixin.ContentMixin(self,childClass)
		else:
			raise TypeError

		
class MaterialRef(core.QTIElement):
	"""The <material_ref> element is used to contain a reference to the required
	full material block. This material will have had an identifier assigned to
	enable such a reference to be reconciled when the instance is parsed into
	the system::

		<!ELEMENT material_ref EMPTY>	
		<!ATTLIST material_ref  linkrefid CDATA  #REQUIRED >"""
	XMLNAME="material_ref"
	XMLATTR_linkrefid='linkRefID'
	XMLCONTENT=xml.XMLEmpty

	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.linkRefID=None
		
	def FindMaterial(self):
		material=None
		doc=self.GetDocument()
		if doc:
			material=doc.FindMaterial(self.linkRefID)
		if material is None:
			raise core.QTIError("Bad material_ref: %s"%str(self.linkRefID))
		return material
		
	def IsInline(self):
		return self.FindMaterial().IsInline()
	
	def ExtractText(self):
		return self.FindMaterial().ExtractText()
	
	def MigrateV2Content(self,parent,childType,log):
		self.FindMaterial().MigrateV2Content(parent,childType,log)
