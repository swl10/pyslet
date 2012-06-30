Common Classes
--------------

.. py:module:: pyslet.qtiv1.common

This module contains the common data elements defined in section 3.6 of the
binding document. The doc string of each element defined by IMS is introduced
with a quote from that document to provide context.  For more information see:
http://www.imsglobal.org/question/qtiv1p2/imsqti_asi_bindv1p2.html


Content Model
~~~~~~~~~~~~~

Perhaps the biggest change between version 1 and version 2 of the specification
was the content model.  There were attempts to improve the original model through
the introduction of the flow concept in version 1.2 but it wasn't until the
externally defined HTML content model was formally adopted in version 2 that some
degree of predictability in rendering became possible.

..	autoclass:: ContentMixin
	:members:
	:show-inheritance:

..	autoclass:: Material
	:members:
	:show-inheritance:

..	autoclass:: AltMaterial
	:members:
	:show-inheritance:

..	autoclass:: MatThingMixin
	:members:
	:show-inheritance:

..	autoclass:: PositionMixin
	:members:
	:show-inheritance:

..	autoclass:: MatText
	:members:
	:show-inheritance:

..	autoclass:: MatEmText
	:members:
	:show-inheritance:

..	autoclass:: MatBreak
	:members:
	:show-inheritance:

..	autoclass:: MatImage
	:members:
	:show-inheritance:

..	autoclass:: MatAudio
	:members:
	:show-inheritance:

..	autoclass:: MatVideo
	:members:
	:show-inheritance:

..	autoclass:: MatApplet
	:members:
	:show-inheritance:

..	autoclass:: MatApplication
	:members:
	:show-inheritance:

..	autoclass:: MatRef
	:members:
	:show-inheritance:

..	autoclass:: MatExtension
	:members:
	:show-inheritance:

..	autoclass:: FlowMixin
	:members:
	:show-inheritance:

..	autoclass:: FlowMatContainer
	:members:
	:show-inheritance:

..	autoclass:: FlowMat
	:members:
	:show-inheritance:

..	autoclass:: PresentationMaterial
	:members:
	:show-inheritance:

..	autoclass:: Reference
	:members:
	:show-inheritance:

..	autoclass:: MaterialRef
	:members:
	:show-inheritance:



Metadata Model
~~~~~~~~~~~~~~

..	autoclass:: MetadataContainerMixin
	:members:
	:show-inheritance:

..	autoclass:: QTIMetadata
	:members:
	:show-inheritance:

..	autoclass:: Vocabulary
	:members:
	:show-inheritance:

..	autoclass:: QTIMetadataField
	:members:
	:show-inheritance:

..	autoclass:: FieldLabel
	:members:
	:show-inheritance:

..	autoclass:: FieldEntry
	:members:
	:show-inheritance:


Objectives & Rubric
~~~~~~~~~~~~~~~~~~~

..	autoclass:: Objectives
	:members:
	:show-inheritance:

..	autoclass:: Rubric
	:members:
	:show-inheritance:


Response Processing Model
~~~~~~~~~~~~~~~~~~~~~~~~~

..	autoclass:: DecVar
	:members:
	:show-inheritance:

..	autoclass:: InterpretVar
	:members:
	:show-inheritance:

..	autoclass:: SetVar
	:members:
	:show-inheritance:

..	autoclass:: DisplayFeedback
	:members:
	:show-inheritance:

..	autoclass:: ConditionVar
	:members:
	:show-inheritance:

..	autoclass:: ExtendableExpressionMixin
	:members:
	:show-inheritance:

..	autoclass:: ExpressionMixin
	:members:
	:show-inheritance:

..	autoclass:: VarThing
	:members:
	:show-inheritance:

..	autoclass:: VarEqual
	:members:
	:show-inheritance:

..	autoclass:: VarInequality
	:members:
	:show-inheritance:

..	autoclass:: VarLT
	:members:
	:show-inheritance:

..	autoclass:: VarLTE
	:members:
	:show-inheritance:

..	autoclass:: VarGT
	:members:
	:show-inheritance:

..	autoclass:: VarGTE
	:members:
	:show-inheritance:

..	autoclass:: VarSubset
	:members:
	:show-inheritance:

..	autoclass:: VarSubString
	:members:
	:show-inheritance:

..	autoclass:: VarInside
	:members:
	:show-inheritance:

..	autoclass:: DurEqual
	:members:
	:show-inheritance:

..	autoclass:: DurLT
	:members:
	:show-inheritance:

..	autoclass:: DurLTE
	:members:
	:show-inheritance:

..	autoclass:: DurGT
	:members:
	:show-inheritance:

..	autoclass:: DurGTE
	:members:
	:show-inheritance:

..	autoclass:: Not
	:members:
	:show-inheritance:

..	autoclass:: And
	:members:
	:show-inheritance:

..	autoclass:: Or
	:members:
	:show-inheritance:

..	autoclass:: Unanswered
	:members:
	:show-inheritance:

..	autoclass:: Other
	:members:
	:show-inheritance:

..	autoclass:: VarExtension
	:members:
	:show-inheritance:


Miscellaneous Classes
~~~~~~~~~~~~~~~~~~~~~


..	autoclass:: QTICommentContainer
	:members:
	:show-inheritance:

..	autoclass:: QTIComment
	:members:
	:show-inheritance:

..	autoclass:: Duration
	:members:
	:show-inheritance:
