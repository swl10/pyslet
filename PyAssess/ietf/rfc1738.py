import os.path

from rfc2396 import AbsoluteURI, URIHierPart, URINetPath, URIAbsPath, URISegment


class RFC1738Error(Exception): pass

class RFCFileSchemeError(RFC1738Error): pass
class RFCRemoteFileError(RFC1738Error): pass

def FilePathToURL(path):
	segments=[]
	path=os.path.abspath(path)
	# check for drive support, we use this as a flag
	drive,tail=os.path.splitdrive(path)
	while path:
		head,tail=os.path.split(path)
		if head==path:
			# path is now unsplittable
			if drive:
				tail=head
				head=''
			else:
				break
		segments[0:0]=[URISegment(tail)]
		path=head
	if segments:
		return AbsoluteURI("file",URIHierPart(URIAbsPath(segments)))
	else:
		return AbosluteURI("file",URIHierPart(URIAbsPath(None)))

def URLToFilePath(url):
	if not isinstance(url,AbsoluteURI):
		raise TypeError
	if not url.scheme.lower()=="file":
		raise ValueError
	if not isinstance(url.pathPart,URIHierPart):
		raise RFCFileSchemeError
	if isinstance(url.pathPart.pathPart,URINetPath):
		authority=url.pathPart.pathPart.authority
		absPath=url.pathPart.pathPart.absPath
	else:
		authority=None
		absPath=url.pathPart.pathPart
	if authority is not None and str(authority).lower()!="localhost":
		raise RFCRemoteFileError
	# we miss a general concept of 'root' file system at this point
	# the workaround is to pretend that '/' will do it and call os.path.join
	# anyway.  On windows, the / is dropped if a drive component comes along
	path='/'
	for seg in absPath.segments:
		# fpath components can't contain parameters
		if seg.params:
			raise RFCFileSchemeError
		path=os.path.join(path,seg.segment)
	return path