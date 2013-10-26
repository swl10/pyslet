#! /usr/bin/env python
"""OData core elements"""


ODATA_METADATA_NAMESPACE="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"	#: namespace for metadata, e.g., the property type attribute
IsDefaultEntityContainer=(ODATA_METADATA_NAMESPACE,u"IsDefaultEntityContainer")
MimeType=(ODATA_METADATA_NAMESPACE,u"MimeType")
HttpMethod=(ODATA_METADATA_NAMESPACE,u"HttpMethod")
HasStream=(ODATA_METADATA_NAMESPACE,u"HasStream")
DataServicesVersion=(ODATA_METADATA_NAMESPACE,"DataServiceVersion")
FC_KeepInContent=(ODATA_METADATA_NAMESPACE,"FC_KeepInContent")
FC_TargetPath=(ODATA_METADATA_NAMESPACE,"FC_TargetPath")
FC_NsPrefix=(ODATA_METADATA_NAMESPACE,"FC_NsPrefix")
FC_NsUri=(ODATA_METADATA_NAMESPACE,"FC_NsUri")
FC_SourcePath=(ODATA_METADATA_NAMESPACE,"FC_SourcePath")

ODATA_DATASERVICES_NAMESPACE="http://schemas.microsoft.com/ado/2007/08/dataservices"		#: namespace for auto-generated elements, e.g., :py:class:`Property`
ODATA_SCHEME="http://schemas.microsoft.com/ado/2007/08/dataservices/scheme"					#: category scheme for type definition terms
ODATA_RELATED="http://schemas.microsoft.com/ado/2007/08/dataservices/related/"				#: link type for related entries

ODATA_RELATED_ENTRY_TYPE="application/atom+xml;type=entry"
ODATA_RELATED_FEED_TYPE="application/atom+xml;type=feed"


class InvalidLiteral(Exception): pass
class InvalidServiceDocument(Exception): pass
class InvalidMetadataDocument(Exception): pass
class InvalidFeedDocument(Exception): pass
class InvalidEntryDocument(Exception): pass
class InvalidFeedURL(Exception): pass
class UnexpectedHTTPResponse(Exception): pass

class ServerError(Exception): pass
class BadURISegment(ServerError): pass
class MissingURISegment(ServerError): pass
class InvalidSystemQueryOption(ServerError): pass
class InvalidPathOption(ServerError): pass
class InvalidMethod(ServerError): pass
class InvalidData(ServerError): pass
class EvaluationError(Exception): pass
