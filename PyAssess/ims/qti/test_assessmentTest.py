import unittest

from assessmentTest import *

def suite():
	return unittest.makeSuite(AssessmentTestTest,'test')

class AssessmentTestTest(unittest.TestCase):
	pass

if __name__ == "__main__":
	unittest.main()