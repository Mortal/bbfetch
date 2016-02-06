import blackboard
from datatable import fetch_datatable


NS = {'h': 'http://www.w3.org/1999/xhtml'}


def strip_prefix(s, prefix):
    if s.startswith(prefix):
        return s[len(prefix):]
    else:
        raise ValueError("%r does not start with %r" % (s, prefix))


def get_groups(session):
    url = ('https://bb.au.dk/webapps/bb-group-mgmt-LEARN/execute/' +
           'groupInventoryList?course_id=%s' % session.course_id +
           '&toggleType=users&chkAllRoles=on')

    def extract(key, cell, d):
        if key != 'Groups':
            return d
        groups = cell.findall(
            './/h:a[@class="userGroupNameListItemRemove"]', NS)
        res = []
        for g in groups:
            name = ' '.join(''.join(g.itertext()).split())
            i = g.get('id')
            res.append((name, strip_prefix(i, 'rmv_')))
        return res

    response, keys, rows = fetch_datatable(
        session, url, extract=extract, table_id='userGroupList_datatable')
    username = keys.index('userorgroupname')
    first_name = keys.index('firstname')
    last_name = keys.index('lastname')
    role = keys.index('Role')
    groups = keys.index('Groups')
    users = []
    for row in rows:
        users.append(dict(
            username=row[username],
            first_name=row[first_name],
            last_name=row[last_name],
            role=row[role],
            groups=row[groups],
        ))
    return users


def print_groups(session):
    users = get_groups(session)
    for user in users:
        print("%s %s (%s, %s) is in %s" %
              (user['first_name'], user['last_name'],
               user['username'], user['role'], user['groups']))


if __name__ == "__main__":
    blackboard.wrapper(print_groups)
