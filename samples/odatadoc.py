#! /usr/bin/env python
"""Generats an HTML document from an OData metadata document"""


import sys
import string
import logging
from optparse import OptionParser
import getpass

import pyslet.iso8601 as iso
import pyslet.rfc2396 as uri
import pyslet.rfc2617 as auth
import pyslet.http.client as http
import pyslet.odata2.csdl as edm
import pyslet.odata2.metadata as edmx
import pyslet.xml.structures as xml


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


def write_doc(doc, template, out):
    if not isinstance(doc.root, edmx.Edmx):
        return "Source was not a DataServices document"
    with open(template, 'rb') as f:
        data = f.read()
    params = {
        'namespace': "",
        'summary': "Schema Documentation",
        'description': '',
        'entity_list': "<p>Not supported in this version</p>",
        'tables': "<p>Not supported in this version</p>",
        'index': "<p>Not supported in this version</p>",
        'date': str(iso.TimePoint.from_now())
    }
    ds = doc.root.DataServices
    if len(ds.Schema) != 1:
        logging.warn("Documenting the first Schema tag only")
    params['namespace'] = xml.escape_char_data7(ds.Schema[0].name)
    sdoc = ds.Schema[0].Documentation
    if sdoc is not None:
        if sdoc.Summary is not None:
            params['summary'] = "%s" % xml.escape_char_data7(
                sdoc.Summary.get_value())
        if sdoc.LongDescription is not None:
            params['description'] = "%s" % xml.escape_char_data7(
                sdoc.LongDescription.get_value())
    tables = []
    dl_items = []
    index_items = []
    for ec in ds.Schema[0].EntityContainer:
        if not ec.is_default_entity_container():
            logging.warn("Ignoring non-default EntityContainer: %s", ec.name)
            continue
        es_list = []
        for es in ec.EntitySet:
            es_list.append(es.name)
        es_list.sort()
        for esn in es_list:
            es = ec[esn]
            dl_items.append('<dt><a href=%s>%s</a></dt>' %
                            (xml.escape_char_data7("#" + es.name, True),
                             xml.escape_char_data7(es.name)))
            index_items.append((es.name, es.name, "entity set"))
            if es.Documentation is not None:
                if es.Documentation.Summary is not None:
                    dl_items.append('<dd>%s</dd>' % xml.escape_char_data7(
                        es.Documentation.Summary.get_value()))
            tables.append(es_table(es, index_items))
    params['entity_list'] = string.join(dl_items, '\n')
    params['tables'] = string.join(tables, "\n\n")
    index_items.sort()
    index_dl = []
    cname = ''
    for name, link, note in index_items:
        if name != cname:
            index_dl.append('<dt>%s</dt>' % xml.escape_char_data7(name))
            cname = name
        index_dl.append('<dd><a href=%s>%s</a></dd>' %
                        (xml.escape_char_data7("#" + link, True),
                         xml.escape_char_data7(note)))
    params['index'] = string.join(index_dl, '\n')
    out.write(data % params)
    return 0


def es_table(es, index_items):
    result = """<h3><a id=%(anchor)s>%(title)s</a></h3>
%(summary)s
%(description)s
<table class="typedef">
    <thead>
        <th>Name</th>
        <th>Type</th>
        <th>Multiplicity</th>
        <th>Description</th>
        <th>Notes</th>
    </thead>
    <tbody>%(body)s</tbody>
</table>"""
    params = {
        'anchor': xml.escape_char_data7(es.name, True),
        'title': '',
        'summary': '',
        'description': '',
        'body': ''}
    tb = []
    type = es.entityType
    if type.has_stream():
        params['title'] = (xml.escape_char_data7(es.name) +
                           " <em>(Media Resource)</em>")
    else:
        params['title'] = xml.escape_char_data7(es.name)
    typedoc = type.Documentation
    if typedoc is not None:
        if typedoc.Summary is not None:
            params['summary'] = (
                '<p class="summary">%s</p>' %
                xml.escape_char_data7(typedoc.Summary.get_value()))
        if typedoc.LongDescription is not None:
            params['description'] = (
                '<p class="description">%s</p>' %
                xml.escape_char_data7(typedoc.LongDescription.get_value()))
    for p in type.Property:
        if p.name in es.keys:
            tr = ['<tr class="key">']
        else:
            tr = ["<tr>"]
        link = '%s.%s' % (es.name, p.name)
        tr.append("<td><a id=%s>%s</a></td>" % (
            xml.EscapeCharData(link, True),
            xml.escape_char_data7(p.name)))
        index_items.append((p.name, link, "property of %s" % es.name))
        tr.append("<td>%s</td>" % xml.escape_char_data7(p.type))
        tr.append("<td>%s</td>" % ("Optional" if p.nullable else "Required"))
        summary = description = ""
        if p.Documentation is not None:
            if p.Documentation.Summary:
                summary = p.Documentation.Summary.get_value()
            if p.Documentation.LongDescription:
                description = p.Documentation.LongDescription.get_value()
        tr.append("<td>%s</td>" % xml.escape_char_data7(summary))
        tr.append("<td>%s</td>" % xml.escape_char_data7(description))
        tr.append("</tr>")
        tb.append(string.join(tr, ''))
    for np in type.NavigationProperty:
        tr = ['<tr class="navigation">']
        link = '%s.%s' % (es.name, np.name)
        tr.append("<td><a id=%s>%s</a></td>" % (
            xml.EscapeCharData(link, True),
            xml.escape_char_data7(np.name)))
        index_items.append((np.name, link, "navigation property of %s" %
                            es.name))
        tr.append("<td><em>%s</em></td>" %
                  xml.escape_char_data7(es.get_target(np.name).name))
        tr.append("<td>%s</td>" %
                  edm.multiplicity_to_str(np.to_end.multiplicity))
        summary = description = ""
        if np.Documentation is not None:
            if np.Documentation.Summary:
                summary = np.Documentation.Summary.get_value()
            if np.Documentation.LongDescription:
                description = np.Documentation.LongDescription.get_value()
        tr.append("<td>%s</td>" % xml.escape_char_data7(summary))
        tr.append("<td>%s</td>" % xml.escape_char_data7(description))
        tr.append("</tr>")
        tb.append(string.join(tr, ''))

    params['body'] = string.join(tb, '\n')
    return result % params


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-s", "--service", dest="url",
                      help="fetch metadata from URL for diff")
    parser.add_option("-u", "--user", dest="user",
                      help="user name for basic auth credentials")
    parser.add_option("--password", dest="password",
                      help="password for basic auth credentials")
    parser.add_option("-t", "--template", dest="template",
                      default="odatadoc.tmpl",
                      help="path to the template file")
    parser.add_option("-v", action="count", dest="logging",
                      default=0, help="increase verbosity of output")
    (options, args) = parser.parse_args()
    if options.logging > 3:
        level = 3
    else:
        level = options.logging
    logging.basicConfig(
        level=[logging.ERROR, logging.WARN, logging.INFO,
               logging.DEBUG][level])
    if len(args) != 1 and options.url is None:
        sys.exit("Usage: odatadoc.py [-s URL] | [metadata]")
    if options.user is not None:
        username = options.user
        if options.password is not None:
            password = options.password
        else:
            password = getpass.getpass()
    else:
        username = password = None
    if not args:
        # load metadata from the URL
        doc = fetch_url(options.url, username, password)
    else:
        doc = load_file(args[0])
    sys.exit(write_doc(doc, options.template, sys.stdout))
