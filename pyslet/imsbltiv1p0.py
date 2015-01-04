#! /usr/bin/env python
"""This module implements the Basic LTI 1.0 specification defined by IMS GLC

This is an experimental module and subject to significant change in future
releases.  Use with caution.
"""

import logging
import os
import random
import string
import time
import urlparse

from hashlib import sha256

import pyslet.odata2.csdl as edm
import pyslet.odata2.core as odata
import pyslet.odata2.metadata as edmx
import pyslet.odata2.sqlds as sql
import pyslet.wsgi as wsgi

from pyslet.pep8 import renamed_method
from pyslet.rfc2396 import URI
from pyslet.urn import URN

try:
    from oauthlib import oauth1 as oauth
    got_oauth = True
except ImportError:
    # at some point in the future, we may just replace the signature
    # verification code with something from the newer oauthlib, if
    # similar functionality can easily be exposed.
    got_oauth = False

    class OAuthMissing(object):

        def __init__(*args, **kwargs):
            raise RuntimeError("oauthlib module required")

    class oauth(object):    # noqa
        RequestValidator = OAuthMissing
        SignatureOnlyEndpoint = OAuthMissing


#: The version of LTI we support
LTI_VERSION = "LTI-1p0"

#: The message type we support
LTI_MESSAGE_TYPE = "basic-lti-launch-request"


class LTIError(Exception):

    """Base class for all LTI errors"""
    pass


class LTIAuthenticationError(LTIError):

    """Indicates an authentication error (on launch)"""
    pass


class LTIProtocolError(LTIError):

    """Indicates a protocol violoation

    This may be raised if the message type or protocol version in a
    launch request do not match the expected values or if a required
    parameter is missing."""
    pass


#: A mapping from a system role handle to the full URN for the role as a
#: :class:`~pyslet.rfc2396.URI` instance.
SYSROLE_HANDLES = {
    'SysAdmin': URI.from_octets('urn:lti:sysrole:ims/lis/SysAdmin'),
    'SysSupport': URI.from_octets('urn:lti:sysrole:ims/lis/SysSupport'),
    'Creator': URI.from_octets('urn:lti:sysrole:ims/lis/Creator'),
    'AccountAdmin': URI.from_octets('urn:lti:sysrole:ims/lis/AccountAdmin'),
    'User': URI.from_octets('urn:lti:sysrole:ims/lis/User'),
    'Administrator': URI.from_octets('urn:lti:sysrole:ims/lis/Administrator'),
    'None': URI.from_octets('urn:lti:sysrole:ims/lis/None')
}

#: A mapping from a institution role handle to the full URN for the role
#: as a :class:`~pyslet.rfc2396.URI` instance.
INSTROLE_HANDLES = {
    'Student': URI.from_octets('urn:lti:instrole:ims/lis/Student'),
    'Faculty': URI.from_octets('urn:lti:instrole:ims/lis/Faculty'),
    'Member': URI.from_octets('urn:lti:instrole:ims/lis/Member'),
    'Learner': URI.from_octets('urn:lti:instrole:ims/lis/Learner'),
    'Instructor': URI.from_octets('urn:lti:instrole:ims/lis/Instructor'),
    'Mentor': URI.from_octets('urn:lti:instrole:ims/lis/Mentor'),
    'Staff': URI.from_octets('urn:lti:instrole:ims/lis/Staff'),
    'Alumni': URI.from_octets('urn:lti:instrole:ims/lis/Alumni'),
    'ProspectiveStudent':
        URI.from_octets('urn:lti:instrole:ims/lis/ProspectiveStudent'),
    'Guest': URI.from_octets('urn:lti:instrole:ims/lis/Guest'),
    'Other': URI.from_octets('urn:lti:instrole:ims/lis/Other'),
    'Administrator': URI.from_octets('urn:lti:instrole:ims/lis/Administrator'),
    'Observer': URI.from_octets('urn:lti:instrole:ims/lis/Observer'),
    'None': URI.from_octets('urn:lti:instrole:ims/lis/None')
}

#: A mapping from LTI role handles to the full URN for the role as a
#: :class:`~pyslet.rfc2396.URI` instance.
ROLE_HANDLES = {
    'Learner': URI.from_octets('urn:lti:role:ims/lis/Learner'),
    'Learner/Learner': URI.from_octets('urn:lti:role:ims/lis/Learner/Learner'),
    'Learner/NonCreditLearner':
        URI.from_octets('urn:lti:role:ims/lis/Learner/NonCreditLearner'),
    'Learner/GuestLearner':
        URI.from_octets('urn:lti:role:ims/lis/Learner/GuestLearner'),
    'Learner/ExternalLearner':
        URI.from_octets('urn:lti:role:ims/lis/Learner/ExternalLearner'),
    'Learner/Instructor':
        URI.from_octets('urn:lti:role:ims/lis/Learner/Instructor'),
    'Instructor': URI.from_octets('urn:lti:role:ims/lis/Instructor'),
    'Instructor/PrimaryInstructor':
        URI.from_octets('urn:lti:role:ims/lis/Instructor/PrimaryInstructor'),
    'Instructor/Lecturer':
        URI.from_octets('urn:lti:role:ims/lis/Instructor/Lecturer'),
    'Instructor/GuestInstructor':
        URI.from_octets('urn:lti:role:ims/lis/Instructor/GuestInstructor'),
    'Instructor/ExternalInstructor':
        URI.from_octets('urn:lti:role:ims/lis/Instructor/ExternalInstructor'),
    'ContentDeveloper':
        URI.from_octets('urn:lti:role:ims/lis/ContentDeveloper'),
    'ContentDeveloper/ContentDeveloper':
        URI.from_octets('urn:lti:role:ims/lis/ContentDeveloper/'
                        'ContentDeveloper'),
    'ContentDeveloper/Librarian':
        URI.from_octets('urn:lti:role:ims/lis/ContentDeveloper/Librarian'),
    'ContentDeveloper/ContentExpert':
        URI.from_octets('urn:lti:role:ims/lis/ContentDeveloper/ContentExpert'),
    'ContentDeveloper/ExternalContentExpert':
        URI.from_octets('urn:lti:role:ims/lis/ContentDeveloper/'
                        'ExternalContentExpert'),
    'Member': URI.from_octets('urn:lti:role:ims/lis/Member'),
    'Member/Member': URI.from_octets('urn:lti:role:ims/lis/Member/Member'),
    'Manager': URI.from_octets('urn:lti:role:ims/lis/Manager'),
    'Manager/AreaManager':
        URI.from_octets('urn:lti:role:ims/lis/Manager/AreaManager'),
    'Manager/CourseCoordinator':
        URI.from_octets('urn:lti:role:ims/lis/Manager/CourseCoordinator'),
    'Manager/Observer':
        URI.from_octets('urn:lti:role:ims/lis/Manager/Observer'),
    'Manager/ExternalObserver':
        URI.from_octets('urn:lti:role:ims/lis/Manager/ExternalObserver'),
    'Mentor': URI.from_octets('urn:lti:role:ims/lis/Mentor'),
    'Mentor/Mentor': URI.from_octets('urn:lti:role:ims/lis/Mentor/Mentor'),
    'Mentor/Reviewer': URI.from_octets('urn:lti:role:ims/lis/Mentor/Reviewer'),
    'Mentor/Advisor': URI.from_octets('urn:lti:role:ims/lis/Mentor/Advisor'),
    'Mentor/Auditor': URI.from_octets('urn:lti:role:ims/lis/Mentor/Auditor'),
    'Mentor/Tutor': URI.from_octets('urn:lti:role:ims/lis/Mentor/Tutor'),
    'Mentor/LearningFacilitator':
        URI.from_octets('urn:lti:role:ims/lis/Mentor/LearningFacilitator'),
    'Mentor/ExternalMentor':
        URI.from_octets('urn:lti:role:ims/lis/Mentor/ExternalMentor'),
    'Mentor/ExternalReviewer':
        URI.from_octets('urn:lti:role:ims/lis/Mentor/ExternalReviewer'),
    'Mentor/ExternalAdvisor':
        URI.from_octets('urn:lti:role:ims/lis/Mentor/ExternalAdvisor'),
    'Mentor/ExternalAuditor':
        URI.from_octets('urn:lti:role:ims/lis/Mentor/ExternalAuditor'),
    'Mentor/ExternalTutor':
        URI.from_octets('urn:lti:role:ims/lis/Mentor/ExternalTutor'),
    'Mentor/ExternalLearningFacilitator':
        URI.from_octets('urn:lti:role:ims/lis/Mentor/'
                        'ExternalLearningFacilitator'),
    'Administrator': URI.from_octets('urn:lti:role:ims/lis/Administrator'),
    'Administrator/Administrator':
        URI.from_octets('urn:lti:role:ims/lis/Administrator/Administrator'),
    'Administrator/Support':
        URI.from_octets('urn:lti:role:ims/lis/Administrator/Support'),
    'Administrator/Developer':
        URI.from_octets('urn:lti:role:ims/lis/Administrator/'
                        'ExternalDeveloper'),
    'Administrator/SystemAdministrator':
        URI.from_octets('urn:lti:role:ims/lis/Administrator/'
                        'SystemAdministrator'),
    'Administrator/ExternalSystemAdministrator':
        URI.from_octets('urn:lti:role:ims/lis/Administrator/'
                        'ExternalSystemAdministrator'),
    'Administrator/ExternalDeveloper':
        URI.from_octets('urn:lti:role:ims/lis/Administrator/'
                        'ExternalDeveloper'),
    'Administrator/ExternalSupport':
        URI.from_octets('urn:lti:role:ims/lis/Administrator/ExternalSupport'),
    'TeachingAssistant':
        URI.from_octets('urn:lti:role:ims/lis/''TeachingAssistant'),
    'TeachingAssistant/TeachingAssistant':
        URI.from_octets('urn:lti:role:ims/lis/TeachingAssistant/'
                        'TeachingAssistant'),
    'TeachingAssistant/TeachingAssistantSection':
        URI.from_octets('urn:lti:role:ims/lis/TeachingAssistant/'
                        'TeachingAssistantSection'),
    'TeachingAssistant/TeachingAssistantSectionAssociation':
        URI.from_octets('urn:lti:role:ims/lis/TeachingAssistant/'
                        'TeachingAssistantSectionAssociation'),
    'TeachingAssistant/TeachingAssistantOffering':
        URI.from_octets('urn:lti:role:ims/lis/TeachingAssistant/'
                        'TeachingAssistantOffering'),
    'TeachingAssistant/TeachingAssistantTemplate':
        URI.from_octets('urn:lti:role:ims/lis/TeachingAssistant/'
                        'TeachingAssistantTemplate'),
    'TeachingAssistant/TeachingAssistantGroup':
        URI.from_octets('urn:lti:role:ims/lis/TeachingAssistant/'
                        'TeachingAssistantGroup'),
    'TeachingAssistant/Grader':
        URI.from_octets('urn:lti:role:ims/lis/TeachingAssistant/Grader')
}


def split_role(role):
    """Splits an LTI role into vocab, type and sub-type

    role
        A :class:`~pyslet.urn.URN` instance containing the
        full definition of the role.

    Returns a triple of:

    vocab
        One of 'role', 'sysrole', 'instrole' or some future vocab
        extension.

    rtype
        The role type, e.g., 'Learner', 'Instructor'

    rsubtype
        The role sub-type , e.g., 'NonCreditLearner', 'Lecturer'. Will
        be None if there is no sub-type.

    If this is not an LTI defined role, or the role descriptor does not
    start with the path ims/lis then ValueError is raised."""
    if not isinstance(role, URN) or role.nid != 'lti':
        raise ValueError("Expected lti role: %s" % str(role))
    rvocab = ims = lis = rtype = rsubtype = None
    srole = role.nss.split(":")
    if len(srole) == 2:
        rvocab = srole[0]
        srole = srole[1].split('/')
        if len(srole) == 3:
            ims = srole[0]
            lis = srole[1]
            rtype = srole[2]
        elif len(srole) == 4:
            ims = srole[0]
            lis = srole[1]
            rtype = srole[2]
            rsubtype = srole[3]
    if rtype and ims == 'ims' and lis == 'lis':
        return rvocab, rtype, rsubtype
    else:
        raise ValueError("Badly formed lti role: %s" % str(role))


def is_subrole(role, parent_role):
    """True if role is a sub-role of parent_role

    role
        A :class:`~pyslet.urn.URN` instance containing the
        full definition of the role to be tested.

    parent_role
        A :class:`~pyslet.urn.URN` instance containing the full
        definition of the parent role.  It must *not* define a subrole
        of ValueError is raised.

    In the special case that role does not have subrole then it is
    simply matched against parent_role.  This ensures that::

        is_subrole(role, ROLE_HANDLES['Learner'])

    will return True in all cases where role is a Learner role."""
    rvocab, rtype, rsubtype = split_role(role)
    pvocab, ptype, psubtype = split_role(parent_role)
    if rvocab == pvocab and rtype == ptype and psubtype is None:
        return True
    return False


CONTEXT_TYPE_HANDLES = {
    'CourseTemplate':
        URI.from_octets('urn:lti:context-type:ims/lis/CourseTemplate'),
    'CourseOffering':
        URI.from_octets('urn:lti:context-type:ims/lis/CourseOffering'),
    'CourseSection':
        URI.from_octets('urn:lti:context-type:ims/lis/CourseSection'),
    'Group': URI.from_octets('urn:lti:context-type:ims/lis/Group')
}


def load_metadata():
    """Loads the default metadata document

    Returns a :class:`pyslet.odata2.metadata.Document` instance. The
    schema is loaded from a bundled metadata document which contains the
    minimum schema required for an LTI tool provider."""
    mdir = os.path.split(os.path.abspath(__file__))[0]
    metadata = edmx.Document()
    with open(os.path.join(mdir, 'imsbltiv1p0_metadata.xml'), 'rb') as f:
        metadata.Read(f)
    return metadata


class ToolConsumer(object):

    """An LTI consumer object

    entity
        An :class:`~pyslet.odata2.csdl.Entity` instance.

    cipher
        An :class:`~pyslet.wsgi.AppCipher` instance.

    This class is a light wrapper for the entity object that is used to
    persist information on the server about the consumer.  The consumer
    is persisted in a data store using a single entity passed on
    construction which must have the following required properties:

    ID: Int64
        A database key for the consumer.

    Handle: String
        A convenient handle for referring to this consumer in the user
        interface of the silo's owner.  This handle is never exposed to
        users launching the tool through the LTI protocol.  For example,
        you might use handles like "LMS Prod" and "LMS Staging" as handles
        to help distinguish different consumers.

    Key: String
        The consumer key

    Secret: String
        The consumer secret (encrypted using *cipher*).

    Silo: Entity
        Required navigation property to the Silo this consumer is
        associated with.

    Contexts: Entity Collection
        Navigation property to the associated contexts from which this
        tool has been launched.

    Resources: Entity Collection
        Navigation property to the associated resources from which this
        tool has been launched.

    Users: Entity Collection
        Navigation property to the associated users that have launched
        the tool."""

    def __init__(self, entity, cipher):
        #: the entity that persists this consumer
        self.entity = entity
        #: the cipher used to
        self.cipher = cipher
        #: the consumer key
        self.key = entity['Key'].value
        self.secret = self.cipher.decrypt(
            self.entity['Secret'].value).decode('utf-8')

    @classmethod
    def new_from_values(cls, entity, cipher, handle, key=None, secret=None):
        """Create an instance from an new entity

        entity
            An :class:`~pyslet.odata2.csdl.Entity` instance from a
            suitable entity set.

        cipher
            An :class:`~pyslet.wsgi.AppCipher` instance, used to encrypt
            the secret before storing it.

        handle
            A string

        key (optional)
            A string, defaults to a string generated with
            :func:`~pyslet.wsgi.generate_key`

        secret (optional)
            A string, defaults to a string generated with
            :func:`~pyslet.wsgi.generate_key`

        The fields of the entity are set from the passed in parameters
        (or the defaults) and then a new instance of *cls* is
        constructed from the entity and cipher and returned as a the
        result."""
        if secret is None:
            secret = wsgi.generate_key()
        if key is None:
            key = wsgi.generate_key()
        entity['ID'].set_from_value(wsgi.key60(key))
        entity['Handle'].set_from_value(handle)
        entity['Key'].set_from_value(key)
        entity['Secret'].set_from_value(cipher.encrypt(secret))
        return cls(entity, cipher)

    def update_from_values(self, handle, secret):
        """Updates an instance from new values

        handle
            A string used to update the consumer's handle

        secret
            A string used to update the consumer's secret

        It is not possible to update the consumer key as this is used to
        set the ID of the consumer itself."""
        self.entity['Handle'].set_from_value(handle)
        self.entity['Secret'].set_from_value(
            self.cipher.encrypt(secret.encode('utf-8')))
        self.entity.commit()
        # the base class only defines a constructor, so we have to hope
        # that it doesn't cache information about consumer secrets and
        # just update the value directly.
        self.secret = secret

    def nonce_key(self, nonce):
        """Returns a key into the nonce table

        nonce
            A string received as a nonce during an LTI launch.

        This method hashes the nonce, along with the consumer entity's
        *ID*, to return a hex digest string that can be used as a key
        for comparing against the nonces used in previous launches.

        Mixing the consumer entity's *ID* into the hash reduces the
        chance of a collision between two nonces from separate
        consumers."""
        return sha256(str(self.entity['ID'].value) + nonce).hexdigest()

    def get_context(self, context_id, title=None, label=None, ctypes=None):
        """Returns a context entity

        context_id
            The context_id string passed on launch

        title (optional)
            The title string passed on launch

        label (optional)
            The label string passed on launch

        ctypes (optional)
            An array of :class:`~pyslet.rfc2396.URI` instances
            representing the context types of this context.  See
            :data:`CONTEXT_TYPE_HANDLES` for more information.

        Returns the context entity.

        If this context has never been seen before then a new entity is
        created and bound to the consumer.  Otherwise, the additional
        information (if supplied) is compared and updated as
        necessary."""
        with self.entity['Contexts'].OpenCollection() as collection:
            key = wsgi.key60(self.entity['Key'].value + context_id)
            try:
                context = collection[key]
                update = False
                if title and context['Title'].value != title:
                    context['Title'].set_from_value(title)
                    update = True
                if label and context['Label'].value != label:
                    context['Label'].set_from_value(label)
                    update = True
                if ctypes:
                    ctypes.sort()
                    ctypes = string.join(map(str, ctypes), ' ')
                    if context['Types'].value != ctypes:
                        context['Types'].set_from_value(ctypes)
                        update = True
                if update:
                    collection.update_entity(context)
            except KeyError:
                # first time we ever saw this context, create an entity
                context = collection.new_entity()
                context['ID'].set_from_value(key)
                context['ContextID'].set_from_value(context_id)
                context['Title'].set_from_value(title)
                context['Label'].set_from_value(label)
                if ctypes:
                    ctypes.sort()
                    ctypes = string.join(map(str, ctypes), ' ')
                    context['Types'].set_from_value(
                        string.join(map(str, ctypes), ' '))
                collection.insert_entity(context)
        return context

    def get_resource(self, resource_link_id, title=None, description=None,
                     context=None):
        """Returns a resource entity

        resource_link_id
            The resource_link_id string passed on launch (required).

        title (optional)
            The title string passed on launch, or None.

        description (optional)
            The description string passed on launch, or None.

        context (optional)
            The context entity referred to in the launch, or None.

        If this resource has never been seen before then a new entity is
        created and bound to the consumer and (if specified) the
        context.  Otherwise, the additional information (if supplied) is
        compared and updated as necessary, with the proviso that a
        resource can never change context, as per the following quote
        from the specification:

            [resource_link_id] will also change if the item is exported
            from one system or context and imported into another system
            or context. """
        with self.entity['Resources'].OpenCollection() as collection:
            link = edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
            link.set_from_value(resource_link_id)
            filter = odata.CommonExpression.from_str("LinkID eq :link",
                                                     {'link': link})
            collection.set_filter(filter)
            resources = collection.values()
            if len(resources) == 0:
                # first time we ever saw this resource, create an entry
                resource = collection.new_entity()
                resource['LinkID'].set_from_value(resource_link_id)
                resource['Title'].set_from_value(title)
                resource['Description'].set_from_value(description)
                if context is not None:
                    # link this resource to this context
                    resource['Context'].BindEntity(context)
                collection.insert_entity(resource)
            elif len(resources) == 1:
                resource = resources[0]
                update = False
                if title and resource['Title'].value != title:
                    resource['Title'].set_from_value(title)
                    update = True
                if (description and resource['Description'].value !=
                        description):
                    resource['Description'].set_from_value(description)
                    update = True
                if update:
                    collection.update_entity(resource)
            else:
                logging.warn("Duplicate resource: %s:%s",
                             self.entity['Key'].value, resource_link_id)
                resource = resource[0]
        return resource

    def get_user(self, user_id, name_given=None, name_family=None,
                 name_full=None, email=None):
        """Returns a user entity

        user_id
            The user_id string passed on launch

        name_given
            The user's given name (or None)

        name_family
            The user's family name (or None)

        name_full
            The user's full name (or None)

        email
            The user's email (or None)

        If this user has never been seen before then a new entity is
        created and bound to the consumer, otherwise the """
        with self.entity['Users'].OpenCollection() as collection:
            id = edm.EDMValue.NewSimpleValue(edm.SimpleType.String)
            id.set_from_value(user_id)
            filter = odata.CommonExpression.from_str("UserID eq :id",
                                                     {'id': id})
            collection.set_filter(filter)
            users = collection.values()
            if len(users) == 0:
                # first time we ever saw this user, create an entry
                user = collection.new_entity()
                user['UserID'].set_from_value(user_id)
                user['GivenName'].set_from_value(name_given)
                user['FamilyName'].set_from_value(name_family)
                user['FullName'].set_from_value(name_full)
                user['Email'].set_from_value(email)
                collection.insert_entity(user)
            elif len(users) == 1:
                user = users[0]
                update = False
                if name_given and name_given != user['GivenName'].value:
                    user['GivenName'].set_from_value(name_given)
                    update = True
                if name_family and name_family != user['FamilyName'].value:
                    user['FamilyName'].set_from_value(name_family)
                    update = True
                if name_full and name_full != user['FullName'].value:
                    user['FullName'].set_from_value(name_full)
                    update = True
                if email and email != user['Email'].value:
                    user['Email'].set_from_value(email)
                    update = True
                if update:
                    collection.update_entity(user)
            else:
                logging.warn("Duplicate user: %s:%s",
                             self.entity['Key'].value, user_id)
                user = users[0]
        return user


class ToolProvider(oauth.RequestValidator):

    """An LTI tool provider object

    consumers
        The :class:`~pyslet.odata2.csdl.EntitySet` containing the
        tool *Consumers*.

    nonces
        The :class:`~pyslet.odata2.csdl.EntitySet` containing the
        used *Nonces*.

    cipher
        An :class:`~pyslet.wsgi.AppCipher` instance.  Used to decrypt
        the consumer secret from the database.

    Implements the RequestValidator object required by the oauthlib
    package. Internally creates an instance of SignatureOnlyEndpoint"""

    def __init__(self, consumers, nonces, cipher):
        #: The entity set containing Silos
        self.consumers = consumers
        #: The entity set containing Nonces
        self.nonces = nonces
        #: The cipher object used for encrypting consumer secrets
        self.cipher = cipher
        self.endpoint = oauth.SignatureOnlyEndpoint(self)

    enforce_ssl = False

    def check_client_key(self, key):
        # any non-empty string is OK as a client key
        return len(key) > 0

    def check_nonce(self, nonce):
        # any non-empty string is OK as a nonce
        return len(nonce) > 0

    def validate_client_key(self, client_key, request):
        try:
            self.lookup_consumer(client_key)
            return True
        except KeyError:
            return False

    def validate_timestamp_and_nonce(self, client_key, timestamp, nonce,
                                     request, request_token=None,
                                     access_token=None):
        key = sha256(str(wsgi.key60(client_key)) + nonce).hexdigest()
        with self.nonces.OpenCollection() as collection:
            now = time.time()
            try:
                e = collection[key]
                last_seen = e['LastSeen'].value.WithZone(0).get_unixtime()
                if last_seen + 5400.0 < now:
                    # last seen more than 90 mins ago, update last_seen
                    e['LastSeen'].set_from_value(now)
                    collection.update_entity(e)
                    return True
                else:
                    # this is an error
                    return False
            except KeyError:
                e = collection.new_entity()
                e.set_key(key)
                e['LastSeen'].set_from_value(now)
                collection.insert_entity(e)
                return True

    def get_client_secret(self, client_key, request):
        return self.lookup_consumer(client_key).secret

    def lookup_consumer(self, key):
        """Implements the required method for consumer lookup

        Returns a :class:`ToolConsumer` instance or raises a KeyError if
        key is not the key of any known consumer."""
        with self.consumers.OpenCollection() as collection:
            return ToolConsumer(collection[wsgi.key60(key)], self.cipher)

    def launch(self, command, url, headers, body_string):
        """Checks a launch request for authorization

        command
            The HTTP method, as an upper-case string.  Should be POST
            for LTI.

        url
            The full URL of the page requested as part of the launch.
            This will be the launch URL specified in the LTI protocol
            and configured in the consumer.

        headers
            A dictionary of headers, must include the Authorization
            header but other values are ignored.

        body_string
            The query string (in the LTI case, this is the content of
            the POST request).

        Returns a :class:`ToolConsumer` instance and a dictionary of
        parameters on success. If the incoming request is not authorized
        then :class:`LTIAuthenticationError` is raised.

        This method also checks the LTI message type and protocol
        version and will raise :class:`LTIProtcolError` if this is not a
        recognized launch request."""
        try:
            result, request = self.endpoint.validate_request(
                url, command, body_string, headers)
            if not result:
                raise LTIAuthenticationError
            # grab the parameters as a dictionary from body_string
            parameters = urlparse.parse_qs(body_string)
            for n, v in parameters.items():
                parameters[n] = string.join(v, ',')
            # the consumer key is in the oauth_consumer_key param
            consumer = self.lookup_consumer(parameters['oauth_consumer_key'])
            message_type = parameters.get('lti_message_type', '')
            if (message_type.lower() != LTI_MESSAGE_TYPE):
                logging.warn("Unknown lti_message_type: %s", message_type)
                raise LTIProtocolError
            message_version = parameters.get('lti_version', '')
            if (message_version != LTI_VERSION):
                logging.warn("Unknown lti_version: %s", message_version)
                raise LTIProtocolError
            return consumer, parameters
        finally:
            pass


# legacy definitions
BLTI_VERSION = LTI_VERSION
BLTI_LAUNCH_REQUEST = LTI_MESSAGE_TYPE

BLTIError = LTIError
BLTIOAuthParameterError = LTIAuthenticationError
BLTIAuthenticationError = LTIAuthenticationError


class BLTIDuplicateKeyError(BLTIError):
    pass


class BLTIConsumer(ToolConsumer):
    pass


class BLTIToolProvider(ToolProvider):

    """Legacy class for tool provider."""

    def __init__(self):
        # initialise a very simple in-memory databse
        metadata = load_metadata()
        self.container = metadata.root.DataServices.defaultContainer
        self.data_source = sql.SQLiteEntityContainer(
            file_path=':memory:', container=self.container)
        self.data_source.create_all_tables()
        cipher = wsgi.AppCipher(0, 'secret', self.container['AppKeys'])
        with self.container['Silos'].OpenCollection() as collection:
            self.silo = collection.new_entity()
            self.silo['ID'].set_from_value(wsgi.key60('BLTIToolProvider'))
            self.silo['Slug'].set_from_value('BLTIToolProvider')
            collection.insert_entity(self.silo)
        ToolProvider.__init__(self, self.container['Consumers'],
                              self.container['Nonces'], cipher)

    @renamed_method
    def GenerateKey(self, key_length=128):   # noqa
        pass

    def generate_key(self, key_length=128):
        """Generates a new key

        key_length
            The minimum key length in bits.  Defaults to 128.

        The key is returned as a sequence of 16 bit hexadecimal
        strings separated by '.' to make them easier to read and
        transcribe into other systems."""
        key = []
        nfours = (key_length + 1) // 16
        try:
            rbytes = os.urandom(nfours * 2)
            for i in xrange(nfours):
                four = "%02X%02X" % (
                    ord(rbytes[2 * i]), ord(rbytes[2 * i + 1]))
                key.append(four)
        except NotImplementedError:
            for i in xrange(nfours):
                four = []
                for j in xrange(4):
                    four.append(random.choice('0123456789ABCDEFG'))
                key.append(string.join(four, ''))
        return string.join(key, '.')

    @renamed_method
    def NewConsumer(self, key=None):    # noqa
        pass

    def new_consumer(self, key=None, secret=None):
        """Creates a new BLTIConsumer instance

        The new instance is added to the database of consumers
        authorized to use this tool.  The consumer key and secret
        are automatically generated using :meth:`generate_key` but
        key and secret can be passed as an argument instead."""
        if key is None:
            key = self.generate_key()
        if secret is None:
            secret = self.generate_key()
        try:
            with self.silo['Consumers'].OpenCollection() as collection:
                consumer = ToolConsumer.new_from_values(
                    collection.new_entity(), self.cipher, key, key=key,
                    secret=secret)
                collection.insert_entity(consumer.entity)
        except edm.ConstraintError:
            raise BLTIDuplicateKeyError(key)
        return key, secret

    @renamed_method
    def LoadFromFile(self, f):  # noqa
        pass

    def load_from_file(self, f):
        """Loads the list of trusted consumers

        The consumers are loaded from a simple file of key, secret
        pairs formatted as::

            <consumer key> [SPACE]+ <consumer secret>

        Lines starting with a '#' are ignored as comments."""
        lines = f.readlines()
        for line in lines:
            if line and line[0] == '#':
                continue
            fields = line.split()
            if len(fields) >= 2:
                try:
                    self.lookup_consumer(fields[0])
                    raise BLTIDuplicateKeyError(fields[0])
                except KeyError:
                    self.new_consumer(fields[0], fields[1])

    @renamed_method
    def SaveToFile(self, f):    # noqa
        pass

    def save_to_file(self, f):
        """Saves the list of trusted consumers

        The consumers are saved in a simple file suitable for
        reading with :meth:`load_from_file`."""
        with self.silo['Consumers'].OpenCollection() as collection:
            consumers = {}
            for c in collection.itervalues():
                consumer = ToolConsumer(c, self.cipher)
                consumers[consumer.key] = consumer.secret
            keys = consumers.keys()
            keys.sort()
            for key in keys:
                f.write("%s %s\n" % (key, consumers[key]))

    @renamed_method
    def Launch(self, command, url, headers, query_string):  # noqa
        pass
