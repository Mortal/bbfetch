import re
import csv
import html5lib
from requests.compat import urljoin

import bbfetch
from bbfetch.elementtext import element_text_content


NS = {'h': 'http://www.w3.org/1999/xhtml'}


def fetch_datatable(session, url, filename=None, **kwargs):
    if filename is not None:
        with open(filename, 'w') as fp:
            data = list(dump_iter_datatable(session, url, fp, **kwargs))
    else:
        data = list(iter_datatable(session, url, **kwargs))
    keys = data[0]
    rows = data[1:-1]
    response = data[-1]
    return response, keys, rows


def dump_iter_datatable(session, url, fp, **kwargs):
    c = csv.writer(fp, dialect='excel-tab')
    for r in iter_datatable(session, url, **kwargs):
        if isinstance(r, list):
            c.writerow(r)
            fp.flush()
        yield r


def iter_datatable(session, url, **kwargs):
    url += '&numResults=1000&startIndex=0'
    l = bbfetch.slowlog()
    response = session.get(url)
    if kwargs.pop('edit_mode', False):
        response = session.ensure_edit_mode(response)
    history = list(response.history) + [response]
    document = html5lib.parse(response.content, transport_encoding=response.encoding)
    keys, rows = parse_datatable(response, document, **kwargs)
    yield keys
    yield from rows
    next_id = 'listContainer_nextpage_top'
    next_o = document.find('.//h:a[@id="%s"]' % next_id, NS)
    if next_o is None:
        l("Fetching datatable took %.1f s")
    else:
        l("Fetching datatable page 1 took %.1f s")
    page_number = 1
    while next_o:
        page_number += 1
        url = urljoin(response.url, next_o.get('href'))
        l = bbfetch.slowlog()
        response = session.get(url)
        l("Fetching datatable page %d took %.4f s", page_number)
        history += list(response.history) + [response]
        document = html5lib.parse(response.content, transport_encoding=response.encoding)
        keys_, rows = parse_datatable(response, document, **kwargs)
        if keys != keys_:
            raise ValueError(
                "Page %d keys (%r) do not match page 1 keys (%r)" %
                (page_number, keys_, keys))
        next_o = document.find('.//h:a[@id="%s"]' % next_id, NS)
        yield from rows
    response.history = history[:-1]
    yield response


def parse_datatable(response, document, extract=None, table_id=None):
    if table_id is None:
        table_id = 'listContainer_datatable'
    table = document.find('.//h:table[@id="%s"]' % table_id, NS)
    if table is None:
        raise bbfetch.ParserError(
            "No table with id %r" % (table_id,), response)
    header = table.find('./h:thead', NS)
    keys = []
    for h in header[0]:
        text = element_text_content(h)
        sortheader = h.find('./h:a[@class="sortheader"]', NS)
        if sortheader:
            mo = re.search(r'sortCol=([^&]*)', sortheader.get('href'))
            if mo:
                text = mo.group(1)
        keys.append(text)
    rows = table.findall('./h:tbody/h:tr', NS)
    res = []
    for row in rows:
        r = []
        res.append(r)
        for key, cell in zip(keys, row):
            v = element_text_content(cell)
            if extract is not None:
                v = extract(key, cell, v)
            r.append(v)
    return keys, res
