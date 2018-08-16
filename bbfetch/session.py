import re
import getpass
import keyring
import html5lib
import aiohttp

from six.moves.urllib.parse import urlencode

from bbfetch.base import BadAuth, ParserError, logger, DOMAIN


NS = {'h': 'http://www.w3.org/1999/xhtml'}


class BlackboardSession:
    def __init__(self, cookiejar, username, course_id):
        self.cookiejar_filename = cookiejar
        self.username = username
        self.course_id = course_id

        self.password = None
        self.cookies = aiohttp.CookieJar()
        self.session = aiohttp.ClientSession(cookie_jar=self.cookies)
        self.load_cookies()

    def __aenter__(self):
        return self.session.__aenter__()

    def __aexit__(self, *args):
        return self.session.__aexit__(*args)

    def load_cookies(self):
        try:
            self.cookies.load(self.cookiejar_filename)
        except FileNotFoundError:
            pass

    def save_cookies(self):
        self.cookies.save(self.cookiejar_filename)

    def get_cookie(self, key, path):
        cookies = self.cookies.filter_cookies('https://' + DOMAIN + path)
        try:
            return cookies[key].value
        except KeyError:
            print(self.cookies)
            raise

    def get_username(self):
        return input("WAYF username: ")

    def get_password(self):
        p = keyring.get_password("fetch.py WAYF", self.username)
        if p is None:
            print("Please enter password for %s to store in keyring." %
                  self.username)
            p = getpass.getpass()
            keyring.set_password("fetch.py WAYF", self.username, p)
        return p

    def get_auth(self):
        if self.username is None:
            self.username = self.get_username()
        if self.password is None:
            self.password = self.get_password()
        return dict(username=self.username, password=self.password)

    def forget_password(self):
        if self.username is None:
            raise ValueError("forget_password: username is None")
        keyring.delete_password("fetch.py WAYF", self.username)

    async def wayf_login(self, response):
        """Login to WAYF.

        Parameters
        ----------
        response : requests.Response
            Login page (with username/password form)
        """

        history = list(response.history) + [response]
        logger.info("Sending login details to WAYF")
        response = await self.session.post(response.url, data=self.get_auth())
        history += list(response.history) + [response]
        if 'Forkert brugernavn eller kodeord' in await response.text():
            raise BadAuth()

        response = await self.post_hidden_form(response)
        history += list(response.history) + [response]
        response = await self.post_hidden_form(response)
        history += list(response.history) + [response]
        response._history = history[:-1]
        return response

    async def relogin(self):
        url = (
            'https://%s/webapps/bb-auth-provider-shibboleth-BBLEARN' % DOMAIN +
            '/execute/shibbolethLogin?authProviderId=_102_1')
        response = await self.get(url)
        if self.detect_login(await response.text()) is False:
            logger.error("Seems logged out after re-login. " +
                         "Try deleting your cookiejar.")
            raise ParserError("Not logged in", response)
        return response

    def detect_login(self, response_text):
        document = html5lib.parse(response_text)
        log_in_id = 'topframe.login.label'
        o = document.find('.//h:a[@id="%s"]' % log_in_id, NS)
        if o is not None:
            return False
        log_out_id = 'topframe.logout.label'
        o = document.find('.//h:a[@id="%s"]' % log_out_id, NS)
        if o is not None:
            return True

    async def post_hidden_form(self, response):
        """Send POST request to form with only hidden fields.

        Parameters
        ----------
        response : requests.Response
            Page containing form with only hidden fields
        """

        document = html5lib.parse(await response.text())
        form = document.find('.//h:form', NS)
        url = form.get('action')
        inputs = form.findall('.//h:input[@name]', NS)
        if not inputs:
            raise ParserError("No <input> with name", response)
        post_data = {
            i.get('name'): i.get('value')
            for i in inputs
        }
        response = await self.session.post(url, data=post_data)

        return response

    async def follow_html_redirect(self, response):
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
            'https://%s/webapps/' % DOMAIN +
            'bb-auth-provider-shibboleth-BBLEARN/execute/shibbolethLogin')
        history = list(response.history) + [response]

        while True:
            document = html5lib.parse(
                await response.text())
            scripts = document.findall('.//h:script', NS)

            next_url = None
            for s in scripts:
                t = ''.join(s.itertext())
                mo = re.match(js_redirect_pattern, t)
                if mo:
                    next_url = mo.group('url')
                    break
            if next_url is not None:
                p = next_url.host + next_url.path
                if p == '%s/webapps/login/' % DOMAIN:
                    qs = next_url.query
                    try:
                        return_url = qs['new_loc'][0]
                    except KeyError:
                        print("We are being redirected to %r" % (next_url,))
                        return_url = ''
                    # It seems that making a GET request to this page
                    # logs you out?
                    if return_url == '/webapps/login/?action=relogin':
                        logger.debug(
                            "Not setting returnUrl to %r", return_url)
                        return_url = ''
                    new_qs = urlencode(
                        dict(returnUrl=return_url,
                             authProviderId='_102_1'))
                    next_url = '%s?%s' % (real_login_url, new_qs)
                response = await self.session.get(next_url)
                history += list(response.history) + [response]
                continue
            break
        response._history = history[:-1]
        return response

    async def autologin(self, response):
        """Automatically log in if necessary.

        If the given response is not for a login form,
        just follow HTML redirects and return the response.
        Otherwise, log in using wayf_login and get_auth.
        """

        response = await self.follow_html_redirect(response)
        if response.url.host == 'wayf.au.dk':
            response = await self.wayf_login(response)
        return response

    def get_edit_mode(self, response_text):
        document = html5lib.parse(response_text)
        mode_switch = document.find('.//*[@id="editModeToggleLink"]', NS)
        if mode_switch is not None:
            return 'read-on' in (mode_switch.get('class') or '').split()

    async def ensure_edit_mode(self, response):
        if self.get_edit_mode(await response.text()) is False:
            url = ('https://%s/webapps/blackboard/execute/' % DOMAIN +
                   'doCourseMenuAction?cmd=setDesignerParticipantViewMode' +
                   '&courseId=' + self.course_id +
                   '&mode=designer')
            logger.debug("Switch to edit mode")
            r = await self.get(url)
            history = (list(response.history) + [response] +
                       list(r.history) + [r])
            response = await self.get(history[0].url)
            response._history = history + list(response.history)
        return response

    async def get(self, url):
        response = await self.autologin(await self.session.get(url))
        if self.detect_login(await response.text()) is False:
            history = response.history + [response]
            relogin_response = await self.relogin()
            history += relogin_response.history + [relogin_response]
            response = await self.autologin(await self.session.get(url))
            response._history = history + list(response.history)
        if response.url != url:
            history = list(response.history) + [response]
            response = await self.session.get(url)
            response._history = history + list(response.history)
        self.log_error(await response.text())
        return response

    def log_error(self, response_text):
        document = html5lib.parse(response_text)
        content = document.find('.//h:div[@id="contentPanel"]', NS)
        if content is not None:
            class_list = (content.get('class') or '').split()
            if 'error' in class_list:
                logger.info("contentPanel indicates an error has occurred")
                # raise ParserError("Error", response)

    async def post(self, url, data, files=None, headers=None):
        response = await self.session.post(
            url, data=data, files=files, headers=headers)
        # if response.history:
        #     logger.warning('POST %r redirected', url)
        #     for r in response.history:
        #         logger.warning("... from %r", r.url)
        #     logger.warning("... to %r", response.url)
        return response

    async def ensure_logged_in(self):
        url = (
            'https://%s/webapps/blackboard/content/manageDashboard.jsp' % DOMAIN +
            '?course_id=%s' % self.course_id +
            '&sortCol=LastLoginCol&sortDir=D')
        async with (await self.get(url)):
            pass


class PassBlackboardSession(BlackboardSession):
    def get_password(self):
        # Use https://www.passwordstore.org/ to get password
        import subprocess
        s = subprocess.check_output(
            ('pass', 'au'), universal_newlines=True)
        return s.splitlines()[0].strip()

    def forget_password(self):
        raise NotImplementedError
