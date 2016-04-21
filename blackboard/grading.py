import os
import re
import json
import numbers
import argparse
import blackboard
from blackboard import logger, ParserError, BadAuth, BlackBoardSession
# from groups import get_groups
from blackboard.gradebook import (
    Gradebook, Attempt, truncate_name, StudentAssignment)
from blackboard.backend import fetch_attempt, submit_grade


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
            if len(name) <= 4:
                cells.append(' %-4s' % name)
            else:
                cells.append(name[:5])
        rows = [cells]
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
                        if self.has_feedback(attempt):
                            cell.append('\u21A5')  # UPWARDS ARROW FROM BAR
                        elif self.has_downloaded(attempt):
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
            rows.append(
                ['%-8s %-30s %-6s' % (username, name, group_name or '')] +
                cells)
        for row in rows:
            print(' | '.join(row))

    def get_attempts(self, visible=True, needs_grading=None,
                     needs_download=None, needs_upload=None):
        students = self.gradebook.students
        if visible is True:
            students = filter(self.get_student_visible, students)
        attempts = (attempt for student in students
                    for assignment in student.assignments
                    for attempt in assignment.attempts)
        attempts = set(attempts)
        if needs_grading is True:
            attempts = filter(lambda a: a.needs_grading, attempts)
        if needs_download is True:
            attempts = filter(lambda a: not self.has_downloaded(a), attempts)
        if needs_upload is True:
            attempts = filter(
                lambda a: self.has_feedback(a) and a.needs_grading, attempts)
        return sorted(attempts)

    def download_all_attempt_files(self, **kwargs):
        kwargs.setdefault('needs_grading', True)
        kwargs.setdefault('needs_download', True)
        for attempt in self.get_attempts(**kwargs):
            self.download_attempt_files(attempt)
            # print("Would download %s to %s" %
            #       (attempt, self.get_attempt_directory_name(attempt)))

    def get_attempt_directory(self, attempt):
        assert isinstance(attempt, Attempt)
        if attempt.assignment.group_assignment:
            key = attempt.id
        else:
            key = attempt.id + 'I'
        st = self.attempt_state.setdefault(key, {})
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
            with open(os.path.join(d, 'student_comments.txt'), 'w') as fp:
                fp.write(data['comments'])
            logger.info("Saving student_comments.txt for attempt %s", attempt)
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
            self.extract_archive(outfile)
            o['local_path'] = outfile
            self.autosave()

    def extract_archive(self, filename):
        path = os.path.dirname(filename)
        if filename.endswith('.zip'):
            logger.debug("Unzip archive %s", filename)
            import zipfile
            with zipfile.ZipFile(filename) as zf:
                zf.extractall(path)

    def get_attempt_files(self, attempt):
        assert isinstance(attempt, Attempt)
        if attempt.assignment.group_assignment:
            key = attempt.id
        else:
            key = attempt.id + 'I'
        keys = 'submission comments files'.split()
        st = self.attempt_state.get(key, {})
        if not all(k in st for k in keys):
            self.refresh_attempt_files(attempt)
            st = self.attempt_state[key]
        return {k: st[k] for k in keys}

    def get_attempt_state(self, attempt):
        if attempt.assignment.group_assignment:
            key = attempt.id
        else:
            key = attempt.id + 'I'
        return self.attempt_state.get(key, {})

    def refresh_attempt_files(self, attempt):
        assert isinstance(attempt, Attempt)
        new_state = fetch_attempt(
            self.session, attempt.id, attempt.assignment.group_assignment)
        if attempt.assignment.group_assignment:
            key = attempt.id
        else:
            key = attempt.id + 'I'
        logger.debug("refresh_attempt_files updating attempt_state[%r]", key)
        self.attempt_state.setdefault(key, {}).update(new_state)
        self.autosave()

    def has_downloaded(self, attempt):
        """
        has_downloaded(attempt) -> True if the attempt's files have been
        downloaded.
        """

        st = self.get_attempt_files(attempt)
        files = st['files']
        all_claimed = all('local_path' in f for f in files)
        if not all_claimed:
            return False
        # Claims they all exist; do they really?
        for f in files:
            if not os.path.exists(f['local_path']):
                del f['local_path']
        # Now, all files have only existing local_path
        all_exist = all('local_path' in f for f in files)
        if not all_exist:
            # We deleted some local_paths
            self.autosave()
        return all_exist

    def has_feedback(self, attempt):
        st = self.get_attempt_state(attempt)
        directory = st.get('directory')
        if not directory:
            return
        feedback_file = os.path.join(directory, 'comments.txt')
        return os.path.exists(feedback_file)

    def get_feedback(self, attempt):
        st = self.get_attempt_state(attempt)
        directory = st.get('directory')
        if not directory:
            return
        feedback_file = os.path.join(directory, 'comments.txt')
        try:
            with open(feedback_file) as fp:
                return fp.read()
        except FileNotFoundError:
            return

    def get_feedback_attachments(self, attempt):
        st = self.get_attempt_state(attempt)
        files = st.get('files', [])
        try:
            filenames = [f['local_path'] for f in files]
        except KeyError:
            raise ValueError("Not all files downloaded")
        annotated_filenames = [
            self.get_annotated_filename(filename)
            for filename in filenames]
        return [filename for filename in annotated_filenames
                if os.path.exists(filename)]

    def get_annotated_filename(self, filename):
        base, ext = os.path.splitext(filename)
        return base + '_ann' + ext

    def get_feedback_score(self, comments):
        rehandin = re.search(r'genaflevering|re-?handin', comments, re.I)
        accept = re.search(r'accepted|godkendt', comments, re.I)
        if rehandin and accept:
            raise ValueError("Both rehandin and accept")
        elif rehandin:
            return 0
        elif accept:
            return 1

    def upload_all_feedback(self, dry_run=False):
        uploads = []
        attempts = self.get_attempts(needs_upload=True)
        for attempt in attempts:
            feedback = self.get_feedback(attempt)
            errors = []
            try:
                score = self.get_feedback_score(feedback)
            except ValueError as exn:
                errors.append(str(exn))
            else:
                if score is None:
                    errors.append("Feedback does not indicate accept/rehandin")
            try:
                attachments = self.get_feedback_attachments(attempt)
            except ValueError as exn:
                errors.append(str(exn))
            if errors:
                print("Error for %s:" % (attempt,))
                for e in errors:
                    print("* %s" % (e,))
            else:
                uploads.append((attempt, score, feedback, attachments))
        if dry_run:
            print(uploads)
        else:
            for attempt, score, feedback, attachments in uploads:
                submit_grade(self.session, attempt.id,
                             attempt.assignment.group_assignment,
                             score, feedback, attachments)

    def main(self, args, session, grading):
        if args.refresh:
            self.refresh()
        if args.download:
            self.download_all_attempt_files()
        if args.upload:
            self.upload_all_feedback(dry_run=False)
        self.print_gradebook()

    @staticmethod
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

    @classmethod
    def get_argument_parser(cls):
        parser = argparse.ArgumentParser()
        parser.add_argument('--quiet', action='store_true')
        # parser.add_argument('--username', default=None)
        # parser.add_argument('--course', default=None)
        parser.add_argument('--cookiejar', default='cookies.txt')
        parser.add_argument('--dbpath', default='grading.json')
        parser.add_argument('--download', '-d', action='store_true')
        parser.add_argument('--upload', '-u', action='store_true')
        parser.add_argument('--no-refresh', '-n', action='store_false',
                            dest='refresh')
        return parser

    @classmethod
    def parse_args(cls):
        parser = cls.get_argument_parser()
        args = parser.parse_args()
        blackboard.configure_logging(quiet=args.quiet)
        return parser, args

    @classmethod
    def get_course(cls, args):
        course = args.course
        if course is None:
            course = cls.get_setting(args.dbpath, 'course')
        if course is None:
            raise Exception("--course is required")
        return course

    @classmethod
    def get_username(cls, args):
        username = args.username
        if username is None:
            username = cls.get_setting(args.dbpath, 'username')
        if username is None:
            raise Exception("--username is required")
        return username

    @classmethod
    def execute_from_command_line(cls):
        parser, args = cls.parse_args()
        try:
            course = cls.get_course(args)
            username = cls.get_username(args)
        except Exception as exn:
            parser.error(str(exn))

        session = BlackBoardSession(args.cookiejar, username, course)
        grading = cls(session)
        grading.load(args.dbpath)
        try:
            grading.main(args, session, grading)
        except ParserError as exn:
            print(exn)
            exn.save()
        except BadAuth:
            print("Bad username or password. Forgetting password.")
            session.forget_password()
        else:
            grading.save(args.dbpath)
        session.save_cookies()
