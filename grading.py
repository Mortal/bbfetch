import io
import os
import re
import json
import numbers
import argparse
import html5lib
from requests.compat import urljoin
import blackboard
from blackboard import logger, ParserError, BadAuth, BlackBoardSession
# from groups import get_groups
from gradebook import Gradebook, Attempt, truncate_name, StudentAssignment
from elementtext import (
    element_to_markdown, element_text_content)


NS = {'h': 'http://www.w3.org/1999/xhtml'}


class Grading(blackboard.Serializable):
    FIELDS = ('attempt_state', 'gradebook', 'username')

    gradebook_class = Gradebook

    def __init__(self, session):
        self.session = session
        self.gradebook = type(self).gradebook_class(self.session)
        self.username = session.username

    def refresh(self):
        logger.info("Refresh gradebook")
        self.gradebook.refresh()
        if not self.attempt_state:
            self.attempt_state = {}
        self.autosave()

    def print_gradebook(self):
        """Print a representation of the gradebook state."""
        assignments = self.gradebook.assignments
        cells = ['%-8s %-30s %-6s' % ('Username', 'Name', 'Group')]
        for assignment in assignments:
            name = self.get_assignment_name_display(assignment)
            cells.append(' %-4s' % name)
        print(' | '.join(cells))
        students = filter(self.get_student_visible, self.gradebook.students)
        students = sorted(students, key=self.get_student_ordering)
        for u in students:
            name = str(u)
            if not u['available']:
                name = '(%s)' % name
            cells = []
            for assignment in assignments:
                try:
                    student_assignment = u.assignments[assignment.id]
                except KeyError:
                    cells.append('     ')
                    continue
                assert isinstance(student_assignment, StudentAssignment)
                cell = []
                for attempt in student_assignment.attempts:
                    if attempt.needs_grading:
                        if self.has_downloaded(attempt):
                            cell.append('!')
                        else:
                            cell.append('\u2913')  # DOWNWARDS ARROW TO BAR
                    elif attempt.score == 0:
                        cell.append('\u2718')  # HEAVY BALLOT X
                    elif attempt.score == 1:
                        cell.append('\u2714')  # HEAVY CHECK MARK
                    elif isinstance(attempt.score, numbers.Real):
                        cell.append('%g' % attempt.score)
                cells.append('%-5s' % ''.join(cell))
            username = u['username'][:8]
            name = truncate_name(name, 30)
            group_name = self.get_group_name_display(u.group)[:6]
            print('%-8s %-30s %-6s | %s' %
                  (username, name, group_name or '', ' | '.join(cells)))

    def get_attempts(self):
        return sorted(set(
            attempt
            for student in self.gradebook.students
            for assignment in student.assignments
            for attempt in assignment.attempts
        ))

    def get_attempt_directory(self, attempt):
        assert isinstance(attempt, Attempt)
        st = self.attempt_state.setdefault(attempt.id, {})
        try:
            d = st['directory']
        except KeyError:
            pass
        else:
            if os.path.exists(d):
                return d
        d = self.get_attempt_directory_name(attempt)
        os.makedirs(d)
        st['directory'] = d
        self.autosave()
        return d

    def get_attempt_directory_name(self, attempt):
        """
        To be overridden in subclass. Decide the name where the attempt's
        files are to be stored.
        """
        assert isinstance(attempt, Attempt)
        cwd = os.getcwd()
        assignment = attempt.assignment
        assignment_name = assignment.name
        group_name = attempt.student.group_name
        return os.path.join(cwd, assignment_name,
                            '%s (%s)' % (group_name, attempt.id))

    def download_attempt_files(self, attempt):
        assert isinstance(attempt, Attempt)
        data = self.get_attempt_files(attempt)
        d = self.get_attempt_directory(attempt)
        if data['comments']:
            with open(os.path.join(d, 'comments.txt'), 'w') as fp:
                fp.write(data['comments'])
            logger.info("Saving comments.txt for attempt %s", attempt)
        if data['submission']:
            with open(os.path.join(d, 'submission.txt'), 'w') as fp:
                fp.write(data['submission'])
            logger.info("Saving submission.txt for attempt %s", attempt)
        for o in data['files']:
            filename = o['filename']
            download_link = o['download_link']
            if 'local_path' in o:
                continue
            outfile = os.path.join(d, filename)
            if os.path.exists(outfile):
                logger.info("%s already exists; skipping", outfile)
                continue
            response = self.session.session.get(download_link, stream=True)
            logger.info("Download %s %s (%s bytes)", attempt,
                        outfile, response.headers.get('content-length'))
            with open(outfile, 'wb') as fp:
                for chunk in response.iter_content(chunk_size=64*1024):
                    if chunk:
                        fp.write(chunk)
            o['local_path'] = outfile
            self.autosave()

    def get_attempt_files(self, attempt):
        assert isinstance(attempt, Attempt)
        keys = 'submission comments files'.split()
        st = self.attempt_state[attempt.id]
        if not all(k in st for k in keys):
            self.refresh_attempt_files(attempt)
            st = self.attempt_state[attempt.id]
        return {k: st[k] for k in keys}

    def refresh_attempt_files(self, attempt):
        assert isinstance(attempt, Attempt)
        url = ('https://bb.au.dk/webapps/assignment/' +
               'gradeAssignmentRedirector' +
               '?course_id=%s' % self.session.course_id +
               '&groupAttemptId=%s' % attempt.id)
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
                files.append(
                    dict(filename=filename, download_link=download_link))
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
        logger.debug("refresh_attempt_files updating attempt_state[%r]",
                     attempt.id)
        self.attempt_state.setdefault(attempt.id, {}).update(
            submission=submission_text,
            comments=comments,
            files=files)
        self.autosave()

    def print_assignments(self):
        def group_key(group):
            k = ()
            for v in group['groupName'].split():
                try:
                    k += (0, int(v))
                except ValueError:
                    k += (1, v)
            return k + (group['last'],)

        all_attempts = self.get_attempts()
        for assignment in self.gradebook.assignments:
            attempts = [a for a in all_attempts
                        if a.assignment == assignment]
            print('='*79)
            print(assignment)
            for attempt in attempts:
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

    def has_downloaded(self, assignment):
        """
        has_downloaded(attempt) -> True if the attempt's files have been
        downloaded.

        has_downloaded(student_assignment) -> True if the student's latest
        attempt's files have been downloaded; None if no attempts exist.
        """

        if isinstance(assignment, Attempt):
            attempts = [assignment]
        else:
            assert isinstance(assignment, StudentAssignment)
            attempts = list(assignment.attempts)
        if attempts:
            st = self.attempt_state.get(attempts[-1].id, {})
            return 'local_files' in st

    def submit_grade(self, attempt_id, grade, text, filenames):
        url = (
            'https://bb.au.dk/webapps/assignment/gradeAssignmentRedirector' +
            '?course_id=%s' % self.session.course_id +
            '&groupAttemptId=%s' % attempt_id)
        # We need to fetch the page to get the nonce
        response = self.session.get(url)
        document = html5lib.parse(response.content, encoding=response.encoding)
        form = document.find('.//h:form[@id="currentAttempt_form"]', NS)
        if form is None:
            raise ParserError("No <form id=currentAttempt_form>", response)
        fields = (form.findall('.//h:input', NS) +
                  form.findall('.//h:textarea', NS))
        data = [
            (field.get('name'), field.get('value'))
            for field in fields
            if field.get('name')
        ]
        data_lookup = {k: i for i, (k, v) in enumerate(data)}

        def data_get(k, *args):
            if args:
                d, = args
            try:
                return data[data_lookup[k]][1]
            except KeyError:
                if args:
                    return d
                raise

        def data_set(k, v):
            try:
                data[data_lookup[k]] = k, v
            except KeyError:
                data_lookup[k] = len(data)
                data.append((k, v))

        def data_extend(kvs):
            for k, v in kvs:
                data_lookup[k] = len(data)
                data.append((k, v))

        data_set('grade', str(grade))
        data_set('feedbacktext', text)

        files = []

        for i, filename in enumerate(filenames):
            base = os.path.basename(filename)
            data_extend([
                ('feedbackFiles_attachmentType', 'L'),
                ('feedbackFiles_fileId', 'new'),
                ('feedbackFiles_artifactFileId', 'undefined'),
                ('feedbackFiles_artifactType', 'undefined'),
                ('feedbackFiles_artifactTypeResourceKey', 'undefined'),
                ('feedbackFiles_linkTitle', base),
            ])
            with open(filename, 'rb') as fp:
                fdata = fp.read()
            files.append(('feedbackFiles_LocalFile%d' % i, (base, fdata)))
        post_url = (
            'https://bb.au.dk/webapps/assignment//gradeGroupAssignment/submit')
        if not files:
            # BlackBoard requires the POST to be
            # Content-Type: multipart/form-data.
            # Unfortunately, requests can only make a form-data POST
            # if it has file-like input in the files list.
            files = [('dummy', io.StringIO(''))]
        try:
            response = self.session.post(post_url, data=data, files=files)
        except:
            logger.exception("data=%r files=%r", data, files)
            raise
        document = html5lib.parse(response.content, encoding=response.encoding)
        msg = document.find('.//h:span[@id="goodMsg1"]', NS)
        if msg is None:
            raise ParserError("No goodMsg1 in POST response", response)
        logger.debug("goodMsg1: %s", element_text_content(msg))


class GradingDads(Grading):
    def get_student_ordering(self, student):
        return (student.group or '\xff', student.name)

    def get_student_visible(self, student):
        group_name = self.get_group_name_display(student.group) or ''
        return group_name.startswith('2-')

    def get_group_name_display(self, group_name):
        if group_name is None:
            return group_name
        elif group_name.startswith('Gruppe'):
            x = group_name.split()
            return '%s-%s' % (x[1], x[3])
        else:
            return group_name

    def get_assignment_name_display(self, assignment):
        if assignment.name.startswith('Aflevering'):
            return assignment.name.split()[-1]
        else:
            return assignment.name

    def get_class_name(self, group_name):
        if group_name.startswith('Gruppe') or group_name.startswith('Hold'):
            x = group_name.split()
            return x[1]

    def get_group_number(self, group_name):
        if group_name.startswith('Gruppe'):
            x = group_name.split()
            return x[3]

    def get_attempt_directory_name(self, attempt):
        group_name = attempt.group_name
        attempt_id = attempt.id
        if attempt_id.startswith('_'):
            attempt_id = attempt_id[1:]
        if attempt_id.endswith('_1'):
            attempt_id = attempt_id[:-2]
        return '{base}/A{assignment}-{class_name}/{group}_{id}'.format(
            base='/home/rav/TA/dADS2-2016',
            assignment=self.get_assignment_name_display(attempt.assignment),
            class_name=self.get_class_name(group_name),
            group=self.get_group_number(group_name),
            id=attempt_id)


def download_attempts(session):
    g = Grading(session)
    g.load('grading.json')
    g.print_assignments()
    for a in g.needs_grading():
        if not a['downloaded']:
            g.download_attempt_files(a['attempt_id'])
    g.save('grading.json')


def submit_feedback(session):
    g = Grading(session)
    g.load('grading.json')
    g.submit_grade('_22022_1', 0.8, 'Test feedback', ['test.txt'])


def submit_feedback_20160417(session):
    g = Grading(session)
    g.load('grading.json')
    g.refresh()
    assignment_id = '219345'
    groups = g.assignments[assignment_id]
    attempt_ids = sorted(groups.keys(), key=lambda x: groups[x]['groupName'])
    for attempt_id in attempt_ids:
        attempt = groups[attempt_id]
        d = g.get_attempt_directory(attempt_id)
        data = g.get_attempt_files(attempt_id)
        uploads = []
        comments = ''
        score = None
        comments_file = os.path.join(d, 'comments.txt')
        if not os.path.exists(comments_file):
            continue

        with open(comments_file) as fp:
            comments = fp.read()
        rehandin = re.search(r'genaflevering|re-?handin', comments, re.I)
        accept = re.search(r'accepted|godkendt', comments, re.I)
        if rehandin and accept:
            score = 0.5
        elif rehandin:
            score = 0
        elif accept:
            score = 1

        for o in data['files']:
            filename = o['filename']
            base, ext = os.path.splitext(filename)
            if ext != '.pdf':
                continue
            # outfile = os.path.join(d, filename)
            annfile = os.path.join(d, '%s_ann%s' % (base, ext))
            if os.path.exists(annfile):
                uploads.append(annfile)
        print(attempt['groupName'], attempt['groupStatus'],
              attempt_id, score, len(comments), uploads)
        if attempt['groupStatus'] == 'ng' and (score == 0 or score == 1):
            g.submit_grade(attempt_id, score, comments, uploads)
    # for a in g.needs_grading():


def main(args, session, grading):
    grading.refresh()
    grading.print_gradebook()


def get_setting(filename, key):
    try:
        with open(filename) as fp:
            o = json.load(fp)
        try:
            return o[key]
        except KeyError:
            return o['payload'][key]
    except Exception:
        pass


def wrapper():
    parser = argparse.ArgumentParser()
    parser.add_argument('--quiet', action='store_true')
    parser.add_argument('--username', '-u', default=None)
    parser.add_argument('--course', default=None)
    parser.add_argument('--cookiejar', default='cookies.txt')
    parser.add_argument('--dbpath', default='grading.json')
    args = parser.parse_args()
    blackboard.configure_logging(quiet=args.quiet)

    course = args.course
    if course is None:
        course = get_setting(args.dbpath, 'course')
    if course is None:
        parser.error("--course is required")
    username = args.username
    if username is None:
        username = get_setting(args.dbpath, 'username')
    if username is None:
        parser.error("--username is required")

    session = BlackBoardSession(args.cookiejar, username, course)
    grading = GradingDads(session)
    grading.load(args.dbpath)
    try:
        main(args, session, grading)
    except ParserError as exn:
        print(exn)
        exn.save()
    except BadAuth:
        print("Bad username or password. Forgetting password.")
        session.forget_password()
    else:
        grading.save(args.dbpath)
    session.save_cookies()


if __name__ == "__main__":
    wrapper()
    # blackboard.wrapper(submit_feedback_20160417)
