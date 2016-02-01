import re
import csv
import html5lib
from requests.compat import urljoin

import blackboard


NS = {'h': 'http://www.w3.org/1999/xhtml'}


def fetch_datatable(session, url, filename=None):
    if filename is not None:
        with open(filename, 'w') as fp:
            data = list(dump_iter_datatable(session, url, fp))
    else:
        data = list(iter_datatable(session, url))
    keys = data[0]
    rows = data[1:-1]
    response = data[-1]
    return response, keys, rows


def dump_iter_datatable(session, url, fp):
    c = csv.writer(fp, dialect='excel-tab')
    for r in iter_datatable(session, url):
        if isinstance(r, list):
            c.writerow(r)
            fp.flush()
        yield r


def iter_datatable(session, url):
    url += '&numResults=1000&startIndex=0'
    l = blackboard.slowlog()
    response = session.get(url)
    l("Fetching datatable page 1 took %.4f s")
    for r in list(response.history) + [response]:
        print("%s %s" % (r.status_code, r.url))
    history = list(response.history) + [response]
    document = html5lib.parse(response.content, encoding=response.encoding)
    keys, rows = parse_datatable(document)
    yield keys
    yield from rows
    next_id = 'listContainer_nextpage_top'
    next_o = document.find('.//h:a[@id="%s"]' % next_id, NS)
    page_number = 1
    while next_o:
        page_number += 1
        url = urljoin(response.url, next_o.get('href'))
        l = blackboard.slowlog()
        response = session.get(url)
        l("Fetching datatable page %d took %.4f s", page_number)
        history += list(response.history) + [response]
        document = html5lib.parse(response.content, encoding=response.encoding)
        keys_, rows = parse_datatable(document)
        if keys != keys_:
            raise ValueError(
                "Page %d keys (%r) do not match page 1 keys (%r)" %
                (page_number, keys_, keys))
        next_o = document.find('.//h:a[@id="%s"]' % next_id, NS)
        yield from rows
    response.history = history[:-1]
    yield response


def parse_datatable(document):
    table = document.find('.//h:table[@id="listContainer_datatable"]', NS)
    header = table.find('./h:thead', NS)
    keys = []
    for h in header[0]:
        text = ' '.join(''.join(h.itertext()).split())
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
        for cell in row:
            r.append(' '.join(''.join(cell.itertext()).split()))
    return keys, res
