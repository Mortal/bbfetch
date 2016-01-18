import re
import html5lib


NS = {'h': 'http://www.w3.org/1999/xhtml'}


def get_visit_stats(session):
    url = (
        'https://bb.au.dk/webapps/blackboard/content/manageDashboard.jsp' +
        '?course_id=%s' % session.course_id +
        '&showAll=true&sortCol=LastLoginCol&sortDir=D')
    r = session.get(url)
    document = html5lib.parse(r.content, encoding=r.encoding)
    keys, rows = parse_visit_stats(document)
    first = keys.index('FirstNameCol')
    last = keys.index('LastNameCol')
    time = keys.index('LastLoginCol')
    data = [('%s %s' % (r[first], r[last]), r[time]) for r in rows]
    return data


def parse_visit_stats(document):
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
