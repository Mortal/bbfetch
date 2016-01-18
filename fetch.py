import os
import re
import json
import getpass
import keyring
import logging
import argparse
import html5lib
import requests
import requests.cookies
# import xml.etree.ElementTree
from six.moves.urllib.parse import urlparse, parse_qs, urlencode
from six.moves.http_cookiejar import LWPCookieJar


logger = logging.getLogger('bblinks')

NS = {'h': 'http://www.w3.org/1999/xhtml'}


def configure_logging(quiet):
    """Configure the Python logging module."""
    handlers = []
    handlers.append(logging.FileHandler('fetch.log', 'a'))
    if not quiet:
        handlers.append(logging.StreamHandler(None))
    fmt = '[%(asctime)s %(levelname)s] %(message)s'
    datefmt = None
    formatter = logging.Formatter(fmt, datefmt, '%')
    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


def wayf_login(session, response, auth_data):
    """Login to WAYF.

    Parameters
    ----------
    session : requests.Session
        The session where we want to log in
    response : requests.Response
        Login page (with username/password form)
    auth_data : callable () -> dict(username=..., password=...)
        Callable returning a dict with the authentication data
    """

    logger.info("Sending login details to WAYF")
    response = session.post(response.url, auth_data)
    logger.debug("WAYF login -> %s", response.url)
    logger.debug("WAYF response %s", response.status_code)
    with open('wayftmp.html', 'wb') as fp:
        fp.write(response.content)

    response = post_hidden_form(session, response)
    logger.debug("Hidden form 1 -> %s %s", response.status_code, response.url)
    response = post_hidden_form(session, response)
    logger.debug("Hidden form 2 -> %s %s", response.status_code, response.url)
    return response


def post_hidden_form(session, response):
    """Send POST request to form with only hidden fields.

    Parameters
    ----------
    session : requests.Session
        The session where we want to submit the form
    response : requests.Response
        Page containing form with only hidden fields
    """

    document = html5lib.parse(response.content, encoding=response.encoding)
    form = document.find('.//h:form', NS)
    url = form.get('action')
    inputs = form.findall('.//h:input[@name]', NS)
    logger.debug("Response page form has %d inputs", len(inputs))
    assert len(inputs) > 0
    post_data = {
        i.get('name'): i.get('value')
        for i in inputs
    }
    response = session.post(url, post_data)

    return response


def make_authenticator(username):
    """Make a get_auth callable.

    The callable returns the given username and a password read with the
    keyring module. If no password is stored, it is prompted at the command
    line using the getpass module, and stored with keyring.

    If username is None, prompts the user for a username before getting the
    password.
    """

    data = dict(username=username, password=None)

    def get_auth():
        if data['password'] is None:
            if data['username'] is None:
                data['username'] = input("WAYF username: ")
            data['password'] = keyring.get_password(
                "fetch.py WAYF", data['username'])
            if data['password'] is None:
                print("Please enter password for %s to store in keyring." %
                      data['username'])
                data['password'] = getpass.getpass()
                keyring.set_password(
                    "fetch.py WAYF", data['username'], data['password'])

        return data

    return get_auth


def follow_html_redirect(session, response):
    """Repeatedly follow HTML redirects in the page.

    If the given response has no HTML redirect, return it unaltered.
    Otherwise, return a new response by following the redirects in the page.
    """

    js_redirect_pattern = (
        r'(?:<!--)?\s*' +
        r'document\.location\.replace\(\'' +
        r'(?P<url>(?:\\.|[^\'])+)' +
        r'\'\);\s*' +
        r'(?:(?://)?-->)?\s*$')
    real_login_url = (
        'https://bb.au.dk/webapps/' +
        'bb-auth-provider-shibboleth-BBLEARN/execute/shibbolethLogin')

    while True:
        document = html5lib.parse(response.content, encoding=response.encoding)
        scripts = document.findall('.//h:script', NS)

        next_url = None
        for s in scripts:
            t = ''.join(s.itertext())
            mo = re.match(js_redirect_pattern, t)
            if mo:
                logger.debug("Detected JavaScript redirect")
                next_url = mo.group('url')
                break
        if next_url is not None:
            o = urlparse(next_url)
            p = o.netloc + o.path
            if p == 'bb.au.dk/webapps/login/':
                qs = parse_qs(o.query)
                new_qs = urlencode(
                    dict(returnUrl=qs['new_loc'][0],
                         authProviderId='_102_1'))
                next_url = '%s?%s' % (real_login_url, new_qs)
                logger.debug("Changing redirect to %r", next_url)
            response = session.get(next_url)
            continue
        break
    return response


def autologin(session, response, get_auth):
    """Automatically log in if necessary.

    If the given response is not for a login form, just follow HTML redirects
    and return the response.
    Otherwise, log in using wayf_login and get_auth.
    """

    response = follow_html_redirect(session, response)
    o = urlparse(response.url)
    if o.netloc == 'wayf.au.dk':
        response = wayf_login(session, response, get_auth())
    return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--quiet', action='store_true')
    parser.add_argument('--username', '-u')
    parser.add_argument('--course', default='_43290_1')
    parser.add_argument('--cookiejar', default='cookies.txt')
    args = parser.parse_args()
    configure_logging(quiet=args.quiet)

    get_auth = make_authenticator(args.username)

    cookies = LWPCookieJar(args.cookiejar)
    try:
        cookies.load(ignore_discard=True)
    except FileNotFoundError:
        pass

    session = requests.Session()
    requests.cookies.merge_cookies(session.cookies, cookies)
    course_id = args.course

    table = get_visit_stats(session, course_id, get_auth)
    with open('visit_stats.txt', 'a') as fp:
        for name, time in table:
            fp.write('%s %s\n' % (time, name))

    requests.cookies.merge_cookies(cookies, session.cookies)
    cookies.save(ignore_discard=True)


def get_visit_stats(session, course_id, get_auth):
    url = (
        'https://bb.au.dk/webapps/blackboard/content/manageDashboard.jsp?' +
        'course_id=%s&showAll=true&sortCol=LastLoginCol&sortDir=D' % course_id)
    r = autologin(session, session.get(url), get_auth)
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


if __name__ == "__main__":
    main()
