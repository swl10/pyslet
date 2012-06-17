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
					parent.ChildElement(html.Br,(qtiv2.IMSQTI_NAMESPACE,'br'))
					brAfter=False				
				if brBefore:
					parent.ChildElement(html.Br,(qtiv2.IMSQTI_NAMESPACE,'br'))
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
							p.ChildElement(html.Br,(qtiv2.IMSQTI_NAMESPACE,'br'))
							brAfter=False
						if isinstance(child,FlowMixin):
							brBefore=brAfter=True
						if p is None:
							p=parent.ChildElement(html.P,(qtiv2.IMSQTI_NAMESPACE,'p'))
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

	<!ELEMENT material (qticomment? , (mattext | matemtext | matimage | mataudio | matvideo | matapplet | matapplication | matref | matbreak | mat_extension)+ , altmaterial*)>	
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
	<!ATTLIST altmaterial  xml:lang CDATA  #IMPLIED >
	"""
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
	"""Mixin to define the positional attributes::
	
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
	"""The <mattext> element contains any text that is to be displayed to the users::

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
		'greek':1,
		'symbol':1
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
					span=parent.ChildElement(html.P,(qtiv2.IMSQTI_NAMESPACE,'p'))
				else:
					span=parent.ChildElement(html.Span,(qtiv2.IMSQTI_NAMESPACE,'span'))
				if lang:
					span.SetLang(lang)
				if self.label:
					#span.label=self.label
					span.SetAttribute('label',self.label)
				# force child elements to render as inline XML
				span.AddData(data)
			elif childType is html.BlockMixin:
				p=parent.ChildElement(html.P,(qtiv2.IMSQTI_NAMESPACE,'p'))
				p.AddData(data)
			else:
				# inline or flow, just add the text directly...
				parent.AddData(data)
		elif self.texttype=='text/html':		
			if childType is html.BlockMixin or (childType is html.FlowMixin and not self.IsInline()):
				# Block or mixed-up flow, wrap all text and inline elements in p
				p=None
				for child in self.matChildren:
					if type(child) in StringTypes or isinstance(child,html.InlineMixin):
						if p is None:
							p=parent.ChildElement(html.P,(qtiv2.IMSQTI_NAMESPACE,'p'))
						if type(child) in StringTypes:
							p.AddData(child)
						else:
							newChild=child.Copy(p)
							qtiv2.FixHTMLNamespace(newChild)															
					else:
						# stop collecting inlines
						p=None
						newChild=child.Copy(parent)
						qtiv2.FixHTMLNamespace(newChild)															
			else:
				# Flow context (with only inline children) or inline context
				for child in self.matChildren:
					if type(child) in StringTypes:
						parent.AddData(child)
					else:
						newChild=child.Copy(parent)
						qtiv2.FixHTMLNamespace(newChild)
		else:
			raise QTIUnimplementedError





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




class MatEmText(MatText):
	"""Represents matemtext element.
	
::

	<!ELEMENT matemtext (#PCDATA)>
	
	<!ATTLIST matemtext  texttype    CDATA  'text/plain'
						  label CDATA  #IMPLIED
						  charset CDATA  'ascii-us'
						  uri CDATA  #IMPLIED
						  xml:space    (preserve | default )  'default'
						  xml:lang    CDATA  #IMPLIED
						  entityref ENTITY  #IMPLIED
						  width CDATA  #IMPLIED
						  height CDATA  #IMPLIED
						  y0 CDATA  #IMPLIED
						  x0 CDATA  #IMPLIED >
	"""
	XMLNAME="matemtext"
	XMLCONTENT=xml.XMLMixedContent
	

class MatImage(core.QTIElement,PositionMixin,MatThingMixin):
	"""Represents matimage element.
	
::

	<!ELEMENT matimage (#PCDATA)>
	
	<!ATTLIST matimage  imagtype    CDATA  'image/jpeg'
						 label CDATA  #IMPLIED
						 height CDATA  #IMPLIED
						 uri CDATA  #IMPLIED
						 embedded CDATA  'base64'
						 width CDATA  #IMPLIED
						 y0 CDATA  #IMPLIED
						 x0 CDATA  #IMPLIED
						 entityref ENTITY  #IMPLIED >
	"""
	XMLNAME="matimage"
	XMLATTR_imagtype='imageType'
	XMLATTR_label='label'
	XMLATTR_uri=('uri',html.DecodeURI,html.EncodeURI)
	XMLCONTENT=xml.XMLMixedContent
	
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		PositionMixin.__init__(self)
		MatThingMixin.__init__(self)
		self.imageType='image/jpeg'
		self.label=None
		self.uri=None
				
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
			p=parent.ChildElement(html.P,(qtiv2.IMSQTI_NAMESPACE,'p'))
			img=p.ChildElement(html.Img,(qtiv2.IMSQTI_NAMESPACE,'img'))
		else:
			img=parent.ChildElement(html.Img,(qtiv2.IMSQTI_NAMESPACE,'img'))
		img.src=self.ResolveURI(self.uri)
		if self.width is not None:
			img.width=html.LengthType(self.width)
		if self.height is not None:
			img.height=html.LengthType(self.height)
	

class MatAudio(core.QTIElement,MatThingMixin):
	"""Represents mataudio element.
	
::

	<!ELEMENT mataudio (#PCDATA)>
	
	<!ATTLIST mataudio  audiotype   CDATA  'audio/base'
						 label CDATA  #IMPLIED
						 uri CDATA  #IMPLIED
						 embedded CDATA  'base64'
						 entityref ENTITY  #IMPLIED >
	"""
	XMLNAME="mataudio"
	XMLCONTENT=xml.XMLMixedContent

	XMLATTR_audiotype='audioType'
	XMLATTR_label='label'
	XMLATTR_uri=('uri',html.DecodeURI,html.EncodeURI)
	XMLCONTENT=xml.XMLMixedContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		MatThingMixin.__init__(self)
		self.audioType='audio/base'
		self.label=None
		self.uri=None
				
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
			p=parent.ChildElement(html.P,(qtiv2.IMSQTI_NAMESPACE,'p'))
			obj=p.ChildElement(html.Object,(qtiv2.IMSQTI_NAMESPACE,'object'))
		else:
			obj=parent.ChildElement(html.Object,(qtiv2.IMSQTI_NAMESPACE,'object'))		
		obj.data=self.ResolveURI(self.uri)
		obj.type=self.audioType


class MatVideo(core.QTIElement):
	"""Represents mataudio element.
	
::

	<!ELEMENT matvideo (#PCDATA)>
	
	<!ATTLIST matvideo  videotype   CDATA  'video/avi'
						 label CDATA  #IMPLIED
						 uri CDATA  #IMPLIED
						 width CDATA  #IMPLIED
						 height CDATA  #IMPLIED
						 y0 CDATA  #IMPLIED
						 x0 CDATA  #IMPLIED
						 embedded CDATA  'base64'
						 entityref ENTITY  #IMPLIED >
	"""
	XMLNAME="matvideo"
	XMLCONTENT=xml.XMLMixedContent


class MatApplet(core.QTIElement):
	"""Represents matapplet element.
	
::

	<!ELEMENT matapplet (#PCDATA)>
	
	<!ATTLIST matapplet  label CDATA  #IMPLIED
						  uri CDATA  #IMPLIED
						  y0 CDATA  #IMPLIED
						  height CDATA  #IMPLIED
						  width CDATA  #IMPLIED
						  x0 CDATA  #IMPLIED
						  embedded CDATA  'base64'
						  entityref ENTITY  #IMPLIED >
	"""
	XMLNAME="matapplet"
	XMLCONTENT=xml.XMLMixedContent


class MatApplication(core.QTIElement):
	"""Represents matapplication element.
	
::

	<!ELEMENT matapplication (#PCDATA)>
	
	<!ATTLIST matapplication  apptype     CDATA  #IMPLIED
							   label CDATA  #IMPLIED
							   uri CDATA  #IMPLIED
							   embedded CDATA  'base64'
							   entityref ENTITY  #IMPLIED >
	"""
	XMLNAME="matapplication"
	XMLCONTENT=xml.XMLMixedContent


class MatBreak(core.QTIElement,MatThingMixin):
	"""Represents matbreak element.
	
::

	<!ELEMENT matbreak EMPTY>
	"""
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
			parent.ChildElement(html.Br,(qtiv2.IMSQTI_NAMESPACE,'br'))
		else:
			# a break in a group of block level elements is ignored
			pass			
	
	
class MatRef(MatThingMixin,core.QTIElement):
	"""Represents matref element::

	<!ELEMENT matref EMPTY>
	
	<!ATTLIST matref  %I_LinkRefId; >
	"""
	XMLNAME="matref"
	XMLATTR_linkrefid='linkRefID'
	XMLCONTENT=xml.XMLEmpty

	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		MatThingMixin.__init__(self)

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


class FlowContainer(QTICommentContainer,ContentMixin):
	"""Abstract class used to represent elements that contain flow and related
	elements::

	<!ELEMENT XXXXXXXXXX (qticomment? , (material | flow | response_*)* )>"""
	def __init__(self,parent):
		QTICommentContainer.__init__(self,parent)
		ContentMixin.__init__(self)

	def GetChildren(self):
		return itertools.chain(
			QTICommentContainer.GetChildren(self),
			self.contentChildren)

	def ContentMixin(self,childClass):
		if childClass in (Material,Flow) or issubclass(childClass,ResponseCommon):
			return ContentMixin.ContentMixin(self,childClass)
		else:
			raise TypeError


class FlowMixin:
	"""Mix-in class to identify all flow elements::
	
	( flow | flow_mat | flow_label)"""
	pass

	
class Flow(FlowContainer,FlowMixin):
	"""This element contains all of the instructions for the presentation with
	flow blocking of the question during a test. This information includes the
	actual material to be presented. The labels for the possible responses are
	also identified and these are used by the response processing element
	defined elsewhere in the Item::

	<!ELEMENT flow (qticomment? ,
		(flow |
		material |
		material_ref |
		response_lid |
		response_xy |
		response_str |
		response_num |
		response_grp |
		response_extension)+
		)>
	<!ATTLIST flow  class CDATA  'Block' >"""
	XMLNAME='flow'
	XMLATTR_class='flowClass'
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		FlowContainer.__init__(self,parent)
		self.flowClass=None
		
	def IsInline(self):
		"""flow is always treated as a block if flowClass is specified, otherwise
		it is treated as a block unless it is an only child."""
		if self.flowClass is None:
			return self.InlineChildren()
		else:
			return False

	def MigrateV2Content(self,parent,childType,log):
		"""flow typically maps to a div element.
		
		A flow with a specified class always becomes a div
		A flow with inline children generates a paragraph to hold them
		A flow with no class is ignored."""
		if self.flowClass is not None:
			if childType in (html.BlockMixin,html.FlowMixin):
				div=parent.ChildElement(html.Div,(qtiv2.IMSQTI_NAMESPACE,'div'))
				div.styleClass=self.flowClass
				FlowContainer.MigrateV2Content(self,div,html.FlowMixin,log)
			else:
				span=parent.ChildElement(html.Span,(qtiv2.IMSQTI_NAMESPACE,'span'))
				span.styleClass=self.flowClass
				FlowContainer.MigrateV2Content(self,span,html.InlineMixin,log)
		else:
			FlowContainer.MigrateV2Content(self,parent,childType,log)


class FlowMatContainer(QTICommentContainer,ContentMixin):
	"""Abstract class used to represent objects that contain flow_mat
	
::

	<!ELEMENT XXXXXXXXXX (qticomment? , (material+ | flow_mat+))>
	"""
	def __init__(self,parent):
		QTICommentContainer.__init__(self,parent)
		ContentMixin.__init__(self)

	def GetChildren(self):
		return itertools.chain(
			QTICommentContainer.GetChildren(self),
			self.contentChildren)

	def Material(self):
		child=Material(self)
		self.contentChildren.append(child)
		return child
	
	def FlowMat(self):
		child=FlowMat(self)
		self.contentChildren.append(child)
		return child


class FlowMat(FlowMatContainer,FlowMixin):
	"""Represent flow_mat element
	
::

	<!ELEMENT flow_mat (qticomment? , (flow_mat | material | material_ref)+)>
	
	<!ATTLIST flow_mat  class CDATA  'Block' >"""
	XMLNAME="flow_mat"
	XMLATTR_class='flowClass'
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		FlowMatContainer.__init__(self,parent)
		self.flowClass=None
		
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
				div=parent.ChildElement(html.Div,(qtiv2.IMSQTI_NAMESPACE,'div'))
				div.styleClass=self.flowClass
				FlowMatContainer.MigrateV2Content(self,div,html.FlowMixin,log)
			else:
				span=parent.ChildElement(html.Span,(qtiv2.IMSQTI_NAMESPACE,'span'))
				span.styleClass=self.flowClass
				FlowMatContainer.MigrateV2Content(self,span,html.InlineMixin,log)
		else:
			# ignore the flow, br handling is done automatically by the parent
			FlowMatContainer.MigrateV2Content(self,parent,childType,log)


class ResponseCommon(core.QTIElement,ContentMixin):
	"""Abstract class to act as a parent for all response_* elements."""

	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		ContentMixin.__init__(self)


class RenderCommon(core.QTIElement,ContentMixin):
	"""Abstract class to act as a parent for all render_* elements."""

	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		ContentMixin.__init__(self)


class ResponseLabelCommon(core.QTIElement,ContentMixin):
	"""Abstract class to act as a parent for response_label."""
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		ContentMixin.__init__(self)


class PresentationMaterial(QTICommentContainer):
	"""Represent presentation_material element
	
::

	<!ELEMENT presentation_material (qticomment? , flow_mat+)>"""
	XMLNAME="presentation_material"
	XMLCONTENT=xml.ElementContent
	

		
class Rubric(FlowMatContainer,core.QTIViewMixin):
	"""Represents the rubric element.
	
::

	<!ELEMENT rubric (qticomment? , (material+ | flow_mat+))>
	
	<!ATTLIST rubric  view	(All | Administrator | AdminAuthority | Assessor | Author |
				Candidate | InvigilatorProctor | Psychometrician | Scorer | 
				Tutor ) 'All' >"""
	XMLNAME='rubric'
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		FlowMatContainer.__init__(self,parent)
		core.QTIViewMixin.__init__(self)
	
	def MigrateV2(self,v2Item,log):
		if self.view.lower()=='all':
			log.append('Warning: rubric with view="All" replaced by <div> with class="rubric"')
			rubric=v2Item.ChildElement(qtiv2.ItemBody).ChildElement(html.Div,(qtiv2.IMSQTI_NAMESPACE,'div'))
			rubric.styleClass='rubric'
		else:
			rubric=v2Item.ChildElement(qtiv2.ItemBody).ChildElement(qtiv2.RubricBlock)
			oldView=self.view.lower()
			view=QTIObjectives.V2_VIEWMAP.get(oldView,'author')
			if view!=oldView:
				log.append("Warning: changing view %s to %s"%(self.view,view))
			rubric.SetAttribute('view',view)
		# rubric is not a flow-container so we force inlines to be p-wrapped
		self.MigrateV2Content(rubric,html.BlockMixin,log)


class QTIObjectives(FlowMatContainer,core.QTIViewMixin):
	"""Represents the objectives element
	
::

	<!ELEMENT objectives (qticomment? , (material+ | flow_mat+))>

	<!ATTLIST objectives  view	(All | Administrator | AdminAuthority | Assessor | Author |
				Candidate | InvigilatorProctor | Psychometrician | Scorer | 
				Tutor ) 'All' >"""
	XMLNAME='objectives'
	XMLCONTENT=xml.ElementContent
		
	def __init__(self,parent):
		FlowMatContainer.__init__(self,parent)
		core.QTIViewMixin.__init__(self)
		
	def MigrateV2(self,v2Item,log):
		"""Adds rubric representing these objectives to the given item's body"""
		rubric=v2Item.ChildElement(qtiv2.ItemBody).ChildElement(qtiv2.RubricBlock)
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


class MaterialRef(core.QTIElement):
	"""Represents material_ref element.
	
::

	<!ELEMENT material_ref EMPTY>
	
	<!ATTLIST material_ref  %I_LinkRefId; >
	"""
	XMLNAME="material_ref"
	XMLCONTENT=xml.XMLEmpty


class ConditionVar(core.QTIElement):
	"""Represents the interpretvar element.

::

	<!ELEMENT conditionvar (not | and | or | unanswered | other | varequal | varlt |
		varlte | vargt | vargte | varsubset | varinside | varsubstring | durequal |
		durlt | durlte | durgt | durgte | var_extension)+>
	
	"""
	XMLNAME="conditionvar"
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.ExpressionMixin=[]
	
	def QTIVarExtension(self):
		child=QTIVarExtension(self)
		self.ExpressionMixin.append(child)
		return child
	
	def GetChildren(self):
		return iter(self.ExpressionMixin)

	def MigrateV2Expression(self,parent,log):
		if len(self.ExpressionMixin)>1:
			# implicit and
			eAnd=parent.ChildElement(qtiv2.QTIAnd)
			for ie in self.ExpressionMixin:
				ie.MigrateV2Expression(eAnd,log)
		elif self.ExpressionMixin:
			self.ExpressionMixin[0].MigrateV2Expression(parent,log)
		else:
			log.append("Warning: empty condition replaced with null operator")
			parent.ChildElement(qtiv2.QTINull)

