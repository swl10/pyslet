#!/usr/bin/env python

from sys import exc_info, stdout
from traceback import print_exception

from PyAssess.ims.qti.common import CheckValue
import PyAssess.ims.qti.asi as item
from PyAssess.ims.qti.session import ItemSession, AssessmentItemState
from PyAssess.ims.qti.deliveryEngine import TextItemView, TextCmdIndexError, InvalidSelectionError

IntroText="""Welcome to PyAssess

This is the PyAssess demonstration program.  This program is a command line QTI
delivery engine which allows you to validate, run (and debug!) your QTI version
2 questions.

"""

try:
	from SOAPpy import SOAPProxy
	IntroText+="""Web-services enabled using SOAPpy
See http://pywebsvcs.sourceforge.net/ for more information

"""
	WS_ENABLED=1
except:
	WS_ENABLED=0

IntroText+="""Type Help at the PyAssess> prompt for details of the available commands.
"""

HelpText="""PyAssess Demo Commands

?
	same as help

ba
	same as beginAttempt
	
beginAttempt
	Start a new attempt at the current item

beginSession
	Start a new session with the currently loaded item

bs
	same as beginSession
			
debug on|off
	Turn on/off verbose error reporting (includes Python tracebacks)

ea
	same as endAttempt
	
endAttempt
	End the current attempt
	
help
	display this help text
	
load <file>
	load an assessment item from the given file

peek
	lists details of all the current session variables
	
quit
	leave the demo immediately
	
setMarkingService <url>
	set the remote marking service to <url>

setms <url>
	same as setMarkingService
	
<num>
	During an attempt, select the control numbered <num>
"""

class PyAssessDemo:
	def __init__(self):
		self.quit=0
		self.p=item.AssessmentItemParser()
		self.item=None
		self.itemSession=None
		self.itemView=None
		self.debug=0
		self.markingService=None
		
	def main(self,args=[]):
		print IntroText
		# take a look at command line options here
		while not self.quit:
			try:
				args=raw_input("PyAssess> ").split()
			except EOFError:
				print "quit"
				self.quit=1
				break
			if not args:
				continue
			cmdStr=args[0].lower()
			if cmdStr.isdigit():
				# This is a runtime control reference
				if self.itemSession and self.itemSession.userState==AssessmentItemState.Interacting:
					try:
						self.itemView.DoAction(args)
						self.item.RenderBody(self.itemView)
					except TextCmdIndexError:
						print "Control index out of range"
					except InvalidSelectionError:
						print "Invalid selection (too many, or incompatible choices selected)"
				else:
					print "Not currently interacting"
				continue
			cmd=self.cmdTable.get(cmdStr,PyAssessDemo.Unknown)
			cmd(self,args)
	
	def ReadItem(self,fName):
		self.item=None
		self.itemSession=None
		self.itemView=None
		try:
			f=file(fName,'r')
		except IOError:
			print "Failed to read file %s"%fName
			err,errValue,tb=exc_info()
			print_exception(err,errValue,None)				
			return
		try:
			self.item=self.p.ReadAssessmentItem(f)
			print "Read item id %s from %s: OK"%(self.item.identifier,fName)
		except:
			print "Failed to parse item from %s: see below for details"%fName
			err,errValue,tb=exc_info()
			if not self.debug:
				tb=None
			print_exception(err,errValue,tb)
		f.close()
							
	def BeginAttempt(self,args):
		if self.itemSession:
			self.itemSession.BeginAttempt()
			self.item.RenderBody(self.itemView)
		elif self.item:
			print "Use beginSession first"
		else:
			print "No item loaded"

	def BeginSession(self,args):
		if self.item:
			self.itemSession=ItemSession(self.item)
			self.itemView=TextItemView(self.itemSession,stdout)
		else:
			print "No item loaded"

	def Debug(self,args):
		badUsage=0
		if len(args)!=2:
			badUsage=1
		else:
			if args[1].lower()=="on":
				self.debug=1
			elif args[1].lower()=="off":
				self.debug=0
			else:
				badUsage=1
		if badUsage:
			print "usage: debug on|off"

	def EndAttempt(self,args):
		if self.itemSession:
			if self.itemSession.userState!=AssessmentItemState.Interacting:
				print "No attempt in progress"
			else:
				self.itemSession.EndAttempt()
				if self.itemSession.userState==AssessmentItemState.Submitted:
					if self.markingService is not None:
						variables=[]
						for v in self.itemSession.GetVariableNames():
							value=self.itemSession.GetVariableValue(v)
							variables.append({'name':v, 'cardinality':value[0],
								'baseType':value[1], 'value':value[2]})
						try:
							newVariables=self.markingService.MarkingService(identifier=self.item.identifier,
								variables=variables)
							for v in newVariables:
								name=v['name']
								cardinality=v['cardinality']
								baseType=v['baseType']
								newValue=v['value']
								value=self.itemSession.GetVariableValue(name)
								if value[0]!=cardinality or value[1]!=baseType:
									raise VariableTypeMismatch
								if newValue is not None:
									CheckValue(value[0],value[1],newValue)
								value[2]=newValue
							self.itemSession.ResponseProcessingComplete()
						except:
							print "Remote response processing failed"
							err,errValue,tb=exc_info()
							if not self.debug:
								tb=None
							print_exception(err,errValue,tb)
					else:
						print "Session submitted, no response processing defined."
				if self.itemSession.userState==AssessmentItemState.ModalFeedback:
					# show modal feedback: todo
					pass
		else:
			print "No attempt in progress"
							
	def Help(self,args):
		if self.itemSession and self.itemSession.userState==AssessmentItemState.Interacting:
			# print ContextHelp
			print HelpText
		else:
			print HelpText
	
	def Load(self,args):
		badUsage=0
		if len(args)!=2:
			badUsage=1
		else:
			self.ReadItem(args[1])
		if badUsage:
			print "load <fileName>"
	
	def Peek(self,args):
		if self.itemSession:
			variables=self.itemSession.variables.keys()
			variables.sort()
			for v in variables:
				print v
				if v in ['completionStatus','duration']:
					typeStr="built-in response variable"
				else:
					decl=self.item.LookupVariableDeclaration(v)
					if isinstance(decl,item.ResponseDeclaration):
						typeStr="response variable"
					elif isinstance(decl,item.OutcomeDeclaration):
						typeStr="outcome variable"
					else:
						typeStr="template variable"
				print "\tType       : %s"%typeStr
				cardinality,baseType,value=self.itemSession.GetVariableValue(v)
				print "\tCardinality: %s"%item.Cardinality.Strings[cardinality]
				print "\tBase-type  : %s"%item.BaseType.Strings[baseType]
				print "\tValue      : %s"%repr(value)
		else:
			print "No item session available"
						
	def Quit(self,args):
		self.quit=1

	def SetMarkingService(self,args):
		if not WS_ENABLED:
			print """Use of remote marking service requires SOAPpy python module to be installed.
			
See http://pywebsvcs.sourceforge.net/ for more information."""
		badUsage=0
		if len(args)!=2:
			badUsage=1
		else:
			print "Setting marking service to %s"%str(args[1])
			self.markingService=SOAPProxy(args[1])
		if badUsage:
			print "setMarkingService <url>"
			return
		
	def Unknown(self,args):
		print "Unrecognized command: %s"%args[0]
		
	cmdTable={
		'?':Help,
		'ba':BeginAttempt,
		'beginattempt':BeginAttempt,
		'beginsession':BeginSession,
		'bs':BeginSession,
		'debug':Debug,
		'ea':EndAttempt,
		'endattempt':EndAttempt,
		'help':Help,
		'load':Load,
		'peek':Peek,
		'quit':Quit,
		'setMarkingService':SetMarkingService,
		'setms':SetMarkingService
		}
	

if __name__ == "__main__":
	demo=PyAssessDemo()
	demo.main()		

