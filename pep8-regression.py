#! /usr/bin/env python

import logging
import os
import os.path
import flake8.main as main

logging.basicConfig(level=logging.ERROR)

if __name__ == "__main__":
    with open('pep8-done.txt') as f:
        for path in f:
            path = path.strip()
            path = os.path.sep.join(path.split('/'))
            if os.path.isfile(path):
                logging.info('Checking file... %s', path)
                main.check_file(path)
            else:
                logging.info('Walking %s', path)
                for dirpath, dirnames, filenames in os.walk(path):
                    # if the file extension is .py, check it!
                    for fname in filenames:
                        fpath = os.path.join(dirpath, fname)
                        root, ext = os.path.splitext(fname)
                        if ext.lower() == ".py":
                            logging.info('Checking file... %s', fpath)
                            main.check_file(fpath)
