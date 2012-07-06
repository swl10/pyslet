#! /usr/bin/env python

import pyslet.xml20081126.structures as xml
import pyslet.xmlnames20091208 as xmlns
import pyslet.xsdatatypes20041028 as xsi
import pyslet.qtiv2.core as core
import pyslet.qtiv2.variables as variables

import string, random, itertools


class Expression(core.QTIElement):
	"""Abstract class for all expression elements."""
	
	def Evaluate(self,state):
		"""Evaluates this expression in the context of the session *state*."""
		raise NotImplementedError("Evaluation of %s"%self.__class__.__name__)

	def IntegerOrTemplateRef(self,state,value):
		"""Given a value of type integerOrTemplateRef this method returns the
		corresponding integer by looking up the value, if necessary, in
		*state*.  If value is a variable reference to a variable with NULL
		value then None is returned."""
		ref=core.GetTemplateRef(value)
		if ref:
			if state.IsTemplate(ref):
				v=state[ref]
				if isinstance(v,variables.IntegerValue):
					return v.value
				else:
					raise core.ProcessingError("Bad reference: %s is not an integer variable"%ref)
			else:
				raise core.ProcessingError("Bad reference: %s is not a template variable"%ref)
		else:
			return xsi.DecodeInteger(value)
			
	def FloatOrTemplateRef(self,state,value):
		"""Given a value of type floatOrTemplateRef this method returns the
		corresponding float by looking up the value, if necessary, in
		*state*.  If value is a variable reference to a variable with NULL
		value then None is returned."""
		ref=core.GetTemplateRef(value)
		if ref:
			if state.IsTemplate(ref):
				v=state[ref]
				if isinstance(v,variables.FloatValue):
					return v.value
				else:
					raise core.ProcessingError("Bad reference: %s is not a float variable"%ref)
			else:
				raise core.ProcessingError("Bad reference: %s is not a template variable"%ref)
		else:
			return xsi.DecodeDouble(value)
			
class BaseValue(Expression):
	"""The simplest expression returns a single value from the set defined by
	the given baseType
	::

		<xsd:attributeGroup name="baseValue.AttrGroup">
			<xsd:attribute name="baseType" type="baseType.Type" use="required"/>
		</xsd:attributeGroup>
		
		<xsd:complexType name="baseValue.Type">
			<xsd:simpleContent>
				<xsd:extension base="xsd:string">
					<xsd:attributeGroup ref="baseValue.AttrGroup"/>
				</xsd:extension>
			</xsd:simpleContent>
		</xsd:complexType>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'baseValue')
	XMLATTR_baseType=('baseType',variables.BaseType.DecodeLowerValue,variables.BaseType.EncodeValue)
	XMLCONTENT=xmlns.XMLMixedContent

	def __init__(self,parent):
		Expression.__init__(self,parent)
		self.baseType=variables.BaseType.string

	def Evaluate(self,state):
		return variables.SingleValue.NewValue(self.baseType,self.GetValue())


class Variable(Expression):
	"""This expression looks up the value of an itemVariable that has been
	declared in a corresponding variableDeclaration or is one of the built-in
	variables::

		<xsd:attributeGroup name="variable.AttrGroup">
			<xsd:attribute name="identifier" type="identifier.Type" use="required"/>
			<xsd:attribute name="weightIdentifier" type="identifier.Type" use="optional"/>
		</xsd:attributeGroup>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'variable')
	XMLATTR_identifier=('identifier',core.ValidateIdentifier,lambda x:x)
	XMLATTR_weightIdentifier=('weightIdentifier',core.ValidateIdentifier,lambda x:x)
	XMLCONTENT=xmlns.XMLEmpty
	
	def __init__(self,parent):
		Expression.__init__(self,parent)
		self.identifier=''
		self.weightIdentifier=None
	
	def Evaluate(self,state):
		try:
			return state[self.identifier]
		except KeyError:
			raise core.ProcessingError("%s has not been declared"%self.identifier)

class Default(Expression):
	"""This expression looks up the declaration of an itemVariable and returns
	the associated defaultValue or NULL if no default value was declared::

		<xsd:attributeGroup name="default.AttrGroup">
			<xsd:attribute name="identifier" type="identifier.Type" use="required"/>
		</xsd:attributeGroup>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'default')
	XMLATTR_identifier=('identifier',core.ValidateIdentifier,lambda x:x)
	XMLCONTENT=xmlns.XMLEmpty
	
	def __init__(self,parent):
		Expression.__init__(self,parent)
		self.identifier=''
	
	def Evaluate(self,state):
		try:
			d=state.GetDeclaration(self.identifier)
			return d.GetDefaultValue()
		except KeyError:
			raise core.ProcessingError("%s has not been declared"%self.identifier)


class Correct(Expression):
	"""This expression looks up the declaration of a response variable and
	returns the associated correctResponse or NULL if no correct value was
	declared::

		<xsd:attributeGroup name="correct.AttrGroup">
			<xsd:attribute name="identifier" type="identifier.Type" use="required"/>
		</xsd:attributeGroup>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'correct')
	XMLATTR_identifier=('identifier',core.ValidateIdentifier,lambda x:x)
	XMLCONTENT=xmlns.XMLEmpty
	
	def __init__(self,parent):
		Expression.__init__(self,parent)
		self.identifier=''
	
	def Evaluate(self,state):
		try:
			d=state.GetDeclaration(self.identifier)
			if isinstance(d,variables.ResponseDeclaration):
				return d.GetCorrectValue()
			elif state.IsResponse(self.identifier):
				raise core.ProcessingError("Can't get the correct value of a built-in response %s"%self.identifier)
			else:
				raise core.ProcessingError("%s is not a response variable"%self.identifier)
		except KeyError:
			raise core.ProcessingError("%s has not been declared"%self.identifier)


class MapResponse(Expression):
	"""This expression looks up the value of a response variable and then
	transforms it using the associated mapping, which must have been declared.
	The result is a single float::

		<xsd:attributeGroup name="mapResponse.AttrGroup">
			<xsd:attribute name="identifier" type="identifier.Type" use="required"/>
		</xsd:attributeGroup>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'mapResponse')
	XMLATTR_identifier=('identifier',core.ValidateIdentifier,lambda x:x)
	XMLCONTENT=xmlns.XMLEmpty
	
	def __init__(self,parent):
		Expression.__init__(self,parent)
		self.identifier=''
	
	def Evaluate(self,state):
		try:
			d=state.GetDeclaration(self.identifier)
			if isinstance(d,variables.ResponseDeclaration):
				if d.Mapping is None:
					raise core.ProcessingError("%s has no mapping"%self.identifier)
				return d.Mapping.MapValue(state[self.identifier])				
			elif state.IsResponse(self.identifier):
				raise core.ProcessingError("Can't map built-in response %s"%self.identifier)
			else:
				raise core.ProcessingError("%s is not a response variable"%self.identifier)
		except KeyError:
			raise core.ProcessingError("%s has not been declared"%self.identifier)


class MapResponsePoint(Expression):
	"""This expression looks up the value of a response variable that must be of
	base-type point, and transforms it using the associated areaMapping::

		<xsd:attributeGroup name="mapResponsePoint.AttrGroup">
			<xsd:attribute name="identifier" type="identifier.Type" use="required"/>
		</xsd:attributeGroup>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'mapResponsePoint')
	XMLATTR_identifier=('identifier',core.ValidateIdentifier,lambda x:x)
	XMLCONTENT=xmlns.XMLEmpty
	
	def __init__(self,parent):
		Expression.__init__(self,parent)
		self.identifier=''
	
	def Evaluate(self,state):
		try:
			d=state.GetDeclaration(self.identifier)
			if isinstance(d,variables.ResponseDeclaration):
				if d.baseType is not variables.BaseType.point:
					raise core.ProcessingError("%s does not have point type"%self.identifier)					
				elif d.AreaMapping is None:
					raise core.ProcessingError("%s has no areaMapping"%self.identifier)
				width,height=d.GetStageDimensions()
				return d.AreaMapping.MapValue(state[self.identifier],width,height)
			elif state.IsResponse(self.identifier):
				raise core.ProcessingError("Can't map built-in response %s"%self.identifier)
			else:
				raise core.ProcessingError("%s is not a response variable"%self.identifier)
		except KeyError:
			raise core.ProcessingError("%s has not been declared"%self.identifier)


class Null(Expression):
	"""null is a simple expression that returns the NULL value - the null value is
	treated as if it is of any desired baseType
	::
	
		<xsd:complexType name="null.Type"/>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'null')
	XMLCONTENT=xmlns.XMLEmpty

	def Evaluate(self,state):
		return variables.Value()


class RandomInteger(Expression):
	"""Selects a random integer from the specified range [min,max] satisfying
	min + step * n for some integer n::
	
		<xsd:attributeGroup name="randomInteger.AttrGroup">
			<xsd:attribute name="min" type="integerOrTemplateRef.Type" use="required"/>
			<xsd:attribute name="max" type="integerOrTemplateRef.Type" use="required"/>
			<xsd:attribute name="step" type="integerOrTemplateRef.Type" use="optional"/>
		</xsd:attributeGroup>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'randomInteger')
	XMLATTR_min='min'
	XMLATTR_max='max'
	XMLATTR_step='step'
	XMLCONTENT=xmlns.XMLEmpty
	
	def __init__(self,parent):
		Expression.__init__(self,parent)
		self.min="0"
		self.max=None
		self.step="1"
	
	def Evaluate(self,state):
		min=self.IntegerOrTemplateRef(state,self.min)
		max=self.IntegerOrTemplateRef(state,self.max)
		step=self.IntegerOrTemplateRef(state,self.step)
		return variables.IntegerValue(min+step*random.randint(0,(max-min)//step))
		
		
class RandomFloat(Expression):
	"""Selects a random float from the specified range [min,max]
	::
	
		<xsd:attributeGroup name="randomFloat.AttrGroup">
			<xsd:attribute name="min" type="floatOrTemplateRef.Type" use="required"/>
			<xsd:attribute name="max" type="floatOrTemplateRef.Type" use="required"/>
		</xsd:attributeGroup>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'randomFloat')
	XMLATTR_min='min'
	XMLATTR_max='max'
	XMLCONTENT=xmlns.XMLEmpty
	
	def __init__(self,parent):
		Expression.__init__(self,parent)
		self.min="0"
		self.max=None
	
	def Evaluate(self,state):
		min=self.FloatOrTemplateRef(state,self.min)
		max=self.FloatOrTemplateRef(state,self.max)
		# strictly speaking, we can never return max, but due to possible rounding
		# this point is academic
		return variables.FloatValue(min+random.random()*(max-min))
		

class NOperator(Expression):
	"""An abstract class to help implement operators which take multiple sub-expressions."""
	XMLCONTENT=xmlns.ElementContent
	
	def __init__(self,parent):
		Expression.__init__(self,parent)
		self.Expression=[]
	
	def GetChildren(self):
		return iter(self.Expression)

	def EvaluateChildren(self,state):
		"""Evaluates all child expressions, returning an iterable of
		:py:class:`Value` instances."""
		for e in self.Expression:
			yield e.Evaluate(state)


class UnaryOperator(Expression):
	"""An abstract class to help implement unary operators."""
	XMLCONTENT=xmlns.ElementContent
	
	def __init__(self,parent):
		Expression.__init__(self,parent)
		self.Expression=None
	
	def GetChildren(self):
		if self.Expression: yield self.Expression


class Multiple(NOperator):
	"""The multiple operator takes 0 or more sub-expressions all of which must
	have either single or multiple cardinality::

		<xsd:group name="multiple.ContentGroup">
			<xsd:sequence>
				<xsd:group ref="expression.ElementGroup" minOccurs="0" maxOccurs="unbounded"/>
			</xsd:sequence>
		</xsd:group>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'multiple')

	def Evaluate(self,state):
		# We are going to recurse through the sub-expressions evaluating as we go...
		baseType=None
		values=list(self.EvaluateChildren(state))
		vInput=[]
		for v in values:
			if v.baseType is None:
				continue
			if baseType is None:
				baseType=v.baseType
			elif baseType!=v.baseType:
				raise core.ProcessingError("Mixed containers are not allowed: expected %s, found %s"%(
					variables.BaseType.EncodeValue(baseType),variables.BaseType.EncodeValue(v.baseType)))
			if not v:
				# ignore NULL
				continue
			if v.Cardinality()==variables.Cardinality.single:
				vInput.append(v.value)
			elif v.Cardinality()==variables.Cardinality.multiple:
				# apologies for the obscure code, but this turns {'x':2,'y':3}
				# into ['y', 'y', 'y', 'x', 'x']
				vInput=vInput+list(itertools.chain(*map(lambda x:[x]*v.value[x],v.value)))
			else:
				raise core.ProcessingError("Ordered or Record values not allowed in Mutiple")
		# finally we have a matching list of input values
		result=variables.MultipleContainer(baseType)
		result.SetValue(vInput)
		return result			


class Ordered(NOperator):
	"""The multiple operator takes 0 or more sub-expressions all of which must
	have either single or multiple cardinality::

		<xsd:group name="ordered.ContentGroup">
			<xsd:sequence>
				<xsd:group ref="expression.ElementGroup" minOccurs="0" maxOccurs="unbounded"/>
			</xsd:sequence>
		</xsd:group>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'ordered')

	def Evaluate(self,state):
		# We are going to recurse through the sub-expressions evaluating as we go...
		baseType=None
		values=list(self.EvaluateChildren(state))
		vInput=[]
		for v in values:
			if v.baseType is None:
				continue
			if baseType is None:
				baseType=v.baseType
			elif baseType!=v.baseType:
				raise core.ProcessingError("Mixed containers are not allowed: expected %s, found %s"%(
					variables.BaseType.EncodeValue(baseType),variables.BaseType.EncodeValue(v.baseType)))
			if not v:
				# ignore NULL
				continue
			if v.Cardinality()==variables.Cardinality.single:
				vInput.append(v.value)
			elif v.Cardinality()==variables.Cardinality.ordered:
				vInput=vInput+list(v.value)
			else:
				raise core.ProcessingError("Multiple or Record values not allowed in Ordered")
		# finally we have a matching list of input values
		result=variables.OrderedContainer(baseType)
		result.SetValue(vInput)
		return result			


class ContainerSize(UnaryOperator):
	"""The containerSize operator takes a sub-expression with any base-type and
	either multiple or ordered cardinality::
	
		<xsd:group name="containerSize.ContentGroup">
			<xsd:sequence>
				<xsd:group ref="expression.ElementGroup" minOccurs="1" maxOccurs="1"/>
			</xsd:sequence>
		</xsd:group>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'containerSize')
		
	def Evaluate(self,state):
		value=self.Expression.Evaluate(state)
		if value.Cardinality()==variables.Cardinality.ordered:
			if value:
				return variables.IntegerValue(len(value.value))
			else:
				return variables.IntegerValue(0)
		elif value.Cardinality()==variables.Cardinality.multiple:
			if value:
				# multiple containers are kept as a mapping to value frequencies
				sum=0
				for v in value.value.values():
					sum+=v
				return variables.IntegerValue(sum)
			else:
				return variables.IntegerValue(0)
		else:			
			raise core.ProcessingError("Ordered or Multiple value required for containerSize")


class IsNull(UnaryOperator):
	"""The isNull operator takes a sub-expression with any base-type and
	cardinality
	::
	
		<xsd:group name="isNull.ContentGroup">
			<xsd:sequence>
				<xsd:group ref="expression.ElementGroup" minOccurs="1" maxOccurs="1"/>
			</xsd:sequence>
		</xsd:group>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'isNull')
		
	def Evaluate(self,state):
		value=self.Expression.Evaluate(state)
		if value:
			return variables.BooleanValue(False)
		else:
			return variables.BooleanValue(True)
	

class Index(UnaryOperator):
	"""The index operator takes a sub-expression with an ordered container value
	and any base-type
	::
	
		<xsd:attributeGroup name="index.AttrGroup">
			<xsd:attribute name="n" type="integer.Type" use="required"/>
		</xsd:attributeGroup>
		
		<xsd:group name="index.ContentGroup">
			<xsd:sequence>
				<xsd:group ref="expression.ElementGroup" minOccurs="1" maxOccurs="1"/>
			</xsd:sequence>
		</xsd:group>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'index')
	XMLATTR_n=('n',xsi.DecodeInteger,xsi.EncodeInteger)
	
	def __init__(self,parent):
		UnaryOperator.__init__(self,parent)
		self.n=None

	def Evaluate(self,state):
		value=self.Expression.Evaluate(state)
		if value.Cardinality()==variables.Cardinality.ordered:
			result=variables.SingleValue.NewValue(value.baseType)
			if value:
				if self.n<1:
					raise core.ProcessingError("Index requires n>0, found %i"%self.n)
				elif self.n<=len(value.value):
					result.SetValue(value.value[self.n-1])
			return result
		else:
			# wrong cardinality
			raise core.ProcessingError("Index requires ordered value, found %s"%
				variables.Cardinality.EncodeValue(value.Cardinality()))


class FieldValue(UnaryOperator):
	"""The field-value operator takes a sub-expression with a record container
	value. The result is the value of the field with the specified
	fieldIdentifier::
	
		<xsd:attributeGroup name="fieldValue.AttrGroup">
			<xsd:attribute name="fieldIdentifier" type="identifier.Type" use="required"/>
		</xsd:attributeGroup>
		
		<xsd:group name="fieldValue.ContentGroup">
			<xsd:sequence>
				<xsd:group ref="expression.ElementGroup" minOccurs="1" maxOccurs="1"/>
			</xsd:sequence>
		</xsd:group>"""
	XMLNAME=(core.IMSQTI_NAMESPACE,'fieldValue')
	XMLATTR_fieldIdentifier=('fieldIdentifier',core.ValidateIdentifier,lambda x:x)
	
	def __init__(self,parent):
		UnaryOperator.__init__(self,parent)
		self.fieldIdentifier=''

	def Evaluate(self,state):
		value=self.Expression.Evaluate(state)
		if value.Cardinality()==variables.Cardinality.record:
			if self.fieldIdentifier in value:
				return value[self.fieldIdentifier]
			else:
				return variables.SingleValue()
		else:
			# wrong cardinality
			raise core.ProcessingError("fieldValue requires record value, found %s"%
				variables.Cardinality.EncodeValue(value.Cardinality()))
	
	