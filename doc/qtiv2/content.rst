Content Model
-------------

.. py:module:: pyslet.qtiv2.content

..	autoclass:: ItemBody
	:members:
	:show-inheritance:


..	autoclass:: BodyElement
	:members:
	:show-inheritance:


Basic Classes
~~~~~~~~~~~~~

Many of the basic classes are drawn directly from the :py:mod:`html401`
module, as a result there are slight modifications to some of the abstract base
class definitions. See :py:class:`~html401.InlineMixin`,
:py:class:`~html401.BlockMixin` and
:py:class:`~html401.FlowMixin`; there is no class corresponding to the
objectFlow concept (see :py:class:`~html401.Object` for more
information).  There is also no representation of the static base classes used
to exclude interactions or any of the other basic container classes, these are
all handled directly by their equivalent html abstractions.

..	autoclass:: FlowContainerMixin
	:members:
	:show-inheritance:


XHMTL Elements
~~~~~~~~~~~~~~

Again, these classes are defined in the accompanying :py:mod:`html401`
module, however we do define some profiles here to make it easier to constraint
general HTML content to the profile defined here.

..	autodata:: TextElements

..	autodata:: ListElements

..	autodata:: ObjectElements

..	autodata:: PresentationElements

..	autodata:: ImageElement

..	autodata:: HypertextElement

..	autodata:: HTMLProfile

