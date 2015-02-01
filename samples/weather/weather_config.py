#! /usr/bin/env python

import logging
import os.path

# The service root of the weather service
SERVICE_ROOT = "http://localhost:8080/"

# The home directory for data files
HOME_DIR = os.path.split(os.path.abspath(__file__))[0]

# The file location to use for logging
LOG_FILE = None

# The logging level
LOG_LEVEL = logging.INFO

# The database connection details
DB_HOST = 'localhost'
DB_NAME = 'weather'
DB_USER = 'weather'
# DB_PASSWORD = 'password'
