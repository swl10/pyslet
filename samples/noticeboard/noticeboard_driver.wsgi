#! /usr/bin/env python

import logging

from mtnoticeboard import MTNoticeBoard

import noticeboard_config as config

logging.basicConfig(filename=config.LOG_FILE, level=config.LOG_LEVEL)
MTNoticeBoard.settings_file = config.SETTINGS.FILE
MTNoticeBoard.setup()
application = MTNoticeBoard()
