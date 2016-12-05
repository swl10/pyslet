#! /usr/bin/env python

import io
import logging
import optparse
import time
import shutil
import tempfile
import unittest

try:
    import pkg_resources
except ImportError:
    pkg_resources = None

from pyslet import imsbltiv1p0 as lti
from pyslet import iso8601 as iso
from pyslet import wsgi
from pyslet.odata2 import csdl as edm
from pyslet.odata2 import sqlds as sql
from pyslet.py2 import (
    range3,
    ul
    )
from pyslet.rfc2396 import URI
from pyslet.urn import URN


from test_wsgi import MockRequest


if not lti.got_oauth:
    logging.warning(
        "Basic LTI tests skipped\n"
        "\tTry installing oathlib from https://pypi.python.org/pypi/oauthlib")
else:
    if pkg_resources:
        v = pkg_resources.get_distribution("oauthlib").version
        if v != "0.7.2":
            logging.warning(
                "\tDesigned for oauthlib-0.7.2, testing with version %s", v)
    else:
        logging.warning(
            "\tCannot determine oauthlib installed package version; "
            "install setuptools to remove this message")


def suite():
    suite_tests = [
        unittest.makeSuite(BLTITests, 'test'),
        unittest.makeSuite(LTIConsumerTests, 'test'),
        unittest.makeSuite(ToolProviderContextTests, 'test'),
        unittest.makeSuite(ToolProviderSessionTests, 'test'),
        ]
    if lti.got_oauth:
        suite_tests = suite_tests + [
            unittest.makeSuite(BLTIProviderTests, 'test'),
            unittest.makeSuite(LTIProviderTests, 'test'), ]
    return unittest.TestSuite(tuple(suite_tests))


class BLTITests(unittest.TestCase):

    def test_constants(self):
        self.assertTrue(lti.LTI_VERSION == "LTI-1p0")
        self.assertTrue(lti.LTI_MESSAGE_TYPE == "basic-lti-launch-request")
        # check support for legacy constants
        self.assertTrue(lti.BLTI_VERSION == "LTI-1p0")
        self.assertTrue(lti.BLTI_LAUNCH_REQUEST == "basic-lti-launch-request")

    def test_sysroles(self):
        # pick one example to check the mapping is working
        self.assertTrue('Administrator' in lti.SYSROLE_HANDLES)
        admin = lti.SYSROLE_HANDLES['Administrator']
        self.assertTrue(isinstance(admin, URI))
        self.assertTrue(isinstance(admin, URN))
        self.assertTrue(admin.nid == 'lti')
        self.assertTrue(admin.nss == 'sysrole:ims/lis/Administrator')
        self.assertTrue(str(admin) == 'urn:lti:sysrole:ims/lis/Administrator')

    def test_institution_roles(self):
        # pick one example to check the mapping is working
        self.assertTrue('Guest' in lti.INSTROLE_HANDLES)
        guest = lti.INSTROLE_HANDLES['Guest']
        self.assertTrue(isinstance(guest, URI))
        self.assertTrue(isinstance(guest, URN))
        self.assertTrue(guest.nid == 'lti')
        self.assertTrue(guest.nss == 'instrole:ims/lis/Guest')
        self.assertTrue(str(guest) == 'urn:lti:instrole:ims/lis/Guest')

    def test_roles(self):
        self.assertTrue('Learner' in lti.ROLE_HANDLES)
        self.assertTrue('Instructor' in lti.ROLE_HANDLES)
        # pick one example to check the mapping is working
        learner = lti.ROLE_HANDLES['Learner']
        self.assertTrue(isinstance(learner, URI))
        self.assertTrue(isinstance(learner, URN))
        self.assertTrue(learner.nid == 'lti')
        self.assertTrue(learner.nss == 'role:ims/lis/Learner')
        self.assertTrue(str(learner) == 'urn:lti:role:ims/lis/Learner')

    def test_split_role(self):
        learner = lti.ROLE_HANDLES['Learner']
        vocab, rtype, subtype = lti.split_role(learner)
        self.assertTrue(vocab == 'role')
        self.assertTrue(rtype == 'Learner')
        self.assertTrue(subtype is None)
        instructor = lti.ROLE_HANDLES['Instructor/Lecturer']
        vocab, rtype, subtype = lti.split_role(instructor)
        self.assertTrue(vocab == 'role')
        self.assertTrue(rtype == 'Instructor')
        self.assertTrue(subtype == 'Lecturer')
        guest = lti.INSTROLE_HANDLES['Guest']
        vocab, rtype, subtype = lti.split_role(guest)
        self.assertTrue(vocab == 'instrole')
        self.assertTrue(rtype == 'Guest')
        self.assertTrue(subtype is None)
        # now check for badly formed or unknown paths
        badrole = URI.from_octets('urn:lti:xrole:pyslet/lti/User')
        try:
            vocab, rtype, subtype = lti.split_role(badrole)
            self.fail("bad lis path")
        except ValueError:
            pass
        # and now with something that isn't the right type of URN
        badrole = URI.from_octets('URN:ISBN:9780099512240')
        self.assertTrue(isinstance(badrole, URN))
        try:
            vocab, rtype, subtype = lti.split_role(badrole)
            self.fail("bad URN type")
        except ValueError:
            pass
        # and finally something that isn't even a URN
        badrole = URI.from_octets(
            'http://www.example.com/ims/lis/WebDeveloper')
        try:
            vocab, rtype, subtype = lti.split_role(badrole)
            self.fail("role from http URL")
        except ValueError:
            pass

    def test_contexts(self):
        # pick one example to check the mapping is working
        self.assertTrue('CourseSection' in lti.CONTEXT_TYPE_HANDLES)
        section = lti.CONTEXT_TYPE_HANDLES['CourseSection']
        self.assertTrue(isinstance(section, URI))
        self.assertTrue(isinstance(section, URN))
        self.assertTrue(section.nid == 'lti')
        self.assertTrue(section.nss == 'context-type:ims/lis/CourseSection')
        self.assertTrue(str(section) ==
                        'urn:lti:context-type:ims/lis/CourseSection')


class LTIConsumerTests(unittest.TestCase):

    def setUp(self):        # noqa
        # load a suitable database schema
        metadata = lti.load_metadata()
        self.container = metadata.root.DataServices.defaultContainer
        self.data_source = sql.SQLiteEntityContainer(
            file_path=':memory:', container=self.container)
        self.data_source.create_all_tables()
        self.cipher = wsgi.AppCipher(0, 'secret', self.container['AppKeys'])
        with self.container['Silos'].open() as collection:
            self.silo = collection.new_entity()
            self.silo['ID'].set_from_value(wsgi.key60(b'testing'))
            self.silo['Slug'].set_from_value('testing')
            collection.insert_entity(self.silo)

    def tearDown(self):     # noqa
        pass

    def test_consumer(self):
        with self.silo['Consumers'].open() as collection:
            entity = collection.new_entity()
            consumer = lti.ToolConsumer.new_from_values(
                entity, self.cipher, 'default', key="12345",
                secret=ul("secret"))
            self.assertTrue(consumer.entity is entity)
            self.assertTrue(isinstance(consumer, lti.ToolConsumer))
            self.assertTrue(consumer.entity['Handle'].value == 'default')
            self.assertTrue(consumer.entity['Key'].value == '12345')
            self.assertTrue(consumer.entity['Secret'].value ==
                            self.cipher.encrypt(b'secret'))
            # at this stage the entity has not been persisted but
            # the local attributes should be set...
            self.assertTrue(consumer.key == '12345')
            self.assertTrue(consumer.secret == 'secret')
            # now check persistence
            self.assertTrue(len(collection) == 0)
            collection.insert_entity(consumer.entity)
            self.assertTrue(len(collection) == 1)
            check_entity = collection.values()[0]
            check_consuemr = lti.ToolConsumer(check_entity, self.cipher)
            self.assertTrue(check_consuemr.entity['Handle'].value ==
                            'default')
            self.assertTrue(check_consuemr.entity['Key'].value ==
                            '12345')
            self.assertTrue(check_consuemr.entity['Secret'].value ==
                            self.cipher.encrypt(b'secret'))
            self.assertTrue(check_consuemr.key == '12345')
            self.assertTrue(check_consuemr.secret == 'secret')
            # now check the update process
            consumer.update_from_values('updated', 'password')
            self.assertTrue(consumer.entity['Handle'].value == 'updated')
            self.assertTrue(consumer.entity['Key'].value == '12345')
            self.assertTrue(consumer.entity['Secret'].value ==
                            self.cipher.encrypt(b'password'))
            self.assertTrue(consumer.key == '12345')
            self.assertTrue(consumer.secret == 'password')
            self.assertTrue(len(collection) == 1)
            check_entity = collection.values()[0]
            check_consuemr = lti.ToolConsumer(check_entity, self.cipher)
            self.assertTrue(check_consuemr.entity['Handle'].value ==
                            'updated')
            self.assertTrue(check_consuemr.entity['Key'].value ==
                            '12345')
            self.assertTrue(check_consuemr.entity['Secret'].value ==
                            self.cipher.encrypt(b'password'))
            self.assertTrue(check_consuemr.key == '12345')
            self.assertTrue(check_consuemr.secret == 'password')

    def test_default_secret(self):
        with self.silo['Consumers'].open() as collection:
            entity = collection.new_entity()
            consumer = lti.ToolConsumer.new_from_values(
                entity, self.cipher, 'default', key="12345")
            # we can default the secret
            self.assertTrue(consumer.key == '12345')
            self.assertTrue(consumer.secret)
            collection.insert_entity(entity)
            consumer2 = lti.ToolConsumer.new_from_values(
                collection.new_entity(), self.cipher, 'default', key="12345")
            # key must be unique
            self.assertTrue(consumer2.key == '12345')
            self.assertTrue(consumer2.secret != consumer.secret)
            # however we should not be able to persist consumer2,
            # matching keys!
            try:
                collection.insert_entity(consumer2.entity)
                self.fail("Duplicate consumer keys")
            except edm.ConstraintError:
                pass

    def test_default_key(self):
        with self.silo['Consumers'].open() as collection:
            entity = collection.new_entity()
            consumer = lti.ToolConsumer.new_from_values(
                entity, self.cipher, 'default', secret=ul("secret"))
            # we can default the key
            self.assertTrue(consumer.key)
            self.assertTrue(consumer.secret == 'secret')
            collection.insert_entity(entity)
            consumer2 = lti.ToolConsumer.new_from_values(
                collection.new_entity(), self.cipher, 'default',
                secret=ul("secret"))
            # secret need not be unique
            self.assertTrue(consumer2.key != consumer.key)
            self.assertTrue(consumer2.secret == 'secret')
            # Fine to persist to consumers with different keys, same
            # secret
            collection.insert_entity(consumer2.entity)

    def test_nonces(self):
        with self.silo['Consumers'].open() as collection:
            consumer = lti.ToolConsumer.new_from_values(
                collection.new_entity(), self.cipher, 'default')
            collection.insert_entity(consumer.entity)
            consumer2 = lti.ToolConsumer.new_from_values(
                collection.new_entity(), self.cipher, 'default2')
            collection.insert_entity(consumer2.entity)
            # now the same nonce from different consumers should
            # result in a different nonce key
            n1 = consumer.nonce_key('nonce1')
            # must be a string of at least 64 characters, from an
            # information point of view
            self.assertTrue(len(n1) >= 64)
            n2 = consumer2.nonce_key('nonce1')
            self.assertTrue(len(n2) >= 64)
            self.assertTrue(n1 != n2)
            # check that we get the same nonce when we do it again...
            self.assertTrue(n1 == consumer.nonce_key('nonce1'))
            self.assertTrue(n2 == consumer2.nonce_key('nonce1'))
            # and that get a different nonce next time!
            self.assertFalse(n1 == consumer.nonce_key('nonce2'))
            self.assertFalse(n2 == consumer2.nonce_key('nonce2'))
            # I don't like empty nonces, and they shouldn't happen in
            # normal use but ensure we can still use them just in case.
            nblank = consumer.nonce_key('')
            self.assertFalse(n1 == nblank)
            self.assertTrue(nblank == consumer.nonce_key(''))
            self.assertFalse(consumer.nonce_key('') == consumer2.nonce_key(''))

    def test_context(self):
        with self.silo['Consumers'].open() as collection:
            consumer = lti.ToolConsumer.new_from_values(
                collection.new_entity(), self.cipher, 'default')
            collection.insert_entity(consumer.entity)
            context_id = '456434513'
            context_title = 'Design of Personal Environments'
            context_label = 'SI182'
            context_types = [lti.CONTEXT_TYPE_HANDLES['Group']]
            context = consumer.get_context(
                context_id, context_title, context_label, context_types)
            # should have created a context entity
            self.assertTrue(isinstance(context, edm.Entity))
            self.assertTrue(context['ContextID'].value == context_id)
            self.assertTrue(context['Title'].value == context_title)
            self.assertTrue(context['Label'].value == context_label)
            # now if we use the same ID we should get a matching entity
            check_context = consumer.get_context(context_id)
            # different instance, same values
            self.assertFalse(context is check_context)
            self.assertTrue(check_context['ContextID'].value == context_id)
            self.assertTrue(check_context['Title'].value == context_title)
            self.assertTrue(check_context['Label'].value == context_label)
            # now update the values when the title changes...
            context = consumer.get_context(context_id, 'Design for People')
            self.assertTrue(context['ContextID'].value == context_id)
            self.assertTrue(context['Title'].value == 'Design for People')
            self.assertTrue(context['Label'].value == context_label)
            # check it was persisted
            check_context = consumer.get_context(context_id)
            self.assertTrue(check_context['Title'].value ==
                            'Design for People')

    def test_resource(self):
        with self.silo['Consumers'].open() as collection:
            consumer = lti.ToolConsumer.new_from_values(
                collection.new_entity(), self.cipher, 'default')
            collection.insert_entity(consumer.entity)
            # now we are ready for a resource without a context
            resource_link_id = '120988f929-274612'
            resource_title = 'Weekly Blog'
            resource_description = 'A weekly blog.'
            resource = consumer.get_resource(resource_link_id, resource_title,
                                             resource_description)
            self.assertTrue(isinstance(resource, edm.Entity))
            self.assertTrue(resource['LinkID'].value == resource_link_id)
            self.assertTrue(resource['Title'].value == resource_title)
            self.assertTrue(resource['Description'].value ==
                            resource_description)
            # now if we use the same ID we should get a matching entity
            check_resource = consumer.get_resource(resource_link_id)
            # different instance, same values
            self.assertFalse(resource is check_resource)
            self.assertTrue(check_resource['LinkID'].value == resource_link_id)
            self.assertTrue(check_resource['Title'].value == resource_title)
            self.assertTrue(check_resource['Description'].value ==
                            resource_description)
            # now update the values when the title changes...
            resource = consumer.get_resource(resource_link_id, 'Monthly Blog')
            self.assertTrue(resource['LinkID'].value == resource_link_id)
            self.assertTrue(resource['Title'].value == 'Monthly Blog')
            self.assertTrue(resource['Description'].value ==
                            resource_description)
            # check it was persisted
            check_resource = consumer.get_resource(resource_link_id)
            self.assertTrue(check_resource['Title'].value == 'Monthly Blog')
            # now check that the resource is not attached to a context
            with resource['Context'].open() as contexts:
                self.assertTrue(len(contexts) == 0)
            # Create a context for the next part of the test
            context_id = '456434513'
            context = consumer.get_context(context_id)
            # A resource cannot be assigned to a context once it has
            # been created
            resource = consumer.get_resource(resource_link_id, context=context)
            with resource['Context'].open() as contexts:
                self.assertTrue(len(contexts) == 0)
            # But a new resource can!
            resource_link_id = '120988f929-274613'
            resource = consumer.get_resource(resource_link_id, context=context)
            with resource['Context'].open() as contexts:
                self.assertTrue(len(contexts) == 1)
            check_context = resource['Context'].get_entity()
            self.assertTrue(check_context['ContextID'].value == context_id)

    def test_user(self):
        with self.silo['Consumers'].open() as collection:
            consumer = lti.ToolConsumer.new_from_values(
                collection.new_entity(), self.cipher, 'default')
            collection.insert_entity(consumer.entity)
            user_id = '292832126'
            name_given = 'Given'
            name_family = 'Public'
            name_full = 'Jane Q. Public'
            email = 'user@school.edu'
            user = consumer.get_user(
                user_id, name_given, name_family, name_full, email)
            # should have created a user entity
            self.assertTrue(isinstance(user, edm.Entity))
            self.assertTrue(user['UserID'].value == user_id)
            self.assertTrue(user['GivenName'].value == name_given)
            self.assertTrue(user['FamilyName'].value == name_family)
            self.assertTrue(user['FullName'].value == name_full)
            self.assertTrue(user['Email'].value == email)
            # now if we use the same ID we should get a matching entity
            check_user = consumer.get_user(user_id)
            # different instance, same values
            self.assertFalse(user is check_user)
            self.assertTrue(check_user['UserID'].value == user_id)
            self.assertTrue(check_user['GivenName'].value == name_given)
            self.assertTrue(check_user['FamilyName'].value == name_family)
            self.assertTrue(check_user['FullName'].value == name_full)
            self.assertTrue(check_user['Email'].value == email)
            # now update the values when their name changes...
            user = consumer.get_user(
                user_id, name_family='Private', name_full='Jane Q. Private')
            self.assertTrue(user['UserID'].value == user_id)
            self.assertTrue(user['GivenName'].value == name_given)
            self.assertTrue(user['FamilyName'].value == 'Private')
            self.assertTrue(user['FullName'].value == 'Jane Q. Private')
            self.assertTrue(user['Email'].value == email)
            # check it was persisted
            check_user = consumer.get_user(user_id)
            self.assertTrue(check_user['FamilyName'].value == 'Private')
            self.assertTrue(check_user['FullName'].value == 'Jane Q. Private')


class MockTime(object):

    #: the float time (since the epoch) corresponding to 01 January
    #: 1970 00:00:00 UTC the OAuth time origin.
    oauth_origin = float(
        iso.TimePoint(
            date=iso.Date(century=19, year=70, month=1, day=1),
            time=iso.Time(hour=0, minute=0, second=0, zdirection=0)
        ).get_unixtime())

    def __init__(self, base=None):
        if base is None:
            self.now = time.time()
        else:
            self.now = base

    def time(self):
        return self.now

    def tick(self, delta=1.0):
        self.now += delta


class LTIProviderTests(unittest.TestCase):

    def setUp(self):        # noqa
        # load a suitable database schema
        metadata = lti.load_metadata()
        self.container = metadata.root.DataServices.defaultContainer
        self.data_source = sql.SQLiteEntityContainer(
            file_path=':memory:', container=self.container)
        self.data_source.create_all_tables()
        self.cipher = wsgi.AppCipher(0, 'secret', self.container['AppKeys'])
        with self.container['Silos'].open() as collection:
            self.silo = collection.new_entity()
            self.silo['ID'].set_from_value(wsgi.key60(b'testing'))
            self.silo['Slug'].set_from_value('testing')
            collection.insert_entity(self.silo)
        self.save_time = time.time
        self.mock_time = MockTime(1420370306 + MockTime.oauth_origin)
        # patch the time module to mock it
        time.time = self.mock_time.time

    def tearDown(self):     # noqa
        time.time = self.save_time

    def test_constructor(self):
        provider = lti.ToolProvider(
            self.container['Consumers'], self.container['Nonces'],
            self.cipher)
        # by default, there are no consumers
        try:
            provider.lookup_consumer('12345')
            self.fail("No consumers")
        except KeyError:
            pass
        with self.silo['Consumers'].open() as collection:
            consumer = lti.ToolConsumer.new_from_values(
                collection.new_entity(), self.cipher, 'default', key="12345",
                secret=ul("secret"))
            collection.insert_entity(consumer.entity)
        try:
            consumer = provider.lookup_consumer('12345')
            self.assertTrue(consumer.key == '12345')
            self.assertTrue(consumer.secret == 'secret')
        except KeyError:
            self.fail("Failed to find consumer")

    def test_nonces(self):
        with self.silo['Consumers'].open() as collection:
            consumer = lti.ToolConsumer.new_from_values(
                collection.new_entity(), self.cipher, 'default', key="12345",
                secret=ul("secret"))
            collection.insert_entity(consumer.entity)
        provider = lti.ToolProvider(
            self.container['Consumers'], self.container['Nonces'],
            self.cipher)
        consumer = provider.lookup_consumer('12345')
        self.assertTrue(provider.validate_timestamp_and_nonce(
            consumer.key, 0, '9e4a4b085c8c46d6aae6b5d9c8a15418', None))
        # the same nonce should now evaluate to True
        self.assertFalse(provider.validate_timestamp_and_nonce(
            consumer.key, 0, '9e4a4b085c8c46d6aae6b5d9c8a15418', None))
        # but a different one is False
        self.assertTrue(provider.validate_timestamp_and_nonce(
            consumer.key, 0, '8f274dca508711c2e70a67ab68fcc1f2', None))
        # now at 89:59 we are still not allowed to reuse the nonce
        self.mock_time.tick(89*60+59.0)
        self.assertFalse(provider.validate_timestamp_and_nonce(
            consumer.key, 0, '9e4a4b085c8c46d6aae6b5d9c8a15418', None))
        # but if we tick over 90 mins we're good to go again
        self.mock_time.tick(1.001)
        self.assertTrue(provider.validate_timestamp_and_nonce(
            consumer.key, 0, '9e4a4b085c8c46d6aae6b5d9c8a15418', None))

    def test_launch(self):
        command = "POST"
        url = "http://www.example.com/launch"
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        query_string = "context_id=456434513&context_label=SI182&"\
            "context_title=Design%20of%20Personal%20Environments&"\
            "launch_presentation_css_url=http%3A%2F%2Fwww.imsglobal.org%2F"\
            "developers%2FLTI%2Ftest%2Fv1p1%2Flms.css&"\
            "launch_presentation_document_target=frame&"\
            "launch_presentation_locale=en-US&"\
            "launch_presentation_return_url=http%3A%2F%2Fwww.imsglobal.org%2F"\
            "developers%2FLTI%2Ftest%2Fv1p1%2Flms_return.php&"\
            "lis_outcome_service_url=http%3A%2F%2Fwww.imsglobal.org%2F"\
            "developers%2FLTI%2Ftest%2Fv1p1%2Fcommon%2F"\
            "tool_consumer_outcome.php%3Fb64%3DMTIzNDU6OjpzZWNyZXQ%3D&"\
            "lis_person_contact_email_primary=user%40school.edu&"\
            "lis_person_name_family=Public&"\
            "lis_person_name_full=Jane%20Q.%20Public&"\
            "lis_person_name_given=Given&"\
            "lis_person_sourcedid=school.edu%3Auser&"\
            "lis_result_sourcedid=feb-123-456-2929%3A%3A28883&"\
            "lti_message_type=basic-lti-launch-request&"\
            "lti_version=LTI-1p0&"\
            "oauth_callback=about%3Ablank&oauth_consumer_key=12345&"\
            "oauth_nonce=45f32b44e314244a222d0e070fa55384&"\
            "oauth_signature=SKhxr%2Bx4p9jVO6sFxKdpA5neDtg%3D&"\
            "oauth_signature_method=HMAC-SHA1&"\
            "oauth_timestamp=1420370306&"\
            "oauth_version=1.0&"\
            "resource_link_description=A%20weekly%20blog.&"\
            "resource_link_id=120988f929-274612&"\
            "resource_link_title=Weekly%20Blog&"\
            "roles=Instructor&"\
            "tool_consumer_info_product_family_code=ims&"\
            "tool_consumer_info_version=1.1&"\
            "tool_consumer_instance_description="\
            "University%20of%20School%20%28LMSng%29&"\
            "tool_consumer_instance_guid=lmsng.school.edu&"\
            "user_id=292832126"
        with self.silo['Consumers'].open() as collection:
            consumer = lti.ToolConsumer.new_from_values(
                collection.new_entity(), self.cipher, 'default', key="12345",
                secret=ul("secret"))
            collection.insert_entity(consumer.entity)
        provider = lti.ToolProvider(
            self.container['Consumers'], self.container['Nonces'],
            self.cipher)
        consumer, parameters = provider.launch(
            command, url, headers, query_string)
        self.assertTrue(consumer.key == '12345')
        self.assertTrue('user_id' in parameters)
        self.assertTrue(parameters['user_id'] == '292832126')
        # we should have an exception if we change the parameters!
        try:
            consumer, parameters = provider.launch(
                "POST", url, headers, query_string + "%custom_value=X")
            self.fail("LTI launch with bad signature")
        except lti.LTIAuthenticationError:
            pass

    def test_bad_launch(self):
        command = "POST"
        url = "http://www.example.com/launch"
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        query_string = "context_id=456434513&context_label=SI182&"\
            "context_title=Design%20of%20Personal%20Environments&"\
            "launch_presentation_css_url=http%3A%2F%2Fwww.imsglobal.org%2F"\
            "developers%2FLTI%2Ftest%2Fv1p1%2Flms.css&"\
            "launch_presentation_document_target=frame&"\
            "launch_presentation_locale=en-US&"\
            "launch_presentation_return_url=http%3A%2F%2Fwww.imsglobal.org%2F"\
            "developers%2FLTI%2Ftest%2Fv1p1%2Flms_return.php&"\
            "lis_outcome_service_url=http%3A%2F%2Fwww.imsglobal.org%2F"\
            "developers%2FLTI%2Ftest%2Fv1p1%2Fcommon%2F"\
            "tool_consumer_outcome.php%3Fb64%3DMTIzNDU6OjpzZWNyZXQ%3D&"\
            "lis_person_contact_email_primary=user%40school.edu&"\
            "lis_person_name_family=Public&"\
            "lis_person_name_full=Jane%20Q.%20Public&"\
            "lis_person_name_given=Given&"\
            "lis_person_sourcedid=school.edu%3Auser&"\
            "lis_result_sourcedid=feb-123-456-2929%3A%3A28883&"\
            "lti_message_type=basic-lti-launch-request&"\
            "lti_version=LTI-1p0&"\
            "oauth_callback=about%3Ablank&oauth_consumer_key=12345&"\
            "oauth_nonce=45f32b44e314244a222d0e070fa55384&"\
            "oauth_signature=SKhxr%2Bx4p9jVO6sFxKdpA5neDtg%3D&"\
            "oauth_signature_method=HMAC-SHA1&"\
            "oauth_timestamp=1420370306&"\
            "oauth_version=1.0&"\
            "resource_link_description=A%20weekly%20blog.&"\
            "resource_link_id=120988f929-274612&"\
            "resource_link_title=Weekly%20Blog&"\
            "roles=Instructor&"\
            "tool_consumer_info_product_family_code=ims&"\
            "tool_consumer_info_version=1.1&"\
            "tool_consumer_instance_description="\
            "University%20of%20School%20%28LMSng%29&"\
            "tool_consumer_instance_guid=lmsng.school.edu&"\
            "user_id=292832126"
        with self.silo['Consumers'].open() as collection:
            consumer = lti.ToolConsumer.new_from_values(
                collection.new_entity(), self.cipher, 'default', key="54321",
                secret=ul("secret"))
            collection.insert_entity(consumer.entity)
        provider = lti.ToolProvider(
            self.container['Consumers'], self.container['Nonces'],
            self.cipher)
        try:
            consumer, parameters = provider.launch(
                command, url, headers, query_string)
            self.fail("LTI launch with unknown consumer key")
        except lti.LTIAuthenticationError:
            pass


class ToolProviderContextTests(unittest.TestCase):

    def test_constructor(self):
        req = MockRequest()
        context = lti.ToolProviderContext(req.environ, req.start_response)
        self.assertTrue(context.consumer is None)
        self.assertTrue(isinstance(context.parameters, dict))
        self.assertTrue(len(context.parameters) == 0)
        self.assertTrue(context.visit is None)
        self.assertTrue(context.resource is None)
        self.assertTrue(context.user is None)
        self.assertTrue(context.group is None)
        self.assertTrue(context.permissions == 0)


class ToolProviderSessionTests(unittest.TestCase):

    def setUp(self):        # noqa
        metadata = lti.load_metadata()
        self.container = metadata.root.DataServices.defaultContainer
        self.data_source = sql.SQLiteEntityContainer(
            file_path=':memory:', container=self.container)
        self.data_source.create_all_tables()
        self.cipher = wsgi.AppCipher(0, 'secret', self.container['AppKeys'])
        with self.container['Silos'].open() as collection:
            self.silo = collection.new_entity()
            self.silo['ID'].set_from_value(wsgi.key60(b'ToolProviderSession'))
            self.silo['Slug'].set_from_value('ToolProviderSession')
            collection.insert_entity(self.silo)
        # create a consumer
        with self.silo['Consumers'].open() as collection:
            self.consumer = lti.ToolConsumer.new_from_values(
                collection.new_entity(), self.cipher, 'test', '12345',
                'secret')
            collection.insert_entity(self.consumer.entity)


EXAMPLE_CONSUMERS = b"""www.example.com Secret
www.questionmark.com password
"""


class BLTIProviderTests(unittest.TestCase):

    def test_constructor(self):
        lti.BLTIToolProvider()

    def test_new_consumer(self):
        tp = lti.BLTIToolProvider()
        keys = {}
        secrets = {}
        for i in range3(100):
            key, secret = tp.new_consumer()
            self.assertFalse(key in keys, "Repeated key from TP")
            keys[key] = secret
            self.assertFalse(secret in secrets, "Repeated secret from IP")
            secrets[secret] = key
        key, secret = tp.new_consumer("www.example.com")
        try:
            key, secret = tp.new_consumer("www.example.com")
            self.fail("Failure to spot duplicate key")
        except lti.BLTIDuplicateKeyError:
            pass

    def test_lookup(self):
        tp = lti.BLTIToolProvider()
        key, secret = tp.new_consumer('hello')
        consumer = tp.lookup_consumer('hello')
        self.assertTrue(consumer.key == 'hello')
        self.assertTrue(consumer.secret == secret)

    def test_load_save(self):
        tp = lti.BLTIToolProvider()
        tp.load_from_file(io.BytesIO(EXAMPLE_CONSUMERS))
        consumer = tp.lookup_consumer('www.example.com')
        self.assertTrue(consumer.secret == "Secret")
        try:
            tp.load_from_file(io.BytesIO(EXAMPLE_CONSUMERS))
            self.fail("Faiure to spot duplicate key on reload")
        except lti.BLTIDuplicateKeyError:
            pass
        f = io.BytesIO()
        tp.save_to_file(f)
        self.assertTrue(f.getvalue() == EXAMPLE_CONSUMERS,
                        "Got \n%s\nExpected: \n%s" %
                        (f.getvalue(), EXAMPLE_CONSUMERS))

    def test_launch(self):
        tp = lti.BLTIToolProvider()
        tp.load_from_file(io.BytesIO(EXAMPLE_CONSUMERS))


class ToolProviderAppTests(unittest.TestCase):

    def setUp(self):        # noqa
        self.d = tempfile.mkdtemp('.d', 'pyslet-test_blti-')

    def tearDown(self):     # noqa
        shutil.rmtree(self.d)

    def test_create_silo_option(self):

        class TPApp(lti.ToolProviderApp):
            private_files = self.d
        p = optparse.OptionParser()
        TPApp.add_options(p)
        options, args = p.parse_args(['-m'])
        # setup should succeed with default metadata
        TPApp.setup(options=options, args=args)
        # in memory database created, no silos
        with TPApp.container['Silos'].open() as collection:
            self.assertTrue(len(collection) == 0)

        class TPApp(lti.ToolProviderApp):
            private_files = self.d
        p = optparse.OptionParser()
        TPApp.add_options(p)
        options, args = p.parse_args(['-m', '--create_silo'])
        TPApp.setup(options=options, args=args)
        # in memory database created, with default silo
        with TPApp.container['Silos'].open() as collection:
            self.assertTrue(len(collection) == 1)
            silo = collection.values()[0]
            self.assertTrue(silo['Slug'].value == 'testing')
        with silo['Consumers'].open() as collection:
            self.assertTrue(len(collection) == 1)
            consumer = collection.values()[0]
            tc = lti.ToolConsumer(consumer, TPApp.new_app_cipher())
            self.assertTrue(tc.key == '12345', tc.key)
            self.assertTrue(tc.secret == 'secret', tc.secret)

    def test_constructor(self):

        class TPApp(lti.ToolProviderApp):
            private_files = self.d
        p = optparse.OptionParser()
        TPApp.add_options(p)
        options, args = p.parse_args(['-m', '--create_silo'])
        TPApp.setup(options=options, args=args)
        with TPApp.container['Silos'].open() as collection:
            self.assertTrue(len(collection) == 1)
            silo = collection.values()[0]
        with silo['Consumers'].open() as collection:
            consumer = collection.values()[0]
            lti.ToolConsumer(consumer, TPApp.new_app_cipher())
        # ready to test the app
        app = TPApp()
        self.assertTrue(isinstance(app.provider, lti.ToolProvider))
        # now test the App logic, initially no visits
        with TPApp.container['Visits'].open() as collection:
            self.assertTrue(len(collection) == 0)

    def test_set_launch_group(self):

        class TPApp(lti.ToolProviderApp):
            private_files = self.d
        p = optparse.OptionParser()
        TPApp.add_options(p)
        options, args = p.parse_args(['-m', '--create_silo'])
        TPApp.setup(options=options, args=args)
        with TPApp.container['Silos'].open() as collection:
            silo = collection.values()[0]
        with silo['Consumers'].open() as collection:
            consumer = collection.values()[0]
            tc = lti.ToolConsumer(consumer, TPApp.new_app_cipher())
        app = TPApp()
        req = MockRequest()
        context = lti.ToolProviderContext(req.environ, req.start_response)
        context.session = wsgi.CookieSession()
        context.session.establish()
        context.consumer = tc
        # parameters will be empty, so no launch group
        app.set_launch_group(context)
        self.assertTrue(context.group is None)
        with TPApp.container['Contexts'].open() as collection:
            self.assertTrue(len(collection) == 0)
        # add in group parameters
        context.parameters['context_id'] = "gid"
        context.parameters['context_type'] = "Group"
        context.parameters['context_title'] = "Group101"
        context.parameters['context_label'] = "G101"
        app.set_launch_group(context)
        # now check that we have a group in the data store
        with TPApp.container['Contexts'].open() as collection:
            self.assertTrue(len(collection) == 1)
            group = collection.values()[0]
            self.assertTrue(group['ContextID'].value == "gid")
            self.assertTrue(group['Title'].value == "Group101")
            self.assertTrue(group['Label'].value == "G101")
            self.assertTrue(
                group['Types'].value == "urn:lti:context-type:ims/lis/Group")
            gconsumer = group['Consumer'].get_entity()
            # check it is associated with the consumer we created
            self.assertTrue(gconsumer == consumer)
            # and there are no resources
            with group['Resources'].open() as rcollection:
                self.assertTrue(len(rcollection) == 0)
        self.assertTrue(context.group == group)

    def test_set_launch_resource(self):

        class TPApp(lti.ToolProviderApp):
            private_files = self.d
        p = optparse.OptionParser()
        TPApp.add_options(p)
        options, args = p.parse_args(['-m', '--create_silo'])
        TPApp.setup(options=options, args=args)
        with TPApp.container['Silos'].open() as collection:
            silo = collection.values()[0]
        with silo['Consumers'].open() as collection:
            consumer = collection.values()[0]
            tc = lti.ToolConsumer(consumer, TPApp.new_app_cipher())
        app = TPApp()
        req = MockRequest()
        context = lti.ToolProviderContext(req.environ, req.start_response)
        context.session = wsgi.CookieSession()
        context.session.establish()
        context.consumer = tc
        # parameters will be empty, so no launch resource: error
        try:
            app.set_launch_resource(context)
            self.fail("resource_link_id is required")
        except lti.LTIProtocolError:
            pass
        with TPApp.container['Resources'].open() as collection:
            self.assertTrue(len(collection) == 0)
        # add a resource link to the parameters
        context.parameters['resource_link_id'] = 'rlink'
        context.parameters['resource_link_title'] = 'A Resource'
        context.parameters['resource_link_description'] = 'About the resource'
        app.set_launch_resource(context)
        with TPApp.container['Resources'].open() as collection:
            self.assertTrue(len(collection) == 1)
            resource = collection.values()[0]
            self.assertTrue(resource['LinkID'].value == "rlink")
            self.assertTrue(resource['Title'].value == "A Resource")
            self.assertTrue(
                resource['Description'].value == "About the resource")
            rconsumer = resource['Consumer'].get_entity()
            # check it is associated with the consumer we created
            self.assertTrue(rconsumer == consumer)
            # and there are is no context
            self.assertTrue(resource['Context'].get_entity() is None)
            # and no visits
            with resource['Visits'].open() as vcollection:
                self.assertTrue(len(vcollection) == 0)
        self.assertTrue(context.resource == resource)
        # now check contexts too
        context.parameters['context_id'] = "gid"
        context.parameters['context_type'] = "Group"
        context.parameters['context_title'] = "Group101"
        context.parameters['context_label'] = "G101"
        context.parameters['resource_link_id'] = 'rlink2'
        context.parameters['resource_link_title'] = 'Another Resource'
        context.parameters['resource_link_description'] = 'Resource & context'
        app.set_launch_group(context)
        app.set_launch_resource(context)
        self.assertTrue(context.resource['LinkID'].value == 'rlink2')
        self.assertTrue(
            context.resource['Context'].get_entity() == context.group)

    def test_set_launch_user(self):

        class TPApp(lti.ToolProviderApp):
            private_files = self.d
        p = optparse.OptionParser()
        TPApp.add_options(p)
        options, args = p.parse_args(['-m', '--create_silo'])
        TPApp.setup(options=options, args=args)
        with TPApp.container['Silos'].open() as collection:
            silo = collection.values()[0]
        with silo['Consumers'].open() as collection:
            consumer = collection.values()[0]
            tc = lti.ToolConsumer(consumer, TPApp.new_app_cipher())
        app = TPApp()
        req = MockRequest()
        context = lti.ToolProviderContext(req.environ, req.start_response)
        context.session = wsgi.CookieSession()
        context.session.establish()
        context.consumer = tc
        # parameters will be empty, so no launch user
        app.set_launch_user(context)
        self.assertTrue(context.user is None)
        with TPApp.container['Users'].open() as collection:
            self.assertTrue(len(collection) == 0)
        # add a user to the parameters
        context.parameters['user_id'] = '123456'
        context.parameters['lis_person_name_given'] = 'Jane'
        context.parameters['lis_person_name_family'] = 'Doe'
        context.parameters['lis_person_name_full'] = 'Jane Doe'
        context.parameters['lis_person_contact_email_primary'] = \
            'j.doe@example.com'
        app.set_launch_user(context)
        with TPApp.container['Users'].open() as collection:
            self.assertTrue(len(collection) == 1)
            user = collection.values()[0]
            self.assertTrue(user['UserID'].value == "123456")
            self.assertTrue(user['GivenName'].value == "Jane")
            self.assertTrue(user['FamilyName'].value == "Doe")
            self.assertTrue(user['FullName'].value == "Jane Doe")
            self.assertTrue(user['Email'].value == "j.doe@example.com")
            uconsumer = user['Consumer'].get_entity()
            # check it is associated with the consumer we created
            self.assertTrue(uconsumer == consumer)
            # and no visits
            with user['Visits'].open() as vcollection:
                self.assertTrue(len(vcollection) == 0)
        self.assertTrue(context.user == user)

    def test_new_visit(self):

        class TPApp(lti.ToolProviderApp):
            private_files = self.d
        p = optparse.OptionParser()
        TPApp.add_options(p)
        options, args = p.parse_args(['-m', '--create_silo'])
        TPApp.setup(options=options, args=args)
        with TPApp.container['Silos'].open() as collection:
            silo = collection.values()[0]
        with silo['Consumers'].open() as collection:
            consumer = collection.values()[0]
            tc = lti.ToolConsumer(consumer, TPApp.new_app_cipher())
        app = TPApp()
        req = MockRequest()
        context = lti.ToolProviderContext(req.environ, req.start_response)
        context.session = wsgi.CookieSession()
        unestablished_id = context.session.sid
        context.consumer = tc
        context.parameters['resource_link_id'] = 'rlink'
        context.parameters['resource_link_title'] = 'A Resource'
        context.parameters['resource_link_description'] = 'About the resource'
        app.set_launch_resource(context)
        # create a new visit in this unestablished session
        app.new_visit(context)
        with TPApp.container['Visits'].open() as collection:
            self.assertTrue(len(collection) == 1)
            visit = collection.values()[0]
            self.assertTrue(visit['Session'].value == unestablished_id)
        self.assertTrue(visit == context.visit)
        # now check that when we establish the session we're updated
        app.establish_session(context)
        self.assertTrue(context.session.established)
        established_id = context.session.sid
        self.assertTrue(unestablished_id != established_id)
        with TPApp.container['Visits'].open() as collection:
            self.assertTrue(len(collection) == 1)
            visit = collection.values()[0]
            self.assertTrue(visit['Session'].value == established_id)
        # but it should still be the same visit
        self.assertTrue(visit == context.visit)
        # now check that a new visit replaces an old one
        first_visit = visit
        context.parameters['user_id'] = '123456'
        context.parameters['lis_person_name_given'] = 'Jane'
        context.parameters['lis_person_name_family'] = 'Doe'
        context.parameters['lis_person_name_full'] = 'Jane Doe'
        context.parameters['lis_person_contact_email_primary'] = \
            'j.doe@example.com'
        app.set_launch_user(context)
        app.new_visit(context)
        self.assertFalse(first_visit == context.visit)
        self.assertTrue(context.visit['Session'].value == established_id)
        with TPApp.container['Visits'].open() as collection:
            self.assertTrue(len(collection) == 2)
            # reload the first visit
            first_visit = collection[first_visit.key()]
            # this visit should no longer be associated with a session
            self.assertTrue(first_visit['Session'].value is None)
        # now check that a new visit with a different user orphans
        # visits from the old user (even when resource doesn't match)
        janes_visit = context.visit
        context.parameters['resource_link_id'] = 'rlink2'
        context.parameters['resource_link_title'] = 'Another Resource'
        context.parameters['resource_link_description'] = 'Details'
        app.set_launch_resource(context)
        context.parameters['user_id'] = '123457'
        context.parameters['lis_person_name_given'] = 'John'
        context.parameters['lis_person_name_family'] = 'Doe'
        context.parameters['lis_person_name_full'] = 'John Doe'
        context.parameters['lis_person_contact_email_primary'] = \
            'j.doe2@example.com'
        app.set_launch_user(context)
        app.new_visit(context)
        self.assertFalse(janes_visit == context.visit)
        with TPApp.container['Visits'].open() as collection:
            self.assertTrue(len(collection) == 3)
            # reload jane's visit
            janes_visit = collection[janes_visit.key()]
            # this visit should no longer be associated with a session
            self.assertTrue(janes_visit['Session'].value is None)
        # check that a login to a different resource with the same
        # user support multiple visits
        johns_first_visit = context.visit
        context.parameters['resource_link_id'] = 'rlink3'
        context.parameters['resource_link_title'] = 'Yet Another Resource'
        context.parameters['resource_link_description'] = 'More Details'
        app.set_launch_resource(context)
        app.new_visit(context)
        self.assertFalse(johns_first_visit == context.visit)
        with TPApp.container['Visits'].open() as collection:
            self.assertTrue(len(collection) == 4)
            # reload john's first visit
            johns_first_visit = collection[johns_first_visit.key()]
            # this visit should still be associated with the session
            self.assertTrue(
                johns_first_visit['Session'].value == established_id)

#         # quick check of find_visit...
#         match_visit = session.find_visit(resource_id)
#         self.assertTrue(match_visit is not None)
#         self.assertTrue(match_visit == visit5)
#         match_visit = session.find_visit(resource2_id)
#         self.assertTrue(match_visit is not None)
#         self.assertTrue(match_visit == visit4)
#         match_visit = session.find_visit(max(resource_id, resource2_id) + 1)
#         self.assertTrue(match_visit is None)
#         # check that a login from the NULL user replaces
#         session.add_visit(self.consumer, visit)
#         session.commit()
#         with session.entity['Visits'].open() as collection:
#             self.assertTrue(len(collection) == 1)
#             self.assertTrue(1 in collection)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
