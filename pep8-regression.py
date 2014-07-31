#! /usr/bin/env python

import os.path
import string
import flake8.main as main

if __name__ == "__main__":
    with open('pep8-done.txt') as f:
        for path in f:
            path = path.strip()
            path = string.join(path.split('/'), os.path.sep)
            main.check_file(path)
