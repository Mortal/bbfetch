import html5lib
import blackboard

from datatable import fetch_datatable


NS = {'h': 'http://www.w3.org/1999/xhtml'}


def get_all_users(session):
    url = (
        'https://bb.au.dk/webapps/blackboard/execute/userManager' +
        '?context=userPicker&course_id=_13158_1&enrollTypeString=UnEnrolled' +
        '&sortCol=userFirstName&sortDir=ASCENDING' +
        '&userInfoSearchKeyString=UserName' +
        '&userInfoSearchOperatorString=Contains&userInfoSearchText=a')
    response, keys, rows = fetch_datatable(session, url, 'get_all_users.csv')
    with open('all_users.html', 'wb') as fp:
        fp.write(url.encode('ascii') + b'\n')
        for r in list(response.history) + [response]:
            fp.write(('%s %s\n' % (r.status_code, r.url)).encode('ascii'))
        fp.write(response.content)
    return parse_all_users(keys, rows)


def parse_all_users(keys, rows):
    first_name = keys.index('userFirstName')
    last_name = keys.index('userLastName')
    username = keys.index('username')
    email_address = keys.index('userEmailAddress')
    return [
        {'first': row[first_name],
         'last': row[last_name],
         'id': row[username],
         'email': row[email_address]}
        for row in rows
    ]
