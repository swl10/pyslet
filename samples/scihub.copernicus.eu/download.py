#! /usr/bin/env python

import getpass
import logging
import sys

from optparse import OptionParser

from pyslet.http.auth import BasicCredentials
from pyslet.odata2.client import Client
from pyslet.py2 import output
from pyslet.rfc2396 import URI


# The URL of the OData service
SERVICE = 'https://scihub.copernicus.eu/apihub/odata/v1'

# The file name to read/write the site certificate to
CERTIFICATE = 'scihub.copernicus.eu.crt'

MAX_LIST = 100

# Example product ids:
# a large one: e9b57d8d-7675-433c-9733-d3ad0996576d
# a small-ish one: 8bf64ff9-f310-4027-b31f-8e95dd9bbf82


def get_cert():
    c = Client()
    url = URI.from_octets(SERVICE)
    output = c.get_server_certificate_chain(url)
    with open(CERTIFICATE, 'wb') as f:
        f.write(output)


def main(user, password, product_list):
    metadata = URI.from_path('metadata.xml')
    service = URI.from_path('scihub.copernicus.eu.xml')
    credentials = BasicCredentials()
    credentials.userid = user
    credentials.password = password
    credentials.protectionSpace = URI.from_octets(SERVICE).get_canonical_root()
    # the full link of odata is https://scihub.copernicus.eu/apihub/odata/v1
    # this is for the authentication
    c = Client(ca_certs=CERTIFICATE)
    c.add_credentials(credentials)
    c.load_service(service_root=service, metadata=metadata)
    with c.feeds['Products'].open() as products:
        for pid in product_list:
            p = products[pid]
            name = p['Name'].value
            size = p['ContentLength'].value
            output("Product: %s [%i]\n" % (name, size))
            with open('%s.zip' % name, 'wb') as f:
                products.read_stream(p.key(), f)
        if not product_list:
            i = 0
            for p in products.itervalues():
                name = p['Name'].value
                type = p['ContentType'].value
                size = p['ContentLength'].value
                output("%s\n" % str(p.get_location()))
                output("    %s %s[%i]\n" % (name, type, size))
                i += 1
                if i > MAX_LIST:
                    break


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-u", "--user", dest="user",
                      help="user name for basic auth credentials")
    parser.add_option("-p", "--password", dest="password",
                      help="password for basic auth credentials")
    parser.add_option("-v", action="count", dest="logging",
                      default=0, help="increase verbosity of output up to 3x")
    parser.add_option("-c", "--cert", action="store_true",
                      default=False, dest="cert",
                      help="download and trust site certificate")
    (options, args) = parser.parse_args()
    if options.logging > 3:
        level = 3
    else:
        level = options.logging
    logging.basicConfig(level=[logging.ERROR, logging.WARN, logging.INFO,
                               logging.DEBUG][level])
    if options.user is None:
        sys.exit("Usage: scihub.py -u <userid> [--password <password>] "
                 "<product> [, <product>]* ")
    username = options.user
    if options.password is not None:
        password = options.password
    else:
        password = getpass.getpass()
    if options.cert:
        get_cert()
    main(username, password, args)
