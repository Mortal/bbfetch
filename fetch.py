import re
import getpass
import keyring
import logging
import argparse
import html5lib
import requests
import requests.cookies
from xml.etree.ElementTree import ElementTree
from six.moves.urllib.parse import urlparse, parse_qs, urlencode
from six.moves.http_cookiejar import LWPCookieJar
from six import BytesIO

import html2text


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


class BlackBoardSession:
    def __init__(self, cookiejar, username, course_id):
        self.cookiejar_filename = cookiejar
        self.username = username
        self.course_id = course_id

        self.password = None
        self.cookies = LWPCookieJar(cookiejar)
        self.session = requests.Session()
        self.load_cookies()

    def load_cookies(self):
        try:
            self.cookies.load(ignore_discard=True)
        except FileNotFoundError:
            pass
        requests.cookies.merge_cookies(self.session.cookies, self.cookies)

    def save_cookies(self):
        requests.cookies.merge_cookies(self.cookies, self.session.cookies)
        self.cookies.save(ignore_discard=True)

    def get_auth(self):
        if self.password is None:
            if self.username is None:
                self.username = input("WAYF username: ")
            self.password = keyring.get_password(
                "fetch.py WAYF", self.username)
            if self.password is None:
                print("Please enter password for %s to store in keyring." %
                      self.username)
                self.password = getpass.getpass()
                keyring.set_password(
                    "fetch.py WAYF", self.username, self.password)

        return dict(username=self.username, password=self.password)

    def wayf_login(self, response):
        """Login to WAYF.

        Parameters
        ----------
        response : requests.Response
            Login page (with username/password form)
        """

        logger.info("Sending login details to WAYF")
        response = self.session.post(response.url, self.get_auth())
        logger.debug("WAYF login -> %s", response.url)
        logger.debug("WAYF response %s", response.status_code)
        with open('wayftmp.html', 'wb') as fp:
            fp.write(response.content)

        response = self.post_hidden_form(response)
        logger.debug("Hidden form 1 -> %s %s",
                     response.status_code, response.url)
        response = self.post_hidden_form(response)
        logger.debug("Hidden form 2 -> %s %s",
                     response.status_code, response.url)
        return response

    def post_hidden_form(self, response):
        """Send POST request to form with only hidden fields.

        Parameters
        ----------
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
        response = self.session.post(url, post_data)

        return response

    def follow_html_redirect(self, response):
        """Repeatedly follow HTML redirects in the page.

        If the given response has no HTML redirect, return it unaltered.
        Otherwise, return a new response by following the redirects.
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
            document = html5lib.parse(
                response.content, encoding=response.encoding)
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
                response = self.session.get(next_url)
                continue
            break
        return response

    def autologin(self, response):
        """Automatically log in if necessary.

        If the given response is not for a login form,
        just follow HTML redirects and return the response.
        Otherwise, log in using wayf_login and get_auth.
        """

        response = self.follow_html_redirect(response)
        o = urlparse(response.url)
        if o.netloc == 'wayf.au.dk':
            response = self.wayf_login(response)
        return response

    def get(self, url):
        return self.autologin(self.session.get(url))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--quiet', action='store_true')
    parser.add_argument('--username', '-u')
    parser.add_argument('--course', default='_43290_1')
    parser.add_argument('--cookiejar', default='cookies.txt')
    args = parser.parse_args()
    configure_logging(quiet=args.quiet)

    session = BlackBoardSession(args.cookiejar, args.username, args.course)

    table = get_visit_stats(session)
    with open('visit_stats.txt', 'a') as fp:
        for name, time in table:
            fp.write('%s %s\n' % (time, name))

    with open('forum_posts.txt', 'a') as fp:
        for post in get_forum_posts(session):
            for k, v in post['metadata']:
                fp.write("%s %s\n" % (k, v))
            fp.write('\n')
            fp.write(post['body'] + '\n')
            fp.write('='*79 + '\n')

    session.save_cookies()


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


def get_forum_posts(session):
    for forum_id, name in get_forum_ids(session):
        print(name)
        nonce, tids = get_thread_ids(session, forum_id)
        threads = get_thread_posts(
            session, forum_id, nonce, tids)
        for post in threads:
            yield post


def get_thread_posts(session, forum_id, nonce, threads):
    ids = [i for i, name in threads]

    url = (
        'https://bb.au.dk/webapps/discussionboard/do/message' +
        '?conf_id=%s&forum_id=%s&action=collect' % forum_id +
        '&blackboard.platform.security.NonceUtil.nonce=%s' % nonce +
        ''.join('&formCBs=%s' % t for t in ids) +
        '&requestType=thread&course_id=%s&' % session.course_id)
    r = session.get(url)
    document = html5lib.parse(r.content, encoding=r.encoding)
    return parse_thread_posts(document)


def parse_thread_posts(document):
    post_elements = document.findall('.//h:div[@class="dbThread"]', NS)
    h_dt = '{%s}dt' % NS['h']
    h_dd = '{%s}dd' % NS['h']
    for post in post_elements:
        checkbox = post.find(
            './/h:input[@type="checkbox"][@name="formCBs"]', NS)
        message_id = checkbox.get('value')
        message_title = checkbox.get('title')

        data = []
        for dl in post.findall('.//h:dl', NS):
            key = None
            for c in dl:
                if key == 'Author:':
                    span = c.find('./h:span', NS)
                    if span:
                        data.append(('role', span.get('class')))
                        span = span.find(
                            './h:span[@class="profileCardAvatarThumb"]', NS)
                        direct_text = (
                            [span.text or ''] + [cc.tail or '' for cc in span])
                        raw_text = ''.join(direct_text)
                    else:
                        data.append(('role', 'anonymous'))
                        raw_text = ''.join(c.itertext())
                else:
                    raw_text = ''.join(c.itertext())

                text = ' '.join(raw_text.split())

                if c.tag == h_dt:
                    key = text
                elif c.tag == h_dd:
                    data.append((key, text))
        body = post.find('.//h:div[@class="vtbegenerated"]', NS)
        if body:
            with BytesIO() as buf:
                # We cannot use default_namespace,
                # since it incorrectly errors on unnamespaced attributes
                # See: https://bugs.python.org/issue17088
                ElementTree(body).write(
                    buf, encoding='utf8', xml_declaration=False,
                    method='xml')
                body = buf.getvalue().decode('utf8')
                # Workaround to make it prettier
                body = body.replace(
                    ' xmlns:html="http://www.w3.org/1999/xhtml"', '')
                body = body.replace('<html:', '<')
                body = body.replace('</html:', '</')
                body = html2text.html2text(body)
        else:
            body = ''
        yield dict(
            message_id=message_id,
            message_title=message_title,
            metadata=data,
            body=body)


def get_forum_ids(session):
    url = (
        'https://bb.au.dk/webapps/discussionboard/do/conference' +
        '?action=list_forums&course_id=%s' % session.course_id +
        '&nav=discussion_board&showAll=true')
    r = session.get(url)
    # with open('tmp.html', 'wb') as fp:
    #     fp.write(r.content)
    document = html5lib.parse(r.content, encoding=r.encoding)
    return parse_forum_ids(document)


def parse_forum_ids(document):
    table = document.find('.//h:table[@id="listContainer_datatable"]', NS)
    links = table.findall(
        './h:tbody/h:tr/h:th/h:span[@class="dbheading"]/h:a', NS)
    forums = []
    for l in links:
        mo = re.search(
            r'conf_id=([^&]+)&forum_id=([^&]+)', l.get('href'))
        text = ' '.join(''.join(l.itertext()).split())
        if mo:
            forums.append(((mo.group(1), mo.group(2)), text))
    return forums


def get_thread_ids(session, forum_id):
    url = (
        'https://bb.au.dk/webapps/discussionboard/do/forum' +
        '?action=list_threads&nav=discussion_board' +
        '&course_id=%s' % session.course_id +
        '&conf_id=%s&forum_id=%s' % forum_id +
        '&showAll=true'
    )
    r = session.get(url)
    document = html5lib.parse(r.content, encoding=r.encoding)
    return parse_thread_ids(document)


def parse_thread_ids(document):
    form = document.find('.//h:form[@name="forumForm"]', NS)

    # Seemingly used by BB to cache requests/prevent spam
    nonce_field = form.find(
        './/h:input[@name="blackboard.platform.security.NonceUtil.nonce"]', NS)
    nonce = nonce_field.get('value')

    thread_fields = form.findall('.//h:input[@name="formCBs"]', NS)
    threads = []
    for f in thread_fields:
        threads.append((f.get('value'), f.get('title')))
    return nonce, threads


if __name__ == "__main__":
    main()
