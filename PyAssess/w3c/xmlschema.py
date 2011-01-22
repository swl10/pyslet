from string import split, join
from math import modf, floor, log10, pow

# We use the machine Epsilon to put bounds on the number of fractional
# digits we generate in decimal representations.
kEpsilon=1.0
kMaxSigFig=0
while 1.0+kEpsilon>1.0:
	kEpsilon=kEpsilon/10.0
	kMaxSigFig+=1

def ParseBoolean(src):
	if src=="true":
		return 1
	elif src=="false":
		return 0
	elif src=="1":
		return 1
	elif src=="0":
		return 0
	else:
		raise ValueError

def FormatBoolean(src):
	if src:
		return "true"
	else:
		return "false"

def ParseInteger(src):
	if not src:
		raise ValueError
	else:
		sign=1
		off=0
		if src[0]=='-':
			sign=-1
			off=1
		elif src[0]=='+':
			off=1
		src=src[off:]
		if not src.isdigit():
			raise ValueError
		return sign*int(src)

def FormatInteger(src):
	return str(src)

def ParseDecimal(src,totalDigits=None,fractionDigits=None):
	parts=split(src,'.')
	if len(parts)==2:
		integerPart,fractionPart=parts
	elif len(parts)==1:
		integerPart=parts[0]
		fractionPart=''
	else:
		raise ValueError(src)
	sign=1.0
	if integerPart:
		if integerPart[0]=='-':
			sign=-1.0
			integerPart=integerPart[1:]
		elif integerPart[0]=='+':
			integerPart=integerPart[1:]
		if integerPart:
			if not integerPart.isdigit():
				raise ValueError(src)
			mainDigits=len(integerPart)
			value=float(integerPart)*sign
		else:
			value=0.0
	else:
		value=0.0
	if fractionPart:
		if not fractionPart.isdigit():
			raise ValueError(src)
		value=value+float(fractionPart)/float(10**len(fractionPart))
	if not (totalDigits is None) and len(integerPart)+len(fractionPart)>totalDigits:
		raise ValueError("%s exceeds %i total digits"%(src,totalDigits))
	if not (fractionDigits is None) and len(fractionPart)>fractionDigits:
		raise ValueError("%s exceeds %i fractional digits"%(src,fractionDigits))
	return value					

def FormatDecimal(src,totalDigits=None,fractionDigits=None):
	# deal with the minus sign first
	#import pdb
	#pdb.set_trace()
	if src<0:
		sign=["-"]
		src=-src
	else:
		sign=[]
	# the canonical representation calls for at least one digit to the right
	# of the decimal point, but later on we'll relax this constraint if totalDigits
	# dictates that we must
	trimFraction=0
	# Now create the string of digits
	if src==0.0:
		digits=[0,0]
		roundPoint=1
		decimalPoint=1
	else:
		exp=int(floor(log10(src)))
		digits=map(lambda x:ord(x)-48,list(str(long(floor(pow(10.0,kMaxSigFig-exp)*src)))))
		if len(digits)>kMaxSigFig+1:
			# we have overflowed
			exp+=1
		elif len(digits)<kMaxSigFig+1:
			# we have underflowed
			exp-=1
			digits.append(0)
		roundPoint=kMaxSigFig
		# Expand digits to ensure that the decimal point falls somewhere in, or just after,
		# the digits it describes
		decimalPoint=exp+1
		if decimalPoint<1:
			# pre-pend zeros
			digits=[0]*(1-decimalPoint)+digits
			roundPoint+=(1-decimalPoint)
			decimalPoint=1
		elif decimalPoint>=len(digits):
			digits=digits+[0]*(decimalPoint-len(digits)+1)
	# Now adjust the rounding position for the requested precision (as necessary)
	if not (totalDigits is None):
		if totalDigits<decimalPoint:
			raise ValueError("%g value exceeds %i total digits"%(src,totalDigits))
		elif totalDigits==decimalPoint:
			# we'll have to trim the fraction
			trimFraction=1
		if totalDigits<roundPoint:
			roundPoint=totalDigits
	if not (fractionDigits is None):
		if decimalPoint+fractionDigits<roundPoint:
			roundPoint=decimalPoint+fractionDigits
	# Now do the rounding, step 1, check for overflow and then zero everything up
	# to and including the round point itself
	overflow=(digits[roundPoint]>4)
	for i in range(len(digits)-1,roundPoint-1,-1):
		digits[i]=0
	# keep rounding until we stop overflowing
	if overflow:
		for i in range(roundPoint-1,-1,-1):
			digits[i]+=1
			if digits[i]>9:
				digits[i]=0
			else:
				overflow=0
				break
		if overflow:
			digits=[1]+digits
			decimalPoint+=1
			roundPoint+=1
			if trimFraction:
				# we were on the limit before, now we've bust it
				raise ValueError("%g value exceeds %i total digits"%(src,totalDigits))
	# Truncate any trailing zeros, except the first zero to the right of the point (maybe)
	trimPoint=len(digits)
	for i in range(len(digits)-1,decimalPoint-trimFraction,-1):
		if digits[i]==0:
			trimPoint=i
		else:
			break
	digits=digits[:trimPoint]
	digits=map(lambda x:chr(48+x),digits)
	return join(sign+digits[:decimalPoint]+['.']+digits[decimalPoint:],'')


def ParseFloat(src):
	parts=split(src,'e')
	if len(parts)==1:
		parts=split(src,'E')
	if len(parts)==2:
		mantissaStr,exponentStr=parts
		mantissa=ParseDecimal(parts[0])
		exponent=ParseInteger(exponentStr)
	elif len(parts)==1:
		mantissa=ParseDecimal(parts[0])
		exponent=0
	else:
		raise ValueError(src)
	return mantissa*pow(10.0,float(exponent))

		
def FormatFloat(src):
	# deal with the minus sign first
	#import pdb
	#pdb.set_trace()
	if src<0:
		sign=["-"]
		src=-src
	else:
		sign=[]
	# Now create the string of digits
	if src==0.0:
		digits=[0,0]
		exponent=0
	else:
		exponent=int(floor(log10(src)))
		digits=map(lambda x:ord(x)-48,list(str(long(floor(pow(10.0,kMaxSigFig-exponent)*src)))))
		if len(digits)>kMaxSigFig+1:
			# we have overflowed
			exponent+=1
		elif len(digits)<kMaxSigFig+1:
			# we have underflowed
			exponent-=1
			digits.append(0)
		if digits[kMaxSigFig]>4:
			digits[kMaxSigFig]=0
			for i in range(kMaxSigFig-1,-1,-1):
				digits[i]+=1
				if digits[i]>9:
					digits[i]=0
				else:
					overflow=0
					break
			if overflow:
				digits=[1,0]
				exponent+=1
		# Truncate any trailing zeros, except the first zero to the right of the point
		trimPoint=len(digits)
		for i in range(len(digits)-1,1,-1):
			if digits[i]==0:
				trimPoint=i
			else:
				break
		digits=digits[:trimPoint]
	digits=map(lambda x:chr(48+x),digits)
	return join(sign+digits[:1]+['.']+digits[1:]+['E',FormatInteger(exponent)],'')
