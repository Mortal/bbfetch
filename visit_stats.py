from datatable import fetch_datatable


def get_visit_stats(session):
    url = (
        'https://bb.au.dk/webapps/blackboard/content/manageDashboard.jsp' +
        '?course_id=%s' % session.course_id +
        '&sortCol=LastLoginCol&sortDir=D')
    response, keys, rows = fetch_datatable(session, url)
    for r in list(response.history) + [response]:
        print("%s %s" % (r.status_code, r.url))
    return parse_visit_stats(keys, rows)


def parse_visit_stats(keys, rows):
    first = keys.index('FirstNameCol')
    last = keys.index('LastNameCol')
    time = keys.index('LastLoginCol')
    data = [('%s %s' % (r[first], r[last]), r[time]) for r in rows]
    return data
