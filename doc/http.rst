Hypertext Transfer Protocol (RFC2616)
=====================================

This sub-package defines functions and classes for working with HTTP as
defined by RFC2616: http://www.ietf.org/rfc/rfc2616.txt and RFC2617:
http://www.ietf.org/rfc/rfc2617.txt

The purpose of this module is to expose some of the basic constructs
(including the synax of protocol components) to allow them to be used
normatively in other contexts.  The module also contains a functional
HTTP client designed to support non-blocking and persistent HTTP client
operations.

.. toctree::
    :maxdepth: 2

    http/client
    http/auth
    http/messages
    http/params
    http/grammar
    http/cookie


