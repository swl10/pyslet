PEP-8 Compatibility
===================

.. py:module:: pyslet.pep8


..  class:: MigratedClass

    Base class to assist with method renaming.  This base class defines
    a metaclass for use in conjunction with the @old_method decorator. 
    It automatically provides old method definitions that generate
    warnings when first called.
    
    Any derived classes will also be defined with this metaclass
    (providing they don't themselves use an overriding metaclass of
    course).  Therefore, the associated metaclass also checks each
    derived class to see if it has overridden any old methods, renaming
    those definitions accordingly in order to preserve the purpose of
    the original decorator.  An example will help::
    
        class Base(pep8.MigratedClass):

            @pep8.old_method('OldName')
            def new_name(self):
                return "Found it!"        
        
    With these definitions, the author of Base has renamed a method
    previously called 'OldName' to 'new_name'.  Authors of older
    code are unaware and continue to use the old name.  The metaclass
    provides the magic to ensure their code does not break::
    
        >>> b = Base()
        >>> b.OldName()
        __main__:1: DeprecationWarning: Base.OldName is deprecated, use,
            new_name instead
        'Found it!'

    The warning is only shown when python is run with the -Wd option.
    
    The metadata also handles the slightly harder problem of dealing
    with derived classes that must work with new code::
    
        class Derived(Base):
        
            def OldName(self):
                return "My old code works!"

        >>> d = Derived()
        >>> d.new_name()
        'My old code works!'
        
    Although more complex, the same is true for class methods.  When
    using the @classmethod decorator you must put it *before* the
    old_method decorator, like this::
    
        @classmethod
        @pep8.old_method('OldClassMethod')
        def new_class_method(cls):
            return "Found it!"

    And similarly for staticmethod::
    
        @staticmethod
        @pep8.old_method('OldStaticMethod')
        def new_static_method():
            return "Found it!"
            
    Again, older code that uses old names will have their calls
    automatically redirected to the new methods and derived classes that
    provide an implementation using the old names will find that their
    implementation is also callable with the new names.
             
    The power of metaclasses means that there is no significant
    performance hit as the extra work is largely done during the
    definition of the class so typically affects module load times
    rather than instance creation and method calling.  Calling the old
    names *is* slower as calls are directed through a wrapper which
    generates the deprecation warnings.  This provides an incentive to
    migrate older code to use the new names of course."""


..  autofunction:: make_attr_name


