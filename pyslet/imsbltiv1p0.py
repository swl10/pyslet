#! /usr/bin/env python
"""This module implements the Basic LTI 1.0 specification defined by IMS GLC

This is an experimental module and subject to significant change in future
releases.  Use with caution.
"""

import logging
import os
import random
import time

from hashlib import sha256

from pyslet import iso8601 as iso
from pyslet import wsgi
from pyslet.odata2 import csdl as edm
from pyslet.odata2 import core as odata
from pyslet.odata2 import metadata as edmx
from pyslet.odata2 import sqlds as sql
from pyslet.py2 import (
    byte_value,
    dict_items,
    dict_keys,
    force_bytes,
    long2,
    parse_qs,
    range3,
    ul
    )
from pyslet.pep8 import MigratedClass, old_method
from pyslet.rfc2396 import URI
from pyslet.urn import URN
from pyslet.xml import structures as xml


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


#: A mapping from LTI context type handles to the full URN for the
#: context type as a :class:`~pyslet.rfc2396.URI` instance.
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
        metadata.read(f)
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
        #: the consumer secret
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
            A text string, defaults to a string generated with
            :func:`~pyslet.wsgi.generate_key`

        secret (optional)
            A text string, defaults to a string generated with
            :func:`~pyslet.wsgi.generate_key`

        The fields of the entity are set from the passed in parameters
        (or the defaults) and then a new instance of *cls* is
        constructed from the entity and cipher and returned as a the
        result."""
        if secret is None:
            secret = wsgi.generate_key()
        if key is None:
            key = wsgi.generate_key()
        entity['ID'].set_from_value(wsgi.key60(key.encode('utf-8')))
        entity['Handle'].set_from_value(handle)
        entity['Key'].set_from_value(key)
        entity['Secret'].set_from_value(cipher.encrypt(secret.encode('utf-8')))
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
        *Key*, to return a hex digest string that can be used as a key
        for comparing against the nonces used in previous launches.

        Mixing the consumer entity's *Key* into the hash reduces the
        chance of a collision between two nonces from separate
        consumers."""
        return sha256(
            (self.entity['Key'].value + nonce).encode('utf-8')).hexdigest()

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
        with self.entity['Contexts'].open() as collection:
            key = wsgi.key60(
                (self.entity['Key'].value + context_id).encode('utf-8'))
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
                    ctypes = ' '.join([str(x) for x in ctypes])
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
                    ctypes = ' '.join([str(x) for x in ctypes])
                    context['Types'].set_from_value(ctypes)
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
        with self.entity['Resources'].open() as collection:
            link = edm.EDMValue.from_type(edm.SimpleType.String)
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
                    resource['Context'].bind_entity(context)
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
        with self.entity['Users'].open() as collection:
            id = edm.EDMValue.from_type(edm.SimpleType.String)
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


class ToolProvider(oauth.RequestValidator, MigratedClass):

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
        key = sha256((client_key + nonce).encode('utf-8')).hexdigest()
        with self.nonces.open() as collection:
            now = time.time()
            try:
                e = collection[key]
                last_seen = e['LastSeen'].value.with_zone(0).get_unixtime()
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

    dummy_client = ul(
        'dummy_'
        '6c877d7e0a8d52d3ea51155c0ce5bd75ceaf7bdd1d2041f9fb3703a207278ab9')

    dummy_secret = ul('secret')

    def get_client_secret(self, client_key, request):
        try:
            return self.lookup_consumer(client_key).secret
        except KeyError:
            # return the same value as the secret
            return self.dummy_secret

    def lookup_consumer(self, key):
        """Implements the required method for consumer lookup

        Returns a :class:`ToolConsumer` instance or raises a KeyError if
        key is not the key of any known consumer."""
        with self.consumers.open() as collection:
            return ToolConsumer(collection[wsgi.key60(force_bytes(key))],
                                self.cipher)

    @old_method('Launch')
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
            parameters = parse_qs(body_string)
            for n, v in dict_items(parameters):
                parameters[n] = ','.join(v)
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


class ToolProviderContext(wsgi.SessionContext):

    def __init__(self, environ, start_response, canonical_root=None):
        wsgi.SessionContext.__init__(self, environ, start_response,
                                     canonical_root)
        #: a :class:`~pyslet.imsbltiv1p0.ToolConsumer` instance
        #: identified from the launch
        self.consumer = None
        #: a dictionary of non-oauth parameters from the launch
        self.parameters = {}
        #: the effective visit entity
        self.visit = None
        #: the effective resource entity
        self.resource = None
        #: the effective user entity
        self.user = None
        #: the effective group (context) entity
        self.group = None
        #: the effective permissions (an integer for bitwise testing)
        self.permissions = 0


class ToolProviderApp(wsgi.SessionApp):

    """Represents WSGI applications that provide LTI Tools

    The key 'ToolProviderApp' is reserved for settings defined by this
    class in the settings file. The defined settings are:

    silo ('testing')
        The name of a default silo to create when the --create_silo
        option is used.

    key ('12345')
        The default consumer key created when --create_silo is used.

    secret ('secret')
        The consumer secret of the default consumer created when
        --create_silo is used."""

    #: We have our own context class
    ContextClass = ToolProviderContext

    @classmethod
    def add_options(cls, parser):
        """Adds the following options:

        --create_silo       create default silo and consumer"""
        super(ToolProviderApp, cls).add_options(parser)
        parser.add_option(
            "--create_silo", dest="create_silo", action="store_true",
            default=False, help="Create default silo and consumer")

    @classmethod
    def setup(cls, options=None, args=None, **kwargs):
        super(ToolProviderApp, cls).setup(options, args, **kwargs)
        tp_settings = cls.settings.setdefault('ToolProviderApp', {})
        silo_name = tp_settings.setdefault('silo', 'testing')
        key = tp_settings.setdefault('key', '12345')
        secret = tp_settings.setdefault('secret', 'secret')
        if options and options.create_silo:
            # we need to create the default silo
            with cls.container['Silos'].open() as collection:
                silo = collection.new_entity()
                silo['Slug'].set_from_value(silo_name)
                collection.insert_entity(silo)
            cipher = cls.new_app_cipher()
            with silo['Consumers'].open() as collection:
                consumer = ToolConsumer.new_from_values(
                    collection.new_entity(), cipher, 'default', key=key,
                    secret=secret)
                collection.insert_entity(consumer.entity)

    @classmethod
    def load_default_metadata(cls):
        mdir = os.path.split(os.path.abspath(__file__))[0]
        metadata_file = os.path.abspath(
            os.path.join(mdir, 'imsbltiv1p0_metadata.xml'))
        metadata = edmx.Document()
        with open(metadata_file, 'rb') as f:
            metadata.read(f)
        return metadata

    def __init__(self, **kwargs):
        super(ToolProviderApp, self).__init__()
        self.provider = ToolProvider(
            self.container['Consumers'],
            self.container['Nonces'],
            self.app_cipher)
        self.stop = False

    def init_dispatcher(self):
        """Provides ToolProviderApp specific bindings.

        This method adds bindings for /launch as the launch URL for the
        tool and all paths within /resource as the resource pages
        themselves."""
        wsgi.SessionApp.init_dispatcher(self)
        self.set_method('/launch', self.lti_launch)
        self.set_method('/resource/*', self.resource_page)

    def set_launch_group(self, context):
        """Sets the group in the context from the launch parameters"""
        group_id = context.parameters.get('context_id', '')
        if not group_id:
            # optional parameter, but recommended
            return None
        group_types = context.parameters.get('context_type', '').split(',')
        gtypes = []
        for group_type in group_types:
            stype = group_type.strip()
            gtype_uri = URI.from_octets(stype)
            if not gtype_uri.is_absolute():
                gtype_uri = CONTEXT_TYPE_HANDLES.get(stype, None)
            gtypes.append(gtype_uri)
        group_title = context.parameters.get('context_title', '')
        group_label = context.parameters.get('context_label', '')
        context.group = context.consumer.get_context(
            group_id, group_title, group_label, gtypes)

    def set_launch_resource(self, context):
        """Sets the resource in the context from the launch parameters"""
        resource_id = context.parameters.get('resource_link_id', '')
        if not resource_id:
            # required parameter
            logging.warn("Missing resource_link_id")
            raise LTIProtocolError
        resource_title = context.parameters.get('resource_link_title', '')
        resource_description = context.parameters.get(
            'resource_link_description', '')
        # the unique resource within this consumer
        context.resource = context.consumer.get_resource(
            resource_id, resource_title, resource_description, context.group)

    def set_launch_user(self, context):
        """Sets the user in the context from the launch parameters"""
        user_id = context.parameters.get('user_id', '')
        if user_id:
            # not required
            context.user = context.consumer.get_user(
                user_id,
                name_given=context.parameters.get(
                    'lis_person_name_given', None),
                name_family=context.parameters.get(
                    'lis_person_name_family', None),
                name_full=context.parameters.get(
                    'lis_person_name_full', None),
                email=context.parameters.get(
                    'lis_person_contact_email_primary', None))
        else:
            context.user = None

    def set_launch_permissions(self, context):
        """Sets the permissions in the context from the launch params"""
        permissions = long2(0)
        if 'roles' in context.parameters:
            roles = context.parameters['roles'].split(',')
            for role in roles:
                srole = role.strip()
                role_uri = URI.from_octets(srole)
                if not role_uri.is_absolute():
                    role_uri = ROLE_HANDLES.get(srole, None)
                permissions |= self.get_permissions(role_uri)
        context.permissions = permissions

    #: Permission bit mask representing 'read' permission
    READ_PERMISSION = 0x1

    #: Permission bit mask representing 'write' permission
    WRITE_PERMISSION = 0x2

    #: Permission bit mask representing 'configure' permission
    CONFIGURE_PERMISSION = 0x4

    @classmethod
    def get_permissions(cls, role):
        """Returns the permissions that apply to a single role

        role
            A single :class:`~pyslet.urn.URN` instance

        Specific LTI tools can override this method to provide more
        complex permission models.  Each permission type is represented
        by an integer bit mask, permissions can be combined with binary
        or '|' to make an overal permissions integer.  The default
        implementation uses the :attr:`READ_PERMISSION`,
        :attr:`WRITE_PERMISSION` and :attr:`CONFIGURE_PERMISSION` bit
        masks but you are free to use any values you wish.

        In this implementation, Instructors (and all sub-roles) are
        granted read, write and configure whereas Learners (and all
        subroles) are granted read only.  Any other role returns 0
        (no permissions).

        An LTI consumer can specify multiple roles on launch, this
        method is called for *each* role and the resulting permissions
        integers are combined to provide an overall permissions
        integer."""
        logging.debug("Launch role: %s", str(role))
        if is_subrole(role, ROLE_HANDLES['Instructor']):
            return (cls.READ_PERMISSION | cls.WRITE_PERMISSION |
                    cls.CONFIGURE_PERMISSION)
        elif is_subrole(role, ROLE_HANDLES['Learner']):
            return cls.READ_PERMISSION
        return 0

    def get_user_display_name(self, context, user=None):
        """Given a user entity, returns a display name

        If user is None then the user from the context is used
        instead."""
        if user is None:
            user = context.user
        if user is None:
            return ''
        if user['FullName']:
            return user['FullName'].value
        elif user['GivenName'] and user['FamilyName']:
            return "%s %s" % (user['GivenName'].value,
                              user['FamilyName'].value)
        elif user['GivenName']:
            return user['GivenName'].value
        elif user['Email']:
            return user['Email'].value
        else:
            return ''

    def get_resource_title(self, context):
        """Given a resource entity, returns a display title"""
        resource = context.resource
        if resource is None:
            return ''
        if resource['Title']:
            return resource['Title'].value
        else:
            return 'Resource: %s' % resource['LinkID'].value

    def new_visit(self, context):
        """Called during launch to create a new visit entity

        A new visit entity is created and bound to the resource entity
        referred to in the launch.  The visit entity stores the
        permissions and a link to the (optional) user entity.

        If a visit to the same resource is already associated with the
        session it is replaced.  This ensures that information about the
        resource, the user, roles and permissions always corresponds to
        the most recent launch.

        Any visits from the same consumer but with a different user are
        also removed.  This handles the case where a previous user of
        the browser session needs to be logged out of the tool."""
        with self.container['Visits'].open() as collection:
            collection.set_expand(
                {'Resource': {'Consumer': None}, 'User': None})
            sid = edm.EDMValue.from_type(edm.SimpleType.String)
            sid.set_from_value(context.session.sid)
            filter = odata.CommonExpression.from_str(
                "Session eq :sid", {'sid': sid})
            collection.set_filter(filter)
            visits = collection.values()
            # now compare these visits to the new one
            for old_visit in visits:
                # if the old visit is to the same resource, replace it
                old_resource = old_visit['Resource'].get_entity()
                if old_resource.key() == context.resource.key():
                    # drop this visit
                    old_visit['Session'].set_from_value(None)
                    old_visit.expand(None, {'Session': None})
                    collection.update_entity(old_visit)
                    continue
                # if the old visit is to the same consumer but with a
                # different user, replace it
                old_consumer = old_resource['Consumer'].get_entity()
                if old_consumer.key() == context.consumer.entity.key():
                    old_user = old_visit['User'].get_entity()
                    # one or the other may be None, will compare by key
                    if context.user != old_user:
                        # drop this visit too
                        old_visit['Session'].set_from_value(None)
                        old_visit.expand(None, {'Session': None})
                        collection.update_entity(old_visit)
            collection.set_expand(None)
            collection.set_filter(None)
            visit = collection.new_entity()
            visit['Permissions'].set_from_value(context.permissions)
            visit['Session'].set_from_value(context.session.sid)
            visit['WhenLaunched'].set_from_value(iso.TimePoint.from_now_utc())
            visit['UserAgent'].set_from_value(
                context.environ.get('HTTP_USER_AGENT', ''))
            visit['Resource'].bind_entity(context.resource)
            user_value = []
            if context.user is not None:
                user_value.append(context.user)
                visit['User'].bind_entity(context.user)
            collection.insert_entity(visit)
            visit['Resource'].set_expansion_values([context.resource])
            visit['User'].set_expansion_values(user_value)
        context.visit = visit

    def find_visit(self, context, resource_id):
        """Finds a visit that matches this resource_id"""
        with self.container['Visits'].open() as collection:
            sid = edm.EDMValue.from_type(edm.SimpleType.String)
            sid.set_from_value(context.session.sid)
            filter = odata.CommonExpression.from_str(
                "Session eq :sid", {'sid': sid})
            collection.set_filter(filter)
            # we want to load the Resource, Resource/Consumer and User
            collection.set_expand({'Resource': {'Consumer': None},
                                   'User': None})
            visits = collection.values()
            for visit in visits:
                resource = visit['Resource'].get_entity()
                if resource.key() == resource_id:
                    return visit
        return None

    def establish_session(self, context):
        """Overridden to update the Session ID in the visit"""
        with self.container['Visits'].open() as collection:
            sid = edm.EDMValue.from_type(edm.SimpleType.String)
            sid.set_from_value(context.session.sid)
            filter = odata.CommonExpression.from_str(
                "Session eq :sid", {'sid': sid})
            collection.set_filter(filter)
            visits = collection.values()
            context.session.establish()
            # we don't expect more than one matching visit here
            for visit in visits:
                visit['Session'].set_from_value(context.session.sid)
                # just update the Session field
                visit.expand(None, {'Session': None})
                collection.update_entity(visit)

    def merge_session(self, context, merge_session):
        """Overridden to update the Session ID in any associated visits"""
        with self.container['Visits'].open() as collection:
            sid = edm.EDMValue.from_type(edm.SimpleType.String)
            sid.set_from_value(merge_session.session.sid)
            filter = odata.CommonExpression.from_str(
                "Session eq :sid", {'sid': sid})
            collection.set_filter(filter)
            collection.set_expand(
                {'Resource': {'Consumer': None}, 'User': None})
            merge_visits = collection.values()
            # there should be only one visit in this session if there
            # are more then something strange is going on
            sid.set_from_value(context.session.sid)
            for merge_visit in merge_visits:
                merge_resource = merge_visit['Resource'].get_entity()
                merge_consumer = merge_resource['Consumer'].get_entity()
                merge_user = merge_visit['User'].get_entity()
                old_visits = collection.values()
                for old_visit in old_visits:
                    # if the old visit is to the same resource, replace it
                    old_resource = old_visit['Resource'].get_entity()
                    if old_resource.key() == merge_resource.key():
                        # drop this visit's session
                        old_visit['Session'].set_from_value(None)
                        old_visit.expand(None, {'Session': None})
                        collection.update_entity(old_visit)
                        continue
                    # if the old visit is to the same consumer but with a
                    # different user, replace it
                    old_consumer = old_resource['Consumer'].get_entity()
                    if old_consumer.key() == merge_consumer.key():
                        old_user = old_visit['User'].get_entity()
                        # one or the other may be None, will compare by key
                        if old_user != merge_user:
                            # drop this visit too
                            old_visit['Session'].set_from_value(None)
                            old_visit.expand(None, {'Session': None})
                            collection.update_entity(old_visit)
                merge_visit['Session'].set_from_value(context.session.sid)
                # just update the Session field
                merge_visit.set_expand(None, {'Session': None})
                collection.update_entity(merge_visit)

    def load_visit(self, context):
        """Loads an existing LTI visit into the context

        You'll normally call this method from each session decorated
        method of your tool provider that applies to a protected
        resource.

        This method sets the following attributes of the context...

        :attr:`ToolProviderContext.resource`
            The resource record is identified from the resource
            id given in the URL path.

        :attr:`ToolProviderContext.visit`
            The session is searched for a visit record matching the
            resource.

        :attr:`ToolProviderContext.permissions`
            Set from the visit record

        :attr:`ToolProviderContext.user`
            The optional user is loaded from the visit.

        :attr:`ToolProviderContext.group`
            The context record identified from the resource id given in
            the URL path.  This may be None if the resource link was not
            created in any context.

        :attr:`ToolProviderContext.consumer`
            The consumer object is looked up from the visit entity.

        If the visit can't be set then an exception is raised, an
        unknown resource raises :class:`pyslet.wsgi.PageNotFound`
        whereas the absence of a valid visit for a known resource raises
        :class:`pyslet.wsgi.PageNotAuthorized`.  These are caught
        automatically by the WSGI handlers and return 404 and 403 errors
        respectively."""
        if context.visit is None:
            path = context.environ['PATH_INFO'].split('/')
            if len(path) < 4:
                raise wsgi.PageNotFound
            resource_id = path[2]
            try:
                resource_id = int(resource_id, 16)
            except ValueError:
                raise wsgi.PageNotFound
            context.visit = self.find_visit(context, resource_id)
            if context.visit is None:
                raise wsgi.PageNotAuthorized
            context.permissions = context.visit['Permissions'].value
            context.resource = context.visit['Resource'].get_entity()
            context.user = context.visit['User'].get_entity()
            context.group = context.resource['Context'].get_entity()
            tc_entity = context.resource['Consumer'].get_entity()
            context.consumer = ToolConsumer(tc_entity, self.app_cipher)

    def lti_launch(self, context):
        # we are only interested in the authorisation header
        h = context.environ.get('CONTENT_TYPE', None)
        if h:
            headers = {'Content-Type': h}
        else:
            headers = None
        try:
            context.consumer, context.parameters = self.provider.launch(
                context.environ['REQUEST_METHOD'].upper(),
                str(context.get_url()), headers, context.get_content())
            self.set_launch_group(context)
            self.set_launch_resource(context)
            self.set_launch_user(context)
            self.set_launch_permissions(context)
            # load the session information into the context and add a
            # new visit to it.
            self.set_session(context)
            self.new_visit(context)
        except LTIProtocolError:
            logging.exception("LTI Protocol Error")
            return self.error_page(context, 400)
        except LTIAuthenticationError:
            logging.exception("LTI Authentication Failure")
            return self.error_page(context, 403)
        launch_target = URI.from_octets(
            "resource/%08X/" %
            context.resource.key()).resolve(context.get_app_root())
        return self.session_page(context, self.launch_redirect, launch_target)

    def launch_redirect(self, context):
        """Redirects to the resource identified on launch

        A POST request should pretty much always redirect to a GET page
        and our tool launches are no different.  This allows you to
        reload a tool page straight away if desired without the risk of
        double-POST issues."""
        resource_link = URI.from_octets(
            "resource/%08X/" %
            context.resource.key()).resolve(context.get_app_root())
        return self.redirect_page(context, resource_link, 303)

    @wsgi.session_decorator
    def resource_page(self, context):
        """Returns a resource page

        This method is the heart of your tool and will be called for all
        URLs that start with a resource path.  You can override the
        behaviour for specific paths by adding new methods to the
        dispatcher with more specific URLs, such as
        /resource/*/view.html, but anything in /resource/*/* that is
        not matched by a more specific method will end up here.

        You'll typically call :meth:`load_visit` to load information
        about the associated LTI visit into the context before proceeding,
        it checks authorisation to view the resource for you.

        The default implementation returns a simple page with the
        resource's title and a simple message reflecting the user name
        of the authorised user."""
        page = """<!DOCTYPE html PUBLIC
    "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
  <head>
   <title>%(title)s</title>
  </head>
<body>
<h4>%(title)s</h4>
<p>Congratulations %(user)s, you've launched an LTI tool created with <a
    href="http://www.pyslet.org/" target="_blank">Pyslet</a>.</p>
</body>
</html>"""
        self.load_visit(context)
        params = {'user':
                  xml.escape_char_data7(self.get_user_display_name(context)),
                  'title':
                  xml.escape_char_data7(self.get_resource_title(context))
                  }
        data = page % params
        context.set_status(200)
        return self.html_response(context, data)


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

    """Legacy class for tool provider.

    Refactored to build directly on the newer :class:`ToolProvider`. A
    single Silo entity is created containing all defined consumers. An
    in-memory SQLite database is used as the data store.  Consumer keys
    are not encrypted (a plaintext cipher is used) as they will not be
    persisted."""

    def __init__(self):
        # initialise a very simple in-memory databse
        metadata = load_metadata()
        self.container = metadata.root.DataServices.defaultContainer
        self.data_source = sql.SQLiteEntityContainer(
            file_path=':memory:', container=self.container)
        self.data_source.create_all_tables()
        cipher = wsgi.AppCipher(0, 'secret', self.container['AppKeys'])
        with self.container['Silos'].open() as collection:
            self.silo = collection.new_entity()
            self.silo['ID'].set_from_value(wsgi.key60(b'BLTIToolProvider'))
            self.silo['Slug'].set_from_value('BLTIToolProvider')
            collection.insert_entity(self.silo)
        ToolProvider.__init__(self, self.container['Consumers'],
                              self.container['Nonces'], cipher)

    @old_method('GenerateKey')
    def generate_key(self, key_length=128):
        """Generates a new key

        Also available as GenerateKey.  This method is deprecated, it
        has been replaced by the similarly named function
        :func:`pyslet.wsgi.generate_key`.

        key_length
            The minimum key length in bits.  Defaults to 128.

        The key is returned as a sequence of 16 bit hexadecimal
        strings separated by '.' to make them easier to read and
        transcribe into other systems."""
        key = []
        nfours = (key_length + 1) // 16
        try:
            rbytes = os.urandom(nfours * 2)
            for i in range3(nfours):
                four = "%02X%02X" % (
                    byte_value(rbytes[2 * i]), byte_value(rbytes[2 * i + 1]))
                key.append(four)
        except NotImplementedError:
            for i in range3(nfours):
                four = []
                for j in range3(4):
                    four.append(random.choice('0123456789ABCDEFG'))
                key.append(''.join(four))
        return '.'.join(key)

    @old_method('NewConsumer')
    def new_consumer(self, key=None, secret=None):
        """Creates a new BLTIConsumer instance

        Also available as NewConsumer

        The new instance is added to the database of consumers
        authorized to use this tool.  The consumer key and secret
        are automatically generated using :meth:`generate_key` but
        key and secret can be passed as optional arguments instead."""
        if key is None:
            key = self.generate_key()
        if secret is None:
            secret = self.generate_key()
        try:
            with self.silo['Consumers'].open() as collection:
                consumer = ToolConsumer.new_from_values(
                    collection.new_entity(), self.cipher, key, key=key,
                    secret=secret)
                collection.insert_entity(consumer.entity)
        except edm.ConstraintError:
            raise BLTIDuplicateKeyError(key)
        return key, secret

    @old_method('LoadFromFile')
    def load_from_file(self, f):
        """Loads the list of trusted consumers

        Also available as LoadFromFile

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
                key = fields[0].decode('utf-8')
                secret = fields[1].decode('utf-8')
                try:
                    self.lookup_consumer(key)
                    raise BLTIDuplicateKeyError(key)
                except KeyError:
                    self.new_consumer(key, secret)

    @old_method('SaveToFile')
    def save_to_file(self, f):
        """Saves the list of trusted consumers

        Also available as SaveToFile

        The consumers are saved in a simple file suitable for
        reading with :meth:`load_from_file`."""
        with self.silo['Consumers'].open() as collection:
            consumers = {}
            for c in collection.itervalues():
                consumer = ToolConsumer(c, self.cipher)
                consumers[consumer.key] = consumer.secret
            keys = sorted(dict_keys(consumers))
            for key in keys:
                f.write(("%s %s\n" % (key, consumers[key])).encode('ascii'))
