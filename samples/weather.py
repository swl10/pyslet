#! /usr/bin/env python
"""Creates an OData in-memory cache of key value pairs"""

# SAMPLE_DIR='small-sample'
SAMPLE_DIR='daily-text'
SAMPLE_DB='weather.db'

SERVICE_PORT=8080
SERVICE_ROOT="http://localhost:%i/"%SERVICE_PORT

import logging, threading, time, string, os, StringIO, os.path
from wsgiref.simple_server import make_server

import pyslet.iso8601 as iso
import pyslet.odata2.csdl as edm
import pyslet.odata2.core as core
import pyslet.odata2.metadata as edmx
from pyslet.odata2.server import ReadOnlyServer
from pyslet.odata2.sqlds import SQLiteEntityContainer
from pyslet.odata2.memds import InMemoryEntityContainer
import pyslet.rfc2616 as http


def LoadMetadata(path='WeatherSchema.xml'):
	"""Loads the metadata file from the current directory."""
	doc=edmx.Document()
	with open(path,'rb') as f:
		doc.Read(f)
	return doc


def MakeContainer(doc,drop=False,path=SAMPLE_DB):
	if drop and os.path.isfile(path):
		os.remove(path)
	create=not os.path.isfile(path)
	container=SQLiteEntityContainer(filePath=path,containerDef=doc.root.DataServices['WeatherSchema.CambridgeWeather'])
	if create:
		container.CreateAllTables()

	

def IsBST(t):
	"""Returns True/False/Unknown if the timepoint t is in BST
	
	This function uses the last Sunday in the month algorithm even
	though most sources say that prior to 1996 the rule was different.
	The only date of contention in this data set is 1995-10-22 which
	should have a clock change but the data set clearly have a change on
	1995-10-29, a week later."""
	century,year,month,day=t.date.GetCalendarDay()
	if month<3:
		return False
	elif month==3:
		if day<24:
			return False
		# deal with switch to BST
		century,decade,year,week,weekday=t.date.GetWeekDay()
		if weekday==7:
			# Sunday - look deeper
			hour,minute,second=t.time.GetTime()
			if hour<=1:
				return False
			else:
				return True
		elif day+(7-weekday)>31:
			# next Sunday's date is in April, we already changed
			return True
		else:
			# next Sunday's date is in March, we haven't changed yet
			return False
	elif month<10:
		return True
	elif month==10:
		if day<24:
			return True
		# deal with switch to GMT
		century,decade,year,week,weekday=t.date.GetWeekDay()
		if weekday==7:
			# Sunday - look deeper
			hour,minute,second=t.time.GetTime()
			if hour<1:
				return True
			elif hour>1:
				return False
			else:
				return None		# Ambiguous time
		elif day+(7-weekday)>31:
			# next Sunday's date is in November, we already changed
			return False
		else:
			# next Sunday's date is in October, we haven't changed yet
			return True		
	else:
		return False
		
	
def LoadDataFromFile(weatherData,f,year,month,day):
	with weatherData.OpenCollection() as collection:
		while True:
			line=f.readline()
			if len(line)==0:
				break
			elif line[0]=='#':
				continue
			data=line.split()
			if not data:
				continue
			if len(data)<11:
				data=data+['*']*(11-len(data))
			for i in (1,3,5,7,8,10):
				try:
					data[i]=float(data[i])
				except ValueError:
					data[i]=None
			for i in (2,4,6):
				try:
					data[i]=int(data[i])
				except ValueError:
					data[i]=None
			dataPoint=collection.NewEntity()
			hour,min=map(int,data[0].split(':'))
			tValue=iso.TimePoint(
				date=iso.Date(century=year/100,year=year%100,month=month,day=day),
				time=iso.Time(hour=hour,minute=min,second=0))
			bst=IsBST(tValue)
			if bst is not False:
				# assume BST for now, add the zone info and then shift to GMT
				tValue=tValue.WithZone(zDirection=1,zHour=1).ShiftZone(zDirection=0)
			dataPoint['TimePoint'].SetFromValue(tValue)
			dataPoint['Temperature'].SetFromValue(data[1])
			dataPoint['Humidity'].SetFromValue(data[2])
			dataPoint['DewPoint'].SetFromValue(data[3])
			dataPoint['Pressure'].SetFromValue(data[4])
			dataPoint['WindSpeed'].SetFromValue(data[5])
			dataPoint['WindDirection'].SetFromValue(data[6])
			dataPoint['Sun'].SetFromValue(data[7])
			dataPoint['Rain'].SetFromValue(data[8])
			shour,smin=map(int,data[9].split(':'))
			dataPoint['SunRainStart'].SetFromValue(iso.Time(hour=shour,minute=smin,second=0))
			dataPoint['WindSpeedMax'].SetFromValue(data[10])
			try:
				collection.InsertEntity(dataPoint)
			except edm.ConstraintError:
				if bst is None:
					# This was an ambiguous entry, the first one is in BST, the
					# second one is in GMT as the clocks have gone back, so we
					# shift forward again and then force the zone to GMT
					tValue=tValue.ShiftZone(zDirection=1,zHour=1).WithZone(zDirection=0)
					dataPoint['TimePoint'].SetFromValue(tValue)
					logging.info("Auto-detecting switch to GMT at: %s",str(tValue)) 
					try:
						collection.InsertEntity(dataPoint)
					except KeyError:
						logging.error("Duplicate data point during BST/GMT switching: %s",str(tValue))
				else:
					logging.error("Unexpected duplicate data point: %s",str(tValue))
	

def LoadData(weatherData,dirName):
	for fileName in os.listdir(dirName):
		if not fileName[0:4].isdigit() or fileName[-1]=='~':
			# ignore odd files and some editor backups
			continue
		logging.info("Loading data from file %s",os.path.join(dirName,fileName))
		year,month,day=map(int,fileName.split('_'))
		with open(os.path.join(dirName,fileName),'r') as f:
			LoadDataFromFile(weatherData,f,year,month,day)

def LoadNotes(weatherNotes,fileName,weatherData):
	with open(fileName,'r') as f:
		id=1
		with weatherNotes.OpenCollection() as collection, weatherData.OpenCollection() as data:
			while True:
				line=f.readline()
				if len(line)==0:
					break
				elif line[0]=='#':
					continue
				noteWords=line.split()
				if noteWords:
					note=collection.NewEntity()
					note['ID'].SetFromValue(id)
					start=iso.TimePoint(
						date=iso.Date.FromString(noteWords[0]),
						time=iso.Time(hour=0,minute=0,second=0))
					note['StartDate'].SetFromValue(start)
					end=iso.TimePoint(
						date=iso.Date.FromString(noteWords[1]).Offset(days=1),
						time=iso.Time(hour=0,minute=0,second=0))
					note['EndDate'].SetFromValue(end)
					note['Details'].SetFromValue(string.join(noteWords[2:],' '))
					collection.InsertEntity(note)
					# now find the data points that match
					data.Filter(core.CommonExpression.FromString("TimePoint ge datetime'%s' and TimePoint lt datetime'%s'"%(unicode(start),unicode(end))))
					for dataPoint in data.values():
						# use values, not itervalues to avoid this bug in Python 2.7
						#	http://bugs.python.org/issue10513
						dataPoint['Note'].BindEntity(note)
						data.UpdateEntity(dataPoint)
					id=id+1
	with weatherNotes.OpenCollection() as collection:
		collection.OrderBy(core.CommonExpression.OrderByFromString('StartDate desc'))
		for e in collection.itervalues():
			with e['DataPoints'].OpenCollection() as affectedData:
				print "%s-%s: %s (%i data points affected)"%(unicode(e['StartDate'].value),
					unicode(e['EndDate'].value),e['Details'].value,len(affectedData))

def DryRun():
	doc=LoadMetadata()
	container=InMemoryEntityContainer(doc.root.DataServices['WeatherSchema.CambridgeWeather'])
	weatherData=doc.root.DataServices['WeatherSchema.CambridgeWeather.DataPoints']
	weatherNotes=doc.root.DataServices['WeatherSchema.CambridgeWeather.Notes']
	LoadData(weatherData,SAMPLE_DIR)
	LoadNotes(weatherNotes,'weathernotes.txt',weatherData)
	return doc.root.DataServices['WeatherSchema.CambridgeWeather']
	
def TestModel(drop=False):
	"""Read and write some key value pairs"""
	doc=LoadMetadata()
	container=MakeContainer(doc,drop)
	weatherData=doc.root.DataServices['WeatherSchema.CambridgeWeather.DataPoints']
	weatherNotes=doc.root.DataServices['WeatherSchema.CambridgeWeather.Notes']
	if drop:
		LoadData(weatherData,SAMPLE_DIR)
		LoadNotes(weatherNotes,'weathernotes.txt',weatherData)
	with weatherData.OpenCollection() as collection:
		collection.OrderBy(core.CommonExpression.OrderByFromString('WindSpeedMax desc'))
		collection.SetPage(30)
		for e in collection.iterpage():
			note=e['Note'].GetEntity()
			if e['WindSpeedMax'] and e['Pressure']:
				print "%s: Pressure %imb, max wind speed %0.1f knots (%0.1f mph); %s"%(unicode(e['TimePoint'].value),
					e['Pressure'].value,e['WindSpeedMax'].value,e['WindSpeedMax'].value*1.15078,
					note['Details'] if note is not None else "")


def runWeatherServer(weatherApp=None):
	"""Starts the web server running"""
	server=make_server('',SERVICE_PORT,weatherApp)
	logging.info("HTTP server on port %i running"%SERVICE_PORT)
	# Respond to requests until process is killed
	server.serve_forever()


def runWeatherLoader(container=None):
	"""Starts a thread that monitors the DTG website for new values"""
	if container is None:
		doc=LoadMetadata()
		container=MakeContainer(doc)
	client=http.HTTPRequestManager()
	weatherData=container['DataPoints']
	DTG="http://www.cl.cam.ac.uk/research/dtg/weather/daily-text.cgi?%s"
	with weatherData.OpenCollection() as collection:
		collection.OrderBy(core.CommonExpression.OrderByFromString('TimePoint desc'))
		sleepInterval=60
		collection.SetPage(1)
		lastPoint=list(collection.iterpage())
		if lastPoint:
			lastPoint=lastPoint[0]['TimePoint'].value
		else:
			lastPoint=iso.TimePoint.FromString("19950630T000000Z")
		nextDay=lastPoint.date
		while True:
			today=iso.TimePoint.FromNowUTC().date
			if nextDay<today:
				# Load in nextDay
				logging.info("Requesting data for %s",str(nextDay))
				century,year,month,day=nextDay.GetCalendarDay()
				request=http.HTTPRequest(DTG%str(nextDay))
				client.ProcessRequest(request)
				if request.status==200:					
					# process this file and move on to the next day
					f=StringIO.StringIO(request.resBody)
					LoadDataFromFile(weatherData,f,century*100+year,month,day)
					nextDay=nextDay.Offset(days=1)
					if sleepInterval>10:
						sleepInterval=sleepInterval//2
				else:
					# back off and try again
					sleepInterval=sleepInterval*2
			else:
				# back off and try again
				sleepInterval=sleepInterval*2
			client.IdleCleanup(0)
			if sleepInterval>86400:
				sleepInterval=86400
			time.sleep(sleepInterval)
		
def main():
	"""Executed when we are launched"""
	doc=LoadMetadata()
	container=MakeContainer(doc)
	server=ReadOnlyServer(serviceRoot=SERVICE_ROOT)
	server.SetModel(doc)
	t=threading.Thread(target=runWeatherServer,kwargs={'weatherApp':server})
	t.setDaemon(True)
	t.start()
	logging.info("Starting HTTP server on %s"%SERVICE_ROOT)
	t.join()
	

if __name__ == '__main__':
	logging.basicConfig(level=logging.INFO)
	main()
