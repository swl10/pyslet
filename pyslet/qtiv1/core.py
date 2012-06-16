#! /usr/bin/env python

import pyslet.xml20081126.structures as xml
import pyslet.xsdatatypes20041028 as xsi
import pyslet.imsqtiv2p1 as qtiv2

import string


class QTIError(Exception):
	"""All errors raised by this module are derived from QTIError."""
	pass
	
class QTIUnimplementedError(QTIError):
	"""A feature of QTI v1 that is not yet implemented by this module."""
	pass


def MakeValidName(name):
	"""This function takes a string that is supposed to match the
	production for Name in XML and forces it to comply by replacing
	illegal characters with '_'.  If name starts with a valid name
	character but not a valid name start character, it is prefixed
	with '_' too."""
	if name:
		goodName=[]
		if not xml.IsNameStartChar(name[0]):
			goodName.append(u'_')
		for c in name:
			if xml.IsNameChar(c):
				goodName.append(c)
			else:
				goodName.append(u'_')
		return string.join(goodName,u'')
	else:
		return u'_'


def ParseYesNo(src):
	"""Returns a True/False parsed from a "Yes" / "No" string.

	This function is generous in what it accepts, it will accept mixed case and
	strips surrounding space.  It returns True if the resulting string matches
	"yes" and False otherwise.

	Reverses the transformation defined by :py:func:`FormatYesNo`."""   
	return src.strip().lower()==u'yes'

def FormatYesNo(value):
	"""Returns "Yes" if *value* is True, "No" otherwise.
	
	Reverses the transformation defined by :py:func:`ParseYesNo`."""   
	if value:
		return u'Yes'
	else:
		return u'No'


class Area(xsi.Enumeration):
	"""Area enumeration::
	
	(Ellipse | Rectangle | Bounded )  'Ellipse'
	
	Defines constants for the above area types.  Usage example::

		Area.Rectangle
	
	Note that::
		
		Area.DEFAULT == Area.Ellipse

	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
	decode={
		u'Ellipse':1,
		u'Rectangle':2,
		u'Bounded':3
		}
xsi.MakeEnumeration(Area,u'Ellipse')


def MigrateV2AreaCoords(area,value,log):
	"""Returns a tuple of (shape,coords array) representing the area.

	*	*area* is one of the :py:class:`Area` constants.

	*	*value* is the string containing the content of the element to which
		the area applies.
					
	This conversion is generous because the separators have never been well
	defined and in some cases content uses a mixture of space and ','.

	Note also that the definition of rarea was updated in the 1.2.1 errata and
	this affects this algorithm.  The clarification on the definition of ellipse
	from radii to diameters might mean that some content ends up with hotspots
	that are too small but this is safer than hotspots that are too large.
	
	Example::
	
		import pyslet.qtiv1.core as qticore1
		import pyslet.qtiv2.core as qticore2
		log=[]
		shape,coords=qticore1.MigrateV2AreaCoords(qticore1.Area.Ellipse,"10,10,2,2",log)
		# returns (qticore2.Shape.circle, [10, 10, 1])
		
	Note that Ellipse was deprecated in QTI version 2::
	
		import pyslet.qtiv1.core as qticore1
		log=[]
		shape,coords=qticore1.MigrateV2AreaCoords(qticore1.Area.Ellipse,"10,10,2,4",log)
		print log
		# outputs the following...
		
		['Warning: ellipse shape is deprecated in version 2']"""
	coords=[]
	vStr=[]
	sep=0
	for c in value:
		if c in "0123456789.":
			if sep and vStr:
				coords.append(int(float(string.join(vStr,''))))
				sep=0
				vStr=[]
			vStr.append(c)
		else:
			sep=1
	if vStr:
		coords.append(int(float(string.join(vStr,''))))
	if area==Area.Rectangle:
		if len(coords)<4:
			log.append("Error: not enough coordinates for rectangle, padding with zeros")
			while len(coords)<4:
				coords.append(0)
		shape=qtiv2.QTIShape.rect
		coords=[coords[0],coords[1],coords[0]+coords[3]-1,coords[1]+coords[2]-1]
	elif area==Area.Ellipse:
		if len(coords)<4:
			if len(corrds)<2:
				log.append("Error: not enough coordinates to locate ellipse, padding with zero")
				while len(coords)<2:
					coords.append(0)
			if len(coords)==2:
				log.append("Error: ellipse has no radius, treating as circule radius 4")
				coords=coords+[8,8]
			elif len(coords)==3:
				log.append("Error: only one radius given for ellipse, assuming circular")
				coords.append(coords[-1])
		if coords[2]==coords[3]:
			r=coords[2]//2 # centre-pixel coordinate model again
			coords=[coords[0],coords[1],r]
			shape=qtiv2.QTIShape.circle
		else:
			log.append("Warning: ellipse shape is deprecated in version 2")
			coords=[coords[0],coords[1],coords[2]//2,coords[3]//2]
			shape=qtiv2.QTIShape.ellipse
	else:
		shape=qtiv2.QTIShape.poly
	return shape,coords


class FIBType(xsi.Enumeration):
	"""Fill-in-the-blank type enumeration::
	
	fibtype      (String | Integer | Decimal | Scientific )  'String'

	Defines constants for the above fill-in-the-blank types.  Usage example::

		FIBType.Decimal
	
	Note that::
		
		FIBType.DEFAULT == FIBType.String

	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
	decode={
		u'String':1,
		u'Integer':2,
		u'Decimal':3,
		u'Scientific':4
		}
xsi.MakeEnumeration(FIBType,u'String')


class NumType(xsi.Enumeration):
	"""numtype enumeration::
	
	numtype      (Integer | Decimal | Scientific )  'Integer'
	
	Defines constants for the above numeric types.  Usage example::

		NumType.Scientific
	
	Note that::
		
		NumType.DEFAULT == NumType.Integer

	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
	decode={
		u'Integer':1,
		u'Decimal':2,
		u'Scientific':3
		}
xsi.MakeEnumeration(NumType,u'Integer')


class PromptType(xsi.Enumeration):
	"""Prompt type enumeration::
	
	prompt       (Box | Dashline | Asterisk | Underline )
	
	Defines constants for the above prompt types.  Usage example::

		PromptType.Dashline
	
	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
	decode={
		u'Box':1,
		u'Dashline':2,
		u'Asterisk':3,
		u'Underline':4
		}
xsi.MakeEnumeration(PromptType)


class Orientation(xsi.Enumeration):
	"""Orientation enumeration::
	
	(Horizontal | Vertical )  'Horizontal'

	Defines constants for the above orientation types.  Usage example::

		Orientation.Horizontal
	
	Note that::
		
		Orientation.DEFAULT == Orientation.Horizontal
		
	For more methods see :py:class:`~pyslet.xsdatatypes20041028.Enumeration`"""
	decode={
		u'Horizontal':1,
		u'Vertical':2,
		}
xsi.MakeEnumeration(Orientation,u'Horizontal')


class QTIElement(xml.Element):
	"""Base class for all elements defined by the QTI specification"""
	
	def DeclareMetadata(self,label,entry,definition=None):
		"""Declares a piece of metadata to be associated with the element.
		
		Most QTIElements will be contained by some type of metadata container
		that collects metadata in a format suitable for easy lookup and export
		to other metadata formats.  The default implementation simply passes the
		call to the parent element or, if there is no parent, the declaration is
		ignored.
		
		For more information see :py:class:`MetadataContainer`."""
		if isinstance(self.parent,QTIElement):
			self.parent.DeclareMetadata(label,entry,definition)
		else:
			pass


