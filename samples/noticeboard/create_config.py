#! /usr/bin/env python

import base64
import json
import os
import sys

if __name__ == '__main__':
    input = sys.argv[1]
    output = sys.argv[2]
    settings = json.load(input)
    password = base64.encodestring(os.urandom(16)).strip("\r\n=")
    settings['WSGIDataApp']['dbpassword'] = password
    with open(output, 'wb') as f:
        f.write(json.dumps(settings).encode('utf-8'))
