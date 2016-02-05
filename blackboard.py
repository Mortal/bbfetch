import re
import time
import getpass
import keyring
import logging
import html5lib
import requests
import requests.cookies
from six.moves.http_cookiejar import LWPCookieJar
from six.moves.urllib.parse import urlparse, parse_qs, urlencode


logger = logging.getLogger('blackboard')

NS = {'h': 'http://www.w3.org/1999/xhtml'}


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

    def get_cookie(self, key, path):
        try:
            return self.session.cookies._cookies['bb.au.dk'][path][key].value
        except KeyError:
            print(self.session.cookies._cookies)
            raise

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

        history = list(response.history) + [response]
        logger.info("Sending login details to WAYF")
        response = self.session.post(response.url, self.get_auth())
        history += list(response.history) + [response]
        logger.debug("WAYF login -> %s", response.url)
        logger.debug("WAYF response %s", response.status_code)
        with open('wayftmp.html', 'wb') as fp:
            fp.write(response.content)

        response = self.post_hidden_form(response)
        history += list(response.history) + [response]
        logger.debug("Hidden form 1 -> %s %s",
                     response.status_code, response.url)
        response = self.post_hidden_form(response)
        history += list(response.history) + [response]
        logger.debug("Hidden form 2 -> %s %s",
                     response.status_code, response.url)
        response.history = history[:-1]
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
        history = list(response.history) + [response]

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
                history += list(response.history) + [response]
                continue
            break
        response.history = history[:-1]
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
        response = self.autologin(self.session.get(url))
        if response.url != url:
            history = list(response.history) + [response]
            response = self.session.get(url)
            response.history = history + list(response.history)
        return response


def slowlog(threshold=2):
    t1 = time.time()

    def report(msg, *args, **kwargs):
        t2 = time.time()
        t = t2 - t1
        if t > threshold:
            if kwargs:
                kwargs['t'] = t
                logger.debug(msg, kwargs)
            else:
                args += (t,)
                logger.debug(msg, *args)

    return report
