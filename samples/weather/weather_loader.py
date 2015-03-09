#! /usr/bin/env python

import logging

import weather
import weather_config as config

logging.basicConfig(filename=config.LOG_FILE, level=config.LOG_LEVEL)
doc = weather.load_metadata()
weather.make_mysql_container(
    doc, host=config.DB_HOST, database=config.DB_USER,
    user=config.DB_USER, password=config.DB_PASSWORD)
containerDef = doc.root.DataServices['WeatherSchema.CambridgeWeather']

if __name__ == "__main__":
    weather.run_weather_loader(containerDef)
