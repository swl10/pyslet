#! /usr/bin/env python

import logging
import time
import StringIO
import unittest

try:
    import pkg_resources
except ImportError:
    pkg_resources = None

import pyslet.imsbltiv1p0 as lti
import pyslet.iso8601 as iso
import pyslet.odata2.csdl as edm
import pyslet.odata2.sqlds as sql
import pyslet.wsgi as wsgi

from pyslet.rfc2396 import URI
from pyslet.urn import URN

from test_wsgi import MockRequest


if not lti.got_oauth:
    print "Basic LTI tests skipped"
    print "\tTry installing oathlib from https://pypi.python.org/pypi/oauthlib"
else:
    if pkg_resources:
        v = pkg_resources.get_distribution("oauthlib").version
        if v != "0.7.2":
            print "\tDesigned for oauthlib-0.7.2, testing with version %s" % v
    else:
        print "\tCannot determine oauthlib installed package version; "\
            "install setuptools to remove this message"


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
        with self.container['Silos'].OpenCollection() as collection:
            self.silo = collection.new_entity()
            self.silo['ID'].set_from_value(wsgi.key60('testing'))
            self.silo['Slug'].set_from_value('testing')
            collection.insert_entity(self.silo)

    def tearDown(self):     # noqa
        pass

    def test_consumer(self):
        with self.silo['Consumers'].OpenCollection() as collection:
            entity = collection.new_entity()
            consumer = lti.ToolConsumer.new_from_values(
                entity, self.cipher, 'default', key="12345", secret="secret")
            self.assertTrue(consumer.entity is entity)
            self.assertTrue(isinstance(consumer, lti.ToolConsumer))
            self.assertTrue(consumer.entity['Handle'].value == 'default')
            self.assertTrue(consumer.entity['Key'].value == '12345')
            self.assertTrue(consumer.entity['Secret'].value ==
                            self.cipher.encrypt('secret'))
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
                            self.cipher.encrypt('secret'))
            self.assertTrue(check_consuemr.key == '12345')
            self.assertTrue(check_consuemr.secret == 'secret')
            # now check the update process
            consumer.update_from_values('updated', 'password')
            self.assertTrue(consumer.entity['Handle'].value == 'updated')
            self.assertTrue(consumer.entity['Key'].value == '12345')
            self.assertTrue(consumer.entity['Secret'].value ==
                            self.cipher.encrypt('password'))
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
                            self.cipher.encrypt('password'))
            self.assertTrue(check_consuemr.key == '12345')
            self.assertTrue(check_consuemr.secret == 'password')

    def test_default_secret(self):
        with self.silo['Consumers'].OpenCollection() as collection:
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
        with self.silo['Consumers'].OpenCollection() as collection:
            entity = collection.new_entity()
            consumer = lti.ToolConsumer.new_from_values(
                entity, self.cipher, 'default', secret="secret")
            # we can default the key
            self.assertTrue(consumer.key)
            self.assertTrue(consumer.secret == 'secret')
            collection.insert_entity(entity)
            consumer2 = lti.ToolConsumer.new_from_values(
                collection.new_entity(), self.cipher, 'default',
                secret="secret")
            # secret need not be unique
            self.assertTrue(consumer2.key != consumer.key)
            self.assertTrue(consumer2.secret == 'secret')
            # Fine to persist to consumers with different keys, same
            # secret
            collection.insert_entity(consumer2.entity)

    def test_nonces(self):
        with self.silo['Consumers'].OpenCollection() as collection:
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
        with self.silo['Consumers'].OpenCollection() as collection:
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
        with self.silo['Consumers'].OpenCollection() as collection:
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
            with resource['Context'].OpenCollection() as contexts:
                self.assertTrue(len(contexts) == 0)
            # Create a context for the next part of the test
            context_id = '456434513'
            context = consumer.get_context(context_id)
            # A resource cannot be assigned to a context once it has
            # been created
            resource = consumer.get_resource(resource_link_id, context=context)
            with resource['Context'].OpenCollection() as contexts:
                self.assertTrue(len(contexts) == 0)
            # But a new resource can!
            resource_link_id = '120988f929-274613'
            resource = consumer.get_resource(resource_link_id, context=context)
            with resource['Context'].OpenCollection() as contexts:
                self.assertTrue(len(contexts) == 1)
            check_context = resource['Context'].GetEntity()
            self.assertTrue(check_context['ContextID'].value == context_id)

    def test_user(self):
        with self.silo['Consumers'].OpenCollection() as collection:
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
            time=iso.Time(hour=0, minute=0, second=0, zDirection=0)
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
        with self.container['Silos'].OpenCollection() as collection:
            self.silo = collection.new_entity()
            self.silo['ID'].set_from_value(wsgi.key60('testing'))
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
        with self.silo['Consumers'].OpenCollection() as collection:
            consumer = lti.ToolConsumer.new_from_values(
                collection.new_entity(), self.cipher, 'default', key="12345",
                secret="secret")
            collection.insert_entity(consumer.entity)
        try:
            consumer = provider.lookup_consumer('12345')
            self.assertTrue(consumer.key == '12345')
            self.assertTrue(consumer.secret == 'secret')
        except KeyError:
            self.fail("Failed to find consumer")

    def test_nonces(self):
        with self.silo['Consumers'].OpenCollection() as collection:
            consumer = lti.ToolConsumer.new_from_values(
                collection.new_entity(), self.cipher, 'default', key="12345",
                secret="secret")
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
        with self.silo['Consumers'].OpenCollection() as collection:
            consumer = lti.ToolConsumer.new_from_values(
                collection.new_entity(), self.cipher, 'default', key="12345",
                secret="secret")
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
        with self.silo['Consumers'].OpenCollection() as collection:
            consumer = lti.ToolConsumer.new_from_values(
                collection.new_entity(), self.cipher, 'default', key="54321",
                secret="secret")
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
        with self.container['Silos'].OpenCollection() as collection:
            self.silo = collection.new_entity()
            self.silo['ID'].set_from_value(wsgi.key60('ToolProviderSession'))
            self.silo['Slug'].set_from_value('ToolProviderSession')
            collection.insert_entity(self.silo)
        # create a consumer
        with self.silo['Consumers'].OpenCollection() as collection:
            self.consumer = lti.ToolConsumer.new_from_values(
                collection.new_entity(), self.cipher, 'test', '12345',
                'secret')
            collection.insert_entity(self.consumer.entity)

    def test_add_and_find_visit(self):
        req = MockRequest()
        context = lti.ToolProviderContext(req.environ, req.start_response)
        with self.container['Sessions'].OpenCollection() as collection:
            session = lti.ToolProviderSession(collection.new_entity())
            session.new_from_context(context)
            session.establish()
            session.commit()
        with session.entity['Visits'].OpenCollection() as collection:
            self.assertTrue(len(collection) == 0)
        # add a resource record
        resource = self.consumer.get_resource(
            'rlink', 'A Resource', 'About the resource')
        resource_id = resource['ID'].value
        # and now a visit
        with self.container['Visits'].OpenCollection() as collection:
            visit = collection.new_entity()
            visit['ID'].set_from_value(1)
            visit['Permissions'].set_from_value(context.permissions)
            visit['Resource'].BindEntity(resource)
            collection.insert_entity(visit)
        # now add this visit to the session
        session.add_visit(self.consumer, visit)
        session.commit()
        # Should now be possible to navigate from session to visit
        with session.entity['Visits'].OpenCollection() as collection:
            self.assertTrue(len(collection) == 1)
            self.assertTrue(list(collection)[0] == 1)
        # check that a visit to the same resource replaces
        with self.container['Visits'].OpenCollection() as collection:
            visit2 = collection.new_entity()
            visit2['ID'].set_from_value(2)
            visit2['Permissions'].set_from_value(context.permissions)
            visit2['Resource'].BindEntity(resource)
            collection.insert_entity(visit2)
        session.add_visit(self.consumer, visit2)
        session.commit()
        with session.entity['Visits'].OpenCollection() as collection:
            self.assertTrue(len(collection) == 1)
            self.assertTrue(list(collection)[0] == 2)
        # check that a login to the same resource with a user replaces
        # no user
        context.user = self.consumer.get_user('steve', 'Steve')
        with self.container['Visits'].OpenCollection() as collection:
            visit3 = collection.new_entity()
            visit3['ID'].set_from_value(3)
            visit3['Permissions'].set_from_value(context.permissions)
            visit3['Resource'].BindEntity(resource)
            visit3['User'].BindEntity(context.user)
            collection.insert_entity(visit3)
        session.add_visit(self.consumer, visit3)
        session.commit()
        with session.entity['Visits'].OpenCollection() as collection:
            self.assertTrue(len(collection) == 1)
            self.assertTrue(list(collection)[0] == 3)
        # check that a login to a different resource with a different
        # user replaces
        user2 = self.consumer.get_user('dave', 'Dave')
        resource2 = self.consumer.get_resource(
            'rlink2', 'Another Resource', 'About the other resource')
        resource2_id = resource2['ID'].value
        with self.container['Visits'].OpenCollection() as collection:
            visit4 = collection.new_entity()
            visit4['ID'].set_from_value(4)
            visit4['Permissions'].set_from_value(context.permissions)
            visit4['Resource'].BindEntity(resource2)
            visit4['User'].BindEntity(user2)
            collection.insert_entity(visit4)
        session.add_visit(self.consumer, visit4)
        session.commit()
        with session.entity['Visits'].OpenCollection() as collection:
            self.assertTrue(len(collection) == 1)
            self.assertTrue(list(collection)[0] == 4)
        # check that a login to a different resource with the same
        # user support multiple visits
        with self.container['Visits'].OpenCollection() as collection:
            visit5 = collection.new_entity()
            visit5['ID'].set_from_value(5)
            visit5['Permissions'].set_from_value(context.permissions)
            visit5['Resource'].BindEntity(resource)
            visit5['User'].BindEntity(user2)
            collection.insert_entity(visit5)
        session.add_visit(self.consumer, visit5)
        session.commit()
        with session.entity['Visits'].OpenCollection() as collection:
            self.assertTrue(len(collection) == 2)
            self.assertTrue(4 in collection)
            self.assertTrue(5 in collection)
        # quick check of find_visit...
        match_visit = session.find_visit(resource_id)
        self.assertTrue(match_visit is not None)
        self.assertTrue(match_visit == visit5)
        match_visit = session.find_visit(resource2_id)
        self.assertTrue(match_visit is not None)
        self.assertTrue(match_visit == visit4)
        match_visit = session.find_visit(max(resource_id, resource2_id) + 1)
        self.assertTrue(match_visit is None)
        # check that a login from the NULL user replaces
        session.add_visit(self.consumer, visit)
        session.commit()
        with session.entity['Visits'].OpenCollection() as collection:
            self.assertTrue(len(collection) == 1)
            self.assertTrue(1 in collection)


EXAMPLE_CONSUMERS = """www.example.com Secret
www.questionmark.com password
"""


class BLTIProviderTests(unittest.TestCase):

    def test_constructor(self):
        lti.BLTIToolProvider()

    def test_new_consumer(self):
        tp = lti.BLTIToolProvider()
        keys = {}
        secrets = {}
        for i in xrange(100):
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
        tp.load_from_file(StringIO.StringIO(EXAMPLE_CONSUMERS))
        consumer = tp.lookup_consumer('www.example.com')
        self.assertTrue(consumer.secret == "Secret")
        try:
            tp.load_from_file(StringIO.StringIO(EXAMPLE_CONSUMERS))
            self.fail("Faiure to spot duplicate key on reload")
        except lti.BLTIDuplicateKeyError:
            pass
        f = StringIO.StringIO()
        tp.save_to_file(f)
        self.assertTrue(f.getvalue() == EXAMPLE_CONSUMERS,
                        "Got \n%s\nExpected: \n%s" %
                        (f.getvalue(), EXAMPLE_CONSUMERS))

    def test_launch(self):
        tp = lti.BLTIToolProvider()
        tp.load_from_file(StringIO.StringIO(EXAMPLE_CONSUMERS))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
