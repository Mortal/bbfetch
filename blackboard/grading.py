import os
import re
import json
import decimal
import numbers
import argparse
import requests
import functools
import blackboard
import collections
from blackboard import logger, ParserError, BadAuth, BlackboardSession
# from groups import get_groups
from blackboard.gradebook import (
    Gradebook, Attempt, truncate_name, StudentAssignment, Rubric,
)
from blackboard.backend import (
    fetch_attempt, submit_grade, fetch_groups, fetch_rubric,
    is_course_id_valid, NotYetSubmitted,
)


NS = {'h': 'http://www.w3.org/1999/xhtml'}


class Grading(blackboard.Serializable):
    FIELDS = ('attempt_state', 'gradebook', 'username', 'groups', 'rubrics')

    session_class = BlackboardSession
    gradebook_class = Gradebook

    def __init__(self, session):
        self.session = session
        self.gradebook = type(self).gradebook_class(self.session)
        self.username = session.username

    def initialize_fields(self):
        super().initialize_fields()
        if not is_course_id_valid(self.session):
            logger.error(
                "Course ID %s does not seem to be a valid Blackboard course",
                self.session.course_id)
            raise SystemExit(1)

    def refresh(self, **kwargs):
        logger.info("Refresh gradebook")
        self.gradebook.refresh(
            student_visible=self.get_student_visible,
            **kwargs)
        if not self.attempt_state:
            self.attempt_state = {}
        if self.should_refresh_groups():
            self.refresh_groups()
        self.autosave()

    def should_refresh_groups(self):
        if not hasattr(self, 'groups') or self.groups is None:
            return True
        if any(k.startswith('Access the profile') for k in self.groups.keys()):
            return True

    def refresh_groups(self):
        logger.info("Fetching student group memberships")
        self.groups = fetch_groups(self.session)
        if any(k.startswith('Access the profile') for k in self.groups.keys()):
            raise Exception("fetch_groups returned bad usernames")

    def get_rubric(self, attempt_rubric):
        if not hasattr(self, 'rubrics') or self.rubrics is None:
            self.rubrics = {}
        rubric_id = attempt_rubric['id']
        if rubric_id not in self.rubrics:
            assoc_id = attempt_rubric['assocEntityId']
            self.rubrics[rubric_id] = fetch_rubric(
                self.session, assoc_id, rubric)

        rubric = self.rubrics[rubric_id]
        title = rubric['title']
        assert title == attempt_rubric['title']
        assert len(rubric['rows']) == len(attempt_rubric['rows'])
        rows = []
        columns = rubric['columns']
        for r1, r2 in zip(rubric['rows'], attempt_rubric['rows']):
            row_title = r1['title']
            assert r1['id'] == r2['row_id']
            assert len(r1['cells']) == len(columns)
            cells = [
                dict(title=title, id=cell['id'], desc=cell['desc'],
                     score=decimal.Decimal(cell['percentage']))
                for title, cell in zip(columns, r1['cells'])
            ]
            cell_id_map = {cell['id']: i for i, cell in enumerate(cells)}
            assert len(cell_id_map) == len(cells), 'IDs not distinct'
            if r2['cell_id'] is not None:
                assert r2['cell_id'] in cell_id_map
            rows.append(dict(
                title=row_title, cells=cells, chosen_id=r2['cell_id']))

        return Rubric(title=title, rows=rows)

    def get_rubrics(self, attempt_id):
        if isinstance(attempt_id, Attempt):
            attempt_id = attempt_id.id
        attempt = self.attempt_state.get(attempt_id, {})
        rubrics = (attempt.get('rubric_data') or dict(rubrics=()))['rubrics']
        return [self.get_rubric(attempt_rubric) for attempt_rubric in rubrics]

    def deserialize_default(self, key):
        if key in ('groups', 'rubrics'):
            return {}
        return super().deserialize_default(key)

    def get_student_groups(self, student):
        if self.groups is None:
            return []
        Group = collections.namedtuple('Group', 'name id')
        try:
            groups = [Group(g[0], g[1])
                      for g in self.groups[student.username]['groups']]
        except KeyError:
            groups = []
        return groups

    def get_student_group_display(self, student):
        groups = self.get_student_groups(student)
        if self.student_group_display_regex is None:
            if not groups:
                return '-'
            else:
                return self.get_group_name_display(groups[0])
        else:
            pattern, repl = self.student_group_display_regex
            for g in groups:
                mo = re.fullmatch(pattern, g.name)
                if mo:
                    return re.sub(pattern, repl, g.name)
            return ''

    def get_assignment_name_display(self, assignment):
        if self.assignment_name_display_regex is None:
            raise NotImplementedError
        else:
            pattern, repl = self.assignment_name_display_regex
            mo = re.fullmatch(pattern, assignment.name)
            if mo is None:
                return assignment.name
            else:
                return re.sub(pattern, repl, assignment.name)

    def get_group_name_display(self, group_name):
        raise NotImplementedError

    def get_student_visible(self, student):
        try:
            gr = self.groups_regex
        except AttributeError:
            gr = None
        if gr is not None:
            for g in self.get_student_groups(student):
                if re.match(gr, g.name) is not None:
                    return True
            return False
        if self.classes is None:
            raise NotImplementedError
        if self.classes is all:
            return True
        if isinstance(self.classes, str):
            classes = (self.classes,)
        else:
            classes = self.classes
        for g in self.get_student_groups(student):
            for c in classes:
                if g.name == c:
                    return True
        return False

    def get_student_ordering(self, student):
        """
        Return a sorting key for the student
        indicating how students should be sorted when displayed.
        Typically you want to sort by group, then by name.
        """
        return (self.get_student_group_display(student), student.name)

    def get_assignment_display(self, u, assignment):
        try:
            student_assignment = u.assignments[assignment.id]
        except KeyError:
            return ''
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
        return ''.join(cell)

    def get_gradebook_columns(self):
        columns = [
            ('Username', lambda u: u.username),
            ('Name', lambda u: truncate_name(u.name, 27)),
            ('Group', self.get_student_group_display),
        ]
        for assignment in self.gradebook.assignments.values():
            name = self.get_assignment_name_display(assignment)
            display = functools.partial(self.get_assignment_display,
                                        assignment=assignment)
            columns.append(('|', lambda u: '|'))
            columns.append((name, display))
        columns.append(('|', lambda u: '|'))
        columns.append(
            ('Pts', lambda u: '%g' % u.score))
        return columns

    def get_gradebook_cells(self, columns, students):
        header_row = []
        for c in columns:
            header_name = c[0]
            header_row.append(header_name)
        rows = [header_row]
        for u in students:
            cells = []
            for c in columns:
                header_value = c[1]
                cells.append(header_value(u))
            rows.append(cells)
        return rows

    def print_gradebook(self):
        """Print a representation of the gradebook state."""
        columns = self.get_gradebook_columns()
        students = filter(self.get_student_visible,
                          self.gradebook.students.values())
        students = sorted(students, key=self.get_student_ordering)
        rows = self.get_gradebook_cells(columns, students)
        col_widths = [0] * len(columns)
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))
        for row in rows:
            row_fmt = []
            for i, cell in enumerate(row):
                row_fmt.append(str(cell).ljust(col_widths[i]))
            print(' '.join(row_fmt).rstrip())

    def dump_gradebook(self, fp):
        columns = [
            ('Group', self.get_student_group_display),
            ('Username', lambda u: u.username),
            ('Student number', lambda u: u.student_number),
            ('First name', lambda u: u.first_name),
            ('Last name', lambda u: u.last_name),
            ('Score', lambda u: '%g' % u.score),
        ]

        def display(u, assignment):
            try:
                student_assignment = u.assignments[assignment.id]
            except KeyError:
                return ''
            score = sum(a.score or 0 for a in student_assignment.attempts)
            if score:
                return len(student_assignment.attempts)
            else:
                return -len(student_assignment.attempts)

        for assignment in self.gradebook.assignments.values():
            name = self.get_assignment_name_display(assignment)
            columns.append(
                (name, functools.partial(display, assignment=assignment)))

        students = filter(self.get_student_visible,
                          self.gradebook.students.values())
        students = sorted(students, key=self.get_student_ordering)
        rows = self.get_gradebook_cells(columns, students)
        for row in rows:
            print('\t'.join(map(str, row)), file=fp)

    def get_attempt(self, group, assignment, attempt_index=-1):
        assert isinstance(group, str)
        if isinstance(assignment, int):
            assignment = str(assignment)
        assert isinstance(assignment, str)
        students = self.gradebook.students.values()
        students = list(filter(self.get_student_visible, students))
        group_students = [
            student for student in students
            if self.get_student_group_display(student) == group
        ]
        if not group_students:
            names = sorted(set(self.get_student_group_display(s)
                               for s in students))
            raise ValueError("No students in a group named %r. " % (group,) +
                             "Must be one of: %s" % (names,))
        student = group_students[0]
        assignments = [
            a for a in self.gradebook.assignments.values()
            if self.get_assignment_name_display(a) == assignment
        ]
        if not assignments:
            names = [self.get_assignment_name_display(a)
                     for a in self.gradebook.assignments.values()]
            raise ValueError("No assignments named %r. " % (assignment,) +
                             "Must be one of: %s" % (names,))
        assignment = assignments[0]
        attempts = student.assignments[assignment.id].attempts
        return attempts[attempt_index]

    def get_attempts(self, visible=True, needs_grading=None,
                     needs_download=None, needs_upload=None):
        students = self.gradebook.students.values()
        if visible is True:
            students = filter(self.get_student_visible, students)
        attempts = (attempt for student in students
                    for assignment in student.assignments.values()
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

    def get_attempt_directory(self, attempt, create):
        assert isinstance(attempt, Attempt)
        st = self.get_attempt_state(attempt, create=create)
        try:
            d = st['directory']
        except KeyError:
            pass
        else:
            if os.path.exists(d):
                return d
        if not create:
            return
        d = self.get_attempt_directory_name(attempt)
        os.makedirs(d, exist_ok=True)
        st['directory'] = d
        self.autosave()
        return d

    def get_attempt_directory_name(self, attempt):
        """
        To be overridden in subclass. Decide the name where the attempt's
        files are to be stored.
        """
        assert isinstance(attempt, Attempt)

        if self.attempt_directory_name is None:
            cwd = os.getcwd()
            assignment = attempt.assignment
            assignment_name = assignment.name
            group_name = attempt.student.group_name
            return os.path.join(cwd, assignment_name,
                                '%s (%s)' % (group_name, attempt.id))

        else:
            group_name = attempt.group_name
            if group_name and group_name.startswith('Gruppe'):
                class_name = group_name.split()[1]
                group_number = group_name.split()[3]
            else:
                class_name = group_number = None

            attempt_id = re.sub(r'_(.*)_1', r'\1', attempt.id)
            assignment = self.get_assignment_name_display(attempt.assignment)

            return os.path.expanduser(self.attempt_directory_name.format(
                assignment=assignment,
                class_name=class_name, group=group_number, id=attempt_id))

    def download_attempt_files(self, attempt):
        assert isinstance(attempt, Attempt)
        try:
            files = self.get_attempt_files(attempt)
        except NotYetSubmitted:
            logger.info('Skip downloading %s (not yet submitted)', attempt)
            return
        d = self.get_attempt_directory(attempt, create=True)
        for o in files:
            filename = o['filename']
            outfile = os.path.join(d, filename)
            if os.path.exists(outfile):
                logger.info("Skip downloading %s %s (already exists)",
                            attempt, outfile)

            elif 'contents' in o:
                s = o['contents']
                if s and not s.endswith('\n'):
                    s += '\n'
                with open(outfile, 'w') as fp:
                    fp.write(s)
                logger.info("Storing %s %s (text content)", attempt, filename)

            else:
                download_link = o['download_link']
                response = self.session.session.get(download_link, stream=True)
                logger.info("Download %s %s", attempt, outfile)
                with open(outfile, 'wb') as fp:
                    for chunk in response.iter_content(chunk_size=64*1024):
                        if chunk:
                            fp.write(chunk)
                self.extract_archive(outfile)

    def extract_archive(self, filename):
        base, ext = os.path.splitext(filename)
        if ext.startswith('.'):
            try:
                method = getattr(self, 'extract_' + ext.strip('.'))
            except AttributeError:
                pass
            else:
                method(filename)

    def extract_zip(self, filename):
        path = os.path.dirname(filename)
        logger.debug("Unzip archive %s", filename)
        import zipfile
        with zipfile.ZipFile(filename) as zf:
            zf.extractall(path)

    def get_attempt_files(self, attempt):
        assert isinstance(attempt, Attempt)
        keys = 'submission comments files'.split()
        st = self.get_attempt_state(attempt)
        if all(k in st for k in keys) and 'score' not in st:
            logger.debug("Refresh attempt %s since it was fetched in an old " +
                         "version of bbfetch", attempt.id)
        elif all(k in st for k in keys) and st['score'] != attempt.score:
            logger.debug("Refresh attempt %s since its score has changed",
                         attempt.id)
        if (not all(k in st for k in keys) or
                'score' not in st or
                st['score'] != attempt.score):
            self.refresh_attempt_files(attempt)
            st = self.get_attempt_state(attempt)
        used_filenames = set(['comments.txt'])
        files = []

        def add_file(name, **data):
            if name in used_filenames:
                base, ext = os.path.splitext(name)
                name = base + attempt.id + ext
            data['filename'] = name
            used_filenames.add(name)
            files.append(data)

        if st['submission']:
            add_file('submission.txt', contents=st['submission'])
        if st['comments']:
            add_file('student_comments.txt', contents=st['comments'])
        if st.get('feedback'):
            used_filenames.remove('comments.txt')
            add_file('comments.txt', contents=st['feedback'])
        rubrics = self.get_rubrics(attempt)
        if rubrics:
            add_file('rubric.txt',
                     contents='\n'.join(r.get_form_as_text() for r in rubrics))
        for o in st.get('feedbackfiles', []):
            add_file(o['filename'], **o)
        for o in st['files']:
            add_file(o['filename'], **o)
        return files

    def get_attempt_state(self, attempt, create=False):
        if attempt.assignment.group_assignment:
            key = attempt.id
        else:
            key = attempt.id + 'I'
        if create:
            return self.attempt_state.setdefault(key, {})
        else:
            return self.attempt_state.get(key, {})

    def refresh_attempt_files(self, attempt):
        assert isinstance(attempt, Attempt)
        logger.info("Fetch details for attempt %s", attempt)
        new_state = fetch_attempt(
            self.session, attempt.id, attempt.assignment.group_assignment)
        st = self.get_attempt_state(attempt, create=True)
        st.update(new_state)
        self.autosave()

    def has_downloaded(self, attempt):
        """
        has_downloaded(attempt) -> True if the attempt's files have been
        downloaded.
        """

        directory = self.get_attempt_directory(attempt, create=False)
        if not directory:
            return False
        try:
            files = self.get_attempt_files(attempt)
        except NotYetSubmitted:
            return False
        filenames = [os.path.join(directory, o['filename']) for o in files]
        return all(os.path.exists(f) for f in filenames)

    def has_feedback(self, attempt):
        directory = self.get_attempt_directory(attempt, create=False)
        if not directory:
            return False
        feedback_file = os.path.join(directory, 'comments.txt')
        return os.path.exists(feedback_file)

    def get_feedback(self, attempt):
        directory = self.get_attempt_directory(attempt, create=False)
        if not directory:
            return
        feedback_file = os.path.join(directory, 'comments.txt')
        try:
            with open(feedback_file) as fp:
                return fp.read()
        except FileNotFoundError:
            return

    def get_feedback_attachments(self, attempt):
        directory = self.get_attempt_directory(attempt, create=False)
        if not directory:
            raise ValueError("Files not downloaded")
        files = self.get_attempt_files(attempt)
        filenames = [os.path.join(directory, o['filename']) for o in files]
        annotated_filenames = [
            self.get_annotated_filename(filename)
            for filename in filenames]
        return [filename for filename in annotated_filenames
                if os.path.exists(filename)]

    def get_rubric_input(self, attempt):
        directory = self.get_attempt_directory(attempt, create=False)
        if not directory:
            return
        rubrics = self.get_rubrics(attempt)
        if not rubrics:
            return
        rubric_file = os.path.join(directory, 'rubric.txt')
        try:
            with open(rubric_file) as fp:
                rubric_input = fp.read()
        except FileNotFoundError:
            return
        return [r.get_form_input(rubric_input) for r in rubrics]

    def get_annotated_filename(self, filename):
        base, ext = os.path.splitext(filename)
        return base + '_ann' + ext

    rehandin_regex = r'genaflevering|re-?handin'
    accept_regex = r'accepted|godkendt'

    def get_feedback_score(self, comments):
        rehandin = re.search(self.rehandin_regex, comments, re.I)
        accept = re.search(self.accept_regex, comments, re.I)
        if rehandin and accept:
            raise ValueError("Both rehandin and accept")
        elif rehandin:
            return 0
        elif accept:
            return 1

    def get_attempt_score(self, attempt, comments):
        return self.get_feedback_score(comments)

    def upload_all_feedback(self, dry_run=False):
        return self.upload_attempts(self.get_attempts(needs_upload=True),
                                    dry_run=dry_run)

    def upload_attempt(self, attempt, dry_run=False):
        return self.upload_attempts([attempt], dry_run=dry_run)

    def upload_attempts(self, attempts, dry_run):
        uploads = []
        for attempt in attempts:
            feedback = self.get_feedback(attempt)
            errors = []
            try:
                score = self.get_attempt_score(attempt, feedback)
            except ValueError as exn:
                errors.append(str(exn))
            else:
                if score is None:
                    errors.append("Feedback does not indicate accept/rehandin")
            try:
                attachments = self.get_feedback_attachments(attempt)
            except ValueError as exn:
                errors.append(str(exn))
            try:
                rubrics = self.get_rubric_input(attempt)
            except ValueError as exn:
                errors.append(str(exn))
            if errors:
                print("Error for %s:" % (attempt,))
                for e in errors:
                    print("* %s" % (e,))
            else:
                uploads.append(
                    (attempt, score, feedback, attachments, rubrics))
        if dry_run:
            for attempt, score, feedback, attachments, rubrics in uploads:
                print("%s %s:" % (attempt.assignment, attempt,))
                print("score: %s, feedback: %s words, %s attachment(s)" %
                      (score, len(feedback.split()), len(attachments)))
                print("rubrics: %s" % (rubrics,))
                print(feedback)
        else:
            for attempt, score, feedback, attachments, rubrics in uploads:
                submit_grade(self.session, attempt.id,
                             attempt.assignment.group_assignment,
                             score, feedback, attachments, rubrics)
            self.gradebook.refresh_attempts(
                attempts=[attempt for attempt, _s, _f, _a, _r in uploads])
            self.autosave()

    def main(self, args, session, grading):
        if args.refresh_groups or args.download >= 1:
            self.refresh_groups()
        if args.refresh:
            try:
                self.refresh(refresh_attempts=args.refresh_attempts)
            except requests.ConnectionError:
                print("Connection failed; continuing in offline mode (-n)")
                args.refresh = False
        if args.check:
            self.check()
        if args.download_attempt:
            group, assignment, attempt_index = args.download_attempt
            self.download_attempt_files(
                self.get_attempt(group, assignment, attempt_index))
        if args.download >= 3:
            self.download_all_attempt_files(
                visible=None, needs_grading=None)
        elif args.download >= 2:
            self.download_all_attempt_files(
                visible=True, needs_grading=None)
        elif args.download >= 1:
            self.download_all_attempt_files(
                visible=True, needs_grading=True)
        if args.upload_check:
            self.upload_all_feedback(dry_run=True)
        if args.upload:
            self.upload_all_feedback(dry_run=False)
            if args.refresh:
                # Refresh after upload to show that feedback
                # has been uploaded
                self.refresh()
        self.print_gradebook()
        if args.save is not None:
            with open(args.save, 'w') as fp:
                self.dump_gradebook(fp)

    def check(self):
        print("Username: %r" % (self.session.username,))
        print("Course: %r" % (self.session.course_id,))
        print("STUDENTS")
        print('')
        for s in self.gradebook.students.values():
            print("Name: %s" % (s,))
            print("Group: %r" %
                  (self.get_student_group_display(s),))
            print("Visible: %s" % (self.get_student_visible(s),))
            print("Order by: %r" % (self.get_student_ordering(s),))
            for assignment in self.gradebook.assignments.values():
                try:
                    student_assignment = s.assignments[assignment.id]
                except KeyError:
                    continue
                a = student_assignment.cached_attempts
                if a is not None:
                    for attempt in a:
                        print("%r %r downloads to directory %r" %
                              (student_assignment, attempt,
                               self.get_attempt_directory_name(attempt)))
                else:
                    print("Student attempts not loaded")
            print('')

    @staticmethod
    def get_setting(key):
        try:
            with open('grading.json') as fp:
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
        parser.add_argument('--check', '-c', action='store_true',
                            help='Test that Grading methods work ' +
                                 '(for debugging)')

        def attempt_type(s):
            group, assignment, index = s.split('/')
            return (group, assignment, int(index))

        parser.add_argument('--download-attempt', '-D', metavar='ATTEMPT',
                            help='Download attempt of particular group: ' +
                                 '"10/2/0" for group 10, assignment 2, ' +
                                 'attempt index 0', type=attempt_type)
        parser.add_argument('--download', '-d', action='count', default=0,
                            help='Download handins that need grading')
        parser.add_argument('--upload', '-u', action='store_true',
                            help='Upload handins that have been graded')
        parser.add_argument('--upload-check', '-U', action='store_true',
                            help='Display what would be uploaded with -u')
        parser.add_argument('--no-refresh', '-n', action='store_false',
                            dest='refresh', help='Run in offline mode')
        parser.add_argument('--refresh-groups', '-g', action='store_true',
                            help='Refresh list of student groups')
        parser.add_argument('--refresh-attempts', '-a', action='store_true',
                            help='Refresh list of student attempts')
        parser.add_argument('--save', '-o',
                            help='Output TSV file with gradebook info')

        return parser

    @classmethod
    def get_course(cls, args):
        if cls.course is None:
            raise NotImplementedError
        else:
            return cls.course

    @classmethod
    def get_username(cls, args):
        if cls.username is None:
            raise NotImplementedError
        else:
            return cls.username

    @classmethod
    def get_password(cls, **kwargs):
        raise NotImplementedError

    def override_get_password(self, args):
        """
        Override the get_password method of BlackboardSession
        to call Grading.get_password instead; if Grading.get_password
        raises NotImplementedError, revert to calling the default
        implementation in BlackboardSession instead.
        """

        session = self.session
        # The default implementation
        super_get_password = session.get_password

        def session_get_password(session):
            # Ensure that get_password takes args and username as keyword args
            # for forward-compatibility
            kwargs = dict(args=args, username=session.username)
            try:
                return type(self).get_password(**kwargs)
            except NotImplementedError:
                # Call the default implementation
                return super_get_password()

        session.get_password = lambda: session_get_password(session)

    @classmethod
    def execute_from_command_line(cls):
        parser = cls.get_argument_parser()
        args = parser.parse_args()
        blackboard.configure_logging(quiet=args.quiet)

        not_implemented = []
        try:
            try:
                course = cls.get_course(args)
            except NotImplementedError:
                not_implemented.append('Grading.get_course')
            try:
                username = cls.get_username(args)
            except NotImplementedError:
                not_implemented.append('Grading.get_username')
        except Exception as exn:
            parser.error(str(exn))
        if not_implemented:
            parser.error("You must implement %s" %
                         ' and '.join(not_implemented))

        session = cls.session_class('cookies.txt', username, course)
        grading = cls(session)
        grading.override_get_password(args)
        try:
            grading.load('grading.json')
            grading.main(args, session, grading)
        except ParserError as exn:
            logger.error("Parsing error")
            print(exn)
            exn.save()
        except BadAuth:
            logger.error("Bad username or password. Forgetting password.")
            session.forget_password()
        except Exception:
            logger.exception("Uncaught exception")
        else:
            grading.save('grading.json')
        session.save_cookies()

    @classmethod
    def init(cls):
        course = cls.get_course(None)
        username = cls.get_username(None)
        cookiejar = 'cookies.txt'
        dbpath = 'grading.json'
        session = cls.session_class(cookiejar, username, course)
        grading = cls(session)
        grading.load(dbpath)
        return grading
