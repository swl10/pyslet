#! /usr/bin/env python
"""Creates an OData service from weather data"""

import io
import logging
import os
import os.path
import threading
import time

from wsgiref.simple_server import make_server

from pyslet import iso8601 as iso
from pyslet.http import client as http
from pyslet.odata2 import csdl as edm
from pyslet.odata2 import core as core
from pyslet.odata2 import metadata as edmx
from pyslet.odata2.memds import InMemoryEntityContainer
from pyslet.odata2.server import ReadOnlyServer
from pyslet.odata2.sqlds import SQLiteEntityContainer
from pyslet.py2 import output, to_text


# SAMPLE_DIR='small-sample'
SAMPLE_DIR = 'daily-text'
SAMPLE_DB = 'weather.db'

SERVICE_PORT = 8080
SERVICE_ROOT = "http://localhost:%i/" % SERVICE_PORT


def load_metadata(path=os.path.join(os.path.split(__file__)[0],
                                    'weather_schema.xml')):
    """Loads the metadata file from the current directory."""
    doc = edmx.Document()
    with open(path, 'rb') as f:
        doc.read(f)
    return doc


def make_container(doc, drop=False, path=SAMPLE_DB):
    if drop and os.path.isfile(path):
        os.remove(path)
    create = not os.path.isfile(path)
    container = SQLiteEntityContainer(
        file_path=path,
        container=doc.root.DataServices['WeatherSchema.CambridgeWeather'])
    if create:
        container.create_all_tables()
    return doc.root.DataServices['WeatherSchema.CambridgeWeather']


def make_mysql_container(doc, drop=False, create=False, host="localhost",
                         user="weather", password="password",
                         database="weather"):
    import pyslet.mysqldbds as mysql
    container = mysql.MySQLEntityContainer(
        host=host, user=user, passwd=password, db=database,
        container=doc.root.DataServices['WeatherSchema.CambridgeWeather'])
    if drop:
        container.drop_all_tables()
    if create:
        container.create_all_tables()
    return doc.root.DataServices['WeatherSchema.CambridgeWeather']


def is_bst(t):
    """Returns True/False/Unknown if the timepoint t is in BST

    This function uses the last Sunday in the month algorithm even
    though most sources say that prior to 1996 the rule was different.
    The only date of contention in this data set is 1995-10-22 which
    should have a clock change but the data set clearly have a change on
    1995-10-29, a week later."""
    century, year, month, day = t.date.get_calendar_day()
    if month < 3:
        return False
    elif month == 3:
        if day < 24:
            return False
        # deal with switch to BST
        century, decade, year, week, weekday = t.date.get_week_day()
        if weekday == 7:
            # Sunday - look deeper
            hour, minute, second = t.time.get_time()
            if hour <= 1:
                return False
            else:
                return True
        elif day + (7 - weekday) > 31:
            # next Sunday's date is in April, we already changed
            return True
        else:
            # next Sunday's date is in March, we haven't changed yet
            return False
    elif month < 10:
        return True
    elif month == 10:
        if day < 24:
            return True
        # deal with switch to GMT
        century, decade, year, week, weekday = t.date.get_week_day()
        if weekday == 7:
            # Sunday - look deeper
            hour, minute, second = t.time.get_time()
            if hour < 1:
                return True
            elif hour > 1:
                return False
            else:
                return None		# Ambiguous time
        elif day + (7 - weekday) > 31:
            # next Sunday's date is in November, we already changed
            return False
        else:
            # next Sunday's date is in October, we haven't changed yet
            return True
    else:
        return False


def load_data_from_file(weather_data, f, year, month, day):
    with weather_data.open() as collection:
        while True:
            line = f.readline().decode('ascii')
            if len(line) == 0 or line.startswith('Date unknown.'):
                break
            elif line[0] == '#':
                continue
            data = line.split()
            if not data:
                continue
            if len(data) < 11:
                data = data + ['*'] * (11 - len(data))
            for i in (1, 3, 5, 7, 8, 10):
                try:
                    data[i] = float(data[i])
                except ValueError:
                    data[i] = None
            for i in (2, 4):
                try:
                    data[i] = int(data[i])
                except ValueError:
                    data[i] = None
            data[6] = data[6].strip()
            data_point = collection.new_entity()
            hour, min = [int(i) for i in data[0].split(':')]
            tvalue = iso.TimePoint(
                date=iso.Date(century=year // 100, year=year %
                              100, month=month, day=day),
                time=iso.Time(hour=hour, minute=min, second=0))
            bst = is_bst(tvalue)
            if bst is not False:
                # assume BST for now, add the zone info and then shift to GMT
                tvalue = tvalue.with_zone(
                    zdirection=1, zhour=1).shift_zone(zdirection=0)
            data_point['TimePoint'].set_from_value(tvalue)
            data_point['Temperature'].set_from_value(data[1])
            data_point['Humidity'].set_from_value(data[2])
            data_point['DewPoint'].set_from_value(data[3])
            data_point['Pressure'].set_from_value(data[4])
            data_point['WindSpeed'].set_from_value(data[5])
            data_point['WindDirection'].set_from_value(data[6])
            data_point['Sun'].set_from_value(data[7])
            data_point['Rain'].set_from_value(data[8])
            shour, smin = [int(i) for i in data[9].split(':')]
            data_point['SunRainStart'].set_from_value(
                iso.Time(hour=shour, minute=smin, second=0))
            data_point['WindSpeedMax'].set_from_value(data[10])
            try:
                collection.insert_entity(data_point)
            except edm.ConstraintError:
                if bst is None:
                    # This was an ambiguous entry, the first one is in
                    # BST, the second one is in GMT as the clocks have
                    # gone back, so we shift forward again and then
                    # force the zone to GMT
                    tvalue = tvalue.shift_zone(
                        zdirection=1, zhour=1).with_zone(zdirection=0)
                    data_point['TimePoint'].set_from_value(tvalue)
                    logging.info(
                        "Auto-detecting switch to GMT at: %s", str(tvalue))
                    try:
                        collection.insert_entity(data_point)
                    except KeyError:
                        logging.error("Duplicate data point during BST/GMT "
                                      "switching: %s", str(tvalue))
                else:
                    logging.error(
                        "Unexpected duplicate data point: %s", str(tvalue))


def load_data(weather_data, dir_name):
    for file_name in os.listdir(dir_name):
        if not file_name[0:4].isdigit() or file_name[-1] == '~':
            # ignore odd files and some editor backups
            continue
        logging.info(
            "Loading data from file %s", os.path.join(dir_name, file_name))
        year, month, day = [int(np) for np in file_name.split('_')]
        with open(os.path.join(dir_name, file_name), 'r') as f:
            load_data_from_file(weather_data, f, year, month, day)


def load_notes(weather_notes, file_name, weather_data):
    with open(file_name, 'r') as f:
        id = 1
        with weather_notes.open() as collection:
            with weather_data.open() as data:
                while True:
                    line = f.readline()
                    if len(line) == 0:
                        break
                    elif line[0] == '#':
                        continue
                    note_words = line.split()
                    if note_words:
                        note = collection.new_entity()
                        note['ID'].set_from_value(id)
                        start = iso.TimePoint(
                            date=iso.Date.from_str(note_words[0]),
                            time=iso.Time(hour=0, minute=0, second=0))
                        note['StartDate'].set_from_value(start)
                        end = iso.TimePoint(
                            date=iso.Date.from_str(
                                note_words[1]).offset(days=1),
                            time=iso.Time(hour=0, minute=0, second=0))
                        note['EndDate'].set_from_value(end)
                        note['Details'].set_from_value(
                            ' '.join(note_words[2:]))
                        collection.insert_entity(note)
                        # now find the data points that match
                        data.set_filter(
                            core.CommonExpression.from_str(
                                "TimePoint ge datetime'%s' and "
                                "TimePoint lt datetime'%s'" %
                                (to_text(start), to_text(end))))
                        for data_point in data.values():
                            # use values, not itervalues to avoid this bug
                            # in Python 2.7 http://bugs.python.org/issue10513
                            data_point['Note'].bind_entity(note)
                            data.update_entity(data_point)
                        id = id + 1
    with weather_notes.open() as collection:
        collection.set_orderby(
            core.CommonExpression.orderby_from_str('StartDate desc'))
        for e in collection.itervalues():
            with e['DataPoints'].open() as affectedData:
                output(
                    "%s-%s: %s (%i data points affected)" %
                    (to_text(e['StartDate'].value),
                     to_text(e['EndDate'].value),
                     e['Details'].value, len(affectedData)))


def dry_run():
    doc = load_metadata()
    InMemoryEntityContainer(
        doc.root.DataServices['WeatherSchema.CambridgeWeather'])
    weather_data = doc.root.DataServices[
        'WeatherSchema.CambridgeWeather.DataPoints']
    weather_notes = doc.root.DataServices[
        'WeatherSchema.CambridgeWeather.Notes']
    load_data(weather_data, SAMPLE_DIR)
    load_notes(weather_notes, 'weathernotes.txt', weather_data)
    return doc.root.DataServices['WeatherSchema.CambridgeWeather']


def test_model(drop=False):
    """Read and write some key value pairs"""
    doc = load_metadata()
    make_container(doc, drop)
    weather_data = doc.root.DataServices[
        'WeatherSchema.CambridgeWeather.DataPoints']
    weather_notes = doc.root.DataServices[
        'WeatherSchema.CambridgeWeather.Notes']
    if drop:
        load_data(weather_data, SAMPLE_DIR)
        load_notes(weather_notes, 'weathernotes.txt', weather_data)
    with weather_data.open() as collection:
        collection.set_orderby(
            core.CommonExpression.orderby_from_str('WindSpeedMax desc'))
        collection.set_page(30)
        for e in collection.iterpage():
            note = e['Note'].get_entity()
            if e['WindSpeedMax'] and e['Pressure']:
                output(
                    "%s: Pressure %imb, max wind speed %0.1f knots "
                    "(%0.1f mph); %s" % (
                        to_text(e['TimePoint'].value), e['Pressure'].value,
                        e['WindSpeedMax'].value,
                        e['WindSpeedMax'].value * 1.15078,
                        note['Details'] if note is not None else ""))


def run_weather_server(weather_app=None):
    """Starts the web server running"""
    server = make_server('', SERVICE_PORT, weather_app)
    logging.info("HTTP server on port %i running" % SERVICE_PORT)
    # Respond to requests until process is killed
    server.serve_forever()


def run_weather_loader(container=None, max_load=30,
                       not_before="19950630T000000"):
    """Monitors the DTG website for new values

    container
        The EntityContainer containing the weather data.

    max_load
        The maximum number of days worth of data to load.  When setting
        up a new server this determines the rate at which the new server
        will catch up.

    This function is designed to be called once per day, it loads
    historical data from the DTG website one day at a time up to a
    maximum of max_load.  If the data can't be loaded, e.g., because the
    DTG site is not reachable, then the method backs off until it has
    waited for approximately 1 hour after which it gives up.  Therefore,
    you should always set max_load greater than 1 to ensure that the
    method catches up with the data after an outage.

    The earliest date it will load is 30th June 1995, the latest date it
    will load is yesterday."""
    if container is None:
        doc = load_metadata()
        container = make_container(doc)
    client = http.Client()
    weather_data = container['DataPoints']
    dtg = "http://www.cl.cam.ac.uk/research/dtg/weather/daily-text.cgi?%s"
    not_before_point = iso.TimePoint.from_str(not_before)
    with weather_data.open() as collection:
        collection.set_orderby(
            core.CommonExpression.orderby_from_str('TimePoint desc'))
        sleep_interval = 60
        collection.set_page(1)
        last_point = list(collection.iterpage())
        if last_point:
            last_point = last_point[0]['TimePoint'].value
            if last_point < not_before_point:
                last_point = not_before_point
        else:
            last_point = not_before_point
        next_day = last_point.date
        n_loaded = 0
        while n_loaded < max_load:
            today = iso.TimePoint.from_now_utc().date
            if next_day < today:
                # Load in next_day
                logging.info("Requesting data for %s", str(next_day))
                century, year, month, day = next_day.get_calendar_day()
                request = http.ClientRequest(dtg % str(next_day))
                client.process_request(request)
                if request.status == 200:
                    # process this file and move on to the next day
                    f = io.BytesIO(request.res_body)
                    load_data_from_file(
                        weather_data, f, century * 100 + year, month, day)
                    n_loaded += 1
                    next_day = next_day.offset(days=1)
                    if sleep_interval > 10:
                        sleep_interval = sleep_interval // 2
                else:
                    # back off and try again
                    sleep_interval = sleep_interval * 2
            else:
                # we're done for today
                client.idle_cleanup(0)
                break
            client.idle_cleanup(0)
            if sleep_interval > 3600:
                # site might be down, postpone
                break
            time.sleep(sleep_interval)


def main():
    """Executed when we are launched"""
    doc = load_metadata()
    make_container(doc)
    server = ReadOnlyServer(serviceRoot=SERVICE_ROOT)
    server.SetModel(doc)
    t = threading.Thread(
        target=run_weather_server, kwargs={'weather_app': server})
    t.setDaemon(True)
    t.start()
    logging.info("Starting HTTP server on %s" % SERVICE_ROOT)
    t.join()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
