#! /usr/bin/env python

import logging

from mtnoticeboard import MTNoticeBoard

import noticeboard_config as config

logging.basicConfig(filename=config.LOG_FILE, level=config.LOG_LEVEL)
MTNoticeBoard.settings_file = config.settings_path
MTNoticeBoard.setup()
application = MTNoticeBoard()
