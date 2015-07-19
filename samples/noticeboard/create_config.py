#! /usr/bin/env python

import base64
import json
import os
import sys

import pyslet.rfc2396 as uri
import pyselt.http.client as http

if __name__ == '__main__':
    input = sys.argv[1]
    output = sys.argv[2]
    with open(input, 'rb') as f:
        settings = json.load(f)
    password = base64.encodestring(os.urandom(16)).strip("\r\n=")
    settings['WSGIDataApp']['dbpassword'] = password
    with open(output, 'wb') as f:
        f.write(json.dumps(settings).encode('utf-8'))
    # now get the certificate chain
    with open(settings['MultiTenantTPApp']['google_certs'], 'wb') as f:
        f.write(http.Client.get_server_certificate_chain(
                uri.URI.from_octets('https://accounts.google.com')))
