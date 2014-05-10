#! /usr/bin/env python
"""Creates an OData in-memory cache of key value pairs"""

SAMPLE_DIR='small-sample'
# SAMPLE_DIR='daily-text'
SAMPLE_DB='weather.db'

SERVICE_PORT=8080
SERVICE_ROOT="http://localhost:%i/"%SERVICE_PORT

import logging, threading, time, string, os
from wsgiref.simple_server import make_server

import pyslet.iso8601 as iso
import pyslet.odata2.csdl as edm
import pyslet.odata2.core as core
import pyslet.odata2.metadata as edmx
from pyslet.odata2.server import ReadOnlyServer
from pyslet.odata2.sqlds import SQLiteEntityContainer
from pyslet.odata2.memds import InMemoryEntityContainer


def LoadMetadata():
	"""Loads the metadata file from the current directory."""
	doc=edmx.Document()
	with open('WeatherSchema.xml','rb') as f:
		doc.Read(f)
	return doc


def MakeContainer(doc,drop=False):
	if drop and os.path.isfile(SAMPLE_DB):
		os.remove(SAMPLE_DB)
	create=not os.path.isfile(SAMPLE_DB)
	container=SQLiteEntityContainer(filePath=SAMPLE_DB,containerDef=doc.root.DataServices['WeatherSchema.CambridgeWeather'])
	if create:
		container.CreateAllTables()
	

def LoadData(weatherData,dirName):
	for fileName in os.listdir(dirName):
		if not fileName[0:4].isdigit() or fileName[-1]=='~':
			# ignore odd files and some editor backups
			continue
		logging.info("Loading data from file %s",os.path.join(dirName,fileName))
		year,month,day=map(int,fileName.split('_'))
		with open(os.path.join(dirName,fileName),'r') as f:
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
					dataPoint['TimePoint'].SetFromValue(iso.TimePoint(
						date=iso.Date(century=year/100,year=year%100,month=month,day=day),
						time=iso.Time(hour=hour,minute=min,second=0)))
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
					except KeyError:
						# duplicate key ignored due to daylight savings
						pass

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
