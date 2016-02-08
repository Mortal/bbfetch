import os
import html5lib
from requests.compat import urljoin
import blackboard
from blackboard import logger
# from groups import get_groups
from gradebook import Gradebook
from elementtext import (
    element_to_markdown, element_text_content, element_to_html)
from xml.etree import ElementTree as ET


NS = {'h': 'http://www.w3.org/1999/xhtml'}


class Grading(blackboard.Serializable):
    FIELDS = ('attempt_state', 'gradebook')

    def __init__(self, session):
        self.session = session
        self.gradebook = Gradebook(self.session)

    def refresh(self):
        self.gradebook.refresh()
        self.assignments = self.get_assignments()
        if not self.attempt_state:
            self.attempt_state = {}

    def load(self, *args, **kwargs):
        super(Grading, self).load(*args, **kwargs)
        self.assignments = self.get_assignments()

    def get_assignments(self):
        assignments = {}
        for assignment in self.gradebook.assignments.keys():
            by_attempt_id = {}
            user_groups = {}
            for user_id, s in self.gradebook.students.items():
                try:
                    assignment_data = s['assignments'][assignment]
                except KeyError:
                    continue
                for i, a in enumerate(assignment_data['attempts']):
                    first = i == 0
                    last = i == (len(assignment_data['attempts']) - 1)
                    data = by_attempt_id.setdefault(
                        a['groupAttemptId'],
                        dict(users=set(), first=first, last=last, **a))
                    data['users'].add(user_id)
                    user_groups.setdefault(user_id, []).append(
                        data['users'])

            for user_id, groups in user_groups.items():
                groups = frozenset(map(frozenset, groups))
                if len(groups) > 1:
                    print("%s has handed in assignment " % user_id +
                          "%s in multiple different groups: " % assignment +
                          "%s" % (groups,))

            assignments[assignment] = by_attempt_id
        return assignments

    def get_attempt(self, attempt_id):
        for assignment_id, by_attempt_id in self.assignments.items():
            try:
                return by_attempt_id[attempt_id]
            except KeyError:
                pass

    def get_attempt_directory(self, attempt_id):
        o = self.attempt_state.setdefault(attempt_id, {})
        try:
            return o['directory']
        except KeyError:
            pass
        cwd = os.getcwd()
        assignment_id, = [
            a for a in self.assignments
            if attempt_id in self.assignments[a]]
        attempt = self.assignments[assignment_id][attempt_id]
        assignment = self.gradebook.assignments[assignment_id]
        assignment_name = assignment['name']
        group_name = attempt['groupName']
        r = 1
        d = os.path.join(cwd, assignment_name, group_name)
        if os.path.exists(d):
            d = os.path.join(cwd, assignment_name,
                             '%s (%s)' % (group_name, attempt_id))
        dirs = [d]
        while not os.path.exists(dirs[-1]):
            dirs.append(os.path.split(dirs[-1])[0])
        for dd in reversed(dirs[:-1]):
            os.mkdir(dd)
        o['directory'] = d
        return d

    def download_attempt_files(self, attempt):
        data = self.get_attempt_files(attempt)
        d = self.get_attempt_directory(attempt)
        local_files = []
        if data['comments']:
            with open(os.path.join(d, 'comments.txt'), 'w') as fp:
                fp.write(data['comments'])
            logger.info("Saving comments.txt")
            local_files.append('comments.txt')
        if data['submission']:
            with open(os.path.join(d, 'submission.txt'), 'w') as fp:
                fp.write(data['submission'])
            logger.info("Saving submission.txt")
            local_files.append('submission.txt')
        for filename, download_link in data['files']:
            outfile = os.path.join(d, filename)
            if os.path.exists(outfile):
                logger.info("%s already exists; skipping", outfile)
                continue
            response = self.session.session.get(download_link, stream=True)
            logger.info("Download %s (%s bytes)",
                        outfile, response.headers.get('content-length'))
            with open(outfile, 'wb') as fp:
                for chunk in response.iter_content(chunk_size=64*1024):
                    if chunk:
                        fp.write(chunk)
            local_files.append(filename)
        self.attempt_state[attempt]['local_files'] = local_files

    def get_attempt_files(self, attempt):
        url = ('https://bb.au.dk/webapps/assignment/' +
               'gradeAssignmentRedirector' +
               '?course_id=%s' % self.session.course_id +
               '&groupAttemptId=%s' % attempt)
        response = self.session.get(url)
        document = html5lib.parse(response.content, encoding=response.encoding)
        submission_text = document.find(
            './/h:div[@id="submissionTextView"]', NS)
        if submission_text is not None:
            submission_text = element_to_markdown(submission_text)
        submission_list = document.find(
            './/h:ul[@id="currentAttempt_submissionList"]', NS)
        if submission_list is None:
            raise ParserError("No currentAttempt_submissionList",
                              response)
        comments = document.find(
            './/h:div[@id="currentAttempt_comments"]', NS)
        if comments is not None:
            xpath = './/h:div[@class="vtbegenerated"]'
            comments = [
                element_to_markdown(e)
                for e in comments.findall(xpath, NS)
            ]
            if not comments:
                raise blackboard.ParserError(
                    "Page contains currentAttempt_comments, " +
                    "but it contains no comments",
                    response)
            comments = '\n\n'.join(comments)
        files = []
        for submission in submission_list:
            filename = element_text_content(submission)
            download_button = submission.find(
                './/h:a[@class="dwnldBtn"]', NS)
            if download_button is not None:
                download_link = urljoin(
                    response.url, download_button.get('href'))
                files.append((filename, download_link))
            else:
                s = 'currentAttempt_attemptFilesubmissionText'
                a = submission.find(
                    './/h:a[@id="' + s + '"]', NS)
                if a is not None:
                    # This <li> is for the submission_text
                    if not submission_text:
                        raise blackboard.ParserError(
                            "%r in file list, but no " % (filename,) +
                            "accompanying submission text contents",
                            response)
                else:
                    raise blackboard.ParserError(
                        "No download link for file %r" % (filename,),
                        response)
        return {
            'submission': submission_text,
            'comments': comments,
            'files': files,
        }

    def print_assignments(self):
        def group_key(group):
            k = ()
            for v in group['groupName'].split():
                try:
                    k += (0, int(v))
                except ValueError:
                    k += (1, v)
            return k + (group['last'],)

        assignments_sorted = sorted(
            self.assignments.items(), key=lambda x: x[0])
        for assignment, groups in assignments_sorted:
            print('='*79)
            print(self.gradebook.assignments[assignment]['name'])
            groups = sorted(groups.values(), key=group_key)
            for attempt in groups:
                if not attempt['last']:
                    continue
                members = sorted(
                    '%s %s' % (s['first_name'], s['last_name'])
                    for s in (self.gradebook.students[i]
                              for i in attempt['users'])
                )
                if attempt['groupStatus'] != 'ng':
                    score = attempt['groupScore']
                    if score == 1:
                        tag = '✔'
                    elif score == 0:
                        tag = '✘'
                    else:
                        tag = '%g' % score
                elif attempt['first']:
                    tag = ' '
                else:
                    tag = '.'
                tail = ''
                if not attempt['last']:
                    tail = ' Superseded by later attempt'
                print("[%s] %s (%s)%s" %
                      (tag, attempt['groupName'], ', '.join(members), tail))

    def needs_grading(self):
        attempts = []
        for assignment, groups in self.assignments.items():
            for attempt_id, attempt in groups.items():
                if attempt['groupStatus'] != 'ng':
                    continue
                r = dict(attempt_id=attempt_id)
                s = self.attempt_state.get(attempt_id, {})
                if 'local_files' in s:
                    r['downloaded'] = True
                else:
                    r['downloaded'] = False
                attempts.append(r)
        return attempts


def download_attempts(session):
    g = Grading(session)
    g.load('grading.json')
    g.print_assignments()
    for a in g.needs_grading():
        if not a['downloaded']:
            g.download_attempt_files(a['attempt_id'])
    g.save('grading.json')


if __name__ == "__main__":
    blackboard.wrapper(download_attempts)
