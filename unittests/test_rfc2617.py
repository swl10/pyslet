#! /usr/bin/env python

import unittest
import StringIO
import socket

def suite():
	return unittest.TestSuite((
		unittest.makeSuite(HTTP2617Tests,'test') #,
#		unittest.makeSuite(MoreTests,'test')
		))


from pyslet.rfc2617 import *
import test_rfc2616 as http

import random
import os,sys

TEST_STRING="The quick brown fox jumped over the lazy dog"

TEST_SERVER_1={
	"GET / HTTP/1.1\r\nHost: www.domain1.com":"HTTP/1.1 401 Who are you?\r\nWWW-Authenticate: Basic realm=\"RFC2617\"\r\nContent-Length: %i\r\n\r\n%s"%(len(TEST_STRING),TEST_STRING),
	"GET / HTTP/1.1\r\nAuthorization: Basic dXNlcjpQYXNzd29yZA==\r\nHost: www.domain1.com":"HTTP/1.1 200 You got it!\r\nContent-Length: %i\r\n\r\n%s"%(len(TEST_STRING),TEST_STRING),	
	}

TEST_SERVER_2={
	"HEAD / HTTP/1.1\r\nHost: www.domain2.com":"HTTP/1.1 301 Moved\r\nLocation: http://www.domain1.com/\r\n\r\n"
	}
	
TEST_SERVER={
	'www.domain1.com': TEST_SERVER_1,
	'www.domain2.com': TEST_SERVER_2
	}

BAD_REQUEST="HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n"

class FakeHTTPConnection(http.FakeHTTPConnection):
	def NewSocket(self):
		http.FakeHTTPConnection.NewSocket(self)
		self.responseTable=TEST_SERVER[self.host]
		
class FakeHTTPRequestManager(http.FakeHTTPRequestManager):
	FakeHTTPConnectionClass=FakeHTTPConnection

		
class HTTP2617Tests(unittest.TestCase):
	def setUp(self):
		self.cwd=os.getcwd()
		
	def tearDown(self):
		os.chdir(self.cwd)
				
	def testCaseBasicChallenge(self):
		c=BasicChallenge()
		self.failUnless(c.scheme=="Basic","Challenge scheme: %s"%c.scheme)
		self.failUnless(c.protectionSpace is None,"Challenge protection space: %s"%c.protectionSpace)
		self.failUnless(c.realm is None,"Initial challenge realm: %s"%c.realm)
		nWords=ParseAuthParams(http.SplitWords('realm="Firewall"'),c)
		self.failUnless(nWords==3,"ParseAuthParams result: %s"%int(nWords))
		self.failUnless(c.realm=="Firewall","Parsed realm: %s"%c.realm)
		self.failUnless(str(c)=='Basic realm="Firewall"',"Format challenge")
		
	def testCaseBasicCredentials(self):
		c=BasicCredentials()
		self.failUnless(c.scheme=="Basic","Credential scheme: %s"%c.scheme)
		self.failUnless(c.protectionSpace is None,"Initial credential protected space: %s"%c.protectionSpace)
		self.failUnless(c.realm is None,"Initial credential realm: %s"%c.realm)
		c.SetBasicCredentials('dXNlcjpQYXNzd29yZA==')		
		self.failUnless(c.userid=="user","User name: %s"%c.userid)
		self.failUnless(c.password=="Password","Password: %s"%c.userid)
		self.failUnless(str(c)=='Basic dXNlcjpQYXNzd29yZA==',"Format credentials")

	def testCase401(self):
		rm=FakeHTTPRequestManager()
		# rm.SetLog(http.HTTP_LOG_DETAIL,sys.stdout)
		rm.httpUserAgent=None
		import pdb;pdb.set_trace
		request1=http.HTTPRequest("http://www.domain1.com/")
		rm.QueueRequest(request1)
		# ManagerLoop will process the queue until it blocks for more than the timeout (default, 60s)
		rm.ManagerLoop()
		response1=request1.response
		self.failUnless(response1.status==401,"Status in response1: %i"%response1.status)
		self.failUnless(response1.reason=="Who are you?","Reason in response1: %s"%response1.reason)
		self.failUnless(request1.resBody==TEST_STRING,"Data in response1: %s"%request1.resBody)
		challenges=response1.GetWWWAuthenticateChallenges()
		self.failUnless(len(challenges)==1 and isinstance(challenges[0],BasicChallenge),"Challenge")
		c=BasicCredentials()
		c.protectionSpace="http://www.domain1.com"
		c.realm=None		# should match all realms!
		c.userid='user'
		c.password='Password'
		rm.AddCredentials(c)
		request2=http.HTTPRequest("http://www.domain1.com/")
		rm.QueueRequest(request2)
		rm.ManagerLoop()
		response2=request2.response
		self.failUnless(response2.protocolVersion=="HTTP/1.1","Protocol in response1: %s"%response1.protocolVersion)
		self.failUnless(response2.status==200,"Status in response1: %i"%response1.status)
		self.failUnless(response2.reason=="You got it!","Reason in response1: %s"%response1.reason)
		self.failUnless(request2.resBody==TEST_STRING,"Data in response1: %s"%request1.resBody)		
		
					

if __name__ == '__main__':
	unittest.main()
