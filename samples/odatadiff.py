#! /usr/bin/env python
"""Compares two OData metadata documents"""

import getpass
import logging
import os
import sys
import traceback

from optparse import OptionParser

from pyslet import rfc2396 as uri
from pyslet import rfc2617 as auth
from pyslet.http import client as http
from pyslet.odata2 import csdl as edm
from pyslet.odata2 import metadata as edmx


def fetch_url(url, username=None, password=None):
    mgr = http.Client()
    url = uri.URI.from_octets(url)
    # does url end with $metadata?
    if url.get_file_name() != "$metadata":
        url = uri.URI.from_octets("$metadata").resolve(url)
    if username:
        cred = auth.BasicCredentials()
        cred.userid = username
        cred.password = password
        cred.protectionSpace = url.get_canonical_root()
        mgr.add_credentials(cred)
    doc = edmx.Document(base_uri=url, reqManager=mgr)
    doc.read()
    mgr.close()
    if not doc.root.get_base():
        doc.root.set_base(url)
    return doc


def load_file(filename):
    doc = edmx.Document()
    with open(filename, 'rb') as f:
        doc.read(f)
    return doc


def save_file(doc, filename):
    # check the base of the doc's root element
    with open(filename, 'wb') as f:
        doc.create(f)


def splitlists(old_list, new_list):
    """Compares lists of strings

    Returns three lists representing strings that have stayed the same,
    strings that have been added in *new_list* and finally strings that
    have been removed from *old_list*."""
    snew = set(new_list)
    sold = set(old_list)
    added = []
    removed = []
    common = []
    for newitem in new_list:
        if newitem in sold:
            common.append(newitem)
        else:
            added.append(newitem)
    for olditem in old_list:
        if olditem not in snew:
            removed.append(olditem)
    return common, added, removed


def odatadiff(old_doc, new_doc, backlinks=False):
    if not isinstance(old_doc.root, edmx.Edmx):
        return "File was not a DataServices document - remove it and re-run"
    if not isinstance(new_doc.root, edmx.Edmx):
        return "No DataServices document found - check service URL"
    oldds = old_doc.root.DataServices
    newds = new_doc.root.DataServices
    oldschemas = [x.name for x in oldds.Schema]
    newschemas = [x.name for x in newds.Schema]
    common, added, removed = splitlists(oldschemas, newschemas)
    for name in added:
        logging.info("%s new Schema Namespace", name)
    for name in removed:
        logging.info("%s Schema Namespace removed", name)
    for name in common:
        logging.debug("%s checking Schema...", name)
        schemadiff(oldds[name], newds[name], backlinks=backlinks)
        logging.debug("%s done", name)


def schemadiff(oldds, newds, backlinks=False):
    oldtypes = [x.name for x in oldds.EntityType]
    newtypes = [x.name for x in newds.EntityType]
    common, added, removed = splitlists(oldtypes, newtypes)
    for name in added:
        logging.info("%s.%s new EntityType", oldds.name, name)
    for name in removed:
        logging.info("%s.%s EntityType removed", oldds.name, name)
    for name in common:
        logging.debug("%s.%s checking EntityType...", oldds.name, name)
        entitydiff(oldds[name], newds[name], backlinks=backlinks)
        logging.debug("%s done", name)


def entitydiff(oldet, newet, backlinks=False):
    oldprops = [x.name for x in oldet.Property]
    newprops = [x.name for x in newet.Property]
    common, added, removed = splitlists(oldprops, newprops)
    for name in added:
        logging.info("%s.%s new Property", oldet.name, name)
    for name in removed:
        logging.info("%s.%s Property removed", oldet.name, name)
    for name in common:
        logging.debug("%s.%s checking Property...", oldet.name, name)
        propdiff(oldet[name], newet[name])
        logging.debug("%s done", name)
    oldkeys = [x.name for x in oldet.Key.PropertyRef]
    newkeys = [x.name for x in newet.Key.PropertyRef]
    common, added, removed = splitlists(oldkeys, newkeys)
    for name in added:
        logging.info("%s.%s new Key Property", oldet.name, name)
    for name in removed:
        logging.info("%s.%s Key Property removed", oldet.name, name)
    oldnav = [x.name for x in oldet.NavigationProperty]
    newnav = [x.name for x in newet.NavigationProperty]
    common, added, removed = splitlists(oldnav, newnav)
    for name in added:
        logging.info("%s.%s new NavigationProperty", oldet.name, name)
    for name in removed:
        logging.info("%s.%s NavigationProperty removed", oldet.name, name)
    for name in common:
        logging.debug("%s.%s checking NavigationProperty...", oldet.name, name)
        navdiff(oldet[name], newet[name], backlinks=backlinks)
        logging.debug("%s done", name)


def propdiff(oldp, newp):
    if oldp.type != newp.type:
        logging.info("%s.%s Property type changed from %s to %s",
                     oldp.parent.name, oldp.name, oldp.type, newp.type)
    if oldp.nullable != newp.nullable:
        logging.info("%s.%s Property nullable changed from %s to %s",
                     oldp.parent.name, oldp.name,
                     str(oldp.nullable), str(newp.nullable))


def navdiff(oldnp, newnp, backlinks=False):
    if oldnp.to_end.type != newnp.to_end.type:
        logging.info("%s.%s Navigation target type changed from %s to %s",
                     oldnp.parent.name, oldnp.name,
                     oldnp.to_end.type, newnp.to_end.type)
    if oldnp.to_end.multiplicity != newnp.to_end.multiplicity:
        logging.info("%s.%s Navigation target multiplicity changed "
                     "from %s to %s",
                     oldnp.parent.name, oldnp.name,
                     edm.multiplicity_to_str(oldnp.to_end.multiplicity),
                     edm.multiplicity_to_str(newnp.to_end.multiplicity))
    if backlinks:
        old_backname = new_backname = None
        if oldnp.backLink is not None:
            old_backname = oldnp.backLink.name
        if newnp.backLink is not None:
            new_backname = oldnp.backLink.name
        if old_backname != new_backname:
            logging.info("%s.%s Navigation back link changed from %s to %s",
                         oldnp.parent.name, oldnp.name,
                         old_backname, new_backname)


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-s", "--service", dest="url",
                      help="fetch metadata from URL for diff")
    parser.add_option("-u", "--user", dest="user",
                      help="user name for basic auth credentials")
    parser.add_option("--password", dest="password",
                      help="password for basic auth credentials")
    parser.add_option("-v", action="count", dest="logging",
                      default=0, help="increase verbosity of output")
    parser.add_option("-b", "--backlinks", action="store_true",
                      dest="backlinks", default=False,
                      help="check navigation backlinks")
    (options, args) = parser.parse_args()
    if options.logging > 3:
        level = 3
    else:
        level = options.logging
    logging.basicConfig(level=[logging.ERROR, logging.WARN, logging.INFO,
                        logging.DEBUG][level])
    if len(args) != 1:
        sys.exit("Usage: odatadiff.py [metadata.xml]")
    if options.user is not None:
        username = options.user
        if options.password is not None:
            password = options.password
        else:
            password = getpass.getpass()
    else:
        username = password = None
    try:
        if os.path.exists(args[0]):
            # called with an existing file, load it
            old_doc = load_file(args[0])
            if options.url is None:
                # use the base of old_doc
                url = old_doc.root.get_base()
                if url is None:
                    sys.exit("xml:base undefined, try again with -s SERVICE")
                new_doc = fetch_url(url, username, password)
            else:
                new_doc = fetch_url(options.url, username, password)
            sys.exit(odatadiff(old_doc, new_doc,
                               backlinks=options.backlinks))
        else:
            # file does not exist, just fetch the metadata
            if options.url is None:
                sys.exit("%s does not exist, use --s URL "
                         "to fetch metadata for the first time" % args[0])
            old_doc = fetch_url(options.url, username, password)
            save_file(old_doc, args[0])
    except Exception as e:
        logging.debug(
            '\n'.join(traceback.format_exception(*sys.exc_info(), limit=10)))
        logging.error(e)
