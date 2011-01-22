import unittest

from session import *
from assessmentItem import AssessmentItem, ResponseDeclaration, OutcomeDeclaration

def suite():
	return unittest.makeSuite(SessionTest,'test')


class SessionTest(unittest.TestCase):
	def setUp(self):
		self.item=AssessmentItem("test","Session Test Item",False,True)
		response=ResponseDeclaration("RESPONSE",Cardinality.Single,BaseType.Identifier)
		response.SetDefaultValue("A")
		self.item.DeclareVariable(response)
		outcome=OutcomeDeclaration("INTEGER_SCORE",Cardinality.Single,BaseType.Integer)
		self.item.DeclareVariable(outcome)
		outcome=OutcomeDeclaration("FLOAT_SCORE",Cardinality.Single,BaseType.Float)
		self.item.DeclareVariable(outcome)
		outcome=OutcomeDeclaration("GRADE_1",Cardinality.Single,BaseType.Identifier)
		self.item.DeclareVariable(outcome)
		outcome=OutcomeDeclaration("GRADE_2",Cardinality.Single,BaseType.Identifier)
		outcome.SetDefaultValue("OK")
		self.item.DeclareVariable(outcome)
		self.item.CreateResponseProcessing()

	def tearDown(self):
		pass
				
	def testConstructor(self):
		"""Test constructor"""
		session=ItemSession(self.item)
		self.failUnless(session.userState==AssessmentItemState.Initial,"initial state test")
		self.failUnless(session.GetOutcomeValue('completionStatus')==
			[Cardinality.Single,BaseType.Identifier,'not_attempted'],"completionStatus initial value")
		self.failUnless(session.GetResponseValue('duration')==
			[Cardinality.Single,BaseType.Duration,0.0],"duration initial value")
		self.failUnless(session.GetResponseValue('RESPONSE')==
			[Cardinality.Single,BaseType.Identifier,None],"RESPONSE initial value")	
		self.failUnless(session.GetOutcomeValue('INTEGER_SCORE')==
			[Cardinality.Single,BaseType.Integer,0],"INTEGER_SCORE initial value")
		self.failUnless(session.GetOutcomeValue('FLOAT_SCORE')==
			[Cardinality.Single,BaseType.Float,0.0],"FLOAT_SCORE initial value")
		self.failUnless(session.GetOutcomeValue('GRADE_1')==
			[Cardinality.Single,BaseType.Identifier,None],"GRADE_1 initial value")
		self.failUnless(session.GetOutcomeValue('GRADE_2')==
			[Cardinality.Single,BaseType.Identifier,"OK"],"GRADE_2 initial value")
					
	def testBeginAttempt(self):
		session=ItemSession(self.item)
		session.BeginAttempt()
		self.failUnless(session.userState==AssessmentItemState.Interacting,"begin attempt state test")
		self.failUnless(session.GetOutcomeValue('completionStatus')==
			[Cardinality.Single,BaseType.Identifier,'unknown'],"begin attempt completionStatus test")
	
	def testEndAttempt(self):
		session=ItemSession(self.item)
		session.BeginAttempt()
		# End of first attempt, no values updated
		session.EndAttempt({})
		# Empty response processing so we advance to ModalFeedback state.
		self.failUnless(session.userState==AssessmentItemState.ModalFeedback,"end attempt state test")
		self.failUnless(session.GetResponseValue('RESPONSE')==
			[Cardinality.Single,BaseType.Identifier,"A"],"RESPONSE default value")
		session.BeginAttempt()
		values={'RESPONSE':'B'}
		session.EndAttempt(values)
		self.failUnless(session.GetResponseValue('RESPONSE')==
			[Cardinality.Single,BaseType.Identifier,"B"],"RESPONSE updated value")	
		session.BeginAttempt()
		session.EndAttempt({})
		self.failUnless(session.GetResponseValue('RESPONSE')==
			[Cardinality.Single,BaseType.Identifier,"B"],"RESPONSE 2nd attempt value")	

			

if __name__ == "__main__":
	unittest.main()		