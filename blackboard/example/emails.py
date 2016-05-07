import re

import blackboard
from blackboard.datatable import fetch_datatable
from blackboard.backend import fetch_groups


def fetch_users(session):
    url = ('https://bb.au.dk/webapps/blackboard/execute/userManager' +
           '?course_id=%s' % session.course_id)
    response, keys, rows = fetch_datatable(session, url)
    try:
        return parse_users(keys, rows)
    except ValueError as exn:
        raise blackboard.ParserError(exn.args[0], response)


def extract_username(s):
    if s.startswith('Access the profile card for user:'):
        raise ValueError("element_text_content did not strip prefix")
    if s.endswith('Remove Users from Course'):
        raise ValueError("element_text_content did not strip suffix: %r" % (s,))
    return s


def parse_users(keys, rows):
    first = keys.index('userFirstName')
    last = keys.index('userLastName')
    email = keys.index('userEmailAddress')
    username = keys.index('username')
    return {
        extract_username(r[username]):
        dict(first_name=r[first],
             last_name=r[last],
             email=r[email],
             username=extract_username(r[username]))
        for r in rows
    }


def fetch_groups_and_emails(session):
    emails = fetch_users(session)
    groups = fetch_groups(session)
    if emails.keys() != groups.keys():
        print("In Users but not Groups: %r" % (set(emails.keys()) - set(groups.keys())))
        print("In Groups but not Users: %r" % (set(groups.keys()) - set(emails.keys())))
        raise Exception("Different username sets")
    for username in emails.keys():
        groups[username].update(emails[username])
    return groups


def print_groups_and_emails(session):
    by_group = {}
    users = fetch_groups_and_emails(session)
    for user in users.values():
        groups = [name for name, group_id in user['groups']]
        for group in groups or ['no group']:
            by_group.setdefault(group, []).append(user)
    for group_name in sorted(by_group.keys()):
        print("%s:\n" % group_name)
        group_users = by_group[group_name]
        group_users = sorted(group_users, key=lambda u: (u['role'], u['first_name'], u['last_name']))
        for user in group_users:
            print("\"%s %s\" <%s>," % (user['first_name'], user['last_name'], user['email']))
        print('')


if __name__ == "__main__":
    blackboard.wrapper(print_groups_and_emails)
