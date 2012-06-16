#! /usr/bin/env python

import pyslet.xml20081126.structures as xml
import pyslet.xsdatatypes20041028 as xsi
import pyslet.html40_19991224 as html
import pyslet.imsqtiv2p1 as qtiv2

import core

import string, itertools
from types import StringTypes

class CommentContainer(core.QTIElement):
	"""Basic element to represent all elements that can contain a comment as their first child::

	<!ELEMENT XXXXXXXXXXXX (qticomment? , ....... )>"""
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		self.QTIComment=None

	def GetChildren(self):
		if self.QTIComment: yield self.QTIComment


class QTIComment(core.QTIElement):
	"""Represents the qticomment element.
	
::

	<!ELEMENT qticomment (#PCDATA)>
	
	<!ATTLIST qticomment  xml:lang CDATA  #IMPLIED >"""
	XMLNAME='qticomment'
	XMLCONTENT=xml.XMLMixedContent


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
				if isinstance(child,(Flow,FlowMat,FlowLabel)):
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
						if isinstance(child,(Flow,FlowMat,FlowLabel)):
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
				except AttributeError:
					raise QTIError("Error: unsupported QTI v1 content element "+child.xmlname)


class Material(CommentContainer,ContentMixin):
	"""Represents the material element
	
::

	<!ELEMENT material (qticomment? , (mattext | matemtext | matimage | mataudio | matvideo | matapplet | matapplication | matref | matbreak | mat_extension)+ , altmaterial*)>
	
	<!ATTLIST material  %I_Label;
						xml:lang CDATA  #IMPLIED >
	"""
	XMLNAME='material'
	XMLATTR_label='label'
	XMLCONTENT=xml.ElementContent
	
	def __init__(self,parent):
		CommentContainer.__init__(self,parent)
		ContentMixin.__init__(self)
		self.label=None
	
	def GetChildren(self):
		return itertools.chain(
			CommentContainer.GetChildren(self),
			self.contentChildren)
	
	def QTIMatThingMixin(self,childClass):
		child=childClass(self)
		self.contentChildren.append(child)
		return child
		
	def ContentChanged(self):
		if self.label:
			doc=self.GetDocument()
			if doc:
				doc.RegisterMaterial(self)
		CommentContainer.ContentChanged(self)


class QTIMatThingMixin(ContentMixin):
	"""An abstract class used to help identify the mat* elements."""
	pass


class QTIPositionMixin:
	"""Mixin to define the positional attributes.
	
	<!ENTITY % I_X0 " x0 CDATA  #IMPLIED">
	
	<!ENTITY % I_Y0 " y0 CDATA  #IMPLIED">
	
	<!ENTITY % I_Height " height CDATA  #IMPLIED">
	
	<!ENTITY % I_Width " width CDATA  #IMPLIED">
	"""
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


class QTIMatText(core.QTIElement,QTIPositionMixin,QTIMatThingMixin):
	"""Represents the mattext element

::

	<!ELEMENT mattext (#PCDATA)>
	
	<!ATTLIST mattext  texttype    CDATA  'text/plain'
						%I_Label;
						%I_CharSet;
						%I_Uri;
						xml:space    (preserve | default )  'default'
						xml:lang    CDATA  #IMPLIED
						%I_EntityRef;
						%I_Width;
						%I_Height;
						%I_Y0;
						%I_X0; >	
	"""
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
		QTIPositionMixin.__init__(self)
		QTIMatThingMixin.__init__(self)
		self.label=None
		self.charset='ascii-us'
		self.uri=None
		self.texttype='text/plain'
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
				if type(child) in StringTypes or issubclass(child.__class__,html.InlineMixin):
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
				elif issubclass(child.__class__,html.InlineMixin):
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
			if self.charset.lower() in QTIMatText.SymbolCharsets:
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
					if type(child) in StringTypes or issubclass(child.__class__,html.InlineMixin):
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


class QTIMatEmText(QTIMatText):
	"""Represents matemtext element.
	
::

	<!ELEMENT matemtext (#PCDATA)>
	
	<!ATTLIST matemtext  texttype    CDATA  'text/plain'
						  %I_Label;
						  %I_CharSet;
						  %I_Uri;
						  xml:space    (preserve | default )  'default'
						  xml:lang    CDATA  #IMPLIED
						  %I_EntityRef;
						  %I_Width;
						  %I_Height;
						  %I_Y0;
						  %I_X0; >
	"""
	XMLNAME="matemtext"
	XMLCONTENT=xml.XMLMixedContent
	

class QTIMatImage(core.QTIElement,QTIPositionMixin,QTIMatThingMixin):
	"""Represents matimage element.
	
::

	<!ELEMENT matimage (#PCDATA)>
	
	<!ATTLIST matimage  imagtype    CDATA  'image/jpeg'
						 %I_Label;
						 %I_Height;
						 %I_Uri;
						 %I_Embedded;
						 %I_Width;
						 %I_Y0;
						 %I_X0;
						 %I_EntityRef; >
	"""
	XMLNAME="matimage"
	XMLATTR_imagtype='imageType'
	XMLATTR_label='label'
	XMLATTR_uri=('uri',html.DecodeURI,html.EncodeURI)
	XMLCONTENT=xml.XMLMixedContent
	
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		QTIPositionMixin.__init__(self)
		QTIMatThingMixin.__init__(self)
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
	

class QTIMatAudio(core.QTIElement,QTIMatThingMixin):
	"""Represents mataudio element.
	
::

	<!ELEMENT mataudio (#PCDATA)>
	
	<!ATTLIST mataudio  audiotype   CDATA  'audio/base'
						 %I_Label;
						 %I_Uri;
						 %I_Embedded;
						 %I_EntityRef; >
	"""
	XMLNAME="mataudio"
	XMLCONTENT=xml.XMLMixedContent

	XMLATTR_audiotype='audioType'
	XMLATTR_label='label'
	XMLATTR_uri=('uri',html.DecodeURI,html.EncodeURI)
	XMLCONTENT=xml.XMLMixedContent
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		QTIMatThingMixin.__init__(self)
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


class QTIMatVideo(core.QTIElement):
	"""Represents mataudio element.
	
::

	<!ELEMENT matvideo (#PCDATA)>
	
	<!ATTLIST matvideo  videotype   CDATA  'video/avi'
						 %I_Label;
						 %I_Uri;
						 %I_Width;
						 %I_Height;
						 %I_Y0;
						 %I_X0;
						 %I_Embedded;
						 %I_EntityRef; >
	"""
	XMLNAME="matvideo"
	XMLCONTENT=xml.XMLMixedContent


class QTIMatApplet(core.QTIElement):
	"""Represents matapplet element.
	
::

	<!ELEMENT matapplet (#PCDATA)>
	
	<!ATTLIST matapplet  %I_Label;
						  %I_Uri;
						  %I_Y0;
						  %I_Height;
						  %I_Width;
						  %I_X0;
						  %I_Embedded;
						  %I_EntityRef; >
	"""
	XMLNAME="matapplet"
	XMLCONTENT=xml.XMLMixedContent


class QTIMatApplication(core.QTIElement):
	"""Represents matapplication element.
	
::

	<!ELEMENT matapplication (#PCDATA)>
	
	<!ATTLIST matapplication  apptype     CDATA  #IMPLIED
							   %I_Label;
							   %I_Uri;
							   %I_Embedded;
							   %I_EntityRef; >
	"""
	XMLNAME="matapplication"
	XMLCONTENT=xml.XMLMixedContent


class QTIMatBreak(core.QTIElement,QTIMatThingMixin):
	"""Represents matbreak element.
	
::

	<!ELEMENT matbreak EMPTY>
	"""
	XMLNAME="matbreak"
	XMLCONTENT=xml.XMLEmpty
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		QTIMatThingMixin.__init__(self)
				
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
	
	
class QTIMatRef(QTIMatThingMixin,core.QTIElement):
	"""Represents matref element::

	<!ELEMENT matref EMPTY>
	
	<!ATTLIST matref  %I_LinkRefId; >
	"""
	XMLNAME="matref"
	XMLATTR_linkrefid='linkRefID'
	XMLCONTENT=xml.XMLEmpty

	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		QTIMatThingMixin.__init__(self)

	def FindMatThing(self):
		matThing=None
		doc=self.GetDocument()
		if doc:
			matThing=doc.FindMatThing(self.linkRefID)
		if matThing is None:
			raise QTIError("Bad matref: %s"%str(self.linkRefID))
		return matThing
		
	def IsInline(self):
		return self.FindMatThing().IsInline()
	
	def ExtractText(self):
		return self.FindMatThing().ExtractText()
	
	def MigrateV2Content(self,parent,childType,log):
		self.FindMatThing().MigrateV2Content(parent,childType,log)


class FlowContainer(CommentContainer,ContentMixin):
	"""Abstract class used to represent elements that contain flow and related
	elements::

	<!ELEMENT XXXXXXXXXX (qticomment? , (material | flow | response_*)* )>"""
	def __init__(self,parent):
		CommentContainer.__init__(self,parent)
		ContentMixin.__init__(self)

	def GetChildren(self):
		return itertools.chain(
			CommentContainer.GetChildren(self),
			self.contentChildren)

	def ContentMixin(self,childClass):
		if childClass in (Material,Flow) or issubclass(childClass,ResponseCommon):
			return ContentMixin.ContentMixin(self,childClass)
		else:
			raise TypeError


class Flow(FlowContainer):
	"""Represents the flow element.
	
::

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
	
	<!ATTLIST flow  %I_Class; >
	"""
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


class FlowMatContainer(CommentContainer,ContentMixin):
	"""Abstract class used to represent objects that contain flow_mat
	
::

	<!ELEMENT XXXXXXXXXX (qticomment? , (material+ | flow_mat+))>
	"""
	def __init__(self,parent):
		CommentContainer.__init__(self,parent)
		ContentMixin.__init__(self)

	def GetChildren(self):
		return itertools.chain(
			CommentContainer.GetChildren(self),
			self.contentChildren)

	def Material(self):
		child=Material(self)
		self.contentChildren.append(child)
		return child
	
	def FlowMat(self):
		child=FlowMat(self)
		self.contentChildren.append(child)
		return child


class FlowMat(FlowMatContainer):
	"""Represent flow_mat element
	
::

	<!ELEMENT flow_mat (qticomment? , (flow_mat | material | material_ref)+)>
	
	<!ATTLIST flow_mat  %I_Class; >"""
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


class FlowLabel(CommentContainer,ContentMixin):
	"""Represents the flow_label element.
	
::

	<!ELEMENT flow_label (qticomment? , (flow_label | response_label)+)>
	
	<!ATTLIST flow_label  %I_Class; >
	"""
	XMLNAME='flow_label'
	XMLCONTENT=xml.ElementContent

	def __init__(self,parent):
		CommentContainer.__init__(self,parent)
		ContentMixin.__init__(self)
	
	def ContentMixin(self,childClass):
		if childClass is FlowLabel or issubclass(childClass,ResponseLabelCommon):
			return ContentMixin.ContentMixin(self,childClass)
		else:
			raise TypeError

	def GetChildren(self):
		return itertools.chain(
			CommentContainer.GetChildren(self),
			self.contentChildren)
		
	def GetLabelContent(self):
		children=[]
		for child in self.contentChildren:
			if isinstance(child,FlowLabel):
				children=children+child.GetLabelContent()
			else:
				children.append(child)
		return children


class ResponseCommon(core.QTIElement,ContentMixin):
	"""Abstract class to act as a parent for all response_* elements."""

	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		ContentMixin.__init__(self)


class ResponseLabelCommon(core.QTIElement,ContentMixin):
	"""Abstract class to act as a parent for response_label."""
	
	def __init__(self,parent):
		core.QTIElement.__init__(self,parent)
		ContentMixin.__init__(self)


class QTIPresentationMaterial(CommentContainer):
	"""Represent presentation_material element
	
::

	<!ELEMENT presentation_material (qticomment? , flow_mat+)>"""
	XMLNAME="presentation_material"
	XMLCONTENT=xml.ElementContent
	

		





	
