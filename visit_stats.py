import html5lib

from datatable import parse_datatable


NS = {'h': 'http://www.w3.org/1999/xhtml'}


def get_visit_stats(session):
    url = (
        'https://bb.au.dk/webapps/blackboard/content/manageDashboard.jsp' +
        '?course_id=%s' % session.course_id +
        '&showAll=true&sortCol=LastLoginCol&sortDir=D')
    r = session.get(url)
    document = html5lib.parse(r.content, encoding=r.encoding)
    keys, rows = parse_datatable(document)
    first = keys.index('FirstNameCol')
    last = keys.index('LastNameCol')
    time = keys.index('LastLoginCol')
    data = [('%s %s' % (r[first], r[last]), r[time]) for r in rows]
    return data
