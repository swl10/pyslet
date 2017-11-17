#! /usr/bin/env python


class ODataError(Exception):

    """Base error for OData exceptions"""
    pass


class ModelError(ODataError):

    """Base error for model exceptions"""
    pass


class ServiceError(ODataError):

    """General error in the data service

    ServiceErrors define two additional fields, the equivalent HTTP code
    and message string.  This saves having to define a lookup table in
    the specific case of the HTTP binding."""

    def __init__(self, message, http_code, http_msg):
        super(ServiceError, self).__init__(message)
        self.http_code = http_code
        self.http_msg = http_msg


class OptimisticConcurrencyError(ODataError):

    """Error raised by etag mismatch"""
    pass


class BoundValue(ODataError):

    """Raised when an operation is not permitted on a bound value"""
    pass


class InvalidEntityID(ODataError):

    """Raised when ID information is missing for an entity"""
    pass


class UnboundValue(ODataError):

    """Raised when an operation is not permitted on an unbound value"""
    pass


class FrozenValueError(ODataError):

    """Raised when an operation is not permitted on a frozen value"""
    pass


class DuplicateNameError(ModelError):

    """Raised when a duplicate name is encountered in a name table"""
    pass


class ObjectNotDeclaredError(ModelError):

    """Raised when an operation on an object is not permitted because
    the object has *not* been declared"""
    pass


class ObjectDeclaredError(ModelError):

    """Raised when an operation on an object is not permitted because
    the object has *already* been declared"""
    pass


class UndeclarationError(ModelError):

    """Raised when an attempt is made to undeclare a name in a name
    table"""
    pass


class NameTableClosed(ModelError):

    """Raised when an attempt to declare a name in a closed name table
    is made"""
    pass


class InheritanceCycleDetected(ModelError):

    """Raised when an inheritance cycle is detected in a model."""
    pass


class PathError(ODataError):

    """Raised during path traversal"""
    pass


class URLError(ODataError):

    """Base error for URL format exceptions"""
    pass


class FormatError(ODataError):

    """Raised when a payload formatting error is encountered."""
    pass


class Requirement(object):

    """Human friendly messages

    Each requirement in the OData specification is transcribed into a
    message string and defined as an attribute of this object.  This
    makes the code easier to read and facilitates the wholescale
    substitution of the messages for unittesting (and potentially
    translation, should the specification be translated into languages
    other than English)."""
    pass


class Req40(object):

    """OData 4.0 reference messages

    Used by unit tests to ensure correct error messages are being
    generated for invalid CSDL test cases."""
    pass

#
#  Part 1: Protocol
#
# Section 4: Service Model

# TODO
Requirement.entity_id_iri = (
    "The entity-id MUST be an IRI")
Req40.entity_id_iri = "4.0 P1 4.1 #1"

# Never raised as we don't validate clients
Requirement.entity_id_anyiri = (
    "The client MUST be prepared to accept any IRI for an entity-id")
Req40.entity_id_anyiri = "4.0 P1 4.1 #2"

# TODO
Requirement.entity_id_uri = (
    "Services MUST use valid URIs for entity ids")
Req40.entity_id_uri = "4.0 P1 4.1 #3"


# Section 5: Versioning

# TODO
Requirement.user_dependent = (
    "If a Service's data model is user or user group dependent, all "
    "changes MUST be safe changes")
Req40.user_dependent = "4.0 P1 5.2"


# Section 6: Extensibility

# TODO
Requirement.custom_option_name = (
    'Custom query options MUST NOT begin with the "$" or "@" character')
Req40.custom_option_name = "4.0 P1 6.1 #1"

# TODO
Requirement.unsupported_option_s = (
    "Services MUST fail any request that contains unsupported OData query "
    "options (%s)")
Req40.unsupported_option_s = "4.0 P1 6.1 #2 (%s)"

# TODO
Requirement.addition_content = (
    "Additional content MUST NOT be present if it needs to be understood "
    "by the receiver in order to correctly interpret the payload")
Req40.addition_content = "4.0 P1 6.2 #1"

# Not validated
Requirement.addition_content_ignored = (
    "Clients and services MUST be prepared to handle or safely ignore any "
    "content not specifically defined in the version of the payload")
Req40.addition_content_ignored = "4.0 P1 6.2 #2"

# Not validated
Requirement.function_side_effects = (
    "Functions MUST NOT have side-effects")
Req40.function_side_effects = "4.0 P1 6.3 #1"

# TODO
Requirement.unknown_function = (
    "An OData service MUST fail any request that contains actions or "
    "functions that it does not understand")
Req40.unknown_function = "4.0 P1 6.3 #2"

# Not validated
Requirement.custom_annotation_required = (
    "A service MUST NOT require the client to understand custom annotations "
    "in order to accurately interpret a response")
Req40.custom_annotation_required = "4.0 P1 6.4"

# TODO
Requirement.custom_header_name = (
    "Custom headers MUST NOT begin with OData")
Req40.custom_header_name = "4.0 P1 6.5 #1"

# Not validated
Requirement.custom_header_required = (
    "A service MUST NOT require the client to understand custom headers "
    "to accurately interpret the response")
Req40.custom_header_required = "4.0 P1 6.5 #2"

# Not validated
Requirement.service_format = (
    "An OData service MUST support at least one of [OData-JSON] or "
    "[OData-Atom]")
Req40.service_format = "4.0 P1 6.6"


# Section 7: Formats

# Not validated
Requirement.service_format = (
    "If both the Accept header and the $format query option are specified "
    "the $format query option MUST be used")
Req40.service_format = "4.0 P1 7 #1"

# Not validated
Requirement.array_order = (
    "Client libraries MUST retain the order of objects within an array in "
    "JSON responses")
Req40.array_order = "4.0 P1 7 #2"

# Not validated
Requirement.element_order = (
    "Client libraries MUST retain the order of elements in document order "
    "for Atom and XML responses, including CSDL documents")
Req40.element_order = "4.0 P1 7 #3"


# Section 8: Header Fields

# TODO
Requirement.element_order = (
    "The format of a non-empty individual request or response body MUST "
    "be specified in the Content-Type header")
Req40.element_order = "4.0 P1 8.1.1 #1"

# Not validated
Requirement.unexpected_format_param = (
    "Clients MUST be prepared for the service to return custom format "
    "parameters not specified in OData")
Req40.unexpected_format_param = "4.0 P1 8.1.1 #2"

# TODO
Requirement.format_param_name = (
    'Custom format parameters MUST NOT start with "odata"')
Req40.format_param_name = "4.0 P1 8.1.1 #3"

# Not validated
Requirement.custom_format_param_required = (
    "Services MUST NOT require generic OData consumers to understand "
    "custom format parameters in order to correctly interpret the payload")
Req40.custom_format_param_required = "4.0 P1 8.1.1 #4"

# TODO
Requirement.version_header = (
    "If an OData-Version header is present on a request, the service MUST "
    "interpret the request according to the specified version of the "
    "protocol, or fail the request")
Req40.version_header = "4.0 P1 8.1.5 #1"

# TODO
Requirement.no_version_header = (
    "If an OData-Version header is not specified in a request, the service "
    "MUST assume the minimum of the OData-MaxVersion and the maximum version "
    "of the protocol that the service understands")
Req40.no_version_header = "4.0 P1 8.1.5 #2"

# TODO
Requirement.version_required = (
    "OData services MUST include the OData-Version header on a response")
Req40.version_required = "4.0 P1 8.1.5 #3"

# Not validated
Requirement.version_processed = (
    "The client MUST interpret the response according to the rules "
    "defined by the OData-Version header")
Req40.version_processed = "4.0 P1 8.1.5 #4"

# TODO
Requirement.format_param_rejected = (
    "Services MUST reject formats that specify unknown or unsupported "
    "format parameters")
Req40.format_param_rejected = "4.0 P1 8.2.1 #1"

# TODO
Requirement.accept_charset = (
    "If the Accept header includes a charset format parameter and the "
    "request contains an Accept-Charset header, then the Accept-Charset "
    "header MUST be used")
Req40.accept_charset = "4.0 P1 8.2.1 #2"

# TODO
Requirement.charset_format_param = (
    "If the Accept header does not include a charset format parameter, "
    "then the Content-Type header of the response MUST NOT contain a "
    "charset format parameter")
Req40.charset_format_param = "4.0 P1 8.2.1 #3"

# TODO
Requirement.if_match = (
    "The value of the If-Match request header MUST be an ETag value "
    'previously retrieved for the entity, or "*" to match any value')
Req40.if_match = "4.0 P1 8.2.4 #1"

# TODO
Requirement.no_if_match = (
    "If an operation requires an ETag and the client does not specify an "
    "If-Match request header the service MUST ensure that no observable "
    "change occurs")
Req40.no_if_match = "4.0 P1 8.2.4 #2"

# TODO
Requirement.etag_match = (
    "If If-Match is specified, the request MUST only be processed if the "
    "specified value matches the current ETag of the target entity")
Req40.etag_match = "4.0 P1 8.2.4 #3"

# TODO
Requirement.etag_nomatch = (
    "If the If-Match value does not match the current ETag of the entity "
    "the service MUST respond with 412 Precondition Failed")
Req40.etag_match = "4.0 P1 8.2.4 #4"

# TODO
Requirement.etag_nomatch_change = (
    "If the If-Match value does not match the current ETag of the entity "
    "the service MUST ensure that no observable change occurs as a "
    "result of the request")
Req40.etag_match = "4.0 P1 8.2.4 #5"

# TODO
Requirement.if_none_match = (
    "The value of the If-None-Match request header MUST be an ETag value "
    'previously retrieved for the entity, or "*"')
Req40.if_none_match = "4.0 P1 8.2.5 #1"

# TODO
Requirement.not_etag_nomatch = (
    "If If-None-Match is specified the request MUST only be processed if "
    "the specified value does not match the current ETag of the entity")
Req40.not_etag_nomatch = "4.0 P1 8.2.5 #2"

# TODO
Requirement.not_etag_match = (
    "If the If-None-Match value matches the current ETag of the entity "
    "for a Data Modification Request or Action Request, the service MUST "
    "respond with 412 Precondition Failed")
Req40.not_etag_match = "4.0 P1 8.2.5 #3"

# TODO
Requirement.not_etag_match_change = (
    "If the If-None-Match value matches the current ETag of the entity "
    "for a Data Modification Request or Action Request, the service MUST "
    "ensure that no observable change occurs")
Req40.not_etag_match_change = "4.0 P1 8.2.5 #4"

# TODO
Requirement.isolation = (
    "If the service doesn't support OData-Isolation:snapshot the service "
    "MUST NOT process the request")
Req40.isolation = "4.0 P1 8.2.6 #1"

# TODO
Requirement.isolation_response = (
    "If the service doesn't support OData-Isolation:snapshot the service "
    "MUST respond with 412 Precondition Failed.")
Req40.isolation_response = "4.0 P1 8.2.6 #2"

# TODO
Requirement.max_version = (
    "If OData-MaxVersion is specified the service MUST generate a response "
    "with an OData-Version less than or equal to that version")
Req40.max_version = "4.0 P1 8.2.6 #3"

# TODO
Requirement.preferences = (
    "The service MUST ignore preference values that are not supported "
    "or known")
Req40.preferences = "4.0 P1 8.2.8"

# TODO
Requirement.allow_entityreferences = (
    "The service MUST NOT return entity references in place of requested "
    "entities if odata.allow-entityreferences has not been specified in "
    "the request")
Req40.allow_entityreferences = "4.0 P1 8.2.8.1 #1"

# TODO
Requirement.allow_entityreferences_applied = (
    "If the service applies the odata.allow-entityreferences preference it "
    "MUST include a Preference-Applied response header containing the "
    "odata.allow-entityreferences preference")
Req40.allow_entityreferences_applied = "4.0 P1 8.2.8.1 #2"

# TODO
Requirement.callback = (
    "The odata.callback preference MUST include the parameter url of a "
    "callback endpoint")
Req40.callback = "4.0 P1 8.2.8.2 #1"

# TODO
Requirement.callback_applied = (
    "If the service applies the odata.callback preference it MUST "
    "include the odata.callback preference in the Preference-Applied "
    "response header")
Req40.callback_applied = "4.0 P1 8.2.8.2 #2"

# Not validated
Requirement.multiple_callbacks = (
    "If the consumer specifies the same URL as callback endpoint in "
    "multiple requests it MUST be prepared to deal with receiving up to "
    "as many notifications as it requested")
Req40.multiple_callbacks = "4.0 P1 8.2.8.2 #3"

# Not validated
Requirement.batch_error = (
    "If odata.continue-on-error is not specified, upon encountering an "
    "error the service MUST return the error within the batch and stop")
Req40.batch_error = "4.0 P1 8.2.8.3"


# Section 11: Data Service Requests

# TODO
Requirement.service_document = (
    "OData services MUST support returning a service document from the "
    "root URL of the service")
Req40.service_document = "4.0 P1 11.1.1"

# TODO
Requirement.metadata_document = (
    "OData services MUST expose a metadata document that describes the "
    "data model exposed by the service")
Req40.metadata_document = "4.0 P1 11.1.2 #1"

# TODO
Requirement.metadata_url = (
    "The Metadata Document URL MUST be the root URL of the service with "
    "$metadata appended")
Req40.metadata_url = "4.0 P1 11.1.2 #2"

# TODO
Requirement.metadata_format = (
    "If a request for metadata does not specify a format preference "
    "then the XML representation MUST be returned")
Req40.metadata_format = "4.0 P1 11.1.2 #3"

# TODO
Requirement.metadata_service = (
    "A metadata service MUST use the schema defined by the CSDL")
Req40.metadata_service = "4.0 P1 11.1.3"

# TODO
Requirement.resource_expired = (
    "If a client subsequently requests an expired resource and it is "
    "not feasible to return 410 Gone then the service MUST respond with "
    "404 Not Found")
Req40.resource_expired = "4.0 P1 11.2 #1"

# TODO
Requirement.query_option_order = (
    "The result of a data request MUST be as if the system query options "
    "were evaluated in the specified order: search, filter, count, "
    "orderby, skip, top, expand, select and format")
Req40.query_option_order = "4.0 P1 11.2 #2"

# TODO
Requirement.additional_properties = (
    "Clients MUST be prepared to receive additional properties in an "
    "entity or complex type instance that are not advertised in metadata")
Req40.additional_properties = "4.0 P1 11.2.1 #1"

# TODO
Requirement.property_denied = (
    "The Core.Permissions annotation MUST be returned with a value of "
    "Core.Permission'None' for properties that are not available due to "
    "permissions")
Req40.property_denied = "4.0 P1 11.2.1 #2"

#
#  Part 2:
#
# Section 2: URL Components

# See test_odata4_service.URITests.test_from_str
Requirement.url_split = (
    "RFC3986 defined URL processing MUST be performed before "
    "percent-decoding")
Req40.url_split = "4.0 P2 2 #1"

# See test_odata4_service.URITests.test_from_str
Requirement.path_split = (
    'The undecoded path MUST be split into segments at "/"')
Req40.path_split = "4.0 P2 2 #2"

# See test_odata4_service.URITests.test_from_str
Requirement.query_split = (
    'The undecoded query MUST be split at "&" into query options, and '
    'each query option at the first "=" into query option name and query '
    'option value')
Req40.query_split = "4.0 P2 2 #3"

# See test_odata4_service.URITests.test_from_str
Requirement.percent_decode = (
    "Path segments, query option names, and query option values MUST be "
    "percent decoded exactly once")
Req40.percent_decode = "4.0 P2 2 #4"

#
# Part 3:
#
# Section 3: Entity Model Wrapper

Requirement.csdl_root = (
    "A CSDL document MUST contain a root edmx:Edmx element")
Req40.csdl_root = "4.0 P3 3.1 #1"

Requirement.csdl_data_services = (
    "[The root] element MUST contain a single direct child "
    "edmx:DataServices element")
Req40.csdl_data_services = "4.0 P3 3.1 #2"

Requirement.edmx_version = (
    "The edmx:Edmx element MUST provide the value 4.0 for the "
    "Version attribute")
Req40.edmx_version = "4.0 P3 3.1.1"

Requirement.schemas = (
    "The edmx:DataServices element MUST contain one or more edm:Schema "
    "elements")
Req40.schemas = "4.0 P3 3.2"

Requirement.reference = (
    "The edmx:Reference element MUST contain at least one edmx:Include or "
    "edmx:IncludeAnnotations child element")
Req40.reference = "4.0 P3 3.3"

Requirement.reference_uri = (
    "The edmx:Reference element MUST specify a Uri attribute")
Req40.reference_uri = "4.0 P3 3.3.1 #1"

Requirement.unique_reference = (
    "Two references MUST NOT specify the same URI")
Req40.unique_reference = "4.0 P3 3.3.1 #2"

Requirement.include_namespace = (
    "The edmx:Include element MUST provide a Namespace value for the "
    "Namespace attribute")
Req40.include_namespace = "4.0 P3 3.4.1 #1"

Requirement.include_schema_s = (
    "The value [of the Namespace attribute] MUST match the namespace of a "
    "schema defined in the referenced CSDL document (%s)")
Req40.include_schema_s = "4.0 P3 3.4.1 #2 (%s)"

Requirement.unique_include_s = (
    "The same namespace MUST NOT be included more than once (%s)")
Req40.unique_include_s = "4.0 P3 3.4.1 #3 (%s)"

Requirement.unique_namespace_s = (
    "A document MUST NOT assign the same alias to different namespaces and "
    "MUST NOT specify an alias with the same name as an in-scope "
    "namespace (%s)")
Req40.unique_namespace_s = "4.0 P3 3.4.2 #1 (%s)"

Requirement.reserved_namespace_s = (
    "The Alias attribute MUST NOT use the reserved values Edm, odata, "
    "System, or Transient (%s)")
Req40.reserved_namespace_s = "4.0 P3 3.4.2 #2 (%s)"

Requirement.term_namespace = (
    "An edmx:IncludeAnnotations element MUST provide a Namespace value for "
    "the TermNamespace attribute")
Req40.term_namespace = "4.0 P3 3.5.1"


# Section 4: Common Characteristics of Entity Models

Requirement.type_name = (
    "A nominal type has a name that MUST be a SimpleIdentifier")
Req40.type_name = "4.0 P3 4.1 #1"


Requirement.type_qname_s = (
    "The qualified type name MUST be unique within a model (%s)")
Req40.type_qname_s = (
    "4.0 P3 4.1 #2; 4.0 P3 5.1.1 #3; 4.0 P3 8.1.1 #2; 4.0 P3 9.1.1 #2; "
    "4.0 P3 10.1.1 #2; 4.0 P3 11.1.1 #2 (%s)")

# UNTESTED - violations are indistinguishable from the use of undeclared
# names
Requirement.type_ref = (
    "When referring to nominal types, the reference MUST use a "
    "Namespace-qualified name or an Alias-qualified name")
Req40.type_ref = "4.0 P3 4.1 #3"

Requirement.annotations_s = (
    "A model element MUST NOT specify more than one annotation for a "
    "given combination of Term and Qualifier attributes (%s)")
Req40.annotations_s = "4.0 P3 4.6 (%s)"


# Section 5: Schema

Requirement.unique_schema_child_s = (
    "Values of the Name attribute MUST be unique across all direct child "
    "elements of a schema (%s)")
Req40.unique_schema_child_s = "4.0 P3 5.1 (%s)"

Requirement.schema_name = (
    "All edm:Schema elements MUST have a namespace defined through a "
    "Namespace attribute")
Req40.schema_name = "4.0 P3 5.1.1 #1"

Requirement.schema_unique_s = (
    "The Schema Namespace attribute MUST be unique within the document (%s)")
Req40.schema_unique_s = "4.0 P3 5.1.1 #2 (%s)"

# Never raised: identical to Requirement.type_qname_s
Requirement.type_unique = (
    "Identifiers that are used to name types MUST be unique within a "
    "namespace")
Req40.type_unique = "4.0 P3 5.1.1 #3"

Requirement.reserved_schema_s = (
    "The Namespace attribute MUST NOT use the reserved values Edm, odata, "
    "System, or Transient (%s)")
Req40.reserved_schema_s = "4.0 P3 5.1.1 #4 (%s)"

Requirement.unique_alias_s = (
    "All edmx:Include and edm:Schema elements within a document MUST specify "
    "different values for the Alias attribute (%s)")
Req40.unique_alias_s = "4.0 P3 5.1.2 #1 (%s)"

Requirement.reserved_alias_s = (
    "The Alias attribute MUST NOT use the reserved values Edm, odata, "
    "System, or Transient (%s)")
Req40.reserved_alias_s = "4.0 P3 5.1.2 #2 (%s)"


# Section 6: Structural Property

# Never raised, see Requirement.property_unique_s
Requirement.property_unique = (
    "A property MUST specify a unique name")
Req40.property_unique = "4.0 P3 6.1 #1"

# Never raised, see Requirement.property_type_s
Requirement.property_type = (
    "A property MUST specify a type")
Req40.property_type = "4.0 P3 6.1 #2"

Requirement.property_name = (
    "The edm:Property element MUST include a Name attribute whose value "
    "is a SimpleIdentifier")
Req40.property_name = "4.0 P3 6.1.1 #1"

Requirement.property_unique_s = (
    "The name of the property MUST be unique within the set of "
    "structural and navigation properties of the containing structured "
    "type and any of its base types (%s)")
Req40.property_unique_s = (
    "4.0 P3 6.1 #1; 4.0 P3 6.1.1 #2; 4.0 P3 7.1.1 #2; 4.0 P3 8 #1 (%s)")

Requirement.property_type_s = (
    "The edm:Property element MUST include a Type attribute (%s)")
Req40.property_type_s = "4.0 P3 6.1 #2; 4.0 P3 6.1.2 #1 (%s)"

Requirement.property_type_declared_s = (
    "The value of the Type attribute MUST be the QualifiedName of a "
    "primitive type, complex type, or enumeration type in scope, or a "
    "collection of one of these types (%s)")
Req40.property_type_declared_s = "4.0 P3 6.1.2 #2 (%s)"

# TODO
Requirement.property_coll_exists = (
    "If the edm:Property element contains a Type attribute that specifies "
    "a collection, the property MUST always exist")
Req40.property_coll_exists = "4.0 P3 6.2.1 #1"

Requirement.decimal_precision = (
    "For a decimal property the Precision MUST be a positive integer")
Req40.decimal_precision = "4.0 P3 6.2.3 #1"

Requirement.temporal_precision = (
    "For a temporal property the Precision MUST be a non-negative integer "
    "between zero and twelve")
Req40.temporal_precision = "4.0 P3 6.2.3 #2"

# Probably untestable at runtime
Requirement.data_loss_precision = (
    "Client developers MUST be aware of the potential for data loss when "
    "round-tripping values of greater precision")
Req40.data_loss_precision = "4.0 P3 6.2.3 #3"

Requirement.scale_gt_precision = (
    "The value of the Scale attribute MUST be less than or equal to the "
    "value of the Precision attribute")
Req40.scale_gt_precision = "4.0 P3 6.2.4"

Requirement.srid_value = (
    "The value of the SRID attribute MUST be a non-negative integer or "
    "the special value variable")
Req40.srid_value = "4.0 P3 6.2.6"

# Never raised, the XML parser will fail if attribute values are invalid
Requirement.string_escape = (
    "Default values of type Edm.String MUST be represented according to the "
    "XML escaping rules for character data in attribute values")
Req40.string_escape = "4.0 P3 6.2.7 #1"

Requirement.primitive_default_s = (
    "Values of other primitive types MUST be represented according to the "
    "appropriate alternative in the primitiveValue rule (%s)")
Req40.primitive_default_s = "4.0 P3 6.2.7 #2 (%s)"


# Section 7: Navigation Property

Requirement.nav_name = (
    "The edm:NavigationProperty element MUST include a Name attribute whose "
    "value is a SimpleIdentifier")
Req40.nav_name = "4.0 P3 7.1.1 #1"

# Never raised, see Requirement.property_unique_s
Requirement.nav_unique = (
    "The name of the navigation property MUST be unique within the set of "
    "structural and navigation properties of the containing structured type "
    "and any of its base types")
Req40.nav_name = "4.0 P3 7.1.1 #2"

Requirement.nav_type_s = (
    "The edm:NavigationProperty element MUST include a Type attribute (%s)")
Req40.nav_type_s = "4.0 P3 7.1.2 #1 (%s)"

Requirement.nav_type_resolved_s = (
    "The value of the type attribute MUST resolve to an entity type or a "
    "collection of an entity type (%s)")
Req40.nav_type_resolved_s = "4.0 P3 7.1.2 #2 (%s)"

# TODO
Requirement.nav_type_related = (
    "The related entities MUST be of the specified entity type or one of "
    "its subtypes")
Req40.nav_type_resolved_s = "4.0 P3 7.1.2 #3"

Requirement.nav_collection_exists_s = (
    "A navigation property whose Type attribute specifies a collection "
    "MUST NOT specify a value for the Nullable attribute (%s)")
Req40.nav_collection_exists_s = "4.0 P3 7.1.3 (%s)"

Requirement.nav_partner_complex_s = (
    "The Partner attribute MUST NOT be specified for navigation properties "
    "of complex types (%s)")
Req40.nav_partner_complex_s = "4.0 P3 7.1.4 #1 (%s)"

Requirement.nav_partner_path_s = (
    "The Partner attribute MUST be a path from the entity type specified in "
    "the Type attribute to a navigation property defined on that type or a "
    "derived type (%s)")
Req40.nav_partner_path_s = "4.0 P3 7.1.4 #2 (%s)"

Requirement.nav_partner_nav_s = (
    "The Partner path MUST NOT traverse any navigation properties (%s)")
Req40.nav_partner_nav_s = "4.0 P3 7.1.4 #3 (%s)"

Requirement.nav_partner_type_s = (
    "The type of the partner navigation property MUST be the containing "
    "entity type of the current navigation property or one of its parent "
    "entity types (%s)")
Req40.nav_partner_type_s = "4.0 P3 7.1.4 #4 (%s)"

# TODO
Requirement.nav_partner_backlink = (
    "The partner navigation property MUST lead back to the source entity "
    "from all related entities")
Req40.nav_partner_backlink = "4.0 P3 7.1.4 #5"

# TODO
Requirement.nav_partner_multilink = (
    "If the Partner attribute identifies a multivalued navigation property, "
    "the source entity MUST be part of that collection")
Req40.nav_partner_multilink = "4.0 P3 7.1.4 #6"

Requirement.nav_partner_bidirection_s = (
    "The partner navigation property MUST either specify the current "
    "navigation property as its partner or it MUST NOT specify a partner "
    "attribute (%s)")
Req40.nav_partner_bidirection_s = "4.0 P3 7.1.4 #7 (%s)"

Requirement.nav_contains_s = (
    "Complex types declaring a containment navigation property MUST NOT "
    "be used as the type of a collection-valued property")
Req40.nav_contains_s = "4.0 P3 7.1.5 #1 (%s)"

Requirement.nav_contains_binding_s = (
    "Containment navigation properties MUST NOT be specified as the last "
    "path segment in the Path attribute of a navigation property binding (%s)")
Req40.nav_contains_binding_s = "4.0 P3 7.1.5 #2; 4.0 P3 13.4.1 #4 (%s)"

Requirement.nav_rcontains_s = (
    "If the containment is recursive, the partner navigation property MUST "
    "be nullable and specify a single entity type (%s)")
Req40.nav_rcontains_s = "4.0 P3 7.1.5 #3 (%s)"

Requirement.nav_nrcontains_s = (
    "If the containment is not recursive, the partner navigation property "
    "MUST NOT be nullable (%s)")
Req40.nav_nrcontains_s = "4.0 P3 7.1.5 #4 (%s)"

Requirement.nav_multi_contains_s = (
    "An entity type hierarchy MUST NOT contain more than one navigation "
    "property with a Partner attribute referencing a containment "
    "relationship (%s)")
Req40.nav_multi_contains_s = "4.0 P3 7.1.5 #5 (%s)"

# TODO
Requirement.ref_constraint_s = (
    "A referential constraint asserts that the dependent property MUST "
    "have the same value as the principal property (%s)")
Req40.ref_constraint_s = "4.0 P3 7.2 #1 (%s)"

Requirement.refcon_match_s = (
    "The type of the dependent property MUST match the type of the "
    "principal property (%s)")
Req40.refcon_match_s = "4.0 P3 7.2 #2; 4.0 P3 7.2.2 #3 (%s)"

Requirement.refcon_match_null_s = (
    "If the navigation property on which the referential constraint is "
    "defined or the principal property is nullable, then the dependent "
    "property MUST be nullable (%s)")
Req40.refcon_match_null_s = "4.0 P3 7.2 #3 (%s)"

Requirement.refcon_match_notnull_s = (
    "If both the navigation property and the principal property are not "
    "nullable, then the dependent property MUST be marked with the "
    "Nullable=\"false\" attribute value (%s)")
Req40.refcon_match_notnull_s = "4.0 P3 7.2 #4 (%s)"

Requirement.refcon_property_s = (
    "A referential constraint MUST specify a value for the Property "
    "attribute (%s)")
Req40.refcon_property_s = "4.0 P3 7.2.1 #1 (%s)"

Requirement.refcon_ppath_s = (
    "The Property attribute value MUST be a path expression resolving to "
    "a primitive property of the dependent entity type (%s)")
Req40.refcon_ppath_s = "4.0 P3 7.2.1 #2 (%s)"

Requirement.refcon_refprop_s = (
    "A referential constraint MUST specify a value for the "
    "ReferencedProperty attribute (%s)")
Req40.refcon_refprop_s = "4.0 P3 7.2.2 #1 (%s)"

Requirement.refcon_rppath_s = (
    "The ReferenceProperty attribute value MUST be a path expression "
    "resolving to a primitive property of the principal entity type (%s)")
Req40.refcon_rppath_s = "4.0 P3 7.2.2 #2 (%s)"

# Never raised: identical to Requirement.refcon_match_s
Requirement.refcon_rptype_s = (
    "The ReferencedProperty MUST have the same data type as the property "
    "of the dependent entity type (%s)")
Req40.refcon_rptype_s = "4.0 P3 7.2.2 #3 (%s)"

Requirement.ondelete_value = (
    "The edm:OnDelete element MUST include the Action attribute with "
    "one of the following values: Cascade, None, SetNull or SetDefault")
Req40.ondelete_value = "4.0 P3 7.2.3"


# Section 8: Entity Type

# Never raised: covered by Requirement.property_unique_s
Requirement.et_unique_names = (
    "All properties MUST have a unique name within an entity type.")
Req40.et_unique_names = "4.0 P3 8 #1"

Requirement.et_same_name_s = (
    "Properties MUST NOT have the same name as the declaring entity "
    "type (%s)")
Req40.et_same_name_s = "4.0 P3 8 #2 (%s)"

Requirement.et_name = (
    "The edm:EntityType element MUST include a Name attribute whose value "
    "is a SimpleIdentifier")
Req40.et_name = "4.0 P3 8.1.1 #1"

# Never raised: identical to Requirement.type_qname_s
Requirement.et_name_unique_s = (
    "The EntityType name MUST be unique within its namespace (%s)")
Req40.et_name_unique_s = "4.0 P3 8.1.1 #2 (%s)"

Requirement.et_cycle_s = (
    "An entity type MUST NOT introduce an inheritance cycle via the base "
    "type attribute (%s)")
Req40.et_cycle_s = "4.0 P3 8.1.2 (%s)"

Requirement.et_abstract_key_s = (
    "A non-abstract entity type MUST define a key or derive from a base "
    "type with a defined key (%s)")
Req40.et_abstract_key_s = "4.0 P3 8.1.3 #1; 4.0 P3 8.2 #1 (%s)"

Requirement.et_abstract_base_s = (
    "An abstract entity type MUST NOT inherit from a non-abstract entity "
    "type (%s)")
Req40.et_abstract_base_s = "4.0 P3 8.1.3 #2 (%s)"

Requirement.et_open_base_s = (
    "An entity type derived from an open entity type MUST NOT provide a "
    "value of false for the OpenType attribute (%s)")
Req40.et_open_base_s = "4.0 P3 8.1.4 #1 (%s)"

# Never raised: we don't validate clients
Requirement.et_extra_props = (
    "Clients MUST always be prepared to deal with additional properties on "
    "instances of any structured type")
Req40.et_extra_props = "4.0 P3 8.1.4 #2; 4.0 P3 9.1.4 #2"

Requirement.et_abstract_no_key_s = (
    "An entity type that is not abstract MUST either contain exactly one "
    "edm:Key element or inherit its key from its base type [not both] (%s)")
Req40.et_abstract_no_key_s = "4.0 P3 8.2 #1 (%s)"

Requirement.et_key_ref_s = (
    "The edm:Key element MUST contain at least one edm:PropertyRef "
    "element (%s)")
Req40.et_key_ref_s = "4.0 P3 8.2 #2 (%s)"

Requirement.key_nullable_s = (
    "The properties that compose the key MUST be non-nullable (%s)")
Req40.key_nullable_s = "4.0 P3 8.2 #3 (%s)"

Requirement.key_type_s = (
    "The properties that compose the key MUST be typed with an enumeration "
    "type or one of the allowed primitive types (%s)")
Req40.key_type_s = "4.0 P3 8.2 #4 (%s)"

# Never tested, this appears to be a constraint on usage
Requirement.key_langunique = (
    "The values of the properties that make up a primary key MUST be "
    "unique across all languages")
Req40.key_langunique = "4.0 P3 8.2 #5"

# Never tested, this appears to be a constraint on usage
Requirement.key_langindepdent = (
    "Entity ids MUST be language independent")
Req40.key_langindepdent = "4.0 P3 8.2 #6"

Requirement.key_name_s = (
    "The edm:PropertyRef element MUST specify a value for the Name "
    "attribute (%s)")
Req40.key_name_s = "4.0 P3 8.3.1 #1 (%s)"

Requirement.key_path_s = (
    "A key property MUST be a primitive property of the entity type itself "
    "or a primitive property of a complex property (%s)")
Req40.key_path_s = "4.0 P3 8.3.1 #2 (%s)"

Requirement.key_alias_s = (
    "If the property identified by the Name attribute is a member of a "
    "complex type, the edm:PropertyRef element MUST specify the Alias "
    "attribute [which must be a SimpleIdentifier] (%s)")
Req40.key_alias_s = "4.0 P3 8.3.2 #1; 4.0 P3 8.3.2 #2 (%s)"

# Never raised, this condition is trapped by Requirement.key_alias_s
Requirement.key_alias_type = (
    "The value of the Alias attribute MUST be a SimpleIdentifier")
Req40.key_alias_type = "4.0 P3 8.3.2 #2"

Requirement.key_alias_unique_s = (
    "The value of the Alias attribute MUST be unique within the set of "
    "aliases, structural and navigation properties of the containing entity "
    "type and any of its base types (%s)")
Req40.key_alias_unique_s = "4.0 P3 8.3.2 #3 (%s)"

Requirement.key_noalias_s = (
    "The Alias attribute MUST NOT be defined if the key property is not a "
    "member of a complex type (%s)")
Req40.key_noalias_s = "4.0 P3 8.3.2 #4 (%s)"

# TODO
Requirement.key_alias_predicate = (
    "For keys that are members of complex types, the alias MUST be used in "
    "the key predicate of URLs instead of the value assigned to the Name "
    "attribute")
Req40.key_alias_predicate = "4.0 P3 8.3.2 #5"

# TODO
Requirement.key_alias_query = (
    "The key alias MUST NOT be used in the query part")
Req40.key_alias_query = "4.0 P3 8.3.2 #6"


# Section 9: Complex Type

# Never raised: covered by Requirement.property_unique_s
Requirement.ct_unique_names = (
    "All properties MUST have a unique name within a complex type")
Req40.key_alias_query = "4.0 P3 9 #1"

Requirement.ct_same_name_s = (
    "Properties MUST NOT have the same name as the declaring complex "
    "type (%s)")
Req40.ct_same_name_s = "4.0 P3 9 #2 (%s)"

Requirement.ct_name = (
    "The edm:ComplexType element MUST include a Name attribute whose "
    "value is a SimpleIdentifier")
Req40.ct_name = "4.0 P3 9.1.1 #1"

# Never raised: identical to Requirement.type_qname_s
Requirement.ct_name_unique_s = (
    "The ComplexType name MUST be unique within its namespace (%s)")
Req40.ct_name_unique_s = "4.0 P3 9.1.1 #2 (%s)"

Requirement.ct_cycle_s = (
    "A complex type MUST NOT introduce an inheritance cycle via the base "
    "type attribute (%s)")
Req40.ct_cycle_s = "4.0 P3 9.1.2 (%s)"

Requirement.ct_open_base_s = (
    "A complex type derived from an open complex type MUST NOT provide a "
    "value of false for the OpenType attribute (%s)")
Req40.ct_open_base_s = "4.0 P3 9.1.4 #1 (%s)"

# Identical to Requirement.et_extra_props
Requirement.ct_extra_props = (
    "Clients MUST always be prepared to deal with additional properties on "
    "instances of any structured type")
Req40.ct_extra_props = "4.0 P3 9.1.4 #2"


# Section 10: Enumeration Type

Requirement.ent_name = (
    "The edm:EnumType element MUST include a Name attribute whose value "
    "is a SimpleIdentifier")
Req40.ent_name = "4.0 P3 10.1.1 #1"

# Never raised: identical to Requirement.type_qname_s
Requirement.ent_name_unique_s = (
    "The EnumType name MUST be unique within its namespace (%s)")
Req40.ent_name_unique_s = "4.0 P3 10.1.1 #2 (%s)"

Requirement.ent_type_s = (
    "The UnderlyingType of an enumeration MUST be one of Edm.Byte, "
    "Edm.SByte, Edm.Int16, Edm.Int32, or Edm.Int64 (%s)")
Req40.ent_type_s = "4.0 P3 10.1.2 (%s)"

Requirement.ent_member_name = (
    "Each edm:Member element MUST include a Name attribute whose value is "
    "a SimpleIdentifier")
Req40.ent_member_name = "4.0 P3 10.2.1 #1"

Requirement.ent_member_unique_s = (
    "The enumeration type MUST NOT declare two members with the same "
    "name (%s)")
Req40.ent_member_unique_s = "4.0 P3 10.2.1 #2 (%s)"

Requirement.ent_auto_value_s = (
    "If the IsFlags attribute has a value of false, either all enumeration "
    "members MUST specify an integer value for the Value attribute, or all "
    "members MUST NOT specify a value for the Value attribute (%s)")
Req40.ent_auto_value_s = "4.0 P3 10.2.2 #1 (%s)"

# Never raised, we do not validate other libraries
Requirement.ent_auto_order = (
    "Client libraries MUST preserve elements in document order")
Req40.ent_auto_order = "4.0 P3 10.2.2 #2"

Requirement.ent_nonauto_value_s = (
    "If the IsFlags attribute has a value of true, a non-negative integer "
    "value MUST be specified for the enumeration member's Value "
    "attribute (%s)")
Req40.ent_nonauto_value_s = "4.0 P3 10.2.2 #3 (%s)"

Requirement.ent_valid_value_s = (
    "The value of an enumeration member MUST be a valid value for the "
    "UnderlyingType of the enumeration type (%s)")
Req40.ent_valid_value_s = "4.0 P3 10.2.2 #4 (%s)"


# Section 11: Type Definition

Requirement.td_name = (
    "The edm:TypeDefinition element MUST include a Name attribute whose "
    "value is a SimpleIdentifier")
Req40.td_name = "4.0 P3 11.1.1 #1"

# Never raised: identical to Requirement.type_qname_s
Requirement.td_name_unique_s = (
    "The TypeDefinition name MUST be unique within its namespace (%s)")
Req40.td_name_unique_s = "4.0 P3 11.1.1 #2 (%s)"

Requirement.td_qname_s = (
    "The edm:TypeDefinition element MUST provide the QualifiedName of a "
    "primitive type as the value of the UnderlyingType attribute (%s)")
Req40.td_qname_s = "4.0 P3 11.1.2 #1 (%s)"

Requirement.td_redef_s = (
    "The underlying type of a type definition MUST NOT be another type "
    "definition (%s)")
Req40.td_redef_s = "4.0 P3 11.1.2 #2 (%s)"

Requirement.td_facet_s = (
    "Facets specified in the type definition MUST NOT be re-specified when "
    "the type definition is used (%s)")
Req40.td_facet_s = "4.0 P3 11.1.3 #1 (%s)"

Requirement.td_annotation_s = (
    "The use of a type definition MUST NOT specify an annotation specified "
    "in the type definition (%s)")
Req40.td_annotation_s = "4.0 P3 11.1.3 #2 (%s)"


# Section 13: Entity Container

Requirement.one_container = (
    "Each metadata document used to describe an OData service MUST define "
    "exactly one entity container")
Req40.one_container = "4.0 P3 13"

Requirement.container_names_s = (
    "Entity set, singleton, action import, and function import names MUST "
    "be unique within an entity container (%s)")
Req40.container_names_s = "4.0 P3 13.1 (%s)"

Requirement.container_name_s = (
    "The edm:EntityContainer element MUST provide a unique SimpleIdentifier "
    "value for the Name attribute (%s)")
Req40.container_name_s = "4.0 P3 13.1.1 (%s)"

Requirement.entity_set_name = (
    "The edm:EntitySet element MUST include a Name attribute whose value "
    "is a SimpleIdentifier")
Req40.entity_set_name = "4.0 P3 13.2.1"

Requirement.entity_set_type_s = (
    "The edm:EntitySet element MUST include an EntityType attribute whose "
    "value is the QualifiedName of an entity type in scope (%s)")
Req40.entity_set_type_s = "4.0 P3 13.2.2 #1 (%s)"

# TODO - validate response from badly behaved service
Requirement.entity_set_instances = (
    "An entity set MUST contain only instances of the entity type specified "
    "by the EntityType attribute or its subtypes")
Req40.entity_set_instances = "4.0 P3 13.2.2 #2"

Requirement.entity_set_abstract_s = (
    "The entity type named by the EntityType attribute MAY be abstract but "
    "MUST have a key defined (%s)")
Req40.entity_set_abstract_s = "4.0 P3 13.2.2 #3 (%s)"

Requirement.singleton_name = (
    "The edm:Singleton element MUST include a Name attribute whose value is "
    "a SimpleIdentifier")
Req40.singleton_name = "4.0 P3 13.3.1"

Requirement.singleton_type_s = (
    "The edm:Singleton element MUST include a Type attribute whose value "
    "is the QualifiedName of an entity type in scope (%s)")
Req40.singleton_type_s = "4.0 P3 13.3.2 #1 (%s)"

# TODO - validate response from badly behaved service
Requirement.singleton_instance = (
    "A singleton MUST reference an instance of the entity type specified "
    "by the Type attribute")
Req40.singleton_instance = "4.0 P3 13.3.2 #2"

# TODO - issue with non-uniqueness of keys!
Requirement.unbound_navigation = (
    "If the navigation property binding is omitted, clients MUST assume "
    "that the target entity set or singleton can vary per related entity")
Req40.unbound_navigation = "4.0 P3 13.4"

Requirement.navbinding_path_s = (
    "A navigation property binding MUST name a navigation property of "
    "the entity set's, singleton's, or containment navigation property's "
    "entity type or one of its subtypes in the Path attribute (%s)")
Req40.navbinding_path_s = "4.0 P3 13.4.1 #1-#3 (%s)"

# Never raised: caught by Requirement.navbinding_path_s
Requirement.navbinding_path_qname_s = (
    "If the navigation property is defined on a subtype, the path attribute "
    "MUST contain the QualifiedName of the subtype (%s)")
Req40.navbinding_path_qname_s = "4.0 P3 13.4.1 #2 (%s)"

# Never raised: caught by Requirement.navbinding_path_s
Requirement.navbinding_path_complex_s = (
    "If the navigation property is defined on a complex type used in the "
    "definition of the entity set's entity type, the path attribute MUST "
    "contain a forward-slash separated list of complex property names (%s)")
Req40.navbinding_path_complex_s = "4.0 P3 13.4.1 #3 (%s)"

# identical to Requirement.nav_contains_binding_s
Requirement.navbind_contain_s = (
    "The navigation binding path can traverse one or more containment "
    "navigation properties but the last segment MUST be a non-containment "
    "navigation property (%s)")
Req40.navbind_contain_s = "4.0 P3 13.4.1 #4 (%s)"

Requirement.navbind_noncontain_s = (
    "In the navigation binding path there MUST NOT be any non-containment "
    "navigation properties prior to the final segment (%s)")
Req40.navbind_noncontain_s = "4.0 P3 13.4.1 #5; 4.0 P3 13.4.2 #3 (%s)"

Requirement.navbinding_unique_s = (
    "A navigation property MUST NOT be named in more than one navigation "
    "property binding (%s)")
Req40.navbinding_unique_s = "4.0 P3 13.4.1 #6 (%s)"

Requirement.navbinding_target_s = (
    "A navigation property binding MUST specify a SimpleIdentifier or "
    "TargetPath value for the Target attribute (%s)")
Req40.navbinding_target_s = "4.0 P3 13.4.2 #1 (%s)"

Requirement.navbinding_simple_target_s = (
    "If the value of the Target attribute is a SimpleIdentifier, it MUST "
    "resolve to an entity set or singleton defined in the same entity "
    "container as the enclosing element (%s)")
Req40.navbinding_simple_target_s = "4.0 P3 13.4.2 #2 (%s)"

# Never raised, simply a restatement of Requirement.navbind_noncontain_s
Requirement.navbinding_noncontain_path = (
    "If the value of the Target attribute is a TargetPath there MUST not "
    "be any noncontainment navigation properties prior to the final segment")
Req40.navbinding_noncontain_path = "4.0 P3 13.4.2 #3"


# Section 14 Vocabulary and Annotation

Requirement.term_name = (
    "The edm:Term element MUST include a Name attribute whose value is "
    "a SimpleIdentifier")
Req40.term_name = "4.0 P3 14.1.1"

Requirement.term_type_s = (
    "The edm:Term element MUST include a Type attribute whose value is "
    "a TypeName (%s)")
Req40.term_type_s = "4.0 P3 14.1.2 (%s)"

Requirement.term_base_s = (
    "The value of the BaseTerm attribute MUST be the name of a term in "
    "scope (%s)")
Req40.term_base_s = "4.0 P3 14.1.3 #1 (%s)"

# TODO as unitest on Annotatable
Requirement.term_base_applied_s = (
    "the base term MUST also be applied with the same qualifier (%s)")
Req40.term_base_applied_s = "4.0 P3 14.1.3 #2 (%s)"

# Never raised, handled by the underlying XML parser
Requirement.term_string_default = (
    "Default values of type Edm.String MUST be represented according to "
    "the XML escaping rules for character data in attribute values")
Req40.term_string_default = "4.0 P3 14.1.4 #1"

Requirement.term_prim_default_s = (
    "Values of primitive types other than Edm.String MUST be represented "
    "according to the appropriate primitiveValue (%s)")
Req40.term_prim_default_s = "4.0 P3 14.1.4 #2 (%s)"

Requirement.annotations_children = (
    "The edm:Annotations element MUST contain at least one "
    "edm:Annotation element")
Req40.annotations_children = "4.0 P3 14.2"

Requirement.annotations_target = (
    "The edm:Annotations element MUST include a Target attribute whose "
    "value is a path expression")
Req40.annotations_target = "4.0 P3 14.2.1 #1"

Requirement.annotations_target_s = (
    "The Target attribute MUST resolve to a model element in the entity "
    "model (%s)")
Req40.annotations_target_s = "4.0 P3 14.2.1 #2 (%s)"

Requirement.annotation_term = (
    "An annotation element MUST provide a QualifiedName value for the "
    "Term attribute")
Req40.annotation_term = "4.0 P3 14.3.1 #1"

Requirement.annotation_term_declared_s = (
    "The value of the Term attribute MUST be the name of a term in scope (%s)")
Req40.annotation_term_declared_s = "4.0 P3 14.3.1 #2 (%s)"

Requirement.annotation_applies_s = (
    "The target of the annotation MUST comply with any AppliesTo "
    "constraint (%s)")
Req40.annotation_applies_s = "4.0 P3 14.3.1 #3 (%s)"

Requirement.annotation_qualifier_s = (
    "Annotation elements MUST NOT provide a value for the qualifier "
    "attribute if the parent edm:Annotations element provides one (%s)")
Req40.annotation_qualifier_s = "4.0 P3 14.3.2 (%s)"

Requirement.annotation_binary_s = (
    "A binary expression MUST be assigned a value conforming to the rule "
    "binaryValue (%s)")
Req40.annotation_binary_s = "4.0 P3 14.4.1 (%s)"

Requirement.annotation_bool_s = (
    "A Boolean expression MUST be assigned a Boolean value (%s)")
Req40.annotation_bool_s = "4.0 P3 14.4.2 (%s)"

Requirement.annotation_date_s = (
    "A date expression MUST be assigned a value of type xs:date and "
    "also conform to rule dateValue; it MUST NOT contain a time-zone "
    "offset (%s)")
Req40.annotation_date_s = "4.0 P3 14.4.3 (%s)"

Requirement.annotation_datetime_s = (
    "A date/time expression MUST be assigned a value of type "
    "xs:dateTimeStamp and also conform to rule dateTimeOffsetValue; it "
    "MUST NOT contain an end-of-day fragment (%s)")
Req40.annotation_datetime_s = "4.0 P3 14.4.4 (%s)"

Requirement.annotation_decimal_s = (
    "A decimal expression MUST be assigned a value conforming to the rule "
    "decimalValue (%s)")
Req40.annotation_decimal_s = "4.0 P3 14.4.5 (%s)"

Requirement.annotation_duration_s = (
    "A duration expression MUST be assigned a value of type "
    "xs:dayTimeDuration (%s)")
Req40.annotation_duration_s = "4.0 P3 14.4.6 (%s)"

Requirement.annotation_enum_s = (
    "An enumeration member expression MUST be assigned a value that "
    "consists of the qualified name of the enumeration type, followed "
    "the name of the member (%s)")
Req40.annotation_enum_s = "4.0 P3 14.4.7 #1 (%s)"

Requirement.annotation_enum_member_s = (
    "Each enumeration member value MUST resolve to the name of a member of "
    "the enumeration type of the specified term (%s)")
Req40.annotation_enum_member_s = "4.0 P3 14.4.7 #2 (%s)"

Requirement.annotation_float_s = (
    "A float expression MUST be assigned a value conforming to the "
    "rule doubleValue (%s)")
Req40.annotation_float_s = "4.0 P3 14.4.8 (%s)"

Requirement.annotation_guid_s = (
    "A guid expression MUST be assigned a value conforming to the rule "
    "guidValue (%s)")
Req40.annotation_guid_s = "4.0 P3 14.4.9 (%s)"

Requirement.annotation_int_s = (
    "An integer MUST be assigned a value conforming to the rule "
    "int64Value (%s)")
Req40.annotation_int_s = "4.0 P3 14.4.10 (%s)"

# Checked by the underlying XML parser only, never raised
Requirement.annotation_string_s = (
    "A string expression MUST be assigned a value of the type xs:string (%s)")
Req40.annotation_string_s = "4.0 P3 14.4.11 (%s)"

Requirement.annotation_time_s = (
    "A time-of-day expression MUST be assigned a value conforming to the "
    "rule timeOfDayValue (%s)")
Req40.annotation_time_s = "4.0 P3 14.4.12 (%s)"

Requirement.annotation_path_s = (
    "The edm:AnnotationPath expression uses the same syntax as edm:Path "
    "except that the last path segment MUST be a term cast (%s)")
Req40.annotation_path_s = "4.0 P3 14.5.2 (%s)"


#
#  JSON Format
#
# Section 5: Service Document

Requirement.service_context = (
    "The value of the odata.context property MUST be the URL of the "
    "metadata document, without any fragment part")
Req40.service_context = "4.0 JSON 5 #1"
